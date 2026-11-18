"""Self-service data export and account deletion (GDPR-style).

Deletion never removes database rows. The account is deactivated and its
personal data is overwritten, so records that other data depends on
(subscriptions, audit logs, opportunities, analyzer history) stay intact but
no longer identify the person.
"""

from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from .entitlements import get_profile
from .models import (
    AccountNotification,
    EmailVerificationRequest,
    MembershipProfile,
    UsageRecord,
    UserSubscription,
    UserToolWorkspace,
)
from .profile_fields import country_name


EXPORT_ROW_LIMIT = 5000
LIVE_SUBSCRIPTION_STATUSES = {'trialing', 'active', 'past_due', 'incomplete', 'unpaid'}


def _iso(value):
    return value.isoformat() if value else None


def build_account_export(user):
    """Everything ResRef stores about the member, as plain JSON data."""
    profile = get_profile(user)
    return {
        'format': 'resref-account-export',
        'version': 1,
        'exported_at': timezone.now().isoformat(),
        'account': {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_joined': _iso(user.date_joined),
            'last_login': _iso(user.last_login),
        },
        'profile': {
            'display_name': profile.display_name,
            'organization': profile.organization,
            'specialization': profile.specialization,
            'avatar_url': profile.avatar_url,
            'country': profile.country,
            'country_name': country_name(profile.country),
            'phone_number': profile.phone_number,
            'marketing_opt_in': profile.marketing_opt_in,
            'auth_provider': profile.auth_provider,
            'google_sign_in_linked': bool(profile.google_subject),
            'email_verified': profile.email_verified,
            'tier': profile.effective_tier,
            'plan': profile.plan.code if profile.plan_id else None,
            'premium_until': _iso(profile.premium_until),
            'created_at': _iso(profile.created_at),
        },
        'subscriptions': [
            {
                'plan': item.plan.code,
                'status': item.status,
                'provider': item.provider,
                'current_period_start': _iso(item.current_period_start),
                'current_period_end': _iso(item.current_period_end),
                'cancel_at_period_end': item.cancel_at_period_end,
                'created_at': _iso(item.created_at),
            }
            for item in UserSubscription.objects.filter(user=user).select_related('plan').order_by('created_at')
        ],
        'tool_workspaces': [
            {'tool_key': item.tool_key, 'data': item.data, 'updated_at': _iso(item.updated_at)}
            for item in UserToolWorkspace.objects.filter(user=user).order_by('tool_key')
        ],
        'notifications': [
            {
                'title': item.title,
                'message': item.message,
                'type': item.notification_type,
                'is_read': item.is_read,
                'created_at': _iso(item.created_at),
            }
            for item in AccountNotification.objects.filter(user=user).order_by('-created_at')[:EXPORT_ROW_LIMIT]
        ],
        'usage': [
            {'feature': item.feature_code, 'amount': item.amount, 'created_at': _iso(item.created_at)}
            for item in UsageRecord.objects.filter(user=user).order_by('-created_at')[:EXPORT_ROW_LIMIT]
        ],
    }


def deletion_blocker(user):
    """Return a message when the account cannot be deleted by its owner."""
    profile = get_profile(user)
    if user.is_staff or user.is_superuser or profile.access_role in {'editor', 'admin'} or profile.can_access_dashboard:
        return 'Team and administrator accounts cannot be deleted here. Ask a ResRef administrator to remove your access first.'
    if hasattr(user, 'team_member'):
        return 'Team accounts cannot be deleted here. Ask a ResRef administrator to remove you from the team first.'
    live = UserSubscription.objects.filter(
        user=user, provider='stripe', status__in=LIVE_SUBSCRIPTION_STATUSES, cancel_at_period_end=False,
    ).exists()
    if live:
        return 'Cancel your paid subscription first (Membership section), then delete your account.'
    return ''


def anonymize_account(user):
    """Deactivate the login and overwrite personal data. Returns the old email."""
    old_email = user.email
    with transaction.atomic():
        user.username = f'deleted-{user.pk}-{uuid4().hex[:8]}'
        user.email = ''
        user.first_name = ''
        user.last_name = ''
        user.is_active = False
        user.set_unusable_password()  # also signs out every other session
        user.save(update_fields=['username', 'email', 'first_name', 'last_name', 'is_active', 'password'])

        profile = MembershipProfile.objects.select_for_update().get(user=user)
        profile.display_name = ''
        profile.avatar_url = ''
        profile.organization = ''
        profile.specialization = ''
        profile.country = ''
        profile.phone_number = ''
        profile.google_subject = None
        profile.marketing_opt_in = False
        profile.email_verified = False
        profile.deleted_at = timezone.now()
        profile.save()

        # Outstanding confirmation / email-change links must stop working.
        EmailVerificationRequest.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())

        if old_email:
            # Stop newsletter mail to the deleted member (the row is kept).
            from dashboard.models import NewsletterSubscriber
            NewsletterSubscriber.objects.filter(email__iexact=old_email).update(is_active=False)
    return old_email
