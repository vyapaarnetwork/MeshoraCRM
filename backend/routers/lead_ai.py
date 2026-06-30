"""Routers — Lead AI (Phase 40.1 refactor).

Extracted verbatim from `server.py`. Contains all 5 AI endpoints that operate
on a lead:

  POST   /leads/{lead_id}/ai/meeting-summary    — convert raw meeting notes
  GET    /leads/{lead_id}/ai/meeting-summaries  — list past summaries
  POST   /leads/{lead_id}/ai/risk-analysis      — deal risk score + factors
  POST   /leads/{lead_id}/ai/follow-up-suggestion — recommended next move
  POST   /leads/{lead_id}/ai/suggest-actions    — extract tasks + follow-ups
                                                  from a discussion comment

Shared LLM context-builder (`_build_lead_ai_context`) and chat helper
(`_ai_lead_chat`) are imported from server to avoid duplication. The API
surface is identical to the pre-refactor code.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import json
import re
import uuid

from server import (
    db,
    get_current_user,
    logger,
    EMERGENT_LLM_KEY,
    _build_lead_ai_context,
    _ai_lead_chat,
)


def _safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


router = APIRouter()


class MeetingSummaryRequest(BaseModel):
    raw_notes: str
    meeting_date: Optional[str] = None  # ISO date
    auto_create_tasks: bool = True


class AISuggestActionsRequest(BaseModel):
    text: str


# ============================ Meeting summary ============================

@router.post("/leads/{lead_id}/ai/meeting-summary")
async def ai_meeting_summary(
    lead_id: str,
    body: MeetingSummaryRequest,
    current_user: dict = Depends(get_current_user),
):
    """Convert raw meeting notes / call transcript into structured intelligence using Gemini 3 Pro.
    Stores the summary as a special-typed comment on the lead, posts a structured 'meeting_summary'
    activity event, and optionally creates Tasks from extracted action items.
    """
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=503, detail="LLM key not configured")

    if not (body.raw_notes or '').strip():
        raise HTTPException(status_code=400, detail="raw_notes is required")
    if len(body.raw_notes) > 25000:
        raise HTTPException(status_code=400, detail="raw_notes too long (max 25000 chars)")

    from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: WPS433

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"meeting-summary-{lead_id}-{uuid.uuid4()}",
        system_message=(
            "You are a sales/CRM intelligence analyst. Given raw meeting notes, call transcripts, "
            "or voice transcripts, extract structured intelligence. ALWAYS respond with STRICT JSON. "
            "No prose, no markdown, no code fences. The JSON object MUST have these keys:\n"
            "- summary (string, 2-3 sentences)\n"
            "- risks (array of short strings — concerns, blockers, friction)\n"
            "- opportunities (array of short strings — upsells, expansion, new use cases)\n"
            "- next_steps (array of short strings — recommended actions for the team)\n"
            "- action_items (array of {title, owner_hint?, priority? in [low|medium|high], due_in_days?})\n"
            "- sentiment (string: positive | neutral | negative | mixed)\n"
            "- key_stakeholders (array of {name, role_hint?})\n\n"
            "Keep arrays concise (max 5 items each). Be specific and actionable. "
            "If the notes are too short or unclear, return empty arrays but still produce a summary."
        )
    ).with_model("gemini", "gemini-3.1-pro-preview")

    prompt = (
        f"Lead: {lead.get('title', '')}\n"
        f"Customer: {lead.get('customer_name', '')} ({lead.get('customer_company', '')})\n"
        f"Meeting date: {body.meeting_date or 'unknown'}\n\n"
        f"Raw notes / transcript:\n{body.raw_notes.strip()}\n\n"
        "Output STRICT JSON only."
    )

    try:
        response = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        logger.exception(f"LLM error during meeting summary: {e}")
        raise HTTPException(status_code=502, detail=f"AI request failed: {str(e)[:120]}")

    raw = (response or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except Exception:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if not m:
            raise HTTPException(status_code=502, detail="AI returned non-JSON output")
        try:
            parsed = json.loads(m.group(0))
        except Exception:
            raise HTTPException(status_code=502, detail="AI returned malformed JSON")

    # Normalize structure
    summary_text = (parsed.get('summary') or '').strip()
    risks = [str(x).strip() for x in (parsed.get('risks') or []) if str(x).strip()][:5]
    opportunities = [str(x).strip() for x in (parsed.get('opportunities') or []) if str(x).strip()][:5]
    next_steps = [str(x).strip() for x in (parsed.get('next_steps') or []) if str(x).strip()][:5]
    action_items = [a for a in (parsed.get('action_items') or []) if isinstance(a, dict) and a.get('title')][:5]
    sentiment = (parsed.get('sentiment') or 'neutral').lower()
    if sentiment not in ('positive', 'neutral', 'negative', 'mixed'):
        sentiment = 'neutral'
    stakeholders = [s for s in (parsed.get('key_stakeholders') or []) if isinstance(s, dict) and s.get('name')][:8]

    summary_doc = {
        "summary": summary_text,
        "risks": risks,
        "opportunities": opportunities,
        "next_steps": next_steps,
        "action_items": action_items,
        "sentiment": sentiment,
        "key_stakeholders": stakeholders,
        "raw_notes_preview": body.raw_notes[:280],
        "meeting_date": body.meeting_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user['id'],
        "created_by_name": current_user['name'],
    }

    # Persist as a structured comment so it shows in the timeline
    comment_payload = (
        f"📝 Meeting Summary ({body.meeting_date or 'no date'})\n\n"
        f"{summary_text}\n\n"
        + ("⚠️ Risks: " + " · ".join(risks) + "\n" if risks else '')
        + ("💡 Opportunities: " + " · ".join(opportunities) + "\n" if opportunities else '')
        + ("➡️ Next steps: " + " · ".join(next_steps) + "\n" if next_steps else '')
    )
    comment = {
        "id": str(uuid.uuid4()),
        "content": comment_payload.strip(),
        "user_id": current_user['id'],
        "user_name": current_user['name'],
        "user_role": current_user['role'],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parent_comment_id": None,
        "meeting_summary": summary_doc,
    }

    await db.leads.update_one(
        {"id": lead_id},
        {
            "$push": {"comments": comment, "meeting_summaries": summary_doc},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
        }
    )

    # Optionally create Tasks from action items
    created_task_ids = []
    if body.auto_create_tasks and action_items:
        today = datetime.now(timezone.utc).date()
        for ai_item in action_items:
            due = None
            try:
                offset = int(ai_item.get('due_in_days') or 0)
                if offset > 0:
                    due = (today + timedelta(days=offset)).isoformat()
            except Exception:
                due = None
            priority = (ai_item.get('priority') or 'medium').lower()
            if priority not in ('low', 'medium', 'high'):
                priority = 'medium'
            task = {
                "id": str(uuid.uuid4()),
                "title": str(ai_item.get('title', '')).strip()[:200] or 'AI action item',
                "description": f"From meeting on {body.meeting_date or 'unspecified date'}. Owner hint: {ai_item.get('owner_hint') or '—'}",
                "assignee_id": current_user['id'],
                "lead_id": lead_id,
                "commercial_id": None,
                "due_date": due,
                "priority": priority,
                "status": "todo",
                "created_by": current_user['id'],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
                "source": "ai_meeting_summary",
            }
            await db.tasks.insert_one(task)
            created_task_ids.append(task['id'])

    return {
        "summary": summary_doc,
        "comment_id": comment['id'],
        "created_task_ids": created_task_ids,
    }


@router.get("/leads/{lead_id}/ai/meeting-summaries")
async def list_meeting_summaries(lead_id: str, current_user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"summaries": (lead.get('meeting_summaries') or [])[::-1]}


# ============================ Risk analysis ============================

@router.post("/leads/{lead_id}/ai/risk-analysis")
async def ai_deal_risk(lead_id: str, current_user: dict = Depends(get_current_user)):
    """AI-driven deal risk analysis. Considers inactivity, sentiment from meeting summaries,
    stakeholder gaps, follow-up health, and deal-value tier to compute a risk score + factors
    + mitigations. Stored on the lead under `ai_risk_analysis`."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(200)
    status_map = {s['id']: s for s in statuses}

    context = _build_lead_ai_context(lead, status_map)
    system_msg = (
        "You are a senior B2B sales risk analyst. Analyze the provided lead context and return STRICT JSON only. "
        "No prose, no markdown, no code fences. Schema:\n"
        "{\n"
        '  "risk_score": 0-100 integer (higher = more risk),\n'
        '  "risk_level": one of [low, medium, high, critical],\n'
        '  "closure_probability": 0-100 integer (likelihood deal closes won),\n'
        '  "top_risk_factors": array of {factor: string, severity: low|medium|high, evidence: string},\n'
        '  "stakeholder_gaps": array of strings (e.g. "No champion identified", "Finance approver missing"),\n'
        '  "recommended_mitigations": array of strings (1-line specific actions),\n'
        '  "early_warning_signals": array of strings,\n'
        '  "confidence": 0-100 integer (how confident is the model given available data)\n'
        "}\n"
        "Be specific. Use the actual lead details, NOT generic advice. Penalize stakeholder gaps and inactivity hard. "
        "If meeting sentiment was negative, raise risk. If a champion is supportive, lower risk."
    )
    parsed = await _ai_lead_chat(lead_id, system_msg, f"Lead context:\n{context}\n\nReturn STRICT JSON only.")

    # Normalize and store
    result = {
        "risk_score": int(parsed.get('risk_score') or 50),
        "risk_level": (parsed.get('risk_level') or 'medium').lower(),
        "closure_probability": int(parsed.get('closure_probability') or 30),
        "top_risk_factors": (parsed.get('top_risk_factors') or [])[:6],
        "stakeholder_gaps": [str(x) for x in (parsed.get('stakeholder_gaps') or [])][:6],
        "recommended_mitigations": [str(x) for x in (parsed.get('recommended_mitigations') or [])][:6],
        "early_warning_signals": [str(x) for x in (parsed.get('early_warning_signals') or [])][:6],
        "confidence": int(parsed.get('confidence') or 60),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": current_user['name'],
    }
    if result['risk_level'] not in ('low', 'medium', 'high', 'critical'):
        result['risk_level'] = 'medium'
    for v in ('risk_score', 'closure_probability', 'confidence'):
        result[v] = max(0, min(100, result[v]))

    await db.leads.update_one({"id": lead_id}, {"$set": {"ai_risk_analysis": result, "updated_at": datetime.now(timezone.utc).isoformat()}})
    return result


# ============================ Follow-up suggestion ============================

@router.post("/leads/{lead_id}/ai/follow-up-suggestion")
async def ai_followup_suggestion(lead_id: str, current_user: dict = Depends(get_current_user)):
    """AI Follow-up Assistant. Returns the recommended next action, optimal timing,
    a ready-to-send conversation starter, and (if applicable) a proposal recommendation."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(200)
    status_map = {s['id']: s for s in statuses}

    context = _build_lead_ai_context(lead, status_map)
    system_msg = (
        "You are a senior B2B sales playbook strategist. Given the lead context, recommend the single best next move. "
        "Return STRICT JSON only. Schema:\n"
        "{\n"
        '  "recommended_action": string (clear, specific verb-led next step),\n'
        '  "rationale": string (1-2 sentences explaining WHY based on the lead context),\n'
        '  "suggested_timing": {when: string e.g. "tomorrow morning"|"next Monday", reason: string},\n'
        '  "channel": one of [email, call, whatsapp, meeting, slack],\n'
        '  "conversation_starter": string (a ready-to-send opening line, 2-3 sentences, professional but warm),\n'
        '  "proposal_recommendation": optional string (only if proposal stage),\n'
        '  "stakeholders_to_loop_in": array of strings (names from the stakeholder list),\n'
        '  "questions_to_ask": array of 2-3 questions to learn more,\n'
        '  "confidence": 0-100 integer\n'
        "}\n"
        "Be specific. If you see meeting summaries, reference what was discussed. "
        "If a stakeholder is resistant, propose how to handle them. If a champion exists, leverage them. "
        "Do NOT use placeholder names like [Customer Name]; use the actual names from the context."
    )
    parsed = await _ai_lead_chat(lead_id, system_msg, f"Lead context:\n{context}\n\nReturn STRICT JSON only.")

    result = {
        "recommended_action": str(parsed.get('recommended_action') or '').strip()[:300],
        "rationale": str(parsed.get('rationale') or '').strip()[:600],
        "suggested_timing": parsed.get('suggested_timing') or {"when": "today", "reason": ""},
        "channel": (parsed.get('channel') or 'email').lower(),
        "conversation_starter": str(parsed.get('conversation_starter') or '').strip()[:1500],
        "proposal_recommendation": str(parsed.get('proposal_recommendation') or '').strip()[:500] or None,
        "stakeholders_to_loop_in": [str(x) for x in (parsed.get('stakeholders_to_loop_in') or [])][:5],
        "questions_to_ask": [str(x) for x in (parsed.get('questions_to_ask') or [])][:5],
        "confidence": max(0, min(100, int(parsed.get('confidence') or 70))),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": current_user['name'],
    }
    if result['channel'] not in ('email', 'call', 'whatsapp', 'meeting', 'slack'):
        result['channel'] = 'email'
    return result


# ============================ Suggest actions (from comment) ============================

@router.post("/leads/{lead_id}/ai/suggest-actions")
async def ai_suggest_actions(lead_id: str, body: AISuggestActionsRequest, current_user: dict = Depends(get_current_user)):
    """Phase 35 — analyze a discussion comment and extract one-click Action Item /
    Customer Follow-Up suggestions. Returns {"tasks": [...], "follow_ups": [...]}
    with normalized due dates so the UI can create them in one click."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    text = (body.text or '').strip()
    if len(text) < 5:
        return {"tasks": [], "follow_ups": []}
    today = datetime.now(timezone.utc).date()
    system_msg = (
        "You are a CRM sales-operations assistant. The user gives you a discussion comment "
        "written on a B2B lead. Extract concrete actionable items and return STRICT JSON only "
        "(no prose, no markdown, no code fences). Schema:\n"
        "{\n"
        '  "tasks": [{"title": string (imperative, <=80 chars), "description": string, '
        '"priority": one of [low, medium, high], "due_in_days": integer >= 0}],\n'
        '  "follow_ups": [{"notes": string (what to follow up about), "due_in_days": integer >= 1, '
        '"pending_with": one of [customer, selling_partner, null], '
        '"time": "HH:MM" 24h string or null if no specific time mentioned}]\n'
        "}\n"
        "Rules: A task (action item) = internal work someone must DO (prepare doc, send proposal, fix pricing). "
        "A follow-up = a scheduled check-in / conversation with the customer or partner. "
        "Only extract items clearly implied by the text — do NOT invent. Max 3 of each. "
        f"If the text mentions a specific day/date/time, convert it to due_in_days from today (today is {today.strftime('%A, %d %b %Y')}). "
        "If nothing actionable, return empty arrays."
    )
    parsed = await _ai_lead_chat(lead_id, system_msg, f"Lead: {lead.get('title')}\nDiscussion comment:\n{text}\n\nReturn STRICT JSON only.")

    tasks_out, followups_out = [], []
    for t in (parsed.get('tasks') or [])[:3]:
        title = str(t.get('title') or '').strip()
        if not title:
            continue
        priority = str(t.get('priority') or 'medium').lower()
        due_days = max(0, min(90, _safe_int(t.get('due_in_days'), 0)))
        tasks_out.append({
            "title": title[:120],
            "description": str(t.get('description') or '').strip()[:500],
            "priority": priority if priority in ('low', 'medium', 'high') else 'medium',
            "due_date": (today + timedelta(days=due_days)).isoformat(),
        })
    for f in (parsed.get('follow_ups') or [])[:3]:
        notes = str(f.get('notes') or '').strip()
        if not notes:
            continue
        due_days = max(1, min(90, _safe_int(f.get('due_in_days'), 1)))
        d = (today + timedelta(days=due_days)).isoformat()
        tm = f.get('time')
        scheduled = f"{d}T{tm}:00" if (isinstance(tm, str) and re.match(r'^\d{2}:\d{2}$', tm)) else d
        pending = f.get('pending_with')
        followups_out.append({
            "notes": notes[:500],
            "scheduled_date": scheduled,
            "pending_with": pending if pending in ('customer', 'selling_partner') else None,
        })
    return {"tasks": tasks_out, "follow_ups": followups_out}
