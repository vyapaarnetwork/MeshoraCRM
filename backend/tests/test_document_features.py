"""
Test Suite for Document Features:
1. Document Tags Master Data - CRUD operations for document tags
2. Document Upload for Leads - Upload, list, download, delete documents
3. Document Upload for Companies - Upload, list, download, delete documents
"""

import pytest
import requests
import os
import uuid
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@vyapaarnetwork.com"
ADMIN_PASSWORD = "admin123"


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
def primary_category_id(admin_token):
    """Get or create a primary category"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    response = requests.get(f"{BASE_URL}/api/master/primary-categories", headers=headers)
    if response.status_code == 200 and len(response.json()) > 0:
        return response.json()[0]["id"]
    
    response = requests.post(f"{BASE_URL}/api/master/primary-categories", json={
        "name": f"Test Category {uuid.uuid4().hex[:6]}",
        "description": "Test category for testing"
    }, headers=headers)
    
    if response.status_code != 200:
        pytest.skip("Failed to create primary category")
    
    return response.json()["id"]


@pytest.fixture(scope="module")
def test_lead_id(admin_token, primary_category_id):
    """Create a test lead for document upload testing"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    unique_id = str(uuid.uuid4())[:8]
    response = requests.post(f"{BASE_URL}/api/leads", json={
        "title": f"TEST_Doc Upload Lead {unique_id}",
        "customer_name": f"Test Customer {unique_id}",
        "customer_email": f"test_doc_{unique_id}@test.com",
        "primary_category_id": primary_category_id,
        "deal_value": 50000
    }, headers=headers)
    
    if response.status_code != 200:
        pytest.skip(f"Failed to create test lead: {response.text}")
    
    return response.json()["id"]


@pytest.fixture(scope="module")
def test_company_id(admin_token):
    """Create a test company for document upload testing"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    unique_id = str(uuid.uuid4())[:8]
    response = requests.post(f"{BASE_URL}/api/companies", json={
        "name": f"TEST_Doc Company {unique_id}",
        "type": "selling_partner",
        "vyapaar_commission_percentage": 15.0,
        "contact_email": f"test_company_{unique_id}@test.com"
    }, headers=headers)
    
    if response.status_code != 200:
        pytest.skip(f"Failed to create test company: {response.text}")
    
    return response.json()["id"]


class TestDocumentTagsMasterData:
    """Test Document Tags Master Data CRUD operations"""
    
    def test_create_lead_document_tag(self, admin_token):
        """Admin can create a document tag for leads"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        unique_id = str(uuid.uuid4())[:8]
        response = requests.post(f"{BASE_URL}/api/master/document-tags", json={
            "name": f"Test Lead Tag {unique_id}",
            "tag_key": f"test_lead_tag_{unique_id}",
            "entity_type": "lead",
            "color": "#3b82f6"
        }, headers=headers)
        
        assert response.status_code == 200, f"Failed to create document tag: {response.text}"
        data = response.json()
        assert data["name"] == f"Test Lead Tag {unique_id}"
        assert data["entity_type"] == "lead"
        assert data["is_active"] == True
        assert "id" in data
        print(f"✓ Created lead document tag: {data['name']}")
        return data["id"]
    
    def test_create_company_document_tag(self, admin_token):
        """Admin can create a document tag for companies"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        unique_id = str(uuid.uuid4())[:8]
        response = requests.post(f"{BASE_URL}/api/master/document-tags", json={
            "name": f"Test Company Tag {unique_id}",
            "tag_key": f"test_company_tag_{unique_id}",
            "entity_type": "company",
            "color": "#22c55e"
        }, headers=headers)
        
        assert response.status_code == 200, f"Failed to create document tag: {response.text}"
        data = response.json()
        assert data["name"] == f"Test Company Tag {unique_id}"
        assert data["entity_type"] == "company"
        print(f"✓ Created company document tag: {data['name']}")
        return data["id"]
    
    def test_list_all_document_tags(self, admin_token):
        """List all document tags"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/master/document-tags", headers=headers)
        assert response.status_code == 200, f"Failed to list document tags: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed all document tags (count: {len(data)})")
    
    def test_list_lead_document_tags(self, admin_token):
        """List document tags filtered by entity_type=lead"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/master/document-tags?entity_type=lead", headers=headers)
        assert response.status_code == 200, f"Failed to list lead document tags: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        # All returned tags should be for leads
        for tag in data:
            assert tag["entity_type"] == "lead"
        print(f"✓ Listed lead document tags (count: {len(data)})")
    
    def test_list_company_document_tags(self, admin_token):
        """List document tags filtered by entity_type=company"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/master/document-tags?entity_type=company", headers=headers)
        assert response.status_code == 200, f"Failed to list company document tags: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        # All returned tags should be for companies
        for tag in data:
            assert tag["entity_type"] == "company"
        print(f"✓ Listed company document tags (count: {len(data)})")
    
    def test_update_document_tag(self, admin_token):
        """Admin can update a document tag"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First create a tag
        unique_id = str(uuid.uuid4())[:8]
        create_response = requests.post(f"{BASE_URL}/api/master/document-tags", json={
            "name": f"Update Test Tag {unique_id}",
            "tag_key": f"update_test_{unique_id}",
            "entity_type": "lead",
            "color": "#3b82f6"
        }, headers=headers)
        
        assert create_response.status_code == 200
        tag_id = create_response.json()["id"]
        
        # Update the tag
        update_response = requests.put(f"{BASE_URL}/api/master/document-tags/{tag_id}", json={
            "name": f"Updated Tag {unique_id}",
            "tag_key": f"updated_{unique_id}",
            "entity_type": "lead",
            "color": "#ef4444"
        }, headers=headers)
        
        assert update_response.status_code == 200, f"Failed to update document tag: {update_response.text}"
        data = update_response.json()
        assert data["name"] == f"Updated Tag {unique_id}"
        assert data["color"] == "#ef4444"
        print(f"✓ Updated document tag successfully")
    
    def test_delete_document_tag(self, admin_token):
        """Admin can delete (soft delete) a document tag"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First create a tag
        unique_id = str(uuid.uuid4())[:8]
        create_response = requests.post(f"{BASE_URL}/api/master/document-tags", json={
            "name": f"Delete Test Tag {unique_id}",
            "tag_key": f"delete_test_{unique_id}",
            "entity_type": "lead",
            "color": "#3b82f6"
        }, headers=headers)
        
        assert create_response.status_code == 200
        tag_id = create_response.json()["id"]
        
        # Delete the tag
        delete_response = requests.delete(f"{BASE_URL}/api/master/document-tags/{tag_id}", headers=headers)
        assert delete_response.status_code == 200, f"Failed to delete document tag: {delete_response.text}"
        
        # Verify tag is no longer in active list
        list_response = requests.get(f"{BASE_URL}/api/master/document-tags", headers=headers)
        tags = list_response.json()
        tag_ids = [t["id"] for t in tags]
        assert tag_id not in tag_ids, "Deleted tag should not appear in active list"
        print(f"✓ Deleted document tag successfully")
    
    def test_duplicate_tag_key_rejected(self, admin_token):
        """Duplicate tag_key within same entity_type should be rejected"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        unique_id = str(uuid.uuid4())[:8]
        tag_key = f"duplicate_test_{unique_id}"
        
        # Create first tag
        response1 = requests.post(f"{BASE_URL}/api/master/document-tags", json={
            "name": f"First Tag {unique_id}",
            "tag_key": tag_key,
            "entity_type": "lead",
            "color": "#3b82f6"
        }, headers=headers)
        assert response1.status_code == 200
        
        # Try to create duplicate
        response2 = requests.post(f"{BASE_URL}/api/master/document-tags", json={
            "name": f"Duplicate Tag {unique_id}",
            "tag_key": tag_key,
            "entity_type": "lead",
            "color": "#22c55e"
        }, headers=headers)
        assert response2.status_code == 400, "Duplicate tag_key should be rejected"
        print(f"✓ Duplicate tag_key correctly rejected")
    
    def test_invalid_entity_type_rejected(self, admin_token):
        """Invalid entity_type should be rejected"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        unique_id = str(uuid.uuid4())[:8]
        response = requests.post(f"{BASE_URL}/api/master/document-tags", json={
            "name": f"Invalid Entity Tag {unique_id}",
            "tag_key": f"invalid_entity_{unique_id}",
            "entity_type": "invalid_type",
            "color": "#3b82f6"
        }, headers=headers)
        
        assert response.status_code == 400, "Invalid entity_type should be rejected"
        print(f"✓ Invalid entity_type correctly rejected")


class TestDocumentUploadForLeads:
    """Test Document Upload functionality for Leads"""
    
    def test_upload_document_to_lead(self, admin_token, test_lead_id):
        """Upload a document to a lead"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Create a simple test file
        file_content = b"This is a test document content for lead upload testing."
        files = {
            'file': ('test_document.txt', io.BytesIO(file_content), 'text/plain')
        }
        data = {
            'entity_type': 'lead',
            'entity_id': test_lead_id,
            'tag': 'proposal',
            'description': 'Test proposal document'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents/upload",
            headers=headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 200, f"Failed to upload document: {response.text}"
        doc_data = response.json()
        assert doc_data["original_filename"] == "test_document.txt"
        assert doc_data["tag"] == "proposal"
        assert "id" in doc_data
        print(f"✓ Uploaded document to lead: {doc_data['original_filename']}")
        return doc_data["id"]
    
    def test_get_lead_documents(self, admin_token, test_lead_id):
        """Get all documents for a lead"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/documents/entity/lead/{test_lead_id}",
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed to get lead documents: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Retrieved lead documents (count: {len(data)})")
    
    def test_download_document(self, admin_token, test_lead_id):
        """Download a document"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First upload a document
        file_content = b"Download test content"
        files = {
            'file': ('download_test.txt', io.BytesIO(file_content), 'text/plain')
        }
        data = {
            'entity_type': 'lead',
            'entity_id': test_lead_id,
            'tag': 'contract'
        }
        
        upload_response = requests.post(
            f"{BASE_URL}/api/documents/upload",
            headers=headers,
            files=files,
            data=data
        )
        assert upload_response.status_code == 200
        doc_id = upload_response.json()["id"]
        
        # Download the document
        download_response = requests.get(
            f"{BASE_URL}/api/documents/{doc_id}/download",
            headers=headers
        )
        
        assert download_response.status_code == 200, f"Failed to download document: {download_response.text}"
        assert download_response.content == file_content
        print(f"✓ Downloaded document successfully")
    
    def test_delete_document(self, admin_token, test_lead_id):
        """Admin can delete a document"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First upload a document
        file_content = b"Delete test content"
        files = {
            'file': ('delete_test.txt', io.BytesIO(file_content), 'text/plain')
        }
        data = {
            'entity_type': 'lead',
            'entity_id': test_lead_id,
            'tag': 'invoice'
        }
        
        upload_response = requests.post(
            f"{BASE_URL}/api/documents/upload",
            headers=headers,
            files=files,
            data=data
        )
        assert upload_response.status_code == 200
        doc_id = upload_response.json()["id"]
        
        # Delete the document
        delete_response = requests.delete(
            f"{BASE_URL}/api/documents/{doc_id}",
            headers=headers
        )
        
        assert delete_response.status_code == 200, f"Failed to delete document: {delete_response.text}"
        
        # Verify document is deleted
        download_response = requests.get(
            f"{BASE_URL}/api/documents/{doc_id}/download",
            headers=headers
        )
        assert download_response.status_code == 404, "Deleted document should not be downloadable"
        print(f"✓ Deleted document successfully")
    
    def test_upload_with_different_tags(self, admin_token, test_lead_id):
        """Upload documents with different tags"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        tags = ['proposal', 'contract', 'invoice', 'quotation']
        
        for tag in tags:
            file_content = f"Test content for {tag}".encode()
            files = {
                'file': (f'{tag}_test.txt', io.BytesIO(file_content), 'text/plain')
            }
            data = {
                'entity_type': 'lead',
                'entity_id': test_lead_id,
                'tag': tag
            }
            
            response = requests.post(
                f"{BASE_URL}/api/documents/upload",
                headers=headers,
                files=files,
                data=data
            )
            
            assert response.status_code == 200, f"Failed to upload {tag} document: {response.text}"
            assert response.json()["tag"] == tag
        
        print(f"✓ Uploaded documents with different tags: {tags}")
    
    def test_lead_detail_includes_documents(self, admin_token, test_lead_id):
        """Lead detail response includes documents"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/leads/{test_lead_id}", headers=headers)
        assert response.status_code == 200, f"Failed to get lead: {response.text}"
        
        data = response.json()
        assert "documents" in data, "Lead response should include documents field"
        assert isinstance(data["documents"], list)
        print(f"✓ Lead detail includes documents (count: {len(data['documents'])})")


class TestDocumentUploadForCompanies:
    """Test Document Upload functionality for Companies"""
    
    def test_upload_document_to_company(self, admin_token, test_company_id):
        """Upload a document to a company"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        file_content = b"This is a corporate profile document."
        files = {
            'file': ('corporate_profile.txt', io.BytesIO(file_content), 'text/plain')
        }
        data = {
            'entity_type': 'company',
            'entity_id': test_company_id,
            'tag': 'corporate_profile',
            'description': 'Company corporate profile'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents/upload",
            headers=headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 200, f"Failed to upload company document: {response.text}"
        doc_data = response.json()
        assert doc_data["original_filename"] == "corporate_profile.txt"
        assert doc_data["tag"] == "corporate_profile"
        print(f"✓ Uploaded document to company: {doc_data['original_filename']}")
        return doc_data["id"]
    
    def test_get_company_documents(self, admin_token, test_company_id):
        """Get all documents for a company"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/documents/entity/company/{test_company_id}",
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed to get company documents: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Retrieved company documents (count: {len(data)})")
    
    def test_upload_company_brochure(self, admin_token, test_company_id):
        """Upload a brochure to a company"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        file_content = b"Company brochure content"
        files = {
            'file': ('brochure.pdf', io.BytesIO(file_content), 'application/pdf')
        }
        data = {
            'entity_type': 'company',
            'entity_id': test_company_id,
            'tag': 'brochure',
            'description': 'Company brochure 2025'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents/upload",
            headers=headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 200, f"Failed to upload brochure: {response.text}"
        doc_data = response.json()
        assert doc_data["tag"] == "brochure"
        print(f"✓ Uploaded company brochure")
    
    def test_upload_product_catalog(self, admin_token, test_company_id):
        """Upload a product catalog to a company"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        file_content = b"Product catalog content"
        files = {
            'file': ('catalog.xlsx', io.BytesIO(file_content), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        }
        data = {
            'entity_type': 'company',
            'entity_id': test_company_id,
            'tag': 'product_catalog'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents/upload",
            headers=headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 200, f"Failed to upload catalog: {response.text}"
        doc_data = response.json()
        assert doc_data["tag"] == "product_catalog"
        print(f"✓ Uploaded product catalog")


class TestDocumentValidation:
    """Test Document Upload validation"""
    
    def test_invalid_entity_type_rejected(self, admin_token, test_lead_id):
        """Invalid entity_type should be rejected"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        file_content = b"Test content"
        files = {
            'file': ('test.txt', io.BytesIO(file_content), 'text/plain')
        }
        data = {
            'entity_type': 'invalid_type',
            'entity_id': test_lead_id,
            'tag': 'proposal'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents/upload",
            headers=headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 400, "Invalid entity_type should be rejected"
        print(f"✓ Invalid entity_type correctly rejected")
    
    def test_nonexistent_lead_rejected(self, admin_token):
        """Upload to nonexistent lead should be rejected"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        file_content = b"Test content"
        files = {
            'file': ('test.txt', io.BytesIO(file_content), 'text/plain')
        }
        data = {
            'entity_type': 'lead',
            'entity_id': 'nonexistent-lead-id',
            'tag': 'proposal'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents/upload",
            headers=headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 404, "Upload to nonexistent lead should return 404"
        print(f"✓ Nonexistent lead correctly rejected")
    
    def test_nonexistent_company_rejected(self, admin_token):
        """Upload to nonexistent company should be rejected"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        file_content = b"Test content"
        files = {
            'file': ('test.txt', io.BytesIO(file_content), 'text/plain')
        }
        data = {
            'entity_type': 'company',
            'entity_id': 'nonexistent-company-id',
            'tag': 'corporate_profile'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents/upload",
            headers=headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 404, "Upload to nonexistent company should return 404"
        print(f"✓ Nonexistent company correctly rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
