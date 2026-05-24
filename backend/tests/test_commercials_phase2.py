"""
Backend tests for Revenue Contracting & Delivery Management — Phase 2.

Coverage:
- POST /api/commercials/run-renewal-scan (admin/finance/delivery; idempotency; Renewal status auto-creation)
- GET  /api/commercials/analytics (?months=6/12/24; series, forecast_90d, revenue_mix, current)
- Route ordering: /analytics and /run-renewal-scan should not collide with /{commercial_id}
- RBAC: customer -> 403 on /commercials, /commercials/dashboard, /commercials/analytics, /commercials/run-renewal-scan
- Selling partner: 200 list (filtered), 403 analytics + renewal scan
- is_finance / is_delivery user flags: persist on POST, returned on GET/auth/me/auth/login, updatable via PUT
- is_finance user (non-admin role) can access dashboard, analytics, run-renewal-scan, list, create commercials
- is_delivery user (non-admin role) can access dashboard, analytics, run-renewal-scan
- End-to-end renewal scan: build a recurring contract with contract_end_date ~5 days, scan -> created==1,
  re-scan -> created==0, skipped==1, contract_status=='renewal_due', renewal_lead_id set,
  lead has status_id=='Renewal', activity 'renewal_lead_created' logged.
"""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://vyapaar-preview-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@vyapaarnetwork.com"
ADMIN_PASSWORD = "admin123"
CUSTOMER_EMAIL = "john@testco.com"
CUSTOMER_PASSWORD = "test123"

TS = int(time.time())


# ----------------------- Fixtures -----------------------
@pytest.fixture(scope="session")
def admin_headers():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def customer_token():
    r = requests.post(f"{API}/auth/login", json={"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Customer login failed: {r.text}")
    return r.json()["access_token"]


def _create_user(admin_headers, suffix, role="sales_associate", is_finance=False, is_delivery=False):
    email = f"test_p2_{suffix}_{TS}@example.com"
    payload = {
        "email": email,
        "password": "test1234",
        "name": f"TEST P2 {suffix}",
        "role": role,
        "phone": "+91 90000 12345",
        "is_finance": is_finance,
        "is_delivery": is_delivery,
    }
    r = requests.post(f"{API}/users", json=payload, headers=admin_headers, timeout=20)
    if r.status_code not in (200, 201):
        pytest.skip(f"Cannot create {suffix} user: {r.status_code} {r.text}")
    login = requests.post(f"{API}/auth/login", json={"email": email, "password": "test1234"}, timeout=20)
    assert login.status_code == 200, login.text
    return {
        "email": email,
        "user": r.json(),
        "user_id": r.json().get("id"),
        "token": login.json()["access_token"],
        "login_user": login.json()["user"],
    }


@pytest.fixture(scope="session")
def finance_user(admin_headers):
    return _create_user(admin_headers, "finance", role="sales_associate", is_finance=True)


@pytest.fixture(scope="session")
def delivery_user(admin_headers):
    return _create_user(admin_headers, "delivery", role="sales_associate", is_delivery=True)


@pytest.fixture(scope="session")
def selling_partner_user(admin_headers):
    return _create_user(admin_headers, "sp", role="selling_partner")


@pytest.fixture(scope="session")
def primary_category_id(admin_headers):
    r = requests.get(f"{API}/master/primary-categories", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    cats = r.json()
    if not cats:
        pytest.skip("No primary categories")
    return cats[0]["id"]


@pytest.fixture(scope="session")
def expiring_recurring_commercial(admin_headers, primary_category_id):
    """Create a lead + recurring commercial that's within the renewal-notice window."""
    statuses = requests.get(f"{API}/master/lead-status", headers=admin_headers, timeout=20).json()
    assert statuses
    new_status = next((s for s in statuses if (s.get("name") or "").lower() in ("new", "open")), statuses[0])
    today = datetime.now(timezone.utc).date()
    lead_payload = {
        "title": f"TEST P2 Renewal Lead {TS}",
        "customer_name": f"TEST P2 Customer {TS}",
        "customer_email": f"test_p2_lead_{TS}@example.com",
        "customer_phone": "+91 90000 50000",
        "status_id": new_status["id"],
        "primary_category_id": primary_category_id,
        "estimated_value": 240000,
    }
    rl = requests.post(f"{API}/leads", json=lead_payload, headers=admin_headers, timeout=20)
    assert rl.status_code in (200, 201), rl.text
    lead = rl.json()

    start_date = (today - timedelta(days=355)).isoformat()
    end_date = (today + timedelta(days=5)).isoformat()
    payload = {
        "lead_id": lead["id"],
        "type": "recurring",
        "billing_frequency": "monthly",
        "contract_value": 12000,
        "contract_start_date": start_date,
        "contract_end_date": end_date,
        "renewal_type": "manual",
        "auto_renewal": False,
        "renewal_notice_days": 30,
        "currency": "INR",
    }
    rc = requests.post(f"{API}/commercials", json=payload, headers=admin_headers, timeout=20)
    assert rc.status_code in (200, 201), rc.text
    return {"lead": lead, "commercial": rc.json()}


# ----------------------- is_finance / is_delivery user flag persistence -----------------------
class TestUserFlags:
    def test_create_user_with_finance_flag_persists(self, admin_headers):
        email = f"test_flag_fin_{TS}_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{API}/users", json={
            "email": email, "password": "test1234", "name": "TEST Flag Fin",
            "role": "sales_associate", "is_finance": True, "is_delivery": False,
        }, headers=admin_headers, timeout=20)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert body.get("is_finance") is True
        assert body.get("is_delivery") is False
        uid = body["id"]

        # GET /api/users includes flags
        ru = requests.get(f"{API}/users", headers=admin_headers, timeout=20)
        assert ru.status_code == 200
        match = next((u for u in ru.json() if u["id"] == uid), None)
        assert match is not None
        assert match.get("is_finance") is True
        assert match.get("is_delivery") is False

        # PUT updates flags
        rp = requests.put(f"{API}/users/{uid}", json={"is_finance": False, "is_delivery": True}, headers=admin_headers, timeout=20)
        assert rp.status_code == 200, rp.text
        assert rp.json().get("is_finance") is False
        assert rp.json().get("is_delivery") is True

        # auth/login & auth/me reflect flags
        login = requests.post(f"{API}/auth/login", json={"email": email, "password": "test1234"}, timeout=20)
        assert login.status_code == 200
        login_user = login.json()["user"]
        assert login_user.get("is_delivery") is True
        assert login_user.get("is_finance") is False

        me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}, timeout=20)
        assert me.status_code == 200
        assert me.json().get("is_delivery") is True
        assert me.json().get("is_finance") is False


# ----------------------- Analytics endpoint -----------------------
class TestAnalyticsEndpoint:
    @pytest.mark.parametrize("months", [6, 12, 24])
    def test_analytics_returns_series(self, admin_headers, months):
        r = requests.get(f"{API}/commercials/analytics?months={months}", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        # Top-level structure
        for key in ("series", "forecast_90d", "revenue_mix", "current"):
            assert key in body, f"missing {key}"
        # series length matches months
        assert isinstance(body["series"], list)
        assert len(body["series"]) == months
        # Each bucket has the required keys
        b = body["series"][0]
        for fld in ("label", "key", "mrr", "arr", "active_contracts", "new_contracts",
                    "churned_contracts", "churn_rate_pct", "revenue_collected", "invoices_raised"):
            assert fld in b, f"series missing field {fld}"
        for fld in ("total", "pending_invoices", "recurring_billings", "project_milestones"):
            assert fld in body["forecast_90d"], f"forecast missing {fld}"
        assert "one_time" in body["revenue_mix"]
        assert "recurring" in body["revenue_mix"]
        for fld in ("mrr", "arr", "active_contracts", "churn_rate_pct"):
            assert fld in body["current"]

    def test_analytics_route_not_caught_by_id_route(self, admin_headers):
        """Analytics must NOT 404 with 'Commercial not found'."""
        r = requests.get(f"{API}/commercials/analytics", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        # Make sure body is analytics shape, not "Commercial not found"
        body = r.json()
        assert "series" in body

    def test_analytics_403_for_customer(self, customer_token):
        r = requests.get(f"{API}/commercials/analytics", headers={"Authorization": f"Bearer {customer_token}"}, timeout=20)
        assert r.status_code == 403, r.text

    def test_analytics_403_for_selling_partner(self, selling_partner_user):
        r = requests.get(f"{API}/commercials/analytics",
                         headers={"Authorization": f"Bearer {selling_partner_user['token']}"}, timeout=20)
        assert r.status_code == 403, r.text

    def test_analytics_200_for_finance_user(self, finance_user):
        r = requests.get(f"{API}/commercials/analytics",
                         headers={"Authorization": f"Bearer {finance_user['token']}"}, timeout=20)
        assert r.status_code == 200, r.text

    def test_analytics_200_for_delivery_user(self, delivery_user):
        r = requests.get(f"{API}/commercials/analytics",
                         headers={"Authorization": f"Bearer {delivery_user['token']}"}, timeout=20)
        assert r.status_code == 200, r.text


# ----------------------- Customer RBAC 403 -----------------------
class TestCustomerRBAC:
    def test_customer_blocked_on_list(self, customer_token):
        r = requests.get(f"{API}/commercials", headers={"Authorization": f"Bearer {customer_token}"}, timeout=20)
        assert r.status_code == 403, f"expected 403 for customer on list, got {r.status_code} {r.text}"

    def test_customer_blocked_on_dashboard(self, customer_token):
        r = requests.get(f"{API}/commercials/dashboard", headers={"Authorization": f"Bearer {customer_token}"}, timeout=20)
        assert r.status_code == 403

    def test_customer_blocked_on_analytics(self, customer_token):
        r = requests.get(f"{API}/commercials/analytics", headers={"Authorization": f"Bearer {customer_token}"}, timeout=20)
        assert r.status_code == 403

    def test_customer_blocked_on_run_renewal_scan(self, customer_token):
        r = requests.post(f"{API}/commercials/run-renewal-scan", headers={"Authorization": f"Bearer {customer_token}"}, timeout=20)
        assert r.status_code == 403


# ----------------------- Selling partner RBAC -----------------------
class TestSellingPartnerRBAC:
    def test_sp_can_list(self, selling_partner_user):
        r = requests.get(f"{API}/commercials", headers={"Authorization": f"Bearer {selling_partner_user['token']}"}, timeout=20)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_sp_403_on_analytics(self, selling_partner_user):
        r = requests.get(f"{API}/commercials/analytics", headers={"Authorization": f"Bearer {selling_partner_user['token']}"}, timeout=20)
        assert r.status_code == 403

    def test_sp_403_on_run_renewal_scan(self, selling_partner_user):
        r = requests.post(f"{API}/commercials/run-renewal-scan", headers={"Authorization": f"Bearer {selling_partner_user['token']}"}, timeout=20)
        assert r.status_code == 403


# ----------------------- Finance/Delivery user write access -----------------------
class TestFinanceAndDeliveryWrite:
    def test_finance_user_can_access_dashboard(self, finance_user):
        r = requests.get(f"{API}/commercials/dashboard", headers={"Authorization": f"Bearer {finance_user['token']}"}, timeout=20)
        assert r.status_code == 200, r.text

    def test_finance_user_can_run_renewal_scan(self, finance_user):
        r = requests.post(f"{API}/commercials/run-renewal-scan", headers={"Authorization": f"Bearer {finance_user['token']}"}, timeout=20)
        assert r.status_code == 200, r.text

    def test_finance_user_can_create_commercial(self, finance_user, admin_headers, primary_category_id):
        # Need a fresh lead
        statuses = requests.get(f"{API}/master/lead-status", headers=admin_headers, timeout=20).json()
        new_status = next((s for s in statuses if (s.get("name") or "").lower() in ("new", "open")), statuses[0])
        rl = requests.post(f"{API}/leads", json={
            "title": f"TEST P2 FinUser Lead {uuid.uuid4().hex[:6]}",
            "customer_name": "TEST FinUser Customer",
            "customer_email": f"finuser_{uuid.uuid4().hex[:6]}@example.com",
            "customer_phone": "+91 90000 60000",
            "status_id": new_status["id"],
            "primary_category_id": primary_category_id,
            "estimated_value": 100000,
        }, headers=admin_headers, timeout=20)
        assert rl.status_code in (200, 201), rl.text
        lead_id = rl.json()["id"]
        rc = requests.post(f"{API}/commercials", json={
            "lead_id": lead_id, "type": "one_time", "total_value": 100000, "currency": "INR",
        }, headers={"Authorization": f"Bearer {finance_user['token']}", "Content-Type": "application/json"}, timeout=20)
        assert rc.status_code in (200, 201), f"Finance user create failed: {rc.status_code} {rc.text}"

    def test_delivery_user_can_access_dashboard_and_analytics(self, delivery_user):
        r1 = requests.get(f"{API}/commercials/dashboard", headers={"Authorization": f"Bearer {delivery_user['token']}"}, timeout=20)
        assert r1.status_code == 200, r1.text
        r2 = requests.get(f"{API}/commercials/analytics", headers={"Authorization": f"Bearer {delivery_user['token']}"}, timeout=20)
        assert r2.status_code == 200, r2.text


# ----------------------- Renewal scan: end-to-end + idempotent -----------------------
class TestRenewalScan:
    def test_renewal_scan_creates_then_idempotent(self, admin_headers, expiring_recurring_commercial):
        commercial_id = expiring_recurring_commercial["commercial"]["id"]

        # First scan: should create 1
        r1 = requests.post(f"{API}/commercials/run-renewal-scan", headers=admin_headers, timeout=30)
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert "created" in body1 and "flagged" in body1 and "skipped" in body1 and "items" in body1
        # Our commercial should be present in items
        my_item = next((i for i in body1["items"] if i["commercial_id"] == commercial_id), None)
        assert my_item is not None, f"Our commercial not in created items: {body1}"
        assert body1["created"] >= 1

        renewal_lead_id = my_item["lead_id"]

        # Verify commercial fields
        rc = requests.get(f"{API}/commercials/{commercial_id}", headers=admin_headers, timeout=20)
        assert rc.status_code == 200
        cb = rc.json()
        assert cb.get("contract_status") == "renewal_due"
        assert cb.get("renewal_lead_id") == renewal_lead_id

        # Verify renewal lead points to Renewal status
        rs = requests.get(f"{API}/master/lead-status", headers=admin_headers, timeout=20).json()
        renewal_status = next((s for s in rs if s.get("name") == "Renewal"), None)
        assert renewal_status is not None, "Renewal status was not auto-created"

        rlead = requests.get(f"{API}/leads/{renewal_lead_id}", headers=admin_headers, timeout=20)
        assert rlead.status_code == 200, rlead.text
        assert rlead.json().get("status_id") == renewal_status["id"]

        # Activity log includes 'renewal_lead_created'
        act = requests.get(f"{API}/commercials/{commercial_id}/activity", headers=admin_headers, timeout=20)
        assert act.status_code == 200, act.text
        events = act.json()
        action_types = {e.get("type") or e.get("action") for e in events}
        assert "renewal_lead_created" in action_types, f"Activity events: {action_types}"

        # Second scan: should be idempotent — skipped count >=1 for our commercial, created shouldn't include us
        r2 = requests.post(f"{API}/commercials/run-renewal-scan", headers=admin_headers, timeout=30)
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        my2 = next((i for i in body2["items"] if i["commercial_id"] == commercial_id), None)
        assert my2 is None, f"Commercial appeared in items again on idempotent scan: {body2}"
        # skipped should be >=1 since the lead already exists
        assert body2["skipped"] >= 1
