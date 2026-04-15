from __future__ import annotations

from flask import Blueprint

from outlook_web.controllers import analytics as analytics_controller


def create_blueprint() -> Blueprint:
    bp = Blueprint("analytics", __name__)

    bp.add_url_rule(
        "/api/analytics/source-domains",
        view_func=analytics_controller.api_source_domains,
        methods=["GET"],
    )

    return bp
