# TDD-00007｜Telegram 实时推送 — 技术设计细节文档

- **文档编号**: TDD-00007
- **创建日期**: 2026-03-04
- **版本**: V1.0
- **状态**: 草案
- **对齐 PRD**: `docs/PRD/PRD-00007-Telegram实时推送.md`
- **对齐 FD**: `docs/FD/FD-00007-Telegram实时推送.md`
- **前置依赖**: `docs/TDD/TDD-00005-多邮箱统一管理.md`（accounts 表结构、调度器框架）

---

## 目录

1. [文档目的](#1-文档目的)
2. [设计原则与硬约束](#2-设计原则与硬约束)
3. [技术架构与数据流](#3-技术架构与数据流)
4. [数据库变更详设](#4-数据库变更详设)
5. [Repository 层详设](#5-repository-层详设)
6. [核心推送服务详设（telegram_push.py）](#6-核心推送服务详设)
7. [调度器集成详设](#7-调度器集成详设)
8. [Controller 与路由层详设](#8-controller-与路由层详设)
9. [前端改造详设](#9-前端改造详设)
10. [加密与安全实现细节](#10-加密与安全实现细节)
11. [兼容性保障](#11-兼容性保障)
12. [测试策略与测试用例](#12-测试策略与测试用例)

---

## 1. 文档目的

本 TDD 描述 PRD-00007「Telegram 实时推送」的完整技术实现细节，重点回答：

- 如何在**不存储任何邮件内容**的前提下实现 Telegram 推送
- 如何**复用现有代码**（`graph.py`、`scheduler.py`、`security/crypto.py`、`repositories/settings.py`）
- 如何实现**时间游标**防轰炸机制（首次开启不推历史）
- 如何在现有调度器框架中添加**独立 job** 且不影响 Token 刷新 job
- **测试边界情况**：Bot 未配置、全局 20 封上限、IMAP 异常静默处理

---

## 2. 设计原则与硬约束

### 2.1 API 与 DB 硬约束

- **新增 1 条路由**：`POST /api/accounts/<id>/telegram-toggle`（独立端点，不改变现有端点）
- **不新增存储邮件的表**：`accounts` 表仅加 2 列，`settings` 表复用 key-value 存储
- **不存储邮件内容**：`telegram_push.py` 不得有任何 `INSERT INTO` 邮件相关数据

### 2.2 复用现有代码（关键）

| 需求 | 复用的现有函数 | 位置 |
|------|--------------|------|
| 获取 Outlook access_token | `get_access_token_graph(client_id, refresh_token)` | `outlook_web/services/graph.py:78` |
| 读取 Outlook 邮件 | `get_emails_graph(client_id, refresh_token, folder, skip, top)` | `outlook_web/services/graph.py:86` |
| 加密敏感字段 | `encrypt_data(data: str) -> str` | `outlook_web/security/crypto.py` |
| 解密敏感字段 | `decrypt_data(encrypted: str) -> str` | `outlook_web/security/crypto.py` |
| 读取 settings | `get_setting(key, default="") -> str` | `outlook_web/repositories/settings.py` |
| 写入 settings | `set_setting(key, value) -> bool` | `outlook_web/repositories/settings.py` |
| 注册调度 job | `scheduler.add_job(...)` with `replace_existing=True` | `outlook_web/services/scheduler.py` |

### 2.3 向后兼容原则

- Token 刷新 job（`"token_refresh"`）逻辑不变、调度不受影响
- 现有 `settings` API（GET/PUT `/api/settings`）现有字段行为不变
- 现有账号管理 API 返回结构新增 `telegram_push_enabled` 字段（原有字段不变）

---

## 3. 技术架构与数据流

### 3.1 Telegram 推送数据流

```
APScheduler（每 telegram_poll_interval 秒）
    ↓ 触发
run_telegram_push_job(app)
    ↓ 读取 settings
get_setting("telegram_bot_token")  →  decrypt_data(...)  →  bot_token
get_setting("telegram_chat_id")    →  chat_id
    ↓ 查询启用推送的账号
get_telegram_push_accounts()       →  List[account_dict]
    ↓ 遍历每个账号
    ├─ Outlook 账号
    │   get_emails_graph(client_id, decrypt(refresh_token), top=50)
    │   → client-side 过滤 receivedDateTime > last_checked_at
    │
    └─ IMAP 账号
        imaplib.IMAP4_SSL(imap_host, imap_port)
        login(email, decrypt(imap_password))
        SEARCH SINCE <date> + client-side 精确过滤
    ↓ 遍历每封邮件（sent_count < 20）
_build_telegram_message(account_email, email)
_send_telegram_message(bot_token, chat_id, message)
    ↓ finally（无论成功/失败）
update_telegram_cursor(account_id, job_start_time)
```

### 3.2 Toggle 开关数据流

```
前端点击 🔔 按钮
    ↓
POST /api/accounts/<id>/telegram-toggle  {"enabled": true/false}
    ↓ login_required 验证
api_telegram_toggle(account_id)
    ↓
toggle_telegram_push(account_id, enabled)
    ├─ 首次开启（enabled=True, last_checked_at IS NULL）
    │   → UPDATE SET telegram_push_enabled=1,
    │                telegram_last_checked_at=<utcnow>  ← 防轰炸游标
    └─ 其他情况
        → UPDATE SET telegram_push_enabled=<0/1>
    ↓
{"success": true, "enabled": bool, "message": "..."}
```

---

## 4. 数据库变更详设

### 4.1 迁移代码（`outlook_web/db.py`）

```python
DB_SCHEMA_VERSION = 4  # 原值 3

# 在 _migrate() 函数中新增：
if current_version < 4:
    try:
        cursor.execute(
            "ALTER TABLE accounts ADD COLUMN telegram_push_enabled INTEGER NOT NULL DEFAULT 0"
        )
    except Exception:
        pass  # 列已存在时忽略（兼容重复执行）
    try:
        cursor.execute(
            "ALTER TABLE accounts ADD COLUMN telegram_last_checked_at TEXT DEFAULT NULL"
        )
    except Exception:
        pass
    cursor.execute("UPDATE schema_migrations SET version = 4")
    conn.commit()
    logger.info("[db] migrated to schema version 4")
```

**注意**：SQLite 的 `ALTER TABLE ADD COLUMN` 不支持 `IF NOT EXISTS`，用 try/except 保证幂等。

### 4.2 Settings 表 Key 定义

| Key | 存储方式 | 默认值 | 说明 |
|-----|----------|--------|------|
| `telegram_bot_token` | 加密（`enc:` 前缀） | `""` | 空字符串 = 未配置，不推送 |
| `telegram_chat_id` | 明文 | `""` | 空字符串 = 未配置，不推送 |
| `telegram_poll_interval` | 明文（整数字符串） | `"600"` | 单位：秒；范围：10–86400 |

---

## 5. Repository 层详设

### 5.1 `toggle_telegram_push(account_id, enabled)` — `repositories/accounts.py`

```python
def toggle_telegram_push(account_id: int, enabled: bool) -> bool:
    """
    切换账号的 Telegram 推送开关。
    - enabled=True 且 last_checked_at IS NULL → 同时设游标为当前 UTC 时间（防轰炸）
    - 账号不存在 → 返回 False
    - 成功 → 返回 True
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # 检查账号是否存在
        row = cursor.execute(
            "SELECT id, telegram_last_checked_at FROM accounts WHERE id = ?",
            (account_id,)
        ).fetchone()
        if not row:
            return False

        if enabled and row["telegram_last_checked_at"] is None:
            # 首次开启：设防轰炸游标
            from datetime import datetime, timezone
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            cursor.execute(
                "UPDATE accounts SET telegram_push_enabled = 1, "
                "telegram_last_checked_at = ? WHERE id = ?",
                (now_iso, account_id)
            )
        else:
            cursor.execute(
                "UPDATE accounts SET telegram_push_enabled = ? WHERE id = ?",
                (1 if enabled else 0, account_id)
            )
        conn.commit()
        return True
```

### 5.2 `update_telegram_cursor(account_id, checked_at)` — `repositories/accounts.py`

```python
def update_telegram_cursor(account_id: int, checked_at: str) -> None:
    """
    更新游标 telegram_last_checked_at。
    checked_at: ISO8601 UTC 字符串（如 "2026-03-04T14:30:00"）
    """
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE accounts SET telegram_last_checked_at = ? WHERE id = ?",
            (checked_at, account_id)
        )
        conn.commit()
```

### 5.3 `get_telegram_push_accounts()` — `repositories/accounts.py`

```python
def get_telegram_push_accounts() -> List[dict]:
    """
    返回所有 telegram_push_enabled=1 的账号。
    加密字段（refresh_token, imap_password）以原始加密值返回，
    调用方负责在使用前调用 decrypt_data() 解密。
    """
    with get_db_connection() as conn:
        rows = conn.execute(
            """SELECT id, email, provider, client_id,
                      refresh_token, imap_host, imap_port, imap_password,
                      telegram_last_checked_at
               FROM accounts
               WHERE telegram_push_enabled = 1
                 AND status != 'disabled'
            """
        ).fetchall()
    return [dict(r) for r in rows]
```

**说明**：过滤 `status != 'disabled'` — 已禁用的账号不轮询。

---

## 6. 核心推送服务详设

### 6.1 文件：`outlook_web/services/telegram_push.py`

#### 6.1.1 `_html_to_plain(html: str) -> str`

用途：将 HTML 正文提取为纯文本，供预览截取。

```python
import re

def _html_to_plain(html: str) -> str:
    """strip HTML tags and collapse whitespace."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
```

#### 6.1.2 `_escape_html(text: str) -> str`

```python
def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )
```

#### 6.1.3 `_build_telegram_message(account_email, email) -> str`

```python
def _build_telegram_message(account_email: str, email: dict) -> str:
    """
    构造 Telegram HTML 格式消息。
    email 字段：subject, sender, received_at（ISO8601）, preview（纯文本，已截取≤200字）
    """
    subject = _escape_html(email.get("subject") or "（无主题）")
    sender  = _escape_html(email.get("sender") or "")
    account = _escape_html(account_email)
    # 时间展示：取前 16 字符 "YYYY-MM-DDTHH:MM" → 替换 T 为空格
    time_raw = (email.get("received_at") or "")[:16].replace("T", " ")

    lines = [
        "📬 <b>新邮件通知</b>",
        "",
        f"账户：<code>{account}</code>",
        f"发件人：<code>{sender}</code>",
        f"主题：{subject}",
        f"时间：{time_raw}",
    ]

    preview = (email.get("preview") or "").strip()
    if preview:
        if len(preview) > 200:
            preview = preview[:200] + "..."
        lines += ["", "内容预览：", _escape_html(preview)]

    text = "\n".join(lines)
    if len(text) > 4096:
        text = text[:4092] + "..."
    return text
```

#### 6.1.4 `_send_telegram_message(bot_token, chat_id, text) -> bool`

```python
import requests

def _send_telegram_message(bot_token: str, chat_id: str, text: str) -> bool:
    """
    调用 Telegram Bot API sendMessage，失败返回 False（不抛异常）。
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if not data.get("ok"):
            import logging
            logging.getLogger(__name__).warning(
                "[telegram_push] api error: %s", resp.text[:200]
            )
            return False
        return True
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("[telegram_push] send failed: %s", exc)
        return False
```

#### 6.1.5 `_fetch_new_emails_graph(account, since_iso) -> List[dict]`

**关键点**：直接复用 `get_emails_graph()`，客户端过滤时间。

```python
from outlook_web.services.graph import get_emails_graph
from outlook_web.security.crypto import decrypt_data
from datetime import datetime, timezone

def _fetch_new_emails_graph(account: dict, since_iso: str) -> List[dict]:
    """
    获取 Outlook 账号的新邮件（received_at > since_iso）。
    复用 get_emails_graph()（不改动 graph.py），客户端二次过滤。
    最多返回 50 封。
    """
    since_dt = datetime.fromisoformat(since_iso).replace(tzinfo=timezone.utc)
    client_id    = account.get("client_id") or ""
    refresh_token = decrypt_data(account.get("refresh_token") or "")

    result = get_emails_graph(
        client_id=client_id,
        refresh_token=refresh_token,
        folder="inbox",
        skip=0,
        top=50,  # 取最新 50 封，邮件按 receivedDateTime desc 排序
    )
    if not result.get("success"):
        raise RuntimeError(f"Graph API error: {result.get('error')}")

    emails = result.get("emails") or []
    output = []
    for m in emails:
        received_raw = m.get("receivedDateTime", "")
        try:
            # Graph API 返回 "2026-03-04T14:30:00Z" 格式
            received_dt = datetime.fromisoformat(
                received_raw.replace("Z", "+00:00")
            )
        except Exception:
            continue
        if received_dt <= since_dt:
            # 由于按 desc 排序，遇到旧邮件后面都是更旧的，提前中断
            break
        sender = (
            (m.get("from") or {})
            .get("emailAddress", {})
            .get("address", "")
        )
        output.append({
            "subject":     m.get("subject", ""),
            "sender":      sender,
            "received_at": received_raw,
            "preview":     (m.get("bodyPreview") or "")[:200],
        })
    return output
```

**注意**：`get_emails_graph()` 按 `receivedDateTime desc` 排序，第一封是最新的。遇到 `received_dt <= since_dt` 时可以 `break`（后面全是更旧的）。

#### 6.1.6 `_fetch_new_emails_imap(account, since_iso) -> List[dict]`

```python
import imaplib
import email as email_lib
from email.header import decode_header as _decode_header_raw

def _fetch_new_emails_imap(account: dict, since_iso: str) -> List[dict]:
    """
    通过 IMAP 获取新邮件（received_at > since_iso）。
    IMAP SEARCH SINCE 精度到天，代码层进行秒级二次过滤。
    最多返回 50 封。连接超时 15 秒。
    """
    since_dt = datetime.fromisoformat(since_iso).replace(tzinfo=timezone.utc)
    imap_host = account.get("imap_host") or ""
    imap_port = int(account.get("imap_port") or 993)
    email_addr = account.get("email") or ""
    imap_password = decrypt_data(account.get("imap_password") or "")

    # IMAP SEARCH SINCE 使用"天"精度，取 since_dt 的日期
    since_imap = since_dt.strftime("%d-%b-%Y")  # e.g. "04-Mar-2026"

    imap = imaplib.IMAP4_SSL(imap_host, imap_port)
    imap.socket().settimeout(15)
    try:
        imap.login(email_addr, imap_password)
        imap.select("INBOX", readonly=True)
        _, msg_ids_raw = imap.search(None, f"SINCE {since_imap}")
        msg_ids = (msg_ids_raw[0].split() if msg_ids_raw and msg_ids_raw[0] else [])

        # 取最近 50 封（IMAP ID 从小到大，取末尾的最新）
        msg_ids = msg_ids[-50:]
        output = []
        for mid in reversed(msg_ids):  # 从新到旧
            _, data = imap.fetch(mid, "(RFC822.HEADER)")
            raw_header = data[0][1] if data and data[0] else b""
            msg = email_lib.message_from_bytes(raw_header)

            # 解析收件时间
            date_str = msg.get("Date", "")
            try:
                from email.utils import parsedate_to_datetime
                received_dt = parsedate_to_datetime(date_str).astimezone(timezone.utc)
            except Exception:
                continue
            if received_dt <= since_dt:
                continue  # 秒级二次过滤

            subject  = _decode_mime_header(msg.get("Subject", ""))
            sender   = msg.get("From", "")
            output.append({
                "subject":     subject,
                "sender":      sender,
                "received_at": received_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "preview":     "",  # IMAP HEADER 模式下无正文，预览为空
            })
            if len(output) >= 50:
                break
        return output
    finally:
        try:
            imap.logout()
        except Exception:
            pass
```

**设计决策**：IMAP 读取使用 `RFC822.HEADER` 而非 `RFC822`，避免下载完整邮件正文（节省带宽，与"不存邮件"原则一致）。因此正文预览始终为空字符串。

**辅助函数**：
```python
def _decode_mime_header(value: str) -> str:
    """解码 MIME encoded-word 格式的邮件头（如 =?UTF-8?B?...?=）"""
    if not value:
        return ""
    parts = _decode_header_raw(value)
    result = []
    for content, charset in parts:
        if isinstance(content, bytes):
            result.append(content.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(content)
    return "".join(result)
```

#### 6.1.7 `run_telegram_push_job(app)` — 主入口

```python
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def run_telegram_push_job(app) -> None:
    """
    调度器主入口。
    在 Flask app context 内运行，确保可访问数据库和配置。
    """
    with app.app_context():
        try:
            _run_telegram_push_job_inner()
        except Exception as e:
            logger.error("[telegram_push] job crashed: %s", e, exc_info=True)


def _run_telegram_push_job_inner() -> None:
    from outlook_web.repositories.settings import get_setting
    from outlook_web.repositories.accounts import (
        get_telegram_push_accounts,
        update_telegram_cursor,
    )
    from outlook_web.security.crypto import decrypt_data

    # 1. 获取配置
    encrypted_token = get_setting("telegram_bot_token", "")
    bot_token = decrypt_data(encrypted_token) if encrypted_token else ""
    chat_id = get_setting("telegram_chat_id", "")

    if not bot_token or not chat_id:
        logger.debug("[telegram_push] skip: bot_token or chat_id not configured")
        return

    # 2. 获取启用推送的账号
    accounts = get_telegram_push_accounts()
    if not accounts:
        return

    job_start_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    sent_count = 0
    MAX_SENT = 20

    # 3. 遍历每个账号
    for account in accounts:
        if sent_count >= MAX_SENT:
            logger.info("[telegram_push] global limit %d reached, stopping", MAX_SENT)
            break

        last_checked = account.get("telegram_last_checked_at")

        # 首次开启防轰炸（toggle_telegram_push 已设游标，此处为双重保障）
        if last_checked is None:
            update_telegram_cursor(account["id"], job_start_time)
            logger.debug("[telegram_push] account=%s first run, skip", account["email"])
            continue

        try:
            provider = (account.get("provider") or "").lower()
            if provider == "outlook":
                emails = _fetch_new_emails_graph(account, last_checked)
            else:
                emails = _fetch_new_emails_imap(account, last_checked)

            # 按时间升序推送（从旧到新）
            emails_sorted = sorted(
                emails,
                key=lambda e: e.get("received_at", "")
            )
            for em in emails_sorted:
                if sent_count >= MAX_SENT:
                    break
                msg = _build_telegram_message(account["email"], em)
                _send_telegram_message(bot_token, chat_id, msg)
                sent_count += 1

        except Exception as exc:
            logger.warning(
                "[telegram_push] account=%s error: %s", account["email"], exc
            )

        finally:
            # 无论成功/失败，更新游标（防死循环重试）
            update_telegram_cursor(account["id"], job_start_time)
```

---

## 7. 调度器集成详设

### 7.1 修改 `outlook_web/services/scheduler.py`

在 `configure_scheduler_jobs(scheduler, app, ...)` 函数末尾新增：

```python
from outlook_web.services.telegram_push import run_telegram_push_job
from outlook_web.repositories.settings import get_setting as _gs

def _get_telegram_interval() -> int:
    try:
        val = int(_gs("telegram_poll_interval") or "600")
        return max(60, min(3600, val))
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

### 7.2 动态更新 Job 间隔（P1）

当 `PUT /api/settings` 保存了 `telegram_poll_interval` 后，在 `controllers/settings.py` 中触发重调度：

```python
# 保存后，若调度器在运行，更新 telegram_push_job 间隔
from outlook_web.services.scheduler import scheduler as _scheduler
if _scheduler and _scheduler.running:
    new_interval = max(60, min(3600, int(new_value)))
    _scheduler.reschedule_job(
        "telegram_push_job",
        trigger="interval",
        seconds=new_interval
    )
```

---

## 8. Controller 与路由层详设

### 8.1 `api_telegram_toggle(account_id)` — `controllers/accounts.py`

```python
from outlook_web.repositories.accounts import toggle_telegram_push as _toggle_tg

@login_required
def api_telegram_toggle(account_id: int):
    """POST /api/accounts/<int:account_id>/telegram-toggle"""
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get("enabled", False))
    success = _toggle_tg(account_id, enabled)
    if not success:
        return jsonify({"success": False, "message": "账号不存在"}), 404
    action = "开启" if enabled else "关闭"
    _audit_log(f"Telegram推送{action}", account_id=account_id)
    return jsonify({
        "success": True,
        "enabled": enabled,
        "message": f"Telegram推送已{action}",
    })
```

### 8.2 路由注册 — `routes/accounts.py`

```python
from outlook_web.controllers.accounts import api_telegram_toggle

accounts_bp.add_url_rule(
    "/api/accounts/<int:account_id>/telegram-toggle",
    view_func=api_telegram_toggle,
    methods=["POST"],
)
```

### 8.3 Settings GET/PUT 扩展 — `controllers/settings.py`

**GET** — 在返回 dict 中新增：
```python
# bot_token 脱敏：显示 "****" + 后4位；空则返回空字符串
raw_token = decrypt_data(get_setting("telegram_bot_token")) if get_setting("telegram_bot_token") else ""
masked_token = ("****" + raw_token[-4:]) if len(raw_token) > 4 else ("*" * len(raw_token)) if raw_token else ""

settings_dict.update({
    "telegram_bot_token":      masked_token,
    "telegram_chat_id":        get_setting("telegram_chat_id", ""),
    "telegram_poll_interval":  int(get_setting("telegram_poll_interval", "600")),
})
```

**PUT** — 新增字段处理逻辑：
```python
TELEGRAM_KEYS = {"telegram_bot_token", "telegram_chat_id", "telegram_poll_interval"}

if "telegram_bot_token" in payload:
    val = (payload["telegram_bot_token"] or "").strip()
    if val and not val.startswith("****"):  # 非脱敏占位符才更新
        set_setting("telegram_bot_token", encrypt_data(val))
    elif val == "":
        set_setting("telegram_bot_token", "")  # 清空

if "telegram_chat_id" in payload:
    set_setting("telegram_chat_id", str(payload["telegram_chat_id"] or "").strip())

if "telegram_poll_interval" in payload:
    try:
        interval = max(10, min(86400, int(payload["telegram_poll_interval"])))
    except (ValueError, TypeError):
        return error_response("telegram_poll_interval 必须为 10–86400 之间的整数", 400)
    set_setting("telegram_poll_interval", str(interval))
    # 触发重调度（P1）
```

---

## 9. 前端改造详设

### 9.1 账号列表 Telegram 开关按钮

**渲染**（在账号行模板中，操作按钮区域末尾新增）：

```javascript
// 在 renderAccountRow() 或相应的行渲染函数中
const tgEnabled = account.telegram_push_enabled === 1;
const tgBtn = `
  <button class="btn-icon telegram-toggle ${tgEnabled ? 'active' : ''}"
          data-id="${account.id}"
          data-enabled="${tgEnabled ? '1' : '0'}"
          title="${tgEnabled ? '关闭 Telegram 推送（当前已开启）' : '开启 Telegram 推送'}"
          aria-label="${tgEnabled ? '关闭' : '开启'} Telegram 推送">
    🔔
  </button>
`;
```

**事件绑定**（事件委托，绑定到账号列表容器）：

```javascript
document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".telegram-toggle");
    if (!btn) return;
    const accountId = parseInt(btn.dataset.id, 10);
    const currentEnabled = btn.dataset.enabled === "1";
    const newEnabled = !currentEnabled;

    // 若开启但未配置 Bot Token，给出友情提示
    if (newEnabled && !window._telegramConfigured) {
        showToast("请先在设置页配置 Telegram Bot Token", "warning");
        return;
    }

    const resp = await fetch(`/api/accounts/${accountId}/telegram-toggle`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({ enabled: newEnabled }),
    });
    const data = await resp.json();
    if (data.success) {
        btn.dataset.enabled = newEnabled ? "1" : "0";
        btn.classList.toggle("active", newEnabled);
        btn.title = newEnabled
            ? "关闭 Telegram 推送（当前已开启）"
            : "开启 Telegram 推送";
        showToast(data.message);
    } else {
        showToast(data.message || "操作失败", "error");
    }
});
```

**`window._telegramConfigured`** 在页面加载时由 `GET /api/settings` 返回值设置：
```javascript
window._telegramConfigured = !!(settings.telegram_bot_token && settings.telegram_chat_id);
```

### 9.2 设置页 Telegram 配置区块

设置模态框中（现有区块之后）新增：

```html
<div class="settings-group" id="telegramSection">
  <h4>📬 Telegram 推送</h4>
  <div class="form-row">
    <label for="telegramBotToken">Bot Token</label>
    <input type="password" id="telegramBotToken"
           placeholder="配置后显示脱敏值，留空不修改" autocomplete="off" />
  </div>
  <div class="form-row">
    <label for="telegramChatId">Chat ID</label>
    <input type="text" id="telegramChatId"
           placeholder="如 -1001234567890 或 @mychannel" />
  </div>
  <div class="form-row">
    <label for="telegramPollInterval">轮询间隔（秒）</label>
    <input type="number" id="telegramPollInterval" min="10" max="86400" value="600" />
    <span class="hint">10–86400，默认 600（10 分钟）</span>
  </div>
</div>
```

---

## 10. 加密与安全实现细节

### 10.1 Bot Token 存储与读取

```
写入：encrypt_data(bot_token) → "enc:xxxx..." → set_setting("telegram_bot_token", ...)
读取：get_setting("telegram_bot_token") → decrypt_data("enc:xxxx...") → bot_token
API返回：脱敏 "****xxxx"（后4位）
```

**注意**：`decrypt_data()` 收到空字符串时返回空字符串，不报错（需在 `telegram_push.py` 处理空字符串为"未配置"情况）。

### 10.2 IMAP 密码 / Refresh Token 读取

Repository `get_telegram_push_accounts()` 返回加密原始值，Service 层调用 `decrypt_data()` 解密：

```python
imap_password = decrypt_data(account.get("imap_password") or "")
refresh_token  = decrypt_data(account.get("refresh_token") or "")
```

### 10.3 日志脱敏规则

**禁止打印到日志的字段**：`bot_token`、`imap_password`、`refresh_token`、`client_id`（完整值）

日志中账号信息只记录 `email` 地址和 `account_id`。

---

## 11. 兼容性保障

| 场景 | 保障措施 |
|------|----------|
| 旧数据库（未迁移） | `_migrate()` 自动执行 version 4 迁移，SQLite ALTER 用 try/except 保证幂等 |
| `telegram_poll_interval` 未设置 | `get_setting()` 返回默认 `""` → 代码层 fallback 为 600 秒 |
| `telegram_bot_token` 为空字符串（未配置） | `decrypt_data("")` 返回 `""` → job 直接 `return`，不报错 |
| 调度器未启动（测试环境） | `run_telegram_push_job` 在测试中直接调用时需 mock app_context |
| 账号 `status=disabled` | `get_telegram_push_accounts()` 过滤掉，不轮询 |

---

## 12. 测试策略与测试用例

### 12.1 测试文件

**新建**：`tests/test_telegram_push.py`

### 12.2 单元测试

#### T-01：`_build_telegram_message` — 正常邮件（含预览）

```
输入：account_email="user@example.com", email={subject="Hello", sender="bob@x.com", received_at="2026-03-04T14:30:00", preview="This is a test email body."}
期望：消息包含 "📬", "user@example.com", "bob@x.com", "Hello", "14:30", "This is a test email body."
```

#### T-02：`_build_telegram_message` — 正文为空

```
输入：preview=""
期望：消息中不包含 "内容预览："
```

#### T-03：`_build_telegram_message` — 超长消息截断

```
输入：preview = "a" * 5000
期望：最终消息 len ≤ 4096，且末尾为 "..."
```

#### T-04：`_build_telegram_message` — HTML 特殊字符转义

```
输入：subject="<Sale> & <Offer>", sender="a&b@test.com"
期望：消息中包含 "&lt;Sale&gt; &amp; &lt;Offer&gt;", "a&amp;b@test.com"
期望：消息中不含原始 "<", ">"（subject/sender 处）
```

#### T-05：`_build_telegram_message` — 正文超 200 字截断

```
输入：preview = "x" * 300
期望：消息中正文为 "x" * 200 + "..."
```

#### T-06：`_html_to_plain` — 去除 HTML 标签

```
输入："<p>Hello <b>World</b></p>"
期望："Hello World"
输入：""
期望：""
```

#### T-07：`_html_to_plain` — 合并多余空白

```
输入："<p>  a  </p>  <br>  <p>b</p>"
期望："a b"（多余空白合并为单个空格）
```

#### T-08：`_escape_html` — 三种特殊字符

```
输入："a & <b> and > c"
期望："a &amp; &lt;b&gt; and &gt; c"
```

### 12.3 Repository 单元测试（需 Flask test DB）

#### T-09：`toggle_telegram_push` — 首次开启设游标

```
前置：DB 中有账号 id=1，telegram_push_enabled=0，telegram_last_checked_at=NULL
操作：toggle_telegram_push(1, True)
断言：
  - 返回 True
  - telegram_push_enabled = 1
  - telegram_last_checked_at IS NOT NULL（不为 None）
  - telegram_last_checked_at 为有效 ISO8601 字符串
```

#### T-10：`toggle_telegram_push` — 关闭推送（不清空游标）

```
前置：telegram_push_enabled=1，telegram_last_checked_at="2026-03-01T10:00:00"
操作：toggle_telegram_push(1, False)
断言：
  - telegram_push_enabled = 0
  - telegram_last_checked_at 仍为 "2026-03-01T10:00:00"（不清空）
```

#### T-11：`toggle_telegram_push` — 账号不存在

```
操作：toggle_telegram_push(99999, True)
断言：返回 False
```

#### T-12：`toggle_telegram_push` — 重复开启不重置游标

```
前置：telegram_push_enabled=1，telegram_last_checked_at="2026-03-01T10:00:00"
操作：toggle_telegram_push(1, True)
断言：
  - 返回 True
  - telegram_last_checked_at 仍为 "2026-03-01T10:00:00"（不重置）
```

#### T-13：`update_telegram_cursor` — 正常更新

```
前置：telegram_last_checked_at = NULL
操作：update_telegram_cursor(1, "2026-03-04T14:30:00")
断言：telegram_last_checked_at = "2026-03-04T14:30:00"
```

#### T-14：`get_telegram_push_accounts` — 只返回启用账号

```
前置：账号 A（enabled=1），账号 B（enabled=0），账号 C（enabled=1, status=disabled）
操作：get_telegram_push_accounts()
断言：结果仅包含账号 A（B 未开启，C 被禁用）
```

### 12.4 `run_telegram_push_job` 集成测试（mock Telegram API + DB）

#### T-15：Bot Token 未配置 → 跳过

```
前置：settings 中 telegram_bot_token="" 或未设置
操作：run_telegram_push_job(app)
断言：Telegram API 未被调用（mock _send_telegram_message 调用次数为 0）
```

#### T-16：Chat ID 未配置 → 跳过

```
前置：telegram_bot_token 已配置，telegram_chat_id=""
操作：run_telegram_push_job(app)
断言：Telegram API 未被调用
```

#### T-17：无启用推送的账号 → 跳过

```
前置：所有账号 telegram_push_enabled=0
操作：run_telegram_push_job(app)
断言：Telegram API 未被调用
```

#### T-18：首次开启（last_checked_at=None） → 设游标，不发消息

```
前置：账号启用推送，telegram_last_checked_at=NULL
操作：run_telegram_push_job(app)（mock _fetch_new_emails_* 返回 2 封邮件）
断言：
  - Telegram API 调用次数为 0（不推送）
  - telegram_last_checked_at 已更新（不再为 NULL）
```

#### T-19：正常推送 → Telegram API 被调用，游标更新

```
前置：账号启用推送，last_checked_at="2026-03-01T00:00:00"
mock：_fetch_new_emails_* 返回 2 封 received_at > last_checked_at 的邮件
操作：run_telegram_push_job(app)
断言：
  - Telegram API 调用次数为 2
  - telegram_last_checked_at 已更新为 job_start_time
```

#### T-20：全局上限 20 封 → 超出不再推送

```
前置：账号 A（有 12 封新邮件）+ 账号 B（有 15 封新邮件）
操作：run_telegram_push_job(app)（mock _fetch_new_emails_*）
断言：
  - Telegram API 总调用次数为 20
  - 两个账号的游标均已更新
```

#### T-21：IMAP 连接异常 → 静默，游标仍更新

```
前置：IMAP 账号启用推送，last_checked_at 已设
mock：_fetch_new_emails_imap 抛出 ConnectionError
操作：run_telegram_push_job(app)
断言：
  - 不抛出异常
  - telegram_last_checked_at 已更新（游标照常更新）
  - Telegram API 未被调用（此账号无邮件推送）
```

#### T-22：Telegram API 发送失败 → 静默，游标仍更新

```
前置：账号有 2 封新邮件
mock：_send_telegram_message 返回 False
操作：run_telegram_push_job(app)
断言：
  - 不抛出异常
  - telegram_last_checked_at 已更新
```

### 12.5 `api_telegram_toggle` 端点测试

#### T-23：开启成功

```
请求：POST /api/accounts/1/telegram-toggle {"enabled": true}（已登录）
断言：{"success": true, "enabled": true}，DB 中 telegram_push_enabled=1
```

#### T-24：关闭成功

```
请求：POST /api/accounts/1/telegram-toggle {"enabled": false}
断言：{"success": true, "enabled": false}，DB 中 telegram_push_enabled=0
```

#### T-25：账号不存在 → 404

```
请求：POST /api/accounts/99999/telegram-toggle {"enabled": true}
断言：HTTP 404，{"success": false}
```

#### T-26：未登录 → 拒绝访问

```
请求：POST /api/accounts/1/telegram-toggle（未携带 session cookie）
断言：HTTP 401 或 302 重定向
```

### 12.6 Settings API 扩展测试

#### T-27：GET /api/settings — 包含 telegram 配置字段

```
前置：已配置 telegram_bot_token（明文 "1234567890:AAxxxxx"）
请求：GET /api/settings（已登录）
断言：返回中包含 telegram_bot_token（脱敏，值类似 "****xxxx"，不返回明文）
断言：包含 telegram_chat_id、telegram_poll_interval
```

#### T-28：PUT /api/settings — 保存 telegram 配置

```
请求：PUT /api/settings {"telegram_bot_token": "NewToken123", "telegram_chat_id": "-123456", "telegram_poll_interval": 300}
断言：返回 success
断言：DB 中 telegram_bot_token 已加密存储（前缀 "enc:"）
断言：get_setting("telegram_chat_id") = "-123456"
断言：get_setting("telegram_poll_interval") = "300"
```

#### T-29：PUT /api/settings — 非法 interval 值

```
请求：PUT /api/settings {"telegram_poll_interval": 30}（低于最小值 60）
断言：返回 HTTP 400 错误
```

#### T-30：PUT /api/settings — 传入脱敏占位符不更新 token

```
前置：DB 中已有真实 bot_token 加密值
请求：PUT /api/settings {"telegram_bot_token": "****xxxx"}（脱敏占位符）
断言：DB 中 token 值未改变
```

### 12.7 回归测试

#### T-31：Token 刷新调度器不受影响

```
操作：启动应用（含调度器），调用 run_telegram_push_job
断言：scheduler 中存在 "token_refresh" job（未被删除/修改）
```

#### T-32：全量回归

```
操作：python -m unittest discover -s tests -v
断言：所有原有测试仍通过（基线 169 + 新增 ≥ 20 条）
```

---

## 附录：实现注意事项

1. **`get_emails_graph()` 邮件顺序**：返回邮件按 `receivedDateTime desc`（最新在前），所以在 `_fetch_new_emails_graph()` 中一旦遇到 `received_dt <= since_dt` 可以立即 `break`，避免扫描全部 50 封。

2. **IMAP SEARCH SINCE 精度**：只精确到天，必须在代码层用 `received_dt > since_dt`（秒级）二次过滤。`since_dt` 是上次检查的完整时间戳，过滤可能包含当天但比游标更旧的邮件。

3. **`decrypt_data("")` 的行为**：需确认 `security/crypto.py` 中 `decrypt_data` 对空字符串的处理（应返回空字符串，不报错）。若报错则在调用前加 `if value else ""` 保护。

4. **测试 DB 隔离**：复用 `tests/_import_app.py` 中已有的测试 app factory（临时 DB、关闭调度器），避免 Telegram push job 在测试中实际触发。

5. **`bodyPreview` 字段**：Graph API 的 `bodyPreview` 已是纯文本截取（约 255 字），不需要 `_html_to_plain()`；IMAP 模式因只取 HEADER 没有正文，预览为空字符串。`_html_to_plain()` 备用，供未来读取完整 IMAP 正文时使用。
