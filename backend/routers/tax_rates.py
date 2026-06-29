"""Tax-rate master (Phase 36.2). Configurable list of flat-% tax rates that
can be attached to a Commercial when the lead is closed. Composite GST is out
of scope for v1 — a single flat % per commercial is enough for the Vyapaar
team to capture the realised number on invoices.
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

_SEED = [
    {"name": "No tax", "percent": 0.0, "is_default": True, "is_inclusive": False},
    {"name": "GST 5%", "percent": 5.0, "is_inclusive": False},
    {"name": "GST 12%", "percent": 12.0, "is_inclusive": False},
    {"name": "GST 18%", "percent": 18.0, "is_inclusive": False},
    {"name": "GST 28%", "percent": 28.0, "is_inclusive": False},
]


def _internal_only(user: dict):
    role = user.get("original_role") or user.get("role")
    if role not in VYAPAAR_INTERNAL:
        raise HTTPException(status_code=403, detail="Vyapaar internal only")


async def ensure_seed():
    if await db.tax_rates.count_documents({}):
        return
    now = datetime.now(timezone.utc).isoformat()
    docs = []
    for i, c in enumerate(_SEED):
        docs.append({
            "id": str(uuid.uuid4()),
            "name": c["name"],
            "percent": c["percent"],
            "is_inclusive": c["is_inclusive"],
            "is_default": c.get("is_default", False),
            "is_active": True,
            "sort_order": i,
            "created_at": now,
            "updated_at": now,
        })
    await db.tax_rates.insert_many(docs)
    logger.info("Seeded %d tax rates", len(docs))


class TaxRateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    percent: float = Field(..., ge=0, le=100)
    is_inclusive: bool = False     # if true → amount already includes tax
    is_default: bool = False
    is_active: bool = True
    sort_order: int = 99


class TaxRateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    percent: Optional[float] = Field(None, ge=0, le=100)
    is_inclusive: Optional[bool] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


@router.get("/tax-rates")
async def list_rates(include_inactive: bool = False, current_user: dict = Depends(get_current_user)):
    # Visible to all logged-in users so the Lead/Commercial UI can render the dropdown
    # (write is internal-only).
    await ensure_seed()
    q = {} if include_inactive else {"is_active": {"$ne": False}}
    items = await db.tax_rates.find(q, {"_id": 0}).sort([("sort_order", 1), ("percent", 1)]).to_list(200)
    return items


@router.post("/tax-rates")
async def create_rate(payload: TaxRateCreate, current_user: dict = Depends(get_current_user)):
    _internal_only(current_user)
    if await db.tax_rates.find_one({"name": {"$regex": f"^{payload.name}$", "$options": "i"}}):
        raise HTTPException(status_code=400, detail="A tax rate with this name already exists")
    if payload.is_default:
        await db.tax_rates.update_many({}, {"$set": {"is_default": False}})
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name.strip(),
        "percent": payload.percent,
        "is_inclusive": payload.is_inclusive,
        "is_default": payload.is_default,
        "is_active": payload.is_active,
        "sort_order": payload.sort_order,
        "created_at": now,
        "updated_at": now,
    }
    await db.tax_rates.insert_one(doc.copy())
    doc.pop("_id", None)
    return doc


@router.patch("/tax-rates/{rate_id}")
async def update_rate(rate_id: str, payload: TaxRateUpdate, current_user: dict = Depends(get_current_user)):
    _internal_only(current_user)
    if not await db.tax_rates.find_one({"id": rate_id}):
        raise HTTPException(status_code=404, detail="Tax rate not found")
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if updates.get("is_default"):
        await db.tax_rates.update_many({"id": {"$ne": rate_id}}, {"$set": {"is_default": False}})
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.tax_rates.update_one({"id": rate_id}, {"$set": updates})
    return await db.tax_rates.find_one({"id": rate_id}, {"_id": 0})


@router.delete("/tax-rates/{rate_id}")
async def delete_rate(rate_id: str, current_user: dict = Depends(get_current_user)):
    _internal_only(current_user)
    if not await db.tax_rates.find_one({"id": rate_id}):
        raise HTTPException(status_code=404, detail="Tax rate not found")
    in_use_commercials = await db.commercials.count_documents({"tax_rate_id": rate_id})
    in_use_invoices = await db.commercial_invoices.count_documents({"tax_rate_id": rate_id})
    if in_use_commercials > 0 or in_use_invoices > 0:
        await db.tax_rates.update_one({"id": rate_id}, {"$set": {"is_active": False}})
        return {"ok": True, "deactivated": True, "commercials": in_use_commercials, "invoices": in_use_invoices}
    await db.tax_rates.delete_one({"id": rate_id})
    return {"ok": True, "deactivated": False}
