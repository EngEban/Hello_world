import uuid

from django.conf import settings
from django.db import models


class AnalyzerSession(models.Model):
    """One uploaded dataset and the analyses run on it.

    The DataFrame itself lives on disk (see ``session_store``) so sessions are
    shared by every gunicorn worker/thread and survive a worker restart; this
    row holds the metadata and results.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Signed-in owner, or None for a visitor identified by ``visitor_key``
    # (a hash of their browser session; visitors can use the analyzer too).
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name='analyzer_sessions')
    visitor_key = models.CharField(max_length=64, blank=True, db_index=True)
    filename = models.CharField(max_length=255)
    storage_path = models.CharField(max_length=300)
    checksum = models.CharField(max_length=64)
    row_count = models.PositiveIntegerField(default=0)
    column_count = models.PositiveIntegerField(default=0)
    variables = models.JSONField(default=list, blank=True)
    results = models.JSONField(default=list, blank=True)
    auto_results = models.JSONField(default=list, blank=True)
    analysis_plan = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['user', 'updated_at']), models.Index(fields=['updated_at'])]

    def __str__(self):
        return f'{self.filename} ({self.user_id or "visitor"})'
