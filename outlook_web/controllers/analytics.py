from __future__ import annotations

import time
from typing import Any, Optional

from flask import jsonify, request

from outlook_web.db import get_db
from outlook_web.errors import build_error_response
from outlook_web.security.auth import login_required


def _extract_domain(from_address: str) -> str:
    raw = (from_address or "").strip()
    if not raw:
        return ""
    # handle "Name <a@b.com>"
    if "<" in raw and ">" in raw:
        try:
            inner = raw.split("<", 1)[1].split(">", 1)[0].strip()
            raw = inner
        except Exception:
            pass
    at = raw.rfind("@")
    if at <= 0:
        return ""
    return raw[at + 1 :].strip().lower()


def _parse_window_param(window_key: str) -> Optional[int]:
    w = (window_key or "").strip().lower()
    if not w or w == "30d":
        return 30 * 24 * 3600
    if w == "90d":
        return 90 * 24 * 3600
    if w == "all":
        return None
    # fallback
    return 30 * 24 * 3600


@login_required
def api_source_domains() -> Any:
    """邮件来源分布：

    数据来源：本地缓存表 `temp_email_messages`（字段 from_address / email_address / timestamp）。

    Query:
      - email: 可选，仅统计某个邮箱账号
      - window: 30d|90d|all
    """

    email = (request.args.get("email") or "").strip()
    window_key = (request.args.get("window") or "30d").strip().lower()

    seconds = _parse_window_param(window_key)
    since_ts = None
    if seconds is not None:
        since_ts = int(time.time()) - int(seconds)

    db = get_db()

    try:
        sql = """
            SELECT email_address, from_address, timestamp
            FROM temp_email_messages
            WHERE 1=1
        """
        params: list[Any] = []
        if email:
            sql += " AND email_address = ?"
            params.append(email)
        if since_ts is not None:
            sql += " AND timestamp IS NOT NULL AND timestamp >= ?"
            params.append(int(since_ts))
        sql += " ORDER BY id DESC LIMIT 5000"

        rows = db.execute(sql, tuple(params)).fetchall()
    except Exception as e:
        return build_error_response(
            "SOURCE_MAP_QUERY_FAILED",
            "查询来源分布失败",
            message_en="Failed to query source map",
            err_type="DatabaseError",
            status=500,
            details=str(e),
        )

    domain_counts: dict[str, int] = {}
    account_domain_counts: dict[str, dict[str, int]] = {}

    for r in rows:
        acc = (r["email_address"] or "").strip()
        dom = _extract_domain(r["from_address"] or "")
        if not dom or not acc:
            continue
        domain_counts[dom] = domain_counts.get(dom, 0) + 1
        if acc not in account_domain_counts:
            account_domain_counts[acc] = {}
        adc = account_domain_counts[acc]
        adc[dom] = adc.get(dom, 0) + 1

    top_domains = sorted(
        [{"domain": k, "count": v} for k, v in domain_counts.items()],
        key=lambda x: (-x["count"], x["domain"]),
    )

    word_cloud = top_domains[:80]

    # graph: pick top accounts (by messages) and top domains (by count)
    top_accounts = sorted(
        [{"email": k, "count": sum(v.values())} for k, v in account_domain_counts.items()],
        key=lambda x: (-x["count"], x["email"]),
    )[:12]
    account_emails = [a["email"] for a in top_accounts]

    top_domain_keys = [d["domain"] for d in top_domains[:18]]

    edges: list[dict[str, Any]] = []
    for acc in account_emails:
        adc = account_domain_counts.get(acc) or {}
        for dom in top_domain_keys:
            c = int(adc.get(dom) or 0)
            if c <= 0:
                continue
            edges.append({"account": acc, "domain": dom, "count": c})

    edges.sort(key=lambda x: (-x["count"], x["account"], x["domain"]))
    edges = edges[:80]

    # only keep domains that appear in edges
    edge_domain_set = {e["domain"] for e in edges}
    graph_domains = [d for d in top_domains if d["domain"] in edge_domain_set][:18]

    return jsonify(
        {
            "success": True,
            "email": email or None,
            "window": window_key,
            "total_messages_scanned": len(rows),
            "top_domains": top_domains[:50],
            "word_cloud": word_cloud,
            "graph": {
                "accounts": account_emails,
                "domains": graph_domains,
                "edges": edges,
            },
        }
    )
