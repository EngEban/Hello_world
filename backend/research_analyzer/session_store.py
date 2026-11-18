"""Disk-backed Research Analyzer sessions.

Datasets are written with ``DataFrame.to_pickle`` so every dtype (categoricals,
nullable integers, datetimes, mixed object columns) round-trips exactly; the
old JSON round-trip silently changed types.  Pickle can execute code when
loaded, so each file is signed with an HMAC derived from SECRET_KEY and the
signature is verified before anything is unpickled.  Files live under
``ANALYZER_STORAGE_DIR`` (private; never served by the media view).
"""

import hashlib
import hmac
import io
import logging
import os
import uuid
from datetime import timedelta
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import AnalyzerSession

logger = logging.getLogger(__name__)


def _root():
    return Path(settings.ANALYZER_STORAGE_DIR)


def _ttl():
    return timedelta(seconds=settings.ANALYZER_SESSION_TTL_SECONDS)


def _signature(payload):
    key = hashlib.sha256(f'research-analyzer:{settings.SECRET_KEY}'.encode()).digest()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def _write(relative_path, df):
    buffer = io.BytesIO()
    df.to_pickle(buffer)
    payload = buffer.getvalue()
    path = _root() / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_bytes(payload)
    os.replace(temporary, path)  # atomic: readers never see a half-written file
    return _signature(payload)


def _delete_file(relative_path):
    try:
        (_root() / relative_path).unlink(missing_ok=True)
    except OSError:
        logger.warning('Could not delete analyzer file %s', relative_path, exc_info=True)


def _active(queryset):
    return queryset.filter(updated_at__gte=timezone.now() - _ttl())


def owner_for(request):
    """(user, visitor_key) owning analyzer sessions for this request.

    Visitors are identified by a hash of their Django session, which is
    created on first use; signed-in members by their account.
    """
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        return user, ''
    if not request.session.session_key:
        request.session['analyzer_visitor'] = True
        request.session.save()
    digest = hmac.new(settings.SECRET_KEY.encode('utf-8'), f'analyzer-visitor:{request.session.session_key}'.encode('utf-8'), hashlib.sha256)
    return None, digest.hexdigest()


def _owner_filter(user, visitor_key):
    return {'user': user} if user is not None else {'user__isnull': True, 'visitor_key': visitor_key}


def create_session(user, filename, df, variables, visitor_key=''):
    session_id = uuid.uuid4()
    folder = user.pk if user is not None else f'v-{visitor_key[:24]}'
    relative_path = f'{folder}/{session_id}.pkl'
    checksum = _write(relative_path, df)
    session = AnalyzerSession.objects.create(
        id=session_id,
        user=user,
        visitor_key='' if user is not None else visitor_key,
        filename=filename[:255],
        storage_path=relative_path,
        checksum=checksum,
        row_count=len(df),
        column_count=len(df.columns),
        variables=variables,
    )
    enforce_user_cap(user, visitor_key)
    return session


def enforce_user_cap(user, visitor_key=''):
    """Keep only the newest ANALYZER_MAX_SESSIONS_PER_USER sessions."""
    cap = settings.ANALYZER_MAX_SESSIONS_PER_USER
    stale = list(AnalyzerSession.objects.filter(**_owner_filter(user, visitor_key)).order_by('-updated_at')[cap:])
    for session in stale:
        delete_session(session)


def get_session(session_id, user, visitor_key=''):
    """The caller's live session, or None (unknown, expired or someone else's)."""
    try:
        session_uuid = uuid.UUID(str(session_id))
    except (TypeError, ValueError):
        return None
    queryset = _active(AnalyzerSession.objects.filter(pk=session_uuid))
    if user is None:
        if not visitor_key:
            return None
        queryset = queryset.filter(user__isnull=True, visitor_key=visitor_key)
    elif not user.is_superuser:
        queryset = queryset.filter(user=user)
    return queryset.first()


def load_dataframe(session):
    path = _root() / session.storage_path
    try:
        payload = path.read_bytes()
    except OSError:
        return None
    if not hmac.compare_digest(_signature(payload), session.checksum):
        logger.error('Analyzer session %s failed its integrity check; refusing to load it.', session.pk)
        return None
    return pd.read_pickle(io.BytesIO(payload))


def save_dataframe(session, df):
    session.checksum = _write(session.storage_path, df)
    session.row_count = len(df)
    session.column_count = len(df.columns)


def save(session, *fields):
    """Persist the given fields (and refresh the sliding expiry)."""
    session.save(update_fields=[*fields, 'updated_at'])


def delete_session(session):
    path = session.storage_path
    with transaction.atomic():
        session.delete()
    _delete_file(path)


def cleanup_expired(limit=None):
    """Delete expired sessions and orphaned files. Returns the number removed."""
    expired = AnalyzerSession.objects.filter(updated_at__lt=timezone.now() - _ttl()).order_by('updated_at')
    if limit:
        expired = expired[:limit]
    removed = 0
    for session in list(expired):
        delete_session(session)
        removed += 1
    return removed


def cleanup_orphans():
    root = _root()
    if not root.exists():
        return 0
    known = set(AnalyzerSession.objects.values_list('storage_path', flat=True))
    cutoff = timezone.now().timestamp() - _ttl().total_seconds()
    removed = 0
    for path in root.glob('*/*'):
        relative = path.relative_to(root).as_posix()
        if relative not in known and path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    return removed
