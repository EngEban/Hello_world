"""Usage endpoints.

Public:
  GET  /api/usage/                       allowance for every metered feature
  GET  /api/usage/<feature>/             allowance for one feature
  POST /api/usage/<feature>/consume/     charge one action for a browser-side tool
Dashboard (settings permissions):
  GET  /api/usage/admin/policies/        policies + today's totals
  POST /api/usage/admin/policies/<feature>/save/
"""

from django.db.models import Count, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from accounts.security import rate_limit
from core.payload import get_payload
from core.permissions import api_permission_required

from . import services
from .models import FeatureUsagePolicy, UsageCounter


def _known_features():
    codes = set(services.METERED_ACTIONS)
    codes.update(FeatureUsagePolicy.objects.values_list('feature_code', flat=True))
    return sorted(codes)


def _not_found():
    return JsonResponse({'success': False, 'error': 'Unknown metered feature.'}, status=404)


@require_GET
def usage_overview_api(request):
    subject = services.subject_for(request)
    policies = {item.feature_code: item for item in FeatureUsagePolicy.objects.all()}
    features = {
        code: services.usage_status(subject, code, policies.get(code) or services.get_policy(code))
        for code in _known_features()
    }
    return JsonResponse({'success': True, 'plan': subject.plan, 'features': features})


@require_GET
def feature_usage_api(request, feature_code):
    if feature_code not in _known_features():
        return _not_found()
    subject = services.subject_for(request)
    return JsonResponse({'success': True, 'usage': services.usage_status(subject, feature_code)})


@require_POST
def consume_usage_api(request, feature_code):
    action = services.CLIENT_METERED_ACTIONS.get(feature_code)
    if not action:
        return _not_found()
    # Bounds row churn from scripted calls; real limits are enforced below.
    if not rate_limit(request, 'usage-consume', feature_code, limit=60, window=60):
        return JsonResponse({'success': False, 'error': 'Too many requests. Please wait a minute and try again.', 'code': 'rate_limited'}, status=429)
    refused = services.gate(request, feature_code, action)
    if refused:
        return refused
    subject = services.subject_for(request)
    return JsonResponse({'success': True, 'usage': services.usage_status(subject, feature_code)})


# ---------------------------------------------------------------- dashboard

def policy_to_dict(policy, totals=None):
    totals = totals or {}
    return {
        'id': policy.pk,
        'feature_code': policy.feature_code,
        'label': services.feature_label(policy.feature_code, policy),
        'limits_enabled': policy.limits_enabled,
        'meter_anonymous': policy.meter_anonymous,
        'anonymous_daily_limit': policy.anonymous_daily_limit,
        'anonymous_monthly_limit': policy.anonymous_monthly_limit,
        'admin_bypass': policy.admin_bypass,
        'display_mode': policy.display_mode,
        'limit_message': policy.limit_message,
        'metered_actions': sorted(services.METERED_ACTIONS.get(policy.feature_code, set())),
        'runs_in_browser': policy.feature_code in services.CLIENT_METERED_ACTIONS,
        'used_today': totals.get('used', 0),
        'subjects_today': totals.get('subjects', 0),
        'updated_at': policy.updated_at.isoformat() if policy.updated_at else None,
    }


def _today_totals():
    start, _reset = services.window('day')
    rows = (
        UsageCounter.objects.filter(period='day', period_start=start)
        .values('feature_code')
        .annotate(used=Sum('count'), subjects=Count('id'))
    )
    return {row['feature_code']: row for row in rows}


@require_GET
@api_permission_required('premium.view')
def admin_policies_api(request):
    totals = _today_totals()
    policies = {item.feature_code: item for item in FeatureUsagePolicy.objects.all()}
    results = [
        policy_to_dict(policies.get(code) or services.get_policy(code), totals.get(code))
        for code in _known_features()
    ]
    day_start, day_reset = services.window('day')
    return JsonResponse({
        'success': True,
        'results': results,
        'timezone': str(services.usage_timezone()),
        'day_start': day_start.isoformat(),
        'day_resets_at': day_reset.isoformat(),
        'display_modes': [{'id': key, 'label': label} for key, label in FeatureUsagePolicy.DISPLAY_MODES],
    })


def _optional_limit(data, key, current):
    if key not in data:
        return current, None
    value = data.get(key)
    if value in (None, ''):
        return None, None
    if isinstance(value, bool):
        return current, f'{key} must be a whole number or empty.'
    try:
        number = int(value)
    except (TypeError, ValueError):
        return current, f'{key} must be a whole number or empty.'
    if number < 0 or number > 1_000_000:
        return current, f'{key} must be between 0 and 1000000.'
    return number, None


def _bool(data, key, current):
    if key not in data:
        return current
    value = data.get(key)
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


@require_POST
@api_permission_required('premium.edit')
def admin_save_policy_api(request, feature_code):
    from accounts.models import FeatureEntitlement

    known = set(_known_features()) | set(FeatureEntitlement.objects.values_list('code', flat=True))
    if feature_code not in known:
        return _not_found()
    data = get_payload(request)
    policy = FeatureUsagePolicy.objects.filter(feature_code=feature_code).first() or FeatureUsagePolicy(
        feature_code=feature_code, label=services.DEFAULT_LABELS.get(feature_code, ''),
    )
    for key in ('anonymous_daily_limit', 'anonymous_monthly_limit'):
        value, problem = _optional_limit(data, key, getattr(policy, key))
        if problem:
            return JsonResponse({'success': False, 'error': problem}, status=400)
        setattr(policy, key, value)
    policy.limits_enabled = _bool(data, 'limits_enabled', policy.limits_enabled)
    policy.meter_anonymous = _bool(data, 'meter_anonymous', policy.meter_anonymous)
    policy.admin_bypass = _bool(data, 'admin_bypass', policy.admin_bypass)
    if 'display_mode' in data:
        if data.get('display_mode') not in dict(FeatureUsagePolicy.DISPLAY_MODES):
            return JsonResponse({'success': False, 'error': 'Unknown display mode.'}, status=400)
        policy.display_mode = data['display_mode']
    if 'label' in data and isinstance(data.get('label'), str):
        policy.label = data['label'].strip()[:200]
    if 'limit_message' in data and isinstance(data.get('limit_message'), str):
        policy.limit_message = data['limit_message'].strip()[:300]
    created = policy.pk is None
    policy.save()
    try:
        from dashboard.api.common import log_activity

        log_activity(
            request, 'settings', 'create' if created else 'update',
            f'Saved usage policy: {policy.feature_code} (limits {"on" if policy.limits_enabled else "off"})', policy,
        )
    except ImportError:  # pragma: no cover - dashboard app is always installed
        pass
    return JsonResponse({'success': True, 'policy': policy_to_dict(policy, _today_totals().get(feature_code))})
