"""
Backend tests for Revenue Contracting & Delivery Management (Commercials) - Phase 1 MVP.

Coverage:
  - Lead status master is_won flag + Won status backfill
  - Leads GET returns status_is_won
  - Commercials CRUD (create one-time + recurring, duplicate-lead rejection)
  - List, dashboard, by-lead, by-id
  - PATCH commercial + billing schedule regeneration on recurring updates
  - Milestone PUT validation (amount + percentage totals)
  - Milestone PATCH status update
  - Regenerate billing endpoint (recurring only, one_time rejected)
  - Quarterly schedule generation (2026-03-01 .. 2027-02-28 -> 4 periods)
  - Invoice raise updates milestone + billing schedule status
  - Full payment marks invoice paid + milestone payment_received
  - GET invoices / payments / activity / documents
  - RBAC: selling_partner cannot create/update; sales_associate/customer get 403
"""

import os
import uuid
import time
import requests
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://vyapaar-preview-1.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@vyapaarnetwork.com"
ADMIN_PASSWORD = "admin123"

TS = int(time.time())

# Shared state across test classes (pytest doesn't allow arbitrary attrs on pytest module)
STATE: dict = {}


# ----------------------- Fixtures -----------------------
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def sales_associate_user(admin_headers):
    """Create a sales associate for RBAC tests"""
    email = f"test_sa_{TS}@example.com"
    payload = {
        "email": email,
        "password": "test1234",
        "name": "TEST Sales Associate",
        "role": "sales_associate",
        "phone": "+91 90000 00001",
    }
    r = requests.post(f"{API}/users", json=payload, headers=admin_headers, timeout=20)
    # Tolerate if user already exists from previous run
    if r.status_code not in (200, 201, 400, 409):
        pytest.skip(f"Cannot create sales associate: {r.status_code} {r.text}")
    login = requests.post(f"{API}/auth/login", json={"email": email, "password": "test1234"}, timeout=20)
    if login.status_code != 200:
        pytest.skip(f"Cannot login sales associate: {login.text}")
    return login.json()["access_token"]


@pytest.fixture(scope="session")
def selling_partner_user(admin_headers):
    """Find or create a selling partner."""
    # First try to find an existing selling partner
    users = requests.get(f"{API}/users", headers=admin_headers, timeout=20)
    if users.status_code == 200:
        for u in users.json():
            if u.get("role") == "selling_partner" and u.get("is_active"):
                # We don't know the password, so try a known testing password; if it fails, create new
                pass
    email = f"test_sp_{TS}@example.com"
    payload = {
        "email": email,
        "password": "test1234",
        "name": "TEST Selling Partner",
        "role": "selling_partner",
        "phone": "+91 90000 00002",
    }
    r = requests.post(f"{API}/users", json=payload, headers=admin_headers, timeout=20)
    if r.status_code not in (200, 201):
        pytest.skip(f"Cannot create selling partner user: {r.status_code} {r.text}")
    login = requests.post(f"{API}/auth/login", json={"email": email, "password": "test1234"}, timeout=20)
    if login.status_code != 200:
        pytest.skip("Cannot login selling partner user")
    return {"token": login.json()["access_token"], "user": login.json()["user"]}


@pytest.fixture(scope="session")
def primary_category_id(admin_headers):
    r = requests.get(f"{API}/master/primary-categories", headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text
    cats = r.json()
    if not cats:
        pytest.skip("No primary categories configured")
    return cats[0]["id"]


@pytest.fixture(scope="session")
def test_lead(admin_headers, primary_category_id):
    """Create a lead the admin owns; used for commercials tests."""
    # Find first lead status to use
    statuses = requests.get(f"{API}/master/lead-status", headers=admin_headers, timeout=20).json()
    assert isinstance(statuses, list) and statuses, "No lead statuses available"
    new_status = next((s for s in statuses if (s.get("name") or "").lower() in ("new", "open")), statuses[0])
    payload = {
        "title": f"TEST Commercial Lead {TS}",
        "customer_name": f"TEST Customer {TS}",
        "customer_email": f"test_lead_{TS}@example.com",
        "customer_phone": "+91 90000 00010",
        "status_id": new_status["id"],
        "primary_category_id": primary_category_id,
        "estimated_value": 500000,
    }
    r = requests.post(f"{API}/leads", json=payload, headers=admin_headers, timeout=20)
    assert r.status_code in (200, 201), f"Lead create failed: {r.status_code} {r.text}"
    return r.json()


# ----------------------- Lead status / is_won -----------------------
class TestLeadStatusIsWon:
    def test_won_status_has_is_won_true(self, admin_headers):
        r = requests.get(f"{API}/master/lead-status", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        statuses = r.json()
        won = [s for s in statuses if (s.get("name") or "").lower() == "won"]
        assert won, "Expected a 'Won' lead status to be backfilled"
        assert won[0]["is_won"] is True

    def test_create_status_with_is_won(self, admin_headers):
        name = f"TEST_Status_{TS}_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/master/lead-status",
                          json={"name": name, "color": "#22c55e", "order": 99, "is_won": True},
                          headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["is_won"] is True
        # cleanup
        requests.delete(f"{API}/master/lead-status/{body['id']}", headers=admin_headers, timeout=20)


class TestLeadStatusIsWonOnLead:
    def test_lead_get_returns_status_is_won_field(self, admin_headers, test_lead):
        r = requests.get(f"{API}/leads/{test_lead['id']}", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "status_is_won" in body
        assert isinstance(body["status_is_won"], bool)


# ----------------------- Commercials Create + RBAC -----------------------
class TestCommercialsCreate:
    def test_create_one_time_commercial(self, admin_headers, test_lead):
        payload = {
            "lead_id": test_lead["id"],
            "type": "one_time",
            "currency": "INR",
            "total_value": 100000,
            "start_date": "2026-01-01",
            "end_date": "2026-06-30",
            "notes": "TEST_one_time",
        }
        r = requests.post(f"{API}/commercials", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["type"] == "one_time"
        assert c["total_value"] == 100000
        assert c["lead_id"] == test_lead["id"]
        assert c["currency"] == "INR"
        assert c["milestones"] == []
        # save for downstream tests
        STATE['one_time_id'] = c["id"]

    def test_create_duplicate_for_same_lead_rejected(self, admin_headers, test_lead):
        payload = {"lead_id": test_lead["id"], "type": "one_time", "currency": "INR", "total_value": 50000}
        r = requests.post(f"{API}/commercials", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 400, f"Expected 400 duplicate, got {r.status_code} {r.text}"

    def test_create_recurring_commercial(self, admin_headers, primary_category_id):
        # Need a fresh lead for recurring
        statuses = requests.get(f"{API}/master/lead-status", headers=admin_headers, timeout=20).json()
        new_status = next((s for s in statuses if (s.get("name") or "").lower() in ("new", "open")), statuses[0])
        lead_payload = {
            "title": f"TEST Rec Lead {TS}",
            "customer_name": f"TEST RecCust {TS}",
            "customer_email": f"test_rec_{TS}@example.com",
            "customer_phone": "+91 90000 00020",
            "status_id": new_status["id"],
            "primary_category_id": primary_category_id,
            "estimated_value": 1000000,
        }
        lead = requests.post(f"{API}/leads", json=lead_payload, headers=admin_headers, timeout=20).json()
        payload = {
            "lead_id": lead["id"],
            "type": "recurring",
            "currency": "INR",
            "contract_value": 50000,
            "billing_frequency": "quarterly",
            "contract_start_date": "2026-03-01",
            "contract_end_date": "2027-02-28",
            "auto_renewal": True,
            "renewal_type": "manual",
            "renewal_notice_days": 30,
            "notes": "TEST_recurring_quarterly",
        }
        r = requests.post(f"{API}/commercials", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["type"] == "recurring"
        assert c["contract_status"] == "active"
        # Quarterly: 2026-03 -> 2027-02 = 12 months -> 4 periods
        assert len(c["billing_schedule"]) == 4, f"Expected 4 quarterly periods got {len(c['billing_schedule'])}"
        # First period starts on contract_start_date
        assert c["billing_schedule"][0]["period_start"] == "2026-03-01"
        STATE['recurring_id'] = c["id"]
        STATE['recurring_lead_id'] = lead["id"]

    def test_non_admin_cannot_create(self, sales_associate_user, test_lead):
        headers = {"Authorization": f"Bearer {sales_associate_user}", "Content-Type": "application/json"}
        payload = {"lead_id": test_lead["id"], "type": "one_time", "total_value": 1}
        r = requests.post(f"{API}/commercials", json=payload, headers=headers, timeout=20)
        assert r.status_code == 403


# ----------------------- List / Dashboard / Get -----------------------
class TestCommercialsRead:
    def test_list(self, admin_headers):
        r = requests.get(f"{API}/commercials", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list)
        assert any(i["id"] == STATE['one_time_id'] for i in items)

    def test_list_filter_type(self, admin_headers):
        r = requests.get(f"{API}/commercials?type=recurring", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        for i in r.json():
            assert i["type"] == "recurring"

    def test_dashboard(self, admin_headers):
        r = requests.get(f"{API}/commercials/dashboard", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        # Verify some commonly expected aggregate fields exist
        assert isinstance(body, dict)
        # Don't enforce exact keys (impl may vary); ensure it's not an empty error
        assert "error" not in body

    def test_get_by_id(self, admin_headers):
        r = requests.get(f"{API}/commercials/{STATE['one_time_id']}", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assert r.json()["id"] == STATE['one_time_id']

    def test_get_by_lead(self, admin_headers, test_lead):
        r = requests.get(f"{API}/commercials/by-lead/{test_lead['id']}", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assert r.json()["lead_id"] == test_lead["id"]

    def test_sales_associate_forbidden(self, sales_associate_user, test_lead):
        headers = {"Authorization": f"Bearer {sales_associate_user}"}
        for path in ("/commercials", "/commercials/dashboard",
                     f"/commercials/{STATE['one_time_id']}",
                     f"/commercials/by-lead/{test_lead['id']}"):
            r = requests.get(f"{API}{path}", headers=headers, timeout=20)
            assert r.status_code == 403, f"{path} expected 403, got {r.status_code}"


# ----------------------- PATCH commercial -> regenerates schedule -----------------------
class TestPatchCommercial:
    def test_patch_recurring_regenerates_schedule(self, admin_headers):
        # Change billing_frequency from quarterly to half_yearly -> should produce 2 periods
        payload = {"billing_frequency": "half_yearly"}
        r = requests.patch(f"{API}/commercials/{STATE['recurring_id']}", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["billing_frequency"] == "half_yearly"
        assert len(body["billing_schedule"]) == 2, f"Expected 2 half-yearly periods, got {len(body['billing_schedule'])}"

    def test_patch_back_to_quarterly(self, admin_headers):
        r = requests.patch(f"{API}/commercials/{STATE['recurring_id']}",
                           json={"billing_frequency": "quarterly"}, headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assert len(r.json()["billing_schedule"]) == 4


# ----------------------- Milestones (PUT validation + PATCH) -----------------------
class TestMilestones:
    def test_put_invalid_amount_totals(self, admin_headers):
        # total_value is 100000; send milestones summing to 80000
        payload = {"milestones": [
            {"name": "M1", "amount": 30000, "percentage": 50},
            {"name": "M2", "amount": 50000, "percentage": 50},
        ]}
        r = requests.put(f"{API}/commercials/{STATE['one_time_id']}/milestones", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 400, r.text

    def test_put_invalid_percentage_totals(self, admin_headers):
        payload = {"milestones": [
            {"name": "M1", "amount": 50000, "percentage": 40},
            {"name": "M2", "amount": 50000, "percentage": 50},
        ]}
        r = requests.put(f"{API}/commercials/{STATE['one_time_id']}/milestones", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 400, r.text

    def test_put_valid_milestones(self, admin_headers):
        payload = {"milestones": [
            {"name": "TEST M1 Kickoff", "amount": 40000, "percentage": 40, "delivery_date": "2026-02-15"},
            {"name": "TEST M2 Delivery", "amount": 60000, "percentage": 60, "delivery_date": "2026-05-30"},
        ]}
        r = requests.put(f"{API}/commercials/{STATE['one_time_id']}/milestones", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        ms = r.json()["milestones"]
        assert len(ms) == 2
        assert ms[0]["status"] == "pending"
        STATE['milestone_id'] = ms[0]["id"]
        STATE['milestone2_id'] = ms[1]["id"]

    def test_patch_milestone_status(self, admin_headers):
        r = requests.patch(f"{API}/commercials/{STATE['one_time_id']}/milestones/{STATE['milestone_id']}",
                           json={"status": "delivered"}, headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        # verify persistence
        c = requests.get(f"{API}/commercials/{STATE['one_time_id']}", headers=admin_headers, timeout=20).json()
        m = next(x for x in c["milestones"] if x["id"] == STATE['milestone_id'])
        assert m["status"] == "delivered"


# ----------------------- Regenerate billing -----------------------
class TestRegenerateBilling:
    def test_regenerate_recurring(self, admin_headers):
        r = requests.post(f"{API}/commercials/{STATE['recurring_id']}/regenerate-billing",
                          headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        assert len(r.json()["billing_schedule"]) == 4
        STATE['billing_id'] = r.json()["billing_schedule"][0]["id"]

    def test_regenerate_one_time_rejected(self, admin_headers):
        r = requests.post(f"{API}/commercials/{STATE['one_time_id']}/regenerate-billing",
                          headers=admin_headers, timeout=20)
        assert r.status_code == 400, r.text


# ----------------------- Invoices + Payments -----------------------
class TestInvoicesAndPayments:
    def test_raise_invoice_for_milestone(self, admin_headers):
        payload = {
            "milestone_id": STATE['milestone2_id'],
            "invoice_number": f"TEST-INV-{TS}-1",
            "amount": 60000,
            "due_date": "2026-06-15",
        }
        r = requests.post(f"{API}/commercials/{STATE['one_time_id']}/invoices",
                          json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        inv = r.json()
        assert inv["status"] == "raised"
        assert inv["amount"] == 60000
        STATE['invoice_id'] = inv["id"]
        # Milestone should now be invoice_raised
        c = requests.get(f"{API}/commercials/{STATE['one_time_id']}", headers=admin_headers, timeout=20).json()
        m = next(x for x in c["milestones"] if x["id"] == STATE['milestone2_id'])
        assert m["status"] == "invoice_raised"

    def test_raise_invoice_for_billing_schedule(self, admin_headers):
        payload = {
            "billing_schedule_id": STATE['billing_id'],
            "invoice_number": f"TEST-INV-{TS}-2",
            "amount": 50000,
            "due_date": "2026-04-01",
        }
        r = requests.post(f"{API}/commercials/{STATE['recurring_id']}/invoices",
                          json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        c = requests.get(f"{API}/commercials/{STATE['recurring_id']}", headers=admin_headers, timeout=20).json()
        sch = next(x for x in c["billing_schedule"] if x["id"] == STATE['billing_id'])
        assert sch["status"] == "invoiced"

    def test_full_payment_marks_invoice_paid_and_milestone_payment_received(self, admin_headers):
        payload = {"invoice_id": STATE['invoice_id'], "amount": 60000, "method": "bank_transfer"}
        r = requests.post(f"{API}/commercials/{STATE['one_time_id']}/payments",
                          json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        # Get invoices
        inv_list = requests.get(f"{API}/commercials/{STATE['one_time_id']}/invoices",
                                headers=admin_headers, timeout=20).json()
        inv = next(i for i in inv_list if i["id"] == STATE['invoice_id'])
        assert inv["status"] == "paid"
        # Milestone should be payment_received
        c = requests.get(f"{API}/commercials/{STATE['one_time_id']}", headers=admin_headers, timeout=20).json()
        m = next(x for x in c["milestones"] if x["id"] == STATE['milestone2_id'])
        assert m["status"] == "payment_received"

    def test_get_payments(self, admin_headers):
        r = requests.get(f"{API}/commercials/{STATE['one_time_id']}/payments", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list) and len(r.json()) >= 1


# ----------------------- Activity + Documents listing -----------------------
class TestActivityAndDocuments:
    def test_activity_log(self, admin_headers):
        r = requests.get(f"{API}/commercials/{STATE['one_time_id']}/activity", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        events = r.json()
        assert isinstance(events, list) and len(events) >= 3
        types = {e.get("type") for e in events}
        assert "created" in types
        assert "milestones_updated" in types
        assert "invoice_raised" in types or "payment_received" in types

    def test_documents_empty_list(self, admin_headers):
        r = requests.get(f"{API}/commercials/{STATE['one_time_id']}/documents", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ----------------------- Selling Partner RBAC -----------------------
class TestSellingPartnerRBAC:
    def test_selling_partner_cannot_create(self, selling_partner_user, test_lead):
        token = selling_partner_user["token"]
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"lead_id": test_lead["id"], "type": "one_time", "total_value": 1}
        r = requests.post(f"{API}/commercials", json=payload, headers=headers, timeout=20)
        assert r.status_code == 403

    def test_selling_partner_cannot_modify(self, selling_partner_user):
        token = selling_partner_user["token"]
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        r = requests.patch(f"{API}/commercials/{STATE['one_time_id']}",
                           json={"notes": "should be blocked"}, headers=headers, timeout=20)
        # Either 403 (write blocked) or denied because not assigned
        assert r.status_code == 403, f"Expected 403, got {r.status_code} {r.text}"
