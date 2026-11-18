"""Launch audit: profile country/phone, security emails, sessions, email change,
data export and self-service account deletion."""

import json
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from dashboard.models import NewsletterSubscriber
from .models import EmailVerificationRequest, MembershipProfile, SubscriptionPlan, UserSubscription, UserToolWorkspace
from .profile_fields import clean_country, clean_phone_number, country_names
from .services import hash_token


PASSWORD = 'Secur3-ResRef!Passphrase'
NEW_PASSWORD = 'Anoth3r-ResRef!Passphrase'


class LaunchAccountTestCase(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox.clear()
        self.client = self.csrf_client()

    def csrf_client(self):
        client = Client(enforce_csrf_checks=True)
        client.get('/api/accounts/csrf/')
        return client

    def post(self, path, data=None, client=None):
        client = client or self.client
        return client.post(path, data=json.dumps(data or {}), content_type='application/json',
                           HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)

    def make_user(self, email='member@example.com', password=PASSWORD):
        user = User.objects.create_user(email, email, password)
        profile = user.membership_profile
        profile.email_verified = True
        profile.save()
        return user

    def login(self, email='member@example.com', password=PASSWORD, client=None, **extra):
        return self.post('/api/accounts/login/', {'email': email, 'password': password, **extra}, client=client)

    def subjects(self):
        return [message.subject for message in mail.outbox]


class ProfileFieldTests(LaunchAccountTestCase):
    def test_country_list_is_iso_alpha2_with_names(self):
        names = country_names()
        self.assertGreaterEqual(len(names), 249)
        self.assertEqual(names['GB'], 'United Kingdom')
        self.assertIn('AQ', names)  # territories without phone numbers are still countries
        self.assertNotIn('AN', names)  # withdrawn code
        self.assertEqual(clean_country(' gb '), 'GB')
        self.assertEqual(clean_country(''), '')
        for bad in ('ZZ', 'GBR', 'G', 5):
            with self.assertRaises(Exception):
                clean_country(bad)

    def test_phone_is_normalised_to_e164(self):
        self.assertEqual(clean_phone_number('+44 7911 123456'), '+447911123456')
        self.assertEqual(clean_phone_number('07911 123456', 'GB'), '+447911123456')
        self.assertEqual(clean_phone_number(''), '')
        for bad in ('12345', '+44 123', 'not a phone', '07911 123456'):
            with self.assertRaises(Exception):
                clean_phone_number(bad)

    @override_settings(ACCOUNT_EMAIL_VERIFICATION_GRACE_DAYS=0)  # strict mode: confirm before first sign-in
    def test_register_stores_country_and_phone(self):
        response = self.post('/api/accounts/register/', {
            'email': 'new@example.com', 'password': PASSWORD, 'full_name': 'New Member',
            'country': 'gb', 'phone_number': '+44 7911 123456',
        })
        self.assertEqual(response.status_code, 202, response.content)
        profile = MembershipProfile.objects.get(user__email='new@example.com')
        self.assertEqual((profile.country, profile.phone_number), ('GB', '+447911123456'))

    def test_register_rejects_invalid_country_or_phone_before_lookup(self):
        self.make_user('taken@example.com')
        for extra in ({'country': 'XX'}, {'phone_number': '+1 555'}):
            for email in ('taken@example.com', 'free@example.com'):
                response = self.post('/api/accounts/register/', {'email': email, 'password': PASSWORD, 'full_name': 'A B', **extra})
                self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email='free@example.com').exists())

    def test_register_password_similar_to_email_is_rejected(self):
        response = self.post('/api/accounts/register/', {
            'email': 'marvellous.researcher@example.com', 'password': 'marvellous.researcher', 'full_name': 'M R',
        })
        self.assertEqual(response.status_code, 400)

    def test_profile_update_and_account_payload(self):
        self.make_user()
        self.login()
        response = self.post('/api/accounts/profile/', {'country': 'US', 'phone_number': '+1 202 555 0143'})
        self.assertEqual(response.status_code, 200, response.content)
        account = response.json()['account']
        self.assertEqual(account['country'], 'US')
        self.assertEqual(account['country_name'], 'United States')
        self.assertEqual(account['phone_number'], '+12025550143')
        self.assertTrue(account['has_password'])
        # Omitting the fields keeps them; blank clears them.
        self.post('/api/accounts/profile/', {'display_name': 'Renamed'})
        self.assertEqual(MembershipProfile.objects.get(user__email='member@example.com').country, 'US')
        cleared = self.post('/api/accounts/profile/', {'country': '', 'phone_number': ''}).json()['account']
        self.assertEqual((cleared['country'], cleared['phone_number']), ('', ''))
        self.assertEqual(self.post('/api/accounts/profile/', {'phone_number': '12'}).status_code, 400)


class EmailAndSessionTests(LaunchAccountTestCase):
    def test_account_emails_have_plain_text_and_html_from_default_sender(self):
        self.make_user()
        self.post('/api/accounts/password-reset/', {'email': 'member@example.com'})
        message = mail.outbox[-1]
        self.assertEqual(message.from_email, 'ResRef <no-reply@resref.com>')
        self.assertIn('/account/reset-password?uid=', message.body)
        html, mime = message.alternatives[0]
        self.assertEqual(mime, 'text/html')
        self.assertIn('Choose a new password', html)
        self.assertIn('reset-password?uid=', html)

    def test_new_signin_email_only_for_unknown_device(self):
        self.make_user()
        self.assertEqual(self.login().status_code, 200)
        self.assertIn('New sign-in to your ResRef account', self.subjects())
        mail.outbox.clear()
        self.post('/api/accounts/logout/')
        self.assertEqual(self.login().status_code, 200)
        self.assertNotIn('New sign-in to your ResRef account', self.subjects())

    @override_settings(ACCOUNT_NEW_SIGNIN_EMAILS=False)
    def test_new_signin_email_can_be_switched_off(self):
        self.make_user()
        self.login()
        self.assertEqual(mail.outbox, [])

    def test_login_rotates_session_and_remember_me_controls_expiry(self):
        self.make_user()
        before = self.client.cookies.get('sessionid')
        self.login(remember=False)
        self.assertNotEqual(before, self.client.cookies['sessionid'].value)
        self.assertTrue(self.client.session.get_expire_at_browser_close())
        other = self.csrf_client()
        self.login(client=other)
        self.assertFalse(other.session.get_expire_at_browser_close())

    def test_password_change_signs_out_other_sessions_and_notifies(self):
        self.make_user()
        other = self.csrf_client()
        self.login()
        self.login(client=other)
        mail.outbox.clear()
        response = self.post('/api/accounts/password/', {'current_password': PASSWORD, 'new_password': NEW_PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(self.client.get('/api/accounts/me/').json()['account'])
        self.assertIsNone(other.get('/api/accounts/me/').json()['account'])
        self.assertIn('Your ResRef password was changed', self.subjects())

    def test_password_change_guessing_is_rate_limited(self):
        self.make_user()
        self.login()
        codes = [self.post('/api/accounts/password/', {'current_password': 'wrong-guess', 'new_password': NEW_PASSWORD}).status_code for _ in range(11)]
        self.assertEqual(codes[-1], 429)

    def test_password_reset_signs_out_sessions_and_notifies(self):
        user = self.make_user()
        self.login()
        mail.outbox.clear()
        self.post('/api/accounts/password-reset/', {'email': user.email}, client=self.csrf_client())
        link = next(line for line in mail.outbox[0].body.splitlines() if 'reset-password?uid=' in line)
        query = parse_qs(urlparse(link).query)
        response = self.post('/api/accounts/password-reset/confirm/', {
            'uid': query['uid'][0], 'token': query['token'][0], 'new_password': NEW_PASSWORD,
        }, client=self.csrf_client())
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.client.get('/api/accounts/me/').json()['account'])
        self.assertIn('Your ResRef password was changed', self.subjects())

    def test_logout_invalidates_the_session(self):
        self.make_user()
        self.login()
        session_key = self.client.session.session_key
        self.post('/api/accounts/logout/')
        from django.contrib.sessions.models import Session
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())

    def test_legacy_verification_rejects_token_for_another_address(self):
        user = User.objects.create_user('legacy@example.com', 'legacy@example.com', PASSWORD)
        EmailVerificationRequest.objects.create(
            user=user, email='other@example.com', token_hash=hash_token('tok-1'), expires_at=timezone.now() + timedelta(hours=1),
        )
        self.client.force_login(user)
        response = self.post('/api/accounts/email-verification/confirm/', {'token': 'tok-1'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(MembershipProfile.objects.get(user=user).email_verified)


class EmailChangeTests(LaunchAccountTestCase):
    def change_link_token(self):
        link = next(line for message in mail.outbox for line in message.body.splitlines() if 'email_change=' in line)
        return parse_qs(urlparse(link.strip()).query)['email_change'][0]

    def test_email_change_requires_confirmation_from_new_address(self):
        user = self.make_user()
        self.login()
        mail.outbox.clear()
        response = self.post('/api/accounts/email/', {'new_email': 'New@Example.com', 'current_password': PASSWORD})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(mail.outbox[0].to, ['new@example.com'])
        user.refresh_from_db()
        self.assertEqual(user.email, 'member@example.com')  # unchanged until confirmed
        token = self.change_link_token()
        mail.outbox.clear()
        confirmed = self.post('/api/accounts/email/confirm/', {'token': token})
        self.assertEqual(confirmed.status_code, 200, confirmed.content)
        user.refresh_from_db()
        self.assertEqual((user.email, user.username), ('new@example.com', 'new@example.com'))
        self.assertEqual(mail.outbox[0].to, ['member@example.com'])  # old address is told
        self.assertEqual(self.post('/api/accounts/email/confirm/', {'token': token}).status_code, 400)  # single use
        # The change token cannot be used to sign in through the sign-up confirmation path.
        self.assertEqual(self.post('/api/accounts/register/confirm/', {'token': token}, client=self.csrf_client()).status_code, 400)

    def test_email_change_needs_password_and_hides_taken_addresses(self):
        self.make_user()
        self.make_user('taken@example.com')
        self.login()
        mail.outbox.clear()
        self.assertEqual(self.post('/api/accounts/email/', {'new_email': 'x@example.com', 'current_password': 'nope'}).status_code, 400)
        taken = self.post('/api/accounts/email/', {'new_email': 'taken@example.com', 'current_password': PASSWORD})
        free = self.post('/api/accounts/email/', {'new_email': 'free@example.com', 'current_password': PASSWORD})
        self.assertEqual(taken.status_code, free.status_code)
        self.assertEqual(taken.json(), free.json())
        self.assertFalse(EmailVerificationRequest.objects.filter(email='taken@example.com').exists())

    def test_change_token_of_one_user_is_useless_to_another(self):
        self.make_user()
        self.login()
        self.post('/api/accounts/email/', {'new_email': 'new@example.com', 'current_password': PASSWORD})
        token = self.change_link_token()
        intruder = self.csrf_client()
        self.make_user('intruder@example.com')
        self.login('intruder@example.com', client=intruder)
        self.assertEqual(self.post('/api/accounts/email/confirm/', {'token': token}, client=intruder).status_code, 400)


class ExportAndDeletionTests(LaunchAccountTestCase):
    def test_export_contains_member_data(self):
        user = self.make_user()
        UserToolWorkspace.objects.create(user=user, tool_key='reference-generator', data={'refs': [1]})
        self.login()
        response = self.client.get('/api/accounts/export/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        data = response.json()
        self.assertEqual(data['account']['email'], 'member@example.com')
        self.assertEqual(data['tool_workspaces'][0]['data'], {'refs': [1]})
        self.assertNotIn('pbkdf2', json.dumps(data).lower())  # never a password hash
        self.assertNotIn('google_subject', data['profile'])

    def test_export_requires_sign_in(self):
        self.assertEqual(self.client.get('/api/accounts/export/').status_code, 401)

    def test_delete_requires_confirmation_and_password(self):
        self.make_user()
        self.login()
        self.assertEqual(self.post('/api/accounts/delete/', {'confirm': 'nope', 'current_password': PASSWORD}).status_code, 400)
        self.assertEqual(self.post('/api/accounts/delete/', {'confirm': 'DELETE', 'current_password': 'wrong'}).status_code, 400)
        self.assertTrue(User.objects.get(email='member@example.com').is_active)

    def test_delete_anonymises_and_keeps_related_rows(self):
        user = self.make_user()
        profile = user.membership_profile
        profile.country, profile.phone_number, profile.organization = 'GB', '+447911123456', 'Uni'
        profile.save()
        UserToolWorkspace.objects.create(user=user, tool_key='reference-generator', data={'refs': [1]})
        NewsletterSubscriber.objects.create(email='member@example.com', is_active=True, confirmed_at=timezone.now())
        self.login()
        mail.outbox.clear()
        response = self.post('/api/accounts/delete/', {'confirm': 'DELETE', 'current_password': PASSWORD})
        self.assertEqual(response.status_code, 200, response.content)
        user.refresh_from_db()
        profile.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(user.email, '')
        self.assertTrue(user.username.startswith('deleted-'))
        self.assertFalse(user.has_usable_password())
        self.assertEqual((profile.country, profile.phone_number, profile.organization), ('', '', ''))
        self.assertIsNotNone(profile.deleted_at)
        self.assertTrue(UserToolWorkspace.objects.filter(user=user).exists())  # nothing hard-deleted
        self.assertFalse(NewsletterSubscriber.objects.get(email='member@example.com').is_active)
        self.assertEqual(mail.outbox[0].to, ['member@example.com'])
        self.assertIsNone(self.client.get('/api/accounts/me/').json()['account'])
        self.assertEqual(self.login().status_code, 401)

    def test_staff_and_paying_members_cannot_self_delete(self):
        staff = self.make_user('staff@example.com')
        staff.is_staff = True
        staff.save()
        self.login('staff@example.com')
        self.assertEqual(self.post('/api/accounts/delete/', {'confirm': 'DELETE', 'current_password': PASSWORD}).status_code, 409)

        payer = self.make_user('payer@example.com')
        plan = SubscriptionPlan.objects.filter(code='premium_monthly').first() or SubscriptionPlan.objects.create(code='premium_monthly', label='Premium')
        UserSubscription.objects.create(user=payer, plan=plan, provider='stripe', status='active')
        client = self.csrf_client()
        self.login('payer@example.com', client=client)
        self.assertEqual(self.post('/api/accounts/delete/', {'confirm': 'DELETE', 'current_password': PASSWORD}, client=client).status_code, 409)
        self.assertTrue(User.objects.get(pk=payer.pk).is_active)

    def test_google_only_account_deletes_with_typed_confirmation(self):
        user = User.objects.create_user('google-abc', 'g@example.com')
        user.set_unusable_password()
        user.save()
        self.client.force_login(user)
        response = self.post('/api/accounts/delete/', {'confirm': 'delete'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(User.objects.get(pk=user.pk).is_active)
