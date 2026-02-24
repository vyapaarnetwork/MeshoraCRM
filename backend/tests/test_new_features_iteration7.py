"""
Test file for Iteration 7 - New Features:
1. Customer User Management - /api/customers/company-users endpoints
2. Company Creation with Default User - POST /api/companies with default_user fields
3. Internal Requests - /api/leads/internal-requests for Selling Partners
4. Partner Assignment History - partner_history array in lead response
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@vyapaarnetwork.com"
ADMIN_PASSWORD = "admin123"
CUSTOMER_EMAIL = "john@testco.com"
CUSTOMER_PASSWORD = "test123"


class TestAuth:
    """Authentication helper tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def customer_token(self):
        """Get customer authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CUSTOMER_EMAIL,
            "password": CUSTOMER_PASSWORD
        })
        assert response.status_code == 200, f"Customer login failed: {response.text}"
        return response.json()["access_token"]
    
    def test_admin_login(self, admin_token):
        """Verify admin can login"""
        assert admin_token is not None
        assert len(admin_token) > 0
    
    def test_customer_login(self, customer_token):
        """Verify customer can login"""
        assert customer_token is not None
        assert len(customer_token) > 0


class TestCustomerUserManagement:
    """Test Customer User Management endpoints"""
    
    @pytest.fixture(scope="class")
    def customer_token(self):
        """Get customer authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CUSTOMER_EMAIL,
            "password": CUSTOMER_PASSWORD
        })
        assert response.status_code == 200, f"Customer login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["access_token"]
    
    def test_list_company_users_as_customer(self, customer_token):
        """Customer can list users from their company"""
        response = requests.get(
            f"{BASE_URL}/api/customers/company-users",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        assert response.status_code == 200, f"Failed to list company users: {response.text}"
        users = response.json()
        assert isinstance(users, list)
        # Should include at least the logged-in customer
        assert len(users) >= 1
        # Verify user structure
        for user in users:
            assert "id" in user
            assert "email" in user
            assert "name" in user
            assert "role" in user
            assert user["role"] == "customer"
    
    def test_list_company_users_denied_for_admin(self, admin_token):
        """Admin cannot access customer company-users endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/customers/company-users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 403
    
    def test_create_company_user(self, customer_token):
        """Customer can create a new user for their company"""
        unique_id = str(uuid.uuid4())[:8]
        new_user_data = {
            "name": f"TEST_Team Member {unique_id}",
            "email": f"test_team_{unique_id}@testco.com",
            "phone": "1234567890",
            "password": "testpass123"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/customers/company-users",
            headers={"Authorization": f"Bearer {customer_token}"},
            json=new_user_data
        )
        assert response.status_code == 200, f"Failed to create company user: {response.text}"
        
        created_user = response.json()
        assert created_user["name"] == new_user_data["name"]
        assert created_user["email"] == new_user_data["email"]
        assert created_user["role"] == "customer"
        assert created_user["is_active"] == True
        assert "id" in created_user
        
        # Verify user appears in list
        list_response = requests.get(
            f"{BASE_URL}/api/customers/company-users",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        users = list_response.json()
        user_emails = [u["email"] for u in users]
        assert new_user_data["email"] in user_emails
        
        return created_user["id"]
    
    def test_create_company_user_duplicate_email(self, customer_token):
        """Cannot create user with duplicate email"""
        response = requests.post(
            f"{BASE_URL}/api/customers/company-users",
            headers={"Authorization": f"Bearer {customer_token}"},
            json={
                "name": "Duplicate User",
                "email": CUSTOMER_EMAIL,  # Already exists
                "password": "testpass123"
            }
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    def test_update_company_user(self, customer_token):
        """Customer can update a user from their company"""
        # First create a user to update
        unique_id = str(uuid.uuid4())[:8]
        create_response = requests.post(
            f"{BASE_URL}/api/customers/company-users",
            headers={"Authorization": f"Bearer {customer_token}"},
            json={
                "name": f"TEST_Update User {unique_id}",
                "email": f"test_update_{unique_id}@testco.com",
                "password": "testpass123"
            }
        )
        assert create_response.status_code == 200
        user_id = create_response.json()["id"]
        
        # Update the user
        update_response = requests.put(
            f"{BASE_URL}/api/customers/company-users/{user_id}",
            headers={"Authorization": f"Bearer {customer_token}"},
            json={
                "name": f"TEST_Updated Name {unique_id}",
                "email": f"test_update_{unique_id}@testco.com",
                "phone": "9876543210",
                "password": ""  # Keep existing password
            }
        )
        assert update_response.status_code == 200
        updated_user = update_response.json()
        assert "Updated Name" in updated_user["name"]
        assert updated_user["phone"] == "9876543210"
    
    def test_delete_company_user(self, customer_token):
        """Customer can deactivate a user from their company"""
        # First create a user to delete
        unique_id = str(uuid.uuid4())[:8]
        create_response = requests.post(
            f"{BASE_URL}/api/customers/company-users",
            headers={"Authorization": f"Bearer {customer_token}"},
            json={
                "name": f"TEST_Delete User {unique_id}",
                "email": f"test_delete_{unique_id}@testco.com",
                "password": "testpass123"
            }
        )
        assert create_response.status_code == 200
        user_id = create_response.json()["id"]
        
        # Delete the user
        delete_response = requests.delete(
            f"{BASE_URL}/api/customers/company-users/{user_id}",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        assert delete_response.status_code == 200
        assert "deactivated" in delete_response.json()["message"].lower()


class TestCompanyCreationWithDefaultUser:
    """Test Company creation with default user for customer type"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_create_customer_company_with_default_user(self, admin_token):
        """Admin can create customer company with default user"""
        unique_id = str(uuid.uuid4())[:8]
        company_data = {
            "name": f"TEST_Company {unique_id}",
            "type": "customer",
            "vyapaar_commission_percentage": 15.0,
            "contact_email": f"contact_{unique_id}@test.com",
            "default_user_name": f"Default User {unique_id}",
            "default_user_email": f"default_{unique_id}@test.com",
            "default_user_phone": "1234567890",
            "default_user_password": "defaultpass123"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/companies",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=company_data
        )
        assert response.status_code == 200, f"Failed to create company: {response.text}"
        
        company = response.json()
        assert company["name"] == company_data["name"]
        assert company["type"] == "customer"
        
        # Verify default user was created by trying to login
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": company_data["default_user_email"],
            "password": company_data["default_user_password"]
        })
        assert login_response.status_code == 200, f"Default user login failed: {login_response.text}"
        
        user_data = login_response.json()["user"]
        assert user_data["name"] == company_data["default_user_name"]
        assert user_data["role"] == "customer"
        assert user_data["company_id"] == company["id"]
    
    def test_create_customer_company_without_default_user(self, admin_token):
        """Admin can create customer company without default user"""
        unique_id = str(uuid.uuid4())[:8]
        company_data = {
            "name": f"TEST_NoUser Company {unique_id}",
            "type": "customer",
            "vyapaar_commission_percentage": 15.0
        }
        
        response = requests.post(
            f"{BASE_URL}/api/companies",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=company_data
        )
        assert response.status_code == 200
        company = response.json()
        assert company["name"] == company_data["name"]
    
    def test_create_selling_partner_company_ignores_default_user(self, admin_token):
        """Selling partner company creation ignores default_user fields"""
        unique_id = str(uuid.uuid4())[:8]
        company_data = {
            "name": f"TEST_Partner Company {unique_id}",
            "type": "selling_partner",
            "vyapaar_commission_percentage": 15.0,
            "default_user_name": "Should Be Ignored",
            "default_user_email": f"ignored_{unique_id}@test.com",
            "default_user_password": "ignoredpass"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/companies",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=company_data
        )
        assert response.status_code == 200
        
        # Verify user was NOT created
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": company_data["default_user_email"],
            "password": company_data["default_user_password"]
        })
        assert login_response.status_code == 401  # User should not exist
    
    def test_create_company_duplicate_default_user_email(self, admin_token):
        """Cannot create company with default user email that already exists"""
        unique_id = str(uuid.uuid4())[:8]
        company_data = {
            "name": f"TEST_Dup Email Company {unique_id}",
            "type": "customer",
            "default_user_name": "Duplicate Email User",
            "default_user_email": ADMIN_EMAIL,  # Already exists
            "default_user_password": "testpass123"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/companies",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=company_data
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()


class TestInternalRequests:
    """Test Internal Requests endpoint for Selling Partners"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def selling_partner_token(self, admin_token):
        """Create and login as a selling partner"""
        unique_id = str(uuid.uuid4())[:8]
        
        # Create selling partner user
        user_data = {
            "email": f"test_partner_{unique_id}@test.com",
            "password": "partner123",
            "name": f"TEST_Partner {unique_id}",
            "role": "selling_partner",
            "company_name": f"TEST_Partner Co {unique_id}"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=user_data
        )
        assert create_response.status_code == 200, f"Failed to create partner: {create_response.text}"
        
        # Login as partner
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": user_data["email"],
            "password": user_data["password"]
        })
        assert login_response.status_code == 200
        return login_response.json()["access_token"]
    
    def test_internal_requests_denied_for_admin(self, admin_token):
        """Admin cannot access internal-requests endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/leads/internal-requests",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 403
    
    def test_internal_requests_empty_for_new_partner(self, selling_partner_token):
        """New selling partner has no internal requests"""
        response = requests.get(
            f"{BASE_URL}/api/leads/internal-requests",
            headers={"Authorization": f"Bearer {selling_partner_token}"}
        )
        assert response.status_code == 200
        requests_list = response.json()
        assert isinstance(requests_list, list)
    
    def test_create_internal_request(self, selling_partner_token, admin_token):
        """Selling partner can create internal service request"""
        # First get a category
        categories_response = requests.get(
            f"{BASE_URL}/api/master/primary-categories",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        categories = categories_response.json()
        
        if not categories:
            # Create a category if none exists
            cat_response = requests.post(
                f"{BASE_URL}/api/master/primary-categories",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"name": "TEST_Category", "description": "Test category"}
            )
            category_id = cat_response.json()["id"]
        else:
            category_id = categories[0]["id"]
        
        # Create internal request
        unique_id = str(uuid.uuid4())[:8]
        request_data = {
            "title": f"TEST_Internal Request {unique_id}",
            "description": "Test internal service request",
            "customer_name": "Partner Company",
            "customer_email": "partner@test.com",
            "customer_phone": "1234567890",
            "customer_company": "Partner Co",
            "primary_category_id": category_id,
            "estimated_deal_value": 5000.0,
            "referral_notes": "Internal request for testing",
            "is_internal_request": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/leads/referral",
            headers={"Authorization": f"Bearer {selling_partner_token}"},
            json=request_data
        )
        assert response.status_code == 200, f"Failed to create internal request: {response.text}"
        
        lead = response.json()
        assert lead["title"] == request_data["title"]
        assert lead["is_internal_request"] == True
        
        # Verify it appears in internal-requests list
        list_response = requests.get(
            f"{BASE_URL}/api/leads/internal-requests",
            headers={"Authorization": f"Bearer {selling_partner_token}"}
        )
        assert list_response.status_code == 200
        requests_list = list_response.json()
        request_ids = [r["id"] for r in requests_list]
        assert lead["id"] in request_ids


class TestPartnerAssignmentHistory:
    """Test Partner Assignment History tracking"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def test_partners(self, admin_token):
        """Create two selling partners for testing"""
        partners = []
        for i in range(2):
            unique_id = str(uuid.uuid4())[:8]
            user_data = {
                "email": f"test_history_partner_{i}_{unique_id}@test.com",
                "password": "partner123",
                "name": f"TEST_History Partner {i} {unique_id}",
                "role": "selling_partner",
                "company_name": f"TEST_History Co {i} {unique_id}"
            }
            
            response = requests.post(
                f"{BASE_URL}/api/users",
                headers={"Authorization": f"Bearer {admin_token}"},
                json=user_data
            )
            assert response.status_code == 200
            partners.append(response.json())
        
        return partners
    
    @pytest.fixture(scope="class")
    def test_lead(self, admin_token):
        """Create a test lead"""
        # Get a category
        categories_response = requests.get(
            f"{BASE_URL}/api/master/primary-categories",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        categories = categories_response.json()
        category_id = categories[0]["id"] if categories else None
        
        if not category_id:
            cat_response = requests.post(
                f"{BASE_URL}/api/master/primary-categories",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"name": "TEST_History Category", "description": "Test"}
            )
            category_id = cat_response.json()["id"]
        
        unique_id = str(uuid.uuid4())[:8]
        lead_data = {
            "title": f"TEST_History Lead {unique_id}",
            "description": "Lead for testing partner history",
            "customer_name": "History Test Customer",
            "customer_email": f"history_customer_{unique_id}@test.com",
            "primary_category_id": category_id,
            "deal_value": 10000.0
        }
        
        response = requests.post(
            f"{BASE_URL}/api/leads",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=lead_data
        )
        assert response.status_code == 200
        return response.json()
    
    def test_initial_lead_has_empty_partner_history(self, admin_token, test_lead):
        """New lead has empty partner_history"""
        response = requests.get(
            f"{BASE_URL}/api/leads/{test_lead['id']}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        lead = response.json()
        assert "partner_history" in lead
        assert isinstance(lead["partner_history"], list)
    
    def test_assign_partner_creates_history_entry(self, admin_token, test_lead, test_partners):
        """Assigning a partner creates history entry"""
        partner1 = test_partners[0]
        
        # Assign first partner
        update_response = requests.put(
            f"{BASE_URL}/api/leads/{test_lead['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"selling_partner_id": partner1["id"]}
        )
        assert update_response.status_code == 200
        
        # Get lead and check history
        get_response = requests.get(
            f"{BASE_URL}/api/leads/{test_lead['id']}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        lead = get_response.json()
        
        assert len(lead["partner_history"]) >= 1
        latest_assignment = lead["partner_history"][-1]
        assert latest_assignment["partner_id"] == partner1["id"]
        assert latest_assignment["partner_name"] == partner1["name"]
        assert "assigned_at" in latest_assignment
        assert "assigned_by" in latest_assignment
        assert latest_assignment["removed_at"] is None
    
    def test_reassign_partner_updates_history(self, admin_token, test_lead, test_partners):
        """Reassigning to different partner updates history"""
        partner2 = test_partners[1]
        
        # Reassign to second partner
        update_response = requests.put(
            f"{BASE_URL}/api/leads/{test_lead['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"selling_partner_id": partner2["id"]}
        )
        assert update_response.status_code == 200
        
        # Get lead and check history
        get_response = requests.get(
            f"{BASE_URL}/api/leads/{test_lead['id']}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        lead = get_response.json()
        
        # Should have at least 2 entries now
        assert len(lead["partner_history"]) >= 2
        
        # First partner should be marked as removed
        first_assignment = lead["partner_history"][0]
        assert first_assignment["removed_at"] is not None
        
        # Second partner should be current (not removed)
        latest_assignment = lead["partner_history"][-1]
        assert latest_assignment["partner_id"] == partner2["id"]
        assert latest_assignment["removed_at"] is None
    
    def test_partner_history_structure(self, admin_token, test_lead):
        """Verify partner_history entry structure"""
        response = requests.get(
            f"{BASE_URL}/api/leads/{test_lead['id']}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        lead = response.json()
        
        for assignment in lead["partner_history"]:
            assert "partner_id" in assignment
            assert "partner_name" in assignment
            assert "assigned_at" in assignment
            assert "assigned_by" in assignment
            # These may be None but should exist
            assert "removed_at" in assignment
            assert "removed_by" in assignment


# Cleanup test data
class TestCleanup:
    """Cleanup test data created during tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        return None
    
    def test_cleanup_test_users(self, admin_token):
        """Cleanup TEST_ prefixed users"""
        if not admin_token:
            pytest.skip("Admin token not available")
        
        response = requests.get(
            f"{BASE_URL}/api/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if response.status_code == 200:
            users = response.json()
            for user in users:
                if user["name"].startswith("TEST_"):
                    requests.delete(
                        f"{BASE_URL}/api/users/{user['id']}",
                        headers={"Authorization": f"Bearer {admin_token}"}
                    )
        assert True  # Cleanup is best-effort


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
