#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for Vyapaar Network CRM
Tests all endpoints, authentication, RBAC, and core functionality
"""

import requests
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class VyapaarCRMTester:
    def __init__(self, base_url: str = "https://vyapaar-preview-1.preview.emergentagent.com"):
        self.base_url = base_url.rstrip('/')
        self.admin_token = None
        self.partner_token = None
        self.associate_token = None
        self.customer_token = None
        
        # Test data storage
        self.test_data = {
            'users': {},
            'companies': {},
            'categories': {},
            'statuses': {},
            'templates': {},
            'leads': {}
        }
        
        # Test results
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
        
    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, headers: Optional[Dict] = None, 
                 token: Optional[str] = None) -> tuple:
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint.lstrip('/')}"
        
        # Prepare headers
        test_headers = {'Content-Type': 'application/json'}
        if token:
            test_headers['Authorization'] = f'Bearer {token}'
        if headers:
            test_headers.update(headers)
        
        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}")
                try:
                    return True, response.json() if response.content else {}
                except:
                    return True, {}
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    self.log(f"   Error: {error_detail}")
                except:
                    self.log(f"   Response: {response.text[:200]}")
                
                self.failed_tests.append({
                    'name': name,
                    'expected': expected_status,
                    'actual': response.status_code,
                    'endpoint': endpoint,
                    'method': method
                })
                return False, {}
                
        except Exception as e:
            self.log(f"❌ {name} - Exception: {str(e)}", "ERROR")
            self.failed_tests.append({
                'name': name,
                'error': str(e),
                'endpoint': endpoint,
                'method': method
            })
            return False, {}
    
    def test_health_check(self):
        """Test basic connectivity"""
        self.log("=== HEALTH CHECK ===")
        success, _ = self.run_test("Health Check", "GET", "/health", 200)
        return success
    
    def test_seed_data(self):
        """Initialize seed data"""
        self.log("=== SEED DATA ===")
        success, _ = self.run_test("Seed Data", "POST", "/seed", 200)
        return success
    
    def test_authentication(self):
        """Test user registration and login"""
        self.log("=== AUTHENTICATION TESTS ===")
        
        # Test admin login
        admin_success, admin_response = self.run_test(
            "Admin Login",
            "POST",
            "/auth/login",
            200,
            {"email": "admin@vyapaarnetwork.com", "password": "admin123"}
        )
        
        if admin_success and 'access_token' in admin_response:
            self.admin_token = admin_response['access_token']
            self.test_data['users']['admin'] = admin_response['user']
            self.log("✅ Admin token obtained")
        else:
            self.log("❌ Failed to get admin token", "ERROR")
            return False
        
        # Test user registration for different roles
        test_users = [
            {
                'role': 'selling_partner',
                'email': 'partner@test.com',
                'password': 'test123',
                'name': 'Test Partner',
                'company_name': 'Test Partner Company'
            },
            {
                'role': 'sales_associate',
                'email': 'associate@test.com',
                'password': 'test123',
                'name': 'Test Associate'
            },
            {
                'role': 'customer',
                'email': 'customer@test.com',
                'password': 'test123',
                'name': 'Test Customer',
                'company_name': 'Test Customer Company'
            }
        ]
        
        for user_data in test_users:
            # Register user
            success, response = self.run_test(
                f"Register {user_data['role']}",
                "POST",
                "/auth/register",
                200,
                user_data
            )
            
            if success and 'access_token' in response:
                token_key = f"{user_data['role']}_token"
                setattr(self, token_key, response['access_token'])
                self.test_data['users'][user_data['role']] = response['user']
                
                # Test login with new user
                login_success, login_response = self.run_test(
                    f"Login {user_data['role']}",
                    "POST",
                    "/auth/login",
                    200,
                    {"email": user_data['email'], "password": user_data['password']}
                )
        
        # Test /auth/me endpoint
        self.run_test("Get Current User", "GET", "/auth/me", 200, token=self.admin_token)
        
        return True
    
    def test_rbac(self):
        """Test Role-Based Access Control"""
        self.log("=== RBAC TESTS ===")
        
        # Test admin-only endpoints with different roles
        admin_endpoints = [
            ("GET", "/users"),
            ("GET", "/master/primary-categories"),
            ("POST", "/master/primary-categories", {"name": "Test Category"}),
        ]
        
        for method, endpoint, *data in admin_endpoints:
            payload = data[0] if data else None
            
            # Should work with admin token
            self.run_test(
                f"Admin access to {endpoint}",
                method,
                endpoint,
                200 if method == "GET" else 200,
                payload,
                token=self.admin_token
            )
            
            # Should fail with partner token
            if hasattr(self, 'partner_token') and self.partner_token:
                self.run_test(
                    f"Partner denied access to {endpoint}",
                    method,
                    endpoint,
                    403,
                    payload,
                    token=self.partner_token
                )
    
    def test_master_data(self):
        """Test master data management"""
        self.log("=== MASTER DATA TESTS ===")
        
        # Test Lead Statuses
        success, statuses = self.run_test("List Lead Statuses", "GET", "/master/lead-status", 200, token=self.admin_token)
        if success:
            self.test_data['statuses'] = statuses
        
        # Test Primary Categories
        success, categories = self.run_test("List Primary Categories", "GET", "/master/primary-categories", 200, token=self.admin_token)
        if success:
            self.test_data['categories']['primary'] = categories
        
        # Test Secondary Categories
        success, sec_categories = self.run_test("List Secondary Categories", "GET", "/master/secondary-categories", 200, token=self.admin_token)
        if success:
            self.test_data['categories']['secondary'] = sec_categories
        
        # Test Commission Templates
        success, templates = self.run_test("List Commission Templates", "GET", "/master/commission-templates", 200, token=self.admin_token)
        if success:
            self.test_data['templates'] = templates
        
        # Test creating new items
        if self.test_data['categories']['primary']:
            primary_id = self.test_data['categories']['primary'][0]['id']
            
            # Create secondary category
            self.run_test(
                "Create Secondary Category",
                "POST",
                "/master/secondary-categories",
                200,
                {
                    "name": "Test Sub Category",
                    "primary_category_id": primary_id,
                    "description": "Test description"
                },
                token=self.admin_token
            )
    
    def test_companies(self):
        """Test company management"""
        self.log("=== COMPANY TESTS ===")
        
        # List companies
        success, companies = self.run_test("List Companies", "GET", "/companies", 200, token=self.admin_token)
        if success:
            self.test_data['companies'] = companies
        
        # Create company
        self.run_test(
            "Create Company",
            "POST",
            "/companies",
            200,
            {
                "name": "Test Company",
                "type": "selling_partner",
                "vyapaar_commission_percentage": 12.0,
                "contact_email": "test@company.com"
            },
            token=self.admin_token
        )
    
    def test_leads(self):
        """Test lead management"""
        self.log("=== LEAD TESTS ===")
        
        # Get required data for lead creation
        if not self.test_data['categories']['primary']:
            self.log("❌ No primary categories available for lead testing", "ERROR")
            return False
        
        primary_category_id = self.test_data['categories']['primary'][0]['id']
        
        # Create lead
        lead_data = {
            "title": "Test Lead",
            "description": "Test lead description",
            "customer_name": "John Doe",
            "customer_email": "john@example.com",
            "customer_phone": "+91 9876543210",
            "customer_company": "John's Company",
            "primary_category_id": primary_category_id,
            "deal_value": 50000.0
        }
        
        success, lead_response = self.run_test(
            "Create Lead",
            "POST",
            "/leads",
            200,
            lead_data,
            token=self.admin_token
        )
        
        if success and 'id' in lead_response:
            lead_id = lead_response['id']
            self.test_data['leads']['test_lead'] = lead_response
            
            # Test lead retrieval
            self.run_test("Get Lead", "GET", f"/leads/{lead_id}", 200, token=self.admin_token)
            
            # Test lead listing
            self.run_test("List Leads", "GET", "/leads", 200, token=self.admin_token)
            
            # Test lead update
            self.run_test(
                "Update Lead",
                "PUT",
                f"/leads/{lead_id}",
                200,
                {"title": "Updated Test Lead", "deal_value": 75000.0},
                token=self.admin_token
            )
            
            # Test follow-up creation
            self.run_test(
                "Add Follow-up",
                "POST",
                f"/leads/{lead_id}/follow-ups",
                200,
                {
                    "scheduled_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
                    "notes": "Follow up with customer"
                },
                token=self.admin_token
            )
            
            # Test comment creation
            self.run_test(
                "Add Comment",
                "POST",
                f"/leads/{lead_id}/comments",
                200,
                {"content": "This is a test comment"},
                token=self.admin_token
            )
        
        return True
    
    def test_dashboard_reports(self):
        """Test dashboard and reporting"""
        self.log("=== DASHBOARD & REPORTS TESTS ===")
        
        # Test dashboard stats
        self.run_test("Dashboard Stats", "GET", "/dashboard/stats", 200, token=self.admin_token)
        
        # Test reports export
        self.run_test("Export Reports", "GET", "/reports/export?format=csv", 200, token=self.admin_token)
        
        # Test partner-specific reports
        if 'selling_partner' in self.test_data['users']:
            partner_id = self.test_data['users']['selling_partner']['id']
            self.run_test(
                "Selling Partner Report",
                "GET",
                f"/reports/selling-partner/{partner_id}",
                200,
                token=self.admin_token
            )
        
        # Test associate reports
        if 'sales_associate' in self.test_data['users']:
            associate_id = self.test_data['users']['sales_associate']['id']
            self.run_test(
                "Sales Associate Report",
                "GET",
                f"/reports/sales-associate/{associate_id}",
                200,
                token=self.admin_token
            )
    
    def test_user_management(self):
        """Test user management endpoints"""
        self.log("=== USER MANAGEMENT TESTS ===")
        
        # List all users (admin only)
        self.run_test("List All Users", "GET", "/users", 200, token=self.admin_token)
        
        # List selling partners
        self.run_test("List Selling Partners", "GET", "/users/selling-partners", 200, token=self.admin_token)
        
        # List sales associates
        self.run_test("List Sales Associates", "GET", "/users/sales-associates", 200, token=self.admin_token)
    
    def run_all_tests(self):
        """Run complete test suite"""
        self.log("🚀 Starting Vyapaar Network CRM Backend Tests")
        self.log(f"Testing against: {self.base_url}")
        
        try:
            # Basic connectivity
            if not self.test_health_check():
                self.log("❌ Health check failed - aborting tests", "ERROR")
                return False
            
            # Initialize data
            self.test_seed_data()
            
            # Core functionality tests
            if not self.test_authentication():
                self.log("❌ Authentication failed - aborting remaining tests", "ERROR")
                return False
            
            self.test_rbac()
            self.test_master_data()
            self.test_companies()
            self.test_leads()
            self.test_dashboard_reports()
            self.test_user_management()
            
            return True
            
        except Exception as e:
            self.log(f"❌ Test suite failed with exception: {str(e)}", "ERROR")
            return False
    
    def print_summary(self):
        """Print test results summary"""
        self.log("=" * 50)
        self.log("📊 TEST SUMMARY")
        self.log("=" * 50)
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        
        self.log(f"Total Tests: {self.tests_run}")
        self.log(f"Passed: {self.tests_passed}")
        self.log(f"Failed: {len(self.failed_tests)}")
        self.log(f"Success Rate: {success_rate:.1f}%")
        
        if self.failed_tests:
            self.log("\n❌ FAILED TESTS:")
            for test in self.failed_tests:
                if 'error' in test:
                    self.log(f"  - {test['name']}: {test['error']}")
                else:
                    self.log(f"  - {test['name']}: Expected {test['expected']}, got {test['actual']}")
        
        return success_rate >= 70  # Consider 70%+ as acceptable

def main():
    """Main test execution"""
    tester = VyapaarCRMTester()
    
    try:
        success = tester.run_all_tests()
        tester.print_summary()
        
        # Return appropriate exit code
        if success and tester.tests_passed / tester.tests_run >= 0.7:
            print("\n🎉 Backend tests completed successfully!")
            return 0
        else:
            print(f"\n⚠️  Backend has issues - {len(tester.failed_tests)} failed tests")
            return 1
            
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Test execution failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())