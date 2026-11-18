from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from dashboard.models import (
    ContactSubmission,
    JobApplication,
    NewsletterSubscriber,
    ResearchOpportunity,
    ServiceDefinition,
    ServiceRequest,
)


class EngagementApiTests(TestCase):
    """List extras behind the redesigned inbox, forms, newsletter, opportunities and services screens."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser('engagement-admin', email='admin@example.com', password='test-only-password')
        self.client.force_login(self.admin)

    def test_contacts_include_status_counts_independent_of_filter(self):
        ContactSubmission.objects.create(name='A', email='a@example.com', message='Hello', status='new')
        ContactSubmission.objects.create(name='B', email='b@example.com', message='Hello', status='new')
        ContactSubmission.objects.create(name='C', email='c@example.com', message='Hello', company='Acme', status='replied')
        data = self.client.get('/api/dashboard/contacts/', {'status': 'replied'}).json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['counts'], {'new': 2, 'read': 0, 'replied': 1, 'archived': 0, 'all': 3})
        self.assertEqual([item['value'] for item in data['statuses']], ['new', 'read', 'replied', 'archived'])
        # Company is searchable too.
        self.assertEqual(self.client.get('/api/dashboard/contacts/', {'q': 'acme'}).json()['results'][0]['name'], 'C')

    def test_applications_include_counts_and_teams(self):
        JobApplication.objects.create(full_name='Applicant', email='x@example.com', team='media', status='interview')
        data = self.client.get('/api/dashboard/applications/').json()
        self.assertEqual(data['counts']['interview'], 1)
        self.assertEqual(data['counts']['all'], 1)
        self.assertIn({'value': 'media', 'label': 'Media Team'}, data['teams'])

    def test_forms_overview_searches_in_database_and_returns_details(self):
        old = ContactSubmission.objects.create(name='Needle Person', email='needle@example.com', message='Old message body')
        for index in range(35):
            ContactSubmission.objects.create(name=f'Filler {index}', email=f'f{index}@example.com', message='Newer')
        JobApplication.objects.create(full_name='Applicant', email='app@example.com', team='media', motivation='Because')
        ServiceRequest.objects.create(requester_name='Req', requester_email='req@example.com', subject='Expert consultation', priority='high')
        found = self.client.get('/api/dashboard/forms/', {'q': 'needle'}).json()
        self.assertEqual([item['record_id'] for item in found['results']], [old.id])
        self.assertEqual(found['results'][0]['message'], 'Old message body')
        apps = self.client.get('/api/dashboard/forms/', {'type': 'team_application'}).json()['results']
        self.assertEqual(apps[0]['details']['Team'], 'Media Team')
        self.assertIn('cv_url', apps[0])
        requests = self.client.get('/api/dashboard/forms/', {'type': 'service_request', 'status': 'new'}).json()
        self.assertEqual(requests['results'][0]['priority'], 'high')
        self.assertEqual(requests['summary']['new_service_requests'], 1)
        self.assertIn('interview', requests['statuses']['team_application'])

    @override_settings(NEWSLETTER_ENABLED=True)
    def test_newsletter_pending_filter_and_recipient_preview(self):
        now = timezone.now()
        NewsletterSubscriber.objects.create(email='b-active@example.com', is_active=True, confirmed_at=now)
        NewsletterSubscriber.objects.create(email='a-active@example.com', is_active=True, confirmed_at=now)
        NewsletterSubscriber.objects.create(email='paused@example.com', is_active=False, confirmed_at=now)
        NewsletterSubscriber.objects.create(email='pending@example.com', is_active=True)
        pending = self.client.get('/api/dashboard/newsletter/', {'status': 'pending'}).json()
        self.assertEqual([item['email'] for item in pending['results']], ['pending@example.com'])
        self.assertNotIn('recipients', pending)
        preview = self.client.get('/api/dashboard/newsletter/', {'include_recipients': '1'}).json()
        self.assertEqual(preview['recipients'], ['a-active@example.com', 'b-active@example.com'])
        self.assertEqual(preview['recipient_total'], preview['summary']['active'])

    def test_opportunity_deadline_filters_and_counts(self):
        today = timezone.localdate()
        ResearchOpportunity.objects.create(title='Soon', slug='soon', status='published', deadline=today + timedelta(days=3))
        ResearchOpportunity.objects.create(title='Expired', slug='expired', status='published', deadline=today - timedelta(days=1))
        ResearchOpportunity.objects.create(title='Later', slug='later', status='published', deadline=today + timedelta(days=60), is_featured=True)
        ResearchOpportunity.objects.create(title='Draft', slug='draft', status='draft', deadline=today + timedelta(days=2))
        data = self.client.get('/api/dashboard/opportunities/').json()
        self.assertEqual(data['counts']['published'], 3)
        self.assertEqual(data['counts']['all'], 4)
        self.assertEqual(data['deadline_counts'], {'closing_soon': 1, 'expired': 1, 'featured': 1})
        soon = self.client.get('/api/dashboard/opportunities/', {'deadline': 'closing_soon'}).json()
        self.assertEqual([item['slug'] for item in soon['results']], ['soon'])
        expired = self.client.get('/api/dashboard/opportunities/', {'deadline': 'expired'}).json()
        self.assertEqual([item['slug'] for item in expired['results']], ['expired'])

    def test_services_and_requests_include_counts_filters_and_assignees(self):
        service = ServiceDefinition.objects.create(title='Stats help', slug='stats-help')
        ServiceDefinition.objects.create(title='Old', slug='old', status='paused')
        staff = User.objects.create_user('helper', password='test-only-password', is_staff=True, first_name='Helper')
        ServiceRequest.objects.create(service=service, requester_name='R1', requester_email='r1@example.com', subject='One', priority='urgent', assigned_to=staff)
        ServiceRequest.objects.create(requester_name='R2', requester_email='r2@example.com', subject='Two', status='in_progress')
        services = self.client.get('/api/dashboard/services/').json()
        self.assertEqual(services['counts'], {'active': 1, 'paused': 1, 'archived': 0, 'all': 2})
        data = self.client.get('/api/dashboard/service-requests/').json()
        self.assertEqual(data['counts']['in_progress'], 1)
        self.assertIn({'id': staff.id, 'name': 'Helper'}, data['assignees'])
        urgent = self.client.get('/api/dashboard/service-requests/', {'priority': 'urgent'}).json()
        self.assertEqual([item['subject'] for item in urgent['results']], ['One'])
        unassigned = self.client.get('/api/dashboard/service-requests/', {'assigned_to': 'none'}).json()
        self.assertEqual([item['subject'] for item in unassigned['results']], ['Two'])

    def test_partial_status_update_keeps_request_fields(self):
        item = ServiceRequest.objects.create(requester_name='R', requester_email='r@example.com', subject='Keep me', internal_notes='note')
        response = self.client.post(f'/api/dashboard/service-requests/{item.id}/save/', {'status': 'completed'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual((item.status, item.subject, item.internal_notes), ('completed', 'Keep me', 'note'))

    def test_lists_still_require_permissions(self):
        self.client.logout()
        for url in ['/api/dashboard/contacts/', '/api/dashboard/forms/', '/api/dashboard/service-requests/', '/api/dashboard/opportunities/']:
            self.assertIn(self.client.get(url).status_code, (401, 403))
