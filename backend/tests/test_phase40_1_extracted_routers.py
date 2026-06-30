"""Phase 40.1 regression — extracted routers/lead_views.py + routers/lead_ai.py.

Validates the post-refactor API surface is 1:1 with the pre-refactor server.py:
 - /api/lead-views — full CRUD with default-singleton constraint
 - /api/leads/{id}/ai/meeting-summaries — list endpoint returns {summaries: [...]}
 - /api/leads/{id}/ai/suggest-actions — returns {tasks: [...], follow_ups: [...]}
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://vyapaar-preview-1.preview.emergentagent.com').rstrip('/')
ADMIN_EMAIL = 'admin@vyapaarnetwork.com'
ADMIN_PASS = 'admin123'


@pytest.fixture(scope='module')
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={'email': ADMIN_EMAIL, 'password': ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json()['access_token']


@pytest.fixture(scope='module')
def headers(admin_token):
    return {'Authorization': f'Bearer {admin_token}', 'Content-Type': 'application/json'}


@pytest.fixture(scope='module')
def sample_lead_id(headers):
    r = requests.get(f"{BASE_URL}/api/leads", headers=headers, timeout=20)
    assert r.status_code == 200
    leads = r.json()
    assert isinstance(leads, list) and len(leads) > 0, "No leads to test AI routes against"
    return leads[0]['id']


# ============================ Lead Views CRUD ============================

class TestLeadViewsCRUD:
    """Extracted to routers/lead_views.py — must preserve full CRUD + default-singleton."""

    def test_list_empty_or_existing(self, headers):
        r = requests.get(f"{BASE_URL}/api/lead-views", headers=headers, timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_view_with_default(self, headers):
        payload = {
            'name': 'TEST_phase40_default_view',
            'filters': {'statuses': ['hot'], 'search': 'acme', 'columns': ['title', 'status']},
            'is_default': True,
        }
        r = requests.post(f"{BASE_URL}/api/lead-views", headers=headers, json=payload, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data['name'] == 'TEST_phase40_default_view'
        assert data['is_default'] is True
        assert data['filters']['search'] == 'acme'
        assert 'id' in data and '_id' not in data
        pytest.view_id_default = data['id']

    def test_only_one_default(self, headers):
        # Create another default — first one should be flipped to false
        payload = {'name': 'TEST_phase40_second_default', 'filters': {}, 'is_default': True}
        r = requests.post(f"{BASE_URL}/api/lead-views", headers=headers, json=payload, timeout=10)
        assert r.status_code == 200
        second_id = r.json()['id']
        pytest.view_id_second = second_id

        r2 = requests.get(f"{BASE_URL}/api/lead-views", headers=headers, timeout=10)
        assert r2.status_code == 200
        rows = r2.json()
        defaults = [v for v in rows if v.get('is_default')]
        assert len(defaults) == 1, f"Expected exactly 1 default, got {len(defaults)}"
        assert defaults[0]['id'] == second_id

    def test_patch_rename(self, headers):
        vid = pytest.view_id_second
        r = requests.patch(f"{BASE_URL}/api/lead-views/{vid}", headers=headers,
                           json={'name': 'TEST_phase40_renamed'}, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()['name'] == 'TEST_phase40_renamed'
        # Verify persisted
        r2 = requests.get(f"{BASE_URL}/api/lead-views", headers=headers, timeout=10)
        match = [v for v in r2.json() if v['id'] == vid]
        assert len(match) == 1 and match[0]['name'] == 'TEST_phase40_renamed'

    def test_patch_empty_name_400(self, headers):
        vid = pytest.view_id_second
        r = requests.patch(f"{BASE_URL}/api/lead-views/{vid}", headers=headers,
                           json={'name': '   '}, timeout=10)
        assert r.status_code == 400

    def test_create_empty_name_400(self, headers):
        r = requests.post(f"{BASE_URL}/api/lead-views", headers=headers,
                         json={'name': '', 'filters': {}}, timeout=10)
        assert r.status_code == 400

    def test_delete_view(self, headers):
        # cleanup both
        for vid_attr in ('view_id_default', 'view_id_second'):
            vid = getattr(pytest, vid_attr, None)
            if vid:
                r = requests.delete(f"{BASE_URL}/api/lead-views/{vid}", headers=headers, timeout=10)
                assert r.status_code == 200
                assert r.json().get('deleted') is True

    def test_delete_nonexistent_404(self, headers):
        r = requests.delete(f"{BASE_URL}/api/lead-views/nonexistent-xxx-id", headers=headers, timeout=10)
        assert r.status_code == 404


# ============================ Lead AI (extracted) ============================

class TestLeadAIExtracted:
    """Validates the 2 endpoints called out in the review: list-meeting-summaries + suggest-actions."""

    def test_list_meeting_summaries_shape(self, headers, sample_lead_id):
        r = requests.get(f"{BASE_URL}/api/leads/{sample_lead_id}/ai/meeting-summaries",
                         headers=headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict) and 'summaries' in data
        assert isinstance(data['summaries'], list)

    def test_list_meeting_summaries_404(self, headers):
        r = requests.get(f"{BASE_URL}/api/leads/nonexistent-lead-id/ai/meeting-summaries",
                         headers=headers, timeout=15)
        assert r.status_code == 404

    def test_suggest_actions_short_text_empty(self, headers, sample_lead_id):
        """Text <5 chars should short-circuit to empty arrays (no LLM call)."""
        r = requests.post(f"{BASE_URL}/api/leads/{sample_lead_id}/ai/suggest-actions",
                         headers=headers, json={'text': 'hi'}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data == {'tasks': [], 'follow_ups': []}

    def test_suggest_actions_real_call(self, headers, sample_lead_id):
        """Full LLM call — verify shape only (LLM content may vary)."""
        payload = {'text': 'Send pricing tomorrow and follow up Monday 10am'}
        r = requests.post(f"{BASE_URL}/api/leads/{sample_lead_id}/ai/suggest-actions",
                         headers=headers, json=payload, timeout=60)
        # LLM may fail in CI (503) — accept that without failing the regression
        if r.status_code == 503:
            pytest.skip(f"LLM unavailable: {r.text[:120]}")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)
        assert 'tasks' in data and isinstance(data['tasks'], list)
        assert 'follow_ups' in data and isinstance(data['follow_ups'], list)
        # If LLM produced anything, verify shape
        for t in data['tasks']:
            assert 'title' in t and 'priority' in t and 'due_date' in t
            assert t['priority'] in ('low', 'medium', 'high')
        for f in data['follow_ups']:
            assert 'notes' in f and 'scheduled_date' in f

    def test_suggest_actions_404(self, headers):
        r = requests.post(f"{BASE_URL}/api/leads/nonexistent/ai/suggest-actions",
                         headers=headers, json={'text': 'send something tomorrow'}, timeout=15)
        assert r.status_code == 404


# ============================ Auth gate ============================

class TestAuthGate:
    def test_lead_views_unauth(self):
        r = requests.get(f"{BASE_URL}/api/lead-views", timeout=10)
        assert r.status_code in (401, 403)

    def test_meeting_summaries_unauth(self):
        r = requests.get(f"{BASE_URL}/api/leads/any/ai/meeting-summaries", timeout=10)
        assert r.status_code in (401, 403)
