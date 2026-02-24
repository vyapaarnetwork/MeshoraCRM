"""
Test Multi-Partner Assignment Feature for Vyapaar Network CRM
Tests:
- POST /api/leads/{id}/assign-partner - Assign additional partner to lead
- POST /api/leads/{id}/mark-partner-won - Mark one partner as winner (others become lost)
- POST /api/leads/{id}/remove-partner - Remove partner from lead (mark as lost)
- Lead Response - assigned_partners array with status (active/won/lost)
- Lead Response - active_partners_count shows number of currently active partners
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMultiPartnerAssignment:
    """Test multi-partner concurrent assignment feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.admin_email = "admin@vyapaarnetwork.com"
        self.admin_password = "admin123"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.admin_email,
            "password": self.admin_password
        })
        assert login_response.status_code == 200, f"Admin login failed: {login_response.text}"
        token = login_response.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get or create test data
        self._setup_test_data()
        
        yield
        
        # Cleanup
        self._cleanup_test_data()
    
    def _setup_test_data(self):
        """Create test partners and lead for testing"""
        # Get existing selling partners
        partners_response = self.session.get(f"{BASE_URL}/api/users?role=selling_partner")
        assert partners_response.status_code == 200
        partners = partners_response.json()
        
        # We need at least 2 partners for testing
        if len(partners) < 2:
            # Create test partners
            for i in range(2 - len(partners)):
                unique_id = str(uuid.uuid4())[:8]
                partner_data = {
                    "email": f"TEST_partner_{unique_id}@test.com",
                    "password": "test123",
                    "name": f"TEST Partner {i+1}",
                    "role": "selling_partner",
                    "company_name": f"TEST Partner Company {i+1}"
                }
                create_response = self.session.post(f"{BASE_URL}/api/users", json=partner_data)
                if create_response.status_code == 200:
                    partners.append(create_response.json())
        
        self.partner_ids = [p['id'] for p in partners[:3] if p.get('is_active', True)]
        self.partner_names = {p['id']: p['name'] for p in partners[:3]}
        
        # Get primary category
        categories_response = self.session.get(f"{BASE_URL}/api/master/primary-categories")
        assert categories_response.status_code == 200
        categories = categories_response.json()
        self.primary_category_id = categories[0]['id'] if categories else None
        
        # Create a test lead for multi-partner testing
        unique_id = str(uuid.uuid4())[:8]
        lead_data = {
            "title": f"TEST Multi-Partner Lead {unique_id}",
            "description": "Test lead for multi-partner assignment testing",
            "customer_name": "Test Customer",
            "customer_email": f"test_customer_{unique_id}@test.com",
            "customer_phone": "1234567890",
            "primary_category_id": self.primary_category_id,
            "deal_value": 50000
        }
        lead_response = self.session.post(f"{BASE_URL}/api/leads", json=lead_data)
        assert lead_response.status_code == 200, f"Failed to create test lead: {lead_response.text}"
        self.test_lead_id = lead_response.json()['id']
        self.test_lead_title = lead_response.json()['title']
    
    def _cleanup_test_data(self):
        """Cleanup test data"""
        # Delete test lead
        if hasattr(self, 'test_lead_id'):
            self.session.delete(f"{BASE_URL}/api/leads/{self.test_lead_id}")
    
    # ==================== ASSIGN PARTNER TESTS ====================
    
    def test_assign_first_partner_to_lead(self):
        """Test assigning first partner to a lead"""
        if len(self.partner_ids) < 1:
            pytest.skip("No partners available for testing")
        
        partner_id = self.partner_ids[0]
        response = self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/assign-partner",
            json={"partner_id": partner_id, "notes": "First partner assignment"}
        )
        
        assert response.status_code == 200, f"Failed to assign partner: {response.text}"
        lead = response.json()
        
        # Verify assigned_partners array
        assert 'assigned_partners' in lead, "assigned_partners field missing"
        assert len(lead['assigned_partners']) >= 1, "No partners in assigned_partners"
        
        # Find the assigned partner
        assigned = next((p for p in lead['assigned_partners'] if p['partner_id'] == partner_id), None)
        assert assigned is not None, "Assigned partner not found in array"
        assert assigned['status'] == 'active', f"Partner status should be 'active', got '{assigned['status']}'"
        assert assigned['partner_name'] is not None, "Partner name should be populated"
        assert assigned['assigned_at'] is not None, "assigned_at should be set"
        assert assigned['assigned_by'] is not None, "assigned_by should be set"
        
        # Verify active_partners_count
        assert lead['active_partners_count'] >= 1, "active_partners_count should be at least 1"
        
        print(f"✓ First partner assigned successfully: {assigned['partner_name']}")
    
    def test_assign_second_partner_concurrent(self):
        """Test assigning second partner to same lead (concurrent assignment)"""
        if len(self.partner_ids) < 2:
            pytest.skip("Need at least 2 partners for concurrent assignment test")
        
        # First assign partner 1
        partner1_id = self.partner_ids[0]
        self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/assign-partner",
            json={"partner_id": partner1_id}
        )
        
        # Then assign partner 2
        partner2_id = self.partner_ids[1]
        response = self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/assign-partner",
            json={"partner_id": partner2_id, "notes": "Second concurrent partner"}
        )
        
        assert response.status_code == 200, f"Failed to assign second partner: {response.text}"
        lead = response.json()
        
        # Verify both partners are in assigned_partners
        active_partners = [p for p in lead['assigned_partners'] if p['status'] == 'active']
        assert len(active_partners) >= 2, f"Expected at least 2 active partners, got {len(active_partners)}"
        
        # Verify active_partners_count
        assert lead['active_partners_count'] >= 2, f"active_partners_count should be at least 2, got {lead['active_partners_count']}"
        
        print(f"✓ Two partners assigned concurrently. Active count: {lead['active_partners_count']}")
    
    def test_assign_duplicate_partner_fails(self):
        """Test that assigning same partner twice fails"""
        if len(self.partner_ids) < 1:
            pytest.skip("No partners available for testing")
        
        partner_id = self.partner_ids[0]
        
        # First assignment
        self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/assign-partner",
            json={"partner_id": partner_id}
        )
        
        # Second assignment of same partner should fail
        response = self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/assign-partner",
            json={"partner_id": partner_id}
        )
        
        assert response.status_code == 400, f"Expected 400 for duplicate assignment, got {response.status_code}"
        assert "already assigned" in response.json().get('detail', '').lower(), "Error message should mention already assigned"
        
        print("✓ Duplicate partner assignment correctly rejected")
    
    def test_assign_invalid_partner_fails(self):
        """Test that assigning non-existent partner fails"""
        fake_partner_id = str(uuid.uuid4())
        
        response = self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/assign-partner",
            json={"partner_id": fake_partner_id}
        )
        
        assert response.status_code == 404, f"Expected 404 for invalid partner, got {response.status_code}"
        
        print("✓ Invalid partner assignment correctly rejected")
    
    # ==================== MARK PARTNER WON TESTS ====================
    
    def test_mark_partner_won_single_partner(self):
        """Test marking a partner as winner when only one partner assigned"""
        if len(self.partner_ids) < 1:
            pytest.skip("No partners available for testing")
        
        partner_id = self.partner_ids[0]
        
        # Assign partner
        self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/assign-partner",
            json={"partner_id": partner_id}
        )
        
        # Mark as won
        response = self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/mark-partner-won",
            json={"partner_id": partner_id, "notes": "Won the deal!"}
        )
        
        assert response.status_code == 200, f"Failed to mark partner won: {response.text}"
        lead = response.json()
        
        # Verify partner status is 'won'
        winner = next((p for p in lead['assigned_partners'] if p['partner_id'] == partner_id), None)
        assert winner is not None, "Winner not found in assigned_partners"
        assert winner['status'] == 'won', f"Winner status should be 'won', got '{winner['status']}'"
        assert winner['won_at'] is not None, "won_at should be set"
        
        # Verify selling_partner_id is set to winner
        assert lead['selling_partner_id'] == partner_id, "selling_partner_id should be set to winner"
        
        # Verify active_partners_count is 0 (no more active partners)
        assert lead['active_partners_count'] == 0, f"active_partners_count should be 0 after win, got {lead['active_partners_count']}"
        
        print(f"✓ Partner marked as winner: {winner['partner_name']}")
    
    def test_mark_partner_won_multiple_partners(self):
        """Test marking one partner as winner when multiple partners assigned (others become lost)"""
        if len(self.partner_ids) < 2:
            pytest.skip("Need at least 2 partners for this test")
        
        partner1_id = self.partner_ids[0]
        partner2_id = self.partner_ids[1]
        
        # Assign both partners
        self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/assign-partner",
            json={"partner_id": partner1_id}
        )
        self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/assign-partner",
            json={"partner_id": partner2_id}
        )
        
        # Mark partner1 as winner
        response = self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/mark-partner-won",
            json={"partner_id": partner1_id}
        )
        
        assert response.status_code == 200, f"Failed to mark partner won: {response.text}"
        lead = response.json()
        
        # Verify partner1 is 'won'
        winner = next((p for p in lead['assigned_partners'] if p['partner_id'] == partner1_id), None)
        assert winner is not None, "Winner not found"
        assert winner['status'] == 'won', f"Winner status should be 'won', got '{winner['status']}'"
        
        # Verify partner2 is 'lost'
        loser = next((p for p in lead['assigned_partners'] if p['partner_id'] == partner2_id), None)
        assert loser is not None, "Loser not found"
        assert loser['status'] == 'lost', f"Loser status should be 'lost', got '{loser['status']}'"
        assert loser['lost_at'] is not None, "lost_at should be set for loser"
        
        # Verify active_partners_count is 0
        assert lead['active_partners_count'] == 0, "No active partners should remain after win"
        
        print(f"✓ Partner {winner['partner_name']} won, {loser['partner_name']} marked as lost")
    
    def test_mark_non_active_partner_won_fails(self):
        """Test that marking a non-active partner as won fails"""
        if len(self.partner_ids) < 2:
            pytest.skip("Need at least 2 partners for this test")
        
        partner1_id = self.partner_ids[0]
        partner2_id = self.partner_ids[1]
        
        # Assign both partners
        self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/assign-partner",
            json={"partner_id": partner1_id}
        )
        self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/assign-partner",
            json={"partner_id": partner2_id}
        )
        
        # Mark partner1 as winner (partner2 becomes lost)
        self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/mark-partner-won",
            json={"partner_id": partner1_id}
        )
        
        # Try to mark partner2 (now lost) as won - should fail
        response = self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/mark-partner-won",
            json={"partner_id": partner2_id}
        )
        
        assert response.status_code == 400, f"Expected 400 for non-active partner, got {response.status_code}"
        
        print("✓ Marking non-active partner as won correctly rejected")
    
    def test_mark_unassigned_partner_won_fails(self):
        """Test that marking an unassigned partner as won fails"""
        fake_partner_id = str(uuid.uuid4())
        
        response = self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/mark-partner-won",
            json={"partner_id": fake_partner_id}
        )
        
        assert response.status_code == 400, f"Expected 400 for unassigned partner, got {response.status_code}"
        
        print("✓ Marking unassigned partner as won correctly rejected")
    
    # ==================== REMOVE PARTNER TESTS ====================
    
    def test_remove_partner_from_lead(self):
        """Test removing a partner from lead (marks as lost)"""
        if len(self.partner_ids) < 1:
            pytest.skip("No partners available for testing")
        
        partner_id = self.partner_ids[0]
        
        # Assign partner
        self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/assign-partner",
            json={"partner_id": partner_id}
        )
        
        # Remove partner
        response = self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/remove-partner",
            json={"partner_id": partner_id, "notes": "Removed for testing"}
        )
        
        assert response.status_code == 200, f"Failed to remove partner: {response.text}"
        lead = response.json()
        
        # Verify partner status is 'lost'
        removed = next((p for p in lead['assigned_partners'] if p['partner_id'] == partner_id), None)
        assert removed is not None, "Removed partner should still be in array"
        assert removed['status'] == 'lost', f"Removed partner status should be 'lost', got '{removed['status']}'"
        assert removed['lost_at'] is not None, "lost_at should be set"
        
        # Verify active_partners_count decreased
        assert lead['active_partners_count'] == 0, "active_partners_count should be 0 after removal"
        
        print(f"✓ Partner removed (marked as lost): {removed['partner_name']}")
    
    def test_remove_non_active_partner_fails(self):
        """Test that removing a non-active partner fails"""
        if len(self.partner_ids) < 1:
            pytest.skip("No partners available for testing")
        
        partner_id = self.partner_ids[0]
        
        # Assign and then remove partner
        self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/assign-partner",
            json={"partner_id": partner_id}
        )
        self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/remove-partner",
            json={"partner_id": partner_id}
        )
        
        # Try to remove again - should fail
        response = self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/remove-partner",
            json={"partner_id": partner_id}
        )
        
        assert response.status_code == 400, f"Expected 400 for non-active partner, got {response.status_code}"
        
        print("✓ Removing non-active partner correctly rejected")
    
    # ==================== LEAD RESPONSE STRUCTURE TESTS ====================
    
    def test_lead_response_has_assigned_partners_array(self):
        """Test that lead response includes assigned_partners array"""
        response = self.session.get(f"{BASE_URL}/api/leads/{self.test_lead_id}")
        
        assert response.status_code == 200
        lead = response.json()
        
        assert 'assigned_partners' in lead, "assigned_partners field missing from lead response"
        assert isinstance(lead['assigned_partners'], list), "assigned_partners should be a list"
        
        print("✓ Lead response includes assigned_partners array")
    
    def test_lead_response_has_active_partners_count(self):
        """Test that lead response includes active_partners_count"""
        response = self.session.get(f"{BASE_URL}/api/leads/{self.test_lead_id}")
        
        assert response.status_code == 200
        lead = response.json()
        
        assert 'active_partners_count' in lead, "active_partners_count field missing from lead response"
        assert isinstance(lead['active_partners_count'], int), "active_partners_count should be an integer"
        
        print("✓ Lead response includes active_partners_count")
    
    def test_partner_assignment_structure(self):
        """Test that partner assignment has correct structure"""
        if len(self.partner_ids) < 1:
            pytest.skip("No partners available for testing")
        
        partner_id = self.partner_ids[0]
        
        # Assign partner
        response = self.session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/assign-partner",
            json={"partner_id": partner_id}
        )
        
        assert response.status_code == 200
        lead = response.json()
        
        assignment = lead['assigned_partners'][0]
        
        # Verify all required fields
        required_fields = ['partner_id', 'partner_name', 'assigned_at', 'assigned_by', 'assigned_by_name', 'status']
        for field in required_fields:
            assert field in assignment, f"Missing field: {field}"
        
        # Verify optional fields exist (can be None)
        optional_fields = ['won_at', 'lost_at', 'notes']
        for field in optional_fields:
            assert field in assignment, f"Missing optional field: {field}"
        
        print(f"✓ Partner assignment has correct structure: {list(assignment.keys())}")
    
    # ==================== EXISTING LEAD WITH MULTI-PARTNER TEST ====================
    
    def test_existing_lead_with_multi_partner(self):
        """Test the existing lead mentioned in the request (1ff464e7-cb58-4b26-b538-cbf2a618febc)"""
        lead_id = "1ff464e7-cb58-4b26-b538-cbf2a618febc"
        
        response = self.session.get(f"{BASE_URL}/api/leads/{lead_id}")
        
        if response.status_code == 404:
            pytest.skip("Test lead not found - may have been deleted")
        
        assert response.status_code == 200, f"Failed to get lead: {response.text}"
        lead = response.json()
        
        # Verify assigned_partners exists
        assert 'assigned_partners' in lead, "assigned_partners missing"
        
        # Check if there are partners with different statuses
        statuses = [p['status'] for p in lead.get('assigned_partners', [])]
        print(f"✓ Existing lead has {len(lead['assigned_partners'])} partners with statuses: {statuses}")
        
        # Verify active_partners_count matches
        active_count = len([p for p in lead['assigned_partners'] if p['status'] == 'active'])
        assert lead['active_partners_count'] == active_count, f"active_partners_count mismatch: {lead['active_partners_count']} vs {active_count}"
        
        print(f"✓ Existing lead verified: {lead['title']}")


class TestMultiPartnerPermissions:
    """Test permission restrictions for multi-partner endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin first to get a lead ID
        admin_login = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@vyapaarnetwork.com",
            "password": "admin123"
        })
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        # Get a lead ID
        leads_response = self.session.get(f"{BASE_URL}/api/leads?limit=1")
        if leads_response.status_code == 200 and leads_response.json():
            self.test_lead_id = leads_response.json()[0]['id']
        else:
            self.test_lead_id = None
        
        # Get a partner ID
        partners_response = self.session.get(f"{BASE_URL}/api/users?role=selling_partner")
        if partners_response.status_code == 200 and partners_response.json():
            self.test_partner_id = partners_response.json()[0]['id']
        else:
            self.test_partner_id = None
        
        yield
    
    def test_non_admin_cannot_assign_partner(self):
        """Test that non-admin users cannot assign partners"""
        if not self.test_lead_id or not self.test_partner_id:
            pytest.skip("No test data available")
        
        # Create a customer user for testing
        unique_id = str(uuid.uuid4())[:8]
        customer_data = {
            "email": f"TEST_customer_{unique_id}@test.com",
            "password": "test123",
            "name": "TEST Customer User",
            "role": "customer"
        }
        
        # Register as customer
        register_response = self.session.post(f"{BASE_URL}/api/auth/register", json=customer_data)
        if register_response.status_code != 200:
            pytest.skip("Could not create test customer")
        
        customer_token = register_response.json()["access_token"]
        
        # Try to assign partner as customer
        customer_session = requests.Session()
        customer_session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {customer_token}"
        })
        
        response = customer_session.post(
            f"{BASE_URL}/api/leads/{self.test_lead_id}/assign-partner",
            json={"partner_id": self.test_partner_id}
        )
        
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
        
        print("✓ Non-admin correctly denied from assigning partners")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
