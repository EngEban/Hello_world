import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from blog.models import Author, Category, Post, PostContributor, Tag
from dashboard.models import DashboardActivityLog


class EditorialWorkspaceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('editorial-admin', password='test-only-password')
        self.client.force_login(self.admin)
        now = timezone.now()
        self.live = Post.objects.create(title='Published article', slug='published', content='<p>Original</p>', published_at=now - timedelta(days=2))
        self.future = Post.objects.create(title='Scheduled article', slug='scheduled', content='<p>Future</p>', published_at=now + timedelta(days=2))
        self.draft = Post.objects.create(title='Draft article', slug='draft', content='<p>Draft</p>', status='draft')

    def bulk(self, ids, action, **extra):
        return self.client.post('/api/dashboard/posts/bulk/', json.dumps({'ids': ids, 'action': action, **extra}), content_type='application/json')

    def test_summary_is_global_and_live_and_scheduled_are_distinct(self):
        data = self.client.get('/api/dashboard/posts/?status=draft&per_page=1').json()
        self.assertEqual(data['summary']['total'], 3)
        self.assertEqual(data['summary']['published'], 1)
        self.assertEqual(data['summary']['scheduled'], 1)
        self.assertEqual(data['pagination']['total_items'], 1)
        self.assertEqual(self.client.get('/api/dashboard/posts/?status=scheduled').json()['results'][0]['id'], self.future.pk)
        self.assertEqual(self.client.get('/api/dashboard/posts/?status=publish').json()['results'][0]['id'], self.live.pk)

    def test_trash_restore_never_deletes_content(self):
        self.assertEqual(self.bulk([self.live.pk], 'trash').status_code, 200)
        self.live.refresh_from_db()
        self.assertEqual(self.live.content, '<p>Original</p>')
        self.assertNotIn(self.live.pk, [p['id'] for p in self.client.get('/api/dashboard/posts/').json()['results']])
        self.assertEqual(self.bulk([self.live.pk], 'restore').status_code, 200)
        self.live.refresh_from_db()
        self.assertEqual(self.live.status, 'draft')
        self.assertTrue(DashboardActivityLog.objects.filter(metadata__action='trash').exists())

    def test_bulk_validates_entire_selection_before_any_change(self):
        self.assertEqual(self.bulk([self.draft.pk, 999999], 'publish').status_code, 409)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, 'draft')
        for ids in [[], list(range(1, 102)), ['bad'], [True]]:
            self.assertEqual(self.bulk(ids, 'draft').status_code, 400)
        self.assertEqual(self.bulk([self.draft.pk], 'delete').status_code, 400)

    def test_schedule_and_publish_preserve_urls(self):
        date = timezone.now() + timedelta(days=3)
        self.assertEqual(self.bulk([self.draft.pk], 'schedule', published_at=date.isoformat()).status_code, 200)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.published_at, date)
        self.assertEqual(self.draft.status, 'publish')
        self.assertEqual(self.draft.slug, 'draft')
        self.assertEqual(self.bulk([self.draft.pk], 'schedule', published_at='2026-99-99T00:00:00Z').status_code, 400)
        self.assertEqual(self.bulk([self.draft.pk], 'publish').status_code, 200)
        self.draft.refresh_from_db()
        self.assertLessEqual(self.draft.published_at, timezone.now())
        original = self.live.published_at
        self.bulk([self.live.pk], 'publish')
        self.live.refresh_from_db()
        self.assertEqual(original, self.live.published_at)

    def test_duplicate_is_unpublished_and_preserves_relationships_without_sharing_pdf(self):
        author = Author.objects.create(login='contributor', display_name='Medical author')
        category = Category.objects.create(name='Research', slug='research')
        tag = Tag.objects.create(name='Evidence', slug='evidence')
        self.live.categories.add(category)
        self.live.tags.add(tag)
        self.live.authors.add(author)
        PostContributor.objects.create(post=self.live, contributor=author, role='reviewer')
        self.live.pdf_file = 'uploads/original.pdf'
        self.live.design_settings = {'author_section_enabled': 'auto', 'is_featured': True}
        self.live.save()
        response = self.bulk([self.live.pk], 'duplicate')
        self.assertEqual(response.status_code, 200)
        copy = Post.objects.get(pk=response.json()['post']['id'])
        self.assertEqual(copy.status, 'draft')
        self.assertIsNone(copy.published_at)
        self.assertFalse(copy.pdf_file)
        self.assertFalse(copy.design_settings['is_featured'])
        self.assertEqual(copy.categories.first(), category)
        self.assertEqual(copy.tags.first(), tag)
        self.assertEqual(copy.contributor_assignments.first().role, 'reviewer')
        self.assertEqual(copy.authors.first(), author)
        self.assertNotEqual(copy.slug, self.live.slug)

    def test_conflict_protection_does_not_overwrite_another_editor(self):
        response = self.client.post(f'/api/dashboard/posts/{self.live.pk}/save/', json.dumps({'expected_updated_at': 'stale', 'title': 'Overwrite'}), content_type='application/json')
        self.assertEqual(response.status_code, 409)
        self.live.refresh_from_db()
        self.assertEqual(self.live.title, 'Published article')

    def test_summary_payload_omits_editor_source_and_detail_load_keeps_it(self):
        self.live.elementor_data = 'Preserved original source'
        self.live.save()
        listing = self.client.get('/api/dashboard/posts/?summary_only=true').json()['results']
        row = next(p for p in listing if p['id'] == self.live.pk)
        self.assertNotIn('content', row)
        self.assertNotIn('elementor_data', row)
        detail = self.client.get(f'/api/dashboard/posts/?id={self.live.pk}&summary_only=true').json()['results'][0]
        self.assertEqual(detail['content'], self.live.content)
        self.assertEqual(detail['elementor_data'], 'Preserved original source')

    def test_new_bulk_endpoint_enforces_csrf_for_authenticated_sessions(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post('/api/dashboard/posts/bulk/', json.dumps({'ids':[self.live.pk], 'action':'draft'}), content_type='application/json').status_code, 403)

    def test_overview_counts_exclude_scheduled_and_nonlive_from_recent_publications(self):
        stats = self.client.get('/api/dashboard/stats/').json()['stats']
        self.assertEqual(stats['published_articles'], 1)
        self.assertEqual(stats['scheduled_articles'], 1)
        self.assertEqual(stats['draft_articles'], 1)
        self.assertEqual(stats['posts_this_week'], 1)

    def test_filters_include_contributor_roles_and_missing_fields(self):
        author = Author.objects.create(login='reviewer', display_name='Reviewer')
        PostContributor.objects.create(post=self.draft, contributor=author, role='reviewer')
        self.assertEqual(self.client.get(f'/api/dashboard/posts/?author={author.pk}').json()['pagination']['total_items'], 1)
        self.assertEqual(self.client.get('/api/dashboard/posts/?needs=seo').json()['pagination']['total_items'], 3)
        self.assertEqual(self.client.get('/api/dashboard/posts/?date_from=2026-99-99').status_code, 400)

    def test_permission_boundaries_and_csrf_remain_enforced(self):
        self.client.logout()
        self.assertEqual(self.bulk([self.live.pk], 'draft').status_code, 401)
        viewer = User.objects.create_user('editorial-viewer', password='test-only-password')
        viewer.membership_profile.access_role = 'viewer'
        viewer.membership_profile.save()
        self.client.force_login(viewer)
        self.assertEqual(self.bulk([self.live.pk], 'draft').status_code, 403)
        viewer.membership_profile.access_role = 'editor'
        viewer.membership_profile.save()
        self.assertEqual(self.bulk([self.live.pk], 'trash').status_code, 403)

    def test_featured_selection_updates_public_home_not_future_content(self):
        self.assertEqual(self.bulk([self.live.pk], 'feature').status_code, 200)
        self.assertEqual(self.client.get('/api/dashboard/posts/?featured=true').json()['results'][0]['id'], self.live.pk)
        self.bulk([self.future.pk], 'feature')
        featured = self.client.get('/api/home/').json()['featured_posts']
        self.assertEqual(featured[0]['id'], self.live.pk)
        self.assertNotIn(self.future.pk, [p['id'] for p in featured])
