"""Phase 27 iteration_16 — focused retest of the 2 CRITICAL backend fixes.
FIX 1: GET /api/leads/{lead_id} includes deal_room_enabled + deal_room_opened_at.
FIX 2: Customer email-match access redacts internal fields.
"""
import os
import requests
import pytest
from http.cookiejar import DefaultCookiePolicy

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""

BASE_URL = _load_backend_url().rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@vyapaarnetwork.com", "password": "admin123"}
CUSTOMER = {"email": "john@testco.com", "password": "test123"}
SEED_LEAD_ID = "59ad1b49-0e02-4689-8cd9-27f1f951b239"


class _BlockAll(DefaultCookiePolicy):
    def set_ok(self, c, r): return False
    def return_ok(self, c, r): return False
    def domain_return_ok(self, d, r): return False
    def path_return_ok(self, p, r): return False


def _login(creds):
    s = requests.Session()
    s.cookies.set_policy(_BlockAll())
    r = s.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def customer():
    return _login(CUSTOMER)


# ---------- FIX 1 ----------
def test_fix1_lead_get_includes_deal_room_fields_admin(admin):
    # Ensure enabled
    t = admin.post(f"{API}/leads/{SEED_LEAD_ID}/deal-room/toggle", json={"enabled": True}, timeout=30)
    assert t.status_code == 200, t.text
    assert t.json().get("enabled") is True

    r = admin.get(f"{API}/leads/{SEED_LEAD_ID}", timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "deal_room_enabled" in body, f"deal_room_enabled MISSING from response keys: {list(body.keys())}"
    assert body["deal_room_enabled"] is True, f"expected True, got {body.get('deal_room_enabled')}"
    assert "deal_room_opened_at" in body
    assert body["deal_room_opened_at"] is not None


# ---------- FIX 2 ----------
def test_fix2_customer_email_match_redacts_internal_fields(customer):
    r = customer.get(f"{API}/leads/{SEED_LEAD_ID}", timeout=30)
    assert r.status_code == 200, f"customer should reach lead via email match: {r.status_code} {r.text}"
    body = r.json()

    # Sanity: it's the right lead
    assert body["id"] == SEED_LEAD_ID
    assert body["customer_email"].lower() == CUSTOMER["email"].lower()

    # Required redactions
    assert body.get("deal_value") == 0, f"deal_value not redacted: {body.get('deal_value')}"
    assert body.get("description") is None, f"description leaked: {body.get('description')!r}"
    assert body.get("commission_breakdown") is None, f"commission_breakdown leaked: {body.get('commission_breakdown')}"
    assert body.get("commission_override") is None
    assert body.get("sales_associate_commission") is None
    assert body.get("sales_associate_id") is None
    assert body.get("sales_associate_name") is None
    assert body.get("referred_by_partner_id") is None
    assert body.get("referred_by_partner_name") is None
    assert body.get("referred_by_associate_id") is None
    assert body.get("referred_by_associate_name") is None

    # Comments: only is_public=true survive
    for c in body.get("comments", []):
        assert c.get("is_public") is True, f"non-public comment leaked: {c}"

    # Deal room visibility must be exposed (so DealRoomTab flips to live)
    assert body.get("deal_room_enabled") is True


# ---------- Regression: admin still gets full data ----------
def test_regression_admin_gets_full_lead(admin):
    r = admin.get(f"{API}/leads/{SEED_LEAD_ID}", timeout=30)
    assert r.status_code == 200
    body = r.json()
    # Admin must see full data
    assert body.get("deal_value") == 500000 or body.get("deal_value") == 500000.0, f"admin deal_value should be 500000, got {body.get('deal_value')}"
    assert body.get("description") is not None and body.get("description") != "", "admin description should be present"
    # admin sees all comments (don't assert count, just confirm field is list)
    assert isinstance(body.get("comments"), list)
