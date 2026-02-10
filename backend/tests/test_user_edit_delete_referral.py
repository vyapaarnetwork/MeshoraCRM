"""
Test suite for Vyapaar Network CRM - User Edit/Delete and Lead Referral Features
Tests:
1. User Edit - Super Admin can edit user details (name, email, phone, company, role)
2. User Delete - Super Admin can delete users (soft delete)
3. User Delete - Cannot delete own account
4. Company assignment - Sales Associates can be assigned to companies
5. Lead Referral - Selling Partners can create referrals
6. Lead Referral - Referrals are saved with Draft status
7. Lead Referral - Referrals show 'referred_by_partner' info
8. Lead Referral - Partner can view their referrals list
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


class TestUserEditDelete:
    """Test User Edit and Delete functionality for Super Admin"""
    
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
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        token = response.json().get("access_token")
        self.admin_user_id = response.json().get("user", {}).get("id")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_admin_can_edit_user_name(self):
        """Test Super Admin can edit user name"""
        # First create a test user
        unique_email = f"test_edit_name_{uuid.uuid4().hex[:8]}@test.com"
        create_response = self.session.post(f"{BASE_URL}/api/users", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Original Name",
            "role": "customer"
        })
        assert create_response.status_code == 200, f"User creation failed: {create_response.text}"
        user_id = create_response.json()["id"]
        
        # Edit the user's name
        update_response = self.session.put(f"{BASE_URL}/api/users/{user_id}", json={
            "name": "Updated Name"
        })
        assert update_response.status_code == 200, f"User update failed: {update_response.text}"
        updated_user = update_response.json()
        assert updated_user["name"] == "Updated Name", f"Name not updated: {updated_user['name']}"
        print(f"✓ Admin can edit user name: {updated_user['name']}")
    
    def test_admin_can_edit_user_email(self):
        """Test Super Admin can edit user email"""
        # Create a test user
        unique_email = f"test_edit_email_{uuid.uuid4().hex[:8]}@test.com"
        create_response = self.session.post(f"{BASE_URL}/api/users", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Test User",
            "role": "customer"
        })
        assert create_response.status_code == 200
        user_id = create_response.json()["id"]
        
        # Edit the user's email
        new_email = f"updated_email_{uuid.uuid4().hex[:8]}@test.com"
        update_response = self.session.put(f"{BASE_URL}/api/users/{user_id}", json={
            "email": new_email
        })
        assert update_response.status_code == 200, f"Email update failed: {update_response.text}"
        updated_user = update_response.json()
        assert updated_user["email"] == new_email, f"Email not updated: {updated_user['email']}"
        print(f"✓ Admin can edit user email: {updated_user['email']}")
    
    def test_admin_can_edit_user_phone(self):
        """Test Super Admin can edit user phone"""
        # Create a test user
        unique_email = f"test_edit_phone_{uuid.uuid4().hex[:8]}@test.com"
        create_response = self.session.post(f"{BASE_URL}/api/users", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Test User",
            "role": "customer",
            "phone": "+91 11111 11111"
        })
        assert create_response.status_code == 200
        user_id = create_response.json()["id"]
        
        # Edit the user's phone
        update_response = self.session.put(f"{BASE_URL}/api/users/{user_id}", json={
            "phone": "+91 99999 99999"
        })
        assert update_response.status_code == 200, f"Phone update failed: {update_response.text}"
        updated_user = update_response.json()
        assert updated_user["phone"] == "+91 99999 99999", f"Phone not updated: {updated_user['phone']}"
        print(f"✓ Admin can edit user phone: {updated_user['phone']}")
    
    def test_admin_can_edit_user_role(self):
        """Test Super Admin can edit user role"""
        # Create a test user as customer
        unique_email = f"test_edit_role_{uuid.uuid4().hex[:8]}@test.com"
        create_response = self.session.post(f"{BASE_URL}/api/users", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Test User",
            "role": "customer"
        })
        assert create_response.status_code == 200
        user_id = create_response.json()["id"]
        
        # Change role to sales_associate
        update_response = self.session.put(f"{BASE_URL}/api/users/{user_id}", json={
            "role": "sales_associate"
        })
        assert update_response.status_code == 200, f"Role update failed: {update_response.text}"
        updated_user = update_response.json()
        assert updated_user["role"] == "sales_associate", f"Role not updated: {updated_user['role']}"
        print(f"✓ Admin can edit user role: {updated_user['role']}")
    
    def test_admin_can_edit_user_company(self):
        """Test Super Admin can assign company to user"""
        # Get existing companies
        companies_response = self.session.get(f"{BASE_URL}/api/companies")
        companies = companies_response.json()
        
        if not companies:
            pytest.skip("No companies available for testing")
        
        company_id = companies[0]["id"]
        company_name = companies[0]["name"]
        
        # Create a test user
        unique_email = f"test_edit_company_{uuid.uuid4().hex[:8]}@test.com"
        create_response = self.session.post(f"{BASE_URL}/api/users", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Test User",
            "role": "sales_associate"
        })
        assert create_response.status_code == 200
        user_id = create_response.json()["id"]
        
        # Assign company to user
        update_response = self.session.put(f"{BASE_URL}/api/users/{user_id}", json={
            "company_id": company_id
        })
        assert update_response.status_code == 200, f"Company assignment failed: {update_response.text}"
        updated_user = update_response.json()
        assert updated_user["company_id"] == company_id, f"Company not assigned: {updated_user['company_id']}"
        print(f"✓ Admin can assign company to user: {company_name}")
    
    def test_admin_can_delete_user_soft_delete(self):
        """Test Super Admin can delete user (soft delete - sets is_active=False)"""
        # Create a test user
        unique_email = f"test_delete_{uuid.uuid4().hex[:8]}@test.com"
        create_response = self.session.post(f"{BASE_URL}/api/users", json={
            "email": unique_email,
            "password": "test123456",
            "name": "User To Delete",
            "role": "customer"
        })
        assert create_response.status_code == 200
        user_id = create_response.json()["id"]
        
        # Delete the user
        delete_response = self.session.delete(f"{BASE_URL}/api/users/{user_id}")
        assert delete_response.status_code == 200, f"User delete failed: {delete_response.text}"
        
        # Verify user is soft deleted (is_active=False)
        get_response = self.session.get(f"{BASE_URL}/api/users/{user_id}")
        assert get_response.status_code == 200
        user = get_response.json()
        assert user["is_active"] == False, f"User not soft deleted: is_active={user['is_active']}"
        print(f"✓ Admin can soft delete user: {user_id}")
    
    def test_admin_cannot_delete_own_account(self):
        """Test Super Admin cannot delete their own account"""
        # Try to delete own account
        delete_response = self.session.delete(f"{BASE_URL}/api/users/{self.admin_user_id}")
        assert delete_response.status_code == 400, f"Expected 400, got {delete_response.status_code}"
        
        error_detail = delete_response.json().get("detail", "")
        assert "Cannot delete your own account" in error_detail, f"Unexpected error: {error_detail}"
        print(f"✓ Admin cannot delete own account (correctly rejected)")
    
    def test_non_admin_cannot_edit_users(self):
        """Test non-admin users cannot edit other users"""
        # Login as a non-admin (create a customer first)
        unique_email = f"test_nonadmin_{uuid.uuid4().hex[:8]}@test.com"
        create_response = self.session.post(f"{BASE_URL}/api/users", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Non Admin User",
            "role": "customer"
        })
        assert create_response.status_code == 200
        user_id = create_response.json()["id"]
        
        # Login as the non-admin user
        non_admin_session = requests.Session()
        non_admin_session.headers.update({"Content-Type": "application/json"})
        login_response = non_admin_session.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": "test123456"
        })
        assert login_response.status_code == 200
        token = login_response.json().get("access_token")
        non_admin_session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Try to edit another user
        update_response = non_admin_session.put(f"{BASE_URL}/api/users/{self.admin_user_id}", json={
            "name": "Hacked Name"
        })
        assert update_response.status_code == 403, f"Expected 403, got {update_response.status_code}"
        print(f"✓ Non-admin cannot edit users (correctly rejected with 403)")


class TestSalesAssociateCompanyAssignment:
    """Test Sales Associate company assignment"""
    
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
        assert response.status_code == 200
        token = response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_create_sales_associate_with_company(self):
        """Test creating Sales Associate with company assignment"""
        # Get existing companies
        companies_response = self.session.get(f"{BASE_URL}/api/companies")
        companies = companies_response.json()
        
        if not companies:
            pytest.skip("No companies available for testing")
        
        company_id = companies[0]["id"]
        
        # Create sales associate with company
        unique_email = f"test_sa_company_{uuid.uuid4().hex[:8]}@test.com"
        create_response = self.session.post(f"{BASE_URL}/api/users", json={
            "email": unique_email,
            "password": "test123456",
            "name": "SA With Company",
            "role": "sales_associate",
            "company_id": company_id
        })
        assert create_response.status_code == 200, f"SA creation failed: {create_response.text}"
        user = create_response.json()
        assert user["company_id"] == company_id, f"Company not assigned: {user['company_id']}"
        print(f"✓ Sales Associate created with company assignment")


class TestLeadReferral:
    """Test Lead Referral functionality for Selling Partners"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test sessions for admin and partner"""
        self.admin_session = requests.Session()
        self.admin_session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        admin_response = self.admin_session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert admin_response.status_code == 200
        admin_token = admin_response.json().get("access_token")
        self.admin_session.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        # Create or get a selling partner for testing
        self.partner_session = requests.Session()
        self.partner_session.headers.update({"Content-Type": "application/json"})
        
        # Try to login as existing partner
        partner_response = self.partner_session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTNER_EMAIL,
            "password": PARTNER_PASSWORD
        })
        
        if partner_response.status_code == 200:
            partner_token = partner_response.json().get("access_token")
            self.partner_id = partner_response.json().get("user", {}).get("id")
            self.partner_session.headers.update({"Authorization": f"Bearer {partner_token}"})
        else:
            # Create a new partner
            unique_email = f"test_partner_{uuid.uuid4().hex[:8]}@test.com"
            create_response = self.admin_session.post(f"{BASE_URL}/api/users", json={
                "email": unique_email,
                "password": "test123456",
                "name": "Test Partner",
                "role": "selling_partner",
                "company_name": "Test Partner Company"
            })
            assert create_response.status_code == 200, f"Partner creation failed: {create_response.text}"
            self.partner_id = create_response.json()["id"]
            
            # Login as the new partner
            partner_login = self.partner_session.post(f"{BASE_URL}/api/auth/login", json={
                "email": unique_email,
                "password": "test123456"
            })
            assert partner_login.status_code == 200
            partner_token = partner_login.json().get("access_token")
            self.partner_session.headers.update({"Authorization": f"Bearer {partner_token}"})
    
    def test_partner_can_create_lead_referral(self):
        """Test Selling Partner can create a lead referral"""
        # Get primary categories
        cat_response = self.admin_session.get(f"{BASE_URL}/api/master/primary-categories")
        categories = cat_response.json()
        
        if not categories:
            pytest.skip("No primary categories available")
        
        primary_category_id = categories[0]["id"]
        
        # Create lead referral
        unique_email = f"referral_customer_{uuid.uuid4().hex[:8]}@test.com"
        referral_response = self.partner_session.post(f"{BASE_URL}/api/leads/referral", json={
            "title": "Test Lead Referral",
            "description": "Testing lead referral feature",
            "customer_name": "Referral Customer",
            "customer_email": unique_email,
            "customer_phone": "+91 88888 88888",
            "customer_company": "Referral Company",
            "primary_category_id": primary_category_id,
            "estimated_deal_value": 50000,
            "referral_notes": "This is a test referral"
        })
        
        assert referral_response.status_code == 200, f"Referral creation failed: {referral_response.text}"
        referral = referral_response.json()
        
        # Verify referral data
        assert referral["title"] == "Test Lead Referral"
        assert referral["customer_name"] == "Referral Customer"
        assert referral["customer_email"] == unique_email
        print(f"✓ Partner can create lead referral: {referral['id']}")
        
        return referral
    
    def test_referral_saved_with_draft_status(self):
        """Test that referrals are saved with Draft status"""
        # Get primary categories
        cat_response = self.admin_session.get(f"{BASE_URL}/api/master/primary-categories")
        categories = cat_response.json()
        
        if not categories:
            pytest.skip("No primary categories available")
        
        primary_category_id = categories[0]["id"]
        
        # Create lead referral
        unique_email = f"draft_referral_{uuid.uuid4().hex[:8]}@test.com"
        referral_response = self.partner_session.post(f"{BASE_URL}/api/leads/referral", json={
            "title": "Draft Status Test Referral",
            "customer_name": "Draft Test Customer",
            "customer_email": unique_email,
            "primary_category_id": primary_category_id,
            "estimated_deal_value": 25000
        })
        
        assert referral_response.status_code == 200
        referral = referral_response.json()
        
        # Verify status is Draft
        assert referral.get("status_name", "").lower() == "draft", f"Expected Draft status, got: {referral.get('status_name')}"
        print(f"✓ Referral saved with Draft status: {referral['status_name']}")
    
    def test_referral_has_referred_by_partner_info(self):
        """Test that referrals show referred_by_partner info"""
        # Get primary categories
        cat_response = self.admin_session.get(f"{BASE_URL}/api/master/primary-categories")
        categories = cat_response.json()
        
        if not categories:
            pytest.skip("No primary categories available")
        
        primary_category_id = categories[0]["id"]
        
        # Create lead referral
        unique_email = f"referred_by_{uuid.uuid4().hex[:8]}@test.com"
        referral_response = self.partner_session.post(f"{BASE_URL}/api/leads/referral", json={
            "title": "Referred By Test",
            "customer_name": "Referred Customer",
            "customer_email": unique_email,
            "primary_category_id": primary_category_id
        })
        
        assert referral_response.status_code == 200
        referral = referral_response.json()
        
        # Verify referred_by_partner_id is set
        assert referral.get("referred_by_partner_id") is not None, "referred_by_partner_id not set"
        assert referral.get("referred_by_partner_name") is not None, "referred_by_partner_name not set"
        print(f"✓ Referral has referred_by_partner info: {referral['referred_by_partner_name']}")
    
    def test_partner_can_view_their_referrals(self):
        """Test Partner can view their referrals list"""
        # First create a referral
        cat_response = self.admin_session.get(f"{BASE_URL}/api/master/primary-categories")
        categories = cat_response.json()
        
        if not categories:
            pytest.skip("No primary categories available")
        
        primary_category_id = categories[0]["id"]
        
        # Create a referral
        unique_email = f"my_referral_{uuid.uuid4().hex[:8]}@test.com"
        self.partner_session.post(f"{BASE_URL}/api/leads/referral", json={
            "title": "My Referral Test",
            "customer_name": "My Referral Customer",
            "customer_email": unique_email,
            "primary_category_id": primary_category_id
        })
        
        # Get my referrals
        referrals_response = self.partner_session.get(f"{BASE_URL}/api/leads/my-referrals")
        assert referrals_response.status_code == 200, f"Failed to get referrals: {referrals_response.text}"
        
        referrals = referrals_response.json()
        assert isinstance(referrals, list), "Referrals should be a list"
        assert len(referrals) > 0, "Should have at least one referral"
        
        # Verify all referrals belong to this partner
        for ref in referrals:
            assert ref.get("referred_by_partner_id") == self.partner_id, f"Referral doesn't belong to partner"
        
        print(f"✓ Partner can view their referrals: {len(referrals)} referrals found")
    
    def test_non_partner_cannot_create_referral(self):
        """Test non-selling-partner cannot create referrals"""
        # Create a customer user
        unique_email = f"test_customer_ref_{uuid.uuid4().hex[:8]}@test.com"
        create_response = self.admin_session.post(f"{BASE_URL}/api/users", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Customer User",
            "role": "customer"
        })
        assert create_response.status_code == 200
        
        # Login as customer
        customer_session = requests.Session()
        customer_session.headers.update({"Content-Type": "application/json"})
        login_response = customer_session.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": "test123456"
        })
        assert login_response.status_code == 200
        token = login_response.json().get("access_token")
        customer_session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get primary categories
        cat_response = self.admin_session.get(f"{BASE_URL}/api/master/primary-categories")
        categories = cat_response.json()
        
        if not categories:
            pytest.skip("No primary categories available")
        
        primary_category_id = categories[0]["id"]
        
        # Try to create referral as customer
        referral_response = customer_session.post(f"{BASE_URL}/api/leads/referral", json={
            "title": "Unauthorized Referral",
            "customer_name": "Test",
            "customer_email": "test@test.com",
            "primary_category_id": primary_category_id
        })
        
        assert referral_response.status_code == 403, f"Expected 403, got {referral_response.status_code}"
        print(f"✓ Non-partner cannot create referral (correctly rejected with 403)")


class TestAdminReferralAssignment:
    """Test Admin can assign referrals to selling partners"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test sessions"""
        self.admin_session = requests.Session()
        self.admin_session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        admin_response = self.admin_session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert admin_response.status_code == 200
        admin_token = admin_response.json().get("access_token")
        self.admin_session.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        # Setup partner session
        self.partner_session = requests.Session()
        self.partner_session.headers.update({"Content-Type": "application/json"})
        
        # Try to login as existing partner or create one
        partner_response = self.partner_session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTNER_EMAIL,
            "password": PARTNER_PASSWORD
        })
        
        if partner_response.status_code == 200:
            partner_token = partner_response.json().get("access_token")
            self.partner_id = partner_response.json().get("user", {}).get("id")
            self.partner_session.headers.update({"Authorization": f"Bearer {partner_token}"})
        else:
            # Create a new partner
            unique_email = f"test_partner_assign_{uuid.uuid4().hex[:8]}@test.com"
            create_response = self.admin_session.post(f"{BASE_URL}/api/users", json={
                "email": unique_email,
                "password": "test123456",
                "name": "Test Partner Assign",
                "role": "selling_partner",
                "company_name": "Test Partner Assign Company"
            })
            assert create_response.status_code == 200
            self.partner_id = create_response.json()["id"]
            
            partner_login = self.partner_session.post(f"{BASE_URL}/api/auth/login", json={
                "email": unique_email,
                "password": "test123456"
            })
            assert partner_login.status_code == 200
            partner_token = partner_login.json().get("access_token")
            self.partner_session.headers.update({"Authorization": f"Bearer {partner_token}"})
    
    def test_admin_assigns_referral_changes_to_new_status(self):
        """Test that when admin assigns a referral to a partner, status changes from Draft to New"""
        # Get primary categories
        cat_response = self.admin_session.get(f"{BASE_URL}/api/master/primary-categories")
        categories = cat_response.json()
        
        if not categories:
            pytest.skip("No primary categories available")
        
        primary_category_id = categories[0]["id"]
        
        # Create a referral as partner
        unique_email = f"assign_test_{uuid.uuid4().hex[:8]}@test.com"
        referral_response = self.partner_session.post(f"{BASE_URL}/api/leads/referral", json={
            "title": "Referral for Assignment",
            "customer_name": "Assignment Test Customer",
            "customer_email": unique_email,
            "primary_category_id": primary_category_id,
            "estimated_deal_value": 75000
        })
        
        assert referral_response.status_code == 200
        referral = referral_response.json()
        lead_id = referral["id"]
        
        # Verify it's in Draft status
        assert referral.get("status_name", "").lower() == "draft", f"Expected Draft, got: {referral.get('status_name')}"
        
        # Get another selling partner to assign
        partners_response = self.admin_session.get(f"{BASE_URL}/api/users/selling-partners")
        partners = partners_response.json()
        
        if not partners or len(partners) == 0:
            pytest.skip("No selling partners available")
        
        # Pick a different partner if possible
        assign_partner_id = partners[0].get("id")
        if not assign_partner_id:
            pytest.skip("No valid selling partner ID found")
        
        # Admin assigns the referral to a selling partner
        update_response = self.admin_session.put(f"{BASE_URL}/api/leads/{lead_id}", json={
            "selling_partner_id": assign_partner_id
        })
        
        assert update_response.status_code == 200, f"Assignment failed: {update_response.text}"
        updated_lead = update_response.json()
        
        # Verify status changed to New
        assert updated_lead.get("status_name", "").lower() == "new", f"Expected New status, got: {updated_lead.get('status_name')}"
        assert updated_lead.get("selling_partner_id") == assign_partner_id
        print(f"✓ Admin assigned referral, status changed from Draft to New")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
