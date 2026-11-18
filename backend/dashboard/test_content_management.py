import json
from io import StringIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from blog.models import Author, Category, Post, PostContributor


@override_settings(ALLOWED_HOSTS=['testserver'])
class ContentManagementTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_superuser('review-admin', 'review@example.invalid', 'Review-Only!12345')
        self.client.force_login(self.user)

    def save(self, url, payload):
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_login_requires_csrf_and_rejects_foreign_origins(self):
        browser = Client(enforce_csrf_checks=True)
        payload = json.dumps({'username': self.user.username, 'password': 'Review-Only!12345'})
        url = '/api/dashboard/auth/login/'
        self.assertEqual(browser.post(url, payload, content_type='application/json').status_code, 403)
        token = browser.get('/api/accounts/csrf/').json()['csrfToken']
        self.assertEqual(browser.post(url, payload, content_type='application/json', HTTP_X_CSRFTOKEN=token,
                                      HTTP_ORIGIN='https://untrusted.example').status_code, 403)
        response = browser.post(url, payload, content_type='application/json', HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN='http://testserver')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(browser.get('/api/dashboard/auth/me/').status_code, 200)

    def test_profiles_are_content_records_and_not_login_accounts(self):
        before = User.objects.count()
        result = self.save('/api/dashboard/authors/save/', {
            'display_name': 'Dr. Research Guest', 'slug': 'research-guest', 'position': 'Researcher',
            'institution': 'Example University', 'short_bio': 'Contributor biography.',
            'website': 'https://example.org/researcher',
        })
        self.assertEqual(User.objects.count(), before)
        profile = self.client.get('/api/authors/research-guest/').json()['author']
        self.assertEqual(profile['institution'], 'Example University')
        self.assertNotIn('email', profile)
        self.assertEqual(result['author']['display_name'], 'Dr. Research Guest')

    def test_uploading_a_post_never_assigns_the_signed_in_account(self):
        Author.objects.create(login=self.user.username, display_name='Uploader profile')
        result = self.save('/api/dashboard/posts/save/', {
            'title': 'Explicit authors only', 'slug': 'explicit-authors-only', 'status': 'publish',
            'content': '<h2>Overview</h2><p>Research content.</p>',
        })
        self.assertEqual(result['post']['authors'], [])
        self.assertFalse(PostContributor.objects.exists())

    def test_card_visibility_does_not_remove_explicit_author_assignment(self):
        author = Author.objects.create(login='guest', display_name='Guest Author')
        payload = {'title': 'Assigned author', 'slug': 'assigned-author', 'status': 'publish',
                   'content': '<p>Content</p>', 'contributors': [{'contributor_id': author.id, 'role': 'author'}],
                   'design_settings': {'author_section_enabled': 'hidden'}}
        post = self.save('/api/dashboard/posts/save/', payload)['post']
        self.assertEqual(post['authors'][0]['id'], author.id)
        self.assertEqual(post['design_settings']['author_section_enabled'], 'hidden')
        payload['design_settings']['author_section_enabled'] = 'auto'
        self.save(f"/api/dashboard/posts/{post['id']}/save/", payload)
        public = self.client.get('/api/posts/assigned-author/').json()['post']
        self.assertEqual(public['authors'][0]['id'], author.id)
        self.assertEqual(public['design_settings']['author_section_enabled'], 'auto')

    def test_category_intro_and_hero_are_editable_without_changing_slug(self):
        result = self.save('/api/dashboard/categories/save/', {
            'name': 'Evidence', 'slug': 'evidence', 'description': 'Explore research evidence.',
            'hero_image': 'https://example.org/topic.png',
        })
        category = self.client.get('/api/categories/').json()['categories'][0]
        self.assertEqual(category['slug'], 'evidence')
        self.assertEqual(category['description'], 'Explore research evidence.')
        self.assertEqual(category['hero_image'], 'https://example.org/topic.png')
        self.assertEqual(result['category']['slug'], 'evidence')

    def test_named_legacy_credit_import_is_idempotent_and_preserves_original_html(self):
        html = '<p>Article body</p><h2>Authorship and Contributions</h2><img src="https://example.org/author.png"><h2>Dr. Named Guest</h2><p>Author</p><p>Senior Resident</p>'
        post = Post.objects.create(title='Legacy named credit', slug='named-credit', content=html)
        before = User.objects.count()
        call_command('import_legacy_contributors', slug=post.slug, apply=True, stdout=StringIO())
        call_command('import_legacy_contributors', slug=post.slug, apply=True, stdout=StringIO())
        post.refresh_from_db()
        self.assertEqual(post.content, html)
        self.assertEqual(post.contributor_assignments.count(), 1)
        self.assertEqual(post.authors.get().display_name, 'Dr. Named Guest')
        self.assertEqual(User.objects.count(), before)
