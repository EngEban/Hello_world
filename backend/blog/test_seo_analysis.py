"""SEO / AEO / GEO analysis (blog/seo_analysis.py) and the dashboard endpoints built on it."""

import json
import os
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from blog.models import Author, Category, Post, PostContributor, Tag
from blog.seo_analysis import analyze, clean_seo_settings, extract_faq, extract_references, load_cases, parse_html, report_for

NOW = '2026-10-27T00:00:00Z'


def words(count, sentence='Researchers collect careful data and report clear results.'):
    per = len(sentence.split())
    return ' '.join([sentence] * (count // per + 1))


def statuses(**data):
    return analyze({'now': NOW, 'updated_at': NOW, 'published_at': NOW, 'site_host': 'resref.com', **data})['checks']


class SharedCasesTests(TestCase):
    """The browser (seoAnalysis.js) and the server must score the same article identically."""

    def test_python_matches_the_cases_the_frontend_also_checks(self):
        for case in load_cases():
            with self.subTest(case=case['name']):
                report = analyze(case['input'])
                expected = case['expected']
                self.assertEqual(report['checks'], expected['checks'])
                self.assertEqual(report['scores'], expected['scores'])
                self.assertEqual(report['words'], expected['words'])
                self.assertEqual(report['language'], expected['language'])
                self.assertEqual(len(report['faq']), expected['faq'])
                self.assertEqual(len(report['references']), expected['references'])


class ThresholdTests(TestCase):
    def test_text_length_follows_yoast_post_and_cornerstone_minimums(self):
        def length(count, cornerstone=False):
            return statuses(content=f'<p>{" ".join(["word"] * count)}</p>', cornerstone=cornerstone)['text_length']
        self.assertEqual(length(300), 'good')
        self.assertEqual(length(260), 'warn')
        self.assertEqual(length(249), 'bad')
        self.assertEqual(length(600, cornerstone=True), 'warn')
        self.assertEqual(length(900, cornerstone=True), 'good')
        self.assertEqual(length(399, cornerstone=True), 'bad')

    def test_meta_description_window_is_120_to_156_characters(self):
        body = '<p>Cohort studies follow groups of people over time to compare outcomes between exposures.</p>'
        base = 'Cohort studies follow groups of people over time to compare outcomes between exposures '
        self.assertEqual(statuses(title='Cohort studies', content=body, seo_description='')['meta_description'], 'bad')
        self.assertEqual(statuses(title='Cohort studies', content=body, seo_description=base[:100])['meta_description'], 'warn')
        good = base + 'so readers can weigh risks, causes and results with confidence.'
        self.assertTrue(120 <= len(good) <= 156, len(good))
        self.assertEqual(statuses(title='Cohort studies', content=body, seo_description=good)['meta_description'], 'good')
        self.assertEqual(statuses(title='Cohort studies', content=body, seo_description=(base * 3)[:170])['meta_description'], 'warn')

    def test_copied_seo_title_and_description_are_flagged_as_mismatches(self):
        checks = statuses(
            title='Mini Nutritional Assessment (MNA): A Full Guide', excerpt='The MNA screens older adults for malnutrition.',
            content='<p>The Mini Nutritional Assessment screens older adults for malnutrition risk in care homes.</p>',
            seo_title='Quality of Life in Reflux and Dyspepsia (QOLRAD): Expert Guide',
            seo_description='Explore the Quality of Life in Reflux and Dyspepsia(QOLRAD) for measuring HRQOL in reflux and dyspepsia patients.',
        )
        self.assertEqual(checks['seo_title'], 'bad')
        self.assertEqual(checks['meta_description'], 'bad')

    def test_rendered_title_includes_the_site_suffix(self):
        # 52 characters + " | ResRef" (9) = 61: over Google's ~60 character display.
        self.assertEqual(statuses(title='x' * 52)['title_length'], 'warn')
        self.assertEqual(statuses(title='x' * 51)['title_length'], 'good')

    def test_keyphrase_checks_wait_for_a_keyphrase_and_density_caps_at_three_percent(self):
        without = statuses(title='Sample size', content=f'<p>{words(400)}</p>')
        self.assertEqual(without['keyphrase'], 'bad')
        self.assertEqual(without['keyphrase_density'], 'na')
        stuffed = statuses(title='Sample size', focus_keyphrase='sample size', content='<p>' + 'Sample size matters. ' * 60 + '</p>')
        self.assertEqual(stuffed['keyphrase_density'], 'bad')
        balanced = statuses(title='Sample size guide', focus_keyphrase='sample size',
                            content='<p>' + 'A sample size estimate needs care. ' + words(300) + '</p>' + '<p>The sample size depends on power.</p>')
        self.assertEqual(balanced['keyphrase_density'], 'good')
        self.assertEqual(balanced['keyphrase_in_title'], 'good')

    def test_development_and_malformed_links_are_broken(self):
        checks = statuses(content='<p><a href="http://resres.local/x">old</a> <a href="https://doi:10.1037/abc">doi</a></p>')
        self.assertEqual(checks['link_health'], 'bad')
        self.assertEqual(checks['internal_links'], 'bad')
        self.assertEqual(statuses(content='<p><a href="https://www.resref.com/tools">tools</a></p>')['internal_links'], 'good')

    def test_language_specific_readability_checks_skip_arabic(self):
        checks = statuses(content='<p>' + 'يقوم الباحث بجمع البيانات وتحليلها بعناية. ' * 40 + '</p>')
        self.assertEqual(checks['transition_words'], 'na')
        self.assertEqual(checks['reading_ease'], 'na')
        self.assertNotEqual(checks['sentence_length'], 'na')


class ExtractionTests(TestCase):
    def test_faq_answers_in_strong_and_line_break_format(self):
        html = ('<h2>Frequently Asked Questions (FAQ)</h2><ol><li><strong>Who can use the VLQ-2?</strong><br />Clinicians and researchers.</li>'
                '<li><strong>2. How long does it take?</strong> About ten minutes.</li></ol><h2>References</h2>'
                '<ol><li>Wilson, K. (2010). The questionnaire. <a href="https://doi.org/10.1007/BF03395706">Link</a></li></ol>')
        document = parse_html(html)
        faq = extract_faq(document.blocks)
        self.assertEqual([item['question'] for item in faq['items']], ['Who can use the VLQ-2?', 'How long does it take?'])
        self.assertEqual(faq['items'][1]['answer'], 'About ten minutes.')
        self.assertEqual(extract_references(document.blocks, document.links)['links'], ['https://doi.org/10.1007/BF03395706'])

    def test_settings_are_cleaned(self):
        self.assertEqual(clean_seo_settings({'focus_keyphrase': '  Cohort   study ', 'related_keyphrases': 'a, b,, c, d, e', 'cornerstone': 'yes'}),
                         {'focus_keyphrase': 'Cohort study', 'related_keyphrases': ['a', 'b', 'c', 'd'], 'cornerstone': False})
        self.assertEqual(clean_seo_settings('nonsense'), {'focus_keyphrase': '', 'related_keyphrases': [], 'cornerstone': False})


class DashboardSeoApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser('seo-admin', password='test-only-password')
        self.client.force_login(self.admin)
        self.category = Category.objects.create(name='Methods', slug='methods')
        self.tag = Tag.objects.create(name='Power', slug='power')
        self.author = Author.objects.create(login='writer', display_name='Writer')
        self.weak = Post.objects.create(title='Draft', slug='draft', content='<p>Short.</p>', status='draft')
        self.strong = Post.objects.create(
            title='Sample size calculation guide', slug='sample-size-calculation', excerpt='How to calculate a sample size for a clinical study.',
            content=('<h2>What is a sample size calculation?</h2><p>A sample size calculation estimates how many participants a study needs '
                     'to detect a meaningful effect with enough statistical power, so researchers avoid underpowered trials and wasted effort.</p>'
                     f'<p>{words(320)}</p><ul><li>Power</li></ul><p><a href="/tools">Tools</a> <a href="https://doi.org/10/x">Study</a></p>'),
            featured_image='https://example.com/a.png', published_at=timezone.now() - timedelta(days=2),
            design_settings={'seo': {'focus_keyphrase': 'sample size calculation'}},
        )
        self.strong.categories.add(self.category)
        self.strong.tags.add(self.tag)
        PostContributor.objects.create(post=self.strong, contributor=self.author, role='author')

    def test_library_rows_carry_scores_and_new_filters_work(self):
        data = self.client.get('/api/dashboard/posts/?summary_only=true').json()
        rows = {row['id']: row for row in data['results']}
        self.assertIsNotNone(rows[self.strong.pk]['optimization']['scores']['overall'])
        self.assertIn('keyphrase', rows[self.weak.pk]['optimization']['issues'])
        self.assertEqual(data['attention']['keyphrase'], 1)
        ids = lambda query: [row['id'] for row in self.client.get(f'/api/dashboard/posts/{query}').json()['results']]
        self.assertEqual(ids('?needs=keyphrase'), [self.weak.pk])
        self.assertEqual(ids('?needs=issue:featured_image'), [self.weak.pk])
        self.assertEqual(ids('?sort=score')[0], self.weak.pk)
        self.assertEqual(self.client.get('/api/dashboard/posts/?needs=issue:not_a_check').status_code, 400)
        # The keyphrase is editor-only: public payloads never include design_settings['seo'].
        public = self.client.get('/api/posts/').json()['results']
        self.assertEqual([post['id'] for post in public], [self.strong.pk])
        self.assertNotIn('seo', public[0]['design_settings'])

    def test_saving_settings_refreshes_the_stored_report(self):
        payload = {'title': 'Draft', 'slug': 'draft', 'content': '<p>Short.</p>', 'seo_settings': {'focus_keyphrase': 'draft notes'},
                   'design_settings': {'is_featured': False, 'seo': {'focus_keyphrase': 'ignored'}}}
        response = self.client.post(f'/api/dashboard/posts/{self.weak.pk}/save/', json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['post']['seo_settings']['focus_keyphrase'], 'draft notes')
        self.weak.refresh_from_db()
        self.assertEqual(self.weak.design_settings['seo']['focus_keyphrase'], 'draft notes')
        self.assertEqual(report_for(self.weak)['checks']['keyphrase'], 'good')
        # Saving design settings alone keeps the SEO settings.
        self.client.post(f'/api/dashboard/posts/{self.weak.pk}/save/', json.dumps({'title': 'Draft', 'design_settings': {'font_size': '18'}}), content_type='application/json')
        self.weak.refresh_from_db()
        self.assertEqual(self.weak.design_settings['seo']['focus_keyphrase'], 'draft notes')

    def test_overview_summarises_health_and_refresh_reports_remaining(self):
        data = self.client.get('/api/dashboard/seo/overview/').json()
        self.assertEqual((data['total'], data['analysed'], data['pending']), (2, 2, 0))
        self.assertEqual(data['lowest'][0]['id'], self.weak.pk)
        self.assertIn('keyphrase', [issue['id'] for issue in data['issues']])
        self.assertEqual(sum(data['bands'].values()), 2)
        cache.clear()
        refresh = self.client.post('/api/dashboard/seo/refresh/').json()
        self.assertEqual((refresh['analysed'], refresh['remaining']), (2, 0))

    def test_edits_produce_a_fresh_report(self):
        self.assertEqual(report_for(self.weak)['checks']['featured_image'], 'bad')
        self.weak.featured_image = 'https://example.com/b.png'
        self.weak.save()
        self.assertEqual(report_for(self.weak)['checks']['featured_image'], 'good')

    def test_overview_requires_content_access(self):
        self.client.logout()
        self.assertIn(self.client.get('/api/dashboard/seo/overview/').status_code, {401, 403})


@mock.patch.dict(os.environ, {'SEO_SITE_URL': 'https://resref.test', 'SEO_ALLOW_INDEXING': 'true'})
class StructuredDataTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_article_with_faq_and_references_publishes_faq_page_and_citations(self):
        category = Category.objects.create(name='Methods', slug='methods')
        post = Post.objects.create(
            title='Valued Living Questionnaire', slug='vlq', status='publish', published_at=timezone.now() - timedelta(days=1),
            design_settings={'seo': {'focus_keyphrase': 'Valued Living Questionnaire'}},
            content=('<p>Intro text.</p><h2>Frequently Asked Questions</h2><p><strong>Who uses it?</strong><br/>Clinicians.</p>'
                     '<p><strong>Is it free?</strong><br/>Yes, for research.</p><h2>References</h2>'
                     '<ol><li>Wilson (2010). <a href="https://doi.org/10.1007/BF03395706">Link</a></li></ol>'),
        )
        post.categories.add(category)
        from resref import seo
        meta = seo.article_meta(post, '/database/methods/vlq')
        self.assertEqual(meta.page_type, 'FAQPage')
        self.assertEqual([item['name'] for item in meta.faq], ['Who uses it?', 'Is it free?'])
        article = next(node for node in meta.graph if node.get('@type') == 'Article')
        self.assertEqual(article['citation'], [{'@type': 'CreativeWork', 'url': 'https://doi.org/10.1007/BF03395706'}])
        self.assertEqual(article['keywords'][0], 'Valued Living Questionnaire')
        graph = seo.structured_data(meta)['@graph']
        self.assertTrue(any(node.get('@type') == 'FAQPage' for node in graph))
