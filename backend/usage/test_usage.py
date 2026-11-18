import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from accounts.entitlements import consume_usage, meter_action
from accounts.models import FeatureEntitlement, UsageLimit, UsageRecord
from usage import services
from usage.models import FeatureUsagePolicy, UsageCounter

PASSWORD = 'Secur3-ResRef!Passphrase'


def set_limit(feature, tier, period, limit, active=True):
    UsageLimit.objects.update_or_create(
        feature_code=feature, tier=tier, period=period, defaults={'limit': limit, 'is_active': active},
    )


class UsageTestCase(TestCase):
    def setUp(self):
        cache.clear()
        # Isolate from the seeded launch allowances.
        UsageLimit.objects.all().update(is_active=False)

    def make_user(self, name, tier='free', **extra):
        user = User.objects.create_user(name, f'{name}@example.com', PASSWORD, **extra)
        if tier != 'free':
            user.membership_profile.tier = tier
            user.membership_profile.save(update_fields=['tier', 'updated_at'])
        return user

    def consume(self, feature='journal_finder', **extra):
        return self.client.post(f'/api/usage/{feature}/consume/', data='{}', content_type='application/json', **extra)


class LaunchDefaultsTests(UsageTestCase):
    def test_launch_policies_are_seeded_generous(self):
        for code in ('reference_generator', 'journal_finder', 'sample_size_calculator', 'research_analyzer'):
            policy = FeatureUsagePolicy.objects.get(feature_code=code)
            self.assertTrue(policy.limits_enabled)
            self.assertFalse(policy.meter_anonymous)
            self.assertTrue(policy.admin_bypass)

    def test_anonymous_use_is_not_counted_by_default(self):
        for _ in range(3):
            self.assertEqual(self.consume().status_code, 200)
        self.assertFalse(UsageCounter.objects.exists())
        usage = self.client.get('/api/usage/journal_finder/').json()['usage']
        self.assertEqual(usage['plan'], 'anonymous')
        self.assertTrue(usage['unlimited'])
        self.assertFalse(usage['counted'])


class DailyLimitTests(UsageTestCase):
    def test_free_daily_limit_blocks_with_clear_429(self):
        set_limit('journal_finder', 'free', 'day', 2)
        user = self.make_user('daily-free')
        self.client.force_login(user)
        codes = [self.consume().status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])
        blocked = self.consume()
        body = blocked.json()
        self.assertEqual(body['code'], 'usage_limit')
        self.assertEqual(body['limit'], 2)
        self.assertEqual(body['remaining'], 0)
        self.assertEqual(body['period'], 'day')
        self.assertTrue(body['reset_at'])
        self.assertIn('resets', body['error'])
        self.assertGreater(int(blocked['Retry-After']), 0)
        self.assertEqual(UsageRecord.objects.filter(user=user, feature_code='journal_finder').count(), 2)

        usage = self.client.get('/api/usage/journal_finder/').json()['usage']
        self.assertEqual((usage['used_today'], usage['limit'], usage['remaining']), (2, 2, 0))

    def test_signing_out_and_in_again_does_not_reset_the_counter(self):
        set_limit('journal_finder', 'free', 'day', 1)
        user = self.make_user('refresh-free')
        self.client.force_login(user)
        self.assertEqual(self.consume().status_code, 200)
        self.client.logout()
        self.client.force_login(user)
        self.assertEqual(self.consume().status_code, 429)

    def test_counter_never_exceeds_limit_even_if_already_full(self):
        set_limit('journal_finder', 'free', 'day', 3)
        user = self.make_user('full-free')
        start, _ = services.window('day')
        UsageCounter.objects.create(subject=f'user:{user.pk}', feature_code='journal_finder', period='day', period_start=start, count=3)
        self.client.force_login(user)
        self.assertEqual(self.consume().status_code, 429)
        self.assertEqual(UsageCounter.objects.get(subject=f'user:{user.pk}', period='day').count, 3)
        # Month and lifetime counters were rolled back with the refused request.
        self.assertFalse(UsageCounter.objects.filter(subject=f'user:{user.pk}', period='month', count__gt=0).exists())

    def test_yesterdays_usage_does_not_count_today(self):
        set_limit('journal_finder', 'free', 'day', 1)
        user = self.make_user('yesterday-free')
        start, _ = services.window('day')
        UsageCounter.objects.create(subject=f'user:{user.pk}', feature_code='journal_finder', period='day', period_start=start - timedelta(days=1), count=1)
        self.client.force_login(user)
        self.assertEqual(self.consume().status_code, 200)

    def test_monthly_limit_applies_alongside_daily(self):
        set_limit('sample_size_calculator', 'free', 'day', 10)
        set_limit('sample_size_calculator', 'free', 'month', 1)
        self.client.force_login(self.make_user('monthly-free'))
        self.assertEqual(self.consume('sample_size_calculator').status_code, 200)
        blocked = self.consume('sample_size_calculator').json()
        self.assertEqual((blocked['period'], blocked['limit']), ('month', 1))

    def test_premium_uses_premium_allowance(self):
        set_limit('journal_finder', 'free', 'day', 1)
        set_limit('journal_finder', 'premium', 'day', 3)
        self.client.force_login(self.make_user('premium-user', tier='premium'))
        self.assertEqual([self.consume().status_code for _ in range(4)], [200, 200, 200, 429])


class SwitchAndBypassTests(UsageTestCase):
    def test_global_switch_off_means_unlimited_but_still_counted(self):
        set_limit('journal_finder', 'free', 'day', 1)
        FeatureUsagePolicy.objects.filter(feature_code='journal_finder').update(limits_enabled=False)
        user = self.make_user('switch-off')
        self.client.force_login(user)
        self.assertEqual([self.consume().status_code for _ in range(3)], [200, 200, 200])
        usage = self.client.get('/api/usage/journal_finder/').json()['usage']
        self.assertTrue(usage['unlimited'])
        self.assertEqual(usage['used_today'], 3)

    def test_admins_bypass_limits(self):
        set_limit('journal_finder', 'free', 'day', 1)
        admin = User.objects.create_superuser('usage-admin', 'usage-admin@example.com', PASSWORD)
        self.client.force_login(admin)
        self.assertEqual([self.consume().status_code for _ in range(3)], [200, 200, 200])
        self.assertEqual(self.client.get('/api/usage/').json()['plan'], 'admin')

    def test_admin_bypass_can_be_turned_off(self):
        set_limit('journal_finder', 'free', 'day', 1)
        set_limit('journal_finder', 'premium', 'day', 1)
        FeatureUsagePolicy.objects.filter(feature_code='journal_finder').update(admin_bypass=False)
        self.client.force_login(User.objects.create_superuser('strict-admin', 'strict-admin@example.com', PASSWORD))
        self.assertEqual([self.consume().status_code for _ in range(2)], [200, 429])

    def test_premium_only_feature_is_refused_server_side(self):
        FeatureEntitlement.objects.filter(code='journal_finder').update(free_enabled=False)
        self.assertEqual(self.consume().json()['code'], 'auth_required')
        self.client.force_login(self.make_user('not-premium'))
        response = self.consume()
        self.assertEqual((response.status_code, response.json()['code']), (403, 'premium_required'))
        self.client.force_login(self.make_user('is-premium', tier='premium'))
        self.assertEqual(self.consume().status_code, 200)

    def test_only_browser_tools_can_be_consumed_from_the_client(self):
        self.assertEqual(self.consume('reference_generator').status_code, 404)
        self.assertEqual(self.consume('research_analyzer').status_code, 404)
        self.assertEqual(self.client.get('/api/usage/unknown_feature/').status_code, 404)


class AnonymousMeteringTests(UsageTestCase):
    def setUp(self):
        super().setUp()
        FeatureUsagePolicy.objects.filter(feature_code='journal_finder').update(meter_anonymous=True, anonymous_daily_limit=1)

    def test_anonymous_limit_is_per_ip_and_hashed(self):
        self.assertEqual(self.consume(REMOTE_ADDR='203.0.113.5').status_code, 200)
        self.assertEqual(self.consume(REMOTE_ADDR='203.0.113.5').status_code, 429)
        self.assertEqual(self.consume(REMOTE_ADDR='203.0.113.6').status_code, 200)
        self.assertFalse(UsageCounter.objects.filter(subject__contains='203.0.113').exists())

    def test_rotating_ipv6_inside_one_prefix_shares_the_allowance(self):
        self.assertEqual(self.consume(REMOTE_ADDR='2001:db8::1').status_code, 200)
        self.assertEqual(self.consume(REMOTE_ADDR='2001:db8::abcd').status_code, 429)

    def test_signed_in_user_is_not_charged_against_ip(self):
        self.assertEqual(self.consume(REMOTE_ADDR='198.51.100.1').status_code, 200)
        self.client.force_login(self.make_user('after-anon'))
        self.assertEqual(self.consume(REMOTE_ADDR='198.51.100.1').status_code, 200)


class EndpointIntegrationTests(UsageTestCase):
    @patch('blog.api_views.search_references', return_value=[{'title': 'A study', 'authors': [], 'year': '2026'}])
    def test_reference_lookup_refuses_before_calling_external_search(self, search):
        set_limit('reference_generator', 'free', 'day', 1)
        self.client.force_login(self.make_user('ref-precheck'))
        first = self.client.get('/api/references/fetch/', {'q': '10.1000/xyz'})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()['usage']['remaining'], 0)
        blocked = self.client.get('/api/references/fetch/', {'q': '10.1000/xyz'})
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json()['limit'], 1)
        self.assertEqual(search.call_count, 1)

    @patch('blog.api_views.search_references', return_value=[{'title': 'A study', 'authors': [], 'year': '2026'}])
    def test_anonymous_reference_lookups_can_be_metered_by_ip(self, _search):
        FeatureUsagePolicy.objects.filter(feature_code='reference_generator').update(meter_anonymous=True, anonymous_daily_limit=2)
        codes = [self.client.get('/api/references/fetch/', {'q': '10.1000/xyz'}).status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])

    def test_legacy_helpers_delegate_to_the_engine(self):
        user = self.make_user('legacy-helper')
        set_limit('advanced_search', 'free', 'day', 1)
        self.assertTrue(consume_usage(user, 'advanced_search')[0])
        self.assertFalse(consume_usage(user, 'advanced_search')[0])
        set_limit('journal_finder', 'free', 'day', 1)
        self.assertEqual(meter_action(user, 'journal_finder', 'journal_match')[0], True)
        self.assertEqual(meter_action(user, 'journal_finder', 'journal_match')[0], False)
        # Unmetered actions (saving, exporting) never count.
        self.assertEqual(meter_action(user, 'journal_finder', 'save_workspace')[0], True)
        # The older accounts endpoint shares the same counter.
        self.client.force_login(user)
        response = self.client.post('/api/accounts/tool-usage/journal-finder/', data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 429)

    def test_reset_time_is_next_midnight(self):
        start, reset = services.window('day')
        self.assertEqual(reset.date(), start + timedelta(days=1))
        self.assertGreater(reset, timezone.now())


class DashboardPolicyApiTests(UsageTestCase):
    def test_requires_settings_permission(self):
        self.assertEqual(self.client.get('/api/usage/admin/policies/').status_code, 401)
        self.client.force_login(self.make_user('plain-member'))
        self.assertEqual(self.client.get('/api/usage/admin/policies/').status_code, 403)

    def test_admin_can_list_and_save_policies(self):
        self.client.force_login(User.objects.create_superuser('policy-admin', 'policy-admin@example.com', PASSWORD))
        listing = self.client.get('/api/usage/admin/policies/').json()
        codes = {row['feature_code'] for row in listing['results']}
        self.assertTrue({'journal_finder', 'reference_generator', 'research_analyzer', 'sample_size_calculator'} <= codes)

        response = self.client.post(
            '/api/usage/admin/policies/journal_finder/save/',
            data=json.dumps({'limits_enabled': False, 'meter_anonymous': True, 'anonymous_daily_limit': '5', 'display_mode': 'always'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        policy = FeatureUsagePolicy.objects.get(feature_code='journal_finder')
        self.assertEqual((policy.limits_enabled, policy.meter_anonymous, policy.anonymous_daily_limit, policy.display_mode), (False, True, 5, 'always'))

        response = self.client.post(
            '/api/usage/admin/policies/journal_finder/save/',
            data=json.dumps({'anonymous_daily_limit': ''}), content_type='application/json',
        )
        self.assertIsNone(response.json()['policy']['anonymous_daily_limit'])
        bad = self.client.post(
            '/api/usage/admin/policies/journal_finder/save/',
            data=json.dumps({'anonymous_daily_limit': -3}), content_type='application/json',
        )
        self.assertEqual(bad.status_code, 400)
        bad_mode = self.client.post(
            '/api/usage/admin/policies/journal_finder/save/',
            data=json.dumps({'display_mode': 'sometimes'}), content_type='application/json',
        )
        self.assertEqual(bad_mode.status_code, 400)
        unknown = self.client.post('/api/usage/admin/policies/not_a_feature/save/', data='{}', content_type='application/json')
        self.assertEqual(unknown.status_code, 404)
