"""Zoho ZeptoMail transactional email service (Phase 32 — Jun 2026).

Used for sending email notifications (lead-assigned, follow-up reminders,
deal-room invites, approval-requested, milestone-due, payment-received, weekly
war-room digest, etc.) tied to each user's notification_preferences.

Design:
  - Async-first using httpx.AsyncClient
  - One retry with exponential backoff + jitter on 5xx / network errors
  - Failures are logged but DO NOT raise (email is a side effect of business ops)
  - Optional admin BCC for compliance audit trail
  - Every send writes a row to the `email_logs` collection (TTL: 90 days)

Inline HTML rendering for now (no ZeptoMail-hosted templates).
Migration to templates can be done later by mapping notification_type → template_key.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

logger = logging.getLogger(__name__)

# --- Configuration (read once at import) ------------------------------------
_BASE_URL = (os.environ.get("ZEPTOMAIL_BASE_URL") or "https://api.zeptomail.in/v1.1").rstrip("/")
_TOKEN = os.environ.get("ZEPTOMAIL_TOKEN", "").strip()
_SENDER_ADDRESS = os.environ.get("ZEPTOMAIL_SENDER_ADDRESS", "").strip()
_SENDER_NAME = os.environ.get("ZEPTOMAIL_SENDER_NAME", "Vyapaar Network").strip()
_ADMIN_BCC = (os.environ.get("ZEPTOMAIL_ADMIN_BCC") or "").strip()


def is_configured() -> bool:
    """Returns True if the integration is wired up. Used by callers to skip
    sending without raising when ZeptoMail isn't configured (dev environments)."""
    return bool(_TOKEN and _SENDER_ADDRESS)


def _auth_value() -> str:
    """ZeptoMail expects the token verbatim with a `Zoho-enczapikey` prefix."""
    t = _TOKEN
    # If user pasted the prefix themselves, don't double it
    if t.lower().startswith("zoho-enczapikey"):
        return t
    return f"Zoho-enczapikey {t}"


def _safe_email(addr: str) -> bool:
    return bool(addr) and re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", addr) is not None


async def _post_with_retry(client: httpx.AsyncClient, path: str, payload: dict) -> httpx.Response:
    """POST with one retry on transient failures (5xx, network). Always returns
    the final response (success or terminal error), never raises to the caller."""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": _auth_value(),
    }
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(2),
        wait=wait_exponential_jitter(initial=1, max=4),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.HTTPError)),
        reraise=True,
    ):
        with attempt:
            resp = await client.post(path, json=payload, headers=headers)
            if 500 <= resp.status_code < 600:
                raise httpx.HTTPError(f"ZeptoMail server error {resp.status_code}: {resp.text[:200]}")
            return resp
    # Should never reach here because reraise=True
    raise RuntimeError("ZeptoMail post exhausted retries without raising")  # pragma: no cover


async def send_email(
    to_address: str,
    subject: str,
    html_body: str,
    *,
    to_name: Optional[str] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    text_body: Optional[str] = None,
    db=None,
    notification_type: Optional[str] = None,
    user_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Send a single transactional email. Never raises — returns a result dict
    with `{ok: bool, status_code, request_id, error}`.

    If `db` is provided, writes an entry to the `email_logs` collection.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "status_code": 0,
        "request_id": None,
        "error": None,
        "skipped": False,
    }

    if not is_configured():
        result["error"] = "zeptomail_not_configured"
        result["skipped"] = True
        logger.warning("ZeptoMail not configured — skipping email to %s", to_address)
        await _log(db, to_address, subject, notification_type, user_id, result, correlation_id)
        return result

    if not _safe_email(to_address):
        result["error"] = f"invalid_to_address:{to_address}"
        logger.warning("ZeptoMail: invalid to_address rejected: %r", to_address)
        await _log(db, to_address, subject, notification_type, user_id, result, correlation_id)
        return result

    payload: Dict[str, Any] = {
        "from": {"address": _SENDER_ADDRESS, "name": _SENDER_NAME},
        "to": [{"email_address": {"address": to_address, "name": to_name or ""}}],
        "subject": subject[:255],
        "htmlbody": html_body,
    }
    if text_body:
        payload["textbody"] = text_body

    cc_list = [c for c in (cc or []) if _safe_email(c)]
    if cc_list:
        payload["cc"] = [{"email_address": {"address": c}} for c in cc_list]

    bcc_list = [b for b in (bcc or []) if _safe_email(b)]
    if _ADMIN_BCC and _safe_email(_ADMIN_BCC) and _ADMIN_BCC not in bcc_list:
        bcc_list.append(_ADMIN_BCC)
    if bcc_list:
        payload["bcc"] = [{"email_address": {"address": b}} for b in bcc_list]

    try:
        async with httpx.AsyncClient(base_url=_BASE_URL, timeout=10.0) as client:
            resp = await _post_with_retry(client, "/email", payload)
        result["status_code"] = resp.status_code
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:500]}
        if 200 <= resp.status_code < 300:
            result["ok"] = True
            data = (body.get("data") or [{}])[0] if isinstance(body.get("data"), list) else {}
            result["request_id"] = body.get("request_id") or data.get("message_id")
            logger.info("ZeptoMail sent: to=%s subject=%r req=%s", to_address, subject[:60], result["request_id"])
        else:
            err = body.get("error") or body
            result["error"] = err
            logger.error("ZeptoMail failed (%s): to=%s body=%s", resp.status_code, to_address, str(body)[:500])
    except Exception as exc:  # network / retries exhausted
        result["error"] = f"exception:{type(exc).__name__}:{str(exc)[:200]}"
        logger.exception("ZeptoMail send raised: to=%s err=%s", to_address, exc)

    await _log(db, to_address, subject, notification_type, user_id, result, correlation_id)
    return result


async def _log(db, to_address, subject, notification_type, user_id, result, correlation_id):
    """Fire-and-forget log row. Never raises."""
    if db is None:
        return
    try:
        await db.email_logs.insert_one({
            "to_address": to_address,
            "subject": subject,
            "notification_type": notification_type,
            "user_id": user_id,
            "correlation_id": correlation_id,
            "ok": result.get("ok"),
            "status_code": result.get("status_code"),
            "request_id": result.get("request_id"),
            "error": (str(result.get("error"))[:1000] if result.get("error") else None),
            "skipped": result.get("skipped", False),
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc),  # Date for TTL index
        })
    except Exception as e:  # pragma: no cover
        logger.warning("email_logs insert failed: %s", e)


async def ensure_email_logs_ttl(db) -> None:
    """Best-effort: ensure a 90-day TTL index on email_logs.created_at."""
    try:
        await db.email_logs.create_index("created_at", expireAfterSeconds=90 * 24 * 3600)
    except Exception as e:  # pragma: no cover
        logger.warning("Could not create email_logs TTL index: %s", e)


# ============================================================================
# Inline HTML templates (notification_type -> renderer). Each renderer returns
# (subject, html_body). They use Meshora brand colors + a minimal responsive
# layout that's safe across email clients (table-based, inline CSS).
# ============================================================================

_BASE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;color:#111827;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f3f4f6;padding:24px 0;">
<tr><td align="center">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
<tr><td style="background:linear-gradient(135deg,#7c3aed,#4f46e5);padding:20px 28px;">
<div style="color:#ffffff;font-size:14px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase;opacity:0.85;">Vyapaar Network</div>
<div style="color:#ffffff;font-size:22px;font-weight:700;margin-top:4px;">{header}</div>
</td></tr>
<tr><td style="padding:28px;">
{body}
</td></tr>
<tr><td style="padding:18px 28px;background:#f9fafb;border-top:1px solid #e5e7eb;color:#6b7280;font-size:12px;">
You're receiving this because your notification preferences allow it.
<br/>You can manage them anytime from <a href="https://app.vyapaar.net/settings" style="color:#4f46e5;">Settings → Profile</a>.
</td></tr>
</table>
</td></tr></table>
</body></html>"""


def _wrap(title: str, header: str, body_html: str) -> str:
    return _BASE_TEMPLATE.format(title=title, header=header, body=body_html)


def _btn(label: str, url: str) -> str:
    return (
        f'<a href="{url}" style="display:inline-block;background:#4f46e5;color:#ffffff;text-decoration:none;'
        f'padding:10px 20px;border-radius:8px;font-weight:600;font-size:14px;margin-top:14px;">{label}</a>'
    )


def render(notification_type: str, ctx: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Pick a renderer for the given notification_type. Returns {subject, html, text} or None
    if there's no renderer (caller may fall back to a generic message)."""
    fn = _RENDERERS.get(notification_type)
    if not fn:
        return None
    try:
        return fn(ctx or {})
    except Exception as e:
        logger.warning("Email template render failed for %s: %s", notification_type, e)
        return None


def _render_lead_assigned(ctx):
    title = "New Lead Assigned"
    lead_title = ctx.get("lead_title", "Untitled lead")
    customer = ctx.get("customer_name") or ctx.get("customer_company") or ""
    assigned_by = ctx.get("assigned_by_name") or "an admin"
    lead_url = ctx.get("lead_url") or f"https://app.vyapaar.net/leads/{ctx.get('lead_id','')}"
    customer_html = f'<div style="color:#6b7280;font-size:14px;">{customer}</div>' if customer else ""
    body = (
        f'<p>Hi {ctx.get("recipient_name","there")},</p>'
        f'<p><strong>{assigned_by}</strong> assigned you a new lead:</p>'
        f'<div style="background:#f3f4f6;border-radius:8px;padding:14px 16px;margin:10px 0;">'
        f'<div style="font-size:16px;font-weight:600;">{lead_title}</div>'
        f'{customer_html}'
        f'</div>'
        f'{_btn("Open Lead", lead_url)}'
    )
    return {"subject": f"[Meshora] New lead assigned: {lead_title}"[:255],
            "html": _wrap(title, title, body),
            "text": f"{assigned_by} assigned you a new lead: {lead_title}. Open: {lead_url}"}


def _render_follow_up_reminder(ctx):
    title = "Follow-up Reminder"
    lead_title = ctx.get("lead_title", "your lead")
    scheduled = ctx.get("scheduled_date", "today")
    notes = ctx.get("notes") or ""
    lead_url = ctx.get("lead_url") or f"https://app.vyapaar.net/leads/{ctx.get('lead_id','')}"
    notes_html = f'<div style="color:#92400e;font-size:13px;margin-top:6px;">Notes: {notes}</div>' if notes else ""
    body = (
        f'<p>Hi {ctx.get("recipient_name","there")},</p>'
        f'<p>Reminder — you have a follow-up scheduled for <strong>{scheduled}</strong> on:</p>'
        f'<div style="background:#fef3c7;border-left:4px solid #f59e0b;padding:12px 14px;margin:10px 0;border-radius:6px;">'
        f'<div style="font-size:16px;font-weight:600;">{lead_title}</div>'
        f'{notes_html}'
        f'</div>'
        f'{_btn("View Follow-up", lead_url)}'
    )
    return {"subject": f"[Meshora] Follow-up reminder: {lead_title}"[:255],
            "html": _wrap(title, title, body),
            "text": f"Follow-up reminder for {lead_title} ({scheduled}). {notes}"}


def _render_deal_room_invite(ctx):
    title = "You're Invited to a Deal Room"
    inviter = ctx.get("inviter_name") or "Vyapaar Network"
    lead_title = ctx.get("lead_title", "a deal")
    magic_link = ctx.get("magic_link") or "https://app.vyapaar.net/deal-rooms"
    expires = ctx.get("expires_at") or ""
    perms = ", ".join(ctx.get("permissions") or []) or "view, comment"
    expires_html = f'<p style="color:#6b7280;font-size:12px;margin-top:18px;">This link expires on {expires}.</p>' if expires else ""
    body = (
        f'<p>Hi {ctx.get("recipient_name","there")},</p>'
        f'<p><strong>{inviter}</strong> has invited you to collaborate in the Deal Room for:</p>'
        f'<div style="background:#ede9fe;border-radius:8px;padding:14px 16px;margin:10px 0;">'
        f'<div style="font-size:16px;font-weight:600;">{lead_title}</div>'
        f'<div style="color:#6b21a8;font-size:13px;margin-top:6px;">Your permissions: {perms}</div>'
        f'</div>'
        f'{_btn("Open Deal Room", magic_link)}'
        f'{expires_html}'
    )
    return {"subject": f"[Vyapaar Network] {inviter} invited you to a Deal Room"[:255],
            "html": _wrap(title, title, body),
            "text": f"{inviter} invited you to the Deal Room for {lead_title}. Open: {magic_link}"}


def _render_approval_requested(ctx):
    title = "Approval Requested"
    approval_title = ctx.get("approval_title", "an approval")
    requester = ctx.get("requester_name") or "the team"
    lead_title = ctx.get("lead_title", "")
    lead_url = ctx.get("lead_url") or f"https://app.vyapaar.net/leads/{ctx.get('lead_id','')}"
    deal_html = f'<div style="color:#1e40af;font-size:13px;margin-top:6px;">Deal: {lead_title}</div>' if lead_title else ""
    body = (
        f'<p>Hi {ctx.get("recipient_name","there")},</p>'
        f'<p><strong>{requester}</strong> has requested your approval:</p>'
        f'<div style="background:#dbeafe;border-radius:8px;padding:14px 16px;margin:10px 0;">'
        f'<div style="font-size:16px;font-weight:600;">{approval_title}</div>'
        f'{deal_html}'
        f'</div>'
        f'{_btn("Review & Respond", lead_url)}'
    )
    return {"subject": f"[Meshora] Approval requested: {approval_title}"[:255],
            "html": _wrap(title, title, body),
            "text": f"{requester} requested your approval for: {approval_title}. {lead_url}"}


def _render_payment_received(ctx):
    title = "Payment Received"
    amount = ctx.get("amount_formatted") or ctx.get("amount") or ""
    customer = ctx.get("customer_company") or ctx.get("customer_name") or "Customer"
    commercial_url = ctx.get("commercial_url") or f"https://app.vyapaar.net/commercials/{ctx.get('commercial_id','')}"
    body = (
        f'<p>Hi {ctx.get("recipient_name","there")},</p>'
        f'<p>A payment was recorded against your deal:</p>'
        f'<div style="background:#d1fae5;border-radius:8px;padding:14px 16px;margin:10px 0;">'
        f'<div style="font-size:18px;font-weight:700;color:#065f46;">{amount}</div>'
        f'<div style="color:#047857;font-size:14px;margin-top:6px;">From {customer}</div>'
        f'</div>'
        f'{_btn("View Commercial", commercial_url)}'
    )
    return {"subject": f"[Meshora] Payment received: {amount}"[:255],
            "html": _wrap(title, title, body),
            "text": f"Payment received: {amount} from {customer}. {commercial_url}"}


def _render_generic(ctx):
    """Fallback for notification types without a dedicated template."""
    title = ctx.get("title") or "Notification"
    message = ctx.get("message") or ""
    cta_url = ctx.get("cta_url")
    body = (
        f'<p>Hi {ctx.get("recipient_name","there")},</p>'
        f'<p>{message}</p>'
        f'{_btn("Open Meshora", cta_url) if cta_url else ""}'
    )
    return {"subject": f"[Meshora] {title}"[:255],
            "html": _wrap(title, title, body),
            "text": message}


_RENDERERS = {
    "lead_assigned": _render_lead_assigned,
    "follow_up_reminder": _render_follow_up_reminder,
    "deal_room_invite": _render_deal_room_invite,
    "approval_requested": _render_approval_requested,
    "payment_received": _render_payment_received,
    "comment_mention": _render_generic,
    "lead_status_changed": _render_generic,
    "lead_won": _render_generic,
    "milestone_due": _render_generic,
    "invoice_overdue": _render_generic,
    "follow_up_overdue": _render_generic,
    "commercial_created": _render_generic,
    "weekly_war_room_digest": _render_generic,
}
