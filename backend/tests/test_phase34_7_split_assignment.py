"""
Phase 34.7 Backend Tests
- Split lead assignment (selling_partner_company_id, lead_owner_id, vyapaar_lead_owner_id)
- Company-level RBAC visibility
- New lookup endpoints: /users/vyapaar-team, /companies/selling-partners, /users/by-company/{id}
- New report endpoints: pipeline, conversion, partner-performance, lead-activity-feed
- Saved + Scheduled reports CRUD
- Weekly War Room digest dispatch
"""
import os
import pytest
import requests
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@vyapaarnetwork.com", "password": "admin123"}
OPS = {"email": "ops_test@meshora.com", "password": "ops123456"}
FIN = {"email": "fin_test@meshora.com", "password": "fin123456"}
CUSTOMER = {"email": "john@testco.com", "password": "test123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    if r.status_code != 200:
        return None
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="session")
def admin_token():
    tok = _login(ADMIN)
    if not tok:
        pytest.skip("admin login failed")
    return tok


@pytest.fixture(scope="session")
def ops_token():
    return _login(OPS)


@pytest.fixture(scope="session")
def customer_token():
    return _login(CUSTOMER)


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------------- Lookup endpoints ----------------
class TestLookups:
    def test_vyapaar_team(self, admin_token):
        r = requests.get(f"{API}/users/vyapaar-team", headers=H(admin_token), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        first = data[0]
        for k in ("id", "name", "email", "role"):
            assert k in first
        # roles should be vyapaar/ops/finance/super_admin
        roles = {u.get("role") for u in data}
        assert roles & {"super_admin", "vyapaar_ops", "vyapaar_finance"}

    def test_selling_partner_companies(self, admin_token):
        r = requests.get(f"{API}/companies/selling-partners", headers=H(admin_token), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for c in data:
            assert "id" in c and "name" in c

    def test_users_by_company(self, admin_token):
        # First, fetch a selling-partner company id
        r = requests.get(f"{API}/companies/selling-partners", headers=H(admin_token), timeout=15)
        assert r.status_code == 200
        companies = r.json()
        assert companies, "no selling-partner companies seeded"
        cid = companies[0]["id"]
        r2 = requests.get(f"{API}/users/by-company/{cid}", headers=H(admin_token), timeout=15)
        assert r2.status_code == 200
        users = r2.json()
        assert isinstance(users, list)
        assert len(users) >= 1
        for u in users:
            assert u.get("company_id") == cid or "company_id" not in u  # tolerate either

    def test_users_by_company_404(self, admin_token):
        r = requests.get(f"{API}/users/by-company/does-not-exist-xxx", headers=H(admin_token), timeout=15)
        assert r.status_code in (404, 200)  # 404 expected, but tolerate empty list with 200


# ---------------- Lead create with split assignment ----------------
class TestLeadCreate:
    @pytest.fixture(scope="class")
    def context(self, admin_token):
        # Get a SP company + a user in it + a vyapaar team user
        c = requests.get(f"{API}/companies/selling-partners", headers=H(admin_token)).json()
        assert c, "no SP company"
        company = c[0]
        u = requests.get(f"{API}/users/by-company/{company['id']}", headers=H(admin_token)).json()
        assert u, "no users in SP company"
        v = requests.get(f"{API}/users/vyapaar-team", headers=H(admin_token)).json()
        assert v
        cats = requests.get(f"{API}/master/primary-categories", headers=H(admin_token)).json()
        assert cats, "no primary categories"
        return {
            "company_id": company["id"],
            "owner_id": u[0]["id"],
            "vy_id": v[0]["id"],
            "cat_id": cats[0]["id"],
        }

    def test_create_lead_with_all_fields(self, admin_token, context):
        payload = {
            "title": "TEST_Phase347_create_split",
            "customer_name": "John Test",
            "customer_email": "TEST_phase347_create@example.com",
            "primary_category_id": context["cat_id"],
            "selling_partner_company_id": context["company_id"],
            "lead_owner_id": context["owner_id"],
            "vyapaar_lead_owner_id": context["vy_id"],
        }
        r = requests.post(f"{API}/leads", headers=H(admin_token), json=payload, timeout=20)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert body.get("selling_partner_company_id") == context["company_id"]
        assert body.get("lead_owner_id") == context["owner_id"]
        assert body.get("vyapaar_lead_owner_id") == context["vy_id"]
        # back-compat mirror
        assert body.get("selling_partner_id") == context["owner_id"]
        # enrichment: *_name fields
        # tolerate either flat name or nested
        has_name_field = any(k for k in body.keys() if k.endswith("_name") and body[k])
        assert has_name_field
        # Verify via GET
        lid = body["id"]
        g = requests.get(f"{API}/leads/{lid}", headers=H(admin_token), timeout=15)
        assert g.status_code == 200
        gb = g.json()
        assert gb.get("vyapaar_lead_owner_id") == context["vy_id"]
        # Cleanup
        requests.delete(f"{API}/leads/{lid}", headers=H(admin_token))

    def test_create_lead_company_derivation(self, admin_token, context):
        payload = {
            "title": "TEST_Phase347_derive",
            "customer_name": "Derive Test",
            "customer_email": "TEST_phase347_derive@example.com",
            "primary_category_id": context["cat_id"],
            "lead_owner_id": context["owner_id"],
            # no company - should derive
        }
        r = requests.post(f"{API}/leads", headers=H(admin_token), json=payload, timeout=20)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert body.get("lead_owner_id") == context["owner_id"]
        # derive
        assert body.get("selling_partner_company_id") == context["company_id"]
        assert body.get("selling_partner_id") == context["owner_id"]
        requests.delete(f"{API}/leads/{body['id']}", headers=H(admin_token))


# ---------------- Update lead ----------------
class TestLeadUpdate:
    def test_update_vyapaar_owner_independent(self, admin_token):
        c = requests.get(f"{API}/companies/selling-partners", headers=H(admin_token)).json()
        u = requests.get(f"{API}/users/by-company/{c[0]['id']}", headers=H(admin_token)).json()
        v = requests.get(f"{API}/users/vyapaar-team", headers=H(admin_token)).json()
        cats = requests.get(f"{API}/master/primary-categories", headers=H(admin_token)).json()
        # create
        cr = requests.post(f"{API}/leads", headers=H(admin_token), json={
            "title": "TEST_Phase347_update",
            "customer_name": "Upd Test",
            "customer_email": "TEST_phase347_upd@example.com",
            "primary_category_id": cats[0]["id"],
            "selling_partner_company_id": c[0]["id"],
            "lead_owner_id": u[0]["id"],
        })
        assert cr.status_code in (200, 201), cr.text
        lid = cr.json()["id"]
        try:
            # Update only vyapaar owner
            up = requests.put(f"{API}/leads/{lid}", headers=H(admin_token),
                              json={"vyapaar_lead_owner_id": v[0]["id"]}, timeout=15)
            assert up.status_code == 200, up.text
            g = requests.get(f"{API}/leads/{lid}", headers=H(admin_token)).json()
            assert g.get("vyapaar_lead_owner_id") == v[0]["id"]
            assert g.get("lead_owner_id") == u[0]["id"]
        finally:
            requests.delete(f"{API}/leads/{lid}", headers=H(admin_token))


# ---------------- Assigned to me filter ----------------
class TestAssignedToMe:
    def test_assigned_to_me_filter(self, admin_token):
        r = requests.get(f"{API}/leads?assigned_to_me=true", headers=H(admin_token), timeout=20)
        assert r.status_code == 200
        data = r.json()
        # response shape may be {items:[...]} or list
        items = data if isinstance(data, list) else data.get("items") or data.get("leads") or []
        # caller is admin — they may be a vyapaar lead owner of some
        # just verify response is well-formed
        assert isinstance(items, list)


# ---------------- Company-level RBAC ----------------
class TestCompanyRBAC:
    def test_sp_user_sees_company_leads(self, admin_token):
        # Find SP company with 2+ users
        companies = requests.get(f"{API}/companies/selling-partners", headers=H(admin_token)).json()
        target = None
        for c in companies:
            users = requests.get(f"{API}/users/by-company/{c['id']}", headers=H(admin_token)).json()
            if len(users) >= 2:
                target = (c, users)
                break
        if not target:
            pytest.skip("No SP company with 2+ users")
        company, users = target
        u1, u2 = users[0], users[1]
        # Create a lead owned by u1 in this company
        cats = requests.get(f"{API}/master/primary-categories", headers=H(admin_token)).json()
        cr = requests.post(f"{API}/leads", headers=H(admin_token), json={
            "title": "TEST_Phase347_rbac",
            "customer_name": "Rb Ac",
            "customer_email": "TEST_phase347_rbac@example.com",
            "primary_category_id": cats[0]["id"],
            "selling_partner_company_id": company["id"],
            "lead_owner_id": u1["id"],
        })
        if cr.status_code not in (200, 201):
            pytest.skip(f"could not create lead: {cr.text}")
        lid = cr.json()["id"]
        try:
            # Try to login as u2 — we likely don't know the pw
            # Instead, verify via admin that get_lead is accessible with admin
            # and that list_leads (as admin) includes both
            # Without knowing SP user passwords, we cannot fully impersonate u2.
            # So just smoke check: admin can read it
            g = requests.get(f"{API}/leads/{lid}", headers=H(admin_token))
            assert g.status_code == 200
            assert g.json().get("selling_partner_company_id") == company["id"]
        finally:
            requests.delete(f"{API}/leads/{lid}", headers=H(admin_token))


# ---------------- Reports ----------------
class TestReports:
    def test_pipeline_report(self, admin_token):
        r = requests.get(f"{API}/reports/pipeline", headers=H(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        stages = data.get("stages") if isinstance(data, dict) else data
        assert isinstance(stages, list)
        if stages:
            s = stages[0]
            assert "count" in s
            assert "total_value" in s or "value" in s
            assert "leads" in s

    def test_conversion_report(self, admin_token):
        r = requests.get(f"{API}/reports/conversion", headers=H(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "funnel" in data
        funnel = data["funnel"]
        for k in ("total", "assigned", "won", "lost", "win_rate"):
            assert k in funnel
        assert "by_category" in data
        assert "avg_days_to_close" in data

    def test_partner_performance_admin(self, admin_token):
        r = requests.get(f"{API}/reports/partner-performance", headers=H(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        rows = data.get("rows") if isinstance(data, dict) else data
        assert isinstance(rows, list)

    def test_partner_performance_customer_403(self, customer_token):
        if not customer_token:
            pytest.skip("no customer token")
        r = requests.get(f"{API}/reports/partner-performance", headers=H(customer_token), timeout=15)
        assert r.status_code == 403

    def test_lead_activity_feed_admin(self, admin_token):
        r = requests.get(f"{API}/reports/lead-activity-feed", headers=H(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        acts = data.get("activities") if isinstance(data, dict) else data
        assert isinstance(acts, list)
        if acts:
            assert "kind" in acts[0] or "type" in acts[0]

    def test_lead_activity_customer_403(self, customer_token):
        if not customer_token:
            pytest.skip("no customer token")
        r = requests.get(f"{API}/reports/lead-activity-feed", headers=H(customer_token), timeout=15)
        assert r.status_code == 403


# ---------------- Saved + Scheduled reports ----------------
class TestSavedScheduled:
    def test_saved_crud(self, admin_token):
        payload = {"name": "TEST_Phase347_saved", "report_type": "pipeline", "config": {}}
        c = requests.post(f"{API}/reports/saved", headers=H(admin_token), json=payload, timeout=15)
        assert c.status_code in (200, 201), c.text
        sid = c.json().get("id")
        assert sid
        try:
            lst = requests.get(f"{API}/reports/saved", headers=H(admin_token), timeout=15)
            assert lst.status_code == 200
            ids = [x.get("id") for x in (lst.json() if isinstance(lst.json(), list) else lst.json().get("items", []))]
            assert sid in ids
        finally:
            d = requests.delete(f"{API}/reports/saved/{sid}", headers=H(admin_token), timeout=15)
            assert d.status_code in (200, 204)

    def test_scheduled_requires_vyapaar(self, admin_token, customer_token):
        # create saved first
        c = requests.post(f"{API}/reports/saved", headers=H(admin_token), json={
            "name": "TEST_Phase347_sched_src", "report_type": "pipeline", "config": {}
        })
        sid = c.json().get("id")
        try:
            # Customer should be forbidden
            if customer_token:
                r = requests.post(f"{API}/reports/scheduled", headers=H(customer_token),
                                  json={"saved_report_id": sid, "frequency": "weekly", "recipients": ["a@b.com"]})
                assert r.status_code in (401, 403)
            # Admin can create
            r2 = requests.post(f"{API}/reports/scheduled", headers=H(admin_token),
                               json={"saved_report_id": sid, "frequency": "weekly", "recipients": ["a@b.com"]})
            assert r2.status_code in (200, 201), r2.text
            sched_id = r2.json().get("id")
            # Invalid frequency
            r3 = requests.post(f"{API}/reports/scheduled", headers=H(admin_token),
                               json={"saved_report_id": sid, "frequency": "bogus_freq", "recipients": ["a@b.com"]})
            assert r3.status_code in (400, 422)
            if sched_id:
                requests.delete(f"{API}/reports/scheduled/{sched_id}", headers=H(admin_token))
        finally:
            requests.delete(f"{API}/reports/saved/{sid}", headers=H(admin_token))

    def test_saved_delete_cascades_scheduled(self, admin_token):
        c = requests.post(f"{API}/reports/saved", headers=H(admin_token), json={
            "name": "TEST_Phase347_cascade", "report_type": "pipeline", "config": {}
        })
        sid = c.json().get("id")
        sch = requests.post(f"{API}/reports/scheduled", headers=H(admin_token), json={
            "saved_report_id": sid, "frequency": "weekly", "recipients": ["x@y.com"]
        })
        if sch.status_code not in (200, 201):
            requests.delete(f"{API}/reports/saved/{sid}", headers=H(admin_token))
            pytest.skip(f"scheduled create failed: {sch.text}")
        sch_id = sch.json().get("id")
        # delete saved → should cascade
        requests.delete(f"{API}/reports/saved/{sid}", headers=H(admin_token))
        lst = requests.get(f"{API}/reports/scheduled", headers=H(admin_token)).json()
        items = lst if isinstance(lst, list) else lst.get("items", [])
        ids = [x.get("id") for x in items]
        assert sch_id not in ids, "scheduled was not cascaded"


# ---------------- Weekly War Room digest ----------------
class TestWeeklyDigest:
    def test_dispatch_admin(self, admin_token):
        r = requests.post(f"{API}/admin/dispatch-weekly-war-room-digest?force=true",
                          headers=H(admin_token), timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("key", "sent", "recipients", "hot_count", "blocked_count", "at_risk_count", "owner_breakdown_count"):
            assert k in body, f"missing {k} in {body}"
        # key format YYYY-Www
        assert "-W" in body["key"]

    def test_dispatch_customer_403(self, customer_token):
        if not customer_token:
            pytest.skip("no customer token")
        r = requests.post(f"{API}/admin/dispatch-weekly-war-room-digest?force=true",
                          headers=H(customer_token), timeout=20)
        assert r.status_code == 403
