"""Turn a WordPress export (WXR XML or SQL dump) into one neutral data shape.

Both readers return a ``WordPressData`` whose lists contain plain dicts, so
the importer never needs to know which export format it was given.
"""
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from urllib.parse import urlsplit

from django.utils import timezone

from . import phpserial
from .sqldump import detect_prefix, read_tables

WXR_NS = {
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'wp': 'http://wordpress.org/export/1.2/',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'excerpt': 'http://wordpress.org/export/1.2/excerpt/',
}
CONTENT_TYPES = {'post', 'page'}


@dataclass
class WordPressData:
    source_format: str
    site_url: str = ''
    authors: list = field(default_factory=list)      # users who wrote content
    users: list = field(default_factory=list)        # every WordPress account (SQL dumps only)
    categories: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    attachments: list = field(default_factory=list)
    items: list = field(default_factory=list)        # posts and pages
    redirects: list = field(default_factory=list)    # plugin redirects (SQL dumps only)
    notes: list = field(default_factory=list)        # format limitations worth reporting


def parse_wp_date(value):
    """WordPress GMT column (or wall-clock value used only for permalink tokens)."""
    value = (value or '').strip()
    if not value or value.startswith('0000-00-00'):
        return None
    try:
        parsed = datetime.strptime(value[:19], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None
    return parsed.replace(tzinfo=dt_timezone.utc)


def parse_local_wp_date(value):
    """WordPress site-local column, read in the project's TIME_ZONE."""
    parsed = parse_wp_date(value)
    return timezone.make_aware(parsed.replace(tzinfo=None)) if parsed else None


def to_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def wordpress_roles(capabilities):
    data = phpserial.loads(capabilities) if isinstance(capabilities, str) else capabilities
    if isinstance(data, dict):
        return sorted(str(role) for role, enabled in data.items() if enabled)
    return []


# --------------------------------------------------------------------------- WXR

def _t(element, path, default=''):
    return (element.findtext(path, default, WXR_NS) or default).strip()


def _xml_start(head):
    positions = [head.find(marker) for marker in (b'<?xml', b'<rss')]
    positions = [position for position in positions if position >= 0]
    return min(positions) if positions else -1


def read_wxr(path):
    with open(path, 'rb') as handle:
        raw = handle.read()
    start = _xml_start(raw[:2048])
    # Some plugins/themes print stray characters before the XML declaration; skip them.
    channel = ET.fromstring(raw[max(start, 0):]).find('channel')
    if channel is None:
        raise ValueError('The XML file does not contain a WordPress <channel>.')
    data = WordPressData('wxr', site_url=_t(channel, 'wp:base_blog_url') or _t(channel, 'link'))
    if start > 0:
        data.notes.append(f'Ignored {start} stray byte(s) before the XML declaration.')
    data.notes.append('WXR exports contain no passwords, user biographies or redirect-plugin rules; use a SQL dump for those.')

    for item in channel.findall('wp:author', WXR_NS):
        login = _t(item, 'wp:author_login')
        if login:
            data.authors.append({
                'wordpress_id': to_int(_t(item, 'wp:author_id')), 'login': login,
                'email': _t(item, 'wp:author_email'), 'display_name': _t(item, 'wp:author_display_name') or login,
                'first_name': _t(item, 'wp:author_first_name'), 'last_name': _t(item, 'wp:author_last_name'),
                'bio': '', 'website': '',
            })
    for item in channel.findall('wp:category', WXR_NS):
        slug = _t(item, 'wp:category_nicename')
        if slug:
            data.categories.append({
                'wordpress_id': to_int(_t(item, 'wp:term_id')), 'slug': slug,
                'name': _t(item, 'wp:cat_name') or slug, 'description': _t(item, 'wp:category_description'),
                'parent_slug': _t(item, 'wp:category_parent'),
            })
    for item in channel.findall('wp:tag', WXR_NS):
        slug = _t(item, 'wp:tag_slug')
        if slug:
            data.tags.append({
                'wordpress_id': to_int(_t(item, 'wp:term_id')), 'slug': slug,
                'name': _t(item, 'wp:tag_name') or slug, 'description': _t(item, 'wp:tag_description'),
            })

    known_categories = {row['slug'] for row in data.categories}
    known_tags = {row['slug'] for row in data.tags}
    for item in channel.findall('item'):
        post_type = _t(item, 'wp:post_type')
        wordpress_id = to_int(_t(item, 'wp:post_id'))
        if wordpress_id is None:
            continue
        meta = {
            _t(row, 'wp:meta_key'): _t(row, 'wp:meta_value')
            for row in item.findall('wp:postmeta', WXR_NS) if _t(row, 'wp:meta_key')
        }
        if post_type == 'attachment':
            data.attachments.append({
                'wordpress_id': wordpress_id, 'title': _t(item, 'title'), 'caption': _t(item, 'excerpt:encoded'),
                'description': _t(item, 'content:encoded'), 'alt_text': meta.get('_wp_attachment_image_alt', ''),
                'url': _t(item, 'wp:attachment_url'), 'attached_file': meta.get('_wp_attached_file', ''),
                'parent_id': to_int(_t(item, 'wp:post_parent')),
            })
            continue
        if post_type not in CONTENT_TYPES:
            continue
        categories, tags, coauthors = [], [], []
        for term in item.findall('category'):
            domain, slug, name = term.get('domain', ''), term.get('nicename', ''), (term.text or '').strip()
            if domain == 'category':
                categories.append(slug)
                if slug and slug not in known_categories:
                    known_categories.add(slug)
                    data.categories.append({'wordpress_id': None, 'slug': slug, 'name': name or slug, 'description': '', 'parent_slug': ''})
            elif domain == 'post_tag':
                tags.append(slug)
                if slug and slug not in known_tags:
                    known_tags.add(slug)
                    data.tags.append({'wordpress_id': None, 'slug': slug, 'name': name or slug, 'description': ''})
            elif domain == 'author':  # Co-Authors Plus
                coauthors.append(slug.removeprefix('cap-'))
        data.items.append({
            'wordpress_id': wordpress_id, 'post_type': post_type, 'status': _t(item, 'wp:status') or 'draft',
            'title': _t(item, 'title'), 'slug': _t(item, 'wp:post_name'), 'content': _t(item, 'content:encoded'),
            'excerpt': _t(item, 'excerpt:encoded'), 'author_login': _t(item, 'dc:creator'),
            'published_at': parse_wp_date(_t(item, 'wp:post_date_gmt')) or parse_local_wp_date(_t(item, 'wp:post_date')),
            'modified_at': None, 'link': _t(item, 'link'), 'parent_id': to_int(_t(item, 'wp:post_parent')),
            'meta': meta, 'categories': [slug for slug in categories if slug], 'tags': [slug for slug in tags if slug],
            'coauthors': coauthors,
        })
    return data


# --------------------------------------------------------------------- SQL dump

def _permalink(structure, item, site_url, categories_by_id, primary_category, authors_by_id, pages_by_id):
    base = site_url.rstrip('/')
    if item['post_type'] == 'page':
        slugs, current, seen = [], item, set()
        while current and current['wordpress_id'] not in seen:
            seen.add(current['wordpress_id'])
            slugs.append(current['slug'])
            current = pages_by_id.get(current.get('parent_id'))
        return f"{base}/{'/'.join(reversed(slugs))}/"
    if not structure:
        return f"{base}/?p={item['wordpress_id']}"
    date = item['published_at_local'] or timezone.now()
    category = categories_by_id.get(primary_category.get(item['wordpress_id']))
    author = authors_by_id.get(item['author_id'])
    tokens = {
        '%year%': f'{date.year:04d}', '%monthnum%': f'{date.month:02d}', '%day%': f'{date.day:02d}',
        '%hour%': f'{date.hour:02d}', '%minute%': f'{date.minute:02d}', '%second%': f'{date.second:02d}',
        '%postname%': item['slug'], '%post_id%': str(item['wordpress_id']),
        '%category%': category['slug'] if category else 'uncategorized',
        '%author%': author['login'] if author else '',
    }
    path = structure
    for token, value in tokens.items():
        path = path.replace(token, value)
    return base + ('/' + path.lstrip('/'))


def read_sql_dump(path, prefix=None):
    prefix = prefix or detect_prefix(path)
    names = {key: f'{prefix}{key}' for key in (
        'options', 'posts', 'postmeta', 'terms', 'term_taxonomy', 'term_relationships',
        'users', 'usermeta', 'redirection_items', 'rank_math_redirections',
    )}
    tables, columns = read_tables(path, names.values())
    get = lambda key: tables.get(names[key], [])  # noqa: E731
    if names['posts'] not in columns and not get('posts'):
        raise ValueError(f'No {names["posts"]} table found. Pass --table-prefix if the site uses a custom prefix.')

    options = {row.get('option_name'): row.get('option_value') or '' for row in get('options')}
    site_url = options.get('home') or options.get('siteurl') or ''
    data = WordPressData('sql', site_url=site_url)

    usermeta = defaultdict(dict)
    for row in get('usermeta'):
        usermeta[to_int(row.get('user_id'))][row.get('meta_key')] = row.get('meta_value') or ''
    users_by_id = {}
    for row in get('users'):
        user_id = to_int(row.get('ID'))
        meta = usermeta.get(user_id, {})
        record = {
            'wordpress_id': user_id, 'login': row.get('user_login') or '', 'email': row.get('user_email') or '',
            'display_name': row.get('display_name') or row.get('user_login') or '',
            'first_name': meta.get('first_name', ''), 'last_name': meta.get('last_name', ''),
            'bio': meta.get('description', ''), 'website': row.get('user_url') or '',
            'nicename': row.get('user_nicename') or '', 'registered': parse_wp_date(row.get('user_registered')),
            'password_hash': row.get('user_pass') or '',
            'roles': wordpress_roles(meta.get(f'{prefix}capabilities', '')),
        }
        users_by_id[user_id] = record
        data.users.append(record)

    terms = {to_int(row.get('term_id')): row for row in get('terms')}
    taxonomy_by_tt = {}
    for row in get('term_taxonomy'):
        term = terms.get(to_int(row.get('term_id')))
        if not term:
            continue
        taxonomy_by_tt[to_int(row.get('term_taxonomy_id'))] = {
            'taxonomy': row.get('taxonomy'), 'term_id': to_int(row.get('term_id')), 'slug': term.get('slug') or '',
            'name': term.get('name') or '', 'description': row.get('description') or '', 'parent': to_int(row.get('parent')) or 0,
        }
    categories_by_id = {}
    for tax in taxonomy_by_tt.values():
        if tax['taxonomy'] == 'category':
            categories_by_id[tax['term_id']] = tax
    for tax in taxonomy_by_tt.values():
        if tax['taxonomy'] == 'category':
            parent = categories_by_id.get(tax['parent'])
            data.categories.append({
                'wordpress_id': tax['term_id'], 'slug': tax['slug'], 'name': tax['name'],
                'description': tax['description'], 'parent_slug': parent['slug'] if parent else '',
            })
        elif tax['taxonomy'] == 'post_tag':
            data.tags.append({'wordpress_id': tax['term_id'], 'slug': tax['slug'], 'name': tax['name'], 'description': tax['description']})

    relationships = defaultdict(list)
    for row in get('term_relationships'):
        tax = taxonomy_by_tt.get(to_int(row.get('term_taxonomy_id')))
        if tax:
            relationships[to_int(row.get('object_id'))].append(tax)

    postmeta = defaultdict(dict)
    for row in get('postmeta'):
        postmeta[to_int(row.get('post_id'))][row.get('meta_key') or ''] = row.get('meta_value') or ''

    upload_base = site_url.rstrip('/') + '/wp-content/uploads/'
    pages_by_id, raw_items, primary_category = {}, [], {}
    for row in get('posts'):
        wordpress_id = to_int(row.get('ID'))
        post_type = row.get('post_type')
        meta = postmeta.get(wordpress_id, {})
        if post_type == 'attachment':
            attached = meta.get('_wp_attached_file', '')
            data.attachments.append({
                'wordpress_id': wordpress_id, 'title': row.get('post_title') or '', 'caption': row.get('post_excerpt') or '',
                'description': row.get('post_content') or '', 'alt_text': meta.get('_wp_attachment_image_alt', ''),
                'url': (upload_base + attached) if attached else (row.get('guid') or ''), 'attached_file': attached,
                'parent_id': to_int(row.get('post_parent')),
            })
            continue
        if post_type not in CONTENT_TYPES:
            continue
        terms_for_post = relationships.get(wordpress_id, [])
        item = {
            'wordpress_id': wordpress_id, 'post_type': post_type, 'status': row.get('post_status') or 'draft',
            'title': row.get('post_title') or '', 'slug': row.get('post_name') or '', 'content': row.get('post_content') or '',
            'excerpt': row.get('post_excerpt') or '', 'author_id': to_int(row.get('post_author')),
            'published_at': parse_wp_date(row.get('post_date_gmt')) or parse_local_wp_date(row.get('post_date')),
            'published_at_local': parse_wp_date(row.get('post_date')),
            'modified_at': parse_wp_date(row.get('post_modified_gmt')), 'parent_id': to_int(row.get('post_parent')),
            'meta': meta,
            'categories': [tax['slug'] for tax in terms_for_post if tax['taxonomy'] == 'category'],
            'tags': [tax['slug'] for tax in terms_for_post if tax['taxonomy'] == 'post_tag'],
            'coauthors': [tax['slug'].removeprefix('cap-') for tax in terms_for_post if tax['taxonomy'] == 'author'],
        }
        primary = to_int(meta.get('rank_math_primary_category')) or to_int(meta.get('_yoast_wpseo_primary_category'))
        candidates = [tax['term_id'] for tax in terms_for_post if tax['taxonomy'] == 'category']
        primary_category[wordpress_id] = primary if primary in candidates else (min(candidates) if candidates else None)
        if post_type == 'page':
            pages_by_id[wordpress_id] = item
        raw_items.append(item)

    structure = options.get('permalink_structure', '')
    author_ids = set()
    for item in raw_items:
        author = users_by_id.get(item['author_id'])
        item['author_login'] = author['login'] if author else ''
        if author:
            author_ids.add(item['author_id'])
        if item['status'] == 'publish' and item['slug']:
            item['link'] = _permalink(structure, item, site_url, categories_by_id, primary_category, users_by_id, pages_by_id)
        else:
            item['link'] = f"{site_url.rstrip('/')}/?p={item['wordpress_id']}"
        item.pop('published_at_local', None)
        data.items.append(item)
    data.authors = [users_by_id[user_id] for user_id in sorted(author_ids)]

    category_base = options.get('category_base', '')
    if category_base and category_base.strip('/') != 'category':
        data.notes.append(f'Custom category base "/{category_base.strip("/")}/": add a prefix redirect to /database/ if old category links matter.')

    for row in get('redirection_items'):
        if (row.get('status') or 'enabled') != 'enabled':
            continue
        target = row.get('action_data') or ''
        data.redirects.append({
            'wordpress_id': to_int(row.get('id')), 'source': 'wp_redirection', 'old': row.get('url') or '',
            'new': target, 'code': to_int(row.get('action_code')) or 301, 'regex': str(row.get('regex') or '0') == '1',
            'action': row.get('action_type') or 'url',
        })
    for row in get('rank_math_redirections'):
        if (row.get('status') or 'active') != 'active':
            continue
        sources = phpserial.loads(row.get('sources') or '') or {}
        for index, source in enumerate(sources.values() if isinstance(sources, dict) else []):
            if not isinstance(source, dict):
                continue
            data.redirects.append({
                'wordpress_id': (to_int(row.get('id')) or 0) * 1000 + index, 'source': 'rank_math',
                'old': source.get('pattern', ''), 'new': row.get('url_to') or '', 'code': to_int(row.get('header_code')) or 301,
                'regex': source.get('comparison', 'exact') != 'exact', 'action': 'url',
            })
    if f'{prefix}yoast_indexable' in columns or 'wpseo-premium-redirects-base' in options:
        data.notes.append('Yoast Premium redirects are stored in wp_options and are not imported automatically; export them as CSV from Yoast and add them in Django admin > Redirects.')
    return data


def read_source(path, fmt='auto', prefix=None):
    if fmt == 'auto':
        with open(path, 'rb') as handle:
            head = handle.read(4096)
        fmt = 'wxr' if 0 <= _xml_start(head) < 1024 else 'sql'
    return read_wxr(path) if fmt == 'wxr' else read_sql_dump(path, prefix=prefix)


def url_path(url):
    """Path part of a WordPress link (``/?p=12`` is returned with its query)."""
    parts = urlsplit(url or '')
    if parts.query and re.match(r'^(p|page_id)=\d+$', parts.query):
        return f'{parts.path or "/"}?{parts.query}'
    return parts.path or ''
