from __future__ import annotations

from flask import Blueprint

from outlook_web.controllers import jobs as jobs_controller


def create_blueprint() -> Blueprint:
    bp = Blueprint("jobs", __name__)
    bp.add_url_rule(
        "/api/jobs/enqueue/<job_name>",
        view_func=jobs_controller.api_enqueue_job,
        methods=["POST"],
    )
    bp.add_url_rule(
        "/api/jobs/<job_id>",
        view_func=jobs_controller.api_get_job_status,
        methods=["GET"],
    )
    return bp

