from django.conf import settings
from django.db import migrations


DEFAULT_FEATURES = [
    ('research_database', 'Research Database', 'Browse ResRef research resources.', True, True),
    ('reference_generator', 'Reference Generator', 'Generate structured references.', True, True),
    ('journal_finder', 'Journal Finder', 'Find journals for a manuscript.', True, True),
    ('advanced_search', 'Advanced Search', 'Use advanced research filters.', False, True),
    ('priority_support', 'Priority Support', 'Receive priority support for requests.', False, True),
]


def seed_accounts(apps, schema_editor):
    user_model = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(*user_model)
    MembershipProfile = apps.get_model('accounts', 'MembershipProfile')
    FeatureEntitlement = apps.get_model('accounts', 'FeatureEntitlement')

    for user in User.objects.all():
        defaults = {}
        if user.is_superuser:
            defaults = {'access_role': 'admin', 'tier': 'premium', 'email_verified': True}
        MembershipProfile.objects.get_or_create(user=user, defaults=defaults)

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


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_accounts, migrations.RunPython.noop),
    ]
