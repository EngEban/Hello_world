"""The one server-side usage-limit engine for every premium-capable tool.

How a metered request is decided (in this order):

1. Feature access - ``accounts.FeatureEntitlement`` (Free/Premium switches,
   feature active). A premium-only feature answers 403 ``premium_required``.
2. Which actions count - ``METERED_ACTIONS`` below. Anything else is free.
3. Who is asking - a signed-in user (plan ``free`` / ``premium`` / ``admin``)
   or an anonymous visitor keyed by a hashed IP (plan ``anonymous``).
4. The allowance - ``accounts.UsageLimit`` rows for Free/Premium, the
   ``FeatureUsagePolicy`` anonymous fields for visitors, nothing for admins.
   ``FeatureUsagePolicy.limits_enabled = False`` switches every limit for the
   feature off at once (usage is still counted).
5. The counter - ``UsageCounter`` rows per day / month / lifetime window,
   incremented with one conditional UPDATE each inside a transaction, so a
   refresh, a modified frontend or parallel API calls cannot exceed the limit.

Views use :func:`gate` (charge now), :func:`precheck` (refuse early without
charging) or the :func:`metered` decorator; all return the same JSON 429.
"""

import hashlib
import hmac
import ipaddress
import math
import os
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from functools import wraps
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils import timezone

from .models import FeatureUsagePolicy, UsageCounter


PERIODS = ('day', 'month', 'lifetime')
LIFETIME_START = date(2000, 1, 1)
PLANS = ('anonymous', 'free', 'premium', 'admin')

# Which actions use up quota (decided 2026-10-18, T-12; extended 2026-10-22).
# Saving a workspace, uploading a dataset, exporting and viewing never count.
METERED_ACTIONS = {
    'reference_generator': {'reference_lookup'},
    'journal_finder': {'journal_match'},
    'sample_size_calculator': {'calculate'},
    'research_analyzer': {'run_analysis', 'generate_master_report'},
}

# Tools whose work runs in the browser report their action through
# POST /api/usage/<feature>/consume/ before showing results.
CLIENT_METERED_ACTIONS = {
    'journal_finder': 'journal_match',
    'sample_size_calculator': 'calculate',
}

ACTION_WORDS = {
    'reference_generator': ('lookup', 'lookups'),
    'journal_finder': ('search', 'searches'),
    'sample_size_calculator': ('calculation', 'calculations'),
    'research_analyzer': ('analysis', 'analyses'),
}

DEFAULT_LABELS = {
    'reference_generator': 'Reference Generator',
    'journal_finder': 'Journal Finder',
    'sample_size_calculator': 'Sample Size Calculator',
    'research_analyzer': 'Research Analyzer',
}


class _LimitReached(Exception):
    def __init__(self, period):
        super().__init__(period)
        self.period = period


@dataclass
class Subject:
    key: str
    plan: str
    user: object = None
    profile: object = None

    @property
    def is_anonymous(self):
        return self.plan == 'anonymous'


@dataclass
class UsageDecision:
    allowed: bool
    feature_code: str
    status: int = 200
    code: str = ''
    message: str = ''
    usage: dict = field(default_factory=dict)
    counted: bool = False


# ---------------------------------------------------------------- time windows

def usage_timezone():
    name = getattr(settings, 'RESREF_USAGE_TIMEZONE', '') or os.getenv('RESREF_USAGE_TIMEZONE', '') or 'UTC'
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo('UTC')


def window(period, now=None):
    """(start date, reset datetime or None) of the current ``period``."""
    tz = usage_timezone()
    local = timezone.localtime(now or timezone.now(), tz)
    today = local.date()
    if period == 'day':
        nxt = today + timedelta(days=1)
        return today, datetime.combine(nxt, time.min, tzinfo=tz)
    if period == 'month':
        start = today.replace(day=1)
        nxt = (start + timedelta(days=32)).replace(day=1)
        return start, datetime.combine(nxt, time.min, tzinfo=tz)
    return LIFETIME_START, None


# ---------------------------------------------------------------- subjects

def is_admin_user(user, profile=None):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if profile is not None:
        role = profile.account_role if profile.account_role_id else None
        if role and role.is_active and (role.is_super_admin or role.code in {'admin', 'super_admin'}):
            return True
        if user.is_staff and profile.access_role == 'admin':
            return True
    return False


def _ip_bucket(request):
    from accounts.security import client_ip

    ip = client_ip(request)
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        return 'unknown'
    if parsed.version == 6:
        # One household/device usually owns a whole /64; rotating within it
        # must not reset the allowance.
        return str(ipaddress.ip_network(f'{parsed}/64', strict=False))
    return str(parsed)


def subject_for(request=None, user=None):
    from accounts.entitlements import get_profile

    user = user if user is not None else getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        profile = get_profile(user)
        plan = 'admin' if is_admin_user(user, profile) else profile.effective_tier
        return Subject(key=f'user:{user.pk}', plan=plan, user=user, profile=profile)
    bucket = _ip_bucket(request) if request is not None else 'unknown'
    digest = hmac.new(settings.SECRET_KEY.encode('utf-8'), f'usage-ip:{bucket}'.encode('utf-8'), hashlib.sha256).hexdigest()
    return Subject(key=f'ip:{digest[:40]}', plan='anonymous')


# ---------------------------------------------------------------- configuration

def get_policy(feature_code):
    """The saved policy, or an unsaved default (limits on, anonymous free)."""
    policy = FeatureUsagePolicy.objects.filter(feature_code=feature_code).first()
    return policy or FeatureUsagePolicy(feature_code=feature_code, label=DEFAULT_LABELS.get(feature_code, ''))


def feature_label(feature_code, policy=None):
    if policy is not None and policy.label:
        return policy.label
    return DEFAULT_LABELS.get(feature_code) or feature_code.replace('_', ' ').title()


def configured_limits(subject, feature_code, policy):
    """{period: limit} configured for this subject's plan (ignores the switch)."""
    if subject.plan == 'anonymous':
        limits = {'day': policy.anonymous_daily_limit, 'month': policy.anonymous_monthly_limit}
        return {period: value for period, value in limits.items() if value is not None}
    if subject.plan == 'admin' and policy.admin_bypass:
        return {}
    from accounts.models import UsageLimit

    tier = subject.profile.effective_tier if subject.profile is not None else 'free'
    limits = {}
    for row in UsageLimit.objects.filter(feature_code=feature_code, tier=tier, is_active=True):
        if row.period in PERIODS:
            limits[row.period] = min(row.limit, limits.get(row.period, row.limit))
    return limits


def enforced_limits(subject, feature_code, policy):
    if not policy.limits_enabled:
        return {}
    return configured_limits(subject, feature_code, policy)


def is_counted(subject, policy):
    return not (subject.is_anonymous and not policy.meter_anonymous)


def access_denial(subject, feature_code):
    """A denied UsageDecision when Free/Premium feature switches forbid use."""
    from accounts.models import FeatureEntitlement

    feature = FeatureEntitlement.objects.filter(code=feature_code).first()
    if feature is None or subject.plan == 'admin':
        return None
    if not feature.is_active:
        return UsageDecision(False, feature_code, 403, 'feature_disabled', 'This feature is not available right now.')
    if subject.is_anonymous:
        if feature.free_enabled:
            return None
        return UsageDecision(False, feature_code, 401, 'auth_required', 'Please sign in to use this feature.')
    if not feature.allows(subject.profile):
        return UsageDecision(False, feature_code, 403, 'premium_required', 'This feature requires premium access.')
    return None


# ---------------------------------------------------------------- status

def _counts(subject, feature_code, now=None):
    starts = {period: window(period, now)[0] for period in PERIODS}
    rows = UsageCounter.objects.filter(subject=subject.key, feature_code=feature_code, period__in=PERIODS)
    found = {(row.period, row.period_start): row.count for row in rows}
    return {period: found.get((period, start), 0) for period, start in starts.items()}


def usage_status(subject, feature_code, policy=None, now=None):
    policy = policy or get_policy(feature_code)
    counted = is_counted(subject, policy)
    counts = _counts(subject, feature_code, now) if counted else {period: 0 for period in PERIODS}
    limits = enforced_limits(subject, feature_code, policy) if counted else {}
    rows = []
    for period in PERIODS:
        if period not in limits:
            continue
        _start, reset_at = window(period, now)
        used = counts[period]
        rows.append({
            'period': period,
            'limit': limits[period],
            'used': used,
            'remaining': max(limits[period] - used, 0),
            'reset_at': reset_at.isoformat() if reset_at else None,
        })
    binding = min(rows, key=lambda item: (item['remaining'], PERIODS.index(item['period']))) if rows else None
    singular, plural = ACTION_WORDS.get(feature_code, ('use', 'uses'))
    denial = access_denial(subject, feature_code)
    return {
        'feature': feature_code,
        # Whether this visitor/member may use the tool at all (Free/Premium switches).
        'access': {'allowed': denial is None, 'code': denial.code if denial else '', 'message': denial.message if denial else ''},
        'label': feature_label(feature_code, policy),
        'plan': subject.plan,
        'limits_enabled': policy.limits_enabled,
        'counted': counted,
        'unlimited': binding is None,
        'display_mode': policy.display_mode,
        'unit': {'singular': singular, 'plural': plural},
        'used_today': counts['day'],
        'used_this_month': counts['month'],
        'limits': rows,
        'limit': binding['limit'] if binding else None,
        'remaining': binding['remaining'] if binding else None,
        'period': binding['period'] if binding else None,
        'reset_at': binding['reset_at'] if binding else None,
    }


def _limit_message(feature_code, policy, row):
    singular, plural = ACTION_WORDS.get(feature_code, ('use', 'uses'))
    label = feature_label(feature_code, policy)
    amount = f"{row['limit']} {singular if row['limit'] == 1 else plural}"
    if row['period'] == 'lifetime':
        message = f'You have used all {amount} available for {label}.'
    else:
        when = 'today' if row['period'] == 'day' else 'this month'
        reset = datetime.fromisoformat(row['reset_at'])
        message = (
            f'You have used all {amount} for {label} {when}. '
            f'Your allowance resets on {reset:%d %b %Y} at {reset:%H:%M} {reset.tzname()}.'
        )
    if policy.limit_message:
        message = f'{message} {policy.limit_message}'
    return message


def _denied_for_limit(subject, feature_code, policy, period):
    usage = usage_status(subject, feature_code, policy)
    row = next((item for item in usage['limits'] if item['period'] == period), None)
    if row is None:  # limit changed between the check and the status read
        row = {'period': period, 'limit': 0, 'used': 0, 'remaining': 0, 'reset_at': window(period)[1].isoformat() if window(period)[1] else None}
    usage = {**usage, 'limit': row['limit'], 'remaining': 0, 'period': period, 'reset_at': row['reset_at']}
    return UsageDecision(False, feature_code, 429, 'usage_limit', _limit_message(feature_code, policy, row), usage)


# ---------------------------------------------------------------- deciding

def precheck(request, feature_code, *, user=None, amount=1, check_access=True):
    """Read-only check. Returns a JsonResponse to send back, or None."""
    decision = check(request, feature_code, user=user, amount=amount, check_access=check_access)
    return None if decision.allowed else decision_response(decision)


def check(request, feature_code, *, user=None, amount=1, check_access=True):
    subject = subject_for(request, user)
    if check_access:
        denial = access_denial(subject, feature_code)
        if denial:
            return denial
    policy = get_policy(feature_code)
    usage = usage_status(subject, feature_code, policy)
    for row in usage['limits']:
        if row['remaining'] < amount:
            return _denied_for_limit(subject, feature_code, policy, row['period'])
    return UsageDecision(True, feature_code, usage=usage)


def consume(request, feature_code, action, *, user=None, amount=1, metadata=None, check_access=True, force=False):
    """Charge ``amount`` units of ``feature_code`` for ``action`` if allowed.

    ``force`` charges even when ``action`` is not in METERED_ACTIONS (legacy
    ``accounts.entitlements.consume_usage`` callers).
    """
    subject = subject_for(request, user)
    if check_access:
        denial = access_denial(subject, feature_code)
        if denial:
            return denial
    policy = get_policy(feature_code)
    if (not force and action not in METERED_ACTIONS.get(feature_code, set())) or not is_counted(subject, policy):
        return UsageDecision(True, feature_code)
    limits = enforced_limits(subject, feature_code, policy)
    now = timezone.now()
    try:
        with transaction.atomic():
            for period in PERIODS:
                start, _reset = window(period, now)
                counter, _created = UsageCounter.objects.get_or_create(
                    subject=subject.key, feature_code=feature_code, period=period, period_start=start,
                )
                rows = UsageCounter.objects.filter(pk=counter.pk)
                limit = limits.get(period)
                if limit is not None:
                    if limit < amount:
                        raise _LimitReached(period)
                    # The limit is part of the UPDATE itself, so concurrent
                    # requests cannot both take the last unit.
                    rows = rows.filter(count__lte=limit - amount)
                if rows.update(count=F('count') + amount, updated_at=now) != 1:
                    raise _LimitReached(period)
            if subject.user is not None:
                from accounts.models import UsageRecord

                UsageRecord.objects.create(
                    user=subject.user,
                    feature_code=feature_code,
                    amount=amount,
                    metadata={**(metadata or {}), 'action': action},
                )
    except _LimitReached as exc:
        return _denied_for_limit(subject, feature_code, policy, exc.period)
    return UsageDecision(True, feature_code, counted=True)


def decision_response(decision):
    payload = {'success': False, 'error': decision.message, 'code': decision.code, 'feature': decision.feature_code}
    response_usage = decision.usage or {}
    if decision.code == 'usage_limit':
        payload.update({
            'usage': response_usage,
            'limit': response_usage.get('limit'),
            'remaining': 0,
            'period': response_usage.get('period'),
            'reset_at': response_usage.get('reset_at'),
        })
    response = JsonResponse(payload, status=decision.status)
    reset_at = response_usage.get('reset_at')
    if decision.status == 429 and reset_at:
        seconds = (datetime.fromisoformat(reset_at) - timezone.now()).total_seconds()
        response['Retry-After'] = str(max(int(math.ceil(seconds)), 1))
    return response


def gate(request, feature_code, action, *, user=None, amount=1, metadata=None, check_access=True):
    """Charge now. Returns a JsonResponse to send back when refused, else None."""
    decision = consume(request, feature_code, action, user=user, amount=amount, metadata=metadata, check_access=check_access)
    return None if decision.allowed else decision_response(decision)


def metered(feature_code, action, *, check_access=True):
    """View decorator: charge one unit before the view runs."""
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            refused = gate(request, feature_code, action, check_access=check_access)
            return refused or view(request, *args, **kwargs)
        return wrapped
    return decorator
