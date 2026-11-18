"""Public-site workflows used by the blog API views (T-20)."""

from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone


def newsletter_enabled_required(view):
    """Answer 404 while the newsletter is switched off (settings.NEWSLETTER_ENABLED)."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not getattr(settings, 'NEWSLETTER_ENABLED', False):
            return JsonResponse({'success': False, 'error': 'The newsletter is not available.'}, status=404)
        return view(request, *args, **kwargs)
    return wrapper


NEWSLETTER_CHECK_INBOX = 'Almost done: check your inbox and click the link to confirm your newsletter subscription.'


def send_newsletter_confirmation(subscriber):
    import hashlib
    import logging
    import secrets
    from django.conf import settings
    from django.core.mail import send_mail

    token = secrets.token_urlsafe(32)
    subscriber.confirmation_token_hash = hashlib.sha256(token.encode()).hexdigest()
    subscriber.confirmation_sent_at = timezone.now()
    subscriber.save(update_fields=['confirmation_token_hash', 'confirmation_sent_at'])
    link = f'{settings.FRONTEND_BASE_URL}/newsletter/confirm?token={token}'
    try:
        send_mail(
            'Confirm your ResRef newsletter subscription',
            f'Please confirm that you want to receive the ResRef newsletter:\n\n{link}\n\n'
            'If you did not ask for this, ignore this email and you will not be subscribed.',
            settings.DEFAULT_FROM_EMAIL,
            [subscriber.email],
            fail_silently=False,
        )
    except Exception:
        logging.getLogger(__name__).exception('Could not send newsletter confirmation email.')
