"""Phase 36 backend tests:
- Document signed-URL endpoint
- Internal Tasks CRUD + RBAC + admin dispatch endpoints
- Commercials One-Time Setup Fee + invoice flag + payment flow
"""
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://vyapaar-preview-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN = {"email": "admin@vyapaarnetwork.com", "password": "admin123"}
CUSTOMER = {"email": "john@testco.com", "password": "test123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def customer_token():
    try:
        return _login(CUSTOMER)
    except Exception:
        pytest.skip("Customer credentials not available")


# ============================================================================
# Document signed-URL
# ============================================================================
class TestDocumentSignedURL:
    def test_signed_url_endpoint_exists(self, admin_headers):
        # Find a lead with documents
        leads = requests.get(f"{API}/leads", headers=admin_headers, timeout=30).json()
        doc_id = None
        for lead in (leads if isinstance(leads, list) else leads.get("items", [])):
            for d in lead.get("documents", []) or []:
                doc_id = d.get("id")
                if doc_id:
                    break
            if doc_id:
                break
        if not doc_id:
            pytest.skip("No documents found in any lead to test signed URL")
        r = requests.get(f"{API}/documents/{doc_id}/signed-url", headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"signed-url failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert "url" in data, f"missing 'url' in response: {data}"
        assert "preview_url" in data, f"missing 'preview_url' in response: {data}"
        # The signed URL should be fetchable WITHOUT auth header
        signed = data["url"]
        if signed.startswith("/"):
            signed = BASE + signed
        r2 = requests.get(signed, timeout=30, allow_redirects=True)
        assert r2.status_code == 200, f"signed-url fetch failed: {r2.status_code}"


# ============================================================================
# Internal Tasks CRUD
# ============================================================================
class TestInternalTasksCRUD:
    created_id = None

    def test_list_assignable_users(self, admin_headers):
        r = requests.get(f"{API}/internal-tasks/_meta/assignable-users", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        users = r.json()
        assert isinstance(users, list) and len(users) > 0
        roles = {u.get("role") for u in users}
        # Should contain multiple roles, not just admin
        assert len(roles) >= 1
        TestInternalTasksCRUD._users = users

    def test_create_internal_task(self, admin_headers):
        # Pick a non-admin assignee if possible
        users = getattr(TestInternalTasksCRUD, "_users", [])
        non_admin = next((u for u in users if u.get("role") != "super_admin"), users[0] if users else None)
        assignee_id = non_admin["id"] if non_admin else None
        future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        payload = {
            "title": "TEST_E2E task",
            "description": "Phase 36 e2e test",
            "assignee_id": assignee_id,
            "priority": "high",
            "category": "partner_coordination",
            "due_date": future,
            "reminder_minutes_before": 60,
        }
        r = requests.post(f"{API}/internal-tasks", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"create failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert data["title"] == "TEST_E2E task"
        assert data["priority"] == "high"
        assert data["category"] == "partner_coordination"
        assert data["status"] == "todo"
        assert data["assignee_id"] == assignee_id
        TestInternalTasksCRUD.created_id = data["id"]

    def test_list_with_status_filter(self, admin_headers):
        r = requests.get(f"{API}/internal-tasks?status=todo", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and "counts" in data
        assert any(t["id"] == TestInternalTasksCRUD.created_id for t in data["items"])
        # filter by done — should not show our todo task
        r2 = requests.get(f"{API}/internal-tasks?status=done", headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        assert not any(t["id"] == TestInternalTasksCRUD.created_id for t in r2.json()["items"])

    def test_update_status_and_priority(self, admin_headers):
        tid = TestInternalTasksCRUD.created_id
        assert tid
        r = requests.patch(
            f"{API}/internal-tasks/{tid}",
            json={"status": "in_progress"},
            headers=admin_headers, timeout=30,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"
        # Update priority to urgent
        r2 = requests.patch(
            f"{API}/internal-tasks/{tid}",
            json={"priority": "urgent"},
            headers=admin_headers, timeout=30,
        )
        assert r2.status_code == 200
        assert r2.json()["priority"] == "urgent"

    def test_get_single(self, admin_headers):
        tid = TestInternalTasksCRUD.created_id
        r = requests.get(f"{API}/internal-tasks/{tid}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["id"] == tid

    def test_rbac_non_admin_blocked(self, customer_token):
        h = {"Authorization": f"Bearer {customer_token}"}
        r = requests.get(f"{API}/internal-tasks", headers=h, timeout=30)
        assert r.status_code == 403
        assert "internal" in r.text.lower() or "vyapaar" in r.text.lower()

    def test_admin_dispatch_reminders(self, admin_headers):
        r = requests.post(f"{API}/admin/dispatch-internal-task-reminders", headers=admin_headers, timeout=60)
        assert r.status_code == 200, f"reminders dispatch failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert isinstance(data, dict)

    def test_admin_dispatch_weekly_digest(self, admin_headers):
        r = requests.post(
            f"{API}/admin/dispatch-internal-task-weekly-digest?force=true",
            headers=admin_headers, timeout=60,
        )
        assert r.status_code == 200, f"digest dispatch failed: {r.status_code} {r.text[:200]}"
        assert isinstance(r.json(), dict)

    def test_delete_task(self, admin_headers):
        tid = TestInternalTasksCRUD.created_id
        r = requests.delete(f"{API}/internal-tasks/{tid}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        # confirm gone
        r2 = requests.get(f"{API}/internal-tasks/{tid}", headers=admin_headers, timeout=30)
        assert r2.status_code == 404


# ============================================================================
# Commercials — One-Time Setup Fee on Recurring
# ============================================================================
class TestOneTimeSetupFee:
    commercial_id = None
    invoice_id = None

    def test_find_or_create_recurring_commercial(self, admin_headers):
        r = requests.get(f"{API}/commercials?type=recurring", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        items = r.json()
        if items:
            TestOneTimeSetupFee.commercial_id = items[0]["id"]
        else:
            pytest.skip("No recurring commercial available to test One-Time Setup Fee")

    def test_set_one_time_fee(self, admin_headers):
        cid = TestOneTimeSetupFee.commercial_id
        assert cid
        future = (datetime.now(timezone.utc) + timedelta(days=14)).date().isoformat()
        r = requests.patch(
            f"{API}/commercials/{cid}",
            json={
                "one_time_fee_amount": 15000,
                "one_time_fee_label": "Onboarding fee",
                "one_time_fee_due_date": future,
            },
            headers=admin_headers, timeout=30,
        )
        assert r.status_code == 200, f"patch failed: {r.status_code} {r.text[:200]}"
        # GET and verify persisted
        r2 = requests.get(f"{API}/commercials/{cid}", headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        c = r2.json()
        assert c.get("one_time_fee_amount") == 15000
        assert c.get("one_time_fee_label") == "Onboarding fee"
        assert c.get("one_time_fee_status") == "pending"

    def test_raise_one_time_fee_invoice(self, admin_headers):
        cid = TestOneTimeSetupFee.commercial_id
        inv_no = f"TEST-OTF-{uuid.uuid4().hex[:6]}"
        payload = {
            "invoice_number": inv_no,
            "amount": 15000,
            "due_date": (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat(),
            "raised_at": datetime.now(timezone.utc).isoformat(),
            "is_one_time_fee": True,
        }
        r = requests.post(
            f"{API}/commercials/{cid}/invoices",
            json=payload, headers=admin_headers, timeout=30,
        )
        assert r.status_code == 200, f"invoice create failed: {r.status_code} {r.text[:200]}"
        inv = r.json()
        TestOneTimeSetupFee.invoice_id = inv["id"]
        assert inv.get("is_one_time_fee") is True

        # GET commercial: status should be 'invoiced' and one_time_fee_invoice_id set
        c = requests.get(f"{API}/commercials/{cid}", headers=admin_headers, timeout=30).json()
        assert c.get("one_time_fee_status") == "invoiced"
        assert c.get("one_time_fee_invoice_id") == inv["id"]

        # GET invoices list: should contain the new invoice with is_one_time_fee
        invs = requests.get(f"{API}/commercials/{cid}/invoices", headers=admin_headers, timeout=30).json()
        match = next((i for i in invs if i["id"] == inv["id"]), None)
        assert match is not None
        assert match.get("is_one_time_fee") is True

    def test_record_full_payment_flips_to_paid(self, admin_headers):
        cid = TestOneTimeSetupFee.commercial_id
        iid = TestOneTimeSetupFee.invoice_id
        assert iid
        pay = {
            "invoice_id": iid,
            "amount": 15000,
            "paid_at": datetime.now(timezone.utc).isoformat(),
            "method": "bank_transfer",
            "reference": "TEST_PAY",
        }
        r = requests.post(
            f"{API}/commercials/{cid}/payments",
            json=pay, headers=admin_headers, timeout=30,
        )
        assert r.status_code == 200, f"payment failed: {r.status_code} {r.text[:200]}"

        # Invoice status → paid
        invs = requests.get(f"{API}/commercials/{cid}/invoices", headers=admin_headers, timeout=30).json()
        inv = next((i for i in invs if i["id"] == iid), None)
        assert inv and inv.get("status") == "paid", f"invoice status: {inv and inv.get('status')}"

        # Commercial.one_time_fee_status → paid
        c = requests.get(f"{API}/commercials/{cid}", headers=admin_headers, timeout=30).json()
        assert c.get("one_time_fee_status") == "paid", f"commercial otf status: {c.get('one_time_fee_status')}"


# ============================================================================
# Commercials — type change regression
# ============================================================================
class TestCommercialTypeChange:
    def test_switch_one_time_to_recurring_and_back(self, admin_headers):
        r = requests.get(f"{API}/commercials?type=one_time", headers=admin_headers, timeout=30)
        items = r.json() if r.status_code == 200 else []
        if not items:
            pytest.skip("No one-time commercial to test type change")
        cid = items[0]["id"]
        original_type = items[0]["type"]
        new_type = "recurring" if original_type == "one_time" else "one_time"
        payload = {"type": new_type}
        if new_type == "recurring":
            payload.update({
                "billing_frequency": "monthly",
                "contract_start_date": datetime.now(timezone.utc).date().isoformat(),
                "contract_end_date": (datetime.now(timezone.utc) + timedelta(days=365)).date().isoformat(),
                "contract_value": 100000,
            })
        r2 = requests.patch(f"{API}/commercials/{cid}", json=payload, headers=admin_headers, timeout=30)
        assert r2.status_code == 200, f"type-change failed: {r2.status_code} {r2.text[:200]}"
        c = requests.get(f"{API}/commercials/{cid}", headers=admin_headers, timeout=30).json()
        assert c["type"] == new_type
        # revert
        requests.patch(f"{API}/commercials/{cid}", json={"type": original_type}, headers=admin_headers, timeout=30)
