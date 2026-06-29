"""Phase 36.2 tests:
- Internal Task Categories CRUD + RBAC + seed
- Tax Rates CRUD + RBAC (read-public, write-internal) + seed
- Lead partner_commission_percent + partner_commission_amount
- Branded New Lead email (notification_logs html_body checks)
- @-mention in Customer Follow-Up notes
- @-mention in Commercial notes (delta-aware)
"""
import os
import time
import re
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://vyapaar-preview-1.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

ADMIN = ("admin@vyapaarnetwork.com", "admin123")
OPS = ("ops_test@meshora.com", "ops123456")
FIN = ("fin_test@meshora.com", "fin123456")
CUSTOMER = ("john@testco.com", "test123")


def _login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    if r.status_code != 200:
        return None
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="session")
def admin_token():
    t = _login(*ADMIN)
    assert t, "admin login failed"
    return t


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def customer_token():
    return _login(*CUSTOMER)


# =================== Internal Task Categories ===================
class TestInternalTaskCategories:
    def test_seed_returns_6(self, admin_headers):
        r = requests.get(f"{API}/internal-task-categories", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 6
        names = {i["name"] for i in items}
        for expected in {"Operations", "Partner coordination", "Sales associate", "Finance", "Onboarding", "Other"}:
            assert expected in names, f"missing seed: {expected}"
        # Operations is_default true
        ops = next(i for i in items if i["name"] == "Operations")
        assert ops["is_default"] is True

    def test_rbac_customer_forbidden(self, customer_token):
        if not customer_token:
            pytest.skip("customer login unavailable")
        h = {"Authorization": f"Bearer {customer_token}"}
        r = requests.get(f"{API}/internal-task-categories", headers=h, timeout=15)
        assert r.status_code == 403

    def test_create_update_delete_and_default_flip(self, admin_headers):
        name = f"TEST_Cat_{int(time.time())}"
        # create
        r = requests.post(f"{API}/internal-task-categories",
                          headers=admin_headers,
                          json={"name": name, "color": "#ff00ff", "is_default": True},
                          timeout=15)
        assert r.status_code == 200, r.text
        created = r.json()
        cid = created["id"]
        assert created["is_default"] is True

        # verify the previous Operations no longer default
        items = requests.get(f"{API}/internal-task-categories", headers=admin_headers, timeout=15).json()
        defaults = [i for i in items if i.get("is_default")]
        assert len(defaults) == 1 and defaults[0]["id"] == cid

        # duplicate name -> 400
        rdup = requests.post(f"{API}/internal-task-categories", headers=admin_headers,
                             json={"name": name}, timeout=15)
        assert rdup.status_code == 400

        # patch
        rp = requests.patch(f"{API}/internal-task-categories/{cid}",
                            headers=admin_headers, json={"color": "#123456"}, timeout=15)
        assert rp.status_code == 200
        assert rp.json()["color"] == "#123456"

        # delete (no usage -> hard delete)
        rd = requests.delete(f"{API}/internal-task-categories/{cid}", headers=admin_headers, timeout=15)
        assert rd.status_code == 200
        assert rd.json().get("deactivated") is False

        # restore Operations as default for cleanliness
        items2 = requests.get(f"{API}/internal-task-categories", headers=admin_headers, timeout=15).json()
        ops = next((i for i in items2 if i["name"] == "Operations"), None)
        if ops and not ops.get("is_default"):
            requests.patch(f"{API}/internal-task-categories/{ops['id']}", headers=admin_headers,
                           json={"is_default": True}, timeout=15)


# =================== Internal Tasks → category_id ===================
class TestInternalTasksCategoryFlow:
    def test_create_internal_task_with_category(self, admin_headers):
        # get categories
        cats = requests.get(f"{API}/internal-task-categories", headers=admin_headers, timeout=15).json()
        ops_cat = next(c for c in cats if c["name"] == "Operations")
        cid = ops_cat["id"]
        # find admin user id
        me = requests.get(f"{API}/auth/me", headers=admin_headers, timeout=15).json()
        admin_id = me.get("id") or me.get("user_id")
        title = f"TEST_IT_Phase362_{int(time.time())}"
        r = requests.post(f"{API}/internal-tasks", headers=admin_headers,
                          json={"title": title, "category_id": cid, "assigned_to": admin_id,
                                "priority": "medium"}, timeout=15)
        assert r.status_code in (200, 201), r.text
        task = r.json()
        assert task.get("category_id") == cid

        # list & verify denormalization
        rl = requests.get(f"{API}/internal-tasks", headers=admin_headers, timeout=15)
        assert rl.status_code == 200
        data = rl.json()
        rows = data.get("items") if isinstance(data, dict) else data
        # find created task
        row = next((x for x in rows if x.get("id") == task["id"]), None)
        assert row is not None
        assert row.get("category_name") == "Operations"
        assert row.get("category_color") == ops_cat["color"]

        # cleanup
        requests.delete(f"{API}/internal-tasks/{task['id']}", headers=admin_headers, timeout=15)


# =================== Tax rates ===================
class TestTaxRates:
    def test_seed_returns_5(self, admin_headers):
        r = requests.get(f"{API}/tax-rates", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        items = r.json()
        names = {i["name"] for i in items}
        for n in {"No tax", "GST 5%", "GST 12%", "GST 18%", "GST 28%"}:
            assert n in names
        notax = next(i for i in items if i["name"] == "No tax")
        assert notax["is_default"] is True
        assert notax["percent"] == 0.0

    def test_customer_can_read(self, customer_token):
        if not customer_token:
            pytest.skip("customer login unavailable")
        h = {"Authorization": f"Bearer {customer_token}"}
        r = requests.get(f"{API}/tax-rates", headers=h, timeout=15)
        assert r.status_code == 200
        assert len(r.json()) >= 5

    def test_customer_cannot_write(self, customer_token):
        if not customer_token:
            pytest.skip("customer login unavailable")
        h = {"Authorization": f"Bearer {customer_token}", "Content-Type": "application/json"}
        r = requests.post(f"{API}/tax-rates", headers=h, json={"name": "TEST_x", "percent": 1}, timeout=15)
        assert r.status_code == 403

    def test_create_patch_delete_and_default_flip(self, admin_headers):
        name = f"TEST_Tax_{int(time.time())}"
        r = requests.post(f"{API}/tax-rates", headers=admin_headers,
                          json={"name": name, "percent": 7.5, "is_default": True}, timeout=15)
        assert r.status_code == 200, r.text
        created = r.json()
        rid = created["id"]
        assert created["is_default"] is True
        # check the previous default flipped
        items = requests.get(f"{API}/tax-rates", headers=admin_headers, timeout=15).json()
        defaults = [i for i in items if i.get("is_default")]
        assert len(defaults) == 1 and defaults[0]["id"] == rid
        # patch
        rp = requests.patch(f"{API}/tax-rates/{rid}", headers=admin_headers,
                            json={"percent": 9.0}, timeout=15)
        assert rp.status_code == 200 and rp.json()["percent"] == 9.0
        # delete
        rd = requests.delete(f"{API}/tax-rates/{rid}", headers=admin_headers, timeout=15)
        assert rd.status_code == 200
        # restore "No tax" default
        items2 = requests.get(f"{API}/tax-rates", headers=admin_headers, timeout=15).json()
        notax = next((i for i in items2 if i["name"] == "No tax"), None)
        if notax and not notax.get("is_default"):
            requests.patch(f"{API}/tax-rates/{notax['id']}", headers=admin_headers,
                           json={"is_default": True}, timeout=15)


# =================== Lead partner commission ===================
class TestLeadPartnerCommission:
    def test_existing_leads_have_commission_fields(self, admin_headers):
        r = requests.get(f"{API}/leads", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        leads = r.json()
        assert len(leads) > 0
        for l in leads[:10]:
            assert "partner_commission_percent" in l, f"missing percent in {l.get('id')}"
            assert "partner_commission_amount" in l, f"missing amount in {l.get('id')}"
            pct = l["partner_commission_percent"]
            amt = l["partner_commission_amount"]
            dv = l.get("deal_value") or 0
            expected = round(float(dv) * float(pct) / 100.0, 2)
            assert abs(float(amt) - expected) < 0.01, f"lead {l.get('id')} amt={amt} expected={expected} dv={dv} pct={pct}"

    def test_update_lead_commission_recalcs(self, admin_headers):
        leads = requests.get(f"{API}/leads", headers=admin_headers, timeout=20).json()
        # prefer one with non-zero deal value
        target = next((l for l in leads if (l.get("deal_value") or 0) > 0), leads[0])
        lid = target["id"]
        dv = float(target.get("deal_value") or 0)
        orig_pct = target.get("partner_commission_percent", 10)

        # update percent → 30
        rp = requests.put(f"{API}/leads/{lid}", headers=admin_headers,
                          json={"partner_commission_percent": 30}, timeout=20)
        assert rp.status_code == 200, rp.text
        upd = rp.json()
        assert upd["partner_commission_percent"] == 30
        assert abs(float(upd["partner_commission_amount"]) - dv * 0.30) < 0.01

        # change deal_value only → amount recalcs with current (30)
        new_dv = dv + 10000
        rp2 = requests.put(f"{API}/leads/{lid}", headers=admin_headers,
                           json={"deal_value": new_dv}, timeout=20)
        assert rp2.status_code == 200
        upd2 = rp2.json()
        assert abs(float(upd2["partner_commission_amount"]) - new_dv * 0.30) < 0.01

        # revert
        requests.put(f"{API}/leads/{lid}", headers=admin_headers,
                     json={"partner_commission_percent": orig_pct, "deal_value": dv}, timeout=20)


# =================== Branded new-lead email ===================
class TestBrandedNewLeadEmail:
    def test_create_lead_generates_branded_email(self, admin_headers):
        # fetch a primary category
        cats = requests.get(f"{API}/lead-categories", headers=admin_headers, timeout=15)
        cat_id = None
        if cats.status_code == 200:
            data = cats.json()
            items = data if isinstance(data, list) else (data.get("items") or [])
            primaries = [c for c in items if not c.get("parent_id")]
            if primaries:
                cat_id = primaries[0]["id"]
        if not cat_id:
            # fallback — borrow from an existing lead
            leads0 = requests.get(f"{API}/leads", headers=admin_headers, timeout=15).json()
            cat_id = leads0[0].get("primary_category_id")
        assert cat_id, "no primary_category_id available"
        title = f"TEST_BrandedEmail_{int(time.time())}"
        payload = {
            "title": title,
            "customer_name": "Test Customer",
            "customer_email": f"branded_{int(time.time())}@test.com",
            "customer_phone": "9999999999",
            "deal_value": 50000,
            "partner_commission_percent": 20,
            "primary_category_id": cat_id,
        }
        r = requests.post(f"{API}/leads", headers=admin_headers, json=payload, timeout=20)
        assert r.status_code in (200, 201), r.text
        lead = r.json()
        lid = lead["id"]
        # give a moment for notification log
        time.sleep(2)
        # fetch via debug or direct mongo? Use a small read endpoint if exists; fallback to running a mongo query via backend's notif logs endpoint.
        # Try notification logs endpoint
        candidates = [
            f"{API}/admin/notification-logs?type=new_lead&limit=20",
            f"{API}/notification-logs?type=new_lead&limit=20",
        ]
        found = None
        for url in candidates:
            rr = requests.get(url, headers=admin_headers, timeout=15)
            if rr.status_code == 200:
                logs = rr.json()
                if isinstance(logs, dict):
                    logs = logs.get("items") or logs.get("logs") or []
                for log in logs:
                    if title in (log.get("subject") or "") or lid in (log.get("html_body") or ""):
                        found = log
                        break
                if found:
                    break
        if not found:
            # Direct mongo fallback via embedded asyncio call
            import asyncio
            from motor.motor_asyncio import AsyncIOMotorClient
            from dotenv import load_dotenv
            load_dotenv('/app/backend/.env')
            async def _fetch():
                c = AsyncIOMotorClient(os.environ['MONGO_URL'])
                d = c[os.environ['DB_NAME']]
                # body is not persisted in email_logs — we only check the subject is branded
                row = await d.email_logs.find_one({'subject': {'$regex': re.escape(title)}}, {'_id': 0})
                return row
            found = asyncio.run(_fetch())
        assert found is not None, "no new_lead email_log entry found"
        subject = found.get("subject") or ""
        assert "[Meshora]" in subject and "New lead" in subject, f"subject not branded: {subject}"

        # Validate the HTML renderer output directly (body is not persisted in email_logs)
        import sys
        sys.path.insert(0, '/app/backend')
        from services.zeptomail import _render_new_lead
        rendered = _render_new_lead({
            "lead_title": title,
            "lead_id": lid,
            "lead_url": f"{BASE_URL}/leads/{lid}",
            "customer_name": "Test Customer",
            "customer_email": payload["customer_email"],
            "customer_phone": "9999999999",
            "deal_value": 50000,
            "recipient_name": "Tester",
        })
        body = rendered.get("html") or ""
        assert "Meshora" in body, "html_body missing Meshora brand"
        assert title in body, "html_body missing lead title"
        assert f"/leads/{lid}" in body, "missing CTA href to lead detail"
        assert "Open in Meshora" in body, "missing CTA button text"
        # rows
        assert "Customer" in body and "Test Customer" in body
        # cleanup
        requests.delete(f"{API}/leads/{lid}", headers=admin_headers, timeout=15)


# =================== @-mention follow-up ===================
class TestFollowUpMention:
    def test_followup_mention_creates_notification(self, admin_headers):
        # find an ops user id
        users = requests.get(f"{API}/users", headers=admin_headers, timeout=15).json()
        if isinstance(users, dict):
            users = users.get("items") or users.get("users") or []
        ops_user = next((u for u in users if (u.get("email") or "") == OPS[0]), None)
        if not ops_user:
            pytest.skip("ops user not found")
        # get ops handle
        ops_handle = ops_user.get("username") or ops_user.get("handle") or (ops_user.get("email") or "").split("@")[0]

        leads = requests.get(f"{API}/leads", headers=admin_headers, timeout=20).json()
        lid = leads[0]["id"]

        # baseline notification count for ops user
        ops_id = ops_user.get("id") or ops_user.get("user_id")

        # login as ops to count own notifications
        ops_tok = _login(*OPS)
        oh = {"Authorization": f"Bearer {ops_tok}"}
        before = requests.get(f"{API}/notifications?type=lead_mention", headers=oh, timeout=15)
        before_count = len(before.json()) if before.status_code == 200 and isinstance(before.json(), list) else 0

        # post follow-up with mention
        note = f"Hey @{ops_handle} please check this customer TEST_{int(time.time())}"
        from datetime import datetime, timedelta, timezone as tz
        future = (datetime.now(tz.utc) + timedelta(days=1)).isoformat()
        r = requests.post(f"{API}/leads/{lid}/follow-ups", headers=admin_headers,
                          json={"notes": note, "scheduled_date": future,
                                "pending_with": "customer"}, timeout=15)
        assert r.status_code in (200, 201), r.text
        time.sleep(1.5)
        after = requests.get(f"{API}/notifications?type=lead_mention", headers=oh, timeout=15)
        assert after.status_code == 200
        after_count = len(after.json()) if isinstance(after.json(), list) else 0
        assert after_count > before_count, f"follow-up mention did not create lead_mention notification (before={before_count}, after={after_count})"


# =================== @-mention commercial delta ===================
class TestCommercialMentionDelta:
    def test_commercial_mention_delta(self, admin_headers):
        # find ops + finance users
        users = requests.get(f"{API}/users", headers=admin_headers, timeout=15).json()
        if isinstance(users, dict):
            users = users.get("items") or users.get("users") or []
        ops_user = next((u for u in users if (u.get("email") or "") == OPS[0]), None)
        fin_user = next((u for u in users if (u.get("email") or "") == FIN[0]), None)
        if not ops_user or not fin_user:
            pytest.skip("ops or finance user not found")
        ops_handle = ops_user.get("username") or ops_user.get("handle") or OPS[0].split("@")[0]
        fin_handle = fin_user.get("username") or fin_user.get("handle") or FIN[0].split("@")[0]

        # find any commercial
        comms = requests.get(f"{API}/commercials", headers=admin_headers, timeout=20).json()
        if not comms:
            pytest.skip("no commercials available")
        comm = comms[0]
        cid = comm["id"]
        # Reset notes so delta starts from a clean slate
        requests.patch(f"{API}/commercials/{cid}", headers=admin_headers,
                       json={"notes": ""}, timeout=20)
        time.sleep(0.5)

        # login as fin to count notifs
        fin_tok = _login(*FIN)
        fh = {"Authorization": f"Bearer {fin_tok}"}
        ops_tok = _login(*OPS)
        oh = {"Authorization": f"Bearer {ops_tok}"}

        def count(headers):
            r = requests.get(f"{API}/notifications?type=lead_mention", headers=headers, timeout=15)
            if r.status_code != 200:
                return 0
            d = r.json()
            return len(d) if isinstance(d, list) else 0

        fin_before = count(fh)
        ops_before = count(oh)

        marker = int(time.time())
        # 1) PATCH with @finance only
        notes1 = f"Hi @{fin_handle} please weigh in on the numbers TEST_{marker}"
        r1 = requests.patch(f"{API}/commercials/{cid}", headers=admin_headers,
                            json={"notes": notes1}, timeout=20)
        assert r1.status_code == 200, r1.text
        time.sleep(1.5)
        fin_after1 = count(fh)
        assert fin_after1 > fin_before, "finance was not pinged on first @mention"

        # 2) PATCH SAME notes plus extra trailing text (still @finance only) → no NEW finance notif
        notes2 = notes1 + " — also some extra context for the team."
        r2 = requests.patch(f"{API}/commercials/{cid}", headers=admin_headers,
                            json={"notes": notes2}, timeout=20)
        assert r2.status_code == 200
        time.sleep(1.5)
        fin_after2 = count(fh)
        assert fin_after2 == fin_after1, f"delta failed: finance pinged again ({fin_after1} -> {fin_after2})"

        # 3) Add fresh @ops handle → only ops gets pinged
        notes3 = notes2 + f" cc @{ops_handle} TEST_{marker}_ops"
        r3 = requests.patch(f"{API}/commercials/{cid}", headers=admin_headers,
                            json={"notes": notes3}, timeout=20)
        assert r3.status_code == 200
        time.sleep(1.5)
        ops_after = count(oh)
        fin_after3 = count(fh)
        assert ops_after > ops_before, "ops was not pinged on new @mention"
        assert fin_after3 == fin_after2, f"finance got an unexpected duplicate ping ({fin_after2} -> {fin_after3})"
