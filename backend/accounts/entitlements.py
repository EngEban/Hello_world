from datetime import datetime, time

from django.conf import settings

from .models import AccountRole, FeatureEntitlement, MembershipProfile, SubscriptionPlan, UsageLimit, UsageRecord


DEFAULT_FEATURES = [
    ('research_database', 'Research Database', 'Browse ResRef research resources.', True, True),
    ('questionnaire_finder', 'Questionnaire Finder', 'Browse questionnaire recommendations and instruments.', True, True),
    ('sample_size_calculator', 'Sample Size Calculator', 'Calculate study sample sizes.', True, True),
    ('reference_generator', 'Reference Generator', 'Generate structured references.', True, True),
    ('journal_finder', 'Journal Finder', 'Find journals for a manuscript.', True, True),
    ('research_analyzer', 'Research Analyzer', 'Prepare datasets, run statistical tests, and generate master reports.', False, True),
    ('advanced_search', 'Advanced Search', 'Use advanced research filters.', False, True),
    ('data_analysis_guide', 'Data Analysis Guide', 'Access guided data analysis workflows and resources.', False, True),
    ('expert_consultation', 'Expert Consultation', 'Request expert research guidance.', True, True),
    ('research_opportunities', 'Research Opportunities', 'Browse research opportunities and collaboration openings.', True, True),
    ('join_team', 'Join Our Team', 'Apply to contribute to the ResRef research network.', True, True),
    ('priority_support', 'Priority Support', 'Receive priority support for requests.', False, True),
]

DEFAULT_PLANS = [
    ('free', 'Free', 'Core ResRef account with public resources and basic tool access.', 'free', 'none', 0, ''),
    ('premium_monthly', 'Premium Monthly', 'Monthly premium access for advanced ResRef workflows.', 'premium', 'month', 0, 'STRIPE_PREMIUM_MONTHLY_PRICE_ID'),
    ('premium_yearly', 'Premium Yearly', 'Yearly premium access for advanced ResRef workflows.', 'premium', 'year', 0, 'STRIPE_PREMIUM_YEARLY_PRICE_ID'),
]

DEFAULT_ROLES = [
    ('free', 'Free User', 'Registered user with free feature access.', False, False),
    ('premium', 'Premium User', 'Registered user with premium feature access.', False, False),
    ('editor', 'Dashboard Editor', 'Can edit dashboard content modules.', True, False),
    ('admin', 'Dashboard Admin', 'Can manage users, content, and settings.', True, False),
    ('super_admin', 'Super Admin', 'Full administrative control.', True, True),
]

DEFAULT_USAGE_LIMITS = [
    ('reference_generator', 'free', 'day', 100),
    ('journal_finder', 'free', 'day', 50),
    ('sample_size_calculator', 'free', 'day', 100),
    ('advanced_search', 'free', 'day', 20),
    ('research_analyzer', 'premium', 'month', 25),
]


def _defaults_are_seeded():
    """Check the migration-seeded rows without performing request-time writes."""
    return (
        AccountRole.objects.filter(code__in=[role[0] for role in DEFAULT_ROLES]).count() == len(DEFAULT_ROLES)
        and FeatureEntitlement.objects.filter(code__in=[feature[0] for feature in DEFAULT_FEATURES]).count() == len(DEFAULT_FEATURES)
        and SubscriptionPlan.objects.filter(code__in=[plan[0] for plan in DEFAULT_PLANS]).count() == len(DEFAULT_PLANS)
        and UsageLimit.objects.filter(
            feature_code__in=[limit[0] for limit in DEFAULT_USAGE_LIMITS],
        ).count() == len(DEFAULT_USAGE_LIMITS)
    )


def _sync_configured_plan_prices():
    """Apply runtime Stripe price configuration without reseeding every table."""
    configured_plans = {
        plan.code: plan
        for plan in SubscriptionPlan.objects.filter(
            code__in=[plan[0] for plan in DEFAULT_PLANS],
        )
    }
    for code, _label, _description, _tier, _interval, _price_cents, price_setting in DEFAULT_PLANS:
        if not price_setting or code not in configured_plans:
            continue
        plan = configured_plans[code]
        price_id = getattr(settings, price_setting, '')
        updates = []
        if price_id and plan.provider_price_id != price_id:
            plan.provider_price_id = price_id
            updates.append('provider_price_id')
        if plan.provider != 'stripe':
            plan.provider = 'stripe'
            updates.append('provider')
        if updates:
            plan.save(update_fields=updates + ['updated_at'])


def seed_default_entitlements(AccountRole, FeatureEntitlement, SubscriptionPlan, UsageLimit):
    """Create missing roles, features, plans and limits; sync Stripe price ids.

    Takes the model classes so the same code runs from a data migration (with
    historical models) and from ``manage.py seed_reference_data``.
    """
    for code, label, description, can_access_dashboard, is_super_admin in DEFAULT_ROLES:
        AccountRole.objects.get_or_create(
            code=code,
            defaults={
                'label': label,
                'description': description,
                'can_access_dashboard': can_access_dashboard,
                'is_super_admin': is_super_admin,
            },
        )
    for code, label, description, free_enabled, premium_enabled in DEFAULT_FEATURES:
        FeatureEntitlement.objects.get_or_create(
            code=code,
            defaults={
                'label': label,
                'description': description,
                'free_enabled': free_enabled,
                'premium_enabled': premium_enabled,
            },
        )
    for code, label, description, tier, interval, price_cents, price_setting in DEFAULT_PLANS:
        plan, created = SubscriptionPlan.objects.get_or_create(
            code=code,
            defaults={
                'label': label,
                'description': description,
                'tier': tier,
                'billing_interval': interval,
                'price_cents': price_cents,
                'provider': 'stripe' if price_setting else 'manual',
                'provider_price_id': getattr(settings, price_setting, '') if price_setting else '',
            },
        )
        if not created and price_setting:
            price_id = getattr(settings, price_setting, '')
            updates = []
            if price_id and plan.provider_price_id != price_id:
                plan.provider_price_id = price_id
                updates.append('provider_price_id')
            if plan.provider != 'stripe':
                plan.provider = 'stripe'
                updates.append('provider')
            if updates:
                plan.save(update_fields=updates + ['updated_at'])
    for feature_code, tier, period, limit in DEFAULT_USAGE_LIMITS:
        UsageLimit.objects.get_or_create(
            feature_code=feature_code,
            tier=tier,
            period=period,
            defaults={'limit': limit},
        )
    _sync_configured_plan_prices()


def ensure_default_entitlements():
    """Defaults are seeded by migration. This only does bounded read checks and
    syncs Stripe price IDs from settings; it reseeds just when an operator has
    deleted a required row. Never needed on ordinary request paths."""
    if _defaults_are_seeded():
        _sync_configured_plan_prices()
        return
    seed_default_entitlements(AccountRole, FeatureEntitlement, SubscriptionPlan, UsageLimit)


def active_features():
    return list(FeatureEntitlement.objects.filter(is_active=True))


def serialize_entitlements(profile, features=None):
    """``features`` lets list views load the feature table once for all rows."""
    if features is None:
        features = active_features()
    return {
        feature.code: {
            'label': feature.label,
            'description': feature.description,
            'allowed': feature.allows(profile),
        }
        for feature in features
    }


def get_profile(user):
    # Reuse the profile Django already cached on the user (select_related or an
    # earlier access) instead of a get_or_create query on every call.
    try:
        return user.membership_profile
    except MembershipProfile.DoesNotExist:
        profile, _ = MembershipProfile.objects.get_or_create(user=user)
        user.membership_profile = profile
        return profile


def feature_code_for_tool(tool_key):
    return {
        'reference-generator': 'reference_generator',
        'journal-finder': 'journal_finder',
        'research-analyzer': 'research_analyzer',
        'sample-size-calculator': 'sample_size_calculator',
        'advanced-search': 'advanced_search',
        'questionnaire-finder': 'questionnaire_finder',
        'data-analysis-guide': 'data_analysis_guide',
        'expert-consultation': 'expert_consultation',
        'research-opportunities': 'research_database',
    }.get(tool_key, tool_key.replace('-', '_'))


# Which actions use up quota now lives in usage.services.METERED_ACTIONS
# (one place for the whole site); re-exported here for existing imports.
def __getattr__(name):
    if name == 'METERED_ACTIONS':
        from usage.services import METERED_ACTIONS
        return METERED_ACTIONS
    raise AttributeError(name)


def meter_action(user, feature_code, action, metadata=None):
    """Record one metered action for a signed-in user.

    Returns (allowed, message). Thin wrapper over the central engine in
    ``usage.services`` (which also handles anonymous visitors when given a
    request); actions not listed in ``usage.services.METERED_ACTIONS`` are
    always allowed and never recorded.
    """
    if not user or not user.is_authenticated:
        return True, ''
    from usage.services import consume

    decision = consume(None, feature_code, action, user=user, metadata=metadata, check_access=False)
    return decision.allowed, decision.message


def check_feature_access(user, feature_code):
    if not user or not user.is_authenticated or not user.is_active:
        return False, 'Please sign in to continue.'
    profile = get_profile(user)
    if user.is_superuser or (profile.account_role_id and profile.account_role.is_super_admin):
        return True, ''
    feature = FeatureEntitlement.objects.filter(code=feature_code, is_active=True).first()
    if not feature:
        return False, 'This feature is not available.'
    if not feature.allows(profile):
        return False, 'This feature requires premium access.'
    return True, ''


def usage_period_start(period):
    """Start of the current usage window (timezone from RESREF_USAGE_TIMEZONE)."""
    from usage.services import usage_timezone, window

    if period not in {'day', 'month'}:
        return None
    start, _reset = window(period)
    return datetime.combine(start, time.min, tzinfo=usage_timezone())


def check_usage_limit(user, feature_code, amount=1):
    """Read-only: would ``amount`` more units fit in the user's allowance?"""
    from usage.services import check

    decision = check(None, feature_code, user=user, amount=amount, check_access=False)
    return decision.allowed, decision.message


def record_usage(user, feature_code, amount=1, metadata=None):
    """Audit row only; quota counting happens in ``usage.services.consume``."""
    return UsageRecord.objects.create(
        user=user,
        feature_code=feature_code,
        amount=amount,
        metadata=metadata or {},
    )


def consume_usage(user, feature_code, amount=1, metadata=None):
    """Atomically enforce configured limits and record one accepted operation.

    Kept for existing callers; delegates to the central engine. ``metadata``
    may carry an ``action``; without one the call is charged as a generic
    use of the feature.
    """
    from usage.services import consume

    metadata = dict(metadata or {})
    action = metadata.pop('action', None) or 'use'
    decision = consume(None, feature_code, action, user=user, amount=amount, metadata=metadata, check_access=False, force=True)
    if not decision.allowed:
        return False, decision.message, None
    record = UsageRecord.objects.filter(user=user, feature_code=feature_code).order_by('-created_at', '-pk').first() if decision.counted else None
    return True, '', record
