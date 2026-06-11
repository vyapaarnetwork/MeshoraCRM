"""Phase 35 backend tests:
- War Room board excludes Lost / Dead / Disqualified
- AI suggest-actions for discussions
- Admin email-scheduler status + manual dispatch
- system-settings PUT/GET for email_scheduler_enabled
- Commercial type change (one_time <-> recurring)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://vyapaar-preview-1.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@vyapaarnetwork.com"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------- War Room: Lost / Dead / Disqualified must be excluded ----------
class TestWarRoomTerminalExclusion:
    def test_war_room_board_excludes_terminal(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/war-room/board", headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        buckets = data.get("buckets") or []
        assert buckets, "Expected at least one bucket"
        forbidden = {"lost", "dead", "disqualified", "closed lost", "closed-lost"}
        bad = []
        bucket_count_sum = 0
        for b in buckets:
            leads = b.get("leads") or []
            bucket_count_sum += b.get("count", len(leads))
            assert len(leads) == b.get("count"), f"Bucket {b.get('id')} count mismatch"
            for lead in leads:
                sn = (lead.get("status_name") or "").strip().lower()
                if sn in forbidden:
                    bad.append({"bucket": b.get("id"), "lead": lead.get("id"), "status": sn})
        assert not bad, f"Terminal statuses leaked into War Room buckets: {bad[:5]}"

        kpi_total = data.get("kpis", {}).get("total_leads")
        assert kpi_total == bucket_count_sum, (
            f"KPI total_leads ({kpi_total}) != sum of bucket counts ({bucket_count_sum})"
        )


# ---------- AI suggest-actions ----------
class TestAISuggestActions:
    def test_suggest_actions_returns_structure(self, admin_headers):
        # Pick any lead
        r = requests.get(f"{BASE_URL}/api/leads", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        leads = r.json()
        if isinstance(leads, dict):
            leads = leads.get("leads") or leads.get("items") or []
        if not leads:
            pytest.skip("No leads in DB to test AI suggest-actions")
        lead_id = leads[0]["id"]
        text = ("Schedule a meeting with the customer tomorrow at 3pm to discuss pricing, "
                "and send the proposal document by Friday.")
        r = requests.post(
            f"{BASE_URL}/api/leads/{lead_id}/ai/suggest-actions",
            headers=admin_headers,
            json={"text": text},
            timeout=120,
        )
        assert r.status_code == 200, f"AI suggest-actions failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert "tasks" in data and "follow_ups" in data
        assert isinstance(data["tasks"], list)
        assert isinstance(data["follow_ups"], list)
        # Don't hard-require LLM to return items, but ensure schema is correct when present
        for t in data["tasks"]:
            assert "title" in t and "due_date" in t and "priority" in t
        for f in data["follow_ups"]:
            assert "notes" in f and "scheduled_date" in f

    def test_suggest_actions_empty_text(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/leads", headers=admin_headers, timeout=30)
        leads = r.json()
        if isinstance(leads, dict):
            leads = leads.get("leads") or leads.get("items") or []
        if not leads:
            pytest.skip("No leads")
        lead_id = leads[0]["id"]
        r = requests.post(
            f"{BASE_URL}/api/leads/{lead_id}/ai/suggest-actions",
            headers=admin_headers, json={"text": "ok"}, timeout=30,
        )
        assert r.status_code == 200
        d = r.json()
        assert d == {"tasks": [], "follow_ups": []}


# ---------- Email Scheduler ----------
class TestEmailScheduler:
    def test_scheduler_status(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/email-scheduler/status", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for k in ("enabled", "loop_running", "zeptomail_configured", "stats_7d", "pending", "recent_logs"):
            assert k in d, f"missing key {k}"
        assert "sent" in d["stats_7d"] and "failed" in d["stats_7d"]
        assert "follow_up_reminders" in d["pending"] and "task_reminders" in d["pending"]
        assert isinstance(d["recent_logs"], list)

    def test_scheduler_toggle_setting(self, admin_headers):
        # Read initial
        r = requests.get(f"{BASE_URL}/api/system-settings/email_scheduler_enabled",
                         headers=admin_headers, timeout=20)
        assert r.status_code == 200
        original = r.json().get("value", True)

        # Flip OFF
        r = requests.put(f"{BASE_URL}/api/system-settings/email_scheduler_enabled",
                         headers=admin_headers, json={"value": False}, timeout=20)
        assert r.status_code == 200, r.text[:200]
        assert r.json().get("value") is False

        # Verify via GET
        r = requests.get(f"{BASE_URL}/api/system-settings/email_scheduler_enabled",
                         headers=admin_headers, timeout=20)
        assert r.json().get("value") is False

        # Verify status endpoint reflects it
        r = requests.get(f"{BASE_URL}/api/admin/email-scheduler/status", headers=admin_headers, timeout=20)
        assert r.json().get("enabled") is False

        # Restore
        r = requests.put(f"{BASE_URL}/api/system-settings/email_scheduler_enabled",
                         headers=admin_headers, json={"value": original}, timeout=20)
        assert r.status_code == 200

    def test_manual_dispatch_followups(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/dispatch-follow-up-reminders",
                          headers=admin_headers, timeout=60)
        # Should be 200 (dispatched, even if 0) or 503 if ZeptoMail unconfigured — both acceptable, not 500
        assert r.status_code in (200, 503), f"unexpected: {r.status_code} {r.text[:200]}"

    def test_manual_dispatch_tasks(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/dispatch-task-reminders",
                          headers=admin_headers, timeout=60)
        assert r.status_code in (200, 503), f"unexpected: {r.status_code} {r.text[:200]}"

    def test_manual_dispatch_weekly(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/dispatch-weekly-war-room-digest",
                          headers=admin_headers, timeout=120)
        assert r.status_code in (200, 503), f"unexpected: {r.status_code} {r.text[:200]}"

    def test_manual_dispatch_monthly(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/dispatch-monthly-digest",
                          headers=admin_headers, timeout=120)
        assert r.status_code in (200, 503), f"unexpected: {r.status_code} {r.text[:200]}"


# ---------- Commercial Type Change ----------
class TestCommercialTypeChange:
    def test_change_commercial_type(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/commercials", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        items = r.json()
        if isinstance(items, dict):
            items = items.get("items") or items.get("commercials") or []
        if not items:
            pytest.skip("No commercials")
        c = items[0]
        cid = c["id"]
        original = c.get("type") or c.get("commercial_type") or "one_time"
        new_type = "recurring" if original == "one_time" else "one_time"

        r = requests.patch(f"{BASE_URL}/api/commercials/{cid}",
                           headers=admin_headers, json={"type": new_type}, timeout=30)
        assert r.status_code == 200, f"PATCH failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        # Ensure field updated (key could be 'type' or 'commercial_type')
        eff = body.get("type") or body.get("commercial_type")
        assert eff == new_type, f"type did not switch: response={body}"

        # Restore
        r = requests.patch(f"{BASE_URL}/api/commercials/{cid}",
                           headers=admin_headers, json={"type": original}, timeout=30)
        assert r.status_code == 200
