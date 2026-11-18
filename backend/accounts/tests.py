import json
import os
import re
import time
from io import StringIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from dashboard.models import ContactSubmission, DashboardActivityLog
from .billing import plan_for_checkout, plan_from_subscription_payload, process_verified_stripe_event
from .entitlements import ensure_default_entitlements
from .models import AccountNotification, BillingWebhookEvent, FeatureEntitlement, MembershipProfile, PasswordHistory, SubscriptionPlan, UsageLimit, UsageRecord, UserSubscription
from .security import client_ip
from .security import rate_limit


class AccountApiTests(TestCase):
    password = 'Secur3-ResRef!Passphrase'
    new_password = 'Anoth3r-ResRef!Passphrase'

    def setUp(self):
        cache.clear()
        self.client = Client(enforce_csrf_checks=True)
        self.client.get('/api/accounts/csrf/')
        self.csrf_token = self.client.cookies['csrftoken'].value

    def post(self, path, data=None, client=None):
        active_client = client or self.client
        return active_client.post(
            path,
            data=json.dumps(data or {}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=active_client.cookies['csrftoken'].value,
        )

    def register_and_confirm(self, email, password, full_name='ResRef Member'):
        """Sign up, then follow the emailed link (which signs the user in)."""
        mail.outbox.clear()
        response = self.post('/api/accounts/register/', {'email': email, 'password': password, 'full_name': full_name})
        self.assertEqual(response.status_code, 202, response.content)
        link = next(line for message in mail.outbox for line in message.body.splitlines() if '/account/confirm-email?token=' in line)
        token = parse_qs(urlparse(link.strip()).query)['token'][0]
        confirmed = self.post('/api/accounts/register/confirm/', {'token': token})
        self.assertEqual(confirmed.status_code, 200, confirmed.content)
        return confirmed.json()['account']

    def client_with_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.get('/api/accounts/csrf/')
        return client

    def test_me_api_uses_seeded_entitlements_without_request_time_writes(self):
        user = User.objects.create_user('query-member', 'query-member@example.com', self.password)
        self.client.force_login(user)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/api/accounts/me/')

        self.assertEqual(response.status_code, 200)
        self.assertLess(len(queries), 100)
        entitlement_tables = ('accounts_accountrole', 'accounts_featureentitlement', 'accounts_subscriptionplan', 'accounts_usagelimit')
        self.assertFalse(any(
            query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
            and any(table in query['sql'].lower() for table in entitlement_tables)
            for query in queries
        ))

    @override_settings(RESREF_TRUST_PROXY=True, RESREF_TRUSTED_PROXY_HOPS=1)
    def test_client_ip_ignores_spoofed_leftmost_forwarded_address(self):
        request = RequestFactory().get(
            '/',
            HTTP_X_FORWARDED_FOR='203.0.113.7, 198.51.100.9',
            REMOTE_ADDR='10.0.0.4',
        )
        self.assertEqual(client_ip(request), '198.51.100.9')

    def test_unknown_stripe_price_does_not_fall_back_to_premium(self):
        SubscriptionPlan.objects.update_or_create(
            code='premium_monthly',
            defaults={
                'label': 'Premium Monthly',
                'tier': 'premium',
                'provider': 'stripe',
                'provider_price_id': 'price_known_monthly',
                'billing_interval': 'month',
                'is_active': True,
            },
        )
        payload = {
            'metadata': {'plan_code': 'premium_monthly'},
            'items': {'data': [{'price': {'id': 'price_unknown'}}]},
        }
        self.assertIsNone(plan_from_subscription_payload(payload))

    @override_settings(
        STRIPE_PREMIUM_MONTHLY_PRICE_ID='price_monthly_configured',
        STRIPE_PREMIUM_YEARLY_PRICE_ID='price_yearly_configured',
    )
    def test_seeded_entitlements_sync_configured_stripe_prices(self):
        SubscriptionPlan.objects.filter(code__in=['premium_monthly', 'premium_yearly']).update(
            provider='manual',
            provider_price_id='',
        )

        ensure_default_entitlements()

        self.assertEqual(plan_for_checkout('premium_monthly').provider_price_id, 'price_monthly_configured')
        self.assertEqual(plan_for_checkout('premium_yearly').provider_price_id, 'price_yearly_configured')

    def test_registration_rejects_passwords_over_256_characters(self):
        response = self.post('/api/accounts/register/', {
            'email': 'overlong-password@example.com',
            'password': 'A1-' + ('x' * 254),
            'full_name': 'Overlong Password',
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Password must be 256 characters or fewer.')

    @override_settings(ACCOUNT_EMAIL_VERIFICATION_GRACE_DAYS=0)  # strict mode: confirm before first sign-in
    def test_register_profile_password_and_login_lifecycle(self):
        account = self.register_and_confirm('member@example.com', self.password)
        self.assertEqual(account['tier'], 'free')
        self.assertEqual(account['access_role'], 'member')

        response = self.post('/api/accounts/profile/', {
            'first_name': 'Research',
            'last_name': 'Member',
            'organization': 'ResRef Lab',
            'specialization': 'Clinical research',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['account']['organization'], 'ResRef Lab')

        response = self.post('/api/accounts/password/', {
            'current_password': self.password,
            'new_password': self.new_password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.post('/api/accounts/logout/').status_code, 200)
        response = self.post('/api/accounts/login/', {
            'email': 'member@example.com',
            'password': self.new_password,
        })
        self.assertEqual(response.status_code, 200)

    def test_csrf_is_required_for_mutating_requests(self):
        response = Client(enforce_csrf_checks=True).post(
            '/api/accounts/register/',
            data=json.dumps({'email': 'blocked@example.com', 'password': self.password}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

        response = Client(enforce_csrf_checks=True).post(
            '/api/contact/',
            data=json.dumps({'name': 'Blocked', 'email': 'blocked@example.com'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

        response = self.post('/api/contact/', {'name': 'Allowed', 'email': 'allowed@example.com', 'message': 'Hello ResRef'})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(ContactSubmission.objects.filter(email='allowed@example.com').exists())

    def test_csrf_endpoint_returns_a_masked_token_for_cross_origin_frontends(self):
        response = self.client.get('/api/accounts/csrf/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['csrfToken'])

    @override_settings(IS_PRODUCTION=False)
    @patch.dict(os.environ, {
        'RESREF_STAGING_ADMIN_USERNAME': 'staging-admin',
        'RESREF_STAGING_ADMIN_EMAIL': 'staging-admin@example.com',
        'RESREF_STAGING_ADMIN_PASSWORD': 'Secur3-Staging!Passphrase',
    }, clear=True)
    def test_staging_admin_bootstrap_creates_an_idempotent_superuser(self):
        call_command('ensure_staging_admin')
        user = User.objects.get(username='staging-admin')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password('Secur3-Staging!Passphrase'))

        call_command('ensure_staging_admin')
        user.refresh_from_db()
        self.assertTrue(user.check_password('Secur3-Staging!Passphrase'))

    @override_settings(IS_PRODUCTION=False)
    @patch.dict(os.environ, {
        'RESREF_STAGING_ADMIN_USERNAME': 'existing-admin',
        'RESREF_STAGING_ADMIN_EMAIL': 'staging-admin@example.com',
        'RESREF_STAGING_ADMIN_PASSWORD': 'New-Secur3-Staging!Passphrase',
        'RESREF_STAGING_ADMIN_RESET_PASSWORD': 'true',
        'RESREF_STAGING_ADMIN_ALLOW_PROMOTION': 'true',
    }, clear=True)
    def test_staging_admin_bootstrap_can_explicitly_reset_an_existing_user(self):
        user = User.objects.create_user(
            'existing-admin', 'old-admin@example.com', 'Old-Secur3-Staging!Passphrase'
        )

        call_command('ensure_staging_admin')

        user.refresh_from_db()
        self.assertEqual(user.email, 'staging-admin@example.com')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password('New-Secur3-Staging!Passphrase'))

    @override_settings(IS_PRODUCTION=False)
    @patch.dict(os.environ, {
        'RESREF_STAGING_ADMIN_USERNAME': 'imported-admin',
        'RESREF_STAGING_ADMIN_EMAIL': 'staging-admin@example.com',
        'RESREF_STAGING_ADMIN_PASSWORD': 'Secur3-Staging!Passphrase',
        'RESREF_STAGING_ADMIN_ALLOW_PROMOTION': 'true',
    }, clear=True)
    def test_staging_admin_bootstrap_accepts_imported_admin_with_a_different_email(self):
        user = User.objects.create_user(
            'imported-admin', 'source-admin@example.com', 'Source-Secur3!Passphrase'
        )

        call_command('ensure_staging_admin')

        user.refresh_from_db()
        self.assertEqual(user.email, 'source-admin@example.com')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password('Source-Secur3!Passphrase'))

    @override_settings(IS_PRODUCTION=True)
    @patch.dict(os.environ, {
        'RESREF_ENV': 'production',
        'RESREF_STAGING_ADMIN_USERNAME': 'production-admin',
    }, clear=True)
    def test_staging_admin_bootstrap_refuses_configured_production(self):
        with self.assertRaisesMessage(CommandError, 'RESREF_STAGING_ADMIN_USERNAME'):
            call_command('ensure_staging_admin')
        self.assertFalse(User.objects.filter(username='production-admin').exists())

    @override_settings(IS_PRODUCTION=True)
    @patch.dict(os.environ, {'RESREF_ENV': 'production'}, clear=True)
    def test_staging_admin_bootstrap_is_noop_in_unconfigured_production(self):
        output = StringIO()
        call_command('ensure_staging_admin', stdout=output)
        self.assertIn('staging administrator bootstrap is disabled', output.getvalue().lower())

    @override_settings(IS_PRODUCTION=False)
    @patch.dict(os.environ, {
        'RESREF_ENV': 'development',
        'RESREF_STAGING_ADMIN_USERNAME': 'unpromoted-admin',
        'RESREF_STAGING_ADMIN_EMAIL': 'unpromoted-admin@example.com',
        'RESREF_STAGING_ADMIN_PASSWORD': 'Secur3-Staging!Passphrase',
    }, clear=True)
    def test_staging_admin_bootstrap_does_not_promote_without_explicit_permission(self):
        user = User.objects.create_user(
            'unpromoted-admin', 'unpromoted-admin@example.com', 'Original-Secur3!Passphrase'
        )
        errors = StringIO()

        call_command('ensure_staging_admin', stderr=errors)

        user.refresh_from_db()
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertIn('was not promoted', errors.getvalue())

    @override_settings(IS_PRODUCTION=False)
    @patch.dict(os.environ, {
        'RESREF_ENV': 'development',
        'RESREF_STAGING_ADMIN_USERNAME': 'already-super',
        'RESREF_STAGING_ADMIN_EMAIL': 'already-super@example.com',
        'RESREF_STAGING_ADMIN_PASSWORD': 'Secur3-Staging!Passphrase',
        'RESREF_STAGING_ADMIN_RESET_PASSWORD': 'true',
        'RESREF_STAGING_ADMIN_ALLOW_PROMOTION': 'true',
    }, clear=True)
    def test_staging_admin_bootstrap_leaves_existing_superuser_unchanged(self):
        user = User.objects.create_superuser(
            'already-super', 'original-super@example.com', 'Original-Secur3!Passphrase'
        )
        output = StringIO()

        call_command('ensure_staging_admin', stdout=output)

        user.refresh_from_db()
        self.assertEqual(user.email, 'original-super@example.com')
        self.assertTrue(user.check_password('Original-Secur3!Passphrase'))
        self.assertIn('already exists as a superuser', output.getvalue())

    @override_settings(
        IS_PRODUCTION=True,
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    )
    def test_production_requires_a_shared_cache_backend(self):
        from resref.settings import validate_production_cache_backend

        with self.assertRaisesMessage(ImproperlyConfigured, 'Production requires a shared cache backend'):
            validate_production_cache_backend(settings.CACHES, settings.IS_PRODUCTION)

    def test_production_requires_a_non_local_redis_url(self):
        from resref.settings import validate_production_cache_backend

        caches = {
            'default': {
                'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                'LOCATION': 'redis://127.0.0.1:6379/1',
            }
        }
        with self.assertRaisesMessage(ImproperlyConfigured, 'non-local shared Redis URL'):
            validate_production_cache_backend(caches, True)

    def test_managed_platform_domains_are_normalized_before_allowlisting(self):
        from resref.settings import deployment_hostnames

        self.assertEqual(
            deployment_hostnames(
                'https://resref-staging-api.up.railway.app',
                'resref-staging-api.up.railway.app',
                'resref-staging-api.onrender.com',
            ),
            ['resref-staging-api.up.railway.app', 'resref-staging-api.onrender.com'],
        )

    @override_settings(
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache'}},
    )
    def test_redis_cache_backend_is_recognized(self):
        self.assertIn('redis', settings.CACHES['default']['BACKEND'].lower())

    @override_settings(IS_PRODUCTION=True)
    def test_rate_limit_rejects_when_production_cache_is_unavailable(self):
        request = RequestFactory().post('/api/accounts/login/', REMOTE_ADDR='203.0.113.8')

        with patch('accounts.security.cache.add', side_effect=ConnectionError('redis unavailable')):
            self.assertFalse(rate_limit(request, 'cache-unavailable', limit=1, window=60))
        with patch('accounts.security.cache.add', return_value=False), patch(
            'accounts.security.cache.incr', side_effect=ConnectionError('redis unavailable')
        ):
            self.assertFalse(rate_limit(request, 'cache-incr-unavailable', limit=1, window=60))
        with patch('accounts.security.cache.add', return_value=False), patch(
            'accounts.security.cache.incr', side_effect=ValueError
        ), patch('accounts.security.cache.set', side_effect=ConnectionError('redis unavailable')):
            self.assertFalse(rate_limit(request, 'cache-set-unavailable', limit=1, window=60))

    @override_settings(IS_PRODUCTION=False)
    def test_rate_limit_locmem_counter_expires_after_its_window(self):
        request = RequestFactory().post('/api/accounts/login/', REMOTE_ADDR='203.0.113.9')

        self.assertTrue(rate_limit(request, 'locmem-expiry', limit=1, window=1))
        self.assertFalse(rate_limit(request, 'locmem-expiry', limit=1, window=1))
        time.sleep(1.1)
        self.assertTrue(rate_limit(request, 'locmem-expiry', limit=1, window=1))

    def test_fixture_user_save_does_not_create_a_duplicate_membership_profile(self):
        fixture_user = User(id=9876, username='fixture-user', email='fixture@example.com')

        fixture_user.save_base(raw=True, force_insert=True, using='default')

        self.assertFalse(MembershipProfile.objects.filter(user_id=fixture_user.id).exists())

    def test_staging_reset_command_refuses_to_run_against_local_sqlite(self):
        if connection.vendor == 'postgresql':
            self.skipTest('This refusal path is specific to the SQLite development backend.')
        with self.assertRaisesMessage(CommandError, 'only supports PostgreSQL'):
            call_command('reset_staging_data')

    def test_dashboard_requires_editor_role_and_staff_status(self):
        user = User.objects.create_user('editor@example.com', 'editor@example.com', self.password, is_staff=True)
        response = self.post('/api/dashboard/auth/login/', {
            'username': user.username,
            'password': self.password,
        })
        self.assertEqual(response.status_code, 403)

        user.membership_profile.access_role = 'editor'
        user.membership_profile.save(update_fields=['access_role', 'updated_at'])
        response = self.post('/api/dashboard/auth/login/', {
            'username': user.username,
            'password': self.password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/dashboard/stats/').status_code, 200)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_link_changes_password(self):
        User.objects.create_user('reset@example.com', 'reset@example.com', self.password)
        response = self.post('/api/accounts/password-reset/', {'email': 'reset@example.com'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        match = re.search(r'uid=([^&\s]+)&token=([^\s]+)', mail.outbox[0].body)
        self.assertIsNotNone(match)
        response = self.post('/api/accounts/password-reset/confirm/', {
            'uid': match.group(1),
            'token': match.group(2),
            'new_password': self.new_password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.get(email='reset@example.com').check_password(self.new_password))

    def test_password_history_blocks_current_and_previously_used_passwords(self):
        user = User.objects.create_user('history@example.com', 'history@example.com', self.password)
        self.client.force_login(user)

        response = self.post('/api/accounts/password/', {
            'current_password': self.password,
            'new_password': self.password,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Your new password must be different from your previous password.')

        response = self.post('/api/accounts/password/', {
            'current_password': self.password,
            'new_password': self.new_password,
        })
        self.assertEqual(response.status_code, 200)
        history = PasswordHistory.objects.get(user=user)
        self.assertNotEqual(history.password_hash, self.password)
        user.refresh_from_db()
        self.assertTrue(user.check_password(self.new_password))

        response = self.post('/api/accounts/password/', {
            'current_password': self.new_password,
            'new_password': self.password,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Your new password must be different from your previous password.')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_blocks_reuse_of_the_current_password(self):
        user = User.objects.create_user('reset-history@example.com', 'reset-history@example.com', self.password)
        self.assertEqual(self.post('/api/accounts/password-reset/', {'email': user.email}).status_code, 200)
        match = re.search(r'uid=([^&\s]+)&token=([^\s]+)', mail.outbox[0].body)

        response = self.post('/api/accounts/password-reset/confirm/', {
            'uid': match.group(1),
            'token': match.group(2),
            'new_password': self.password,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Your new password must be different from your previous password.')
        user.refresh_from_db()
        self.assertTrue(user.check_password(self.password))

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        PASSWORD_RESET_EMAIL_LIMIT=1,
        PASSWORD_RESET_IP_LIMIT=1,
        PASSWORD_RESET_COOLDOWN_SECONDS=300,
    )
    def test_password_reset_cooldown_is_neutral_and_limited_by_email_and_ip(self):
        User.objects.create_user('reset-limit@example.com', 'reset-limit@example.com', self.password)
        response = self.post('/api/accounts/password-reset/', {'email': 'reset.limit@gmail.com'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

        response = self.client.post(
            '/api/accounts/password-reset/',
            data=json.dumps({'email': 'resetlimit@gmail.com'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.csrf_token,
            REMOTE_ADDR='198.51.100.25',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['message'], 'If an account exists for that email address, a reset link has been sent.')
        self.assertEqual(len(mail.outbox), 0)

        cache.clear()
        response = self.client.post(
            '/api/accounts/password-reset/',
            data=json.dumps({'email': 'first@example.com'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.csrf_token,
            REMOTE_ADDR='198.51.100.99',
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            '/api/accounts/password-reset/',
            data=json.dumps({'email': 'second@example.com'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.csrf_token,
            REMOTE_ADDR='198.51.100.99',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['message'], 'If an account exists for that email address, a reset link has been sent.')

    @override_settings(ACCOUNT_EMAIL_VERIFICATION_GRACE_DAYS=0)  # strict mode: confirm before first sign-in
    def test_gmail_dot_variants_share_one_account_for_registration_and_login(self):
        account = self.register_and_confirm('res.ref.member@gmail.com', self.password)
        self.assertEqual(account['email'], 'resrefmember@gmail.com')
        self.assertEqual(User.objects.filter(email='resrefmember@gmail.com').count(), 1)

        self.assertEqual(self.post('/api/accounts/logout/').status_code, 200)
        response = self.post('/api/accounts/login/', {
            'email': 'resref.member@gmail.com',
            'password': self.password,
        })
        self.assertEqual(response.status_code, 200)

        response = self.post('/api/accounts/register/', {
            'email': 'resrefmember@gmail.com',
            'password': self.new_password,
            'full_name': 'Duplicate Member',
        })
        # Neutral answer (S-15): same status and text as a brand-new sign-up.
        self.assertEqual(response.status_code, 202)
        self.assertNotIn('already', response.json()['message'].split('Already have')[0])
        self.assertEqual(User.objects.filter(email='resrefmember@gmail.com').count(), 1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    @override_settings(ACCOUNT_EMAIL_VERIFICATION_GRACE_DAYS=0)  # strict mode: confirm before first sign-in
    def test_registration_response_is_identical_for_new_and_existing_email(self):
        payload = {
            'email': 'uniform@example.com',
            'password': self.password,
            'full_name': 'Uniform User',
        }
        new_response = self.post('/api/accounts/register/', payload)
        existing_response = self.post('/api/accounts/register/', payload)
        user = User.objects.get(email='uniform@example.com')
        user.membership_profile.email_verified = True
        user.membership_profile.save(update_fields=['email_verified', 'updated_at'])
        verified_response = self.post('/api/accounts/register/', payload)

        self.assertEqual(new_response.status_code, existing_response.status_code)
        self.assertEqual(new_response.content, existing_response.content)
        self.assertEqual(new_response.content, verified_response.content)
        self.assertNotIn(settings.SESSION_COOKIE_NAME, new_response.cookies)
        self.assertNotIn(settings.SESSION_COOKIE_NAME, existing_response.cookies)
        self.assertEqual(User.objects.filter(email='uniform@example.com').count(), 1)
        # new: confirmation link; pending again: fresh link; confirmed: notice.
        self.assertEqual(len(mail.outbox), 3)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    @override_settings(ACCOUNT_EMAIL_VERIFICATION_GRACE_DAYS=0)  # strict mode: confirm before first sign-in
    def test_new_registration_creates_account_and_sends_activation_email(self):
        response = self.post('/api/accounts/register/', {
            'email': 'activation@example.com',
            'password': self.password,
            'full_name': 'Activation User',
        })

        self.assertEqual(response.status_code, 202)
        self.assertNotIn('account', response.json())
        self.assertIsNone(self.client.get('/api/accounts/me/').json()['account'])
        user = User.objects.get(email='activation@example.com')
        self.assertFalse(user.membership_profile.email_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Confirm your ResRef account', mail.outbox[0].subject)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_response_is_identical_for_registered_and_unknown_emails(self):
        User.objects.create_user('reset-known@example.com', 'reset-known@example.com', self.password)

        known_response = self.post('/api/accounts/password-reset/', {'email': 'reset-known@example.com'})
        unknown_response = self.post('/api/accounts/password-reset/', {'email': 'reset-unknown@example.com'})

        self.assertEqual(known_response.status_code, unknown_response.status_code)
        self.assertEqual(known_response.content, unknown_response.content)
        self.assertEqual(len(mail.outbox), 1)

    @patch('accounts.services.send_mail', side_effect=RuntimeError('SMTP connection details'))
    def test_password_reset_smtp_failure_is_uniform_and_logged(self, send_mail):
        User.objects.create_user('reset-smtp@example.com', 'reset-smtp@example.com', self.password)

        with self.assertLogs('accounts.api_views', level='ERROR'):
            response = self.post('/api/accounts/password-reset/', {'email': 'reset-smtp@example.com'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['message'], 'If an account exists for that email address, a reset link has been sent.')
        send_mail.assert_called_once()

    @patch('accounts.services.send_mail', side_effect=RuntimeError('SMTP connection details'))
    def test_email_verification_smtp_failure_is_logged_without_error_response(self, send_mail):
        user = User.objects.create_user('verify-smtp@example.com', 'verify-smtp@example.com', self.password)
        self.client.force_login(user)

        with self.assertLogs('accounts.api_views', level='ERROR'):
            response = self.post('/api/accounts/email-verification/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['message'], 'A verification link has been sent to your email address.')
        send_mail.assert_called_once()

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='google-client-id')
    @patch('google.oauth2.id_token.verify_oauth2_token', side_effect=ValueError('private verification detail'))
    def test_google_login_does_not_echo_verification_errors(self, verify):
        response = self.post('/api/accounts/google/', {'credential': 'malformed-credential'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Google sign-in could not be verified.')
        self.assertNotIn('private verification detail', response.content.decode())

    def test_google_sign_in_stays_disabled_until_configured(self):
        response = self.client.get('/api/accounts/config/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['google_enabled'])
        self.assertEqual(self.post('/api/accounts/google/', {'credential': 'not-a-token'}).status_code, 503)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='google-client-id')
    @patch('accounts.api_views.verify_google_credential')
    def test_google_sign_in_links_unbound_password_account(self, verify_google_credential):
        user = User.objects.create_user('google-link@example.com', 'google-link@example.com', self.password)
        # Only accounts whose email is verified may be linked (S-03).
        user.membership_profile.email_verified = True
        user.membership_profile.save(update_fields=['email_verified', 'updated_at'])
        verify_google_credential.return_value = {
            'sub': 'google-subject-a', 'email': user.email, 'email_verified': True,
        }

        response = self.post('/api/accounts/google/', {'credential': 'valid-credential'})

        self.assertEqual(response.status_code, 200)
        user.membership_profile.refresh_from_db()
        self.assertEqual(user.membership_profile.google_subject, 'google-subject-a')
        self.assertEqual(user.membership_profile.auth_provider, 'google')
        self.assertTrue(DashboardActivityLog.objects.filter(
            module='accounts', action='update', object_id=str(user.id),
        ).exists())

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='google-client-id')
    @patch('accounts.api_views.verify_google_credential')
    def test_google_sign_in_uses_existing_subject_before_email(self, verify_google_credential):
        user = User.objects.create_user('subject-owner@example.com', 'subject-owner@example.com', self.password)
        user.membership_profile.google_subject = 'google-subject-existing'
        user.membership_profile.auth_provider = 'google'
        user.membership_profile.save(update_fields=['google_subject', 'auth_provider', 'updated_at'])
        verify_google_credential.return_value = {
            'sub': 'google-subject-existing', 'email': 'changed-google-email@example.com', 'email_verified': True,
        }

        response = self.post('/api/accounts/google/', {'credential': 'valid-credential'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['account']['email'], user.email)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='google-client-id')
    @patch('accounts.api_views.verify_google_credential')
    def test_google_sign_in_does_not_link_matching_legacy_username(self, verify_google_credential):
        legacy_user = User.objects.create_user('google-claim@example.com', 'legacy-owner@example.com', self.password)
        verify_google_credential.return_value = {
            'sub': 'google-subject-email-only', 'email': 'google-claim@example.com', 'email_verified': True,
        }

        response = self.post('/api/accounts/google/', {'credential': 'valid-credential'})

        self.assertEqual(response.status_code, 200)
        legacy_user.membership_profile.refresh_from_db()
        self.assertIsNone(legacy_user.membership_profile.google_subject)
        self.assertEqual(User.objects.get(email='google-claim@example.com').membership_profile.google_subject, 'google-subject-email-only')

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='google-client-id')
    @patch('accounts.api_views.verify_google_credential')
    def test_google_sign_in_refuses_to_replace_existing_subject(self, verify_google_credential):
        victim = User.objects.create_user('google-victim@example.com', 'google-victim@example.com', self.password)
        victim.membership_profile.google_subject = 'google-subject-a'
        victim.membership_profile.auth_provider = 'google'
        victim.membership_profile.save(update_fields=['google_subject', 'auth_provider', 'updated_at'])
        verify_google_credential.return_value = {
            'sub': 'google-subject-b', 'email': victim.email, 'email_verified': True,
        }

        response = self.post('/api/accounts/google/', {'credential': 'attacker-credential'})

        self.assertEqual(response.status_code, 403)
        victim.membership_profile.refresh_from_db()
        self.assertEqual(victim.membership_profile.google_subject, 'google-subject-a')
        self.assertIsNone(self.client.get('/api/accounts/me/').json()['account'])
        self.assertTrue(DashboardActivityLog.objects.filter(
            module='accounts', action='system', object_id=str(victim.id),
        ).exists())

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='google-client-id')
    @patch('accounts.api_views.verify_google_credential')
    def test_authenticated_password_verified_google_link_succeeds(self, verify_google_credential):
        user = User.objects.create_user('explicit-link@example.com', 'explicit-link@example.com', self.password)
        self.client.force_login(user)
        verify_google_credential.return_value = {
            'sub': 'google-subject-explicit', 'email': user.email, 'email_verified': True,
        }

        response = self.post('/api/accounts/google/link/', {
            'credential': 'valid-credential', 'current_password': self.password,
        })

        self.assertEqual(response.status_code, 200)
        user.membership_profile.refresh_from_db()
        self.assertEqual(user.membership_profile.google_subject, 'google-subject-explicit')

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='')
    def test_google_link_requires_google_configuration(self):
        user = User.objects.create_user('link-unconfigured@example.com', 'link-unconfigured@example.com', self.password)
        self.client.force_login(user)

        response = self.post('/api/accounts/google/link/', {
            'credential': 'credential', 'current_password': self.password,
        })

        self.assertEqual(response.status_code, 503)
        self.assertTrue(DashboardActivityLog.objects.filter(
            module='accounts', action='system', object_id=str(user.id),
        ).exists())

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='google-client-id')
    @patch('accounts.api_views.verify_google_credential')
    def test_password_verified_google_link_can_replace_own_subject(self, verify_google_credential):
        user = User.objects.create_user('relink@example.com', 'relink@example.com', self.password)
        user.membership_profile.google_subject = 'google-subject-old'
        user.membership_profile.auth_provider = 'google'
        user.membership_profile.save(update_fields=['google_subject', 'auth_provider', 'updated_at'])
        self.client.force_login(user)
        verify_google_credential.return_value = {
            'sub': 'google-subject-new', 'email': user.email, 'email_verified': True,
        }

        response = self.post('/api/accounts/google/link/', {
            'credential': 'valid-credential', 'current_password': self.password,
        })

        self.assertEqual(response.status_code, 200)
        user.membership_profile.refresh_from_db()
        self.assertEqual(user.membership_profile.google_subject, 'google-subject-new')
        self.assertTrue(DashboardActivityLog.objects.filter(
            module='accounts', action='update', object_id=str(user.id),
            metadata__replaced_existing_google_identity=True,
        ).exists())

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='google-client-id')
    @patch('accounts.api_views.verify_google_credential')
    def test_google_sign_in_creates_new_account(self, verify_google_credential):
        verify_google_credential.return_value = {
            'sub': 'google-subject-new', 'email': 'google-new@example.com', 'email_verified': True,
        }

        response = self.post('/api/accounts/google/', {'credential': 'valid-credential'})

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email='google-new@example.com')
        self.assertEqual(user.membership_profile.google_subject, 'google-subject-new')

    def test_tool_workspace_requires_sign_in(self):
        response = self.client.get('/api/accounts/tool-workspaces/reference-generator/')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.post('/api/accounts/tool-workspaces/reference-generator/', {'data': {}}).status_code, 401)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', FRONTEND_BASE_URL='http://localhost:5173')
    def test_email_verification_flow_marks_profile_verified(self):
        user = User.objects.create_user('verify@example.com', 'verify@example.com', self.password)
        self.client.force_login(user)
        response = self.post('/api/accounts/email-verification/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        verify_url = re.search(r'http://localhost:5173/account\?verify=([^\s]+)', mail.outbox[0].body)
        self.assertIsNotNone(verify_url)
        token = parse_qs(urlparse(verify_url.group(0)).query)['verify'][0]

        response = self.post('/api/accounts/email-verification/confirm/', {'token': token})
        self.assertEqual(response.status_code, 200)
        user.membership_profile.refresh_from_db()
        self.assertTrue(user.membership_profile.email_verified)
        self.assertTrue(response.json()['account']['email_verified'])

    def test_tool_workspace_sync_is_scoped_to_signed_in_user(self):
        user = User.objects.create_user('sync-a@example.com', 'sync-a@example.com', self.password)
        self.client.force_login(user)
        workspace = {
            'style': 'apa',
            'activeListId': 'main-list',
            'lists': [{
                'id': 'main-list',
                'name': 'Systematic review',
                'references': [{'id': 'ref-1', 'type': 'journal', 'title': 'Secure citation sync'}],
            }],
        }
        response = self.post('/api/accounts/tool-workspaces/reference-generator/', {'data': workspace})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['style'], 'apa')

        response = self.client.get('/api/accounts/tool-workspaces/reference-generator/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['lists'][0]['name'], 'Systematic review')

        other_client = self.client_with_csrf()
        other_user = User.objects.create_user('sync-b@example.com', 'sync-b@example.com', self.password)
        other_client.force_login(other_user)
        response = other_client.get('/api/accounts/tool-workspaces/reference-generator/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data'], {})

    @override_settings(USER_TOOL_WORKSPACE_MAX_BYTES=32)
    def test_tool_workspace_rejects_unknown_key_and_oversized_payload(self):
        user = User.objects.create_user('sync-size@example.com', 'sync-size@example.com', self.password)
        self.client.force_login(user)
        self.assertEqual(self.post('/api/accounts/tool-workspaces/not-a-tool/', {'data': {}}).status_code, 404)
        response = self.post('/api/accounts/tool-workspaces/reference-generator/', {'data': {'blob': 'x' * 80}})
        self.assertEqual(response.status_code, 413)

    def test_tool_workspace_respects_feature_entitlements(self):
        user = User.objects.create_user('blocked-tool@example.com', 'blocked-tool@example.com', self.password)
        FeatureEntitlement.objects.update_or_create(
            code='journal_finder',
            defaults={
                'label': 'Journal Finder',
                'description': 'Restricted test feature',
                'free_enabled': False,
                'premium_enabled': True,
                'is_active': True,
            },
        )
        self.client.force_login(user)

        response = self.post('/api/accounts/tool-workspaces/journal-finder/', {'data': {'shortlist': []}})
        self.assertEqual(response.status_code, 403)

        user.membership_profile.tier = 'premium'
        user.membership_profile.save(update_fields=['tier', 'updated_at'])
        response = self.post('/api/accounts/tool-workspaces/journal-finder/', {'data': {'shortlist': []}})
        self.assertEqual(response.status_code, 200)

    def test_workspace_autosave_never_consumes_usage(self):
        user = User.objects.create_user('limited-tool@example.com', 'limited-tool@example.com', self.password)
        UsageLimit.objects.update_or_create(
            feature_code='reference_generator',
            tier='free',
            period='day',
            defaults={'limit': 1, 'is_active': True},
        )
        self.client.force_login(user)

        for index in range(3):
            response = self.post('/api/accounts/tool-workspaces/reference-generator/', {'data': {'items': [index]}})
            self.assertEqual(response.status_code, 200)
        self.assertFalse(UsageRecord.objects.filter(user=user).exists())

    def test_journal_match_usage_is_metered_for_signed_in_users(self):
        user = User.objects.create_user('journal-limit@example.com', 'journal-limit@example.com', self.password)
        UsageLimit.objects.update_or_create(
            feature_code='journal_finder', tier='free', period='day',
            defaults={'limit': 2, 'is_active': True},
        )
        self.assertEqual(self.post('/api/accounts/tool-usage/journal-finder/', {}).status_code, 401)
        self.client.force_login(user)
        codes = [self.post('/api/accounts/tool-usage/journal-finder/', {}).status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])
        self.assertEqual(UsageRecord.objects.filter(user=user, feature_code='journal_finder').count(), 2)
        self.assertEqual(self.post('/api/accounts/tool-usage/not-a-tool/', {}).status_code, 404)

    def test_billing_checkout_requires_test_stripe_configuration(self):
        user = User.objects.create_user('billing-free@example.com', 'billing-free@example.com', self.password)
        self.client.force_login(user)

        response = self.post('/api/accounts/billing/checkout/', {'plan': 'premium_monthly'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('Stripe', response.json()['error'])  # no config details (S-14)

    def test_notifications_api_and_mark_read_flow(self):
        user = User.objects.create_user('notify@example.com', 'notify@example.com', self.password)
        notification = AccountNotification.objects.create(
            user=user,
            title='Payment failed',
            message='Update your billing details.',
            notification_type='billing',
            action_url='/account',
        )
        AccountNotification.objects.create(
            user=None,
            title='Platform announcement',
            message='A new ResRef update is available.',
            notification_type='announcement',
        )
        self.client.force_login(user)

        response = self.client.get('/api/accounts/notifications/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        # Broadcasts now have per-user read state, so both count as unread.
        self.assertEqual(payload['unread_count'], 2)
        self.assertEqual(len(payload['results']), 2)

        response = self.post(f'/api/accounts/notifications/{notification.id}/read/')
        self.assertEqual(response.status_code, 200)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_stripe_subscription_webhook_is_idempotent_and_syncs_premium_access(self):
        user = User.objects.create_user('premium-sync@example.com', 'premium-sync@example.com', self.password)
        plan, _ = SubscriptionPlan.objects.update_or_create(
            code='premium_monthly',
            defaults={
                'label': 'Premium Monthly',
                'tier': 'premium',
                'provider': 'stripe',
                'provider_price_id': 'price_test_monthly',
                'billing_interval': 'month',
                'is_active': True,
            },
        )
        event = {
            'id': 'evt_subscription_active',
            'type': 'customer.subscription.updated',
            'data': {
                'object': {
                    'id': 'sub_test_123',
                    'customer': 'cus_test_123',
                    'status': 'active',
                    'current_period_start': int(time.time()) - 60,
                    'current_period_end': int(time.time()) + 86400,
                    'cancel_at_period_end': False,
                    'metadata': {'resref_user_id': str(user.id), 'plan_code': plan.code},
                    'items': {'data': [{'price': {'id': plan.provider_price_id}}]},
                },
            },
        }

        result = process_verified_stripe_event(event)
        self.assertTrue(result['processed'])
        self.assertFalse(result['duplicate'])
        user.membership_profile.refresh_from_db()
        self.assertEqual(user.membership_profile.tier, 'premium')
        self.assertTrue(UserSubscription.objects.filter(user=user, provider_subscription_id='sub_test_123', status='active').exists())

        duplicate = process_verified_stripe_event(event)
        self.assertFalse(duplicate['processed'])
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(BillingWebhookEvent.objects.filter(event_id='evt_subscription_active').count(), 1)

        cancelled_event = {
            **event,
            'id': 'evt_subscription_cancelled',
            'type': 'customer.subscription.deleted',
            'data': {'object': {**event['data']['object'], 'status': 'canceled', 'current_period_end': int(time.time()) - 60}},
        }
        process_verified_stripe_event(cancelled_event)
        user.membership_profile.refresh_from_db()
        self.assertEqual(user.membership_profile.tier, 'free')


class GoogleLinkingSafetyTests(TestCase):
    password = 'Secur3-ResRef!Passphrase'

    def setUp(self):
        cache.clear()

    def _google(self, info):
        from unittest import mock
        with override_settings(GOOGLE_OAUTH_CLIENT_ID='client-id.apps.googleusercontent.com'), \
                mock.patch('google.oauth2.id_token.verify_oauth2_token', return_value=info):
            return self.client.post('/api/accounts/google/', data=json.dumps({'credential': 'x'}), content_type='application/json')

    def _info(self, email, sub='google-sub-1'):
        return {'iss': 'https://accounts.google.com', 'email': email, 'email_verified': True, 'sub': sub, 'name': 'G User'}

    def test_google_does_not_take_over_unverified_password_account(self):
        User.objects.create_user('squatter@example.com', 'squatter@example.com', self.password)
        response = self._google(self._info('squatter@example.com'))
        self.assertEqual(response.status_code, 409)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_google_links_verified_account(self):
        user = User.objects.create_user('verified@example.com', 'verified@example.com', self.password)
        user.membership_profile.email_verified = True
        user.membership_profile.save(update_fields=['email_verified', 'updated_at'])
        response = self._google(self._info('verified@example.com'))
        self.assertEqual(response.status_code, 200)
        user.membership_profile.refresh_from_db()
        self.assertEqual(user.membership_profile.google_subject, 'google-sub-1')

    def test_google_rejects_different_subject_and_inactive_users(self):
        user = User.objects.create_user('linked@example.com', 'linked@example.com', self.password)
        user.membership_profile.email_verified = True
        user.membership_profile.google_subject = 'original-sub'
        user.membership_profile.save(update_fields=['email_verified', 'google_subject', 'updated_at'])
        self.assertEqual(self._google(self._info('linked@example.com', sub='other-sub')).status_code, 403)  # remote's stricter refusal
        user.is_active = False
        user.save(update_fields=['is_active'])
        self.assertEqual(self._google(self._info('linked@example.com', sub='original-sub')).status_code, 403)

    def test_google_creates_new_account(self):
        response = self._google(self._info('brand-new@example.com', sub='new-sub'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(email='brand-new@example.com').exists())


# Fake values, assembled so the CI secret scanner does not flag them.
FAKE_STRIPE_TEST_KEY = 'sk_' + 'test_unit_only'
FAKE_STRIPE_LIVE_KEY = 'sk_' + 'live_never_accepted'
FAKE_WEBHOOK_SECRET = 'whsec' + '_unit_test_secret'


@override_settings(STRIPE_SECRET_KEY=FAKE_STRIPE_TEST_KEY, STRIPE_WEBHOOK_SECRET=FAKE_WEBHOOK_SECRET)
class StripeWebhookTests(TestCase):
    """T-17: real Stripe SDK objects (not dicts) and signed webhooks."""

    password = 'Secur3-ResRef!Passphrase'

    def setUp(self):
        self.user = User.objects.create_user('stripe-user@example.com', 'stripe-user@example.com', self.password)
        self.plan, _ = SubscriptionPlan.objects.update_or_create(
            code='premium_monthly',
            defaults={'label': 'Premium Monthly', 'tier': 'premium', 'provider': 'stripe',
                      'provider_price_id': 'price_test_monthly', 'billing_interval': 'month', 'is_active': True},
        )

    def _subscription(self, status='active', event_id='evt_t17', event_type='customer.subscription.updated'):
        now = int(time.time())
        # API 2025-03-31+: the billing period lives on the subscription item.
        return {
            'id': event_id, 'object': 'event', 'type': event_type,
            'data': {'object': {
                'id': 'sub_t17', 'object': 'subscription', 'customer': 'cus_t17', 'status': status,
                'cancel_at_period_end': False,
                'metadata': {'resref_user_id': str(self.user.id), 'plan_code': self.plan.code},
                'items': {'object': 'list', 'data': [{
                    'id': 'si_t17', 'object': 'subscription_item',
                    'current_period_start': now - 60, 'current_period_end': now + 30 * 86400,
                    'price': {'id': self.plan.provider_price_id, 'object': 'price'},
                }]},
            }},
        }

    def _signed_post(self, payload):
        import hashlib
        import hmac
        body = json.dumps(payload)
        timestamp = int(time.time())
        signature = hmac.new(FAKE_WEBHOOK_SECRET.encode(), f'{timestamp}.{body}'.encode(), hashlib.sha256).hexdigest()
        return self.client.post(
            '/api/accounts/billing/webhook/', data=body, content_type='application/json',
            HTTP_STRIPE_SIGNATURE=f't={timestamp},v1={signature}',
        )

    def test_stripe_object_from_sdk_is_processed(self):
        import stripe
        event = stripe.Event.construct_from(self._subscription(), FAKE_STRIPE_TEST_KEY)
        self.assertFalse(isinstance(event, dict))  # the case that used to crash
        result = process_verified_stripe_event(event)
        self.assertTrue(result['processed'])
        subscription = UserSubscription.objects.get(provider_subscription_id='sub_t17')
        self.assertIsNotNone(subscription.current_period_end)
        self.assertGreater(subscription.current_period_end.timestamp(), time.time() + 29 * 86400)
        self.user.membership_profile.refresh_from_db()
        self.assertEqual(self.user.membership_profile.tier, 'premium')

    def test_signed_webhook_goes_through_construct_event(self):
        response = self._signed_post(self._subscription(event_id='evt_signed'))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['processed'])
        duplicate = self._signed_post(self._subscription(event_id='evt_signed'))
        self.assertTrue(duplicate.json()['duplicate'])
        self.assertEqual(BillingWebhookEvent.objects.filter(event_id='evt_signed').count(), 1)

    def test_bad_signature_is_rejected(self):
        body = json.dumps(self._subscription(event_id='evt_forged'))
        response = self.client.post('/api/accounts/billing/webhook/', data=body, content_type='application/json',
                                    HTTP_STRIPE_SIGNATURE=f't={int(time.time())},v1=deadbeef')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(BillingWebhookEvent.objects.filter(event_id='evt_forged').exists())

    def test_failed_processing_rolls_back_so_stripe_can_retry(self):
        with patch('accounts.billing.sync_subscription_payload', side_effect=RuntimeError('db hiccup')):
            with self.assertRaises(RuntimeError):
                process_verified_stripe_event(self._subscription(event_id='evt_retry'))
        self.assertFalse(BillingWebhookEvent.objects.filter(event_id='evt_retry').exists())
        self.assertTrue(process_verified_stripe_event(self._subscription(event_id='evt_retry'))['processed'])

    def test_checkout_session_object_is_serialized(self):
        import stripe
        self.client.force_login(self.user)
        session = stripe.checkout.Session.construct_from({'id': 'cs_test_1', 'object': 'checkout.session', 'url': 'https://checkout.stripe.com/c/pay/cs_test_1'}, FAKE_STRIPE_TEST_KEY)
        with patch('accounts.api_views.create_checkout_session', return_value=session):
            response = self.client.post('/api/accounts/billing/checkout/', data=json.dumps({'plan': 'premium_monthly'}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['checkout_url'], 'https://checkout.stripe.com/c/pay/cs_test_1')

    @override_settings(STRIPE_SECRET_KEY=FAKE_STRIPE_LIVE_KEY)
    def test_live_keys_are_refused(self):
        from django.core.exceptions import ImproperlyConfigured
        from .billing import get_stripe
        with self.assertRaises(ImproperlyConfigured):
            get_stripe()



class RegistrationConfirmationTests(TestCase):
    """T-18 / S-15: sign-up never reveals existing accounts; login waits for the link."""

    password = 'Secur3-ResRef!Passphrase'

    def setUp(self):
        cache.clear()
        mail.outbox.clear()

    def _post(self, path, data):
        return self.client.post(path, data=json.dumps(data), content_type='application/json')

    def _token(self):
        link = next(line for message in mail.outbox for line in message.body.splitlines() if 'confirm-email?token=' in line)
        return parse_qs(urlparse(link.strip()).query)['token'][0]

    @override_settings(ACCOUNT_EMAIL_VERIFICATION_GRACE_DAYS=0)  # strict mode: confirm before first sign-in
    def test_existing_and_new_addresses_get_the_same_answer(self):
        User.objects.create_user('taken@example.com', 'taken@example.com', self.password)
        taken = self._post('/api/accounts/register/', {'email': 'taken@example.com', 'password': self.password, 'full_name': 'X'})
        fresh = self._post('/api/accounts/register/', {'email': 'fresh@example.com', 'password': self.password, 'full_name': 'Y'})
        self.assertEqual(taken.status_code, fresh.status_code)
        self.assertEqual(taken.json(), fresh.json())
        self.assertNotIn('_auth_user_id', self.client.session)
        subjects = sorted(message.subject for message in mail.outbox)
        self.assertEqual(len(subjects), 2)
        self.assertIn('Someone tried to create a ResRef account with your email', subjects)

    @override_settings(ACCOUNT_EMAIL_VERIFICATION_GRACE_DAYS=0)  # strict mode: confirm before first sign-in
    def test_unconfirmed_account_cannot_sign_in_until_link_is_used(self):
        self._post('/api/accounts/register/', {'email': 'wait@example.com', 'password': self.password, 'full_name': 'W'})
        blocked = self._post('/api/accounts/login/', {'email': 'wait@example.com', 'password': self.password})
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()['code'], 'email_unconfirmed')
        token = self._token()
        confirmed = self._post('/api/accounts/register/confirm/', {'token': token})
        self.assertEqual(confirmed.status_code, 200)
        self.assertTrue(confirmed.json()['account']['email_verified'])
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(self._post('/api/accounts/register/confirm/', {'token': token}).status_code, 400)  # single use
        self.client.logout()
        self.assertEqual(self._post('/api/accounts/login/', {'email': 'wait@example.com', 'password': self.password}).status_code, 200)

    def test_accounts_created_before_the_rule_are_not_locked_out(self):
        User.objects.create_user('legacy@example.com', 'legacy@example.com', self.password)
        self.assertEqual(self._post('/api/accounts/login/', {'email': 'legacy@example.com', 'password': self.password}).status_code, 200)

    def test_resend_is_neutral_and_sends_only_for_pending_accounts(self):
        self._post('/api/accounts/register/', {'email': 'again@example.com', 'password': self.password, 'full_name': 'A'})
        mail.outbox.clear()
        pending = self._post('/api/accounts/register/resend/', {'email': 'again@example.com'})
        unknown = self._post('/api/accounts/register/resend/', {'email': 'nobody@example.com'})
        self.assertEqual(pending.json(), unknown.json())
        self.assertEqual(len(mail.outbox), 1)

    def test_password_reset_confirms_the_address(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        self._post('/api/accounts/register/', {'email': 'reset@example.com', 'password': self.password, 'full_name': 'R'})
        user = User.objects.get(email='reset@example.com')
        response = self._post('/api/accounts/password-reset/confirm/', {
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': default_token_generator.make_token(user),
            'new_password': 'Another-Secur3-Passphrase!',
        })
        self.assertEqual(response.status_code, 200, response.content)
        user.membership_profile.refresh_from_db()
        self.assertTrue(user.membership_profile.email_verified)
        self.assertFalse(user.membership_profile.email_confirmation_required)

    def test_google_claims_an_unconfirmed_squatted_account_and_drops_its_password(self):
        from unittest import mock
        self._post('/api/accounts/register/', {'email': 'owner@example.com', 'password': self.password, 'full_name': 'Squatter'})
        info = {'iss': 'https://accounts.google.com', 'email': 'owner@example.com', 'email_verified': True, 'sub': 'real-owner', 'name': 'Owner'}
        with override_settings(GOOGLE_OAUTH_CLIENT_ID='client-id.apps.googleusercontent.com'), \
                mock.patch('google.oauth2.id_token.verify_oauth2_token', return_value=info):
            response = self._post('/api/accounts/google/', {'credential': 'x'})
        self.assertEqual(response.status_code, 200, response.content)
        user = User.objects.get(email='owner@example.com')
        self.assertFalse(user.has_usable_password())


@override_settings(NEWSLETTER_ENABLED=True)
class NewsletterDoubleOptInTests(TestCase):
    """T-18 / S-16."""

    def setUp(self):
        cache.clear()
        mail.outbox.clear()

    def _subscribe(self, email):
        return self.client.post('/api/newsletter/subscribe/', data=json.dumps({'email': email}), content_type='application/json')

    def test_subscriber_is_pending_until_confirmed(self):
        from dashboard.models import NewsletterSubscriber
        response = self._subscribe('reader@example.com')
        self.assertEqual(response.status_code, 202)
        subscriber = NewsletterSubscriber.objects.get(email='reader@example.com')
        self.assertFalse(subscriber.is_active)
        self.assertIsNone(subscriber.confirmed_at)
        link = next(line for line in mail.outbox[0].body.splitlines() if 'newsletter/confirm?token=' in line)
        token = parse_qs(urlparse(link.strip()).query)['token'][0]
        confirmed = self.client.post('/api/newsletter/confirm/', data=json.dumps({'token': token}), content_type='application/json')
        self.assertEqual(confirmed.status_code, 200)
        subscriber.refresh_from_db()
        self.assertTrue(subscriber.is_active)
        self.assertIsNotNone(subscriber.confirmed_at)
        again = self.client.post('/api/newsletter/confirm/', data=json.dumps({'token': token}), content_type='application/json')
        self.assertEqual(again.status_code, 400)

    def test_answers_are_identical_for_every_state(self):
        from dashboard.models import NewsletterSubscriber
        from django.utils import timezone
        NewsletterSubscriber.objects.create(email='active@example.com', is_active=True, confirmed_at=timezone.now())
        NewsletterSubscriber.objects.create(email='paused@example.com', is_active=False, confirmed_at=timezone.now())
        answers = {email: self._subscribe(email).json() for email in ('active@example.com', 'paused@example.com', 'new@example.com')}
        self.assertEqual(len({json.dumps(value, sort_keys=True) for value in answers.values()}), 1)
        self.assertFalse(NewsletterSubscriber.objects.get(email='paused@example.com').is_active)


class DashboardScopeTests(TestCase):
    """T-18 / S-10: role names alone never unlock dashboard data."""

    password = 'Secur3-ResRef!Passphrase'

    def test_admin_role_without_dashboard_access_gets_no_user_results(self):
        outsider = User.objects.create_user('outsider@example.com', 'outsider@example.com', self.password)
        outsider.membership_profile.access_role = 'admin'  # but not staff -> no dashboard access
        outsider.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(outsider)
        response = self.client.get('/api/search/', {'q': 'example', 'type': 'user'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'].get('users', []), [])

    def test_export_requires_read_permission_for_the_module(self):
        from dashboard.models import TeamMember
        from accounts.models import AccountRole
        viewer = User.objects.create_user('viewer@example.com', 'viewer@example.com', self.password, is_staff=True)
        TeamMember.objects.create(user=viewer, role='editor')
        viewer.membership_profile.account_role = AccountRole.objects.get(code='manager')
        viewer.membership_profile.save(update_fields=['account_role', 'updated_at'])
        self.client.force_login(viewer)
        # Managers may export content, but not account settings.
        self.assertEqual(self.client.get('/api/dashboard/export/posts/?format=json').status_code, 200)
        self.assertEqual(self.client.get('/api/dashboard/export/settings/?format=json').status_code, 403)


class EmailConfirmationSwitchTests(TestCase):
    """Temporary mode while no SMTP provider is configured."""

    password = 'Secur3-ResRef!Passphrase'

    def setUp(self):
        cache.clear()

    def _post(self, path, data):
        return self.client.post(path, data=json.dumps(data), content_type='application/json')

    @override_settings(ACCOUNT_EMAIL_CONFIRMATION_REQUIRED=False)
    def test_switch_off_signs_new_accounts_in_immediately(self):
        response = self._post('/api/accounts/register/', {'email': 'now@example.com', 'password': self.password, 'full_name': 'Now'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['account']['email'], 'now@example.com')
        self.assertIn('_auth_user_id', self.client.session)
        self.client.logout()
        self.assertEqual(self._post('/api/accounts/login/', {'email': 'now@example.com', 'password': self.password}).status_code, 200)

    @override_settings(ACCOUNT_EMAIL_VERIFICATION_GRACE_DAYS=0)  # strict mode: confirm before first sign-in
    def test_accounts_waiting_for_confirmation_can_sign_in_once_switched_off(self):
        self._post('/api/accounts/register/', {'email': 'waiting@example.com', 'password': self.password, 'full_name': 'W'})
        self.assertEqual(self._post('/api/accounts/login/', {'email': 'waiting@example.com', 'password': self.password}).status_code, 403)
        with override_settings(ACCOUNT_EMAIL_CONFIRMATION_REQUIRED=False):
            self.assertEqual(self._post('/api/accounts/login/', {'email': 'waiting@example.com', 'password': self.password}).status_code, 200)
