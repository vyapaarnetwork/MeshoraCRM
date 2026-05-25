"""Phase 27.5 — Deal Room Magic-Link Invitations.

Covers:
- POST /api/leads/{id}/deal-room/invites (admin/ops/assigned-partner; customer/sales 403)
- GET /api/leads/{id}/deal-room/invites (no raw tokens)
- DELETE /api/leads/{id}/deal-room/invites/{invite_id} (revoke)
- PUBLIC GET /api/deal-room/access/{token}
- PUBLIC POST /api/deal-room/access/{token}/messages
- PUBLIC POST /api/deal-room/access/{token}/approvals/{aid}/respond
- Regression: Phase 27 toggle, GET, public message still work; LeadResponse exposes deal_room_enabled
"""
import os
import pytest
import requests
from http.cookiejar import DefaultCookiePolicy

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@vyapaarnetwork.com", "password": "admin123"}
CUSTOMER = {"email": "john@testco.com", "password": "test123"}

LEAD_ID = "59ad1b49-0e02-4689-8cd9-27f1f951b239"  # canonical fixture (deal_room_enabled=true)


class _BlockAll(DefaultCookiePolicy):
    def set_ok(self, cookie, request): return False
    def return_ok(self, cookie, request): return False
    def domain_return_ok(self, domain, request): return False
    def path_return_ok(self, path, request): return False


def _login(creds):
    s = requests.Session()
    s.cookies.set_policy(_BlockAll())
    r = s.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    s.user = data.get("user") or {}
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def customer():
    return _login(CUSTOMER)


@pytest.fixture(scope="module")
def anon():
    s = requests.Session()
    s.cookies.set_policy(_BlockAll())
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def ensure_deal_room_open(admin):
    # Make sure the canonical lead has deal_room_enabled=True
    r = admin.get(f"{API}/leads/{LEAD_ID}", timeout=15)
    assert r.status_code == 200, r.text
    if not r.json().get("deal_room_enabled"):
        r2 = admin.post(f"{API}/leads/{LEAD_ID}/deal-room/toggle", json={"enabled": True}, timeout=15)
        assert r2.status_code == 200, r2.text
    return True


# ----------------- REGRESSION: Phase 27 LeadResponse exposes deal_room_enabled -----------------

def test_lead_response_includes_deal_room_enabled(admin, ensure_deal_room_open):
    r = admin.get(f"{API}/leads/{LEAD_ID}", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "deal_room_enabled" in body, "Phase 27 regression: LeadResponse must include deal_room_enabled"
    assert body["deal_room_enabled"] is True


# ----------------- CREATE INVITE -----------------

@pytest.fixture(scope="module")
def created_invite(admin, ensure_deal_room_open):
    payload = {
        "email": "TEST_stakeholder1@example.com",
        "name": "Sarah Test",
        "permissions": ["view", "comment", "approve"],
        "expires_in_days": 7,
        "note": "Pls review",
    }
    r = admin.post(f"{API}/leads/{LEAD_ID}/deal-room/invites", json=payload, timeout=20)
    assert r.status_code == 200, f"invite create failed: {r.status_code} {r.text}"
    data = r.json()
    # Schema assertions
    for k in ("id", "email", "name", "permissions", "token", "magic_link", "expires_at", "use_count"):
        assert k in data, f"missing key {k}"
    assert data["email"] == "test_stakeholder1@example.com"
    assert data["name"] == "Sarah Test"
    assert set(data["permissions"]) == {"view", "comment", "approve"}
    assert isinstance(data["token"], str) and len(data["token"]) >= 32
    assert "/deal-room/" in data["magic_link"]
    assert data["magic_link"].endswith(data["token"])
    assert data["use_count"] == 0
    return data


def test_create_invite_admin_ok(created_invite):
    assert created_invite["token"]


def test_create_invite_customer_403(customer):
    r = customer.post(
        f"{API}/leads/{LEAD_ID}/deal-room/invites",
        json={"email": "TEST_x@x.com", "name": "X", "permissions": ["view"], "expires_in_days": 7},
        timeout=20,
    )
    assert r.status_code == 403, f"customer must not be able to invite: {r.status_code} {r.text}"


def test_create_invite_requires_deal_room_enabled(admin):
    """Toggle off → invite create must return 400. Then re-enable to keep other tests happy."""
    r0 = admin.post(f"{API}/leads/{LEAD_ID}/deal-room/toggle", json={"enabled": False}, timeout=15)
    assert r0.status_code == 200
    try:
        r = admin.post(
            f"{API}/leads/{LEAD_ID}/deal-room/invites",
            json={"email": "TEST_y@x.com", "name": "Y", "permissions": ["view"], "expires_in_days": 7},
            timeout=15,
        )
        assert r.status_code == 400, f"should 400 when deal room disabled: {r.status_code} {r.text}"
    finally:
        rb = admin.post(f"{API}/leads/{LEAD_ID}/deal-room/toggle", json={"enabled": True}, timeout=15)
        assert rb.status_code == 200


# ----------------- LIST INVITES -----------------

def test_list_invites_admin_excludes_token(admin, created_invite):
    r = admin.get(f"{API}/leads/{LEAD_ID}/deal-room/invites", timeout=15)
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    assert any(i.get("id") == created_invite["id"] for i in items), "created invite must be listed"
    for i in items:
        assert "token" not in i, "raw token must NOT be returned in list endpoint"


def test_list_invites_customer_403(customer):
    r = customer.get(f"{API}/leads/{LEAD_ID}/deal-room/invites", timeout=15)
    assert r.status_code == 403


# ----------------- PUBLIC: GET ACCESS -----------------

def test_public_get_access_anonymous(anon, created_invite):
    # Use a raw requests Session that does NOT send Authorization header
    r = anon.get(f"{API}/deal-room/access/{created_invite['token']}", timeout=20)
    assert r.status_code == 200, f"public access failed: {r.status_code} {r.text}"
    body = r.json()
    for k in ("invite", "lead", "active_partners", "public_comments", "approvals", "documents"):
        assert k in body
    assert body["invite"]["name"] == "Sarah Test"
    assert set(body["invite"]["permissions"]) == {"view", "comment", "approve"}
    # All comments returned must be public (server filters)
    for c in body["public_comments"]:
        assert c.get("is_public") is True
    # Approvals only customer/all
    for a in body["approvals"]:
        assert a.get("assignee_role") in ("customer", "all")


def test_public_get_access_invalid_token_403(anon):
    r = anon.get(f"{API}/deal-room/access/invalid_token_xyz_123", timeout=15)
    assert r.status_code == 403


def test_public_get_access_bumps_use_count(admin, anon, created_invite):
    # hit twice
    anon.get(f"{API}/deal-room/access/{created_invite['token']}", timeout=15)
    anon.get(f"{API}/deal-room/access/{created_invite['token']}", timeout=15)
    # check list
    items = admin.get(f"{API}/leads/{LEAD_ID}/deal-room/invites", timeout=15).json()
    row = next((i for i in items if i["id"] == created_invite["id"]), None)
    assert row is not None
    assert row.get("use_count", 0) >= 2, f"use_count should be bumped: {row}"
    assert row.get("last_used_at"), "last_used_at must be set after access"


# ----------------- PUBLIC: POST MESSAGE -----------------

def test_public_post_message_with_comment_permission(anon, admin, created_invite):
    content = "TEST_guest_msg hello from automated test"
    r = anon.post(
        f"{API}/deal-room/access/{created_invite['token']}/messages",
        json={"content": content}, timeout=20,
    )
    assert r.status_code == 200, f"guest msg post failed: {r.status_code} {r.text}"
    c = r.json()
    assert c["content"] == content
    assert c["user_role"] == "guest"
    assert c["user_name"] == "Sarah Test (Guest)"
    assert c["is_public"] is True

    # Verify it appears in the public deal-room view (admin)
    dr = admin.get(f"{API}/leads/{LEAD_ID}/deal-room", timeout=15)
    assert dr.status_code == 200
    messages = dr.json().get("public_comments") or dr.json().get("comments") or []
    # also try the public access path
    if not any(m.get("content") == content for m in messages):
        body2 = anon.get(f"{API}/deal-room/access/{created_invite['token']}", timeout=15).json()
        messages = body2.get("public_comments") or []
    assert any(m.get("content") == content for m in messages), "guest msg must appear in deal room"


@pytest.fixture(scope="module")
def view_only_invite(admin, ensure_deal_room_open):
    payload = {
        "email": "TEST_view_only@example.com",
        "name": "ViewOnly Guest",
        "permissions": ["view"],
        "expires_in_days": 7,
    }
    r = admin.post(f"{API}/leads/{LEAD_ID}/deal-room/invites", json=payload, timeout=20)
    assert r.status_code == 200
    return r.json()


def test_public_post_message_403_without_permission(anon, view_only_invite):
    r = anon.post(
        f"{API}/deal-room/access/{view_only_invite['token']}/messages",
        json={"content": "should fail"}, timeout=15,
    )
    assert r.status_code == 403


# ----------------- PUBLIC: APPROVAL RESPOND -----------------

@pytest.fixture(scope="module")
def customer_approval(admin):
    """Create a pending approval targeted at customer to be approved by guest."""
    payload = {
        "title": "TEST_phase27_5 guest approval",
        "description": "Please approve",
        "assignee_role": "customer",
    }
    r = admin.post(f"{API}/leads/{LEAD_ID}/approvals", json=payload, timeout=20)
    assert r.status_code in (200, 201), f"approval create failed: {r.status_code} {r.text}"
    return r.json()


def test_public_approval_respond_requires_approve_permission(anon, view_only_invite, customer_approval):
    r = anon.post(
        f"{API}/deal-room/access/{view_only_invite['token']}/approvals/{customer_approval['id']}/respond",
        json={"decision": "approved"}, timeout=15,
    )
    assert r.status_code == 403


def test_public_approval_respond_success(anon, admin, created_invite, customer_approval):
    r = anon.post(
        f"{API}/deal-room/access/{created_invite['token']}/approvals/{customer_approval['id']}/respond",
        json={"decision": "approved", "note": "Looks good — TEST"}, timeout=20,
    )
    assert r.status_code == 200, f"guest approve failed: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("decision") == "approved" or body.get("status") == "approved"
    assert "Guest" in (body.get("responded_by_name") or "")

    # Cannot respond again (no longer pending)
    r2 = anon.post(
        f"{API}/deal-room/access/{created_invite['token']}/approvals/{customer_approval['id']}/respond",
        json={"decision": "rejected"}, timeout=15,
    )
    assert r2.status_code == 400


# ----------------- REVOKE -----------------

def test_revoke_invite_then_public_access_403(admin, anon, view_only_invite):
    rv = admin.delete(
        f"{API}/leads/{LEAD_ID}/deal-room/invites/{view_only_invite['id']}", timeout=15,
    )
    assert rv.status_code == 200, rv.text
    assert rv.json().get("revoked") is True

    # subsequent public access must 403
    r = anon.get(f"{API}/deal-room/access/{view_only_invite['token']}", timeout=15)
    assert r.status_code == 403


def test_revoke_invite_customer_403(customer, created_invite):
    r = customer.delete(
        f"{API}/leads/{LEAD_ID}/deal-room/invites/{created_invite['id']}", timeout=15,
    )
    assert r.status_code == 403


# ----------------- DEAL ROOM DISABLE GATES PUBLIC ACCESS -----------------

def test_public_access_403_when_deal_room_disabled(admin, anon, created_invite):
    r0 = admin.post(f"{API}/leads/{LEAD_ID}/deal-room/toggle", json={"enabled": False}, timeout=15)
    assert r0.status_code == 200
    try:
        r = anon.get(f"{API}/deal-room/access/{created_invite['token']}", timeout=15)
        assert r.status_code == 403
    finally:
        rb = admin.post(f"{API}/leads/{LEAD_ID}/deal-room/toggle", json={"enabled": True}, timeout=15)
        assert rb.status_code == 200


# ----------------- CLEANUP -----------------

def test_cleanup_revoke_created_invite(admin, created_invite):
    r = admin.delete(f"{API}/leads/{LEAD_ID}/deal-room/invites/{created_invite['id']}", timeout=15)
    assert r.status_code in (200, 404)
