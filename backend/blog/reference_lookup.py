import hashlib
import html
import re
from difflib import SequenceMatcher
from urllib.parse import quote, urlparse

import requests
from django.conf import settings
from django.core.cache import cache


CROSSREF_BASE_URL = 'https://api.crossref.org/v1'
OPENALEX_BASE_URL = 'https://api.openalex.org'
DOI_RESOLVER_URL = 'https://doi.org'
PUBMED_SUMMARY_URL = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi'
OPENLIBRARY_BOOKS_URL = 'https://openlibrary.org/api/books'
DOI_PATTERN = re.compile(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', re.IGNORECASE)
# "PMID: 12345678", "pubmed.ncbi.nlm.nih.gov/12345678" or a bare 5-9 digit number.
PMID_PATTERN = re.compile(r'^(?:pmid\s*:?\s*|https?://(?:www\.)?(?:pubmed\.ncbi\.nlm\.nih\.gov|ncbi\.nlm\.nih\.gov/pubmed)/)?(\d{5,9})/?$', re.IGNORECASE)
ISBN_PATTERN = re.compile(r'^(?:isbn(?:-1[03])?\s*:?\s*)?([0-9][0-9\- ]{8,16}[0-9Xx])$', re.IGNORECASE)
SOURCE_TYPES = {'journal', 'book', 'chapter', 'report', 'website'}
MAX_QUERY_LINES = 5
MAX_RESULTS = 8
CACHE_SECONDS = 15 * 60


def clean_text(value):
    if isinstance(value, list):
        value = ' '.join(str(item) for item in value if item)
    value = html.unescape(str(value or ''))
    return re.sub(r'<[^>]+>', '', value).strip()


def first_value(value):
    return clean_text(value[0]) if isinstance(value, list) and value else clean_text(value)


def normalize_doi(value):
    match = DOI_PATTERN.search(value or '')
    return match.group(0).rstrip('.,') if match else ''


def normalize_isbn(value):
    """Return a valid ISBN-10 or ISBN-13 (digits only) found in the text, else ''."""
    match = ISBN_PATTERN.match(clean_text(value))
    if not match:
        return ''
    digits = re.sub(r'[^0-9Xx]', '', match.group(1)).upper()
    if len(digits) == 13 and digits.isdigit() and digits[:3] in ('978', '979'):
        total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
        return digits if (10 - total % 10) % 10 == int(digits[12]) else ''
    if len(digits) == 10 and digits[:9].isdigit():
        total = sum((10 - i) * int(d) for i, d in enumerate(digits[:9])) + (10 if digits[9] == 'X' else int(digits[9]) if digits[9].isdigit() else -999)
        return digits if total % 11 == 0 else ''
    return ''


def normalize_pmid(value):
    match = PMID_PATTERN.match(clean_text(value))
    return match.group(1) if match else ''


NAME_AFFIXES = re.compile(r'^(dr|prof|professor|mr|mrs|ms|md|m\.d|phd|ph\.d|mph|msc|bsc|frcp|frcs|facp|rn|dds|dmd|mba)\.?,?$', re.IGNORECASE)


def split_name(display_name):
    # Titles and degrees ("Dr", "M.D.", "PhD") are not part of the name.
    parts = [part for part in clean_text(display_name).replace(',', ' ').split() if not NAME_AFFIXES.match(part)]
    return {'first': ' '.join(parts[:-1]), 'middle': '', 'last': parts[-1]} if parts else {'first': '', 'middle': '', 'last': ''}


def request_headers():
    email = settings.CROSSREF_POLITE_EMAIL
    suffix = f' (mailto:{email})' if email else ''
    return {'User-Agent': f'ResRef-Citation-Generator/1.0{suffix}', 'Accept': 'application/json'}


def crossref_params(extra=None):
    params = dict(extra or {})
    if settings.CROSSREF_POLITE_EMAIL:
        params['mailto'] = settings.CROSSREF_POLITE_EMAIL
    return params


def crossref_to_record(item):
    issued = item.get('issued', {}).get('date-parts') or item.get('created', {}).get('date-parts') or [[]]
    authors = [
        {
            'first': clean_text(author.get('given')),
            'middle': '',
            'last': clean_text(author.get('family') or author.get('name')),
        }
        for author in item.get('author', [])
        if author.get('given') or author.get('family') or author.get('name')
    ]
    crossref_type = item.get('type', '')
    source_type = CROSSREF_TYPES.get(crossref_type, 'journal')
    container = first_value(item.get('container-title'))
    publisher = clean_text(item.get('publisher'))
    editors = '; '.join(
        ' '.join(part for part in (clean_text(editor.get('given')), clean_text(editor.get('family') or editor.get('name'))) if part)
        for editor in item.get('editor', [])
    )
    institution = first_value([entry.get('name') for entry in item.get('institution', []) if entry.get('name')])
    return {
        'source': 'crossref',
        'type': source_type,
        'title': first_value(item.get('title')),
        'journal': container if source_type == 'journal' else '',
        'journal_abbrev': first_value(item.get('short-container-title')) if source_type == 'journal' else '',
        'booktitle': container if source_type == 'chapter' else '',
        'editors': editors,
        'org': (institution or publisher) if source_type == 'report' else '',
        'site': (clean_text(item.get('group-title')) or institution or publisher) if source_type == 'website' else '',
        'number': clean_text(item.get('number')) if source_type == 'report' else '',
        'edition': clean_text(item.get('edition-number')),
        'isbn': first_value(item.get('ISBN')),
        'publisher': publisher,
        'year': str(issued[0][0]) if issued and issued[0] else '',
        'volume': clean_text(item.get('volume')),
        'issue': clean_text(item.get('issue')),
        'pages': clean_text(item.get('page')),
        'doi': clean_text(item.get('DOI')),
        'url': clean_text(item.get('URL')),
        'authors': authors,
    }


CROSSREF_TYPES = {
    'journal-article': 'journal',
    'book': 'book',
    'monograph': 'book',
    'edited-book': 'book',
    'reference-book': 'book',
    'book-set': 'book',
    'book-chapter': 'chapter',
    'book-section': 'chapter',
    'book-part': 'chapter',
    'reference-entry': 'chapter',
    'proceedings-article': 'chapter',
    'report': 'report',
    'report-component': 'report',
    'dissertation': 'report',
    'posted-content': 'website',
    'dataset': 'website',
}


def openalex_to_record(item):
    primary_location = item.get('primary_location') or {}
    source = primary_location.get('source') or item.get('host_venue') or {}
    biblio = item.get('biblio') or {}
    first_page = clean_text(biblio.get('first_page'))
    last_page = clean_text(biblio.get('last_page'))
    pages = f'{first_page}-{last_page}' if first_page and last_page else first_page
    authors = [
        split_name(authorship.get('author', {}).get('display_name'))
        for authorship in item.get('authorships', [])
        if authorship.get('author', {}).get('display_name')
    ]
    source_type = {
        'book': 'book',
        'book-chapter': 'chapter',
        'report': 'report',
        'dissertation': 'report',
    }.get(item.get('type'), 'journal')
    container = clean_text(source.get('display_name'))
    publisher = clean_text(source.get('host_organization_name'))
    return {
        'source': 'openalex',
        'type': source_type,
        'title': clean_text(item.get('title') or item.get('display_name')),
        'journal': container if source_type == 'journal' else '',
        'journal_abbrev': '',
        'booktitle': container if source_type == 'chapter' else '',
        'org': (publisher or container) if source_type == 'report' else '',
        'publisher': publisher,
        'year': str(item.get('publication_year') or ''),
        'volume': clean_text(biblio.get('volume')),
        'issue': clean_text(biblio.get('issue')),
        'pages': pages,
        'doi': normalize_doi(item.get('doi', '')),
        'url': clean_text(item.get('doi') or primary_location.get('landing_page_url') or item.get('id')),
        'authors': authors,
    }


def manual_url_record(url, forced_type=''):
    parsed = urlparse(url)
    hostname = parsed.hostname or ''
    return {
        'source': 'manual-url',
        'type': forced_type or 'website',
        'title': hostname,
        'journal': '',
        'journal_abbrev': '',
        'publisher': '',
        'site': hostname,
        'year': '',
        'volume': '',
        'issue': '',
        'pages': '',
        'doi': '',
        'url': url,
        'authors': [],
    }


def fetch_crossref_doi(doi):
    response = requests.get(
        f'{CROSSREF_BASE_URL}/works/{quote(doi, safe="")}',
        params=crossref_params(),
        headers=request_headers(),
        timeout=(3.05, 8),
    )
    if response.status_code == 404:
        # Not a Crossref DOI (e.g. DataCite: arXiv, Zenodo). doi.org returns
        # CSL-JSON for any registration agency.
        return fetch_doi_csl(doi)
    response.raise_for_status()
    return [crossref_to_record(response.json()['message'])]


def fetch_doi_csl(doi):
    response = requests.get(
        f'{DOI_RESOLVER_URL}/{quote(doi, safe="/")}',
        headers={**request_headers(), 'Accept': 'application/vnd.citationstyles.csl+json'},
        timeout=(3.05, 8),
    )
    response.raise_for_status()
    item = response.json()
    if not isinstance(item, dict) or not item.get('title'):
        return []
    csl_types = {'article-journal': 'journal-article', 'book': 'book', 'chapter': 'book-chapter', 'report': 'report', 'thesis': 'dissertation', 'paper-conference': 'proceedings-article'}
    item = {**item, 'type': csl_types.get(item.get('type'), 'posted-content'), 'DOI': item.get('DOI') or doi}
    record = crossref_to_record(item)
    record['source'] = 'doi.org'
    record['url'] = record['url'] or f'https://doi.org/{doi}'
    return [record]


def fetch_pubmed(pmid):
    response = requests.get(
        PUBMED_SUMMARY_URL,
        params={'db': 'pubmed', 'id': pmid, 'retmode': 'json', 'tool': 'resref'},
        headers=request_headers(),
        timeout=(3.05, 8),
    )
    response.raise_for_status()
    item = response.json().get('result', {}).get(pmid)
    if not item or item.get('error'):
        return []
    authors = []
    for author in item.get('authors', []):
        if author.get('authtype') not in (None, 'Author'):
            continue
        name = clean_text(author.get('name'))
        last, _, initials = name.rpartition(' ')
        # PubMed names look like "Smith JA"; collective names have no initials.
        if last and initials.isupper() and len(initials) <= 3:
            authors.append({'first': ' '.join(initials), 'middle': '', 'last': last})
        elif name:
            authors.append({'first': '', 'middle': '', 'last': name})
    ids = {entry.get('idtype'): entry.get('value') for entry in item.get('articleids', [])}
    doi = normalize_doi(ids.get('doi', ''))
    year = re.search(r'\d{4}', clean_text(item.get('pubdate')) or clean_text(item.get('epubdate')))
    return [{
        'source': 'pubmed',
        'type': 'journal',
        'title': clean_text(item.get('title')).rstrip('.'),
        'journal': clean_text(item.get('fulljournalname')),
        'journal_abbrev': clean_text(item.get('source')),
        'publisher': '',
        'year': year.group(0) if year else '',
        'volume': clean_text(item.get('volume')),
        'issue': clean_text(item.get('issue')),
        'pages': clean_text(item.get('pages')),
        'doi': doi,
        'pmid': pmid,
        'url': f'https://doi.org/{doi}' if doi else f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/',
        'authors': authors,
    }]


def fetch_isbn(isbn):
    response = requests.get(
        OPENLIBRARY_BOOKS_URL,
        params={'bibkeys': f'ISBN:{isbn}', 'format': 'json', 'jscmd': 'data'},
        headers=request_headers(),
        timeout=(3.05, 8),
    )
    response.raise_for_status()
    item = response.json().get(f'ISBN:{isbn}')
    if not item:
        return []
    year = re.search(r'\d{4}', clean_text(item.get('publish_date')))
    return [{
        'source': 'openlibrary',
        'type': 'book',
        'title': ': '.join(part for part in (clean_text(item.get('title')), clean_text(item.get('subtitle'))) if part),
        'journal': '',
        'journal_abbrev': '',
        'publisher': first_value([entry.get('name') for entry in item.get('publishers', []) if entry.get('name')]),
        'year': year.group(0) if year else '',
        'volume': '',
        'issue': '',
        'pages': '',
        'doi': '',
        'isbn': isbn,
        'url': clean_text(item.get('url')),
        'authors': [split_name(author.get('name')) for author in item.get('authors', []) if author.get('name')],
    }]


def search_crossref_title(query):
    response = requests.get(
        f'{CROSSREF_BASE_URL}/works',
        params=crossref_params({'query.title': query, 'rows': 5}),
        headers=request_headers(),
        timeout=(3.05, 8),
    )
    response.raise_for_status()
    return [crossref_to_record(item) for item in response.json().get('message', {}).get('items', [])]


def search_openalex_title(query):
    if not settings.OPENALEX_API_KEY:
        return []
    response = requests.get(
        f'{OPENALEX_BASE_URL}/works',
        params={'search': query, 'per-page': 5, 'api_key': settings.OPENALEX_API_KEY},
        headers=request_headers(),
        timeout=(3.05, 8),
    )
    response.raise_for_status()
    return [openalex_to_record(item) for item in response.json().get('results', [])]


def record_key(record):
    return '|'.join([
        clean_text(record.get('doi')).lower(),
        clean_text(record.get('title')).lower(),
        clean_text(record.get('url')).lower(),
    ])


def score_record(query, record):
    score = SequenceMatcher(None, query.lower(), clean_text(record.get('title')).lower()).ratio()
    year = int(record.get('year')) if str(record.get('year', '')).isdigit() else 0
    return score, year


def search_references(query, forced_type=''):
    forced_type = forced_type if forced_type in SOURCE_TYPES else ''
    query = clean_text(query)[:1200]
    cache_key = 'resref-citations:' + hashlib.sha256(f'{forced_type}:{query}'.encode('utf-8')).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    records = []
    lines = [line.strip() for line in query.splitlines() if line.strip()][:MAX_QUERY_LINES]
    for line in lines:
        doi = normalize_doi(line)
        try:
            if doi:
                records.extend(fetch_crossref_doi(doi))
                continue
            pmid = normalize_pmid(line)
            if pmid:
                records.extend(fetch_pubmed(pmid))
                continue
            isbn = normalize_isbn(line)
            if isbn:
                records.extend(fetch_isbn(isbn))
                continue
            if re.match(r'^https?://', line, re.IGNORECASE):
                records.append(manual_url_record(line, forced_type))
                continue
            records.extend(search_crossref_title(line))
            records.extend(search_openalex_title(line))
        except (requests.RequestException, KeyError, TypeError, ValueError):
            continue

    unique = {}
    for record in records:
        # A chosen source type only fills in when the source did not say;
        # it never turns a known book or chapter into a journal article.
        if forced_type and record.get('source') in ('manual-url',):
            record['type'] = forced_type
        key = record_key(record)
        if key and key not in unique:
            unique[key] = record
    # Results of the chosen source type are listed first.
    results = sorted(
        unique.values(),
        key=lambda item: (not forced_type or item.get('type') == forced_type, *score_record(query, item)),
        reverse=True,
    )[:MAX_RESULTS]
    cache.set(cache_key, results, CACHE_SECONDS)
    return results
