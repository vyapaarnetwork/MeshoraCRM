"""Internal-task category master (Phase 36.2)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from server import db, get_current_user, UserRole, logger  # noqa: F401

router = APIRouter()

VYAPAAR_INTERNAL = {UserRole.SUPER_ADMIN.value, UserRole.VYAPAAR_OPS.value, UserRole.VYAPAAR_FINANCE.value}

# Seed defaults — matched 1:1 to the previous hardcoded InternalTaskCategory enum.
_DEFAULT_SEED = [
    {"name": "Operations", "color": "#4f46e5", "is_default": True},
    {"name": "Partner coordination", "color": "#7c3aed"},
    {"name": "Sales associate", "color": "#06b6d4"},
    {"name": "Finance", "color": "#059669"},
    {"name": "Onboarding", "color": "#f59e0b"},
    {"name": "Other", "color": "#64748b"},
]


def _internal_only(user: dict):
    role = user.get("original_role") or user.get("role")
    if role not in VYAPAAR_INTERNAL:
        raise HTTPException(status_code=403, detail="Vyapaar internal only")


async def ensure_seed():
    count = await db.internal_task_categories.count_documents({})
    if count:
        return
    now = datetime.now(timezone.utc).isoformat()
    docs = [
        {
            "id": str(uuid.uuid4()),
            "name": c["name"],
            "color": c["color"],
            "is_active": True,
            "is_default": c.get("is_default", False),
            "sort_order": i,
            "created_at": now,
            "updated_at": now,
        }
        for i, c in enumerate(_DEFAULT_SEED)
    ]
    await db.internal_task_categories.insert_many(docs)
    logger.info("Seeded %d internal-task categories", len(docs))


class InternalTaskCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    color: Optional[str] = "#4f46e5"
    is_active: bool = True
    is_default: bool = False
    sort_order: int = 99


class InternalTaskCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    color: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    sort_order: Optional[int] = None


@router.get("/internal-task-categories")
async def list_categories(include_inactive: bool = False, current_user: dict = Depends(get_current_user)):
    _internal_only(current_user)
    await ensure_seed()
    q = {} if include_inactive else {"is_active": {"$ne": False}}
    items = await db.internal_task_categories.find(q, {"_id": 0}).sort([("sort_order", 1), ("name", 1)]).to_list(200)
    return items


@router.post("/internal-task-categories")
async def create_category(payload: InternalTaskCategoryCreate, current_user: dict = Depends(get_current_user)):
    _internal_only(current_user)
    if await db.internal_task_categories.find_one({"name": {"$regex": f"^{payload.name}$", "$options": "i"}}):
        raise HTTPException(status_code=400, detail="A category with this name already exists")
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name.strip(),
        "color": payload.color or "#4f46e5",
        "is_active": payload.is_active,
        "is_default": payload.is_default,
        "sort_order": payload.sort_order,
        "created_at": now,
        "updated_at": now,
    }
    if payload.is_default:
        await db.internal_task_categories.update_many({}, {"$set": {"is_default": False}})
    await db.internal_task_categories.insert_one(doc.copy())
    doc.pop("_id", None)
    return doc


@router.patch("/internal-task-categories/{cat_id}")
async def update_category(cat_id: str, payload: InternalTaskCategoryUpdate, current_user: dict = Depends(get_current_user)):
    _internal_only(current_user)
    existing = await db.internal_task_categories.find_one({"id": cat_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Category not found")
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if "name" in updates:
        clash = await db.internal_task_categories.find_one({
            "id": {"$ne": cat_id},
            "name": {"$regex": f"^{updates['name']}$", "$options": "i"},
        })
        if clash:
            raise HTTPException(status_code=400, detail="A category with this name already exists")
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    if updates.get("is_default"):
        await db.internal_task_categories.update_many({"id": {"$ne": cat_id}}, {"$set": {"is_default": False}})
    await db.internal_task_categories.update_one({"id": cat_id}, {"$set": updates})
    return await db.internal_task_categories.find_one({"id": cat_id}, {"_id": 0})


@router.delete("/internal-task-categories/{cat_id}")
async def delete_category(cat_id: str, current_user: dict = Depends(get_current_user)):
    _internal_only(current_user)
    existing = await db.internal_task_categories.find_one({"id": cat_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Category not found")
    # Soft-delete instead of hard delete so existing tasks keep their reference
    in_use = await db.internal_tasks.count_documents({"category_id": cat_id})
    if in_use > 0:
        await db.internal_task_categories.update_one({"id": cat_id}, {"$set": {"is_active": False}})
        return {"ok": True, "deactivated": True, "in_use": in_use}
    await db.internal_task_categories.delete_one({"id": cat_id})
    return {"ok": True, "deactivated": False}
