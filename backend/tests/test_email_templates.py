"""
Email Templates Feature Tests
Tests for configurable email templates for 6 events:
- New Lead Created
- Lead Assigned to Partner
- Lead Status Changed
- Lead Won
- Lead Lost
- Follow-up Reminder
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@vyapaarnetwork.com"
ADMIN_PASSWORD = "admin123"

# Expected event types
EXPECTED_EVENT_TYPES = [
    "new_lead",
    "lead_assigned",
    "lead_status_changed",
    "lead_won",
    "lead_lost",
    "follow_up_reminder"
]

# Expected event labels
EXPECTED_EVENT_LABELS = {
    "new_lead": "New Lead Created",
    "lead_assigned": "Lead Assigned to Partner",
    "lead_status_changed": "Lead Status Changed",
    "lead_won": "Lead Won (Deal Closed)",
    "lead_lost": "Lead Lost",
    "follow_up_reminder": "Follow-up Reminder"
}


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Get headers with admin auth token"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


class TestEmailTemplatesList:
    """Tests for GET /api/email-templates - List all templates"""
    
    def test_list_templates_returns_all_6_events(self, admin_headers):
        """Verify all 6 email templates are returned"""
        response = requests.get(f"{BASE_URL}/api/email-templates", headers=admin_headers)
        
        assert response.status_code == 200, f"Failed to list templates: {response.text}"
        templates = response.json()
        
        # Should return exactly 6 templates
        assert len(templates) == 6, f"Expected 6 templates, got {len(templates)}"
        
        # Verify all event types are present
        event_types = [t["event_type"] for t in templates]
        for expected_type in EXPECTED_EVENT_TYPES:
            assert expected_type in event_types, f"Missing event type: {expected_type}"
    
    def test_templates_have_required_fields(self, admin_headers):
        """Verify each template has all required fields"""
        response = requests.get(f"{BASE_URL}/api/email-templates", headers=admin_headers)
        templates = response.json()
        
        required_fields = ["event_type", "event_label", "subject", "body", "is_enabled", "variables"]
        
        for template in templates:
            for field in required_fields:
                assert field in template, f"Template {template.get('event_type')} missing field: {field}"
    
    def test_templates_have_correct_labels(self, admin_headers):
        """Verify event labels are correct"""
        response = requests.get(f"{BASE_URL}/api/email-templates", headers=admin_headers)
        templates = response.json()
        
        for template in templates:
            event_type = template["event_type"]
            expected_label = EXPECTED_EVENT_LABELS.get(event_type)
            assert template["event_label"] == expected_label, \
                f"Wrong label for {event_type}: expected '{expected_label}', got '{template['event_label']}'"
    
    def test_templates_have_variables(self, admin_headers):
        """Verify each template has variables defined"""
        response = requests.get(f"{BASE_URL}/api/email-templates", headers=admin_headers)
        templates = response.json()
        
        for template in templates:
            assert len(template["variables"]) > 0, \
                f"Template {template['event_type']} has no variables"
            
            # Each variable should have key and description
            for var in template["variables"]:
                assert "key" in var, f"Variable missing 'key' in {template['event_type']}"
                assert "description" in var, f"Variable missing 'description' in {template['event_type']}"
    
    def test_templates_have_default_content(self, admin_headers):
        """Verify templates have default subject and body"""
        response = requests.get(f"{BASE_URL}/api/email-templates", headers=admin_headers)
        templates = response.json()
        
        for template in templates:
            assert template["subject"], f"Template {template['event_type']} has empty subject"
            assert template["body"], f"Template {template['event_type']} has empty body"
    
    def test_unauthorized_access_denied(self):
        """Verify non-admin cannot access templates"""
        response = requests.get(f"{BASE_URL}/api/email-templates")
        assert response.status_code in [401, 403], "Should deny unauthorized access"


class TestEmailTemplateGet:
    """Tests for GET /api/email-templates/{event_type} - Get single template"""
    
    def test_get_new_lead_template(self, admin_headers):
        """Get new_lead template"""
        response = requests.get(f"{BASE_URL}/api/email-templates/new_lead", headers=admin_headers)
        
        assert response.status_code == 200
        template = response.json()
        assert template["event_type"] == "new_lead"
        assert template["event_label"] == "New Lead Created"
        assert "{{lead_title}}" in template["subject"] or "lead_title" in str(template["variables"])
    
    def test_get_lead_assigned_template(self, admin_headers):
        """Get lead_assigned template"""
        response = requests.get(f"{BASE_URL}/api/email-templates/lead_assigned", headers=admin_headers)
        
        assert response.status_code == 200
        template = response.json()
        assert template["event_type"] == "lead_assigned"
        assert template["event_label"] == "Lead Assigned to Partner"
    
    def test_get_invalid_event_type(self, admin_headers):
        """Invalid event type should return 400"""
        response = requests.get(f"{BASE_URL}/api/email-templates/invalid_event", headers=admin_headers)
        assert response.status_code == 400


class TestEmailTemplateUpdate:
    """Tests for PUT /api/email-templates/{event_type} - Update template"""
    
    def test_update_template_subject(self, admin_headers):
        """Update template subject"""
        new_subject = "TEST: Updated Subject - {{lead_title}}"
        
        response = requests.put(
            f"{BASE_URL}/api/email-templates/new_lead",
            headers=admin_headers,
            json={"subject": new_subject}
        )
        
        assert response.status_code == 200, f"Failed to update: {response.text}"
        template = response.json()
        assert template["subject"] == new_subject
        assert template["updated_at"] is not None
    
    def test_update_template_body(self, admin_headers):
        """Update template body"""
        new_body = "<h1>TEST: Custom Email Body</h1><p>Lead: {{lead_title}}</p>"
        
        response = requests.put(
            f"{BASE_URL}/api/email-templates/lead_assigned",
            headers=admin_headers,
            json={"body": new_body}
        )
        
        assert response.status_code == 200
        template = response.json()
        assert template["body"] == new_body
    
    def test_update_template_enabled_status(self, admin_headers):
        """Update template enabled/disabled status"""
        # Disable template
        response = requests.put(
            f"{BASE_URL}/api/email-templates/lead_status_changed",
            headers=admin_headers,
            json={"is_enabled": False}
        )
        
        assert response.status_code == 200
        template = response.json()
        assert template["is_enabled"] == False
        
        # Re-enable template
        response = requests.put(
            f"{BASE_URL}/api/email-templates/lead_status_changed",
            headers=admin_headers,
            json={"is_enabled": True}
        )
        
        assert response.status_code == 200
        template = response.json()
        assert template["is_enabled"] == True
    
    def test_update_multiple_fields(self, admin_headers):
        """Update subject, body, and enabled status together"""
        update_data = {
            "subject": "TEST: Multi-field Update - {{lead_title}}",
            "body": "<p>TEST: Updated body content</p>",
            "is_enabled": True
        }
        
        response = requests.put(
            f"{BASE_URL}/api/email-templates/lead_won",
            headers=admin_headers,
            json=update_data
        )
        
        assert response.status_code == 200
        template = response.json()
        assert template["subject"] == update_data["subject"]
        assert template["body"] == update_data["body"]
        assert template["is_enabled"] == update_data["is_enabled"]
    
    def test_update_invalid_event_type(self, admin_headers):
        """Update invalid event type should return 400"""
        response = requests.put(
            f"{BASE_URL}/api/email-templates/invalid_event",
            headers=admin_headers,
            json={"subject": "Test"}
        )
        assert response.status_code == 400


class TestEmailTemplatePreview:
    """Tests for POST /api/email-templates/{event_type}/preview - Preview with sample data"""
    
    def test_preview_replaces_variables(self, admin_headers):
        """Preview should replace variables with sample data"""
        template_data = {
            "subject": "New Lead: {{lead_title}}",
            "body": "<p>Customer: {{customer_name}}, Email: {{customer_email}}</p>"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/email-templates/new_lead/preview",
            headers=admin_headers,
            json=template_data
        )
        
        assert response.status_code == 200, f"Preview failed: {response.text}"
        preview = response.json()
        
        # Variables should be replaced with sample data
        assert "{{lead_title}}" not in preview["subject"]
        assert "{{customer_name}}" not in preview["body"]
        assert "{{customer_email}}" not in preview["body"]
        
        # Sample data should be present
        assert "Website Development Project" in preview["subject"]  # Sample lead_title
        assert "John Smith" in preview["body"]  # Sample customer_name
    
    def test_preview_lead_assigned_template(self, admin_headers):
        """Preview lead_assigned template"""
        template_data = {
            "subject": "Lead Assigned: {{lead_title}}",
            "body": "<p>Hi {{partner_name}}, you have a new lead from {{customer_name}}</p>"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/email-templates/lead_assigned/preview",
            headers=admin_headers,
            json=template_data
        )
        
        assert response.status_code == 200
        preview = response.json()
        
        assert "{{partner_name}}" not in preview["body"]
        assert "ABC Digital Services" in preview["body"]  # Sample partner_name
    
    def test_preview_follow_up_reminder(self, admin_headers):
        """Preview follow_up_reminder template"""
        template_data = {
            "subject": "Reminder: {{lead_title}}",
            "body": "<p>Follow-up on {{follow_up_date}}: {{follow_up_notes}}</p>"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/email-templates/follow_up_reminder/preview",
            headers=admin_headers,
            json=template_data
        )
        
        assert response.status_code == 200
        preview = response.json()
        
        assert "{{follow_up_date}}" not in preview["body"]
        assert "15 Feb 2025" in preview["body"]  # Sample follow_up_date


class TestEmailTemplateReset:
    """Tests for POST /api/email-templates/{event_type}/reset - Reset to default"""
    
    def test_reset_template_to_default(self, admin_headers):
        """Reset template should restore default content"""
        # First, update the template
        custom_subject = "TEST: Custom Subject Before Reset"
        requests.put(
            f"{BASE_URL}/api/email-templates/lead_lost",
            headers=admin_headers,
            json={"subject": custom_subject}
        )
        
        # Verify it was updated
        response = requests.get(f"{BASE_URL}/api/email-templates/lead_lost", headers=admin_headers)
        assert response.json()["subject"] == custom_subject
        
        # Reset to default
        response = requests.post(
            f"{BASE_URL}/api/email-templates/lead_lost/reset",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Reset failed: {response.text}"
        assert "message" in response.json()
        
        # Verify it's back to default
        response = requests.get(f"{BASE_URL}/api/email-templates/lead_lost", headers=admin_headers)
        template = response.json()
        
        # Should have default subject (not our custom one)
        assert template["subject"] != custom_subject
        assert "Lead Lost" in template["subject"]  # Default subject contains this
    
    def test_reset_invalid_event_type(self, admin_headers):
        """Reset invalid event type should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/email-templates/invalid_event/reset",
            headers=admin_headers
        )
        assert response.status_code == 400


class TestEmailTemplateToggle:
    """Tests for toggling template enabled/disabled status"""
    
    def test_toggle_template_off_and_on(self, admin_headers):
        """Toggle template enabled status"""
        event_type = "follow_up_reminder"
        
        # Get current status
        response = requests.get(f"{BASE_URL}/api/email-templates/{event_type}", headers=admin_headers)
        original_status = response.json()["is_enabled"]
        
        # Toggle off
        response = requests.put(
            f"{BASE_URL}/api/email-templates/{event_type}",
            headers=admin_headers,
            json={"is_enabled": False}
        )
        assert response.status_code == 200
        assert response.json()["is_enabled"] == False
        
        # Toggle on
        response = requests.put(
            f"{BASE_URL}/api/email-templates/{event_type}",
            headers=admin_headers,
            json={"is_enabled": True}
        )
        assert response.status_code == 200
        assert response.json()["is_enabled"] == True


class TestEmailTemplateVariables:
    """Tests for GET /api/email-templates/variables/{event_type} - Get variables"""
    
    def test_get_new_lead_variables(self, admin_headers):
        """Get variables for new_lead event"""
        response = requests.get(
            f"{BASE_URL}/api/email-templates/variables/new_lead",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["event_type"] == "new_lead"
        assert data["event_label"] == "New Lead Created"
        assert len(data["variables"]) > 0
        
        # Check for expected variables
        var_keys = [v["key"] for v in data["variables"]]
        assert "{{lead_title}}" in var_keys
        assert "{{customer_name}}" in var_keys
        assert "{{customer_email}}" in var_keys
    
    def test_get_lead_assigned_variables(self, admin_headers):
        """Get variables for lead_assigned event"""
        response = requests.get(
            f"{BASE_URL}/api/email-templates/variables/lead_assigned",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        var_keys = [v["key"] for v in data["variables"]]
        assert "{{partner_name}}" in var_keys
        assert "{{partner_email}}" in var_keys
    
    def test_get_follow_up_reminder_variables(self, admin_headers):
        """Get variables for follow_up_reminder event"""
        response = requests.get(
            f"{BASE_URL}/api/email-templates/variables/follow_up_reminder",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        var_keys = [v["key"] for v in data["variables"]]
        assert "{{follow_up_date}}" in var_keys
        assert "{{follow_up_notes}}" in var_keys
        assert "{{recipient_name}}" in var_keys
    
    def test_get_invalid_event_variables(self, admin_headers):
        """Invalid event type should return 400"""
        response = requests.get(
            f"{BASE_URL}/api/email-templates/variables/invalid_event",
            headers=admin_headers
        )
        assert response.status_code == 400


class TestEmailTemplateDataPersistence:
    """Tests for verifying data persistence after updates"""
    
    def test_update_persists_after_list(self, admin_headers):
        """Verify updated template appears in list"""
        unique_subject = "TEST_PERSIST: Unique Subject for Persistence Test"
        
        # Update template
        requests.put(
            f"{BASE_URL}/api/email-templates/lead_won",
            headers=admin_headers,
            json={"subject": unique_subject}
        )
        
        # Get list and verify
        response = requests.get(f"{BASE_URL}/api/email-templates", headers=admin_headers)
        templates = response.json()
        
        lead_won_template = next((t for t in templates if t["event_type"] == "lead_won"), None)
        assert lead_won_template is not None
        assert lead_won_template["subject"] == unique_subject


# Cleanup - Reset all templates to default after tests
@pytest.fixture(scope="module", autouse=True)
def cleanup_templates(admin_headers):
    """Reset templates after all tests"""
    yield
    # Reset all templates to default
    for event_type in EXPECTED_EVENT_TYPES:
        try:
            requests.post(
                f"{BASE_URL}/api/email-templates/{event_type}/reset",
                headers=admin_headers
            )
        except:
            pass
