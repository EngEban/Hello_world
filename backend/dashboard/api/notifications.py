from collections import OrderedDict

from accounts.models import AccountNotification
from accounts.notifications import recipients_for_audience, send_account_notification

from .common import *
from resref.url_safety import is_safe_internal_path


NOTIFICATION_AUDIENCES = {'all', 'admins', 'staff', 'premium', 'free', 'selected'}


def _campaign_history():
    """Return one management record per dashboard-sent notification campaign."""
    campaigns = OrderedDict()
    active_accounts = None
    # Recent deliveries are enough for the management view and keep this
    # endpoint fast even after the dashboard has been used for years.
    recent = AccountNotification.objects.annotate(broadcast_reads=Count('reads')).order_by('-created_at')[:1000]
    for item in recent:
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        campaign_id = metadata.get('campaign_id')
        if not campaign_id:
            continue
        campaign = campaigns.setdefault(campaign_id, {
            'id': campaign_id,
            'title': item.title,
            'message': item.message,
            'type': item.notification_type,
            'action_url': item.action_url,
            'audience': metadata.get('audience', 'system'),
            'created_by': metadata.get('created_by', ''),
            'created_at': item.created_at.isoformat(),
            'recipient_count': 0,
            'read_count': 0,
        })
        if item.user_id is None:
            # Broadcast: one row for everyone, read state kept per user.
            if active_accounts is None:
                active_accounts = User.objects.filter(is_active=True).count()
            campaign['recipient_count'] += active_accounts
            campaign['read_count'] += item.broadcast_reads
            continue
        campaign['recipient_count'] += 1
        campaign['read_count'] += int(item.is_read)
    return list(campaigns.values())[:100]


@require_GET
@api_permission_required('notifications.view')
def notifications_api(request):
    # How many active accounts each audience reaches, so the composer can show
    # the reach before anything is sent.
    audience_counts = {
        audience: recipients_for_audience(audience).distinct().count()
        for audience in sorted(NOTIFICATION_AUDIENCES - {'selected'})
    }
    return JsonResponse({'success': True, 'results': _campaign_history(), 'audience_counts': audience_counts})


@require_POST
@api_permission_required('notifications.create')
def send_notification_api(request):
    data = get_payload(request)
    title = str(data.get('title') or '').strip()
    message = str(data.get('message') or '').strip()
    audience = str(data.get('audience') or 'all').strip().lower()
    notification_type = str(data.get('notification_type') or 'info').strip().lower()
    action_url = str(data.get('action_url') or '').strip()

    if not title:
        return error_response('A notification title is required.')
    if not message:
        return error_response('A notification message is required.')
    if len(title) > 200 or len(message) > 4000:
        return error_response('Notification title or message is too long.')
    if audience not in NOTIFICATION_AUDIENCES:
        return error_response('Choose a valid notification audience.')
    if notification_type not in dict(AccountNotification.TYPES):
        return error_response('Choose a valid notification type.')
    if action_url and not (is_safe_internal_path(action_url) or action_url.startswith('https://')):
        return error_response('Notification links must be an internal path or an HTTPS URL.')
    user_ids = data.get('user_ids') if isinstance(data.get('user_ids'), list) else []
    if audience == 'selected' and not user_ids:
        return error_response('Choose at least one recipient.')

    result = send_account_notification(
        recipients_for_audience(audience, user_ids),
        title,
        message,
        notification_type=notification_type,
        action_url=action_url,
        metadata={
            'source': 'dashboard',
            'audience': audience,
            'created_by': request.user.email or request.user.username,
        },
    )
    log_activity(
        request,
        'notifications',
        'create',
        f'Sent notification to {result["recipient_count"]} account(s): {title}',
        metadata={**result, 'audience': audience},
    )
    return JsonResponse({'success': True, **result})
