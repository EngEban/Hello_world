import csv
import json
import tempfile
from datetime import timedelta
from io import BytesIO, StringIO

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from accounts.entitlements import ensure_default_entitlements
from accounts.models import AccountNotification, AccountRole, FeatureEntitlement, SubscriptionPlan, UsageLimit
from dashboard.api.media import unsafe_upload_filename
from blog.models import Author, Category, MediaAsset, Post
from dashboard.models import ContactSubmission, DashboardActivityLog, FAQCategory, FAQItem, JoinTeamEntry, NewsletterCampaign, NewsletterSubscriber, ResearchOpportunity, TeamMember


class DashboardApiPermissionTests(TestCase):
    password = 'Secur3-ResRef!Passphrase'

    def setUp(self):
        cache.clear()

    def test_dashboard_endpoints_require_authenticated_staff_access(self):
        response = self.client.get('/api/dashboard/stats/')
        self.assertEqual(response.status_code, 401)

        user = User.objects.create_user(
            username='member@example.com',
            email='member@example.com',
            password=self.password,
            is_staff=True,
        )
        self.client.force_login(user)
        response = self.client.get('/api/dashboard/stats/')
        self.assertEqual(response.status_code, 403)

        user.membership_profile.access_role = 'editor'
        user.membership_profile.save(update_fields=['access_role', 'updated_at'])
        response = self.client.get('/api/dashboard/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('stats', response.json())

    def test_dashboard_access_can_use_account_role(self):
        role, _ = AccountRole.objects.get_or_create(
            code='editor',
            defaults={
                'label': 'Dashboard Editor',
                'can_access_dashboard': True,
            },
        )
        role.can_access_dashboard = True
        role.save(update_fields=['can_access_dashboard'])
        user = User.objects.create_user(
            username='role-editor@example.com',
            email='role-editor@example.com',
            password=self.password,
            is_staff=False,
        )
        user.membership_profile.account_role = role
        user.membership_profile.save(update_fields=['account_role', 'updated_at'])

        self.client.force_login(user)
        response = self.client.get('/api/dashboard/stats/')
        self.assertEqual(response.status_code, 200)

    def test_dashboard_login_is_rate_limited(self):
        payload = {'username': 'missing@example.com', 'password': 'wrong-password'}
        for _ in range(8):
            response = self.client.post(
                '/api/dashboard/auth/login/',
                data=json.dumps(payload),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 401)  # wrong credentials (T-14)

        response = self.client.post(
            '/api/dashboard/auth/login/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 429)

    def test_dashboard_login_accepts_mobile_capitalized_username(self):
        user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password=self.password,
        )
        response = self.client.post(
            '/api/dashboard/auth/login/',
            data=json.dumps({'username': 'Admin', 'password': self.password}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user']['id'], user.id)

    def test_admin_can_send_account_specific_notifications_and_view_history(self):
        admin = User.objects.create_superuser('notify-admin', 'notify-admin@example.com', self.password)
        member = User.objects.create_user('notify-member', 'notify-member@example.com', self.password)
        User.objects.create_user('inactive-member', 'inactive@example.com', self.password, is_active=False)
        self.client.force_login(admin)

        response = self.client.post(
            '/api/dashboard/notifications/send/',
            data=json.dumps({
                'audience': 'selected',
                'user_ids': [member.id],
                'title': 'New platform update',
                'message': 'A research tool has been improved.',
                'notification_type': 'announcement',
                'action_url': '/tools',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['recipient_count'], 1)
        notification = AccountNotification.objects.get(user=member)
        self.assertEqual(notification.title, 'New platform update')
        self.assertTrue(notification.metadata.get('campaign_id'))
        self.assertEqual(AccountNotification.objects.filter(user=admin).count(), 0)

        history = self.client.get('/api/dashboard/notifications/')
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()['results'][0]['recipient_count'], 1)

    def test_publishing_an_opportunity_creates_one_deduplicated_broadcast(self):
        admin = User.objects.create_superuser('opportunity-admin', 'opportunity-admin@example.com', self.password)
        member = User.objects.create_user('opportunity-member', 'opportunity-member@example.com', self.password)
        self.client.force_login(admin)
        response = self.client.post(
            '/api/dashboard/opportunities/save/',
            data=json.dumps({
                'title': 'Clinical Research Fellow',
                'slug': 'clinical-research-fellow',
                'status': 'published',
                'opportunity_type': 'position',
                'priority': 'normal',
                'application_url': 'https://example.com/apply',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        notification = AccountNotification.objects.get(user=None, notification_type='opportunity')
        self.assertIn('Clinical Research Fellow', notification.message)
        self.assertEqual(notification.metadata['event'], 'opportunity_published')
        self.assertFalse(AccountNotification.objects.filter(user=member).exists())

        # Unpublish + publish again must not notify twice.
        opportunity_id = response.json()['opportunity']['id']
        for status in ('draft', 'published'):
            self.client.post(f'/api/dashboard/opportunities/{opportunity_id}/status/', data=json.dumps({'status': status}), content_type='application/json')
        self.assertEqual(AccountNotification.objects.filter(notification_type='opportunity').count(), 1)

        # The member sees it as unread, marks it read, and that state is theirs only.
        self.client.force_login(member)
        listing = self.client.get('/api/accounts/notifications/').json()
        self.assertEqual(listing['unread_count'], 1)
        self.assertFalse(listing['results'][0]['is_read'])
        self.client.post(f'/api/accounts/notifications/{notification.id}/read/')
        listing = self.client.get('/api/accounts/notifications/').json()
        self.assertEqual(listing['unread_count'], 0)
        self.assertTrue(listing['results'][0]['is_read'])
        self.client.force_login(admin)
        self.assertEqual(self.client.get('/api/accounts/notifications/').json()['unread_count'], 1)

    def test_publishing_opportunity_generates_slug_when_editor_leaves_it_blank(self):
        admin = User.objects.create_superuser('opportunity-slug-admin', 'opportunity-slug-admin@example.com', self.password)
        self.client.force_login(admin)

        response = self.client.post(
            '/api/dashboard/opportunities/save/',
            data=json.dumps({
                'title': 'Community Research Coordinator',
                'slug': '',
                'status': 'published',
                'opportunity_type': 'position',
                'priority': 'normal',
                'contact_email': 'opportunities@example.com',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['opportunity']['slug'], 'community-research-coordinator')

    def test_opportunity_publishing_is_flexible_and_keeps_configured_custom_fields(self):
        admin = User.objects.create_superuser('opportunity-fields-admin', 'opportunity-fields-admin@example.com', self.password)
        self.client.force_login(admin)

        response = self.client.post(
            '/api/dashboard/opportunities/save/',
            data=json.dumps({
                'title': 'Flexible Research Collaboration',
                'status': 'published',
                'opportunity_type': 'collaboration',
                'priority': 'normal',
                'custom_fields': [
                    {'label': 'Study phase', 'type': 'select', 'value': 'Recruiting', 'options': ['Planning', 'Recruiting'], 'is_public': True},
                    {'label': 'Internal reviewer', 'type': 'text', 'value': 'Editorial team', 'is_public': False},
                ],
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        opportunity = response.json()['opportunity']
        self.assertEqual(opportunity['status'], 'published')
        self.assertEqual(opportunity['custom_fields'][0]['label'], 'Study phase')
        self.assertFalse(opportunity['custom_fields'][1]['is_public'])

    @override_settings(NEWSLETTER_ENABLED=True)
    def test_public_newsletter_subscription_does_not_reactivate_paused_subscriber(self):
        response = self.client.post(
            '/api/newsletter/subscribe/',
            data=json.dumps({'email': 'NewSubscriber@Example.COM'}),
            content_type='application/json',
        )

        # Double opt-in: the address is stored but stays inactive until confirmed.
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()['success'])
        subscriber = NewsletterSubscriber.objects.get(email='newsubscriber@example.com')
        self.assertFalse(subscriber.is_active)

        subscriber.is_active = False
        subscriber.confirmed_at = timezone.now()
        subscriber.save(update_fields=['is_active', 'confirmed_at'])

        response = self.client.post(
            '/api/newsletter/subscribe/',
            data=json.dumps({'email': 'newsubscriber@example.com'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 202)
        subscriber.refresh_from_db()
        self.assertFalse(subscriber.is_active)
        self.assertNotIn('paused', response.json()['message'].lower())  # neutral (S-16)
        self.assertEqual(NewsletterSubscriber.objects.filter(email='newsubscriber@example.com').count(), 1)

        response = self.client.post(
            '/api/newsletter/subscribe/',
            data=json.dumps({'email': 'not-an-email'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_viewer_dashboard_hides_activity_and_sensitive_team_fields(self):
        role, _ = AccountRole.objects.update_or_create(
            code='viewer',
            defaults={'label': 'Dashboard Viewer', 'can_access_dashboard': True},
        )
        user = User.objects.create_user(
            username='viewer@example.com',
            email='viewer@example.com',
            password=self.password,
        )
        user.membership_profile.account_role = role
        user.membership_profile.save(update_fields=['account_role', 'updated_at'])
        DashboardActivityLog.objects.create(
            actor=user,
            action='update',
            module='users',
            message='Changed a sensitive account setting.',
        )
        self.client.force_login(user)

        bootstrap = self.client.get('/api/dashboard/bootstrap/')
        stats = self.client.get('/api/dashboard/stats/')
        activity = self.client.get('/api/dashboard/activity/')
        team = self.client.get('/api/dashboard/team/')

        self.assertEqual(bootstrap.status_code, 200)
        self.assertEqual(bootstrap.json()['recent_activity'], [])
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.json()['recent_activity'], [])
        self.assertEqual(activity.status_code, 403)
        self.assertEqual(team.status_code, 200)
        team_member = team.json()['results'][0]
        self.assertNotIn('permissions', team_member)
        self.assertNotIn('features', team_member)
        self.assertNotIn('auth_provider', team_member)
        self.assertNotIn('configured_tier', team_member)

    def test_author_editor_rejects_unsafe_external_urls(self):
        user = User.objects.create_user(
            username='author-admin@example.com',
            email='author-admin@example.com',
            password=self.password,
            is_staff=True,
        )
        user.membership_profile.access_role = 'admin'
        user.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(user)

        response = self.client.post(
            '/api/dashboard/authors/save/',
            data=json.dumps({
                'login': 'unsafe-author',
                'display_name': 'Unsafe Author',
                'website': 'javascript:alert(1)',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Author.objects.filter(login='unsafe-author').exists())

    @override_settings(NEWSLETTER_ENABLED=True)
    def test_dashboard_newsletter_management_filters_updates_and_deletes(self):
        active = NewsletterSubscriber.objects.create(email='active@example.com', is_active=True, confirmed_at=timezone.now())
        paused = NewsletterSubscriber.objects.create(email='paused@example.com', is_active=False)
        user = User.objects.create_user(
            username='newsletter-admin@example.com',
            email='newsletter-admin@example.com',
            password=self.password,
            is_staff=True,
        )
        user.membership_profile.access_role = 'admin'
        user.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(user)

        response = self.client.get('/api/dashboard/newsletter/?status=active&q=active')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['summary']['total'], 2)
        self.assertEqual([item['email'] for item in payload['results']], ['active@example.com'])

        response = self.client.post(
            f'/api/dashboard/newsletter/{active.id}/update/',
            data=json.dumps({'is_active': False}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['subscriber']['is_active'])
        active.refresh_from_db()
        self.assertFalse(active.is_active)

        response = self.client.post(f'/api/dashboard/newsletter/{paused.id}/delete/')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(NewsletterSubscriber.objects.filter(id=paused.id).exists())

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='ResRef <no-reply@resref.com>',
        NEWSLETTER_MAX_RECIPIENTS_PER_SEND=10,
    )
    @override_settings(NEWSLETTER_ENABLED=True)
    def test_admin_can_send_newsletter_once_to_active_subscribers(self):
        NewsletterSubscriber.objects.create(email='active-one@example.com', is_active=True, confirmed_at=timezone.now())
        NewsletterSubscriber.objects.create(email='active-two@example.com', is_active=True, confirmed_at=timezone.now())
        NewsletterSubscriber.objects.create(email='paused@example.com', is_active=False, confirmed_at=timezone.now())
        NewsletterSubscriber.objects.create(email='unconfirmed@example.com', is_active=True)
        user = User.objects.create_user(
            username='newsletter-sender@example.com',
            email='newsletter-sender@example.com',
            password=self.password,
            is_staff=True,
        )
        user.membership_profile.access_role = 'admin'
        user.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(user)

        payload = {
            'subject': 'Weekly ResRef research update',
            'message': 'This is a plain text newsletter body for active ResRef subscribers.',
            'confirm_phrase': 'SEND NEWSLETTER',
            'idempotency_key': 'newsletter-test-key-1',
        }
        response = self.client.post(
            '/api/dashboard/newsletter/send/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        # The request only queues the campaign; nothing is sent inline.
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(response.json()['campaign']['status'], 'queued')
        self.assertEqual(response.json()['campaign']['pending_count'], 2)
        call_command('process_outbox', stdout=StringIO())
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual({message.to[0] for message in mail.outbox}, {'active-one@example.com', 'active-two@example.com'})
        self.assertNotIn('paused@example.com', {message.to[0] for message in mail.outbox})
        self.assertTrue(all(len(message.to) == 1 for message in mail.outbox))
        campaign = NewsletterCampaign.objects.get(idempotency_key='newsletter-test-key-1')
        self.assertEqual(campaign.status, 'sent')
        self.assertEqual(campaign.recipient_count, 2)
        self.assertEqual(campaign.failed_count, 0)

        response = self.client.post(
            '/api/dashboard/newsletter/send/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['duplicate'])
        call_command('process_outbox', stdout=StringIO())
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        NEWSLETTER_MAX_RECIPIENTS_PER_SEND=10,
    )
    @override_settings(NEWSLETTER_ENABLED=True)
    def test_newsletter_send_requires_admin_and_confirmation(self):
        NewsletterSubscriber.objects.create(email='active@example.com', is_active=True, confirmed_at=timezone.now())
        editor = User.objects.create_user(
            username='newsletter-editor@example.com',
            email='newsletter-editor@example.com',
            password=self.password,
            is_staff=True,
        )
        editor.membership_profile.access_role = 'editor'
        editor.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(editor)
        payload = {
            'subject': 'Weekly ResRef research update',
            'message': 'This is a plain text newsletter body for active ResRef subscribers.',
            'confirm_phrase': 'SEND NEWSLETTER',
            'idempotency_key': 'newsletter-test-key-2',
        }

        response = self.client.post(
            '/api/dashboard/newsletter/send/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

        admin = User.objects.create_user(
            username='newsletter-admin-confirm@example.com',
            email='newsletter-admin-confirm@example.com',
            password=self.password,
            is_staff=True,
        )
        admin.membership_profile.access_role = 'admin'
        admin.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(admin)
        payload['confirm_phrase'] = 'send newsletter'
        response = self.client.post(
            '/api/dashboard/newsletter/send/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(NewsletterCampaign.objects.filter(idempotency_key='newsletter-test-key-2').exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_admin_cannot_assign_super_admin_role(self):
        admin = User.objects.create_user(
            username='dashboard-admin@example.com',
            email='dashboard-admin@example.com',
            password=self.password,
            is_staff=True,
        )
        admin.membership_profile.access_role = 'admin'
        admin.membership_profile.save(update_fields=['access_role', 'updated_at'])
        target = User.objects.create_user(
            username='target@example.com',
            email='target@example.com',
            password=self.password,
        )
        AccountRole.objects.update_or_create(
            code='super_admin',
            defaults={
                'label': 'Super Admin',
                'can_access_dashboard': True,
                'is_super_admin': True,
                'is_active': True,
            },
        )

        self.client.force_login(admin)
        response = self.client.post(
            f'/api/dashboard/users/{target.id}/save/',
            data=json.dumps({
                'email': target.email,
                'username': target.username,
                'is_active': True,
                'is_staff': True,
                'access_role': 'admin',
                'account_role': 'super_admin',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        target.membership_profile.refresh_from_db()
        self.assertNotEqual(target.membership_profile.account_role.code if target.membership_profile.account_role_id else '', 'super_admin')

    def _dashboard_admin(self, email='plain-admin@example.com'):
        admin = User.objects.create_user(username=email, email=email, password=self.password, is_staff=True)
        admin.membership_profile.access_role = 'admin'
        admin.membership_profile.save(update_fields=['access_role', 'updated_at'])
        return admin

    def _super_admin_role(self):
        role, _ = AccountRole.objects.update_or_create(
            code='super_admin',
            defaults={'label': 'Super Admin', 'can_access_dashboard': True, 'is_super_admin': True, 'is_active': True},
        )
        return role

    def test_rejected_user_save_does_not_persist_any_change(self):
        admin = self._dashboard_admin()
        self._super_admin_role()
        target = User.objects.create_user('rollback@example.com', 'rollback@example.com', self.password)
        self.client.force_login(admin)

        response = self.client.post(
            f'/api/dashboard/users/{target.id}/save/',
            data=json.dumps({
                'email': target.email,
                'username': target.username,
                'first_name': 'CHANGED',
                'is_staff': True,
                'account_role': 'super_admin',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        target.refresh_from_db()
        self.assertEqual(target.first_name, '')
        self.assertFalse(target.is_staff)

    def test_admin_cannot_take_over_super_admin_role_account(self):
        admin = self._dashboard_admin()
        role = self._super_admin_role()
        owner = User.objects.create_user('owner@example.com', 'owner@example.com', self.password, is_staff=True)
        owner.membership_profile.account_role = role
        owner.membership_profile.save(update_fields=['account_role', 'updated_at'])
        self.client.force_login(admin)

        for payload in (
            {'email': 'attacker@example.com', 'username': owner.username},
            {'email': owner.email, 'username': owner.username, 'password': 'Brand-New-Passphrase-2026!'},
        ):
            response = self.client.post(
                f'/api/dashboard/users/{owner.id}/save/',
                data=json.dumps(payload),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 403)
        owner.refresh_from_db()
        self.assertEqual(owner.email, 'owner@example.com')
        self.assertTrue(owner.check_password(self.password))

    def test_admin_cannot_reset_password_of_another_admin(self):
        admin = self._dashboard_admin()
        other = self._dashboard_admin('other-admin@example.com')
        self.client.force_login(admin)
        response = self.client.post(
            f'/api/dashboard/users/{other.id}/save/',
            data=json.dumps({'email': other.email, 'username': other.username, 'password': 'Brand-New-Passphrase-2026!'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        other.refresh_from_db()
        self.assertTrue(other.check_password(self.password))

    def test_admin_can_rename_peer_when_full_object_is_sent_unchanged(self):
        admin = self._dashboard_admin()
        other = self._dashboard_admin('peer-admin@example.com')
        self.client.force_login(admin)
        listing = self.client.get('/api/dashboard/users/?q=peer-admin').json()
        payload = next(item for item in listing['results'] if item['id'] == other.id)
        payload['first_name'] = 'Renamed'
        response = self.client.post(f'/api/dashboard/users/{other.id}/save/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        other.refresh_from_db()
        self.assertEqual(other.first_name, 'Renamed')

    def test_saving_a_name_keeps_plan_and_role(self):
        admin = User.objects.create_superuser('plan-admin', 'plan-admin@example.com', self.password)
        target = User.objects.create_user('plan-target@example.com', 'plan-target@example.com', self.password)
        plan = SubscriptionPlan.objects.create(code='premium_monthly_test', label='Premium monthly', tier='premium')
        target.membership_profile.plan = plan
        target.membership_profile.tier = 'premium'
        target.membership_profile.save(update_fields=['plan', 'tier', 'updated_at'])
        self.client.force_login(admin)
        response = self.client.post(
            f'/api/dashboard/users/{target.id}/save/',
            data=json.dumps({'email': target.email, 'username': target.username, 'first_name': 'Sara'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        target.membership_profile.refresh_from_db()
        self.assertEqual(target.membership_profile.plan_id, plan.id)

    def test_admin_cannot_grant_staff_and_rejection_is_audited(self):
        admin = User.objects.create_user('staff-attacker', 'staff-attacker@example.com', self.password, is_staff=True)
        admin.membership_profile.access_role = 'admin'
        admin.membership_profile.save(update_fields=['access_role', 'updated_at'])
        target = User.objects.create_user('premium-target', 'premium-target@example.com', self.password)

        self.client.force_login(admin)
        response = self.client.post(
            f'/api/dashboard/users/{target.id}/save/',
            data=json.dumps({'email': target.email, 'username': target.username, 'is_staff': True}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        target.refresh_from_db()
        self.assertFalse(target.is_staff)
        log = DashboardActivityLog.objects.filter(actor=admin, module='users', action='system').latest('id')
        self.assertIn('is_staff', log.metadata['rejected_fields'])

    def test_admin_cannot_demote_super_admin_when_role_is_omitted(self):
        ensure_default_entitlements()
        admin = User.objects.create_user('demotion-attacker', 'demotion-attacker@example.com', self.password, is_staff=True)
        admin.membership_profile.access_role = 'admin'
        admin.membership_profile.save(update_fields=['access_role', 'updated_at'])
        victim = User.objects.create_user('role-victim', 'role-victim@example.com', self.password)
        victim.membership_profile.account_role = AccountRole.objects.get(code='super_admin')
        victim.membership_profile.access_role = 'admin'
        victim.membership_profile.save(update_fields=['account_role', 'access_role', 'updated_at'])

        self.client.force_login(admin)
        response = self.client.post(
            f'/api/dashboard/users/{victim.id}/save/',
            data=json.dumps({'email': victim.email, 'username': victim.username, 'display_name': 'Attempted Demotion'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        victim.membership_profile.refresh_from_db()
        self.assertEqual(victim.membership_profile.account_role.code, 'super_admin')

    def test_admin_cannot_change_billing_entitlements(self):
        admin = User.objects.create_user('billing-attacker', 'billing-attacker@example.com', self.password, is_staff=True)
        admin.membership_profile.access_role = 'admin'
        admin.membership_profile.save(update_fields=['access_role', 'updated_at'])
        target = User.objects.create_user('billing-target', 'billing-target@example.com', self.password)
        target.membership_profile.access_role = 'editor'
        target.membership_profile.save(update_fields=['access_role', 'updated_at'])

        self.client.force_login(admin)
        response = self.client.post(
            f'/api/dashboard/users/{target.id}/save/',
            data=json.dumps({
                'email': target.email,
                'username': target.username,
                'premium_until': (timezone.now() + timedelta(days=30)).date().isoformat(),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        target.membership_profile.refresh_from_db()
        self.assertIsNone(target.membership_profile.premium_until)

    def test_admin_cannot_promote_a_team_member_to_admin(self):
        admin = User.objects.create_user('team-attacker', 'team-attacker@example.com', self.password, is_staff=True)
        admin.membership_profile.access_role = 'admin'
        admin.membership_profile.save(update_fields=['access_role', 'updated_at'])
        target = User.objects.create_user('team-target', 'team-target@example.com', self.password, is_staff=True)
        team_member = TeamMember.objects.create(user=target, role='viewer', is_active=True)

        self.client.force_login(admin)
        response = self.client.post(
            f'/api/dashboard/users/{target.id}/save/',
            data=json.dumps({'email': target.email, 'username': target.username, 'team_role': 'admin'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        team_member.refresh_from_db()
        self.assertEqual(team_member.role, 'viewer')

    def test_department_update_does_not_reactivate_an_inactive_team_member(self):
        admin = User.objects.create_user('reactivation-attacker', 'reactivation-attacker@example.com', self.password, is_staff=True)
        admin.membership_profile.access_role = 'admin'
        admin.membership_profile.save(update_fields=['access_role', 'updated_at'])
        target = User.objects.create_user('inactive-team-target', 'inactive-team-target@example.com', self.password, is_staff=True)
        team_member = TeamMember.objects.create(user=target, role='admin', is_active=False)

        self.client.force_login(admin)
        response = self.client.post(
            f'/api/dashboard/users/{target.id}/save/',
            data=json.dumps({'email': target.email, 'username': target.username, 'department': 'Research'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        team_member.refresh_from_db()
        self.assertFalse(team_member.is_active)

    def test_super_admin_can_change_privileged_and_billing_fields(self):
        ensure_default_entitlements()
        super_admin = User.objects.create_superuser('real-super-admin', 'real-super-admin@example.com', self.password)
        target = User.objects.create_user('privileged-target', 'privileged-target@example.com', self.password)

        self.client.force_login(super_admin)
        response = self.client.post(
            f'/api/dashboard/users/{target.id}/save/',
            data=json.dumps({
                'email': target.email,
                'username': target.username,
                'is_staff': True,
                'access_role': 'admin',
                'tier': 'premium',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        target.refresh_from_db()
        target.membership_profile.refresh_from_db()
        self.assertTrue(target.is_staff)
        self.assertEqual(target.membership_profile.access_role, 'admin')
        self.assertEqual(target.membership_profile.tier, 'premium')

    def test_admin_can_create_a_normal_editor(self):
        ensure_default_entitlements()
        admin = User.objects.create_user('editor-creator', 'editor-creator@example.com', self.password, is_staff=True)
        admin.membership_profile.access_role = 'admin'
        admin.membership_profile.save(update_fields=['access_role', 'updated_at'])

        self.client.force_login(admin)
        response = self.client.post(
            '/api/dashboard/users/save/',
            data=json.dumps({
                'email': 'new-editor@example.com',
                'username': 'new-editor',
                'is_staff': True,
                'access_role': 'editor',
                'team_role': 'editor',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        created = User.objects.get(email='new-editor@example.com')
        self.assertTrue(created.is_staff)
        self.assertEqual(created.membership_profile.access_role, 'editor')

    def test_dashboard_user_editor_rejects_reused_passwords(self):
        admin = User.objects.create_superuser('password-admin', 'password-admin@example.com', self.password)
        target = User.objects.create_user('password-target', 'password-target@example.com', self.password)
        self.client.force_login(admin)

        response = self.client.post(
            f'/api/dashboard/users/{target.id}/save/',
            data=json.dumps({
                'email': target.email,
                'username': target.username,
                'password': self.password,
                'is_active': True,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Your new password must be different from your previous password.')

    def test_media_upload_rejects_fake_image_content(self):
        user = User.objects.create_user(
            username='media-admin@example.com',
            email='media-admin@example.com',
            password=self.password,
            is_staff=True,
        )
        user.membership_profile.access_role = 'admin'
        user.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(user)

        fake_image = SimpleUploadedFile('fake.png', b'not a real image', content_type='image/png')
        response = self.client.post(
            '/api/dashboard/media/save/',
            data={'title': 'Fake upload', 'file': fake_image},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(MediaAsset.objects.filter(title='Fake upload').exists())

    def test_dashboard_user_editor_enforces_password_length_ceiling(self):
        admin = User.objects.create_superuser('password-length-admin', 'password-length-admin@example.com', self.password)
        target = User.objects.create_user('password-length-target', 'password-length-target@example.com', self.password)
        self.client.force_login(admin)

        response = self.client.post(
            f'/api/dashboard/users/{target.id}/save/',
            data=json.dumps({
                'email': target.email,
                'username': target.username,
                'password': 'A1-' + ('x' * 297),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Password must be 256 characters or fewer.')

        accepted_password = 'A1-' + ('x' * 197)
        response = self.client.post(
            f'/api/dashboard/users/{target.id}/save/',
            data=json.dumps({
                'email': target.email,
                'username': target.username,
                'password': accepted_password,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        target.refresh_from_db()
        self.assertTrue(target.check_password(accepted_password))

    def test_media_upload_rejects_dangerous_extensions_and_filenames(self):
        user = User.objects.create_user(
            username='media-filename-admin@example.com',
            email='media-filename-admin@example.com',
            password=self.password,
            is_staff=True,
        )
        user.membership_profile.access_role = 'admin'
        user.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(user)

        image_bytes = BytesIO()
        Image.new('RGB', (8, 8), color='#0b328f').save(image_bytes, format='PNG')
        for filename in ('payload.html', 'payload.svg', 'payload.js'):
            response = self.client.post(
                '/api/dashboard/media/save/',
                data={'file': SimpleUploadedFile(filename, image_bytes.getvalue(), content_type='image/png')},
            )
            self.assertEqual(response.status_code, 400, filename)
        # Django normalizes uploaded names to a basename before this endpoint,
        # while the validator remains defensive for any direct caller.
        self.assertTrue(unsafe_upload_filename('../outside.png'))
        self.assertTrue(unsafe_upload_filename('bad\x00name.png'))
        self.assertEqual(MediaAsset.objects.count(), 0)

    def test_media_route_serves_images_with_safe_headers_in_production(self):
        user = User.objects.create_user(
            username='media-delivery-admin@example.com',
            email='media-delivery-admin@example.com',
            password=self.password,
            is_staff=True,
        )
        user.membership_profile.access_role = 'admin'
        user.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(user)

        image_bytes = BytesIO()
        Image.new('RGB', (8, 8), color='#0b328f').save(image_bytes, format='PNG')
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root, DEBUG=False):
            upload = self.client.post(
                '/api/dashboard/media/save/',
                data={'file': SimpleUploadedFile('delivery.png', image_bytes.getvalue(), content_type='not-trusted')},
            )
            self.assertEqual(upload.status_code, 200)
            asset = MediaAsset.objects.get(pk=upload.json()['media']['id'])

            response = self.client.get(asset.file.url)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/png')
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
            self.assertIn("default-src 'none'", response['Content-Security-Policy'])
            self.assertEqual(b''.join(response.streaming_content), image_bytes.getvalue())

    def test_dashboard_can_upload_a_valid_webp_and_publish_an_article_that_uses_it(self):
        user = User.objects.create_user(
            username='article-media-admin@example.com',
            email='article-media-admin@example.com',
            password=self.password,
            is_staff=True,
        )
        user.membership_profile.access_role = 'admin'
        user.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(user)

        image_bytes = BytesIO()
        Image.new('RGB', (48, 32), color='#0b328f').save(image_bytes, format='WEBP')
        image_file = SimpleUploadedFile('research-diagram.webp', image_bytes.getvalue(), content_type='image/webp')

        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            media_response = self.client.post(
                '/api/dashboard/media/save/',
                data={
                    'title': 'Research diagram',
                    'alt_text': 'Diagram showing the research process',
                    'caption': 'Research process diagram',
                    'file': image_file,
                },
            )
            self.assertEqual(media_response.status_code, 200)
            media = media_response.json()['media']
            self.assertTrue(media['url'])
            self.assertEqual(media['alt_text'], 'Diagram showing the research process')

            category = Category.objects.create(name='Publishing workflow', slug='publishing-workflow')
            post_response = self.client.post(
                '/api/dashboard/posts/save/',
                data=json.dumps({
                    'title': 'Publishing an article with a figure',
                    'slug': 'publishing-an-article-with-a-figure',
                    'content': f'<p>Article body.</p><figure><img src="{media["url"]}" alt="Research process diagram"><figcaption>Research process diagram</figcaption></figure>',
                    'excerpt': 'A published article with an accessible figure.',
                    'post_type': 'post',
                    'status': 'publish',
                    'featured_image': media['url'],
                    'categories': [category.id],
                }),
                content_type='application/json',
            )
            self.assertEqual(post_response.status_code, 200)

            public_response = self.client.get('/api/posts/publishing-an-article-with-a-figure/')
            self.assertEqual(public_response.status_code, 200)
            public_post = public_response.json()['post']
            self.assertIn(media['url'], public_post['content'])
            self.assertEqual(public_post['featured_image'], media['url'])

    def test_dashboard_post_pdf_upload_validates_pdf_signature(self):
        user = User.objects.create_user(
            username='pdf-admin@example.com',
            email='pdf-admin@example.com',
            password=self.password,
            is_staff=True,
        )
        user.membership_profile.access_role = 'admin'
        user.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(user)
        post = Post.objects.create(
            title='PDF Resource',
            slug='pdf-resource',
            content='<p>Research guide.</p>',
            status='publish',
            published_at=timezone.now(),
        )

        fake_pdf = SimpleUploadedFile('fake.pdf', b'not a real pdf', content_type='application/pdf')
        response = self.client.post(f'/api/dashboard/posts/{post.id}/pdf/', data={'file': fake_pdf})
        self.assertEqual(response.status_code, 400)
        post.refresh_from_db()
        self.assertFalse(post.pdf_file)

        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            valid_pdf = SimpleUploadedFile('guide.pdf', b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF', content_type='application/pdf')
            response = self.client.post(
                f'/api/dashboard/posts/{post.id}/pdf/',
                data={'file': valid_pdf, 'title': 'Downloadable Guide'},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()['post']
            self.assertEqual(payload['pdf_title'], 'Downloadable Guide')
            self.assertTrue(payload['pdf_url'])

    def test_dashboard_publish_existing_draft_sets_missing_publication_date(self):
        user = User.objects.create_user(
            username='publisher-admin@example.com',
            email='publisher-admin@example.com',
            password=self.password,
            is_staff=True,
        )
        user.membership_profile.access_role = 'admin'
        user.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(user)
        category = Category.objects.create(name='Publishing Test', slug='publishing-test')
        post = Post.objects.create(
            title='Hidden Draft Article',
            slug='hidden-draft-article',
            content='<p>Research content.</p>',
            post_type='post',
            status='draft',
            published_at=None,
        )
        post.categories.add(category)

        response = self.client.post(
            f'/api/dashboard/posts/{post.id}/save/',
            data=json.dumps({
                'title': post.title,
                'slug': post.slug,
                'content': post.content,
                'post_type': 'post',
                'status': 'publish',
                'published_at': '',
                'categories': [category.id],
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.status, 'publish')
        self.assertIsNotNone(post.published_at)
        public_response = self.client.get('/api/posts/?q=Hidden%20Draft%20Article')
        self.assertEqual(public_response.json()['pagination']['total_items'], 1)

    def test_public_api_health_is_available_without_authentication(self):
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

    @override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r'^api/health/$'])
    def test_healthcheck_stays_available_over_platform_private_http(self):
        response = self.client.get('/api/health/', secure=False)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

    @override_settings(
        RESREF_CSP_ENABLED=True,
        RESREF_CSP_REPORT_ONLY=True,
        RESREF_CONTENT_SECURITY_POLICY="default-src 'self'",
    )
    def test_security_headers_are_applied_to_api_responses(self):
        response = self.client.get('/api/health/')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['Cross-Origin-Opener-Policy'], 'same-origin')
        self.assertIn('Permissions-Policy', response)
        self.assertEqual(response['Content-Security-Policy-Report-Only'], "default-src 'self'")

    def test_default_csp_limits_connection_hosts(self):
        from resref.settings import DEFAULT_CONTENT_SECURITY_POLICY

        connect_src = next(
            directive.strip() for directive in DEFAULT_CONTENT_SECURITY_POLICY.split(';')
            if directive.strip().startswith('connect-src ')
        )
        self.assertNotIn('https:', connect_src.split())
        self.assertEqual(
            connect_src,
            "connect-src 'self' https://api.crossref.org https://api.openalex.org https://api.stripe.com https://accounts.google.com",
        )

    def test_admin_can_update_feature_entitlement_access(self):
        user = User.objects.create_user(
            username='admin@example.com',
            email='admin@example.com',
            password=self.password,
            is_staff=True,
        )
        user.membership_profile.access_role = 'admin'
        user.membership_profile.save(update_fields=['access_role', 'updated_at'])
        feature = FeatureEntitlement.objects.create(
            code='test_feature',
            label='Test Feature',
            description='Original',
            free_enabled=False,
            premium_enabled=True,
        )

        self.client.force_login(user)
        response = self.client.post(
            f'/api/dashboard/feature-entitlements/{feature.id}/save/',
            data=json.dumps({
                'label': 'Test Feature',
                'description': 'Updated',
                'free_enabled': True,
                'premium_enabled': True,
                'is_active': True,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        feature.refresh_from_db()
        self.assertTrue(feature.free_enabled)
        self.assertEqual(feature.description, 'Updated')

    def test_admin_can_manage_subscription_plans_and_usage_limits(self):
        user = User.objects.create_user(
            username='premium-admin@example.com',
            email='premium-admin@example.com',
            password=self.password,
            is_staff=True,
        )
        user.membership_profile.access_role = 'admin'
        user.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(user)

        plan_response = self.client.post(
            '/api/dashboard/subscription-plans/save/',
            data=json.dumps({
                'code': 'premium_research',
                'label': 'Premium Research',
                'description': 'Premium access for research workflows.',
                'tier': 'premium',
                'provider': 'manual',
                'billing_interval': 'month',
                'price_cents': 1999,
                'currency': 'USD',
                'is_public': True,
                'is_active': True,
            }),
            content_type='application/json',
        )
        self.assertEqual(plan_response.status_code, 200)
        self.assertTrue(SubscriptionPlan.objects.filter(code='premium_research').exists())

        limit_response = self.client.post(
            '/api/dashboard/usage-limits/save/',
            data=json.dumps({
                'feature_code': 'ai_research_assistant',
                'tier': 'free',
                'period': 'day',
                'limit': 25,
                'is_active': True,
            }),
            content_type='application/json',
        )
        self.assertEqual(limit_response.status_code, 200)
        self.assertTrue(UsageLimit.objects.filter(feature_code='ai_research_assistant', tier='free', limit=25).exists())

    def test_join_team_entries_are_protected_and_editable_by_admin(self):
        response = self.client.get('/api/dashboard/join-team/')
        self.assertEqual(response.status_code, 401)

        user = User.objects.create_user(
            username='join-admin@example.com',
            email='join-admin@example.com',
            password=self.password,
            is_staff=True,
        )
        user.membership_profile.access_role = 'admin'
        user.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(user)

        response = self.client.post(
            '/api/dashboard/join-team/save/',
            data=json.dumps({
                'title': 'Evidence Review Team',
                'description': 'Support literature screening and research synthesis workflows.',
                'icon_key': 'search',
                'action_label': 'Apply via Google Form',
                'action_url': 'https://forms.gle/example',
                'status': 'published',
                'sort_order': 15,
                'seo_title': 'Evidence Review Team | Join ResRef',
                'seo_description': 'Join ResRef evidence review projects and support medical research synthesis.',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(JoinTeamEntry.objects.filter(title='Evidence Review Team').exists())
        self.assertEqual(response.json()['entry']['action_url'], 'https://forms.gle/example')

        response = self.client.post(
            '/api/dashboard/join-team/save/',
            data=json.dumps({
                'title': 'Unsafe Link',
                'description': 'Should not accept unsafe links.',
                'action_label': 'Apply',
                'action_url': 'javascript:alert(1)',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class PublicOpportunityApiTests(TestCase):
    def test_public_opportunities_show_only_published_safe_fields(self):
        ResearchOpportunity.objects.create(
            title='Published research role',
            slug='published-research-role',
            summary='A published opportunity.',
            status='published',
            contact_email='research@example.com',
            custom_fields=[
                {'label': 'Study phase', 'value': 'Recruiting', 'is_public': True},
                {'label': 'Internal reviewer', 'value': 'Editorial team', 'is_public': False},
            ],
            internal_notes='Internal reviewer note',
        )
        ResearchOpportunity.objects.create(
            title='Draft research role',
            slug='draft-research-role',
            summary='A draft opportunity.',
            status='draft',
            contact_email='draft@example.com',
        )

        response = self.client.get('/api/opportunities/')
        self.assertEqual(response.status_code, 200)
        data = response.json()['results']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['title'], 'Published research role')
        self.assertNotIn('internal_notes', data[0])
        self.assertEqual(data[0]['custom_fields'], [{'label': 'Study phase', 'value': 'Recruiting', 'is_public': True}])

    def test_closed_opportunities_are_public_only_when_the_admin_keeps_them_visible(self):
        ResearchOpportunity.objects.create(
            title='Visible closed fellowship',
            slug='visible-closed-fellowship',
            summary='The cohort is complete, but the programme details remain useful.',
            status='closed',
            show_when_closed=True,
        )
        ResearchOpportunity.objects.create(
            title='Hidden closed fellowship',
            slug='hidden-closed-fellowship',
            summary='This record should remain private after closing.',
            status='closed',
            show_when_closed=False,
        )

        response = self.client.get('/api/opportunities/')
        self.assertEqual(response.status_code, 200)
        results = {item['title']: item for item in response.json()['results']}
        self.assertIn('Visible closed fellowship', results)
        self.assertNotIn('Hidden closed fellowship', results)
        self.assertTrue(results['Visible closed fellowship']['is_closed'])
        self.assertEqual(results['Visible closed fellowship']['status'], 'closed')

        current_response = self.client.get('/api/opportunities/?current=true')
        self.assertNotIn('Visible closed fellowship', {item['title'] for item in current_response.json()['results']})


class PublicDatabaseApiTests(TestCase):
    def test_public_categories_hide_dashboard_hidden_categories(self):
        visible = Category.objects.create(name='Visible Specialty', slug='visible-specialty', show_in_database=True, database_order=1)
        hidden = Category.objects.create(name='Hidden Specialty', slug='hidden-specialty', show_in_database=False, database_order=2)
        child_hidden = Category.objects.create(name='Hidden Child', slug='hidden-child', parent=visible, show_in_database=False)

        response = self.client.get('/api/categories/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()['categories']
        slugs = {item['slug'] for item in payload}
        self.assertIn(visible.slug, slugs)
        self.assertNotIn(hidden.slug, slugs)
        visible_payload = next(item for item in payload if item['slug'] == visible.slug)
        self.assertNotIn(child_hidden.slug, {item['slug'] for item in visible_payload['children']})

    def test_public_post_detail_returns_multiple_authors_primary_first(self):
        primary = Author.objects.create(login='primary', display_name='Primary Author')
        coauthor = Author.objects.create(login='coauthor', display_name='Co Author', role='Editor')
        category = Category.objects.create(name='Nutrition', slug='nutrition')
        post = Post.objects.create(
            title='Multi-author Article',
            slug='multi-author-article',
            content='<p>Research content.</p>',
            status='publish',
            author=primary,
            published_at=timezone.now(),
        )
        post.authors.set([coauthor, primary])
        post.categories.add(category)

        response = self.client.get('/api/posts/multi-author-article/')
        self.assertEqual(response.status_code, 200)
        authors = response.json()['post']['authors']
        self.assertEqual([author['display_name'] for author in authors], ['Primary Author', 'Co Author'])
        self.assertEqual(authors[1]['role'], 'Editor')

    def test_public_post_detail_does_not_use_primary_author_as_contributor_fallback(self):
        uploader = Author.objects.create(login='uploader', display_name='Uploader Author')
        Post.objects.create(
            title='Legacy Byline Only Article',
            slug='legacy-byline-only-article',
            content='<p>Research content.</p>',
            status='publish',
            author=uploader,
            published_at=timezone.now(),
        )

        response = self.client.get('/api/posts/legacy-byline-only-article/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['post']['authors'], [])
        self.assertEqual(response.json()['post']['author'], '')

    def test_public_post_detail_normalizes_legacy_media_hosts(self):
        Post.objects.create(
            title='Legacy Media Article',
            slug='legacy-media-article',
            content='<p><img src="https://resres.local/wp-content/uploads/2026/01/research-note.png"></p>',
            featured_image='https://resres.local/wp-content/uploads/2026/01/cover.png',
            status='publish',
            published_at=timezone.now(),
        )

        response = self.client.get('/api/posts/legacy-media-article/')
        self.assertEqual(response.status_code, 200)
        post = response.json()['post']
        self.assertIn('https://resref.com/wp-content/uploads/2026/01/research-note.png', post['content'])
        self.assertEqual(post['featured_image'], 'https://resref.com/wp-content/uploads/2026/01/cover.png')


class PublicFaqApiTests(TestCase):
    def test_public_faq_groups_only_published_items(self):
        category = FAQCategory.objects.create(name='Test FAQ Group', slug='test-faq-group', sort_order=999)
        FAQItem.objects.create(category=category, question='Published question?', answer='Published answer.', status='published', sort_order=10)
        FAQItem.objects.create(category=category, question='Hidden question?', answer='Hidden answer.', status='hidden', sort_order=20)

        response = self.client.get('/api/faq/')
        self.assertEqual(response.status_code, 200)
        categories = response.json()['categories']
        test_category = next(item for item in categories if item['slug'] == 'test-faq-group')
        self.assertEqual(test_category['name'], 'Test FAQ Group')
        self.assertEqual(len(test_category['items']), 1)
        self.assertEqual(test_category['items'][0]['question'], 'Published question?')


class PublicJoinTeamApiTests(TestCase):
    def test_public_join_team_entries_only_show_published_cards(self):
        JoinTeamEntry.objects.create(
            title='Published Team',
            slug='published-team',
            description='Published public card.',
            action_url='https://forms.gle/published',
            status='published',
            sort_order=1,
        )
        JoinTeamEntry.objects.create(
            title='Draft Team',
            slug='draft-team',
            description='Draft card.',
            action_url='https://forms.gle/draft',
            status='draft',
            sort_order=2,
        )

        response = self.client.get('/api/join-team/')
        self.assertEqual(response.status_code, 200)
        data = response.json()['results']
        titles = {item['title'] for item in data}
        self.assertIn('Published Team', titles)
        self.assertNotIn('Draft Team', titles)
        published = next(item for item in data if item['title'] == 'Published Team')
        self.assertNotIn('status', published)


class QueryCountTests(TestCase):
    """T-09: list endpoints must not issue one query per row."""

    password = 'Secur3-ResRef!Passphrase'

    def setUp(self):
        cache.clear()

    def test_account_me_query_budget(self):
        user = User.objects.create_superuser('budget-admin', 'budget-admin@example.com', self.password)
        self.client.force_login(user)
        with self._at_most(10):
            response = self.client.get('/api/accounts/me/')
        self.assertEqual(response.status_code, 200)

    def test_dashboard_users_list_query_budget(self):
        from dashboard.models import TeamMember
        admin = User.objects.create_superuser('list-admin', 'list-admin@example.com', self.password)
        for index in range(20):
            user = User.objects.create_user(f'row{index}@example.com', f'row{index}@example.com', self.password)
            if index % 3 == 0:
                TeamMember.objects.create(user=user, role='viewer')
        self.client.force_login(admin)
        with self._at_most(15):
            response = self.client.get('/api/dashboard/users/?per_page=10')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 10)
        with self._at_most(15):
            response = self.client.get('/api/dashboard/users/?role=viewer&per_page=10')
        self.assertEqual(response.status_code, 200)

    def test_taxonomy_lists_do_not_grow_with_rows(self):
        admin = User.objects.create_superuser('tax-admin', 'tax-admin@example.com', self.password)
        author = Author.objects.create(login='a1', display_name='A1')
        for index in range(8):
            category = Category.objects.create(name=f'Cat {index}', slug=f'cat-{index}')
            post = Post.objects.create(title=f'P{index}', slug=f'p-{index}', content='x', author=author)
            post.categories.add(category)
            post.authors.add(author)
        self.client.force_login(admin)
        for url in ('/api/dashboard/categories/', '/api/dashboard/authors/', '/api/dashboard/tags/', '/api/categories/', '/api/faq/'):
            with self._at_most(8):
                response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
        authors = self.client.get('/api/dashboard/authors/').json()['results']
        self.assertEqual(authors[0]['usage_count'], 8)

    def _at_most(self, limit):
        from contextlib import contextmanager
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        @contextmanager
        def check():
            with CaptureQueriesContext(connection) as context:
                yield
            executed = [query for query in context.captured_queries if not query['sql'].startswith(('SAVEPOINT', 'RELEASE SAVEPOINT'))]
            self.assertLessEqual(len(executed), limit, '\n'.join(query['sql'][:120] for query in executed))

        return check()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DashboardRoleFilterTests(TestCase):
    """The SQL role filter must agree with get_dashboard_role for every shape of user."""

    def test_role_q_matches_python_role(self):
        from dashboard.models import TeamMember
        from dashboard.permissions import clear_role_cache, dashboard_role_q, get_dashboard_role

        roles = {code: AccountRole.objects.get_or_create(code=code, defaults={'label': code})[0]
                 for code in ('free', 'premium', 'editor', 'admin', 'super_admin', 'viewer')}
        roles['super_admin'].is_super_admin = True
        roles['super_admin'].save()
        inactive_editor = AccountRole.objects.create(code='retired-editor', label='Retired', is_active=False)
        counter = 0
        for account_role in [None, *roles.values(), inactive_editor]:
            for access_role in ('member', 'editor', 'admin'):
                for team_role in (None, 'admin', 'editor', 'contributor', 'viewer', 'inactive-viewer'):
                    counter += 1
                    user = User.objects.create_user(f'shape{counter}@example.com', f'shape{counter}@example.com', 'x')
                    profile = user.membership_profile
                    profile.account_role = account_role
                    profile.access_role = access_role
                    profile.save()
                    if team_role:
                        TeamMember.objects.create(user=user, role=team_role.replace('inactive-', ''), is_active=not team_role.startswith('inactive'))
        User.objects.create_superuser('shape-root', 'shape-root@example.com', 'x')

        users = list(User.objects.select_related('membership_profile__account_role', 'team_member'))
        for role in ('admin', 'editor', 'contributor', 'viewer', 'member'):
            expected = set()
            for user in users:
                clear_role_cache(user)
                if get_dashboard_role(user) == role:
                    expected.add(user.pk)
            actual = set(User.objects.filter(dashboard_role_q(role)).values_list('pk', flat=True))
            self.assertEqual(actual, expected, role)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', NEWSLETTER_ENABLED=False)
class NewsletterDisabledTests(TestCase):
    """While the newsletter is switched off nothing is emailed and its APIs are gone."""

    def test_outbox_sends_nothing_and_keeps_campaign_queued(self):
        from dashboard.outbox import process_outbox, queue_campaign
        campaign = queue_campaign(
            subject='Off', message='Body text long enough for the newsletter.',
            recipients=['reader@example.com'], idempotency_key='off-1', sent_by=None,
        )
        process_outbox()
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'queued')
        self.assertEqual(len(mail.outbox), 0)

    def test_public_subscribe_returns_404_without_email(self):
        response = self.client.post('/api/newsletter/subscribe/', data='{"email": "reader@example.com"}', content_type='application/json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(len(mail.outbox), 0)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', NEWSLETTER_ENABLED=True)
class NewsletterOutboxTests(TestCase):
    """T-10: the outbox sends in batches, resumes, and retries failures."""

    def _queue(self, count):
        from dashboard.outbox import queue_campaign
        return queue_campaign(
            subject='Batch test', message='Body text long enough for the newsletter.',
            recipients=[f'reader{index}@example.com' for index in range(count)],
            idempotency_key=f'batch-{count}', sent_by=None,
        )

    def test_batches_until_done_without_duplicates(self):
        from dashboard.outbox import process_outbox
        campaign = self._queue(5)
        process_outbox(batch_size=2)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'sending')
        self.assertEqual(len(mail.outbox), 2)
        process_outbox(batch_size=2)
        process_outbox(batch_size=2)
        process_outbox(batch_size=2)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'sent')
        self.assertEqual(len(mail.outbox), 5)
        self.assertEqual(len({message.to[0] for message in mail.outbox}), 5)

    def test_connection_failure_retries_then_marks_failed(self):
        from unittest import mock
        from dashboard.outbox import MAX_ATTEMPTS, process_outbox
        campaign = self._queue(2)
        with mock.patch('dashboard.outbox.get_connection', side_effect=OSError('smtp down')):
            for _ in range(MAX_ATTEMPTS):
                process_outbox()
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'failed')
        self.assertEqual(campaign.failed_count, 2)
        self.assertIn('smtp down', campaign.error_message)
        self.assertEqual(len(mail.outbox), 0)
