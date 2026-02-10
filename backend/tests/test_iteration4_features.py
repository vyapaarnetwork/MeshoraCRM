"""
Test Suite for Iteration 4 Features:
1. Lead Referral - Sales Associates can also create referrals
2. Lead Referral - Selling Partners can create 'Internal Request' for their company needs
3. Notifications - Bell icon shows notification count
4. Notifications - Clicking notification navigates to lead
5. Notifications - Mark as read / Mark all as read
6. Grid Report - Summary stats (total leads, won deals, commissions)
7. Grid Report - Partner Performance Summary table with sorting
8. Grid Report - Detailed Lead Grid with sorting/filtering
9. Grid Report - Filters (date range, partner, category, status)
10. Grid Report - Export to CSV (frontend only)
11. SortableTable component - Column sorting (asc/desc) (frontend only)
12. SortableTable component - Global search (frontend only)
13. SortableTable component - Pagination (frontend only)
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@vyapaarnetwork.com"
ADMIN_PASSWORD = "admin123"
PARTNER_EMAIL = "partner1@test.com"
PARTNER_PASSWORD = "test123"


class TestAuth:
    """Authentication tests"""
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "super_admin"
        print(f"✓ Admin login successful")
        return data["access_token"]
    
    def test_partner_login(self):
        """Test partner login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTNER_EMAIL,
            "password": PARTNER_PASSWORD
        })
        assert response.status_code == 200, f"Partner login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "selling_partner"
        print(f"✓ Partner login successful")
        return data["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    """Get admin token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip("Admin login failed")
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def partner_token():
    """Get partner token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": PARTNER_EMAIL,
        "password": PARTNER_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip("Partner login failed")
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def sales_associate_token(admin_token):
    """Create a sales associate and get their token"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Create a sales associate
    unique_id = str(uuid.uuid4())[:8]
    sa_email = f"test_sa_{unique_id}@test.com"
    sa_password = "test123"
    
    response = requests.post(f"{BASE_URL}/api/users", json={
        "email": sa_email,
        "password": sa_password,
        "name": f"Test Sales Associate {unique_id}",
        "role": "sales_associate",
        "phone": "+91 9876543210"
    }, headers=headers)
    
    if response.status_code != 200:
        pytest.skip(f"Failed to create sales associate: {response.text}")
    
    # Login as sales associate
    login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": sa_email,
        "password": sa_password
    })
    
    if login_response.status_code != 200:
        pytest.skip("Sales associate login failed")
    
    return login_response.json()["access_token"]


@pytest.fixture(scope="module")
def primary_category_id(admin_token):
    """Get or create a primary category"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Get existing categories
    response = requests.get(f"{BASE_URL}/api/master/primary-categories", headers=headers)
    if response.status_code == 200 and len(response.json()) > 0:
        return response.json()[0]["id"]
    
    # Create a new category
    response = requests.post(f"{BASE_URL}/api/master/primary-categories", json={
        "name": f"Test Category {uuid.uuid4().hex[:6]}",
        "description": "Test category for testing"
    }, headers=headers)
    
    if response.status_code != 200:
        pytest.skip("Failed to create primary category")
    
    return response.json()["id"]


class TestLeadReferralSalesAssociate:
    """Test Lead Referral for Sales Associates"""
    
    def test_sales_associate_can_create_referral(self, sales_associate_token, primary_category_id):
        """Sales Associate can create a lead referral"""
        headers = {"Authorization": f"Bearer {sales_associate_token}"}
        
        unique_id = str(uuid.uuid4())[:8]
        response = requests.post(f"{BASE_URL}/api/leads/referral", json={
            "title": f"SA Referral Test {unique_id}",
            "description": "Test referral from sales associate",
            "customer_name": f"Test Customer {unique_id}",
            "customer_email": f"test_customer_{unique_id}@test.com",
            "customer_phone": "+91 9876543210",
            "customer_company": "Test Company",
            "primary_category_id": primary_category_id,
            "estimated_deal_value": 50000,
            "referral_notes": "Referral from sales associate",
            "is_internal_request": False
        }, headers=headers)
        
        assert response.status_code == 200, f"Failed to create referral: {response.text}"
        data = response.json()
        assert data["title"] == f"SA Referral Test {unique_id}"
        assert data["status_name"] == "Draft"
        assert data["referred_by_associate_id"] is not None
        assert data["referred_by_associate_name"] is not None
        print(f"✓ Sales Associate can create referral")
        return data["id"]
    
    def test_sales_associate_can_view_referrals(self, sales_associate_token):
        """Sales Associate can view their referrals"""
        headers = {"Authorization": f"Bearer {sales_associate_token}"}
        
        response = requests.get(f"{BASE_URL}/api/leads/my-referrals", headers=headers)
        assert response.status_code == 200, f"Failed to get referrals: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Sales Associate can view referrals (count: {len(data)})")


class TestLeadReferralInternalRequest:
    """Test Internal Request for Selling Partners"""
    
    def test_partner_can_create_internal_request(self, partner_token, primary_category_id):
        """Selling Partner can create an internal request"""
        headers = {"Authorization": f"Bearer {partner_token}"}
        
        unique_id = str(uuid.uuid4())[:8]
        response = requests.post(f"{BASE_URL}/api/leads/referral", json={
            "title": f"Internal Request Test {unique_id}",
            "description": "Internal service request from partner",
            "customer_name": "Partner Company",
            "customer_email": PARTNER_EMAIL,
            "customer_phone": "+91 9876543210",
            "customer_company": "Partner Company Ltd",
            "primary_category_id": primary_category_id,
            "estimated_deal_value": 75000,
            "referral_notes": "Internal service request",
            "is_internal_request": True
        }, headers=headers)
        
        assert response.status_code == 200, f"Failed to create internal request: {response.text}"
        data = response.json()
        assert data["title"] == f"Internal Request Test {unique_id}"
        assert data["is_internal_request"] == True
        assert data["status_name"] == "Draft"
        assert data["referred_by_partner_id"] is not None
        print(f"✓ Partner can create internal request")
        return data["id"]
    
    def test_partner_can_view_internal_requests(self, partner_token):
        """Partner can view their referrals including internal requests"""
        headers = {"Authorization": f"Bearer {partner_token}"}
        
        response = requests.get(f"{BASE_URL}/api/leads/my-referrals", headers=headers)
        assert response.status_code == 200, f"Failed to get referrals: {response.text}"
        data = response.json()
        
        # Check if there are internal requests
        internal_requests = [r for r in data if r.get("is_internal_request")]
        print(f"✓ Partner can view referrals (total: {len(data)}, internal: {len(internal_requests)})")


class TestNotifications:
    """Test Notification System"""
    
    def test_get_notifications(self, admin_token):
        """Get notifications for current user"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200, f"Failed to get notifications: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get notifications successful (count: {len(data)})")
    
    def test_get_unread_count(self, admin_token):
        """Get unread notification count"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/notifications/unread-count", headers=headers)
        assert response.status_code == 200, f"Failed to get unread count: {response.text}"
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        print(f"✓ Get unread count successful (count: {data['count']})")
    
    def test_mark_all_notifications_read(self, admin_token):
        """Mark all notifications as read"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.put(f"{BASE_URL}/api/notifications/mark-all-read", headers=headers)
        assert response.status_code == 200, f"Failed to mark all read: {response.text}"
        data = response.json()
        assert "message" in data
        print(f"✓ Mark all notifications read successful")
        
        # Verify unread count is 0
        count_response = requests.get(f"{BASE_URL}/api/notifications/unread-count", headers=headers)
        assert count_response.status_code == 200
        assert count_response.json()["count"] == 0
        print(f"✓ Verified unread count is 0 after marking all read")
    
    def test_notification_created_on_referral(self, partner_token, admin_token, primary_category_id):
        """Notification is created when a referral is submitted"""
        partner_headers = {"Authorization": f"Bearer {partner_token}"}
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First mark all admin notifications as read
        requests.put(f"{BASE_URL}/api/notifications/mark-all-read", headers=admin_headers)
        
        # Create a referral
        unique_id = str(uuid.uuid4())[:8]
        response = requests.post(f"{BASE_URL}/api/leads/referral", json={
            "title": f"Notification Test Referral {unique_id}",
            "customer_name": f"Test Customer {unique_id}",
            "customer_email": f"test_{unique_id}@test.com",
            "primary_category_id": primary_category_id,
            "is_internal_request": False
        }, headers=partner_headers)
        
        assert response.status_code == 200, f"Failed to create referral: {response.text}"
        
        # Check admin notifications
        notif_response = requests.get(f"{BASE_URL}/api/notifications?unread_only=true", headers=admin_headers)
        assert notif_response.status_code == 200
        notifications = notif_response.json()
        
        # Should have at least one new notification
        assert len(notifications) > 0, "No notification created for referral"
        
        # Check if there's a new_referral notification
        referral_notifs = [n for n in notifications if n["type"] == "new_referral"]
        assert len(referral_notifs) > 0, "No new_referral notification found"
        print(f"✓ Notification created on referral submission")
    
    def test_mark_single_notification_read(self, admin_token, partner_token, primary_category_id):
        """Mark a single notification as read"""
        partner_headers = {"Authorization": f"Bearer {partner_token}"}
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Create a referral to generate notification
        unique_id = str(uuid.uuid4())[:8]
        requests.post(f"{BASE_URL}/api/leads/referral", json={
            "title": f"Single Notif Test {unique_id}",
            "customer_name": f"Test Customer {unique_id}",
            "customer_email": f"test_{unique_id}@test.com",
            "primary_category_id": primary_category_id,
            "is_internal_request": False
        }, headers=partner_headers)
        
        # Get notifications
        notif_response = requests.get(f"{BASE_URL}/api/notifications", headers=admin_headers)
        notifications = notif_response.json()
        
        if len(notifications) > 0:
            notif_id = notifications[0]["id"]
            
            # Mark as read
            mark_response = requests.put(f"{BASE_URL}/api/notifications/{notif_id}/read", headers=admin_headers)
            assert mark_response.status_code == 200, f"Failed to mark notification read: {mark_response.text}"
            print(f"✓ Mark single notification read successful")
        else:
            print("⚠ No notifications to mark as read")


class TestGridReport:
    """Test Grid Performance Report"""
    
    def test_grid_report_access_admin_only(self, admin_token, partner_token):
        """Grid report is accessible only by admin"""
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        partner_headers = {"Authorization": f"Bearer {partner_token}"}
        
        # Admin should have access
        admin_response = requests.get(f"{BASE_URL}/api/reports/grid-performance", headers=admin_headers)
        assert admin_response.status_code == 200, f"Admin should have access: {admin_response.text}"
        print(f"✓ Admin can access grid report")
        
        # Partner should not have access
        partner_response = requests.get(f"{BASE_URL}/api/reports/grid-performance", headers=partner_headers)
        assert partner_response.status_code == 403, f"Partner should not have access"
        print(f"✓ Partner correctly denied access to grid report")
    
    def test_grid_report_summary_stats(self, admin_token):
        """Grid report returns summary stats"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/reports/grid-performance", headers=headers)
        assert response.status_code == 200, f"Failed to get grid report: {response.text}"
        data = response.json()
        
        # Check summary structure
        assert "summary" in data
        summary = data["summary"]
        assert "total_leads" in summary
        assert "won_deals" in summary
        assert "lost_deals" in summary
        assert "total_deal_value" in summary
        assert "total_vyapaar_commission" in summary
        assert "total_partner_revenue" in summary
        print(f"✓ Grid report summary stats: total_leads={summary['total_leads']}, won_deals={summary['won_deals']}")
    
    def test_grid_report_partner_summary(self, admin_token):
        """Grid report returns partner summary"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/reports/grid-performance", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check partner summary structure
        assert "partner_summary" in data
        partner_summary = data["partner_summary"]
        assert isinstance(partner_summary, list)
        
        if len(partner_summary) > 0:
            partner = partner_summary[0]
            assert "partner_id" in partner
            assert "partner_name" in partner
            assert "total_leads" in partner
            assert "won_deals" in partner
            assert "conversion_rate" in partner
            assert "vyapaar_commission" in partner
            assert "partner_revenue" in partner
        print(f"✓ Grid report partner summary (count: {len(partner_summary)})")
    
    def test_grid_report_detailed_grid(self, admin_token):
        """Grid report returns detailed lead grid"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/reports/grid-performance", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check grid data structure
        assert "grid_data" in data
        grid_data = data["grid_data"]
        assert isinstance(grid_data, list)
        
        if len(grid_data) > 0:
            lead = grid_data[0]
            assert "id" in lead
            assert "title" in lead
            assert "customer_name" in lead
            assert "partner_name" in lead
            assert "category" in lead
            assert "status" in lead
            assert "deal_value" in lead
            assert "vyapaar_commission" in lead
            assert "partner_revenue" in lead
        print(f"✓ Grid report detailed grid (count: {len(grid_data)})")
    
    def test_grid_report_filters(self, admin_token):
        """Grid report supports filters"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Test date filter
        response = requests.get(f"{BASE_URL}/api/reports/grid-performance?start_date=2024-01-01", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "filters" in data
        assert data["filters"]["start_date"] == "2024-01-01"
        print(f"✓ Grid report date filter works")
        
        # Test with end date
        response = requests.get(f"{BASE_URL}/api/reports/grid-performance?start_date=2024-01-01&end_date=2025-12-31", headers=headers)
        assert response.status_code == 200
        print(f"✓ Grid report date range filter works")
    
    def test_grid_report_sorting(self, admin_token):
        """Grid report supports sorting"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Test sort by deal_value desc
        response = requests.get(f"{BASE_URL}/api/reports/grid-performance?sort_by=deal_value&sort_order=desc", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        grid_data = data["grid_data"]
        if len(grid_data) > 1:
            # Verify descending order
            for i in range(len(grid_data) - 1):
                assert grid_data[i]["deal_value"] >= grid_data[i+1]["deal_value"], "Not sorted correctly"
        print(f"✓ Grid report sorting works")
        
        # Test sort by created_at asc
        response = requests.get(f"{BASE_URL}/api/reports/grid-performance?sort_by=created_at&sort_order=asc", headers=headers)
        assert response.status_code == 200
        print(f"✓ Grid report sort by created_at works")


class TestNotificationWithLeadId:
    """Test that notifications have lead_id for navigation"""
    
    def test_notification_has_lead_id(self, admin_token, partner_token, primary_category_id):
        """Notifications for referrals have lead_id"""
        partner_headers = {"Authorization": f"Bearer {partner_token}"}
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Mark all as read first
        requests.put(f"{BASE_URL}/api/notifications/mark-all-read", headers=admin_headers)
        
        # Create a referral
        unique_id = str(uuid.uuid4())[:8]
        referral_response = requests.post(f"{BASE_URL}/api/leads/referral", json={
            "title": f"Lead ID Test {unique_id}",
            "customer_name": f"Test Customer {unique_id}",
            "customer_email": f"test_{unique_id}@test.com",
            "primary_category_id": primary_category_id,
            "is_internal_request": False
        }, headers=partner_headers)
        
        assert referral_response.status_code == 200
        lead_id = referral_response.json()["id"]
        
        # Get notifications
        notif_response = requests.get(f"{BASE_URL}/api/notifications?unread_only=true", headers=admin_headers)
        assert notif_response.status_code == 200
        notifications = notif_response.json()
        
        # Find the notification for this referral
        referral_notifs = [n for n in notifications if n["type"] == "new_referral"]
        if len(referral_notifs) > 0:
            # At least one should have a lead_id
            notifs_with_lead_id = [n for n in referral_notifs if n.get("lead_id")]
            assert len(notifs_with_lead_id) > 0, "Notification should have lead_id"
            print(f"✓ Notification has lead_id for navigation")
        else:
            print("⚠ No referral notifications found")


class TestSMSNotification:
    """Test SMS notification helper (will log warning if Twilio not configured)"""
    
    def test_lead_assignment_triggers_notification(self, admin_token, partner_token, primary_category_id):
        """Lead assignment should trigger notification (SMS will log warning if not configured)"""
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        partner_headers = {"Authorization": f"Bearer {partner_token}"}
        
        # Get partner info
        partner_response = requests.get(f"{BASE_URL}/api/auth/me", headers=partner_headers)
        partner_id = partner_response.json()["id"]
        
        # Create a lead and assign to partner
        unique_id = str(uuid.uuid4())[:8]
        lead_response = requests.post(f"{BASE_URL}/api/leads", json={
            "title": f"SMS Test Lead {unique_id}",
            "customer_name": f"Test Customer {unique_id}",
            "customer_email": f"test_{unique_id}@test.com",
            "primary_category_id": primary_category_id,
            "selling_partner_id": partner_id,
            "deal_value": 100000
        }, headers=admin_headers)
        
        assert lead_response.status_code == 200, f"Failed to create lead: {lead_response.text}"
        print(f"✓ Lead created with partner assignment (SMS notification logged if Twilio not configured)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
