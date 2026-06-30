"""Routers — Lead Views (saved filter presets).

Phase 40.1 refactor — extracted verbatim from `server.py` (was lines 8634-8706).
Each user can save their own filter presets (statuses, healths, search, columns,
sort order). Exactly one preset per user can be marked `is_default`.

API surface is unchanged: GET/POST `/lead-views`, PATCH/DELETE `/lead-views/{id}`.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid

from server import db, get_current_user

router = APIRouter()


class LeadViewCreate(BaseModel):
    name: str
    filters: Dict[str, Any] = {}  # {statuses:[], healths:[], assigned_to_me, search, sort_by, sort_dir, columns:[]}
    is_default: bool = False


class LeadViewUpdate(BaseModel):
    name: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None


@router.get("/lead-views")
async def list_lead_views(current_user: dict = Depends(get_current_user)):
    rows = await db.lead_views.find({"user_id": current_user['id']}, {"_id": 0}).sort("name", 1).to_list(200)
    return rows


@router.post("/lead-views")
async def create_lead_view(body: LeadViewCreate, current_user: dict = Depends(get_current_user)):
    name = (body.name or '').strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if len(name) > 80:
        raise HTTPException(status_code=400, detail="Name too long (max 80)")
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": current_user['id'],
        "name": name,
        "filters": body.filters or {},
        "is_default": bool(body.is_default),
        "created_at": now,
        "updated_at": now,
    }
    # Only one default per user — un-default any other view if this one is being saved as default
    if doc['is_default']:
        await db.lead_views.update_many(
            {"user_id": current_user['id'], "is_default": True},
            {"$set": {"is_default": False}},
        )
    await db.lead_views.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.patch("/lead-views/{view_id}")
async def update_lead_view(view_id: str, body: LeadViewUpdate, current_user: dict = Depends(get_current_user)):
    view = await db.lead_views.find_one({"id": view_id, "user_id": current_user['id']}, {"_id": 0})
    if not view:
        raise HTTPException(status_code=404, detail="View not found")
    update: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if body.name is not None:
        n = body.name.strip()
        if not n:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        update["name"] = n[:80]
    if body.filters is not None:
        update["filters"] = body.filters
    if body.is_default is not None:
        update["is_default"] = bool(body.is_default)
        if body.is_default:
            await db.lead_views.update_many(
                {"user_id": current_user['id'], "is_default": True, "id": {"$ne": view_id}},
                {"$set": {"is_default": False}},
            )
    await db.lead_views.update_one({"id": view_id}, {"$set": update})
    return {**view, **update}


@router.delete("/lead-views/{view_id}")
async def delete_lead_view(view_id: str, current_user: dict = Depends(get_current_user)):
    res = await db.lead_views.delete_one({"id": view_id, "user_id": current_user['id']})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="View not found")
    return {"deleted": True}
