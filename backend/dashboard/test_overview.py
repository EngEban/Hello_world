from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from blog.models import Category, Post
from dashboard.models import ContactSubmission


class DashboardOverviewDataTests(TestCase):
    """Data behind the redesigned overview: content health, trend, drafts and sidebar badges."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser('overview-admin', password='test-only-password')
        self.client.force_login(self.admin)
        now = timezone.now()
        self.category = Category.objects.create(name='Methods', slug='methods')
        complete = Post.objects.create(
            title='Complete article', slug='complete', content='<p>Body</p>', excerpt='Summary',
            featured_image='https://example.com/a.webp', seo_title='SEO', seo_description='Description',
            published_at=now - timedelta(days=1),
        )
        complete.categories.add(self.category)
        Post.objects.create(title='Bare draft', slug='bare', content='<p>Draft</p>', status='draft')
        Post.objects.create(title='In review', slug='review', content='<p>Review</p>', status='pending')
        Post.objects.create(title='Trashed', slug='trashed', content='<p>Gone</p>', status='trash')
        ContactSubmission.objects.create(name='Visitor', email='visitor@example.com', message='Hello')

    def test_stats_include_content_health_trend_and_recent_drafts(self):
        data = self.client.get('/api/dashboard/stats/').json()
        health = data['content_health']
        # Trash is excluded; the complete article is healthy, the other two are not.
        self.assertEqual(health['total'], 3)
        self.assertEqual(health['missing_seo'], 2)
        self.assertEqual(health['missing_image'], 2)
        self.assertEqual(health['missing_excerpt'], 2)
        self.assertEqual(health['uncategorized'], 2)
        self.assertEqual(len(data['publishing_trend']), 12)
        self.assertEqual(data['publishing_trend'][-1]['count'] + data['publishing_trend'][-2]['count'], 1)
        self.assertEqual([item['title'] for item in data['recent_drafts']], ['Bare draft'])

    def test_bootstrap_badges_count_pending_work(self):
        badges = self.client.get('/api/dashboard/bootstrap/').json()['badges']
        self.assertEqual(badges['/dashboard/posts'], 1)
        self.assertEqual(badges['/dashboard/contacts'], 1)
        self.assertEqual(badges['/dashboard/forms'], 1)
        self.assertNotIn('/dashboard/services', badges)  # zero counts are left out

    def test_article_list_filters_missing_excerpt_and_category(self):
        excerpt = self.client.get('/api/dashboard/posts/', {'needs': 'excerpt'}).json()
        category = self.client.get('/api/dashboard/posts/', {'needs': 'category'}).json()
        self.assertEqual(sorted(item['slug'] for item in excerpt['results']), ['bare', 'review'])
        self.assertEqual(sorted(item['slug'] for item in category['results']), ['bare', 'review'])
