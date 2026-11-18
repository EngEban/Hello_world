import shutil
import tempfile
from pathlib import Path

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from blog.models import Author, Category, Post

from .models import Redirect
from .paths import normalize_path, safe_target


class PathTests(TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_path('/2024/05/My-Post/'), '/2024/05/my-post')
        self.assertEqual(normalize_path('https://resref.com/a//b/?x=1'), '/a/b')
        self.assertEqual(normalize_path('/'), '/')
        self.assertEqual(normalize_path('/caf%C3%A9/'), '/café')

    def test_safe_target(self):
        self.assertTrue(safe_target('/database/x'))
        self.assertTrue(safe_target('https://example.com/x'))
        for bad in ['//evil.com', 'javascript:alert(1)', '', '/\\evil.com', 'ftp://x']:
            self.assertFalse(safe_target(bad), bad)

    def test_model_validation(self):
        with self.assertRaises(ValidationError):
            Redirect(old_path='/a', new_url='//evil.com').full_clean()
        with self.assertRaises(ValidationError):
            Redirect(old_path='/a/', new_url='/A').full_clean()


class MiddlewareTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_exact_redirect_keeps_query_and_counts_hits(self):
        Redirect.objects.create(old_path='/2024/05/Old-Post/', new_url='/database/methods/old-post')
        response = self.client.get('/2024/05/old-post/?utm_source=x')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/database/methods/old-post?utm_source=x')
        self.assertEqual(Redirect.objects.get().hits, 1)

    def test_inactive_and_edited_rows_take_effect_immediately(self):
        row = Redirect.objects.create(old_path='/old', new_url='/new')
        self.assertEqual(self.client.get('/old')['Location'], '/new')
        row.new_url = '/newer'
        row.save()
        self.assertEqual(self.client.get('/old')['Location'], '/newer')
        row.is_active = False
        row.save()
        self.assertNotEqual(self.client.get('/old').status_code, 301)

    def test_prefix_redirect_preserves_file_name_case(self):
        Redirect.objects.create(old_path='/files/', new_url='/media/files/', is_prefix=True)
        self.assertEqual(self.client.get('/files/2024/Report.PDF')['Location'], '/media/files/2024/Report.PDF')

    def test_wordpress_id_category_and_author_patterns(self):
        category = Category.objects.create(name='Methods', slug='methods')
        post = Post.objects.create(title='T', slug='cohort', content='x', wordpress_id=101, status='publish')
        post.categories.add(category)
        Post.objects.create(title='Draft', slug='draft', content='x', wordpress_id=102, status='draft')
        Author.objects.create(login='dr-sara', display_name='Dr Sara Ali')
        self.assertEqual(self.client.get('/?p=101')['Location'], '/database/methods/cohort')
        self.assertNotEqual(self.client.get('/?p=102').status_code, 301)  # drafts are not revealed
        self.assertEqual(self.client.get('/category/research/methods/')['Location'], '/database/methods')
        self.assertEqual(self.client.get('/category/methods/page/2/')['Location'], '/database/methods')
        self.assertEqual(self.client.get('/author/dr-sara/')['Location'], '/authors/dr-sara-ali')
        self.assertNotEqual(self.client.get('/category/unknown/').status_code, 301)

    def test_uploads_redirect_to_copied_file(self):
        media_root = Path(tempfile.mkdtemp())
        try:
            target = media_root / 'wp-content/uploads/2024/05/Figure.png'
            target.parent.mkdir(parents=True)
            target.write_bytes(b'x')
            with override_settings(MEDIA_ROOT=str(media_root), STORAGES={
                'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
            }):
                self.assertEqual(self.client.get('/wp-content/uploads/2024/05/Figure.png')['Location'], '/media/wp-content/uploads/2024/05/Figure.png')
                self.assertNotEqual(self.client.get('/wp-content/uploads/2024/05/missing.png').status_code, 301)
                self.assertNotEqual(self.client.get('/wp-content/uploads/../../settings.py').status_code, 301)
        finally:
            shutil.rmtree(media_root, ignore_errors=True)

    def test_api_admin_and_writes_are_never_redirected(self):
        Redirect.objects.create(old_path='/api/health', new_url='/elsewhere')
        self.assertEqual(self.client.get('/api/health/').status_code, 200)
        Redirect.objects.create(old_path='/form', new_url='/contact')
        self.assertNotEqual(self.client.post('/form').status_code, 301)
