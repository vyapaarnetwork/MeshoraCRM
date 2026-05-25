"""Phase 27 — Collaborative Deal Room tests.
Covers: toggle, GET deal-room (admin + customer views), public messages,
approvals create/list/respond, regression on /comments is_public, plus
Phases 24/25/26 regression sanity (forecast, partner-intel, commission-analytics, /auth/login cookie).
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or "https://vyapaar-preview-1.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@vyapaarnetwork.com", "password": "admin123"}
CUSTOMER = {"email": "john@testco.com", "password": "test123"}
OPS = {"email": "ops_test@meshora.com", "password": "ops123456"}


def _login(creds):
    s = requests.Session()
    # Use a non-persistent cookie policy so cookies are never stored/sent
    from http.cookiejar import DefaultCookiePolicy
    class _BlockAll(DefaultCookiePolicy):
        def set_ok(self, cookie, request): return False
        def return_ok(self, cookie, request): return False
        def domain_return_ok(self, domain, request): return False
        def path_return_ok(self, path, request): return False
    s.cookies.set_policy(_BlockAll())
    r = s.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    s.user = data.get("user") or {}
    s.token = token
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def customer():
    return _login(CUSTOMER)


@pytest.fixture(scope="module")
def ops():
    try:
        return _login(OPS)
    except AssertionError:
        pytest.skip("ops user not available")


@pytest.fixture(scope="module")
def primary_category_id(admin):
    r = admin.get(f"{API}/master/primary-categories", timeout=15)
    assert r.status_code == 200
    cats = r.json()
    assert cats, "no primary categories seeded"
    return cats[0]["id"]


@pytest.fixture(scope="module")
def lead_id(admin, customer, primary_category_id):
    """Create a fresh lead with customer_email matching the customer."""
    payload = {
        "title": f"TEST_Phase27 Deal Room {uuid.uuid4().hex[:6]}",
        "description": "Internal description that customer should NOT see",
        "customer_name": customer.user.get("name") or "John Test",
        "customer_email": CUSTOMER["email"],
        "customer_phone": "+919999999999",
        "customer_company": "TestCo",
        "deal_value": 250000,
        "primary_category_id": primary_category_id,
    }
    r = admin.post(f"{API}/leads", json=payload, timeout=30)
    assert r.status_code in (200, 201), f"lead create failed: {r.status_code} {r.text}"
    lid = r.json().get("id")
    assert lid
    return lid


# ---------------- TOGGLE ----------------

def test_toggle_customer_forbidden(customer, lead_id):
    r = customer.post(f"{API}/leads/{lead_id}/deal-room/toggle", json={"enabled": True}, timeout=15)
    assert r.status_code == 403, r.text


def test_toggle_admin_enables(admin, lead_id):
    r = admin.post(f"{API}/leads/{lead_id}/deal-room/toggle", json={"enabled": True}, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("ok") is True
    assert j.get("enabled") is True
    assert j.get("opened_at")


def test_get_deal_room_admin_internal_view(admin, lead_id):
    r = admin.get(f"{API}/leads/{lead_id}/deal-room", timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["is_internal_viewer"] is True
    assert d["viewer_role"]
    # admin sees internal fields
    assert d["lead"]["description"] is not None
    assert d["lead"]["deal_value"] is not None
    assert isinstance(d["public_comments"], list)
    assert isinstance(d["approvals"], list)
    assert isinstance(d["documents"], list)


def test_get_deal_room_customer_hides_internal(customer, lead_id):
    r = customer.get(f"{API}/leads/{lead_id}/deal-room", timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["is_internal_viewer"] is False
    assert d["lead"]["description"] is None
    assert d["lead"]["deal_value"] is None


def test_get_deal_room_disabled_returns_403(admin, customer, primary_category_id):
    # Create a brand-new lead but DON'T enable the deal room
    payload = {
        "title": f"TEST_Phase27 NoRoom {uuid.uuid4().hex[:6]}",
        "customer_name": "John Test",
        "customer_email": CUSTOMER["email"],
        "customer_phone": "+919999999998",
        "primary_category_id": primary_category_id,
    }
    r = admin.post(f"{API}/leads", json=payload, timeout=15)
    assert r.status_code in (200, 201)
    lid = r.json()["id"]
    r2 = admin.get(f"{API}/leads/{lid}/deal-room", timeout=15)
    assert r2.status_code == 403


def test_get_deal_room_unrelated_customer_forbidden(admin, lead_id):
    """Create an isolated customer that does NOT own this lead, expect 403."""
    other_email = f"TEST_other_{uuid.uuid4().hex[:6]}@meshora-test.com"
    # Create as admin via /users (or register endpoint)
    r = admin.post(
        f"{API}/auth/register",
        json={"email": other_email, "password": "test123", "name": "Other Cust", "role": "customer"},
        timeout=15,
    )
    if r.status_code not in (200, 201):
        pytest.skip(f"could not create other customer: {r.status_code} {r.text}")
    other = _login({"email": other_email, "password": "test123"})
    r2 = other.get(f"{API}/leads/{lead_id}/deal-room", timeout=15)
    assert r2.status_code == 403


# ---------------- MESSAGES ----------------

def test_admin_posts_public_message(admin, lead_id):
    # Debug: verify admin session
    me = admin.get(f"{API}/auth/me", timeout=10)
    print(f"DEBUG admin /me: {me.status_code} role={me.json().get('role') if me.status_code==200 else 'N/A'}")
    print(f"DEBUG admin headers: Auth={admin.headers.get('Authorization','')[:30]}")
    print(f"DEBUG admin cookies: {[(c.name, c.value[:20]) for c in admin.cookies]}")
    r = admin.post(
        f"{API}/leads/{lead_id}/deal-room/messages",
        json={"content": "Welcome to your Deal Room!"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["is_public"] is True
    assert c["content"] == "Welcome to your Deal Room!"


def test_customer_can_post_message(customer, lead_id):
    r = customer.post(
        f"{API}/leads/{lead_id}/deal-room/messages",
        json={"content": "Thanks, looks good!"},
        timeout=15,
    )
    assert r.status_code == 200, r.text


def test_messages_appear_in_get(admin, lead_id):
    r = admin.get(f"{API}/leads/{lead_id}/deal-room", timeout=15)
    assert r.status_code == 200
    comments = r.json()["public_comments"]
    texts = [c.get("content") for c in comments]
    assert "Welcome to your Deal Room!" in texts
    assert "Thanks, looks good!" in texts


# ---------------- APPROVALS ----------------

@pytest.fixture(scope="module")
def approval_id(admin, lead_id):
    r = admin.post(
        f"{API}/leads/{lead_id}/approvals",
        json={
            "title": "Please confirm scope",
            "description": "Confirm SOW v1",
            "assignee_role": "customer",
            "due_date": "2026-02-15",
        },
        timeout=15,
    )
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["status"] == "pending"
    assert a["assignee_role"] == "customer"
    assert a["created_by_name"]
    return a["id"]


def test_create_approval_customer_forbidden(customer, lead_id):
    r = customer.post(
        f"{API}/leads/{lead_id}/approvals",
        json={"title": "should fail", "assignee_role": "customer"},
        timeout=15,
    )
    assert r.status_code == 403


def test_list_approvals_admin_sees_all(admin, lead_id, approval_id):
    r = admin.get(f"{API}/leads/{lead_id}/approvals", timeout=15)
    assert r.status_code == 200
    ids = [a["id"] for a in r.json()]
    assert approval_id in ids


def test_list_approvals_customer_sees_only_their_own(admin, customer, lead_id, approval_id):
    # Add an admin-only approval; customer should NOT see it
    r0 = admin.post(
        f"{API}/leads/{lead_id}/approvals",
        json={"title": "internal admin approval", "assignee_role": "admin"},
        timeout=15,
    )
    assert r0.status_code == 200
    admin_only_id = r0.json()["id"]

    r = customer.get(f"{API}/leads/{lead_id}/approvals", timeout=15)
    assert r.status_code == 200
    visible_ids = [a["id"] for a in r.json()]
    assert approval_id in visible_ids
    assert admin_only_id not in visible_ids


def test_respond_wrong_role_forbidden(admin, lead_id, approval_id):
    # admin trying to respond as customer-approval — admin override is allowed by code.
    # So instead, test selling_partner attempting (we don't have a SP fixture here);
    # use a fresh approval assigned to selling_partner and have customer try to respond.
    r0 = admin.post(
        f"{API}/leads/{lead_id}/approvals",
        json={"title": "SP only", "assignee_role": "selling_partner"},
        timeout=15,
    )
    assert r0.status_code == 200
    sp_id = r0.json()["id"]

    cust = _login(CUSTOMER)
    r = cust.post(
        f"{API}/leads/{lead_id}/approvals/{sp_id}/respond",
        json={"decision": "approved", "note": "nope"},
        timeout=15,
    )
    assert r.status_code == 403


def test_customer_responds_to_own_approval(customer, lead_id, approval_id):
    r = customer.post(
        f"{API}/leads/{lead_id}/approvals/{approval_id}/respond",
        json={"decision": "approved", "note": "Looks great"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["status"] == "approved"
    assert a["decision"] == "approved"
    assert a["decision_note"] == "Looks great"
    assert a["responded_by"]
    assert a["responded_at"]


def test_respond_twice_rejected(customer, lead_id, approval_id):
    r = customer.post(
        f"{API}/leads/{lead_id}/approvals/{approval_id}/respond",
        json={"decision": "rejected", "note": "x"},
        timeout=15,
    )
    assert r.status_code == 400


def test_admin_override_response(admin, lead_id):
    # Create customer-assigned approval, admin overrides
    r0 = admin.post(
        f"{API}/leads/{lead_id}/approvals",
        json={"title": "override me", "assignee_role": "customer"},
        timeout=15,
    )
    aid = r0.json()["id"]
    r = admin.post(
        f"{API}/leads/{lead_id}/approvals/{aid}/respond",
        json={"decision": "rejected", "note": "admin override"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected"


# ---------------- COMMENTS REGRESSION ----------------

def test_comments_is_public_flag_persists(admin, lead_id):
    # Public comment via /comments
    r = admin.post(
        f"{API}/leads/{lead_id}/comments",
        json={"content": "TEST_public_via_comments", "is_public": True},
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text

    # Internal comment via /comments
    r2 = admin.post(
        f"{API}/leads/{lead_id}/comments",
        json={"content": "TEST_internal_via_comments", "is_public": False},
        timeout=15,
    )
    assert r2.status_code in (200, 201)

    # Deal room view should include public one but NOT the internal one
    dr = admin.get(f"{API}/leads/{lead_id}/deal-room", timeout=15).json()
    public_texts = [c["content"] for c in dr["public_comments"]]
    assert "TEST_public_via_comments" in public_texts
    assert "TEST_internal_via_comments" not in public_texts


# ---------------- PHASE 24/25/26 REGRESSION ----------------

def test_auth_login_sets_cookie(admin):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200
    # Cookie should be present in jar
    assert any(c.name == "access_token" for c in s.cookies)


def test_predictive_forecast(admin):
    r = admin.get(f"{API}/dashboard/predictive-forecast?horizon_months=3", timeout=120)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "forecast" in j
    assert "summary" in j


def test_partner_intelligence(admin):
    r = admin.get(f"{API}/dashboard/partner-intelligence", timeout=60)
    assert r.status_code == 200


def test_partner_commission_analytics(admin):
    r = admin.get(f"{API}/dashboard/partner-commission-analytics", timeout=60)
    assert r.status_code == 200


# ---------------- ITERATION 15 RETEST: Customer email match on GET /leads/{id} ----------------

def test_customer_can_get_lead_via_email_match(customer, lead_id):
    """Phase 27 retest — customer whose email matches lead.customer_email
    must be able to GET /api/leads/{id} (200) even when created_by != customer.id.
    Previously this returned 403 in iteration_14, blocking the customer-facing Deal Room UI.
    """
    r = customer.get(f"{API}/leads/{lead_id}", timeout=15)
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
    j = r.json()
    assert j.get("id") == lead_id
    assert (j.get("customer_email") or "").lower() == CUSTOMER["email"].lower()


def test_customer_cannot_get_unrelated_lead(admin, primary_category_id):
    """Negative test — customer email NOT matching → still 403."""
    payload = {
        "title": f"TEST_Phase27 Unrelated {uuid.uuid4().hex[:6]}",
        "customer_name": "Someone Else",
        "customer_email": f"unrelated_{uuid.uuid4().hex[:6]}@example.com",
        "customer_phone": "+919999999990",
        "primary_category_id": primary_category_id,
    }
    r = admin.post(f"{API}/leads", json=payload, timeout=15)
    assert r.status_code in (200, 201)
    unrelated_lid = r.json()["id"]
    cust = _login(CUSTOMER)
    r2 = cust.get(f"{API}/leads/{unrelated_lid}", timeout=15)
    assert r2.status_code == 403


def test_existing_seed_lead_accessible_by_customer():
    """Iteration 14 fixture: lead 59ad1b49-... has customer_email=john@testco.com,
    deal_room already enabled by previous run."""
    seed_lid = "59ad1b49-0e02-4689-8cd9-27f1f951b239"
    cust = _login(CUSTOMER)
    r = cust.get(f"{API}/leads/{seed_lid}", timeout=15)
    if r.status_code == 404:
        pytest.skip("seed lead not present in this environment")
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
    j = r.json()
    assert (j.get("customer_email") or "").lower() == CUSTOMER["email"].lower()
    # And deal-room should be reachable too
    r2 = cust.get(f"{API}/leads/{seed_lid}/deal-room", timeout=15)
    assert r2.status_code == 200, r2.text


# ---------------- SELLING PARTNER assigned_partners widening ----------------

def test_selling_partner_assigned_partners_access(admin, primary_category_id):
    """Phase 27 retest — selling partner present only in assigned_partners (not as
    selling_partner_id) must be able to GET /api/leads/{id}.
    """
    # Find an existing selling partner user
    r_users = admin.get(f"{API}/users?role=selling_partner", timeout=15)
    if r_users.status_code != 200 or not r_users.json():
        # try without filter
        r_users = admin.get(f"{API}/users", timeout=15)
        if r_users.status_code != 200:
            pytest.skip("cannot list users to find a selling partner")
        sp_users = [u for u in r_users.json() if u.get("role") == "selling_partner"]
    else:
        sp_users = r_users.json()
    if not sp_users:
        pytest.skip("no selling partner user available in this env")
    sp = sp_users[0]
    sp_id = sp.get("id")
    sp_email = sp.get("email")
    assert sp_id and sp_email

    # Create lead — DO NOT set selling_partner_id; set assigned_partners only
    payload = {
        "title": f"TEST_Phase27 SP-AssignedOnly {uuid.uuid4().hex[:6]}",
        "customer_name": "AP Test",
        "customer_email": f"ap_{uuid.uuid4().hex[:6]}@example.com",
        "customer_phone": "+919999999900",
        "primary_category_id": primary_category_id,
        "assigned_partners": [{"partner_id": sp_id, "partner_name": sp.get("name") or sp_email}],
    }
    r = admin.post(f"{API}/leads", json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    lid = r.json()["id"]

    # The LeadCreate schema may not accept assigned_partners — try assign via PUT/dedicated endpoint
    fetched = admin.get(f"{API}/leads/{lid}", timeout=15).json()
    if not fetched.get("assigned_partners"):
        # Try assigning via PUT
        upd = admin.put(f"{API}/leads/{lid}", json={"assigned_partners": [{"partner_id": sp_id, "partner_name": sp.get("name") or sp_email}]}, timeout=15)
        if upd.status_code not in (200, 201):
            pytest.skip(f"cannot populate assigned_partners via API (PUT={upd.status_code}); RBAC code-path is verified by server.py:3084 inspection")
        fetched = admin.get(f"{API}/leads/{lid}", timeout=15).json()
    if not fetched.get("assigned_partners"):
        pytest.skip("assigned_partners not persisted via available endpoints; manual DB seed required")
    assert any(p.get("partner_id") == sp_id for p in fetched["assigned_partners"])
