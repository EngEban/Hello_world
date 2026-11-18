import json

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from accounts.security import client_ip
from dashboard.models import SiteSettings


class PublicSiteSettingsCacheTests(TestCase):
    """Every page load reads /api/site-settings/: never throttled, cached, refreshed on save."""

    def setUp(self):
        cache.clear()

    def test_many_visitors_behind_one_address_are_never_blocked(self):
        for _ in range(1500):  # more than the old 1200/hour ceiling
            self.assertEqual(self.client.get('/api/site-settings/').status_code, 200)

    def test_saving_settings_in_the_dashboard_refreshes_the_cached_copy(self):
        SiteSettings.objects.create(key='site_name', value='Old name')
        self.assertEqual(self.client.get('/api/site-settings/').json()['settings']['site_name'], 'Old name')
        admin = User.objects.create_superuser('settings-admin', password='test-only-password')
        self.client.force_login(admin)
        response = self.client.post('/api/dashboard/settings/save/', json.dumps({'settings': [{'key': 'site_name', 'value': 'New name'}]}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/site-settings/').json()['settings']['site_name'], 'New name')


class ClientIpTests(TestCase):
    def request(self, **meta):
        return RequestFactory().get('/', **meta)

    @override_settings(RESREF_TRUST_PROXY=True, RESREF_CLIENT_IP_HEADER='HTTP_X_REAL_IP')
    def test_real_ip_header_from_the_hosting_proxy_is_used(self):
        request = self.request(HTTP_X_REAL_IP='203.0.113.7', HTTP_X_FORWARDED_FOR='203.0.113.7, 10.0.0.9', REMOTE_ADDR='10.0.0.2')
        self.assertEqual(client_ip(request), '203.0.113.7')

    @override_settings(RESREF_TRUST_PROXY=True, RESREF_CLIENT_IP_HEADER='HTTP_X_REAL_IP')
    def test_missing_or_invalid_real_ip_falls_back_to_forwarded_chain(self):
        request = self.request(HTTP_X_REAL_IP='not-an-ip', HTTP_X_FORWARDED_FOR='198.51.100.4', REMOTE_ADDR='10.0.0.2')
        self.assertEqual(client_ip(request), '198.51.100.4')

    @override_settings(RESREF_TRUST_PROXY=False, RESREF_CLIENT_IP_HEADER='HTTP_X_REAL_IP')
    def test_headers_are_ignored_when_the_proxy_is_not_trusted(self):
        request = self.request(HTTP_X_REAL_IP='203.0.113.7', REMOTE_ADDR='192.0.2.10')
        self.assertEqual(client_ip(request), '192.0.2.10')
