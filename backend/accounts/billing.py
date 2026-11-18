from datetime import datetime, timezone as datetime_timezone

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.utils import timezone

from .entitlements import ensure_default_entitlements, get_profile
from .models import AccountNotification, BillingWebhookEvent, SubscriptionPlan, UserSubscription


ACTIVE_SUBSCRIPTION_STATUSES = {'trialing', 'active', 'manual'}
PREMIUM_PLAN_CODES = {'premium_monthly', 'premium_yearly'}


def get_stripe():
    try:
        import stripe
    except ImportError as exc:
        raise ImproperlyConfigured('Stripe Python SDK is not installed.') from exc
    if not settings.STRIPE_SECRET_KEY:
        raise ImproperlyConfigured('Stripe test secret key is not configured.')
    if not settings.STRIPE_SECRET_KEY.startswith('sk_test_'):
        raise ImproperlyConfigured('Only Stripe test-mode secret keys are allowed in this integration stage.')
    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.api_version = '2026-02-25.clover'
    return stripe


def as_dict(value):
    """Plain nested dicts from a Stripe object.

    Since stripe-python 13, StripeObject is no longer a dict subclass:
    ``dict(obj)`` raises and ``obj.get`` does not exist. ``to_dict()`` is
    recursive, so everything below works on ordinary dicts.
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, 'to_dict'):
        return value.to_dict()
    if hasattr(value, 'to_dict_recursive'):  # stripe-python < 13
        return value.to_dict_recursive()
    raise ValidationError('Unexpected Stripe payload type.')


def timestamp_to_datetime(value):
    if not value:
        return None
    return datetime.fromtimestamp(int(value), tz=datetime_timezone.utc)


def create_notification(user, title, message, notification_type='info', action_url='', metadata=None):
    if not user:
        return None
    return AccountNotification.objects.create(
        user=user,
        title=title[:200],
        message=message,
        notification_type=notification_type,
        action_url=action_url[:500],
        metadata=metadata or {},
    )


def active_subscription_for_user(user):
    return (
        UserSubscription.objects
        .select_related('plan')
        .filter(user=user, provider='stripe', provider_customer_id__gt='')
        .order_by('-updated_at')
        .first()
    )


def sync_profile_from_subscriptions(user):
    profile = get_profile(user)
    active_subscription = (
        UserSubscription.objects
        .select_related('plan')
        .filter(user=user, plan__tier='premium', status__in=ACTIVE_SUBSCRIPTION_STATUSES)
        .filter(models_current_filter())
        .order_by('-current_period_end', '-updated_at')
        .first()
    )
    if active_subscription:
        profile.tier = 'premium'
        profile.plan = active_subscription.plan
        profile.premium_until = active_subscription.current_period_end
    elif not user.is_superuser and not (profile.account_role_id and profile.account_role.can_access_dashboard):
        free_plan = SubscriptionPlan.objects.filter(code='free', is_active=True).first()
        profile.tier = 'free'
        profile.plan = free_plan
        profile.premium_until = None
    profile.save(update_fields=['tier', 'plan', 'premium_until', 'updated_at'])
    return profile


def models_current_filter():
    from django.db.models import Q
    return Q(current_period_end__isnull=True) | Q(current_period_end__gt=timezone.now())


def plan_for_checkout(plan_code):
    ensure_default_entitlements()
    plan = SubscriptionPlan.objects.filter(code=plan_code, tier='premium', is_active=True).first()
    if not plan or plan.code not in PREMIUM_PLAN_CODES:
        raise ValidationError('Choose a valid Premium plan.')
    if not plan.provider_price_id:
        raise ImproperlyConfigured('Stripe Premium price ID is not configured for this plan.')
    if not plan.provider_price_id.startswith('price_'):
        raise ImproperlyConfigured('Stripe Premium price ID must be a Stripe Price ID.')
    return plan


def create_checkout_session(user, plan_code):
    stripe = get_stripe()
    plan = plan_for_checkout(plan_code)
    subscription = active_subscription_for_user(user)
    customer_id = subscription.provider_customer_id if subscription else ''
    if not customer_id:
        customer = stripe.Customer.create(
            email=user.email or None,
            name=user.get_full_name() or user.username,
            metadata={'resref_user_id': str(user.id)},
        )
        customer_id = customer['id']
        UserSubscription.objects.update_or_create(
            user=user,
            provider='stripe',
            provider_customer_id=customer_id,
            provider_subscription_id='',
            defaults={'plan': plan, 'status': 'incomplete'},
        )
    session = stripe.checkout.Session.create(
        mode='subscription',
        customer=customer_id,
        client_reference_id=str(user.id),
        line_items=[{'price': plan.provider_price_id, 'quantity': 1}],
        success_url=settings.STRIPE_BILLING_SUCCESS_URL,
        cancel_url=settings.STRIPE_BILLING_CANCEL_URL,
        metadata={'resref_user_id': str(user.id), 'plan_code': plan.code},
        subscription_data={'metadata': {'resref_user_id': str(user.id), 'plan_code': plan.code}},
    )
    return session


def create_portal_session(user):
    stripe = get_stripe()
    subscription = active_subscription_for_user(user)
    if not subscription or not subscription.provider_customer_id:
        raise ValidationError('No billing customer is connected to this account yet.')
    return stripe.billing_portal.Session.create(
        customer=subscription.provider_customer_id,
        return_url=f'{settings.FRONTEND_BASE_URL}/account',
    )


def cancel_user_subscription(user):
    stripe = get_stripe()
    subscription = (
        UserSubscription.objects
        .select_related('plan')
        .filter(user=user, provider='stripe', provider_subscription_id__gt='', status__in=ACTIVE_SUBSCRIPTION_STATUSES)
        .order_by('-updated_at')
        .first()
    )
    if not subscription:
        raise ValidationError('No active Stripe subscription was found for this account.')
    stripe.Subscription.modify(subscription.provider_subscription_id, cancel_at_period_end=True)
    subscription.cancel_at_period_end = True
    subscription.save(update_fields=['cancel_at_period_end', 'updated_at'])
    create_notification(
        user,
        'Subscription cancellation scheduled',
        'Your Premium subscription is set to cancel at the end of the current billing period.',
        'billing',
        '/account',
    )
    return subscription


def user_from_payload(payload):
    metadata = as_dict(payload.get('metadata') or {})
    user_id = metadata.get('resref_user_id') or payload.get('client_reference_id')
    if user_id:
        return User.objects.filter(pk=user_id).first()
    customer_id = payload.get('customer')
    if customer_id:
        subscription = UserSubscription.objects.select_related('user').filter(provider='stripe', provider_customer_id=customer_id).order_by('-updated_at').first()
        return subscription.user if subscription else None
    return None


def subscription_period(payload):
    """(start, end) of the current billing period.

    From API version 2025-03-31 onwards these live on each subscription item
    instead of the subscription; older payloads keep them at the top level.
    """
    items = as_dict(payload.get('items') or {}).get('data') or []
    first_item = as_dict(items[0]) if items else {}
    start = first_item.get('current_period_start') or payload.get('current_period_start')
    end = first_item.get('current_period_end') or payload.get('current_period_end')
    return timestamp_to_datetime(start), timestamp_to_datetime(end)


def plan_from_subscription_payload(payload):
    metadata = as_dict(payload.get('metadata') or {})
    items = as_dict(payload.get('items') or {})
    data = items.get('data') or []
    price_id = ''
    if data:
        price = as_dict(as_dict(data[0]).get('price') or {})
        price_id = price.get('id') or ''
    if price_id:
        plans = SubscriptionPlan.objects.filter(
            provider='stripe',
            provider_price_id=price_id,
            tier='premium',
            is_active=True,
        )
        if metadata.get('plan_code'):
            plans = plans.filter(code=metadata['plan_code'])
        return plans.first()
    if metadata.get('plan_code'):
        return SubscriptionPlan.objects.filter(
            code=metadata['plan_code'],
            provider='stripe',
            tier='premium',
            is_active=True,
        ).first()
    return None


@transaction.atomic
def sync_subscription_payload(payload, user=None):
    ensure_default_entitlements()
    payload = as_dict(payload)
    user = user or user_from_payload(payload)
    if not user:
        return None
    plan = plan_from_subscription_payload(payload)
    if not plan:
        return None
    subscription_id = payload.get('id') or ''
    customer_id = payload.get('customer') or ''
    status = (payload.get('status') or 'incomplete')[:20]
    period_start, period_end = subscription_period(payload)
    subscription, _ = UserSubscription.objects.update_or_create(
        provider='stripe',
        provider_subscription_id=subscription_id,
        defaults={
            'user': user,
            'plan': plan,
            'status': status,
            'provider_customer_id': customer_id,
            'current_period_start': period_start,
            'current_period_end': period_end,
            'cancel_at_period_end': bool(payload.get('cancel_at_period_end')),
            'metadata': {
                'latest_invoice': payload.get('latest_invoice') or '',
                'price_id': plan.provider_price_id,
            },
        },
    )
    sync_profile_from_subscriptions(user)
    return subscription


def retrieve_and_sync_subscription(subscription_id, user=None):
    if not subscription_id:
        return None
    stripe = get_stripe()
    payload = stripe.Subscription.retrieve(subscription_id)
    return sync_subscription_payload(payload, user=user)


def subscription_id_from_invoice(invoice):
    invoice = as_dict(invoice)
    if invoice.get('subscription'):
        return invoice.get('subscription')
    parent = as_dict(invoice.get('parent') or {})
    subscription_details = as_dict(parent.get('subscription_details') or {})
    return subscription_details.get('subscription') or ''


def process_verified_stripe_event(event):
    """Apply one verified Stripe event exactly once.

    The event row (unique event_id) is created and locked inside the same
    transaction as the changes it causes: concurrent or retried deliveries
    wait for the lock and then see processed_at, and a failure rolls back
    both so Stripe's retry processes it again.
    """
    event = as_dict(event)
    event_id = event.get('id')
    event_type = event.get('type', '')
    if not event_id:
        raise ValidationError('Stripe event is missing an event ID.')
    with transaction.atomic():
        BillingWebhookEvent.objects.get_or_create(
            provider='stripe',
            event_id=event_id,
            defaults={'event_type': event_type, 'metadata': {'type': event_type}},
        )
        record = BillingWebhookEvent.objects.select_for_update().get(event_id=event_id)
        if record.processed_at:
            return {'processed': False, 'duplicate': True}
        _apply_stripe_event(event_type, event)
        record.event_type = event_type
        record.processed_at = timezone.now()
        record.save(update_fields=['event_type', 'processed_at', 'metadata'])
    return {'processed': True, 'duplicate': False}


def _apply_stripe_event(event_type, event):
    obj = as_dict(as_dict(event.get('data') or {}).get('object') or {})
    user = user_from_payload(obj)
    if event_type == 'checkout.session.completed':
        retrieve_and_sync_subscription(obj.get('subscription'), user=user)
        create_notification(user, 'Premium subscription activated', 'Your ResRef Premium subscription is now active.', 'billing', '/account')
    elif event_type in {'customer.subscription.created', 'customer.subscription.updated'}:
        subscription = sync_subscription_payload(obj, user=user)
        if subscription and subscription.status in {'active', 'trialing'}:
            create_notification(subscription.user, 'Subscription updated', 'Your ResRef Premium subscription has been updated.', 'billing', '/account')
    elif event_type == 'customer.subscription.deleted':
        subscription = sync_subscription_payload({**obj, 'status': 'canceled'}, user=user)
        if subscription:
            create_notification(subscription.user, 'Subscription cancelled', 'Your ResRef Premium subscription has been cancelled.', 'billing', '/account')
    elif event_type == 'invoice.payment_succeeded':
        subscription = retrieve_and_sync_subscription(subscription_id_from_invoice(obj), user=user)
        create_notification(subscription.user if subscription else user, 'Payment received', 'Your ResRef Premium payment was received.', 'billing', '/account')
    elif event_type == 'invoice.payment_failed':
        subscription = retrieve_and_sync_subscription(subscription_id_from_invoice(obj), user=user)
        create_notification(subscription.user if subscription else user, 'Payment failed', 'Your Premium payment could not be completed. Please update your billing details.', 'billing', '/account')
