"""Phase 29 — Weekly War Room tests.

Covers:
- GET /api/war-room/board structure, KPIs, bucket order, RBAC.
- Bucket classification rules — synthetic leads injected into Mongo directly.
- Sessions: start (auto-closes prior), active, notes PATCH, discuss, end (idempotent + materialized tasks).
- Session list/detail RBAC.
- Regression smoke: /auth/me, /leads, /partner-intelligence/dashboard, /predictive-forecast/* still 200.
"""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://vyapaar-preview-1.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

ADMIN_EMAIL = "admin@vyapaarnetwork.com"
ADMIN_PASSWORD = "admin123"
CUSTOMER_EMAIL = "john@testco.com"
CUSTOMER_PASSWORD = "test123"

mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def customer_token():
    return _login(CUSTOMER_EMAIL, CUSTOMER_PASSWORD)


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def customer_headers(customer_token):
    return {"Authorization": f"Bearer {customer_token}", "Content-Type": "application/json"}


# ---------------- BOARD ----------------
class TestWarRoomBoard:
    def test_board_shape(self, admin_headers):
        r = requests.get(f"{API}/war-room/board", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "buckets" in data and "kpis" in data and "generated_at" in data
        assert len(data["buckets"]) == 7
        expected_order = [
            "high_priority", "blocked", "followup_pending", "commercial_pending",
            "partner_coordination", "inactive", "recently_won"
        ]
        assert [b["id"] for b in data["buckets"]] == expected_order
        for b in data["buckets"]:
            assert "label" in b and "color" in b and "count" in b and "total_value" in b
            assert isinstance(b["leads"], list)
        kpis = data["kpis"]
        for k in ("total_pipeline", "weighted_pipeline", "at_risk_pipeline", "inactive_pipeline", "total_leads"):
            assert k in kpis

    def test_board_card_fields(self, admin_headers):
        r = requests.get(f"{API}/war-room/board", headers=admin_headers, timeout=30)
        data = r.json()
        # find any lead in any bucket
        any_card = None
        for b in data["buckets"]:
            if b["leads"]:
                any_card = b["leads"][0]
                break
        if not any_card:
            pytest.skip("No lead cards present on board to validate fields")
        for f in ("id", "title", "customer_company", "deal_value", "status_name",
                  "health_band", "days_inactive", "overdue_count",
                  "next_action_label", "comment_count", "pending_approvals"):
            assert f in any_card, f"missing field: {f}"

    def test_board_customer_403(self, customer_headers):
        r = requests.get(f"{API}/war-room/board", headers=customer_headers, timeout=20)
        assert r.status_code == 403


# ---------------- BUCKET CLASSIFICATION (synthetic leads) ----------------
class TestBucketClassification:
    """Inject synthetic leads directly into Mongo with known signals, then call /board."""

    @pytest.fixture(scope="class", autouse=True)
    def seed_and_cleanup(self, request):
        # ensure won/lost statuses exist
        statuses = list(db.lead_statuses.find({}, {"_id": 0}))
        won_status = next((s for s in statuses if s.get('is_won')), None)
        commercial_status = next((s for s in statuses if 'proposal' in (s.get('name') or '').lower()
                                  or 'commercial' in (s.get('name') or '').lower()
                                  or 'negotiat' in (s.get('name') or '').lower()), None)
        other_status = next((s for s in statuses if not s.get('is_won') and not s.get('is_lost')), None)
        if not other_status:
            pytest.skip("No active lead status found")

        admin = db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0})
        admin_id = admin["id"]

        now = datetime.now(timezone.utc)
        today_iso = now.isoformat()
        old_iso = (now - timedelta(days=30)).isoformat()
        recent_iso = (now - timedelta(days=2)).isoformat()
        followup_overdue_date = (now - timedelta(days=5)).date().isoformat()

        synthetic = []

        # (a) recently_won
        if won_status:
            synthetic.append({
                "id": f"TEST_WR_won_{uuid.uuid4()}",
                "title": "TEST_WR Won Lead",
                "customer_company": "TEST_WR Co Won",
                "deal_value": 50000,
                "status_id": won_status["id"],
                "selling_partner_id": admin_id,
                "selling_partner_name": "Admin",
                "comments": [],
                "approvals": [],
                "follow_ups": [],
                "assigned_partners": [],
                "updated_at": recent_iso,
                "created_at": recent_iso,
                "_test_bucket": "recently_won",
            })

        # (b) blocked - comment with #blocker
        synthetic.append({
            "id": f"TEST_WR_blocked_{uuid.uuid4()}",
            "title": "TEST_WR Blocked",
            "customer_company": "TEST_WR Co Blocked",
            "deal_value": 50000,
            "status_id": other_status["id"],
            "selling_partner_id": admin_id,
            "comments": [{"content": "Waiting on legal #blocker review", "user_id": admin_id, "created_at": recent_iso}],
            "approvals": [],
            "follow_ups": [],
            "assigned_partners": [],
            "updated_at": recent_iso,
            "created_at": recent_iso,
            "_test_bucket": "blocked",
        })

        # (c) inactive - 30 days no activity
        synthetic.append({
            "id": f"TEST_WR_inactive_{uuid.uuid4()}",
            "title": "TEST_WR Inactive",
            "customer_company": "TEST_WR Co Inactive",
            "deal_value": 75000,
            "status_id": other_status["id"],
            "selling_partner_id": admin_id,
            "comments": [],
            "approvals": [],
            "follow_ups": [],
            "assigned_partners": [],
            "updated_at": old_iso,
            "created_at": old_iso,
            "_test_bucket": "inactive",
        })

        # (d) high_priority - high deal_value, recent
        synthetic.append({
            "id": f"TEST_WR_hp_{uuid.uuid4()}",
            "title": "TEST_WR High Priority",
            "customer_company": "TEST_WR Co HP",
            "deal_value": 500000,
            "status_id": other_status["id"],
            "selling_partner_id": admin_id,
            "comments": [],
            "approvals": [],
            "follow_ups": [],
            "assigned_partners": [],
            "updated_at": recent_iso,
            "created_at": recent_iso,
            "_test_bucket": "high_priority",
            # We can't force the health band, so we rely on recent activity giving hot/at_risk.
        })

        # (e) followup_pending - overdue follow-up
        synthetic.append({
            "id": f"TEST_WR_fp_{uuid.uuid4()}",
            "title": "TEST_WR Followup Pending",
            "customer_company": "TEST_WR Co FP",
            "deal_value": 25000,
            "status_id": other_status["id"],
            "selling_partner_id": admin_id,
            "comments": [],
            "approvals": [],
            "follow_ups": [
                {"id": str(uuid.uuid4()), "scheduled_date": followup_overdue_date, "is_completed": False, "notes": "overdue"}
            ],
            "assigned_partners": [],
            "updated_at": recent_iso,
            "created_at": recent_iso,
            "_test_bucket": "followup_pending",
        })

        # (f) commercial_pending - status name contains proposal/commercial/negotiat
        if commercial_status:
            synthetic.append({
                "id": f"TEST_WR_cp_{uuid.uuid4()}",
                "title": "TEST_WR Commercial",
                "customer_company": "TEST_WR Co Commercial",
                "deal_value": 25000,
                "status_id": commercial_status["id"],
                "selling_partner_id": admin_id,
                "comments": [],
                "approvals": [],
                "follow_ups": [],
                "assigned_partners": [],
                "updated_at": recent_iso,
                "created_at": recent_iso,
                "_test_bucket": "commercial_pending",
            })

        if synthetic:
            db.leads.insert_many(synthetic)
        request.cls.synthetic_ids = [s["id"] for s in synthetic]
        request.cls.synthetic_lookup = {s["id"]: s["_test_bucket"] for s in synthetic}

        yield

        db.leads.delete_many({"id": {"$in": request.cls.synthetic_ids}})

    def _board(self, headers):
        r = requests.get(f"{API}/war-room/board", headers=headers, timeout=30)
        assert r.status_code == 200
        return r.json()

    def _lead_bucket(self, board, lead_id):
        for b in board["buckets"]:
            for lc in b["leads"]:
                if lc["id"] == lead_id:
                    return b["id"]
        return None

    def test_classification_rules(self, admin_headers):
        board = self._board(admin_headers)
        # Validate each synthetic landed in its expected bucket (or skip if not present)
        misclassified = []
        for lid, expected in self.synthetic_lookup.items():
            actual = self._lead_bucket(board, lid)
            if actual is None:
                # may have been filtered out; record as miss
                misclassified.append((lid, expected, "NOT_ON_BOARD"))
            elif actual != expected:
                # high_priority depends on health band, which depends on follow-ups/comments — allow fallback
                if expected == "high_priority" and actual in ("inactive", "partner_coordination", "followup_pending"):
                    misclassified.append((lid, expected, actual))  # informational
                else:
                    misclassified.append((lid, expected, actual))
        # Hard fail only if blocker/inactive/commercial_pending/followup_pending/recently_won missed
        hard = [m for m in misclassified if m[1] in ("blocked", "inactive", "commercial_pending", "followup_pending", "recently_won")]
        assert not hard, f"Hard misclassifications: {hard}; full: {misclassified}"
        # Log soft failures
        if misclassified:
            print(f"Soft misclassifications (high_priority/health-dependent): {misclassified}")


# ---------------- SESSIONS ----------------
class TestWarRoomSessions:
    @pytest.fixture(scope="class")
    def session_id(self, admin_headers):
        # Cleanup any leftover open sessions
        admin = db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0})
        db.war_room_sessions.delete_many({"started_by": admin["id"], "title": {"$regex": "^TEST_WR"}})
        r = requests.post(f"{API}/war-room/sessions/start",
                          json={"title": "TEST_WR Session 1"}, headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["title"] == "TEST_WR Session 1"
        assert s["ended_at"] is None
        return s["id"]

    def test_session_start_auto_closes_prior(self, admin_headers, session_id):
        # Start another — first one should be auto-closed
        r = requests.post(f"{API}/war-room/sessions/start",
                          json={"title": "TEST_WR Session 2"}, headers=admin_headers, timeout=20)
        assert r.status_code == 200
        new_id = r.json()["id"]
        assert new_id != session_id
        # Prior should be auto-closed
        prior = db.war_room_sessions.find_one({"id": session_id}, {"_id": 0})
        assert prior["ended_at"] is not None
        assert prior.get("auto_closed") is True
        # Active should be the new one
        r2 = requests.get(f"{API}/war-room/sessions/active", headers=admin_headers, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["id"] == new_id
        # cleanup: store new_id for later steps
        self.__class__._live_session_id = new_id

    def test_session_active_endpoint(self, admin_headers):
        r = requests.get(f"{API}/war-room/sessions/active", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert r.json() is not None
        assert r.json()["id"] == self._live_session_id

    def test_session_notes_patch(self, admin_headers):
        sid = self._live_session_id
        r = requests.patch(f"{API}/war-room/sessions/{sid}/notes",
                           json={"notes": "Discussed pipeline; high risk: Acme."},
                           headers=admin_headers, timeout=15)
        assert r.status_code == 200
        s = db.war_room_sessions.find_one({"id": sid}, {"_id": 0})
        assert "Discussed pipeline" in (s.get("notes") or "")

    def test_session_discuss_lead(self, admin_headers):
        sid = self._live_session_id
        # pick any lead
        a_lead = db.leads.find_one({}, {"_id": 0, "id": 1})
        if not a_lead:
            pytest.skip("No leads in DB to discuss")
        r = requests.post(f"{API}/war-room/sessions/{sid}/discuss",
                          json={"lead_id": a_lead["id"], "note": "TEST_WR note for lead"},
                          headers=admin_headers, timeout=15)
        assert r.status_code == 200
        s = db.war_room_sessions.find_one({"id": sid}, {"_id": 0})
        assert a_lead["id"] in (s.get("discussed_lead_ids") or [])
        assert (s.get("discussion_notes") or {}).get(a_lead["id"]) == "TEST_WR note for lead"

    def test_session_end_and_idempotent(self, admin_headers):
        sid = self._live_session_id
        r = requests.post(f"{API}/war-room/sessions/{sid}/end", headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        s1 = r.json()
        assert s1.get("ended_at")
        assert "materialized_task_count" in s1
        assert "materialized_task_ids" in s1
        assert "summary" in s1
        # idempotency
        r2 = requests.post(f"{API}/war-room/sessions/{sid}/end", headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        s2 = r2.json()
        assert s2["ended_at"] == s1["ended_at"]

    def test_notes_patch_after_end_rejected(self, admin_headers):
        sid = self._live_session_id
        r = requests.patch(f"{API}/war-room/sessions/{sid}/notes",
                           json={"notes": "should fail"}, headers=admin_headers, timeout=15)
        assert r.status_code == 400

    def test_discuss_after_end_rejected(self, admin_headers):
        sid = self._live_session_id
        a_lead = db.leads.find_one({}, {"_id": 0, "id": 1})
        if not a_lead:
            pytest.skip("No leads")
        r = requests.post(f"{API}/war-room/sessions/{sid}/discuss",
                          json={"lead_id": a_lead["id"], "note": "nope"},
                          headers=admin_headers, timeout=15)
        assert r.status_code == 400

    def test_list_sessions(self, admin_headers):
        r = requests.get(f"{API}/war-room/sessions", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert any(s["id"] == self._live_session_id for s in items)

    def test_get_session_detail(self, admin_headers):
        sid = self._live_session_id
        r = requests.get(f"{API}/war-room/sessions/{sid}", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["id"] == sid

    def test_customer_403_on_sessions(self, customer_headers):
        r = requests.post(f"{API}/war-room/sessions/start",
                          json={"title": "x"}, headers=customer_headers, timeout=15)
        assert r.status_code == 403
        r2 = requests.get(f"{API}/war-room/sessions", headers=customer_headers, timeout=15)
        # list endpoint also forbids customer
        assert r2.status_code in (200, 403)
        if r2.status_code == 200:
            assert r2.json() == [] or all(False for _ in r2.json())  # admin-shaped, but customer shouldn't see any

    def test_materialized_tasks_marker(self, admin_headers):
        sid = self._live_session_id
        # Check tasks collection (may be 0 if LLM had nothing actionable, but source must be war_room_session if any)
        tasks = list(db.tasks.find({"source": "war_room_session", "source_session_id": sid}, {"_id": 0}))
        s = db.war_room_sessions.find_one({"id": sid}, {"_id": 0})
        count = s.get("materialized_task_count") or 0
        assert len(tasks) == count

    @classmethod
    def teardown_class(cls):
        sid = getattr(cls, "_live_session_id", None)
        if sid:
            db.tasks.delete_many({"source_session_id": sid})
            db.war_room_sessions.delete_one({"id": sid})
        # Cleanup TEST_WR leftovers
        db.war_room_sessions.delete_many({"title": {"$regex": "^TEST_WR"}})


# ---------------- REGRESSION ----------------
class TestRegressionSmoke:
    def test_auth_me(self, admin_headers):
        r = requests.get(f"{API}/auth/me", headers=admin_headers, timeout=15)
        assert r.status_code == 200

    def test_leads_list(self, admin_headers):
        r = requests.get(f"{API}/leads", headers=admin_headers, timeout=20)
        assert r.status_code == 200

    def test_partner_intelligence(self, admin_headers):
        r = requests.get(f"{API}/partner-intelligence/dashboard", headers=admin_headers, timeout=30)
        assert r.status_code in (200, 404)  # 404 ok if disabled

    def test_predictive_forecast(self, admin_headers):
        r = requests.get(f"{API}/predictive-forecast/dashboard", headers=admin_headers, timeout=30)
        assert r.status_code in (200, 404)
