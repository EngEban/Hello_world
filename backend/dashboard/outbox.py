"""Newsletter outbox: queued campaigns are sent by ``manage.py process_outbox``.

The web request only snapshots the recipient list (one row per address) and
returns.  A Railway cron service runs the command every few minutes; each run
claims a batch of pending deliveries, sends them over one SMTP connection and
records the result per recipient, so a crash or redeploy never loses or
duplicates a send.
"""

import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import NewsletterCampaign, NewsletterDelivery

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
STALE_CLAIM_AFTER = timedelta(minutes=30)


def newsletter_email_body(message):
    return (
        f'{message}\n\n'
        '--\n'
        'ResRef Newsletter\n'
        'You are receiving this email because this address subscribed to ResRef updates.\n'
        'To unsubscribe or pause messages, reply to this email or contact info@resref.com.'
    )


def queue_campaign(*, subject, message, recipients, idempotency_key, sent_by):
    with transaction.atomic():
        campaign = NewsletterCampaign.objects.create(
            subject=subject,
            message=message,
            status='queued',
            recipient_count=len(recipients),
            failed_count=0,
            idempotency_key=idempotency_key,
            sent_by=sent_by,
        )
        NewsletterDelivery.objects.bulk_create(
            [NewsletterDelivery(campaign=campaign, email=email) for email in recipients],
            batch_size=500,
        )
    return campaign


def delivery_counts(campaign):
    counts = campaign.deliveries.aggregate(
        sent=Count('id', filter=Q(status='sent')),
        failed=Count('id', filter=Q(status='failed')),
        waiting=Count('id', filter=Q(status__in=['pending', 'claimed'])),
    )
    return {key: value or 0 for key, value in counts.items()}


def _release_stale_claims():
    cutoff = timezone.now() - STALE_CLAIM_AFTER
    NewsletterDelivery.objects.filter(status='claimed', claimed_at__lt=cutoff).update(status='pending', claim_token='')


def _claim(campaign, batch_size):
    token = uuid.uuid4().hex
    ids = list(
        campaign.deliveries.filter(status='pending').order_by('id').values_list('id', flat=True)[:batch_size]
    )
    if not ids:
        return []
    # The status filter makes the claim safe if two runs overlap.
    NewsletterDelivery.objects.filter(pk__in=ids, status='pending').update(
        status='claimed', claim_token=token, claimed_at=timezone.now(),
    )
    return list(NewsletterDelivery.objects.filter(claim_token=token, status='claimed').order_by('id'))


def _finish_if_done(campaign):
    counts = delivery_counts(campaign)
    if counts['waiting']:
        return False
    campaign.failed_count = counts['failed']
    if counts['sent'] == 0:
        campaign.status = 'failed'
    elif counts['failed']:
        campaign.status = 'partial'
    else:
        campaign.status = 'sent'
    campaign.sent_at = timezone.now()
    campaign.save(update_fields=['status', 'failed_count', 'sent_at'])
    return True


def _retry_or_fail(delivery, error):
    delivery.claim_token = ''
    delivery.error_message = str(error)[:500]
    delivery.status = 'failed' if delivery.attempts >= MAX_ATTEMPTS else 'pending'


def process_campaign(campaign, batch_size):
    NewsletterCampaign.objects.filter(pk=campaign.pk, status='queued').update(status='sending')
    campaign.refresh_from_db()
    batch = _claim(campaign, batch_size)
    result = {'sent': 0, 'failed': 0, 'retry': 0}
    if not batch:
        _finish_if_done(campaign)
        return result

    fields = ['attempts', 'status', 'claim_token', 'sent_at', 'error_message']
    try:
        connection = get_connection(fail_silently=False)
        connection.open()
    except Exception as exc:
        logger.exception('Newsletter %s: email connection failed', campaign.pk)
        for delivery in batch:
            delivery.attempts += 1
            _retry_or_fail(delivery, exc)
        NewsletterDelivery.objects.bulk_update(batch, fields)
        campaign.error_message = str(exc)[:1000]
        campaign.save(update_fields=['error_message'])
        result['retry'] = sum(delivery.status == 'pending' for delivery in batch)
        result['failed'] = len(batch) - result['retry']
        _finish_if_done(campaign)
        return result

    body = newsletter_email_body(campaign.message)
    try:
        for delivery in batch:
            delivery.attempts += 1
            try:
                accepted = EmailMessage(
                    subject=campaign.subject,
                    body=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[delivery.email],
                    connection=connection,
                ).send()
                if not accepted:
                    raise RuntimeError('The email backend did not accept the message.')
            except Exception as exc:
                _retry_or_fail(delivery, exc)
                result['failed' if delivery.status == 'failed' else 'retry'] += 1
                continue
            delivery.status = 'sent'
            delivery.claim_token = ''
            delivery.sent_at = timezone.now()
            delivery.error_message = ''
            result['sent'] += 1
    finally:
        connection.close()
        NewsletterDelivery.objects.bulk_update(batch, fields)
    _finish_if_done(campaign)
    return result


def process_outbox(batch_size=None):
    """Send the next batch of every queued/sending campaign. Returns totals."""
    totals = {'campaigns': 0, 'sent': 0, 'failed': 0, 'retry': 0}
    # Switched off: queued campaigns stay queued and nothing is emailed.
    if not getattr(settings, 'NEWSLETTER_ENABLED', False):
        return totals
    batch_size = batch_size or getattr(settings, 'NEWSLETTER_BATCH_SIZE', 200)
    _release_stale_claims()
    for campaign in NewsletterCampaign.objects.filter(status__in=['queued', 'sending']).order_by('created_at'):
        result = process_campaign(campaign, batch_size)
        totals['campaigns'] += 1
        for key in ('sent', 'failed', 'retry'):
            totals[key] += result[key]
    return totals
