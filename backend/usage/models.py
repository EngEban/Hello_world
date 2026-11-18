"""Usage metering: per-feature policy switches and race-safe counters.

Per-plan allowances for signed-in Free and Premium users live in
``accounts.UsageLimit`` (feature + tier + day/month/lifetime), which the
dashboard already edits. This app adds what that table cannot express:

* ``FeatureUsagePolicy`` - one row per metered feature: the global on/off
  switch for limits, anonymous (per-IP) allowances, admin bypass and how the
  public tool shows the remaining allowance.
* ``UsageCounter`` - one row per subject (user or hashed IP) / feature /
  period window. Increments are single conditional UPDATE statements, so two
  simultaneous requests can never both take the last unit.
"""

from django.db import models


class FeatureUsagePolicy(models.Model):
    DISPLAY_MODES = [
        ('always', 'Always show remaining allowance'),
        ('near_limit', 'Show when the allowance is nearly used'),
        ('never', 'Never show (only the limit-reached message)'),
    ]

    feature_code = models.SlugField(max_length=100, unique=True)
    label = models.CharField(max_length=200, blank=True)
    # Global switch. Off = nobody is blocked by a usage limit for this feature
    # (usage is still counted so the dashboard can show demand).
    limits_enabled = models.BooleanField(default=True)
    # Anonymous visitors are counted per hashed IP only when this is on.
    meter_anonymous = models.BooleanField(default=False)
    anonymous_daily_limit = models.PositiveIntegerField(null=True, blank=True)
    anonymous_monthly_limit = models.PositiveIntegerField(null=True, blank=True)
    # Administrators (superusers, super-admin and admin roles) are never blocked.
    admin_bypass = models.BooleanField(default=True)
    display_mode = models.CharField(max_length=20, choices=DISPLAY_MODES, default='near_limit')
    limit_message = models.CharField(
        max_length=300, blank=True,
        help_text='Optional extra sentence shown when the limit is reached (for example an upgrade hint).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['feature_code']
        verbose_name_plural = 'feature usage policies'

    def __str__(self):
        return f'{self.feature_code} (limits {"on" if self.limits_enabled else "off"})'


class UsageCounter(models.Model):
    PERIODS = [('day', 'Daily'), ('month', 'Monthly'), ('lifetime', 'Lifetime')]

    # 'user:<id>' or 'ip:<keyed hash>'; never a raw IP address.
    subject = models.CharField(max_length=80)
    feature_code = models.SlugField(max_length=100)
    period = models.CharField(max_length=10, choices=PERIODS)
    period_start = models.DateField()
    count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['subject', 'feature_code', 'period', 'period_start'],
                name='usage_counter_unique_window',
            ),
        ]
        indexes = [
            models.Index(fields=['feature_code', 'period', 'period_start']),
        ]

    def __str__(self):
        return f'{self.subject} / {self.feature_code} / {self.period} {self.period_start}: {self.count}'
