"""Phase 18 tests — VYAPAAR_OPS & VYAPAAR_FINANCE role behaviour.

Covers:
- New UserRole enum values accepted by POST /api/users
- auth/me flag derivation for both new roles
- VYAPAAR_OPS read + write to leads/companies/master
- VYAPAAR_FINANCE read-only outside commercials (403 on writes)
- VYAPAAR_FINANCE write access on /api/commercials/*
- Regression: existing super_admin / customer / selling_partner flows
- Existing commercials & leads endpoints still respond 200
"""

import os
import uuid
import pytest
import requests

# Read from frontend/.env so test runs even when REACT_APP_BACKEND_URL is not exported
def _load_backend_url():
    url = os.environ.get('REACT_APP_BACKEND_URL')
    if url:
        return url.rstrip('/')
    env_path = '/app/frontend/.env'
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip().rstrip('/')
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

# --- Credentials (from /app/memory/test_credentials.md) ---
ADMIN = {"email": "admin@vyapaarnetwork.com", "password": "admin123"}
OPS = {"email": "ops_test@meshora.com", "password": "ops123456"}
FIN = {"email": "fin_test@meshora.com", "password": "fin123456"}
CUSTOMER = {"email": "john@testco.com", "password": "test123"}


# ---------- Auth helpers ----------

def _login(creds: dict):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    return r


def _auth_headers(creds: dict):
    r = _login(creds)
    if r.status_code != 200:
        pytest.skip(f"Login failed for {creds['email']}: {r.status_code} {r.text}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin_headers():
    return _auth_headers(ADMIN)


@pytest.fixture(scope="module")
def ops_headers():
    return _auth_headers(OPS)


@pytest.fixture(scope="module")
def fin_headers():
    return _auth_headers(FIN)


@pytest.fixture(scope="module")
def customer_headers():
    return _auth_headers(CUSTOMER)


@pytest.fixture(scope="module")
def primary_category_id(admin_headers):
    r = requests.get(f"{API}/master/primary-categories", headers=admin_headers, timeout=10)
    if r.status_code != 200 or not r.json():
        pytest.skip("No primary categories")
    return r.json()[0]["id"]


@pytest.fixture(scope="module")
def first_company_id(admin_headers):
    r = requests.get(f"{API}/companies", headers=admin_headers, timeout=10)
    if r.status_code != 200 or not r.json():
        pytest.skip("No companies seeded")
    return r.json()[0]["id"]


def _lead_payload(company_id, category_id, name_suffix=""):
    return {
        "title": f"TEST Lead {name_suffix or uuid.uuid4().hex[:6]}",
        "customer_name": f"TEST {name_suffix or 'Customer'}",
        "customer_email": f"TEST_{uuid.uuid4().hex[:6]}@x.com",
        "customer_phone": "9999999999",
        "company_id": company_id,
        "primary_category_id": category_id,
        "deal_value": 25000,
        "vyapaar_percentage": 12,
    }


# ============================================================
# Login regressions
# ============================================================

class TestLoginRegression:
    def test_admin_login(self):
        r = _login(ADMIN)
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["role"] == "super_admin"
        assert "access_token" in body

    def test_customer_login(self):
        r = _login(CUSTOMER)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "customer"

    def test_ops_login(self):
        r = _login(OPS)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "vyapaar_ops"

    def test_finance_login(self):
        r = _login(FIN)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "vyapaar_finance"


# ============================================================
# auth/me flag derivation
# ============================================================

class TestAuthMeFlags:
    def test_ops_me_flags(self, ops_headers):
        r = requests.get(f"{API}/auth/me", headers=ops_headers, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["role"] == "vyapaar_ops"
        assert d["is_vyapaar_ops"] is True
        assert d["is_finance"] is False

    def test_finance_me_flags(self, fin_headers):
        r = requests.get(f"{API}/auth/me", headers=fin_headers, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["role"] == "vyapaar_finance"
        assert d["is_finance"] is True
        # Per server.py auth/me logic: is_vyapaar_ops is False for finance role
        assert d["is_vyapaar_ops"] is False


# ============================================================
# Creating users with new roles (admin only)
# ============================================================

class TestUserCreationWithNewRoles:
    def test_create_vyapaar_ops_user(self, admin_headers):
        suffix = uuid.uuid4().hex[:6]
        payload = {
            "email": f"TEST_ops_{suffix}@meshora.com",
            "name": "TEST Ops User",
            "password": "ops123456",
            "role": "vyapaar_ops",
        }
        r = requests.post(f"{API}/users", json=payload, headers=admin_headers, timeout=10)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert body["role"] == "vyapaar_ops"
        assert body["email"] == payload["email"]
        # Cleanup
        requests.delete(f"{API}/users/{body['id']}", headers=admin_headers, timeout=10)

    def test_create_vyapaar_finance_user(self, admin_headers):
        suffix = uuid.uuid4().hex[:6]
        payload = {
            "email": f"TEST_fin_{suffix}@meshora.com",
            "name": "TEST Fin User",
            "password": "fin123456",
            "role": "vyapaar_finance",
        }
        r = requests.post(f"{API}/users", json=payload, headers=admin_headers, timeout=10)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert body["role"] == "vyapaar_finance"
        # Cleanup
        requests.delete(f"{API}/users/{body['id']}", headers=admin_headers, timeout=10)

    def test_invalid_role_rejected(self, admin_headers):
        payload = {
            "email": f"TEST_bad_{uuid.uuid4().hex[:6]}@meshora.com",
            "name": "Bad",
            "password": "pwd123456",
            "role": "not_a_real_role",
        }
        r = requests.post(f"{API}/users", json=payload, headers=admin_headers, timeout=10)
        assert r.status_code in (400, 422)


# ============================================================
# Read access for OPS + FINANCE
# ============================================================

class TestReadAccess:
    @pytest.mark.parametrize("path", ["/companies", "/leads", "/users"])
    def test_ops_can_read(self, ops_headers, path):
        r = requests.get(f"{API}{path}", headers=ops_headers, timeout=15)
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
        assert isinstance(r.json(), list)

    @pytest.mark.parametrize("path", ["/companies", "/leads", "/users"])
    def test_finance_can_read(self, fin_headers, path):
        r = requests.get(f"{API}{path}", headers=fin_headers, timeout=15)
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
        assert isinstance(r.json(), list)


# ============================================================
# VYAPAAR_FINANCE write block (403 outside commercials)
# ============================================================

class TestFinanceWriteBlock:
    def test_finance_cannot_create_lead(self, fin_headers, first_company_id, primary_category_id):
        payload = _lead_payload(first_company_id, primary_category_id, "FinBlock")
        r = requests.post(f"{API}/leads", json=payload, headers=fin_headers, timeout=10)
        assert r.status_code == 403
        assert "read-only" in r.text.lower() or "finance" in r.text.lower()

    def test_finance_cannot_create_company(self, fin_headers):
        payload = {"name": f"TEST_FinBlockCo_{uuid.uuid4().hex[:6]}", "type": "customer"}
        r = requests.post(f"{API}/companies", json=payload, headers=fin_headers, timeout=10)
        assert r.status_code == 403

    def test_finance_cannot_write_master_category(self, fin_headers):
        payload = {"name": f"TEST_Cat_{uuid.uuid4().hex[:6]}"}
        r = requests.post(f"{API}/master/primary-categories", json=payload, headers=fin_headers, timeout=10)
        assert r.status_code == 403

    def test_finance_cannot_delete_user(self, fin_headers, admin_headers):
        # use admin's id as target — block fires before any logic anyway
        me = requests.get(f"{API}/auth/me", headers=admin_headers, timeout=10).json()
        r = requests.delete(f"{API}/users/{me['id']}", headers=fin_headers, timeout=10)
        assert r.status_code == 403


# ============================================================
# VYAPAAR_OPS can write to leads/companies/master
# ============================================================

class TestOpsWriteAccess:
    def test_ops_can_create_and_delete_lead(self, ops_headers, first_company_id, primary_category_id):
        payload = _lead_payload(first_company_id, primary_category_id, "Ops Lead")
        r = requests.post(f"{API}/leads", json=payload, headers=ops_headers, timeout=15)
        assert r.status_code in (200, 201), r.text
        lead = r.json()
        lead_id = lead["id"]

        # Verify via GET
        g = requests.get(f"{API}/leads/{lead_id}", headers=ops_headers, timeout=10)
        assert g.status_code == 200
        assert g.json()["id"] == lead_id

        # Cleanup
        d = requests.delete(f"{API}/leads/{lead_id}", headers=ops_headers, timeout=10)
        assert d.status_code in (200, 204)


# ============================================================
# VYAPAAR_FINANCE can write commercials
# ============================================================

class TestFinanceCommercialsWrite:
    def test_finance_can_list_commercials(self, fin_headers):
        r = requests.get(f"{API}/commercials", headers=fin_headers, timeout=15)
        assert r.status_code == 200

    def test_finance_can_access_dashboard(self, fin_headers):
        r = requests.get(f"{API}/commercials/dashboard", headers=fin_headers, timeout=15)
        assert r.status_code == 200

    def test_finance_can_post_invoice(self, fin_headers, admin_headers):
        # need an existing commercial
        comms = requests.get(f"{API}/commercials", headers=admin_headers, timeout=15).json()
        if not comms:
            pytest.skip("No commercials seeded")
        com_id = comms[0]["id"]
        payload = {
            "amount": 1000,
            "raised_date": "2026-01-01",
            "due_date": "2026-02-01",
        }
        r = requests.post(
            f"{API}/commercials/{com_id}/invoices",
            json=payload,
            headers=fin_headers,
            timeout=15,
        )
        # Allow either success (201/200) or business validation error (400)
        # but NEVER 403 — that would mean the finance write-allow rule broke.
        assert r.status_code != 403, f"Finance must be allowed to POST invoice; got 403: {r.text}"
        assert r.status_code in (200, 201, 400, 422), r.text


# ============================================================
# Existing commercials endpoints (regression)
# ============================================================

class TestCommercialsRegression:
    @pytest.mark.parametrize("path", [
        "/commercials",
        "/commercials/dashboard",
        "/commercials/analytics",
        "/commercials/kanban",
    ])
    def test_admin_commercials_endpoints(self, admin_headers, path):
        r = requests.get(f"{API}{path}", headers=admin_headers, timeout=20)
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"


# ============================================================
# Existing leads endpoints (regression)
# ============================================================

class TestLeadsRegression:
    def test_admin_lead_crud_flow(self, admin_headers, first_company_id, primary_category_id):
        payload = _lead_payload(first_company_id, primary_category_id, "Phase18")
        payload["customer_name"] = "TEST Phase18 Lead"
        c = requests.post(f"{API}/leads", json=payload, headers=admin_headers, timeout=10)
        assert c.status_code in (200, 201), c.text
        lead = c.json()
        lid = lead["id"]

        # GET
        g = requests.get(f"{API}/leads/{lid}", headers=admin_headers, timeout=10)
        assert g.status_code == 200

        # PUT
        u = requests.put(
            f"{API}/leads/{lid}",
            json={"customer_name": "TEST Phase18 Updated"},
            headers=admin_headers, timeout=10,
        )
        assert u.status_code == 200
        assert u.json()["customer_name"] == "TEST Phase18 Updated"

        # Add comment
        cm = requests.post(
            f"{API}/leads/{lid}/comments",
            json={"text": "TEST comment"},
            headers=admin_headers, timeout=10,
        )
        assert cm.status_code in (200, 201)

        # DELETE
        d = requests.delete(f"{API}/leads/{lid}", headers=admin_headers, timeout=10)
        assert d.status_code in (200, 204)

        # Verify gone
        g2 = requests.get(f"{API}/leads/{lid}", headers=admin_headers, timeout=10)
        assert g2.status_code == 404
