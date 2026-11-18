from .common import *
from ..services import _notify_opportunity_published


def _text(data, key, fallback=''):
    # Custom-field helper: values are always coerced to text.
    return str(data.get(key, fallback) or '').strip()


CLOSING_SOON_DAYS = 14


def _status_counts(queryset, choices):
    """{'all': n, '<status>': n, ...} for list tabs and board columns."""
    rows = {row['status']: row['total'] for row in queryset.order_by().values('status').annotate(total=Count('id'))}
    counts = {value: rows.get(value, 0) for value, _label in choices}
    counts['all'] = sum(rows.values())
    return counts


def _assignees():
    """Staff accounts that service requests can be assigned to."""
    users = User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(is_superuser=True)).order_by('first_name', 'username')[:100]
    return [{'id': user.id, 'name': user.get_full_name() or user.email or user.username} for user in users]


CUSTOM_FIELD_TYPES = {'text', 'textarea', 'select', 'checkbox', 'email', 'url', 'date'}


def normalize_opportunity_custom_fields(value):
    """Store a small, safe set of administrator-defined opportunity details."""
    if not isinstance(value, list):
        return []

    normalized = []
    for field in value[:20]:
        if not isinstance(field, dict):
            continue
        label = _text(field, 'label')[:80]
        if not label:
            continue
        field_type = _text(field, 'type', 'text')
        if field_type not in CUSTOM_FIELD_TYPES:
            field_type = 'text'
        options = field.get('options', [])
        if not isinstance(options, list):
            options = []
        normalized.append({
            'label': label,
            'type': field_type,
            'value': _text(field, 'value')[:2000],
            'help_text': _text(field, 'help_text')[:240],
            'options': [_text({'option': option}, 'option')[:80] for option in options[:20] if _text({'option': option}, 'option')],
            'is_public': parse_boolean(field.get('is_public'), True),
            'is_required': parse_boolean(field.get('is_required'), False),
        })
    return normalized


@require_GET
@api_permission_required('opportunities.view')
def opportunities_api(request):
    qs = ResearchOpportunity.objects.select_related('assigned_to', 'specialty')
    if request.GET.get('status'):
        qs = qs.filter(status=request.GET.get('status'))
    if request.GET.get('category'):
        category = request.GET.get('category')
        qs = qs.filter(Q(category__iexact=category) | Q(specialty__slug=category) | Q(specialty__name__iexact=category))
    if request.GET.get('specialty'):
        qs = qs.filter(specialty_id=parse_int(request.GET.get('specialty')))
    if request.GET.get('type'):
        qs = qs.filter(opportunity_type=request.GET.get('type'))
    if request.GET.get('location'):
        qs = qs.filter(location__icontains=request.GET.get('location'))
    today = timezone.localdate()
    soon = today + timedelta(days=CLOSING_SOON_DAYS)
    deadline = request.GET.get('deadline', '').strip()
    if deadline == 'closing_soon':
        qs = qs.filter(status='published', deadline__gte=today, deadline__lte=soon)
    elif deadline == 'expired':
        qs = qs.filter(status='published', deadline__lt=today)
    elif deadline == 'featured':
        qs = qs.filter(is_featured=True)
    qs = apply_common_filters(qs, request, ['title', 'summary', 'description', 'category', 'organization', 'location'], ['title', 'status', 'deadline', 'updated_at', 'priority', 'opportunity_type'], '-updated_at')
    payload = paginate(qs, request, opportunity_to_dict, 25)
    every = ResearchOpportunity.objects.all()
    payload['counts'] = _status_counts(every, ResearchOpportunity.STATUS)
    payload['deadline_counts'] = {
        'closing_soon': every.filter(status='published', deadline__gte=today, deadline__lte=soon).count(),
        'expired': every.filter(status='published', deadline__lt=today).count(),
        'featured': every.filter(is_featured=True).count(),
    }
    payload['closing_soon_days'] = CLOSING_SOON_DAYS
    return JsonResponse(payload)

@require_POST
@api_save_permission_required('opportunities')
def save_opportunity_api(request, pk=None):
    data = get_payload(request)
    item = get_object_or_404(ResearchOpportunity, pk=pk) if pk else ResearchOpportunity(created_by=request.user)
    previous_status = item.status if item.pk else None
    item.title = text_field(data, 'title', item.title)
    item.slug = text_field(data, 'slug', item.slug) or item.slug
    item.organization = text_field(data, 'organization', item.organization)
    item.opportunity_type = data.get('opportunity_type') or data.get('type') or item.opportunity_type
    if 'specialty' in data:
        specialty_id = id_field(data.get('specialty'), 'specialty')
        item.specialty = Category.objects.filter(pk=specialty_id).first() if specialty_id else None
    item.summary = text_field(data, 'short_description', '') or text_field(data, 'summary', item.summary)
    item.description = text_field(data, 'full_description', '') or text_field(data, 'description', item.description)
    item.category = text_field(data, 'category', item.category)
    item.status = data.get('status', item.status)
    item.priority = data.get('priority', item.priority)
    item.location = text_field(data, 'location', item.location)
    item.is_remote = parse_boolean(data.get('is_remote'), item.is_remote)
    item.eligibility = text_field(data, 'eligibility', item.eligibility)
    item.requirements = text_field(data, 'requirements', item.requirements) or item.eligibility
    item.benefits = text_field(data, 'benefits', item.benefits)
    if 'custom_fields' in data:
        item.custom_fields = normalize_opportunity_custom_fields(data.get('custom_fields', []))
    item.application_url = text_field(data, 'application_url', item.application_url)
    item.contact_email = text_field(data, 'contact_email', item.contact_email)
    if 'deadline' in data:
        deadline = text_field(data, 'deadline')
        item.deadline = parse_date(deadline) if deadline else None
        if deadline and item.deadline is None:
            return error_response('Deadline must be a date (YYYY-MM-DD).')
    item.is_featured = parse_boolean(data.get('is_featured'), item.is_featured)
    item.show_when_closed = parse_boolean(data.get('show_when_closed'), item.show_when_closed)
    if 'assigned_to' in data:
        assignee_id = id_field(data.get('assigned_to'), 'assigned_to')
        item.assigned_to = User.objects.filter(pk=assignee_id).first() if assignee_id else None
    item.internal_notes = text_field(data, 'internal_notes', item.internal_notes)
    item.seo_title = text_field(data, 'seo_title', item.seo_title)
    item.seo_description = text_field(data, 'seo_description', item.seo_description)
    if not item.title:
        return error_response('Opportunity title is required.')
    if item.status not in dict(ResearchOpportunity.STATUS):
        return error_response('Unknown opportunity status.')
    if item.opportunity_type not in dict(ResearchOpportunity.TYPES):
        return error_response('Unknown opportunity type.')
    if item.priority not in dict(ResearchOpportunity.PRIORITIES):
        return error_response('Unknown priority.')
    if len(item.summary) > 280:
        return error_response('Short description must be 280 characters or less.')
    if item.slug and ResearchOpportunity.objects.exclude(pk=item.pk).filter(slug=item.slug).exists():
        return error_response('This opportunity slug is already used.')
    if item.specialty and not item.category:
        item.category = item.specialty.name
    # The editor deliberately allows a blank slug and advertises it as
    # auto-generated.  Generate it before Django model validation so the
    # required SlugField cannot produce the misleading "cannot be blank" API
    # error on every new opportunity.
    item.ensure_slug()
    try:
        item.full_clean(exclude=['created_by', 'assigned_to'])
    except ValidationError as exc:
        return error_response(' '.join(sum(exc.message_dict.values(), [])) if hasattr(exc, 'message_dict') else ' '.join(exc.messages))
    item.save()
    if item.status == 'published' and previous_status != 'published':
        _notify_opportunity_published(item, request.user)
    log_activity(request, 'opportunities', 'update' if pk else 'create', f'Saved opportunity: {item.title}', item)
    return JsonResponse({'success': True, 'opportunity': opportunity_to_dict(item)})

@require_POST
@api_permission_required('opportunities.delete')
def delete_opportunity_api(request, pk):
    item = get_object_or_404(ResearchOpportunity, pk=pk)
    item.status = 'archived'
    item.save(update_fields=['status', 'updated_at'])
    log_activity(request, 'opportunities', 'status', f'Archived opportunity: {item.title}', item)
    return JsonResponse({'success': True, 'opportunity': opportunity_to_dict(item)})

@require_POST
@api_permission_required('opportunities.manage')
def opportunity_status_api(request, pk):
    item = get_object_or_404(ResearchOpportunity, pk=pk)
    previous_status = item.status
    status = _text(get_payload(request), 'status')
    if status not in dict(ResearchOpportunity.STATUS):
        return error_response('Unknown opportunity status.')
    item.status = status
    item.save(update_fields=['status', 'updated_at'])
    if status == 'published' and previous_status != 'published':
        _notify_opportunity_published(item, request.user)
    log_activity(request, 'opportunities', 'status', f'Changed opportunity status to {status}: {item.title}', item)
    return JsonResponse({'success': True, 'opportunity': opportunity_to_dict(item)})

@require_GET
@api_permission_required('services.view')
def services_api(request):
    qs = ServiceDefinition.objects.prefetch_related('requests')
    if request.GET.get('status'):
        qs = qs.filter(status=request.GET.get('status'))
    if request.GET.get('category'):
        qs = qs.filter(category__iexact=request.GET.get('category'))
    qs = apply_common_filters(qs, request, ['title', 'summary', 'description', 'category'], ['title', 'status', 'updated_at'], 'title')
    payload = paginate(qs, request, service_to_dict, 30)
    payload['counts'] = _status_counts(ServiceDefinition.objects.all(), ServiceDefinition.STATUS)
    return JsonResponse(payload)

@require_POST
@api_save_permission_required('services')
def save_service_api(request, pk=None):
    data = get_payload(request)
    item = get_object_or_404(ServiceDefinition, pk=pk) if pk else ServiceDefinition(created_by=request.user)
    item.title = text_field(data, 'title', item.title)
    item.slug = text_field(data, 'slug', item.slug) or item.slug
    item.summary = text_field(data, 'summary', item.summary)
    item.description = text_field(data, 'description', item.description)
    item.category = text_field(data, 'category', item.category)
    item.status = data.get('status', item.status)
    item.assigned_team = text_field(data, 'assigned_team', item.assigned_team)
    item.price_note = text_field(data, 'price_note', item.price_note)
    item.turnaround_time = text_field(data, 'turnaround_time', item.turnaround_time)
    if 'intake_schema' in data:
        item.intake_schema = data['intake_schema'] if isinstance(data['intake_schema'], dict) else {}
    item.is_featured = parse_boolean(data.get('is_featured'), item.is_featured)
    item.internal_notes = text_field(data, 'internal_notes', item.internal_notes)
    if not item.title:
        return error_response('Service title is required.')
    if item.status not in dict(ServiceDefinition.STATUS):
        return error_response('Unknown service status.')
    if item.slug and ServiceDefinition.objects.exclude(pk=item.pk).filter(slug=item.slug).exists():
        return error_response('This service slug is already used.')
    item.save()
    log_activity(request, 'services', 'update' if pk else 'create', f'Saved service: {item.title}', item)
    return JsonResponse({'success': True, 'service': service_to_dict(item)})

@require_POST
@api_permission_required('services.delete')
def delete_service_api(request, pk):
    item = get_object_or_404(ServiceDefinition, pk=pk)
    title = item.title
    item.delete()
    log_activity(request, 'services', 'delete', f'Deleted service: {title}', metadata={'id': pk})
    return JsonResponse({'success': True})

@require_GET
@api_permission_required('services.view')
def service_requests_api(request):
    qs = ServiceRequest.objects.select_related('service', 'assigned_to')
    if request.GET.get('status'):
        qs = qs.filter(status=request.GET.get('status'))
    if request.GET.get('service'):
        qs = qs.filter(service_id=parse_int(request.GET.get('service')))
    if request.GET.get('priority'):
        qs = qs.filter(priority=request.GET.get('priority'))
    assigned = request.GET.get('assigned_to', '').strip()
    if assigned == 'none':
        qs = qs.filter(assigned_to__isnull=True)
    elif assigned:
        qs = qs.filter(assigned_to_id=parse_int(assigned))
    qs = apply_common_filters(qs, request, ['requester_name', 'requester_email', 'subject', 'message', 'organization'], ['status', 'priority', 'created_at', 'updated_at'], '-created_at')
    payload = paginate(qs, request, service_request_to_dict, 25)
    payload['counts'] = _status_counts(ServiceRequest.objects.all(), ServiceRequest.STATUS)
    payload['assignees'] = _assignees()
    return JsonResponse(payload)

@require_POST
@api_save_permission_required('services')
def save_service_request_api(request, pk=None):
    data = get_payload(request)
    item = get_object_or_404(ServiceRequest, pk=pk) if pk else ServiceRequest()
    service_id = id_field(data.get('service'), 'service')
    item.service = ServiceDefinition.objects.filter(pk=service_id).first() if service_id else item.service
    item.requester_name = text_field(data, 'requester_name', item.requester_name)
    item.requester_email = text_field(data, 'requester_email', item.requester_email)
    item.organization = text_field(data, 'organization', item.organization)
    item.subject = text_field(data, 'subject', item.subject)
    item.message = text_field(data, 'message', item.message)
    item.status = data.get('status', item.status)
    item.priority = data.get('priority', item.priority)
    if 'assigned_to' in data:
        assignee_id = id_field(data.get('assigned_to'), 'assigned_to')
        item.assigned_to = User.objects.filter(pk=assignee_id).first() if assignee_id else None
    item.internal_notes = text_field(data, 'internal_notes', item.internal_notes)
    if not item.requester_name or not item.requester_email or not item.subject:
        return error_response('Requester name, email, and subject are required.')
    if item.status not in dict(ServiceRequest.STATUS):
        return error_response('Unknown request status.')
    if item.priority not in dict(ServiceRequest.PRIORITIES):
        return error_response('Unknown priority.')
    item.save()
    log_activity(request, 'services', 'update' if pk else 'create', f'Saved service request: {item.subject}', item)
    return JsonResponse({'success': True, 'request': service_request_to_dict(item)})
