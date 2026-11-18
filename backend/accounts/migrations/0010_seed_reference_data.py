from django.db import migrations


def seed(apps, schema_editor):
    from accounts.entitlements import seed_default_entitlements

    seed_default_entitlements(
        apps.get_model('accounts', 'AccountRole'),
        apps.get_model('accounts', 'FeatureEntitlement'),
        apps.get_model('accounts', 'SubscriptionPlan'),
        apps.get_model('accounts', 'UsageLimit'),
    )


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0009_seed_current_entitlements'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
