# TODO-00007｜Telegram 实时推送 — 任务待办清单

- **文档状态**: 草案
- **版本**: V1.0
- **日期**: 2026-03-04
- **对齐 PRD**: `docs/PRD/PRD-00007-Telegram实时推送.md`
- **对齐 FD**: `docs/FD/FD-00007-Telegram实时推送.md`

---

## 前置准备

### 0.1 文档确认

- [ ] PRD 已完成（`docs/PRD/PRD-00007-Telegram实时推送.md`）
- [ ] FD 已完成（`docs/FD/FD-00007-Telegram实时推送.md`）
- [ ] 阅读并理解所有约束条款与边界情况（特别是：不存邮件内容、防轰炸、全局 20 封上限）

### 0.2 环境准备

- [ ] 确认开发环境正常（Python/Flask/SQLite）
- [ ] 安装依赖：`pip install -r requirements.txt`（如新增依赖则先更新）
- [ ] 准备测试用 Telegram Bot（从 BotFather 创建，获取 Token + Chat ID）

### 0.3 基线测试（改动前必做）

- [ ] 运行现有测试：`python -m unittest discover -s tests -v`
- [ ] 记录当前测试通过数量（作为基线）
- [ ] 手动验证核心链路无回归：账号管理、Token 刷新、导入导出

---

## P0（必须完成）

---

### 阶段 1：数据库 Schema 迁移

**目标**：`accounts` 表新增 2 列，schema version 3 → 4。  
**涉及文件**：`outlook_web/db.py`

#### 1.1 `outlook_web/db.py` — 迁移逻辑

- [ ] 将 `DB_SCHEMA_VERSION` 从 `3` 改为 `4`
- [ ] 在 `_migrate()` 中新增 version 4 迁移块：
  ```python
  if current_version < 4:
      cursor.execute("ALTER TABLE accounts ADD COLUMN telegram_push_enabled INTEGER NOT NULL DEFAULT 0")
      cursor.execute("ALTER TABLE accounts ADD COLUMN telegram_last_checked_at TEXT DEFAULT NULL")
      cursor.execute("UPDATE schema_migrations SET version = 4")
      conn.commit()
  ```
- [ ] 确认迁移幂等（多次执行不报错）
- [ ] 启动应用验证迁移正常执行，`accounts` 表有新列

---

### 阶段 2：Repository 层扩展

**目标**：新增账号 Telegram 开关/游标操作函数 + Settings 读写辅助。  
**涉及文件**：`outlook_web/repositories/accounts.py`、`outlook_web/repositories/settings.py`

#### 2.1 `outlook_web/repositories/accounts.py`

- [ ] 新增 `toggle_telegram_push(account_id: int, enabled: bool) -> bool`
  - 首次开启（`enabled=True` 且 `last_checked_at IS NULL`）时，同时将游标设为当前 UTC 时间
  - 账号不存在返回 `False`
- [ ] 新增 `update_telegram_cursor(account_id: int, checked_at: str) -> None`
  - `checked_at` 为 ISO8601 UTC 字符串
- [ ] 新增 `get_telegram_push_accounts() -> List[dict]`
  - 查询 `telegram_push_enabled = 1` 的所有账号
  - 返回字段：`id, email, provider, refresh_token, imap_host, imap_port, imap_password, telegram_last_checked_at`

#### 2.2 `outlook_web/repositories/settings.py`

- [ ] 确认现有 `get_setting(key)` / `set_setting(key, value)` 可直接复用（无需新增函数）
- [ ] 确认 `telegram_bot_token` 存储时可通过现有加密机制处理

---

### 阶段 3：核心推送服务

**目标**：实现轮询 + 推送的核心逻辑，不存储任何邮件内容。  
**涉及文件**：`outlook_web/services/telegram_push.py`（新建）

#### 3.1 新建 `outlook_web/services/telegram_push.py`

- [ ] 实现 `_html_to_plain(html: str) -> str`（strip HTML tags，提取纯文本）
- [ ] 实现 `_build_telegram_message(account_email: str, email: dict) -> str`
  - 格式：账户 + 发件人 + 主题 + 时间 + 正文预览（前 200 字）
  - HTML 转义（`&` `<` `>`）
  - 总长度超 4096 字符时截断
- [ ] 实现 `_send_telegram_message(bot_token: str, chat_id: str, text: str) -> bool`
  - 调用 `https://api.telegram.org/bot{token}/sendMessage`
  - `parse_mode=HTML`，`disable_web_page_preview=True`
  - 超时 10 秒，失败返回 `False`，不抛异常
- [ ] 实现 `_fetch_new_emails_imap(account: dict, since: str) -> List[dict]`
  - IMAP4_SSL 连接，SEARCH SINCE，代码层二次过滤精确到秒
  - 最多返回 50 封
  - 返回字段：`subject, sender, received_at, preview`
  - 完成后 logout，连接超时 15 秒
- [ ] 实现 `_fetch_new_emails_graph(account: dict, since: str) -> List[dict]`
  - Graph API `$filter=receivedDateTime gt {since}Z`，`$top=50`
  - 复用现有 access_token 获取/刷新逻辑
  - 返回字段同上
- [ ] 实现 `run_telegram_push_job(app) -> None`（主入口）
  - 步骤详见 FD §5.1.3
  - 全局上限 20 封
  - 首次开启跳过（游标为 None → 设为当前时间）
  - 无论成功/失败，每个账号游标都更新为本轮 `job_start_time`
  - 所有异常 try/except 静默，记录 warning 日志

---

### 阶段 4：调度器集成

**目标**：将 `telegram_push_job` 注册到现有 APScheduler，支持动态更新间隔。  
**涉及文件**：`outlook_web/services/scheduler.py`

#### 4.1 `outlook_web/services/scheduler.py`

- [ ] 在 `start_scheduler(app)` 中新增 `telegram_push_job` 注册：
  - `trigger="interval"`，`seconds=_get_telegram_interval()`
  - `max_instances=1`，`coalesce=True`，`replace_existing=True`
- [ ] 实现 `_get_telegram_interval() -> int`：读取 `telegram_poll_interval` setting，默认 600，最小 10
- [ ] 确认调度器重启不影响现有 Token 刷新 job

---

### 阶段 5：Controller + Route 层

**目标**：新增 `telegram-toggle` API 端点，以及 settings 层对 Telegram 配置的读写支持。  
**涉及文件**：`outlook_web/controllers/accounts.py`、`outlook_web/controllers/settings.py`、`outlook_web/routes/accounts.py`

#### 5.1 `outlook_web/controllers/accounts.py`

- [ ] 新增 `api_telegram_toggle(account_id: int)` 函数
  - 装饰器：`@login_required`
  - 读取 body `{"enabled": true/false}`
  - 调用 `toggle_telegram_push()`
  - 写审计日志
  - 返回 `{"success": true, "enabled": bool, "message": "..."}`
  - 账号不存在返回 404

#### 5.2 `outlook_web/routes/accounts.py`

- [ ] 注册路由：`POST /api/accounts/<int:account_id>/telegram-toggle` → `api_telegram_toggle`

#### 5.3 `outlook_web/controllers/settings.py`

- [ ] GET `/api/settings`：返回值新增 `telegram_bot_token`（脱敏，只显示 `****` + 后4位）、`telegram_chat_id`、`telegram_poll_interval`
- [ ] PUT `/api/settings`：新增对 3 个 telegram key 的处理：
  - `telegram_poll_interval`：校验 10 ≤ value ≤ 86400，转为字符串存储
  - `telegram_bot_token`：非空时加密存储；空字符串时清空
  - `telegram_chat_id`：字符串直接存储
  - 保存后触发调度器重调度 `telegram_push_job`

---

### 阶段 6：前端改造

**目标**：账号列表新增推送开关按钮；设置页新增 Telegram 配置区块。  
**涉及文件**：`static/js/features/accounts.js`、设置相关模板/JS

#### 6.1 账号列表开关按钮

- [ ] 在账号行操作区新增 Telegram 开关按钮（🔔 图标）
- [ ] 开启状态下按钮高亮（`.active` 样式）
- [ ] 点击调用 `POST /api/accounts/<id>/telegram-toggle`
- [ ] 成功后更新按钮状态，显示 toast 提示
- [ ] 全局未配置 Bot Token 时，开启操作给出友情提示（「请先在设置页配置 Telegram Bot Token」）

#### 6.2 设置页 Telegram 配置区块

- [ ] 在设置模态框/设置页新增「📬 Telegram 推送」区块
- [ ] 包含：Bot Token 输入框（password 类型）、Chat ID 输入框、轮询间隔输入框（10–86400）
- [ ] 页面加载时读取当前配置值（bot_token 显示脱敏值）
- [ ] 「保存」按钮：调用现有 `PUT /api/settings`
- [ ] 「发送测试消息」按钮（可选 P1）：新增后端 `POST /api/settings/telegram-test` 端点

---

### 阶段 7：测试

**目标**：新增单元测试和集成测试，确保功能正确且无回归。  
**涉及文件**：`tests/test_telegram_push.py`（新建）

#### 7.1 新建 `tests/test_telegram_push.py`

- [ ] 测试 `_build_telegram_message()`：
  - 正常邮件（含预览）
  - 正文为空（省略预览区块）
  - 超长消息截断至 4096
  - HTML 转义（`<`, `>`, `&`）
- [ ] 测试 `_html_to_plain()`：HTML 标签剥除
- [ ] 测试 `run_telegram_push_job()`（mock DB + Telegram API）：
  - Bot Token 未配置 → 跳过
  - 无启用推送的账号 → 跳过
  - 首次开启（last_checked_at=None）→ 更新游标，不发消息
  - 正常推送：验证 Telegram API 被调用、游标被更新
  - 全局上限 20 封：超出后不再调用 Telegram API
  - IMAP 异常 → 静默，游标仍更新
- [ ] 测试 `api_telegram_toggle` 端点：
  - 开启成功
  - 关闭成功
  - 账号不存在 → 404
  - 未登录 → 401/重定向

#### 7.2 回归验证

- [ ] 全量测试通过：`python -m unittest discover -s tests -v`
- [ ] 手动验证：配置真实 Telegram Bot，测试端对端推送
- [ ] 手动验证：Token 刷新调度器正常运行（不受影响）
- [ ] 手动验证：账号列表开关状态正确持久化

---

## P1（优先级次之）

### 发送测试消息按钮

- [ ] 新增 `POST /api/settings/telegram-test` 端点
  - 使用当前配置的 bot_token + chat_id 发送一条测试消息
  - 返回成功/失败及原因
- [ ] 前端「发送测试消息」按钮调用该端点，显示结果

### 动态轮询间隔重调度

- [ ] 保存 `telegram_poll_interval` 后，调用调度器动态更新 job 间隔（无需重启应用）

---

## 发布检查

- [ ] 所有 P0 阶段任务完成
- [ ] 全量测试通过，无回归
- [ ] 手动端对端验收通过（开启推送 → 收到真实 Telegram 通知）
- [ ] 更新 `DEVLOG.md`，版本号升至 `v1.5.0`
- [ ] 提交代码，打 tag `v1.5.0`，推送 GitHub Release
