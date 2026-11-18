"""Read-only dashboard queries (T-20)."""

from datetime import timedelta

from django.utils import timezone

from .models import NewsletterSubscriber


def newsletter_summary():
    since = timezone.now() - timedelta(days=30)
    return {
        'total': NewsletterSubscriber.objects.count(),
        'active': NewsletterSubscriber.objects.filter(is_active=True, confirmed_at__isnull=False).count(),
        'paused': NewsletterSubscriber.objects.filter(is_active=False, confirmed_at__isnull=False).count(),
        'pending': NewsletterSubscriber.objects.filter(confirmed_at__isnull=True).count(),
        'recent_30d': NewsletterSubscriber.objects.filter(created_at__gte=since).count(),
    }
