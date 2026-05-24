"""Phase 3 — AI suggestions, PDF invoices, Kanban view.

Endpoints under test:
- POST /api/commercials/ai/suggest-milestones (Gemini 3 Pro via emergentintegrations)
- GET  /api/commercials/{id}/ai/renewal-probability (heuristic)
- GET  /api/commercials/{id}/ai/payment-delay-risk (heuristic)
- GET  /api/commercials/kanban
- GET  /api/commercials/{id}/invoices/{inv_id}/pdf (reportlab)
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    # fall back to public preview URL (read from frontend/.env)
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
                break

ADMIN_EMAIL = "admin@vyapaarnetwork.com"
ADMIN_PASSWORD = "admin123"
CUSTOMER_EMAIL = "john@testco.com"
CUSTOMER_PASSWORD = "test123"


# -------- Auth helpers --------
def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def customer_token():
    try:
        return _login(CUSTOMER_EMAIL, CUSTOMER_PASSWORD)
    except AssertionError:
        pytest.skip("customer account not seeded")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def customer_headers(customer_token):
    return {"Authorization": f"Bearer {customer_token}"}


# -------- Seed helpers --------
@pytest.fixture(scope="module")
def seed_commercials(admin_headers):
    """Create a one_time commercial + a recurring commercial we control end-to-end."""
    # Fetch a primary_category and lead status
    rc = requests.get(f"{BASE_URL}/api/master/primary-categories", headers=admin_headers, timeout=20)
    assert rc.status_code == 200, rc.text
    cats = rc.json()
    if not cats:
        pytest.skip("No primary categories seeded")
    primary_category_id = cats[0]["id"]

    rs = requests.get(f"{BASE_URL}/api/master/lead-status", headers=admin_headers, timeout=20)
    assert rs.status_code == 200, rs.text
    statuses = rs.json()
    assert statuses
    status_id = next((x for x in statuses if (x.get("name") or "").lower() in ("new", "open")), statuses[0])["id"]

    lead_payload = {
        "title": f"TEST P3 Website Build {uuid.uuid4().hex[:6]}",
        "customer_name": "TEST P3 Customer",
        "customer_email": f"testp3+{uuid.uuid4().hex[:6]}@example.com",
        "customer_phone": "+91 9999999999",
        "status_id": status_id,
        "primary_category_id": primary_category_id,
        "deal_value": 200000,
    }
    rl = requests.post(f"{BASE_URL}/api/leads", json=lead_payload, headers=admin_headers, timeout=30)
    assert rl.status_code in (200, 201), f"lead create failed {rl.status_code} {rl.text}"
    lead_id = rl.json()["id"]

    # One-time commercial with one invoice
    one_time = {
        "lead_id": lead_id,
        "type": "one_time",
        "total_value": 200000,
        "currency": "INR",
        "start_date": "2026-01-01",
        "end_date": "2026-04-30",
        "milestones": [
            {"name": "Kickoff", "percentage": 50, "amount": 100000, "delivery_date": "2026-02-01"},
            {"name": "Final delivery", "percentage": 50, "amount": 100000, "delivery_date": "2026-04-30"},
        ],
    }
    rc1 = requests.post(f"{BASE_URL}/api/commercials", json=one_time, headers=admin_headers, timeout=30)
    assert rc1.status_code in (200, 201), f"one_time commercial create failed {rc1.status_code} {rc1.text}"
    one_time_id = rc1.json()["id"]

    # Raise an invoice on the one_time
    inv_payload = {
        "invoice_number": f"TEST-P3-INV-{uuid.uuid4().hex[:6].upper()}",
        "amount": 100000,
        "due_date": "2026-02-15",
        "notes": "Kickoff invoice (TEST P3)",
    }
    rinv = requests.post(
        f"{BASE_URL}/api/commercials/{one_time_id}/invoices",
        json=inv_payload,
        headers=admin_headers,
        timeout=30,
    )
    assert rinv.status_code in (200, 201), f"invoice create failed {rinv.status_code} {rinv.text}"
    invoice_id = rinv.json()["id"]

    # Recurring commercial (needs a separate lead — one commercial per lead)
    lead2_payload = {**lead_payload, "title": f"TEST P3 SaaS Subscription {uuid.uuid4().hex[:6]}", "customer_email": f"testp3rec+{uuid.uuid4().hex[:6]}@example.com"}
    rl2 = requests.post(f"{BASE_URL}/api/leads", json=lead2_payload, headers=admin_headers, timeout=30)
    assert rl2.status_code in (200, 201), f"lead2 create failed {rl2.status_code} {rl2.text}"
    lead2_id = rl2.json()["id"]

    recurring = {
        "lead_id": lead2_id,
        "type": "recurring",
        "total_value": 12000,
        "currency": "INR",
        "billing_frequency": "monthly",
        "billing_amount": 1000,
        "contract_start_date": "2025-01-01",
        "contract_end_date": "2026-12-31",
        "auto_renewal": True,
        "renewal_type": "auto",
        "contract_status": "active",
    }
    rc2 = requests.post(f"{BASE_URL}/api/commercials", json=recurring, headers=admin_headers, timeout=30)
    assert rc2.status_code in (200, 201), f"recurring create failed {rc2.status_code} {rc2.text}"
    recurring_id = rc2.json()["id"]

    return {
        "lead_id": lead_id,
        "one_time_id": one_time_id,
        "invoice_id": invoice_id,
        "recurring_id": recurring_id,
    }


# ==================== AI suggest-milestones ====================
class TestAiSuggestMilestones:
    def test_customer_forbidden(self, customer_headers):
        r = requests.post(
            f"{BASE_URL}/api/commercials/ai/suggest-milestones",
            json={"project_title": "x", "total_value": 100000},
            headers=customer_headers,
            timeout=30,
        )
        assert r.status_code == 403, f"customer should be forbidden, got {r.status_code}"

    def test_admin_success_percentages_sum_100(self, admin_headers):
        payload = {
            "project_title": "TEST P3 — AI suggested milestones",
            "description": "Build a B2B marketplace MVP: auth, lead pipeline, commercials, basic analytics.",
            "total_value": 500000,
            "start_date": "2026-02-01",
            "end_date": "2026-05-31",
            "currency": "INR",
        }
        r = requests.post(
            f"{BASE_URL}/api/commercials/ai/suggest-milestones",
            json=payload,
            headers=admin_headers,
            timeout=90,  # LLM call ~3-8s; allow head-room
        )
        # The endpoint may return 502 if the upstream LLM hiccups.
        if r.status_code == 502:
            pytest.skip(f"upstream LLM unavailable: {r.text}")
        assert r.status_code == 200, f"AI suggest failed {r.status_code}: {r.text}"
        data = r.json()
        assert "milestones" in data and isinstance(data["milestones"], list)
        assert len(data["milestones"]) >= 1
        assert data.get("model")  # model string surfaced

        total_pct = sum(m["percentage"] for m in data["milestones"])
        assert abs(total_pct - 100.0) <= 0.01, f"percentages must sum to 100 (+/-0.01), got {total_pct}"

        total_amt = sum(m["amount"] for m in data["milestones"])
        # Amounts roughly add up to total_value (rounding tolerance)
        assert abs(total_amt - payload["total_value"]) <= 50, f"amounts off: {total_amt} vs {payload['total_value']}"

        for m in data["milestones"]:
            assert "name" in m and "description" in m
            assert "percentage" in m and "amount" in m
            assert "delivery_offset_days" in m
            assert "delivery_date" in m  # may be None if no start_date provided


# ==================== AI renewal probability ====================
class TestAiRenewalProbability:
    def test_one_time_returns_400(self, admin_headers, seed_commercials):
        r = requests.get(
            f"{BASE_URL}/api/commercials/{seed_commercials['one_time_id']}/ai/renewal-probability",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 400, f"one_time should be 400, got {r.status_code}: {r.text}"

    def test_recurring_returns_score(self, admin_headers, seed_commercials):
        r = requests.get(
            f"{BASE_URL}/api/commercials/{seed_commercials['recurring_id']}/ai/renewal-probability",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200, f"recurring should be 200, got {r.status_code}: {r.text}"
        d = r.json()
        assert 0.0 <= d["probability"] <= 1.0
        assert d["band"] in ("low", "medium", "high")
        assert isinstance(d["factors"], list) and len(d["factors"]) >= 1
        assert "total_invoiced" in d and "total_paid" in d and "overdue_count" in d
        # Auto-renewal=True + renewal_type=auto -> probability should be high band
        assert d["probability"] >= 0.7, f"expected high probability with auto-renewal, got {d['probability']}"

    def test_nonexistent_returns_404(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/commercials/does-not-exist-{uuid.uuid4().hex[:6]}/ai/renewal-probability",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 404


# ==================== AI payment-delay-risk ====================
class TestAiPaymentDelayRisk:
    def test_one_time_with_invoice(self, admin_headers, seed_commercials):
        r = requests.get(
            f"{BASE_URL}/api/commercials/{seed_commercials['one_time_id']}/ai/payment-delay-risk",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        d = r.json()
        assert "avg_pay_lag_days" in d  # may be None if no paid invoices
        assert isinstance(d["invoices"], list)
        # Should include our raised invoice
        assert len(d["invoices"]) >= 1
        inv = d["invoices"][0]
        for k in ("invoice_id", "invoice_number", "outstanding", "due_date", "risk_score", "band", "factors"):
            assert k in inv, f"missing key {k} in invoice item: {inv}"
        assert 0.0 <= inv["risk_score"] <= 1.0
        assert inv["band"] in ("low", "medium", "high")

    def test_recurring_works(self, admin_headers, seed_commercials):
        r = requests.get(
            f"{BASE_URL}/api/commercials/{seed_commercials['recurring_id']}/ai/payment-delay-risk",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200  # works for both types
        d = r.json()
        assert isinstance(d["invoices"], list)


# ==================== Kanban ====================
class TestCommercialsKanban:
    def test_admin_gets_all_columns(self, admin_headers, seed_commercials):
        r = requests.get(f"{BASE_URL}/api/commercials/kanban", headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        d = r.json()
        keys = [c["key"] for c in d["columns"]]
        for required in ("active", "renewal_due", "renewed", "on_hold", "expired", "cancelled", "one_time"):
            assert required in keys, f"missing column '{required}' in {keys}"
        # Our seeded items should be present
        one_time_ids = [c["id"] for c in next(c for c in d["columns"] if c["key"] == "one_time")["items"]]
        assert seed_commercials["one_time_id"] in one_time_ids
        active_ids = [c["id"] for c in next(c for c in d["columns"] if c["key"] == "active")["items"]]
        assert seed_commercials["recurring_id"] in active_ids
        # Each column has label + color
        for c in d["columns"]:
            assert "label" in c and "color" in c and "items" in c

    def test_customer_forbidden(self, customer_headers):
        r = requests.get(f"{BASE_URL}/api/commercials/kanban", headers=customer_headers, timeout=30)
        assert r.status_code == 403, f"customer should be forbidden, got {r.status_code}"

    def test_kanban_does_not_collide_with_dynamic_id(self, admin_headers):
        """/commercials/kanban must NOT be parsed as /commercials/{id}."""
        r = requests.get(f"{BASE_URL}/api/commercials/kanban", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert "columns" in r.json(), "kanban path was hijacked by /commercials/{id}"


# ==================== PDF invoice ====================
class TestInvoicePdf:
    def test_admin_can_download(self, admin_headers, seed_commercials):
        r = requests.get(
            f"{BASE_URL}/api/commercials/{seed_commercials['one_time_id']}/invoices/{seed_commercials['invoice_id']}/pdf",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        ct = r.headers.get("Content-Type", "")
        assert ct.startswith("application/pdf"), f"bad content-type: {ct}"
        assert r.content[:4] == b"%PDF", f"missing %PDF magic, first bytes: {r.content[:8]!r}"
        assert len(r.content) > 1024, f"PDF too small: {len(r.content)} bytes"

    def test_customer_forbidden(self, customer_headers, seed_commercials):
        r = requests.get(
            f"{BASE_URL}/api/commercials/{seed_commercials['one_time_id']}/invoices/{seed_commercials['invoice_id']}/pdf",
            headers=customer_headers,
            timeout=30,
        )
        # Customer doesn't own this lead — expect 403 (or 404 if access guard blocks)
        assert r.status_code in (403, 404), f"customer should not access, got {r.status_code}"

    def test_nonexistent_invoice_404(self, admin_headers, seed_commercials):
        r = requests.get(
            f"{BASE_URL}/api/commercials/{seed_commercials['one_time_id']}/invoices/does-not-exist/pdf",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 404

    def test_nonexistent_commercial_404(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/commercials/does-not-exist/invoices/x/pdf",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 404


# ==================== Regression on Phase 1+2 ====================
class TestRegression:
    def test_list_commercials(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/commercials", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_dashboard(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/commercials/dashboard", headers=admin_headers, timeout=30)
        assert r.status_code == 200

    def test_analytics(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/commercials/analytics", headers=admin_headers, timeout=30)
        assert r.status_code == 200

    def test_get_commercial_by_id(self, admin_headers, seed_commercials):
        r = requests.get(
            f"{BASE_URL}/api/commercials/{seed_commercials['one_time_id']}",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200
        assert r.json()["id"] == seed_commercials["one_time_id"]

    def test_list_invoices(self, admin_headers, seed_commercials):
        r = requests.get(
            f"{BASE_URL}/api/commercials/{seed_commercials['one_time_id']}/invoices",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_run_renewal_scan(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/commercials/run-renewal-scan", headers=admin_headers, timeout=30)
        assert r.status_code == 200
