# FD-00007｜Telegram 实时推送 — 功能实现设计文档

## 文档信息

- **文档编号**: FD-00007
- **创建日期**: 2026-03-04
- **版本**: V1.0
- **状态**: 草案
- **对齐 PRD**: `docs/PRD/PRD-00007-Telegram实时推送.md`
- **前置 FD**: `docs/FD/FD-00005-多邮箱统一管理.md`
- **覆盖范围**: 后端（DB + Repository + Service + Controller + Scheduler）+ 前端（设置页 + 账号列表）

---

## 一、功能概述

### 1.1 设计目标

在**不存储任何邮件内容**的前提下，通过时间游标轮询实现新邮件 Telegram 实时推送：

1. 新增全局 Telegram 配置（Bot Token + Chat ID + 轮询间隔），存入现有 `settings` 表
2. 每个账号独立开关（`telegram_push_enabled`），游标（`telegram_last_checked_at`）存入 `accounts` 表
3. 调度器新增独立 job，读取邮件、推送、丢弃内容，仅更新游标
4. 前端账号列表新增开关按钮，设置页新增 Telegram 配置区块

### 1.2 核心约束

1. **不存储邮件内容**：轮询读取后直接丢弃，不写入任何新表或现有表
2. **不改变现有调度器行为**：Token 刷新 job 不受影响
3. **不改变现有 API 路由**：新增 `/api/accounts/<id>/telegram-toggle`，不修改现有端点响应结构
4. **Bot Token 加密**：使用现有 `encrypt_value` / `decrypt_value` 机制

### 1.3 Out of Scope

- Webhook 外发、其他推送渠道
- 过滤规则引擎
- 邮件内容本地缓存

---

## 二、后端改造总览

### 2.1 变更文件清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `outlook_web/db.py` | **修改** | schema migration：accounts 表新增 2 列，schema version 4 |
| `outlook_web/repositories/accounts.py` | **修改** | 新增 `toggle_telegram_push()`、`update_telegram_cursor()`、`get_telegram_push_accounts()` |
| `outlook_web/repositories/settings.py` | **修改** | 新增 Telegram 相关 settings key 的读写支持 |
| `outlook_web/controllers/accounts.py` | **修改** | 新增 `api_telegram_toggle()` 端点处理函数 |
| `outlook_web/controllers/settings.py` | **修改** | 新增 Telegram 配置字段的读取/保存/脱敏处理 |
| `outlook_web/routes/accounts.py` | **修改** | 注册 `/api/accounts/<id>/telegram-toggle` 路由 |
| `outlook_web/services/telegram_push.py` | **新增** | 核心推送服务：轮询、构造消息、发送 |
| `outlook_web/services/scheduler.py` | **修改** | 新增 `telegram_push_job`，注册到调度器 |
| `templates/partials/settings_modal.html`（或对应设置模板） | **修改** | 新增 Telegram 配置区块 |
| `static/js/features/accounts.js` | **修改** | 新增 Telegram 开关按钮渲染与点击逻辑 |
| `static/js/features/settings.js`（或对应 JS） | **修改** | 新增 Telegram 配置的读取/保存逻辑 |

### 2.2 不变更的文件

| 文件 | 原因 |
|------|------|
| `outlook_web/routes/settings.py` | 设置路由不变，复用现有 GET/PUT /api/settings |
| `outlook_web/security/*` | 安全机制不变 |
| `outlook_web/services/providers.py` | 无需改动 |
| `outlook_web/services/gptmail.py` | 无关 |

---

## 三、数据库变更

### 3.1 Schema Migration（version 3 → 4）

**文件**：`outlook_web/db.py`

在 `_migrate()` 函数中新增 version 4 迁移：

```python
if current_version < 4:
    # 新增 Telegram 推送相关列
    cursor.execute("""
        ALTER TABLE accounts
        ADD COLUMN telegram_push_enabled INTEGER NOT NULL DEFAULT 0
    """)
    cursor.execute("""
        ALTER TABLE accounts
        ADD COLUMN telegram_last_checked_at TEXT DEFAULT NULL
    """)
    cursor.execute("UPDATE schema_migrations SET version = 4")
    conn.commit()
```

**常量更新**：

```python
DB_SCHEMA_VERSION = 4  # 原值 3
```

### 3.2 Settings 表新增 Keys

不需要 DDL，复用现有 key-value `settings` 表：

| Key | 默认值 | 类型 | 说明 |
|-----|--------|------|------|
| `telegram_bot_token` | `""` | 字符串（加密存储） | Telegram Bot Token |
| `telegram_chat_id` | `""` | 字符串（明文） | 接收推送的 Chat ID |
| `telegram_poll_interval` | `"600"` | 字符串（整数秒） | 轮询间隔，10–86400 |

---

## 四、Repository 层

### 4.1 `outlook_web/repositories/accounts.py` 新增函数

```python
def toggle_telegram_push(account_id: int, enabled: bool) -> bool:
    """
    切换账号的 Telegram 推送开关。
    首次开启（enabled=True 且 last_checked_at IS NULL）时，
    同时将 telegram_last_checked_at 设为当前 UTC 时间（防首次轰炸）。
    返回操作是否成功（账号存在则 True）。
    """

def update_telegram_cursor(account_id: int, checked_at: str) -> None:
    """
    更新账号的 telegram_last_checked_at 游标。
    checked_at 为 ISO8601 UTC 字符串（如 "2026-03-04T14:30:00"）。
    """

def get_telegram_push_accounts() -> List[dict]:
    """
    返回所有 telegram_push_enabled=1 的账号列表。
    字段：id, email, provider, refresh_token(加密), imap_host, imap_port,
          imap_password(加密), telegram_last_checked_at
    """
```

### 4.2 `outlook_web/repositories/settings.py` 新增辅助函数

```python
TELEGRAM_KEYS = {"telegram_bot_token", "telegram_chat_id", "telegram_poll_interval"}
TELEGRAM_SENSITIVE_KEYS = {"telegram_bot_token"}  # 需加密存储 + 脱敏返回

def get_telegram_settings() -> dict:
    """返回 telegram 相关配置，bot_token 脱敏处理（仅显示后4位）"""

def save_telegram_settings(bot_token: str | None, chat_id: str | None, poll_interval: int | None) -> None:
    """保存 telegram 配置，bot_token 加密存储"""
```

---

## 五、Service 层

### 5.1 新增 `outlook_web/services/telegram_push.py`

#### 5.1.1 模块职责

- 连接 IMAP/Graph 读取新邮件列表
- 构造 Telegram HTML 格式消息
- 调用 Telegram Bot API 发送消息
- **不**存储任何邮件内容

#### 5.1.2 核心函数签名

```python
def run_telegram_push_job(app) -> None:
    """
    主入口，由调度器调用。
    接收 Flask app 对象以在应用上下文中操作数据库。
    """

def _fetch_new_emails_imap(account: dict, since: str) -> List[dict]:
    """
    通过 IMAP 获取 received_at > since 的邮件。
    返回字段：subject, sender, received_at, preview（正文前 200 字纯文本）
    since: ISO8601 UTC 字符串
    最多返回 50 封（本地截断，由全局上限 20 进一步限制）
    """

def _fetch_new_emails_graph(account: dict, since: str) -> List[dict]:
    """
    通过 Microsoft Graph API 获取 received_at > since 的邮件。
    返回字段同上。
    """

def _build_telegram_message(account_email: str, email: dict) -> str:
    """
    构造 Telegram HTML 消息文本。
    格式见 PRD §3.4。
    """

def _send_telegram_message(bot_token: str, chat_id: str, text: str) -> bool:
    """
    调用 Telegram sendMessage API。
    超时 10 秒，失败返回 False（不抛异常）。
    """

def _html_to_plain(html: str) -> str:
    """将 HTML 正文提取为纯文本（strip tags），用于预览截取。"""
```

#### 5.1.3 主流程伪码

```python
def run_telegram_push_job(app):
    with app.app_context():
        # 1. 获取配置
        bot_token = decrypt(get_setting("telegram_bot_token"))
        chat_id = get_setting("telegram_chat_id")
        if not bot_token or not chat_id:
            return

        # 2. 获取启用推送的账号
        accounts = get_telegram_push_accounts()
        if not accounts:
            return

        job_start_time = utcnow_isoformat()
        sent_count = 0
        MAX_SENT = 20

        # 3. 遍历账号
        for account in accounts:
            if sent_count >= MAX_SENT:
                break

            last_checked = account["telegram_last_checked_at"]

            # 首次开启：设游标为当前时间，跳过本轮
            if last_checked is None:
                update_telegram_cursor(account["id"], job_start_time)
                continue

            try:
                # 4. 拉取新邮件
                # 注意：toggle_telegram_push() 在首次开启时已设游标，此处 last_checked 不会为 None
                if account["provider"] == "outlook":
                    emails = _fetch_new_emails_graph(account, last_checked)
                else:
                    emails = _fetch_new_emails_imap(account, last_checked)

                # 5. 推送（按时间升序）
                for email in sorted(emails, key=lambda e: e["received_at"]):
                    if sent_count >= MAX_SENT:
                        break
                    msg = _build_telegram_message(account["email"], email)
                    _send_telegram_message(bot_token, chat_id, msg)
                    sent_count += 1

            except Exception as e:
                logger.warning(f"[telegram_push] account={account['email']} error: {e}")

            finally:
                # 6. 无论成功/失败，更新游标
                update_telegram_cursor(account["id"], job_start_time)
```

### 5.2 修改 `outlook_web/services/scheduler.py`

#### 5.2.1 新增 Job 注册

在 `start_scheduler(app)` 函数中新增：

```python
from outlook_web.services.telegram_push import run_telegram_push_job
from outlook_web.repositories.settings import get_setting

def _get_telegram_interval():
    try:
        return max(10, int(get_setting("telegram_poll_interval") or "600"))
    except Exception:
        return 600

scheduler.add_job(
    func=run_telegram_push_job,
    args=[app],
    trigger="interval",
    seconds=_get_telegram_interval(),
    id="telegram_push_job",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)
```

#### 5.2.2 Settings 变更时重启 Job

当 `PUT /api/settings` 保存了 `telegram_poll_interval` 时，重新调度 `telegram_push_job`（参照现有 `refresh_cron` 的动态重调度实现）。

---

## 六、Controller 层

### 6.1 新增 `api_telegram_toggle(account_id)`

**文件**：`outlook_web/controllers/accounts.py`

```python
@login_required
def api_telegram_toggle(account_id: int):
    """
    POST /api/accounts/<id>/telegram-toggle
    Body: {"enabled": true/false}
    Response: {"success": true, "enabled": <bool>, "message": "..."}
    """
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get("enabled", False))
    success = toggle_telegram_push(account_id, enabled)
    if not success:
        return jsonify({"success": False, "message": "账号不存在"}), 404
    action = "开启" if enabled else "关闭"
    audit_log(f"Telegram推送{action}", account_id=account_id)
    return jsonify({"success": True, "enabled": enabled, "message": f"Telegram推送已{action}"})
```

### 6.2 修改 `outlook_web/controllers/settings.py`

**GET `/api/settings`**：在返回的 settings dict 中新增 telegram 相关字段（bot_token 脱敏）。

**PUT `/api/settings`**：新增对 `telegram_bot_token`、`telegram_chat_id`、`telegram_poll_interval` 的校验与保存：
- `telegram_poll_interval`：整数，范围 10–86400，默认 600
- `telegram_bot_token`：字符串，非空时加密存储
- `telegram_chat_id`：字符串，格式宽松（数字或 `@channel`）

保存 `telegram_poll_interval` 后，触发调度器重调度（注意传入真实 Flask app 实例，避免 LocalProxy 被 scheduler job 长期持有）。

---

## 七、路由层

### 7.1 修改 `outlook_web/routes/accounts.py`

```python
from outlook_web.controllers.accounts import api_telegram_toggle

accounts_bp.add_url_rule(
    "/api/accounts/<int:account_id>/telegram-toggle",
    view_func=api_telegram_toggle,
    methods=["POST"],
)
```

---

## 八、前端改造

### 8.1 账号列表：Telegram 开关按钮

**文件**：`static/js/features/accounts.js`

在账号行的操作按钮区域（删除/编辑等按钮旁）新增 Telegram 开关按钮：

```html
<!-- telegram_push_enabled = 0 时 -->
<button class="btn-icon telegram-toggle" data-id="{{id}}" data-enabled="0"
        title="开启 Telegram 推送" aria-label="开启 Telegram 推送">
  🔔
</button>

<!-- telegram_push_enabled = 1 时 -->
<button class="btn-icon telegram-toggle active" data-id="{{id}}" data-enabled="1"
        title="关闭 Telegram 推送（当前已开启）" aria-label="关闭 Telegram 推送">
  🔔
</button>
```

**点击逻辑**：

```javascript
async function toggleTelegramPush(accountId, currentEnabled) {
    const newEnabled = !currentEnabled;
    const resp = await fetch(`/api/accounts/${accountId}/telegram-toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
        body: JSON.stringify({ enabled: newEnabled }),
    });
    const data = await resp.json();
    if (data.success) {
        showToast(data.message);
        refreshAccountRow(accountId, { telegram_push_enabled: newEnabled ? 1 : 0 });
    } else {
        showToast(data.message || "操作失败", "error");
    }
}
```

**样式**：开启状态下按钮高亮（`.active` 类，蓝色或橙色）。

### 8.2 设置页：Telegram 配置区块

**位置**：在设置页新增「📬 Telegram 推送」折叠区块或独立卡片，包含：

```html
<div class="settings-section" id="telegramSection">
  <h3>📬 Telegram 推送</h3>
  <div class="form-group">
    <label>Bot Token</label>
    <input type="password" id="telegramBotToken" placeholder="留空表示不修改（已配置时显示脱敏值）" />
  </div>
  <div class="form-group">
    <label>Chat ID</label>
    <input type="text" id="telegramChatId" placeholder="如：-1001234567890 或 @mychannel" />
  </div>
  <div class="form-group">
    <label>轮询间隔（秒）</label>
    <input type="number" id="telegramPollInterval" min="10" max="86400" value="600" />
    <span class="hint">10–86400，默认 600（10 分钟）</span>
  </div>
  <button id="saveTelegramSettings">保存 Telegram 设置</button>
  <button id="testTelegramSettings">发送测试消息</button>
</div>
```

**「发送测试消息」按钮**（可选，P1）：调用后端发一条测试消息到 Telegram，验证配置是否正确。

---

## 九、IMAP 读取邮件实现细节

### 9.1 IMAP SEARCH 实现

```python
import imaplib, email
from datetime import datetime, timezone

def _fetch_new_emails_imap(account: dict, since: str) -> List[dict]:
    since_dt = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
    # IMAP SEARCH 日期格式：DD-Mon-YYYY
    since_imap = since_dt.strftime("%d-%b-%Y")

    imap = imaplib.IMAP4_SSL(account["imap_host"], account.get("imap_port", 993))
    imap.login(account["email"], decrypt(account["imap_password"]))
    imap.select("INBOX")

    _, msg_ids = imap.search(None, f'SINCE {since_imap}')
    result = []
    for mid in (msg_ids[0].split() or [])[-50:]:  # 最多取最近 50 封
        _, data = imap.fetch(mid, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])
        received_at = _parse_email_date(msg["Date"])
        if received_at <= since_dt:
            continue  # IMAP SEARCH 精度到天，需二次过滤
        result.append({
            "subject": _decode_header(msg["Subject"]),
            "sender": msg["From"],
            "received_at": received_at.isoformat(),
            "preview": _extract_preview(msg, 200),
        })
    imap.logout()
    return result
```

**注意**：IMAP `SEARCH SINCE` 精度到天，需在代码层面做二次精确过滤（`received_at > since_dt`）。

### 9.2 Graph API 实现

```python
def _fetch_new_emails_graph(account: dict, since: str) -> List[dict]:
    """
    使用 Microsoft Graph API 获取新邮件。
    复用现有 token refresh 逻辑：调用 outlook_web/services/token_refresh.py 中的
    get_valid_access_token(account) 或等效函数获取有效 access_token。
    """
    from outlook_web.services.token_refresh import get_valid_access_token  # 实现时确认实际模块路径
    access_token = get_valid_access_token(account)
    url = "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages"
    params = {
        "$filter": f"receivedDateTime gt {since}Z",
        "$select": "subject,from,receivedDateTime,bodyPreview",
        "$top": 50,
        "$orderby": "receivedDateTime asc",
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    messages = resp.json().get("value", [])
    return [{
        "subject": m.get("subject", ""),
        "sender": m.get("from", {}).get("emailAddress", {}).get("address", ""),
        "received_at": m.get("receivedDateTime", ""),
        "preview": (m.get("bodyPreview", "") or "")[:200],
    } for m in messages]
```

---

## 十、消息构造

### 10.1 `_build_telegram_message()` 实现

```python
def _build_telegram_message(account_email: str, email: dict) -> str:
    def esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    lines = [
        "📬 <b>新邮件通知</b>",
        "",
        f"账户：<code>{esc(account_email)}</code>",
        f"发件人：<code>{esc(email.get('sender', ''))}</code>",
        f"主题：{esc(email.get('subject', '（无主题）'))}",
        f"时间：{email.get('received_at', '')[:16].replace('T', ' ')}",
    ]
    preview = (email.get("preview") or "").strip()
    if preview:
        if len(preview) > 200:
            preview = preview[:200] + "..."
        lines += ["", "内容预览：", esc(preview)]

    text = "\n".join(lines)
    if len(text) > 4096:
        text = text[:4092] + "..."
    return text
```

---

## 十一、安全考量

| 方面 | 实现 |
|------|------|
| Bot Token 存储 | 使用 `encrypt_value()` 加密后存入 `settings` 表，API 返回时仅显示 `****xxxx`（后4位） |
| IMAP 密码 | 复用现有加密机制，不新增处理逻辑 |
| Graph Token | 复用现有 token refresh，access_token 不落库 |
| 日志脱敏 | 日志中不打印 bot_token、imap_password、refresh_token |

---

## 十二、测试要点

| 测试类型 | 覆盖点 |
|----------|--------|
| 单元测试 | `_build_telegram_message()`、`_html_to_plain()`、消息截断、HTML 转义 |
| 单元测试 | `toggle_telegram_push()` 首次开启游标设置逻辑 |
| 集成测试 | `api_telegram_toggle` 端点（开启/关闭/账号不存在） |
| 集成测试 | `PUT /api/settings` 保存 telegram 配置（合法/非法值） |
| Mock 测试 | `run_telegram_push_job()`：Bot 未配置跳过、首次开启跳过、全局上限 20 封、IMAP 异常静默 |
| 回归测试 | Token 刷新调度器不受影响 |
