from importlib import import_module
from io import StringIO
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase

from blog.legacy_credits import extract_profiles, restore_article_credits_v1
from blog.models import Author, Post, PostContributor


HTML = ('<p>Unchanged body</p><h2>Authorship and Contributions</h2>'
        '<img src="http://resref.local/wp-content/uploads/portrait.png">'
        '<h2>Dr. Named Researcher</h2><p>Author</p><p>Senior Resident</p>'
        '<h2>Dr. Named Reviewer</h2><p>Reviewer</p>')


class LegacyCreditRecoveryTests(TestCase):
    def restore(self, post):
        return restore_article_credits_v1(post, Author, PostContributor)

    def test_recovery_preserves_article_content_dates_and_is_idempotent(self):
        post = Post.objects.create(title='Named credits', slug='named-credits', content=HTML)
        before = (post.content, post.slug, post.published_at, post.updated_at)
        self.assertEqual(self.restore(post), 2)
        self.assertEqual(self.restore(post), 0)
        post.refresh_from_db()
        self.assertEqual((post.content, post.slug, post.published_at, post.updated_at), before)
        self.assertEqual(post.design_settings['author_section_enabled'], 'auto')
        self.assertEqual(list(post.contributor_assignments.values_list('role', flat=True)), ['author', 'reviewer'])
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(post.authors.get(display_name='Dr. Named Researcher').avatar, 'https://resref.com/wp-content/uploads/portrait.png')

    def test_hidden_cards_stay_hidden_but_named_credits_are_recovered(self):
        post = Post.objects.create(title='Hidden', slug='hidden', content=HTML, design_settings={'author_section_enabled': 'hidden'})
        self.restore(post)
        post.refresh_from_db()
        self.assertEqual(post.design_settings['author_section_enabled'], 'hidden')
        self.assertEqual(post.contributor_assignments.count(), 2)

    def test_existing_curated_assignments_are_never_replaced(self):
        guest = Author.objects.create(login='curated', display_name='Chosen Guest')
        post = Post.objects.create(title='Curated', slug='curated', content=HTML)
        PostContributor.objects.create(post=post, contributor=guest, role='editor')
        self.assertEqual(self.restore(post), 0)
        self.assertEqual(list(post.contributor_assignments.values_list('contributor_id', flat=True)), [guest.pk])
        self.assertEqual(Author.objects.count(), 1)

    def test_uploader_and_ordinary_body_text_are_not_authorship(self):
        uploader = Author.objects.create(login='uploader', display_name='Upload Account')
        post = Post.objects.create(title='No credits', slug='no-credits', author=uploader,
                                   content='<h2>General Introduction</h2><p>Author</p>')
        self.assertEqual(self.restore(post), 0)
        self.assertFalse(post.authors.exists())
        self.assertFalse(post.contributor_assignments.exists())
        self.assertNotIn('author_section_enabled', post.design_settings)

    def test_same_person_can_have_two_explicit_roles(self):
        profiles = extract_profiles(HTML + '<h2>Dr. Named Researcher</h2><p>Editor</p>')
        self.assertEqual([profile['role'] for profile in profiles], ['author', 'reviewer', 'editor'])

    def test_reuses_profiles_without_overwriting_curated_information(self):
        author = Author.objects.create(login='existing', display_name='Dr. Named Researcher', position='Chosen affiliation')
        post = Post.objects.create(title='Existing', slug='existing', content=HTML)
        self.restore(post)
        author.refresh_from_db()
        self.assertEqual(author.position, 'Chosen affiliation')
        self.assertEqual(author.avatar, 'https://resref.com/wp-content/uploads/portrait.png')
        self.assertEqual(Author.objects.filter(display_name=author.display_name).count(), 1)

    def test_bulk_preview_does_not_write_and_apply_skips_trash_and_pages(self):
        post = Post.objects.create(title='Keep', slug='keep', content=HTML)
        Post.objects.create(title='Trash', slug='trash', content=HTML, status='trash')
        Post.objects.create(title='Page', slug='page', content=HTML, post_type='page')
        call_command('import_legacy_contributors', '--all', stdout=StringIO())
        self.assertEqual(PostContributor.objects.count(), 0)
        call_command('import_legacy_contributors', '--all', '--apply', stdout=StringIO())
        self.assertEqual(set(PostContributor.objects.values_list('post_id', flat=True)), {post.pk})

    def test_data_migration_works_with_historical_models(self):
        post = Post.objects.create(title='Migration', slug='migration', content=HTML)
        state = MigrationLoader(connection).project_state([('blog', '0008_category_description_hero_image')])
        migration = import_module('blog.migrations.0009_restore_explicit_article_credits')
        migration.restore_explicit_credits(state.apps, SimpleNamespace(connection=connection))
        post.refresh_from_db()
        self.assertEqual(post.contributor_assignments.count(), 2)
        self.assertEqual(post.design_settings['author_section_enabled'], 'auto')
