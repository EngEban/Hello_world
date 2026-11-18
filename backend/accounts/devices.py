"""Known-device cookie used to decide when to send a "new sign-in" email.

The cookie is signed and only holds short keyed hashes of account ids, so it
reveals nothing about which accounts used the browser.
"""

from django.conf import settings
from django.utils.crypto import salted_hmac


DEVICE_COOKIE = 'resref_device'
DEVICE_COOKIE_SALT = 'resref.accounts.known-device'
DEVICE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
MAX_REMEMBERED_ACCOUNTS = 5


def _tag(user):
    return salted_hmac(DEVICE_COOKIE_SALT, f'{user.pk}:{user.date_joined.isoformat()}').hexdigest()[:20]


def _tags(request):
    try:
        raw = request.get_signed_cookie(DEVICE_COOKIE, default='', salt=DEVICE_COOKIE_SALT)
    except Exception:
        raw = ''
    return [item for item in (raw or '').split('.') if item]


def is_known_device(request, user):
    return _tag(user) in _tags(request)


def remember_device(response, request, user):
    tag = _tag(user)
    tags = [item for item in _tags(request) if item != tag]
    tags = (tags + [tag])[-MAX_REMEMBERED_ACCOUNTS:]
    response.set_signed_cookie(
        DEVICE_COOKIE,
        '.'.join(tags),
        salt=DEVICE_COOKIE_SALT,
        max_age=DEVICE_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE or 'Lax',
    )
    return response
