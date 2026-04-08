from __future__ import annotations

from typing import Any

from flask import jsonify

from outlook_web.security.auth import login_required


@login_required
def api_get_job_status(job_id: str) -> Any:
    try:
        from outlook_web.queueing import QueueNotConfiguredError, fetch_job, is_queue_enabled
    except Exception as exc:
        return jsonify({"success": False, "error": {"code": "QUEUE_NOT_AVAILABLE", "message": str(exc)}}), 500

    if not is_queue_enabled():
        return jsonify({"success": False, "error": {"code": "QUEUE_DISABLED", "message": "Queue is disabled"}}), 400

    try:
        job = fetch_job(job_id)
    except QueueNotConfiguredError as exc:
        return jsonify({"success": False, "error": {"code": "QUEUE_NOT_CONFIGURED", "message": str(exc)}}), 400
    except Exception:
        return jsonify({"success": False, "error": {"code": "JOB_NOT_FOUND", "message": "Job not found"}}), 404

    # RQ: queued / started / finished / failed / deferred / scheduled
    status = job.get_status(refresh=False)
    result = None
    if status == "finished":
        try:
            result = job.result
        except Exception:
            result = None

    error = None
    if status == "failed":
        error = {"message": "Job failed", "exc_info": job.exc_info}

    return (
        jsonify(
            {
                "success": True,
                "job": {
                    "id": job_id,
                    "status": status,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "ended_at": job.ended_at.isoformat() if job.ended_at else None,
                    "result": result,
                    "error": error,
                },
            }
        ),
        200,
    )


@login_required
def api_enqueue_job(job_name: str) -> Any:
    try:
        from outlook_web.queueing import QueueNotConfiguredError, enqueue, is_queue_enabled
    except Exception as exc:
        return jsonify({"success": False, "error": {"code": "QUEUE_NOT_AVAILABLE", "message": str(exc)}}), 500

    if not is_queue_enabled():
        return jsonify({"success": False, "error": {"code": "QUEUE_DISABLED", "message": "Queue is disabled"}}), 400

    job_map = {
        "scheduled-refresh": "outlook_web.jobs.scheduled_refresh_job",
        "notification-dispatch": "outlook_web.jobs.notification_dispatch_job",
    }
    target = job_map.get((job_name or "").strip().lower())
    if not target:
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "UNKNOWN_JOB",
                        "message": "Unknown job",
                        "allowed": sorted(job_map.keys()),
                    },
                }
            ),
            400,
        )

    try:
        job_id = enqueue(target)
    except QueueNotConfiguredError as exc:
        return jsonify({"success": False, "error": {"code": "QUEUE_NOT_CONFIGURED", "message": str(exc)}}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": {"code": "ENQUEUE_FAILED", "message": str(exc)}}), 500

    return jsonify({"success": True, "job_id": job_id, "job": job_name}), 200

