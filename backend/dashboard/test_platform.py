"""Platform-level behaviour: health check and public media serving."""

import tempfile
from pathlib import Path

from django.test import TestCase, override_settings


class HealthCheckTests(TestCase):
    def test_health_reports_database_status(self):
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['database'], 'ok')


class PublicMediaTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.tmp.name)
        (root / 'uploads' / 'mediaasset').mkdir(parents=True)
        (root / 'uploads' / 'jobapplication').mkdir(parents=True)
        (root / 'uploads' / 'mediaasset' / 'a.png').write_bytes(b'\x89PNG\r\n\x1a\nfake')
        (root / 'uploads' / 'mediaasset' / 'page.html').write_text('<script>alert(1)</script>')
        (root / 'uploads' / 'jobapplication' / 'cv.pdf').write_bytes(b'%PDF-1.4 cv')
        self.override = override_settings(MEDIA_ROOT=root, DEBUG=False)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.tmp.cleanup()

    def test_public_image_is_served_without_debug(self):
        response = self.client.get('/media/uploads/mediaasset/a.png')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        response.close()  # release the file handle (Windows cannot delete open files)

    def test_cv_uploads_are_never_public(self):
        self.assertEqual(self.client.get('/media/uploads/jobapplication/cv.pdf').status_code, 404)

    def test_active_content_types_are_not_served(self):
        self.assertEqual(self.client.get('/media/uploads/mediaasset/page.html').status_code, 404)

    def test_path_traversal_is_rejected(self):
        response = self.client.get('/media/uploads/mediaasset/..%2F..%2Fsettings.png')
        self.assertEqual(response.status_code, 404)


class LoginProtectionTests(TestCase):
    password = 'Secur3-ResRef!Passphrase'

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    @override_settings(STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    })
    def test_admin_login_is_rate_limited(self):
        from django.contrib.auth.models import User
        User.objects.create_superuser('root-admin', 'root@example.com', self.password)
        codes = [
            self.client.post('/admin/login/', {'username': 'root-admin', 'password': 'wrong-password'}).status_code
            for _ in range(10)
        ]
        self.assertEqual(codes[0], 200)
        self.assertEqual(codes[-1], 429)

    def test_account_counter_blocks_attempts_from_rotating_ips(self):
        import json
        statuses = []
        for attempt in range(25):
            response = self.client.post(
                '/api/accounts/login/',
                data=json.dumps({'email': 'victim@example.com', 'password': 'wrong-password-123'}),
                content_type='application/json',
                REMOTE_ADDR=f'10.0.0.{attempt + 1}',
            )
            statuses.append(response.status_code)
        self.assertIn(429, statuses)


class PublicFormTests(TestCase):
    """T-13: applications and service requests are saved, validated and limited."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.override = override_settings(MEDIA_ROOT=Path(self.tmp.name), STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        })
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.tmp.cleanup()

    def _apply(self, **extra):
        from django.core.files.uploadedfile import SimpleUploadedFile
        data = {'full_name': 'Lina Applicant', 'email': 'lina@example.com', 'team': 'Community Team', 'motivation': 'I would love to help the research community.'}
        data.update(extra)
        return self.client.post('/api/applications/', data)

    def test_application_with_pdf_cv_is_saved_and_cv_is_private(self):
        from django.contrib.auth.models import User
        from django.core.files.uploadedfile import SimpleUploadedFile
        from dashboard.models import JobApplication
        response = self._apply(cv=SimpleUploadedFile('cv.pdf', b'%PDF-1.7 test cv', content_type='application/pdf'))
        self.assertEqual(response.status_code, 201, response.content)
        application = JobApplication.objects.get()
        self.assertEqual(application.team, 'community')
        self.assertTrue(application.cv_file.name.startswith('uploads/jobapplication/'))

        cv_url = f'/api/dashboard/applications/{application.id}/cv/'
        self.assertEqual(self.client.get(cv_url).status_code, 401)
        self.assertEqual(self.client.get('/media/' + application.cv_file.name).status_code, 404)
        admin = User.objects.create_superuser('cv-admin', 'cv-admin@example.com', 'Secur3-ResRef!Passphrase')
        self.client.force_login(admin)
        download = self.client.get(cv_url)
        self.assertEqual(download.status_code, 200)
        self.assertIn('attachment', download['Content-Disposition'])
        self.assertEqual(b''.join(download.streaming_content), b'%PDF-1.7 test cv')
        # Closing a streamed response fires request_finished, which would close the
        # database connection (and break the test transaction on PostgreSQL).
        from django.core.signals import request_finished
        from django.db import close_old_connections
        request_finished.disconnect(close_old_connections)
        try:
            download.close()
        finally:
            request_finished.connect(close_old_connections)
        listing = self.client.get('/api/dashboard/applications/').json()
        self.assertEqual(listing['results'][0]['cv_url'], cv_url)

    def test_cv_must_really_be_pdf_or_docx_and_small(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake = self._apply(cv=SimpleUploadedFile('cv.pdf', b'<html>not a pdf</html>', content_type='application/pdf'))
        self.assertEqual(fake.status_code, 400)
        exe = self._apply(email='x2@example.com', cv=SimpleUploadedFile('cv.exe', b'MZ', content_type='application/octet-stream'))
        self.assertEqual(exe.status_code, 400)
        big = self._apply(email='x3@example.com', cv=SimpleUploadedFile('cv.pdf', b'%PDF-' + b'0' * (5 * 1024 * 1024), content_type='application/pdf'))
        self.assertEqual(big.status_code, 400)

    def test_application_requires_fields_and_is_rate_limited(self):
        self.assertEqual(self.client.post('/api/applications/', {'email': 'bad'}).status_code, 400)
        codes = [self._apply().status_code for _ in range(4)]
        self.assertEqual(codes, [201, 201, 201, 429])

    def test_service_request_is_saved_for_the_dashboard(self):
        import json
        from dashboard.models import ServiceRequest
        response = self.client.post('/api/service-requests/', data=json.dumps({
            'name': 'Omar', 'email': 'omar@example.com', 'request_type': 'Expert consultation',
            'specialization': 'Statistics', 'message': 'Need help choosing a test.', 'whatsapp': '+971 55 123 4567',
        }), content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        item = ServiceRequest.objects.get()
        self.assertEqual(item.subject, 'Expert consultation: Statistics')
        self.assertIn('WhatsApp: +971 55 123 4567', item.message)
        bad = self.client.post('/api/service-requests/', data='[1, 2]', content_type='application/json')
        self.assertEqual(bad.status_code, 400)


class ApiInputHandlingTests(TestCase):
    """T-14: bad input is a 400, partial saves keep data, errors are JSON."""

    password = 'Secur3-ResRef!Passphrase'

    def setUp(self):
        from django.contrib.auth.models import User
        from django.core.cache import cache
        cache.clear()
        self.admin = User.objects.create_superuser('input-admin', 'input-admin@example.com', self.password)
        self.client.force_login(self.admin)

    def _post(self, url, payload, raw=False):
        import json
        return self.client.post(url, data=payload if raw else json.dumps(payload), content_type='application/json')

    def test_non_object_json_and_wrong_types_are_400_not_500(self):
        self.assertEqual(self._post('/api/dashboard/posts/save/', '[1, 2, 3]', raw=True).status_code, 400)
        self.assertEqual(self._post('/api/dashboard/posts/save/', '"text"', raw=True).status_code, 400)
        response = self._post('/api/dashboard/posts/save/', {'title': ['not', 'text']})
        self.assertEqual(response.status_code, 400)
        self.assertIn('must be text', response.json()['error'])
        response = self._post('/api/dashboard/service-requests/save/', {
            'requester_name': 'A', 'requester_email': 'a@example.com', 'subject': 'S', 'assigned_to': 'abc',
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['success'], False)

    def test_partial_save_keeps_status_and_content(self):
        from blog.models import Post
        post = Post.objects.create(title='Draft', slug='draft-post', content='Body', status='draft')
        response = self._post(f'/api/dashboard/posts/{post.id}/save/', {'title': 'Draft renamed'})
        self.assertEqual(response.status_code, 200, response.content)
        post.refresh_from_db()
        self.assertEqual(post.status, 'draft')
        self.assertEqual(post.content, 'Body')
        self.assertEqual(post.slug, 'draft-post')
        created = self._post('/api/dashboard/posts/save/', {'title': 'Brand new'}).json()['post']
        self.assertEqual(created['status'], 'draft')

    def test_partial_opportunity_save_keeps_fields(self):
        from dashboard.models import ResearchOpportunity
        item = ResearchOpportunity.objects.create(title='Fellowship', slug='fellowship', organization='Uni', summary='Short', location='Dubai', status='draft')
        response = self._post(f'/api/dashboard/opportunities/{item.id}/save/', {'title': 'Fellowship 2026'})
        self.assertEqual(response.status_code, 200, response.content)
        item.refresh_from_db()
        self.assertEqual((item.organization, item.summary, item.location, item.status), ('Uni', 'Short', 'Dubai', 'draft'))

    def test_api_errors_are_json(self):
        missing = self.client.get('/api/does-not-exist/')
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()['success'], False)
        wrong_method = self.client.get('/api/dashboard/posts/save/')
        self.assertEqual(wrong_method.status_code, 405)
        self.assertIn('error', wrong_method.json())
        from django.test import Client
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.admin)
        csrf = strict.post('/api/dashboard/posts/save/', data='{}', content_type='application/json')
        self.assertEqual(csrf.status_code, 403)
        self.assertEqual(csrf.json()['code'], 'csrf_failed')

    def test_unhandled_exception_is_json_500(self):
        from unittest import mock
        with mock.patch('dashboard.api.posts.post_to_dict', side_effect=RuntimeError('boom')):
            self.client.raise_request_exception = False
            response = self._post('/api/dashboard/posts/save/', {'title': 'Explodes'})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()['success'], False)
        self.assertNotIn('boom', response.json()['error'])

    def test_wrong_credentials_are_401(self):
        from django.test import Client
        anonymous = Client()
        response = anonymous.post('/api/dashboard/auth/login/', data='{"username": "input-admin", "password": "wrong-password"}', content_type='application/json')
        self.assertEqual(response.status_code, 401)
        response = anonymous.post('/api/accounts/login/', data='{"email": "input-admin@example.com", "password": "wrong-password"}', content_type='application/json')
        self.assertEqual(response.status_code, 401)


class ContentSecurityPolicyTests(TestCase):
    @override_settings(RESREF_CSP_ENABLED=True)
    def test_csp_allows_google_fonts(self):
        from django.conf import settings
        policy = settings.RESREF_CONTENT_SECURITY_POLICY
        self.assertIn('https://fonts.googleapis.com', policy)
        self.assertIn('https://fonts.gstatic.com', policy)
        response = self.client.get('/api/health/')
        self.assertIn('fonts.googleapis.com', response.get('Content-Security-Policy', ''))


class FaqItemValidationTests(TestCase):
    def test_new_faq_item_without_category_is_400_not_500(self):
        import json
        from django.contrib.auth.models import User
        admin = User.objects.create_superuser('faq-admin', 'faq-admin@example.com', 'Secur3-ResRef!Passphrase')
        self.client.force_login(admin)
        response = self.client.post('/api/dashboard/faq/items/save/', data=json.dumps({
            'question': 'Is this valid?', 'answer': 'No category.', 'category': '',
        }), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('category', response.json()['error'])
