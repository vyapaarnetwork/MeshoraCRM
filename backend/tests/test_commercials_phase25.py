"""
Backend tests for Commercials Phase 2.5 — Reminder scan (in-app notifications).

Coverage:
- POST /api/commercials/run-reminder-scan
  - Returns expected shape for admin
  - 403 for customer
  - Idempotent dedup (re-run within 20h => notifications=0)
  - Construct: milestone due in 2d -> milestones_due>=1, notification emitted
  - Construct: invoice overdue 5d -> invoices_overdue>=1, notification emitted
  - Construct: recurring contract end in 10d, notice 30 -> renewals>=1, notification emitted
- Notification model
  - GET /api/notifications surfaces commercial_id for commercial_* notifications
  - New NotificationType values surface (commercial_milestone_due, commercial_billing_due,
    commercial_invoice_overdue, commercial_renewal_window)
- Regression: existing notification flows (new_lead) still fire — NotificationType extension safe
- Route ordering: /commercials/run-reminder-scan not eaten by /commercials/{commercial_id}
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
COMMERCIAL_TYPES = (
    "commercial_milestone_due",
    "commercial_billing_due",
    "commercial_invoice_overdue",
    "commercial_renewal_window",
)


# ----------------------- Fixtures -----------------------
@pytest.fixture(scope="session")
def admin_headers():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def admin_id(admin_headers):
    r = requests.get(f"{API}/auth/me", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    return r.json()["id"]


@pytest.fixture(scope="session")
def customer_token():
    r = requests.post(f"{API}/auth/login", json={"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Customer login failed: {r.text}")
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def primary_category_id(admin_headers):
    r = requests.get(f"{API}/master/primary-categories", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    cats = r.json()
    if not cats:
        pytest.skip("No primary categories")
    return cats[0]["id"]


@pytest.fixture(scope="session")
def new_status_id(admin_headers):
    r = requests.get(f"{API}/master/lead-status", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    statuses = r.json()
    assert statuses
    s = next((x for x in statuses if (x.get("name") or "").lower() in ("new", "open")), statuses[0])
    return s["id"]


def _make_lead(admin_headers, primary_category_id, new_status_id, label):
    payload = {
        "title": f"TEST P25 {label} {TS}-{uuid.uuid4().hex[:5]}",
        "customer_name": f"TEST P25 Cust {label}",
        "customer_email": f"test_p25_{label}_{TS}_{uuid.uuid4().hex[:4]}@example.com",
        "customer_phone": "+91 90000 90000",
        "status_id": new_status_id,
        "primary_category_id": primary_category_id,
        "deal_value": 50000,
    }
    r = requests.post(f"{API}/leads", json=payload, headers=admin_headers, timeout=20)
    assert r.status_code in (200, 201), r.text
    return r.json()


# ----------------------- 1. Shape / RBAC / route ordering -----------------------
class TestReminderScanBasics:
    def test_scan_returns_expected_shape_for_admin(self, admin_headers):
        r = requests.post(f"{API}/commercials/run-reminder-scan", headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        for key in (
            "milestones_due", "invoices_overdue", "billings_due", "renewals",
            "notifications", "scanned_commercials", "scanned_invoices",
        ):
            assert key in body, f"missing key {key} in {body}"
            assert isinstance(body[key], int)

    def test_scan_blocks_customer(self, customer_token):
        r = requests.post(
            f"{API}/commercials/run-reminder-scan",
            headers={"Authorization": f"Bearer {customer_token}"},
            timeout=30,
        )
        assert r.status_code == 403, f"Expected 403 for customer, got {r.status_code}: {r.text}"

    def test_route_ordering_not_eaten_by_dynamic(self, admin_headers):
        # If /commercials/{commercial_id} caught run-reminder-scan, we'd see 404 / different shape
        r = requests.post(f"{API}/commercials/run-reminder-scan", headers=admin_headers, timeout=60)
        assert r.status_code == 200
        assert "notifications" in r.json()


# ----------------------- 2. Construct: milestone due in 2 days -----------------------
class TestMilestoneDueScenario:
    @pytest.fixture(scope="class")
    def setup(self, admin_headers, primary_category_id, new_status_id):
        lead = _make_lead(admin_headers, primary_category_id, new_status_id, "milestone")
        today = datetime.now(timezone.utc).date()
        payload = {
            "lead_id": lead["id"],
            "type": "one_time",
            "currency": "INR",
            "total_value": 100000,
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
        }
        rc = requests.post(f"{API}/commercials", json=payload, headers=admin_headers, timeout=20)
        assert rc.status_code in (200, 201), rc.text
        commercial = rc.json()

        # Add a milestone delivery_date = today+2 via bulk milestones endpoint
        ms_payload = {
            "milestones": [
                {
                    "name": f"TEST P25 MS {TS}",
                    "description": "milestone for scan",
                    "delivery_date": (today + timedelta(days=2)).isoformat(),
                    "amount": 50000,
                    "percentage": 50,
                    "status": "pending",
                    "order": 1,
                },
                {
                    "name": f"TEST P25 MS2 {TS}",
                    "delivery_date": (today + timedelta(days=20)).isoformat(),
                    "amount": 50000,
                    "percentage": 50,
                    "status": "pending",
                    "order": 2,
                },
            ]
        }
        rms = requests.put(
            f"{API}/commercials/{commercial['id']}/milestones",
            json=ms_payload, headers=admin_headers, timeout=30,
        )
        assert rms.status_code in (200, 201), rms.text
        # PUT /milestones returns {milestones: [...]}. Fetch full commercial for the test.
        gc = requests.get(f"{API}/commercials/{commercial['id']}", headers=admin_headers, timeout=20)
        assert gc.status_code == 200, gc.text
        return {"lead": lead, "commercial": gc.json()}

    def test_milestone_due_emits_notification(self, admin_headers, admin_id, setup):
        commercial_id = setup["commercial"]["id"]
        # First scan
        r1 = requests.post(f"{API}/commercials/run-reminder-scan", headers=admin_headers, timeout=60)
        assert r1.status_code == 200, r1.text
        b1 = r1.json()
        assert b1["milestones_due"] >= 1
        # Admin should have a commercial_milestone_due notification for THIS commercial
        rn = requests.get(f"{API}/notifications", headers=admin_headers, timeout=20)
        assert rn.status_code == 200
        notifs = rn.json()
        match = [n for n in notifs
                 if n.get("type") == "commercial_milestone_due"
                 and n.get("commercial_id") == commercial_id]
        assert match, f"No commercial_milestone_due notification with commercial_id={commercial_id}"
        # Validate commercial_id field is surfaced on response model
        assert "commercial_id" in match[0]
        assert match[0]["commercial_id"] == commercial_id

    def test_milestone_due_idempotent_second_scan(self, admin_headers, setup):
        # Run-reminder-scan a second time -> notifications=0 (dedup within 20h)
        r2 = requests.post(f"{API}/commercials/run-reminder-scan", headers=admin_headers, timeout=60)
        assert r2.status_code == 200
        b2 = r2.json()
        # eligible items still counted; but no new notifications emitted
        assert b2["notifications"] == 0, f"Expected 0 new notifications on re-scan, got {b2}"


# ----------------------- 3. Construct: invoice overdue 5 days -----------------------
class TestInvoiceOverdueScenario:
    @pytest.fixture(scope="class")
    def setup(self, admin_headers, primary_category_id, new_status_id):
        lead = _make_lead(admin_headers, primary_category_id, new_status_id, "invoice")
        today = datetime.now(timezone.utc).date()
        payload = {
            "lead_id": lead["id"],
            "type": "one_time",
            "currency": "INR",
            "total_value": 80000,
            "start_date": (today - timedelta(days=30)).isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
        }
        rc = requests.post(f"{API}/commercials", json=payload, headers=admin_headers, timeout=20)
        assert rc.status_code in (200, 201), rc.text
        commercial = rc.json()

        inv_payload = {
            "invoice_number": f"TESTP25-INV-{TS}-{uuid.uuid4().hex[:4]}",
            "amount": 25000,
            "due_date": (today - timedelta(days=5)).isoformat(),
            "raised_at": (today - timedelta(days=10)).isoformat(),
            "notes": "TEST P25 overdue invoice",
        }
        ri = requests.post(
            f"{API}/commercials/{commercial['id']}/invoices",
            json=inv_payload, headers=admin_headers, timeout=20,
        )
        assert ri.status_code in (200, 201), ri.text
        return {"lead": lead, "commercial": commercial, "invoice": ri.json()}

    def test_invoice_overdue_emits_notification(self, admin_headers, setup):
        commercial_id = setup["commercial"]["id"]
        r1 = requests.post(f"{API}/commercials/run-reminder-scan", headers=admin_headers, timeout=60)
        assert r1.status_code == 200, r1.text
        b1 = r1.json()
        assert b1["invoices_overdue"] >= 1
        rn = requests.get(f"{API}/notifications", headers=admin_headers, timeout=20)
        assert rn.status_code == 200
        notifs = rn.json()
        match = [n for n in notifs
                 if n.get("type") == "commercial_invoice_overdue"
                 and n.get("commercial_id") == commercial_id]
        assert match, f"No commercial_invoice_overdue notification with commercial_id={commercial_id}"


# ----------------------- 4. Construct: recurring contract renewal window (end=today+10, notice=30) -----------------------
class TestRenewalWindowScenario:
    @pytest.fixture(scope="class")
    def setup(self, admin_headers, primary_category_id, new_status_id):
        lead = _make_lead(admin_headers, primary_category_id, new_status_id, "renewal")
        today = datetime.now(timezone.utc).date()
        payload = {
            "lead_id": lead["id"],
            "type": "recurring",
            "currency": "INR",
            "billing_frequency": "monthly",
            "contract_value": 12000,
            "contract_start_date": (today - timedelta(days=355)).isoformat(),
            "contract_end_date": (today + timedelta(days=10)).isoformat(),
            "renewal_type": "manual",
            "auto_renewal": False,
            "renewal_notice_days": 30,
        }
        rc = requests.post(f"{API}/commercials", json=payload, headers=admin_headers, timeout=20)
        assert rc.status_code in (200, 201), rc.text
        return {"lead": lead, "commercial": rc.json()}

    def test_renewal_window_emits_notification(self, admin_headers, setup):
        commercial_id = setup["commercial"]["id"]
        r1 = requests.post(f"{API}/commercials/run-reminder-scan", headers=admin_headers, timeout=60)
        assert r1.status_code == 200, r1.text
        b1 = r1.json()
        assert b1["renewals"] >= 1
        rn = requests.get(f"{API}/notifications", headers=admin_headers, timeout=20)
        assert rn.status_code == 200
        notifs = rn.json()
        match = [n for n in notifs
                 if n.get("type") == "commercial_renewal_window"
                 and n.get("commercial_id") == commercial_id]
        assert match, f"No commercial_renewal_window notification with commercial_id={commercial_id}"


# ----------------------- 5. Notifications schema & regression -----------------------
class TestNotificationSchema:
    def test_get_notifications_returns_commercial_id_field(self, admin_headers):
        r = requests.get(f"{API}/notifications", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        notifs = r.json()
        # commercial_id key MUST exist on commercial_* notifications
        commercial_notifs = [n for n in notifs if (n.get("type") or "").startswith("commercial_")]
        if not commercial_notifs:
            pytest.skip("No commercial_* notifications yet to inspect; earlier tests should have created some")
        for n in commercial_notifs:
            assert "commercial_id" in n
            assert n["commercial_id"], f"commercial_id should be set on commercial_* notification: {n}"

    def test_all_four_new_notification_types_appear(self, admin_headers):
        r = requests.get(f"{API}/notifications", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        types_seen = {n.get("type") for n in r.json()}
        missing = [t for t in COMMERCIAL_TYPES if t not in types_seen and t != "commercial_billing_due"]
        # commercial_billing_due is optional (we didn't construct a billing scenario here),
        # but the other three MUST exist from the constructed scenarios above.
        assert not missing, f"Expected notification types missing from /notifications: {missing}"


class TestRegressionExistingNotifications:
    def test_creating_lead_still_fires_new_lead_notification(self, admin_headers, primary_category_id, new_status_id):
        # Snapshot baseline (use high limit so older new_lead notifs aren't masked by other notifications)
        rn0 = requests.get(f"{API}/notifications?limit=200", headers=admin_headers, timeout=20)
        assert rn0.status_code == 200
        base_count = sum(1 for n in rn0.json() if n.get("type") == "new_lead")

        lead = _make_lead(admin_headers, primary_category_id, new_status_id, "regression")
        # small wait for notification doc to be inserted
        time.sleep(1)
        rn1 = requests.get(f"{API}/notifications?limit=200", headers=admin_headers, timeout=20)
        assert rn1.status_code == 200
        after_count = sum(1 for n in rn1.json() if n.get("type") == "new_lead")
        assert after_count >= base_count + 1, (
            f"new_lead notification did not fire after lead create (before={base_count}, after={after_count}); "
            "NotificationType extension may have broken existing flows"
        )
        # And that new_lead notification should have lead_id populated, commercial_id None
        new_lead_notifs = [n for n in rn1.json() if n.get("type") == "new_lead" and n.get("lead_id") == lead["id"]]
        if new_lead_notifs:
            assert new_lead_notifs[0].get("commercial_id") in (None, "")
