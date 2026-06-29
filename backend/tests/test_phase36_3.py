"""Phase 36.3 backend tests — Referral Commission Levels master + Lead commission fields."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@vyapaarnetwork.com"
ADMIN_PASSWORD = "admin123"
CUSTOMER_EMAIL = "john@testco.com"
CUSTOMER_PASSWORD = "test123"

SEED_LEVELS = [
    ("Lead Scout", 10.0),
    ("Opportunity Builder", 20.0),
    ("Deal Enabler", 30.0),
    ("Growth Catalyst", 40.0),
    ("Strategic Partner", 50.0),
]


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def customer_token():
    r = requests.post(f"{API}/auth/login", json={"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD})
    if r.status_code != 200:
        pytest.skip("customer login failed")
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- referral-commissions master ----------
class TestReferralCommissionMaster:
    def test_seed_levels_present(self, admin_token):
        r = requests.get(f"{API}/referral-commissions", headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        items = r.json()
        names = {(i["name"], float(i["percent"])) for i in items}
        for name, pct in SEED_LEVELS:
            assert (name, pct) in names, f"Missing seed {name} {pct}%"

    def test_default_is_lead_scout(self, admin_token):
        r = requests.get(f"{API}/referral-commissions", headers=_auth(admin_token))
        defaults = [i for i in r.json() if i.get("is_default")]
        assert len(defaults) == 1
        assert defaults[0]["name"] == "Lead Scout"

    def test_customer_read_allowed(self, customer_token):
        # Read open to all logged-in users (per router comment)
        r = requests.get(f"{API}/referral-commissions", headers=_auth(customer_token))
        assert r.status_code == 200
        assert len(r.json()) >= 5

    def test_customer_write_forbidden(self, customer_token):
        r = requests.post(
            f"{API}/referral-commissions",
            json={"name": f"TEST_Cust_{int(time.time())}", "percent": 5},
            headers=_auth(customer_token),
        )
        assert r.status_code == 403

    def test_admin_crud_full_cycle(self, admin_token):
        name = f"TEST_Phase363_{int(time.time())}"
        # CREATE
        r = requests.post(
            f"{API}/referral-commissions",
            json={"name": name, "percent": 15.5, "meaning": "test row", "sort_order": 50},
            headers=_auth(admin_token),
        )
        assert r.status_code == 200, r.text
        created = r.json()
        rc_id = created["id"]
        assert created["name"] == name
        assert float(created["percent"]) == 15.5

        # GET (list, find it)
        r2 = requests.get(f"{API}/referral-commissions?include_inactive=true", headers=_auth(admin_token))
        assert any(x["id"] == rc_id for x in r2.json())

        # PATCH
        r3 = requests.patch(
            f"{API}/referral-commissions/{rc_id}",
            json={"percent": 17.0, "meaning": "updated"},
            headers=_auth(admin_token),
        )
        assert r3.status_code == 200, r3.text
        upd = r3.json()
        assert float(upd["percent"]) == 17.0
        assert upd["meaning"] == "updated"

        # DELETE (not in use → hard delete)
        r4 = requests.delete(f"{API}/referral-commissions/{rc_id}", headers=_auth(admin_token))
        assert r4.status_code == 200, r4.text
        body = r4.json()
        assert body["ok"] is True
        assert body["deactivated"] is False

        # Confirm gone
        r5 = requests.get(f"{API}/referral-commissions?include_inactive=true", headers=_auth(admin_token))
        assert not any(x["id"] == rc_id for x in r5.json())

    def test_duplicate_name_rejected(self, admin_token):
        r = requests.post(
            f"{API}/referral-commissions",
            json={"name": "Lead Scout", "percent": 99},
            headers=_auth(admin_token),
        )
        assert r.status_code == 400


# ---------- Lead commission fields ----------
class TestLeadCommissionFields:
    @pytest.fixture(scope="class")
    def levels(self, admin_token):
        return requests.get(f"{API}/referral-commissions", headers=_auth(admin_token)).json()

    @pytest.fixture(scope="class")
    def vyapaar_template_id(self, admin_token):
        r = requests.get(f"{API}/master/commission-templates", headers=_auth(admin_token))
        if r.status_code != 200 or not r.json():
            pytest.skip("No vyapaar commission templates available")
        return r.json()[0]["id"]

    @pytest.fixture(scope="class")
    def primary_category_id(self, admin_token):
        r = requests.get(f"{API}/master/primary-categories", headers=_auth(admin_token))
        if r.status_code == 200 and r.json():
            return r.json()[0]["id"]
        pytest.skip("No categories available")

    def _make_lead(self, admin_token, primary_category_id, extra=None):
        payload = {
            "title": f"TEST_Phase363_Lead_{int(time.time()*1000)}",
            "customer_name": "TEST Customer",
            "customer_email": f"test{int(time.time()*1000)}@x.com",
            "customer_phone": "9999999999",
            "deal_value": 100000,
            "primary_category_id": primary_category_id,
        }
        if extra:
            payload.update(extra)
        r = requests.post(f"{API}/leads", json=payload, headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        return r.json()

    def test_create_with_referral_commission_id(self, admin_token, levels, primary_category_id):
        opportunity_builder = next(l for l in levels if l["name"] == "Opportunity Builder")
        lead = self._make_lead(admin_token, primary_category_id, {"referral_commission_id": opportunity_builder["id"]})
        lead_id = lead["id"]

        # GET back
        r = requests.get(f"{API}/leads/{lead_id}", headers=_auth(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body.get("referral_commission_id") == opportunity_builder["id"]
        assert float(body.get("referral_commission_percent")) == 20.0
        # cleanup
        requests.delete(f"{API}/leads/{lead_id}", headers=_auth(admin_token))

    def test_create_with_vyapaar_template_id(self, admin_token, vyapaar_template_id, primary_category_id):
        lead = self._make_lead(admin_token, primary_category_id, {"vyapaar_commission_template_id": vyapaar_template_id})
        lead_id = lead["id"]
        r = requests.get(f"{API}/leads/{lead_id}", headers=_auth(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body.get("vyapaar_commission_template_id") == vyapaar_template_id
        requests.delete(f"{API}/leads/{lead_id}", headers=_auth(admin_token))

    def test_create_without_commission_defaults_to_lead_scout(self, admin_token, primary_category_id):
        lead = self._make_lead(admin_token, primary_category_id)
        lead_id = lead["id"]
        r = requests.get(f"{API}/leads/{lead_id}", headers=_auth(admin_token))
        body = r.json()
        # Default should be Lead Scout 10%
        assert float(body.get("referral_commission_percent") or 0) == 10.0
        requests.delete(f"{API}/leads/{lead_id}", headers=_auth(admin_token))

    def test_update_changes_referral_level(self, admin_token, levels, primary_category_id):
        lead = self._make_lead(admin_token, primary_category_id)
        lead_id = lead["id"]
        strategic = next(l for l in levels if l["name"] == "Strategic Partner")

        r = requests.put(
            f"{API}/leads/{lead_id}",
            json={"referral_commission_id": strategic["id"]},
            headers=_auth(admin_token),
        )
        assert r.status_code == 200, r.text

        r2 = requests.get(f"{API}/leads/{lead_id}", headers=_auth(admin_token))
        body = r2.json()
        assert body.get("referral_commission_id") == strategic["id"]
        assert float(body.get("referral_commission_percent")) == 50.0

        requests.delete(f"{API}/leads/{lead_id}", headers=_auth(admin_token))

    def test_update_vyapaar_template(self, admin_token, vyapaar_template_id, primary_category_id):
        lead = self._make_lead(admin_token, primary_category_id)
        lead_id = lead["id"]
        r = requests.put(
            f"{API}/leads/{lead_id}",
            json={"vyapaar_commission_template_id": vyapaar_template_id},
            headers=_auth(admin_token),
        )
        assert r.status_code == 200, r.text
        r2 = requests.get(f"{API}/leads/{lead_id}", headers=_auth(admin_token))
        assert r2.json().get("vyapaar_commission_template_id") == vyapaar_template_id
        requests.delete(f"{API}/leads/{lead_id}", headers=_auth(admin_token))


# ---------- Regression: existing endpoints still 200 ----------
class TestRegressionEndpoints:
    @pytest.mark.parametrize("path", [
        "/leads",
        "/master/lead-status",
        "/war-room/board",
        "/commercials",
        "/internal-tasks",
        "/tax-rates",
    ])
    def test_endpoint_200(self, admin_token, path):
        r = requests.get(f"{API}{path}", headers=_auth(admin_token))
        assert r.status_code == 200, f"{path} returned {r.status_code}: {r.text[:200]}"
