"""Phase 40.2 — Lead customer-picker backend tests.

Validates:
- POST /api/leads with customer_company_id persists + returns it
- POST/GET returns denormalised customer_company_type ('customer' | 'selling_partner')
- PUT /api/leads/{id} can set, change, or clear customer_company_id (clear via "")
- GET /api/leads/{id} includes new fields
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
ADMIN_EMAIL = 'admin@vyapaarnetwork.com'
ADMIN_PASS = 'admin123'


@pytest.fixture(scope='module')
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={'email': ADMIN_EMAIL, 'password': ADMIN_PASS},
        timeout=20,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json()['access_token']


@pytest.fixture(scope='module')
def headers(admin_token):
    return {'Authorization': f'Bearer {admin_token}', 'Content-Type': 'application/json'}


@pytest.fixture(scope='module')
def companies(headers):
    r = requests.get(f"{BASE_URL}/api/companies", headers=headers, timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) > 0, "Need companies in master to test"
    return data


@pytest.fixture(scope='module')
def customer_company(companies):
    co = next((c for c in companies if (c.get('type') or '').lower() == 'customer'), None)
    if not co:
        pytest.skip("No Customer-type company in master")
    return co


@pytest.fixture(scope='module')
def selling_partner_company(companies):
    co = next((c for c in companies if (c.get('type') or '').lower() == 'selling_partner'), None)
    if not co:
        pytest.skip("No Selling Partner-type company in master")
    return co


@pytest.fixture(scope='module')
def primary_category_id(headers):
    r = requests.get(f"{BASE_URL}/api/master/primary-categories", headers=headers, timeout=20)
    assert r.status_code == 200
    cats = r.json()
    assert len(cats) > 0
    return cats[0]['id']


def _lead_payload(primary_category_id, **overrides):
    base = {
        'title': f"TEST_p402_{uuid.uuid4().hex[:8]}",
        'description': 'Phase 40.2 test',
        'customer_name': 'TEST Customer',
        'customer_email': f"test_p402_{uuid.uuid4().hex[:6]}@example.com",
        'customer_phone': '+91-9999999999',
        'customer_company': 'TEST Co',
        'primary_category_id': primary_category_id,
        'deal_value': 1000.0,
    }
    base.update(overrides)
    return base


class TestCustomerCompanyIdCreate:
    """POST /api/leads with customer_company_id (Customer type)."""

    def test_create_with_customer_company_id(self, headers, primary_category_id, customer_company):
        payload = _lead_payload(primary_category_id, customer_company_id=customer_company['id'])
        r = requests.post(f"{BASE_URL}/api/leads", headers=headers, json=payload, timeout=20)
        assert r.status_code == 200, f"create failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert data.get('customer_company_id') == customer_company['id'], \
            f"customer_company_id missing/wrong: {data.get('customer_company_id')}"
        assert data.get('customer_company_type') == 'customer', \
            f"expected type 'customer' got {data.get('customer_company_type')!r}"
        # Cleanup
        requests.delete(f"{BASE_URL}/api/leads/{data['id']}", headers=headers, timeout=15)

    def test_create_with_selling_partner_company_id(self, headers, primary_category_id, selling_partner_company):
        payload = _lead_payload(primary_category_id, customer_company_id=selling_partner_company['id'])
        r = requests.post(f"{BASE_URL}/api/leads", headers=headers, json=payload, timeout=20)
        assert r.status_code == 200, f"create failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert data.get('customer_company_id') == selling_partner_company['id']
        assert data.get('customer_company_type') == 'selling_partner', \
            f"expected 'selling_partner' got {data.get('customer_company_type')!r}"
        requests.delete(f"{BASE_URL}/api/leads/{data['id']}", headers=headers, timeout=15)

    def test_create_without_customer_company_id(self, headers, primary_category_id):
        payload = _lead_payload(primary_category_id)
        r = requests.post(f"{BASE_URL}/api/leads", headers=headers, json=payload, timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data.get('customer_company_id') in (None, ''), \
            f"expected None/'' got {data.get('customer_company_id')!r}"
        assert data.get('customer_company_type') is None
        requests.delete(f"{BASE_URL}/api/leads/{data['id']}", headers=headers, timeout=15)


class TestCustomerCompanyIdGetAndUpdate:
    """GET + PUT — verify persistence, change, and clear."""

    @pytest.fixture
    def lead_with_company(self, headers, primary_category_id, customer_company):
        payload = _lead_payload(primary_category_id, customer_company_id=customer_company['id'])
        r = requests.post(f"{BASE_URL}/api/leads", headers=headers, json=payload, timeout=20)
        assert r.status_code == 200
        lead = r.json()
        yield lead
        requests.delete(f"{BASE_URL}/api/leads/{lead['id']}", headers=headers, timeout=15)

    def test_get_includes_new_fields(self, headers, lead_with_company, customer_company):
        r = requests.get(f"{BASE_URL}/api/leads/{lead_with_company['id']}", headers=headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get('customer_company_id') == customer_company['id']
        assert d.get('customer_company_type') == 'customer'

    def test_put_changes_customer_company_id(
        self, headers, lead_with_company, selling_partner_company
    ):
        # change from customer-type to selling_partner-type
        r = requests.put(
            f"{BASE_URL}/api/leads/{lead_with_company['id']}",
            headers=headers,
            json={'customer_company_id': selling_partner_company['id']},
            timeout=20,
        )
        assert r.status_code == 200, f"put failed: {r.status_code} {r.text[:300]}"
        d = r.json()
        assert d.get('customer_company_id') == selling_partner_company['id']
        assert d.get('customer_company_type') == 'selling_partner'

        # Verify via GET
        g = requests.get(f"{BASE_URL}/api/leads/{lead_with_company['id']}", headers=headers, timeout=15)
        assert g.json().get('customer_company_id') == selling_partner_company['id']

    def test_put_clears_customer_company_id_with_empty_string(self, headers, lead_with_company):
        # Per the review: clearing must be possible by sending ''
        r = requests.put(
            f"{BASE_URL}/api/leads/{lead_with_company['id']}",
            headers=headers,
            json={'customer_company_id': ''},
            timeout=20,
        )
        assert r.status_code == 200, f"put failed: {r.status_code} {r.text[:300]}"
        d = r.json()
        assert not d.get('customer_company_id'), \
            f"expected cleared got {d.get('customer_company_id')!r}"
        assert d.get('customer_company_type') is None

        g = requests.get(f"{BASE_URL}/api/leads/{lead_with_company['id']}", headers=headers, timeout=15)
        assert not g.json().get('customer_company_id')
