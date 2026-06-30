"""Routers — Finance & Commission Management (Phase 37).

Built on top of the existing Commercials module. Adds:

  Lead → Commercial → Revenue Schedule → Revenue Events → (Invoice + Collection + Settlement)

A `Revenue Event` is the atomic billable unit and is generated when a Commercial is
approved. Each event walks its own lifecycle independently:

    created → ready_for_invoice → invoice_raised → invoice_sent → awaiting_payment
            → payment_received → referral_payable → referral_paid → closed

Sources of revenue events for a single Commercial:
  - One-Time projects   → 1 event per milestone (revenue_type='milestone')
                          OR 1 event for the full deal if no milestones exist.
  - Recurring contracts → 1 event per billing_schedule row (revenue_type matches frequency)
                          PLUS 1 event for the one_time_fee_amount if set (revenue_type='one_time').

Each event caches the Vyapaar % and Referral % from the parent lead at generation
time, so commission can be recomputed without re-joining.

This module imports shared infra from `server`. RBAC: super_admin OR is_finance
OR is_vyapaar_ops (per product requirement). Read-only fan-out for selling
partners on their own leads' events is intentionally NOT exposed yet — Finance
module is internal to the Vyapaar team.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid

from server import (
    db,
    get_current_user,
    UserRole,
    logger,
)

router = APIRouter()

# ============================ Enums & Models ============================

class RevenueType(str, Enum):
    ONE_TIME = "one_time"
    MILESTONE = "milestone"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    HALF_YEARLY = "half_yearly"
    ANNUAL = "annual"
    RENEWAL = "renewal"
    UPSELL = "upsell"
    CROSS_SELL = "cross_sell"
    OTHER = "other"


class LifecycleStatus(str, Enum):
    CREATED = "created"
    READY_FOR_INVOICE = "ready_for_invoice"
    INVOICE_RAISED = "invoice_raised"
    INVOICE_SENT = "invoice_sent"
    AWAITING_PAYMENT = "awaiting_payment"
    PAYMENT_RECEIVED = "payment_received"
    REFERRAL_PAYABLE = "referral_payable"
    REFERRAL_PAID = "referral_paid"
    CLOSED = "closed"


class InvoiceSource(str, Enum):
    MANUAL = "manual"
    ZOHO = "zoho"


# Forward state machine — what each state can move to.
_LIFECYCLE_TRANSITIONS: Dict[str, List[str]] = {
    LifecycleStatus.CREATED.value: [LifecycleStatus.READY_FOR_INVOICE.value],
    LifecycleStatus.READY_FOR_INVOICE.value: [LifecycleStatus.INVOICE_RAISED.value],
    LifecycleStatus.INVOICE_RAISED.value: [LifecycleStatus.INVOICE_SENT.value, LifecycleStatus.AWAITING_PAYMENT.value],
    LifecycleStatus.INVOICE_SENT.value: [LifecycleStatus.AWAITING_PAYMENT.value, LifecycleStatus.PAYMENT_RECEIVED.value],
    LifecycleStatus.AWAITING_PAYMENT.value: [LifecycleStatus.PAYMENT_RECEIVED.value],
    LifecycleStatus.PAYMENT_RECEIVED.value: [LifecycleStatus.REFERRAL_PAYABLE.value, LifecycleStatus.CLOSED.value],
    LifecycleStatus.REFERRAL_PAYABLE.value: [LifecycleStatus.REFERRAL_PAID.value],
    LifecycleStatus.REFERRAL_PAID.value: [LifecycleStatus.CLOSED.value],
    LifecycleStatus.CLOSED.value: [],
}


class RevenueEventUpdate(BaseModel):
    # Invoice tracking (Section C — currently manual)
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    invoice_due_date: Optional[str] = None
    invoice_pdf_url: Optional[str] = None
    invoice_raised_by_id: Optional[str] = None
    invoice_remarks: Optional[str] = None
    invoice_source: Optional[InvoiceSource] = None
    # Collection tracking (Section D)
    amount_received: Optional[float] = None
    payment_date: Optional[str] = None
    bank_reference: Optional[str] = None
    utr: Optional[str] = None
    outstanding_balance: Optional[float] = None
    collection_notes: Optional[str] = None
    # Referral settlement (Section E)
    referral_invoice_received: Optional[bool] = None
    referral_invoice_number: Optional[str] = None
    referral_payment_date: Optional[str] = None
    referral_utr: Optional[str] = None
    referral_tds: Optional[float] = None
    referral_gst: Optional[float] = None
    referral_remarks: Optional[str] = None
    # Misc
    expected_amount: Optional[float] = None
    due_date: Optional[str] = None
    name: Optional[str] = None


class TransitionPayload(BaseModel):
    note: Optional[str] = None


# ============================ Helpers ============================

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_finance_user(current_user: dict) -> bool:
    """Module RBAC: super admin, finance, or vyapaar ops can use Finance module."""
    if current_user.get('role') == UserRole.SUPER_ADMIN.value:
        return True
    return bool(current_user.get('is_finance') or current_user.get('is_vyapaar_ops'))


def _require_finance(current_user: dict):
    if not _is_finance_user(current_user):
        raise HTTPException(status_code=403, detail="Finance module is restricted to Vyapaar Finance / Operations team")


async def _log_finance(commercial_id: str, revenue_event_id: Optional[str], current_user: dict, action: str, message: str, meta: Optional[dict] = None):
    await db.finance_timeline.insert_one({
        "id": str(uuid.uuid4()),
        "commercial_id": commercial_id,
        "revenue_event_id": revenue_event_id,
        "user_id": current_user.get('id'),
        "user_name": current_user.get('name'),
        "action": action,
        "message": message,
        "meta": meta or {},
        "created_at": _now_iso(),
    })


def _resolve_commission_pcts(lead: dict) -> Dict[str, float]:
    """Pull cached commission percents from the lead (Phase 36.3 template flow).

    Fallbacks for legacy leads keep the calculation usable.
    """
    vyapaar = lead.get('commission_override')
    if vyapaar is None:
        vyapaar = lead.get('vyapaar_percentage')
    if vyapaar is None:
        vyapaar = 15.0
    referral = lead.get('referral_commission_percent')
    if referral is None:
        referral = lead.get('sales_associate_commission')
    if referral is None:
        referral = 0.0
    return {"vyapaar": float(vyapaar), "referral": float(referral)}


def _calc_amounts(expected_amount: float, vyapaar_pct: float, referral_pct: float) -> Dict[str, float]:
    """Referral % is taken on the Vyapaar share (consistent with LeadForm preview)."""
    expected = float(expected_amount or 0)
    vyapaar_amt = round(expected * vyapaar_pct / 100, 2)
    referral_amt = round(vyapaar_amt * referral_pct / 100, 2) if referral_pct else 0.0
    net = round(vyapaar_amt - referral_amt, 2)
    return {
        "vyapaar_amount": vyapaar_amt,
        "referral_amount": referral_amt,
        "net_revenue": net,
    }


def _serialise(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != '_id'}


def _freq_to_revenue_type(freq: Optional[str]) -> str:
    return {
        "monthly": RevenueType.MONTHLY.value,
        "quarterly": RevenueType.QUARTERLY.value,
        "half_yearly": RevenueType.HALF_YEARLY.value,
        "annual": RevenueType.ANNUAL.value,
    }.get((freq or "").lower(), RevenueType.OTHER.value)


def _derive_deal_type(commercial: dict) -> str:
    """Hybrid = recurring + one-time fee. Else 'one_time' / 'recurring' from base type."""
    base = commercial.get('type')
    if base == 'recurring' and float(commercial.get('one_time_fee_amount') or 0) > 0:
        return "hybrid"
    return base or "one_time"


# ============================ Revenue Schedule generation ============================

async def _build_revenue_schedule_for_commercial(commercial: dict, lead: dict, current_user: dict) -> List[dict]:
    """Pure generator — returns event dicts without inserting. Called from approve flow."""
    pcts = _resolve_commission_pcts(lead)
    v_pct = pcts['vyapaar']
    r_pct = pcts['referral']

    events: List[dict] = []
    commercial_id = commercial['id']
    now = _now_iso()
    customer_name = commercial.get('customer_name') or lead.get('customer_name')
    lead_title = commercial.get('lead_title') or lead.get('title')
    sp_id = lead.get('selling_partner_id')
    sp_name = lead.get('selling_partner_name')
    ref_id = lead.get('sales_associate_id') or lead.get('referrer_user_id')
    ref_name = lead.get('sales_associate_name') or lead.get('referrer_name')

    def _base_event(name: str, revenue_type: str, due_date: Optional[str], expected_amount: float, source_kind: str, source_id: Optional[str], order: int) -> dict:
        amounts = _calc_amounts(expected_amount, v_pct, r_pct)
        return {
            "id": str(uuid.uuid4()),
            "commercial_id": commercial_id,
            "lead_id": commercial.get('lead_id'),
            "lead_title": lead_title,
            "customer_id": commercial.get('customer_id'),
            "customer_name": customer_name,
            "selling_partner_id": sp_id,
            "selling_partner_name": sp_name,
            "referral_partner_id": ref_id,
            "referral_partner_name": ref_name,
            "primary_category_id": lead.get('primary_category_id'),
            "primary_category_name": lead.get('primary_category_name'),
            "name": name,
            "revenue_type": revenue_type,
            "due_date": due_date,
            "expected_amount": float(expected_amount or 0),
            "vyapaar_pct": v_pct,
            "vyapaar_amount": amounts['vyapaar_amount'],
            "referral_pct": r_pct,
            "referral_amount": amounts['referral_amount'],
            "net_revenue": amounts['net_revenue'],
            "lifecycle_status": LifecycleStatus.CREATED.value,
            "source_kind": source_kind,           # 'milestone' | 'billing_schedule' | 'one_time_fee' | 'standalone'
            "source_id": source_id,
            "order": order,
            "invoice_source": InvoiceSource.MANUAL.value,
            # Invoice / Collection / Settlement fields — populated by lifecycle transitions
            "invoice_number": None,
            "invoice_date": None,
            "invoice_due_date": due_date,
            "invoice_pdf_url": None,
            "invoice_raised_by_id": None,
            "invoice_raised_by_name": None,
            "invoice_remarks": None,
            "amount_received": 0.0,
            "payment_date": None,
            "bank_reference": None,
            "utr": None,
            "outstanding_balance": float(expected_amount or 0),
            "collection_notes": None,
            "referral_invoice_received": False,
            "referral_invoice_number": None,
            "referral_payment_date": None,
            "referral_utr": None,
            "referral_tds": None,
            "referral_gst": None,
            "referral_remarks": None,
            "created_at": now,
            "updated_at": now,
            "created_by_id": current_user.get('id'),
            "created_by_name": current_user.get('name'),
        }

    base_type = commercial.get('type')

    if base_type == 'one_time':
        milestones = commercial.get('milestones', []) or []
        if milestones:
            for idx, m in enumerate(milestones):
                events.append(_base_event(
                    name=m.get('name') or f"Milestone {idx + 1}",
                    revenue_type=RevenueType.MILESTONE.value,
                    due_date=m.get('invoice_due_date') or m.get('delivery_date'),
                    expected_amount=float(m.get('amount') or 0),
                    source_kind='milestone',
                    source_id=m.get('id'),
                    order=idx,
                ))
        else:
            events.append(_base_event(
                name=f"{lead_title or 'Project'} — Full payment",
                revenue_type=RevenueType.ONE_TIME.value,
                due_date=commercial.get('end_date') or commercial.get('start_date'),
                expected_amount=float(commercial.get('total_value') or 0),
                source_kind='standalone',
                source_id=None,
                order=0,
            ))

    elif base_type == 'recurring':
        order = 0
        # Hybrid implementation / setup fee — first event
        if float(commercial.get('one_time_fee_amount') or 0) > 0:
            events.append(_base_event(
                name=commercial.get('one_time_fee_label') or "Implementation / Setup fee",
                revenue_type=RevenueType.ONE_TIME.value,
                due_date=commercial.get('one_time_fee_due_date') or commercial.get('contract_start_date'),
                expected_amount=float(commercial.get('one_time_fee_amount') or 0),
                source_kind='one_time_fee',
                source_id=None,
                order=order,
            ))
            order += 1
        # Recurring billing schedule rows
        rev_type = _freq_to_revenue_type(commercial.get('billing_frequency'))
        for row in (commercial.get('billing_schedule') or []):
            events.append(_base_event(
                name=f"{(commercial.get('billing_frequency') or 'recurring').replace('_', ' ').title()} — {row.get('period_start')} → {row.get('period_end')}",
                revenue_type=rev_type,
                due_date=row.get('due_date') or row.get('period_start'),
                expected_amount=float(row.get('amount') or 0),
                source_kind='billing_schedule',
                source_id=row.get('id'),
                order=order,
            ))
            order += 1

    return events


# ============================ Approval & Schedule generation ============================

@router.post("/commercials/{commercial_id}/approve")
async def approve_commercial(commercial_id: str, current_user: dict = Depends(get_current_user)):
    """Approve a Commercial → auto-generate the Revenue Schedule (Revenue Events).

    Idempotent: re-running on an already-approved Commercial returns the existing
    events without regenerating.
    """
    _require_finance(current_user)
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")

    if commercial.get('approval_status') == 'approved':
        existing = await db.revenue_events.find({"commercial_id": commercial_id}, {"_id": 0}).sort("order", 1).to_list(2000)
        return {"approved_at": commercial.get('approved_at'), "events": existing, "generated": False}

    lead = await db.leads.find_one({"id": commercial.get('lead_id')}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=400, detail="Linked lead not found — cannot resolve commissions")

    events = await _build_revenue_schedule_for_commercial(commercial, lead, current_user)
    if events:
        await db.revenue_events.insert_many([dict(e) for e in events])

    now = _now_iso()
    await db.commercials.update_one(
        {"id": commercial_id},
        {"$set": {
            "approval_status": "approved",
            "approved_at": now,
            "approved_by_id": current_user.get('id'),
            "approved_by_name": current_user.get('name'),
            "deal_type": _derive_deal_type(commercial),
            "invoice_source": commercial.get('invoice_source') or InvoiceSource.MANUAL.value,
            "updated_at": now,
        }},
    )
    await _log_finance(commercial_id, None, current_user, "commercial_approved",
                      f"Commercial approved — {len(events)} revenue event(s) generated",
                      {"event_count": len(events), "deal_type": _derive_deal_type(commercial)})
    sanitised = [_serialise(e) for e in events]
    return {"approved_at": now, "events": sanitised, "generated": True}


@router.post("/commercials/{commercial_id}/regenerate-revenue-schedule")
async def regenerate_revenue_schedule(commercial_id: str, current_user: dict = Depends(get_current_user)):
    """Wipe and rebuild the Revenue Schedule. Only available BEFORE any event has
    progressed beyond `created` (so we don't blow away invoice / payment history).
    """
    _require_finance(current_user)
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    lead = await db.leads.find_one({"id": commercial.get('lead_id')}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=400, detail="Linked lead not found")
    in_flight = await db.revenue_events.count_documents({
        "commercial_id": commercial_id,
        "lifecycle_status": {"$nin": [LifecycleStatus.CREATED.value]},
    })
    if in_flight > 0:
        raise HTTPException(status_code=400, detail=f"{in_flight} revenue event(s) already past 'created' — cannot regenerate. Edit events individually.")
    await db.revenue_events.delete_many({"commercial_id": commercial_id})
    events = await _build_revenue_schedule_for_commercial(commercial, lead, current_user)
    if events:
        await db.revenue_events.insert_many([dict(e) for e in events])
    await _log_finance(commercial_id, None, current_user, "schedule_regenerated",
                      f"Revenue schedule regenerated — {len(events)} event(s)")
    return {"events": [_serialise(e) for e in events]}


# ============================ Read endpoints ============================

@router.get("/finance/revenue-events")
async def list_revenue_events(
    commercial_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    selling_partner_id: Optional[str] = None,
    referral_partner_id: Optional[str] = None,
    primary_category_id: Optional[str] = None,
    revenue_type: Optional[str] = None,
    lifecycle_status: Optional[str] = None,
    due_from: Optional[str] = None,
    due_to: Optional[str] = None,
    limit: int = Query(500, le=2000),
    current_user: dict = Depends(get_current_user),
):
    _require_finance(current_user)
    query: Dict[str, Any] = {}
    for key, val in (
        ("commercial_id", commercial_id),
        ("lead_id", lead_id),
        ("customer_id", customer_id),
        ("selling_partner_id", selling_partner_id),
        ("referral_partner_id", referral_partner_id),
        ("primary_category_id", primary_category_id),
        ("revenue_type", revenue_type),
        ("lifecycle_status", lifecycle_status),
    ):
        if val:
            query[key] = val
    if due_from or due_to:
        rng: Dict[str, Any] = {}
        if due_from:
            rng["$gte"] = due_from
        if due_to:
            rng["$lte"] = due_to
        query["due_date"] = rng
    items = await db.revenue_events.find(query, {"_id": 0}).sort("due_date", 1).to_list(limit)
    return items


@router.get("/finance/revenue-events/{event_id}")
async def get_revenue_event(event_id: str, current_user: dict = Depends(get_current_user)):
    _require_finance(current_user)
    ev = await db.revenue_events.find_one({"id": event_id}, {"_id": 0})
    if not ev:
        raise HTTPException(status_code=404, detail="Revenue event not found")
    return ev


@router.get("/finance/revenue-events/{event_id}/timeline")
async def revenue_event_timeline(event_id: str, current_user: dict = Depends(get_current_user)):
    _require_finance(current_user)
    ev = await db.revenue_events.find_one({"id": event_id}, {"_id": 0})
    if not ev:
        raise HTTPException(status_code=404, detail="Revenue event not found")
    rows = await db.finance_timeline.find(
        {"$or": [{"revenue_event_id": event_id}, {"commercial_id": ev['commercial_id'], "revenue_event_id": None}]},
        {"_id": 0},
    ).sort("created_at", -1).to_list(500)
    return rows


@router.get("/commercials/{commercial_id}/revenue-events")
async def revenue_events_for_commercial(commercial_id: str, current_user: dict = Depends(get_current_user)):
    _require_finance(current_user)
    items = await db.revenue_events.find({"commercial_id": commercial_id}, {"_id": 0}).sort("order", 1).to_list(2000)
    return items


# ============================ Mutate / Lifecycle ============================

@router.patch("/finance/revenue-events/{event_id}")
async def update_revenue_event(event_id: str, payload: RevenueEventUpdate, current_user: dict = Depends(get_current_user)):
    _require_finance(current_user)
    ev = await db.revenue_events.find_one({"id": event_id}, {"_id": 0})
    if not ev:
        raise HTTPException(status_code=404, detail="Revenue event not found")
    updates = {k: (v.value if isinstance(v, Enum) else v) for k, v in payload.model_dump(exclude_unset=True).items()}
    # If expected_amount changes, recompute commission amounts
    if 'expected_amount' in updates:
        amts = _calc_amounts(updates['expected_amount'], ev['vyapaar_pct'], ev['referral_pct'])
        updates.update(amts)
        updates['outstanding_balance'] = float(updates['expected_amount'] or 0) - float(ev.get('amount_received') or 0)
    # If amount_received changes manually, recompute outstanding
    if 'amount_received' in updates:
        new_total = float(updates['amount_received'] or 0)
        expected = float(updates.get('expected_amount', ev.get('expected_amount')) or 0)
        updates['outstanding_balance'] = round(expected - new_total, 2)
    updates['updated_at'] = _now_iso()
    await db.revenue_events.update_one({"id": event_id}, {"$set": updates})
    await _log_finance(ev['commercial_id'], event_id, current_user, "event_updated",
                      f"Revenue event updated — fields: {', '.join(updates.keys())}", {"fields": list(updates.keys())})
    updated = await db.revenue_events.find_one({"id": event_id}, {"_id": 0})
    return updated


def _can_transition(from_state: str, to_state: str) -> bool:
    return to_state in _LIFECYCLE_TRANSITIONS.get(from_state, [])


@router.post("/finance/revenue-events/{event_id}/transitions/{action}")
async def transition_revenue_event(event_id: str, action: str, payload: TransitionPayload = TransitionPayload(), current_user: dict = Depends(get_current_user)):
    """Move a revenue event to its next state.

    Supported actions (each maps to a state):
      mark_ready_for_invoice, mark_invoice_raised, mark_invoice_sent,
      mark_awaiting_payment, mark_payment_received, mark_referral_payable,
      mark_referral_paid, close, reopen
    """
    _require_finance(current_user)
    ev = await db.revenue_events.find_one({"id": event_id}, {"_id": 0})
    if not ev:
        raise HTTPException(status_code=404, detail="Revenue event not found")
    target_map = {
        "mark_ready_for_invoice": LifecycleStatus.READY_FOR_INVOICE.value,
        "mark_invoice_raised": LifecycleStatus.INVOICE_RAISED.value,
        "mark_invoice_sent": LifecycleStatus.INVOICE_SENT.value,
        "mark_awaiting_payment": LifecycleStatus.AWAITING_PAYMENT.value,
        "mark_payment_received": LifecycleStatus.PAYMENT_RECEIVED.value,
        "mark_referral_payable": LifecycleStatus.REFERRAL_PAYABLE.value,
        "mark_referral_paid": LifecycleStatus.REFERRAL_PAID.value,
        "close": LifecycleStatus.CLOSED.value,
    }
    if action == "reopen":
        # Allow Finance to step back one state (audit-logged). Only from CLOSED → REFERRAL_PAID.
        if ev['lifecycle_status'] != LifecycleStatus.CLOSED.value:
            raise HTTPException(status_code=400, detail="Only closed events can be reopened")
        to_state = LifecycleStatus.REFERRAL_PAID.value if ev.get('referral_partner_id') else LifecycleStatus.PAYMENT_RECEIVED.value
    else:
        to_state = target_map.get(action)
        if not to_state:
            raise HTTPException(status_code=400, detail=f"Unknown transition action: {action}")
        if not _can_transition(ev['lifecycle_status'], to_state):
            raise HTTPException(status_code=400, detail=f"Cannot transition from {ev['lifecycle_status']} → {to_state}")
        # If moving to REFERRAL_PAYABLE but the event has no referral commission, skip straight to closure-ready
        if to_state == LifecycleStatus.REFERRAL_PAYABLE.value and not float(ev.get('referral_pct') or 0):
            raise HTTPException(status_code=400, detail="No referral commission on this event — use close instead")

    now = _now_iso()
    updates: Dict[str, Any] = {"lifecycle_status": to_state, "updated_at": now}
    # Auto-stamp meaningful side effects on certain transitions
    if to_state == LifecycleStatus.INVOICE_RAISED.value and not ev.get('invoice_date'):
        updates['invoice_date'] = now[:10]
        updates['invoice_raised_by_id'] = current_user.get('id')
        updates['invoice_raised_by_name'] = current_user.get('name')
    if to_state == LifecycleStatus.PAYMENT_RECEIVED.value:
        # Default the received amount to the full expected if not already set
        if not ev.get('amount_received'):
            updates['amount_received'] = float(ev.get('expected_amount') or 0)
            updates['outstanding_balance'] = 0.0
        if not ev.get('payment_date'):
            updates['payment_date'] = now[:10]
    if to_state == LifecycleStatus.REFERRAL_PAID.value and not ev.get('referral_payment_date'):
        updates['referral_payment_date'] = now[:10]

    await db.revenue_events.update_one({"id": event_id}, {"$set": updates})
    await _log_finance(
        ev['commercial_id'], event_id, current_user, f"transition.{action}",
        payload.note or f"Status: {ev['lifecycle_status']} → {to_state}",
        {"from": ev['lifecycle_status'], "to": to_state, "note": payload.note},
    )
    return await db.revenue_events.find_one({"id": event_id}, {"_id": 0})


# ============================ Dashboard KPIs ============================

@router.get("/finance/dashboard")
async def finance_dashboard(current_user: dict = Depends(get_current_user)):
    _require_finance(current_user)
    today = datetime.now(timezone.utc).date()
    today_iso = today.isoformat()
    in_30 = (today + timedelta(days=30)).isoformat()
    quarter_end = (today + timedelta(days=90)).isoformat()
    year_end = (today + timedelta(days=365)).isoformat()

    all_events = await db.revenue_events.find({}, {"_id": 0}).to_list(20000)

    def _sum(field, predicate):
        return round(sum(float(e.get(field) or 0) for e in all_events if predicate(e)), 2)

    # Lifecycle buckets
    open_states = {LifecycleStatus.CREATED.value, LifecycleStatus.READY_FOR_INVOICE.value,
                   LifecycleStatus.INVOICE_RAISED.value, LifecycleStatus.INVOICE_SENT.value,
                   LifecycleStatus.AWAITING_PAYMENT.value}
    receivable_states = {LifecycleStatus.INVOICE_RAISED.value, LifecycleStatus.INVOICE_SENT.value,
                         LifecycleStatus.AWAITING_PAYMENT.value}
    referral_pending_states = {LifecycleStatus.PAYMENT_RECEIVED.value, LifecycleStatus.REFERRAL_PAYABLE.value}

    def _is_overdue(ev):
        dd = ev.get('due_date')
        return bool(dd and dd < today_iso and ev.get('lifecycle_status') in receivable_states)

    receivables = {
        "total_commission_receivable": _sum('vyapaar_amount', lambda e: e['lifecycle_status'] in open_states),
        "invoices_pending_count": sum(1 for e in all_events if e['lifecycle_status'] == LifecycleStatus.READY_FOR_INVOICE.value),
        "collections_pending_amount": _sum('expected_amount', lambda e: e['lifecycle_status'] in receivable_states),
        "overdue_collections_amount": _sum('expected_amount', _is_overdue),
        "overdue_collections_count": sum(1 for e in all_events if _is_overdue(e)),
    }

    payables = {
        "referral_payable_amount": _sum('referral_amount', lambda e: e['lifecycle_status'] in referral_pending_states),
        "referral_pending_count": sum(1 for e in all_events if e['lifecycle_status'] in referral_pending_states),
        "referral_overdue_count": sum(
            1 for e in all_events
            if e['lifecycle_status'] == LifecycleStatus.REFERRAL_PAYABLE.value
            and e.get('updated_at') and e['updated_at'][:10] < (today - timedelta(days=15)).isoformat()
        ),
    }

    realised_states = {LifecycleStatus.PAYMENT_RECEIVED.value, LifecycleStatus.REFERRAL_PAYABLE.value,
                       LifecycleStatus.REFERRAL_PAID.value, LifecycleStatus.CLOSED.value}
    recurring_types = {RevenueType.MONTHLY.value, RevenueType.QUARTERLY.value, RevenueType.HALF_YEARLY.value, RevenueType.ANNUAL.value, RevenueType.RENEWAL.value}

    revenue = {
        "gross_revenue_realised": _sum('expected_amount', lambda e: e['lifecycle_status'] in realised_states),
        "vyapaar_net_revenue_realised": _sum('net_revenue', lambda e: e['lifecycle_status'] in realised_states),
        "recurring_revenue_open": _sum('expected_amount', lambda e: e['revenue_type'] in recurring_types and e['lifecycle_status'] in open_states),
        "expected_revenue_this_month": _sum('expected_amount', lambda e: e.get('due_date') and today_iso <= e['due_date'] <= in_30),
        "expected_revenue_this_quarter": _sum('expected_amount', lambda e: e.get('due_date') and today_iso <= e['due_date'] <= quarter_end),
        "expected_revenue_this_year": _sum('expected_amount', lambda e: e.get('due_date') and today_iso <= e['due_date'] <= year_end),
    }

    operations = {
        "events_created": sum(1 for e in all_events if e['lifecycle_status'] == LifecycleStatus.CREATED.value),
        "events_closed": sum(1 for e in all_events if e['lifecycle_status'] == LifecycleStatus.CLOSED.value),
        "invoices_pending": sum(1 for e in all_events if e['lifecycle_status'] == LifecycleStatus.READY_FOR_INVOICE.value),
        "collections_pending": sum(1 for e in all_events if e['lifecycle_status'] in receivable_states),
        "settlements_pending": sum(1 for e in all_events if e['lifecycle_status'] in referral_pending_states),
        "total_events": len(all_events),
    }

    return {
        "receivables": receivables,
        "payables": payables,
        "revenue": revenue,
        "operations": operations,
        "as_of": today_iso,
    }
