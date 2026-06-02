"""Follow-up reminder scheduler (Phase 33 — Jun 2026).

Lightweight in-process asyncio loop, no external deps.
Spawned from server.py's @app.on_event("startup").

Every 60 seconds:
  1. Scan all leads with at least one incomplete + un-reminded follow-up.
  2. For each such follow-up, compute the reminder_due_at:
       reminder_due_at = scheduled_date 00:00:00 UTC - reminder_minutes_before
     If reminder_minutes_before == 0, skip.
  3. If now >= reminder_due_at AND reminder_sent != True → render the
     follow_up_reminder template and dispatch via zeptomail.send_email().
  4. Mark the follow-up's `reminder_sent = True` + `reminder_sent_at` on success.

Recipient resolution priority (first non-empty wins):
   1. follow_up.assignee_id (Phase 30)
   2. lead.selling_partner_id
   3. lead.created_by

If we still can't find a user, the reminder is marked sent (skipped) to avoid
hammering the same lead every minute.

The loop is idempotent: re-running with the same DB state produces no duplicate
emails because of the `reminder_sent` flag.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

SCAN_INTERVAL_SECONDS = 60
_RUNNING_TASK: Optional[asyncio.Task] = None


def _parse_scheduled_dt(scheduled_date: str) -> Optional[datetime]:
    """Follow-ups store scheduled_date as 'YYYY-MM-DD' or ISO datetime.
    We anchor date-only values to 09:00 UTC so a "Monday" reminder doesn't
    blast at midnight server-time."""
    if not scheduled_date:
        return None
    s = scheduled_date.strip()
    try:
        # Plain date — anchor at 09:00 UTC (=2:30pm IST), the typical "morning of"
        if len(s) == 10 and s[4] == '-' and s[7] == '-':
            return datetime.strptime(s, "%Y-%m-%d").replace(hour=9, tzinfo=timezone.utc)
        # Full ISO
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        logger.warning("Could not parse follow-up scheduled_date: %r", scheduled_date)
        return None


async def _resolve_recipient(db, lead: dict, followup: dict) -> Optional[dict]:
    """Find a user record for this reminder. Returns None if no one to mail."""
    for uid_key in ('assignee_id',):
        uid = followup.get(uid_key)
        if uid:
            u = await db.users.find_one({"id": uid, "is_active": {"$ne": False}}, {"_id": 0})
            if u and u.get('email'):
                return u
    for uid_key in ('selling_partner_id', 'created_by'):
        uid = lead.get(uid_key)
        if uid:
            u = await db.users.find_one({"id": uid, "is_active": {"$ne": False}}, {"_id": 0})
            if u and u.get('email'):
                return u
    return None


async def _process_lead_followups(db, zeptomail, lead: dict, now: datetime) -> int:
    """Process all due reminders on a single lead. Returns count dispatched."""
    sent_count = 0
    follow_ups = lead.get('follow_ups') or []
    for f in follow_ups:
        if f.get('is_completed'):
            continue
        if f.get('reminder_sent'):
            continue
        minutes_before = int(f.get('reminder_minutes_before') or 0)
        if minutes_before <= 0:
            # User chose "No reminder" — mark sent so we don't re-check forever
            await db.leads.update_one(
                {"id": lead['id'], "follow_ups.id": f['id']},
                {"$set": {
                    "follow_ups.$.reminder_sent": True,
                    "follow_ups.$.reminder_sent_at": now.isoformat(),
                    "follow_ups.$.reminder_skip_reason": "no_reminder_requested",
                }}
            )
            continue
        scheduled_dt = _parse_scheduled_dt(f.get('scheduled_date'))
        if not scheduled_dt:
            await db.leads.update_one(
                {"id": lead['id'], "follow_ups.id": f['id']},
                {"$set": {
                    "follow_ups.$.reminder_sent": True,
                    "follow_ups.$.reminder_sent_at": now.isoformat(),
                    "follow_ups.$.reminder_skip_reason": "unparseable_date",
                }}
            )
            continue
        reminder_due_at = scheduled_dt - timedelta(minutes=minutes_before)
        if now < reminder_due_at:
            continue  # not yet

        recipient = await _resolve_recipient(db, lead, f)
        if not recipient:
            await db.leads.update_one(
                {"id": lead['id'], "follow_ups.id": f['id']},
                {"$set": {
                    "follow_ups.$.reminder_sent": True,
                    "follow_ups.$.reminder_sent_at": now.isoformat(),
                    "follow_ups.$.reminder_skip_reason": "no_recipient_resolvable",
                }}
            )
            continue

        # Respect notification preferences (opt-IN by default)
        prefs = recipient.get('notification_preferences') or {}
        if prefs.get('follow_up_reminder', True) is False:
            await db.leads.update_one(
                {"id": lead['id'], "follow_ups.id": f['id']},
                {"$set": {
                    "follow_ups.$.reminder_sent": True,
                    "follow_ups.$.reminder_sent_at": now.isoformat(),
                    "follow_ups.$.reminder_skip_reason": "opted_out",
                }}
            )
            continue

        ctx = {
            "recipient_name": recipient.get('name', ''),
            "lead_title": lead.get('title') or lead.get('customer_company') or "your lead",
            "scheduled_date": scheduled_dt.strftime('%A, %d %b %Y · %H:%M UTC'),
            "notes": f.get('notes') or "",
            "lead_id": lead['id'],
            "lead_url": f"https://app.vyapaar.net/leads/{lead['id']}",
        }
        rendered = zeptomail.render("follow_up_reminder", ctx) or {}
        result = await zeptomail.send_email(
            to_address=recipient['email'],
            to_name=recipient.get('name'),
            subject=rendered.get("subject") or f"[Meshora] Follow-up reminder: {ctx['lead_title']}",
            html_body=rendered.get("html") or f"<p>Reminder: follow-up on {ctx['lead_title']}.</p>",
            text_body=rendered.get("text"),
            db=db,
            notification_type="follow_up_reminder",
            user_id=recipient.get('id'),
            correlation_id=f"followup:{f['id']}",
        )

        update = {
            "follow_ups.$.reminder_sent": True,
            "follow_ups.$.reminder_sent_at": now.isoformat(),
            "follow_ups.$.reminder_recipient_id": recipient.get('id'),
            "follow_ups.$.reminder_result_ok": bool(result.get('ok')),
        }
        if not result.get('ok'):
            update["follow_ups.$.reminder_error"] = str(result.get('error'))[:500]
        await db.leads.update_one(
            {"id": lead['id'], "follow_ups.id": f['id']},
            {"$set": update}
        )
        if result.get('ok'):
            sent_count += 1
            logger.info("Follow-up reminder sent: lead=%s followup=%s to=%s", lead['id'], f['id'], recipient['email'])
    return sent_count


async def dispatch_due_reminders(db, zeptomail) -> dict:
    """Run a single scan-and-dispatch pass. Returns {'scanned': X, 'sent': Y}."""
    now = datetime.now(timezone.utc)
    # Cheap filter: only leads with at least one incomplete follow-up
    cursor = db.leads.find(
        {"follow_ups": {"$elemMatch": {"is_completed": {"$ne": True}, "reminder_sent": {"$ne": True}}}},
        {"_id": 0, "id": 1, "title": 1, "customer_company": 1, "follow_ups": 1, "created_by": 1, "selling_partner_id": 1}
    )
    scanned = 0
    sent = 0
    async for lead in cursor:
        scanned += 1
        try:
            sent += await _process_lead_followups(db, zeptomail, lead, now)
        except Exception as e:
            logger.exception("Follow-up reminder pass failed for lead %s: %s", lead.get('id'), e)
    return {"scanned": scanned, "sent": sent, "now": now.isoformat()}


async def _reminder_loop(db, zeptomail) -> None:
    logger.info("Follow-up reminder loop started (interval=%ss)", SCAN_INTERVAL_SECONDS)
    while True:
        try:
            res = await dispatch_due_reminders(db, zeptomail)
            if res.get('sent'):
                logger.info("Follow-up reminder pass: scanned=%s sent=%s", res['scanned'], res['sent'])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Reminder loop iteration crashed: %s", e)
        try:
            await asyncio.sleep(SCAN_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            raise


def start_reminder_loop(db, zeptomail) -> None:
    """Idempotent — only starts the loop once per process."""
    global _RUNNING_TASK
    if _RUNNING_TASK and not _RUNNING_TASK.done():
        return
    _RUNNING_TASK = asyncio.create_task(_reminder_loop(db, zeptomail))


def stop_reminder_loop() -> None:
    global _RUNNING_TASK
    if _RUNNING_TASK and not _RUNNING_TASK.done():
        _RUNNING_TASK.cancel()
    _RUNNING_TASK = None
