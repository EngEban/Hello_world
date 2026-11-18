"""Tiny versioned cache so redirect lookups cost no DB query on most requests."""
import hashlib
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)
VERSION_KEY = 'legacy-redirects:version'
TTL = 300
MISS = '__none__'


def _version():
    try:
        return cache.get_or_set(VERSION_KEY, 1, None)
    except Exception:  # cache outage must never break page delivery
        return 0


def bump_version():
    try:
        cache.set(VERSION_KEY, (_version() or 0) + 1, None)
    except Exception:
        logger.warning('Could not invalidate the redirect cache.')


def cached(name, key, compute):
    version = _version()
    if not version:
        return compute()
    cache_key = f'legacy-redirects:{version}:{name}:{hashlib.sha1(key.encode()).hexdigest()}'
    try:
        value = cache.get(cache_key)
    except Exception:
        value = None
    if value is None:
        value = compute()
        try:
            cache.set(cache_key, MISS if value is None else value, TTL)
        except Exception:
            pass
        return value
    return None if value == MISS else value
