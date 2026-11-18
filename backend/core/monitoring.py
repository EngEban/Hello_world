"""Optional Sentry error reporting.

Nothing happens unless SENTRY_DSN is set, so local development, CI and any
deployment without a Sentry project behave exactly as before.
"""

import logging
import os

logger = logging.getLogger('resref.monitoring')

# Request headers that can carry credentials; dropped from every event.
_SENSITIVE_HEADERS = {'authorization', 'cookie', 'x-csrftoken', 'x-api-key', 'stripe-signature'}


def _float_env(name, default):
    try:
        return min(max(float(os.getenv(name, str(default))), 0.0), 1.0)
    except ValueError:
        return default


def scrub_event(event, hint=None):
    """Remove cookies, auth headers, bodies and query strings before sending."""
    request = event.get('request') or {}
    headers = request.get('headers')
    if isinstance(headers, dict):
        request['headers'] = {
            key: ('[Filtered]' if key.lower() in _SENSITIVE_HEADERS else value)
            for key, value in headers.items()
        }
    request.pop('cookies', None)
    request.pop('data', None)
    if request.get('query_string'):
        request['query_string'] = '[Filtered]'
    if request:
        event['request'] = request
    user = event.get('user')
    if isinstance(user, dict):
        # Keep only the numeric id so an error can be traced to an account
        # without sending e-mail addresses or IPs to a third party.
        event['user'] = {'id': user['id']} if 'id' in user else {}
    return event


def init_sentry(environment):
    dsn = os.getenv('SENTRY_DSN', '').strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
    except ImportError:
        logger.warning('SENTRY_DSN is set but sentry-sdk is not installed; error reporting is off.')
        return False
    sentry_sdk.init(
        dsn=dsn,
        integrations=[DjangoIntegration()],
        environment=os.getenv('SENTRY_ENVIRONMENT', '').strip() or environment,
        release=(os.getenv('SENTRY_RELEASE', '').strip() or os.getenv('RAILWAY_GIT_COMMIT_SHA', '').strip() or None),
        # Performance tracing is off unless explicitly enabled (it costs quota).
        traces_sample_rate=_float_env('SENTRY_TRACES_SAMPLE_RATE', 0.0),
        send_default_pii=False,
        max_request_body_size='never',
        before_send=scrub_event,
    )
    # Bad Host headers come from internet scanners, not from bugs.
    from sentry_sdk.integrations.logging import ignore_logger
    ignore_logger('django.security.DisallowedHost')
    return True
