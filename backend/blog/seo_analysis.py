"""Server-side SEO / AEO / GEO analysis of articles.

This is the Python twin of frontend/src/pages/dashboard/posts/seoAnalysis.js,
which scores articles in real time in the editor. The dashboard overview and
the article library use the stored results of this module, so both must apply
the same rules; ``seo_analysis_cases.json`` holds shared cases that the
backend and frontend tests check against. The JavaScript file documents the
sources behind each threshold and owns the human-readable messages; this
module only returns statuses and scores.
"""
import json
import math
import re
import unicodedata
from datetime import datetime, timezone as dt_timezone
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ANALYSIS_VERSION = 1
TITLE_SUFFIX = ' | ResRef'
GROUPS = ('seo', 'readability', 'aeo', 'geo')
GROUP_WEIGHTS = {'seo': 0.4, 'readability': 0.2, 'aeo': 0.2, 'geo': 0.2}
CASES_PATH = Path(__file__).with_name('seo_analysis_cases.json')

# (id, group, weight) — the same catalogue and order as CHECKS in seoAnalysis.js.
CHECKS = [
    ('keyphrase', 'seo', 4), ('keyphrase_length', 'seo', 1), ('keyphrase_in_title', 'seo', 3),
    ('keyphrase_in_description', 'seo', 2), ('keyphrase_in_intro', 'seo', 2), ('keyphrase_in_slug', 'seo', 1),
    ('keyphrase_density', 'seo', 2), ('keyphrase_in_subheadings', 'seo', 2), ('keyphrase_in_alt', 'seo', 1),
    ('seo_title', 'seo', 2), ('title_length', 'seo', 2), ('meta_description', 'seo', 3), ('slug', 'seo', 1),
    ('text_length', 'seo', 3), ('single_h1', 'seo', 2), ('internal_links', 'seo', 2), ('outbound_links', 'seo', 1),
    ('link_health', 'seo', 2), ('featured_image', 'seo', 2), ('images', 'seo', 1), ('image_alt', 'seo', 2),
    ('subheading_distribution', 'readability', 2), ('paragraph_length', 'readability', 2),
    ('sentence_length', 'readability', 2), ('transition_words', 'readability', 1), ('passive_voice', 'readability', 1),
    ('sentence_variety', 'readability', 1), ('reading_ease', 'readability', 1),
    ('direct_answer', 'aeo', 3), ('questions', 'aeo', 2), ('concise_answers', 'aeo', 2), ('faq', 'aeo', 2),
    ('lists_tables', 'aeo', 2), ('definition', 'aeo', 1),
    ('citations', 'geo', 3), ('source_quality', 'geo', 1), ('statistics', 'geo', 2), ('quotations', 'geo', 1),
    ('author', 'geo', 2), ('freshness', 'geo', 1), ('sections', 'geo', 2), ('summary', 'geo', 1), ('topics', 'geo', 1),
    ('excerpt', 'geo', 1), ('structured_data', 'geo', 1),
]
CHECK_IDS = [check_id for check_id, _group, _weight in CHECKS]
CHECK_INFO = {check_id: (group, weight) for check_id, group, weight in CHECKS}
KEYPHRASE_CHECKS = {'keyphrase_length', 'keyphrase_in_title', 'keyphrase_in_description', 'keyphrase_in_intro',
                    'keyphrase_in_slug', 'keyphrase_density', 'keyphrase_in_subheadings', 'keyphrase_in_alt'}

STOP_WORDS = set('a an and are as at be but by for from has have how i if in into is it its of on or our so than that the '
                 'their them there these this those to was we were what when where which who why will with you your can do '
                 'does vs about after before over under between'.split())
QUESTION_STARTERS = set('what how why when where who whom whose which can could does do did is are should will would was were'.split())
TRANSITIONS = [
    'accordingly', 'additionally', 'afterwards', 'also', 'although', 'besides', 'because', 'consequently', 'conversely',
    'finally', 'first', 'firstly', 'second', 'secondly', 'third', 'furthermore', 'hence', 'however', 'indeed', 'instead',
    'likewise', 'meanwhile', 'moreover', 'nevertheless', 'nonetheless', 'otherwise', 'overall', 'similarly', 'specifically',
    'subsequently', 'then', 'therefore', 'thus', 'ultimately', 'whereas', 'while', 'yet', 'for example', 'for instance',
    'in addition', 'in contrast', 'in fact', 'in particular', 'in short', 'in summary', 'in conclusion', 'as a result',
    'on the other hand', 'such as', 'to illustrate', 'that is', 'in other words', 'as well as', 'even though', 'due to',
    'because of', 'above all', 'after all', 'by contrast', 'in turn', 'to summarize', 'notably', 'importantly',
]
IRREGULAR_PARTICIPLES = ('been begun bitten blown born borne bought brought built caught chosen done drawn driven eaten fallen '
                         'felt found forgotten forgiven frozen given gone grown held hidden hit hurt kept known laid led left lent '
                         'lost made meant met paid put read risen run said seen sent set shown shut sold spent spoken spread stolen '
                         'struck sung taken taught thought thrown told understood withdrawn won worn written').split()
PASSIVE_PATTERN = re.compile(
    r'\b(?:am|is|are|was|were|be|been|being|get|gets|got|gotten)\s+(?:\w+ly\s+)?(?:\w+ed|' + '|'.join(IRREGULAR_PARTICIPLES) + r')\b',
    re.ASCII)
SUMMARY_HEADINGS = ['key takeaways', 'key takeaway', 'takeaways', 'summary', 'conclusion', 'conclusions', 'tl dr', 'tldr',
                    'bottom line', 'final thoughts', 'in brief', 'key points', 'a word from', 'wrapping up']
DEFINITION_VERBS = set('is are was were refers means describes defined measures assesses evaluates represents involves'.split())
AUTHORITATIVE_HOSTS = ['doi.org', 'ncbi.nlm.nih.gov', 'nih.gov', 'who.int', 'cdc.gov', 'europepmc.org', 'cochranelibrary.com',
                       'nature.com', 'sciencedirect.com', 'springer.com', 'wiley.com', 'thelancet.com', 'nejm.org', 'bmj.com',
                       'jamanetwork.com', 'plos.org', 'frontiersin.org', 'tandfonline.com', 'sagepub.com', 'oup.com',
                       'cambridge.org', 'apa.org', 'elsevier.com', 'cell.com', 'science.org', 'pnas.org', 'arxiv.org',
                       'jstor.org', 'scholar.google.com']
DEV_HOST = re.compile(r'^(localhost|127\.0\.0\.1|\[::1\]|0\.0\.0\.0)(:\d+)?$|\.(local|localhost|test|invalid)(:\d+)?$')
INVISIBLE = re.compile('[​-‍﻿]')
PLACEHOLDER = re.compile(r'%{1,2}[a-z_]+%{1,2}', re.IGNORECASE)
QUESTION_MARK = re.compile('[?؟]')
ENDS_WITH_QUESTION = re.compile('[?؟]\\s*$')
SENTENCE_SPLIT = re.compile('(?<=[.!?؟])\\s+')
FAQ_NUMBERING = re.compile(r'^\s*(?:q(?:uestion)?\s*\d*\s*[:.)-]|\d+\s*[.)-])\s*', re.IGNORECASE)
REFERENCE_HEADING = re.compile(r' (references?|sources?|bibliography|works cited|citations?|further reading|reference list|literature cited)\b')
STATISTIC = re.compile(r'\d+(?:[.,]\d+)?\s?%|\d+\.\d+|\b\d{2,}\b', re.ASCII)
QUOTE = re.compile('“[^”]{20,}”|"[^"]{20,}"')
SLUG_PATTERN = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


# --------------------------------------------------------------------------- text helpers

def js_round(value):
    """Math.round semantics (half up), so scores match the browser exactly."""
    return int(math.floor(value + 0.5))


WHITESPACE = re.compile(r'\s+')
NON_WORD = re.compile(r'[\W_]+')
WORD_CHAR = re.compile(r'[^\W_]')


def squash(value):
    return WHITESPACE.sub(' ', INVISIBLE.sub('', str(value or ''))).strip()


def strip_placeholders(value):
    return re.sub(r'^[\s|:–—-]+|[\s|:–—-]+$', '', squash(PLACEHOLDER.sub('', str(value or '')))).strip()


@lru_cache(maxsize=8192)
def _normalize(text):
    text = text.lower()
    if not text.isascii():
        text = unicodedata.normalize('NFKD', text)
        text = ''.join(char for char in text if not unicodedata.category(char).startswith('M'))
    text = INVISIBLE.sub('', text).replace("'", '').replace('’', '')
    return NON_WORD.sub(' ', text).strip()


def normalize(value):
    return _normalize(str(value or ''))


@lru_cache(maxsize=8192)
def _tokens(text):
    normal = _normalize(text)
    return tuple(normal.split(' ')) if normal else ()


def tokens(value):
    return _tokens(str(value or ''))


def stem(word):
    if len(word) > 4 and word.endswith('ies'):
        return word[:-3] + 'y'
    if len(word) > 3 and word.endswith('s') and not word.endswith('ss'):
        return word[:-1]
    return word


def content_words(phrase):
    words = tokens(phrase)
    kept = [word for word in words if word not in STOP_WORDS]
    return [stem(word) for word in (kept or words)]


@lru_cache(maxsize=8192)
def _count_words(text):
    return sum(1 for word in squash(text).split(' ') if WORD_CHAR.search(word))


def count_words(value):
    return _count_words(str(value or ''))


@lru_cache(maxsize=4096)
def _sentences(text):
    return tuple(sentence for sentence in SENTENCE_SPLIT.split(squash(text)) if tokens(sentence))


def sentences_of(text):
    return list(_sentences(str(text or '')))


def pct(part, whole):
    return (part / whole) * 100 if whole else 0


def phrase_match(text, phrase):
    words = [stem(word) for word in tokens(text)]
    wanted = [stem(word) for word in tokens(phrase)]
    if not wanted or not words:
        return 'none'
    if f" {' '.join(wanted)} " in f" {' '.join(words)} ":
        return 'exact'
    present = set(words)
    return 'all' if all(word in present for word in content_words(phrase)) else 'none'


def matches_any(text, phrases):
    return any(phrase_match(text, phrase) != 'none' for phrase in phrases)


def overlap(text, reference):
    wanted = list(dict.fromkeys(content_words(text)))
    if not wanted:
        return 1
    present = {stem(word) for word in tokens(reference)}
    return sum(1 for word in wanted if word in present) / len(wanted)


def suggest_keyphrase(title):
    head = re.split(r'\s*[:|–—]\s*|\s+-\s+', squash(title))[0] if squash(title) else ''
    head = squash(re.sub(r'\([^)]*\)', ' ', head))
    return head if 1 <= count_words(head) <= 6 else ''


# --------------------------------------------------------------------------- HTML parsing

BLOCK_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'blockquote', 'td', 'th', 'dt', 'dd', 'figcaption', 'div', 'section', 'br', 'tr'}
SKIP_TAGS = {'script', 'style', 'noscript', 'iframe', 'svg', 'button', 'form', 'select', 'textarea', 'template', 'object'}
KEPT_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'}


class _Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.images, self.links = [], [], []
        self.lists = self.tables = self.blockquotes = 0
        self._buffer, self._tag, self._skip = [], 'p', 0

    def _flush(self):
        text = squash(''.join(self._buffer))
        if text:
            self.blocks.append({'tag': self._tag, 'text': text})
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip += 1
            return
        if self._skip:
            return
        if tag in BLOCK_TAGS:
            self._flush()
            self._tag = tag if tag in KEPT_TAGS else 'cell' if tag in {'td', 'th'} else 'p'
        if tag in {'ul', 'ol'}:
            self.lists += 1
        elif tag == 'table':
            self.tables += 1
        elif tag == 'blockquote':
            self.blockquotes += 1
        values = {}
        for name, value in attrs:
            values.setdefault(name, value)
        if tag == 'img':
            self.images.append({'src': values.get('src') or '', 'alt': squash(values.get('alt') or '')})
        elif tag == 'a' and values.get('href'):
            self.links.append({'href': values['href'].strip(), 'block': len(self.blocks)})

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag in BLOCK_TAGS:
            self._flush()
            self._tag = 'p'

    def handle_data(self, data):
        if not self._skip:
            self._buffer.append(data)

    def close(self):
        super().close()
        self._flush()


def parse_html(html):
    parser = _Document()
    try:
        parser.feed(str(html or ''))
        parser.close()
    except Exception:  # pragma: no cover - HTMLParser is lenient; never fail an analysis
        pass
    return parser


def is_heading(block):
    return block['tag'] in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}


def heading_level(block):
    return int(block['tag'][1])


def is_question(text):
    words = tokens(text)
    return bool(ENDS_WITH_QUESTION.search(text)) or bool(words and words[0] in QUESTION_STARTERS)


def host_of(href):
    try:
        parts = urlsplit(href)
        parts.port  # noqa: B018 - raises ValueError for malformed hosts such as "https://doi:10.1037/…"
        host = parts.netloc.lower()
    except ValueError:
        return ''
    return host[4:] if host.startswith('www.') else host


def classify_link(href, site_host):
    value = href.strip().lower()
    if not value or value.startswith('#') or re.match(r'^(mailto|tel|javascript|data|sms|whatsapp):', value):
        return 'other'
    if re.match(r'^https?://', value) or value.startswith('//'):
        host = host_of('https:' + value if value.startswith('//') else value)
        if host and (host == site_host or host.endswith('.' + site_host)):
            return 'internal'
        return 'broken' if not host or DEV_HOST.search(host) else 'external'
    return 'internal'


def authoritative(host):
    return bool(re.search(r'\.(gov|edu|int)$', host) or re.search(r'\.(gov|edu|ac)\.[a-z]{2}$', host)
                or any(host == item or host.endswith('.' + item) for item in AUTHORITATIVE_HOSTS))


def find_section(blocks, test):
    index = next((i for i, block in enumerate(blocks) if is_heading(block) and heading_level(block) >= 2
                  and test(f" {normalize(block['text'])} ")), -1)
    if index < 0:
        return None
    level = heading_level(blocks[index])
    end = index + 1
    while end < len(blocks) and not (is_heading(blocks[end]) and heading_level(blocks[end]) <= level):
        end += 1
    return {'start': index, 'end': end, 'blocks': blocks[index + 1:end]}


def extract_faq(blocks):
    """Question/answer pairs inside a "Frequently asked questions" section."""
    section = find_section(blocks, lambda text: ' faq' in text or ' frequently asked ' in text)
    if not section:
        return {'found': False, 'items': []}
    items, current = [], None
    for block in section['blocks']:
        text, answer = block['text'], ''
        found = QUESTION_MARK.search(text)
        mark = found.start() if found else -1
        ends = bool(ENDS_WITH_QUESTION.search(text))
        if ends or (mark > 0 and count_words(text[:mark + 1]) <= 25 and (is_heading(block) or not current or current['answer'])):
            if not ends:
                answer, text = squash(text[mark + 1:]), text[:mark + 1]
            current = {'question': squash(FAQ_NUMBERING.sub('', text, count=1)), 'answer': answer, 'first': answer}
            items.append(current)
        elif current:
            current['answer'] = squash(f"{current['answer']} {text}")
            if not current['first']:
                current['first'] = text
    return {'found': True, 'items': [
        {'question': item['question'], 'answer': item['answer'][:2000], 'first': item['first']}
        for item in items if item['question'] and item['answer']
    ]}


def extract_references(blocks, links):
    section = find_section(blocks, lambda text: bool(REFERENCE_HEADING.match(text)))
    if not section:
        return {'found': False, 'items': 0, 'links': []}
    inside = [link['href'] for link in links if section['start'] < link['block'] < section['end']
              and re.match(r'^https?://', link['href'], re.IGNORECASE)]
    return {'found': True, 'items': sum(1 for block in section['blocks'] if count_words(block['text']) >= 3), 'links': inside}


NOT_LETTER = re.compile(r'[^a-z]')
SILENT_ENDING = re.compile(r'(?:[^laeiouy]es|ed|[^laeiouy]e)$')
VOWEL_GROUP = re.compile(r'[aeiouy]{1,2}')


@lru_cache(maxsize=16384)
def syllables(word):
    value = NOT_LETTER.sub('', word.lower())
    if not value:
        return 0
    if len(value) <= 3:
        return 1
    value = SILENT_ENDING.sub('', value)
    value = value[1:] if value.startswith('y') else value
    return max(1, len(VOWEL_GROUP.findall(value)))


def measure(data):
    doc = parse_html(data.get('content'))
    blocks = doc.blocks
    prose = [block for block in blocks if block['tag'] in {'p', 'li'}]
    paragraphs = [block for block in blocks if block['tag'] == 'p']
    body_text = ' '.join(block['text'] for block in blocks)
    sentences = [sentence for block in prose for sentence in sentences_of(block['text'])]
    headings = [block for block in blocks if is_heading(block) and heading_level(block) >= 2]
    subheadings = [block for block in headings if heading_level(block) <= 3]
    intro = next((block['text'] for block in paragraphs if count_words(block['text']) >= 5), '')
    site_host = str(data.get('site_host') or 'resref.com').lower()
    site_host = site_host[4:] if site_host.startswith('www.') else site_host
    kinds = [classify_link(link['href'], site_host) for link in doc.links]
    internal = [link for link, kind in zip(doc.links, kinds) if kind == 'internal']
    external = [link for link, kind in zip(doc.links, kinds) if kind == 'external']
    broken = [link for link, kind in zip(doc.links, kinds) if kind == 'broken']
    external_hosts = list(dict.fromkeys(
        host for host in (host_of('https:' + link['href'] if link['href'].startswith('//') else link['href']) for link in external) if host))

    section_words = [0]
    for block in blocks:
        if is_heading(block):
            section_words.append(0)
        else:
            section_words[-1] += count_words(block['text'])

    sentence_words = [count_words(sentence) for sentence in sentences]
    starts = [(tokens(sentence) or [''])[0] for sentence in sentences]
    repeated_runs, run = 0, 1
    for index, start in enumerate(starts):
        run = run + 1 if index and start and start == starts[index - 1] else 1
        if run == 3:
            repeated_runs += 1
    joined = [f" {' '.join(tokens(sentence))} " for sentence in sentences]
    paragraph_sentences = [f" {' '.join(tokens(sentence))} " for block in paragraphs for sentence in sentences_of(block['text'])]
    letter_words = [word for sentence in sentences for word in tokens(sentence) if re.search(r'[a-z]', word)]
    flesch = None
    if sentences and letter_words:
        syllable_count = sum(syllables(word) for word in letter_words)
        flesch = 206.835 - 1.015 * (len(letter_words) / len(sentences)) - 84.6 * (syllable_count / len(letter_words))
    faq = extract_faq(blocks)
    references = extract_references(blocks, doc.links)

    def answer_after(index):
        level = heading_level(blocks[index])
        following = next((block for block in blocks[index + 1:] if not is_heading(block) or heading_level(block) <= level), None)
        return following['text'] if following and not is_heading(following) else ''

    answers = [answer_after(index) for index, block in enumerate(blocks)
               if is_heading(block) and heading_level(block) >= 2 and is_question(block['text'])]
    answers += [item['first'] for item in faq['items']]
    arabic = len(re.findall('[؀-ۿ]', body_text))
    latin = len(re.findall('[a-z]', body_text, re.IGNORECASE))
    cells = [block['text'] for block in blocks if block['tag'] == 'cell']
    return {
        'doc': doc, 'blocks': blocks, 'intro': intro, 'words': sum(count_words(block['text']) for block in blocks),
        'sentences': sentences, 'headings': headings, 'subheadings': subheadings, 'paragraphs': paragraphs,
        'internal': internal, 'external': external, 'external_hosts': external_hosts, 'broken': broken,
        'language': 'ar' if arabic > latin else 'en',
        'h1': sum(1 for block in blocks if block['tag'] == 'h1'),
        'max_section_words': max(section_words),
        'long_paragraphs': sum(1 for block in paragraphs if count_words(block['text']) > 150),
        'very_long_paragraphs': sum(1 for block in paragraphs if count_words(block['text']) > 200),
        'long_sentence_pct': pct(sum(1 for count in sentence_words if count > 20), len(sentences)),
        'transition_pct': pct(sum(1 for text in paragraph_sentences if any(f' {word} ' in text for word in TRANSITIONS)), len(paragraph_sentences)),
        'paragraph_sentences': len(paragraph_sentences),
        'passive_pct': pct(sum(1 for text in joined if PASSIVE_PATTERN.search(text)), len(sentences)),
        'repeated_runs': repeated_runs, 'flesch': flesch,
        'questions': sum(1 for block in headings if is_question(block['text'])) + len(faq['items']),
        'concise_answers': sum(1 for text in answers if 20 <= count_words(text) <= 80),
        'answer_count': len(answers), 'faq': faq, 'references': references,
        'statistics': sum(1 for text in sentences + cells if STATISTIC.search(text)),
        'quotes': doc.blockquotes + len(QUOTE.findall(body_text)),
        'summary': any(any(f' {phrase} ' in f" {normalize(block['text'])} " for phrase in SUMMARY_HEADINGS) for block in headings),
        'authoritative_hosts': sum(1 for host in external_hosts if authoritative(host)),
    }


# --------------------------------------------------------------------------- rules

def parse_instant(value):
    if not value:
        return None
    if isinstance(value, datetime):
        moment = value
    else:
        try:
            moment = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except ValueError:
            return None
    return moment if moment.tzinfo else moment.replace(tzinfo=dt_timezone.utc)


def analyze(raw):
    """Statuses (good / warn / bad / na) for every check plus group scores."""
    data = {'title': '', 'seo_title': '', 'seo_description': '', 'excerpt': '', 'slug': '', 'content': '', 'post_type': 'post',
            'featured_image': '', 'categories': 0, 'tags': 0, 'contributors': 0, 'focus_keyphrase': '',
            'related_keyphrases': [], 'cornerstone': False, **raw}
    facts = measure(data)
    is_page = data['post_type'] == 'page'
    now = parse_instant(data.get('now')) or datetime.now(dt_timezone.utc)
    keyphrase = squash(data['focus_keyphrase'])
    synonyms = [squash(item) for item in (data['related_keyphrases'] or []) if squash(item)][:4]
    phrases = [phrase for phrase in [keyphrase, *synonyms] if phrase]
    title = squash(data['title'])
    custom_title = strip_placeholders(data['seo_title'])
    seo_title = custom_title or title
    rendered_title = f'{seo_title}{TITLE_SUFFIX}'
    description = strip_placeholders(data['seo_description'])
    excerpt = squash(data['excerpt'])
    slug = str(data['slug'] or '').strip()
    english = facts['language'] == 'en'
    reference = ' '.join([title, excerpt, facts['intro'], *(block['text'] for block in facts['headings'])])
    key_words = content_words(keyphrase) if keyphrase else []
    images = facts['doc'].images
    out = {}

    # --- search
    out['keyphrase'] = 'good' if keyphrase else 'bad'
    if keyphrase:
        count = len(key_words)
        out['keyphrase_length'] = 'good' if count <= 4 else 'warn' if count <= 8 else 'bad'
        in_title = phrase_match(seo_title, keyphrase)
        title_start = normalize(seo_title).startswith(normalize(keyphrase))
        out['keyphrase_in_title'] = 'good' if in_title == 'exact' and title_start else 'warn' if in_title != 'none' else 'bad'
        description_text = description or excerpt
        hits = sum(1 for sentence in sentences_of(description_text) if phrase_match(sentence, keyphrase) != 'none')
        out['keyphrase_in_description'] = 'bad' if not description_text or not hits else 'good' if hits <= 2 else 'warn'
        intro = facts['intro']
        intro_match = intro and any(matches_any(sentence, phrases) for sentence in sentences_of(intro))
        out['keyphrase_in_intro'] = ('bad' if not intro else 'good' if intro_match
                                     else 'warn' if matches_any(intro, phrases) else 'bad')
        slug_words = {stem(word) for word in tokens(slug.replace('-', ' '))}
        slug_hits = sum(1 for word in key_words if word in slug_words)
        out['keyphrase_in_slug'] = 'good' if slug_hits == len(key_words) else 'warn' if slug_hits else 'bad'
        hits = sum(1 for sentence in facts['sentences'] if phrase_match(sentence, keyphrase) != 'none')
        density = pct(hits, facts['words'])
        minimum = max(1, math.ceil(facts['words'] * 0.005))
        out['keyphrase_density'] = ('na' if not facts['words'] else 'bad' if density > 3
                                    else 'good' if hits >= minimum else 'warn')
        subheadings = facts['subheadings']
        with_keyphrase = sum(1 for block in subheadings if matches_any(block['text'], phrases))
        share = pct(with_keyphrase, len(subheadings))
        out['keyphrase_in_subheadings'] = (
            'na' if not subheadings else 'warn' if share > 75
            else 'good' if share >= 30 or (with_keyphrase >= 1 and len(subheadings) < 4)
            else 'warn' if with_keyphrase else 'bad')
        alt_hits = sum(1 for image in images if matches_any(image['alt'], phrases))
        alt_share = pct(alt_hits, len(images))
        out['keyphrase_in_alt'] = (
            'na' if not images else ('good' if alt_hits else 'warn') if len(images) < 5
            else 'warn' if alt_share > 70 else 'good' if alt_share >= 30 else 'warn')
    else:
        out.update({check_id: 'na' for check_id in KEYPHRASE_CHECKS})

    out['seo_title'] = 'warn' if not custom_title else 'bad' if overlap(custom_title, reference) < 0.3 else 'good'
    title_chars = len(rendered_title)
    out['title_length'] = 'warn' if title_chars > 60 or title_chars < 30 else 'good'
    out['meta_description'] = (
        'bad' if not description
        else 'bad' if overlap(description, reference) < 0.3 and len(content_words(description)) >= 5
        else 'warn' if len(description) > 156 or len(description) < 120 else 'good')
    out['slug'] = 'bad' if not slug else 'warn' if not SLUG_PATTERN.match(slug) or len(slug) > 75 else 'good'
    good_words, ok_words = (900, 400) if data['cornerstone'] else (300, 250)
    out['text_length'] = 'good' if facts['words'] >= good_words else 'warn' if facts['words'] >= ok_words else 'bad'
    out['single_h1'] = 'bad' if facts['h1'] else 'good'
    out['internal_links'] = 'good' if facts['internal'] else 'bad'
    out['outbound_links'] = 'good' if facts['external'] else 'warn'
    out['link_health'] = 'na' if not facts['doc'].links else 'bad' if facts['broken'] else 'good'
    out['featured_image'] = 'good' if data['featured_image'] else 'bad'
    out['images'] = 'good' if images else 'warn'
    missing_alt = sum(1 for image in images if not image['alt'])
    out['image_alt'] = 'na' if not images else 'good' if not missing_alt else 'bad' if missing_alt == len(images) else 'warn'

    # --- readability
    out['subheading_distribution'] = (
        'good' if facts['words'] <= 300 and not facts['headings']
        else 'bad' if facts['max_section_words'] > 350 else 'warn' if facts['max_section_words'] > 300 else 'good')
    out['paragraph_length'] = ('bad' if facts['very_long_paragraphs'] else 'warn' if facts['long_paragraphs']
                               else 'good' if facts['paragraphs'] else 'na')
    long_pct = facts['long_sentence_pct']
    out['sentence_length'] = 'na' if not facts['sentences'] else 'bad' if long_pct > 35 else 'warn' if long_pct > 25 else 'good'
    transition = facts['transition_pct']
    out['transition_words'] = ('na' if not english or facts['paragraph_sentences'] < 5
                               else 'good' if transition >= 30 else 'warn' if transition >= 20 else 'bad')
    passive = facts['passive_pct']
    out['passive_voice'] = ('na' if not english or not facts['sentences']
                            else 'bad' if passive > 15 else 'warn' if passive > 10 else 'good')
    out['sentence_variety'] = 'na' if not facts['sentences'] else 'warn' if facts['repeated_runs'] else 'good'
    flesch = facts['flesch']
    out['reading_ease'] = ('na' if not english or flesch is None or len(facts['sentences']) < 5
                           else 'good' if flesch >= 50 else 'warn' if flesch >= 30 else 'bad')

    if facts['words'] < 50:
        out.update({check_id: 'na' for check_id, group, _weight in CHECKS if group == 'readability'})

    # --- answers (AEO)
    intro_words = count_words(facts['intro'])
    out['direct_answer'] = ('bad' if not facts['intro'] else 'good' if 40 <= intro_words <= 60
                            else 'warn' if 25 <= intro_words <= 100 else 'bad')
    want_questions = 2 if facts['words'] >= 600 else 1
    out['questions'] = ('good' if facts['questions'] >= want_questions else 'warn' if facts['questions']
                        else 'bad' if facts['words'] >= 600 else 'warn')
    out['concise_answers'] = ('na' if not facts['answer_count']
                              else 'good' if facts['concise_answers'] / facts['answer_count'] >= 0.5
                              else 'warn' if facts['concise_answers'] else 'bad')
    out['faq'] = 'good' if len(facts['faq']['items']) >= 2 else 'warn'
    out['lists_tables'] = 'na' if facts['words'] < 300 else 'good' if facts['doc'].lists + facts['doc'].tables else 'warn'
    subject = keyphrase or suggest_keyphrase(title)
    first_sentence = (sentences_of(facts['intro']) or [''])[0]
    defines = subject and phrase_match(first_sentence, subject) != 'none'
    out['definition'] = ('na' if not facts['intro'] or not subject
                         else 'good' if defines and any(word in DEFINITION_VERBS for word in tokens(first_sentence)) else 'warn')

    # --- AI visibility (GEO)
    refs = facts['references']
    out['citations'] = ('good' if (refs['found'] and (refs['items'] >= 3 or refs['links'])) or len(facts['external_hosts']) >= 3
                        else 'warn' if refs['found'] or facts['external'] else 'bad')
    out['source_quality'] = 'na' if not facts['external'] else 'good' if facts['authoritative_hosts'] else 'warn'
    out['statistics'] = 'good' if facts['statistics'] >= 3 else 'warn'
    out['quotations'] = 'good' if facts['quotes'] else 'warn'
    out['author'] = 'na' if is_page else 'good' if data['contributors'] else 'bad'
    updated = parse_instant(data.get('updated_at')) or now
    age_days = (now - updated).total_seconds() / 86400
    out['freshness'] = ('warn' if is_page else 'bad') if not data.get('published_at') else 'warn' if age_days > 365 else 'good'
    h2 = sum(1 for block in facts['blocks'] if block['tag'] == 'h2')
    if facts['words'] >= 600:
        out['sections'] = 'good' if h2 >= 3 else 'warn' if h2 else 'bad'
    else:
        out['sections'] = 'good' if h2 else 'warn'
    out['summary'] = 'good' if facts['summary'] else 'warn'
    out['topics'] = ('na' if is_page else 'good' if data['categories'] and data['tags']
                     else 'warn' if data['categories'] or data['tags'] else 'bad')
    out['excerpt'] = 'good' if len(excerpt) >= 70 else 'warn' if excerpt else 'bad'
    missing = [not data['featured_image'], not data.get('published_at'), not is_page and not data['contributors'], len(title) > 110]
    out['structured_data'] = 'na' if is_page else 'warn' if any(missing) else 'good'

    checks = {check_id: out[check_id] for check_id in CHECK_IDS}
    return {
        'version': ANALYSIS_VERSION, 'language': facts['language'], 'words': facts['words'],
        'scores': score_checks(checks), 'checks': checks,
        'faq': [{'question': item['question'], 'answer': item['answer']} for item in facts['faq']['items']],
        'references': refs['links'],
    }


POINTS = {'good': 1, 'warn': 0.5, 'bad': 0}


def score_checks(checks):
    totals = {}
    for check_id, status in checks.items():
        if check_id not in CHECK_INFO or status not in POINTS:
            continue
        group, weight = CHECK_INFO[check_id]
        total = totals.setdefault(group, [0, 0])
        total[0] += weight * POINTS[status]
        total[1] += weight
    scores = {group: js_round(100 * totals[group][0] / totals[group][1]) if totals.get(group, [0, 0])[1] else None for group in GROUPS}
    used = [group for group in GROUPS if scores[group] is not None]
    share = sum(GROUP_WEIGHTS[group] for group in used)
    overall = 0
    for group in used:
        overall += scores[group] * GROUP_WEIGHTS[group]
    scores['overall'] = js_round(overall / share) if share else None
    return scores


def score_band(score):
    if score is None:
        return 'none'
    return 'good' if score >= 80 else 'ok' if score >= 50 else 'poor'


# --------------------------------------------------------------------------- settings and cached reports
# No database columns: the editor's settings live in ``Post.design_settings['seo']``
# and reports are computed on demand and kept in the cache. A report's cache key
# includes everything it depends on, so any edit produces a fresh analysis.

SETTINGS_KEY = 'seo'
CACHE_SECONDS = 7 * 24 * 3600  # also bounds how stale the "updated within a year" check can get
REPORT_PREFETCH = ('categories', 'tags', 'authors', 'contributor_assignments')


def clean_seo_settings(value):
    """Validate the editor's ``seo_settings`` payload."""
    value = value if isinstance(value, dict) else {}
    related = value.get('related_keyphrases') or []
    if isinstance(related, str):
        related = related.split(',')
    related = [squash(item)[:120] for item in related if isinstance(item, str) and squash(item)][:4]
    return {
        'focus_keyphrase': squash(value.get('focus_keyphrase') if isinstance(value.get('focus_keyphrase'), str) else '')[:120],
        'related_keyphrases': related,
        'cornerstone': value.get('cornerstone') is True,
    }


def post_seo_settings(post):
    design = post.design_settings if isinstance(post.design_settings, dict) else {}
    return clean_seo_settings(design.get(SETTINGS_KEY))


def site_host():
    from resref.seo import site_url
    host = urlsplit(site_url()).netloc.lower()
    return host[4:] if host.startswith('www.') else host


def _contributors(post):
    return len(post.contributor_assignments.all()) or len(post.authors.all())


def post_input(post, now=None, host=None):
    return {
        'title': post.title, 'seo_title': post.seo_title, 'seo_description': post.seo_description, 'excerpt': post.excerpt,
        'slug': post.slug, 'content': post.content, 'post_type': post.post_type, 'featured_image': post.featured_image,
        'published_at': post.published_at, 'updated_at': post.updated_at, 'categories': len(post.categories.all()),
        'tags': len(post.tags.all()), 'contributors': _contributors(post), 'now': now, 'site_host': host or site_host(),
        **post_seo_settings(post),
    }


def compact_report(report):
    """What the cache keeps: scores, statuses and a few counts (no text)."""
    return {'version': report['version'], 'language': report['language'], 'words': report['words'],
            'scores': report['scores'], 'checks': report['checks'], 'faq': len(report['faq']), 'references': len(report['references'])}


def report_key(post, host):
    # updated_at changes on every save; relation counts cover credits, categories and tags.
    stamp = post.updated_at.isoformat() if post.updated_at else ''
    return (f'seo-report:v{ANALYSIS_VERSION}:{host}:{post.pk}:{stamp}:'
            f'{len(post.categories.all())}:{len(post.tags.all())}:{_contributors(post)}')


def cached_reports(queryset, budget=None):
    """Reports for every post in ``queryset``: cached ones, plus up to ``budget`` newly analysed.

    Returns ``(reports_by_id, pending)`` where ``pending`` counts posts left unanalysed.
    """
    from django.core.cache import cache
    from blog.models import Post
    host = site_host()
    posts = list(queryset.defer('content', 'elementor_data').prefetch_related(*REPORT_PREFETCH))
    keys = {post.pk: report_key(post, host) for post in posts}
    found = cache.get_many(list(keys.values()))
    reports = {pk: found[key] for pk, key in keys.items() if key in found}
    missing = [pk for pk in keys if pk not in reports]
    todo = missing if budget is None else missing[:max(budget, 0)]
    fresh = {}
    for post in Post.objects.filter(pk__in=todo).prefetch_related(*REPORT_PREFETCH):
        report = compact_report(analyze(post_input(post, host=host)))
        reports[post.pk] = report
        fresh[report_key(post, host)] = report
    if fresh:
        cache.set_many(fresh, CACHE_SECONDS)
    return reports, len(missing) - len(fresh)


def report_for(post):
    """Analyse one post now (e.g. right after saving) and cache the result."""
    from blog.models import Post
    reports, _pending = cached_reports(Post.objects.filter(pk=post.pk))
    return reports.get(post.pk)


def load_cases():
    return json.loads(CASES_PATH.read_text(encoding='utf-8'))
