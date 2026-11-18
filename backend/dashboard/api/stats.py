from .common import *
from accounts.models import AccountNotification

@require_GET
@api_permission_required('dashboard.view')
def dashboard_bootstrap_api(request):
    recent_activity = []
    if has_dashboard_permission(request.user, 'activity.view'):
        recent_activity = DashboardActivityLog.objects.select_related('actor')[:8]
    new_contacts = ContactSubmission.objects.filter(status='new').count()
    new_applications = JobApplication.objects.filter(status='new').count()
    new_requests = ServiceRequest.objects.filter(status='new').count()
    pending_count = new_contacts + new_applications + new_requests
    # Counts shown next to sidebar items, keyed by route. Only modules the user
    # can open are listed, so a badge never reveals data the role cannot read.
    badge_sources = [
        ('/dashboard/posts', 'content.view', lambda: Post.objects.filter(post_type='post', status='pending').count()),
        ('/dashboard/contacts', 'forms.view', lambda: new_contacts),
        ('/dashboard/forms', 'forms.view', lambda: new_contacts + new_applications),
        ('/dashboard/services', 'services.view', lambda: new_requests),
    ]
    badges = {route: count() for route, permission, count in badge_sources if has_dashboard_permission(request.user, permission)}
    account_notifications = AccountNotification.objects.filter(user=request.user, is_read=False)[:5]
    notifications = [
        {'id': item.id, 'type': item.notification_type, 'title': item.title, 'message': item.message}
        for item in account_notifications
    ]
    notifications.append(
        {'id': 'pending-work', 'type': 'info', 'title': 'Pending work', 'message': f'{pending_count} items need review.'}
    )
    return JsonResponse({
        'user': user_to_dict(request.user),
        'role': get_dashboard_role(request.user),
        'permissions': permissions_for_user(request.user),
        'is_super_admin': is_super_admin(request.user),
        'modules': module_registry_for_user(request.user),
        'notifications': notifications,
        'badges': {route: count for route, count in badges.items() if count},
        'recent_activity': [activity_to_dict(item) for item in recent_activity],
    })

@require_GET
@api_permission_required('dashboard.view')
def dashboard_stats_api(request):
    now = timezone.now()
    last_30 = now - timedelta(days=30)
    last_7 = now - timedelta(days=7)
    stats = {
        'total_posts': Post.objects.filter(post_type='post').count(),
        'total_pages': Post.objects.filter(post_type='page').count(),
        'total_categories': Category.objects.count(),
        'total_authors': Author.objects.count(),
        'total_media': MediaAsset.objects.count(),
        'draft_content': Post.objects.filter(status='draft').count(),
        'draft_articles': Post.objects.filter(post_type='post', status='draft').count(),
        'published_articles': Post.objects.filter(post_type='post', status='publish', published_at__lte=now).count(),
        'scheduled_articles': Post.objects.filter(post_type='post', status='publish', published_at__gt=now).count(),
        'review_articles': Post.objects.filter(post_type='post', status='pending').count(),
        'new_contacts': ContactSubmission.objects.filter(status='new').count(),
        'total_contacts': ContactSubmission.objects.count(),
        'new_applications': JobApplication.objects.filter(status='new').count(),
        'subscribers': NewsletterSubscriber.objects.filter(is_active=True).count(),
        'team_members': User.objects.filter(is_active=True).count(),
        'research_opportunities': ResearchOpportunity.objects.count(),
        'open_opportunities': ResearchOpportunity.objects.filter(status='published').count(),
        'active_services': ServiceDefinition.objects.filter(status='active').count(),
        'new_service_requests': ServiceRequest.objects.filter(status='new').count(),
        'posts_this_month': Post.objects.filter(post_type='post', status='publish', published_at__gte=last_30, published_at__lte=now).count(),
        'posts_this_week': Post.objects.filter(post_type='post', status='publish', published_at__gte=last_7, published_at__lte=now).count(),
    }
    content_status = list(Post.objects.values('status').annotate(count=Count('id')).order_by('status'))
    service_status = list(ServiceRequest.objects.values('status').annotate(count=Count('id')).order_by('status'))
    application_status = list(JobApplication.objects.values('status').annotate(count=Count('id')).order_by('status'))
    recent_activity = []
    if has_dashboard_permission(request.user, 'activity.view'):
        recent_activity = DashboardActivityLog.objects.select_related('actor')[:10]
    articles = Post.objects.filter(post_type='post').exclude(status='trash')
    content_health = articles.aggregate(
        missing_seo=Count('id', filter=Q(seo_title='') | Q(seo_description=''), distinct=True),
        missing_image=Count('id', filter=Q(featured_image=''), distinct=True),
        missing_excerpt=Count('id', filter=Q(excerpt=''), distinct=True),
        uncategorized=Count('id', filter=Q(categories__isnull=True), distinct=True),
    )
    content_health['total'] = articles.count()
    # Published articles per week for the last 12 weeks (oldest first).
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    publishing_trend = []
    for offset in range(11, -1, -1):
        start = week_start - timedelta(weeks=offset)
        end = start + timedelta(weeks=1)
        publishing_trend.append({
            'week': start.date().isoformat(),
            'count': Post.objects.filter(post_type='post', status='publish', published_at__gte=start, published_at__lt=min(end, now)).count(),
        })
    pending_tasks = [
        {'label': 'New contacts', 'count': stats['new_contacts'], 'route': '/dashboard/forms?type=contacts'},
        {'label': 'Team applications', 'count': stats['new_applications'], 'route': '/dashboard/forms?type=applications'},
        {'label': 'Service requests', 'count': stats['new_service_requests'], 'route': '/dashboard/services?tab=requests'},
        {'label': 'Draft articles', 'count': stats['draft_articles'], 'route': '/dashboard/posts?status=draft'},
    ]
    return JsonResponse({
        'stats': stats,
        'editorial_queue': [
            {'id':post.id, 'title':post.title, 'status':post.status, 'published_at':post.published_at.isoformat() if post.published_at else None, 'updated_at':post.updated_at.isoformat()}
            for post in Post.objects.filter(post_type='post').filter(Q(status='pending') | Q(status='publish', published_at__gt=now)).order_by('published_at', '-updated_at')[:6]
        ] if has_dashboard_permission(request.user, 'content.view') else [],
        'recent_drafts': [
            {'id': post.id, 'title': post.title, 'post_type': post.post_type, 'updated_at': post.updated_at.isoformat()}
            for post in Post.objects.filter(status='draft').order_by('-updated_at')[:5]
        ] if has_dashboard_permission(request.user, 'content.view') else [],
        'content_health': content_health if has_dashboard_permission(request.user, 'content.view') else None,
        'publishing_trend': publishing_trend,
        'charts': {
            'content_status': content_status,
            'service_status': service_status,
            'application_status': application_status,
        },
        'pending_tasks': pending_tasks,
        'recent_activity': [activity_to_dict(item) for item in recent_activity],
    })

@require_GET
@api_permission_required('activity.view')
def activity_api(request):
    qs = DashboardActivityLog.objects.select_related('actor')
    if request.GET.get('module'):
        qs = qs.filter(module=request.GET.get('module'))
    if request.GET.get('action'):
        qs = qs.filter(action=request.GET.get('action'))
    qs = apply_common_filters(qs, request, ['message', 'object_label', 'module'], ['module', 'action', 'created_at'], '-created_at')
    return JsonResponse(paginate(qs, request, activity_to_dict, 30))
