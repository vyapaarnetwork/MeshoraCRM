"""Routers — Collaborative Deal Rooms (Phase 27 + 27.5).

Extracted from server.py to keep the monolith manageable. Contains:
  - Per-lead Deal Room toggle, customer-facing view, public messages
  - Approvals (create / list / respond)
  - External magic-link invitations (create / list / revoke)
  - Public guest endpoints for the magic-link recipients (no auth required)

Late-binding imports from `server` are used so this module can safely depend
on shared infra (db, models, helpers) without circular import problems.
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

# Late-binding imports: resolved when server.py finishes executing.
from server import (
    db,
    get_current_user,
    UserRole,
    NotificationType,
    create_notification,
    logger,
    CommentCreate,
)

router = APIRouter()

# ==================== PHASE 27: COLLABORATIVE DEAL ROOMS ====================

VALID_APPROVAL_STATUS = {"pending", "approved", "rejected"}


class DealRoomToggle(BaseModel):
    enabled: bool


class ApprovalCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assignee_role: str = "customer"  # customer | selling_partner | admin
    due_date: Optional[str] = None


class ApprovalResponse(BaseModel):
    decision: str  # approved | rejected
    note: Optional[str] = None


def _can_access_deal_room(lead: dict, user: dict) -> bool:
    """Decide if the user can see the deal room for this lead.
    Admin/ops/finance: always. Selling partner: only if assigned. Customer: only if owner.
    """
    role = user.get('role')
    if role == UserRole.SUPER_ADMIN.value:
        return True
    if user.get('is_vyapaar_ops'):
        return True
    if role == UserRole.SELLING_PARTNER.value:
        partner_ids = {p.get('partner_id') for p in (lead.get('assigned_partners') or [])}
        return user['id'] in partner_ids or lead.get('selling_partner_id') == user['id']
    if role == UserRole.SALES_ASSOCIATE.value:
        return lead.get('sales_associate_id') == user['id']
    if role == UserRole.CUSTOMER.value:
        return lead.get('created_by') == user['id'] or lead.get('customer_email') == user.get('email')
    return False


@router.post("/leads/{lead_id}/deal-room/toggle")
async def toggle_deal_room(lead_id: str, body: DealRoomToggle, current_user: dict = Depends(get_current_user)):
    """Enable/disable the customer-facing Deal Room for a lead. Admin or assigned partner only."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    # Permission: only admin/ops or the assigned selling partner can toggle
    role = current_user.get('role')
    is_assigned_partner = (
        role == UserRole.SELLING_PARTNER.value
        and (current_user['id'] == lead.get('selling_partner_id')
             or any(p.get('partner_id') == current_user['id'] for p in (lead.get('assigned_partners') or [])))
    )
    if role != UserRole.SUPER_ADMIN.value and not current_user.get('is_vyapaar_ops') and not is_assigned_partner:
        raise HTTPException(status_code=403, detail="Not authorized to toggle deal room")

    now = datetime.now(timezone.utc).isoformat()
    update = {"deal_room_enabled": bool(body.enabled), "updated_at": now}
    if body.enabled and not lead.get('deal_room_opened_at'):
        update["deal_room_opened_at"] = now
        update["deal_room_opened_by"] = current_user['id']
        update["deal_room_opened_by_name"] = current_user['name']

    await db.leads.update_one({"id": lead_id}, {"$set": update})
    return {"ok": True, "enabled": bool(body.enabled), "opened_at": update.get("deal_room_opened_at") or lead.get('deal_room_opened_at')}


@router.get("/leads/{lead_id}/deal-room")
async def get_deal_room(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Return the curated customer-facing view of a lead.
    Customers see ONLY public comments + approvals + shared documents + status.
    Internal users see the full curated view + an `is_internal_viewer` flag.
    """
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.get('deal_room_enabled'):
        raise HTTPException(status_code=403, detail="Deal Room is not active for this lead")
    if not _can_access_deal_room(lead, current_user):
        raise HTTPException(status_code=403, detail="Not authorized for this Deal Room")

    is_customer = current_user.get('role') == UserRole.CUSTOMER.value

    # Public comments only (threaded preserved)
    public_comments = [c for c in (lead.get('comments') or []) if c.get('is_public')]

    # Status + stage info
    st = await db.lead_statuses.find_one({"id": lead.get('status_id')}, {"_id": 0}) if lead.get('status_id') else None
    status_name = (st or {}).get('name', 'Unstaged')

    # Approvals
    approvals = lead.get('approvals') or []
    # Customers only see approvals assigned to them or visible to all
    if is_customer:
        approvals = [a for a in approvals if a.get('assignee_role') in ('customer', 'all')]

    # Documents — show only the ones marked is_shared_in_deal_room=True (default True for backward compat)
    docs = [d for d in (lead.get('documents') or []) if d.get('is_shared_in_deal_room', True)]
    # Strip absolute file path from response
    safe_docs = [{
        "id": d.get('id'),
        "filename": d.get('filename'),
        "original_filename": d.get('original_filename'),
        "uploaded_at": d.get('uploaded_at'),
        "uploaded_by_name": d.get('uploaded_by_name'),
        "tag": d.get('tag'),
        "size_kb": d.get('size_kb'),
        "is_shared_in_deal_room": d.get('is_shared_in_deal_room', True),
    } for d in docs]

    # Active partners (names only — customers don't see internal user data)
    active_partners = [
        {"partner_name": p.get('partner_name'), "company_name": p.get('partner_company')}
        for p in (lead.get('assigned_partners') or [])
        if p.get('status') == 'active'
    ]

    # Commercial summary if exists
    commercial = await db.commercials.find_one({"lead_id": lead_id}, {"_id": 0})
    commercial_summary = None
    if commercial:
        commercial_summary = {
            "id": commercial.get('id'),
            "type": commercial.get('type'),
            "currency": commercial.get('currency', 'INR'),
            "project_value": commercial.get('project_value') or commercial.get('total_value'),
            "billing_cycle": commercial.get('billing_cycle'),
            "contract_start_date": commercial.get('contract_start_date'),
            "contract_end_date": commercial.get('contract_end_date'),
            "milestones_count": len(commercial.get('milestones') or []),
            "invoices_count": len(commercial.get('invoices') or []),
            "contract_status": commercial.get('contract_status'),
        }

    return {
        "lead": {
            "id": lead['id'],
            "title": lead.get('title'),
            "description": lead.get('description') if not is_customer else None,
            "customer_name": lead.get('customer_name'),
            "customer_company": lead.get('customer_company'),
            "primary_category_name": lead.get('primary_category_name'),
            "deal_value": lead.get('deal_value') if not is_customer else None,
            "status_name": status_name,
            "status_color": (st or {}).get('color', '#6366F1'),
            "created_at": lead.get('created_at'),
            "deal_room_enabled": True,
            "deal_room_opened_at": lead.get('deal_room_opened_at'),
        },
        "active_partners": active_partners,
        "public_comments": public_comments,
        "approvals": approvals,
        "documents": safe_docs,
        "commercial": commercial_summary,
        "is_internal_viewer": not is_customer,
        "viewer_role": current_user.get('role'),
    }


@router.post("/leads/{lead_id}/deal-room/messages")
async def post_deal_room_message(lead_id: str, body: CommentCreate, current_user: dict = Depends(get_current_user)):
    """Post a public message inside the Deal Room. Anyone with access (incl. customer) can post.
    This is just an alias for /comments that force-sets is_public=True."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.get('deal_room_enabled'):
        raise HTTPException(status_code=403, detail="Deal Room is not active for this lead")
    if not _can_access_deal_room(lead, current_user):
        raise HTTPException(status_code=403, detail="Not authorized for this Deal Room")

    comment = {
        "id": str(uuid.uuid4()),
        "content": (body.content or '').strip()[:5000],
        "user_id": current_user['id'],
        "user_name": current_user['name'],
        "user_role": current_user['role'],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parent_comment_id": body.parent_comment_id,
        "is_public": True,
    }
    if not comment['content']:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    await db.leads.update_one(
        {"id": lead_id},
        {"$push": {"comments": comment}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    # Notify everyone with deal-room access except the author
    recipients = set()
    if lead.get('created_by') and lead['created_by'] != current_user['id']:
        recipients.add(lead['created_by'])
    if lead.get('selling_partner_id') and lead['selling_partner_id'] != current_user['id']:
        recipients.add(lead['selling_partner_id'])
    for p in (lead.get('assigned_partners') or []):
        if p.get('status') == 'active' and p.get('partner_id') and p['partner_id'] != current_user['id']:
            recipients.add(p['partner_id'])
    for uid in recipients:
        try:
            await create_notification(
                user_id=uid,
                title=f"New Deal Room message · {lead.get('title','')}",
                message=f"{current_user['name']}: {comment['content'][:140]}",
                notification_type=NotificationType.LEAD_MENTION,
                lead_id=lead_id,
            )
        except Exception as e:
            logger.warning(f"Deal Room notification failed: {e}")

    return comment


@router.post("/leads/{lead_id}/approvals")
async def create_approval(lead_id: str, body: ApprovalCreate, current_user: dict = Depends(get_current_user)):
    """Create a Deal Room approval request. Admin / ops / assigned partner only."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    role = current_user.get('role')
    is_assigned_partner = (
        role == UserRole.SELLING_PARTNER.value
        and (current_user['id'] == lead.get('selling_partner_id')
             or any(p.get('partner_id') == current_user['id'] for p in (lead.get('assigned_partners') or [])))
    )
    if role != UserRole.SUPER_ADMIN.value and not current_user.get('is_vyapaar_ops') and not is_assigned_partner:
        raise HTTPException(status_code=403, detail="Not authorized")

    if body.assignee_role not in ('customer', 'selling_partner', 'admin', 'all'):
        raise HTTPException(status_code=400, detail="Invalid assignee_role")

    approval = {
        "id": str(uuid.uuid4()),
        "title": body.title.strip()[:200],
        "description": (body.description or '').strip()[:2000],
        "assignee_role": body.assignee_role,
        "due_date": body.due_date,
        "status": "pending",
        "created_by": current_user['id'],
        "created_by_name": current_user['name'],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "responded_at": None,
        "responded_by": None,
        "responded_by_name": None,
        "decision": None,
        "decision_note": None,
    }
    await db.leads.update_one(
        {"id": lead_id},
        {"$push": {"approvals": approval}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    # Notify the customer if this approval is for them
    if body.assignee_role in ('customer', 'all') and lead.get('created_by'):
        try:
            await create_notification(
                user_id=lead['created_by'],
                title=f"Approval requested · {lead.get('title','')}",
                message=f"{current_user['name']} requested your approval: {approval['title']}",
                notification_type=NotificationType.LEAD_MENTION,
                lead_id=lead_id,
            )
        except Exception as e:
            logger.warning(f"Approval notification failed: {e}")
    return approval


@router.get("/leads/{lead_id}/approvals")
async def list_approvals(lead_id: str, current_user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not _can_access_deal_room(lead, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")
    approvals = lead.get('approvals') or []
    if current_user.get('role') == UserRole.CUSTOMER.value:
        approvals = [a for a in approvals if a.get('assignee_role') in ('customer', 'all')]
    return approvals


@router.post("/leads/{lead_id}/approvals/{approval_id}/respond")
async def respond_to_approval(
    lead_id: str, approval_id: str, body: ApprovalResponse, current_user: dict = Depends(get_current_user)
):
    """Approve or reject an approval. Only the targeted assignee role can respond."""
    if body.decision not in ('approved', 'rejected'):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    approvals = lead.get('approvals') or []
    target = next((a for a in approvals if a.get('id') == approval_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Approval not found")
    if target.get('status') != 'pending':
        raise HTTPException(status_code=400, detail="Approval already responded to")

    # Permission: assignee role must match the user's role (or admin override)
    user_role = current_user.get('role')
    is_admin_like = user_role == UserRole.SUPER_ADMIN.value or current_user.get('is_vyapaar_ops')
    if target['assignee_role'] != 'all' and not is_admin_like:
        if target['assignee_role'] == 'customer' and user_role != UserRole.CUSTOMER.value:
            raise HTTPException(status_code=403, detail="This approval is for the customer to respond to")
        if target['assignee_role'] == 'selling_partner' and user_role != UserRole.SELLING_PARTNER.value:
            raise HTTPException(status_code=403, detail="This approval is for the selling partner")
        if target['assignee_role'] == 'admin' and not is_admin_like:
            raise HTTPException(status_code=403, detail="This approval is for admin")
    # Verify deal room access
    if not _can_access_deal_room(lead, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    target['status'] = body.decision
    target['decision'] = body.decision
    target['decision_note'] = (body.note or '').strip()[:1000]
    target['responded_at'] = datetime.now(timezone.utc).isoformat()
    target['responded_by'] = current_user['id']
    target['responded_by_name'] = current_user['name']

    await db.leads.update_one(
        {"id": lead_id, "approvals.id": approval_id},
        {"$set": {"approvals.$": target, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    # Notify the creator
    creator_id = target.get('created_by')
    if creator_id and creator_id != current_user['id']:
        try:
            await create_notification(
                user_id=creator_id,
                title=f"Approval {body.decision} · {target.get('title','')}",
                message=f"{current_user['name']} {body.decision} your request.",
                notification_type=NotificationType.LEAD_MENTION,
                lead_id=lead_id,
            )
        except Exception as e:
            logger.warning(f"Approval response notification failed: {e}")
    return target


# ==================== PHASE 27.5: DEAL ROOM MAGIC LINK INVITATIONS ====================

VALID_INVITE_PERMISSIONS = {"view", "comment", "approve"}


class DealRoomInviteCreate(BaseModel):
    email: EmailStr
    name: str
    permissions: List[str] = ["view", "comment"]  # subset of view/comment/approve
    expires_in_days: int = 14
    note: Optional[str] = None


class DealRoomGuestMessage(BaseModel):
    content: str


class DealRoomGuestApprovalResponse(BaseModel):
    decision: str  # approved | rejected
    note: Optional[str] = None


def _generate_invite_token() -> str:
    """Generate a URL-safe 32-byte random token."""
    import secrets
    return secrets.token_urlsafe(32)


async def _find_active_invite(token: str) -> Optional[dict]:
    """Fetch an invite by token. Returns None if missing / revoked / expired."""
    invite = await db.deal_room_invites.find_one({"token": token}, {"_id": 0})
    if not invite:
        return None
    if invite.get('revoked'):
        return None
    expires_at = invite.get('expires_at')
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            if exp_dt < datetime.now(timezone.utc):
                return None
        except Exception:
            pass
    return invite


@router.post("/leads/{lead_id}/deal-room/invites")
async def create_deal_room_invite(
    lead_id: str, body: DealRoomInviteCreate, current_user: dict = Depends(get_current_user)
):
    """Generate a magic-link invite for an external stakeholder. Admin/ops/assigned-partner only."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.get('deal_room_enabled'):
        raise HTTPException(status_code=400, detail="Open the Deal Room before sending invites")

    role = current_user.get('role')
    is_assigned_partner = (
        role == UserRole.SELLING_PARTNER.value
        and (current_user['id'] == lead.get('selling_partner_id')
             or any(p.get('partner_id') == current_user['id'] for p in (lead.get('assigned_partners') or [])))
    )
    if role != UserRole.SUPER_ADMIN.value and not current_user.get('is_vyapaar_ops') and not is_assigned_partner:
        raise HTTPException(status_code=403, detail="Not authorized")

    perms = [p for p in (body.permissions or []) if p in VALID_INVITE_PERMISSIONS]
    if not perms:
        perms = ["view", "comment"]

    expires_in = max(1, min(90, int(body.expires_in_days or 14)))
    token = _generate_invite_token()
    invite = {
        "id": str(uuid.uuid4()),
        "lead_id": lead_id,
        "email": body.email.lower(),
        "name": body.name.strip()[:100],
        "permissions": perms,
        "token": token,
        "note": (body.note or '').strip()[:300],
        "created_by": current_user['id'],
        "created_by_name": current_user['name'],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=expires_in)).isoformat(),
        "revoked": False,
        "last_used_at": None,
        "use_count": 0,
    }
    await db.deal_room_invites.insert_one(invite)

    # Build the magic link using the same external URL the frontend uses
    base_url = os.environ.get("FRONTEND_PUBLIC_URL") or os.environ.get("BACKEND_PUBLIC_URL") or ""
    magic_link = f"{base_url.rstrip('/')}/deal-room/{token}" if base_url else f"/deal-room/{token}"

    return {
        "id": invite['id'],
        "email": invite['email'],
        "name": invite['name'],
        "permissions": perms,
        "token": token,
        "magic_link": magic_link,
        "expires_at": invite['expires_at'],
        "use_count": 0,
    }


@router.get("/leads/{lead_id}/deal-room/invites")
async def list_deal_room_invites(lead_id: str, current_user: dict = Depends(get_current_user)):
    """List all invites for this lead. Admin/ops/partner only."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    role = current_user.get('role')
    is_assigned_partner = (
        role == UserRole.SELLING_PARTNER.value
        and (current_user['id'] == lead.get('selling_partner_id')
             or any(p.get('partner_id') == current_user['id'] for p in (lead.get('assigned_partners') or [])))
    )
    if role != UserRole.SUPER_ADMIN.value and not current_user.get('is_vyapaar_ops') and not is_assigned_partner:
        raise HTTPException(status_code=403, detail="Not authorized")
    invites = await db.deal_room_invites.find({"lead_id": lead_id}, {"_id": 0, "token": 0}).sort("created_at", -1).to_list(50)
    # Don't return raw tokens in list view; only return after creation
    return invites


@router.delete("/leads/{lead_id}/deal-room/invites/{invite_id}")
async def revoke_deal_room_invite(lead_id: str, invite_id: str, current_user: dict = Depends(get_current_user)):
    """Revoke an invite. Admin/ops/partner only."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    role = current_user.get('role')
    is_assigned_partner = (
        role == UserRole.SELLING_PARTNER.value
        and (current_user['id'] == lead.get('selling_partner_id')
             or any(p.get('partner_id') == current_user['id'] for p in (lead.get('assigned_partners') or [])))
    )
    if role != UserRole.SUPER_ADMIN.value and not current_user.get('is_vyapaar_ops') and not is_assigned_partner:
        raise HTTPException(status_code=403, detail="Not authorized")
    res = await db.deal_room_invites.update_one(
        {"id": invite_id, "lead_id": lead_id},
        {"$set": {"revoked": True, "revoked_at": datetime.now(timezone.utc).isoformat()}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invite not found")
    return {"revoked": True}


# ----- PUBLIC magic-link endpoints (no auth required) -----

async def _resolve_invite_or_404(token: str) -> tuple:
    invite = await _find_active_invite(token)
    if not invite:
        raise HTTPException(status_code=403, detail="Invite is invalid, expired, or revoked")
    lead = await db.leads.find_one({"id": invite['lead_id']}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.get('deal_room_enabled'):
        raise HTTPException(status_code=403, detail="Deal Room is no longer active for this lead")
    return invite, lead


@router.get("/deal-room/access/{token}")
async def guest_view_deal_room(token: str):
    """Public endpoint — guest views the Deal Room via magic link. No auth required."""
    invite, lead = await _resolve_invite_or_404(token)

    # Bump usage tracker (fire-and-forget)
    try:
        await db.deal_room_invites.update_one(
            {"id": invite['id']},
            {"$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}, "$inc": {"use_count": 1}}
        )
    except Exception:
        pass

    st = await db.lead_statuses.find_one({"id": lead.get('status_id')}, {"_id": 0}) if lead.get('status_id') else None
    public_comments = [c for c in (lead.get('comments') or []) if c.get('is_public')]
    # Guest sees approvals targeted at customer or all (same as customer view)
    approvals = [a for a in (lead.get('approvals') or []) if a.get('assignee_role') in ('customer', 'all')]
    docs = [d for d in (lead.get('documents') or []) if d.get('is_shared_in_deal_room', True)]
    safe_docs = [{
        "id": d.get('id'), "filename": d.get('filename'), "original_filename": d.get('original_filename'),
        "uploaded_at": d.get('uploaded_at'), "uploaded_by_name": d.get('uploaded_by_name'),
        "tag": d.get('tag'), "size_kb": d.get('size_kb'),
    } for d in docs]
    active_partners = [
        {"partner_name": p.get('partner_name'), "company_name": p.get('partner_company')}
        for p in (lead.get('assigned_partners') or []) if p.get('status') == 'active'
    ]

    return {
        "invite": {
            "name": invite['name'],
            "email": invite['email'],
            "permissions": invite['permissions'],
            "expires_at": invite['expires_at'],
            "invited_by_name": invite.get('created_by_name'),
        },
        "lead": {
            "id": lead['id'],
            "title": lead.get('title'),
            "customer_name": lead.get('customer_name'),
            "customer_company": lead.get('customer_company'),
            "primary_category_name": lead.get('primary_category_name'),
            "status_name": (st or {}).get('name', 'Unstaged'),
            "status_color": (st or {}).get('color', '#6366F1'),
        },
        "active_partners": active_partners,
        "public_comments": public_comments,
        "approvals": approvals,
        "documents": safe_docs,
    }


@router.post("/deal-room/access/{token}/messages")
async def guest_post_message(token: str, body: DealRoomGuestMessage):
    """Guest posts a public message via magic link. Requires `comment` permission."""
    invite, lead = await _resolve_invite_or_404(token)
    if 'comment' not in (invite.get('permissions') or []):
        raise HTTPException(status_code=403, detail="This invite does not allow posting messages")
    content = (body.content or '').strip()[:5000]
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    comment = {
        "id": str(uuid.uuid4()),
        "content": content,
        "user_id": f"guest:{invite['id']}",
        "user_name": f"{invite['name']} (Guest)",
        "user_role": "guest",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parent_comment_id": None,
        "is_public": True,
        "guest_invite_id": invite['id'],
    }
    await db.leads.update_one(
        {"id": lead['id']},
        {"$push": {"comments": comment}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    # Notify lead participants
    recipients = set()
    if lead.get('created_by'):
        recipients.add(lead['created_by'])
    if lead.get('selling_partner_id'):
        recipients.add(lead['selling_partner_id'])
    for p in (lead.get('assigned_partners') or []):
        if p.get('status') == 'active' and p.get('partner_id'):
            recipients.add(p['partner_id'])
    for uid in recipients:
        try:
            await create_notification(
                user_id=uid,
                title=f"Guest message · {lead.get('title','')}",
                message=f"{invite['name']} (guest): {content[:140]}",
                notification_type=NotificationType.LEAD_MENTION,
                lead_id=lead['id'],
            )
        except Exception as e:
            logger.warning(f"Guest msg notification failed: {e}")
    # Bump invite usage
    try:
        await db.deal_room_invites.update_one(
            {"id": invite['id']},
            {"$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}, "$inc": {"use_count": 1}}
        )
    except Exception:
        pass
    return comment


@router.post("/deal-room/access/{token}/approvals/{approval_id}/respond")
async def guest_respond_to_approval(
    token: str, approval_id: str, body: DealRoomGuestApprovalResponse
):
    """Guest responds to an approval via magic link. Requires `approve` permission."""
    if body.decision not in ('approved', 'rejected'):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")
    invite, lead = await _resolve_invite_or_404(token)
    if 'approve' not in (invite.get('permissions') or []):
        raise HTTPException(status_code=403, detail="This invite does not allow responding to approvals")
    approvals = lead.get('approvals') or []
    target = next((a for a in approvals if a.get('id') == approval_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Approval not found")
    if target.get('status') != 'pending':
        raise HTTPException(status_code=400, detail="Approval already responded to")
    if target.get('assignee_role') not in ('customer', 'all'):
        raise HTTPException(status_code=403, detail="This approval is not for external stakeholders")

    target['status'] = body.decision
    target['decision'] = body.decision
    target['decision_note'] = (body.note or '').strip()[:1000]
    target['responded_at'] = datetime.now(timezone.utc).isoformat()
    target['responded_by'] = f"guest:{invite['id']}"
    target['responded_by_name'] = f"{invite['name']} (Guest)"
    await db.leads.update_one(
        {"id": lead['id'], "approvals.id": approval_id},
        {"$set": {"approvals.$": target, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    creator_id = target.get('created_by')
    if creator_id:
        try:
            await create_notification(
                user_id=creator_id,
                title=f"Approval {body.decision} by guest · {target.get('title','')}",
                message=f"{invite['name']} (guest) {body.decision} your request.",
                notification_type=NotificationType.LEAD_MENTION,
                lead_id=lead['id'],
            )
        except Exception as e:
            logger.warning(f"Guest approval notif failed: {e}")
    try:
        await db.deal_room_invites.update_one(
            {"id": invite['id']},
            {"$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}, "$inc": {"use_count": 1}}
        )
    except Exception:
        pass
    return target
