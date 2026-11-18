"""IndexNow: tell Bing (and other IndexNow search engines) when a public page changes.

The key is public by design: search engines fetch it from /<key>.txt to confirm
the ping came from this site. Pings run after the database commit, in a
background thread, and never block or fail a save.
"""
import logging
import threading
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.db import transaction
from django.http import Http404, HttpResponse
from django.utils import timezone

from .seo import absolute, article_path, indexing_allowed, page_path, site_url

logger = logging.getLogger(__name__)
ENDPOINT = 'https://api.indexnow.org/indexnow'


def key():
    return getattr(settings, 'INDEXNOW_KEY', '')


def key_file(request, key_value):
    if not key() or key_value != key():
        raise Http404
    return HttpResponse(key(), content_type='text/plain; charset=utf-8')


def _send(urls):
    payload = {'host': urlsplit(site_url()).netloc, 'key': key(), 'keyLocation': absolute(f'/{key()}.txt'), 'urlList': urls}
    try:
        response = requests.post(ENDPOINT, json=payload, timeout=10)
        if response.status_code >= 400:
            logger.warning('IndexNow answered %s for %s URL(s).', response.status_code, len(urls))
    except requests.RequestException:
        logger.warning('IndexNow ping failed for %s URL(s).', len(urls), exc_info=True)


def notify_posts(posts):
    """Queue one ping for the public addresses of these posts once the save commits."""
    if not key() or not indexing_allowed() or settings.DEBUG:
        return
    now = timezone.now()
    urls = list(dict.fromkeys(
        absolute(article_path(post) if post.post_type == 'post' else page_path(post))
        for post in posts if post.status == 'publish' and post.published_at and post.published_at <= now))
    if urls:
        transaction.on_commit(lambda: threading.Thread(target=_send, args=(urls,), daemon=True).start())
