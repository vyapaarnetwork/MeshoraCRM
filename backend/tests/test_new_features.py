"""
Test suite for Vyapaar Network CRM - New Features
Tests:
1. Customer-only self-registration (non-customer roles rejected)
2. Admin user creation for all roles
3. Draft status for leads without selling partner
4. Draft to New status transition when partner assigned
5. Follow-up pending_with field
6. Companies sub-categories for selling partners
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@vyapaarnetwork.com"
ADMIN_PASSWORD = "admin123"

class TestAuthAndRegistration:
    """Test customer-only self-registration and admin user creation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_admin_token(self):
        """Get admin authentication token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    
    def test_customer_self_registration_success(self):
        """Test that customers can self-register"""
        unique_email = f"test_customer_{uuid.uuid4().hex[:8]}@test.com"
        response = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Test Customer",
            "role": "customer",
            "company_name": "Test Company",
            "phone": "+91 98765 43210"
        })
        
        assert response.status_code == 200, f"Customer registration failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "customer"
        assert data["user"]["email"] == unique_email
        print(f"✓ Customer self-registration successful: {unique_email}")
    
    def test_selling_partner_self_registration_rejected(self):
        """Test that selling partners cannot self-register (403 error)"""
        unique_email = f"test_sp_{uuid.uuid4().hex[:8]}@test.com"
        response = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Test Selling Partner",
            "role": "selling_partner",
            "company_name": "Test SP Company"
        })
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        data = response.json()
        assert "Only customers can self-register" in data.get("detail", "")
        print("✓ Selling partner self-registration correctly rejected with 403")
    
    def test_sales_associate_self_registration_rejected(self):
        """Test that sales associates cannot self-register (403 error)"""
        unique_email = f"test_sa_{uuid.uuid4().hex[:8]}@test.com"
        response = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Test Sales Associate",
            "role": "sales_associate"
        })
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        data = response.json()
        assert "Only customers can self-register" in data.get("detail", "")
        print("✓ Sales associate self-registration correctly rejected with 403")
    
    def test_super_admin_self_registration_rejected(self):
        """Test that super admins cannot self-register (403 error)"""
        unique_email = f"test_admin_{uuid.uuid4().hex[:8]}@test.com"
        response = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Test Admin",
            "role": "super_admin"
        })
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ Super admin self-registration correctly rejected with 403")
    
    def test_admin_login(self):
        """Test admin login works"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "super_admin"
        print("✓ Admin login successful")


class TestAdminUserCreation:
    """Test admin can create users of any role"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with admin auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_admin_create_selling_partner(self):
        """Test admin can create selling partner user"""
        unique_email = f"test_sp_admin_{uuid.uuid4().hex[:8]}@test.com"
        response = self.session.post(f"{BASE_URL}/api/users", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Admin Created SP",
            "role": "selling_partner",
            "company_name": "SP Company Created by Admin",
            "phone": "+91 98765 43210"
        })
        
        assert response.status_code == 200, f"Admin create SP failed: {response.text}"
        data = response.json()
        assert data["role"] == "selling_partner"
        assert data["email"] == unique_email
        print(f"✓ Admin created selling partner: {unique_email}")
    
    def test_admin_create_sales_associate(self):
        """Test admin can create sales associate user"""
        unique_email = f"test_sa_admin_{uuid.uuid4().hex[:8]}@test.com"
        response = self.session.post(f"{BASE_URL}/api/users", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Admin Created SA",
            "role": "sales_associate",
            "phone": "+91 98765 43210"
        })
        
        assert response.status_code == 200, f"Admin create SA failed: {response.text}"
        data = response.json()
        assert data["role"] == "sales_associate"
        assert data["email"] == unique_email
        print(f"✓ Admin created sales associate: {unique_email}")
    
    def test_admin_create_customer(self):
        """Test admin can create customer user"""
        unique_email = f"test_cust_admin_{uuid.uuid4().hex[:8]}@test.com"
        response = self.session.post(f"{BASE_URL}/api/users", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Admin Created Customer",
            "role": "customer",
            "company_name": "Customer Company by Admin"
        })
        
        assert response.status_code == 200, f"Admin create customer failed: {response.text}"
        data = response.json()
        assert data["role"] == "customer"
        print(f"✓ Admin created customer: {unique_email}")


class TestDraftLeadStatus:
    """Test Draft status for leads without selling partner"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with admin auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_draft_status_exists(self):
        """Test that Draft status exists in lead statuses"""
        response = self.session.get(f"{BASE_URL}/api/master/lead-status")
        
        assert response.status_code == 200, f"Failed to get lead statuses: {response.text}"
        statuses = response.json()
        
        status_names = [s["name"].lower() for s in statuses]
        assert "draft" in status_names, f"Draft status not found. Available: {status_names}"
        print(f"✓ Draft status exists in lead statuses: {status_names}")
    
    def test_lead_without_partner_gets_draft_status(self):
        """Test that lead created without selling partner gets Draft status"""
        # First get a primary category
        cat_response = self.session.get(f"{BASE_URL}/api/master/primary-categories")
        assert cat_response.status_code == 200
        categories = cat_response.json()
        
        if not categories:
            pytest.skip("No primary categories available")
        
        primary_category_id = categories[0]["id"]
        
        # Create lead without selling partner
        unique_email = f"test_lead_{uuid.uuid4().hex[:8]}@test.com"
        response = self.session.post(f"{BASE_URL}/api/leads", json={
            "title": "Test Draft Lead",
            "description": "Testing draft status",
            "customer_name": "Test Customer",
            "customer_email": unique_email,
            "primary_category_id": primary_category_id,
            "deal_value": 10000
            # No selling_partner_id - should get Draft status
        })
        
        assert response.status_code == 200, f"Lead creation failed: {response.text}"
        lead = response.json()
        
        # Verify status is Draft
        assert lead.get("status_name", "").lower() == "draft", f"Expected Draft status, got: {lead.get('status_name')}"
        print(f"✓ Lead without partner created with Draft status: {lead['id']}")
        
        return lead["id"]
    
    def test_draft_to_new_when_partner_assigned(self):
        """Test that Draft lead moves to New when partner is assigned"""
        # First get a primary category
        cat_response = self.session.get(f"{BASE_URL}/api/master/primary-categories")
        categories = cat_response.json()
        
        if not categories:
            pytest.skip("No primary categories available")
        
        primary_category_id = categories[0]["id"]
        
        # Get a selling partner
        partners_response = self.session.get(f"{BASE_URL}/api/users/selling-partners")
        partners = partners_response.json()
        
        if not partners:
            pytest.skip("No selling partners available")
        
        selling_partner_id = partners[0]["id"]
        
        # Create lead without selling partner (should be Draft)
        unique_email = f"test_lead_{uuid.uuid4().hex[:8]}@test.com"
        create_response = self.session.post(f"{BASE_URL}/api/leads", json={
            "title": "Test Draft to New Lead",
            "description": "Testing status transition",
            "customer_name": "Test Customer",
            "customer_email": unique_email,
            "primary_category_id": primary_category_id,
            "deal_value": 15000
        })
        
        assert create_response.status_code == 200
        lead = create_response.json()
        lead_id = lead["id"]
        
        # Verify it's Draft
        assert lead.get("status_name", "").lower() == "draft", f"Expected Draft, got: {lead.get('status_name')}"
        print(f"✓ Lead created with Draft status: {lead_id}")
        
        # Now assign a selling partner
        update_response = self.session.put(f"{BASE_URL}/api/leads/{lead_id}", json={
            "selling_partner_id": selling_partner_id
        })
        
        assert update_response.status_code == 200, f"Lead update failed: {update_response.text}"
        updated_lead = update_response.json()
        
        # Verify status changed to New
        assert updated_lead.get("status_name", "").lower() == "new", f"Expected New status, got: {updated_lead.get('status_name')}"
        print(f"✓ Lead status changed from Draft to New after partner assignment")


class TestFollowUpPendingWith:
    """Test follow-up pending_with field"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with admin auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_followup_with_pending_with_customer(self):
        """Test creating follow-up with pending_with = customer"""
        # Get existing leads
        leads_response = self.session.get(f"{BASE_URL}/api/leads")
        leads = leads_response.json()
        
        if not leads:
            pytest.skip("No leads available for testing")
        
        lead_id = leads[0]["id"]
        
        # Create follow-up with pending_with
        response = self.session.post(f"{BASE_URL}/api/leads/{lead_id}/follow-ups", json={
            "scheduled_date": "2026-02-15",
            "notes": "Test follow-up pending with customer",
            "pending_with": "customer"
        })
        
        assert response.status_code == 200, f"Follow-up creation failed: {response.text}"
        lead = response.json()
        
        # Find the new follow-up
        follow_ups = lead.get("follow_ups", [])
        assert len(follow_ups) > 0, "No follow-ups found"
        
        # Check the latest follow-up has pending_with
        latest_followup = follow_ups[-1]
        assert latest_followup.get("pending_with") == "customer", f"Expected pending_with=customer, got: {latest_followup.get('pending_with')}"
        print(f"✓ Follow-up created with pending_with=customer")
    
    def test_followup_with_pending_with_selling_partner(self):
        """Test creating follow-up with pending_with = selling_partner"""
        # Get existing leads
        leads_response = self.session.get(f"{BASE_URL}/api/leads")
        leads = leads_response.json()
        
        if not leads:
            pytest.skip("No leads available for testing")
        
        lead_id = leads[0]["id"]
        
        # Create follow-up with pending_with
        response = self.session.post(f"{BASE_URL}/api/leads/{lead_id}/follow-ups", json={
            "scheduled_date": "2026-02-20",
            "notes": "Test follow-up pending with selling partner",
            "pending_with": "selling_partner"
        })
        
        assert response.status_code == 200, f"Follow-up creation failed: {response.text}"
        lead = response.json()
        
        # Find the new follow-up
        follow_ups = lead.get("follow_ups", [])
        latest_followup = follow_ups[-1]
        assert latest_followup.get("pending_with") == "selling_partner", f"Expected pending_with=selling_partner, got: {latest_followup.get('pending_with')}"
        print(f"✓ Follow-up created with pending_with=selling_partner")


class TestCompanySubcategories:
    """Test company sub-categories for selling partners"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with admin auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_create_company_with_subcategories(self):
        """Test creating selling partner company with subcategories"""
        # Get secondary categories
        cat_response = self.session.get(f"{BASE_URL}/api/master/secondary-categories")
        categories = cat_response.json()
        
        subcategory_ids = [c["id"] for c in categories[:2]] if categories else []
        
        # Create company with subcategories
        unique_name = f"Test SP Company {uuid.uuid4().hex[:8]}"
        response = self.session.post(f"{BASE_URL}/api/companies", json={
            "name": unique_name,
            "type": "selling_partner",
            "vyapaar_commission_percentage": 12.5,
            "subcategory_ids": subcategory_ids,
            "contact_email": "test@company.com"
        })
        
        assert response.status_code == 200, f"Company creation failed: {response.text}"
        company = response.json()
        
        assert company["name"] == unique_name
        assert company["type"] == "selling_partner"
        
        if subcategory_ids:
            assert company.get("subcategory_ids") == subcategory_ids, f"Subcategory IDs mismatch"
            assert company.get("subcategories") is not None, "Subcategories not populated"
            print(f"✓ Company created with {len(subcategory_ids)} subcategories")
        else:
            print("✓ Company created (no subcategories available to test)")
    
    def test_company_list_includes_subcategories(self):
        """Test that company list includes subcategory information"""
        response = self.session.get(f"{BASE_URL}/api/companies?type=selling_partner")
        
        assert response.status_code == 200, f"Failed to get companies: {response.text}"
        companies = response.json()
        
        # Check if any company has subcategories
        companies_with_subs = [c for c in companies if c.get("subcategories")]
        
        if companies_with_subs:
            company = companies_with_subs[0]
            assert isinstance(company["subcategories"], list)
            if company["subcategories"]:
                assert "id" in company["subcategories"][0]
                assert "name" in company["subcategories"][0]
            print(f"✓ Companies list includes subcategory information")
        else:
            print("✓ Companies list retrieved (no companies with subcategories found)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
