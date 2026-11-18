from .common import *
from resref.url_safety import is_safe_link, looks_like_link_setting
from accounts.models import FeatureEntitlement, MembershipProfile, SubscriptionPlan, UsageLimit
from django.utils.text import slugify


def entitlement_to_dict(item):
    return {
        'id': item.id,
        'code': item.code,
        'label': item.label,
        'description': item.description,
        'free_enabled': item.free_enabled,
        'premium_enabled': item.premium_enabled,
        'is_active': item.is_active,
    }


def subscription_plan_to_dict(item):
    return {
        'id': item.id,
        'code': item.code,
        'label': item.label,
        'description': item.description,
        'tier': item.tier,
        'provider': item.provider,
        'provider_price_id': item.provider_price_id,
        'billing_interval': item.billing_interval,
        'price_cents': item.price_cents,
        'currency': item.currency,
        'is_public': item.is_public,
        'is_active': item.is_active,
        'updated_at': item.updated_at.isoformat() if item.updated_at else None,
    }


def usage_limit_to_dict(item):
    return {
        'id': item.id,
        'feature_code': item.feature_code,
        'tier': item.tier,
        'period': item.period,
        'limit': item.limit,
        'is_active': item.is_active,
        'updated_at': item.updated_at.isoformat() if item.updated_at else None,
    }

@require_GET
@api_permission_required('settings.view')
def settings_api(request):
    settings = SiteSettings.objects.order_by('group', 'label', 'key')
    return JsonResponse({'results': [setting_to_dict(setting) for setting in settings]})

@require_POST
@api_permission_required('settings.edit')
def save_settings_api(request):
    data = get_payload(request)
    pending_settings = data.get('settings', [])
    if not isinstance(pending_settings, list):
        return error_response('settings must be a list.')
    pending_settings = [item for item in pending_settings if isinstance(item, dict)]
    # Validate every link before writing anything, so a bad value cannot
    # leave a half-saved batch.
    for item in pending_settings:
        key = str(item.get('key') or '').strip()
        # Over-long values would raise a database error (HTTP 500) on PostgreSQL.
        if len(key) > 100 or len(str(item.get('label') or '').strip()) > 200 or len(str(item.get('group') or '').strip()) > 100:
            return error_response('Setting keys and groups must be 100 characters or fewer, labels 200.')
        if key and looks_like_link_setting(key) and not is_safe_link(str(item.get('value') or '')):
            return error_response(f'"{key}" must be an http(s), mailto or tel link, or a path starting with "/".')
    sensitive_keys = [
        str(item.get('key', '')).strip() for item in pending_settings
        if isinstance(item, dict) and SiteSettings.is_sensitive_key(str(item.get('key', '')).strip())
    ]
    if sensitive_keys:
        log_activity(
            request, 'settings', 'system', 'Rejected attempt to store a secret in site settings',
            metadata={'setting_keys': sensitive_keys},
        )
        return error_response('Secrets, keys, tokens, and passwords must be configured through environment variables, not site settings.')
    saved = []
    for item in pending_settings:
        key = str(item.get('key') or '').strip()
        if not key:
            continue
        setting, _ = SiteSettings.objects.update_or_create(
            key=key,
            defaults={
                'value': item.get('value', ''),
                'label': str(item.get('label') or '').strip(),
                'group': str(item.get('group') or 'general').strip() or 'general',
            },
        )
        saved.append(setting_to_dict(setting))
    log_activity(request, 'settings', 'update', f'Updated {len(saved)} site settings')
    from django.core.cache import cache
    from blog.api_views import PUBLIC_SITE_SETTINGS_CACHE_KEY
    cache.delete(PUBLIC_SITE_SETTINGS_CACHE_KEY)
    return JsonResponse({'success': True, 'results': saved})


@require_GET
@api_permission_required('premium.view')
def feature_entitlements_api(request):
    qs = FeatureEntitlement.objects.order_by('label')
    return JsonResponse({'results': [entitlement_to_dict(item) for item in qs]})


@require_POST
@api_save_permission_required('premium')
def save_feature_entitlement_api(request, pk=None):
    data = get_payload(request)
    item = get_object_or_404(FeatureEntitlement, pk=pk) if pk else FeatureEntitlement()
    code = slugify(data.get('code', item.code or '')).replace('-', '_')[:100]
    label = text_field(data, 'label', item.label)
    if not code:
        return error_response('Feature code is required.')
    if not label:
        return error_response('Feature label is required.')
    if FeatureEntitlement.objects.exclude(pk=item.pk).filter(code=code).exists():
        return error_response('A feature with this code already exists.')
    item.code = code
    item.label = label[:200]
    item.description = text_field(data, 'description', item.description, 1000)
    item.free_enabled = parse_boolean(data.get('free_enabled'), item.free_enabled)
    item.premium_enabled = parse_boolean(data.get('premium_enabled'), item.premium_enabled)
    item.is_active = parse_boolean(data.get('is_active'), item.is_active)
    item.save()
    log_activity(request, 'settings', 'update' if pk else 'create', f'Saved feature access: {item.label}', item)
    return JsonResponse({'success': True, 'feature': entitlement_to_dict(item)})


@require_GET
@api_permission_required('premium.view')
def subscription_plans_api(request):
    qs = SubscriptionPlan.objects.order_by('tier', 'price_cents', 'label')
    return JsonResponse({'results': [subscription_plan_to_dict(item) for item in qs]})


@require_POST
@api_save_permission_required('premium')
def save_subscription_plan_api(request, pk=None):
    data = get_payload(request)
    item = get_object_or_404(SubscriptionPlan, pk=pk) if pk else SubscriptionPlan()
    code = slugify(data.get('code', item.code or ''))[:80]
    label = text_field(data, 'label', item.label)
    if not code:
        return error_response('Plan code is required.')
    if not label:
        return error_response('Plan label is required.')
    if SubscriptionPlan.objects.exclude(pk=item.pk).filter(code=code).exists():
        return error_response('A plan with this code already exists.')
    tier = data.get('tier', item.tier or 'free')
    provider = data.get('provider', item.provider or 'manual')
    billing_interval = data.get('billing_interval', item.billing_interval or 'none')
    if tier not in dict(MembershipProfile.TIERS):
        return error_response('Unknown plan tier.')
    if provider not in dict(SubscriptionPlan.PROVIDERS):
        return error_response('Unknown billing provider.')
    if billing_interval not in dict(SubscriptionPlan.INTERVALS):
        return error_response('Unknown billing interval.')
    item.code = code
    item.label = label[:160]
    item.description = text_field(data, 'description', item.description, 1000)
    item.tier = tier
    item.provider = provider
    item.provider_price_id = text_field(data, 'provider_price_id', item.provider_price_id, 255)
    item.billing_interval = billing_interval
    item.price_cents = max(parse_int(data.get('price_cents'), item.price_cents or 0) or 0, 0)
    item.currency = text_field(data, 'currency', item.currency or 'USD', 10).upper() or 'USD'
    item.is_public = parse_boolean(data.get('is_public'), item.is_public)
    item.is_active = parse_boolean(data.get('is_active'), item.is_active)
    item.save()
    log_activity(request, 'settings', 'update' if pk else 'create', f'Saved subscription plan: {item.label}', item)
    return JsonResponse({'success': True, 'plan': subscription_plan_to_dict(item)})


@require_GET
@api_permission_required('premium.view')
def usage_limits_api(request):
    qs = UsageLimit.objects.order_by('feature_code', 'tier', 'period')
    return JsonResponse({'results': [usage_limit_to_dict(item) for item in qs]})


@require_POST
@api_save_permission_required('premium')
def save_usage_limit_api(request, pk=None):
    data = get_payload(request)
    item = get_object_or_404(UsageLimit, pk=pk) if pk else UsageLimit()
    feature_code = slugify(data.get('feature_code', item.feature_code or '')).replace('-', '_')[:100]
    if not feature_code:
        return error_response('Feature code is required.')
    tier = data.get('tier', item.tier or 'free')
    period = data.get('period', item.period or 'day')
    if tier not in dict(MembershipProfile.TIERS):
        return error_response('Unknown account tier.')
    if period not in dict(UsageLimit.PERIODS):
        return error_response('Unknown usage period.')
    limit_value = parse_int(data.get('limit'), item.limit or 0)
    if not limit_value or limit_value < 1:
        return error_response('Usage limit must be at least 1.')
    duplicate = UsageLimit.objects.exclude(pk=item.pk).filter(feature_code=feature_code, tier=tier, period=period).exists()
    if duplicate:
        return error_response('A usage limit already exists for this feature, tier, and period.')
    item.feature_code = feature_code
    item.tier = tier
    item.period = period
    item.limit = limit_value
    item.is_active = parse_boolean(data.get('is_active'), item.is_active)
    item.save()
    log_activity(request, 'settings', 'update' if pk else 'create', f'Saved usage limit: {item.feature_code} / {item.tier}', item)
    return JsonResponse({'success': True, 'limit': usage_limit_to_dict(item)})

@require_GET
@api_permission_required('settings.view')
def api_docs_api(request):
    return JsonResponse({
        'title': 'ResRef Dashboard API',
        'version': 1,
        'auth': 'Session authentication with CSRF-protected writes. Dashboard users require staff status and dashboard role permissions.',
        'patterns': {
            'pagination': 'GET endpoints return results and pagination where list size can grow.',
            'filtering': 'Use q, status, category, sort, page, and per_page where supported.',
            'exports': '/api/dashboard/export/<module>/?format=csv|excel|json|pdf',
            'audit': 'Mutating dashboard endpoints write DashboardActivityLog rows.',
        },
        'modules': DASHBOARD_MODULES,
        'endpoints': [
            {'method': 'GET', 'path': '/api/dashboard/stats/', 'module': 'overview'},
            {'method': 'GET', 'path': '/api/dashboard/users/', 'module': 'users'},
            {'method': 'POST', 'path': '/api/dashboard/users/save/', 'module': 'users'},
            {'method': 'GET', 'path': '/api/dashboard/posts/', 'module': 'content'},
            {'method': 'GET', 'path': '/api/dashboard/opportunities/', 'module': 'opportunities'},
            {'method': 'GET', 'path': '/api/dashboard/services/', 'module': 'services'},
            {'method': 'GET', 'path': '/api/dashboard/service-requests/', 'module': 'services'},
            {'method': 'GET', 'path': '/api/dashboard/forms/', 'module': 'forms'},
            {'method': 'GET', 'path': '/api/dashboard/reports/', 'module': 'reports'},
            {'method': 'GET', 'path': '/api/dashboard/activity/', 'module': 'settings'},
            {'method': 'GET', 'path': '/api/dashboard/roles-permissions/', 'module': 'roles'},
            {'method': 'POST', 'path': '/api/dashboard/roles/save/', 'module': 'roles'},
            {'method': 'POST', 'path': '/api/dashboard/roles/<id>/save/', 'module': 'roles'},
            {'method': 'POST', 'path': '/api/dashboard/roles/<id>/delete/', 'module': 'roles'},
            {'method': 'POST', 'path': '/api/dashboard/roles/<id>/members/', 'module': 'roles'},
            {'method': 'GET', 'path': '/api/dashboard/feature-entitlements/', 'module': 'premium'},
            {'method': 'POST', 'path': '/api/dashboard/feature-entitlements/save/', 'module': 'premium'},
            {'method': 'GET', 'path': '/api/dashboard/subscription-plans/', 'module': 'premium'},
            {'method': 'POST', 'path': '/api/dashboard/subscription-plans/save/', 'module': 'premium'},
            {'method': 'GET', 'path': '/api/dashboard/usage-limits/', 'module': 'premium'},
            {'method': 'POST', 'path': '/api/dashboard/usage-limits/save/', 'module': 'premium'},
        ],
    })
