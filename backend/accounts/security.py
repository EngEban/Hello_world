import hashlib
import ipaddress
import logging

from django.conf import settings
from django.core.cache import cache


logger = logging.getLogger(__name__)


def client_ip(request):
    try:
        if settings.RESREF_TRUST_PROXY:
            # Railway's edge proxy puts the visitor's address in X-Real-IP. Using
            # it avoids treating every visitor behind the same edge as one IP.
            header = getattr(settings, 'RESREF_CLIENT_IP_HEADER', '')
            if header:
                try:
                    return str(ipaddress.ip_address(request.META.get(header, '').strip()))
                except ValueError:
                    pass
            forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
            chain = [item.strip() for item in forwarded.split(',') if item.strip()]
            chain.append(request.META.get('REMOTE_ADDR', '').strip())
            valid_chain = []
            for candidate in chain:
                try:
                    valid_chain.append(str(ipaddress.ip_address(candidate)))
                except ValueError:
                    continue
            trusted_hops = max(int(getattr(settings, 'RESREF_TRUSTED_PROXY_HOPS', 1)), 1)
            if len(valid_chain) > trusted_hops:
                return valid_chain[-(trusted_hops + 1)]
    except (TypeError, ValueError):
        # An invalid proxy setting must collapse to one restrictive bucket.
        return 'unknown'
    remote_addr = request.META.get('REMOTE_ADDR', '').strip()
    try:
        return str(ipaddress.ip_address(remote_addr))
    except ValueError:
        return 'unknown'


def _rate_limit_key(request, scope, identity='', include_ip=True):
    identity = identity.strip().casefold() if isinstance(identity, str) else ''
    source_ip = client_ip(request) if include_ip else ''
    raw_key = f'{scope}:{source_ip}:{identity}'
    digest = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
    return f'resref-rate:{digest}'


def rate_limit(request, scope, identity='', limit=5, window=900, *, include_ip=True):
    key = _rate_limit_key(request, scope, identity, include_ip=include_ip)
    try:
        if cache.add(key, 1, window):
            attempts = 1
        else:
            try:
                attempts = cache.incr(key)
            except ValueError:
                cache.set(key, 1, window)
                attempts = 1
    except Exception:
        if settings.IS_PRODUCTION:
            logger.exception('Rate-limit cache is unavailable; rejecting request.')
            return False
        raise
    return attempts <= limit


def clear_rate_limit(request, scope, identity='', *, include_ip=True):
    try:
        cache.delete(_rate_limit_key(request, scope, identity, include_ip=include_ip))
    except Exception:
        if settings.IS_PRODUCTION:
            logger.exception('Rate-limit cache is unavailable; retaining the existing limit state.')
            return False
        raise
    return True


# Login protection uses three independent counters so that neither rotating IPs
# (credential stuffing against one account) nor rotating accounts (spraying from
# one IP) gets around the limit.
LOGIN_LIMITS = {
    'pair': (8, 900),        # same IP + same account: 8 per 15 minutes
    'account': (20, 3600),   # same account from any IP: 20 per hour
    'ip': (60, 900),         # same IP, any account: 60 per 15 minutes
}


def login_allowed(request, scope, identifier):
    identifier = identifier or ''
    pair_limit, pair_window = LOGIN_LIMITS['pair']
    account_limit, account_window = LOGIN_LIMITS['account']
    ip_limit, ip_window = LOGIN_LIMITS['ip']
    allowed = rate_limit(request, f'{scope}:pair', identifier, limit=pair_limit, window=pair_window)
    if identifier:
        allowed = rate_limit(request, f'{scope}:account', identifier, limit=account_limit, window=account_window, include_ip=False) and allowed
    allowed = rate_limit(request, f'{scope}:ip', '', limit=ip_limit, window=ip_window) and allowed
    return allowed


def login_succeeded(request, scope, identifier):
    clear_rate_limit(request, f'{scope}:pair', identifier or '')
    if identifier:
        clear_rate_limit(request, f'{scope}:account', identifier, include_ip=False)
