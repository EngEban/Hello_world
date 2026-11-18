"""Helpers for links that administrators type and the public site renders."""

from urllib.parse import urlsplit

SAFE_SCHEMES = {'http', 'https', 'mailto', 'tel'}


def is_safe_internal_path(value):
    """A same-site path such as ``/account``; rejects ``//host`` and ``/\\host``."""
    return isinstance(value, str) and value.startswith('/') and not value.startswith(('//', '/\\'))


def is_safe_link(value, *, allow_internal=True, schemes=SAFE_SCHEMES):
    """True for empty values, safe same-site paths and allowed absolute URLs."""
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    value = value.strip()
    if not value:
        return True
    if any(ord(char) < 32 for char in value):
        return False
    if value.startswith('/'):
        return allow_internal and is_safe_internal_path(value)
    if value.startswith('#'):
        return allow_internal
    parts = urlsplit(value)
    if parts.scheme.lower() not in schemes:
        return False
    if parts.scheme.lower() in {'http', 'https'} and not parts.netloc:
        return False
    return True


def looks_like_link_setting(key):
    key = (key or '').lower()
    return key.endswith(('_url', '_link', '_href')) or 'action_url' in key or key in {'url', 'link', 'href'}
