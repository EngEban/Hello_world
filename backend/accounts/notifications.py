"""Safe, per-recipient account notification helpers.

Announcements are stored once for every recipient instead of relying on a
shared global row.  This makes read state, delivery history, and audit data
accurate for each account.
"""

from uuid import uuid4

from django.contrib.auth.models import User
from django.db.models import Q

from .models import AccountNotification, AccountNotificationRead


def recipients_for_audience(audience, user_ids=None):
    """Return active users for a supported dashboard notification audience."""
    audience = str(audience or 'all').strip().lower()
    users = User.objects.filter(is_active=True).select_related('membership_profile')

    if audience == 'selected':
        normalized_ids = [int(item) for item in (user_ids or []) if str(item).isdigit()]
        return users.filter(pk__in=normalized_ids)
    if audience == 'admins':
        return users.filter(Q(is_superuser=True) | Q(membership_profile__access_role='admin'))
    if audience == 'staff':
        return users.filter(is_staff=True)
    if audience == 'premium':
        return users.filter(membership_profile__tier='premium')
    if audience == 'free':
        return users.filter(membership_profile__tier='free')
    return users


def send_account_notification(users, title, message, *, notification_type='info', action_url='', metadata=None, campaign_id=None):
    """Create one notification per distinct active account and return delivery info."""
    campaign_id = campaign_id or uuid4().hex
    shared_metadata = {**(metadata or {}), 'campaign_id': campaign_id}
    recipients = list(users.filter(is_active=True).distinct())
    rows = [
        AccountNotification(
            user=user,
            title=str(title).strip()[:200],
            message=str(message).strip(),
            notification_type=notification_type,
            action_url=str(action_url).strip()[:500],
            metadata=shared_metadata,
        )
        for user in recipients
    ]
    AccountNotification.objects.bulk_create(rows)
    return {'campaign_id': campaign_id, 'recipient_count': len(rows)}


def notify_user(user, title, message, **kwargs):
    if not user or not user.is_active:
        return None
    return send_account_notification(User.objects.filter(pk=user.pk), title, message, **kwargs)


def broadcast_notification(title, message, *, dedupe_key, notification_type='info', action_url='', metadata=None):
    """Create a single notification shown to every account (user=None).

    Cost is one row regardless of the number of users; read state is kept per
    user in AccountNotificationRead.  ``dedupe_key`` makes repeated events (an
    opportunity re-published) a no-op.  Returns (notification, created).
    """
    return AccountNotification.objects.get_or_create(
        dedupe_key=dedupe_key[:120],
        defaults={
            'user': None,
            'title': str(title).strip()[:200],
            'message': str(message).strip(),
            'notification_type': notification_type,
            'action_url': str(action_url).strip()[:500],
            'metadata': {**(metadata or {}), 'campaign_id': dedupe_key[:120]},
        },
    )


def visible_notifications(user):
    """Personal rows plus broadcasts published since the account was created."""
    return AccountNotification.objects.filter(
        Q(user=user) | Q(user__isnull=True, created_at__gte=user.date_joined)
    )


def unread_count(user):
    personal = AccountNotification.objects.filter(user=user, is_read=False).count()
    broadcasts = (
        AccountNotification.objects.filter(user__isnull=True, created_at__gte=user.date_joined)
        .exclude(reads__user=user)
        .count()
    )
    return personal + broadcasts


def read_broadcast_ids(user, notifications):
    ids = [item.pk for item in notifications if item.user_id is None]
    if not ids:
        return set()
    return set(
        AccountNotificationRead.objects.filter(user=user, notification_id__in=ids).values_list('notification_id', flat=True)
    )


def mark_notification_read(user, notification):
    if notification.user_id:
        notification.mark_read()
    else:
        AccountNotificationRead.objects.get_or_create(user=user, notification=notification)
