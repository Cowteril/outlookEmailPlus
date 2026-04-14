"""HTTP 路由层（Blueprint）。

目标：按领域拆分 routes，并在 create_app 内集中注册，保持 URL 不变。

说明：
- `outlook_web.app.create_app` 会执行 `from outlook_web.routes import xxx`。
- 因此这里需要显式导出各个路由模块（accounts/emails/...）。
"""

from __future__ import annotations

# 显式 re-export，供 `from outlook_web.routes import ...` 使用
from . import (
    accounts,
    analytics,
    audit,
    emails,
    external_pool,
    external_temp_emails,
    groups,
    jobs,
    pages,
    scheduler,
    settings,
    system,
    tags,
    temp_emails,
)

# oauth 可能在某些分支/版本中不存在；为兼容 create_app 的导入，这里做可选导出。
try:
    from . import oauth  # type: ignore
except Exception:  # pragma: no cover
    oauth = None  # type: ignore

__all__ = [
    "accounts",
    "analytics",
    "audit",
    "emails",
    "external_pool",
    "external_temp_emails",
    "groups",
    "jobs",
    "oauth",
    "pages",
    "scheduler",
    "settings",
    "system",
    "tags",
    "temp_emails",
]
