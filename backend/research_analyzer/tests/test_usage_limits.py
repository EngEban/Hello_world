import json

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from accounts.models import UsageLimit
from usage.models import FeatureUsagePolicy


class AnalyzerUsageLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('analyzer-quota', 'analyzer-quota@example.com', 'pass12345')
        self.user.membership_profile.tier = 'premium'
        self.user.membership_profile.save(update_fields=['tier', 'updated_at'])
        UsageLimit.objects.update_or_create(
            feature_code='research_analyzer', tier='premium', period='day',
            defaults={'limit': 1, 'is_active': True},
        )
        self.client.force_login(self.user)
        upload = self.client.post(
            '/api/research-analyzer/upload/',
            {'file': SimpleUploadedFile('study.csv', b'score\n1\n2\n3\n', content_type='text/csv')},
        )
        self.session_id = upload.json()['session_id']

    def analyze(self):
        return self.client.post(
            '/api/research-analyzer/analyze/',
            data=json.dumps({'session_id': self.session_id, 'test': 'descriptive', 'params': {'variables': [{'name': 'score', 'type': 'numeric'}]}}),
            content_type='application/json',
        )

    def test_limit_response_tells_the_user_when_it_resets(self):
        self.assertEqual(self.analyze().status_code, 200)
        blocked = self.analyze()
        self.assertEqual(blocked.status_code, 429)
        body = blocked.json()
        self.assertEqual((body['code'], body['limit'], body['remaining'], body['period']), ('usage_limit', 1, 0, 'day'))
        self.assertTrue(body['reset_at'])
        self.assertIn('Retry-After', blocked)

    def test_switching_limits_off_in_the_dashboard_unblocks_immediately(self):
        self.assertEqual(self.analyze().status_code, 200)
        self.assertEqual(self.analyze().status_code, 429)
        FeatureUsagePolicy.objects.filter(feature_code='research_analyzer').update(limits_enabled=False)
        self.assertEqual(self.analyze().status_code, 200)
