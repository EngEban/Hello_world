from django.conf import settings
from django.utils.html import strip_tags

from accounts.security import rate_limit

from .common import *
from blog.services import newsletter_enabled_required

from ..selectors import newsletter_summary
from ..services import active_newsletter_recipients
from ..outbox import delivery_counts, process_outbox, queue_campaign


NEWSLETTER_CONFIRM_PHRASE = 'SEND NEWSLETTER'


def newsletter_to_dict(item):
    return {
        'id': item.id,
        'email': item.email,
        'is_active': item.is_active,
        'confirmed': item.confirmed_at is not None,
        'confirmed_at': item.confirmed_at.isoformat() if item.confirmed_at else None,
        'created_at': item.created_at.isoformat(),
    }


def _progress(item):
    if item.status in {'queued', 'sending'}:
        counts = delivery_counts(item)
        return {'sent_count': counts['sent'], 'pending_count': counts['waiting']}
    return {'sent_count': max(item.recipient_count - item.failed_count, 0), 'pending_count': 0}


def newsletter_campaign_to_dict(item):
    sender = ''
    if item.sent_by_id:
        sender = item.sent_by.get_full_name() or item.sent_by.email or item.sent_by.username
    return {
        'id': item.id,
        'subject': item.subject,
        'message': item.message,
        'status': item.status,
        'recipient_count': item.recipient_count,
        'failed_count': item.failed_count,
        **_progress(item),
        'error_message': item.error_message,
        'sent_by': sender,
        'created_at': item.created_at.isoformat(),
        'sent_at': item.sent_at.isoformat() if item.sent_at else None,
    }


def clean_newsletter_subject(value):
    subject = ' '.join(str(value or '').strip().split())
    if len(subject) < 5:
        raise ValidationError('Subject must be at least 5 characters.')
    if len(subject) > 160:
        raise ValidationError('Subject must be 160 characters or fewer.')
    if '\r' in subject or '\n' in subject:
        raise ValidationError('Subject cannot contain line breaks.')
    return subject


def clean_newsletter_message(value):
    message = strip_tags(str(value or '')).replace('\r\n', '\n').replace('\r', '\n').strip()
    if len(message) < 20:
        raise ValidationError('Message must be at least 20 characters.')
    if len(message) > 6000:
        raise ValidationError('Message must be 6000 characters or fewer.')
    return message


def apply_join_team_payload(item, data):
    def clean_string(key, fallback=''):
        value = data.get(key, fallback)
        return str(value or '').strip()

    item.title = clean_string('title', item.title)
    item.slug = clean_string('slug', item.slug)
    item.description = clean_string('description', item.description)
    item.icon_key = data.get('icon_key', item.icon_key)
    item.action_label = clean_string('action_label', item.action_label)
    item.action_url = clean_string('action_url', item.action_url)
    item.status = data.get('status', item.status)
    item.sort_order = parse_int(data.get('sort_order'), item.sort_order) or 0
    item.seo_title = clean_string('seo_title', item.seo_title)
    item.seo_description = clean_string('seo_description', item.seo_description)
    return item

def status_counts(queryset, choices):
    """{'all': n, '<status>': n, ...} for list tabs, independent of the current filter."""
    rows = {row['status']: row['total'] for row in queryset.order_by().values('status').annotate(total=Count('id'))}
    counts = {value: rows.get(value, 0) for value, _label in choices}
    counts['all'] = sum(rows.values())
    return counts


@require_GET
@api_permission_required('forms.view')
def contacts_api(request):
    qs = ContactSubmission.objects.all()
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    qs = apply_common_filters(qs, request, ['name', 'email', 'message', 'specialization', 'company'], ['status', 'created_at'], '-created_at')
    payload = paginate(qs, request, contact_to_dict)
    payload['counts'] = status_counts(ContactSubmission.objects.all(), ContactSubmission.STATUS)
    payload['statuses'] = [{'value': value, 'label': label} for value, label in ContactSubmission.STATUS]
    return JsonResponse(payload)

@require_POST
@api_permission_required('forms.edit')
def update_contact_api(request, pk):
    contact = get_object_or_404(ContactSubmission, pk=pk)
    status = get_payload(request).get('status', contact.status)
    if status not in dict(ContactSubmission.STATUS):
        return error_response('Unknown contact status.')
    contact.status = status
    contact.save(update_fields=['status'])
    log_activity(request, 'forms', 'status', f'Updated contact status: {contact.name}', contact, {'status': status})
    return JsonResponse({'success': True, 'contact': contact_to_dict(contact)})

@require_GET
@api_permission_required('forms.view')
def applications_api(request):
    qs = JobApplication.objects.all()
    if request.GET.get('team'):
        qs = qs.filter(team=request.GET.get('team'))
    if request.GET.get('status'):
        qs = qs.filter(status=request.GET.get('status'))
    qs = apply_common_filters(qs, request, ['full_name', 'email', 'motivation', 'experience'], ['status', 'team', 'created_at'], '-created_at')
    payload = paginate(qs, request, application_to_dict)
    payload['counts'] = status_counts(JobApplication.objects.all(), JobApplication.STATUS)
    payload['teams'] = [{'value': value, 'label': label} for value, label in JobApplication.TEAMS]
    return JsonResponse(payload)

@require_GET
@api_permission_required('forms.view')
def application_cv_api(request, pk):
    """CVs are personal data: only dashboard users with forms.read get them,
    always as a download (never rendered inline)."""
    from django.http import FileResponse, Http404

    app = get_object_or_404(JobApplication, pk=pk)
    if not app.cv_file:
        raise Http404('No CV uploaded.')
    extension = app.cv_file.name.rsplit('.', 1)[-1].lower()
    safe_name = slugify(app.full_name) or 'applicant'
    log_activity(request, 'forms', 'export', f'Downloaded CV: {app.full_name}', app)
    response = FileResponse(app.cv_file.open('rb'), as_attachment=True, filename=f'cv-{safe_name}.{extension}')
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response


@require_POST
@api_permission_required('forms.edit')
def update_application_api(request, pk):
    app = get_object_or_404(JobApplication, pk=pk)
    data = get_payload(request)
    status = data.get('status', app.status)
    if status not in dict(JobApplication.STATUS):
        return error_response('Unknown application status.')
    app.status = status
    app.notes = text_field(data, 'notes', app.notes)
    app.save(update_fields=['status', 'notes'])
    log_activity(request, 'forms', 'status', f'Updated application: {app.full_name}', app, {'status': status})
    return JsonResponse({'success': True, 'application': application_to_dict(app)})


@require_GET
@api_permission_required('forms.view')
def join_team_entries_api(request):
    qs = JoinTeamEntry.objects.all()
    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status=status)
    qs = apply_common_filters(qs, request, ['title', 'description', 'action_url', 'seo_title'], ['status', 'sort_order', 'updated_at', 'title'], 'sort_order')
    return JsonResponse(paginate(qs, request, join_team_entry_to_dict, per_page=50))


@require_POST
@api_save_permission_required('forms')
def save_join_team_entry_api(request, pk=None):
    item = get_object_or_404(JoinTeamEntry, pk=pk) if pk else JoinTeamEntry()
    data = get_payload(request)
    item = apply_join_team_payload(item, data)
    try:
        item.save()
    except ValidationError as exc:
        if hasattr(exc, 'message_dict'):
            message = ' '.join(message for messages in exc.message_dict.values() for message in messages)
        else:
            message = ' '.join(exc.messages)
        return error_response(message)
    log_activity(request, 'forms', 'update' if pk else 'create', f'Saved join team card: {item.title}', item)
    return JsonResponse({'success': True, 'entry': join_team_entry_to_dict(item)})


@require_POST
@api_permission_required('forms.delete')
def delete_join_team_entry_api(request, pk):
    item = get_object_or_404(JoinTeamEntry, pk=pk)
    label = item.title
    item.delete()
    log_activity(request, 'forms', 'delete', f'Deleted join team card: {label}', metadata={'title': label})
    return JsonResponse({'success': True})

@require_GET
@api_permission_required('team.view')
def team_api(request):
    users = User.objects.select_related('membership_profile', 'team_member').all().order_by('-date_joined')
    return JsonResponse({'results': [team_member_to_dict(user) for user in users]})

@newsletter_enabled_required
@require_GET
@api_permission_required('forms.read')
def newsletter_api(request):
    qs = NewsletterSubscriber.objects.all()
    status = request.GET.get('status', '').strip()
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'paused':
        qs = qs.filter(is_active=False)
    elif status == 'pending':
        qs = qs.filter(confirmed_at__isnull=True)
    elif status == 'confirmed':
        qs = qs.filter(is_active=True, confirmed_at__isnull=False)
    qs = apply_common_filters(qs, request, ['email'], ['email', 'is_active', 'created_at'], '-created_at')
    payload = paginate(qs, request, newsletter_to_dict, 30)
    payload['summary'] = newsletter_summary()
    payload['campaigns'] = [
        newsletter_campaign_to_dict(item)
        for item in NewsletterCampaign.objects.select_related('sent_by').order_by('-created_at')[:10]
    ]
    payload['send_limits'] = {
        'max_recipients': settings.NEWSLETTER_MAX_RECIPIENTS_PER_SEND,
        'confirm_phrase': NEWSLETTER_CONFIRM_PHRASE,
    }
    if parse_boolean(request.GET.get('include_recipients'), False):
        # Exactly the list a broadcast would go to right now (active + confirmed),
        # so the composer can show who will receive it before sending.
        recipients = list(
            NewsletterSubscriber.objects.filter(is_active=True, confirmed_at__isnull=False)
            .order_by('email').values_list('email', flat=True).distinct()
        )
        payload['recipients'] = recipients[:settings.NEWSLETTER_MAX_RECIPIENTS_PER_SEND]
        payload['recipient_total'] = len(recipients)
    return JsonResponse(payload)

@newsletter_enabled_required
@require_POST
@api_permission_required('forms.write')
def update_newsletter_api(request, pk):
    subscriber = get_object_or_404(NewsletterSubscriber, pk=pk)
    subscriber.is_active = parse_boolean(get_payload(request).get('is_active'), subscriber.is_active)
    subscriber.save(update_fields=['is_active'])
    log_activity(request, 'forms', 'status', f'Updated newsletter subscriber: {subscriber.email}', subscriber, {'is_active': subscriber.is_active})
    return JsonResponse({'success': True, 'subscriber': newsletter_to_dict(subscriber), 'summary': newsletter_summary()})


@newsletter_enabled_required
@require_POST
@api_permission_required('forms.write')
def delete_newsletter_api(request, pk):
    subscriber = get_object_or_404(NewsletterSubscriber, pk=pk)
    email = subscriber.email
    subscriber.delete()
    log_activity(request, 'forms', 'delete', f'Deleted newsletter subscriber: {email}', metadata={'email': email})
    return JsonResponse({'success': True, 'summary': newsletter_summary()})


@newsletter_enabled_required
@require_POST
@api_permission_required('forms.write')
def send_newsletter_api(request):
    if get_dashboard_role(request.user) != 'admin':
        return error_response('Only dashboard admins can send newsletter broadcasts.', 403)
    if not rate_limit(request, 'newsletter-send-user', str(request.user.id), limit=3, window=3600):
        return error_response('Too many newsletter send attempts. Please wait before trying again.', 429)
    if not rate_limit(request, 'newsletter-send-ip', limit=8, window=3600):
        return error_response('Too many newsletter send attempts from this location. Please try again later.', 429)

    data = get_payload(request)
    idempotency_key = str(data.get('idempotency_key') or '').strip()[:80]
    if not idempotency_key:
        return error_response('A send request key is required. Refresh the page and try again.')
    existing = NewsletterCampaign.objects.filter(idempotency_key=idempotency_key).select_related('sent_by').first()
    if existing:
        return JsonResponse({
            'success': True,
            'duplicate': True,
            'message': 'This newsletter send request was already processed.',
            'campaign': newsletter_campaign_to_dict(existing),
            'summary': newsletter_summary(),
        })

    if str(data.get('confirm_phrase') or '').strip() != NEWSLETTER_CONFIRM_PHRASE:
        return error_response(f'Type {NEWSLETTER_CONFIRM_PHRASE} to confirm this one-time send.')

    try:
        subject = clean_newsletter_subject(data.get('subject'))
        message = clean_newsletter_message(data.get('message'))
        recipients = active_newsletter_recipients()
    except ValidationError as exc:
        return error_response(' '.join(exc.messages))

    if not recipients:
        return error_response('There are no active newsletter subscribers to email.')
    if len(recipients) > settings.NEWSLETTER_MAX_RECIPIENTS_PER_SEND:
        return error_response(
            f'This send has {len(recipients)} recipients, above the configured limit of '
            f'{settings.NEWSLETTER_MAX_RECIPIENTS_PER_SEND}. Use a dedicated email provider for larger campaigns.'
        )

    campaign = queue_campaign(
        subject=subject,
        message=message,
        recipients=recipients,
        idempotency_key=idempotency_key,
        sent_by=request.user,
    )
    log_activity(
        request,
        'newsletter',
        'system',
        f'Queued newsletter campaign: {subject}',
        campaign,
        {'recipient_count': len(recipients)},
    )
    if settings.NEWSLETTER_SEND_INLINE:
        # Development convenience; production sends from the cron service.
        process_outbox()
        campaign.refresh_from_db()
    plural = 's' if len(recipients) != 1 else ''
    message_text = (
        f'Newsletter queued for {len(recipients)} active subscriber{plural}. '
        'It is sent in the background within a few minutes.'
        if campaign.status in {'queued', 'sending'}
        else f'Newsletter processed for {len(recipients)} active subscriber{plural}.'
    )
    return JsonResponse({
        'success': True,
        'message': message_text,
        'campaign': newsletter_campaign_to_dict(campaign),
        'summary': newsletter_summary(),
    })

@require_GET
@api_permission_required('forms.view')
def forms_overview_api(request):
    """One inbox across contacts, team applications and service requests.

    Filters (type, status, q) run in the database before the per-source cap,
    so searching finds older submissions too. Each row carries enough detail
    for a reading pane (message, extra fields, notes, CV link)."""
    source = request.GET.get('type', '').strip()
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    limit = 30

    def search(qs, fields):
        if status:
            qs = qs.filter(status=status)
        if q:
            query = Q()
            for field in fields:
                query |= Q(**{f'{field}__icontains': q})
            qs = qs.filter(query)
        return qs[:limit]

    results = []
    if source in ('', 'contact'):
        for item in search(ContactSubmission.objects.all(), ['name', 'email', 'message', 'company']):
            results.append({
                'id': f'contact-{item.id}', 'record_id': item.id, 'type': 'contact', 'title': item.name, 'email': item.email,
                'status': item.status, 'created_at': item.created_at.isoformat(), 'route': '/dashboard/contacts',
                'excerpt': item.message[:180], 'message': item.message, 'phone': item.whatsapp,
                'details': {'Company': item.company, 'Specialization': item.specialization, 'WhatsApp': item.whatsapp},
            })
    if source in ('', 'team_application'):
        teams = dict(JobApplication.TEAMS)
        for item in search(JobApplication.objects.all(), ['full_name', 'email', 'motivation', 'experience']):
            results.append({
                'id': f'application-{item.id}', 'record_id': item.id, 'type': 'team_application', 'title': item.full_name, 'email': item.email,
                'status': item.status, 'created_at': item.created_at.isoformat(), 'route': '/dashboard/applications',
                'excerpt': (item.motivation or item.experience)[:180], 'message': item.motivation, 'phone': item.whatsapp,
                'details': {'Team': teams.get(item.team, item.team), 'WhatsApp': item.whatsapp, 'Experience': item.experience, 'Portfolio': item.portfolio},
                'notes': item.notes, 'has_cv': bool(item.cv_file),
                'cv_url': f'/api/dashboard/applications/{item.id}/cv/' if item.cv_file else '',
            })
    if source in ('', 'service_request'):
        for item in search(ServiceRequest.objects.select_related('service'), ['subject', 'requester_name', 'requester_email', 'message']):
            results.append({
                'id': f'service-{item.id}', 'record_id': item.id, 'type': 'service_request', 'title': item.subject, 'email': item.requester_email,
                'status': item.status, 'created_at': item.created_at.isoformat(), 'route': '/dashboard/services?tab=requests',
                'excerpt': item.message[:180], 'message': item.message, 'phone': '',
                'details': {'Requester': item.requester_name, 'Organization': item.organization, 'Service': item.service.title if item.service else 'General', 'Priority': item.priority},
                'notes': item.internal_notes, 'priority': item.priority,
            })
    results.sort(key=lambda item: item['created_at'], reverse=True)
    return JsonResponse({'results': results[:50], 'summary': {
        'contacts': ContactSubmission.objects.count(),
        'team_applications': JobApplication.objects.count(),
        'service_requests': ServiceRequest.objects.count(),
        'newsletter_subscribers': NewsletterSubscriber.objects.count(),
        'new_contacts': ContactSubmission.objects.filter(status='new').count(),
        'new_team_applications': JobApplication.objects.filter(status='new').count(),
        'new_service_requests': ServiceRequest.objects.filter(status='new').count(),
    }, 'statuses': {
        'contact': [value for value, _label in ContactSubmission.STATUS],
        'team_application': [value for value, _label in JobApplication.STATUS],
        'service_request': [value for value, _label in ServiceRequest.STATUS],
    }})
