"""Server-side discoverability for the React single-page application.

Social-preview crawlers and most AI crawlers do not run JavaScript, so the
compiled ``index.html`` is served with per-URL metadata already in its head:
title, description, canonical link, robots directive, Open Graph / Twitter
cards and JSON-LD structured data, plus a plain ``<noscript>`` summary of the
page content.  Also here: robots.txt, sitemap.xml, llms.txt and llms-full.txt.

Every value placed in HTML is escaped (``html.escape`` for markup and
attributes; JSON-LD has ``<``, ``>`` and ``&`` unicode-escaped) and article
bodies are reduced to escaped plain text, so stored content can never inject
markup into the shell.

Configuration (all optional, read from the environment):
  SEO_SITE_URL            Canonical origin, e.g. https://resref.com. Defaults to
                          FRONTEND_BASE_URL (itself derived from PUBLIC_HOSTNAME).
  SEO_ALLOW_INDEXING      true/false. Defaults to true only when
                          RESREF_ENV=production, so staging/preview copies are
                          never indexed.
  SEO_AI_CRAWLERS         allow (default) | search-only | block.
  GA_MEASUREMENT_ID       Google Analytics 4 measurement ID (G-XXXXXXXXXX).
  GOOGLE_SITE_VERIFICATION  Search Console HTML-tag verification token.
  BING_SITE_VERIFICATION    Bing Webmaster Tools msvalidate.01 token.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpResponsePermanentRedirect
from django.utils import timezone

logger = logging.getLogger(__name__)

SITE_NAME = 'ResRef'
SITE_TAGLINE = 'Research Resources, Tools & Support'
# One entity description, reused by the Organization JSON-LD, llms.txt and the
# home page so search and answer engines see a consistent "about" statement.
# Keep frontend/src/utils/seo.js ORGANIZATION_DESCRIPTION identical.
ORGANIZATION_DESCRIPTION = (
    'ResRef is a research reference platform for students, clinicians and researchers. '
    'It offers a searchable database of research resources and validated questionnaires, '
    'learning articles on research methods, practical research tools, research opportunities '
    'and expert research consultation.'
)
TWITTER_HANDLE = '@ResRefcom'
# Mirrors SOCIAL_LINKS in frontend/src/siteData.js.
SOCIAL_PROFILES = (
    'https://www.facebook.com/ResRefcom/',
    'https://x.com/ResRefcom',
    'https://www.youtube.com/@ResRefcom',
    'https://www.instagram.com/resrefcom',
    'https://www.linkedin.com/company/resrefcom/',
    'https://t.me/ResRefcom',
)
DEFAULT_IMAGE_FILE = 'og-default.png'  # 1200x630, frontend/public/og-default.png
LOGO_FILE = 'resref-logo-mark.png'

INDEX = 'index, follow, max-image-preview:large, max-snippet:-1'
NOINDEX = 'noindex, follow'
NOINDEX_NOFOLLOW = 'noindex, nofollow'

SEO_START = '<!-- resref:seo:start -->'
SEO_END = '<!-- resref:seo:end -->'
NOSCRIPT_MARKER = '<!-- resref:noscript -->'

GA_ID_PATTERN = re.compile(r'^G-[A-Z0-9]{4,20}$')
VERIFICATION_PATTERN = re.compile(r'^[A-Za-z0-9_-]{8,128}$')
SLUG_PATTERN = re.compile(r'^[-\w]{1,500}$')

# Public, indexable application pages. Titles/descriptions mirror the client
# SEO constants (frontend/src/config/contentStructure.js) so the server and the
# browser agree; test_seo checks that they stay in sync.
STATIC_PAGES = {
    '/': ('ResRef — Research Resources, Tools & Support',
          'Research tools, articles and questionnaire guides, plus consultation support for students, clinicians and researchers.', None, 'WebPage'),
    '/database': ('Research Database | ResRef',
                  'Medical knowledge and research resources, organised for discovery. Browse published articles, '
                  'validated questionnaires and research resources by topic.', 'Database', 'CollectionPage'),
    '/articles': ('Mastering Research | ResRef',
                  'Practical resources for planning, writing, publishing, and progressing through research.',
                  'Mastering Research', 'CollectionPage'),
    '/questionnaires': ('Questionnaires & Scales | ResRef',
                        'Find validated research questionnaires and measurement scales organised by specialty.',
                        'Questionnaires', 'CollectionPage'),
    '/tools': ('Research Tools — Free Calculators & Generators | ResRef',
               'Free interactive research tools for academics and clinicians. Sample size calculator, reference '
               'generator, and more built for real research workflows.', 'Research Tools', 'CollectionPage'),
    '/consultation': ('Free Expert Research Consultation | ResRef',
                      'Get personalised, free research consultation from ResRef expert team. Support for study design, '
                      'data analysis, literature review, methodology, and more.', 'Expert Consultation', 'WebPage'),
    '/opportunities': ('Research Opportunities — Open Positions & Collaborations | ResRef',
                       'Discover open research positions, academic collaborations, and clinical study opportunities. '
                       'Updated regularly by the ResRef community.', 'Research Opportunities', 'CollectionPage'),
    '/join': ('Join the ResRef Team — Volunteer Roles in Research & Technology',
              'Contribute to a growing research platform. Open volunteer roles in education, design, technology, '
              'data, media, and quality control.', 'Join Our Team', 'WebPage'),
    '/about': ('About ResRef — Our Mission, Team & Platform Story',
               'ResRef is a research reference platform built to make the research journey clearer, more organised, '
               'and more connected for students, clinicians, and institutions.', 'About', 'AboutPage'),
    '/contact': ('Contact Us | ResRef',
                 'Contact ResRef for research questions, expert consultation, platform support, collaborations, and '
                 'institutional partnership enquiries.', 'Contact', 'ContactPage'),
    '/faq': ('Frequently Asked Questions | ResRef',
             'Find answers to common questions about ResRef, including the database, tools, consultation service, '
             'team roles, and platform access.', 'FAQ', 'FAQPage'),
    '/terms-of-use': ('Terms of Use | ResRef',
                      'The terms that apply to using ResRef, its research resources, tools and support services.',
                      'Terms of Use', 'WebPage'),
    '/privacy-policy': ('Privacy Policy | ResRef',
                        'What information ResRef collects, why it is collected, how it is used and the choices you have.',
                        'Privacy Policy', 'WebPage'),
    '/cookie-policy': ('Cookie Policy | ResRef',
                       'How ResRef uses essential cookies and, only with your consent, Google Analytics cookies.',
                       'Cookie Policy', 'WebPage'),
}

# The research tools are open to everyone (sign-in only saves work to an
# account), so their pages are indexed and listed in the sitemap.
TOOL_PAGES = {
    '/tools/sample-size-calculator': ('Sample Size Calculator — Free Study Planning Tool | ResRef',
                                      'Calculate the sample size for your study design: proportions, means, '
                                      'comparisons and more, with method notes and manuscript wording.'),
    '/tools/reference-generator': ('Reference Generator — Free Citation Tool | ResRef',
                                   'Find references by DOI, URL or title, format them in common citation styles '
                                   'and export your bibliography.'),
    '/tools/journal-finder': ('Journal Finder — Find the Right Journal | ResRef',
                              'Match your manuscript to suitable journals by subject, access, publication cost '
                              'and quartile.'),
    '/tools/research-analyzer': ('Research Analyzer — Statistical Analysis & Reports | ResRef',
                                 'Upload research data, run statistical tests and generate structured analysis '
                                 'reports in English or Arabic.'),
}

# How-to steps, coverage and FAQ for each tool. One file feeds both the visible
# page (frontend ToolGuide) and the server-rendered copy for crawlers. In the
# Docker image it is copied next to this module.
TOOL_GUIDE_FILES = (Path(__file__).with_name('tool_guides.json'),
                    Path(__file__).resolve().parents[2] / 'frontend' / 'src' / 'data' / 'toolGuides.json')
_tool_guides = {}


def tool_guides():
    if not _tool_guides:
        for candidate in TOOL_GUIDE_FILES:
            if candidate.exists():
                _tool_guides.update(json.loads(candidate.read_text(encoding='utf-8')))
                break
        else:
            logger.warning('Tool guides not found; tool pages are served without their guide text.')
    return _tool_guides


def tool_meta(path, title, description):
    meta = PageMeta(title=title, description=description, path=path,
                    breadcrumbs=[('Research Tools', '/tools'), (title.split(' | ')[0].split(' — ')[0], path)])
    guide = tool_guides().get(path)
    if not guide:
        meta.noscript = noscript_summary(meta)
        return meta
    app = {
        '@type': 'WebApplication', '@id': meta.canonical + '#app', 'name': guide['name'], 'url': meta.canonical,
        'description': guide['summary'], 'applicationCategory': guide['category'],
        'operatingSystem': 'Any (web browser)', 'browserRequirements': 'Requires JavaScript',
        'featureList': guide['features'], 'publisher': {'@id': absolute('/#organization')},
    }
    if guide.get('free'):
        app['isAccessibleForFree'] = True
        app['offers'] = {'@type': 'Offer', 'price': '0', 'priceCurrency': 'USD'}
    meta.graph.append(app)
    meta.page_type = 'FAQPage'
    meta.faq = [{'@type': 'Question', 'name': item['q'], 'acceptedAnswer': {'@type': 'Answer', 'text': item['a']}}
                for item in guide['faq']]
    steps = ''.join(f'<li>{escape(step)}</li>' for step in guide['steps'])
    covers = ''.join(f'<li>{escape(item)}</li>' for item in guide['features'])
    faq = ''.join(f'<h3>{escape(item["q"])}</h3><p>{escape(item["a"])}</p>' for item in guide['faq'])
    meta.noscript = noscript_summary(meta, extra=(
        f'<p>{escape(guide["summary"])}</p><h2>How to use the {escape(guide["name"])}</h2><ol>{steps}</ol>'
        f'<h2>What it covers</h2><ul>{covers}</ul><h2>Frequently asked questions</h2>{faq}'))
    return meta


PRIVATE_PAGES = {
    '/sign-in': 'Sign in | ResRef',
    '/auth': 'Sign in | ResRef',
    '/register': 'Create an account | ResRef',
    '/account': 'My account | ResRef',
    '/account/reset-password': 'Reset password | ResRef',
    '/account/confirm-email': 'Confirm email | ResRef',
    '/newsletter/confirm': 'Confirm newsletter subscription | ResRef',
}

# Client-side <Navigate> aliases answered with a permanent redirect so search
# engines consolidate signals on one URL.
REDIRECTS = {
    '/home': '/',
    '/homepage': '/',
    '/questionnaires-2': '/questionnaires',
    '/journal-finder': '/tools/journal-finder',
    '/sample-size-calculator': '/tools/sample-size-calculator',
    '/reference-generator': '/tools/reference-generator',
    '/research-analyzer': '/tools/research-analyzer',
    '/expert-consultation': '/consultation',
    '/research-opportunities': '/opportunities',
    '/join-our-team': '/join',
    '/about-us': '/about',
    '/contact-us': '/contact',
}

TEAM_PAGE = ('Our Team | ResRef', 'Meet the founder, leadership, directors and teams behind ResRef.')

NOT_FOUND = ('Page Not Found | ResRef',
             'Find your way back to ResRef home, research database, tools, or contact support.')

# robots.txt: AI crawler user agents. "Training" crawlers collect data for model
# training; "answer" agents fetch pages to cite them in AI search answers.
AI_TRAINING_CRAWLERS = (
    'GPTBot', 'ClaudeBot', 'anthropic-ai', 'Google-Extended', 'Applebot-Extended', 'CCBot',
    'meta-externalagent', 'Bytespider', 'cohere-training-data-crawler',
)
AI_ANSWER_CRAWLERS = (
    'OAI-SearchBot', 'ChatGPT-User', 'Claude-SearchBot', 'Claude-User', 'PerplexityBot', 'Perplexity-User',
)
# Read-only public API endpoints the SPA needs to render content. Googlebot
# renders JavaScript, so these must stay crawlable even though /api/ is not.
CRAWLABLE_API_PREFIXES = (
    '/api/home/', '/api/posts/', '/api/pages/', '/api/categories/', '/api/authors/',
    '/api/faq/', '/api/site-settings/', '/api/opportunities/', '/api/join-team/',
)


# --------------------------------------------------------------------------- configuration

def env_flag(name, default):
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def site_url():
    configured = os.getenv('SEO_SITE_URL', '').strip() or getattr(settings, 'FRONTEND_BASE_URL', '')
    parts = urlsplit(configured)
    if parts.scheme in {'http', 'https'} and parts.netloc:
        return f'{parts.scheme}://{parts.netloc}'
    return 'https://resref.com'


def indexing_allowed():
    return env_flag('SEO_ALLOW_INDEXING', getattr(settings, 'IS_PRODUCTION', False))


def ai_crawler_policy():
    value = os.getenv('SEO_AI_CRAWLERS', 'allow').strip().lower()
    return value if value in {'allow', 'search-only', 'block'} else 'allow'


def ga_measurement_id():
    value = os.getenv('GA_MEASUREMENT_ID', '').strip().upper()
    return value if GA_ID_PATTERN.match(value) else ''


def verification_token(name):
    value = os.getenv(name, '').strip()
    return value if VERIFICATION_PATTERN.match(value) else ''


def absolute(path):
    if not path:
        return ''
    if path.startswith(('https://', 'http://')):
        return path
    return f"{site_url()}/{path.lstrip('/')}"


def public_asset(name):
    """URL of a file from frontend/public (served under STATIC_URL in production)."""
    prefix = settings.STATIC_URL if getattr(settings, 'SERVE_FRONTEND_FROM_DJANGO', False) else '/'
    return absolute(f"{prefix.rstrip('/')}/{name}")


# --------------------------------------------------------------------------- text helpers

PLACEHOLDER_PATTERN = re.compile(r'%{1,2}[a-z_]+%{1,2}', re.IGNORECASE)


class _TextExtractor(HTMLParser):
    """Collect readable blocks (headings, paragraphs, list items) as plain text."""

    BLOCKS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'blockquote', 'td', 'th', 'dt', 'dd', 'figcaption', 'div', 'section', 'br', 'tr'}
    SKIP = {'script', 'style', 'noscript', 'iframe', 'svg', 'button', 'form', 'select', 'textarea', 'template', 'object'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self._buffer, self._tag, self._skip = [], [], 'p', 0

    def _flush(self):
        text = re.sub(r'\s+', ' ', ''.join(self._buffer)).strip()
        if text:
            self.blocks.append((self._tag, text))
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag in self.BLOCKS:
            self._flush()
            self._tag = tag if tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'} else 'p'

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in self.BLOCKS:
            self._flush()
            self._tag = 'p'

    def handle_data(self, data):
        if not self._skip:
            self._buffer.append(data)

    def close(self):
        super().close()
        self._flush()


def text_blocks(html_value, limit=40000):
    parser = _TextExtractor()
    try:
        parser.feed(str(html_value or ''))
        parser.close()
    except Exception:  # pragma: no cover - HTMLParser is lenient; stay safe anyway
        return []
    blocks, total = [], 0
    for tag, text in parser.blocks:
        total += len(text)
        if total > limit:
            break
        blocks.append((tag, text))
    return blocks


def plain(value):
    blocks = text_blocks(value, limit=20000)
    return re.sub(r'\s+', ' ', ' '.join(text for _, text in blocks)).strip()


def clean_seo_text(value):
    text = PLACEHOLDER_PATTERN.sub('', plain(value))
    text = re.sub(r'\s+', ' ', text)
    return re.sub(r'^[\s|:–—-]+|[\s|:–—-]+$', '', text).strip()


def shorten(text, length=300):
    text = (text or '').strip()
    if len(text) <= length:
        return text
    cut = text[:length - 1].rsplit(' ', 1)[0].rstrip(',;:.-– ')
    return f'{cut}…'


def json_ld(data):
    encoded = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    return encoded.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


# --------------------------------------------------------------------------- page model

@dataclass
class PageMeta:
    title: str
    description: str
    path: str
    robots: str = INDEX
    og_type: str = 'website'
    image: str = ''
    image_alt: str = ''
    status: int = 200
    page_type: str = 'WebPage'
    breadcrumbs: list = field(default_factory=list)  # [(name, path)], home excluded
    graph: list = field(default_factory=list)  # extra JSON-LD nodes
    article: dict = field(default_factory=dict)  # og article:* properties
    noscript: str = ''
    faq: list = field(default_factory=list)  # FAQPage questions
    main_entity: str = ''  # @id of the ProfilePage main entity

    @property
    def canonical(self):
        return absolute(self.path)


def organization_node():
    node = {
        '@type': 'Organization', '@id': absolute('/#organization'), 'name': SITE_NAME, 'url': absolute('/'),
        'logo': {'@type': 'ImageObject', 'url': public_asset(LOGO_FILE)},
        'description': ORGANIZATION_DESCRIPTION, 'sameAs': list(SOCIAL_PROFILES),
    }
    email = site_setting('contact_email')
    if email and '@' in email:
        node['email'] = email
    return node


def website_node():
    return {
        '@type': 'WebSite', '@id': absolute('/#website'), 'url': absolute('/'), 'name': SITE_NAME,
        'description': ORGANIZATION_DESCRIPTION, 'publisher': {'@id': absolute('/#organization')},
        'inLanguage': 'en',
        'potentialAction': {
            '@type': 'SearchAction',
            'target': {'@type': 'EntryPoint', 'urlTemplate': absolute('/database') + '?q={search_term_string}'},
            'query-input': 'required name=search_term_string',
        },
    }


def structured_data(meta):
    page = {
        '@type': meta.page_type, '@id': meta.canonical + '#webpage', 'url': meta.canonical,
        'name': meta.title, 'description': meta.description,
        'isPartOf': {'@id': absolute('/#website')}, 'about': {'@id': absolute('/#organization')},
    }
    graph = [organization_node(), website_node()]
    if meta.page_type != 'none':
        graph.append(page)
    graph.extend(meta.graph)
    if meta.breadcrumbs:
        items = [{'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': absolute('/')}]
        for index, (name, path) in enumerate(meta.breadcrumbs, start=2):
            items.append({'@type': 'ListItem', 'position': index, 'name': name, 'item': absolute(path)})
        crumbs = {'@type': 'BreadcrumbList', '@id': meta.canonical + '#breadcrumb', 'itemListElement': items}
        graph.append(crumbs)
        if meta.page_type != 'none':
            page['breadcrumb'] = {'@id': crumbs['@id']}
    return {'@context': 'https://schema.org', '@graph': graph}


_settings_cache = {}


def site_setting(key):
    if key in _settings_cache:
        return _settings_cache[key]
    try:
        from dashboard.models import SiteSettings
        row = SiteSettings.objects.filter(key=key).first()
        value = str(row.value).strip() if row and row.value else ''
    except Exception:
        value = ''
    _settings_cache[key] = value
    return value


# --------------------------------------------------------------------------- content lookups

def published_posts(post_type='post'):
    from blog.models import Post
    return Post.objects.filter(post_type=post_type, status='publish', published_at__lte=timezone.now())


def article_path(post):
    first = next(iter(post.categories.all()), None)
    return f"/database/{first.slug if first else 'research'}/{post.slug}"


RESERVED_FIRST_SEGMENTS = {'database', 'authors', 'page', 'tools', 'dashboard', 'account', 'api', 'static', 'media', 'admin', 'newsletter', 'team'}


def page_path(page):
    """Managed pages keep their legacy WordPress address (/<slug>, as the
    legacy-redirects app links them) unless an application route owns it."""
    path = f'/{page.slug}'
    taken = path in STATIC_PAGES or path in REDIRECTS or path in PRIVATE_PAGES or page.slug in RESERVED_FIRST_SEGMENTS
    return f'/page/{page.slug}' if taken else path


def link_list(items):
    rows = ''.join(f'<li><a href="{escape(path)}">{escape(label)}</a></li>' for label, path in items)
    return f'<ul>{rows}</ul>' if rows else ''


def latest_article_links(limit=24, category=None):
    posts = published_posts().prefetch_related('categories').order_by('-published_at')
    if category is not None:
        posts = posts.filter(categories=category).distinct()
    return [(post.title, article_path(post)) for post in posts[:limit]]


SITE_NAVIGATION = (
    ('Research Database', '/database'), ('Mastering Research', '/articles'), ('Research Tools', '/tools'),
    ('Expert Consultation', '/consultation'), ('Research Opportunities', '/opportunities'),
    ('About ResRef', '/about'), ('FAQ', '/faq'), ('Contact', '/contact'),
)


def noscript_summary(meta, links=(), extra=''):
    nav = link_list(SITE_NAVIGATION)
    heading = escape(meta.title.replace(' | ResRef', ''))
    body = f'<h1>{heading}</h1><p>{escape(meta.description)}</p>{extra}'
    if links:
        body += f'<h2>Articles</h2>{link_list(links)}'
    return f'<main>{body}<nav aria-label="Site">{nav}</nav></main>'


def post_payload(post):
    from blog.api_views import normalize_legacy_media_urls, post_to_dict
    data = post_to_dict(post)
    data['featured_image'] = normalize_legacy_media_urls(post.featured_image)
    return data


def article_meta(post, request_path):
    data = post_payload(post)
    title = plain(post.title)
    excerpt = plain(post.excerpt)
    blocks = text_blocks(post.content)
    description = clean_seo_text(post.seo_description) or excerpt or shorten(' '.join(text for tag, text in blocks if tag == 'p'), 300)
    description = shorten(description, 300)
    path = article_path(post)
    category = next(iter(post.categories.all()), None)
    byline = [author for author in data['authors'] if not author.get('role_label') or author.get('role') in {'author', 'co_author'}]
    image = absolute(data['featured_image']) if data['featured_image'] else ''
    meta = PageMeta(
        title=f"{clean_seo_text(post.seo_title) or title} | ResRef", description=description, path=path,
        og_type='article', image=image, image_alt=title, page_type='WebPage',
        breadcrumbs=[('Database', '/database')] + ([(plain(category.name), f'/database/{category.slug}')] if category else []) + [(title, path)],
    )
    # The "resref" profile credits the organization itself, not a person.
    authors = [{'@id': absolute('/#organization')} if author.get('slug') == 'resref' else {
        '@type': 'Person', 'name': plain(author['display_name']),
        **({'url': absolute(f"/authors/{author['slug']}")} if author.get('slug') else {}),
    } for author in byline]
    article = {
        '@type': 'Article', '@id': meta.canonical + '#article', 'headline': shorten(title, 110),
        'description': description, 'url': meta.canonical,
        'mainEntityOfPage': {'@id': meta.canonical + '#webpage'},
        'isPartOf': {'@id': absolute('/#website')}, 'publisher': {'@id': absolute('/#organization')},
        'author': authors or [{'@id': absolute('/#organization')}],
        'dateModified': post.updated_at.isoformat(),
        'wordCount': sum(len(text.split()) for _, text in blocks),
    }
    if post.published_at:
        article['datePublished'] = post.published_at.isoformat()
    if image:
        article['image'] = [image]
    if category:
        article['articleSection'] = plain(category.name)
    from blog.seo_analysis import extract_faq, extract_references, parse_html, post_seo_settings
    keyphrase = plain(post_seo_settings(post)['focus_keyphrase'])
    tags = list(dict.fromkeys(([keyphrase] if keyphrase else []) + [plain(tag['name']) for tag in data['tags']]))
    if tags:
        article['keywords'] = tags
    # Answer and citation signals detected in the visible article text (see
    # blog/seo_analysis.py): an FAQ section becomes FAQPage markup and the
    # references section becomes schema.org citations.
    document = parse_html(post.content)
    questions = extract_faq(document.blocks)['items']
    if len(questions) >= 2:
        meta.page_type = 'FAQPage'
        meta.faq = [{'@type': 'Question', 'name': shorten(item['question'], 300),
                     'acceptedAnswer': {'@type': 'Answer', 'text': shorten(item['answer'], 2000)}} for item in questions[:30]]
    citations = list(dict.fromkeys(extract_references(document.blocks, document.links)['links']))[:30]
    if citations:
        article['citation'] = [{'@type': 'CreativeWork', 'url': url} for url in citations]
    meta.graph.append(article)
    meta.article = {
        'article:published_time': post.published_at.isoformat() if post.published_at else '',
        'article:modified_time': post.updated_at.isoformat(),
        'article:section': plain(category.name) if category else '',
    }
    # Plain-text rendering of the article for crawlers that do not run JavaScript.
    headings = [(tag, text) for tag, text in blocks if tag in {'h2', 'h3'}]
    toc = ''
    if len(headings) >= 2:
        toc = '<nav aria-label="Article contents"><h2>Contents</h2><ol>' + ''.join(
            f'<li>{escape(text)}</li>' for _, text in headings) + '</ol></nav>'
    body = []
    for tag, text in blocks:
        tag = tag if tag in {'h2', 'h3', 'h4', 'li'} else ('h2' if tag == 'h1' else 'h4' if tag in {'h5', 'h6'} else 'p')
        body.append(f'<{tag}>{escape(text)}</{tag}>')
    names = ', '.join(plain(author['display_name']) for author in byline)
    byline_html = f'<p>By {escape(names)}</p>' if names else ''
    date_html = f'<p>Published <time datetime="{post.published_at.date().isoformat()}">{post.published_at.date().isoformat()}</time></p>' if post.published_at else ''
    meta.noscript = (
        f'<main><article><header><h1>{escape(title)}</h1>{byline_html}{date_html}'
        f'<p>{escape(description)}</p></header>{toc}{"".join(body)}</article></main>'
    )
    return meta


def page_meta_for(page, path):
    title = plain(page.title)
    description = shorten(clean_seo_text(page.seo_description) or plain(page.excerpt) or plain(page.content), 300) or NOT_FOUND[1]
    meta = PageMeta(title=f'{clean_seo_text(page.seo_title) or title} | ResRef', description=description, path=path,
                    breadcrumbs=[(title, path)])
    blocks = ''.join(f'<p>{escape(text)}</p>' for _, text in text_blocks(page.content, limit=20000))
    meta.noscript = f'<main><article><h1>{escape(title)}</h1>{blocks}</article></main>'
    return meta


def author_meta(author):
    from blog.api_views import author_to_public_dict
    from blog.models import Post, PostContributor
    data = author_to_public_dict(author)
    name = plain(author.display_name)
    path = f'/authors/{author.slug}'
    contributed = PostContributor.objects.filter(
        contributor=author, post__status='publish', post__post_type='post', post__published_at__lte=timezone.now(),
    ).values_list('post_id', flat=True)
    posts = Post.objects.filter(status='publish', post_type='post', published_at__lte=timezone.now()).filter(
        id__in=list(contributed)) | published_posts().filter(authors=author)
    posts = posts.distinct().prefetch_related('categories').order_by('-published_at')
    links = [(post.title, article_path(post)) for post in posts[:50]]
    bio = plain(author.short_bio or author.bio)
    description = shorten(clean_seo_text(author.seo_description) or bio or f'{name} — contributor profile on ResRef.', 300)
    meta = PageMeta(
        title=f'{clean_seo_text(author.seo_title) or name} | Contributors | ResRef', description=description, path=path,
        og_type='profile', image=absolute(data['avatar']) if data['avatar'] else '', image_alt=name,
        page_type='ProfilePage', breadcrumbs=[('Database', '/database'), (name, path)],
        robots=INDEX if links else NOINDEX,
    )
    person = {'@type': 'Person', '@id': meta.canonical + '#person', 'name': name, 'url': meta.canonical}
    if data['avatar']:
        person['image'] = absolute(data['avatar'])
    if author.position:
        person['jobTitle'] = plain(author.position)
    if author.institution:
        person['affiliation'] = {'@type': 'Organization', 'name': plain(author.institution)}
    if bio:
        person['description'] = shorten(bio, 500)
    if author.specialty:
        person['knowsAbout'] = plain(author.specialty)
    same_as = [value for value in (author.orcid, author.google_scholar, author.researchgate, author.linkedin, author.twitter, author.website)
               if value and value.startswith(('https://', 'http://'))]
    if same_as:
        person['sameAs'] = same_as
    meta.graph.append(person)
    meta.main_entity = person['@id']
    meta.noscript = noscript_summary(meta, links)
    return meta


def faq_graph():
    from dashboard.models import FAQItem
    items = FAQItem.objects.filter(status='published').select_related('category')[:200]
    questions = [{
        '@type': 'Question', 'name': plain(item.question),
        'acceptedAnswer': {'@type': 'Answer', 'text': shorten(plain(item.answer), 2000)},
    } for item in items if plain(item.question) and plain(item.answer)]
    return questions


# --------------------------------------------------------------------------- routing

class Redirect(Exception):
    def __init__(self, location):
        super().__init__(location)
        self.location = location


def _query_suffix(request, keep=None):
    params = request.GET.copy() if request is not None else {}
    if keep is not None:
        params = {key: params[key] for key in keep if params.get(key)}
        return f'?{urlencode(params)}' if params else ''
    encoded = params.urlencode() if hasattr(params, 'urlencode') else ''
    return f'?{encoded}' if encoded else ''


def listing_canonical(request, path):
    try:
        page = int(request.GET.get('page', '1'))
    except (TypeError, ValueError):
        page = 1
    return f'{path}?page={page}' if page > 1 else path


def static_meta(path, request):
    title, description, crumb, page_type = STATIC_PAGES[path]
    meta = PageMeta(title=title, description=description, path=path, page_type=page_type,
                    breadcrumbs=[(crumb, path)] if crumb else [])
    links = []
    extra = ''
    if path == '/':
        extra = f'<p>{escape(ORGANIZATION_DESCRIPTION)}</p>'
        links = latest_article_links(12)
    elif path == '/database':
        from blog.models import Category
        meta.path = listing_canonical(request, path)
        topics = [(plain(category.name), f'/database/{category.slug}') for category in
                  Category.objects.filter(parent=None, show_in_database=True).order_by('database_order', 'name')]
        extra = f'<h2>Topics</h2>{link_list(topics)}' if topics else ''
        links = latest_article_links(24)
        cat = request.GET.get('cat', '')
        if cat and SLUG_PATTERN.match(cat) and Category.objects.filter(slug=cat).exists():
            meta.path = f'/database/{cat}'
    elif path == '/articles':
        from blog.models import Category
        meta.path = listing_canonical(request, path)
        learn = Category.objects.filter(slug='mastering-research').first()
        links = latest_article_links(24, learn) if learn else []
    elif path == '/tools':
        tools = [(TOOL_PAGES[tool][0].split(' — ')[0].split(' | ')[0], tool) for tool in TOOL_PAGES]
        extra = '<h2>Tools</h2><ul>' + ''.join(
            f'<li><a href="{escape(tool)}">{escape(name)}</a>: {escape(tool_guides().get(tool, {}).get("summary", TOOL_PAGES[tool][1]))}</li>'
            for name, tool in tools) + '</ul>'
    elif path == '/faq':
        questions = faq_graph()
        if questions:
            meta.page_type = 'FAQPage'
            meta.faq = questions
            extra = ''.join(f'<h2>{escape(q["name"])}</h2><p>{escape(q["acceptedAnswer"]["text"])}</p>' for q in questions)
        else:
            meta.page_type = 'WebPage'
    if request.GET.get('q') or request.GET.get('tag') or request.GET.get('focus'):
        meta.robots = NOINDEX
    meta.noscript = noscript_summary(meta, links, extra)
    return meta


def resolve(request, path):
    """Return PageMeta for a SPA path, or raise Redirect."""
    from blog.models import Author, Category

    if path in REDIRECTS:
        raise Redirect(REDIRECTS[path] + _query_suffix(request))
    if path == '/advanced-search':
        raise Redirect('/database?focus=search')
    if path in STATIC_PAGES:
        return static_meta(path, request)
    if path in TOOL_PAGES:
        return tool_meta(path, *TOOL_PAGES[path])
    if path in PRIVATE_PAGES:
        return PageMeta(title=PRIVATE_PAGES[path], description=STATIC_PAGES['/'][1], path=path,
                        robots=NOINDEX, page_type='none')
    if path == '/team/preview':
        return PageMeta(title='Team page preview | ResRef', description=STATIC_PAGES['/'][1], path=path,
                        robots=NOINDEX_NOFOLLOW, page_type='none')
    if path == '/team':
        # Does not exist for visitors or crawlers until a Super Admin publishes it.
        from dashboard.models import TeamPageSettings
        if not TeamPageSettings.is_live():
            return not_found(path)
        meta = PageMeta(title=TEAM_PAGE[0], description=TEAM_PAGE[1], path=path, breadcrumbs=[('Our Team', path)])
        meta.noscript = noscript_summary(meta)
        return meta
    if path == '/dashboard' or path.startswith('/dashboard/'):
        return PageMeta(title='Dashboard | ResRef', description=STATIC_PAGES['/'][1], path='/dashboard',
                        robots=NOINDEX_NOFOLLOW, page_type='none')

    parts = path.strip('/').split('/')
    if len(parts) > 1 and '@' in parts[-1]:
        # Email addresses once linked without "mailto:" turned into /<page>/<address>.
        raise Redirect('/' + '/'.join(parts[:-1]))
    if not all(SLUG_PATTERN.match(part) for part in parts):
        return not_found(path)

    if len(parts) == 2 and parts[0] == 'database':
        category = Category.objects.filter(slug=parts[1]).first()
        if not category:
            return not_found(path)
        name = plain(category.name)
        description = shorten(plain(category.description), 300) or f'Explore published articles, research tools, and resources in {name}.'
        meta = PageMeta(title=f'{name} | ResRef', description=description, path=listing_canonical(request, path),
                        page_type='CollectionPage', image=absolute(category.hero_image) if category.hero_image else '',
                        breadcrumbs=[('Database', '/database'), (name, f'/database/{category.slug}')])
        if request.GET.get('q') or request.GET.get('tag'):
            meta.robots = NOINDEX
        meta.noscript = noscript_summary(meta, latest_article_links(48, category))
        return meta

    if len(parts) == 3 and parts[0] == 'database':
        post = published_posts().prefetch_related('categories', 'tags', 'authors', 'contributor_assignments__contributor').select_related('author').filter(slug=parts[2]).first()
        if post:
            canonical = article_path(post)
            if canonical != path:
                raise Redirect(canonical + _query_suffix(request))
            return article_meta(post, path)
        page = published_posts('page').filter(slug=parts[2]).first()
        return page_meta_for(page, page_path(page)) if page else not_found(path)

    if len(parts) == 2 and parts[0] == 'author' and Author.objects.filter(slug=parts[1], is_active=True).exists():
        raise Redirect(f'/authors/{parts[1]}')  # WordPress author address

    if len(parts) == 2 and parts[0] == 'authors':
        author = Author.objects.select_related('profile_media').filter(slug=parts[1], is_active=True).first()
        return author_meta(author) if author else not_found(path)

    if len(parts) == 2 and parts[0] == 'page':
        page = published_posts('page').filter(slug=parts[1]).first()
        if not page and f'/{parts[1]}' in STATIC_PAGES:
            raise Redirect(f'/{parts[1]}')  # e.g. /page/privacy-policy, now a built-in page
        return page_meta_for(page, page_path(page)) if page else not_found(path)

    if len(parts) == 1:
        post = published_posts().prefetch_related('categories').filter(slug=parts[0]).first()
        if post:
            # Legacy WordPress article URLs (/<slug>) move to the canonical article address.
            raise Redirect(article_path(post) + _query_suffix(request))
        page = published_posts('page').filter(slug=parts[0]).first()
        if page:
            return page_meta_for(page, page_path(page))
        if parts[0].endswith('-') or len(parts[0]) >= 20:
            # Links cut short elsewhere (/alsfrs-r-guide-) still reach the one article they began.
            matches = list(published_posts().prefetch_related('categories').filter(slug__startswith=parts[0])[:2])
            if len(matches) == 1:
                raise Redirect(article_path(matches[0]) + _query_suffix(request))
    return not_found(path)


# Addresses only the old WordPress site had (feeds, wp-* files, uploaded media
# playlists). They answer 410 Gone so search engines drop them sooner.
WORDPRESS_ONLY = re.compile(r'^/(?:wp-|xmlrpc\.php|upload/)|/(?:feed|rss2?|atom)(?:/|$)', re.I)


def not_found(path):
    title, description = NOT_FOUND
    status = 410 if WORDPRESS_ONLY.search(path) else 404
    meta = PageMeta(title=title, description=description, path=path, robots=NOINDEX, status=status, page_type='none')
    meta.noscript = noscript_summary(meta)
    return meta


def fallback_meta(path):
    """Used when the database is unavailable: generic metadata, never a 404."""
    if path in STATIC_PAGES:
        title, description, _crumb, _type = STATIC_PAGES[path]
    else:
        title, description = STATIC_PAGES['/'][0], STATIC_PAGES['/'][1]
    return PageMeta(title=title, description=description, path=path if path in STATIC_PAGES else '/',
                    robots=NOINDEX if path not in STATIC_PAGES else INDEX, page_type='none')


# --------------------------------------------------------------------------- rendering

def head_html(meta):
    robots = meta.robots if indexing_allowed() else NOINDEX_NOFOLLOW
    image = meta.image or public_asset(DEFAULT_IMAGE_FILE)
    tags = [
        f'<title data-seo="server">{escape(meta.title)}</title>',
        f'<meta data-seo="server" name="description" content="{escape(meta.description)}" />',
        f'<meta data-seo="server" name="robots" content="{escape(robots)}" />',
        f'<meta name="resref:seo-path" content="{escape(meta.path.split("?")[0])}" />',
        f'<meta name="resref:site-url" content="{escape(site_url())}" />',
    ]
    if meta.status == 200:
        tags.append(f'<link data-seo="server" rel="canonical" href="{escape(meta.canonical)}" />')
    og = {
        'og:site_name': SITE_NAME, 'og:locale': 'en_US', 'og:type': meta.og_type, 'og:title': meta.title,
        'og:description': meta.description, 'og:url': meta.canonical if meta.status == 200 else '',
        'og:image': image, 'og:image:alt': meta.image_alt or SITE_NAME,
    }
    if not meta.image:
        og.update({'og:image:width': '1200', 'og:image:height': '630'})
    og.update({key: value for key, value in meta.article.items() if value})
    for key, value in og.items():
        if value:
            tags.append(f'<meta data-seo="server" property="{key}" content="{escape(value)}" />')
    twitter = {'twitter:card': 'summary_large_image', 'twitter:site': TWITTER_HANDLE, 'twitter:title': meta.title,
               'twitter:description': meta.description, 'twitter:image': image}
    for key, value in twitter.items():
        tags.append(f'<meta data-seo="server" name="{key}" content="{escape(value)}" />')
    for name, env_name in (('google-site-verification', 'GOOGLE_SITE_VERIFICATION'), ('msvalidate.01', 'BING_SITE_VERIFICATION')):
        token = verification_token(env_name)
        if token:
            tags.append(f'<meta name="{name}" content="{escape(token)}" />')
    ga_id = ga_measurement_id()
    if ga_id:
        tags.append(f'<meta name="resref:ga-id" content="{escape(ga_id)}" />')
    if meta.status == 200:
        data = structured_data(meta)
        for node in data['@graph']:
            if node.get('@type') == 'FAQPage' and meta.faq:
                node['mainEntity'] = meta.faq
            if node.get('@type') == 'ProfilePage' and meta.main_entity:
                node['mainEntity'] = {'@id': meta.main_entity}
        tags.append(f'<script data-seo="server" type="application/ld+json">{json_ld(data)}</script>')
    return '\n    '.join(tags)


_shell_cache = {'mtime': None, 'html': ''}


def load_shell(index_path):
    stat = index_path.stat()
    if _shell_cache['mtime'] != stat.st_mtime_ns:
        _shell_cache.update(mtime=stat.st_mtime_ns, html=index_path.read_text(encoding='utf-8'))
    return _shell_cache['html']


TITLE_PATTERN = re.compile(r'<title>.*?</title>', re.IGNORECASE | re.DOTALL)


def render_shell(shell, meta):
    head = head_html(meta)
    if SEO_START in shell and SEO_END in shell:
        before, rest = shell.split(SEO_START, 1)
        _old, after = rest.split(SEO_END, 1)
        html = f'{before}{SEO_START}\n    {head}\n    {SEO_END}{after}'
    elif TITLE_PATTERN.search(shell):
        html = TITLE_PATTERN.sub(lambda _match: head, shell, count=1)
    else:
        html = shell.replace('</head>', f'{head}\n</head>', 1)
    if meta.noscript:
        block = f'<noscript>{meta.noscript}</noscript>'
        html = html.replace(NOSCRIPT_MARKER, block, 1) if NOSCRIPT_MARKER in html else html.replace('</body>', f'{block}\n</body>', 1)
    return html


ANALYTICS_CSP_SOURCES = {
    'script-src': ('https://www.googletagmanager.com',),
    # GA4 also posts some hits to www.google.com/g/collect (observed with Consent Mode).
    'connect-src': ('https://*.google-analytics.com', 'https://*.analytics.google.com', 'https://*.googletagmanager.com',
                    'https://www.google.com'),
    'img-src': ('https://*.google-analytics.com', 'https://*.googletagmanager.com', 'https://www.google.com'),
}


def policy_with_analytics(policy):
    """Add the Google Analytics origins to a CSP string (only used when GA is configured)."""
    directives = [part.strip() for part in policy.split(';') if part.strip()]
    names = [part.split()[0].lower() for part in directives]
    for name, sources in ANALYTICS_CSP_SOURCES.items():
        if name in names:
            index = names.index(name)
            current = directives[index].split()
            directives[index] = ' '.join(current + [source for source in sources if source not in current])
        elif name != 'img-src':
            fallback = next((d for d in directives if d.split()[0].lower() == 'default-src'), "default-src 'self'")
            directives.append(' '.join([name] + fallback.split()[1:] + list(sources)))
    return '; '.join(directives)


def spa_response(request, index_path, path):
    """Serve the SPA shell for ``path`` with server-rendered metadata."""
    if request.method in {'GET', 'HEAD'} and path != '/' and path.endswith('/'):
        # One URL per page: /about/ -> /about (React Router treats both alike).
        # Collapsing leading slashes keeps the target on this site (never //host).
        clean_path = '/' + path.strip('/')
        target = None
        try:
            # Old addresses go straight to their final page, not through a second redirect.
            target = resolve(request, clean_path)
        except Redirect as redirect:
            return HttpResponsePermanentRedirect(redirect.location)
        except Exception:
            logger.exception('SEO redirect lookup failed for %s; removing the slash only.', path)
        finally:
            _settings_cache.clear()
        if target is None or target.status not in (404, 410):
            return HttpResponsePermanentRedirect(clean_path + _query_suffix(request))
        path = clean_path  # A missing page answers 404 at once, not after a redirect.
    try:
        meta = resolve(request, path)
    except Redirect as redirect:
        return HttpResponsePermanentRedirect(redirect.location)
    except Exception:
        logger.exception('SEO metadata could not be built for %s; serving generic metadata.', path)
        meta = fallback_meta(path)
    finally:
        _settings_cache.clear()
    try:
        html = render_shell(load_shell(index_path), meta)
    except Exception:
        logger.exception('SEO metadata could not be rendered for %s; serving the plain shell.', path)
        html, meta.status = load_shell(index_path), 200
    response = HttpResponse(html, status=meta.status, content_type='text/html; charset=utf-8')
    # The shell references content-hashed bundles: always revalidate it so a
    # new deploy is picked up immediately.
    response['Cache-Control'] = 'no-cache'
    robots = meta.robots if indexing_allowed() else NOINDEX_NOFOLLOW
    if robots != INDEX:
        response['X-Robots-Tag'] = robots
    if ga_measurement_id() and getattr(settings, 'RESREF_CSP_ENABLED', False):
        header = 'Content-Security-Policy-Report-Only' if getattr(settings, 'RESREF_CSP_REPORT_ONLY', False) else 'Content-Security-Policy'
        response[header] = policy_with_analytics(getattr(settings, 'RESREF_CONTENT_SECURITY_POLICY', ''))
    return response


# --------------------------------------------------------------------------- robots / sitemap / llms

def text_response(body, content_type='text/plain; charset=utf-8', max_age=3600):
    response = HttpResponse(body, content_type=content_type)
    response['Cache-Control'] = f'public, max-age={max_age}'
    return response


def robots_txt(request):
    base = site_url()
    if not indexing_allowed():
        return text_response('# Indexing is disabled for this environment (SEO_ALLOW_INDEXING).\nUser-agent: *\nDisallow: /\n')
    lines = ['# ResRef robots.txt', 'User-agent: *', 'Allow: /',
             'Disallow: /dashboard', 'Disallow: /account', 'Disallow: /api/',
             # The hosting platform's internal address; not a page of this site.
             'Disallow: /.railway/']
    lines += [f'Allow: {prefix}' for prefix in CRAWLABLE_API_PREFIXES]
    policy = ai_crawler_policy()
    blocked = AI_TRAINING_CRAWLERS if policy == 'search-only' else AI_TRAINING_CRAWLERS + AI_ANSWER_CRAWLERS if policy == 'block' else ()
    if blocked:
        lines += ['', f'# AI crawlers blocked by SEO_AI_CRAWLERS={policy}']
        for agent in blocked:
            lines += [f'User-agent: {agent}', 'Disallow: /']
    lines += ['', f'Sitemap: {base}/sitemap.xml', '']
    return text_response('\n'.join(lines))


def sitemap_entries():
    from django.db.models import Max, Q
    from blog.models import Author, Category, PostContributor

    entries = [(path, None) for path in STATIC_PAGES]
    entries += [(path, None) for path in TOOL_PAGES]
    from dashboard.models import TeamPageSettings
    if TeamPageSettings.is_live():
        entries.append(('/team', None))
    now = timezone.now()
    public = Q(post__post_type='post', post__status='publish', post__published_at__lte=now)
    for category in Category.objects.filter(show_in_database=True).annotate(
            latest=Max('post__updated_at', filter=public)).filter(latest__isnull=False).order_by('database_order', 'name'):
        entries.append((f'/database/{category.slug}', category.latest))
    for post in published_posts().prefetch_related('categories').order_by('-published_at')[:45000]:
        entries.append((article_path(post), post.updated_at))
    for page in published_posts('page').order_by('slug'):
        entries.append((page_path(page), page.updated_at))
    credited = set(PostContributor.objects.filter(post__post_type='post', post__status='publish', post__published_at__lte=now)
                   .values_list('contributor_id', flat=True))
    legacy = set(published_posts().values_list('authors', flat=True))
    for author in Author.objects.filter(is_active=True, id__in=(credited | legacy) - {None}).order_by('slug'):
        entries.append((f'/authors/{author.slug}', None))
    return entries


def sitemap_xml(request):
    key = f'seo:sitemap:{site_url()}'
    body = cache.get(key)
    if body is None:
        rows = []
        for path, lastmod in sitemap_entries():
            stamp = f'<lastmod>{lastmod.date().isoformat()}</lastmod>' if lastmod else ''
            rows.append(f'<url><loc>{escape(absolute(path))}</loc>{stamp}</url>')
        body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + '\n'.join(rows) + '\n</urlset>\n')
        cache.set(key, body, 900)
    return text_response(body, 'application/xml; charset=utf-8', 900)


def llms_txt(request):
    key = f'seo:llms:{site_url()}'
    body = cache.get(key)
    if body is None:
        from blog.models import Category
        lines = [f'# {SITE_NAME}', '', f'> {ORGANIZATION_DESCRIPTION}', '',
                 'ResRef articles are written and reviewed by named contributors; each article page lists its authors, '
                 'publication date and last update. Content is for education and research support and does not replace '
                 'professional, clinical or statistical advice.', '',
                 '## Key pages', '']
        for path in ('/', '/database', '/articles', '/tools', '/consultation', '/opportunities', '/faq', '/about', '/contact'):
            title, description, *_rest = STATIC_PAGES[path]
            lines.append(f'- [{title.replace(" | ResRef", "")}]({absolute(path)}): {description}')
        lines += ['', '## Research tools', '']
        for path in TOOL_PAGES:
            name = tool_guides().get(path, {}).get('name') or TOOL_PAGES[path][0].split(' — ')[0]
            lines.append(f'- [{name}]({absolute(path)}): {tool_guides().get(path, {}).get("summary") or TOOL_PAGES[path][1]}')
        topics = Category.objects.filter(parent=None, show_in_database=True).order_by('database_order', 'name')
        if topics:
            lines += ['', '## Database topics', '']
            for category in topics:
                summary = shorten(plain(category.description), 200)
                lines.append(f'- [{plain(category.name)}]({absolute(f"/database/{category.slug}")})' + (f': {summary}' if summary else ''))
        lines += ['', '## Latest articles', '']
        for post in published_posts().prefetch_related('categories').order_by('-published_at')[:30]:
            summary = shorten(clean_seo_text(post.seo_description) or plain(post.excerpt), 200)
            lines.append(f'- [{plain(post.title)}]({absolute(article_path(post))})' + (f': {summary}' if summary else ''))
        lines += ['', '## Optional', '',
                  f'- [Full article index]({absolute("/llms-full.txt")}): every published article with its summary',
                  f'- [Sitemap]({absolute("/sitemap.xml")})',
                  f'- [Terms of Use]({absolute("/terms-of-use")})',
                  f'- [Privacy Policy]({absolute("/privacy-policy")})', '']
        body = '\n'.join(lines)
        cache.set(key, body, 3600)
    return text_response(body, 'text/plain; charset=utf-8')


def llms_full_txt(request):
    key = f'seo:llms-full:{site_url()}'
    body = cache.get(key)
    if body is None:
        lines = [f'# {SITE_NAME} — full article index', '', f'> {ORGANIZATION_DESCRIPTION}', '']
        posts = published_posts().prefetch_related('categories', 'authors', 'contributor_assignments__contributor').order_by('-published_at')[:3000]
        for post in posts:
            assignments = [a.contributor for a in post.contributor_assignments.all() if a.role in {'author', 'co_author'}]
            authors = ', '.join(plain(author.display_name) for author in (assignments or list(post.authors.all())))
            outline = [text for tag, text in text_blocks(post.content, limit=20000) if tag in {'h2', 'h3'}][:15]
            lines += [f'## {plain(post.title)}', '', f'URL: {absolute(article_path(post))}']
            if authors:
                lines.append(f'Authors: {authors}')
            if post.published_at:
                lines.append(f'Published: {post.published_at.date().isoformat()}; updated: {post.updated_at.date().isoformat()}')
            summary = clean_seo_text(post.seo_description) or plain(post.excerpt)
            if summary:
                lines += ['', shorten(summary, 600)]
            if outline:
                lines += ['', 'Sections: ' + '; '.join(outline)]
            lines.append('')
        body = '\n'.join(lines)
        cache.set(key, body, 3600)
    return text_response(body, 'text/plain; charset=utf-8')


def index_path_for():
    return Path(settings.FRONTEND_DIST_DIR) / 'index.html'
