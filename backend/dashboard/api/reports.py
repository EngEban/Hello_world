from .common import *

@require_GET
@api_permission_required('reports.view')
def reports_api(request):
    last_30 = timezone.now() - timedelta(days=30)
    return JsonResponse({
        'summary': {
            'users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'content_items': Post.objects.count(),
            'published_content': Post.objects.filter(status='publish').count(),
            'service_requests': ServiceRequest.objects.count(),
            'open_opportunities': ResearchOpportunity.objects.filter(status='published').count(),
            'new_forms_30_days': ContactSubmission.objects.filter(created_at__gte=last_30).count() + JobApplication.objects.filter(created_at__gte=last_30).count(),
        },
        'content_by_status': list(Post.objects.values('status').annotate(count=Count('id')).order_by('status')),
        'forms_by_status': list(ContactSubmission.objects.values('status').annotate(count=Count('id')).order_by('status')),
        'services_by_status': list(ServiceRequest.objects.values('status').annotate(count=Count('id')).order_by('status')),
        'opportunities_by_status': list(ResearchOpportunity.objects.values('status').annotate(count=Count('id')).order_by('status')),
        'export_modules': sorted(EXPORT_SERIALIZERS.keys()),
        # Same modules with the read permission each export needs, so the page can
        # show which exports this account may download (the export view enforces it).
        'exports': [
            {
                'module': module,
                'permission': EXPORT_READ_PERMISSIONS.get(module, 'settings.view'),
                'allowed': has_dashboard_permission(request.user, 'reports.manage')
                and has_dashboard_permission(request.user, EXPORT_READ_PERMISSIONS.get(module, 'settings.view')),
            }
            for module in sorted(EXPORT_SERIALIZERS.keys())
        ],
        'users_by_tier': list(
            User.objects.values('membership_profile__tier').annotate(count=Count('id')).order_by('membership_profile__tier')
        ),
        'signups_trend': _weekly_counts(User.objects.all(), 'date_joined'),
        'activity_30_days': DashboardActivityLog.objects.filter(created_at__gte=last_30).count(),
        'activity_by_module': list(
            DashboardActivityLog.objects.filter(created_at__gte=last_30)
            .values('module').annotate(count=Count('id')).order_by('-count', 'module')[:8]
        ),
    })


def _weekly_counts(queryset, field, weeks=12):
    """Rows per week for the last `weeks` weeks, oldest first ([{week, count}])."""
    now = timezone.now()
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    series = []
    for offset in range(weeks - 1, -1, -1):
        start = week_start - timedelta(weeks=offset)
        end = start + timedelta(weeks=1)
        series.append({
            'week': start.date().isoformat(),
            'count': queryset.filter(**{f'{field}__gte': start, f'{field}__lt': end}).count(),
        })
    return series

FORMULA_TRIGGERS = ('=', '+', '-', '@', '\t', '\r')


def flatten_export_value(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    result = '' if value is None else str(value)
    # Spreadsheet programs can treat formula markers, including a leading tab
    # or carriage return before a marker, as executable formulas when CSV data
    # is opened. Prefixing an apostrophe makes every such cell inert text.
    if result and result[0] in FORMULA_TRIGGERS:
        result = "'" + result
    return result

# reports.export alone must not unlock data the user cannot read (S-10).
EXPORT_READ_PERMISSIONS = {
    'users': 'users.view',
    'posts': 'content.view', 'categories': 'taxonomy.view', 'tags': 'taxonomy.view',
    'authors': 'taxonomy.view', 'media': 'media.view',
    'faq-categories': 'faq.view', 'faq-items': 'faq.view',
    'contacts': 'forms.view', 'applications': 'forms.view', 'join-team': 'forms.view',
    'newsletter': 'forms.view', 'newsletter-campaigns': 'forms.view',
    'opportunities': 'opportunities.view',
    'services': 'services.view', 'service-requests': 'services.view',
    'activity': 'activity.view',
    'settings': 'settings.view',
}


@require_GET
@api_permission_required('reports.manage')
def export_api(request, module):
    if module not in EXPORT_SERIALIZERS:
        return error_response('Unknown export module.', 404)
    required = EXPORT_READ_PERMISSIONS.get(module, 'settings.view')
    if not has_dashboard_permission(request.user, required):
        return error_response(f'Missing dashboard permission: {required}', 403)
    export_format = request.GET.get('format', 'csv').lower()
    queryset_factory, serializer = EXPORT_SERIALIZERS[module]
    queryset = queryset_factory()
    rows = [serializer(item) for item in queryset[:2000]]
    log_activity(request, 'reports', 'export', f'Exported {module} as {export_format}', metadata={'module': module, 'format': export_format, 'rows': len(rows)})
    if export_format == 'json':
        return JsonResponse({'results': rows})
    if export_format in {'csv', 'xlsx', 'excel'}:
        headers = sorted({key for row in rows for key in row.keys()}) if rows else ['message']
        content_type = 'text/csv; charset=utf-8' if export_format == 'csv' else 'application/vnd.ms-excel; charset=utf-8'
        extension = 'csv' if export_format == 'csv' else 'xls'
        response = HttpResponse(content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="resref-{module}.{extension}"'
        writer = csv.writer(response)
        writer.writerow(headers)
        if rows:
            for row in rows:
                writer.writerow([flatten_export_value(row.get(header)) for header in headers])
        else:
            writer.writerow([f'No {module} records found.'])
        return response
    if export_format == 'pdf':
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
        except ImportError:
            return error_response('PDF export is prepared but requires reportlab on the server. Install reportlab>=4.0 to enable it.', 501)
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="resref-{module}.pdf"'
        pdf = canvas.Canvas(response, pagesize=letter)
        width, height = letter
        y = height - 48
        pdf.setFont('Helvetica-Bold', 14)
        pdf.drawString(40, y, f'ResRef export: {module}')
        pdf.setFont('Helvetica', 9)
        y -= 24
        for row in rows[:60]:
            text = ' | '.join(f'{key}: {flatten_export_value(value)}' for key, value in list(row.items())[:5])
            pdf.drawString(40, y, text[:120])
            y -= 14
            if y < 48:
                pdf.showPage()
                pdf.setFont('Helvetica', 9)
                y = height - 48
        pdf.save()
        return response
    return error_response('Export format must be csv, excel, json, or pdf.')
