from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from blog.models import Category, Post
from dashboard.models import ResearchOpportunity


class HomepagePreviewTests(TestCase):
    def test_resource_count_excludes_drafts_pages_and_future_posts(self):
        now = timezone.now()
        for i in range(8):
            Post.objects.create(title=f'Resource {i}', slug=f'resource-{i}', content='Research', published_at=now)
        Post.objects.create(title='Draft', slug='draft', status='draft', published_at=now)
        Post.objects.create(title='Page', slug='page', post_type='page', published_at=now)
        Post.objects.create(title='Future', slug='future', published_at=now + timedelta(days=1))
        payload = self.client.get('/api/home/').json()
        self.assertEqual(payload['resource_count'], 8)
        self.assertEqual(payload['category_count'], 0)
        self.assertEqual(len(payload['featured_posts']), 6)
        self.assertNotIn('categories', payload)

    def test_learning_preview_only_returns_mastering_research_articles(self):
        now = timezone.now()
        research = Category.objects.create(name='Mastering Research', slug='mastering-research')
        other = Category.objects.create(name='Other Resources', slug='other-resources')
        learning_post = Post.objects.create(title='Research Learning', slug='research-learning', content='Research', published_at=now)
        other_post = Post.objects.create(title='Other Resource', slug='other-resource', content='Research', published_at=now)
        learning_post.categories.add(research)
        other_post.categories.add(other)

        payload = self.client.get('/api/home/').json()

        self.assertEqual(payload['category_count'], 2)
        self.assertEqual([item['title'] for item in payload['learning_posts']], ['Research Learning'])

    def test_current_preview_excludes_expired_and_unpublished_opportunities(self):
        today = timezone.localdate()
        for title, status, deadline in [
            ('Open', 'published', None), ('Today', 'published', today),
            ('Expired', 'published', today - timedelta(days=1)), ('Draft', 'draft', None),
        ]:
            ResearchOpportunity.objects.create(title=title, status=status, deadline=deadline)
        payload = self.client.get('/api/opportunities/', {'current': 'true'}).json()
        self.assertEqual({item['title'] for item in payload['results']}, {'Open', 'Today'})
        self.assertEqual(self.client.get('/api/opportunities/').json()['pagination']['total_items'], 3)
