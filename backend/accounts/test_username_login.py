import json

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase


class UsernameSignInTests(TestCase):
    """Members can sign in with their email or their username (any letter case)."""

    password = 'Secur3-ResRef!Passphrase'

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('jamal.ataya', 'jamal@example.com', self.password)
        profile = self.user.membership_profile
        profile.email_verified = True
        profile.save()

    def sign_in(self, identifier, password=None):
        return self.client.post('/api/accounts/login/', json.dumps({'email': identifier, 'password': password or self.password}), content_type='application/json')

    def test_username_and_email_both_sign_in(self):
        self.assertEqual(self.sign_in('jamal.ataya').status_code, 200)
        self.client.logout()
        self.assertEqual(self.sign_in('Jamal.Ataya').status_code, 200)
        self.client.logout()
        self.assertEqual(self.sign_in('jamal@example.com').status_code, 200)

    def test_wrong_password_gives_one_neutral_message(self):
        response = self.sign_in('jamal.ataya', 'wrong-password-123')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'Invalid email, username or password.')
