"""Account workflows used by the API views (T-20): transactional email,
sign-up confirmation and security notices."""

import hashlib
import logging
import os
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .entitlements import get_profile
from .models import EmailVerificationRequest
from .notifications import notify_user

logger = logging.getLogger('accounts.api_views')


def hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


CONFIRMATION_SENT_MESSAGE = (
    'This email address is already registered. If the account is not confirmed yet, we have sent a new '
    'confirmation link. Otherwise, sign in or use "Forgot your password?".'
)
NEUTRAL_CONFIRMATION_MESSAGE = (
    'Check your inbox: if this email can be used for a new ResRef account, we have sent a link to confirm it. '
    'Already have an account? Sign in instead.'
)
EMAIL_CHANGE_TOKEN_HOURS = 24


def _setting_bool(name, default):
    """Read a boolean from settings, falling back to the environment."""
    if hasattr(settings, name):
        return bool(getattr(settings, name))
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


def new_signin_emails_enabled():
    return _setting_bool('ACCOUNT_NEW_SIGNIN_EMAILS', True)


def _html_paragraphs(body, action_url):
    paragraphs = []
    for block in body.split('\n\n'):
        text = ' '.join(line.strip() for line in block.splitlines() if line.strip())
        if text and text != action_url:
            paragraphs.append(text)
    return paragraphs


def send_account_email(address, subject, body, *, action_url='', action_label=''):
    """Send a transactional email (plain text + HTML) through the configured
    Django email backend (Brevo SMTP in production, via DJANGO_EMAIL_*).

    The sender is always DJANGO_DEFAULT_FROM_EMAIL. Failures are logged, never
    shown to users, so responses cannot reveal delivery outcomes.
    """
    if not address:
        return False
    try:
        html = render_to_string('accounts/email/message.html', {
            'subject': subject,
            'paragraphs': _html_paragraphs(body, action_url),
            'action_url': action_url,
            'action_label': action_label or 'Open ResRef',
        })
        timeout = getattr(settings, 'EMAIL_TIMEOUT', None) or 15
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [address],
            fail_silently=False,
            connection=get_connection(timeout=timeout),
            html_message=html,
        )
        return True
    except Exception:
        logger.exception('Could not send "%s" email.', subject)
        return False


def send_confirmation_link(user):
    token = secrets.token_urlsafe(32)
    EmailVerificationRequest.objects.create(
        user=user,
        email=user.email,
        token_hash=hash_token(token),
        expires_at=timezone.now() + timedelta(hours=48),
    )
    confirm_url = f'{settings.FRONTEND_BASE_URL}/account/confirm-email?token={token}'
    return send_account_email(
        user.email,
        'Confirm your ResRef account',
        f'Welcome to ResRef! Confirm your email address to finish creating your account:\n\n{confirm_url}\n\n'
        'The link is valid for 48 hours. If you did not sign up, ignore this email.',
        action_url=confirm_url,
        action_label='Confirm my email',
    )


def mark_email_confirmed(user):
    profile = get_profile(user)
    if profile.email_verified and not profile.email_confirmation_required:
        return profile
    first_confirmation = profile.email_confirmation_required
    profile.email_verified = True
    profile.email_confirmation_required = False
    profile.save(update_fields=['email_verified', 'email_confirmation_required', 'updated_at'])
    if first_confirmation:
        notify_user(
            user,
            'Welcome to ResRef',
            'Your account is ready. Your saved work and platform activity are linked to this account.',
            notification_type='info',
            action_url='/account',
            metadata={'event': 'account_registered'},
        )
    return profile


# --------------------------------------------------------------------------
# Security notices (email + in-app). Never include tokens or passwords.

def _request_summary(request):
    from .security import client_ip

    agent = (request.META.get('HTTP_USER_AGENT', '') or 'Unknown browser').strip()[:160] if request else 'Unknown browser'
    when = timezone.localtime(timezone.now()).strftime('%d %b %Y, %H:%M %Z')
    ip = client_ip(request) if request else 'unknown'
    return f'Time: {when}\nIP address: {ip}\nBrowser: {agent}'


def _security_footer():
    return (
        'If this was not you, reset your password straight away from the sign-in page '
        f'({settings.FRONTEND_BASE_URL}/sign-in) and contact ResRef support.'
    )


def notify_password_changed(user, request=None, *, via_reset=False):
    how = 'with a password-reset link' if via_reset else 'from your account page'
    send_account_email(
        user.email,
        'Your ResRef password was changed',
        f'The password for your ResRef account was changed {how}. '
        'Other devices signed in to your account have been signed out.\n\n'
        f'{_request_summary(request)}\n\n{_security_footer()}',
    )
    notify_user(
        user, 'Password changed', f'Your password was changed {how}. Other devices were signed out.',
        notification_type='security', action_url='/account#account-security', metadata={'event': 'password_changed'},
    )


def notify_new_signin(user, request, method):
    if not new_signin_emails_enabled():
        return
    label = 'Google' if method == 'google' else 'email and password'
    send_account_email(
        user.email,
        'New sign-in to your ResRef account',
        f'Your ResRef account was just signed in on a device we have not seen before, using {label}.\n\n'
        f'{_request_summary(request)}\n\nIf this was you, there is nothing to do. {_security_footer()}',
    )


def notify_google_linked(user, request=None):
    send_account_email(
        user.email,
        'Google sign-in was connected to your ResRef account',
        'You can now sign in to ResRef with your Google account.\n\n'
        f'{_request_summary(request)}\n\n{_security_footer()}',
    )
    notify_user(
        user, 'Google sign-in connected', 'Your account can now be accessed with Google sign-in.',
        notification_type='security', action_url='/account#account-security', metadata={'event': 'google_linked'},
    )


def send_email_change_link(user, new_email):
    token = secrets.token_urlsafe(32)
    EmailVerificationRequest.objects.create(
        user=user,
        email=new_email,
        token_hash=hash_token(token),
        expires_at=timezone.now() + timedelta(hours=EMAIL_CHANGE_TOKEN_HOURS),
    )
    confirm_url = f'{settings.FRONTEND_BASE_URL}/account?email_change={token}'
    return send_account_email(
        new_email,
        'Confirm your new ResRef email address',
        'You asked to use this email address for your ResRef account. Open this link while signed in '
        f'to confirm the change:\n\n{confirm_url}\n\n'
        f'The link is valid for {EMAIL_CHANGE_TOKEN_HOURS} hours. If you did not ask for this, ignore this email.',
        action_url=confirm_url,
        action_label='Confirm new email',
    )


def notify_email_address_taken(new_email):
    send_account_email(
        new_email,
        'Someone tried to use your email for another ResRef account',
        'A signed-in ResRef member asked to move their account to this email address, but it already belongs '
        'to your account, so nothing was changed.\n\nIf you have any concerns, reset your password from the '
        f'sign-in page: {settings.FRONTEND_BASE_URL}/sign-in',
    )


def notify_email_changed(user, old_email, request=None):
    send_account_email(
        old_email,
        'Your ResRef email address was changed',
        f'The email address for your ResRef account was changed from {old_email} to {mask_email(user.email)}. '
        'Sign-in, password resets and account notices now go to the new address.\n\n'
        f'{_request_summary(request)}\n\nIf this was not you, contact ResRef support immediately.',
    )
    notify_user(
        user, 'Email address changed', f'Your account email is now {user.email}.',
        notification_type='security', action_url='/account#account-profile', metadata={'event': 'email_changed'},
    )


def mask_email(address):
    local, _, domain = (address or '').partition('@')
    if not domain:
        return '***'
    return f'{local[:1]}***@{domain}'
