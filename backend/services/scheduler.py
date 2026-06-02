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


async def _resolve_commercial_recipient(db, commercial: dict) -> Optional[dict]:
    """Find a user to email about a milestone. Tries the finance/owner chain
    first, then falls back to the lead creator. Returns None if no email
    address resolvable."""
    candidate_keys = ('account_manager_id', 'billing_contact_id', 'contract_owner_id', 'project_owner_id')
    for k in candidate_keys:
        uid = commercial.get(k)
        if uid:
            u = await db.users.find_one({"id": uid, "is_active": {"$ne": False}}, {"_id": 0})
            if u and u.get('email'):
                return u
    lead_id = commercial.get('lead_id')
    if lead_id:
        lead = await db.leads.find_one({"id": lead_id}, {"_id": 0, "created_by": 1, "selling_partner_id": 1})
        for k in ('created_by', 'selling_partner_id'):
            uid = (lead or {}).get(k)
            if uid:
                u = await db.users.find_one({"id": uid, "is_active": {"$ne": False}}, {"_id": 0})
                if u and u.get('email'):
                    return u
    return None


def _format_amount(amount, currency="INR") -> str:
    if amount is None:
        return ""
    try:
        amt = float(amount)
    except Exception:
        return str(amount)
    if currency == "INR":
        # Indian formatting: 1,25,000.00
        s = f"{amt:,.2f}"
        # Convert "125,000.00" → "1,25,000.00"
        head, _, tail = s.partition(".")
        head = head.replace(",", "")
        sign = ""
        if head.startswith("-"):
            sign = "-"
            head = head[1:]
        if len(head) > 3:
            last3 = head[-3:]
            rest = head[:-3]
            rest = ",".join([rest[max(i-2,0):i] for i in range(len(rest), 0, -2)][::-1])
            head = f"{rest},{last3}"
        return f"₹{sign}{head}.{tail}"
    return f"{currency} {amt:,.2f}"


def _hours_until(target: datetime, now: datetime) -> float:
    return (target - now).total_seconds() / 3600


def _milestone_due_label(hours: float) -> str:
    if hours < 0:
        h = abs(hours)
        if h < 1:
            return "just now"
        if h < 24:
            return f"{int(h)}h ago"
        return f"{int(h/24)}d ago"
    if hours < 1:
        return "within the hour"
    if hours < 24:
        return f"in {int(hours)}h"
    return f"in {int(hours/24)}d"


async def dispatch_due_milestone_reminders(db, zeptomail, window_hours: int = 48) -> dict:
    """Phase 33.5 — scan commercials for milestones whose invoice_due_date (or
    delivery_date as fallback) is within the next `window_hours` and which are
    not yet completed (paid/cancelled) and not yet reminded. Sends one
    `milestone_due` email per milestone, then flags `milestone_reminder_sent=True`.

    The same flag also fires for milestones that are already overdue (so the
    finance team gets pinged at least once after the deadline)."""
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(hours=window_hours)
    # Cheap filter: only commercials with at least one milestone in a non-terminal status
    cursor = db.commercials.find(
        {"milestones": {"$elemMatch": {
            "status": {"$nin": ["payment_received", "cancelled"]},
            "milestone_reminder_sent": {"$ne": True},
        }}},
        {"_id": 0}
    )
    scanned = 0
    sent = 0
    async for c in cursor:
        scanned += 1
        for m in (c.get('milestones') or []):
            if m.get('milestone_reminder_sent'):
                continue
            status = (m.get('status') or '').lower()
            if status in ('payment_received', 'cancelled'):
                continue
            # Pick the most informative due date
            raw_due = m.get('invoice_due_date') or m.get('delivery_date')
            due_kind = 'invoice' if m.get('invoice_due_date') else 'delivery'
            if not raw_due:
                continue
            try:
                if len(raw_due) == 10 and raw_due[4] == '-' and raw_due[7] == '-':
                    due_dt = datetime.strptime(raw_due, "%Y-%m-%d").replace(hour=17, tzinfo=timezone.utc)
                else:
                    due_dt = datetime.fromisoformat(raw_due.replace('Z', '+00:00'))
                    if due_dt.tzinfo is None:
                        due_dt = due_dt.replace(tzinfo=timezone.utc)
            except Exception:
                # Mark unparseable as sent to avoid scanning forever
                await db.commercials.update_one(
                    {"id": c['id'], "milestones.id": m['id']},
                    {"$set": {
                        "milestones.$.milestone_reminder_sent": True,
                        "milestones.$.milestone_reminder_sent_at": now.isoformat(),
                        "milestones.$.milestone_reminder_skip_reason": "unparseable_date",
                    }}
                )
                continue

            # Only fire when due is within window (covers "approaching deadline" + "just slipped past")
            if due_dt > window_end:
                continue

            recipient = await _resolve_commercial_recipient(db, c)
            if not recipient:
                await db.commercials.update_one(
                    {"id": c['id'], "milestones.id": m['id']},
                    {"$set": {
                        "milestones.$.milestone_reminder_sent": True,
                        "milestones.$.milestone_reminder_sent_at": now.isoformat(),
                        "milestones.$.milestone_reminder_skip_reason": "no_recipient_resolvable",
                    }}
                )
                continue

            prefs = recipient.get('notification_preferences') or {}
            if prefs.get('milestone_due', True) is False:
                await db.commercials.update_one(
                    {"id": c['id'], "milestones.id": m['id']},
                    {"$set": {
                        "milestones.$.milestone_reminder_sent": True,
                        "milestones.$.milestone_reminder_sent_at": now.isoformat(),
                        "milestones.$.milestone_reminder_skip_reason": "opted_out",
                    }}
                )
                continue

            hours_left = _hours_until(due_dt, now)
            ctx = {
                "recipient_name": recipient.get('name', ''),
                "milestone_name": m.get('name') or "Milestone",
                "customer_company": c.get('customer_name') or "",
                "amount_formatted": _format_amount(m.get('amount'), c.get('currency', 'INR')),
                "due_date": raw_due,
                "due_label": _milestone_due_label(hours_left),
                "hours_left": hours_left,
                "due_kind": due_kind,
                "commercial_id": c['id'],
                "commercial_url": f"https://app.vyapaar.net/commercials/{c['id']}",
            }
            rendered = zeptomail.render("milestone_due", ctx) or {}
            result = await zeptomail.send_email(
                to_address=recipient['email'],
                to_name=recipient.get('name'),
                subject=rendered.get("subject") or f"[Meshora] Milestone due: {ctx['milestone_name']}",
                html_body=rendered.get("html") or f"<p>Milestone '{ctx['milestone_name']}' due {ctx['due_label']}.</p>",
                text_body=rendered.get("text"),
                db=db,
                notification_type="milestone_due",
                user_id=recipient.get('id'),
                correlation_id=f"milestone:{m['id']}",
            )
            update = {
                "milestones.$.milestone_reminder_sent": True,
                "milestones.$.milestone_reminder_sent_at": now.isoformat(),
                "milestones.$.milestone_reminder_recipient_id": recipient.get('id'),
                "milestones.$.milestone_reminder_result_ok": bool(result.get('ok')),
            }
            if not result.get('ok'):
                update["milestones.$.milestone_reminder_error"] = str(result.get('error'))[:500]
            await db.commercials.update_one(
                {"id": c['id'], "milestones.id": m['id']},
                {"$set": update}
            )
            if result.get('ok'):
                sent += 1
                logger.info("Milestone-due reminder sent: commercial=%s milestone=%s to=%s", c['id'], m['id'], recipient['email'])
    return {"scanned": scanned, "sent": sent, "now": now.isoformat(), "window_hours": window_hours}


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
        # Piggyback the milestone-due scan on the same minute-tick.
        try:
            res = await dispatch_due_milestone_reminders(db, zeptomail)
            if res.get('sent'):
                logger.info("Milestone-due pass: scanned=%s sent=%s", res['scanned'], res['sent'])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Milestone-due loop iteration crashed: %s", e)
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
