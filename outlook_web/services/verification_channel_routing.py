from __future__ import annotations

from typing import Any, Dict, List, Optional

from outlook_web.services import graph as graph_service
from outlook_web.services import imap as imap_service

CHANNEL_GRAPH_INBOX = "graph_inbox"
CHANNEL_GRAPH_JUNK = "graph_junk"
CHANNEL_IMAP_NEW = "imap_new"
CHANNEL_IMAP_OLD = "imap_old"

DEFAULT_VERIFICATION_CHANNEL_CHAIN = (
    CHANNEL_GRAPH_INBOX,
    CHANNEL_GRAPH_JUNK,
    CHANNEL_IMAP_NEW,
    CHANNEL_IMAP_OLD,
)
VALID_VERIFICATION_CHANNELS = set(DEFAULT_VERIFICATION_CHANNEL_CHAIN)

IMAP_SERVER_NEW = "outlook.live.com"
IMAP_SERVER_OLD = "outlook.office365.com"


def normalize_verification_channel(value: Any) -> Optional[str]:
    text = str(value or "").strip().lower()
    if text in VALID_VERIFICATION_CHANNELS:
        return text
    return None


def build_verification_channel_plan(preferred_channel: Any) -> List[str]:
    preferred = normalize_verification_channel(preferred_channel)
    if not preferred:
        return list(DEFAULT_VERIFICATION_CHANNEL_CHAIN)
    return [preferred] + [channel for channel in DEFAULT_VERIFICATION_CHANNEL_CHAIN if channel != preferred]


def map_method_to_verification_channel(method: str, *, folder: str = "inbox") -> Optional[str]:
    method_text = str(method or "").strip().lower()
    folder_text = str(folder or "inbox").strip().lower()
    if method_text == "graph api":
        return CHANNEL_GRAPH_JUNK if folder_text == "junkemail" else CHANNEL_GRAPH_INBOX
    if method_text == "imap (new)":
        return CHANNEL_IMAP_NEW
    if method_text == "imap (old)":
        return CHANNEL_IMAP_OLD
    return None


def channel_method_label(channel: str) -> str:
    normalized = normalize_verification_channel(channel)
    if normalized == CHANNEL_GRAPH_INBOX:
        return "Graph API (Inbox)"
    if normalized == CHANNEL_GRAPH_JUNK:
        return "Graph API (Junk)"
    if normalized == CHANNEL_IMAP_NEW:
        return "IMAP (New)"
    if normalized == CHANNEL_IMAP_OLD:
        return "IMAP (Old)"
    return ""


def is_outlook_oauth_account(account: Dict[str, Any]) -> bool:
    account_type = str(account.get("account_type") or "outlook").strip().lower()
    if account_type != "outlook":
        return False
    return bool(str(account.get("client_id") or "").strip()) and bool(str(account.get("refresh_token") or "").strip())


def fetch_emails_for_channel(
    *,
    account: Dict[str, Any],
    channel: str,
    proxy_url: str = "",
    skip: int = 0,
    top: int = 20,
) -> Dict[str, Any]:
    normalized = normalize_verification_channel(channel)
    if not normalized:
        return {
            "success": False,
            "error": {
                "code": "INVALID_CHANNEL",
                "message": "invalid verification channel",
            },
        }

    if normalized in (CHANNEL_GRAPH_INBOX, CHANNEL_GRAPH_JUNK):
        folder = "junkemail" if normalized == CHANNEL_GRAPH_JUNK else "inbox"
        graph_result = graph_service.get_emails_graph(
            str(account.get("client_id") or ""),
            str(account.get("refresh_token") or ""),
            folder=folder,
            skip=int(skip or 0),
            top=int(top or 20),
            proxy_url=proxy_url,
        )
        if not graph_result.get("success"):
            return {
                "success": False,
                "auth_expired": bool(graph_result.get("auth_expired")),
                "error": graph_result.get("error"),
                "channel": normalized,
            }

        emails = []
        for item in graph_result.get("emails", []) or []:
            enriched = dict(item)
            enriched["folder"] = folder
            enriched["_verification_channel"] = normalized
            emails.append(enriched)
        return {
            "success": True,
            "emails": emails,
            "new_refresh_token": graph_result.get("new_refresh_token"),
            "channel": normalized,
        }

    imap_server = IMAP_SERVER_NEW if normalized == CHANNEL_IMAP_NEW else IMAP_SERVER_OLD
    imap_result = imap_service.get_emails_imap_with_server(
        str(account.get("email") or ""),
        str(account.get("client_id") or ""),
        str(account.get("refresh_token") or ""),
        folder="inbox",
        skip=int(skip or 0),
        top=int(top or 20),
        server=imap_server,
    )
    if not imap_result.get("success"):
        return {
            "success": False,
            "error": imap_result.get("error"),
            "channel": normalized,
        }

    emails = []
    for item in imap_result.get("emails", []) or []:
        enriched = dict(item)
        enriched["folder"] = "inbox"
        enriched["_verification_channel"] = normalized
        emails.append(enriched)
    return {"success": True, "emails": emails, "channel": normalized}


def fetch_email_detail_for_channel(
    *,
    account: Dict[str, Any],
    channel: str,
    message_id: str,
    proxy_url: str = "",
) -> Optional[Dict[str, Any]]:
    normalized = normalize_verification_channel(channel)
    if not normalized or not message_id:
        return None

    if normalized in (CHANNEL_GRAPH_INBOX, CHANNEL_GRAPH_JUNK):
        return graph_service.get_email_detail_graph(
            str(account.get("client_id") or ""),
            str(account.get("refresh_token") or ""),
            str(message_id),
            proxy_url,
        )

    if normalized == CHANNEL_IMAP_NEW:
        return imap_service.get_email_detail_imap_with_server(
            str(account.get("email") or ""),
            str(account.get("client_id") or ""),
            str(account.get("refresh_token") or ""),
            str(message_id),
            "inbox",
            IMAP_SERVER_NEW,
        )

    return imap_service.get_email_detail_imap_with_server(
        str(account.get("email") or ""),
        str(account.get("client_id") or ""),
        str(account.get("refresh_token") or ""),
        str(message_id),
        "inbox",
        IMAP_SERVER_OLD,
    )
