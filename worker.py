from __future__ import annotations

import os


def main() -> None:
    """
    启动一个 RQ worker，用于执行队列任务。

    用法：
    - PowerShell:
      $env:REDIS_URL="redis://localhost:6379/0"
      $env:QUEUE_ENABLED="true"
      python worker.py
    """
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        raise SystemExit("REDIS_URL is required to run worker")

    queue_name = os.getenv("QUEUE_NAME", "outlook-email-plus").strip() or "outlook-email-plus"

    try:
        import redis
        from rq import Connection, Worker
    except Exception as exc:  # pragma: no cover
        raise SystemExit("Missing dependencies. Install: pip install -r requirements.txt") from exc

    conn = redis.Redis.from_url(redis_url)
    with Connection(conn):
        worker = Worker([queue_name])
        worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()

