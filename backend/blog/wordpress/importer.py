"""Safe, repeatable WordPress import (merge engine).

Rules (see docs/launch/wordpress-migration.md):
* Never deletes anything: no rows, no files, no category/tag links.
* Matches by WordPress ID first (model ``wordpress_id`` or the import ledger),
  then by natural key (slug / login / email / URL).
* Three-way merge per field using the ledger: a field changes only when
  WordPress changed it AND nobody edited it in the new dashboard. Both changed
  -> conflict (kept local; ``--overwrite`` takes the WordPress value).
* Empty WordPress values never clear a filled field.
* Each entity runs in its own transaction; ``dry_run`` wraps everything in one
  transaction that is rolled back, and copies no files.
"""
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from django.contrib.auth.hashers import get_hashers_by_algorithm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from accounts.identity import find_user_by_email, normalize_email
from blog.models import Author, Category, MediaAsset, Post, Tag
from redirects.models import Redirect, WordPressImportRecord
from redirects.paths import normalize_path, safe_target
from redirects.targets import RESERVED_FIRST_SEGMENTS, RESERVED_PREFIXES, post_public_path

from .hashers import ALGORITHM as WP_HASH_ALGORITHM, is_supported_wordpress_hash
from .media import COPYABLE_EXTENSIONS, IMAGE_EXTENSIONS, MediaSource, MediaSourceError, extension, relative_upload_path, sha256, store_file
from .sources import url_path

ENTITY_ORDER = ['authors', 'categories', 'tags', 'media', 'posts', 'redirects', 'users']
DEFAULT_ENTITIES = [name for name in ENTITY_ORDER if name != 'users']
SKIPPED_STATUSES = {'auto-draft', 'inherit'}
STATUS_MAP = {'future': 'publish'}  # the public API already hides posts dated in the future
STAFF_ROLES = {'administrator', 'editor', 'author', 'contributor', 'shop_manager'}
UNEDITED_WINDOW = timedelta(minutes=10)
SEO_TOKEN = re.compile(r'%%?[a-z_]+(?:\([^)]*\))?%%?')


def fingerprint(value):
    if value is None:
        value = ''
    elif isinstance(value, datetime):
        value = value.astimezone(timezone.get_fixed_timezone(0)).replace(microsecond=0).isoformat()
    else:
        value = str(value).replace('\r\n', '\n').strip()
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:24]


def is_empty(value):
    return value is None or (isinstance(value, str) and not value.strip())


def clean_slug(value, limit):
    slug = slugify(value or '')[:limit]
    if not slug:
        from urllib.parse import unquote

        slug = slugify(unquote(value or ''), allow_unicode=True)[:limit]
    return slug.strip('-')


def resolve_seo(template, title, excerpt=''):
    """Turn Yoast/Rank Math templates into plain text; '' when it is only the default pattern."""
    if not template:
        return ''
    text = template
    for token in ('%%sitename%%', '%sitename%', '%%sep%%', '%sep%', '%%page%%', '%page%'):
        text = text.replace(token, ' ')
    for token in ('%%title%%', '%title%'):
        text = text.replace(token, title)
    for token in ('%%excerpt%%', '%excerpt%'):
        text = text.replace(token, excerpt)
    text = SEO_TOKEN.sub(' ', text)
    text = re.sub(r'\s+', ' ', text).strip(' -|–—:')
    return '' if text == title.strip() else text


class Report:
    OUTCOMES = ['created', 'updated', 'linked', 'unchanged', 'conflict', 'skipped', 'error']

    def __init__(self):
        self.counts = defaultdict(Counter)
        self.details = []
        self.notes = []
        self.extra = defaultdict(Counter)

    def add(self, entity, outcome, key, message='', fields=None):
        self.counts[entity][outcome] += 1
        if outcome in {'conflict', 'error', 'skipped', 'created', 'updated', 'linked'}:
            self.details.append({'entity': entity, 'outcome': outcome, 'key': str(key), 'message': message, 'fields': fields or []})

    def as_dict(self):
        return {
            'counts': {entity: dict(counter) for entity, counter in self.counts.items()},
            'extra': {entity: dict(counter) for entity, counter in self.extra.items()},
            'notes': self.notes, 'details': self.details,
        }

    def dumps(self):
        return json.dumps(self.as_dict(), indent=2, default=str)


class WordPressImporter:
    def __init__(self, data, *, dry_run=True, only=None, overwrite=False, uploads_dir=None, media_base_url=None,
                 optimize_images=False, import_password_hashes=False, published_only=False, skip_trash=False,
                 trust_unedited_before=None, assume_unedited=True, log=None):
        self.data = data
        self.dry_run = dry_run
        self.only = list(only or DEFAULT_ENTITIES)
        self.overwrite = overwrite
        self.media_source = MediaSource(uploads_dir, media_base_url)
        self.optimize_images = optimize_images
        self.import_password_hashes = import_password_hashes
        self.published_only = published_only
        self.skip_trash = skip_trash
        self.trust_unedited_before = trust_unedited_before
        self.assume_unedited = assume_unedited
        self.log = log or (lambda message: None)
        self.report = Report()
        self.report.notes.extend(data.notes)
        self.site_host = ''
        if data.site_url:
            from urllib.parse import urlsplit

            self.site_host = urlsplit(data.site_url).netloc.lower()

    # ------------------------------------------------------------------ run
    def run(self):
        if self.dry_run:
            with transaction.atomic():
                self._run_entities()
                transaction.set_rollback(True)
        else:
            self._run_entities()
        return self.report

    def _run_entities(self):
        for entity in ENTITY_ORDER:
            if entity not in self.only:
                continue
            self.log(f'Importing {entity}...')
            try:
                with transaction.atomic():
                    getattr(self, f'import_{entity}')()
            except Exception as exc:
                self.report.add(entity, 'error', '*', f'Whole {entity} batch rolled back: {type(exc).__name__}: {exc}')
                raise

    def _record(self, entity, key, func):
        """Run one record in a savepoint so a bad row cannot break the batch."""
        try:
            with transaction.atomic():
                return func()
        except Exception as exc:  # report and continue with the next record
            self.report.add(entity, 'error', key, f'{type(exc).__name__}: {exc}')
            return None

    # --------------------------------------------------------------- ledger
    @staticmethod
    def ledger(entity, wordpress_id):
        if wordpress_id is None:
            return None
        return WordPressImportRecord.objects.filter(entity=entity, wordpress_id=wordpress_id).first()

    def save_ledger(self, entity, wordpress_id, obj, incoming, record=None, checksum=None):
        if wordpress_id is None:
            return
        hashes = dict(record.field_hashes) if record else {}
        hashes.update({name: fingerprint(value) for name, value in incoming.items() if not is_empty(value)})
        values = {'object_id': str(obj.pk), 'field_hashes': hashes, 'source_format': self.data.source_format}
        if checksum:
            values['checksum'] = checksum
        WordPressImportRecord.objects.update_or_create(entity=entity, wordpress_id=wordpress_id, defaults=values)

    def baseline_trusted(self, obj, linked_by_wordpress_id):
        """Without a ledger, decide whether an old-importer row was never edited here."""
        if not linked_by_wordpress_id:
            return False
        updated, created = getattr(obj, 'updated_at', None), getattr(obj, 'created_at', None)
        if self.trust_unedited_before and updated and updated < self.trust_unedited_before:
            return True
        return bool(self.assume_unedited and updated and created and updated - created <= UNEDITED_WINDOW)

    def merge(self, obj, incoming, record, trusted):
        """Return (changes, conflicts) for a three-way merge of ``incoming`` into ``obj``."""
        changes, conflicts = {}, []
        for name, new in incoming.items():
            if is_empty(new):
                continue
            current = getattr(obj, name)
            if fingerprint(current) == fingerprint(new):
                continue
            if self.overwrite:
                changes[name] = new
                continue
            base = record.field_hashes.get(name) if record else None
            if base is not None:
                if fingerprint(new) == base:
                    continue  # WordPress unchanged since last import: keep the local edit
                if fingerprint(current) == base:
                    changes[name] = new
                else:
                    conflicts.append(name)
            elif is_empty(current) or trusted:
                changes[name] = new
            else:
                conflicts.append(name)
        return changes, conflicts

    def apply(self, entity, key, obj, incoming, record, trusted, *, created=False, linked=False):
        if created:
            obj.save()
            self.report.add(entity, 'created', key)
            return obj
        changes, conflicts = self.merge(obj, incoming, record, trusted)
        for name, value in changes.items():
            setattr(obj, name, value)
        if changes:
            obj.save()
        if conflicts:
            self.report.add(entity, 'conflict', key, 'edited in the new site and changed in WordPress; kept the new-site value (use --overwrite to take WordPress)', conflicts)
            if changes:
                self.report.extra[entity]['updated fields alongside conflicts'] += 1
        elif changes:
            self.report.add(entity, 'updated', key, '', sorted(changes))
        elif linked:
            self.report.add(entity, 'linked', key, 'existing record linked to its WordPress ID')
        else:
            self.report.add(entity, 'unchanged', key)
        return obj

    # -------------------------------------------------------------- authors
    def import_authors(self):
        for row in self.data.authors:
            self._record('authors', row['login'], lambda row=row: self._author(row))

    def _author(self, row):
        wp_id, login = row.get('wordpress_id'), row['login'][:100]
        incoming = {
            'display_name': (row.get('display_name') or login)[:200], 'email': (row.get('email') or '')[:254],
            'bio': row.get('bio') or '', 'website': (row.get('website') or '')[:1000],
        }
        record = self.ledger('author', wp_id)
        author = Author.objects.filter(pk=record.object_id).first() if record else None
        by_id = False
        if not author and wp_id is not None:
            author = Author.objects.filter(wordpress_id=wp_id).first()
            by_id = bool(author)
        linked = False
        if not author:
            author = Author.objects.filter(login=login).first()
            if author:
                if author.wordpress_id not in (None, wp_id):
                    self.report.add('authors', 'conflict', login, f'login already used by WordPress author #{author.wordpress_id}')
                    return
                if wp_id is not None and author.wordpress_id is None:
                    if Author.objects.filter(wordpress_id=wp_id).exists():
                        self.report.add('authors', 'conflict', login, f'WordPress ID {wp_id} already linked to another author')
                        return
                    author.wordpress_id = wp_id
                    author.save(update_fields=['wordpress_id'])
                    linked = True
        if not author:
            author = Author(login=login, wordpress_id=wp_id, **incoming)
            self.apply('authors', login, author, incoming, None, False, created=True)
        else:
            self.apply('authors', login, author, incoming, record, self.baseline_trusted(author, by_id), linked=linked)
        self.save_ledger('author', wp_id, author, incoming, record)

    def find_author(self, login, wordpress_id=None):
        record = self.ledger('author', wordpress_id)
        if record:
            author = Author.objects.filter(pk=record.object_id).first()
            if author:
                return author
        if wordpress_id is not None:
            author = Author.objects.filter(wordpress_id=wordpress_id).first()
            if author:
                return author
        return Author.objects.filter(login=login).first() if login else None

    # ------------------------------------------------------------- taxonomy
    def _term(self, entity, model, ledger_entity, row, fields):
        wp_id, slug = row.get('wordpress_id'), clean_slug(row['slug'], 200)
        if not slug:
            self.report.add(entity, 'skipped', row['slug'], 'empty slug')
            return None
        record = self.ledger(ledger_entity, wp_id)
        obj = model.objects.filter(pk=record.object_id).first() if record else None
        if not obj:
            obj = model.objects.filter(slug=slug).first()
        if not obj:
            obj = model(slug=slug, **fields)
            self.apply(entity, slug, obj, fields, None, False, created=True)
        else:
            # Taxonomy rows have no edit timestamps: without a ledger only empty fields are filled.
            self.apply(entity, slug, obj, fields, record, False, linked=record is None and wp_id is not None)
        self.save_ledger(ledger_entity, wp_id, obj, fields, record)
        return obj

    def import_categories(self):
        by_source_slug = {}
        for row in self.data.categories:
            fields = {'name': (row.get('name') or row['slug'])[:200], 'description': row.get('description') or ''}
            obj = self._record('categories', row['slug'], lambda row=row, fields=fields: self._term('categories', Category, 'category', row, fields))
            if obj:
                by_source_slug[row['slug']] = (obj, row)
        for source_slug, (category, row) in by_source_slug.items():
            parent_entry = by_source_slug.get(row.get('parent_slug') or '')
            if not parent_entry or parent_entry[0].pk == category.pk:
                continue
            parent = parent_entry[0]
            record = self.ledger('category', row.get('wordpress_id'))
            if category.parent_id == parent.pk:
                continue
            base = record.field_hashes.get('parent_id') if record else None
            if category.parent_id is None or self.overwrite or (base is not None and base == fingerprint(category.parent_id)):
                category.parent = parent
                category.save(update_fields=['parent'])
                self.report.extra['categories']['parent set'] += 1
            elif base != fingerprint(parent.pk):
                self.report.add('categories', 'conflict', category.slug, 'parent category differs from WordPress; kept', ['parent'])
            if record:
                record.field_hashes['parent_id'] = fingerprint(parent.pk)
                record.save(update_fields=['field_hashes', 'last_imported_at'])

    def import_tags(self):
        for row in self.data.tags:
            fields = {'name': (row.get('name') or row['slug'])[:200]}
            self._record('tags', row['slug'], lambda row=row, fields=fields: self._term('tags', Tag, 'tag', row, fields))

    def find_term(self, model, ledger_entity, source_slug):
        """Ledger first (the term may have been renamed in the new site), then slug."""
        rows = self.data.categories if ledger_entity == 'category' else self.data.tags
        if not hasattr(self, '_term_ids'):
            self._term_ids = {}
        ids = self._term_ids.setdefault(ledger_entity, {row['slug']: row.get('wordpress_id') for row in rows})
        record = self.ledger(ledger_entity, ids.get(source_slug))
        if record:
            obj = model.objects.filter(pk=record.object_id).first()
            if obj:
                return obj
        slug = clean_slug(source_slug, 200)
        return model.objects.filter(slug=slug).first() if slug else None

    # ----------------------------------------------------------------- media
    def import_media(self):
        if not self.media_source.enabled:
            self.report.notes.append('Media files were not copied (no --uploads-dir or --media-base-url given); only media records were imported.')
        linked_paths = set()
        for row in self.data.attachments:
            relative = relative_upload_path(row.get('attached_file'), row.get('url'))
            if relative:
                linked_paths.add(relative)
            self._record('media', row['wordpress_id'], lambda row=row, relative=relative: self._media(row, relative))
        if self.media_source.uploads_dir:
            files, skipped = self.media_source.walk()
            for ext, count in skipped.items():
                self.report.extra['upload files']['skipped .' + ext] += count
            for relative in files:
                if relative in linked_paths:
                    continue  # already handled with its attachment
                self._record('upload files', relative, lambda relative=relative: self._copy_file(relative))

    def _copy_file(self, relative):
        try:
            data = self.media_source.read(relative)
        except MediaSourceError as exc:
            self.report.add('upload files', 'error', relative, str(exc))
            return None, None
        outcome, name, message = store_file(relative, data, dry_run=self.dry_run, overwrite=self.overwrite)
        self.report.extra['upload files'][outcome] += 1
        if outcome == 'conflict':
            self.report.add('upload files', 'conflict', relative, message)
        return (name if outcome in {'copied', 'exists'} else None), data

    def _media(self, row, relative):
        wp_id = row['wordpress_id']
        incoming = {
            'title': (row.get('title') or '')[:300], 'alt_text': (row.get('alt_text') or '')[:500],
            'caption': row.get('caption') or '', 'url': (row.get('url') or '')[:1500],
        }
        record = self.ledger('media', wp_id)
        asset = MediaAsset.objects.filter(pk=record.object_id).first() if record else None
        if not asset:
            asset = MediaAsset.objects.filter(wordpress_id=wp_id).first()
        linked = False
        if not asset and incoming['url']:
            asset = MediaAsset.objects.filter(url=incoming['url'], wordpress_id__isnull=True).first()
            if asset:
                asset.wordpress_id = wp_id
                asset.save(update_fields=['wordpress_id'])
                linked = True
        if not asset:
            asset = MediaAsset(wordpress_id=wp_id, **incoming)
            self.apply('media', wp_id, asset, incoming, None, False, created=True)
        else:
            self.apply('media', wp_id, asset, incoming, record, False, linked=linked)

        checksum = None
        if self.media_source.enabled and relative:
            if extension(relative) not in COPYABLE_EXTENSIONS:
                self.report.extra['upload files']['skipped .' + extension(relative)] += 1
            else:
                name, data = self._copy_file(relative)
                if data is not None:
                    checksum = sha256(data)
                if name and not asset.file and extension(relative) in IMAGE_EXTENSIONS and not self.dry_run:
                    asset.file.name = name
                    update = ['file']
                    if self.optimize_images and not asset.optimized_file:
                        from django.core.files.base import ContentFile

                        from blog.image_optimization import webp_derivative

                        try:
                            derivative = webp_derivative(ContentFile(data, name=relative.rsplit('/', 1)[-1]))
                        except Exception:
                            derivative = None
                        if derivative:
                            asset.optimized_file.save(derivative.name, derivative, save=False)
                            update.append('optimized_file')
                    asset.save(update_fields=update)
                    self.report.extra['media']['file linked'] += 1
        self.save_ledger('media', wp_id, asset, incoming, record, checksum=checksum)

    def find_media(self, wordpress_id):
        if wordpress_id is None:
            return None
        return MediaAsset.objects.filter(wordpress_id=wordpress_id).first()

    # ----------------------------------------------------------------- posts
    def wanted_items(self):
        for row in self.data.items:
            status = row.get('status') or 'draft'
            if status in SKIPPED_STATUSES:
                continue
            if self.published_only and status not in {'publish', 'future'}:
                continue
            if self.skip_trash and status == 'trash':
                continue
            yield row

    def import_posts(self):
        unmapped = Counter()
        mapped_meta = {
            '_thumbnail_id', '_elementor_data', '_wp_page_template', 'rank_math_title', 'rank_math_description',
            '_yoast_wpseo_title', '_yoast_wpseo_metadesc', '_edit_lock', '_edit_last', '_wp_old_slug',
        }
        for row in self.wanted_items():
            for key in row.get('meta', {}):
                if key not in mapped_meta and not key.startswith(('_oembed', '_elementor_', '_wp_', '_menu_item')):
                    unmapped[key] += 1
            self._record('posts', row['wordpress_id'], lambda row=row: self._post(row))
        for key, count in unmapped.most_common(15):
            self.report.extra['posts: WordPress fields not imported'][key] = count

    def _post(self, row):
        wp_id, post_type = row['wordpress_id'], row['post_type']
        meta = row.get('meta', {})
        title = (row.get('title') or f'Untitled WordPress {post_type} {wp_id}')[:500]
        thumbnail = self.find_media(int(meta['_thumbnail_id'])) if str(meta.get('_thumbnail_id', '')).isdigit() else None
        author = self.find_author(row.get('author_login'), row.get('author_id'))
        status = STATUS_MAP.get(row.get('status'), row.get('status'))
        incoming = {
            'title': title, 'content': row.get('content') or '', 'excerpt': row.get('excerpt') or '',
            'post_type': post_type, 'status': status if status in dict(Post.STATUSES) else 'draft',
            'author_id': author.pk if author else None,
            'featured_image': (thumbnail.source_url() if thumbnail else '')[:1000],
            'seo_title': resolve_seo(meta.get('rank_math_title') or meta.get('_yoast_wpseo_title', ''), title, row.get('excerpt') or '')[:500],
            'seo_description': resolve_seo(meta.get('rank_math_description') or meta.get('_yoast_wpseo_metadesc', ''), title, row.get('excerpt') or ''),
            'wordpress_url': (row.get('link') or '')[:1000], 'elementor_data': meta.get('_elementor_data', ''),
            'page_template': meta.get('_wp_page_template', '')[:200], 'published_at': row.get('published_at'),
        }
        desired_slug = clean_slug(row.get('slug') or title, 480) or f'wordpress-content-{wp_id}'

        record = self.ledger('post', wp_id)
        post = Post.objects.filter(pk=record.object_id).first() if record else None
        by_id = False
        if not post:
            post = Post.objects.filter(wordpress_id=wp_id).first()
            by_id = bool(post)
        linked = False
        if not post:
            candidate = Post.objects.filter(slug=desired_slug).first()
            if candidate and candidate.wordpress_id is None and candidate.post_type == post_type:
                post, linked = candidate, True
                post.wordpress_id = wp_id
                post.save(update_fields=['wordpress_id'])
                self.report.extra['posts']['matched by slug'] += 1

        if not post:
            slug = self.free_slug(desired_slug, wp_id)
            if slug != desired_slug:
                self.report.add('posts', 'conflict', wp_id, f'slug "{desired_slug}" belongs to another record; created as "{slug}"', ['slug'])
            post = Post(slug=slug, wordpress_id=wp_id, **incoming)
            self.apply('posts', wp_id, post, incoming, None, False, created=True)
        else:
            trusted = self.baseline_trusted(post, by_id)
            merge_fields = dict(incoming)
            if desired_slug != post.slug:
                if Post.objects.exclude(pk=post.pk).filter(slug=desired_slug).exists():
                    if re.fullmatch(rf'{re.escape(desired_slug[:470])}-\d+', post.slug):
                        # WordPress allowed the same slug twice (e.g. a post and a page); the
                        # earlier import already gave this one a numbered slug.
                        self.report.extra['posts']['numbered slug kept (duplicate WordPress slug)'] += 1
                    else:
                        self.report.add('posts', 'conflict', wp_id, f'WordPress slug "{desired_slug}" is used by another record; kept "{post.slug}"', ['slug'])
                else:
                    merge_fields['slug'] = desired_slug
            old_slug = post.slug
            self.apply('posts', wp_id, post, merge_fields, record, trusted, linked=linked)
            if post.slug != old_slug:
                self.add_redirect('permalink', None, f'/{old_slug}', post_public_path(post), 'wordpress', note=f'slug changed by import (WordPress #{wp_id})')
            incoming = merge_fields
        self.link_taxonomy(post, row)
        self.save_ledger('post', wp_id, post, incoming, record)

    def free_slug(self, base, wp_id):
        slug, number = base, 1
        while Post.objects.filter(slug=slug).exclude(wordpress_id=wp_id).exists():
            number += 1
            slug = f'{base[:470]}-{number}'
        return slug

    def link_taxonomy(self, post, row):
        """Additive only: links missing in the new site are added, none are removed."""
        added = 0
        for source_slug in row.get('categories', []):
            category = self.find_term(Category, 'category', source_slug)
            if category and not post.categories.filter(pk=category.pk).exists():
                post.categories.add(category)
                added += 1
        for source_slug in row.get('tags', []):
            tag = self.find_term(Tag, 'tag', source_slug)
            if tag and not post.tags.filter(pk=tag.pk).exists():
                post.tags.add(tag)
                added += 1
        if added:
            self.report.extra['posts']['category/tag links added'] += added

    # ------------------------------------------------------------- redirects
    def site_path(self, url):
        """Same-site absolute URLs become paths; other URLs stay absolute."""
        from urllib.parse import urlsplit

        url = (url or '').strip()
        if url.startswith('/'):
            return url
        parts = urlsplit(url)
        if parts.netloc and parts.netloc.lower() in {self.site_host, 'www.' + self.site_host, self.site_host.removeprefix('www.')}:
            return (parts.path or '/') + (f'?{parts.query}' if parts.query else '')
        return url

    def add_redirect(self, ledger_entity, wordpress_id, old, new, source, code=301, note=''):
        old_norm = normalize_path(old)
        key = old_norm
        if old_norm == '/':
            return  # the home page stays the home page
        if not old_norm or not safe_target(new) or old_norm == normalize_path(new):
            self.report.add('redirects', 'skipped', key or old, 'empty, unsafe or self-pointing redirect')
            return
        segments = old_norm.strip('/').split('/')
        if (len(segments) == 1 and segments[0] in RESERVED_FIRST_SEGMENTS) or segments[0] in RESERVED_PREFIXES:
            self.report.add('redirects', 'skipped', key, 'old path is an address of the new site itself')
            return
        if len(segments) == 1 and Post.objects.filter(slug=segments[0]).exists():
            self.report.add('redirects', 'skipped', key, 'old path is the address of another article or page in the new site')
            return
        incoming = {'new_url': new[:1000], 'status_code': code}
        record = self.ledger(ledger_entity, wordpress_id)
        existing = Redirect.objects.filter(old_path=old_norm).first()
        if not existing:
            redirect = Redirect(old_path=old_norm, source=source, note=note[:300], **incoming)
            self.apply('redirects', key, redirect, incoming, None, False, created=True)
        elif existing.source == 'manual' and not self.overwrite:
            if fingerprint(existing.new_url) != fingerprint(new):
                self.report.add('redirects', 'conflict', key, f'staff redirect to {existing.new_url} kept (WordPress says {new})', ['new_url'])
            else:
                self.report.add('redirects', 'unchanged', key)
            return
        else:
            redirect = self.apply('redirects', key, existing, incoming, record, False)
        if wordpress_id is not None:
            self.save_ledger(ledger_entity, wordpress_id, redirect, incoming, record)

    def import_redirects(self):
        permalink_map = {}
        for row in self.wanted_items():
            if row.get('status') not in {'publish', 'future'}:
                continue
            post = Post.objects.filter(wordpress_id=row['wordpress_id']).first()
            if not post:
                continue
            target = post_public_path(post)
            permalink_map[normalize_path(f'/{post.slug}')] = target
            old = url_path(row.get('link'))
            if not old or '?' in old:
                continue  # /?p=123 links are handled by the middleware
            permalink_map[normalize_path(old)] = target
            if normalize_path(old) in {normalize_path(f'/{post.slug}'), normalize_path(target)}:
                continue  # the old address still works in the new site
            self._record('redirects', old, lambda row=row, old=old, target=target: self.add_redirect('permalink', row['wordpress_id'], old, target, 'wordpress', note=f'WordPress #{row["wordpress_id"]}'))
        for rule in self.data.redirects:
            key = rule.get('old') or '?'
            if rule.get('regex'):
                self.report.add('redirects', 'skipped', key, 'regular-expression rule: add it by hand if still needed')
                continue
            code = rule.get('code') or 301
            if code not in {301, 302, 307, 308}:
                self.report.add('redirects', 'skipped', key, f'HTTP {code} rule (not a redirect)')
                continue
            target = self.site_path(rule.get('new'))
            if target.startswith('/'):
                target = permalink_map.get(normalize_path(target), target)
            self._record('redirects', key, lambda rule=rule, target=target, code=code: self.add_redirect(
                rule['source'], rule.get('wordpress_id'), rule['old'], target, rule['source'], code=code, note='Imported WordPress redirect rule'))

    # ----------------------------------------------------------------- users
    def import_users(self):
        if not self.data.users:
            self.report.notes.append('No WordPress user accounts in this export (WXR has none); members can register again or be imported from a SQL dump.')
            return
        hasher_ready = WP_HASH_ALGORITHM in get_hashers_by_algorithm()
        if self.import_password_hashes and not hasher_ready:
            self.report.notes.append('The WordPress password hasher is not in PASSWORD_HASHERS: imported members get no password and must use "Forgot password".')
        for row in self.data.users:
            self._record('users', row.get('login') or row.get('wordpress_id'), lambda row=row: self._user(row, hasher_ready))

    def _user(self, row, hasher_ready):
        wp_id, email = row.get('wordpress_id'), normalize_email(row.get('email') or '')
        key = row.get('login') or wp_id
        if not email or '@' not in email:
            self.report.add('users', 'skipped', key, 'no email address')
            return
        roles = set(row.get('roles') or [])
        if roles & STAFF_ROLES:
            self.report.extra['users: WordPress staff roles (not granted here)'][', '.join(sorted(roles & STAFF_ROLES))] += 1
        incoming = {'first_name': (row.get('first_name') or '')[:150], 'last_name': (row.get('last_name') or '')[:150]}
        record = self.ledger('user', wp_id)
        user = User.objects.filter(pk=record.object_id).first() if record else None
        linked = False
        if not user:
            user = find_user_by_email(email)
            linked = bool(user)
        if user:
            # Existing accounts keep their password, roles and status untouched.
            self.apply('users', key, user, incoming, record, False, linked=linked and record is None)
        else:
            if User.objects.filter(username__iexact=email).exists():
                self.report.add('users', 'conflict', key, 'an account already uses this email as its username')
                return
            user = User(username=email, email=email, is_active=True, is_staff=False, is_superuser=False, **incoming)
            if row.get('registered'):
                user.date_joined = row['registered']
            wp_hash = row.get('password_hash') or ''
            if self.import_password_hashes and hasher_ready and is_supported_wordpress_hash(wp_hash):
                user.password = f'{WP_HASH_ALGORITHM}${wp_hash}'
                self.report.extra['users']['password kept from WordPress'] += 1
            else:
                user.set_unusable_password()
                self.report.extra['users']['must use "Forgot password"'] += 1
            self.apply('users', key, user, incoming, None, False, created=True)
            profile = getattr(user, 'membership_profile', None)
            if profile is not None:
                profile.display_name = (row.get('display_name') or '')[:200]
                profile.auth_provider = 'password'
                profile.save(update_fields=['display_name', 'auth_provider', 'updated_at'])
        self.save_ledger('user', wp_id, user, incoming, record)
