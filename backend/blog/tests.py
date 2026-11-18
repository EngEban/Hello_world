from unittest.mock import Mock, patch

from django.core.cache import cache
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import UserToolWorkspace
from dashboard.models import ContactSubmission, DashboardActivityLog, ResearchOpportunity, SiteSettings
from .models import Author, Category, MediaAsset, Post, PostContributor
from .reference_lookup import normalize_isbn, search_references, split_name


def response_with(payload):
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


@override_settings(ALLOWED_HOSTS=['testserver'])
class ContributorPublicApiTests(TestCase):
    def setUp(self):
        self.author = Author.objects.create(
            login='ada-lovelace', display_name='Ada Lovelace', credentials='PhD',
            specialty='Research methods', is_active=True,
        )
        self.post = Post.objects.create(
            title='Contributor credit test', slug='contributor-credit-test', content='Content',
            excerpt='A credited article.', post_type='post', status='publish', published_at=timezone.now(),
        )
        PostContributor.objects.create(post=self.post, contributor=self.author, role='editor', contribution_note='Editorial review')
        self.post.authors.add(self.author)

    def test_post_exposes_structured_contributor_credit(self):
        response = self.client.get('/api/posts/contributor-credit-test/')
        self.assertEqual(response.status_code, 200)
        author = response.json()['post']['authors'][0]
        self.assertEqual(author['slug'], 'ada-lovelace')
        self.assertEqual(author['role'], 'editor')
        self.assertEqual(author['role_label'], 'Editor')

    def test_public_profile_excludes_email_and_lists_unique_articles(self):
        response = self.client.get('/api/authors/ada-lovelace/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('email', response.json()['author'])
        self.assertEqual(response.json()['contributions'][0]['post']['slug'], 'contributor-credit-test')

    def test_legacy_uploader_is_not_exposed_as_an_assigned_author(self):
        legacy = Post.objects.create(title='Legacy author', slug='legacy-author', content='<h2>Overview</h2>',
                                     status='publish', author=self.author, published_at=timezone.now())
        payload = self.client.get('/api/posts/legacy-author/').json()['post']
        self.assertEqual(payload['authors'], [])
        self.assertIn('updated_at', payload)
        profile = self.client.get('/api/authors/ada-lovelace/').json()
        self.assertNotIn(legacy.id, [item['post']['id'] for item in profile['contributions']])

    def test_sorting_preserves_pagination_and_excludes_unpublished(self):
        for title, slug, status in [('A first', 'a-first', 'publish'), ('Z last', 'z-last', 'publish'), ('A hidden', 'a-hidden', 'draft')]:
            Post.objects.create(title=title, slug=slug, status=status, content='test', published_at=timezone.now())
        payload = self.client.get('/api/posts/?sort=title&per_page=1&page=2').json()
        self.assertEqual(payload['pagination']['total_items'], 3)
        self.assertEqual(payload['pagination']['current_page'], 2)
        self.assertEqual(payload['results'][0]['slug'], self.post.slug)
        self.assertEqual(self.client.get('/api/posts/a-hidden/').status_code, 404)

    def test_category_tree_retains_visibility_and_counts_in_one_query(self):
        root = Category.objects.create(name='Medicine', slug='medicine')
        child = Category.objects.create(name='Heart', slug='heart', parent=root)
        hidden = Category.objects.create(name='Hidden', slug='hidden', show_in_database=False)
        Category.objects.create(name='Hidden child', slug='hidden-child', parent=hidden)
        self.post.categories.add(child)
        with self.assertNumQueries(1):
            response = self.client.get('/api/categories/')
        categories = response.json()['categories']
        self.assertEqual(len(categories), 1)
        self.assertEqual(categories[0]['slug'], 'medicine')
        self.assertEqual(categories[0]['children'][0]['post_count'], 1)


class ReferenceLookupTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(CROSSREF_POLITE_EMAIL='citations@example.com', OPENALEX_API_KEY='')
    @patch('blog.reference_lookup.requests.get')
    def test_doi_lookup_returns_structured_crossref_metadata(self, get):
        get.return_value = response_with({
            'message': {
                'type': 'journal-article',
                'title': ['Research methods'],
                'container-title': ['Medical Research Journal'],
                'short-container-title': ['Med Res J'],
                'issued': {'date-parts': [[2025]]},
                'author': [{'given': 'Ada', 'family': 'Lovelace'}],
                'volume': '12',
                'issue': '4',
                'page': '10-18',
                'DOI': '10.1234/example.1',
                'URL': 'https://doi.org/10.1234/example.1',
            },
        })

        results = search_references('https://doi.org/10.1234/example.1')

        self.assertEqual(results[0]['doi'], '10.1234/example.1')
        self.assertEqual(results[0]['journal_abbrev'], 'Med Res J')
        self.assertEqual(results[0]['authors'][0]['last'], 'Lovelace')
        self.assertIn('/v1/works/10.1234%2Fexample.1', get.call_args.args[0])
        self.assertEqual(get.call_args.kwargs['params']['mailto'], 'citations@example.com')

    @override_settings(CROSSREF_POLITE_EMAIL='', OPENALEX_API_KEY='')
    @patch('blog.reference_lookup.requests.get')
    def test_public_url_creates_manual_record_without_fetching_the_url(self, get):
        results = search_references('https://example.com/research/article')

        self.assertEqual(results[0]['source'], 'manual-url')
        self.assertEqual(results[0]['type'], 'website')
        self.assertEqual(results[0]['site'], 'example.com')
        get.assert_not_called()

    @override_settings(CROSSREF_POLITE_EMAIL='', OPENALEX_API_KEY='openalex-test-key')
    @patch('blog.reference_lookup.requests.get')
    def test_title_search_combines_crossref_and_optional_openalex(self, get):
        get.side_effect = [
            response_with({'message': {'items': [{
                'title': ['Crossref result'],
                'DOI': '10.1234/crossref',
                'issued': {'date-parts': [[2024]]},
            }]}}),
            response_with({'results': [{
                'title': 'OpenAlex result',
                'doi': 'https://doi.org/10.1234/openalex',
                'publication_year': 2023,
                'authorships': [{'author': {'display_name': 'Grace Hopper'}}],
            }]}),
        ]

        results = search_references('research title')

        self.assertEqual(len(results), 2)
        self.assertEqual({item['source'] for item in results}, {'crossref', 'openalex'})
        self.assertEqual(get.call_args_list[1].kwargs['params']['api_key'], 'openalex-test-key')

    @override_settings(CROSSREF_POLITE_EMAIL='', OPENALEX_API_KEY='')
    @patch('blog.reference_lookup.requests.get')
    def test_api_keeps_legacy_fields_and_returns_result_choices(self, get):
        get.return_value = response_with({'message': {'items': [{
            'title': ['Reference generator'],
            'container-title': ['ResRef Journal'],
            'DOI': '10.1234/resref',
            'issued': {'date-parts': [[2026]]},
            'author': [{'given': 'Research', 'family': 'Editor'}],
        }]}})

        response = self.client.get('/api/references/fetch/?q=Reference%20generator&type=journal')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['title'], 'Reference generator')
        self.assertEqual(data['results'][0]['type'], 'journal')
        self.assertEqual(data['reference']['doi'], '10.1234/resref')


@override_settings(ALLOWED_HOSTS=['testserver'])
class PublicSiteSettingsApiTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_public_endpoint_returns_only_allowlisted_settings(self):
        SiteSettings.objects.create(key='site_name', value='ResRef')
        SiteSettings.objects.create(key='contact_email', value='info@example.com')
        SiteSettings.objects.create(key='home_gateway_title', value='Configured public headline')
        SiteSettings.objects.create(key='stripe_secret_key', value='must-not-leak')

        response = self.client.get('/api/site-settings/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['settings'], {
            'site_name': 'ResRef',
            'contact_email': 'info@example.com',
            'home_gateway_title': 'Configured public headline',
        })
        self.assertNotIn('stripe_secret_key', response.json()['settings'])

    def test_dashboard_rejects_sensitive_setting_and_audits_attempt(self):
        admin = User.objects.create_superuser('settings-admin', 'settings@example.com', 'pass12345')
        self.client.force_login(admin)

        response = self.client.post(
            '/api/dashboard/settings/save/',
            data={'settings': [{'key': 'stripe_secret_key', 'value': 'must-not-store'}]},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('environment variables', response.json()['error'])
        self.assertFalse(SiteSettings.objects.filter(key='stripe_secret_key').exists())
        self.assertTrue(DashboardActivityLog.objects.filter(
            actor=admin, module='settings', action='system',
            metadata__setting_keys=['stripe_secret_key'],
        ).exists())

    def test_sensitive_batch_rejection_does_not_save_preceding_settings(self):
        admin = User.objects.create_superuser('settings-batch-admin', 'batch@example.com', 'pass12345')
        self.client.force_login(admin)

        response = self.client.post(
            '/api/dashboard/settings/save/',
            data={'settings': [
                {'key': 'site_name', 'value': 'Should not save'},
                {'key': 'api_token', 'value': 'must-not-store'},
            ]},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(SiteSettings.objects.filter(key='site_name').exists())


@override_settings(ALLOWED_HOSTS=['testserver'])
class UnifiedSearchApiTests(TestCase):
    password = 'Secur3-ResRef!Passphrase'

    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(name='Dermatology', slug='dermatology')
        self.post = Post.objects.create(
            title='Dermatology Questionnaire',
            slug='dermatology-questionnaire',
            content='Validated skin research instrument.',
            excerpt='Validated skin questionnaire.',
            post_type='post',
            status='publish',
            published_at=timezone.now(),
            seo_title='Dermatology research questionnaire',
            seo_description='Validated dermatology questionnaire for research.',
        )
        self.post.categories.add(self.category)

    def test_unified_search_keeps_public_post_search_and_filters(self):
        Post.objects.create(
            title='Draft Dermatology Resource',
            slug='draft-dermatology-resource',
            content='Draft content',
            post_type='post',
            status='draft',
            published_at=timezone.now(),
        )
        response = self.client.get('/api/search/?q=skin&content_type=post&category=dermatology')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['counts']['posts'], 1)
        self.assertEqual(data['results']['posts'][0]['title'], 'Dermatology Questionnaire')
        self.assertEqual(data['results']['posts'][0]['metadata']['seo_title'], 'Dermatology research questionnaire')
        self.assertIn('General file/document search is not available', data['limitations'][0])

    def test_user_search_is_admin_only_and_uses_profile_fields(self):
        target = User.objects.create_user(username='researcher', email='target@example.com', password=self.password)
        target.membership_profile.display_name = 'Clinical Methods Lead'
        target.membership_profile.specialization = 'Biostatistics'
        target.membership_profile.save(update_fields=['display_name', 'specialization', 'updated_at'])
        editor = User.objects.create_user(username='editor', email='editor@example.com', password=self.password, is_staff=True)
        editor.membership_profile.access_role = 'editor'
        editor.membership_profile.save(update_fields=['access_role', 'updated_at'])

        self.client.force_login(editor)
        response = self.client.get('/api/search/?q=Biostatistics&content_type=user')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results']['users'], [])

        admin = User.objects.create_user(username='admin', email='admin@example.com', password=self.password, is_staff=True)
        admin.membership_profile.access_role = 'admin'
        admin.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(admin)
        response = self.client.get('/api/search/?q=Biostatistics&content_type=user')

        self.assertEqual(response.status_code, 200)
        users = response.json()['results']['users']
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]['metadata']['display_name'], 'Clinical Methods Lead')
        self.assertEqual(users[0]['metadata']['specialization'], 'Biostatistics')

    def test_tool_search_uses_only_current_user_workspace(self):
        owner = User.objects.create_user(username='owner', email='owner@example.com', password=self.password)
        other = User.objects.create_user(username='other', email='other@example.com', password=self.password)
        UserToolWorkspace.objects.create(user=owner, tool_key='sample-size-calculator', data={'title': 'cohort design'})
        UserToolWorkspace.objects.create(user=other, tool_key='reference-generator', data={'title': 'hidden cohort'})

        self.client.force_login(owner)
        response = self.client.get('/api/search/?q=cohort&content_type=tool')

        self.assertEqual(response.status_code, 200)
        tools = response.json()['results']['tools']
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]['metadata']['owner_id'], owner.id)
        self.assertEqual(tools[0]['metadata']['tool_key'], 'sample-size-calculator')

    def test_media_search_requires_content_read_permission(self):
        MediaAsset.objects.create(title='Protocol figure', alt_text='CONSORT diagram', url='https://example.com/image.png')

        response = self.client.get('/api/search/?q=CONSORT&content_type=media')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results']['media'], [])

        editor = User.objects.create_user(username='editor', email='editor@example.com', password=self.password, is_staff=True)
        editor.membership_profile.access_role = 'editor'
        editor.membership_profile.save(update_fields=['access_role', 'updated_at'])
        self.client.force_login(editor)
        response = self.client.get('/api/search/?q=CONSORT&content_type=media')

        self.assertEqual(response.status_code, 200)
        media = response.json()['results']['media']
        self.assertEqual(len(media), 1)
        self.assertEqual(media[0]['title'], 'Protocol figure')

    def test_public_opportunities_are_searchable(self):
        ResearchOpportunity.objects.create(
            title='Remote methods role',
            slug='remote-methods-role',
            summary='Support methodology projects.',
            status='published',
            organization='ResRef',
            location='Remote',
        )

        response = self.client.get('/api/search/?q=methodology&content_type=opportunity')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results']['opportunities'][0]['title'], 'Remote methods role')


@override_settings(ALLOWED_HOSTS=['testserver'])
class ContactSubmitApiTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_contact_submission_validates_required_fields_and_email(self):
        response = self.client.post(
            '/api/contact/',
            data={'name': 'Research User', 'email': 'not-an-email', 'message': 'Need support.'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ContactSubmission.objects.exists())

    def test_contact_submission_rejects_whitespace_only_email(self):
        response = self.client.post(
            '/api/contact/',
            data={'name': 'Research User', 'email': '   ', 'message': 'Need support.'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ContactSubmission.objects.exists())

    def test_contact_submission_validates_optional_whatsapp_number(self):
        response = self.client.post(
            '/api/contact/',
            data={
                'name': 'Research User',
                'email': 'user@example.com',
                'whatsapp': 'abc123',
                'message': 'Need support.',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ContactSubmission.objects.exists())

    def test_contact_submission_trims_and_stores_valid_payload(self):
        response = self.client.post(
            '/api/contact/',
            data={
                'name': '  Research User  ',
                'email': '  USER@Example.COM ',
                'whatsapp': '  +971 55 997 7405  ',
                'message': '  Need support with a protocol. ',
                'company': ' Consultation ',
            },
        )

        self.assertEqual(response.status_code, 201)
        submission = ContactSubmission.objects.get()
        self.assertEqual(submission.name, 'Research User')
        self.assertEqual(submission.email, 'user@example.com')
        self.assertEqual(submission.whatsapp, '+971 55 997 7405')
        self.assertEqual(submission.message, 'Need support with a protocol.')

    def test_contact_submission_is_rate_limited_by_email(self):
        payload = {'name': 'Research User', 'email': 'rate@example.com', 'message': 'Need support.'}

        for _ in range(8):
            self.assertEqual(self.client.post('/api/contact/', data=payload).status_code, 201)
        response = self.client.post('/api/contact/', data=payload)

        self.assertEqual(response.status_code, 429)



class ReferenceLookupMeteringTests(TestCase):
    """T-12: successful lookups by signed-in users count; anonymous use does not."""

    def setUp(self):
        cache.clear()

    @patch('blog.api_views.search_references', return_value=[{'title': 'A study', 'authors': [], 'year': '2026'}])
    def test_signed_in_lookups_are_metered(self, _search):
        from accounts.models import UsageLimit, UsageRecord
        UsageLimit.objects.update_or_create(
            feature_code='reference_generator', tier='free', period='day',
            defaults={'limit': 1, 'is_active': True},
        )
        for _ in range(3):
            self.assertEqual(self.client.get('/api/references/fetch/', {'q': '10.1000/xyz'}).status_code, 200)
        self.assertFalse(UsageRecord.objects.exists())

        user = User.objects.create_user('ref-limit@example.com', 'ref-limit@example.com', 'Secur3-ResRef!Passphrase')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/api/references/fetch/', {'q': '10.1000/xyz'}).status_code, 200)
        blocked = self.client.get('/api/references/fetch/', {'q': '10.1000/xyz'})
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json()['code'], 'usage_limit')
        self.assertEqual(UsageRecord.objects.filter(user=user, feature_code='reference_generator').count(), 1)

    @patch('blog.api_views.search_references', return_value=[])
    def test_failed_lookups_do_not_count(self, _search):
        from accounts.models import UsageRecord
        user = User.objects.create_user('ref-miss@example.com', 'ref-miss@example.com', 'Secur3-ResRef!Passphrase')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/api/references/fetch/', {'q': 'nothing'}).status_code, 404)
        self.assertFalse(UsageRecord.objects.exists())


class PublicSiteSettingsTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_normal_browsing_from_one_address_is_not_throttled(self):
        for _ in range(100):
            response = self.client.get('/api/site-settings/')
            self.assertEqual(response.status_code, 200)
        self.assertIn('max-age', response['Cache-Control'])


@override_settings(CROSSREF_POLITE_EMAIL='', OPENALEX_API_KEY='')
class ReferenceIdentifierLookupTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch('blog.reference_lookup.requests.get')
    def test_chapter_doi_keeps_its_type_and_fills_book_title(self, get):
        get.return_value = response_with({'message': {
            'type': 'book-chapter',
            'title': ['Sampling methods'],
            'container-title': ['Handbook of Epidemiology'],
            'publisher': 'Springer',
            'editor': [{'given': 'Ana', 'family': 'Silva'}],
            'issued': {'date-parts': [[2021]]},
            'author': [{'given': 'Omar', 'family': 'Haddad'}],
            'DOI': '10.1007/978-0-387-09834-0_1',
        }})

        record = search_references('10.1007/978-0-387-09834-0_1', 'journal')[0]

        self.assertEqual(record['type'], 'chapter')
        self.assertEqual(record['booktitle'], 'Handbook of Epidemiology')
        self.assertEqual(record['journal'], '')
        self.assertEqual(record['editors'], 'Ana Silva')

    @patch('blog.reference_lookup.requests.get')
    def test_doi_missing_from_crossref_falls_back_to_doi_org(self, get):
        not_found = Mock(status_code=404)
        csl = response_with({'type': 'article', 'title': 'A preprint', 'author': [{'given': 'Lin', 'family': 'Wei'}],
                             'issued': {'date-parts': [[2023]]}, 'publisher': 'arXiv', 'DOI': '10.48550/arXiv.2301.00001'})
        get.side_effect = [not_found, csl]

        record = search_references('https://doi.org/10.48550/arXiv.2301.00001')[0]

        self.assertEqual(record['title'], 'A preprint')
        self.assertEqual(record['source'], 'doi.org')
        self.assertEqual(record['site'], 'arXiv')
        self.assertIn('citationstyles', get.call_args_list[1].kwargs['headers']['Accept'])

    @patch('blog.reference_lookup.requests.get')
    def test_pmid_lookup_uses_pubmed_summary(self, get):
        get.return_value = response_with({'result': {'31452104': {
            'title': 'Hypertension in rural clinics.',
            'fulljournalname': 'BMC Public Health',
            'source': 'BMC Public Health',
            'pubdate': '2019 Aug 26',
            'volume': '19', 'issue': '1', 'pages': '1154',
            'authors': [{'name': 'Smith JA', 'authtype': 'Author'}, {'name': 'WHO Study Group', 'authtype': 'CollectiveName'}],
            'articleids': [{'idtype': 'doi', 'value': '10.1186/s12889-019-7487-3'}],
        }}})

        record = search_references('PMID: 31452104')[0]

        self.assertEqual(record['source'], 'pubmed')
        self.assertEqual(record['title'], 'Hypertension in rural clinics')
        self.assertEqual(record['year'], '2019')
        self.assertEqual(record['doi'], '10.1186/s12889-019-7487-3')
        self.assertEqual(record['authors'], [{'first': 'J A', 'middle': '', 'last': 'Smith'}])
        self.assertIn('esummary', get.call_args.args[0])

    @patch('blog.reference_lookup.requests.get')
    def test_isbn_lookup_uses_open_library_and_checks_the_check_digit(self, get):
        get.return_value = response_with({'ISBN:9780198529996': {
            'title': 'Medical statistics', 'publishers': [{'name': 'Oxford University Press'}],
            'publish_date': '2005', 'authors': [{'name': 'Douglas Altman'}], 'url': 'https://openlibrary.org/books/x',
        }})

        record = search_references('ISBN 978-0-19-852999-6')[0]

        self.assertEqual(record['type'], 'book')
        self.assertEqual(record['publisher'], 'Oxford University Press')
        self.assertEqual(record['authors'][0]['last'], 'Altman')
        self.assertEqual(normalize_isbn('978-0-19-852999-5'), '')
        self.assertEqual(normalize_isbn('0-19-852999-X'), '')
        self.assertEqual(normalize_isbn('0306406152'), '0306406152')
        self.assertEqual(split_name('Tom Burns M.D.'), {'first': 'Tom', 'middle': '', 'last': 'Burns'})
