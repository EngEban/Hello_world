import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.test import TestCase, override_settings
from django.utils import timezone

from core.email_backends import BrevoApiEmailBackend


@override_settings(
    ACCOUNT_EMAIL_CONFIRMATION_REQUIRED=True,
    ACCOUNT_EMAIL_VERIFICATION_GRACE_DAYS=2,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class VerificationGracePeriodTests(TestCase):
    """New members get in straight away and have 2 days to confirm their email."""

    password = 'Secur3-ResRef!Passphrase'

    def setUp(self):
        cache.clear()

    def register(self, email='new.member@example.com'):
        return self.client.post('/api/accounts/register/', json.dumps({
            'full_name': 'New Member', 'email': email, 'password': self.password, 'country': 'AE',
        }), content_type='application/json')

    def sign_in(self, email='new.member@example.com'):
        return self.client.post('/api/accounts/login/', json.dumps({'email': email, 'password': self.password}), content_type='application/json')

    def test_registration_signs_in_immediately_and_sends_the_link(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data['verification_required'])
        self.assertFalse(data['account']['email_verified'])
        self.assertIsNotNone(data['account']['email_verify_by'])
        self.assertIn('within 2 days', data['message'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Confirm your ResRef account', mail.outbox[0].subject)
        self.assertEqual(self.client.get('/api/accounts/me/').json()['account']['email'], 'new.member@example.com')

    def test_unconfirmed_member_can_sign_in_during_the_grace_period_only(self):
        self.register()
        self.client.logout()
        self.assertEqual(self.sign_in().status_code, 200)
        self.client.logout()
        User.objects.filter(email='new.member@example.com').update(date_joined=timezone.now() - timedelta(days=3))
        blocked = self.sign_in()
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()['code'], 'email_unconfirmed')

    def test_existing_address_gets_a_clear_message(self):
        self.register()
        self.client.logout()
        again = self.register()
        self.assertEqual(again.status_code, 202)
        self.assertIn('already registered', again.json()['message'])


class BrevoApiBackendTests(TestCase):
    def test_sends_html_and_text_through_the_https_api(self):
        message = EmailMultiAlternatives('Hello', 'Plain body', 'ResRef <no-reply@resref.com>', ['member@example.com'])
        message.attach_alternative('<p>HTML body</p>', 'text/html')
        with mock.patch('core.email_backends.requests.Session.post') as post:
            post.return_value.status_code = 201
            sent = BrevoApiEmailBackend(api_key='xkeysib-test').send_messages([message])
        self.assertEqual(sent, 1)
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['sender'], {'email': 'no-reply@resref.com', 'name': 'ResRef'})
        self.assertEqual(payload['to'], [{'email': 'member@example.com'}])
        self.assertEqual(payload['htmlContent'], '<p>HTML body</p>')
        self.assertEqual(payload['textContent'], 'Plain body')
        self.assertEqual(post.call_args.kwargs['headers']['api-key'], 'xkeysib-test')

    def test_api_errors_are_raised_so_they_are_logged(self):
        message = EmailMultiAlternatives('Hello', 'Body', 'no-reply@resref.com', ['member@example.com'])
        with mock.patch('core.email_backends.requests.Session.post') as post:
            post.return_value.status_code = 401
            post.return_value.text = '{"message":"Key not found"}'
            with self.assertRaises(RuntimeError):
                BrevoApiEmailBackend(api_key='xkeysib-wrong').send_messages([message])
