from __future__ import annotations

from typing import Any, Optional

from outlook_web import config


class QueueNotConfiguredError(RuntimeError):
    pass


def _require_redis_url() -> str:
    redis_url = config.get_redis_url()
    if not redis_url:
        raise QueueNotConfiguredError("REDIS_URL is not configured")
    return redis_url


def get_redis_connection():
    try:
        import redis
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("redis package is required. Install: pip install redis>=5.0.0") from exc

    redis_url = _require_redis_url()
    return redis.Redis.from_url(redis_url)


def get_queue():
    try:
        from rq import Queue
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("rq package is required. Install: pip install rq>=1.16.0") from exc

    conn = get_redis_connection()
    return Queue(name=config.get_queue_name(), connection=conn)


def is_queue_enabled() -> bool:
    return config.get_queue_enabled()


def enqueue(callable_or_path: Any, *args: Any, job_timeout: Optional[int] = None, **kwargs: Any) -> str:
    """
    入队一个任务，返回 job_id。

    - callable_or_path: 既支持可调用对象（推荐），也支持可 import 的字符串路径。
    """
    if not is_queue_enabled():
        raise QueueNotConfiguredError("Queue is disabled")

    q = get_queue()
    job = q.enqueue(callable_or_path, *args, job_timeout=job_timeout, **kwargs)
    return str(job.get_id())


def fetch_job(job_id: str):
    try:
        from rq.job import Job
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("rq package is required. Install: pip install rq>=1.16.0") from exc

    conn = get_redis_connection()
    return Job.fetch(job_id, connection=conn)

