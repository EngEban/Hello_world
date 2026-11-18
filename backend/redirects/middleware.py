"""301 redirects for old WordPress addresses.

The React app answers every unknown path with a 200 shell, so redirects must
be decided before the request reaches the SPA fallback. Order:

1. Rows in the ``Redirect`` table (exact match, then longest prefix match).
2. Built-in WordPress patterns that need no rows:
   ``/?p=123`` / ``/?page_id=123``  -> the published post/page with that WordPress ID
   ``/category/<slug>/``            -> ``/database/<slug>``
   ``/author/<login>/``             -> ``/authors/<profile-slug>``
   ``/wp-content/uploads/<file>``   -> the copied file in media storage

Only GET/HEAD requests outside /api/, /static/, /media/, admin and the
dashboard are considered. Lookups are cached, and any failure falls through
to the normal response: a redirect problem must never take a page down.
"""
import logging

from django.conf import settings
from django.db.models import F
from django.http.response import HttpResponseRedirectBase
from django.utils import timezone

from .cache import cached
from .paths import normalize_path, safe_target
from .targets import WP_UPLOADS_STORAGE_PREFIX, post_public_path

logger = logging.getLogger(__name__)


class _Redirect(HttpResponseRedirectBase):
    allowed_schemes = ['http', 'https']

    def __init__(self, url, status):
        super().__init__(url)
        self.status_code = status


def _excluded_prefixes():
    admin = '/' + getattr(settings, 'ADMIN_URL_PATH', 'admin/').strip('/') + '/'
    return ('/api/', '/static/', '/media/', '/dashboard', '/assets/', '/admin/', admin)


def _exact(norm):
    from .models import Redirect

    return Redirect.objects.filter(old_path=norm, is_active=True, is_prefix=False).values('id', 'new_url', 'status_code').first()


def _prefix_rows():
    from .models import Redirect

    rows = list(Redirect.objects.filter(is_active=True, is_prefix=True).values('id', 'old_path', 'new_url', 'status_code'))
    return sorted(rows, key=lambda row: len(row['old_path']), reverse=True)


def _wordpress_id_target(wordpress_id):
    from blog.models import Post

    post = Post.objects.filter(wordpress_id=wordpress_id, status='publish').first()
    return post_public_path(post) if post else None


def _category_target(slug):
    from blog.models import Category

    return f'/database/{slug}' if Category.objects.filter(slug=slug).exists() else None


def _author_target(login):
    from blog.models import Author

    author = Author.objects.filter(login__iexact=login).only('slug').first() or Author.objects.filter(slug=login).only('slug').first()
    return f'/authors/{author.slug}' if author else None


def _upload_target(relative):
    from django.core.files.storage import default_storage

    name = WP_UPLOADS_STORAGE_PREFIX + relative
    return default_storage.url(name) if default_storage.exists(name) else None


class LegacyRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in {'GET', 'HEAD'}:
            try:
                response = self.redirect_for(request)
            except Exception:  # pragma: no cover - defensive; never break pages
                logger.exception('Legacy redirect lookup failed for %s', request.path)
                response = None
            if response is not None:
                return response
        return self.get_response(request)

    def redirect_for(self, request):
        path = request.path_info or '/'
        if path.startswith(_excluded_prefixes()):
            return None
        norm = normalize_path(path)

        if norm == '/':
            for key in ('p', 'page_id'):
                value = request.GET.get(key, '')
                if value.isdigit():
                    target = cached('wpid', value, lambda: _wordpress_id_target(int(value)))
                    return self.build(target, 301, request, keep_query=False)
            return None

        row = cached('exact', norm, lambda: _exact(norm))
        if row:
            return self.build(row['new_url'], row['status_code'], request, row_id=row['id'])

        for row in cached('prefixes', 'all', _prefix_rows) or []:
            prefix = row['old_path'].rstrip('/')
            if prefix and (norm == prefix or norm.startswith(prefix + '/')):
                # Keep the original (case-preserving) remainder: file names matter.
                remainder = normalize_path(path, lower=False)[len(prefix):].lstrip('/')
                base = row['new_url'] if row['new_url'].endswith('/') else row['new_url'] + '/'
                return self.build(base + remainder if remainder else row['new_url'], row['status_code'], request, row_id=row['id'])

        parts = norm.strip('/').split('/')
        if parts[0] == 'category' and len(parts) >= 2:
            # Hierarchical category URLs end with the child slug; /page/N/
            # archive pagination points at the category itself.
            segments = parts[1:parts.index('page', 1)] if 'page' in parts[1:] else parts[1:]
            if segments:
                slug = segments[-1]
                return self.build(cached('category', slug, lambda: _category_target(slug)), 301, request)
        if parts[0] == 'author' and len(parts) >= 2:
            return self.build(cached('author', parts[1], lambda: _author_target(parts[1])), 301, request)
        if norm.startswith('/wp-content/uploads/') and len(parts) > 2:
            relative = path.split('/wp-content/uploads/', 1)[-1]
            if relative and '..' not in relative.split('/'):
                return self.build(cached('upload', relative, lambda: _upload_target(relative)), 301, request, keep_query=False)
        return None

    def build(self, target, status, request, keep_query=True, row_id=None):
        if not target or not safe_target(target):
            return None
        if '://' not in target and normalize_path(target) == normalize_path(request.path_info):
            return None  # never redirect to the same address
        query = request.META.get('QUERY_STRING', '')
        if keep_query and query and '?' not in target:
            target = f'{target}?{query}'
        if row_id:
            from .models import Redirect

            Redirect.objects.filter(pk=row_id).update(hits=F('hits') + 1, last_hit_at=timezone.now())
        return _Redirect(target, status)
