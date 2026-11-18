from django.db import migrations


DEFAULT_ROLES = [
    ('free', 'Free User', 'Registered user with free feature access.', False, False),
    ('premium', 'Premium User', 'Registered user with premium feature access.', False, False),
    ('editor', 'Dashboard Editor', 'Can edit dashboard content modules.', True, False),
    ('admin', 'Dashboard Admin', 'Can manage users, content, and settings.', True, False),
    ('super_admin', 'Super Admin', 'Full administrative control.', True, True),
]

DEFAULT_PLANS = [
    ('free', 'Free', 'Core ResRef account with public resources and basic tool access.', 'free', 'none', 0),
    ('premium', 'Premium', 'Prepared premium plan for future paid tools and priority support.', 'premium', 'month', 0),
]

DEFAULT_FEATURES = [
    ('research_database', 'Research Database', 'Browse ResRef research resources.', True, True),
    ('sample_size_calculator', 'Sample Size Calculator', 'Calculate study sample sizes.', True, True),
    ('reference_generator', 'Reference Generator', 'Generate structured references.', True, True),
    ('journal_finder', 'Journal Finder', 'Find journals for a manuscript.', True, True),
    ('advanced_search', 'Advanced Search', 'Use advanced research filters.', False, True),
    ('priority_support', 'Priority Support', 'Receive priority support for requests.', False, True),
]

DEFAULT_USAGE_LIMITS = [
    ('reference_generator', 'free', 'day', 100),
    ('journal_finder', 'free', 'day', 50),
    ('sample_size_calculator', 'free', 'day', 100),
    ('advanced_search', 'free', 'day', 20),
]


def seed_saas_foundation(apps, schema_editor):
    AccountRole = apps.get_model('accounts', 'AccountRole')
    SubscriptionPlan = apps.get_model('accounts', 'SubscriptionPlan')
    FeatureEntitlement = apps.get_model('accounts', 'FeatureEntitlement')
    UsageLimit = apps.get_model('accounts', 'UsageLimit')
    MembershipProfile = apps.get_model('accounts', 'MembershipProfile')

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

    for code, label, description, tier, billing_interval, price_cents in DEFAULT_PLANS:
        SubscriptionPlan.objects.get_or_create(
            code=code,
            defaults={
                'label': label,
                'description': description,
                'tier': tier,
                'billing_interval': billing_interval,
                'price_cents': price_cents,
            },
        )

    for code, label, description, free_enabled, premium_enabled in DEFAULT_FEATURES:
        FeatureEntitlement.objects.update_or_create(
            code=code,
            defaults={
                'label': label,
                'description': description,
                'free_enabled': free_enabled,
                'premium_enabled': premium_enabled,
                'is_active': True,
            },
        )

    for feature_code, tier, period, limit in DEFAULT_USAGE_LIMITS:
        UsageLimit.objects.get_or_create(
            feature_code=feature_code,
            tier=tier,
            period=period,
            defaults={'limit': limit},
        )

    free_role = AccountRole.objects.filter(code='free').first()
    premium_role = AccountRole.objects.filter(code='premium').first()
    editor_role = AccountRole.objects.filter(code='editor').first()
    admin_role = AccountRole.objects.filter(code='admin').first()
    super_admin_role = AccountRole.objects.filter(code='super_admin').first()
    free_plan = SubscriptionPlan.objects.filter(code='free').first()
    premium_plan = SubscriptionPlan.objects.filter(code='premium').first()

    for profile in MembershipProfile.objects.select_related('user').all():
        user = profile.user
        if user.is_superuser:
            profile.account_role = super_admin_role
            profile.plan = premium_plan
        elif profile.access_role == 'admin':
            profile.account_role = admin_role
            profile.plan = premium_plan if profile.tier == 'premium' else free_plan
        elif profile.access_role == 'editor':
            profile.account_role = editor_role
            profile.plan = premium_plan if profile.tier == 'premium' else free_plan
        elif profile.tier == 'premium':
            profile.account_role = premium_role
            profile.plan = premium_plan
        else:
            profile.account_role = free_role
            profile.plan = free_plan
        profile.save(update_fields=['account_role', 'plan', 'updated_at'])


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0004_accountrole_subscriptionplan_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_saas_foundation, migrations.RunPython.noop),
    ]
