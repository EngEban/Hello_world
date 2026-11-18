from django.contrib import admin
from django.urls import path, include, re_path
from pathlib import Path, PurePosixPath

from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.conf import settings
from django.utils._os import safe_join
from django.db import connection
from django.views.static import serve as development_media_serve
import logging

from . import indexnow, seo

logger = logging.getLogger(__name__)


# Personal documents (CVs) and analyzer datasets are never served from /media/,
# even if a URL leaks; CVs are downloaded through the authenticated dashboard.
PRIVATE_MEDIA_PREFIXES = ('uploads/jobapplication/', 'private/')

MEDIA_FILE_POLICIES = {
    'jpg': ('image/jpeg', 'inline'),
    'jpeg': ('image/jpeg', 'inline'),
    'png': ('image/png', 'inline'),
    'webp': ('image/webp', 'inline'),
    'gif': ('image/gif', 'inline'),
    'avif': ('image/avif', 'inline'),
    # Existing public article attachments and staff-only CV downloads remain
    # available, but documents are always downloaded rather than rendered.
    'pdf': ('application/pdf', 'attachment'),
    'doc': ('application/msword', 'attachment'),
    'docx': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'attachment'),
}


def secure_media_file(request, path):
    """Serve only verified image extensions with headers safe for same-origin use."""
    if settings.DEBUG:
        # Preserve Django's established development media behavior exactly.
        return development_media_serve(request, path, document_root=settings.MEDIA_ROOT)
    normalized = path.replace('\\', '/')
    parts = PurePosixPath(normalized).parts
    if (
        not normalized
        or normalized.startswith('/')
        or '\\' in path
        or any(ord(character) < 32 or ord(character) == 127 for character in path)
        or any(part in {'.', '..'} for part in parts)
    ):
        raise Http404
    if normalized.startswith(PRIVATE_MEDIA_PREFIXES):
        raise Http404
    extension = PurePosixPath(normalized).suffix.lower().lstrip('.')
    file_policy = MEDIA_FILE_POLICIES.get(extension)
    if not file_policy:
        # Never expose arbitrary files from MEDIA_ROOT on the app origin. Only
        # established image/document types have an explicit delivery policy.
        raise Http404
    try:
        file_path = safe_join(settings.MEDIA_ROOT, normalized)
    except SuspiciousFileOperation as exc:
        raise Http404 from exc
    if not Path(file_path).is_file():
        raise Http404

    content_type, disposition = file_policy
    response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = disposition
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    response['Cache-Control'] = 'public, max-age=86400'
    return response


def api_health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:  # pragma: no cover - exercised only when the DB is down
        logger.exception('Health check could not reach the database.')
        return JsonResponse({'status': 'error', 'database': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok', 'database': 'ok', 'message': 'ResRef Django API is running.'})


def throttled_admin_login(request, *args, **kwargs):
    """Django admin's login with the same brute-force limits as the API logins."""
    from accounts.identity import normalize_email
    from accounts.security import login_allowed, login_succeeded

    if request.method == 'POST':
        identifier = normalize_email(str(request.POST.get('username', ''))[:150])
        if not login_allowed(request, 'admin-login', identifier):
            return HttpResponse('Too many sign-in attempts. Please wait before trying again.', status=429, content_type='text/plain')
        response = admin.site.login(request, *args, **kwargs)
        if request.user.is_authenticated:
            login_succeeded(request, 'admin-login', identifier)
        return response
    return admin.site.login(request, *args, **kwargs)


def frontend_dev_redirect(request):
    return redirect(f'{settings.FRONTEND_BASE_URL}/')


def frontend_application(request, _path=''):
    """Serve the compiled React shell when Django is the public web app.

    API and Django-admin routes are registered before this fallback.  In local
    development the existing Vite redirect remains in place instead.
    """
    if not settings.SERVE_FRONTEND_FROM_DJANGO:
        return frontend_dev_redirect(request)

    index_path = settings.FRONTEND_DIST_DIR / 'index.html'
    if not index_path.is_file():
        return HttpResponse('Frontend build is not available.', status=503)
    # Per-URL title, description, canonical, robots, social cards and JSON-LD
    # are written into the shell so crawlers that do not run JavaScript see them.
    return seo.spa_response(request, index_path, request.path)


handler404 = 'core.errors.handler404'
handler500 = 'core.errors.handler500'

urlpatterns = [
    path(f'{settings.ADMIN_URL_PATH}login/', throttled_admin_login, name='admin_login_throttled'),
    path(settings.ADMIN_URL_PATH, admin.site.urls),
    path('api/health/', api_health, name='api_health'),
    path('api/', include('blog.api_urls')),
    path('api/accounts/', include('accounts.api_urls')),
    path('api/dashboard/', include('dashboard.api_urls')),
    path('api/research-analyzer/', include('research_analyzer.urls')),
    path('api/sample-size/', include('research_analyzer.sample_size_urls')),
    # Discoverability: crawler directives, sitemap and AI-readable site summaries.
    # Browsers and Google ask for /favicon.ico directly; the file ships with the frontend.
    path('favicon.ico', lambda request: redirect(settings.STATIC_URL + 'favicon.ico', permanent=True), name='favicon'),
    path('robots.txt', seo.robots_txt, name='robots_txt'),
    # IndexNow key file: search engines fetch it to confirm our change pings.
    re_path(r'^(?P<key_value>[0-9a-f]{32})\.txt$', indexnow.key_file, name='indexnow_key'),
    path('sitemap.xml', seo.sitemap_xml, name='sitemap_xml'),
    path('llms.txt', seo.llms_txt, name='llms_txt'),
    path('llms-full.txt', seo.llms_full_txt, name='llms_full_txt'),
    path('api/usage/', include('usage.urls')),
    # This route intentionally permits only the Media Library's image formats.
    # Files under MEDIA_ROOT share the application origin, so serving any other
    # extension here could turn a future upload validation mistake into stored XSS.
    re_path(r'^media/(?P<path>.+)$', secure_media_file, name='secure_media_file'),
    # Do not turn missing API/admin/static/media paths into a successful SPA
    # response; only client-side application routes belong to this fallback.
    re_path(r'^(?!(?:api|admin|static|media)(?:/|$))(?P<_path>.*)$', frontend_application, name='frontend_application'),
]
