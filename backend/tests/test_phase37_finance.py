"""Phase 37 backend tests — Finance & Commission Management module.

Covers:
  - Commercial approval → Revenue Schedule auto-generation (One-Time, Recurring, Hybrid)
  - Revenue event CRUD
  - Lifecycle state machine transitions
  - Finance dashboard KPIs
  - RBAC (only super_admin / is_finance / is_vyapaar_ops can call finance endpoints)
  - Finance timeline audit log
"""
import os
import uuid
import pytest
import requests
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@vyapaarnetwork.com"
ADMIN_PASSWORD = "admin123"
CUSTOMER_EMAIL = "john@testco.com"
CUSTOMER_PASSWORD = "test123"


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


def _seed_won_lead(admin_token, *, title_suffix: str = ""):
    """Create a Won lead with template-driven commissions."""
    # Pull master data
    statuses = requests.get(f"{API}/master/lead-status", headers=_auth(admin_token)).json()
    cats = requests.get(f"{API}/master/primary-categories", headers=_auth(admin_token)).json()
    refs = requests.get(f"{API}/referral-commissions", headers=_auth(admin_token)).json()
    won = next((s for s in statuses if s.get('is_won') or 'won' in (s.get('name') or '').lower()), statuses[0])
    cat = cats[0]
    opp_builder = next((r for r in refs if r['name'] == 'Opportunity Builder'), refs[0])

    payload = {
        "title": f"TEST_Phase37 {title_suffix} {uuid.uuid4().hex[:6]}",
        "customer_name": "Phase37 Customer",
        "customer_email": f"phase37-{uuid.uuid4().hex[:6]}@example.com",
        "customer_phone": "9999999999",
        "primary_category_id": cat['id'],
        "deal_value": 100000,
        "commission_override": 15.0,
        "referral_commission_id": opp_builder['id'],
        "status_id": won['id'],
    }
    r = requests.post(f"{API}/leads", json=payload, headers=_auth(admin_token))
    assert r.status_code in (200, 201), r.text
    return r.json()


def _ensure_no_existing_commercial(admin_token, lead_id):
    """Delete any existing commercial on this lead so we can create fresh."""
    coms = requests.get(f"{API}/commercials", headers=_auth(admin_token)).json()
    for c in coms:
        if c.get('lead_id') == lead_id:
            requests.delete(f"{API}/commercials/{c['id']}", headers=_auth(admin_token))


# =====================================================================
# Scenario A — One-Time Commercial with milestones
# =====================================================================
class TestOneTimeFlow:
    @pytest.fixture(scope="class")
    def setup_one_time(self, admin_token):
        lead = _seed_won_lead(admin_token, title_suffix="onetime")
        _ensure_no_existing_commercial(admin_token, lead['id'])
        # Create One-Time commercial
        r = requests.post(f"{API}/commercials", json={
            "lead_id": lead['id'],
            "type": "one_time",
            "total_value": 100000,
            "start_date": "2026-03-01",
            "end_date": "2026-06-30",
        }, headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        commercial = r.json()
        # Add 2 milestones (50k each)
        r = requests.put(f"{API}/commercials/{commercial['id']}/milestones", json={
            "milestones": [
                {"name": "Kickoff", "amount": 50000, "percentage": 50, "delivery_date": "2026-03-15", "invoice_due_date": "2026-03-20"},
                {"name": "Go-Live", "amount": 50000, "percentage": 50, "delivery_date": "2026-06-15", "invoice_due_date": "2026-06-20"},
            ],
        }, headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        return {"lead": lead, "commercial": commercial}

    def test_approve_generates_events_per_milestone(self, admin_token, setup_one_time):
        cid = setup_one_time['commercial']['id']
        r = requests.post(f"{API}/commercials/{cid}/approve", headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body['generated'] is True
        assert len(body['events']) == 2
        events = body['events']
        names = [e['name'] for e in events]
        assert "Kickoff" in names
        assert "Go-Live" in names
        for e in events:
            assert e['revenue_type'] == 'milestone'
            assert e['expected_amount'] == 50000
            # Vyapaar 15% of 50k = 7500
            assert e['vyapaar_amount'] == 7500.0
            # Opportunity Builder 20% of 7500 = 1500
            assert e['referral_amount'] == 1500.0
            # Net = 6000
            assert e['net_revenue'] == 6000.0
            assert e['lifecycle_status'] == 'created'

    def test_approve_idempotent(self, admin_token, setup_one_time):
        cid = setup_one_time['commercial']['id']
        r = requests.post(f"{API}/commercials/{cid}/approve", headers=_auth(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body['generated'] is False
        assert len(body['events']) == 2

    def test_list_events_by_commercial(self, admin_token, setup_one_time):
        cid = setup_one_time['commercial']['id']
        r = requests.get(f"{API}/commercials/{cid}/revenue-events", headers=_auth(admin_token))
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_lifecycle_state_machine(self, admin_token, setup_one_time):
        cid = setup_one_time['commercial']['id']
        events = requests.get(f"{API}/commercials/{cid}/revenue-events", headers=_auth(admin_token)).json()
        ev = events[0]
        eid = ev['id']
        # created → ready_for_invoice
        r = requests.post(f"{API}/finance/revenue-events/{eid}/transitions/mark_ready_for_invoice", json={"note": "ready"}, headers=_auth(admin_token))
        assert r.status_code == 200 and r.json()['lifecycle_status'] == 'ready_for_invoice'
        # → invoice_raised (auto-stamps invoice_date + raised_by)
        r = requests.post(f"{API}/finance/revenue-events/{eid}/transitions/mark_invoice_raised", headers=_auth(admin_token))
        body = r.json()
        assert body['lifecycle_status'] == 'invoice_raised'
        assert body['invoice_date'] is not None
        assert body['invoice_raised_by_name'] is not None
        # → invoice_sent → awaiting_payment → payment_received
        for action in ('mark_invoice_sent', 'mark_awaiting_payment', 'mark_payment_received'):
            r = requests.post(f"{API}/finance/revenue-events/{eid}/transitions/{action}", headers=_auth(admin_token))
            assert r.status_code == 200, f"{action} → {r.text}"
        body = r.json()
        assert body['lifecycle_status'] == 'payment_received'
        # Auto-stamp: amount_received = expected, outstanding = 0, payment_date set
        assert body['amount_received'] == 50000
        assert body['outstanding_balance'] == 0
        assert body['payment_date'] is not None
        # → referral_payable (has referral partner? Lead has Opportunity Builder ref-pct=20)
        r = requests.post(f"{API}/finance/revenue-events/{eid}/transitions/mark_referral_payable", headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        # → referral_paid → closed
        r = requests.post(f"{API}/finance/revenue-events/{eid}/transitions/mark_referral_paid", headers=_auth(admin_token))
        assert r.json()['lifecycle_status'] == 'referral_paid'
        r = requests.post(f"{API}/finance/revenue-events/{eid}/transitions/close", headers=_auth(admin_token))
        assert r.json()['lifecycle_status'] == 'closed'

    def test_invalid_transition_rejected(self, admin_token, setup_one_time):
        cid = setup_one_time['commercial']['id']
        events = requests.get(f"{API}/commercials/{cid}/revenue-events", headers=_auth(admin_token)).json()
        ev = next(e for e in events if e['lifecycle_status'] == 'created')
        # Cannot jump from created → payment_received
        r = requests.post(f"{API}/finance/revenue-events/{ev['id']}/transitions/mark_payment_received", headers=_auth(admin_token))
        assert r.status_code == 400

    def test_event_update_recomputes_amounts(self, admin_token, setup_one_time):
        cid = setup_one_time['commercial']['id']
        events = requests.get(f"{API}/commercials/{cid}/revenue-events", headers=_auth(admin_token)).json()
        ev = next(e for e in events if e['lifecycle_status'] == 'created')
        # Change expected_amount → vyapaar/referral/net recompute
        r = requests.patch(f"{API}/finance/revenue-events/{ev['id']}", json={"expected_amount": 80000}, headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body['expected_amount'] == 80000
        assert body['vyapaar_amount'] == 12000.0  # 15% of 80k
        assert body['referral_amount'] == 2400.0  # 20% of 12k
        assert body['net_revenue'] == 9600.0

    def test_event_timeline(self, admin_token, setup_one_time):
        cid = setup_one_time['commercial']['id']
        events = requests.get(f"{API}/commercials/{cid}/revenue-events", headers=_auth(admin_token)).json()
        # The closed event has the longest timeline
        closed = next(e for e in events if e['lifecycle_status'] == 'closed')
        r = requests.get(f"{API}/finance/revenue-events/{closed['id']}/timeline", headers=_auth(admin_token))
        assert r.status_code == 200
        rows = r.json()
        actions = [row['action'] for row in rows]
        # Should include all the transitions + the original commercial approval
        assert any('transition.' in a for a in actions)
        assert 'commercial_approved' in actions


# =====================================================================
# Scenario B — Recurring Commercial (3-month monthly contract)
# =====================================================================
class TestRecurringFlow:
    @pytest.fixture(scope="class")
    def setup_recurring(self, admin_token):
        lead = _seed_won_lead(admin_token, title_suffix="recurring")
        _ensure_no_existing_commercial(admin_token, lead['id'])
        r = requests.post(f"{API}/commercials", json={
            "lead_id": lead['id'],
            "type": "recurring",
            "contract_value": 50000,
            "billing_frequency": "monthly",
            "contract_start_date": "2026-03-01",
            "contract_end_date": "2026-05-31",
        }, headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        return {"lead": lead, "commercial": r.json()}

    def test_recurring_approve_generates_3_monthly_events(self, admin_token, setup_recurring):
        cid = setup_recurring['commercial']['id']
        r = requests.post(f"{API}/commercials/{cid}/approve", headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        events = r.json()['events']
        assert len(events) == 3
        for e in events:
            assert e['revenue_type'] == 'monthly'
            assert e['expected_amount'] == 50000

    def test_recurring_deal_type_recorded_on_commercial(self, admin_token, setup_recurring):
        cid = setup_recurring['commercial']['id']
        r = requests.get(f"{API}/commercials", headers=_auth(admin_token))
        c = next(c for c in r.json() if c['id'] == cid)
        assert c.get('approval_status') == 'approved'
        assert c.get('deal_type') == 'recurring'


# =====================================================================
# Scenario C — Hybrid (Recurring + One-Time setup fee)
# =====================================================================
class TestHybridFlow:
    def test_hybrid_generates_setup_plus_recurring(self, admin_token):
        lead = _seed_won_lead(admin_token, title_suffix="hybrid")
        _ensure_no_existing_commercial(admin_token, lead['id'])
        r = requests.post(f"{API}/commercials", json={
            "lead_id": lead['id'],
            "type": "recurring",
            "contract_value": 25000,
            "billing_frequency": "quarterly",
            "contract_start_date": "2026-04-01",
            "contract_end_date": "2026-09-30",
            "one_time_fee_amount": 100000,
            "one_time_fee_label": "Implementation",
            "one_time_fee_due_date": "2026-04-01",
        }, headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        commercial = r.json()
        cid = commercial['id']
        r = requests.post(f"{API}/commercials/{cid}/approve", headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        events = r.json()['events']
        # 1 setup + 2 quarterly events
        assert len(events) >= 3
        setup_event = next(e for e in events if e['source_kind'] == 'one_time_fee')
        assert setup_event['name'] == 'Implementation'
        assert setup_event['expected_amount'] == 100000
        assert setup_event['revenue_type'] == 'one_time'
        recurring_events = [e for e in events if e['source_kind'] == 'billing_schedule']
        assert len(recurring_events) >= 2
        # Verify deal_type derived as hybrid
        coms = requests.get(f"{API}/commercials", headers=_auth(admin_token)).json()
        c = next(c for c in coms if c['id'] == cid)
        assert c.get('deal_type') == 'hybrid'


# =====================================================================
# Scenario D — Dashboard & filtering
# =====================================================================
class TestDashboardAndFilters:
    def test_finance_dashboard_returns_kpi_shape(self, admin_token):
        r = requests.get(f"{API}/finance/dashboard", headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("receivables", "payables", "revenue", "operations", "as_of"):
            assert key in body
        for k in ("total_commission_receivable", "invoices_pending_count", "collections_pending_amount", "overdue_collections_amount"):
            assert k in body['receivables']
        for k in ("referral_payable_amount", "referral_pending_count"):
            assert k in body['payables']
        for k in ("gross_revenue_realised", "vyapaar_net_revenue_realised", "recurring_revenue_open", "expected_revenue_this_month"):
            assert k in body['revenue']

    def test_list_events_filter_by_lifecycle(self, admin_token):
        r = requests.get(f"{API}/finance/revenue-events?lifecycle_status=created", headers=_auth(admin_token))
        assert r.status_code == 200
        for e in r.json():
            assert e['lifecycle_status'] == 'created'

    def test_list_events_filter_by_revenue_type(self, admin_token):
        r = requests.get(f"{API}/finance/revenue-events?revenue_type=milestone", headers=_auth(admin_token))
        assert r.status_code == 200
        for e in r.json():
            assert e['revenue_type'] == 'milestone'


# =====================================================================
# Scenario H — Monday Finance digest (Phase 39)
# =====================================================================
class TestFinanceDigest:
    def test_force_dispatch_returns_counts(self, admin_token):
        r = requests.post(f"{API}/admin/dispatch-finance-weekly-digest?force=true", headers=_auth(admin_token))
        # 503 if ZeptoMail not configured; 200 if configured. Both are acceptable.
        assert r.status_code in (200, 503), r.text
        if r.status_code == 200:
            body = r.json()
            assert 'overdue_count' in body
            assert 'stale_referral_count' in body
            assert 'renewals_count' in body
            assert 'attempted' in body
            assert 'key' in body and body['key'].startswith(str(datetime.now().year))

    def test_customer_blocked_from_dispatch(self, customer_token):
        r = requests.post(f"{API}/admin/dispatch-finance-weekly-digest?force=true", headers=_auth(customer_token))
        assert r.status_code == 403


# =====================================================================
# Scenario G — Auto-fire quick-setup when status flips to Won
# =====================================================================
class TestAutoFireOnWon:
    def test_status_flip_to_won_auto_generates_revenue_schedule(self, admin_token):
        # Seed a NOT-won lead first
        statuses = requests.get(f"{API}/master/lead-status", headers=_auth(admin_token)).json()
        cats = requests.get(f"{API}/master/primary-categories", headers=_auth(admin_token)).json()
        not_won = next((s for s in statuses if not s.get('is_won')), statuses[0])
        won = next((s for s in statuses if s.get('is_won')), None)
        if not won:
            pytest.skip("no won status seeded")
        cat = cats[0]
        payload = {
            "title": f"TEST_AutoFire_{uuid.uuid4().hex[:6]}",
            "customer_name": "Auto-fire Cust",
            "customer_email": f"autofire-{uuid.uuid4().hex[:6]}@example.com",
            "customer_phone": "9000000111",
            "primary_category_id": cat['id'],
            "deal_value": 50000,
            "commission_override": 15,
            "status_id": not_won['id'],
        }
        r = requests.post(f"{API}/leads", json=payload, headers=_auth(admin_token))
        assert r.status_code in (200, 201), r.text
        lead = r.json()
        # No commercial exists yet
        coms_before = requests.get(f"{API}/commercials", headers=_auth(admin_token)).json()
        assert not any(c.get('lead_id') == lead['id'] for c in coms_before)
        # Flip to Won
        r = requests.put(f"{API}/leads/{lead['id']}", json={"status_id": won['id']}, headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        # Now a commercial should exist and be approved
        import time
        time.sleep(0.5)
        coms_after = requests.get(f"{API}/commercials", headers=_auth(admin_token)).json()
        matching = [c for c in coms_after if c.get('lead_id') == lead['id']]
        assert len(matching) == 1, f"expected 1 auto-created commercial, got {len(matching)}"
        c = matching[0]
        assert c.get('approval_status') == 'approved'
        # Revenue events should be present
        evs = requests.get(f"{API}/commercials/{c['id']}/revenue-events", headers=_auth(admin_token)).json()
        assert len(evs) >= 1
        assert evs[0]['expected_amount'] == 50000


# =====================================================================
# Scenario F — Quick setup (one-click from Lead Detail)
# =====================================================================
class TestQuickSetup:
    def test_quick_setup_creates_and_approves_one_time(self, admin_token):
        lead = _seed_won_lead(admin_token, title_suffix="quicksetup-ot")
        _ensure_no_existing_commercial(admin_token, lead['id'])
        r = requests.post(f"{API}/leads/{lead['id']}/quick-setup-commercials",
                          json={"type": "one_time"}, headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body['existed'] is False
        assert body['generated'] is True
        assert body['type'] == 'one_time'
        assert len(body['events']) == 1
        ev = body['events'][0]
        # 100k deal × 15% = 15k Vyapaar; 20% of 15k = 3k referral; net 12k
        assert ev['expected_amount'] == 100000
        assert ev['vyapaar_amount'] == 15000
        assert ev['referral_amount'] == 3000
        assert ev['net_revenue'] == 12000
        assert ev['lifecycle_status'] == 'created'

    def test_quick_setup_idempotent(self, admin_token):
        lead = _seed_won_lead(admin_token, title_suffix="quicksetup-idem")
        _ensure_no_existing_commercial(admin_token, lead['id'])
        r1 = requests.post(f"{API}/leads/{lead['id']}/quick-setup-commercials",
                           json={"type": "one_time"}, headers=_auth(admin_token))
        assert r1.status_code == 200
        cid1 = r1.json()['commercial_id']
        # Second call should not double-create
        r2 = requests.post(f"{API}/leads/{lead['id']}/quick-setup-commercials",
                           json={"type": "one_time"}, headers=_auth(admin_token))
        assert r2.status_code == 200
        assert r2.json().get('existed') is True or r2.json().get('generated') is False
        # Same commercial id
        coms = requests.get(f"{API}/commercials", headers=_auth(admin_token)).json()
        matching = [c for c in coms if c.get('lead_id') == lead['id']]
        assert len(matching) == 1
        assert matching[0]['id'] == cid1

    def test_quick_setup_recurring(self, admin_token):
        lead = _seed_won_lead(admin_token, title_suffix="quicksetup-rec")
        _ensure_no_existing_commercial(admin_token, lead['id'])
        r = requests.post(f"{API}/leads/{lead['id']}/quick-setup-commercials",
                          json={"type": "recurring", "contract_months": 3, "billing_frequency": "monthly"},
                          headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body['type'] == 'recurring'
        # 3-month monthly contract → 3-4 events (depending on calendar boundary)
        assert 3 <= len(body['events']) <= 4

    def test_quick_setup_blocked_for_customer(self, customer_token, admin_token):
        # Need a fresh Won lead; create as admin then try as customer
        lead = _seed_won_lead(admin_token, title_suffix="quicksetup-rbac")
        _ensure_no_existing_commercial(admin_token, lead['id'])
        r = requests.post(f"{API}/leads/{lead['id']}/quick-setup-commercials",
                          json={"type": "one_time"}, headers=_auth(customer_token))
        assert r.status_code == 403


# =====================================================================
# Scenario E — RBAC
# =====================================================================
class TestRBAC:
    def test_customer_blocked_from_finance_dashboard(self, customer_token):
        r = requests.get(f"{API}/finance/dashboard", headers=_auth(customer_token))
        assert r.status_code == 403

    def test_customer_blocked_from_listing_events(self, customer_token):
        r = requests.get(f"{API}/finance/revenue-events", headers=_auth(customer_token))
        assert r.status_code == 403

    def test_customer_blocked_from_approving(self, customer_token, admin_token):
        # Find any commercial
        coms = requests.get(f"{API}/commercials", headers=_auth(admin_token)).json()
        if not coms:
            pytest.skip("no commercials to test")
        r = requests.post(f"{API}/commercials/{coms[0]['id']}/approve", headers=_auth(customer_token))
        assert r.status_code == 403
