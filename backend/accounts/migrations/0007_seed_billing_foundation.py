from django.db import migrations


def seed_billing_foundation(apps, schema_editor):
    SubscriptionPlan = apps.get_model('accounts', 'SubscriptionPlan')
    MembershipProfile = apps.get_model('accounts', 'MembershipProfile')
    UserSubscription = apps.get_model('accounts', 'UserSubscription')

    free_plan, _ = SubscriptionPlan.objects.update_or_create(
        code='free',
        defaults={
            'label': 'Free',
            'description': 'Core ResRef account with public resources and basic tool access.',
            'tier': 'free',
            'provider': 'manual',
            'provider_price_id': '',
            'billing_interval': 'none',
            'price_cents': 0,
            'currency': 'USD',
            'is_public': True,
            'is_active': True,
        },
    )
    premium_monthly, _ = SubscriptionPlan.objects.update_or_create(
        code='premium_monthly',
        defaults={
            'label': 'Premium Monthly',
            'description': 'Monthly ResRef Premium plan for advanced tools and priority support.',
            'tier': 'premium',
            'provider': 'stripe',
            'provider_price_id': '',
            'billing_interval': 'month',
            'price_cents': 0,
            'currency': 'USD',
            'is_public': True,
            'is_active': True,
        },
    )
    SubscriptionPlan.objects.update_or_create(
        code='premium_yearly',
        defaults={
            'label': 'Premium Yearly',
            'description': 'Yearly ResRef Premium plan for advanced tools and priority support.',
            'tier': 'premium',
            'provider': 'stripe',
            'provider_price_id': '',
            'billing_interval': 'year',
            'price_cents': 0,
            'currency': 'USD',
            'is_public': True,
            'is_active': True,
        },
    )

    legacy = SubscriptionPlan.objects.filter(code='premium').first()
    if legacy:
        legacy.label = 'Premium Legacy'
        legacy.description = 'Legacy Premium compatibility plan. New billing uses premium_monthly or premium_yearly.'
        legacy.tier = 'premium'
        legacy.provider = 'manual'
        legacy.provider_price_id = ''
        legacy.is_public = False
        legacy.is_active = True
        legacy.save(update_fields=['label', 'description', 'tier', 'provider', 'provider_price_id', 'is_public', 'is_active'])
        MembershipProfile.objects.filter(plan=legacy).update(plan=premium_monthly)
        UserSubscription.objects.filter(plan=legacy).update(plan=premium_monthly)

    MembershipProfile.objects.filter(tier='free', plan__isnull=True).update(plan=free_plan)
    MembershipProfile.objects.filter(tier='premium', plan__isnull=True).update(plan=premium_monthly)


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0006_accountnotification_billingwebhookevent_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_billing_foundation, migrations.RunPython.noop),
    ]
