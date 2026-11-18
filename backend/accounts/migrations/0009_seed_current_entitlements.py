from django.db import migrations


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

DEFAULT_USAGE_LIMITS = [
    ('reference_generator', 'free', 'day', 100),
    ('journal_finder', 'free', 'day', 50),
    ('sample_size_calculator', 'free', 'day', 100),
    ('advanced_search', 'free', 'day', 20),
    ('research_analyzer', 'premium', 'month', 25),
]


def seed_current_entitlements(apps, schema_editor):
    FeatureEntitlement = apps.get_model('accounts', 'FeatureEntitlement')
    UsageLimit = apps.get_model('accounts', 'UsageLimit')

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
    for feature_code, tier, period, limit in DEFAULT_USAGE_LIMITS:
        UsageLimit.objects.get_or_create(
            feature_code=feature_code,
            tier=tier,
            period=period,
            defaults={'limit': limit},
        )


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0008_passwordhistory'),
    ]

    operations = [
        migrations.RunPython(seed_current_entitlements, migrations.RunPython.noop),
    ]
