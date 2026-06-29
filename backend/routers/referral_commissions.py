"""Referral Commission Levels master (Phase 36.3).

Models the 5-tier referral commission scheme: Lead Scout / Opportunity Builder
/ Deal Enabler / Growth Catalyst / Strategic Partner — corresponding to
10 / 20 / 30 / 40 / 50%. The percent is applied at the *lead* level (set when
creating/editing the lead) and represents what Vyapaar pays back to the
referrer (sales associate / selling partner) on closure.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from server import db, get_current_user, UserRole, logger  # noqa: F401

router = APIRouter()
VYAPAAR_INTERNAL = {UserRole.SUPER_ADMIN.value, UserRole.VYAPAAR_OPS.value, UserRole.VYAPAAR_FINANCE.value}

# Spec from product:
#   Commission | Level                 | Meaning
#   10%        | Lead Scout            | Identified or referred a potential opportunity
#   20%        | Opportunity Builder   | Qualified and nurtured the opportunity
#   30%        | Deal Enabler          | Actively drove discussions and engagement
#   40%        | Growth Catalyst       | Played a major role in winning the business
#   50%        | Strategic Partner     | Owned the opportunity from introduction to closure
_SEED = [
    {"name": "Lead Scout",          "percent": 10.0, "meaning": "Identified or referred a potential opportunity",       "is_default": True,  "sort_order": 1},
    {"name": "Opportunity Builder", "percent": 20.0, "meaning": "Qualified and nurtured the opportunity",                "sort_order": 2},
    {"name": "Deal Enabler",        "percent": 30.0, "meaning": "Actively drove discussions and engagement",             "sort_order": 3},
    {"name": "Growth Catalyst",     "percent": 40.0, "meaning": "Played a major role in winning the business",           "sort_order": 4},
    {"name": "Strategic Partner",   "percent": 50.0, "meaning": "Owned the opportunity from introduction to closure",    "sort_order": 5},
]


def _internal_only(user: dict):
    role = user.get("original_role") or user.get("role")
    if role not in VYAPAAR_INTERNAL:
        raise HTTPException(status_code=403, detail="Vyapaar internal only")


async def ensure_seed():
    if await db.referral_commissions.count_documents({}):
        return
    now = datetime.now(timezone.utc).isoformat()
    docs = [
        {
            "id": str(uuid.uuid4()),
            "name": s["name"],
            "percent": s["percent"],
            "meaning": s["meaning"],
            "is_active": True,
            "is_default": s.get("is_default", False),
            "sort_order": s["sort_order"],
            "created_at": now,
            "updated_at": now,
        }
        for s in _SEED
    ]
    await db.referral_commissions.insert_many(docs)
    logger.info("Seeded %d referral commission levels", len(docs))


class ReferralCommissionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    percent: float = Field(..., ge=0, le=100)
    meaning: Optional[str] = Field(None, max_length=400)
    is_active: bool = True
    is_default: bool = False
    sort_order: int = 99


class ReferralCommissionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    percent: Optional[float] = Field(None, ge=0, le=100)
    meaning: Optional[str] = Field(None, max_length=400)
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    sort_order: Optional[int] = None


@router.get("/referral-commissions")
async def list_referral_commissions(include_inactive: bool = False, current_user: dict = Depends(get_current_user)):
    # Read open to all logged-in users (so the Lead form dropdown works for any role)
    await ensure_seed()
    q = {} if include_inactive else {"is_active": {"$ne": False}}
    items = await db.referral_commissions.find(q, {"_id": 0}).sort([("sort_order", 1), ("percent", 1)]).to_list(50)
    return items


@router.post("/referral-commissions")
async def create_referral_commission(payload: ReferralCommissionCreate, current_user: dict = Depends(get_current_user)):
    _internal_only(current_user)
    if await db.referral_commissions.find_one({"name": {"$regex": f"^{payload.name}$", "$options": "i"}}):
        raise HTTPException(status_code=400, detail="A level with this name already exists")
    if payload.is_default:
        await db.referral_commissions.update_many({}, {"$set": {"is_default": False}})
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name.strip(),
        "percent": payload.percent,
        "meaning": (payload.meaning or "").strip() or None,
        "is_active": payload.is_active,
        "is_default": payload.is_default,
        "sort_order": payload.sort_order,
        "created_at": now,
        "updated_at": now,
    }
    await db.referral_commissions.insert_one(doc.copy())
    doc.pop("_id", None)
    return doc


@router.patch("/referral-commissions/{rc_id}")
async def update_referral_commission(rc_id: str, payload: ReferralCommissionUpdate, current_user: dict = Depends(get_current_user)):
    _internal_only(current_user)
    if not await db.referral_commissions.find_one({"id": rc_id}):
        raise HTTPException(status_code=404, detail="Level not found")
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if updates.get("is_default"):
        await db.referral_commissions.update_many({"id": {"$ne": rc_id}}, {"$set": {"is_default": False}})
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.referral_commissions.update_one({"id": rc_id}, {"$set": updates})
    return await db.referral_commissions.find_one({"id": rc_id}, {"_id": 0})


@router.delete("/referral-commissions/{rc_id}")
async def delete_referral_commission(rc_id: str, current_user: dict = Depends(get_current_user)):
    _internal_only(current_user)
    if not await db.referral_commissions.find_one({"id": rc_id}):
        raise HTTPException(status_code=404, detail="Level not found")
    in_use = await db.leads.count_documents({"referral_commission_id": rc_id})
    if in_use > 0:
        await db.referral_commissions.update_one({"id": rc_id}, {"$set": {"is_active": False}})
        return {"ok": True, "deactivated": True, "in_use": in_use}
    await db.referral_commissions.delete_one({"id": rc_id})
    return {"ok": True, "deactivated": False}
