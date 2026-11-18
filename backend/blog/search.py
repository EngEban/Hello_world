import json

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.models import UserToolWorkspace
from blog.models import MediaAsset, Post
from dashboard.models import ResearchOpportunity
from dashboard.permissions import has_dashboard_access, has_dashboard_permission


PUBLIC_TYPES = {'post', 'page', 'opportunity'}
DASHBOARD_TYPES = {'media'}
ADMIN_TYPES = {'user'}
PERSONAL_TYPES = {'tool'}
ALL_TYPES = PUBLIC_TYPES | DASHBOARD_TYPES | ADMIN_TYPES | PERSONAL_TYPES
DEFAULT_TYPES = {'post', 'page', 'opportunity', 'tool'}
MAX_PER_TYPE = 20
TYPE_ALIASES = {
    'posts': 'post',
    'pages': 'page',
    'opportunities': 'opportunity',
    'tools': 'tool',
    'workspaces': 'tool',
    'users': 'user',
    'media-assets': 'media',
    'files': 'media',
}


def clean_query(value):
    return str(value or '').strip()[:250]


def requested_types(value):
    if not value:
        return DEFAULT_TYPES
    items = {
        TYPE_ALIASES.get(item.strip().lower(), item.strip().lower())
        for item in str(value).replace(',', ' ').split()
        if item.strip()
    }
    if 'all' in items:
        return ALL_TYPES
    return items & ALL_TYPES


def limited_count(value, default=8):
    try:
        return min(max(int(value or default), 1), MAX_PER_TYPE)
    except (TypeError, ValueError):
        return default


def public_post_queryset(params, post_type='post'):
    q = clean_query(params.get('q') or params.get('search'))
    category = clean_query(params.get('category') or params.get('cat'))
    tag = clean_query(params.get('tag'))
    date_from = parse_date(params.get('date_from') or params.get('published_after') or '')
    date_to = parse_date(params.get('date_to') or params.get('published_before') or '')

    qs = (
        Post.objects
        .filter(post_type=post_type, status='publish', published_at__lte=timezone.now())
        .select_related('author')
        .prefetch_related('categories', 'tags')
        .defer('content', 'elementor_data')
    )
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(content__icontains=q) | Q(excerpt__icontains=q))
    if category:
        qs = qs.filter(categories__slug=category)
    if tag:
        qs = qs.filter(tags__slug=tag)
    if date_from:
        qs = qs.filter(published_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(published_at__date__lte=date_to)
    return qs.order_by('-published_at').distinct()


def category_slug(post):
    first_category = next(iter(post.categories.all()), None)
    return first_category.slug if first_category else 'research'


def post_result(post):
    return {
        'type': post.post_type,
        'id': post.id,
        'title': post.title,
        'excerpt': post.excerpt,
        'url': f'/database/{category_slug(post)}/{post.slug}' if post.post_type == 'post' else f'/page/{post.slug}',
        'published_at': post.published_at.isoformat() if post.published_at else None,
        'metadata': {
            'seo_title': post.seo_title,
            'seo_description': post.seo_description,
            'categories': [{'id': item.id, 'name': item.name, 'slug': item.slug} for item in post.categories.all()],
            'tags': [{'id': item.id, 'name': item.name, 'slug': item.slug} for item in post.tags.all()],
        },
    }


def workspace_matches(workspace, q):
    if not q:
        return True
    q = q.lower()
    if q in workspace.tool_key.lower():
        return True
    try:
        searchable_data = json.dumps(workspace.data or {}, ensure_ascii=False, sort_keys=True).lower()
    except (TypeError, ValueError):
        searchable_data = str(workspace.data or '').lower()
    return q in searchable_data


def tool_results(request, q, limit):
    if not request.user.is_authenticated:
        return []
    qs = (
        UserToolWorkspace.objects
        .filter(user=request.user)
        .select_related('user')
        .order_by('-updated_at')[:100]
    )
    results = []
    for workspace in qs:
        if not workspace_matches(workspace, q):
            continue
        results.append({
            'type': 'tool',
            'id': workspace.id,
            'title': workspace.tool_key.replace('-', ' ').title(),
            'excerpt': 'Saved tool workspace',
            'url': f'/tools/{workspace.tool_key}',
            'updated_at': workspace.updated_at.isoformat() if workspace.updated_at else None,
            'metadata': {
                'tool_key': workspace.tool_key,
                'owner_id': workspace.user_id,
            },
        })
        if len(results) >= limit:
            break
    return results


def admin_user_results(request, q, limit, params):
    # A role name alone is not enough: an account with access_role="admin" but
    # no dashboard access (not staff, inactive role) must see nothing (S-10).
    if not has_dashboard_access(request.user) or not has_dashboard_permission(request.user, 'users.view'):
        return []
    qs = User.objects.select_related('membership_profile').order_by('-date_joined')
    if q:
        qs = qs.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(membership_profile__display_name__icontains=q)
            | Q(membership_profile__specialization__icontains=q)
            | Q(membership_profile__organization__icontains=q)
        )
    tier = params.get('tier')
    if tier in {'free', 'premium'}:
        qs = qs.filter(membership_profile__tier=tier)
    access_role = params.get('access_role')
    if access_role in {'member', 'editor', 'admin'}:
        qs = qs.filter(membership_profile__access_role=access_role)
    status = params.get('status')
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)

    results = []
    for user in qs[:limit]:
        profile = getattr(user, 'membership_profile', None)
        display_name = (
            getattr(profile, 'display_name', '')
            or user.get_full_name()
            or user.email
            or user.username
        )
        results.append({
            'type': 'user',
            'id': user.id,
            'title': display_name,
            'excerpt': user.email or user.username,
            'url': f'/dashboard/users?user={user.id}',
            'metadata': {
                'username': user.username,
                'email': user.email,
                'display_name': display_name,
                'specialization': getattr(profile, 'specialization', ''),
                'tier': getattr(profile, 'effective_tier', ''),
                'access_role': getattr(profile, 'access_role', ''),
                'is_active': user.is_active,
            },
        })
    return results


def media_results(request, q, limit):
    if not has_dashboard_access(request.user) or not has_dashboard_permission(request.user, 'content.view'):
        return []
    qs = MediaAsset.objects.all().order_by('-created_at')
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(alt_text__icontains=q)
            | Q(caption__icontains=q)
            | Q(url__icontains=q)
        )
    return [
        {
            'type': 'media',
            'id': asset.id,
            'title': asset.title or asset.alt_text or f'Media {asset.id}',
            'excerpt': asset.caption or asset.alt_text,
            'url': asset.source_url(),
            'created_at': asset.created_at.isoformat() if asset.created_at else None,
            'metadata': {
                'alt_text': asset.alt_text,
                'wordpress_id': asset.wordpress_id,
            },
        }
        for asset in qs[:limit]
    ]


def opportunity_results(params, q, limit):
    category = clean_query(params.get('category') or params.get('cat'))
    date_from = parse_date(params.get('date_from') or '')
    date_to = parse_date(params.get('date_to') or '')
    qs = ResearchOpportunity.objects.filter(status='published').select_related('specialty')
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(summary__icontains=q)
            | Q(description__icontains=q)
            | Q(category__icontains=q)
            | Q(organization__icontains=q)
            | Q(location__icontains=q)
            | Q(specialty__name__icontains=q)
        )
    if category:
        qs = qs.filter(Q(category__iexact=category) | Q(specialty__slug=category) | Q(specialty__name__iexact=category))
    if date_from:
        qs = qs.filter(updated_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(updated_at__date__lte=date_to)
    qs = qs.order_by('-is_featured', 'deadline', '-updated_at')
    return [
        {
            'type': 'opportunity',
            'id': item.id,
            'title': item.title,
            'excerpt': item.summary,
            'url': f'/opportunities?opportunity={item.slug}',
            'updated_at': item.updated_at.isoformat() if item.updated_at else None,
            'metadata': {
                'organization': item.organization,
                'category': item.specialty.name if item.specialty_id else item.category,
                'type': item.opportunity_type,
                'deadline': item.deadline.isoformat() if item.deadline else '',
                'is_remote': item.is_remote,
            },
        }
        for item in qs[:limit]
    ]


def unified_search(request):
    params = request.GET
    q = clean_query(params.get('q') or params.get('search'))
    limit = limited_count(params.get('per_type'))
    types = requested_types(params.get('content_type') or params.get('type'))
    results = {}

    if 'post' in types:
        results['posts'] = [post_result(item) for item in public_post_queryset(params, 'post')[:limit]]
    if 'page' in types:
        results['pages'] = [post_result(item) for item in public_post_queryset(params, 'page')[:limit]]
    if 'tool' in types:
        results['tools'] = tool_results(request, q, limit)
    if 'opportunity' in types:
        results['opportunities'] = opportunity_results(params, q, limit)
    if 'user' in types:
        results['users'] = admin_user_results(request, q, limit, params)
    if 'media' in types:
        results['media'] = media_results(request, q, limit)

    flat_results = [item for group in results.values() for item in group]
    return {
        'query': q,
        'content_types': sorted(types),
        'results': results,
        'flat_results': flat_results,
        'counts': {key: len(value) for key, value in results.items()},
        'limitations': [
            'General file/document search is not available because the project currently has no dedicated searchable file model. MediaAsset image metadata is searchable for dashboard users with content.read permission.'
        ],
    }
