"""
Phase 30 backend test suite covering:
 - Item 1: company_role + notification_preferences on user create/update + /auth/me
 - Item 3: follow-up assignee_id + reminder_minutes_before + assignee_name enrichment
 - Item 4: War Room board contains 'open_leads' bucket
 - Item 6: GET /api/notifications/types catalog + profile PUT for notification_preferences
 - Helper: GET /api/users/assignable
"""

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://vyapaar-preview-1.preview.emergentagent.com").rstrip("/")
ADMIN = {"email": "admin@vyapaarnetwork.com", "password": "admin123"}


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"No token in login response: {data}"
    return tok


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------- Item 1: company_role + notification_preferences on /auth/me ----------
class TestAuthMe:
    def test_me_returns_phase30_fields(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        data = r.json()
        # Fields should be present (may be None for super_admin)
        assert "company_role" in data, "company_role missing from /auth/me"
        assert "notification_preferences" in data, "notification_preferences missing from /auth/me"


# ---------- Item 6: Notifications types catalog ----------
class TestNotificationsCatalog:
    def test_catalog_returns_entries(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/notifications/types", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        types = r.json()
        assert isinstance(types, list), f"Expected list, got {type(types)}"
        assert len(types) >= 1, "Notifications types catalog is empty"
        # Each entry must have at least key + label/description
        sample = types[0]
        assert "key" in sample or "id" in sample or "type" in sample, f"Catalog entry shape unexpected: {sample}"


# ---------- Helper: users/assignable ----------
class TestUsersAssignable:
    def test_assignable_returns_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/users/assignable", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        users = r.json()
        assert isinstance(users, list)
        assert len(users) > 0
        # Each user must have id + name (so SearchableUserSelect can render)
        sample = users[0]
        assert "id" in sample
        assert "name" in sample


# ---------- Item 4: War Room board includes open_leads bucket ----------
class TestWarRoomOpenLeads:
    def test_board_has_open_leads_bucket(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/war-room/board", headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"Board failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        buckets = data.get("buckets") or data.get("board") or data
        # Bucket structure may be {buckets: [...]} or dict
        bucket_ids = []
        if isinstance(buckets, list):
            bucket_ids = [b.get("id") for b in buckets]
        elif isinstance(buckets, dict) and "buckets" in buckets:
            bucket_ids = [b.get("id") for b in buckets["buckets"]]
        assert "open_leads" in bucket_ids, f"open_leads bucket missing. Found: {bucket_ids}"

    def test_open_leads_bucket_has_count_field(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/war-room/board", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        buckets = data.get("buckets") if isinstance(data, dict) else data
        if isinstance(buckets, list):
            open_b = next((b for b in buckets if b.get("id") == "open_leads"), None)
            assert open_b is not None
            # count or leads list
            assert "count" in open_b or "leads" in open_b, f"open_leads bucket shape: {open_b.keys()}"


# ---------- Item 1: Admin create user with company_role + notification_preferences ----------
class TestAdminUserCreateUpdate:
    @pytest.fixture(scope="class")
    def test_user_id(self, admin_headers):
        """Create test user, return id, then cleanup."""
        uid_email = f"TEST_phase30_{uuid.uuid4().hex[:8]}@meshora.com"
        payload = {
            "email": uid_email,
            "password": "Test1234!",
            "name": "TEST Phase30 User",
            "role": "selling_partner",
            "company_name": f"TEST Phase30 Co {uuid.uuid4().hex[:6]}",
            "company_role": "founder",
            "notification_preferences": {"lead_assigned": True, "deal_won": False},
        }
        r = requests.post(f"{BASE_URL}/api/users", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code in (200, 201), f"Create user failed: {r.status_code} {r.text[:400]}"
        created = r.json()
        uid = created.get("id")
        assert uid
        yield uid, uid_email
        # Cleanup
        try:
            requests.delete(f"{BASE_URL}/api/users/{uid}", headers=admin_headers, timeout=15)
        except Exception:
            pass

    def test_create_persists_company_role(self, admin_headers, test_user_id):
        uid, _ = test_user_id
        r = requests.get(f"{BASE_URL}/api/users/{uid}", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        u = r.json()
        assert u.get("company_role") == "founder", f"company_role not persisted: {u.get('company_role')}"

    def test_create_persists_notification_preferences(self, admin_headers, test_user_id):
        uid, _ = test_user_id
        r = requests.get(f"{BASE_URL}/api/users/{uid}", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        u = r.json()
        prefs = u.get("notification_preferences") or {}
        assert prefs.get("lead_assigned") is True
        assert prefs.get("deal_won") is False

    def test_update_company_role(self, admin_headers, test_user_id):
        uid, _ = test_user_id
        r = requests.put(
            f"{BASE_URL}/api/users/{uid}",
            json={"company_role": "sales"},
            headers=admin_headers,
            timeout=20,
        )
        assert r.status_code == 200, f"Update failed: {r.status_code} {r.text[:300]}"
        # Verify persistence
        r2 = requests.get(f"{BASE_URL}/api/users/{uid}", headers=admin_headers, timeout=20)
        assert r2.status_code == 200
        assert r2.json().get("company_role") == "sales"

    def test_update_notification_preferences(self, admin_headers, test_user_id):
        uid, _ = test_user_id
        new_prefs = {"lead_assigned": False, "deal_won": True, "followup_due": True}
        r = requests.put(
            f"{BASE_URL}/api/users/{uid}",
            json={"notification_preferences": new_prefs},
            headers=admin_headers,
            timeout=20,
        )
        assert r.status_code == 200
        r2 = requests.get(f"{BASE_URL}/api/users/{uid}", headers=admin_headers, timeout=20)
        prefs = r2.json().get("notification_preferences") or {}
        assert prefs.get("deal_won") is True
        assert prefs.get("lead_assigned") is False


# ---------- Item 6: Profile PUT accepts notification_preferences ----------
class TestProfileNotificationPrefs:
    def test_profile_put_notification_preferences(self, admin_headers):
        new_prefs = {"lead_assigned": True, "deal_won": True}
        r = requests.put(
            f"{BASE_URL}/api/profile",
            json={"notification_preferences": new_prefs},
            headers=admin_headers,
            timeout=20,
        )
        assert r.status_code == 200, f"Profile PUT failed: {r.status_code} {r.text[:300]}"
        # Verify via /auth/me
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=admin_headers, timeout=20).json()
        prefs = me.get("notification_preferences") or {}
        assert prefs.get("lead_assigned") is True
        assert prefs.get("deal_won") is True


# ---------- Item 3: Follow-up with assignee_id + reminder_minutes_before ----------
class TestFollowUpAssigneeReminder:
    @pytest.fixture(scope="class")
    def existing_lead(self, admin_headers):
        """Pick any existing lead to attach a follow-up to."""
        r = requests.get(f"{BASE_URL}/api/leads", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        leads = r.json()
        if isinstance(leads, dict):
            leads = leads.get("leads") or leads.get("items") or []
        assert isinstance(leads, list) and len(leads) > 0, "No existing leads to test with"
        return leads[0]

    @pytest.fixture(scope="class")
    def assignee(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/users/assignable", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        users = r.json()
        assert len(users) > 0
        return users[0]

    def test_create_followup_with_assignee_and_reminder(self, admin_headers, existing_lead, assignee):
        lead_id = existing_lead.get("id")
        marker = f"TEST_phase30_followup_{uuid.uuid4().hex[:6]}"
        payload = {
            "scheduled_date": "2026-12-31T10:00:00",
            "notes": marker,
            "assignee_id": assignee["id"],
            "reminder_minutes_before": 60,
        }
        r = requests.post(
            f"{BASE_URL}/api/leads/{lead_id}/follow-ups",
            json=payload,
            headers=admin_headers,
            timeout=20,
        )
        assert r.status_code in (200, 201), f"Follow-up create failed: {r.status_code} {r.text[:300]}"
        # POST returns the updated LeadResponse with follow_ups array
        created_lead = r.json()
        followups = created_lead.get("follow_ups") or []
        match = next((f for f in followups if f.get("notes") == marker), None)
        assert match is not None, f"Created follow-up not found in lead.follow_ups. Got {len(followups)} items"
        assert match.get("assignee_id") == assignee["id"], f"assignee_id not persisted: {match.get('assignee_id')}"
        assert match.get("reminder_minutes_before") == 60, f"reminder not persisted: {match.get('reminder_minutes_before')}"
        # assignee_name enrichment
        assert match.get("assignee_name") == assignee["name"], f"assignee_name missing/wrong: {match.get('assignee_name')}"
