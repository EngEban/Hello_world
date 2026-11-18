import os
import re
from pathlib import Path
from urllib.parse import quote, urlparse
from django.core.exceptions import ImproperlyConfigured
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


# ── Helper functions ──────────────────────────────────────
def load_local_env(path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip().lstrip('\ufeff')
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}


def env_list(name, default=''):
    return [item.strip() for item in os.getenv(name, default).split(',') if item.strip()]


def deployment_hostnames(*values):
    """Return valid hostnames supplied by a managed hosting platform."""
    hosts = []
    for value in values:
        value = (value or '').strip()
        if not value:
            continue
        parsed = urlparse(value if '://' in value else f'//{value}')
        hostname = parsed.hostname
        if hostname and hostname not in hosts:
            hosts.append(hostname)
    return hosts


def env_cookie_same_site(name, default='Lax'):
    value = os.getenv(name, default).strip().lower()
    supported_values = {'lax': 'Lax', 'strict': 'Strict', 'none': 'None'}
    if value not in supported_values:
        raise ImproperlyConfigured(f'{name} must be one of: Lax, Strict, None.')
    return supported_values[value]


def validate_production_cache_backend(caches, is_production):
    default_cache = caches.get('default', {})
    backend = default_cache.get('BACKEND', '')
    if is_production and 'redis' not in backend.lower():
        raise ImproperlyConfigured(
            'Production requires a shared cache backend. Set '
            'DJANGO_CACHE_BACKEND=django.core.cache.backends.redis.RedisCache'
        )
    if is_production:
        location = default_cache.get('LOCATION', '')
        hostname = urlparse(location).hostname
        if urlparse(location).scheme not in {'redis', 'rediss'} or hostname in {None, 'localhost', '127.0.0.1', '::1'}:
            raise ImproperlyConfigured(
                'Production requires a non-local shared Redis URL. Set DJANGO_CACHE_LOCATION '
                'to the private managed-Redis connection URI.'
            )


# ── Environment / Core Security ───────────────────────────
load_local_env(BASE_DIR / '.env')
RESREF_ENV = os.getenv('RESREF_ENV', 'development').strip().lower()
IS_PRODUCTION = RESREF_ENV == 'production'
STAGING_ADMIN_ENVIRONMENT_VARIABLES = (
    'RESREF_STAGING_ADMIN_USERNAME',
    'RESREF_STAGING_ADMIN_EMAIL',
    'RESREF_STAGING_ADMIN_PASSWORD',
    'RESREF_STAGING_ADMIN_RESET_PASSWORD',
    'RESREF_STAGING_ADMIN_ALLOW_PROMOTION',
)

if IS_PRODUCTION:
    configured_staging_admin_variables = [
        name for name in STAGING_ADMIN_ENVIRONMENT_VARIABLES if name in os.environ
    ]
    if configured_staging_admin_variables:
        raise ImproperlyConfigured(
            'Staging-admin environment variables must not be set when RESREF_ENV=production: '
            + ', '.join(configured_staging_admin_variables)
        )

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured(
        'DJANGO_SECRET_KEY environment variable is required. '
        'Generate one with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"'
    )
# Sessions, password-reset links and signed tokens all depend on this key, so
# production refuses a short, placeholder or build-time value.
if IS_PRODUCTION and (
    len(SECRET_KEY) < 50
    or len(set(SECRET_KEY)) < 5
    or SECRET_KEY.startswith('django-insecure')
    or SECRET_KEY == 'build-only-not-a-secret'
):
    raise ImproperlyConfigured(
        'DJANGO_SECRET_KEY is too weak for production: use a random value of at least 50 characters.'
    )

# DEBUG is never on unless explicitly requested, and never in production.
DEBUG = env_bool('DJANGO_DEBUG', False)
if IS_PRODUCTION and DEBUG:
    raise ImproperlyConfigured('DJANGO_DEBUG must be false when RESREF_ENV=production.')
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost')
RENDER_EXTERNAL_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME', '').strip()
RAILWAY_PUBLIC_DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN', '').strip()
# Railway injects RAILWAY_ENVIRONMENT (and RAILWAY_PUBLIC_DOMAIN when a public
# domain exists). PUBLIC_HOSTNAME is an optional custom domain; it comes first
# so generated links use it.
ON_RAILWAY = bool(os.getenv('RAILWAY_ENVIRONMENT', '').strip() or RAILWAY_PUBLIC_DOMAIN)
DEPLOYMENT_HOSTNAMES = deployment_hostnames(
    os.getenv('PUBLIC_HOSTNAME', ''),
    RAILWAY_PUBLIC_DOMAIN,
    RENDER_EXTERNAL_HOSTNAME,
)
PUBLIC_HOSTNAME = DEPLOYMENT_HOSTNAMES[0] if DEPLOYMENT_HOSTNAMES else ''
for deployment_hostname in DEPLOYMENT_HOSTNAMES:
    if deployment_hostname not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(deployment_hostname)
# Railway sends deployment health checks with this Host header. Add it only
# when running on Railway so local and other hosted deployments remain strict.
if ON_RAILWAY and 'healthcheck.railway.app' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('healthcheck.railway.app')
# A wildcard host lets an attacker choose the domain used in password-reset
# and confirmation e-mails (Host-header poisoning).
if IS_PRODUCTION and '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must list real hostnames, not "*", in production.')
SERVE_FRONTEND_FROM_DJANGO = env_bool('SERVE_FRONTEND_FROM_DJANGO', False)
# Moving Django admin off /admin/ removes it from automated password-guessing scans.
ADMIN_URL_PATH = os.getenv('DJANGO_ADMIN_PATH', 'admin/').strip().strip('/') + '/'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'blog',
    'accounts.apps.AccountsConfig',
    'dashboard',
    'research_analyzer.apps.ResearchAnalyzerConfig',
    'usage',
    'redirects.apps.LegacyRedirectsConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.WwwRedirectMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'resref.security_headers.SecurityHeadersMiddleware',
    'core.errors.ApiErrorMiddleware',
    'core.middleware.RequestSizeLimitMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'redirects.middleware.LegacyRedirectMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'resref.urls'
# /api/ CSRF failures answer in JSON like every other API error.
CSRF_FAILURE_VIEW = 'core.errors.csrf_failure'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'resref.wsgi.application'

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
if not DATABASE_URL:
    # Railway's standard PostgreSQL template exposes these individual PG*
    # variables as well as DATABASE_URL. Constructing the URI here is a safe
    # fallback for deployments where a dashboard reference to DATABASE_URL was
    # accidentally created as an empty value. Quote credentials because a
    # managed provider may generate URL-reserved password characters.
    railway_pg_parts = {
        name: os.getenv(name, '').strip()
        for name in ('PGHOST', 'PGPORT', 'PGUSER', 'PGPASSWORD', 'PGDATABASE')
    }
    if all(railway_pg_parts.values()):
        DATABASE_URL = (
            f"postgresql://{quote(railway_pg_parts['PGUSER'], safe='')}:"
            f"{quote(railway_pg_parts['PGPASSWORD'], safe='')}@"
            f"{railway_pg_parts['PGHOST']}:{railway_pg_parts['PGPORT']}/"
            f"{quote(railway_pg_parts['PGDATABASE'], safe='')}"
        )
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(os.getenv('DJANGO_DB_CONN_MAX_AGE', '600')),
            ssl_require=env_bool('DJANGO_DB_SSL_REQUIRE', IS_PRODUCTION),
        )
    }
    # Reuse persistent connections safely when a worker recovers from a
    # database restart or managed-provider failover.
    DATABASES['default']['CONN_HEALTH_CHECKS'] = True
    if DATABASES['default'].get('ENGINE', '').endswith('postgresql'):
        # Fail fast (instead of hanging a worker until gunicorn kills it) when
        # the database is unreachable. statement_timeout is opt-in because
        # migrations and large exports may legitimately run longer.
        _db_options = DATABASES['default'].setdefault('OPTIONS', {})
        _db_options.setdefault('connect_timeout', int(os.getenv('DJANGO_DB_CONNECT_TIMEOUT', '10')))
        _statement_timeout_ms = int(os.getenv('DJANGO_DB_STATEMENT_TIMEOUT_MS', '0'))
        if _statement_timeout_ms > 0:
            _db_options['options'] = f'-c statement_timeout={_statement_timeout_ms}'
elif IS_PRODUCTION:
    raise ImproperlyConfigured(
        'DATABASE_URL is required when RESREF_ENV=production. '
        'Configure a PostgreSQL connection URL through the environment.'
    )
else:
    # SQLite remains available only for disposable local development and the
    # existing lightweight test workflow. Production always requires DATABASE_URL.
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'


def WHITENOISE_IMMUTABLE_FILE_TEST(path, url):
    # Vite's hashed bundles never change, so browsers may cache them for a year.
    return url.startswith(STATIC_URL + 'assets/') or bool(re.match(r'^.+\.[0-9a-f]{12}\..+$', url))

# Home-screen app settings; WhiteNoise would otherwise send them as a download.
WHITENOISE_MIMETYPES = {'.webmanifest': 'application/manifest+json'}

STATIC_SOURCE_DIR = BASE_DIR / 'static'
FRONTEND_DIST_DIR = BASE_DIR / 'frontend_dist'
# This project does not currently include a shared ``backend/static`` directory.
# Avoid a deployment-check warning while still discovering it automatically if it
# is added later.
STATICFILES_DIRS = [directory for directory in (STATIC_SOURCE_DIR, FRONTEND_DIST_DIR) if directory.exists()]
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.getenv('MEDIA_ROOT', '').strip() or BASE_DIR / 'media')

# User uploads.  Two modes:
#   MEDIA_STORAGE=local (default): files on disk at MEDIA_ROOT.  In production
#     MEDIA_ROOT must be a persistent volume (Railway Volume), and Django serves
#     public uploads itself (see resref/urls.py).
#   MEDIA_STORAGE=s3: any S3-compatible bucket (Cloudflare R2, AWS S3, ...).
MEDIA_STORAGE = os.getenv('MEDIA_STORAGE', 'local').strip().lower()
if MEDIA_STORAGE not in {'local', 's3'}:
    raise ImproperlyConfigured('MEDIA_STORAGE must be "local" or "s3".')
if MEDIA_STORAGE == 's3':
    _s3_required = ['AWS_STORAGE_BUCKET_NAME', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']
    _missing = [name for name in _s3_required if not os.getenv(name, '').strip()]
    if _missing:
        raise ImproperlyConfigured(f'MEDIA_STORAGE=s3 requires: {", ".join(_missing)}')
    DEFAULT_FILE_STORAGE_CONFIG = {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'bucket_name': os.getenv('AWS_STORAGE_BUCKET_NAME').strip(),
            'access_key': os.getenv('AWS_ACCESS_KEY_ID').strip(),
            'secret_key': os.getenv('AWS_SECRET_ACCESS_KEY').strip(),
            'endpoint_url': os.getenv('AWS_S3_ENDPOINT_URL', '').strip() or None,
            'region_name': os.getenv('AWS_S3_REGION_NAME', '').strip() or None,
            'custom_domain': os.getenv('AWS_S3_CUSTOM_DOMAIN', '').strip() or None,
            'location': os.getenv('AWS_LOCATION', 'media').strip(),
            'querystring_auth': env_bool('AWS_QUERYSTRING_AUTH', False),
            'file_overwrite': False,
            'default_acl': None,
            'object_parameters': {'CacheControl': 'public, max-age=86400'},
        },
    }
else:
    DEFAULT_FILE_STORAGE_CONFIG = {'BACKEND': 'django.core.files.storage.FileSystemStorage'}
SERVE_MEDIA_FROM_DJANGO = env_bool('SERVE_MEDIA_FROM_DJANGO', MEDIA_STORAGE == 'local')
# Research Analyzer datasets: private files on local disk (never the public
# bucket). Under MEDIA_ROOT so a Railway volume keeps them across restarts.
ANALYZER_STORAGE_DIR = Path(os.getenv('ANALYZER_STORAGE_DIR', '').strip() or MEDIA_ROOT / 'private' / 'analyzer')
ANALYZER_SESSION_TTL_SECONDS = max(int(os.getenv('ANALYZER_SESSION_TTL_SECONDS', str(15 * 60))), 300)
ANALYZER_MAX_SESSIONS_PER_USER = max(int(os.getenv('ANALYZER_MAX_SESSIONS_PER_USER', '2')), 1)

STORAGES = {
    'default': DEFAULT_FILE_STORAGE_CONFIG,
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email
# BREVO_API_KEY switches sending to Brevo's HTTPS API (core.email_backends), which
# works on every Railway plan; Railway blocks SMTP ports on Trial/Hobby plans.
BREVO_API_KEY = os.getenv('BREVO_API_KEY', '').strip()
EMAIL_BACKEND = (
    'core.email_backends.BrevoApiEmailBackend' if BREVO_API_KEY
    else os.getenv('DJANGO_EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
)
EMAIL_HOST = os.getenv('DJANGO_EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('DJANGO_EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('DJANGO_EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('DJANGO_EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('DJANGO_EMAIL_USE_TLS', True)
EMAIL_TIMEOUT = int(os.getenv('DJANGO_EMAIL_TIMEOUT', '15'))
DEFAULT_FROM_EMAIL = os.getenv('DJANGO_DEFAULT_FROM_EMAIL', 'ResRef <no-reply@resref.com>')
if IS_PRODUCTION and EMAIL_BACKEND.endswith(('console.EmailBackend', 'locmem.EmailBackend', 'dummy.EmailBackend')):
    import warnings
    warnings.warn(
        'Production has no real email backend: sign-up confirmations, password resets and newsletter '
        'opt-ins are only written to the logs. Set DJANGO_EMAIL_BACKEND and the DJANGO_EMAIL_* variables.',
        RuntimeWarning,
    )
# New self-registered accounts must click an emailed link before they can sign
# in. Set to false ONLY while no email provider (SMTP) is configured; new
# accounts are then signed in immediately. Remove the variable once SMTP works.
# It MUST be true (or unset) at public launch.
ACCOUNT_EMAIL_CONFIRMATION_REQUIRED = env_bool('ACCOUNT_EMAIL_CONFIRMATION_REQUIRED', True)
# New members can use their account immediately and have this many days to
# confirm their email; after that, sign-in waits for the confirmation link.
# 0 = confirmation is required before the first sign-in.
ACCOUNT_EMAIL_VERIFICATION_GRACE_DAYS = max(int(os.getenv('ACCOUNT_EMAIL_VERIFICATION_GRACE_DAYS', '2')), 0)
# "New sign-in from an unfamiliar browser" emails; set false to save email quota.
ACCOUNT_NEW_SIGNIN_EMAILS = env_bool('ACCOUNT_NEW_SIGNIN_EMAILS', True)
# The newsletter is switched off: its APIs return 404 and the outbox sends nothing.
# Subscriber data is kept; set true to bring the feature back.
NEWSLETTER_ENABLED = env_bool('NEWSLETTER_ENABLED', False)
NEWSLETTER_MAX_RECIPIENTS_PER_SEND = int(os.getenv('NEWSLETTER_MAX_RECIPIENTS_PER_SEND', '1000'))
# Newsletters are queued and sent by `manage.py process_outbox` (Railway cron).
# Set true only for local development to send right after queuing.
NEWSLETTER_SEND_INLINE = env_bool('NEWSLETTER_SEND_INLINE', False)
NEWSLETTER_BATCH_SIZE = max(int(os.getenv('NEWSLETTER_BATCH_SIZE', '200')), 1)

# Login
LOGIN_URL = '/dashboard/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/dashboard/login/'


# React frontend / API settings
CORS_ALLOWED_ORIGINS = env_list('DJANGO_CORS_ALLOWED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173')
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173')
FRONTEND_BASE_URL = os.getenv('FRONTEND_BASE_URL', '').rstrip('/')
# The all-in-one deployment serves React and Django from one public hostname.
# Derive that URL on Railway/Render when the dashboard variable is absent, so
# email links, redirects, and Stripe return URLs cannot point at a stale
# separately-deployed frontend.
if not FRONTEND_BASE_URL and SERVE_FRONTEND_FROM_DJANGO and DEPLOYMENT_HOSTNAMES:
    FRONTEND_BASE_URL = f'https://{DEPLOYMENT_HOSTNAMES[0]}'
if not FRONTEND_BASE_URL:
    FRONTEND_BASE_URL = 'http://127.0.0.1:5173'
for deployment_hostname in DEPLOYMENT_HOSTNAMES:
    if f'https://{deployment_hostname}' not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(f'https://{deployment_hostname}')
GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '').strip()
CROSSREF_POLITE_EMAIL = os.getenv('CROSSREF_POLITE_EMAIL', '').strip()
OPENALEX_API_KEY = os.getenv('OPENALEX_API_KEY', '').strip()

# Stripe test-mode billing. Keep live keys out of development and source control.
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '').strip()
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '').strip()
STRIPE_PREMIUM_MONTHLY_PRICE_ID = os.getenv('STRIPE_PREMIUM_MONTHLY_PRICE_ID', '').strip()
STRIPE_PREMIUM_YEARLY_PRICE_ID = os.getenv('STRIPE_PREMIUM_YEARLY_PRICE_ID', '').strip()
STRIPE_BILLING_SUCCESS_URL = os.getenv('STRIPE_BILLING_SUCCESS_URL', '').strip() or f'{FRONTEND_BASE_URL}/account?billing=success'
STRIPE_BILLING_CANCEL_URL = os.getenv('STRIPE_BILLING_CANCEL_URL', '').strip() or f'{FRONTEND_BASE_URL}/account?billing=cancelled'

if IS_PRODUCTION:
    if not FRONTEND_BASE_URL.startswith('https://'):
        raise ImproperlyConfigured('FRONTEND_BASE_URL must be an HTTPS URL when RESREF_ENV=production.')
    if not SERVE_FRONTEND_FROM_DJANGO:
        if FRONTEND_BASE_URL not in CORS_ALLOWED_ORIGINS:
            raise ImproperlyConfigured('DJANGO_CORS_ALLOWED_ORIGINS must include FRONTEND_BASE_URL in production.')
        if FRONTEND_BASE_URL not in CSRF_TRUSTED_ORIGINS:
            raise ImproperlyConfigured('DJANGO_CSRF_TRUSTED_ORIGINS must include FRONTEND_BASE_URL in production.')

# Authentication and security
# Django's default hashers; the WordPress (phpass) hasher is last so it is only
# used to verify imported WordPress passwords, which are upgraded on first sign-in.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.ScryptPasswordHasher',
    'blog.wordpress.hashers.WordPressPasswordHasher',
]
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = env_cookie_same_site('DJANGO_SESSION_COOKIE_SAMESITE')
SESSION_COOKIE_SECURE = env_bool('DJANGO_SESSION_COOKIE_SECURE', IS_PRODUCTION)
# Keep an authenticated session for a reasonable period and refresh its expiry
# while the user is active.  This is especially important on mobile browsers,
# which routinely background a tab while a user switches applications.  The
# cookie remains HTTPS-only and HttpOnly in production.
SESSION_COOKIE_AGE = int(os.getenv('DJANGO_SESSION_COOKIE_AGE', str(60 * 60 * 24 * 7)))
SESSION_EXPIRE_AT_BROWSER_CLOSE = env_bool('DJANGO_SESSION_EXPIRE_AT_BROWSER_CLOSE', False)
SESSION_SAVE_EVERY_REQUEST = env_bool('DJANGO_SESSION_SAVE_EVERY_REQUEST', True)
# Password history is saved as Django's salted, one-way hashes only.  Reset
# requests are limited independently by account identifier and client IP.
PASSWORD_HISTORY_COUNT = max(int(os.getenv('PASSWORD_HISTORY_COUNT', '5')), 1)
PASSWORD_RESET_EMAIL_LIMIT = max(int(os.getenv('PASSWORD_RESET_EMAIL_LIMIT', '3')), 1)
PASSWORD_RESET_IP_LIMIT = max(int(os.getenv('PASSWORD_RESET_IP_LIMIT', '10')), 1)
PASSWORD_RESET_COOLDOWN_SECONDS = max(int(os.getenv('PASSWORD_RESET_COOLDOWN_SECONDS', str(60 * 60))), 60)
CSRF_COOKIE_SECURE = env_bool('DJANGO_CSRF_COOKIE_SECURE', IS_PRODUCTION)
CSRF_COOKIE_SAMESITE = env_cookie_same_site('DJANGO_CSRF_COOKIE_SAMESITE')
SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', IS_PRODUCTION)
# Railway probes services over its private HTTP network. Redirecting that
# minimal, unauthenticated liveness endpoint to HTTPS produces a 301 and marks
# an otherwise healthy deployment unavailable. The public site and every other
# endpoint still require HTTPS in production.
SECURE_REDIRECT_EXEMPT = [r'^api/health/$']
SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_SECURE_HSTS_SECONDS', '31536000' if IS_PRODUCTION else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = env_bool('DJANGO_SECURE_HSTS_PRELOAD', False)
# includeSubdomains/preload are decisions for the final custom domain, not for
# a platform subdomain such as *.up.railway.app, so their checks are silenced
# until those settings are switched on explicitly.
SILENCED_SYSTEM_CHECKS = env_list(
    'DJANGO_SILENCED_SYSTEM_CHECKS',
    ','.join(code for code, enabled in (
        ('security.W005', not SECURE_HSTS_INCLUDE_SUBDOMAINS),
        ('security.W021', not SECURE_HSTS_PRELOAD),
    ) if enabled),
)
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
RESREF_TRUST_PROXY = env_bool('RESREF_TRUST_PROXY', ON_RAILWAY)
RESREF_TRUSTED_PROXY_HOPS = max(int(os.getenv('RESREF_TRUSTED_PROXY_HOPS', '1')), 1)
# Header holding the real visitor IP set by the hosting proxy (Railway: X-Real-IP).
# Set RESREF_CLIENT_IP_HEADER='' to fall back to X-Forwarded-For hop counting.
RESREF_CLIENT_IP_HEADER = os.getenv('RESREF_CLIENT_IP_HEADER', 'HTTP_X_REAL_IP' if ON_RAILWAY else '').strip()
if RESREF_TRUST_PROXY:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# IndexNow key (public by design: served at /<key>.txt). Empty turns the pings off.
INDEXNOW_KEY = os.getenv('INDEXNOW_KEY', 'b69f2024f43c8b0af232a9614aeb9f8b').strip()

RESREF_CSP_ENABLED = env_bool('DJANGO_CSP_ENABLED', IS_PRODUCTION)
RESREF_CSP_REPORT_ONLY = env_bool('DJANGO_CSP_REPORT_ONLY', False)
DEFAULT_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "img-src 'self' data: https:; "
    # Roboto/Comfortaa come from Google Fonts; the Google sign-in button loads
    # its own stylesheet from accounts.google.com.
    "font-src 'self' data: https://fonts.gstatic.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://accounts.google.com; "
    "script-src 'self' https://accounts.google.com https://js.stripe.com; "
    "connect-src 'self' https://api.crossref.org https://api.openalex.org "
    "https://api.stripe.com https://accounts.google.com; "
    "frame-src 'self' https://accounts.google.com https://docs.google.com https://js.stripe.com"
)
RESREF_CONTENT_SECURITY_POLICY = os.getenv('DJANGO_CONTENT_SECURITY_POLICY', '').strip() or DEFAULT_CONTENT_SECURITY_POLICY
RESREF_PERMISSIONS_POLICY = os.getenv(
    'DJANGO_PERMISSIONS_POLICY',
    'camera=(), microphone=(), geolocation=(), payment=(self)'
)

# Rate limits, login lockouts and lookups must be shared across workers and
# restarts, so production refuses to start without a non-local Redis cache.
# Railway's managed Redis exposes REDIS_URL; setting it is enough.
_redis_url = os.getenv('REDIS_URL', '').strip()
CACHES = {
    'default': {
        'BACKEND': os.getenv('DJANGO_CACHE_BACKEND', '').strip()
        or ('django.core.cache.backends.redis.RedisCache' if _redis_url else 'django.core.cache.backends.locmem.LocMemCache'),
        # Keep the explicit DJANGO_CACHE_LOCATION override for other providers.
        'LOCATION': os.getenv('DJANGO_CACHE_LOCATION', '').strip()
        or _redis_url
        or 'resref-security-cache',
        'KEY_PREFIX': 'resref',
    }
}
if CACHES['default']['BACKEND'].endswith('LocMemCache'):
    # The default 300-entry limit is smaller than one cached SEO report per article.
    CACHES['default']['OPTIONS'] = {'MAX_ENTRIES': 5000}
validate_production_cache_backend(CACHES, IS_PRODUCTION)
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv('DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE', str(5 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv('DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE', str(5 * 1024 * 1024)))
USER_TOOL_WORKSPACE_MAX_BYTES = int(os.getenv('USER_TOOL_WORKSPACE_MAX_BYTES', str(600 * 1024)))
# Whole-request ceiling (core.middleware.RequestSizeLimitMiddleware). It sits
# above the largest legitimate upload: the 20 MB Research Analyzer dataset.
RESREF_MAX_REQUEST_BYTES = max(int(os.getenv('DJANGO_MAX_REQUEST_BYTES', str(25 * 1024 * 1024))), 0)

# Railway (and similar platforms) expects application logs on stdout/stderr.
# DJANGO_LOG_FORMAT=json writes one JSON object per line; secrets and URL
# tokens are masked in every format.
DJANGO_LOG_LEVEL = os.getenv('DJANGO_LOG_LEVEL', 'INFO').upper()
DJANGO_LOG_FORMAT = os.getenv('DJANGO_LOG_FORMAT', 'text').strip().lower()
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'redact_secrets': {'()': 'core.logging.RedactSecretsFilter'},
    },
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
        },
        'json': {'()': 'core.logging.JsonFormatter'},
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json' if DJANGO_LOG_FORMAT == 'json' else 'verbose',
            'filters': ['redact_secrets'],
        },
    },
    'root': {
        'handlers': ['console'],
        'level': DJANGO_LOG_LEVEL,
    },
}

# Optional error reporting: active only when SENTRY_DSN is set.
from core.monitoring import init_sentry  # noqa: E402
SENTRY_ENABLED = init_sentry(RESREF_ENV)
