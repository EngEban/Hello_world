from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from accounts.entitlements import get_profile
from accounts.models import AccountRole
from dashboard.models import DashboardActivityLog


class AdminPagesDataTests(TestCase):
    """Data behind the redesigned Users, Reports and Notifications pages."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser('pages-admin', email='pages-admin@example.com', password='test-only-password')
        self.client.force_login(self.admin)
        self.premium = User.objects.create_user('premium-member', email='premium@example.com', password='test-only-password')
        profile = get_profile(self.premium)
        profile.tier = 'premium'
        profile.display_name = 'Dr Premium Reader'
        profile.save()
        self.staff = User.objects.create_user('staff-editor', email='staff@example.com', password='test-only-password', is_staff=True)
        User.objects.create_user('old-account', email='old@example.com', password='test-only-password', is_active=False)
        # Superusers may get a premium profile automatically, so count rather than assume.
        self.premium_total = User.objects.filter(membership_profile__tier='premium').count()
        DashboardActivityLog.objects.create(action='update', module='settings', message='Updated settings')
        DashboardActivityLog.objects.create(action='export', module='reports', message='Exported posts')
        DashboardActivityLog.objects.create(action='export', module='reports', message='Exported users')

    def test_user_list_has_directory_summary_independent_of_filters(self):
        data = self.client.get('/api/dashboard/users/?status=inactive').json()
        self.assertEqual(data['pagination']['total_items'], 1)
        summary = data['summary']
        self.assertEqual(summary['total'], 4)
        self.assertEqual(summary['active'], 3)
        self.assertEqual(summary['inactive'], 1)
        self.assertEqual(summary['dashboard_access'], 2)  # superuser + active staff
        self.assertEqual(summary['premium'], self.premium_total)
        self.assertEqual(summary['admins'], 1)
        self.assertEqual(summary['joined_30_days'], 4)

    def test_user_search_matches_display_name(self):
        data = self.client.get('/api/dashboard/users/?q=Premium%20Reader').json()
        self.assertEqual([row['email'] for row in data['results']], ['premium@example.com'])

    def test_reports_include_trends_activity_and_export_permissions(self):
        data = self.client.get('/api/dashboard/reports/').json()
        self.assertEqual(len(data['signups_trend']), 12)
        self.assertEqual(sum(item['count'] for item in data['signups_trend'][-5:]), 4)
        self.assertEqual(data['activity_30_days'], 3)
        self.assertEqual(data['activity_by_module'][0], {'module': 'reports', 'count': 2})
        tiers = {row['membership_profile__tier']: row['count'] for row in data['users_by_tier']}
        self.assertEqual(tiers.get('premium'), self.premium_total)
        exports = {row['module']: row for row in data['exports']}
        self.assertEqual(set(exports), set(data['export_modules']))
        self.assertTrue(all(row['allowed'] for row in exports.values()))
        self.assertEqual(exports['users']['permission'], 'users.view')

    def test_export_permissions_reflect_a_limited_role(self):
        viewer = User.objects.create_user('report-viewer', email='viewer@example.com', password='test-only-password', is_staff=True)
        viewer.membership_profile.account_role = AccountRole.objects.get(code='manager')
        viewer.membership_profile.save(update_fields=['account_role', 'updated_at'])
        cache.clear()
        self.client.force_login(viewer)
        data = self.client.get('/api/dashboard/reports/').json()
        exports = {row['module']: row for row in data['exports']}
        # Managers may export content and users but not settings.
        self.assertTrue(exports['posts']['allowed'])
        self.assertFalse(exports['settings']['allowed'])
        self.assertEqual(self.client.get('/api/dashboard/export/settings/?format=csv').status_code, 403)

    def test_notifications_list_reports_audience_reach(self):
        counts = self.client.get('/api/dashboard/notifications/').json()['audience_counts']
        self.assertEqual(counts['all'], 3)
        self.assertEqual(counts['premium'], self.premium_total)
        self.assertEqual(counts['staff'], 2)
        self.assertEqual(counts['admins'], 1)
        self.assertNotIn('selected', counts)
