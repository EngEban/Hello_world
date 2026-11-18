import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from blog.models import Author, Category, Post, PostContributor


class ArticleLibraryApiTests(TestCase):
    """Library filters, attention counts and the trash-first delete rule."""

    def setUp(self):
        self.admin = User.objects.create_superuser('articles-admin', password='test-only-password')
        self.client.force_login(self.admin)
        now = timezone.now()
        self.category = Category.objects.create(name='Methods', slug='methods')
        self.author = Author.objects.create(login='writer', display_name='Writer')
        self.complete = Post.objects.create(
            title='Complete article', slug='complete', content='<p>Body</p>', excerpt='A summary',
            featured_image='https://example.com/a.png', seo_title='SEO', seo_description='Description',
            published_at=now - timedelta(days=1),
        )
        self.complete.categories.add(self.category)
        PostContributor.objects.create(post=self.complete, contributor=self.author, role='author')
        self.bare = Post.objects.create(title='Bare draft', slug='bare', content='<p>Draft</p>', status='draft')
        self.trashed = Post.objects.create(title='Trashed', slug='trashed', content='<p>Old</p>', status='trash')
        self.page = Post.objects.create(title='About', slug='about', content='<p>Page</p>', post_type='page')

    def get(self, query=''):
        return self.client.get(f'/api/dashboard/posts/{query}')

    def test_excerpt_and_category_filters(self):
        self.assertEqual([p['id'] for p in self.get('?needs=excerpt').json()['results']], [self.bare.pk])
        self.assertEqual([p['id'] for p in self.get('?needs=category').json()['results']], [self.bare.pk])
        self.assertEqual([p['id'] for p in self.get('?needs=contributors').json()['results']], [self.bare.pk])

    def test_attention_counts_match_filters_and_ignore_trash_and_other_type(self):
        data = self.get('?summary_only=true').json()
        # Neither article has a focus keyphrase and both are short, so both need optimization work.
        self.assertEqual(data['attention'], {'seo': 1, 'image': 1, 'excerpt': 1, 'category': 1, 'contributors': 1, 'keyphrase': 2, 'low_score': 2})
        for key, count in data['attention'].items():
            self.assertEqual(self.get(f'?needs={key}').json()['pagination']['total_items'], count)
        self.assertEqual(self.get('?type=page').json()['attention']['excerpt'], 1)

    def test_attention_is_not_computed_for_single_record_loads(self):
        self.assertNotIn('attention', self.get(f'?id={self.complete.pk}').json())

    def test_permanent_delete_requires_trash_first(self):
        response = self.client.post(f'/api/dashboard/posts/{self.bare.pk}/delete/')
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Post.objects.filter(pk=self.bare.pk).exists())
        self.assertEqual(self.client.post(f'/api/dashboard/posts/{self.trashed.pk}/delete/').status_code, 200)
        self.assertFalse(Post.objects.filter(pk=self.trashed.pk).exists())

    def test_permanent_delete_still_needs_delete_permission(self):
        editor = User.objects.create_user('articles-editor', password='test-only-password')
        editor.membership_profile.access_role = 'editor'
        editor.membership_profile.save()
        self.client.force_login(editor)
        self.assertEqual(self.client.post(f'/api/dashboard/posts/{self.trashed.pk}/delete/').status_code, 403)
        self.assertTrue(Post.objects.filter(pk=self.trashed.pk).exists())

    def test_single_item_quick_actions_use_bulk_endpoint(self):
        def bulk(action, **extra):
            return self.client.post('/api/dashboard/posts/bulk/', json.dumps({'ids': [self.bare.pk], 'action': action, **extra}), content_type='application/json')
        self.assertEqual(bulk('pending').status_code, 200)
        self.bare.refresh_from_db()
        self.assertEqual(self.bare.status, 'pending')
        self.assertEqual(bulk('feature').status_code, 200)
        self.bare.refresh_from_db()
        self.assertTrue(self.bare.design_settings.get('is_featured'))
        self.assertEqual(bulk('trash').status_code, 200)
        self.assertEqual(bulk('restore').status_code, 200)
        self.bare.refresh_from_db()
        self.assertEqual(self.bare.status, 'draft')
        self.assertEqual(self.bare.content, '<p>Draft</p>')
