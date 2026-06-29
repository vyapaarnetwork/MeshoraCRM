"""Internal Vyapaar Tasks router (Phase 36 — Jun 2026).

A standalone task-management module for the Vyapaar internal team. Distinct
from per-lead "Action Items" (which live under each lead). Use-cases:
  - Internal Vyapaar Operations (e.g. "Reconcile June commissions")
  - Partner-coordination work (e.g. "Onboard Selling Partner XYZ")
  - Sales-associate coordination ("Send updated rate-card to Aisha")

Creators: Vyapaar internal users only (super_admin, vyapaar_ops, vyapaar_finance).
Assignees: ANY active user role (partners, associates, customers can be assigned too).

Email notifications:
  - On assignment / re-assignment
  - When task becomes due (exact-time reminder loop, like lead Action Items)
  - Weekly Monday 09:00 IST digest of pending + due-this-week tasks

Imports infra (db, current_user, ZeptoMail helper) from server.py — same late-binding
pattern as routers/commercials.py.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone, timedelta, date
from enum import Enum
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

# Late-binding import — server.py registers this router AFTER all module-level
# names exist, then triggers the import.
from server import (
    db,
    get_current_user,
    UserRole,
    logger,
    create_notification,
)

router = APIRouter()

_MENTION_RE = re.compile(r'(?<!\w)@([a-zA-Z][a-zA-Z0-9_.\-]{1,40})')


def _parse_mentions(text: str) -> List[str]:
    """Extract @mention handles from a free-text description. Returns lowercased name fragments."""
    return [m.lower() for m in _MENTION_RE.findall(text or "")]


async def _notify_mentions(task: dict, content: str, author: dict, kind: str = "created", only_tokens: Optional[List[str]] = None):
    """Resolve @mentions in an internal-task description, fire an in-app
    notification + email to each matched active user (skips the author and the
    assignee — the assignee already gets a dedicated assignment email).

    If `only_tokens` is supplied, ONLY notify those handles (used by PATCH to
    avoid re-pinging already-mentioned teammates). The `content` is still used
    for the email/notification preview text.
    """
    tokens = [t.lower() for t in (only_tokens or _parse_mentions(content))]
    if not tokens:
        return
    seen: set = set()
    seen.add(author.get("id"))
    if task.get("assignee_id"):
        seen.add(task["assignee_id"])
    url_path = f"/internal-tasks/{task['id']}"
    full_url = f"https://app.vyapaar.net{url_path}"
    short = (content or "")[:160].replace("\n", " ").strip()
    for token in tokens:
        if not token:
            continue
        cursor = db.users.find({
            "is_active": {"$ne": False},
            "$or": [
                {"name": {"$regex": f"^{re.escape(token)}", "$options": "i"}},
                {"email": {"$regex": f"^{re.escape(token)}@", "$options": "i"}},
            ],
        }, {"_id": 0, "id": 1, "name": 1, "email": 1})
        async for u in cursor:
            uid = u.get("id")
            if not uid or uid in seen:
                continue
            seen.add(uid)
            try:
                await create_notification(
                    user_id=uid,
                    notification_type="internal_task_mention",
                    title=f'{author.get("name","Someone")} mentioned you in an internal task',
                    message=f'On "{task.get("title","")}": {short}',
                    data={
                        "internal_task_id": task["id"],
                        "url": url_path,
                        "cta_url": full_url,
                        "author_id": author.get("id"),
                        "author_name": author.get("name"),
                        "kind": kind,
                    },
                )
            except Exception as e:
                logger.warning("internal-task mention notify failed for %s: %s", uid, e)

# ============================================================================
# Models
# ============================================================================

VYAPAAR_INTERNAL_ROLES = {
    UserRole.SUPER_ADMIN.value,
    UserRole.VYAPAAR_OPS.value,
    UserRole.VYAPAAR_FINANCE.value,
}


class InternalTaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


class InternalTaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class InternalTaskCategory(str, Enum):
    """Lightweight grouping so the list page can be filtered. Free-form
    `tags` are also supported for additional structure."""
    OPERATIONS = "operations"
    PARTNER_COORDINATION = "partner_coordination"
    SALES_ASSOCIATE = "sales_associate"
    FINANCE = "finance"
    ONBOARDING = "onboarding"
    OTHER = "other"


class InternalTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=240)
    description: Optional[str] = Field(None, max_length=4000)
    assignee_id: Optional[str] = None        # any active user
    due_date: Optional[str] = None           # ISO date OR ISO datetime
    priority: InternalTaskPriority = InternalTaskPriority.MEDIUM
    category_id: Optional[str] = None         # FK → internal_task_categories.id
    category: Optional[InternalTaskCategory] = None  # legacy free-form (back-compat for API callers)
    related_partner_id: Optional[str] = None  # link to a selling-partner user/company
    related_lead_id: Optional[str] = None     # optional cross-link
    reminder_minutes_before: int = 0          # 0 = no email reminder
    tags: List[str] = []


class InternalTaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=240)
    description: Optional[str] = Field(None, max_length=4000)
    assignee_id: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[InternalTaskPriority] = None
    category_id: Optional[str] = None
    category: Optional[InternalTaskCategory] = None
    related_partner_id: Optional[str] = None
    related_lead_id: Optional[str] = None
    reminder_minutes_before: Optional[int] = None
    tags: Optional[List[str]] = None
    status: Optional[InternalTaskStatus] = None


# ============================================================================
# Helpers
# ============================================================================

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_internal(current_user: dict):
    role = current_user.get("original_role") or current_user.get("role")
    if role not in VYAPAAR_INTERNAL_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Internal Tasks are available only to Vyapaar internal users (Super Admin / Ops / Finance).",
        )


async def _enrich(task: dict) -> dict:
    """Add denormalised display fields (assignee / creator / partner / lead)."""
    if task.get("assignee_id"):
        u = await db.users.find_one({"id": task["assignee_id"]}, {"_id": 0, "name": 1, "email": 1, "role": 1})
        if u:
            task["assignee_name"] = u.get("name")
            task["assignee_email"] = u.get("email")
            task["assignee_role"] = u.get("role")
    if task.get("created_by"):
        u = await db.users.find_one({"id": task["created_by"]}, {"_id": 0, "name": 1})
        if u:
            task["created_by_name"] = u.get("name")
    if task.get("related_partner_id"):
        p = await db.users.find_one({"id": task["related_partner_id"]}, {"_id": 0, "name": 1, "company_name": 1})
        if p:
            task["related_partner_name"] = p.get("company_name") or p.get("name")
    if task.get("related_lead_id"):
        lead = await db.leads.find_one({"id": task["related_lead_id"]}, {"_id": 0, "title": 1, "customer_company": 1})
        if lead:
            task["related_lead_title"] = lead.get("title") or lead.get("customer_company")
    # Phase 36.2 — denormalise category master name + colour for the list UI
    if task.get("category_id"):
        cat = await db.internal_task_categories.find_one({"id": task["category_id"]}, {"_id": 0, "name": 1, "color": 1})
        if cat:
            task["category_name"] = cat.get("name")
            task["category_color"] = cat.get("color")
    return task


def _is_overdue(task: dict) -> bool:
    if task.get("status") in (InternalTaskStatus.DONE.value, InternalTaskStatus.CANCELLED.value):
        return False
    due = task.get("due_date")
    if not due:
        return False
    try:
        if "T" in due:
            return datetime.fromisoformat(due.replace("Z", "+00:00")) < datetime.now(timezone.utc)
        return date.fromisoformat(due) < datetime.now(timezone.utc).date()
    except Exception:
        return False


async def _send_assignment_email(task: dict, kind: str = "assigned"):
    """Fire an email to the assignee. Never raises."""
    if not task.get("assignee_id"):
        return
    try:
        from services import zeptomail as _zepto
        if not _zepto.is_configured():
            return
        u = await db.users.find_one({"id": task["assignee_id"]}, {"_id": 0, "name": 1, "email": 1})
        if not u or not u.get("email"):
            return
        creator = await db.users.find_one({"id": task.get("created_by")}, {"_id": 0, "name": 1})
        verb = {
            "assigned": "assigned a task to you",
            "reassigned": "reassigned a task to you",
            "due_reminder": "scheduled a reminder for your task",
        }.get(kind, "updated a task")
        due_label = task.get("due_date") or "no due date"
        url = f"https://app.vyapaar.net/internal-tasks/{task['id']}"
        body = (
            f'<p>Hi {u.get("name","there")},</p>'
            f'<p><strong>{(creator or {}).get("name","Someone")}</strong> {verb}:</p>'
            f'<div style="background:#f9fafb;border-left:4px solid #4f46e5;padding:14px 16px;margin:12px 0;border-radius:6px;">'
            f'<div style="font-size:16px;font-weight:600;">{task.get("title","")}</div>'
            f'<div style="color:#6b7280;font-size:13px;margin-top:4px;">'
            f'Priority: {task.get("priority","medium")} &middot; Due: {due_label}'
            f'</div>'
            f'</div>'
            f'{_zepto._btn("Open Task", url)}'  # noqa: SLF001 — reuse internal button helper
        )
        subject = {
            "assigned": f"[Meshora] New internal task: {task.get('title','')[:120]}",
            "reassigned": f"[Meshora] Task reassigned to you: {task.get('title','')[:120]}",
            "due_reminder": f"[Meshora] Reminder: {task.get('title','')[:120]} is due soon",
        }.get(kind, f"[Meshora] Task update: {task.get('title','')[:120]}")
        html = _zepto._wrap(subject, "Internal Task", body)  # noqa: SLF001
        await _zepto.send_email(
            to_address=u["email"], to_name=u.get("name"),
            subject=subject, html_body=html,
            db=db, notification_type=f"internal_task_{kind}", user_id=u.get("id"),
        )
    except Exception as e:
        logger.warning("internal-task email failed (%s): %s", kind, e)


# ============================================================================
# CRUD
# ============================================================================

@router.post("/internal-tasks")
async def create_internal_task(payload: InternalTaskCreate, current_user: dict = Depends(get_current_user)):
    _ensure_internal(current_user)
    if payload.assignee_id:
        a = await db.users.find_one({"id": payload.assignee_id}, {"_id": 0, "id": 1, "is_active": 1})
        if not a:
            raise HTTPException(status_code=400, detail="Assignee user not found")
        if a.get("is_active") is False:
            raise HTTPException(status_code=400, detail="Assignee user is inactive")
    # Phase 36.2 — resolve category from master collection (fallback to default)
    category_id = payload.category_id
    if not category_id:
        default_cat = await db.internal_task_categories.find_one({"is_default": True, "is_active": {"$ne": False}}, {"_id": 0, "id": 1})
        if not default_cat:
            default_cat = await db.internal_task_categories.find_one({"is_active": {"$ne": False}}, {"_id": 0, "id": 1}, sort=[("sort_order", 1)])
        category_id = (default_cat or {}).get("id")
    task = {
        "id": str(uuid.uuid4()),
        "title": payload.title.strip(),
        "description": (payload.description or "").strip() or None,
        "assignee_id": payload.assignee_id,
        "due_date": payload.due_date,
        "priority": payload.priority.value,
        "category_id": category_id,
        "category": payload.category.value if payload.category else None,  # back-compat
        "related_partner_id": payload.related_partner_id,
        "related_lead_id": payload.related_lead_id,
        "reminder_minutes_before": int(payload.reminder_minutes_before or 0),
        "tags": [t.strip() for t in (payload.tags or []) if t.strip()][:8],
        "status": InternalTaskStatus.TODO.value,
        "created_by": current_user["id"],
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "reminder_sent": False,
    }
    await db.internal_tasks.insert_one(task.copy())
    if task["assignee_id"] and task["assignee_id"] != current_user["id"]:
        await _send_assignment_email(task, kind="assigned")
    # Phase 36 — fire @mention notifications from the description
    if task.get("description"):
        await _notify_mentions(task, task["description"], current_user, kind="created")
    enriched = await _enrich({k: v for k, v in task.items() if k != "_id"})
    enriched["is_overdue"] = _is_overdue(enriched)
    return enriched


@router.get("/internal-tasks")
async def list_internal_tasks(
    status: Optional[str] = None,
    assignee_id: Optional[str] = None,
    category: Optional[str] = None,
    category_id: Optional[str] = None,
    priority: Optional[str] = None,
    mine: bool = False,
    q: Optional[str] = None,
    overdue_only: bool = False,
    current_user: dict = Depends(get_current_user),
):
    _ensure_internal(current_user)
    query: dict = {}
    if status:
        query["status"] = status
    if assignee_id:
        query["assignee_id"] = assignee_id
    if mine:
        query["$or"] = [{"assignee_id": current_user["id"]}, {"created_by": current_user["id"]}]
    if category:
        query["category"] = category
    if category_id:
        query["category_id"] = category_id
    if priority:
        query["priority"] = priority
    if q:
        query["title"] = {"$regex": q.strip()[:80], "$options": "i"}
    docs = await db.internal_tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    out = []
    today_str = datetime.now(timezone.utc).date().isoformat()
    for t in docs:
        await _enrich(t)
        t["is_overdue"] = _is_overdue(t)
        if overdue_only and not t["is_overdue"]:
            continue
        out.append(t)
    out.sort(key=lambda x: (
        x.get("status") in ("done", "cancelled"),    # active first
        not x.get("is_overdue"),                      # overdue first within active
        x.get("due_date") or "9999",                  # earliest due first
    ))
    # Headline counts for the UI
    counts = {
        "total": len(out),
        "todo": sum(1 for t in out if t.get("status") == "todo"),
        "in_progress": sum(1 for t in out if t.get("status") == "in_progress"),
        "blocked": sum(1 for t in out if t.get("status") == "blocked"),
        "done": sum(1 for t in out if t.get("status") == "done"),
        "overdue": sum(1 for t in out if t.get("is_overdue")),
        "due_today": sum(
            1 for t in out
            if t.get("due_date") and t["due_date"][:10] == today_str
            and t.get("status") not in ("done", "cancelled")
        ),
    }
    return {"items": out, "counts": counts}


@router.get("/internal-tasks/{task_id}")
async def get_internal_task(task_id: str, current_user: dict = Depends(get_current_user)):
    _ensure_internal(current_user)
    t = await db.internal_tasks.find_one({"id": task_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Internal task not found")
    await _enrich(t)
    t["is_overdue"] = _is_overdue(t)
    return t


@router.patch("/internal-tasks/{task_id}")
async def update_internal_task(task_id: str, payload: InternalTaskUpdate, current_user: dict = Depends(get_current_user)):
    _ensure_internal(current_user)
    existing = await db.internal_tasks.find_one({"id": task_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Internal task not found")
    updates = {k: (v.value if isinstance(v, Enum) else v) for k, v in payload.model_dump(exclude_unset=True).items()}
    # Validate new assignee
    if "assignee_id" in updates and updates["assignee_id"]:
        a = await db.users.find_one({"id": updates["assignee_id"]}, {"_id": 0, "id": 1, "is_active": 1})
        if not a:
            raise HTTPException(status_code=400, detail="Assignee user not found")
        if a.get("is_active") is False:
            raise HTTPException(status_code=400, detail="Assignee user is inactive")
    updates["updated_at"] = _now_iso()
    # Reset reminder_sent if due_date moved into the future
    if "due_date" in updates and updates["due_date"] != existing.get("due_date"):
        updates["reminder_sent"] = False
    # If status flipped to done, record completion timestamp
    if updates.get("status") == InternalTaskStatus.DONE.value and existing.get("status") != InternalTaskStatus.DONE.value:
        updates["completed_at"] = _now_iso()
        updates["completed_by"] = current_user["id"]
    await db.internal_tasks.update_one({"id": task_id}, {"$set": updates})
    fresh = await db.internal_tasks.find_one({"id": task_id}, {"_id": 0})
    # Notify if assignee changed to a different person
    if "assignee_id" in updates and updates["assignee_id"] and updates["assignee_id"] != existing.get("assignee_id"):
        await _send_assignment_email(fresh, kind="reassigned")
    # Phase 36 — fire @mention notifications only for NEW handles in the description
    if "description" in updates and (updates.get("description") or ""):
        prev_handles = set(_parse_mentions(existing.get("description") or ""))
        new_handles = set(_parse_mentions(updates["description"] or ""))
        newly_added = new_handles - prev_handles
        if newly_added:
            await _notify_mentions(
                fresh,
                updates["description"] or "",
                current_user,
                kind="updated",
                only_tokens=list(newly_added),
            )
    await _enrich(fresh)
    fresh["is_overdue"] = _is_overdue(fresh)
    return fresh


@router.delete("/internal-tasks/{task_id}")
async def delete_internal_task(task_id: str, current_user: dict = Depends(get_current_user)):
    _ensure_internal(current_user)
    existing = await db.internal_tasks.find_one({"id": task_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Internal task not found")
    # Only super_admin or the creator may delete
    role = current_user.get("original_role") or current_user.get("role")
    if role != UserRole.SUPER_ADMIN.value and existing.get("created_by") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Only the creator or a super admin can delete an internal task")
    await db.internal_tasks.delete_one({"id": task_id})
    return {"ok": True}


@router.get("/internal-tasks/_meta/assignable-users")
async def get_assignable_users(current_user: dict = Depends(get_current_user)):
    """Phase 36 — internal task assignee pool. Any active user can be assigned
    per the product requirement (Vyapaar internal can assign to partners /
    associates / customers / other ops users)."""
    _ensure_internal(current_user)
    users = await db.users.find(
        {"is_active": {"$ne": False}},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1, "company_name": 1},
    ).sort("name", 1).to_list(500)
    return users
