from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .entitlements import ensure_default_entitlements
from .models import AccountRole, SubscriptionPlan, MembershipProfile


@receiver(post_save, sender=User)
def ensure_membership_profile(sender, instance, created, raw=False, **kwargs):
    # Do not create/update profiles while Django is loading fixtures.
    # The MembershipProfile records will be loaded directly from the fixture.
    if raw:
        return

    profile, _ = MembershipProfile.objects.get_or_create(user=instance)

    # A Django superuser is an explicit operator-created break-glass account.
    # Mirror that status into ResRef entitlements; this signal never creates or
    # promotes Django superusers itself.
    if (
        instance.is_superuser
        and (
            profile.access_role != "admin"
            or profile.tier != "premium"
            or not profile.account_role_id
            or not profile.plan_id
        )
    ):
        ensure_default_entitlements()

        profile.access_role = "admin"
        profile.tier = "premium"
        profile.email_verified = True
        profile.account_role = AccountRole.objects.filter(
            code="super_admin",
            is_active=True,
        ).first()
        profile.plan = SubscriptionPlan.objects.filter(
            code="premium_monthly",
            is_active=True,
        ).first()

        profile.save(
            update_fields=[
                "access_role",
                "tier",
                "email_verified",
                "account_role",
                "plan",
                "updated_at",
            ]
        )
