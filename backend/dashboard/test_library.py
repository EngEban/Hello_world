import json

from django.contrib.auth.models import User
from django.test import TestCase

from blog.models import Author, Category, MediaAsset, Post
from dashboard.models import FAQCategory, FAQItem


class MediaLibraryApiTests(TestCase):
    """Filters, summary and usage data behind the redesigned Media Library."""

    def setUp(self):
        self.admin = User.objects.create_superuser('library-admin', password='test-only-password')
        self.client.force_login(self.admin)
        self.described = MediaAsset.objects.create(title='Alpha chart', alt_text='Bar chart of results', url='https://cdn.example.com/alpha.png')
        self.bare = MediaAsset.objects.create(title='Zulu photo', url='https://cdn.example.com/zulu.png', wordpress_id=77)
        self.caption_only = MediaAsset.objects.create(title='Middle', caption='Unique caption words', url='https://cdn.example.com/middle.png')

    def get(self, **params):
        response = self.client.get('/api/dashboard/media/', params)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_summary_counts_total_and_missing_alt_text(self):
        data = self.get()
        self.assertEqual(data['summary'], {'total': 3, 'missing_alt': 2})

    def test_missing_alt_filter_returns_only_undescribed_images(self):
        data = self.get(missing_alt='1')
        self.assertEqual({item['id'] for item in data['results']}, {self.bare.id, self.caption_only.id})
        self.assertEqual(data['summary']['missing_alt'], 2)

    def test_search_includes_caption_and_sort_by_title(self):
        self.assertEqual([item['id'] for item in self.get(q='unique caption')['results']], [self.caption_only.id])
        titles = [item['title'] for item in self.get(sort='title')['results']]
        self.assertEqual(titles, ['Alpha chart', 'Middle', 'Zulu photo'])
        self.assertEqual(self.get(sort='oldest')['results'][0]['id'], self.described.id)

    def test_source_filter_and_source_field(self):
        wordpress = self.get(source='wordpress')['results']
        self.assertEqual([item['id'] for item in wordpress], [self.bare.id])
        self.assertEqual(wordpress[0]['source'], 'wordpress')
        self.assertEqual({item['id'] for item in self.get(source='external')['results']}, {self.described.id, self.caption_only.id})
        self.assertEqual(self.get(source='upload')['results'], [])

    def test_usage_for_single_asset_lists_referencing_content(self):
        Post.objects.create(title='Uses alpha', slug='uses-alpha', content='<p>x</p>', featured_image='https://cdn.example.com/alpha.png')
        Post.objects.create(title='Inline alpha', slug='inline-alpha', content='<img src="https://cdn.example.com/alpha.png">')
        Post.objects.create(title='Trashed alpha', slug='trashed-alpha', content='<p>x</p>', featured_image='https://cdn.example.com/alpha.png', status='trash')
        Author.objects.create(login='a', display_name='A', slug='a', profile_media=self.described)
        Category.objects.create(name='C', slug='c', hero_image='https://cdn.example.com/alpha.png')
        data = self.get(id=self.described.id, usage='1')
        self.assertEqual(len(data['results']), 1)
        usage = data['results'][0]['usage']
        self.assertEqual(usage['post_count'], 2)
        self.assertEqual(usage['authors'], 1)
        self.assertEqual(usage['categories'], 1)
        self.assertEqual(usage['total'], 4)
        self.assertNotIn('usage', self.get()['results'][0])

    def test_media_list_still_requires_content_permission(self):
        self.client.logout()
        self.assertIn(self.client.get('/api/dashboard/media/').status_code, {401, 403})


class FaqLibraryApiTests(TestCase):
    def test_categories_include_hidden_count(self):
        admin = User.objects.create_superuser('faq-library-admin', password='test-only-password')
        self.client.force_login(admin)
        category = FAQCategory.objects.create(name='General', slug='general')
        FAQItem.objects.create(category=category, question='Visible?', answer='Yes')
        FAQItem.objects.create(category=category, question='Hidden?', answer='No', status='hidden')
        data = self.client.get('/api/dashboard/faq/categories/').json()['results'][0]
        self.assertEqual((data['item_count'], data['published_count'], data['hidden_count']), (2, 1, 1))


class CategoryOrderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('order-admin', password='test-only-password')
        self.client.force_login(self.user)
        self.first = Category.objects.create(name='First', slug='first', database_order=1)
        self.second = Category.objects.create(name='Second', slug='second', database_order=2)
        self.child_a = Category.objects.create(name='Child A', slug='child-a', parent=self.first, database_order=1)
        self.child_b = Category.objects.create(name='Child B', slug='child-b', parent=self.first, database_order=2)

    def reorder(self, ids):
        return self.client.post('/api/dashboard/categories/reorder/', json.dumps({'ids': ids}), content_type='application/json')

    def test_public_list_follows_the_saved_order(self):
        response = self.reorder([self.second.id, self.first.id, self.child_b.id, self.child_a.id])
        self.assertEqual(response.status_code, 200)
        roots = self.client.get('/api/categories/').json()['categories']
        self.assertEqual([item['slug'] for item in roots], ['second', 'first'])
        self.assertEqual([item['slug'] for item in roots[1]['children']], ['child-b', 'child-a'])

    def test_reorder_applies_to_every_category(self):
        extra = [Category.objects.create(name=f'Extra {index}', slug=f'extra-{index}', database_order=index + 3).id for index in range(20)]
        response = self.reorder([*reversed(extra), self.second.id, self.first.id])
        self.assertEqual(response.status_code, 200)
        roots = self.client.get('/api/categories/').json()['categories']
        self.assertEqual(roots[0]['id'], extra[-1])
        self.assertEqual([item['slug'] for item in roots[-2:]], ['second', 'first'])

    def test_reorder_needs_edit_permission(self):
        self.client.logout()
        self.client.force_login(User.objects.create_user('no-rights', password='test-only-password'))
        self.assertIn(self.reorder([self.second.id, self.first.id]).status_code, (401, 403))
        self.first.refresh_from_db()
        self.assertEqual(self.first.database_order, 1)

    def test_new_category_joins_the_end_of_its_group(self):
        response = self.client.post('/api/dashboard/categories/save/', json.dumps({'name': 'Third', 'slug': 'third', 'database_order': 0}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Category.objects.get(slug='third').database_order, 3)
