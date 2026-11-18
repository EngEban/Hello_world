"""Path helpers shared by the redirect middleware and the WordPress importer."""
import re
from urllib.parse import unquote, urlsplit

_SLASHES = re.compile(r'/{2,}')


def normalize_path(value, lower=True):
    """Canonical form for matching: decoded, lower-case, no trailing slash, no query."""
    value = (value or '').strip()
    if '://' in value:
        value = urlsplit(value).path
    value = value.split('?', 1)[0].split('#', 1)[0]
    value = unquote(value).replace('\\', '/')
    value = _SLASHES.sub('/', '/' + value.lstrip('/'))
    if len(value) > 1:
        value = value.rstrip('/') or '/'
    return value.lower() if lower else value


def safe_target(url):
    """Only same-site paths or explicit http(s) URLs; never protocol-relative."""
    url = (url or '').strip()
    if not url or '\\' in url or any(ord(char) < 32 for char in url):
        return False
    if url.startswith('/'):
        return not url.startswith('//')
    parts = urlsplit(url)
    return parts.scheme in {'http', 'https'} and bool(parts.netloc)
