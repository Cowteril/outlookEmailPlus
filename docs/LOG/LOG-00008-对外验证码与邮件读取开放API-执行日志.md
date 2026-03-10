# LOG-00008｜对外验证码与邮件读取开放 API — 执行日志

## 目标

- 在不破坏现有内部接口的前提下，实现 `/api/external/*` 开放接口（仅 `X-API-Key` 鉴权）
- 按既有测试用例驱动落地实现，并通过全量回归测试

## 执行记录（2026-03-08）

### 1) Settings 接入 external_api_key + API Key 鉴权

- 新增 settings 仓库能力：
  - `get_external_api_key()`：读取并自动解密（兼容明文历史数据）
  - `get_external_api_key_masked()`：脱敏展示
- 扩展 `GET /api/settings` 返回：
  - `external_api_key_set`
  - `external_api_key_masked`
- 扩展 `PUT /api/settings` 支持保存/清空 `external_api_key`（加密存储，不回显明文）
- 新增 `api_key_required()`：
  - Header 仅接受 `X-API-Key`
  - 未配置 `external_api_key` → `403 API_KEY_NOT_CONFIGURED`
  - 缺失/错误 → `401 UNAUTHORIZED`
- 数据库初始化补齐默认 setting：`external_api_key=""`（幂等）

验证：
- `python -m unittest tests.test_settings_external_api_key -v` ✅

### 2) 参数化验证码/验证链接提取器

- 在 `verification_extractor.py` 新增 `extract_verification_info_with_options()`：
  - `code_regex`：自定义正则优先
  - `code_length`：如 `6-6`（仅数字验证码）
  - `code_source`：`subject/content/html/all`
  - 验证链接优先关键词：`verify/confirm/activate/validation`
- 返回增强字段：
  - `verification_link`
  - `match_source`
  - `confidence`

验证：
- `python -m unittest tests.test_verification_extractor_options -v` ✅

### 3) 开放 API（/api/external/*）落地

- 新增 `outlook_web/services/external_api.py` 作为开放接口编排层：
  - `ok()/fail()` 统一响应结构
  - 自定义异常统一映射错误码与 HTTP 状态码
  - Graph → IMAP(New) → IMAP(Old) 回退（列表/详情）
  - `wait-message` 轮询实现（最大超时 120 秒，sleep 可被 mock）
  - 访问审计：写入 `audit_logs(resource_type="external_api")`
- 注册路由：
  - `outlook_web/routes/system.py`：`/api/external/health|capabilities|account-status`
  - `outlook_web/routes/emails.py`：`/api/external/messages|messages/latest|messages/{id}|raw|verification-code|verification-link|wait-message`
- 控制器实现：
  - `outlook_web/controllers/system.py`
  - `outlook_web/controllers/emails.py`
- 补齐 RAW 内容：
  - Outlook OAuth IMAP（XOAUTH2）详情返回 `raw_content`
  - 标准 IMAP(Generic) 详情返回 `raw_content`

验证：
- `python -m unittest tests.test_external_api -v` ✅

### 4) 全量回归

验证：
- `python -m unittest discover -s tests -v` ✅（253 tests）

---

## 执行记录（2026-03-09）

### 5) 对齐 OpenAPI/PRD：System 接口返回字段补齐

- `GET /api/external/capabilities`
  - 补齐 `version` 字段（与 OpenAPI `CapabilitiesData.required=[service, version, features]` 对齐）
- `GET /api/external/account-status`
  - 补齐 `account_type` / `provider` / `can_read`
  - 增强 `email` 参数校验：为空或不包含 `@` → `400 INVALID_PARAM`
- 补齐 OpenAPI 文档：`HealthData` 增加 `version`（与 PRD “健康检查返回版本号” 对齐）

验证：
- `python -m unittest tests.test_external_api.ExternalApiSystemTests -v` ✅
- `python -m unittest tests.test_external_api -v` ✅
- `python -m unittest tests.test_settings_external_api_key -v` ✅
- `python -m unittest tests.test_verification_extractor_options -v` ✅
- `python -m unittest discover -s tests -v` ✅（253 tests）

### 6) 前端设置页集成 external_api_key（UI 配置闭环）

- `templates/index.html`
  - 设置页新增“对外开放 API Key”输入框（不回显明文，仅用于写入/清空）
- `static/js/main.js`
  - `loadSettings()` 使用 `*_api_key_masked` 回填脱敏值，并记录 `dataset.maskedValue/isSet`
  - `saveSettings()` 避免把脱敏占位符写回 DB；外部 API Key 支持清空禁用
- `outlook_web/controllers/settings.py`
  - `PUT /api/settings` 对 `gptmail_api_key` / `external_api_key` 增加“脱敏占位符不覆盖”保护
  - `gptmail_api_key` 支持清空（与前端行为一致）

验证：
- `python -m unittest discover -s tests -v` ✅（256 tests）

### 7) 手工冒烟测试（启动服务验证端到端链路）

启动方式（禁用调度器自启 + 使用临时 DB，避免污染本地 `data/`）：

```powershell
$env:SECRET_KEY="test-secret-key-32bytes-minimum-0000000000000000"
$env:LOGIN_PASSWORD="testpass123"
$env:SCHEDULER_AUTOSTART="false"
$env:DATABASE_PATH=(Join-Path $env:TEMP "outlookEmail-manual-smoke.db")
python -m flask --app web_outlook_app run --host 127.0.0.1 --port 5055
```

验证步骤（均通过）：
- 登录：`POST /login` → 200
- 获取 CSRF：`GET /api/csrf-token` → 200
- 写入对外 API Key：`PUT /api/settings {"external_api_key":"abc123"}` → 200
- 读取设置脱敏：`GET /api/settings` → `external_api_key_set=true` 且 `external_api_key_masked` 非明文
- 外部健康检查：`GET /api/external/health`（Header `X-API-Key: abc123`）→ 200 `code=OK`

## 执行记录（2026-03-10）

### 8) 对齐 PRD 语义偏差并补强回归用例

- 修复 `verification-code` / `verification-link`
  - 未显式传入 `since_minutes` 时，默认按 PRD 使用最近 `10` 分钟窗口
  - 避免命中过期历史验证码/历史验证链接
- 修复 `wait-message`
  - 由“存在匹配邮件即返回”改为“仅当调用开始后出现的新邮件才返回”
  - 保留超时上限 `120` 秒与同步轮询实现
- 修复 Graph 链路 RAW 内容
  - 新增 Graph MIME 读取函数，优先使用 `/me/messages/{id}/$value`
  - `messages/{id}` 与 `messages/{id}/raw` 在 Graph 成功时返回真实 MIME 内容，而非仅正文
- 补齐审计日志闭环
  - 新增 `/api/external/messages/{id}/raw`
  - 新增 `/api/external/health`
  - 新增 `/api/external/capabilities`
  - 新增 `/api/external/account-status`
- 补充回归测试
  - `messages/latest` 筛选与最新命中
  - `verification-*` 默认 10 分钟窗口
  - `wait-message` 仅返回新邮件
  - Graph RAW 内容与外部审计日志写入

验证：
- `python -m unittest tests.test_external_api -v` ✅
- `python -m unittest tests.test_settings_external_api_key -v` ✅
- `python -m unittest tests.test_verification_extractor_options -v` ✅
- `python -m unittest discover -s tests -v` ✅（256 tests）
