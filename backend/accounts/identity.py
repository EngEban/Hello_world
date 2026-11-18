"""Canonical account identifiers used by every account entry point."""

from django.contrib.auth.models import User
from django.db.models import Q


GMAIL_DOMAINS = {'gmail.com', 'googlemail.com'}


def normalize_email(value):
    """Return a stable email identifier without changing non-Gmail addresses.

    Gmail ignores dots in the local part.  Persisting the canonical value prevents
    people from registering multiple ResRef accounts for the same Gmail inbox.
    The function deliberately does not remove plus-addressing because the
    platform policy only treats Gmail dot variants as equivalent.
    """
    if not isinstance(value, str):
        return ''
    email = value.strip().casefold()
    if '@' not in email:
        return email
    local_part, domain = email.rsplit('@', 1)
    if local_part and domain in GMAIL_DOMAINS:
        return f'{local_part.replace(".", "")}@gmail.com'
    return email


def find_user_by_identifier(identifier, queryset=None):
    """Find an account by username or normalized email, including legacy Gmail rows."""
    normalized = normalize_email(identifier)
    if not normalized:
        return None
    queryset = User.objects.all() if queryset is None else queryset
    direct_match = queryset.filter(
        Q(email__iexact=normalized) | Q(username__iexact=normalized)
    ).first()
    if direct_match:
        return direct_match

    # Older deployments may contain a dotted Gmail value.  Keep those users
    # sign-in and reset compatible while preventing any new duplicates.
    if not normalized.endswith('@gmail.com'):
        return None
    candidates = queryset.filter(
        Q(email__iendswith='@gmail.com')
        | Q(email__iendswith='@googlemail.com')
        | Q(username__iendswith='@gmail.com')
        | Q(username__iendswith='@googlemail.com')
    ).only('id', 'email', 'username')
    for candidate in candidates.iterator():
        if normalize_email(candidate.email) == normalized or normalize_email(candidate.username) == normalized:
            return candidate
    return None


def find_user_by_email(email, queryset=None):
    """Find by email only; OAuth identity linking must never match usernames."""
    normalized = normalize_email(email)
    if not normalized:
        return None
    queryset = User.objects.all() if queryset is None else queryset
    direct_match = queryset.filter(email__iexact=normalized).first()
    if direct_match:
        return direct_match
    if not normalized.endswith('@gmail.com'):
        return None
    for candidate in queryset.filter(
        Q(email__iendswith='@gmail.com') | Q(email__iendswith='@googlemail.com')
    ).only('id', 'email').iterator():
        if normalize_email(candidate.email) == normalized:
            return candidate
    return None
