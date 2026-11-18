"""Pre-launch security and platform audit (request limits, logging, monitoring,
production guards, permission gaps). Run with ``manage.py test core``."""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from blog.models import Post
from core.logging import JsonFormatter, RedactSecretsFilter, redact
from core.monitoring import init_sentry, scrub_event
from dashboard.models import SiteSettings

BACKEND_DIR = Path(__file__).resolve().parent.parent


class RequestSizeLimitTests(TestCase):
    @override_settings(RESREF_MAX_REQUEST_BYTES=100)
    def test_oversized_body_is_rejected_before_the_view_reads_it(self):
        response = self.client.post('/api/contact/', data='x' * 500, content_type='application/json')
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()['code'], 'request_too_large')

    @override_settings(RESREF_MAX_REQUEST_BYTES=100)
    def test_small_body_passes(self):
        response = self.client.post('/api/contact/', data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 400)  # normal validation error, not 413

    def test_default_cap_is_above_the_largest_upload(self):
        from django.conf import settings
        self.assertGreater(settings.RESREF_MAX_REQUEST_BYTES, 20 * 1024 * 1024)


class LogRedactionTests(SimpleTestCase):
    def test_redacts_passwords_tokens_and_url_tokens(self):
        text = redact('password=hunter2 "token": "abc123" GET /reset?token=SECRETVALUE&x=1')
        self.assertNotIn('hunter2', text)
        self.assertNotIn('abc123', text)
        self.assertNotIn('SECRETVALUE', text)
        self.assertIn('x=1', text)

    def test_filter_rewrites_record(self):
        record = logging.LogRecord('t', logging.INFO, __file__, 1, 'login %s', ('password=letmein',), None)
        RedactSecretsFilter().filter(record)
        self.assertNotIn('letmein', record.getMessage())

    def test_json_formatter_outputs_one_object(self):
        record = logging.LogRecord('resref.api', logging.ERROR, __file__, 1, 'boom', (), None)
        payload = json.loads(JsonFormatter().format(record))
        self.assertEqual(payload['level'], 'ERROR')
        self.assertEqual(payload['message'], 'boom')


class MonitoringTests(SimpleTestCase):
    def test_sentry_is_off_without_dsn(self):
        previous = os.environ.pop('SENTRY_DSN', None)
        try:
            self.assertFalse(init_sentry('development'))
        finally:
            if previous is not None:
                os.environ['SENTRY_DSN'] = previous

    def test_scrub_event_drops_personal_and_secret_data(self):
        event = scrub_event({
            'request': {
                'headers': {'Cookie': 'sessionid=1', 'Authorization': 'Bearer x', 'Accept': 'text/html'},
                'cookies': {'sessionid': '1'},
                'data': {'email': 'a@example.com'},
                'query_string': 'token=abc',
            },
            'user': {'id': 7, 'email': 'a@example.com', 'ip_address': '1.2.3.4'},
        })
        self.assertEqual(event['request']['headers']['Cookie'], '[Filtered]')
        self.assertEqual(event['request']['headers']['Authorization'], '[Filtered]')
        self.assertEqual(event['request']['headers']['Accept'], 'text/html')
        self.assertNotIn('cookies', event['request'])
        self.assertNotIn('data', event['request'])
        self.assertEqual(event['request']['query_string'], '[Filtered]')
        self.assertEqual(event['user'], {'id': 7})


class ProductionSettingsGuardTests(SimpleTestCase):
    """Import the settings in a child process with production variables."""

    def import_settings(self, **overrides):
        env = {
            key: value for key, value in os.environ.items()
            if not key.startswith(('DJANGO_', 'RESREF_', 'RAILWAY_', 'SENTRY_', 'DATABASE_URL', 'REDIS_URL', 'PG'))
        }
        env.update({
            'RESREF_ENV': 'production',
            'DJANGO_SECRET_KEY': 'k' * 20 + 'abcdefghijklmnopqrstuvwxyz0123456789',
            'DATABASE_URL': 'postgresql://u:p@db.internal:5432/resref',
            'REDIS_URL': 'redis://redis.internal:6379/0',
            'SERVE_FRONTEND_FROM_DJANGO': 'true',
            'PUBLIC_HOSTNAME': 'resref.example.com',
            'FRONTEND_BASE_URL': 'https://resref.example.com',
            # Present (even empty) variables win over a developer's backend/.env.
            'DJANGO_DEBUG': 'false',
            'DJANGO_ALLOWED_HOSTS': 'resref.example.com',
            'DJANGO_CACHE_BACKEND': '',
            'DJANGO_CACHE_LOCATION': '',
            'DJANGO_CORS_ALLOWED_ORIGINS': '',
            'DJANGO_CSRF_TRUSTED_ORIGINS': '',
            'MEDIA_STORAGE': 'local',
            'SENTRY_DSN': '',
        })
        env.update(overrides)
        return subprocess.run(
            [sys.executable, '-c', 'import resref.settings as s; print(s.DATABASES["default"]["OPTIONS"].get("connect_timeout"))'],
            cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=60,
        )

    def test_valid_production_settings_load(self):
        result = self.import_settings()
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertEqual(result.stdout.strip(), '10')

    def test_weak_secret_key_is_refused(self):
        result = self.import_settings(DJANGO_SECRET_KEY='short-key')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY is too weak', result.stderr)

    def test_wildcard_allowed_hosts_is_refused(self):
        result = self.import_settings(DJANGO_ALLOWED_HOSTS='*')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_ALLOWED_HOSTS', result.stderr)


class TrashPermissionTests(TestCase):
    def setUp(self):
        self.post = Post.objects.create(title='Draft', slug='audit-draft', content='<p>x</p>', status='draft')
        self.editor = User.objects.create_user('audit-editor', password='test-only-password', is_staff=True)
        self.editor.membership_profile.access_role = 'editor'
        self.editor.membership_profile.save()

    def save(self, status):
        return self.client.post(
            f'/api/dashboard/posts/{self.post.pk}/save/',
            json.dumps({'title': 'Draft', 'status': status}), content_type='application/json',
        )

    def test_editor_without_delete_permission_cannot_trash_via_save(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.save('pending').status_code, 200)
        response = self.save('trash')
        self.assertEqual(response.status_code, 403)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'pending')

    def test_admin_can_trash_via_save(self):
        self.client.force_login(User.objects.create_superuser('audit-admin', password='test-only-password'))
        self.assertEqual(self.save('trash').status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'trash')


class SettingsLengthValidationTests(TestCase):
    def test_overlong_setting_key_is_a_400_not_a_500(self):
        self.client.force_login(User.objects.create_superuser('audit-settings', password='test-only-password'))
        response = self.client.post(
            '/api/dashboard/settings/save/',
            json.dumps({'settings': [{'key': 'k' * 150, 'value': 'v'}]}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SiteSettings.objects.filter(key__startswith='kkkk').exists())


class PublicEndpointRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @override_settings(NEWSLETTER_ENABLED=True)
    def test_newsletter_confirm_is_rate_limited(self):
        statuses = [
            self.client.post('/api/newsletter/confirm/', json.dumps({'token': f'bad-{i}'}), content_type='application/json').status_code
            for i in range(31)
        ]
        self.assertEqual(statuses[0], 400)
        self.assertEqual(statuses[-1], 429)

    def test_post_search_is_rate_limited_but_plain_listing_is_not(self):
        for _ in range(120):
            self.assertEqual(self.client.get('/api/posts/?q=method').status_code, 200)
        self.assertEqual(self.client.get('/api/posts/?q=method').status_code, 429)
        self.assertEqual(self.client.get('/api/posts/').status_code, 200)


class DeploymentScriptTests(SimpleTestCase):
    def test_access_log_never_contains_query_strings(self):
        script = (BACKEND_DIR / 'start.sh').read_text(encoding='utf-8')
        self.assertIn('%(U)s', script)
        self.assertNotIn('%(r)s', script)
        self.assertNotIn('%(q)s', script)
        self.assertNotIn('\r', script)

    def test_railway_skips_duplicate_migrations(self):
        script = (BACKEND_DIR / 'start.sh').read_text(encoding='utf-8')
        self.assertIn('RAILWAY_ENVIRONMENT', script)
        railway = json.loads((BACKEND_DIR.parent / 'railway.json').read_text(encoding='utf-8'))
        self.assertIn('python manage.py migrate --noinput', railway['deploy']['preDeployCommand'])
