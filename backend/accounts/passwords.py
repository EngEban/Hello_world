"""Password-history helpers.  Only Django password hashes are ever stored."""

from django.conf import settings
from django.contrib.auth.hashers import check_password, is_password_usable
from django.db import transaction

from .models import PasswordHistory


PASSWORD_REUSE_MESSAGE = 'Your new password must be different from your previous password.'


def password_history_limit():
    try:
        return max(1, min(int(getattr(settings, 'PASSWORD_HISTORY_COUNT', 5)), 24))
    except (TypeError, ValueError):
        return 5


def password_was_used(user, raw_password):
    """Check the current password and retained salted hashes without plaintext."""
    password_hashes = [user.password]
    password_hashes.extend(
        PasswordHistory.objects.filter(user=user)
        .order_by('-created_at')
        .values_list('password_hash', flat=True)[:password_history_limit()]
    )
    return any(
        password_hash and is_password_usable(password_hash) and check_password(raw_password, password_hash)
        for password_hash in password_hashes
    )


def set_password_with_history(user, raw_password, *, save=True):
    """Set a password and retain the prior Django hash for reuse prevention.

    ``save=False`` is for callers already managing a wider database transaction;
    the user instance must already be persisted in that case.
    """
    if password_was_used(user, raw_password):
        return False

    previous_hash = user.password
    with transaction.atomic():
        user.set_password(raw_password)
        if save:
            user.save(update_fields=['password'])
        if previous_hash and is_password_usable(previous_hash):
            PasswordHistory.objects.create(user=user, password_hash=previous_hash)
            retained_ids = list(
                PasswordHistory.objects.filter(user=user)
                .order_by('-created_at')
                .values_list('id', flat=True)[password_history_limit():]
            )
            if retained_ids:
                PasswordHistory.objects.filter(id__in=retained_ids).delete()
    return True
