"""Server-rendered SEO, robots.txt, sitemap.xml and llms.txt (resref/seo.py)."""

import json
import os
import re
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from blog.models import Author, Category, Post, PostContributor
from dashboard.models import FAQCategory, FAQItem
from resref import seo

SHELL = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <!-- resref:seo:start -->
    <title>ResRef</title>
    <!-- resref:seo:end -->
    <script type="module" src="/static/assets/index-abc.js"></script>
  </head>
  <body>
    <div id="root"></div>
    <!-- resref:noscript -->
  </body>
</html>
"""

ENV = {'SEO_SITE_URL': 'https://resref.test', 'SEO_ALLOW_INDEXING': 'true', 'SEO_AI_CRAWLERS': 'allow',
       'GA_MEASUREMENT_ID': '', 'GOOGLE_SITE_VERIFICATION': '', 'BING_SITE_VERIFICATION': ''}


class SeoTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.dist = tempfile.TemporaryDirectory()
        Path(self.dist.name, 'index.html').write_text(SHELL, encoding='utf-8')
        self.settings_override = override_settings(SERVE_FRONTEND_FROM_DJANGO=True, FRONTEND_DIST_DIR=Path(self.dist.name))
        self.settings_override.enable()
        self.env = mock.patch.dict(os.environ, ENV)
        self.env.start()
        now = timezone.now()
        self.category = Category.objects.create(name='Cardiology', slug='cardiology', description='Heart research resources.')
        self.author = Author.objects.create(login='dr-a', display_name='Dr Amal Hassan', slug='amal-hassan',
                                            orcid='https://orcid.org/0000-0000-0000-0001', position='Cardiologist',
                                            institution='Cairo University', bio='Researcher in cardiology.')
        self.post = Post.objects.create(
            title='Heart failure scales', slug='heart-failure-scales', excerpt='Validated scales for heart failure.',
            content='<h2>Overview</h2><p>Scales help.</p><h2>Choosing a scale</h2><p>Pick one.</p>'
                    '<script>alert(1)</script><p>&lt;/noscript&gt;<b>bold</b></p>',
            published_at=now - timedelta(days=2))
        self.post.categories.add(self.category)
        PostContributor.objects.create(post=self.post, contributor=self.author, role='author')
        Post.objects.create(title='Draft idea', slug='draft-idea', content='x', status='draft', published_at=now)
        Post.objects.create(title='Private note', slug='private-note', content='x', status='private', published_at=now)
        Post.objects.create(title='Binned', slug='binned', content='x', status='trash', published_at=now)
        Post.objects.create(title='Scheduled', slug='scheduled', content='x', published_at=now + timedelta(days=3))
        Post.objects.create(title='Mission page', slug='mission', post_type='page', content='<p>Our mission.</p>', published_at=now)

    def tearDown(self):
        self.env.stop()
        self.settings_override.disable()
        self.dist.cleanup()
        seo._shell_cache.update(mtime=None, html='')

    def json_ld(self, response):
        match = re.search(r'<script data-seo="server" type="application/ld\+json">(.*?)</script>', response.content.decode(), re.S)
        self.assertIsNotNone(match)
        return json.loads(match.group(1))

    def nodes(self, response, node_type):
        return [node for node in self.json_ld(response)['@graph'] if node.get('@type') == node_type]


class SpaMetadataTests(SeoTestCase):
    def test_home_has_entity_graph_canonical_and_social_cards(self):
        response = self.client.get('/')
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-cache')
        self.assertIn('<title data-seo="server">ResRef — Research Resources, Tools &amp; Support</title>', html)
        self.assertIn('<link data-seo="server" rel="canonical" href="https://resref.test/" />', html)
        self.assertIn('property="og:image" content="https://resref.test/static/og-default.png"', html)
        self.assertIn('name="twitter:card" content="summary_large_image"', html)
        self.assertIn('content="index, follow', html)
        self.assertNotIn('X-Robots-Tag', response)
        organization = self.nodes(response, 'Organization')[0]
        self.assertEqual(organization['description'], seo.ORGANIZATION_DESCRIPTION)
        website = self.nodes(response, 'WebSite')[0]
        self.assertEqual(website['potentialAction']['target']['urlTemplate'], 'https://resref.test/database?q={search_term_string}')
        self.assertIn('<noscript><main>', html)
        self.assertIn('href="/database/cardiology/heart-failure-scales"', html)

    def test_resref_profile_credits_the_organization(self):
        resref = Author.objects.create(login='resref', display_name='ResRef', slug='resref')
        PostContributor.objects.create(post=self.post, contributor=resref, role='author', display_order=1)
        response = self.client.get('/database/cardiology/heart-failure-scales')
        authors = self.nodes(response, 'Article')[0]['author']
        self.assertEqual(authors[0]['name'], 'Dr Amal Hassan')
        self.assertEqual(authors[1], {'@id': 'https://resref.test/#organization'})
        self.assertIn('By Dr Amal Hassan, ResRef', response.content.decode())

    def test_article_metadata_structured_data_and_safe_noscript_text(self):
        response = self.client.get('/database/cardiology/heart-failure-scales')
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('<title data-seo="server">Heart failure scales | ResRef</title>', html)
        self.assertIn('property="og:type" content="article"', html)
        self.assertIn('property="article:published_time"', html)
        article = self.nodes(response, 'Article')[0]
        self.assertEqual(article['author'][0]['name'], 'Dr Amal Hassan')
        self.assertEqual(article['author'][0]['url'], 'https://resref.test/authors/amal-hassan')
        self.assertEqual(article['publisher'], {'@id': 'https://resref.test/#organization'})
        self.assertIn('datePublished', article)
        self.assertIn('dateModified', article)
        crumbs = self.nodes(response, 'BreadcrumbList')[0]['itemListElement']
        self.assertEqual([item['name'] for item in crumbs], ['Home', 'Database', 'Cardiology', 'Heart failure scales'])
        noscript = html.split('<noscript>', 1)[1].split('</noscript>', 1)[0]
        self.assertIn('<li>Choosing a scale</li>', noscript)  # contents list from headings
        self.assertNotIn('<script', noscript)
        self.assertNotIn('alert(1)', noscript)
        self.assertIn('&lt;/noscript&gt;bold', noscript)

    def test_stored_markup_is_escaped_in_head_and_json_ld(self):
        Post.objects.filter(pk=self.post.pk).update(
            seo_title='p < 0.05 "significant"<script>alert(1)</script>', seo_description='</script><script>alert(2)</script> & more')
        html = self.client.get('/database/cardiology/heart-failure-scales').content.decode()
        head = html.split('</head>', 1)[0]
        self.assertNotIn('<script>alert', head)
        self.assertNotIn('</script><script>', head)
        self.assertIn('<title data-seo="server">p &lt; 0.05 &quot;significant&quot; | ResRef</title>', head)
        self.assertIn('"name":"p \\u003c 0.05', head)

    def test_non_canonical_article_addresses_redirect_permanently(self):
        response = self.client.get('/database/other/heart-failure-scales?ref=x')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/database/cardiology/heart-failure-scales?ref=x')
        response = self.client.get('/heart-failure-scales')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/database/cardiology/heart-failure-scales')

    def test_unpublished_and_unknown_urls_are_404_noindex(self):
        for path in ('/database/cardiology/draft-idea', '/private-note', '/binned', '/scheduled',
                     '/qa-no-such-page', '/database/no-such-topic', '/authors/nobody', '/a/b/c'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404, path)
            self.assertEqual(response['X-Robots-Tag'], 'noindex, follow', path)
            self.assertIn('Page Not Found | ResRef', response.content.decode(), path)
            self.assertNotIn('rel="canonical"', response.content.decode(), path)
            self.assertIn('<div id="root">', response.content.decode(), path)  # the SPA still renders

    def test_old_and_broken_addresses_reach_the_right_page(self):
        article = '/database/cardiology/heart-failure-scales'
        self.assertEqual(self.client.get('/heart-failure-')['Location'], article)
        self.assertEqual(self.client.get('/heart-failure-scales/someone@example.org')['Location'], '/heart-failure-scales')
        self.assertEqual(self.client.get('/page/privacy-policy')['Location'], '/privacy-policy')
        self.assertEqual(self.client.get('/author/amal-hassan')['Location'], '/authors/amal-hassan')
        self.assertEqual(self.client.get('/author/nobody').status_code, 404)
        # Too short, or matching nothing: still a plain 404, with no redirect first.
        self.assertEqual(self.client.get('/heart').status_code, 404)
        self.assertEqual(self.client.get('/no-such-article-at-all/').status_code, 404)
        self.assertEqual(self.client.get('/about/')['Location'], '/about')
        for path in ('/category/cardiology/feed/', '/wp-includes/js/wp-emoji-release.min.js', '/upload/123.m3u8', '/author/x/feed'):
            self.assertEqual(self.client.get(path).status_code, 410, path)
        self.assertEqual(self.client.get('/feedback-scales').status_code, 404)
        self.assertEqual(self.client.get('/favicon.ico')['Location'], '/static/favicon.ico')

    def test_www_pages_move_to_the_main_address(self):
        with override_settings(PUBLIC_HOSTNAME='resref.com', ALLOWED_HOSTS=['resref.com', 'www.resref.com']):
            response = self.client.get('/about?x=1', HTTP_HOST='www.resref.com')
            self.assertEqual(response.status_code, 301)
            self.assertEqual(response['Location'], 'http://resref.com/about?x=1')
            self.assertEqual(self.client.get('/about', HTTP_HOST='resref.com').status_code, 200)
            self.assertNotEqual(self.client.post('/api/v1/', HTTP_HOST='www.resref.com').status_code, 301)

    def test_trailing_slash_and_aliases_redirect_without_leaving_the_site(self):
        self.assertEqual(self.client.get('/about/')['Location'], '/about')
        self.assertEqual(self.client.get('/about-us/')['Location'], '/about')
        self.assertEqual(self.client.get('/about-us/?cat=x')['Location'], '/about?cat=x')
        self.assertEqual(self.client.get('/about-us?x=1')['Location'], '/about?x=1')
        self.assertEqual(self.client.get('/home').status_code, 301)
        from django.test import RequestFactory
        response = seo.spa_response(RequestFactory().get('/'), Path(self.dist.name, 'index.html'), '//evil.example/')
        # A page that does not exist answers 404 here and never redirects to another host.
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('Location', response)

    def test_private_search_and_gated_pages_are_noindex(self):
        for path in ('/sign-in', '/register', '/account', '/account/reset-password', '/database?q=heart'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn('noindex', response['X-Robots-Tag'], path)
        dashboard = self.client.get('/dashboard/posts')
        self.assertEqual(dashboard['X-Robots-Tag'], 'noindex, nofollow')

    def test_listing_canonical_keeps_page_number_only(self):
        html = self.client.get('/database/cardiology?page=2&sort=title').content.decode()
        self.assertIn('rel="canonical" href="https://resref.test/database/cardiology?page=2"', html)
        self.assertEqual(len(self.nodes(self.client.get('/database/cardiology'), 'CollectionPage')), 1)

    def test_author_profile_person_and_page_canonical(self):
        response = self.client.get('/authors/amal-hassan')
        person = self.nodes(response, 'Person')[0]
        self.assertEqual(person['sameAs'], ['https://orcid.org/0000-0000-0000-0001'])
        self.assertEqual(person['affiliation']['name'], 'Cairo University')
        self.assertEqual(self.nodes(response, 'ProfilePage')[0]['mainEntity'], {'@id': person['@id']})
        page = self.client.get('/mission').content.decode()
        self.assertIn('rel="canonical" href="https://resref.test/mission"', page)
        self.assertIn('rel="canonical" href="https://resref.test/mission"', self.client.get('/page/mission').content.decode())
        # A page whose slug belongs to an application route keeps the /page/ address.
        Post.objects.create(title='Old about', slug='about', post_type='page', content='x', published_at=timezone.now())
        self.assertIn('rel="canonical" href="https://resref.test/page/about"', self.client.get('/page/about').content.decode())

    def test_faq_page_lists_published_questions(self):
        group = FAQCategory.objects.create(name='General', slug='general')
        FAQItem.objects.create(category=group, question='Is the QA test question answered?', answer='<p>Yes, the database is free.</p>')
        FAQItem.objects.create(category=group, question='Hidden?', answer='No', status='hidden')
        faq = self.nodes(self.client.get('/faq'), 'FAQPage')[0]
        answers = {q['name']: q['acceptedAnswer']['text'] for q in faq['mainEntity']}
        self.assertEqual(answers['Is the QA test question answered?'], 'Yes, the database is free.')
        self.assertNotIn('Hidden?', answers)

    def test_indexing_disabled_marks_every_page_noindex(self):
        with mock.patch.dict(os.environ, {'SEO_ALLOW_INDEXING': 'false'}):
            response = self.client.get('/')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.assertIn('name="robots" content="noindex, nofollow"', response.content.decode())

    def test_analytics_and_verification_tags_only_when_configured(self):
        html = self.client.get('/').content.decode()
        self.assertNotIn('resref:ga-id', html)
        self.assertNotIn('google-site-verification', html)
        env = {'GA_MEASUREMENT_ID': 'G-ABC123XYZ9', 'GOOGLE_SITE_VERIFICATION': 'abcDEF_123-token',
               'BING_SITE_VERIFICATION': '0123456789ABCDEF0123456789ABCDEF'}
        with mock.patch.dict(os.environ, env), override_settings(RESREF_CSP_ENABLED=True, RESREF_CSP_REPORT_ONLY=False,
                                                                  RESREF_CONTENT_SECURITY_POLICY="default-src 'self'; script-src 'self'; connect-src 'self'"):
            response = self.client.get('/')
        html = response.content.decode()
        self.assertIn('<meta name="resref:ga-id" content="G-ABC123XYZ9" />', html)
        self.assertIn('<meta name="google-site-verification" content="abcDEF_123-token" />', html)
        self.assertIn('<meta name="msvalidate.01"', html)
        csp = response['Content-Security-Policy']
        self.assertIn("script-src 'self' https://www.googletagmanager.com", csp)
        self.assertIn('https://*.google-analytics.com', csp)
        with mock.patch.dict(os.environ, {'GA_MEASUREMENT_ID': '"><script>', 'GOOGLE_SITE_VERIFICATION': '"><b>'}):
            html = self.client.get('/').content.decode()
        self.assertNotIn('resref:ga-id', html)
        self.assertNotIn('google-site-verification', html)

    def test_database_failure_falls_back_to_generic_metadata(self):
        with mock.patch.object(seo, 'resolve', side_effect=RuntimeError('db down')), self.assertLogs('resref.seo', 'ERROR'):
            response = self.client.get('/database/cardiology/heart-failure-scales')
        self.assertEqual(response.status_code, 200)
        self.assertIn('<div id="root">', response.content.decode())

    def test_build_without_markers_still_gets_metadata(self):
        Path(self.dist.name, 'index.html').write_text('<html><head><title>ResRef</title></head><body><div id="root"></div></body></html>', encoding='utf-8')
        seo._shell_cache.update(mtime=None, html='')
        html = self.client.get('/about').content.decode()
        self.assertIn('About ResRef — Our Mission, Team &amp; Platform Story', html)
        self.assertEqual(html.count('<title'), 1)

    def test_static_titles_match_frontend_constants(self):
        source = Path(__file__).resolve().parents[2] / 'frontend' / 'src' / 'config' / 'contentStructure.js'
        if not source.is_file():
            self.skipTest('frontend sources not present')
        text = source.read_text(encoding='utf-8')
        for path in ('/', '/tools', '/consultation', '/opportunities', '/join', '/about', '/contact', '/faq'):
            title, description, *_rest = seo.STATIC_PAGES[path]
            self.assertIn(f"title: '{title}'", text, path)
            self.assertIn(description, text, path)

    def test_tool_pages_carry_their_guide_app_data_and_faq(self):
        response = self.client.get('/tools/sample-size-calculator')
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('How to use the Sample Size Calculator', html)
        self.assertIn('Frequently asked questions', html)
        app = self.nodes(response, 'WebApplication')[0]
        self.assertEqual(app['name'], 'Sample Size Calculator')
        self.assertEqual(app['offers']['price'], '0')
        faq = self.nodes(response, 'FAQPage')[0]
        self.assertGreaterEqual(len(faq['mainEntity']), 3)
        hub = self.client.get('/tools').content.decode()
        self.assertIn('href="/tools/research-analyzer"', hub)

    def test_indexnow_key_file_and_ping_after_publish(self):
        from resref import indexnow
        with override_settings(INDEXNOW_KEY='0123456789abcdef0123456789abcdef'):
            self.assertEqual(self.client.get('/0123456789abcdef0123456789abcdef.txt').content, b'0123456789abcdef0123456789abcdef')
            self.assertEqual(self.client.get('/ffffffffffffffffffffffffffffffff.txt').status_code, 404)
            with mock.patch.object(indexnow, 'indexing_allowed', return_value=True),                     mock.patch.object(indexnow.threading, 'Thread', side_effect=lambda target, args, daemon: mock.Mock(start=lambda: target(*args))),                     mock.patch.object(indexnow.requests, 'post', return_value=mock.Mock(status_code=200)) as post:
                with self.captureOnCommitCallbacks(execute=True):
                    indexnow.notify_posts([self.post, Post.objects.get(slug='draft-idea')])
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['urlList'], ['https://resref.test/database/cardiology/heart-failure-scales'])
        self.assertEqual(payload['keyLocation'], 'https://resref.test/0123456789abcdef0123456789abcdef.txt')


class CrawlerFileTests(SeoTestCase):
    def test_robots_txt_allows_public_content_and_rendering_apis(self):
        body = self.client.get('/robots.txt').content.decode()
        self.assertIn('Disallow: /dashboard', body)
        self.assertIn('Disallow: /.railway/', body)
        self.assertIn('Disallow: /api/', body)
        self.assertIn('Allow: /api/posts/', body)
        self.assertIn('Sitemap: https://resref.test/sitemap.xml', body)
        self.assertNotIn('GPTBot', body)  # AI crawlers allowed by default
        from django.conf import settings
        self.assertNotIn(settings.ADMIN_URL_PATH.strip('/'), body.replace('/api/', ''))

    def test_robots_txt_ai_policy_and_disabled_indexing(self):
        with mock.patch.dict(os.environ, {'SEO_AI_CRAWLERS': 'search-only'}):
            body = self.client.get('/robots.txt').content.decode()
        self.assertIn('User-agent: GPTBot\nDisallow: /', body)
        self.assertNotIn('OAI-SearchBot', body)
        with mock.patch.dict(os.environ, {'SEO_AI_CRAWLERS': 'block'}):
            self.assertIn('User-agent: OAI-SearchBot', self.client.get('/robots.txt').content.decode())
        with mock.patch.dict(os.environ, {'SEO_ALLOW_INDEXING': 'false'}):
            self.assertIn('User-agent: *\nDisallow: /', self.client.get('/robots.txt').content.decode())

    def test_sitemap_lists_only_public_canonical_urls(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response['Content-Type'], 'application/xml; charset=utf-8')
        body = response.content.decode()
        self.assertIn('<loc>https://resref.test/database/cardiology/heart-failure-scales</loc><lastmod>', body)
        self.assertIn('<loc>https://resref.test/database/cardiology</loc>', body)
        self.assertIn('<loc>https://resref.test/authors/amal-hassan</loc>', body)
        self.assertIn('<loc>https://resref.test/mission</loc>', body)
        self.assertIn('<loc>https://resref.test/faq</loc>', body)
        for hidden in ('draft-idea', 'private-note', 'binned', 'scheduled', '/dashboard', '/account', '/sign-in'):
            self.assertNotIn(hidden, body)
        # Tools are open to everyone, so they are indexed and listed.
        self.assertIn('<loc>https://resref.test/tools/journal-finder</loc>', body)
        for hidden in ():
            self.assertNotIn(hidden, body)

    def test_llms_txt_describes_site_and_links_articles(self):
        body = self.client.get('/llms.txt').content.decode()
        self.assertTrue(body.startswith('# ResRef\n\n> ' + seo.ORGANIZATION_DESCRIPTION))
        self.assertIn('[Heart failure scales](https://resref.test/database/cardiology/heart-failure-scales)', body)
        self.assertNotIn('Draft idea', body)
        full = self.client.get('/llms-full.txt').content.decode()
        self.assertIn('Authors: Dr Amal Hassan', full)
        self.assertIn('Sections: Overview; Choosing a scale', full)
