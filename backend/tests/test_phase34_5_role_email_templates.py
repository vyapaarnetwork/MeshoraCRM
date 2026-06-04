"""Phase 34.5 — Role-based notification filtering + Meshora email templates DB-editability.

Coverage:
  * /api/notifications/types role/company_role filtering (admin, sales_associate, SP×{finance,sales,ops,founder}, customer, vyapaar_ops)
  * /api/email-templates catalog (19 entries, all new event types present)
  * PUT + GET + POST preview round-trip for deal_room_invite template
  * POST /api/admin/test-email → ZeptoMail accepted + Meshora wrapper present
  * Role-gated create_notification → email_logs filtered out for disallowed types
"""

import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@vyapaarnetwork.com"
ADMIN_PASSWORD = "admin123"
SAFE_RECIPIENT = "Mrunal@vyapaar.net"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# --- /api/notifications/types role filter -------------------------------------

class TestNotificationTypesRoleFilter:
    def test_admin_no_params_returns_full_catalog(self, admin_headers):
        r = requests.get(f"{API}/notifications/types", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        keys = {item["key"] for item in data}
        # New types must be present
        expected_new = {"lead_dead", "lead_disqualified", "deal_room_invite",
                        "approval_requested", "task_assigned", "follow_up_overdue"}
        missing = expected_new - keys
        assert not missing, f"Missing new types in catalog: {missing}. Got {len(data)} items: {keys}"
        print(f"Admin catalog size: {len(data)} keys={sorted(keys)}")

    def test_sales_associate_returns_exactly_10(self, admin_headers):
        r = requests.get(f"{API}/notifications/types?role=sales_associate", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        keys = {item["key"] for item in data}
        expected = {"new_lead", "lead_assigned", "lead_won", "lead_lost", "lead_dead",
                    "lead_disqualified", "follow_up_reminder", "follow_up_overdue",
                    "comment_mention", "task_assigned"}
        assert keys == expected, f"sales_associate mismatch. Got {keys}, expected {expected}"
        # Confirm forbidden types NOT present
        for forbidden in ("milestone_due", "approval_requested", "deal_room_invite",
                          "invoice_overdue", "payment_received"):
            assert forbidden not in keys

    def test_sp_finance_returns_exactly_5(self, admin_headers):
        r = requests.get(f"{API}/notifications/types?role=selling_partner&company_role=finance",
                         headers=admin_headers)
        assert r.status_code == 200
        keys = {item["key"] for item in r.json()}
        expected = {"milestone_due", "invoice_overdue", "payment_received",
                    "comment_mention", "task_assigned"}
        assert keys == expected, f"SP+finance mismatch. Got {keys}"

    def test_sp_sales_includes_required(self, admin_headers):
        r = requests.get(f"{API}/notifications/types?role=selling_partner&company_role=sales",
                         headers=admin_headers)
        assert r.status_code == 200
        keys = {item["key"] for item in r.json()}
        for must in ("approval_requested", "deal_room_invite", "lead_assigned", "follow_up_reminder"):
            assert must in keys, f"SP+sales missing {must}. Got {keys}"

    def test_sp_operations_includes_and_excludes(self, admin_headers):
        r = requests.get(f"{API}/notifications/types?role=selling_partner&company_role=operations",
                         headers=admin_headers)
        assert r.status_code == 200
        keys = {item["key"] for item in r.json()}
        for must in ("milestone_due", "approval_requested", "deal_room_invite",
                     "lead_won", "lead_lost", "lead_dead", "lead_disqualified"):
            assert must in keys, f"SP+ops missing {must}"
        for forbidden in ("invoice_overdue", "payment_received"):
            assert forbidden not in keys, f"SP+ops should NOT have {forbidden}"

    def test_sp_founder_returns_all(self, admin_headers):
        r_all = requests.get(f"{API}/notifications/types", headers=admin_headers)
        full_count = len(r_all.json())
        r = requests.get(f"{API}/notifications/types?role=selling_partner&company_role=founder",
                         headers=admin_headers)
        assert r.status_code == 200
        assert len(r.json()) == full_count, "SP+founder must equal full catalog"

    def test_customer_returns_exactly_3(self, admin_headers):
        r = requests.get(f"{API}/notifications/types?role=customer", headers=admin_headers)
        assert r.status_code == 200
        keys = {item["key"] for item in r.json()}
        expected = {"approval_requested", "deal_room_invite", "comment_mention"}
        assert keys == expected, f"customer mismatch. Got {keys}"

    def test_vyapaar_ops_returns_all(self, admin_headers):
        r_all = requests.get(f"{API}/notifications/types", headers=admin_headers)
        full_count = len(r_all.json())
        r = requests.get(f"{API}/notifications/types?role=vyapaar_ops", headers=admin_headers)
        assert r.status_code == 200
        assert len(r.json()) == full_count


# --- /api/email-templates catalog + edit/preview ------------------------------

class TestEmailTemplates:
    def test_list_templates_contains_all_new_types(self, admin_headers):
        r = requests.get(f"{API}/email-templates", headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        events = {t["event_type"] for t in data}
        required = {"lead_disqualified", "lead_dead", "deal_room_invite",
                    "approval_requested", "milestone_due", "invoice_overdue",
                    "payment_received", "comment_mention", "task_assigned",
                    "commercial_created", "follow_up_overdue",
                    "weekly_war_room_digest"}
        missing = required - events
        assert not missing, f"Missing event_types: {missing}. Got {len(data)} templates: {sorted(events)}"
        # Each template must have non-empty subject + body + variables
        for tpl in data:
            assert tpl.get("subject"), f"empty subject for {tpl.get('event_type')}"
            assert tpl.get("body"), f"empty body for {tpl.get('event_type')}"
            assert "variables" in tpl, f"missing variables for {tpl.get('event_type')}"
        print(f"Total templates: {len(data)}")

    def test_put_get_preview_deal_room_invite(self, admin_headers):
        nonce = uuid.uuid4().hex[:6]
        new_subject = f"[TEST_{nonce}] You're invited to a Deal Room {{{{recipient_name}}}}"
        # Use the supported {{token}} syntax
        new_body = f"<p>Hi {{{{recipient_name}}}}, join the room. token={nonce}</p>"

        # PUT — update
        put_r = requests.put(
            f"{API}/email-templates/deal_room_invite",
            json={"subject": new_subject, "body": new_body},
            headers=admin_headers,
        )
        assert put_r.status_code in (200, 201), f"PUT failed: {put_r.status_code} {put_r.text}"

        # GET — verify persisted
        get_r = requests.get(f"{API}/email-templates/deal_room_invite", headers=admin_headers)
        assert get_r.status_code == 200
        got = get_r.json()
        assert got["subject"] == new_subject
        assert nonce in got["body"]

        # POST preview
        prev_r = requests.post(
            f"{API}/email-templates/deal_room_invite/preview",
            json={"subject": new_subject, "body": new_body},
            headers=admin_headers,
        )
        assert prev_r.status_code == 200, f"preview failed: {prev_r.status_code} {prev_r.text}"
        prev = prev_r.json()
        rendered_body = (prev.get("body") or "") + (prev.get("html") or "")
        rendered_subject = prev.get("subject", "")
        # No raw {{token}} placeholders should leak (basic sanity)
        assert "{{recipient_name}}" not in rendered_body, f"unrendered token left: {rendered_body[:200]}"
        assert "{{recipient_name}}" not in rendered_subject, f"unrendered token in subject: {rendered_subject}"
        assert nonce in rendered_subject + rendered_body


class TestAdminTestEmail:
    def test_test_email_deal_room_invite_with_meshora_wrapper(self, admin_headers):
        r = requests.post(
            f"{API}/admin/test-email",
            json={"to_address": SAFE_RECIPIENT, "notification_type": "deal_room_invite"},
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200, f"test-email returned {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("ok") is True, f"ok != true: {data}"
        # ZeptoMail responds with 201 in status_code on success
        assert data.get("status_code") in (200, 201), f"unexpected status_code: {data}"

    def test_meshora_wrapper_via_inprocess_render(self):
        """Verify the _BASE_TEMPLATE wrapper actually injects 'Meshora' wordmark
        and 'Powered by Vyapaar Network' footer (Phase 34.5 spec)."""
        import sys
        sys.path.insert(0, "/app/backend")
        from services import zeptomail as _zepto  # type: ignore
        rendered = _zepto.render("deal_room_invite", {
            "recipient_name": "Test User",
            "inviter_name": "Admin",
            "magic_link": "https://example.org/d/sample",
            "lead_title": "Sample Deal",
            "permissions": ["view"],
            "expires_at": "in 7 days",
        })
        assert rendered, "zeptomail.render returned None for deal_room_invite"
        html = rendered.get("html") or ""
        assert "Meshora" in html, f"Meshora wordmark missing. Snippet: {html[:400]}"
        assert "Powered by Vyapaar Network" in html, "Footer 'Powered by Vyapaar Network' missing"


# --- Role-gated dispatch (matrix + in-process verification) -------------------

class TestRoleGatedDispatch:
    """Verifies the role gate at function level. The HTTP path uses
    `is_notification_allowed_for_role` inside create_notification() to skip
    email dispatch for disallowed types — covered here via direct import."""

    def test_matrix_blocks_milestone_due_for_sales_associate(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from server import is_notification_allowed_for_role  # type: ignore
        assert is_notification_allowed_for_role("milestone_due", "sales_associate", None) is False
        assert is_notification_allowed_for_role("invoice_overdue", "sales_associate", None) is False
        assert is_notification_allowed_for_role("approval_requested", "sales_associate", None) is False
        assert is_notification_allowed_for_role("deal_room_invite", "sales_associate", None) is False

    def test_matrix_allows_lead_assigned_for_sales_associate(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from server import is_notification_allowed_for_role  # type: ignore
        assert is_notification_allowed_for_role("lead_assigned", "sales_associate", None) is True
        assert is_notification_allowed_for_role("follow_up_overdue", "sales_associate", None) is True
        assert is_notification_allowed_for_role("comment_mention", "sales_associate", None) is True
        assert is_notification_allowed_for_role("task_assigned", "sales_associate", None) is True

    def test_matrix_customer_only_three(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from server import is_notification_allowed_for_role  # type: ignore
        for t in ("approval_requested", "deal_room_invite", "comment_mention"):
            assert is_notification_allowed_for_role(t, "customer", None) is True
        for t in ("lead_won", "milestone_due", "lead_assigned", "task_assigned"):
            assert is_notification_allowed_for_role(t, "customer", None) is False

    def test_create_notification_call_site_consults_role_gate(self):
        """Static check: server.py create_notification() must invoke
        is_notification_allowed_for_role on the recipient before queueing email."""
        with open("/app/backend/server.py") as f:
            src = f.read()
        assert "is_notification_allowed_for_role" in src, \
            "server.py does not reference role gate function — dispatch may not be filtered"
        # Confirm at least one usage inside notification code path
        idx = src.find("def create_notification")
        if idx >= 0:
            window = src[idx: idx + 5000]
            assert "is_notification_allowed_for_role" in window or "allowed_notification_types_for" in window, \
                "create_notification body does NOT call the role gate. Email dispatch is unfiltered."
