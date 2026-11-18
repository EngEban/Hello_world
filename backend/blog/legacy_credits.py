"""Version-one recovery of explicitly named WordPress credits.

Independent of live models so migrations can use historical models.
Never infer authorship from the uploader or modify article HTML.
"""
import re

from html.parser import HTMLParser
from django.db import transaction
from django.utils.text import slugify
from django.utils import timezone


def normalize_portrait(url):
    for host in ('http://resres.local', 'https://resres.local', 'http://resref.local', 'https://resref.local'):
        url = url.replace(f'{host}/wp-content/uploads/', 'https://resref.com/wp-content/uploads/')
    return url if url.startswith(('https://', 'http://')) else ''


class LegacyCreditsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.started = False
        self.heading = None
        self.name = ''
        self.image = ''
        self.profile_image = ''
        self.texts = []
        self.links = []
        self.profiles = {}

    def flush(self):
        if not self.name or len(self.name.split()) < 2 or len(self.name) > 200:
            return
        pattern = r'(?:Author|Co-author|Editor|Reviewer|Translator|Formatter)(?:\s*[&/]\s*(?:Translator|Formatter))?'
        role_text = next((text for text in self.texts[:2] if re.fullmatch(pattern, text, re.I)), '')
        if not role_text:
            return
        role = 'co_author' if role_text.lower() == 'co-author' else role_text.lower().split()[0]
        profile = self.profiles.setdefault((self.name, role), {
            'name': self.name, 'role': role, 'role_text': role_text,
            'bio': '', 'position': '', 'avatar': self.profile_image, 'links': {},
        })
        for text in self.texts:
            if len(text) > 150 and not text.startswith(('Phone:', 'Email:')) and len(text) > len(profile['bio']):
                profile['bio'] = text
            elif text != role_text and len(text) < 150 and any(word in text for word in ('Resident', 'Consultant')):
                profile['position'] = profile['position'] or text
        for url in self.links:
            if not url.startswith(('https://', 'http://')):
                continue
            for domain, field in [('linkedin.com', 'linkedin'), ('researchgate.net', 'researchgate'), ('scholar.google.', 'google_scholar'), ('orcid.org', 'orcid'), ('twitter.com', 'twitter'), ('facebook.com', 'website')]:
                if domain in url:
                    profile['links'].setdefault(field, url)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img':
            self.image = normalize_portrait(attrs.get('src', ''))
        if tag in ('h2', 'h3'):
            self.flush()
            self.name = ''
            self.heading = []
            self.texts, self.links = [], []
            self.profile_image = self.image
        elif tag == 'a' and self.started:
            self.links.append(attrs.get('href', ''))

    def handle_endtag(self, tag):
        if tag in ('h2', 'h3') and self.heading is not None:
            text = ' '.join(self.heading).strip()
            if text.lower() == 'authorship and contributions':
                self.started = True
            elif self.started:
                self.name = text
            self.heading = None

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return
        if self.heading is not None:
            self.heading.append(text)
        elif self.started and self.name:
            self.texts.append(text)


def extract_profiles(content):
    parser = LegacyCreditsParser()
    parser.feed(content)
    parser.flush()
    return list(parser.profiles.values())

def restore_article_credits_v1(post, Author, PostContributor, using='default'):
    """Return added role count, preserving explicit credits and card opt-outs."""
    with transaction.atomic(using=using):
        assignments = PostContributor.objects.using(using).filter(post_id=post.pk)
        if assignments.exists() or post.authors.exists():
            added = 0
        else:
            profiles = extract_profiles(post.content)
            authors = []
            for index, profile in enumerate(profiles):
                author = Author.objects.using(using).filter(display_name__iexact=profile['name']).order_by('pk').first()
                if not author:
                    base = slugify(profile['name'])[:180] or 'contributor'
                    slug, suffix = base, 2
                    while Author.objects.using(using).filter(slug=slug).exists():
                        slug = f'{base}-{suffix}'; suffix += 1
                    login = f'legacy-{slug}'[:100]
                    while Author.objects.using(using).filter(login=login).exists():
                        login = f'legacy-{slug[:80]}-{suffix}'; suffix += 1
                    author = Author.objects.using(using).create(
                        login=login, slug=slug, display_name=profile['name'],
                        bio=profile['bio'], short_bio=profile['bio'] if len(profile['bio']) <= 400 else profile['bio'][:397].rsplit(' ', 1)[0] + '…', position=profile['position'],
                        avatar=profile['avatar'], **profile['links'],
                        created_at=timezone.now(), updated_at=timezone.now(),
                    )
                else:
                    recovered = {'bio': profile['bio'], 'short_bio': profile['bio'][:397].rsplit(' ', 1)[0] + '…' if len(profile['bio']) > 400 else profile['bio'],
                                 'position': profile['position'], 'avatar': profile['avatar'], **profile['links']}
                    missing = {key: value for key, value in recovered.items() if value and not getattr(author, key)}
                    if missing:
                        Author.objects.using(using).filter(pk=author.pk).update(**missing)
                PostContributor.objects.using(using).create(post_id=post.pk, contributor_id=author.pk, role=profile['role'], display_order=index,
                                               contribution_note=profile['role_text'] if '&' in profile['role_text'] else '')
                authors.append(author)
            if authors:
                post.authors.set(authors)
            added = len(profiles)
        design = dict(post.design_settings or {})
        if (assignments.exists() or post.authors.exists()) and 'author_section_enabled' not in design:
            design['author_section_enabled'] = 'auto'
            # Preserve original publication and update dates.
            type(post).objects.using(using).filter(pk=post.pk).update(design_settings=design)
            post.design_settings = design
        return added
