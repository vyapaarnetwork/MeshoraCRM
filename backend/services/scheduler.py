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
from datetime import datetime, timezone, timedelta, date
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


async def _resolve_commercial_recipients_multi(db, commercial: dict) -> list:
    """Phase 36 — multi-recipient resolver for commercials notifications.
    Returns a de-duped list of {id,name,email,role} dicts containing:
      - Account Manager
      - Billing Contact
      - Contract Owner / Project Owner / Delivery SPOC (if present)
      - All active Vyapaar Super Admin + Finance users (compliance bcc-style)
    The caller can additionally honor per-user notification_preferences."""
    seen = set()
    out: list = []

    def _add(u: Optional[dict]):
        if not u or not u.get('email'):
            return
        if u['id'] in seen:
            return
        seen.add(u['id'])
        out.append(u)

    role_keys = (
        'account_manager_id', 'billing_contact_id', 'contract_owner_id',
        'project_owner_id', 'delivery_spoc_id',
    )
    for k in role_keys:
        uid = commercial.get(k)
        if uid:
            u = await db.users.find_one({"id": uid, "is_active": {"$ne": False}}, {"_id": 0})
            _add(u)

    # Vyapaar admin + finance team — always notified for revenue events
    admins = await db.users.find(
        {"is_active": {"$ne": False}, "role": {"$in": ["super_admin", "vyapaar_finance"]}},
        {"_id": 0},
    ).to_list(100)
    for u in admins:
        _add(u)
    return out



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

            # Phase 36 — also CC the full Vyapaar revenue chain (admin + finance +
            # Account Manager + Billing Contact) so they are always in the loop.
            cc_pool = await _resolve_commercial_recipients_multi(db, c)
            cc_emails = [
                u['email'] for u in cc_pool
                if u.get('email') and u['id'] != recipient.get('id')
                and (u.get('notification_preferences') or {}).get('milestone_due', True) is not False
            ]

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
            rendered = (await zeptomail.render_with_db_override(db, "milestone_due", ctx)) or {}
            result = await zeptomail.send_email(
                to_address=recipient['email'],
                to_name=recipient.get('name'),
                cc=cc_emails or None,  # Phase 36 — keep admin/finance + AM/billing in the loop
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


async def dispatch_commercial_renewal_reminders(db, zeptomail) -> dict:
    """Phase 36 — for every active Recurring contract whose contract_end_date is
    within renewal_notice_days (default 30), send ONE reminder to the AM +
    Billing Contact + admin/finance team. Idempotent via `renewal_reminder_sent`."""
    if not zeptomail.is_configured():
        return {"scanned": 0, "sent": 0, "skipped": "zeptomail_not_configured"}
    now = datetime.now(timezone.utc)
    today = now.date()
    cursor = db.commercials.find({
        "type": "recurring",
        "contract_status": {"$nin": ["expired", "cancelled"]},
        "contract_end_date": {"$nin": [None, ""]},
        "renewal_reminder_sent": {"$ne": True},
    }, {"_id": 0})
    scanned, sent = 0, 0
    async for c in cursor:
        scanned += 1
        try:
            end_str = c.get('contract_end_date') or ''
            if not end_str:
                continue
            try:
                end_d = date.fromisoformat(end_str[:10])
            except Exception:
                continue
            notice_days = int(c.get('renewal_notice_days') or 30)
            days_to_renew = (end_d - today).days
            # Window: enter the notice window OR up to 7 days post-expiry
            if days_to_renew > notice_days or days_to_renew < -7:
                continue
            recipients = await _resolve_commercial_recipients_multi(db, c)
            if not recipients:
                await db.commercials.update_one(
                    {"id": c['id']},
                    {"$set": {"renewal_reminder_sent": True, "renewal_reminder_skip_reason": "no_recipient"}},
                )
                continue
            primary = recipients[0]
            cc = [u['email'] for u in recipients[1:] if u.get('email')]
            label = "expired" if days_to_renew < 0 else (
                "today" if days_to_renew == 0 else f"in {days_to_renew} days"
            )
            subject = f"[Meshora] Contract renewal {label}: {c.get('customer_name','')}"
            url = f"https://app.vyapaar.net/commercials/{c['id']}"
            body = (
                f'<p>Hi {primary.get("name","there")},</p>'
                f'<p>The recurring contract for <strong>{c.get("customer_name","this customer")}</strong> ends on <strong>{end_str[:10]}</strong> ({label}).</p>'
                f'<div style="background:#f9fafb;border-left:4px solid #4f46e5;padding:14px 16px;margin:12px 0;border-radius:6px;">'
                f'<div style="font-size:16px;font-weight:600;">{c.get("lead_title","Contract")}</div>'
                f'<div style="color:#6b7280;font-size:13px;margin-top:4px;">'
                f'Value: {_format_amount(c.get("contract_value"), c.get("currency","INR"))} &middot; Renewal type: {c.get("renewal_type","manual")}'
                f'</div></div>'
                f'{zeptomail._btn("Open Commercial", url)}'  # noqa: SLF001
            )
            html = zeptomail._wrap("Renewal due soon", "Renewal Reminder", body)  # noqa: SLF001
            res = await zeptomail.send_email(
                to_address=primary['email'], to_name=primary.get('name'), cc=cc or None,
                subject=subject, html_body=html, db=db,
                notification_type="renewal_reminder", user_id=primary.get('id'),
                correlation_id=f"renewal:{c['id']}",
            )
            await db.commercials.update_one(
                {"id": c['id']},
                {"$set": {
                    "renewal_reminder_sent": True,
                    "renewal_reminder_sent_at": now.isoformat(),
                    "renewal_reminder_result_ok": bool(res.get('ok')),
                }},
            )
            if res.get('ok'):
                sent += 1
        except Exception as e:
            logger.exception("renewal reminder failed for commercial %s: %s", c.get('id'), e)
    return {"scanned": scanned, "sent": sent, "now": now.isoformat()}


async def dispatch_invoice_overdue_reminders(db, zeptomail) -> dict:
    """Phase 36 — daily scan for `commercial_invoices` whose due_date < today
    and status is in (raised, partial). Fires one reminder per invoice
    (idempotent via `overdue_reminder_sent`)."""
    if not zeptomail.is_configured():
        return {"scanned": 0, "sent": 0, "skipped": "zeptomail_not_configured"}
    now = datetime.now(timezone.utc)
    today_iso = now.date().isoformat()
    cursor = db.commercial_invoices.find({
        "status": {"$in": ["raised", "partial"]},
        "due_date": {"$lt": today_iso, "$nin": [None, ""]},
        "overdue_reminder_sent": {"$ne": True},
    }, {"_id": 0})
    scanned, sent = 0, 0
    async for inv in cursor:
        scanned += 1
        try:
            c = await db.commercials.find_one({"id": inv.get('commercial_id')}, {"_id": 0})
            if not c:
                continue
            recipients = await _resolve_commercial_recipients_multi(db, c)
            if not recipients:
                await db.commercial_invoices.update_one({"id": inv['id']}, {"$set": {"overdue_reminder_sent": True}})
                continue
            primary = recipients[0]
            cc = [u['email'] for u in recipients[1:] if u.get('email')]
            amount = _format_amount(inv.get('amount'), c.get('currency', 'INR'))
            days_overdue = max(0, (now.date() - date.fromisoformat(inv['due_date'][:10])).days)
            subject = f"[Meshora] Invoice overdue: {inv.get('invoice_number','')} ({amount})"
            url = f"https://app.vyapaar.net/commercials/{c['id']}"
            body = (
                f'<p>Hi {primary.get("name","there")},</p>'
                f'<p>Invoice <strong>{inv.get("invoice_number","")}</strong> for <strong>{c.get("customer_name","this customer")}</strong> is <strong>{days_overdue} day(s) overdue</strong>.</p>'
                f'<div style="background:#fef2f2;border-left:4px solid #dc2626;padding:14px 16px;margin:12px 0;border-radius:6px;">'
                f'<div style="font-size:16px;font-weight:600;">{amount}</div>'
                f'<div style="color:#6b7280;font-size:13px;margin-top:4px;">Due {inv.get("due_date","")[:10]}</div>'
                f'</div>'
                f'{zeptomail._btn("Open Commercial", url)}'  # noqa: SLF001
            )
            html = zeptomail._wrap("Invoice overdue", "Invoice Overdue", body)  # noqa: SLF001
            res = await zeptomail.send_email(
                to_address=primary['email'], to_name=primary.get('name'), cc=cc or None,
                subject=subject, html_body=html, db=db,
                notification_type="invoice_overdue", user_id=primary.get('id'),
                correlation_id=f"invoice_overdue:{inv['id']}",
            )
            await db.commercial_invoices.update_one(
                {"id": inv['id']},
                {"$set": {
                    "overdue_reminder_sent": True,
                    "overdue_reminder_sent_at": now.isoformat(),
                    "status": "overdue",
                }},
            )
            if res.get('ok'):
                sent += 1
        except Exception as e:
            logger.exception("invoice overdue reminder failed for invoice %s: %s", inv.get('id'), e)
    return {"scanned": scanned, "sent": sent, "now": now.isoformat()}



async def dispatch_monthly_won_digest(db, zeptomail, force: bool = False) -> dict:
    """Phase 34.5 — fires on the 1st of every month at 09:00 UTC. Sends a
    comparison digest of last-month vs prior-month won deals to all active
    Super Admins + Vyapaar Ops users. Idempotent via `monthly_digest_runs`
    collection — only one send per (year, month) tuple even if the loop catches
    the 09:xx window multiple times."""
    now = datetime.now(timezone.utc)
    # Determine "last month"
    if now.month == 1:
        last_month = (now.year - 1, 12)
        prior_month = (now.year - 1, 11)
    elif now.month == 2:
        last_month = (now.year, 1)
        prior_month = (now.year - 1, 12)
    else:
        last_month = (now.year, now.month - 1)
        prior_month = (now.year, now.month - 2)

    if not force:
        # Only run on the 1st, between 09:00 and 09:59 UTC
        if now.day != 1 or now.hour != 9:
            return {"skipped": True, "reason": "outside_window", "now": now.isoformat()}
    run_key = f"{last_month[0]}-{last_month[1]:02d}"
    existing = await db.monthly_digest_runs.find_one({"key": run_key})
    if existing and not force:
        return {"skipped": True, "reason": "already_sent", "key": run_key}

    # Aggregate won leads for last_month & prior_month
    won_statuses = await db.lead_statuses.find({"is_won": True}, {"_id": 0}).to_list(20)
    won_ids = [s['id'] for s in won_statuses]
    if not won_ids:
        return {"skipped": True, "reason": "no_won_statuses"}
    leads = await db.leads.find({"status_id": {"$in": won_ids}}, {"_id": 0}).to_list(10000)

    def _month_of(raw):
        if not raw:
            return None
        try:
            if len(raw) == 10:
                return (int(raw[:4]), int(raw[5:7]))
            return (int(raw[:4]), int(raw[5:7]))
        except Exception:
            return None

    def _bucket(lead):
        anchor = lead.get('closure_date') or (lead.get('updated_at') or '')[:10]
        return _month_of(anchor)

    last_leads = [l for l in leads if _bucket(l) == last_month]
    prior_leads = [l for l in leads if _bucket(l) == prior_month]
    last_total = sum(float(l.get('deal_value') or 0) for l in last_leads)
    prior_total = sum(float(l.get('deal_value') or 0) for l in prior_leads)

    last_label = datetime(last_month[0], last_month[1], 1).strftime('%B %Y')
    prior_label = datetime(prior_month[0], prior_month[1], 1).strftime('%B %Y')
    delta_count = len(last_leads) - len(prior_leads)
    delta_value = last_total - prior_total
    delta_pct = round((delta_count / len(prior_leads)) * 100, 1) if prior_leads else None

    # Render
    def _fmt_inr(amount):
        try:
            from services.scheduler import _format_amount
            return _format_amount(amount, "INR")
        except Exception:
            return f"₹{amount:,.2f}"

    deals_rows = "".join([
        f'<tr><td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;">{l.get("title") or "—"}</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;color:#6b7280;">{l.get("customer_company") or l.get("customer_name") or "—"}</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;text-align:right;font-weight:600;">{_fmt_inr(float(l.get("deal_value") or 0))}</td></tr>'
        for l in sorted(last_leads, key=lambda x: float(x.get('deal_value') or 0), reverse=True)[:20]
    ]) or '<tr><td colspan="3" style="padding:12px;color:#6b7280;text-align:center;">No deals closed last month.</td></tr>'

    arrow = "↑" if delta_count > 0 else ("↓" if delta_count < 0 else "→")
    arrow_color = "#059669" if delta_count > 0 else ("#dc2626" if delta_count < 0 else "#6b7280")
    pct_text = f"{delta_pct:+.1f}%" if delta_pct is not None else "n/a"

    body_html = (
        f'<p>Hi team,</p>'
        f'<p>Here\'s the monthly performance digest comparing <strong>{last_label}</strong> with <strong>{prior_label}</strong>:</p>'
        f'<table cellpadding="0" cellspacing="0" border="0" style="width:100%;margin:16px 0;">'
        f'<tr>'
        f'<td style="background:#ede9fe;border-radius:8px;padding:14px;text-align:center;width:48%;">'
        f'<div style="font-size:12px;color:#6b21a8;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">{last_label}</div>'
        f'<div style="font-size:28px;font-weight:700;color:#5b21b6;margin:4px 0;">{len(last_leads)}</div>'
        f'<div style="font-size:14px;color:#6b21a8;">deals · {_fmt_inr(last_total)}</div>'
        f'</td>'
        f'<td style="width:4%;"></td>'
        f'<td style="background:#f3f4f6;border-radius:8px;padding:14px;text-align:center;width:48%;">'
        f'<div style="font-size:12px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">{prior_label}</div>'
        f'<div style="font-size:28px;font-weight:700;color:#374151;margin:4px 0;">{len(prior_leads)}</div>'
        f'<div style="font-size:14px;color:#6b7280;">deals · {_fmt_inr(prior_total)}</div>'
        f'</td>'
        f'</tr></table>'
        f'<p style="font-size:15px;"><span style="font-size:22px;color:{arrow_color};">{arrow}</span> '
        f'<strong style="color:{arrow_color};">{abs(delta_count)}</strong> deals '
        f'({pct_text}) — value change <strong>{_fmt_inr(delta_value)}</strong></p>'
        f'<h3 style="margin-top:24px;font-size:16px;">Top deals closed in {last_label}</h3>'
        f'<table cellpadding="0" cellspacing="0" border="0" style="width:100%;border:1px solid #e5e7eb;border-radius:8px;border-collapse:separate;border-spacing:0;font-size:14px;">'
        f'<thead><tr style="background:#f9fafb;">'
        f'<th style="text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;font-size:12px;color:#6b7280;text-transform:uppercase;">Deal</th>'
        f'<th style="text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;font-size:12px;color:#6b7280;text-transform:uppercase;">Customer</th>'
        f'<th style="text-align:right;padding:8px;border-bottom:1px solid #e5e7eb;font-size:12px;color:#6b7280;text-transform:uppercase;">Value</th>'
        f'</tr></thead>'
        f'<tbody>{deals_rows}</tbody>'
        f'</table>'
    )
    subject = f"[Meshora] {last_label} won-deals digest — {len(last_leads)} deals, {_fmt_inr(last_total)}"

    # Recipients: super_admin + is_vyapaar_ops + vyapaar_finance
    recipients = await db.users.find({
        "is_active": {"$ne": False},
        "$or": [
            {"role": "super_admin"},
            {"role": "vyapaar_ops"},
            {"role": "vyapaar_finance"},
            {"is_vyapaar_ops": True},
        ],
    }, {"_id": 0, "email": 1, "name": 1, "id": 1, "notification_preferences": 1}).to_list(200)

    sent = 0
    failed = 0
    for r in recipients:
        if not r.get('email'):
            continue
        prefs = r.get('notification_preferences') or {}
        if prefs.get('monthly_won_digest', True) is False:
            continue
        # Wrap in branded shell
        wrapped = zeptomail._wrap("Monthly Won-Deals Digest", f"{last_label} · Won Deals Digest", body_html)
        result = await zeptomail.send_email(
            to_address=r['email'],
            to_name=r.get('name'),
            subject=subject,
            html_body=wrapped,
            db=db,
            notification_type="monthly_won_digest",
            user_id=r.get('id'),
            correlation_id=f"monthly:{run_key}",
        )
        if result.get('ok'):
            sent += 1
        else:
            failed += 1

    await db.monthly_digest_runs.insert_one({
        "key": run_key,
        "ran_at": now.isoformat(),
        "last_month_label": last_label,
        "last_count": len(last_leads),
        "last_total": last_total,
        "prior_count": len(prior_leads),
        "prior_total": prior_total,
        "recipients_attempted": len(recipients),
        "sent": sent,
        "failed": failed,
    })
    return {"key": run_key, "sent": sent, "failed": failed, "recipients": len(recipients), "last_count": len(last_leads), "prior_count": len(prior_leads)}


async def dispatch_weekly_war_room_digest(db, zeptomail, force: bool = False) -> dict:
    """Phase 34.7 — Mondays 09:xx UTC. Sends a War Room digest grouped by Vyapaar
    Lead Owner so the Vyapaar team can spot what's HOT / BLOCKED / AT-RISK across
    leads they personally own + an Unassigned bucket at the bottom.

    Idempotent via `weekly_digest_runs` keyed by ISO-week (YYYY-Www).
    Recipients: all active super_admin + vyapaar_ops + vyapaar_finance users
    with notification_preferences.weekly_war_room_digest != False.
    """
    now = datetime.now(timezone.utc)
    iso_year, iso_week, iso_dow = now.isocalendar()
    run_key = f"{iso_year}-W{iso_week:02d}"

    if not force:
        # Mondays (ISO dow == 1), 09:xx UTC
        if iso_dow != 1 or now.hour != 9:
            return {"skipped": True, "reason": "outside_window", "now": now.isoformat()}
        existing = await db.weekly_digest_runs.find_one({"key": run_key})
        if existing:
            return {"skipped": True, "reason": "already_sent", "key": run_key}

    # Load leads + statuses
    leads = await db.leads.find({}, {"_id": 0}).to_list(5000)
    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(50)
    status_map = {s['id']: s for s in statuses}

    # Compute health bands inline (lightweight) — anything >7d inactive or with
    # pending approvals counts as "blocked", >14d inactive == "at_risk", high-value
    # recent activity == "hot".
    today = now.date()

    def _days_since(raw):
        if not raw:
            return 999
        try:
            d = datetime.fromisoformat(raw.replace('Z', '+00:00')).date()
            return (today - d).days
        except Exception:
            return 999

    hot, blocked, at_risk = [], [], []
    for l in leads:
        st = status_map.get(l.get('status_id')) or {}
        if st.get('is_won') or st.get('is_lost'):
            continue
        dv = float(l.get('deal_value') or 0)
        days_inactive = _days_since(l.get('updated_at') or l.get('created_at'))
        pending_appr = sum(1 for a in (l.get('approvals') or []) if a.get('status') == 'pending')
        has_blocker = any(
            '#blocker' in (c.get('content') or '').lower() or '#blocked' in (c.get('content') or '').lower()
            for c in (l.get('comments') or [])[-10:]
        )
        if has_blocker or (pending_appr and days_inactive >= 3):
            blocked.append(l)
        elif days_inactive >= 14 and dv >= 100000:
            at_risk.append(l)
        elif days_inactive <= 3 and dv >= 250000:
            hot.append(l)

    all_relevant = {l['id']: l for l in hot + blocked + at_risk}

    # Group by Vyapaar Lead Owner (None bucket = Unassigned)
    grouped = {}
    for lid, l in all_relevant.items():
        owner_id = l.get('vyapaar_lead_owner_id') or '__unassigned__'
        grouped.setdefault(owner_id, {"hot": [], "blocked": [], "at_risk": []})

    for l in hot:
        grouped[l.get('vyapaar_lead_owner_id') or '__unassigned__']['hot'].append(l)
    for l in blocked:
        grouped[l.get('vyapaar_lead_owner_id') or '__unassigned__']['blocked'].append(l)
    for l in at_risk:
        grouped[l.get('vyapaar_lead_owner_id') or '__unassigned__']['at_risk'].append(l)

    # Resolve owner names
    owner_ids = [oid for oid in grouped if oid != '__unassigned__']
    owners = {}
    if owner_ids:
        owners_list = await db.users.find({"id": {"$in": owner_ids}}, {"_id": 0, "id": 1, "name": 1, "email": 1}).to_list(200)
        owners = {u['id']: u for u in owners_list}

    def _fmt_inr(amount):
        try:
            return _format_amount(amount, "INR")
        except Exception:
            return f"₹{amount:,.0f}"

    def _row(bucket_name, lead, accent):
        return (
            f'<tr><td style="padding:5px 8px;border-bottom:1px solid #f1f5f9;color:{accent};font-weight:600;width:60px;">{bucket_name}</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #f1f5f9;">{lead.get("title") or "—"}</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #f1f5f9;color:#64748b;">{lead.get("customer_company") or lead.get("customer_name") or "—"}</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #f1f5f9;text-align:right;font-weight:600;">{_fmt_inr(float(lead.get("deal_value") or 0))}</td></tr>'
        )

    # Sort owners: assigned first (by total count desc), unassigned last
    def _bucket_total(b):
        return len(b['hot']) + len(b['blocked']) + len(b['at_risk'])

    sorted_owners = sorted(
        [oid for oid in grouped if oid != '__unassigned__'],
        key=lambda oid: _bucket_total(grouped[oid]),
        reverse=True,
    )
    if '__unassigned__' in grouped:
        sorted_owners.append('__unassigned__')

    owner_sections = []
    for oid in sorted_owners:
        b = grouped[oid]
        if oid == '__unassigned__':
            header = '⚠️ Unassigned (no Vyapaar Lead Owner)'
            sub = 'These leads need a Vyapaar owner.'
            color = '#dc2626'
        else:
            u = owners.get(oid) or {}
            header = u.get('name') or 'Unknown owner'
            sub = u.get('email') or ''
            color = '#4f46e5'

        rows_html = []
        for l in b['hot']:
            rows_html.append(_row('🔥 HOT', l, '#ea580c'))
        for l in b['blocked']:
            rows_html.append(_row('🚧 BLK', l, '#dc2626'))
        for l in b['at_risk']:
            rows_html.append(_row('⏳ RISK', l, '#7c3aed'))

        owner_sections.append(
            f'<div style="margin:18px 0 8px;">'
            f'<div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:{color};color:#fff;border-radius:6px;">'
            f'<strong>{header}</strong>'
            f'<span style="font-size:11px;opacity:0.85;">{sub}</span>'
            f'<span style="margin-left:auto;font-size:11px;opacity:0.85;">{len(b["hot"])} hot · {len(b["blocked"])} blocked · {len(b["at_risk"])} risk</span>'
            f'</div>'
            f'<table cellpadding="0" cellspacing="0" border="0" style="width:100%;margin-top:6px;font-size:13px;">{"".join(rows_html) or "<tr><td colspan=4 style=padding:8px;color:#94a3b8;font-style:italic;>No active war-room leads.</td></tr>"}</table>'
            f'</div>'
        )

    body_html = (
        f'<p>Hi team,</p>'
        f'<p>Here\'s this week\'s War Room snapshot grouped by Vyapaar Lead Owner. '
        f'Totals: <strong>{len(hot)}</strong> hot · <strong>{len(blocked)}</strong> blocked · <strong>{len(at_risk)}</strong> at-risk.</p>'
        f'{"".join(owner_sections) or "<p style=color:#6b7280>Nothing in the War Room this week — great hygiene 🎉</p>"}'
        f'<p style="margin-top:18px;"><a href="https://app.vyapaar.net/war-room" style="background:#4f46e5;color:#fff;text-decoration:none;padding:8px 16px;border-radius:6px;font-weight:600;">Open War Room</a></p>'
    )

    subject = f"[Meshora] Weekly War Room — {len(hot)} hot · {len(blocked)} blocked · {len(at_risk)} at-risk"

    # Resolve Vyapaar admin recipients
    recipients = await db.users.find({
        "is_active": True,
        "$or": [
            {"role": {"$in": ["super_admin", "vyapaar_ops", "vyapaar_finance"]}},
            {"is_vyapaar_ops": True},
        ],
    }, {"_id": 0, "email": 1, "name": 1, "id": 1, "notification_preferences": 1}).to_list(200)

    sent = failed = 0
    for r in recipients:
        if not r.get('email'):
            continue
        prefs = r.get('notification_preferences') or {}
        if prefs.get('weekly_war_room_digest', True) is False:
            continue
        wrapped = zeptomail._wrap("Weekly War Room Digest", f"Week of {now.strftime('%d %b %Y')}", body_html)
        result = await zeptomail.send_email(
            to_address=r['email'],
            to_name=r.get('name'),
            subject=subject,
            html_body=wrapped,
            db=db,
            notification_type="weekly_war_room_digest",
            user_id=r.get('id'),
            correlation_id=f"weekly:{run_key}",
        )
        if result.get('ok'):
            sent += 1
        else:
            failed += 1

    await db.weekly_digest_runs.insert_one({
        "key": run_key,
        "ran_at": now.isoformat(),
        "hot_count": len(hot),
        "blocked_count": len(blocked),
        "at_risk_count": len(at_risk),
        "owner_breakdown": [
            {
                "owner_id": oid if oid != '__unassigned__' else None,
                "owner_name": (owners.get(oid) or {}).get('name') if oid != '__unassigned__' else 'Unassigned',
                "hot": len(grouped[oid]['hot']),
                "blocked": len(grouped[oid]['blocked']),
                "at_risk": len(grouped[oid]['at_risk']),
            }
            for oid in sorted_owners
        ],
        "recipients_attempted": len(recipients),
        "sent": sent,
        "failed": failed,
    })

    return {
        "key": run_key, "sent": sent, "failed": failed,
        "recipients": len(recipients),
        "hot_count": len(hot), "blocked_count": len(blocked), "at_risk_count": len(at_risk),
        "owner_breakdown_count": len(sorted_owners),
    }


async def dispatch_due_task_reminders(db, zeptomail) -> dict:
    """Phase 35 — scan tasks (action items) whose due_date minus
    reminder_minutes_before has passed and dispatch a `task_due_reminder` email.
    Idempotent via `task_reminder_sent=True` flag. Skip-with-reason audit trail
    mirrors the follow-up dispatcher."""
    now = datetime.now(timezone.utc)
    cursor = db.tasks.find(
        {
            "status": {"$ne": "done"},
            "task_reminder_sent": {"$ne": True},
            "reminder_minutes_before": {"$gt": 0},
            "due_date": {"$nin": [None, ""]},
        },
        {"_id": 0},
    )
    scanned = 0
    sent = 0
    async for task in cursor:
        scanned += 1
        try:
            due_dt = _parse_scheduled_dt(task.get('due_date'))
            if not due_dt:
                await db.tasks.update_one({"id": task['id']}, {"$set": {
                    "task_reminder_sent": True,
                    "task_reminder_sent_at": now.isoformat(),
                    "task_reminder_skip_reason": "unparseable_date",
                }})
                continue
            reminder_due_at = due_dt - timedelta(minutes=int(task.get('reminder_minutes_before') or 0))
            if now < reminder_due_at:
                continue  # not yet

            # Recipient: assignee → creator
            recipient = None
            for uid in (task.get('assignee_id'), task.get('created_by')):
                if uid:
                    u = await db.users.find_one({"id": uid, "is_active": {"$ne": False}}, {"_id": 0})
                    if u and u.get('email'):
                        recipient = u
                        break
            if not recipient:
                await db.tasks.update_one({"id": task['id']}, {"$set": {
                    "task_reminder_sent": True,
                    "task_reminder_sent_at": now.isoformat(),
                    "task_reminder_skip_reason": "no_recipient_resolvable",
                }})
                continue

            prefs = recipient.get('notification_preferences') or {}
            if prefs.get('task_due_reminder', True) is False:
                await db.tasks.update_one({"id": task['id']}, {"$set": {
                    "task_reminder_sent": True,
                    "task_reminder_sent_at": now.isoformat(),
                    "task_reminder_skip_reason": "opted_out",
                }})
                continue

            lead_title = ""
            lead_url = "https://app.vyapaar.net/leads"
            if task.get('lead_id'):
                lead = await db.leads.find_one({"id": task['lead_id']}, {"_id": 0, "title": 1})
                lead_title = (lead or {}).get('title') or ""
                lead_url = f"https://app.vyapaar.net/leads/{task['lead_id']}"

            hours_left = _hours_until(due_dt, now)
            ctx = {
                "recipient_name": recipient.get('name', ''),
                "task_title": task.get('title') or "Action item",
                "description": task.get('description') or "",
                "priority": task.get('priority') or "medium",
                "due_date": due_dt.strftime('%A, %d %b %Y · %H:%M UTC'),
                "due_label": _milestone_due_label(hours_left),
                "lead_title": lead_title or "—",
                "lead_url": lead_url,
            }
            rendered = (await zeptomail.render_with_db_override(db, "task_due_reminder", ctx)) or {}
            result = await zeptomail.send_email(
                to_address=recipient['email'],
                to_name=recipient.get('name'),
                subject=rendered.get("subject") or f"[Meshora] Action item due {ctx['due_label']}: {ctx['task_title']}",
                html_body=rendered.get("html") or f"<p>Action item '{ctx['task_title']}' is due {ctx['due_label']}.</p>",
                text_body=rendered.get("text"),
                db=db,
                notification_type="task_due_reminder",
                user_id=recipient.get('id'),
                correlation_id=f"task:{task['id']}",
            )
            update = {
                "task_reminder_sent": True,
                "task_reminder_sent_at": now.isoformat(),
                "task_reminder_recipient_id": recipient.get('id'),
                "task_reminder_result_ok": bool(result.get('ok')),
            }
            if not result.get('ok'):
                update["task_reminder_error"] = str(result.get('error'))[:500]
            await db.tasks.update_one({"id": task['id']}, {"$set": update})
            if result.get('ok'):
                sent += 1
                logger.info("Task-due reminder sent: task=%s to=%s", task['id'], recipient['email'])
        except Exception as e:
            logger.exception("Task reminder pass failed for task %s: %s", task.get('id'), e)
    return {"scanned": scanned, "sent": sent, "now": now.isoformat()}


async def _scheduler_enabled(db) -> bool:
    """Phase 35 — global kill-switch stored in system_settings. Defaults to ON."""
    try:
        doc = await db.system_settings.find_one({"key": "email_scheduler_enabled"}, {"_id": 0})
        if doc is not None and doc.get('value') is False:
            return False
    except Exception:
        pass
    return True


# ===========================================================================
# Phase 36 — Internal Vyapaar Tasks: exact-time reminder + weekly Monday digest
# ===========================================================================

async def dispatch_due_internal_task_reminders(db, zeptomail) -> dict:
    """Scan internal_tasks whose reminder window has been crossed and fire one
    email per task. Idempotent via the `reminder_sent` flag on each task."""
    now = datetime.now(timezone.utc)
    scanned, sent = 0, 0
    if not zeptomail.is_configured():
        return {"scanned": 0, "sent": 0, "skipped": "zeptomail_not_configured"}
    cursor = db.internal_tasks.find({
        "status": {"$nin": ["done", "cancelled"]},
        "reminder_minutes_before": {"$gt": 0},
        "reminder_sent": {"$ne": True},
        "due_date": {"$nin": [None, ""]},
        "assignee_id": {"$nin": [None, ""]},
    }, {"_id": 0})
    async for task in cursor:
        scanned += 1
        try:
            due = task.get("due_date") or ""
            # Build a UTC datetime for the comparison
            if "T" in due:
                due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
                if due_dt.tzinfo is None:
                    due_dt = due_dt.replace(tzinfo=timezone.utc)
            else:
                # Date-only → fire reminder at 09:00 UTC on that date
                due_dt = datetime.fromisoformat(due + "T09:00:00+00:00")
            fire_at = due_dt - timedelta(minutes=int(task.get("reminder_minutes_before") or 0))
            if now < fire_at:
                continue
            # Look up assignee
            assignee = await db.users.find_one({"id": task["assignee_id"]}, {"_id": 0, "name": 1, "email": 1})
            if not (assignee and assignee.get("email")):
                await db.internal_tasks.update_one({"id": task["id"]}, {"$set": {"reminder_sent": True}})
                continue
            subject = f"[Meshora] Reminder: {task.get('title','Internal Task')[:120]} is due soon"
            url = f"https://app.vyapaar.net/internal-tasks/{task['id']}"
            body = (
                f'<p>Hi {assignee.get("name","there")},</p>'
                f'<p>Your internal task is coming up <strong>{due}</strong>:</p>'
                f'<div style="background:#f9fafb;border-left:4px solid #f59e0b;padding:14px 16px;margin:12px 0;border-radius:6px;">'
                f'<div style="font-size:16px;font-weight:600;">{task.get("title","")}</div>'
                f'<div style="color:#6b7280;font-size:13px;margin-top:4px;">'
                f'Priority: {task.get("priority","medium")} · Category: {task.get("category","operations")}'
                f'</div>'
                f'</div>'
                f'{zeptomail._btn("Open Task", url)}'  # noqa: SLF001
            )
            html = zeptomail._wrap(subject, "Internal Task Reminder", body)  # noqa: SLF001
            res = await zeptomail.send_email(
                to_address=assignee["email"], to_name=assignee.get("name"),
                subject=subject, html_body=html,
                db=db, notification_type="internal_task_due_reminder", user_id=task["assignee_id"],
            )
            if res.get("ok"):
                await db.internal_tasks.update_one({"id": task["id"]}, {"$set": {"reminder_sent": True}})
                sent += 1
        except Exception as e:
            logger.exception("Internal-task reminder failed for task %s: %s", task.get("id"), e)
    return {"scanned": scanned, "sent": sent, "now": now.isoformat()}


async def dispatch_weekly_internal_task_digest(db, zeptomail, force: bool = False) -> dict:
    """Phase 36 — Mondays 09:xx **IST** (03:xx UTC) digest to every active
    Vyapaar internal user. Each recipient receives THEIR personal task picture:
      - Overdue tasks (count + top 5)
      - Tasks due this week
      - New tasks assigned to them in the last 7 days

    Idempotent via `internal_task_digest_runs` keyed by ISO-week.
    """
    now_utc = datetime.now(timezone.utc)
    # IST = UTC + 5:30
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    iso_year, iso_week, iso_dow_ist = now_ist.isocalendar()
    run_key = f"{iso_year}-W{iso_week:02d}"
    if not force:
        # Mondays in IST (iso_dow_ist == 1), 09:xx IST
        if iso_dow_ist != 1 or now_ist.hour != 9:
            return {"skipped": True, "reason": "outside_window", "now_ist": now_ist.isoformat()}
        existing = await db.internal_task_digest_runs.find_one({"key": run_key})
        if existing:
            return {"skipped": True, "reason": "already_sent", "key": run_key}

    if not zeptomail.is_configured():
        return {"skipped": True, "reason": "zeptomail_not_configured"}

    internal_roles = ["super_admin", "vyapaar_ops", "vyapaar_finance"]
    recipients = await db.users.find({
        "is_active": {"$ne": False},
        "role": {"$in": internal_roles},
    }, {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1}).to_list(200)

    today = now_ist.date()
    week_end = today + timedelta(days=6)  # Monday + 6 = Sunday
    seven_days_ago = (now_utc - timedelta(days=7)).isoformat()
    sent = 0
    attempted = 0
    for u in recipients:
        if not u.get("email"):
            continue
        attempted += 1
        # Pull tasks for this user
        my_tasks = await db.internal_tasks.find({
            "$or": [{"assignee_id": u["id"]}, {"created_by": u["id"]}],
            "status": {"$nin": ["done", "cancelled"]},
        }, {"_id": 0}).to_list(500)
        overdue, due_this_week, new_assigned = [], [], []
        for t in my_tasks:
            due = (t.get("due_date") or "")[:10]
            try:
                due_d = date.fromisoformat(due) if due else None
            except Exception:
                due_d = None
            if due_d:
                if due_d < today:
                    overdue.append(t)
                elif today <= due_d <= week_end:
                    due_this_week.append(t)
            # Newly assigned to me in last 7 days
            if (
                t.get("assignee_id") == u["id"]
                and (t.get("updated_at") or t.get("created_at") or "") >= seven_days_ago
            ):
                new_assigned.append(t)
        if not (overdue or due_this_week or new_assigned):
            continue
        subject = f"[Meshora] Your week — {len(overdue)} overdue, {len(due_this_week)} due this week"
        html = _render_internal_task_digest_html(u, overdue, due_this_week, new_assigned, zeptomail)
        res = await zeptomail.send_email(
            to_address=u["email"], to_name=u.get("name"),
            subject=subject, html_body=html,
            db=db, notification_type="internal_task_weekly_digest", user_id=u["id"],
        )
        if res.get("ok"):
            sent += 1
    # Persist run
    await db.internal_task_digest_runs.update_one(
        {"key": run_key},
        {"$set": {"key": run_key, "ran_at": now_utc.isoformat(), "sent": sent, "attempted": attempted}},
        upsert=True,
    )
    return {"key": run_key, "sent": sent, "attempted": attempted, "ran_at": now_utc.isoformat()}


async def dispatch_weekly_finance_digest(db, zeptomail, force: bool = False) -> dict:
    """Phase 39 — Mondays 09:xx **IST** (03:xx UTC) Finance digest to Vyapaar
    Finance, Ops and Admin users. Each digest contains 3 sections:
      (a) Unpaid invoices > 30 days old (event due_date older than 30d AND in
          invoice_raised / invoice_sent / awaiting_payment)
      (b) Referral payables sitting in 'referral_payable' > 15 days
          (event updated_at older than 15d AND lifecycle_status == referral_payable)
      (c) Renewals due within the next 30 days
          (revenue_type == renewal AND today <= due_date <= today + 30d)

    Idempotent via `finance_digest_runs` keyed by ISO-week.
    """
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    iso_year, iso_week, iso_dow_ist = now_ist.isocalendar()
    run_key = f"{iso_year}-W{iso_week:02d}"
    if not force:
        if iso_dow_ist != 1 or now_ist.hour != 9:
            return {"skipped": True, "reason": "outside_window", "now_ist": now_ist.isoformat()}
        existing = await db.finance_digest_runs.find_one({"key": run_key})
        if existing:
            return {"skipped": True, "reason": "already_sent", "key": run_key}

    if not zeptomail.is_configured():
        return {"skipped": True, "reason": "zeptomail_not_configured"}

    today = now_ist.date()
    thirty_days_ago_iso = (today - timedelta(days=30)).isoformat()
    fifteen_days_ago_iso = (now_utc - timedelta(days=15)).isoformat()
    in_30_days_iso = (today + timedelta(days=30)).isoformat()
    today_iso = today.isoformat()

    # (a) Overdue invoices
    overdue_invoices = await db.revenue_events.find({
        "lifecycle_status": {"$in": ["invoice_raised", "invoice_sent", "awaiting_payment"]},
        "due_date": {"$lt": thirty_days_ago_iso, "$ne": None},
    }, {"_id": 0}).sort("due_date", 1).to_list(200)

    # (b) Stale referral payables
    stale_referrals = await db.revenue_events.find({
        "lifecycle_status": "referral_payable",
        "updated_at": {"$lt": fifteen_days_ago_iso},
    }, {"_id": 0}).sort("updated_at", 1).to_list(200)

    # (c) Upcoming renewals
    upcoming_renewals = await db.revenue_events.find({
        "revenue_type": "renewal",
        "due_date": {"$gte": today_iso, "$lte": in_30_days_iso},
        "lifecycle_status": {"$nin": ["closed", "referral_paid"]},
    }, {"_id": 0}).sort("due_date", 1).to_list(200)

    has_content = bool(overdue_invoices or stale_referrals or upcoming_renewals)

    finance_roles = ["super_admin", "vyapaar_ops", "vyapaar_finance"]
    # Also include explicit `is_finance` flagged users regardless of role
    recipients = await db.users.find({
        "is_active": {"$ne": False},
        "$or": [
            {"role": {"$in": finance_roles}},
            {"is_finance": True},
        ],
    }, {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1}).to_list(200)

    sent = 0
    attempted = 0
    for u in recipients:
        if not u.get("email"):
            continue
        attempted += 1
        # Only send to users who actually have something to action OR if user is super_admin
        # (admins always get the digest so they have visibility even when empty)
        if not has_content and u.get('role') != 'super_admin':
            continue
        total = len(overdue_invoices) + len(stale_referrals) + len(upcoming_renewals)
        subject = (
            f"[Meshora Finance] Weekly digest — {len(overdue_invoices)} overdue, "
            f"{len(stale_referrals)} stale referrals, {len(upcoming_renewals)} renewals"
            if has_content else "[Meshora Finance] Weekly digest — all clear ✅"
        )
        _ = total  # noqa: F841
        html = _render_finance_digest_html(u, overdue_invoices, stale_referrals, upcoming_renewals, zeptomail)
        res = await zeptomail.send_email(
            to_address=u["email"], to_name=u.get("name"),
            subject=subject, html_body=html,
            db=db, notification_type="finance_weekly_digest", user_id=u["id"],
        )
        if res.get("ok"):
            sent += 1
    await db.finance_digest_runs.update_one(
        {"key": run_key},
        {"$set": {
            "key": run_key, "ran_at": now_utc.isoformat(),
            "sent": sent, "attempted": attempted,
            "overdue_count": len(overdue_invoices),
            "stale_referral_count": len(stale_referrals),
            "renewals_count": len(upcoming_renewals),
        }},
        upsert=True,
    )
    return {
        "key": run_key, "sent": sent, "attempted": attempted,
        "overdue_count": len(overdue_invoices),
        "stale_referral_count": len(stale_referrals),
        "renewals_count": len(upcoming_renewals),
        "ran_at": now_utc.isoformat(),
    }


def _render_finance_digest_html(user, overdue_invoices, stale_referrals, upcoming_renewals, zeptomail) -> str:
    base_url = (zeptomail.frontend_base_url or "").rstrip("/") if hasattr(zeptomail, "frontend_base_url") else ""

    def fmt_inr(v):
        try:
            return f"₹{float(v or 0):,.0f}"
        except Exception:
            return "₹0"

    def section(label, items, accent, columns):
        if not items:
            return ""
        rows = ""
        for e in items[:10]:
            cells = "".join(
                f'<td style="padding:6px 8px;border-bottom:1px solid #f1f5f9;color:#475569;font-size:13px;">{c}</td>'
                for c in columns(e)
            )
            rows += f'<tr>{cells}</tr>'
        more = ""
        if len(items) > 10:
            more = f'<div style="padding:8px;text-align:center;color:#94a3b8;font-size:12px;border-top:1px solid #f1f5f9;">+ {len(items) - 10} more — see Finance dashboard</div>'
        return f'''
        <div style="margin:18px 0;">
          <div style="background:{accent};color:#fff;padding:8px 12px;border-radius:6px 6px 0 0;font-size:13px;font-weight:600;">
            {label} <span style="background:rgba(255,255,255,0.25);padding:2px 8px;border-radius:10px;margin-left:6px;">{len(items)}</span>
          </div>
          <table style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #e2e8f0;border-top:none;">
            {rows}
          </table>
          {more}
        </div>
        '''

    def overdue_rows(e):
        return [
            f'<a href="{base_url}/finance/events/{e["id"]}" style="color:#4f46e5;text-decoration:none;font-weight:500;">{e.get("name") or "Event"}</a>',
            e.get('customer_name') or '—',
            e.get('invoice_number') or 'no invoice #',
            fmt_inr(e.get('outstanding_balance') or e.get('expected_amount')),
            e.get('due_date') or '—',
        ]

    def stale_rows(e):
        return [
            f'<a href="{base_url}/finance/events/{e["id"]}" style="color:#4f46e5;text-decoration:none;font-weight:500;">{e.get("name") or "Event"}</a>',
            e.get('customer_name') or '—',
            e.get('referral_partner_name') or '—',
            fmt_inr(e.get('referral_amount')),
            (e.get('updated_at') or '')[:10],
        ]

    def renewal_rows(e):
        return [
            f'<a href="{base_url}/finance/events/{e["id"]}" style="color:#4f46e5;text-decoration:none;font-weight:500;">{e.get("name") or "Event"}</a>',
            e.get('customer_name') or '—',
            fmt_inr(e.get('expected_amount')),
            e.get('due_date') or '—',
        ]

    has_content = bool(overdue_invoices or stale_referrals or upcoming_renewals)
    empty_banner = '' if has_content else '''
      <div style="text-align:center;padding:24px;background:#ecfdf5;border:1px solid #6ee7b7;border-radius:8px;margin:18px 0;">
        <div style="font-size:32px;">✅</div>
        <div style="color:#065f46;font-weight:600;margin-top:6px;">All clear this week.</div>
        <div style="color:#047857;font-size:13px;margin-top:4px;">No overdue invoices, no stale referral payables, no renewals due in 30 days.</div>
      </div>
    '''

    return f'''<!doctype html>
    <html><body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
      <div style="max-width:680px;margin:0 auto;padding:20px;">
        <div style="background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);color:#fff;padding:20px 24px;border-radius:10px 10px 0 0;">
          <div style="font-size:13px;opacity:0.85;text-transform:uppercase;letter-spacing:1px;">Meshora · Finance Weekly Digest</div>
          <div style="font-size:22px;font-weight:700;margin-top:6px;">Hi {user.get('name', 'there').split()[0]} 👋</div>
          <div style="font-size:13px;margin-top:4px;opacity:0.9;">Your Monday morning briefing on receivables, payables & renewals.</div>
        </div>
        <div style="background:#fff;padding:18px 24px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 10px 10px;">
          {empty_banner}
          {section('🔴 Unpaid invoices · 30+ days old', overdue_invoices, '#dc2626', overdue_rows)}
          {section('🟡 Referral payables · stale 15+ days', stale_referrals, '#d97706', stale_rows)}
          {section('🔵 Renewals · due in next 30 days', upcoming_renewals, '#2563eb', renewal_rows)}
          <div style="margin-top:24px;padding-top:18px;border-top:1px solid #e2e8f0;text-align:center;">
            <a href="{base_url}/finance" style="background:#4f46e5;color:#fff;padding:10px 22px;border-radius:6px;text-decoration:none;font-weight:600;font-size:13px;display:inline-block;">Open Finance Dashboard</a>
          </div>
          <div style="margin-top:16px;text-align:center;color:#94a3b8;font-size:11px;">
            You receive this digest every Monday at 9 AM IST because you have Finance access in Meshora.
          </div>
        </div>
      </div>
    </body></html>
    '''


def _render_internal_task_digest_html(user, overdue, due_this_week, new_assigned, zeptomail) -> str:
    def section(label, items, accent):
        if not items:
            return ""
        rows = ""
        for t in items[:5]:
            due = (t.get("due_date") or "—")[:10]
            rows += (
                f'<tr><td style="padding:8px 0;border-bottom:1px solid #f3f4f6;">'
                f'<div style="font-weight:600;">{t.get("title","")}</div>'
                f'<div style="color:#6b7280;font-size:12px;">Due {due} &middot; {t.get("priority","medium")}</div>'
                f'</td></tr>'
            )
        extra = f"<p style=\"color:#6b7280;font-size:12px;\">+{len(items)-5} more</p>" if len(items) > 5 else ""
        return (
            f'<h3 style="margin:18px 0 6px;color:{accent};">{label} ({len(items)})</h3>'
            f'<table style="width:100%;border-collapse:collapse;">{rows}</table>{extra}'
        )
    body = (
        f'<p>Hi {user.get("name","there")},</p>'
        f'<p>Here is your internal-task snapshot for the week:</p>'
        f'{section("Overdue", overdue, "#b91c1c")}'
        f'{section("Due this week", due_this_week, "#b45309")}'
        f'{section("Newly assigned to you", new_assigned, "#1d4ed8")}'
        f'{zeptomail._btn("Open Internal Tasks", "https://app.vyapaar.net/internal-tasks")}'  # noqa: SLF001
    )
    return zeptomail._wrap("Your week in Meshora", "Weekly Internal Tasks Digest", body)  # noqa: SLF001


async def _reminder_loop(db, zeptomail) -> None:
    logger.info("Follow-up reminder loop started (interval=%ss)", SCAN_INTERVAL_SECONDS)
    while True:
        # Phase 35 — respect the admin's global on/off toggle
        if not await _scheduler_enabled(db):
            try:
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                raise
            continue
        try:
            res = await dispatch_due_reminders(db, zeptomail)
            if res.get('sent'):
                logger.info("Follow-up reminder pass: scanned=%s sent=%s", res['scanned'], res['sent'])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Reminder loop iteration crashed: %s", e)
        # Piggyback the task (action item) due-reminder scan — Phase 35.
        try:
            res = await dispatch_due_task_reminders(db, zeptomail)
            if res.get('sent'):
                logger.info("Task-due pass: scanned=%s sent=%s", res['scanned'], res['sent'])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Task-due loop iteration crashed: %s", e)
        # Piggyback the milestone-due scan on the same minute-tick.
        try:
            res = await dispatch_due_milestone_reminders(db, zeptomail)
            if res.get('sent'):
                logger.info("Milestone-due pass: scanned=%s sent=%s", res['scanned'], res['sent'])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Milestone-due loop iteration crashed: %s", e)
        # Phase 36 — renewal-window reminders for recurring contracts
        try:
            res = await dispatch_commercial_renewal_reminders(db, zeptomail)
            if res.get('sent'):
                logger.info("Renewal-reminder pass: scanned=%s sent=%s", res['scanned'], res['sent'])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Renewal-reminder loop iteration crashed: %s", e)
        # Phase 36 — invoice-overdue reminders
        try:
            res = await dispatch_invoice_overdue_reminders(db, zeptomail)
            if res.get('sent'):
                logger.info("Invoice-overdue pass: scanned=%s sent=%s", res['scanned'], res['sent'])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Invoice-overdue loop iteration crashed: %s", e)
        # Piggyback the monthly won-deals digest scan (fires once on 1st of month, 09:xx UTC).
        try:
            res = await dispatch_monthly_won_digest(db, zeptomail)
            if not res.get('skipped'):
                logger.info("Monthly won-deals digest fired: key=%s sent=%s recipients=%s",
                            res.get('key'), res.get('sent'), res.get('recipients'))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Monthly digest iteration crashed: %s", e)
        # Piggyback the Weekly War Room digest scan (Mondays 09:xx UTC).
        try:
            res = await dispatch_weekly_war_room_digest(db, zeptomail)
            if not res.get('skipped'):
                logger.info("Weekly War Room digest fired: key=%s sent=%s hot=%s blocked=%s risk=%s",
                            res.get('key'), res.get('sent'), res.get('hot_count'),
                            res.get('blocked_count'), res.get('at_risk_count'))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Weekly War Room digest iteration crashed: %s", e)
        # Phase 36 — internal task due-reminder + Monday IST digest
        try:
            res = await dispatch_due_internal_task_reminders(db, zeptomail)
            if res.get('sent'):
                logger.info("Internal-task reminder pass: scanned=%s sent=%s", res['scanned'], res['sent'])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Internal-task reminder loop crashed: %s", e)
        try:
            res = await dispatch_weekly_internal_task_digest(db, zeptomail)
            if not res.get('skipped'):
                logger.info("Internal-task weekly digest fired: key=%s sent=%s attempted=%s",
                            res.get('key'), res.get('sent'), res.get('attempted'))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Internal-task weekly digest crashed: %s", e)
        # Phase 39 — Finance weekly digest (Monday 09:xx IST)
        try:
            res = await dispatch_weekly_finance_digest(db, zeptomail)
            if not res.get('skipped'):
                logger.info("Finance weekly digest fired: key=%s sent=%s overdue=%s stale=%s renewals=%s",
                            res.get('key'), res.get('sent'), res.get('overdue_count'),
                            res.get('stale_referral_count'), res.get('renewals_count'))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Finance weekly digest crashed: %s", e)
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


def is_loop_running() -> bool:
    """Phase 35 — liveness probe for the Email Scheduler admin dashboard."""
    return bool(_RUNNING_TASK and not _RUNNING_TASK.done())
