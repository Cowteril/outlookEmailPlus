from __future__ import annotations

from typing import Any, Dict, Optional


def scheduled_refresh_job(*, trace_id: Optional[str] = None) -> Dict[str, Any]:
    """
    RQ Job：执行一次“定时刷新”任务。

    注意：
    - Job 内部自行创建 Flask app，避免在队列中序列化 app 对象。
    - autostart_scheduler=False 避免 worker 启动后再次拉起 APScheduler。
    """
    from outlook_web.app import create_app
    from outlook_web.services import graph as graph_service
    from outlook_web.services import scheduler as scheduler_service

    app = create_app(autostart_scheduler=False)
    scheduler_service.scheduled_refresh_task(app, graph_service.test_refresh_token_with_rotation)
    return {"ok": True, "job": "scheduled_refresh", "trace_id": trace_id}


def notification_dispatch_job(*, trace_id: Optional[str] = None) -> Dict[str, Any]:
    """
    RQ Job：执行一次“统一通知分发”任务。
    """
    from outlook_web.app import create_app
    from outlook_web.services import notification_dispatch

    app = create_app(autostart_scheduler=False)
    notification_dispatch.run_notification_dispatch_job(app)
    return {"ok": True, "job": "notification_dispatch", "trace_id": trace_id}

