"""Let imported WordPress members sign in with their existing password.

WordPress hashes are stored as ``wordpress$<original hash>``. On the first
successful sign-in Django re-hashes the password with the project's default
hasher (PBKDF2) because ``must_update`` is always true, so the WordPress hash
disappears from the database user by user.

Supported formats:
* ``$P$`` / ``$H$`` portable phpass (WordPress up to 6.7) — pure Python.
* ``$wp$2y$`` (WordPress 6.8+: bcrypt of a base64 HMAC-SHA384) and plain
  ``$2y$`` bcrypt — need the ``bcrypt`` package; without it they fail closed
  (the member uses "Forgot password").
* 32-character MD5 (very old WordPress) — accepted only for migration.

Activation needs one settings change (owned by the settings owner)::

    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.PBKDF2PasswordHasher',
        'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
        'django.contrib.auth.hashers.Argon2PasswordHasher',
        'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
        'django.contrib.auth.hashers.ScryptPasswordHasher',
        'blog.wordpress.hashers.WordPressPasswordHasher',   # must NOT be first
    ]
"""
import base64
import hashlib
import hmac
import re

from django.contrib.auth.hashers import BasePasswordHasher, mask_hash
from django.utils.crypto import constant_time_compare
from django.utils.translation import gettext_noop as _

ITOA64 = './0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
ALGORITHM = 'wordpress'


def _encode64(data, count):
    output, i = [], 0
    while i < count:
        value = data[i]
        i += 1
        output.append(ITOA64[value & 0x3F])
        if i < count:
            value |= data[i] << 8
        output.append(ITOA64[(value >> 6) & 0x3F])
        if i >= count:
            break
        i += 1
        if i < count:
            value |= data[i] << 16
        output.append(ITOA64[(value >> 12) & 0x3F])
        if i >= count:
            break
        i += 1
        output.append(ITOA64[(value >> 18) & 0x3F])
    return ''.join(output)


def phpass_crypt(password, setting):
    """Port of PasswordHash::crypt_private from phpass 0.3/0.5 (used by WordPress)."""
    if setting[:3] not in ('$P$', '$H$') or len(setting) < 12:
        return None
    count_log2 = ITOA64.find(setting[3])
    if count_log2 < 7 or count_log2 > 30:
        return None
    salt = setting[4:12]
    if len(salt) != 8:
        return None
    secret = password.encode('utf-8')
    digest = hashlib.md5(salt.encode('ascii') + secret).digest()
    for _ in range(1 << count_log2):
        digest = hashlib.md5(digest + secret).digest()
    return setting[:12] + _encode64(digest, 16)


def _bcrypt_check(secret, hashed):
    try:
        import bcrypt
    except ImportError:
        return False
    try:
        # PHP writes $2y$; the Python library verifies $2b$ identically.
        return bcrypt.checkpw(secret, hashed.replace('$2y$', '$2b$', 1).encode('ascii'))
    except ValueError:
        return False


def verify_wordpress_hash(password, wp_hash):
    if not isinstance(password, str) or not wp_hash:
        return False
    if wp_hash.startswith('$wp$2'):
        mac = hmac.new(b'wp-sha384', password.encode('utf-8'), hashlib.sha384).digest()
        return _bcrypt_check(base64.b64encode(mac), wp_hash[3:])
    if wp_hash.startswith(('$2y$', '$2a$', '$2b$')):
        return _bcrypt_check(password.encode('utf-8'), wp_hash)
    if wp_hash.startswith(('$P$', '$H$')):
        computed = phpass_crypt(password, wp_hash)
        return bool(computed) and constant_time_compare(computed, wp_hash)
    if re.fullmatch(r'[0-9a-f]{32}', wp_hash):
        return constant_time_compare(hashlib.md5(password.encode('utf-8')).hexdigest(), wp_hash)
    return False


def is_supported_wordpress_hash(wp_hash):
    return bool(wp_hash) and (
        wp_hash.startswith(('$P$', '$H$', '$wp$2', '$2y$', '$2a$', '$2b$')) or bool(re.fullmatch(r'[0-9a-f]{32}', wp_hash))
    )


class WordPressPasswordHasher(BasePasswordHasher):
    """Verify-only hasher for imported WordPress password hashes."""

    algorithm = ALGORITHM

    def salt(self):  # pragma: no cover - never used to create hashes
        return ''

    def encode(self, password, salt):
        raise NotImplementedError('WordPress hashes are only verified, never created. Keep this hasher out of first place.')

    def decode(self, encoded):
        algorithm, wp_hash = encoded.split('$', 1)
        assert algorithm == self.algorithm
        return {'algorithm': algorithm, 'hash': wp_hash, 'salt': ''}

    def verify(self, password, encoded):
        return verify_wordpress_hash(password, self.decode(encoded)['hash'])

    def safe_summary(self, encoded):
        return {_('algorithm'): self.algorithm, _('hash'): mask_hash(self.decode(encoded)['hash'])}

    def must_update(self, encoded):
        return True

    def harden_runtime(self, password, encoded):
        pass
