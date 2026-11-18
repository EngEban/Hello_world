"""Dashboard workflows shared by the API modules (T-20)."""

from urllib.parse import quote

from django.core.validators import validate_email

from accounts.notifications import broadcast_notification

from .models import NewsletterSubscriber


def _notify_opportunity_published(item, actor):
    """One broadcast row per opportunity (not one per account), deduplicated so
    re-publishing never notifies twice."""
    broadcast_notification(
        'New research opportunity',
        f'{item.title} is now available in Research Opportunities.',
        dedupe_key=f'opportunity-published:{item.pk}',
        notification_type='opportunity',
        action_url=f'/opportunities?search={quote(item.title)}',
        metadata={
            'source': 'system',
            'event': 'opportunity_published',
            'opportunity_id': item.pk,
            'created_by': actor.email or actor.username,
            'audience': 'all',
        },
    )


def active_newsletter_recipients():
    recipients = list(
        NewsletterSubscriber.objects.filter(is_active=True, confirmed_at__isnull=False)
        .order_by('email')
        .values_list('email', flat=True)
        .distinct()
    )
    for email in recipients:
        validate_email(email)
    return recipients
