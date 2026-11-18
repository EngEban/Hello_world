import json
import logging
import secrets
from datetime import timedelta
from functools import wraps
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import URLValidator, validate_email
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .billing import as_dict, cancel_user_subscription, create_checkout_session, create_portal_session, get_stripe, process_verified_stripe_event
from .entitlements import (
    ensure_default_entitlements,
    check_feature_access,
    meter_action,
    feature_code_for_tool,
    get_profile,
    serialize_entitlements,
)
from .devices import is_known_device, remember_device
from .identity import find_user_by_email, normalize_email
from .lifecycle import anonymize_account, build_account_export, deletion_blocker
from .models import AccountRole, EmailVerificationRequest, MembershipProfile, SubscriptionPlan, UserToolWorkspace
from .notifications import mark_notification_read, notify_user, read_broadcast_ids, unread_count, visible_notifications
from .passwords import PASSWORD_REUSE_MESSAGE, password_was_used, set_password_with_history
from .profile_fields import clean_country, clean_phone_number, country_name
from .security import client_ip, login_allowed, login_succeeded, rate_limit
from .selectors import latest_subscription_for_user, find_user
from .services import (
    CONFIRMATION_SENT_MESSAGE,
    NEUTRAL_CONFIRMATION_MESSAGE,
    hash_token,
    mark_email_confirmed,
    notify_email_address_taken,
    notify_email_changed,
    notify_google_linked,
    notify_new_signin,
    notify_password_changed,
    send_account_email,
    send_confirmation_link,
    send_email_change_link,
)
from django.contrib.auth.hashers import make_password
from dashboard.models import DashboardActivityLog


logger = logging.getLogger(__name__)
PASSWORD_RESET_RESPONSE = {
    'success': True,
    'message': 'If an account exists for that email address, a reset link has been sent.',
}


ALLOWED_TOOL_WORKSPACES = {
    'reference-generator',
    'journal-finder',
    'research-analyzer',
    'sample-size-calculator',
    'advanced-search',
    'research-opportunities',
}


def payload(request):
    try:
        data = json.loads(request.body.decode('utf-8') or '{}') if request.body else {}
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def text_value(data, key, default='', max_length=None):
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ValidationError(f'{key.replace("_", " ").title()} must be text.')
    value = value.strip()
    if max_length and len(value) > max_length:
        raise ValidationError(f'{key.replace("_", " ").title()} is too long.')
    return value


def password_value(data, key):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value) > 256:
        raise ValidationError('Password must be 256 characters or fewer.')
    return value


def boolean_value(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def error(message, status=400):
    return JsonResponse({'success': False, 'error': message}, status=status)


def send_email_verification(user):
    token = secrets.token_urlsafe(32)
    EmailVerificationRequest.objects.create(
        user=user,
        email=user.email,
        token_hash=hash_token(token),
        expires_at=timezone.now() + timedelta(hours=24),
    )
    verify_url = f'{settings.FRONTEND_BASE_URL}/account?verify={token}'
    send_account_email(
        user.email,
        'Verify your ResRef email address',
        f'Use this secure link to verify your ResRef email address:\n\n{verify_url}\n\nIf you did not request this, ignore this email.',
        action_url=verify_url,
        action_label='Verify my email',
    )


def remember_me_value(data):
    """Default True keeps the long-lived session; False ends it with the browser."""
    value = data.get('remember', True)
    return value if isinstance(value, bool) else boolean_value(value)


def apply_session_lifetime(request, remember):
    if not remember:
        request.session.set_expiry(0)


def signed_in_response(request, user, payload_data, *, method, status=200, notify=True):
    """Build the sign-in response, emailing the owner about unfamiliar devices."""
    known = is_known_device(request, user)
    if notify and not known:
        notify_new_signin(user, request, method)
    response = JsonResponse(payload_data, status=status)
    return remember_device(response, request, user)


def profile_location_values(data, profile=None):
    """Validate optional country/phone input, keeping current values when absent."""
    country = profile.country if profile else ''
    phone = profile.phone_number if profile else ''
    if 'country' in data:
        country = clean_country(data.get('country'))
    if 'phone_number' in data:
        phone = clean_phone_number(data.get('phone_number'), country)
    return country, phone


def log_google_link(request, user, action, message, metadata=None):
    """Record OAuth linking decisions without storing credentials or token data."""
    try:
        DashboardActivityLog.objects.create(
            actor=request.user if request.user.is_authenticated else None,
            action=action,
            module='accounts',
            object_id=str(user.pk),
            object_label=user.email[:255],
            message=message,
            metadata=metadata or {},
            ip_address=client_ip(request),
            user_agent=(request.META.get('HTTP_USER_AGENT', '') or '')[:500],
        )
    except Exception:
        logger.exception('Google linking audit log write failed.')


def verify_google_credential(credential):
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    info = id_token.verify_oauth2_token(credential, google_requests.Request(), settings.GOOGLE_OAUTH_CLIENT_ID)
    # The verifier validates audience and signature; retain this explicit issuer
    # check as a defense-in-depth boundary for future verifier changes.
    if info.get('iss') not in {'accounts.google.com', 'https://accounts.google.com'}:
        raise ValueError('Google sign-in issuer is not trusted.')
    if not info.get('email_verified') or not info.get('email') or not info.get('sub'):
        raise ValueError('Google account email is not verified.')
    return info


def account_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return error('Please sign in to continue.', 401)
        return view(request, *args, **kwargs)
    return wrapped


def workspace_to_dict(workspace, tool_key):
    return {
        'tool_key': tool_key,
        'data': workspace.data if workspace else {},
        'updated_at': workspace.updated_at.isoformat() if workspace else None,
    }


def subscription_to_dict(subscription):
    if not subscription:
        return None
    return {
        'id': subscription.id,
        'plan': subscription.plan.code,
        'plan_label': subscription.plan.label,
        'status': subscription.status,
        'provider': subscription.provider,
        'current_period_end': subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        'cancel_at_period_end': subscription.cancel_at_period_end,
    }


def notification_to_dict(item, broadcast_read=False):
    return {
        'id': item.id,
        'title': item.title,
        'message': item.message,
        'type': item.notification_type,
        'action_url': item.action_url,
        'is_read': item.is_read if item.user_id else broadcast_read,
        'created_at': item.created_at.isoformat(),
        'read_at': item.read_at.isoformat() if item.read_at else None,
    }


def verification_deadline(user, profile):
    """When an unconfirmed member loses access (None = no deadline applies)."""
    grace_days = getattr(settings, 'ACCOUNT_EMAIL_VERIFICATION_GRACE_DAYS', 0)
    if profile.email_verified or not profile.email_confirmation_required or not grace_days:
        return None
    return user.date_joined + timedelta(days=grace_days)


def must_confirm_before_sign_in(user, profile):
    if not settings.ACCOUNT_EMAIL_CONFIRMATION_REQUIRED:
        return False
    if profile.email_verified or not profile.email_confirmation_required:
        return False
    deadline = verification_deadline(user, profile)
    return deadline is None or timezone.now() >= deadline


def account_to_dict(user):
    profile = get_profile(user)
    return {
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'display_name': profile.display_name or user.get_full_name() or user.email,
        'avatar_url': profile.avatar_url,
        'organization': profile.organization,
        'specialization': profile.specialization,
        'marketing_opt_in': profile.marketing_opt_in,
        'country': profile.country,
        'country_name': country_name(profile.country),
        'phone_number': profile.phone_number,
        'has_password': user.has_usable_password(),
        'tier': profile.effective_tier,
        'plan': profile.plan.code if profile.plan_id else profile.effective_tier,
        'role': profile.account_role.code if profile.account_role_id else ('admin' if profile.access_role == 'admin' else profile.effective_tier),
        'access_role': profile.access_role,
        'auth_provider': profile.auth_provider,
        'email_verified': profile.email_verified,
        'email_verify_by': (lambda deadline: deadline.isoformat() if deadline else None)(verification_deadline(user, profile)),
        'premium_until': profile.premium_until.isoformat() if profile.premium_until else None,
        'can_access_dashboard': profile.can_access_dashboard,
        'features': serialize_entitlements(profile),
        'subscription': subscription_to_dict(latest_subscription_for_user(user)),
        'billing_configured': bool(settings.STRIPE_SECRET_KEY and (settings.STRIPE_PREMIUM_MONTHLY_PRICE_ID or settings.STRIPE_PREMIUM_YEARLY_PRICE_ID)),
    }


@ensure_csrf_cookie
@require_GET
def csrf_api(request):
    # The React app is served from a different Render subdomain in staging.
    # Its JavaScript cannot read a cookie scoped to the API subdomain, so return
    # Django's safe masked CSRF token as well as setting the usual cookie.
    return JsonResponse({'success': True, 'csrfToken': get_token(request)})


@require_GET
def config_api(request):
    return JsonResponse({
        'google_enabled': bool(settings.GOOGLE_OAUTH_CLIENT_ID),
        'google_client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'tiers': [
            {'code': 'free', 'label': 'Free', 'description': 'Core ResRef tools and research resources.'},
            {'code': 'premium', 'label': 'Premium', 'description': 'Advanced tools and future premium services.'},
        ],
        'billing': {
            'configured': bool(settings.STRIPE_SECRET_KEY and (settings.STRIPE_PREMIUM_MONTHLY_PRICE_ID or settings.STRIPE_PREMIUM_YEARLY_PRICE_ID)),
            'plans': [
                {'code': 'premium_monthly', 'label': 'Premium Monthly', 'interval': 'month', 'available': bool(settings.STRIPE_PREMIUM_MONTHLY_PRICE_ID)},
                {'code': 'premium_yearly', 'label': 'Premium Yearly', 'interval': 'year', 'available': bool(settings.STRIPE_PREMIUM_YEARLY_PRICE_ID)},
            ],
        },
    })


@require_POST
def confirm_registration_api(request):
    """Public: the emailed link confirms the address and signs the user in."""
    try:
        token = text_value(payload(request), 'token', max_length=200)
    except ValidationError:
        token = ''
    verification = EmailVerificationRequest.objects.select_related('user').filter(
        token_hash=hash_token(token),
        used_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first() if token else None
    if not verification or not verification.user.is_active or verification.email != verification.user.email:
        return error('This confirmation link is invalid or has expired. Request a new one from the sign-in page.', 400)
    user = verification.user
    verification.used_at = timezone.now()
    verification.save(update_fields=['used_at'])
    mark_email_confirmed(user)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    # First sign-in of a brand-new account: remember the device, no alert email.
    return signed_in_response(request, user, {'success': True, 'account': account_to_dict(user)}, method='password', notify=False)


@require_POST
def resend_confirmation_api(request):
    """Public and neutral: the answer never reveals whether the address exists."""
    try:
        email = normalize_email(text_value(payload(request), 'email', max_length=150))
    except ValidationError:
        email = ''
    allowed = rate_limit(request, 'confirmation-resend-email', email, limit=3, window=3600, include_ip=False) and rate_limit(
        request, 'confirmation-resend-ip', limit=10, window=3600
    )
    if allowed and email:
        user = find_user(email)
        if user and user.is_active:
            profile = get_profile(user)
            if profile.email_confirmation_required and not profile.email_verified:
                send_confirmation_link(user)
    return JsonResponse({'success': True, 'message': 'If that address has an unconfirmed account, a new link is on its way.'})


@require_POST
def register_api(request):
    data = payload(request)
    try:
        email = normalize_email(text_value(data, 'email', max_length=150))
        password = password_value(data, 'password')
        full_name = text_value(data, 'full_name', max_length=150)
        validate_email(email)
        # Country and phone are validated before the account lookup as well,
        # so a bad value never reveals anything about the address.
        country, phone_number = profile_location_values(data)
    except ValidationError as exc:
        return error(' '.join(exc.messages))
    if not rate_limit(request, 'register', email, limit=8, window=3600):
        return error('Too many registration attempts. Please try again later.', 429)
    # Password rules are checked before looking the address up, so the answer
    # never depends on whether an account already exists (S-15). A transient
    # user lets the similarity check compare against the name and email.
    try:
        validate_password(password, user=User(username=email, email=email, first_name=full_name))
    except ValidationError as exc:
        return error(' '.join(exc.messages))
    existing = find_user(email)
    if existing:
        # Hash once like the new-account path does, so response time does not
        # reveal that the address is already registered.
        make_password(password)
        # Same answer either way (S-15). A pending account gets a fresh link;
        # the owner of a confirmed account is told about the attempt.
        existing_profile = get_profile(existing)
        if existing.is_active and existing_profile.email_confirmation_required and not existing_profile.email_verified:
            send_confirmation_link(existing)
        elif existing.is_active:
            send_account_email(
                existing.email,
                'Someone tried to create a ResRef account with your email',
                'A new ResRef account was requested with this email address, but you already have one.\n\n'
                f'Sign in: {settings.FRONTEND_BASE_URL}/sign-in\n'
                'Forgot your password? Use "Forgot password" on the sign-in page.\n\n'
                'If this was not you, you can ignore this email.',
            )
    else:
        confirmation_required = settings.ACCOUNT_EMAIL_CONFIRMATION_REQUIRED
        with transaction.atomic():
            user = User.objects.create_user(username=email, email=email, password=password, first_name=full_name)
            profile = get_profile(user)
            profile.display_name = full_name
            profile.marketing_opt_in = boolean_value(data.get('marketing_opt_in', False))
            profile.account_role = AccountRole.objects.filter(code='free', is_active=True).first()
            profile.plan = SubscriptionPlan.objects.filter(code='free', is_active=True).first()
            profile.email_confirmation_required = confirmation_required
            profile.country = country
            profile.phone_number = phone_number
            profile.save(update_fields=['display_name', 'marketing_opt_in', 'account_role', 'plan', 'email_confirmation_required', 'country', 'phone_number', 'updated_at'])
        grace_days = settings.ACCOUNT_EMAIL_VERIFICATION_GRACE_DAYS
        if confirmation_required and grace_days:
            # The member can use ResRef straight away and has a few days to
            # confirm the address (owner decision: access first, verify within
            # the grace period). Signing in here reveals that the address was new.
            send_confirmation_link(user)
        if not confirmation_required or grace_days:
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            notify_user(
                user,
                'Welcome to ResRef',
                'Your account is ready. Your saved work and platform activity are linked to this account.',
                notification_type='info',
                action_url='/account',
                metadata={'event': 'account_registered'},
            )
            return signed_in_response(
                request, user, {
                    'success': True,
                    'verification_required': bool(confirmation_required),
                    'message': (f'Welcome to ResRef! We sent a confirmation link to {user.email}. Please confirm it within {grace_days} days.'
                                if confirmation_required else ''),
                    'account': account_to_dict(user),
                },
                method='password', status=201, notify=False,
            )
        send_confirmation_link(user)
    # No session and no account data. With a grace period, new accounts are
    # signed in above, so this answer only reaches already-registered addresses
    # and can say so; without one it stays neutral (S-15).
    return JsonResponse({
        'success': True,
        'verification_required': True,
        'message': CONFIRMATION_SENT_MESSAGE if settings.ACCOUNT_EMAIL_VERIFICATION_GRACE_DAYS else NEUTRAL_CONFIRMATION_MESSAGE,
    }, status=202)


@require_POST
def login_api(request):
    data = payload(request)
    try:
        identifier = text_value(data, 'email', data.get('username', ''), max_length=150)
        password = password_value(data, 'password')
    except ValidationError:
        return error('Invalid email, username or password.')
    identifier = normalize_email(identifier)
    if not login_allowed(request, 'login', identifier):
        return error('Too many sign-in attempts. Please wait before trying again.', 429)
    user = find_user(identifier)
    authenticated = authenticate(request, username=user.username if user else identifier, password=password)
    if not authenticated or not authenticated.is_active:
        return error('Invalid email, username or password.', 401)
    profile = get_profile(authenticated)
    if must_confirm_before_sign_in(authenticated, profile):
        return JsonResponse({
            'success': False,
            'code': 'email_unconfirmed',
            'error': 'Please confirm your email address first. Use the link we emailed you, or request a new one.',
        }, status=403)
    # login() issues a new session key (prevents session fixation).
    login(request, authenticated)
    apply_session_lifetime(request, remember_me_value(data))
    login_succeeded(request, 'login', identifier)
    return signed_in_response(request, authenticated, {'success': True, 'account': account_to_dict(authenticated)}, method='password')


@require_POST
def google_login_api(request):
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        return error('Google sign-in is not configured yet.', 503)
    if not rate_limit(request, 'google-login', limit=15, window=900):
        return error('Too many sign-in attempts. Please wait before trying again.', 429)
    try:
        credential = text_value(payload(request), 'credential', max_length=10000)
    except ValidationError:
        return error('Google did not return a valid credential.')
    if not credential:
        return error('Google did not return a valid credential.')
    try:
        info = verify_google_credential(credential)
    except ImportError:
        return error('Google sign-in library is not installed. Contact the site administrator.', 503)
    except Exception:
        # OAuth libraries can expose issuer, audience, or token-parser detail.
        # Keep it in server logs and never reflect it to an unauthenticated client.
        logger.exception('Google sign-in credential verification failed.')
        return error('Google sign-in could not be verified.', 400)
    email = normalize_email(info['email'])
    if len(email) > 150:
        return error('This Google account email address is too long.', 400)
    subject = info['sub']
    profile = MembershipProfile.objects.filter(google_subject=subject).select_related('user').first()
    linked_existing_account = False
    created_account = False
    if profile:
        user = profile.user
    else:
        # Google claims must never select an account merely because they match
        # a legacy username; automatic linking is email-only.
        user = find_user_by_email(email)
        if user:
            profile = get_profile(user)
            if profile.google_subject and profile.google_subject != subject:
                log_google_link(
                    request, user, 'system', 'Refused automatic Google re-link attempt',
                    {'reason': 'different_google_subject'},
                )
                return error('This Google account cannot be linked automatically. Sign in with your password first.', 403)
            if profile.email_confirmation_required and not profile.email_verified:
                # Self-registered but never confirmed: whoever chose that password
                # never proved the address. Google just did, so drop the password.
                user.set_unusable_password()
                user.save(update_fields=['password'])
            elif user.has_usable_password() and not profile.email_verified:
                # Linking now would let someone who pre-registered the address
                # keep password access after the real owner signs in (S-03).
                log_google_link(request, user, 'system', 'Refused Google link to unverified password account')
                return error(
                    'An account with this email already exists. Sign in with your password and verify '
                    'your email first, then you can use Google sign-in.',
                    409,
                )
            linked_existing_account = True
        else:
            # Do not reuse the asserted email as a username: a legacy account
            # may own that username without owning the email address.
            user = User.objects.create_user(
                username=f'google-{uuid4().hex}',
                email=email,
                first_name=(info.get('name') or '')[:150],
            )
            user.set_unusable_password()
            user.save(update_fields=['password'])
            created_account = True
    if not user.is_active:
        log_google_link(request, user, 'system', 'Refused Google sign-in for inactive account')
        return error('Google sign-in could not be completed.', 403)
    with transaction.atomic():
        profile = MembershipProfile.objects.select_for_update().get(user=user)
        ensure_default_entitlements()
        profile.google_subject = subject
        profile.auth_provider = 'google'
        profile.email_verified = True
        profile.email_confirmation_required = False
        profile.display_name = (info.get('name', '') or profile.display_name)[:200]
        profile.avatar_url = (info.get('picture', '') or profile.avatar_url)[:1000]
        if not profile.account_role_id:
            profile.account_role = AccountRole.objects.filter(code='free', is_active=True).first()
        if not profile.plan_id:
            profile.plan = SubscriptionPlan.objects.filter(code='free', is_active=True).first()
        profile.save(update_fields=['google_subject', 'auth_provider', 'email_verified', 'email_confirmation_required', 'display_name', 'avatar_url', 'account_role', 'plan', 'updated_at'])
    if linked_existing_account:
        log_google_link(request, user, 'update', 'Linked Google identity to existing account')
        notify_google_linked(user, request)
    if created_account:
        notify_user(
            user,
            'Welcome to ResRef',
            'Your account is ready. Your saved work and platform activity are linked to this account.',
            notification_type='info',
            action_url='/account',
            metadata={'event': 'account_registered'},
        )
    login(request, user)
    return signed_in_response(
        request, user, {'success': True, 'account': account_to_dict(user)},
        method='google', notify=not created_account and not linked_existing_account,
    )


@account_required
@require_POST
def google_link_api(request):
    """Link a Google subject only after proving control of the password account."""
    if not request.user.is_active:
        log_google_link(request, request.user, 'system', 'Refused Google link for inactive account')
        return error('An active account is required to link Google sign-in.', 403)
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        log_google_link(request, request.user, 'system', 'Refused Google link because sign-in is not configured')
        return error('Google sign-in is not configured yet.', 503)
    try:
        data = payload(request)
        credential = text_value(data, 'credential', max_length=10000)
        current_password = password_value(data, 'current_password')
    except ValidationError:
        log_google_link(request, request.user, 'system', 'Refused Google link with invalid request data')
        return error('Google credential and current password are required.')
    if not rate_limit(request, 'google-link', str(request.user.pk), limit=5, window=900):
        return error('Too many attempts. Please wait before trying again.', 429)
    if not credential or not current_password or not request.user.check_password(current_password):
        log_google_link(request, request.user, 'system', 'Refused Google link after failed password re-verification')
        return error('Current password is incorrect.')
    try:
        info = verify_google_credential(credential)
    except ImportError:
        log_google_link(request, request.user, 'system', 'Refused Google link because the verifier is unavailable')
        return error('Google sign-in library is not installed. Contact the site administrator.', 503)
    except Exception:
        logger.exception('Google linking credential verification failed.')
        log_google_link(request, request.user, 'system', 'Refused Google link with unverifiable credential')
        return error('Google sign-in could not be verified.', 400)

    if normalize_email(info['email']) != normalize_email(request.user.email):
        log_google_link(request, request.user, 'system', 'Refused Google link with a different email address')
        return error('The verified Google email must match your account email.', 400)
    subject = info['sub']
    with transaction.atomic():
        owner = MembershipProfile.objects.select_for_update().filter(google_subject=subject).select_related('user').first()
        profile = MembershipProfile.objects.select_for_update().get(user=request.user)
        if owner and owner.user_id != request.user.id:
            log_google_link(request, request.user, 'system', 'Refused Google link already owned by another account')
            return error('This Google identity is already linked to another account.', 400)
        replaced_existing_identity = bool(
            profile.google_subject and profile.google_subject != subject
        )
        # A current authenticated session plus password re-verification proves
        # account control, so intentional re-linking is safe only on this path.
        profile.google_subject = subject
        profile.auth_provider = 'google'
        profile.email_verified = True
        profile.save(update_fields=['google_subject', 'auth_provider', 'email_verified', 'updated_at'])
    log_google_link(
        request,
        request.user,
        'update',
        'Re-linked Google identity through password re-verification'
        if replaced_existing_identity else 'Linked Google identity through password re-verification',
        {'replaced_existing_google_identity': replaced_existing_identity},
    )
    notify_google_linked(request.user, request)
    return JsonResponse({'success': True, 'account': account_to_dict(request.user)})


@require_POST
def logout_api(request):
    logout(request)
    return JsonResponse({'success': True})


@require_GET
def me_api(request):
    return JsonResponse({'account': account_to_dict(request.user) if request.user.is_authenticated else None})


@account_required
@require_http_methods(['GET', 'POST'])
def tool_workspace_api(request, tool_key):
    if tool_key not in ALLOWED_TOOL_WORKSPACES:
        return error('Unknown ResRef tool workspace.', 404)
    feature_code = feature_code_for_tool(tool_key)
    allowed, message = check_feature_access(request.user, feature_code)
    if not allowed:
        return error(message, 403)

    if request.method == 'GET':
        workspace = UserToolWorkspace.objects.filter(user=request.user, tool_key=tool_key).first()
        return JsonResponse({'success': True, **workspace_to_dict(workspace, tool_key)})

    data = payload(request).get('data')
    if not isinstance(data, dict):
        return error('Workspace data must be a JSON object.')
    try:
        serialized = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    except (TypeError, ValueError):
        return error('Workspace data must be valid JSON.')
    max_bytes = getattr(settings, 'USER_TOOL_WORKSPACE_MAX_BYTES', 600 * 1024)
    if len(serialized.encode('utf-8')) > max_bytes:
        return error('Workspace data is too large. Export files locally for very large libraries.', 413)

    # Autosave is not a tool action, so it never uses up quota (T-12).
    workspace, _ = UserToolWorkspace.objects.get_or_create(user=request.user, tool_key=tool_key)
    workspace.data = data
    workspace.save(update_fields=['data', 'updated_at'])
    return JsonResponse({'success': True, **workspace_to_dict(workspace, tool_key)})


# Client-side tools report their metered action here before running it.
CLIENT_METERED_TOOLS = {'journal-finder': ('journal_finder', 'journal_match')}


@account_required
@require_POST
def tool_usage_api(request, tool_key):
    if tool_key not in CLIENT_METERED_TOOLS:
        return error('Unknown ResRef tool.', 404)
    feature_code, action = CLIENT_METERED_TOOLS[tool_key]
    allowed, message = check_feature_access(request.user, feature_code)
    if not allowed:
        return error(message, 403)
    allowed, message = meter_action(request.user, feature_code, action)
    if not allowed:
        return error(message, 429)
    return JsonResponse({'success': True})


def billing_error(exc):
    if isinstance(exc, ImproperlyConfigured):
        # Configuration details belong in the logs, not in API responses.
        logger.error('Billing is not configured: %s', exc)
        return error('Billing is not available right now. Please try again later.', 503)
    if isinstance(exc, ValidationError):
        return error(' '.join(exc.messages))
    return error('Billing request could not be completed.', 400)


@account_required
@require_POST
def billing_checkout_api(request):
    data = payload(request)
    try:
        plan_code = text_value(data, 'plan', 'premium_monthly', max_length=80)
    except ValidationError as exc:
        return error(' '.join(exc.messages))
    if not rate_limit(request, 'billing-checkout', str(request.user.id), limit=10, window=3600):
        return error('Too many billing attempts. Please try again later.', 429)
    try:
        session = create_checkout_session(request.user, plan_code)
    except (ImproperlyConfigured, ValidationError) as exc:
        return billing_error(exc)
    session = as_dict(session)
    return JsonResponse({'success': True, 'checkout_url': session.get('url'), 'session_id': session.get('id')})


@account_required
@require_POST
def billing_portal_api(request):
    if not rate_limit(request, 'billing-portal', str(request.user.id), limit=20, window=3600):
        return error('Too many billing portal requests. Please try again later.', 429)
    try:
        session = create_portal_session(request.user)
    except (ImproperlyConfigured, ValidationError) as exc:
        return billing_error(exc)
    return JsonResponse({'success': True, 'portal_url': as_dict(session).get('url')})


@account_required
@require_POST
def billing_cancel_api(request):
    if not rate_limit(request, 'billing-cancel', str(request.user.id), limit=5, window=3600):
        return error('Too many cancellation attempts. Please try again later.', 429)
    try:
        subscription = cancel_user_subscription(request.user)
    except (ImproperlyConfigured, ValidationError) as exc:
        return billing_error(exc)
    return JsonResponse({'success': True, 'subscription': subscription_to_dict(subscription)})


@account_required
@require_GET
def notifications_api(request):
    items = list(visible_notifications(request.user).order_by('-created_at')[:30])
    read_ids = read_broadcast_ids(request.user, items)
    return JsonResponse({
        'success': True,
        'unread_count': unread_count(request.user),
        'results': [notification_to_dict(item, item.pk in read_ids) for item in items],
    })


@account_required
@require_POST
def notification_read_api(request, pk):
    notification = visible_notifications(request.user).filter(pk=pk).first()
    if not notification:
        return error('Notification was not found.', 404)
    mark_notification_read(request.user, notification)
    return JsonResponse({'success': True, 'notification': notification_to_dict(notification, True)})


@csrf_exempt
@require_POST
def stripe_webhook_api(request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        return error('Stripe webhook secret is not configured.', 503)
    signature = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    try:
        stripe = get_stripe()
        event = stripe.Webhook.construct_event(request.body, signature, settings.STRIPE_WEBHOOK_SECRET)
        result = process_verified_stripe_event(event)
    except ValueError:
        return error('Invalid Stripe webhook payload.', 400)
    except (ImproperlyConfigured, ValidationError) as exc:
        return billing_error(exc)
    except Exception as exc:
        if exc.__class__.__name__ == 'SignatureVerificationError':
            return error('Invalid Stripe webhook signature.', 400)
        raise
    return JsonResponse({'success': True, **result})


@account_required
@require_POST
def update_profile_api(request):
    data = payload(request)
    user = request.user
    profile = get_profile(user)
    try:
        user.first_name = text_value(data, 'first_name', user.first_name, 150)
        user.last_name = text_value(data, 'last_name', user.last_name, 150)
        profile.display_name = text_value(data, 'display_name', profile.display_name, 200)
        profile.organization = text_value(data, 'organization', profile.organization, 250)
        profile.specialization = text_value(data, 'specialization', profile.specialization, 250)
        profile.avatar_url = text_value(data, 'avatar_url', profile.avatar_url, 1000)
        if profile.avatar_url:
            URLValidator(schemes=['https'])(profile.avatar_url)
        profile.country, profile.phone_number = profile_location_values(data, profile)
    except ValidationError as exc:
        return error(' '.join(exc.messages))
    user.save(update_fields=['first_name', 'last_name'])
    profile.marketing_opt_in = boolean_value(data.get('marketing_opt_in', profile.marketing_opt_in))
    profile.save()
    return JsonResponse({'success': True, 'account': account_to_dict(user)})


@account_required
@require_POST
def change_password_api(request):
    data = payload(request)
    user = request.user
    if not user.has_usable_password():
        return error('This account uses Google sign-in. Add a password through the reset-password flow.')
    try:
        current_password = password_value(data, 'current_password')
        new_password = password_value(data, 'new_password')
    except ValidationError as exc:
        return error(' '.join(exc.messages))
    # A stolen session must not be able to guess the current password.
    if not rate_limit(request, 'password-change', str(user.pk), limit=10, window=900, include_ip=False):
        return error('Too many attempts. Please wait before trying again.', 429)
    if not user.check_password(current_password):
        return error('Current password is incorrect.')
    if password_was_used(user, new_password):
        return error(PASSWORD_REUSE_MESSAGE)
    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        return error(' '.join(exc.messages))
    if not set_password_with_history(user, new_password):
        return error(PASSWORD_REUSE_MESSAGE)
    # Keeps this session signed in; every other session's auth hash no longer
    # matches, so other devices are signed out on their next request.
    update_session_auth_hash(request, user)
    notify_password_changed(user, request)
    return JsonResponse({'success': True})


@require_POST
def request_password_reset_api(request):
    try:
        email = normalize_email(text_value(payload(request), 'email', max_length=150))
    except ValidationError:
        email = ''
    email_allowed = rate_limit(
        request,
        'password-reset-email',
        email,
        limit=settings.PASSWORD_RESET_EMAIL_LIMIT,
        window=settings.PASSWORD_RESET_COOLDOWN_SECONDS,
        include_ip=False,
    )
    ip_allowed = rate_limit(
        request,
        'password-reset-ip',
        limit=settings.PASSWORD_RESET_IP_LIMIT,
        window=settings.PASSWORD_RESET_COOLDOWN_SECONDS,
    )
    if not email_allowed or not ip_allowed:
        # Keep rate-limit outcomes indistinguishable from nonexistent accounts.
        return JsonResponse(PASSWORD_RESET_RESPONSE)
    user = find_user(email)
    if user and not user.is_active:
        user = None
    if user:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = f'{settings.FRONTEND_BASE_URL}/account/reset-password?uid={uid}&token={token}'
        send_account_email(
            user.email,
            'Reset your ResRef password',
            f'Use this secure link to reset your ResRef password:\n\n{reset_url}\n\n'
            'The link works once and expires automatically. If you did not request this, ignore this email.',
            action_url=reset_url,
            action_label='Choose a new password',
        )
    # Same status and body for every address and SMTP outcome prevents enumeration.
    return JsonResponse(PASSWORD_RESET_RESPONSE)


@account_required
@require_POST
def request_email_verification_api(request):
    user = request.user
    profile = get_profile(user)
    if profile.email_verified:
        return JsonResponse({'success': True, 'message': 'Your email address is already verified.'})
    if not user.email:
        return error('Please add an email address before requesting verification.')
    if not rate_limit(request, 'email-verification', user.email or user.username, limit=5, window=3600):
        return error('Too many verification requests. Please try again later.', 429)
    send_email_verification(user)
    return JsonResponse({'success': True, 'message': 'A verification link has been sent to your email address.'})


@account_required
@require_POST
def confirm_email_verification_api(request):
    try:
        token = text_value(payload(request), 'token', max_length=200)
    except ValidationError:
        return error('Verification link is invalid or expired.')
    verification = EmailVerificationRequest.objects.filter(
        user=request.user,
        token_hash=hash_token(token),
        used_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    # Email-change links are for the new address and must not verify the old one.
    if not verification or normalize_email(verification.email) != normalize_email(request.user.email):
        return error('Verification link is invalid or expired.')
    verification.used_at = timezone.now()
    verification.save(update_fields=['used_at'])
    mark_email_confirmed(request.user)
    return JsonResponse({'success': True, 'account': account_to_dict(request.user)})


@require_POST
def confirm_password_reset_api(request):
    data = payload(request)
    try:
        user_id = force_str(urlsafe_base64_decode(text_value(data, 'uid', max_length=100)))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist, ValidationError):
        return error('Password-reset link is invalid or expired.')
    try:
        token = text_value(data, 'token', max_length=200)
        new_password = password_value(data, 'new_password')
    except ValidationError as exc:
        return error(' '.join(exc.messages))
    if not rate_limit(request, 'password-reset-confirm', limit=30, window=900):
        return error('Too many attempts. Please wait before trying again.', 429)
    if not default_token_generator.check_token(user, token):
        return error('Password-reset link is invalid or expired.')
    if password_was_used(user, new_password):
        return error(PASSWORD_REUSE_MESSAGE)
    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        return error(' '.join(exc.messages))
    if not set_password_with_history(user, new_password):
        return error(PASSWORD_REUSE_MESSAGE)
    # The reset link was delivered to the address, so it is now confirmed.
    # The new password hash also signs out every existing session.
    mark_email_confirmed(user)
    notify_password_changed(user, request, via_reset=True)
    return JsonResponse({'success': True})


EMAIL_CHANGE_SENT_MESSAGE = (
    'We sent a confirmation link to the new address. Your email changes only after you open it while signed in.'
)


@account_required
@require_POST
def request_email_change_api(request):
    """Start an email change: the new address must prove it receives mail."""
    data = payload(request)
    user = request.user
    try:
        new_email = normalize_email(text_value(data, 'new_email', max_length=150))
        current_password = password_value(data, 'current_password')
        validate_email(new_email)
    except ValidationError:
        return error('Enter a valid new email address.')
    if not user.has_usable_password():
        return error('Set a password first (use "Forgot password" on the sign-in page), then change your email.')
    if not rate_limit(request, 'email-change', str(user.pk), limit=5, window=3600, include_ip=False):
        return error('Too many email change requests. Please try again later.', 429)
    if not user.check_password(current_password):
        return error('Current password is incorrect.')
    if new_email == normalize_email(user.email):
        return error('That is already your account email address.')
    owner = find_user(new_email)
    if owner and owner.pk != user.pk:
        # Same answer as success, so the form cannot be used to look up accounts.
        notify_email_address_taken(new_email)
    else:
        send_email_change_link(user, new_email)
    return JsonResponse({'success': True, 'message': EMAIL_CHANGE_SENT_MESSAGE})


@account_required
@require_POST
def confirm_email_change_api(request):
    try:
        token = text_value(payload(request), 'token', max_length=200)
    except ValidationError:
        token = ''
    user = request.user
    verification = EmailVerificationRequest.objects.filter(
        user=user,
        token_hash=hash_token(token),
        used_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first() if token else None
    invalid = 'This email change link is invalid or has expired. Request a new one from your account page.'
    if not verification or normalize_email(verification.email) == normalize_email(user.email):
        return error(invalid)
    new_email = normalize_email(verification.email)
    with transaction.atomic():
        owner = find_user(new_email)
        if owner and owner.pk != user.pk:
            return error('This email address is already used by another account.', 409)
        old_email = user.email
        fields = ['email']
        if normalize_email(user.username) == normalize_email(old_email) and not User.objects.filter(username__iexact=new_email).exclude(pk=user.pk).exists():
            user.username = new_email
            fields.append('username')
        user.email = new_email
        user.save(update_fields=fields)
        now = timezone.now()
        EmailVerificationRequest.objects.filter(user=user, used_at__isnull=True).update(used_at=now)
        profile = MembershipProfile.objects.select_for_update().get(user=user)
        profile.email_verified = True
        profile.email_confirmation_required = False
        profile.save(update_fields=['email_verified', 'email_confirmation_required', 'updated_at'])
    request.session.cycle_key()
    notify_email_changed(user, old_email, request)
    return JsonResponse({'success': True, 'account': account_to_dict(user)})


@account_required
@require_GET
def export_account_api(request):
    if not rate_limit(request, 'account-export', str(request.user.pk), limit=5, window=3600, include_ip=False):
        return error('Too many export requests. Please try again later.', 429)
    response = JsonResponse(build_account_export(request.user), json_dumps_params={'ensure_ascii': False, 'indent': 2})
    stamp = timezone.now().strftime('%Y%m%d')
    response['Content-Disposition'] = f'attachment; filename="resref-account-{stamp}.json"'
    response['Cache-Control'] = 'no-store'
    return response


DELETE_CONFIRMATION_WORD = 'DELETE'


@account_required
@require_POST
def delete_account_api(request):
    """Self-service deletion: deactivate the login and anonymise personal data."""
    data = payload(request)
    user = request.user
    try:
        confirmation = text_value(data, 'confirm', max_length=20)
        current_password = password_value(data, 'current_password')
    except ValidationError:
        return error('Type DELETE to confirm.')
    if confirmation.upper() != DELETE_CONFIRMATION_WORD:
        return error('Type DELETE to confirm.')
    if not rate_limit(request, 'account-delete', str(user.pk), limit=5, window=900, include_ip=False):
        return error('Too many attempts. Please wait before trying again.', 429)
    if user.has_usable_password() and not user.check_password(current_password):
        return error('Current password is incorrect.')
    blocker = deletion_blocker(user)
    if blocker:
        return error(blocker, 409)
    user_id = user.pk
    old_email = anonymize_account(user)
    try:
        DashboardActivityLog.objects.create(
            actor=None,
            action='delete',
            module='accounts',
            object_id=str(user_id),
            object_label=f'Deleted member #{user_id}',
            message='Member deleted their account (deactivated and anonymised).',
            metadata={'event': 'account_self_deleted'},
            ip_address=None,
            user_agent='',
        )
    except Exception:
        logger.exception('Account deletion audit log write failed.')
    if old_email:
        send_account_email(
            old_email,
            'Your ResRef account was deleted',
            'Your ResRef account has been deleted as you asked. Your personal details were removed and you can no '
            'longer sign in with it. Records we must keep (such as billing history) no longer identify you.\n\n'
            'If you did not do this, contact ResRef support immediately.',
        )
    logout(request)
    return JsonResponse({'success': True, 'message': 'Your account was deleted and you have been signed out.'})
