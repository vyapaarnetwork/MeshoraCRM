"""Routers — Revenue Contracting & Delivery Management (extracted from server.py).

Phase 1: Closed-Won wizard + One-Time milestones + Recurring billing + invoices + payments
        + documents + activity log + dashboard
Phase 2: Renewal pipeline auto-creation + analytics + finance/delivery RBAC
Phase 2.5: In-app reminder scan (notifications dedup)
Phase 3: AI milestone suggestions (Gemini 3 Pro) + renewal probability + payment-delay risk
         + Kanban + PDF invoice generation

This module imports shared infra (db, get_current_user, UserRole, NotificationType,
create_notification, UPLOAD_DIR, logger) from `server`. The dependency direction is:
    server.py → ROUTERS = [routers.commercials]  (server imports the router AT THE BOTTOM
    after all globals are defined, so commercials.py can safely `from server import …`).
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from io import BytesIO
import os
import re
import uuid
import json as _json
import aiofiles

# Late-binding imports from server (resolved when server.py finishes executing the
# top-level code that defines these names, then triggers `from routers.commercials …`).
from server import (
    db,
    get_current_user,
    UserRole,
    NotificationType,
    create_notification,
    UPLOAD_DIR,
    logger,
)

router = APIRouter()

# ==================== REVENUE CONTRACTING & DELIVERY MANAGEMENT ====================
# Phase 1 MVP: Closed-Won wizard + One-Time projects (milestones) + Recurring contracts
# (billing schedule) + invoices + payments + documents + activity timeline + dashboard.

class CommercialType(str, Enum):
    ONE_TIME = "one_time"
    RECURRING = "recurring"

class BillingFrequency(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    HALF_YEARLY = "half_yearly"
    ANNUAL = "annual"

class MilestoneStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"
    INVOICE_RAISED = "invoice_raised"
    PAYMENT_RECEIVED = "payment_received"
    OVERDUE = "overdue"

class ContractStatus(str, Enum):
    ACTIVE = "active"
    RENEWAL_DUE = "renewal_due"
    RENEWED = "renewed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"

class RenewalType(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"
    APPROVAL_REQUIRED = "approval_required"

class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    RAISED = "raised"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

# ---- Pydantic schemas ----
class MilestoneInput(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    delivery_date: Optional[str] = None
    amount: float = 0.0
    percentage: float = 0.0
    invoice_due_date: Optional[str] = None
    status: MilestoneStatus = MilestoneStatus.PENDING
    order: int = 0

class CommercialCreate(BaseModel):
    lead_id: str
    type: CommercialType
    currency: str = "INR"
    notes: Optional[str] = None
    # One-time fields
    total_value: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    project_owner_id: Optional[str] = None
    delivery_spoc_id: Optional[str] = None
    billing_contact_id: Optional[str] = None
    # Recurring fields
    contract_value: Optional[float] = None
    billing_frequency: Optional[BillingFrequency] = None
    contract_start_date: Optional[str] = None
    contract_end_date: Optional[str] = None
    auto_renewal: Optional[bool] = False
    renewal_type: Optional[RenewalType] = RenewalType.MANUAL
    renewal_notice_days: Optional[int] = 30
    account_manager_id: Optional[str] = None
    contract_owner_id: Optional[str] = None
    # Phase 36 — One-Time Setup Fee on Recurring contracts (SaaS onboarding /
    # implementation / customisation fee). Tracked separately from the recurring
    # billing schedule. Uses the same commission % as the base deal.
    one_time_fee_amount: Optional[float] = None
    one_time_fee_label: Optional[str] = None      # e.g. "Onboarding fee", "Setup"
    one_time_fee_due_date: Optional[str] = None
    # Phase 36.2 — Tax rate (flat %) attached to this commercial. Master in tax_rates.
    tax_rate_id: Optional[str] = None

class CommercialUpdate(BaseModel):
    type: Optional[CommercialType] = None  # Phase 35 — allow switching One-Time ↔ Recurring post-creation
    notes: Optional[str] = None
    currency: Optional[str] = None
    total_value: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    project_owner_id: Optional[str] = None
    delivery_spoc_id: Optional[str] = None
    billing_contact_id: Optional[str] = None
    contract_value: Optional[float] = None
    billing_frequency: Optional[BillingFrequency] = None
    contract_start_date: Optional[str] = None
    contract_end_date: Optional[str] = None
    auto_renewal: Optional[bool] = None
    renewal_type: Optional[RenewalType] = None
    renewal_notice_days: Optional[int] = None
    account_manager_id: Optional[str] = None
    contract_owner_id: Optional[str] = None
    contract_status: Optional[ContractStatus] = None
    # Phase 36 — editable One-Time Fee on Recurring contracts
    one_time_fee_amount: Optional[float] = None
    one_time_fee_label: Optional[str] = None
    one_time_fee_due_date: Optional[str] = None
    one_time_fee_status: Optional[str] = None  # 'pending' | 'invoiced' | 'paid' | 'waived'
    # Phase 36.2 — editable tax rate
    tax_rate_id: Optional[str] = None

class MilestonesBulkInput(BaseModel):
    milestones: List[MilestoneInput]

class InvoiceCreate(BaseModel):
    milestone_id: Optional[str] = None
    billing_schedule_id: Optional[str] = None
    invoice_number: str
    amount: float
    due_date: Optional[str] = None
    raised_at: Optional[str] = None
    notes: Optional[str] = None
    is_one_time_fee: Optional[bool] = False  # Phase 36 — flags an invoice as the recurring contract's One-Time Setup Fee

class InvoiceUpdate(BaseModel):
    invoice_number: Optional[str] = None
    amount: Optional[float] = None
    due_date: Optional[str] = None
    raised_at: Optional[str] = None
    status: Optional[InvoiceStatus] = None
    notes: Optional[str] = None

class PaymentCreate(BaseModel):
    invoice_id: Optional[str] = None
    milestone_id: Optional[str] = None
    billing_schedule_id: Optional[str] = None
    amount: float
    paid_at: Optional[str] = None
    method: Optional[str] = None
    reference: Optional[str] = None
    notes: Optional[str] = None

class BillingScheduleUpdate(BaseModel):
    status: Optional[str] = None
    amount: Optional[float] = None
    due_date: Optional[str] = None

# ---- Helpers ----
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _resolve_default_tax_rate_id() -> Optional[str]:
    """Phase 36.2 — pick the master row flagged is_default, fall back to None."""
    try:
        row = await db.tax_rates.find_one({"is_default": True, "is_active": {"$ne": False}}, {"_id": 0, "id": 1})
        return (row or {}).get("id")
    except Exception:
        return None

async def _log_commercial_activity(commercial_id: str, current_user: dict, activity_type: str, message: str, meta: dict = None):
    await db.commercial_activity.insert_one({
        "id": str(uuid.uuid4()),
        "commercial_id": commercial_id,
        "user_id": current_user['id'],
        "user_name": current_user.get('name'),
        "type": activity_type,
        "message": message,
        "meta": meta or {},
        "created_at": _now_iso()
    })

async def _ensure_commercial_access(commercial: dict, current_user: dict, write: bool = False):
    """Admin = full. Finance & Delivery users = write. Selling Partner = read-only on their own leads' commercials. Others = denied."""
    role = current_user.get('role')
    if role == UserRole.SUPER_ADMIN.value:
        return
    # Finance & Delivery elevated roles (Phase 2)
    if current_user.get('is_finance') or current_user.get('is_delivery') or current_user.get('is_vyapaar_ops'):
        return
    if role == UserRole.SELLING_PARTNER.value:
        if write:
            raise HTTPException(status_code=403, detail="Selling partners have read-only access to commercials")
        lead = await db.leads.find_one({"id": commercial['lead_id']}, {"_id": 0})
        if not lead:
            raise HTTPException(status_code=404, detail="Linked lead not found")
        partner_ids = [p.get('partner_id') for p in lead.get('assigned_partners', [])]
        if (lead.get('selling_partner_id') == current_user['id']
                or current_user['id'] in partner_ids
                or current_user.get('company_id') and current_user['company_id'] in [p.get('partner_id') for p in lead.get('assigned_partners', [])]):
            return
        raise HTTPException(status_code=403, detail="You don't have access to this commercial")
    raise HTTPException(status_code=403, detail="Insufficient permissions")

def _add_months(dt: datetime, months: int) -> datetime:
    """Add `months` to dt, clamping the day to the last day of the resulting month."""
    new_month = dt.month + months
    year = dt.year + (new_month - 1) // 12
    month = (new_month - 1) % 12 + 1
    # last day of new month
    if month == 12:
        last_day = 31
    else:
        last_day = (datetime(year, month + 1, 1) - timedelta(days=1)).day
    return dt.replace(year=year, month=month, day=min(dt.day, last_day))

FREQ_MONTHS = {
    "monthly": 1,
    "quarterly": 3,
    "half_yearly": 6,
    "annual": 12,
}

def _generate_billing_schedule(commercial: dict) -> List[dict]:
    freq = commercial.get('billing_frequency')
    start = commercial.get('contract_start_date')
    end = commercial.get('contract_end_date')
    value = commercial.get('contract_value') or 0
    if not freq or not start or not end:
        return []
    months_step = FREQ_MONTHS.get(freq)
    if not months_step:
        return []
    try:
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00')) if 'T' in start else datetime.fromisoformat(start + "T00:00:00+00:00")
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00')) if 'T' in end else datetime.fromisoformat(end + "T23:59:59+00:00")
    except Exception:
        return []
    schedule: List[dict] = []
    cursor = start_dt
    period_idx = 0
    while cursor <= end_dt and period_idx < 240:  # hard cap to avoid infinite loops
        next_cursor = _add_months(cursor, months_step)
        period_end = min(next_cursor - timedelta(seconds=1), end_dt)
        schedule.append({
            "id": str(uuid.uuid4()),
            "period_start": cursor.date().isoformat(),
            "period_end": period_end.date().isoformat(),
            "due_date": cursor.date().isoformat(),
            "amount": value,
            "status": "scheduled",  # scheduled | invoiced | paid | skipped
            "invoice_id": None,
            "order": period_idx,
        })
        cursor = next_cursor
        period_idx += 1
    return schedule

def _serialise_commercial(c: dict) -> dict:
    return {k: v for k, v in c.items() if k != '_id'}

# ---- Endpoints ----
@router.post("/commercials")
async def create_commercial(payload: CommercialCreate, current_user: dict = Depends(get_current_user)):
    if not (current_user.get('role') == UserRole.SUPER_ADMIN.value or current_user.get('is_finance') or current_user.get('is_delivery') or current_user.get('is_vyapaar_ops')):
        raise HTTPException(status_code=403, detail="Only admin / finance / delivery users can create commercials")
    lead = await db.leads.find_one({"id": payload.lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    existing = await db.commercials.find_one({"lead_id": payload.lead_id}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Commercials already exists for this lead", headers={"X-Commercial-Id": existing['id']})
    now = _now_iso()
    commercial_id = str(uuid.uuid4())
    doc = {
        "id": commercial_id,
        "lead_id": payload.lead_id,
        "lead_title": lead.get('title'),
        "customer_name": lead.get('customer_name'),
        "customer_id": lead.get('customer_id'),
        "type": payload.type.value,
        "currency": payload.currency or "INR",
        "notes": payload.notes,
        "created_by": current_user['id'],
        "created_by_name": current_user.get('name'),
        "created_at": now,
        "updated_at": now,
        # one-time
        "total_value": payload.total_value,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "project_owner_id": payload.project_owner_id,
        "delivery_spoc_id": payload.delivery_spoc_id,
        "billing_contact_id": payload.billing_contact_id,
        # recurring
        "contract_value": payload.contract_value,
        "billing_frequency": payload.billing_frequency.value if payload.billing_frequency else None,
        "contract_start_date": payload.contract_start_date,
        "contract_end_date": payload.contract_end_date,
        "auto_renewal": bool(payload.auto_renewal),
        "renewal_type": payload.renewal_type.value if payload.renewal_type else "manual",
        "renewal_notice_days": payload.renewal_notice_days or 30,
        "account_manager_id": payload.account_manager_id,
        "contract_owner_id": payload.contract_owner_id,
        "contract_status": ContractStatus.ACTIVE.value if payload.type == CommercialType.RECURRING else None,
        # Phase 36 — One-Time Setup Fee (SaaS onboarding etc.) on Recurring contracts
        "one_time_fee_amount": payload.one_time_fee_amount,
        "one_time_fee_label": (payload.one_time_fee_label or "").strip() or None,
        "one_time_fee_due_date": payload.one_time_fee_due_date,
        "one_time_fee_status": "pending" if payload.one_time_fee_amount else None,
        "one_time_fee_invoice_id": None,
        # Phase 36.2 — tax_rate_id (defaults to the master "is_default" row if not provided)
        "tax_rate_id": payload.tax_rate_id or (await _resolve_default_tax_rate_id()),
        "milestones": [],
        "billing_schedule": [],
    }
    if payload.type == CommercialType.RECURRING:
        doc['billing_schedule'] = _generate_billing_schedule(doc)
    await db.commercials.insert_one(doc)
    await _log_commercial_activity(commercial_id, current_user, "created", f"{payload.type.value.replace('_', ' ').title()} commercial created")
    return _serialise_commercial(doc)

@router.get("/commercials")
async def list_commercials(
    type: Optional[str] = None,
    contract_status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query: Dict[str, Any] = {}
    if type:
        query['type'] = type
    if contract_status:
        query['contract_status'] = contract_status
    # Selling partners only see their own
    if current_user.get('role') == UserRole.SELLING_PARTNER.value:
        leads = await db.leads.find({
            "$or": [
                {"selling_partner_id": current_user['id']},
                {"assigned_partners.partner_id": current_user['id']},
                {"assigned_partners.partner_id": current_user.get('company_id')},
            ]
        }, {"_id": 0, "id": 1}).to_list(2000)
        lead_ids = [ld['id'] for ld in leads]
        query['lead_id'] = {"$in": lead_ids}
    elif not (current_user.get('role') == UserRole.SUPER_ADMIN.value or current_user.get('is_finance') or current_user.get('is_delivery') or current_user.get('is_vyapaar_ops')):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    items = await db.commercials.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return items

@router.get("/commercials/dashboard")
async def commercials_dashboard(current_user: dict = Depends(get_current_user)):
    if not (current_user.get('role') == UserRole.SUPER_ADMIN.value or current_user.get('is_finance') or current_user.get('is_delivery') or current_user.get('is_vyapaar_ops')):
        raise HTTPException(status_code=403, detail="Admin / finance / delivery only")
    today = datetime.now(timezone.utc).date()
    all_comm = await db.commercials.find({}, {"_id": 0}).to_list(2000)
    one_time = [c for c in all_comm if c.get('type') == 'one_time']
    recurring = [c for c in all_comm if c.get('type') == 'recurring']
    # One-time metrics
    total_project_value = sum((c.get('total_value') or 0) for c in one_time)
    revenue_realized = 0.0
    pending_invoices = 0
    overdue_invoices = 0
    upcoming_milestones = 0
    invoices = await db.commercial_invoices.find({}, {"_id": 0}).to_list(5000)
    payments = await db.commercial_payments.find({}, {"_id": 0}).to_list(5000)
    for p in payments:
        revenue_realized += float(p.get('amount') or 0)
    for inv in invoices:
        if inv.get('status') in ('raised', 'partial'):
            pending_invoices += 1
            try:
                if inv.get('due_date') and datetime.fromisoformat(inv['due_date']).date() < today:
                    overdue_invoices += 1
            except Exception:
                pass
    in_30 = today + timedelta(days=30)
    for c in one_time:
        for m in c.get('milestones', []):
            try:
                if m.get('delivery_date') and today <= datetime.fromisoformat(m['delivery_date']).date() <= in_30 and m.get('status') in ('pending', 'in_progress'):
                    upcoming_milestones += 1
            except Exception:
                pass
    # Recurring metrics — MRR (monthly equivalent), ARR
    mrr = 0.0
    for c in recurring:
        if c.get('contract_status') in (None, 'active', 'renewal_due'):
            v = float(c.get('contract_value') or 0)
            months = FREQ_MONTHS.get(c.get('billing_frequency') or 'monthly', 1)
            mrr += v / months
    arr = mrr * 12
    # Upcoming renewals (contract end within 60 days)
    upcoming_renewals = []
    in_60 = today + timedelta(days=60)
    for c in recurring:
        end = c.get('contract_end_date')
        if not end:
            continue
        try:
            end_d = datetime.fromisoformat(end).date()
            if today <= end_d <= in_60:
                upcoming_renewals.append({
                    "id": c['id'],
                    "lead_title": c.get('lead_title'),
                    "customer_name": c.get('customer_name'),
                    "end_date": end,
                    "days_to_expiry": (end_d - today).days,
                    "contract_value": c.get('contract_value'),
                })
        except Exception:
            pass
    upcoming_renewals.sort(key=lambda x: x['days_to_expiry'])
    return {
        "one_time": {
            "total_project_value": total_project_value,
            "revenue_realized": revenue_realized,
            "pending_invoices": pending_invoices,
            "overdue_invoices": overdue_invoices,
            "upcoming_milestones": upcoming_milestones,
            "project_count": len(one_time),
        },
        "recurring": {
            "mrr": mrr,
            "arr": arr,
            "active_subscriptions": len([c for c in recurring if c.get('contract_status') == 'active']),
            "upcoming_renewals": upcoming_renewals[:10],
            "total_contracts": len(recurring),
        },
    }

# ---- Phase 2: Renewal Pipeline auto-creation ----
@router.post("/commercials/run-renewal-scan")
async def run_renewal_scan(current_user: dict = Depends(get_current_user)):
    """Scan active recurring contracts; for any that have entered their renewal-notice window
    and don't already have a renewal lead, mark contract_status=renewal_due and auto-create a
    renewal Lead (status Renewal) tagged back to the contract.
    Idempotent — safe to call repeatedly."""
    if not (current_user.get('role') == UserRole.SUPER_ADMIN.value or current_user.get('is_finance') or current_user.get('is_delivery') or current_user.get('is_vyapaar_ops')):
        raise HTTPException(status_code=403, detail="Admin / finance / delivery only")

    today = datetime.now(timezone.utc).date()
    # Ensure a "Renewal" lead status exists
    renewal_status = await db.lead_statuses.find_one({"name": "Renewal"}, {"_id": 0})
    if not renewal_status:
        rs_id = str(uuid.uuid4())
        renewal_status = {
            "id": rs_id, "name": "Renewal", "color": "#0EA5E9", "order": 10,
            "is_active": True, "is_won": False
        }
        await db.lead_statuses.insert_one(renewal_status)

    candidates = await db.commercials.find({
        "type": "recurring",
        "contract_status": {"$in": ["active", "renewal_due"]}
    }, {"_id": 0}).to_list(2000)

    created_count = 0
    flagged_count = 0
    skipped_count = 0
    items: List[dict] = []
    for c in candidates:
        end_date = c.get('contract_end_date')
        if not end_date:
            continue
        try:
            end_d = datetime.fromisoformat(end_date).date()
        except Exception:
            continue
        notice_days = int(c.get('renewal_notice_days') or 30)
        notice_start = end_d - timedelta(days=notice_days)
        if today < notice_start:
            continue  # Not yet in renewal window

        if c.get('renewal_lead_id'):
            existing = await db.leads.find_one({"id": c['renewal_lead_id']}, {"_id": 0})
            if existing:
                if c.get('contract_status') != 'renewal_due':
                    await db.commercials.update_one({"id": c['id']}, {"$set": {"contract_status": "renewal_due", "updated_at": _now_iso()}})
                    flagged_count += 1
                skipped_count += 1
                continue

        original_lead = await db.leads.find_one({"id": c['lead_id']}, {"_id": 0}) or {}
        primary_category_id = original_lead.get('primary_category_id')
        if not primary_category_id:
            cat = await db.primary_categories.find_one({"is_active": True}, {"_id": 0})
            if not cat:
                continue
            primary_category_id = cat['id']

        new_lead_id = str(uuid.uuid4())
        days_to_expiry = (end_d - today).days
        lead_doc = {
            "id": new_lead_id,
            "title": f"Renewal — {c.get('lead_title') or original_lead.get('title') or 'contract'}",
            "description": f"Auto-created renewal opportunity for contract ending {end_date} ({days_to_expiry} days). Auto renewal: {'Yes' if c.get('auto_renewal') else 'No'}. Renewal type: {c.get('renewal_type','manual')}.",
            "customer_name": c.get('customer_name') or original_lead.get('customer_name') or 'Renewal Customer',
            "customer_email": original_lead.get('customer_email') or '',
            "customer_phone": original_lead.get('customer_phone'),
            "customer_company": original_lead.get('customer_company'),
            "customer_id": c.get('customer_id') or original_lead.get('customer_id'),
            "selling_partner_id": original_lead.get('selling_partner_id'),
            "sales_associate_id": original_lead.get('sales_associate_id'),
            "primary_category_id": primary_category_id,
            "secondary_category_id": original_lead.get('secondary_category_id'),
            "deal_value": c.get('contract_value') or 0,
            "status_id": renewal_status['id'],
            "is_internal_request": False,
            "renewal_for_commercial_id": c['id'],
            "renewal_for_lead_id": c['lead_id'],
            "follow_ups": [], "comments": [], "documents": [],
            "assigned_partners": [],
            "created_by": current_user['id'],
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        await db.leads.insert_one(lead_doc)
        await db.commercials.update_one({"id": c['id']}, {"$set": {
            "contract_status": "renewal_due",
            "renewal_lead_id": new_lead_id,
            "updated_at": _now_iso(),
        }})
        await _log_commercial_activity(c['id'], current_user, "renewal_lead_created", f"Renewal pipeline auto-created (lead {lead_doc['title']})", {"renewal_lead_id": new_lead_id})
        created_count += 1
        items.append({"commercial_id": c['id'], "lead_id": new_lead_id, "title": lead_doc['title'], "days_to_expiry": days_to_expiry})

    return {
        "created": created_count,
        "flagged": flagged_count,
        "skipped": skipped_count,
        "items": items,
    }

# ---- Phase 2: Analytics ----
@router.get("/commercials/analytics")
async def commercials_analytics(months: int = 12, current_user: dict = Depends(get_current_user)):
    """Returns MRR trend (last N months), churn metrics, revenue forecast (next 90 days),
    and project-vs-recurring revenue mix."""
    if not (current_user.get('role') == UserRole.SUPER_ADMIN.value or current_user.get('is_finance') or current_user.get('is_delivery') or current_user.get('is_vyapaar_ops')):
        raise HTTPException(status_code=403, detail="Admin / finance / delivery only")

    today = datetime.now(timezone.utc).date()
    months = max(1, min(36, int(months)))

    all_comm = await db.commercials.find({}, {"_id": 0}).to_list(2000)
    payments = await db.commercial_payments.find({}, {"_id": 0}).to_list(5000)
    invoices = await db.commercial_invoices.find({}, {"_id": 0}).to_list(5000)

    buckets: List[dict] = []
    cursor = datetime(today.year, today.month, 1)
    cursor = _add_months(cursor, -(months - 1))
    for _ in range(months):
        next_month = _add_months(cursor, 1)
        buckets.append({
            "label": cursor.strftime("%b %Y"),
            "key": cursor.strftime("%Y-%m"),
            "start_date": cursor.date(),
            "end_date": (next_month - timedelta(days=1)).date(),
            "mrr": 0.0,
            "active_contracts": 0,
            "new_contracts": 0,
            "churned_contracts": 0,
            "revenue_collected": 0.0,
            "invoices_raised": 0.0,
        })
        cursor = next_month

    def _to_date_safe(s):
        if not s:
            return None
        try:
            return datetime.fromisoformat(str(s).replace('Z', '+00:00')).date()
        except Exception:
            try:
                return datetime.fromisoformat(str(s)[:10]).date()
            except Exception:
                return None

    for c in all_comm:
        if c.get('type') != 'recurring':
            continue
        start = _to_date_safe(c.get('contract_start_date'))
        end = _to_date_safe(c.get('contract_end_date'))
        cstatus = c.get('contract_status') or 'active'
        v = float(c.get('contract_value') or 0)
        months_step = FREQ_MONTHS.get(c.get('billing_frequency') or 'monthly', 1)
        monthly_value = v / months_step if months_step else 0

        churn_date = None
        if cstatus in ('cancelled', 'expired') and end:
            churn_date = end

        for b in buckets:
            if not start:
                continue
            active_in_bucket = start <= b['end_date'] and (not end or end >= b['start_date'])
            if active_in_bucket:
                if cstatus not in ('cancelled', 'expired') or (end and end >= b['start_date']):
                    b['active_contracts'] += 1
                    b['mrr'] += monthly_value
                if b['start_date'] <= start <= b['end_date']:
                    b['new_contracts'] += 1
                if churn_date and b['start_date'] <= churn_date <= b['end_date']:
                    b['churned_contracts'] += 1

    for p in payments:
        pd = _to_date_safe(p.get('paid_at'))
        if not pd:
            continue
        for b in buckets:
            if b['start_date'] <= pd <= b['end_date']:
                b['revenue_collected'] += float(p.get('amount') or 0)
                break

    for inv in invoices:
        rd = _to_date_safe(inv.get('raised_at'))
        if not rd:
            continue
        for b in buckets:
            if b['start_date'] <= rd <= b['end_date']:
                b['invoices_raised'] += float(inv.get('amount') or 0)
                break

    series = []
    for b in buckets:
        churn_rate = 0
        if b['active_contracts'] > 0:
            churn_rate = round((b['churned_contracts'] / max(b['active_contracts'], 1)) * 100, 2)
        series.append({
            "label": b['label'],
            "key": b['key'],
            "mrr": round(b['mrr'], 2),
            "arr": round(b['mrr'] * 12, 2),
            "active_contracts": b['active_contracts'],
            "new_contracts": b['new_contracts'],
            "churned_contracts": b['churned_contracts'],
            "churn_rate_pct": churn_rate,
            "revenue_collected": round(b['revenue_collected'], 2),
            "invoices_raised": round(b['invoices_raised'], 2),
        })

    in_90 = today + timedelta(days=90)
    forecast_pending_invoices = 0.0
    forecast_recurring_billings = 0.0
    forecast_milestones = 0.0
    for inv in invoices:
        if inv.get('status') in ('raised', 'partial', 'overdue'):
            due = _to_date_safe(inv.get('due_date'))
            amt_outstanding = float(inv.get('amount') or 0) - float(inv.get('amount_paid') or 0)
            if due and today <= due <= in_90:
                forecast_pending_invoices += max(0, amt_outstanding)
    for c in all_comm:
        if c.get('type') == 'recurring':
            for s in (c.get('billing_schedule') or []):
                if s.get('status') == 'scheduled':
                    due = _to_date_safe(s.get('due_date'))
                    if due and today <= due <= in_90:
                        forecast_recurring_billings += float(s.get('amount') or 0)
        else:
            for m in (c.get('milestones') or []):
                if m.get('status') in ('pending', 'in_progress', 'delivered'):
                    due = _to_date_safe(m.get('invoice_due_date') or m.get('delivery_date'))
                    if due and today <= due <= in_90:
                        forecast_milestones += float(m.get('amount') or 0)

    forecast_total = forecast_pending_invoices + forecast_recurring_billings + forecast_milestones

    one_time_revenue = 0.0
    recurring_revenue = 0.0
    for p in payments:
        comm = next((x for x in all_comm if x['id'] == p.get('commercial_id')), None)
        if not comm:
            continue
        if comm.get('type') == 'recurring':
            recurring_revenue += float(p.get('amount') or 0)
        else:
            one_time_revenue += float(p.get('amount') or 0)

    return {
        "series": series,
        "forecast_90d": {
            "total": round(forecast_total, 2),
            "pending_invoices": round(forecast_pending_invoices, 2),
            "recurring_billings": round(forecast_recurring_billings, 2),
            "project_milestones": round(forecast_milestones, 2),
        },
        "revenue_mix": {
            "one_time": round(one_time_revenue, 2),
            "recurring": round(recurring_revenue, 2),
        },
        "current": {
            "mrr": series[-1]['mrr'] if series else 0,
            "arr": series[-1]['arr'] if series else 0,
            "active_contracts": series[-1]['active_contracts'] if series else 0,
            "churn_rate_pct": series[-1]['churn_rate_pct'] if series else 0,
        }
    }

# ---- Phase 2.5: Reminder scan (in-app notifications; email/SMS scaffolded but disabled) ----
COMMERCIAL_REMINDER_DEDUP_HOURS = 20  # don't re-notify same item more often than this

async def _has_recent_commercial_reminder(user_id: str, ntype: str, commercial_id: str, key: str, hours: int = COMMERCIAL_REMINDER_DEDUP_HOURS) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    existing = await db.notifications.find_one({
        "user_id": user_id,
        "type": ntype,
        "commercial_id": commercial_id,
        "data.dedup_key": key,
        "created_at": {"$gte": cutoff}
    }, {"_id": 0})
    return bool(existing)

async def _emit_commercial_reminder(user_ids: List[str], ntype: str, title: str, message: str, commercial_id: str, lead_id: str, dedup_key: str, extra: dict = None) -> int:
    """Create in-app notifications (dedup-aware). Also a placeholder for SendGrid/Twilio when keys are configured later."""
    sent = 0
    payload = {"dedup_key": dedup_key, **(extra or {})}
    for uid in set(filter(None, user_ids)):
        if await _has_recent_commercial_reminder(uid, ntype, commercial_id, dedup_key):
            continue
        await create_notification(uid, ntype, title, message, lead_id=lead_id, data=payload, commercial_id=commercial_id)
        sent += 1
    # Email/SMS hooks — disabled until keys configured. To enable later, drop in calls here:
    #   send_email(billing_contact_email, title, message); send_sms(billing_contact_phone, message)
    return sent

async def _commercial_recipient_ids(commercial: dict) -> List[str]:
    """Recipients = owners on the commercial + super admins."""
    ids = [
        commercial.get('project_owner_id'),
        commercial.get('delivery_spoc_id'),
        commercial.get('billing_contact_id'),
        commercial.get('account_manager_id'),
        commercial.get('contract_owner_id'),
        commercial.get('created_by'),
    ]
    admins = await db.users.find({"role": "super_admin", "is_active": True}, {"_id": 0, "id": 1}).to_list(100)
    ids.extend(a['id'] for a in admins)
    return [i for i in ids if i]

@router.post("/commercials/run-reminder-scan")
async def run_commercial_reminder_scan(milestone_lead_days: int = 3, current_user: dict = Depends(get_current_user)):
    """Scan commercials and emit in-app notifications for:
      - Milestones due within `milestone_lead_days` (default 3)
      - Invoices past their due_date and still unpaid
      - Recurring billings due within `milestone_lead_days`
      - Contracts inside their renewal-notice window
    Idempotent: dedup window of 20h per (user, type, commercial, dedup_key)."""
    if not (current_user.get('role') == UserRole.SUPER_ADMIN.value or current_user.get('is_finance') or current_user.get('is_delivery') or current_user.get('is_vyapaar_ops')):
        raise HTTPException(status_code=403, detail="Admin / finance / delivery only")

    today = datetime.now(timezone.utc).date()
    cutoff = today + timedelta(days=milestone_lead_days)
    all_comm = await db.commercials.find({}, {"_id": 0}).to_list(2000)
    invoices = await db.commercial_invoices.find({"status": {"$in": ["raised", "partial", "overdue"]}}, {"_id": 0}).to_list(5000)

    counts = {"milestones_due": 0, "invoices_overdue": 0, "billings_due": 0, "renewals": 0, "notifications": 0}

    def _safe_date(s):
        if not s:
            return None
        try:
            return datetime.fromisoformat(str(s).replace('Z', '+00:00')).date()
        except Exception:
            try:
                return datetime.fromisoformat(str(s)[:10]).date()
            except Exception:
                return None

    # Build a lookup of commercials by id for invoice scan
    comm_by_id = {c['id']: c for c in all_comm}

    # 1) Milestones due
    for c in all_comm:
        if c.get('type') != 'one_time':
            continue
        recipients = await _commercial_recipient_ids(c)
        for m in c.get('milestones', []):
            if m.get('status') not in ('pending', 'in_progress'):
                continue
            d = _safe_date(m.get('delivery_date'))
            if not d or not (today <= d <= cutoff):
                continue
            days = (d - today).days
            dedup = f"milestone:{m['id']}:{d.isoformat()}"
            title = f"Milestone due in {days}d — {c.get('lead_title')}"
            message = f"\"{m.get('name')}\" is due on {d.isoformat()} ({c.get('currency','INR')} {m.get('amount',0)})."
            n = await _emit_commercial_reminder(
                recipients, NotificationType.COMMERCIAL_MILESTONE_DUE.value, title, message,
                commercial_id=c['id'], lead_id=c.get('lead_id'),
                dedup_key=dedup, extra={"milestone_id": m['id'], "due_date": d.isoformat(), "days": days}
            )
            counts['milestones_due'] += 1
            counts['notifications'] += n

    # 2) Invoices overdue
    for inv in invoices:
        d = _safe_date(inv.get('due_date'))
        if not d or d >= today:
            continue
        c = comm_by_id.get(inv.get('commercial_id'))
        if not c:
            continue
        recipients = await _commercial_recipient_ids(c)
        days = (today - d).days
        outstanding = float(inv.get('amount') or 0) - float(inv.get('amount_paid') or 0)
        if outstanding <= 0:
            continue
        dedup = f"invoice:{inv['id']}:{today.isoformat()}"  # day-bucketed so it re-pings once/day
        title = f"Invoice overdue {days}d — {inv.get('invoice_number')}"
        message = f"{c.get('currency','INR')} {outstanding:.2f} outstanding on \"{c.get('lead_title')}\" (due {d.isoformat()})."
        n = await _emit_commercial_reminder(
            recipients, NotificationType.COMMERCIAL_INVOICE_OVERDUE.value, title, message,
            commercial_id=c['id'], lead_id=c.get('lead_id'),
            dedup_key=dedup, extra={"invoice_id": inv['id'], "outstanding": outstanding, "days_overdue": days}
        )
        counts['invoices_overdue'] += 1
        counts['notifications'] += n

    # 3) Recurring billings due soon
    for c in all_comm:
        if c.get('type') != 'recurring':
            continue
        recipients = await _commercial_recipient_ids(c)
        for s in (c.get('billing_schedule') or []):
            if s.get('status') != 'scheduled':
                continue
            d = _safe_date(s.get('due_date'))
            if not d or not (today <= d <= cutoff):
                continue
            days = (d - today).days
            dedup = f"billing:{s['id']}:{d.isoformat()}"
            title = f"Billing period due in {days}d — {c.get('lead_title')}"
            message = f"Recurring billing for {s.get('period_start')} → {s.get('period_end')} ({c.get('currency','INR')} {s.get('amount',0)}) due {d.isoformat()}."
            n = await _emit_commercial_reminder(
                recipients, NotificationType.COMMERCIAL_BILLING_DUE.value, title, message,
                commercial_id=c['id'], lead_id=c.get('lead_id'),
                dedup_key=dedup, extra={"billing_id": s['id'], "due_date": d.isoformat(), "days": days}
            )
            counts['billings_due'] += 1
            counts['notifications'] += n

    # 4) Renewal window (recurring contracts whose end_date - renewal_notice_days <= today)
    for c in all_comm:
        if c.get('type') != 'recurring':
            continue
        end = _safe_date(c.get('contract_end_date'))
        if not end:
            continue
        notice = int(c.get('renewal_notice_days') or 30)
        window_start = end - timedelta(days=notice)
        if today < window_start or today > end:
            continue
        recipients = await _commercial_recipient_ids(c)
        days = (end - today).days
        dedup = f"renewal:{c['id']}:{end.isoformat()}"
        auto = "Auto-renews" if c.get('auto_renewal') else "Manual renewal required"
        title = f"Renewal window — {days}d to expiry"
        message = f"Contract \"{c.get('lead_title')}\" ends {end.isoformat()}. {auto}."
        n = await _emit_commercial_reminder(
            recipients, NotificationType.COMMERCIAL_RENEWAL_WINDOW.value, title, message,
            commercial_id=c['id'], lead_id=c.get('lead_id'),
            dedup_key=dedup, extra={"end_date": end.isoformat(), "days_to_expiry": days, "auto_renewal": bool(c.get('auto_renewal'))}
        )
        counts['renewals'] += 1
        counts['notifications'] += n

    return {**counts, "scanned_commercials": len(all_comm), "scanned_invoices": len(invoices)}

# ---- Phase 3: AI suggestions, PDF invoices, Kanban ----
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

class AIMilestoneSuggestRequest(BaseModel):
    project_title: Optional[str] = None
    description: Optional[str] = None
    total_value: float
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    currency: str = "INR"

@router.post("/commercials/ai/suggest-milestones")
async def ai_suggest_milestones(payload: AIMilestoneSuggestRequest, current_user: dict = Depends(get_current_user)):
    """Use the configured LLM to suggest a milestone breakdown based on past deals + project brief."""
    if not (current_user.get('role') == UserRole.SUPER_ADMIN.value or current_user.get('is_finance') or current_user.get('is_delivery') or current_user.get('is_vyapaar_ops')):
        raise HTTPException(status_code=403, detail="Admin / finance / delivery only")
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=503, detail="LLM key not configured. Set EMERGENT_LLM_KEY in backend .env")

    # Gather past one-time projects for context (most recent 20)
    past = await db.commercials.find({"type": "one_time", "milestones": {"$exists": True, "$ne": []}}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
    past_summaries = []
    for p in past[:12]:
        ms = p.get('milestones') or []
        past_summaries.append({
            "title": p.get('lead_title'),
            "value": p.get('total_value'),
            "milestones": [{"name": m.get('name'), "percentage": m.get('percentage'), "amount": m.get('amount')} for m in ms],
        })

    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"milestone-suggest-{current_user['id']}-{uuid.uuid4()}",
        system_message=(
            "You are a delivery-management assistant. Given a project brief and a sample of past "
            "deals' milestone structures, suggest a clean milestone breakdown. Always respond with "
            "STRICT JSON. No prose, no markdown. The JSON object MUST have a 'milestones' array of "
            "{name (string), description (string), percentage (number), delivery_offset_days (integer, "
            "days from project start)}. The sum of all percentages MUST equal exactly 100."
        )
    ).with_model("gemini", "gemini-3.1-pro-preview")

    duration_hint = ""
    if payload.start_date and payload.end_date:
        try:
            sd = datetime.fromisoformat(payload.start_date[:10]).date()
            ed = datetime.fromisoformat(payload.end_date[:10]).date()
            duration_hint = f"Total project duration: {(ed - sd).days} days."
        except Exception:
            pass

    prompt = (
        f"Project title: {payload.project_title or 'Untitled'}\n"
        f"Brief: {payload.description or 'N/A'}\n"
        f"Total value: {payload.currency} {payload.total_value}\n"
        f"{duration_hint}\n\n"
        f"Past deals for reference (truncated):\n{_json.dumps(past_summaries[:6], indent=2)}\n\n"
        "Suggest 3-5 milestones that match typical project shapes for this kind of work. "
        "Output STRICT JSON only."
    )

    try:
        response = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        logger.exception(f"LLM error: {e}")
        raise HTTPException(status_code=502, detail=f"LLM request failed: {str(e)[:120]}")

    raw = (response or "").strip()
    # Strip code fences if present
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        parsed = _json.loads(raw)
        milestones = parsed.get("milestones") or []
    except Exception:
        # Last-resort: try to find JSON braces
        import re as _re
        m = _re.search(r'\{.*\}', raw, _re.DOTALL)
        if not m:
            raise HTTPException(status_code=502, detail="LLM returned non-JSON output")
        try:
            parsed = _json.loads(m.group(0))
            milestones = parsed.get("milestones") or []
        except Exception:
            raise HTTPException(status_code=502, detail="LLM returned malformed JSON")

    # Normalise: clamp percentages, compute amounts, compute delivery_date
    start_dt = None
    if payload.start_date:
        try:
            start_dt = datetime.fromisoformat(payload.start_date[:10]).date()
        except Exception:
            pass

    total_pct = sum((m.get('percentage') or 0) for m in milestones)
    if not milestones or total_pct <= 0:
        raise HTTPException(status_code=502, detail="LLM suggestions had invalid percentages")
    factor = 100.0 / total_pct
    cleaned = []
    pct_sum = 0
    for idx, m in enumerate(milestones):
        pct = round(float(m.get('percentage') or 0) * factor, 2)
        pct_sum += pct
        offset = int(m.get('delivery_offset_days') or 0)
        delivery_date = (start_dt + timedelta(days=offset)).isoformat() if start_dt else None
        amount = round(payload.total_value * (pct / 100.0), 2)
        cleaned.append({
            "name": str(m.get('name') or f"Milestone {idx+1}")[:120],
            "description": str(m.get('description') or '')[:500],
            "percentage": pct,
            "amount": amount,
            "delivery_date": delivery_date,
            "delivery_offset_days": offset,
        })
    # Correct rounding drift on last entry
    if cleaned and abs(pct_sum - 100) > 0.01:
        diff = round(100 - pct_sum + cleaned[-1]['percentage'], 2)
        cleaned[-1]['percentage'] = diff
        cleaned[-1]['amount'] = round(payload.total_value * (diff / 100.0), 2)

    return {"milestones": cleaned, "model": "gemini-3.1-pro-preview"}

@router.get("/commercials/{commercial_id}/ai/renewal-probability")
async def ai_renewal_probability(commercial_id: str, current_user: dict = Depends(get_current_user)):
    """Heuristic-based renewal probability with optional LLM-generated reasoning."""
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=False)
    if commercial.get('type') != 'recurring':
        raise HTTPException(status_code=400, detail="Renewal probability only applies to recurring contracts")

    # --- Heuristic scoring (deterministic; works without LLM) ---
    score = 0.50
    factors: List[str] = []

    if commercial.get('auto_renewal'):
        score += 0.25
        factors.append("Auto-renewal enabled (+25%)")
    if commercial.get('renewal_type') == 'auto':
        score += 0.10
        factors.append("Renewal type: auto (+10%)")
    elif commercial.get('renewal_type') == 'approval_required':
        score -= 0.05
        factors.append("Approval required (-5%)")

    # Payment history strength
    payments = await db.commercial_payments.find({"commercial_id": commercial_id}, {"_id": 0}).to_list(500)
    invoices = await db.commercial_invoices.find({"commercial_id": commercial_id}, {"_id": 0}).to_list(500)
    total_invoiced = sum(float(i.get('amount') or 0) for i in invoices)
    total_paid = sum(float(p.get('amount') or 0) for p in payments)
    on_time_pmt = total_paid >= total_invoiced * 0.95
    overdue_count = 0
    today = datetime.now(timezone.utc).date()
    for inv in invoices:
        if inv.get('status') in ('raised', 'partial'):
            try:
                if inv.get('due_date') and datetime.fromisoformat(inv['due_date'][:10]).date() < today:
                    overdue_count += 1
            except Exception:
                pass

    if on_time_pmt and len(invoices) >= 2:
        score += 0.10
        factors.append("Strong payment history (+10%)")
    if overdue_count > 0:
        penalty = min(0.25, 0.05 * overdue_count)
        score -= penalty
        factors.append(f"{overdue_count} overdue invoice(s) (-{int(penalty*100)}%)")

    # Contract tenure: longer active contracts renew more
    if commercial.get('contract_start_date') and commercial.get('contract_end_date'):
        try:
            s = datetime.fromisoformat(commercial['contract_start_date'][:10]).date()
            e = datetime.fromisoformat(commercial['contract_end_date'][:10]).date()
            tenure_months = max(0, (e - s).days // 30)
            if tenure_months >= 12:
                score += 0.05
                factors.append(f"{tenure_months}m tenure (+5%)")
        except Exception:
            pass

    if commercial.get('contract_status') in ('cancelled', 'expired'):
        score = max(0.10, score - 0.40)
        factors.append("Contract not active (-40%)")

    score = max(0.0, min(1.0, score))
    band = 'high' if score >= 0.7 else ('medium' if score >= 0.4 else 'low')

    return {
        "commercial_id": commercial_id,
        "probability": round(score, 2),
        "band": band,
        "factors": factors,
        "total_invoiced": round(total_invoiced, 2),
        "total_paid": round(total_paid, 2),
        "overdue_count": overdue_count,
    }

@router.get("/commercials/{commercial_id}/ai/payment-delay-risk")
async def ai_payment_delay_risk(commercial_id: str, current_user: dict = Depends(get_current_user)):
    """Heuristic payment-delay risk per outstanding invoice."""
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=False)

    invoices = await db.commercial_invoices.find({"commercial_id": commercial_id}, {"_id": 0}).to_list(500)

    # Historical average pay-lag (days between raised_at and paid_at on PAID invoices)
    pay_lags = []
    for inv in invoices:
        if inv.get('status') == 'paid' and inv.get('paid_at') and inv.get('raised_at'):
            try:
                r = datetime.fromisoformat(inv['raised_at'].replace('Z', '+00:00'))
                p = datetime.fromisoformat(inv['paid_at'].replace('Z', '+00:00'))
                pay_lags.append((p - r).days)
            except Exception:
                pass
    avg_lag = round(sum(pay_lags) / len(pay_lags), 1) if pay_lags else None

    today = datetime.now(timezone.utc).date()
    items = []
    for inv in invoices:
        if inv.get('status') not in ('raised', 'partial', 'overdue'):
            continue
        risk_score = 0.30
        risk_factors = []
        if inv.get('due_date'):
            try:
                d = datetime.fromisoformat(inv['due_date'][:10]).date()
                days_to_due = (d - today).days
                if days_to_due < 0:
                    risk_score += min(0.50, 0.05 * abs(days_to_due))
                    risk_factors.append(f"{abs(days_to_due)}d overdue")
                elif days_to_due <= 3:
                    risk_score += 0.20
                    risk_factors.append(f"Due in {days_to_due}d")
            except Exception:
                pass
        if avg_lag is not None and avg_lag > 14:
            risk_score += 0.15
            risk_factors.append(f"Avg pay-lag {avg_lag}d")
        outstanding = float(inv.get('amount') or 0) - float(inv.get('amount_paid') or 0)
        if outstanding > 100000:  # large invoices skew risk
            risk_score += 0.10
            risk_factors.append("Large outstanding")

        risk_score = min(1.0, max(0.0, risk_score))
        items.append({
            "invoice_id": inv['id'],
            "invoice_number": inv.get('invoice_number'),
            "outstanding": round(outstanding, 2),
            "due_date": inv.get('due_date'),
            "risk_score": round(risk_score, 2),
            "band": 'high' if risk_score >= 0.7 else ('medium' if risk_score >= 0.4 else 'low'),
            "factors": risk_factors,
        })
    items.sort(key=lambda x: -x['risk_score'])
    return {"avg_pay_lag_days": avg_lag, "invoices": items}

@router.get("/commercials/kanban")
async def commercials_kanban(current_user: dict = Depends(get_current_user)):
    """Group all commercials into kanban columns by status."""
    if not (current_user.get('role') == UserRole.SUPER_ADMIN.value or current_user.get('is_finance') or current_user.get('is_delivery') or current_user.get('is_vyapaar_ops') or current_user.get('role') == UserRole.SELLING_PARTNER.value):
        raise HTTPException(status_code=403, detail="Forbidden")
    query: Dict[str, Any] = {}
    if current_user.get('role') == UserRole.SELLING_PARTNER.value:
        leads = await db.leads.find({
            "$or": [
                {"selling_partner_id": current_user['id']},
                {"assigned_partners.partner_id": current_user['id']},
                {"assigned_partners.partner_id": current_user.get('company_id')},
            ]
        }, {"_id": 0, "id": 1}).to_list(2000)
        query['lead_id'] = {"$in": [ld['id'] for ld in leads]}
    items = await db.commercials.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)

    columns: Dict[str, dict] = {
        "active": {"key": "active", "label": "Active", "color": "#10B981", "items": []},
        "renewal_due": {"key": "renewal_due", "label": "Renewal Due", "color": "#F59E0B", "items": []},
        "renewed": {"key": "renewed", "label": "Renewed", "color": "#4169E1", "items": []},
        "on_hold": {"key": "on_hold", "label": "On Hold", "color": "#6B7280", "items": []},
        "expired": {"key": "expired", "label": "Expired", "color": "#DC143C", "items": []},
        "cancelled": {"key": "cancelled", "label": "Cancelled", "color": "#9CA3AF", "items": []},
        "one_time": {"key": "one_time", "label": "One-Time Projects", "color": "#8B5CF6", "items": []},
    }
    for c in items:
        if c.get('type') == 'one_time':
            columns['one_time']['items'].append(c)
        else:
            col = c.get('contract_status') or 'active'
            if col in columns:
                columns[col]['items'].append(c)
            else:
                columns['active']['items'].append(c)
    return {"columns": list(columns.values())}

@router.get("/commercials/{commercial_id}/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(commercial_id: str, invoice_id: str, current_user: dict = Depends(get_current_user)):
    """Generate a PDF for an invoice on the fly."""
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=False)
    invoice = await db.commercial_invoices.find_one({"id": invoice_id, "commercial_id": commercial_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    # Pull seller info from first super-admin's company (or fall back)
    customer = None
    if commercial.get('customer_id'):
        customer = await db.customers.find_one({"id": commercial['customer_id']}, {"_id": 0})

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', parent=styles['Heading1'], textColor=colors.HexColor('#0F172A'), spaceAfter=6)
    h2 = ParagraphStyle('h2', parent=styles['Heading3'], textColor=colors.HexColor('#0F172A'), spaceAfter=4)
    body = ParagraphStyle('body', parent=styles['BodyText'], textColor=colors.HexColor('#0F172A'))
    muted = ParagraphStyle('muted', parent=styles['BodyText'], textColor=colors.HexColor('#64748B'), fontSize=9)
    story = []
    story.append(Paragraph("INVOICE", h1))
    story.append(Paragraph("<b>Meshora — Powered by Vyapaar Network</b>", muted))
    story.append(Spacer(1, 8))
    meta_rows = [
        ["Invoice Number", invoice.get('invoice_number') or '-'],
        ["Status", (invoice.get('status') or '').upper()],
        ["Raised", (invoice.get('raised_at') or '')[:10]],
        ["Due", (invoice.get('due_date') or '-')[:10]],
    ]
    t = Table(meta_rows, colWidths=[40*mm, 80*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#0F172A')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # Bill-to / Project
    story.append(Paragraph("Billed to", h2))
    bill_to = customer.get('name') if customer else (commercial.get('customer_name') or '-')
    bill_email = customer.get('email') if customer else ''
    story.append(Paragraph(f"{bill_to}", body))
    if bill_email:
        story.append(Paragraph(bill_email, muted))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Project / Contract", h2))
    story.append(Paragraph(commercial.get('lead_title') or '-', body))
    story.append(Spacer(1, 10))

    # Amount block
    currency = invoice.get('currency') or commercial.get('currency') or 'INR'
    amt = float(invoice.get('amount') or 0)
    paid = float(invoice.get('amount_paid') or 0)
    due = amt - paid
    amt_rows = [
        ["Item", "Amount"],
        [Paragraph(f"Invoice for {commercial.get('lead_title')}", body), f"{currency} {amt:,.2f}"],
        ["Total", f"{currency} {amt:,.2f}"],
        ["Amount paid", f"{currency} {paid:,.2f}"],
        ["Amount due", f"{currency} {due:,.2f}"],
    ]
    at = Table(amt_rows, colWidths=[120*mm, 50*mm])
    at.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (-1,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTNAME', (0,-1), (0,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#FEF3C7')),
        ('GRID', (0,0), (-1,-1), 0.25, colors.HexColor('#E2E8F0')),
        ('ALIGN', (-1,0), (-1,-1), 'RIGHT'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(at)
    story.append(Spacer(1, 12))
    if invoice.get('notes'):
        story.append(Paragraph("Notes", h2))
        story.append(Paragraph(invoice['notes'], body))

    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", muted))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()

    headers = {"Content-Disposition": f"attachment; filename=invoice_{invoice.get('invoice_number','inv')}.pdf"}
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)

@router.get("/commercials/by-lead/{lead_id}")
async def get_commercial_by_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    commercial = await db.commercials.find_one({"lead_id": lead_id}, {"_id": 0})
    if not commercial:
        return None
    await _ensure_commercial_access(commercial, current_user, write=False)
    return commercial

@router.get("/commercials/{commercial_id}")
async def get_commercial(commercial_id: str, current_user: dict = Depends(get_current_user)):
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=False)
    return commercial

@router.patch("/commercials/{commercial_id}")
async def update_commercial(commercial_id: str, payload: CommercialUpdate, current_user: dict = Depends(get_current_user)):
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=True)
    updates = {k: (v.value if isinstance(v, Enum) else v) for k, v in payload.model_dump(exclude_unset=True).items()}
    updates['updated_at'] = _now_iso()
    # Phase 35 — contract type can be edited post-creation (One-Time ↔ Recurring)
    type_changed = 'type' in updates and updates['type'] != commercial.get('type')
    effective_type = updates.get('type', commercial.get('type'))
    # If billing-relevant fields changed for recurring (or we just became recurring), regenerate schedule
    regenerate = effective_type == 'recurring' and (type_changed or any(
        k in updates for k in ('billing_frequency', 'contract_start_date', 'contract_end_date', 'contract_value')
    ))
    await db.commercials.update_one({"id": commercial_id}, {"$set": updates})
    if regenerate:
        merged = {**commercial, **updates}
        new_schedule = _generate_billing_schedule(merged)
        await db.commercials.update_one({"id": commercial_id}, {"$set": {"billing_schedule": new_schedule}})
    # Phase 36 — if a one-time fee was just added (was 0 / null, now > 0), set status=pending
    if (
        'one_time_fee_amount' in updates
        and float(updates.get('one_time_fee_amount') or 0) > 0
        and not commercial.get('one_time_fee_status')
    ):
        await db.commercials.update_one(
            {"id": commercial_id},
            {"$set": {"one_time_fee_status": "pending"}},
        )
    if type_changed:
        await _log_commercial_activity(
            commercial_id, current_user, "type_changed",
            f"Contract type changed from {commercial.get('type')} to {updates['type']}",
            {"from": commercial.get('type'), "to": updates['type']},
        )
    # Phase 36.2 — @mentions on commercial notes ping new handles only (delta-aware)
    if 'notes' in updates and (updates.get('notes') or ''):
        try:
            from server import _parse_mentions as _pm, _notify_mentions as _nm
            prev = set(_pm(commercial.get('notes') or ''))
            now_set = set(_pm(updates.get('notes') or ''))
            newly_added = now_set - prev
            if newly_added:
                pseudo_lead_title = f"Commercial: {commercial.get('customer_name','')}"
                pseudo_lead_id = commercial.get('lead_id') or commercial_id
                # Pass the full updated notes for the preview text, but restrict
                # notification fan-out via only_tokens so previously-mentioned
                # users are NOT re-pinged.
                await _nm(
                    updates.get('notes') or '',
                    pseudo_lead_id,
                    pseudo_lead_title,
                    current_user,
                    only_tokens=list(newly_added),
                )
        except Exception as e:
            logger.warning("commercial-notes mention notify failed: %s", e)
    await _log_commercial_activity(commercial_id, current_user, "updated", "Commercial updated", {"fields": list(updates.keys())})
    updated = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    return updated

@router.put("/commercials/{commercial_id}/milestones")
async def replace_milestones(commercial_id: str, payload: MilestonesBulkInput, current_user: dict = Depends(get_current_user)):
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=True)
    if commercial.get('type') != 'one_time':
        raise HTTPException(status_code=400, detail="Milestones are only supported on one-time projects")
    # Validate totals.
    # Amounts are the source of truth when a project total_value is set:
    # if amounts sum to the project value, the breakdown is mathematically valid
    # regardless of any per-row 2-decimal display rounding on percentages.
    total_amount = sum(m.amount for m in payload.milestones)
    total_pct = sum(m.percentage for m in payload.milestones)
    target_total = float(commercial.get('total_value') or 0)
    if target_total > 0:
        if payload.milestones and round(total_amount, 2) != round(target_total, 2):
            raise HTTPException(status_code=400, detail=f"Sum of milestone amounts ({total_amount}) must equal total project value ({target_total})")
    elif payload.milestones and abs(total_pct - 100) > 0.5:
        # No project value set — percentages are the source of truth.
        # Allow up to 0.5% drift to accommodate per-row 2-decimal rounding.
        raise HTTPException(status_code=400, detail=f"Sum of milestone percentages must equal 100 (got {round(total_pct, 2)})")
    serialised = []
    for idx, m in enumerate(payload.milestones):
        # When project total_value is set, recompute each percentage from the
        # amount to keep stored data exact (avoids per-row rounding drift).
        if target_total > 0:
            pct = round((m.amount / target_total) * 100, 4)
        else:
            pct = m.percentage
        serialised.append({
            "id": m.id or str(uuid.uuid4()),
            "name": m.name,
            "description": m.description,
            "delivery_date": m.delivery_date,
            "amount": m.amount,
            "percentage": pct,
            "invoice_due_date": m.invoice_due_date,
            "status": m.status.value,
            "order": idx,
        })
    await db.commercials.update_one({"id": commercial_id}, {"$set": {"milestones": serialised, "updated_at": _now_iso()}})
    await _log_commercial_activity(commercial_id, current_user, "milestones_updated", f"Milestones saved ({len(serialised)} total)")
    return {"milestones": serialised}

@router.patch("/commercials/{commercial_id}/milestones/{milestone_id}")
async def update_milestone_status(commercial_id: str, milestone_id: str, payload: dict, current_user: dict = Depends(get_current_user)):
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=True)
    milestones = commercial.get('milestones', [])
    found = False
    for m in milestones:
        if m['id'] == milestone_id:
            found = True
            for key in ('status', 'delivery_date', 'invoice_due_date', 'description'):
                if key in payload:
                    m[key] = payload[key]
            break
    if not found:
        raise HTTPException(status_code=404, detail="Milestone not found")
    await db.commercials.update_one({"id": commercial_id}, {"$set": {"milestones": milestones, "updated_at": _now_iso()}})
    await _log_commercial_activity(commercial_id, current_user, "milestone_status", "Milestone updated", {"milestone_id": milestone_id, "changes": payload})
    return {"milestones": milestones}

@router.post("/commercials/{commercial_id}/regenerate-billing")
async def regenerate_billing(commercial_id: str, current_user: dict = Depends(get_current_user)):
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=True)
    if commercial.get('type') != 'recurring':
        raise HTTPException(status_code=400, detail="Billing schedule only applies to recurring contracts")
    schedule = _generate_billing_schedule(commercial)
    await db.commercials.update_one({"id": commercial_id}, {"$set": {"billing_schedule": schedule, "updated_at": _now_iso()}})
    await _log_commercial_activity(commercial_id, current_user, "billing_regenerated", f"Billing schedule regenerated ({len(schedule)} periods)")
    return {"billing_schedule": schedule}

@router.post("/commercials/{commercial_id}/invoices")
async def create_invoice(commercial_id: str, payload: InvoiceCreate, current_user: dict = Depends(get_current_user)):
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=True)
    invoice_id = str(uuid.uuid4())
    doc = {
        "id": invoice_id,
        "commercial_id": commercial_id,
        "milestone_id": payload.milestone_id,
        "billing_schedule_id": payload.billing_schedule_id,
        "invoice_number": payload.invoice_number,
        "amount": payload.amount,
        "currency": commercial.get('currency', 'INR'),
        "status": InvoiceStatus.RAISED.value,
        "due_date": payload.due_date,
        "raised_at": payload.raised_at or _now_iso(),
        "paid_at": None,
        "amount_paid": 0.0,
        "notes": payload.notes,
        "is_one_time_fee": bool(payload.is_one_time_fee),  # Phase 36 — track SaaS setup-fee invoices distinctly
        "created_at": _now_iso(),
        "created_by": current_user['id'],
    }
    await db.commercial_invoices.insert_one(doc)
    # Phase 36 — flip the one-time fee status when its invoice is raised
    if payload.is_one_time_fee and commercial.get('one_time_fee_amount'):
        await db.commercials.update_one(
            {"id": commercial_id},
            {"$set": {"one_time_fee_status": "invoiced", "one_time_fee_invoice_id": invoice_id, "updated_at": _now_iso()}},
        )
    # Link to milestone / billing schedule
    if payload.milestone_id:
        milestones = commercial.get('milestones', [])
        for m in milestones:
            if m['id'] == payload.milestone_id:
                m['status'] = MilestoneStatus.INVOICE_RAISED.value
                m['invoice_id'] = invoice_id
        await db.commercials.update_one({"id": commercial_id}, {"$set": {"milestones": milestones}})
    if payload.billing_schedule_id:
        schedule = commercial.get('billing_schedule', [])
        for s in schedule:
            if s['id'] == payload.billing_schedule_id:
                s['status'] = 'invoiced'
                s['invoice_id'] = invoice_id
        await db.commercials.update_one({"id": commercial_id}, {"$set": {"billing_schedule": schedule}})
    await _log_commercial_activity(commercial_id, current_user, "invoice_raised", f"Invoice {payload.invoice_number} raised ({commercial.get('currency','INR')} {payload.amount})", {"invoice_id": invoice_id})
    return {k: v for k, v in doc.items() if k != '_id'}

@router.get("/commercials/{commercial_id}/invoices")
async def list_invoices(commercial_id: str, current_user: dict = Depends(get_current_user)):
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=False)
    invoices = await db.commercial_invoices.find({"commercial_id": commercial_id}, {"_id": 0}).sort("raised_at", -1).to_list(500)
    return invoices

@router.patch("/commercials/{commercial_id}/invoices/{invoice_id}")
async def update_invoice(commercial_id: str, invoice_id: str, payload: InvoiceUpdate, current_user: dict = Depends(get_current_user)):
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=True)
    updates = {k: (v.value if isinstance(v, Enum) else v) for k, v in payload.model_dump(exclude_unset=True).items()}
    if updates:
        await db.commercial_invoices.update_one({"id": invoice_id, "commercial_id": commercial_id}, {"$set": updates})
        await _log_commercial_activity(commercial_id, current_user, "invoice_updated", "Invoice updated", {"invoice_id": invoice_id, "fields": list(updates.keys())})
    invoice = await db.commercial_invoices.find_one({"id": invoice_id}, {"_id": 0})
    return invoice

@router.post("/commercials/{commercial_id}/payments")
async def record_payment(commercial_id: str, payload: PaymentCreate, current_user: dict = Depends(get_current_user)):
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=True)
    payment_id = str(uuid.uuid4())
    paid_at = payload.paid_at or _now_iso()
    pdoc = {
        "id": payment_id,
        "commercial_id": commercial_id,
        "invoice_id": payload.invoice_id,
        "milestone_id": payload.milestone_id,
        "billing_schedule_id": payload.billing_schedule_id,
        "amount": payload.amount,
        "currency": commercial.get('currency', 'INR'),
        "paid_at": paid_at,
        "method": payload.method,
        "reference": payload.reference,
        "notes": payload.notes,
        "created_at": _now_iso(),
        "created_by": current_user['id'],
    }
    await db.commercial_payments.insert_one(pdoc)
    # Update invoice status & amount_paid
    if payload.invoice_id:
        invoice = await db.commercial_invoices.find_one({"id": payload.invoice_id}, {"_id": 0})
        if invoice:
            new_paid = float(invoice.get('amount_paid') or 0) + float(payload.amount)
            target = float(invoice.get('amount') or 0)
            if new_paid >= target - 0.005:
                new_status = InvoiceStatus.PAID.value
                paid_full_at = paid_at
            elif new_paid > 0:
                new_status = InvoiceStatus.PARTIAL.value
                paid_full_at = None
            else:
                new_status = invoice.get('status')
                paid_full_at = None
            await db.commercial_invoices.update_one({"id": payload.invoice_id}, {"$set": {
                "amount_paid": new_paid, "status": new_status, "paid_at": paid_full_at
            }})
            # If full paid → mark milestone payment_received
            if new_status == InvoiceStatus.PAID.value and invoice.get('milestone_id'):
                milestones = commercial.get('milestones', [])
                for m in milestones:
                    if m['id'] == invoice['milestone_id']:
                        m['status'] = MilestoneStatus.PAYMENT_RECEIVED.value
                await db.commercials.update_one({"id": commercial_id}, {"$set": {"milestones": milestones}})
            # If billing schedule → mark paid
            if new_status == InvoiceStatus.PAID.value and invoice.get('billing_schedule_id'):
                schedule = commercial.get('billing_schedule', [])
                for s in schedule:
                    if s['id'] == invoice['billing_schedule_id']:
                        s['status'] = 'paid'
                await db.commercials.update_one({"id": commercial_id}, {"$set": {"billing_schedule": schedule}})
            # Phase 36 — flip one_time_fee_status to 'paid' when its invoice is fully paid
            if new_status == InvoiceStatus.PAID.value and invoice.get('is_one_time_fee'):
                await db.commercials.update_one(
                    {"id": commercial_id},
                    {"$set": {"one_time_fee_status": "paid", "updated_at": _now_iso()}},
                )
    await _log_commercial_activity(commercial_id, current_user, "payment_received", f"Payment of {commercial.get('currency','INR')} {payload.amount} received", {"payment_id": payment_id})
    return {k: v for k, v in pdoc.items() if k != '_id'}

@router.get("/commercials/{commercial_id}/payments")
async def list_payments(commercial_id: str, current_user: dict = Depends(get_current_user)):
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=False)
    payments = await db.commercial_payments.find({"commercial_id": commercial_id}, {"_id": 0}).sort("paid_at", -1).to_list(500)
    return payments

@router.post("/commercials/{commercial_id}/documents")
async def upload_commercial_document(
    commercial_id: str,
    file: UploadFile = File(...),
    document_type: str = Form("other"),
    title: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=True)
    upload_dir = UPLOAD_DIR / 'commercials' / commercial_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', file.filename or 'upload')
    doc_id = str(uuid.uuid4())
    storage_path = upload_dir / f"{doc_id}_{safe_name}"
    async with aiofiles.open(storage_path, 'wb') as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            await out.write(chunk)
    size = storage_path.stat().st_size
    doc = {
        "id": doc_id,
        "commercial_id": commercial_id,
        "document_type": document_type,  # proposal | sow | contract | invoice | other
        "title": title or safe_name,
        "filename": safe_name,
        "storage_path": str(storage_path),
        "size": size,
        "content_type": file.content_type,
        "uploaded_by": current_user['id'],
        "uploaded_by_name": current_user.get('name'),
        "uploaded_at": _now_iso(),
    }
    await db.commercial_documents.insert_one(doc)
    await _log_commercial_activity(commercial_id, current_user, "document_uploaded", f"{document_type.title()} uploaded: {safe_name}", {"document_id": doc_id})
    return {k: v for k, v in doc.items() if k not in ('_id', 'storage_path')}

@router.get("/commercials/{commercial_id}/documents")
async def list_commercial_documents(commercial_id: str, current_user: dict = Depends(get_current_user)):
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=False)
    docs = await db.commercial_documents.find({"commercial_id": commercial_id}, {"_id": 0, "storage_path": 0}).sort("uploaded_at", -1).to_list(500)
    return docs

@router.get("/commercials/{commercial_id}/documents/{document_id}/download")
async def download_commercial_document(commercial_id: str, document_id: str, current_user: dict = Depends(get_current_user)):
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=False)
    doc = await db.commercial_documents.find_one({"id": document_id, "commercial_id": commercial_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return FileResponse(doc['storage_path'], filename=doc['filename'], media_type=doc.get('content_type') or 'application/octet-stream')

@router.delete("/commercials/{commercial_id}/documents/{document_id}")
async def delete_commercial_document(commercial_id: str, document_id: str, current_user: dict = Depends(get_current_user)):
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=True)
    doc = await db.commercial_documents.find_one({"id": document_id, "commercial_id": commercial_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        Path(doc['storage_path']).unlink(missing_ok=True)
    except Exception:
        pass
    await db.commercial_documents.delete_one({"id": document_id})
    await _log_commercial_activity(commercial_id, current_user, "document_deleted", f"Document deleted: {doc['filename']}")
    return {"deleted": True}

@router.get("/commercials/{commercial_id}/activity")
async def list_commercial_activity(commercial_id: str, current_user: dict = Depends(get_current_user)):
    commercial = await db.commercials.find_one({"id": commercial_id}, {"_id": 0})
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    await _ensure_commercial_access(commercial, current_user, write=False)
    events = await db.commercial_activity.find({"commercial_id": commercial_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return events

