"""Read-only account queries (T-20)."""

from .identity import find_user_by_identifier
from .models import UserSubscription


def latest_subscription_for_user(user):
    return (
        UserSubscription.objects
        .select_related('plan')
        .filter(user=user)
        .order_by('-updated_at')
        .first()
    )


def find_user(identifier):
    return find_user_by_identifier(identifier)
