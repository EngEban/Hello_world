"""Seed launch usage policies and carry existing usage into the new counters.

Additive only: creates missing rows, never updates or deletes anything.
Launch defaults keep the existing generous Free allowances (managed in the
dashboard under Premium Controls > Usage limits) and leave anonymous use
unmetered. Restrictive limits are switched on later from the dashboard.
"""

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import migrations
from django.db.models import Sum
from django.utils import timezone


LAUNCH_POLICIES = [
    ('reference_generator', 'Reference Generator'),
    ('journal_finder', 'Journal Finder'),
    ('sample_size_calculator', 'Sample Size Calculator'),
    ('research_analyzer', 'Research Analyzer'),
]


def _tz():
    try:
        return ZoneInfo(os.getenv('RESREF_USAGE_TIMEZONE', '') or 'UTC')
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo('UTC')


def seed(apps, schema_editor):
    FeatureUsagePolicy = apps.get_model('usage', 'FeatureUsagePolicy')
    UsageCounter = apps.get_model('usage', 'UsageCounter')
    UsageRecord = apps.get_model('accounts', 'UsageRecord')

    for code, label in LAUNCH_POLICIES:
        FeatureUsagePolicy.objects.get_or_create(
            feature_code=code,
            defaults={
                'label': label,
                'limits_enabled': True,
                'meter_anonymous': False,
                'admin_bypass': True,
                'display_mode': 'near_limit',
            },
        )

    tz = _tz()
    today = timezone.localtime(timezone.now(), tz).date()
    month_start = today.replace(day=1)
    windows = [
        ('day', today, datetime.combine(today, datetime.min.time(), tzinfo=tz)),
        ('month', month_start, datetime.combine(month_start, datetime.min.time(), tzinfo=tz)),
        ('lifetime', date(2000, 1, 1), None),
    ]
    counters = []
    for period, start, since in windows:
        records = UsageRecord.objects.all()
        if since is not None:
            records = records.filter(created_at__gte=since)
        totals = records.values('user_id', 'feature_code').annotate(total=Sum('amount'))
        for row in totals:
            if row['total']:
                counters.append(UsageCounter(
                    subject=f"user:{row['user_id']}",
                    feature_code=row['feature_code'],
                    period=period,
                    period_start=start,
                    count=row['total'],
                ))
    UsageCounter.objects.bulk_create(counters, ignore_conflicts=True, batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ('usage', '0001_initial'),
        ('accounts', '0012_email_confirmation_required'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
