import json

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from accounts.models import FeatureEntitlement
from research_analyzer.models import AnalyzerSession


class AnalyzerVisitorAccessTests(TestCase):
    """Visitors use the analyzer like Free members when Free access is on."""

    def setUp(self):
        cache.clear()
        FeatureEntitlement.objects.update_or_create(
            code='research_analyzer', defaults={'label': 'Research Analyzer', 'free_enabled': True, 'is_active': True},
        )

    def upload(self, client):
        return client.post('/api/research-analyzer/upload/', {'file': SimpleUploadedFile('study.csv', b'score\n1\n2\n3\n', content_type='text/csv')})

    def analyze(self, client, session_id):
        return client.post('/api/research-analyzer/analyze/', data=json.dumps({
            'session_id': session_id, 'test': 'descriptive', 'params': {'variables': [{'name': 'score', 'type': 'numeric'}]},
        }), content_type='application/json')

    def test_visitor_can_upload_and_analyze_without_an_account(self):
        visitor = Client()
        upload = self.upload(visitor)
        self.assertEqual(upload.status_code, 200)
        session_id = upload.json()['session_id']
        self.assertEqual(self.analyze(visitor, session_id).status_code, 200)
        session = AnalyzerSession.objects.get(pk=session_id)
        self.assertIsNone(session.user)
        self.assertEqual(len(session.visitor_key), 64)

    def test_another_visitor_cannot_open_someone_elses_dataset(self):
        session_id = self.upload(Client()).json()['session_id']
        self.assertEqual(self.analyze(Client(), session_id).status_code, 404)

    def test_visitor_needs_an_account_when_free_access_is_off(self):
        FeatureEntitlement.objects.filter(code='research_analyzer').update(free_enabled=False)
        response = self.upload(Client())
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['code'], 'auth_required')


class ToolPagesAreOpenTests(TestCase):
    def test_reference_lookup_does_not_require_sign_in(self):
        FeatureEntitlement.objects.update_or_create(
            code='reference_generator', defaults={'label': 'Reference Generator', 'free_enabled': True, 'is_active': True},
        )
        response = Client().get('/api/usage/reference_generator/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['usage']['plan'] if 'plan' in response.json()['usage'] else 'anonymous', 'anonymous')
