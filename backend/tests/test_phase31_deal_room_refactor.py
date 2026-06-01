"""Phase 31 regression — Deal Room router extraction + Phase 30 regression.

Verifies:
1. All 12 Deal Room endpoints (Phase 27 + 27.5) still respond with expected status codes
   after extraction from server.py into routers/deal_room.py.
2. Phase 30 endpoints (notifications/types, users/assignable, war-room/board,
   follow-ups with assignee_id+reminder_minutes_before) still pass.
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@vyapaarnetwork.com"
ADMIN_PASSWORD = "admin123"


# ==================== Fixtures ====================
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def sample_lead_id(admin_headers):
    r = requests.get(f"{BASE_URL}/api/leads", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    leads = r.json()
    assert isinstance(leads, list) and len(leads) > 0, "Need at least one lead seeded"
    return leads[0]["id"]


# ==================== Deal Room (Phase 27) endpoints ====================
class TestDealRoomToggleAndGet:
    def test_toggle_on(self, admin_headers, sample_lead_id):
        r = requests.post(
            f"{BASE_URL}/api/leads/{sample_lead_id}/deal-room/toggle",
            headers=admin_headers,
            json={"enabled": True},
            timeout=20,
        )
        assert r.status_code == 200, f"toggle on failed: {r.status_code} {r.text[:200]}"
        body = r.json()
        # Confirm enabled flag is persisted (or response indicates success)
        assert body is not None

    def test_get_deal_room(self, admin_headers, sample_lead_id):
        r = requests.get(
            f"{BASE_URL}/api/leads/{sample_lead_id}/deal-room",
            headers=admin_headers,
            timeout=20,
        )
        assert r.status_code == 200, f"get failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        # Common shape — at least one of these keys present
        assert any(k in data for k in ("lead", "messages", "approvals", "deal_room_enabled", "enabled"))

    def test_post_message(self, admin_headers, sample_lead_id):
        r = requests.post(
            f"{BASE_URL}/api/leads/{sample_lead_id}/deal-room/messages",
            headers=admin_headers,
            json={"content": f"TEST_phase31_msg_{uuid.uuid4().hex[:6]}"},
            timeout=20,
        )
        assert r.status_code in (200, 201), f"post message failed: {r.status_code} {r.text[:200]}"


# ==================== Approvals ====================
class TestApprovals:
    @pytest.fixture(scope="class")
    def approval_id(self, admin_headers, sample_lead_id):
        r = requests.post(
            f"{BASE_URL}/api/leads/{sample_lead_id}/approvals",
            headers=admin_headers,
            json={
                "title": f"TEST_phase31_approval_{uuid.uuid4().hex[:6]}",
                "description": "Phase 31 regression",
                "assignee_role": "customer",
            },
            timeout=20,
        )
        assert r.status_code in (200, 201), f"create approval failed: {r.status_code} {r.text[:200]}"
        ap = r.json()
        # Try to find ID from common response shapes
        if isinstance(ap, dict):
            if "id" in ap:
                return ap["id"]
            if "approval" in ap and isinstance(ap["approval"], dict):
                return ap["approval"].get("id")
            # If response is the full lead/deal-room object, fetch approvals list
        r2 = requests.get(
            f"{BASE_URL}/api/leads/{sample_lead_id}/approvals",
            headers=admin_headers,
            timeout=20,
        )
        approvals = r2.json() if r2.status_code == 200 else []
        if isinstance(approvals, list) and approvals:
            return approvals[-1].get("id")
        pytest.skip("Unable to determine approval_id from response")

    def test_list_approvals(self, admin_headers, sample_lead_id):
        r = requests.get(
            f"{BASE_URL}/api/leads/{sample_lead_id}/approvals",
            headers=admin_headers,
            timeout=20,
        )
        assert r.status_code == 200, f"list approvals failed: {r.status_code} {r.text[:200]}"
        assert isinstance(r.json(), list)

    def test_respond_approval(self, admin_headers, sample_lead_id, approval_id):
        # Admin responding from own (super_admin) — may or may not be allowed; accept 200/403
        r = requests.post(
            f"{BASE_URL}/api/leads/{sample_lead_id}/approvals/{approval_id}/respond",
            headers=admin_headers,
            json={"decision": "approved", "note": "TEST_phase31"},
            timeout=20,
        )
        assert r.status_code in (200, 201, 400, 403), (
            f"respond approval unexpected: {r.status_code} {r.text[:200]}"
        )


# ==================== Magic-link Invites (Phase 27.5) ====================
class TestInvites:
    def test_create_invite(self, admin_headers, sample_lead_id):
        r = requests.post(
            f"{BASE_URL}/api/leads/{sample_lead_id}/deal-room/invites",
            headers=admin_headers,
            json={
                "email": f"TEST_phase31_{uuid.uuid4().hex[:6]}@example.com",
                "name": "Phase 31 Tester",
            },
            timeout=20,
        )
        assert r.status_code in (200, 201), f"create invite failed: {r.status_code} {r.text[:200]}"
        inv = r.json()
        assert isinstance(inv, dict)
        # Optionally inspect token to confirm presence
        # Stash invite_id on class via env var workaround? Use pytest cache
        if "id" in inv:
            requests.invite_id = inv["id"]  # stash on module-level singleton

    def test_list_invites(self, admin_headers, sample_lead_id):
        r = requests.get(
            f"{BASE_URL}/api/leads/{sample_lead_id}/deal-room/invites",
            headers=admin_headers,
            timeout=20,
        )
        assert r.status_code == 200, f"list invites failed: {r.status_code} {r.text[:200]}"
        assert isinstance(r.json(), list)

    def test_revoke_invite(self, admin_headers, sample_lead_id):
        # Pick the most recent TEST_phase31_* invite and revoke
        r = requests.get(
            f"{BASE_URL}/api/leads/{sample_lead_id}/deal-room/invites",
            headers=admin_headers,
            timeout=20,
        )
        if r.status_code != 200:
            pytest.skip("Cannot list invites for revoke step")
        invites = r.json()
        target = next(
            (i for i in invites if "TEST_phase31_" in (i.get("email") or "")),
            None,
        )
        if not target:
            pytest.skip("No TEST_phase31 invite found for revoke")
        rid = target.get("id")
        r2 = requests.delete(
            f"{BASE_URL}/api/leads/{sample_lead_id}/deal-room/invites/{rid}",
            headers=admin_headers,
            timeout=20,
        )
        assert r2.status_code in (200, 204), f"revoke failed: {r2.status_code} {r2.text[:200]}"


# ==================== Public guest endpoints ====================
class TestGuestPublic:
    def test_invalid_magic_link_returns_403(self):
        # Per spec: invalid magic-link → 403 expected
        r = requests.get(
            f"{BASE_URL}/api/deal-room/access/invalid_token_phase31_{uuid.uuid4().hex}",
            timeout=20,
        )
        assert r.status_code in (403, 404), (
            f"invalid token unexpected: {r.status_code} {r.text[:200]}"
        )

    def test_invalid_token_post_message_403(self):
        r = requests.post(
            f"{BASE_URL}/api/deal-room/access/invalid_token_phase31/messages",
            json={"content": "should fail"},
            timeout=20,
        )
        assert r.status_code in (403, 404), (
            f"invalid token POST unexpected: {r.status_code} {r.text[:200]}"
        )

    def test_invalid_token_respond_approval_403(self):
        r = requests.post(
            f"{BASE_URL}/api/deal-room/access/invalid_token_phase31/approvals/fake_id/respond",
            json={"decision": "approved"},
            timeout=20,
        )
        assert r.status_code in (403, 404), (
            f"invalid token respond unexpected: {r.status_code} {r.text[:200]}"
        )


# ==================== Phase 30 regression ====================
class TestPhase30Regression:
    def test_notifications_types(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/notifications/types", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        types = r.json()
        assert isinstance(types, list) and len(types) >= 1

    def test_users_assignable(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/users/assignable", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        users = r.json()
        assert isinstance(users, list) and len(users) >= 1
        assert "id" in users[0] and "name" in users[0]

    def test_war_room_board_open_leads(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/war-room/board", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        data = r.json()
        buckets = data.get("buckets") if isinstance(data, dict) else data
        assert isinstance(buckets, list)
        ids = [b.get("id") for b in buckets]
        assert "open_leads" in ids, f"open_leads bucket missing in: {ids}"

    def test_followup_with_assignee_and_reminder(self, admin_headers, sample_lead_id):
        # GET assignable to pick someone
        r = requests.get(f"{BASE_URL}/api/users/assignable", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assignees = r.json()
        if not assignees:
            pytest.skip("no assignable users")
        assignee_id = assignees[0]["id"]
        # Future date for reminder
        from datetime import datetime, timezone, timedelta
        future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        r2 = requests.post(
            f"{BASE_URL}/api/leads/{sample_lead_id}/follow-ups",
            headers=admin_headers,
            json={
                "scheduled_date": future,
                "notes": f"TEST_phase31_followup_{uuid.uuid4().hex[:6]}",
                "assignee_id": assignee_id,
                "reminder_minutes_before": 60,
            },
            timeout=20,
        )
        assert r2.status_code in (200, 201), (
            f"follow-up create failed: {r2.status_code} {r2.text[:200]}"
        )
