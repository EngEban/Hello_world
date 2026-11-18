from django.core.cache import cache
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Case, Count, IntegerField, Prefetch, Q, When
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.utils.html import strip_tags
import json
import re

from accounts.security import rate_limit
from .seo_analysis import post_seo_settings
from .models import Author, Post, PostContributor, Category, Tag
from .reference_lookup import SOURCE_TYPES, search_references
from .search import unified_search
from .selectors import published_post_count
from .services import NEWSLETTER_CHECK_INBOX, newsletter_enabled_required, send_newsletter_confirmation
from dashboard.models import ContactSubmission, FAQCategory, FAQItem, JoinTeamEntry, NewsletterSubscriber, ResearchOpportunity, SiteSettings

PHONE_ALLOWED_PATTERN = re.compile(r'^\+?[0-9\s().-]{7,20}$')
LEGACY_MEDIA_HOSTS = (
    'http://resres.local',
    'https://resres.local',
    'http://resref.local',
    'https://resref.local',
)


def api_error(message, status=400):
    return JsonResponse({'success': False, 'error': message}, status=status)


def clean_text(payload, key, max_length, required=False):
    value = str(payload.get(key, '') or '').strip()
    if required and not value:
        raise ValidationError(f'{key.replace("_", " ").title()} is required.')
    if len(value) > max_length:
        raise ValidationError(f'{key.replace("_", " ").title()} is too long.')
    return value


def validate_optional_phone_number(value):
    if not value:
        return
    digits = re.sub(r'\D', '', value)
    if len(digits) < 7 or len(digits) > 15 or not PHONE_ALLOWED_PATTERN.match(value):
        raise ValidationError('Please enter a valid WhatsApp number.')


def read_minutes_for(post):
    text = strip_tags(post.content or '')
    words = len(re.findall(r'\w+', text))
    return max(1, round(words / 220)) if words else 1


def normalize_legacy_media_urls(value):
    text = value or ''
    for host in LEGACY_MEDIA_HOSTS:
        text = text.replace(f'{host}/wp-content/uploads/', 'https://resref.com/wp-content/uploads/')
    return text


def category_to_dict(category, public_only=False):
    children = category.children.all()
    if public_only:
        children = children.filter(show_in_database=True)
    count = published_post_count(category)
    return {
        'id': category.id,
        'name': category.name,
        'description': category.description,
        'hero_image': normalize_legacy_media_urls(category.hero_image),
        'slug': category.slug,
        'parent_id': category.parent_id,
        'show_in_database': category.show_in_database,
        'database_order': category.database_order,
        'count': count,
        'post_count': count,
        'children': [category_to_dict(child, public_only=public_only) for child in children.order_by('database_order', 'name')],
    }


def author_to_public_dict(author):
    image = author.profile_media.source_url() if getattr(author, 'profile_media_id', None) else author.avatar
    return {
        'id': author.id,
        'slug': author.slug,
        'display_name': author.display_name,
        'prefix': author.prefix,
        'credentials': author.credentials,
        'role': author.role,
        'position': author.position,
        'specialty': author.specialty,
        'institution': author.institution,
        'country': author.country,
        'bio': author.bio,
        'short_bio': author.short_bio or author.bio,
        'avatar': image,
        'website': author.website,
        'orcid': author.orcid,
        'google_scholar': author.google_scholar,
        'researchgate': author.researchgate,
        'linkedin': author.linkedin,
        'twitter': author.twitter,
        'seo_title': author.seo_title,
        'seo_description': author.seo_description,
    }


def contributor_assignment_to_public_dict(assignment):
    data = author_to_public_dict(assignment.contributor)
    data.update({
        'role': assignment.role,
        'role_label': assignment.get_role_display(),
        'contribution_note': assignment.contribution_note,
        'display_order': assignment.display_order,
    })
    return data


def file_url(value, request=None):
    if not value:
        return ''
    url = value.url
    return request.build_absolute_uri(url) if request else url


def post_to_dict(post, include_content=False, include_editor_meta=False, request=None):
    assignments = list(post.contributor_assignments.all())
    authors = [assignment.contributor for assignment in assignments] or list(post.authors.all())
    if post.author and any(author.id == post.author_id for author in authors):
        authors = [post.author] + [author for author in authors if author.id != post.author_id]
    author_names = ', '.join(author.display_name for author in authors)
    data = {
        'id': post.id,
        'title': post.title,
        'slug': post.slug,
        'excerpt': post.excerpt,
        'post_type': post.post_type,
        'status': post.status,
        'featured_image': normalize_legacy_media_urls(post.featured_image),
        'seo_title': post.seo_title,
        'seo_description': post.seo_description,
        # The editor's SEO settings live in design_settings['seo']; they are editor-only.
        'design_settings': {key: value for key, value in (post.design_settings or {}).items() if key != 'seo'} if isinstance(post.design_settings, dict) else {},
        'read_minutes': read_minutes_for(post),
        'published_at': post.published_at.isoformat() if post.published_at else None,
        'updated_at': post.updated_at.isoformat(),
        'author_id': post.author_id,
        'author': author_names,
        'authors': [contributor_assignment_to_public_dict(assignment) for assignment in assignments] if assignments else [author_to_public_dict(author) for author in authors],
        'pdf_url': file_url(post.pdf_file, request),
        'pdf_title': post.pdf_title,
        'categories': [{'id': c.id, 'name': c.name, 'slug': c.slug} for c in post.categories.all()],
        'tags': [{'id': t.id, 'name': t.name, 'slug': t.slug} for t in post.tags.all()],
    }
    if include_content:
        data['content'] = normalize_legacy_media_urls(post.content)
    if include_editor_meta:
        data.update({
            'wordpress_id': post.wordpress_id,
            'wordpress_url': post.wordpress_url,
            'elementor_data': post.elementor_data,
            'page_template': post.page_template,
            'seo_settings': post_seo_settings(post),
            'updated_at': post.updated_at.isoformat(),
            'author_ids': [author.id for author in authors],
            'contributors': [
                {'contributor_id': assignment.contributor_id, 'role': assignment.role,
                 'display_order': assignment.display_order, 'contribution_note': assignment.contribution_note}
                for assignment in assignments
            ],
        })
    return data


def paginated_response(queryset, page_number, per_page=12, serializer=post_to_dict):
    paginator = Paginator(queryset, per_page)
    page = paginator.get_page(page_number)
    return {
        'results': [serializer(item) for item in page.object_list],
        'pagination': {
            'current_page': page.number,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_next': page.has_next(),
            'has_previous': page.has_previous(),
        }
    }


@require_GET
def home_api(request):
    published_posts = Post.objects.filter(post_type='post', status='publish', published_at__lte=timezone.now())
    resource_count = published_posts.count()
    category_count = Category.objects.filter(parent=None, show_in_database=True).count()
    posts = published_posts.select_related('author').prefetch_related('categories', 'tags', 'authors', 'contributor_assignments__contributor').annotate(
        featured_priority=Case(When(design_settings__is_featured=True, then=0), default=1, output_field=IntegerField())
    ).order_by('featured_priority', '-published_at')[:6]
    learning_posts = published_posts.filter(categories__slug='mastering-research').select_related('author').prefetch_related('categories', 'tags', 'authors', 'contributor_assignments__contributor').distinct().order_by('-published_at')[:3]
    return JsonResponse({
        'resource_count': resource_count,
        'category_count': category_count,
        'featured_posts': [post_to_dict(post, request=request) for post in posts],
        'learning_posts': [post_to_dict(post, request=request) for post in learning_posts],
    })


@require_GET
def posts_api(request):
    q = request.GET.get('q', '')
    cat_slug = request.GET.get('cat', '')
    tag_slug = request.GET.get('tag', '')
    post_type = request.GET.get('type', 'post')
    if q and not rate_limit(request, 'posts-search', limit=120, window=60):
        # Full-text icontains over article bodies is the costliest public query.
        return api_error('Too many searches. Please wait a minute and try again.', 429)
    posts = Post.objects.filter(post_type=post_type, status='publish', published_at__lte=timezone.now()).select_related('author').prefetch_related('categories', 'tags', 'authors', 'contributor_assignments__contributor')
    if q:
        posts = posts.filter(Q(title__icontains=q) | Q(content__icontains=q) | Q(excerpt__icontains=q))
    if cat_slug:
        posts = posts.filter(categories__slug=cat_slug)
    if tag_slug:
        posts = posts.filter(tags__slug=tag_slug)
    # Explicit allowlist keeps sorting stable and prevents arbitrary field access.
    ordering = {'latest': '-published_at', 'oldest': 'published_at', 'updated': '-updated_at', 'title': 'title'}
    posts = posts.order_by(ordering.get(request.GET.get('sort'), '-published_at'), 'id').distinct()
    try:
        per_page = min(max(int(request.GET.get('per_page', 12) or 12), 1), 50)
    except (TypeError, ValueError):
        per_page = 12
    return JsonResponse(paginated_response(posts, request.GET.get('page'), per_page, lambda post: post_to_dict(post, request=request)))


@require_GET
def unified_search_api(request):
    if not rate_limit(request, 'unified-search', limit=90, window=60):
        return JsonResponse({'success': False, 'error': 'Too many searches. Please wait a minute and try again.'}, status=429)
    return JsonResponse(unified_search(request))


@require_GET
def post_detail_api(request, slug):
    post = get_object_or_404(Post.objects.select_related('author').prefetch_related('categories', 'tags', 'authors', 'contributor_assignments__contributor'), slug=slug, post_type='post', status='publish', published_at__lte=timezone.now())
    related = Post.objects.filter(categories__in=post.categories.all(), post_type='post', status='publish', published_at__lte=timezone.now()).select_related('author').prefetch_related('categories', 'tags', 'authors', 'contributor_assignments__contributor').exclude(id=post.id).distinct()[:3]
    return JsonResponse({'post': post_to_dict(post, include_content=True, request=request), 'related_posts': [post_to_dict(item, request=request) for item in related]})


@require_GET
def page_detail_api(request, slug):
    page = get_object_or_404(Post.objects.select_related('author').prefetch_related('categories', 'tags', 'authors', 'contributor_assignments__contributor'), slug=slug, post_type='page', status='publish', published_at__lte=timezone.now())
    return JsonResponse({'page': post_to_dict(page, include_content=True, request=request)})


@require_GET
def categories_api(request):
    # Build the existing hierarchy in one query instead of counting each topic
    # separately; the same public visibility and direct article counts apply.
    categories = Category.objects.filter(show_in_database=True).annotate(
        public_post_count=Count('post', filter=Q(
            post__post_type='post', post__status='publish', post__published_at__lte=timezone.now(),
        )),
    ).order_by('database_order', 'name')
    nodes = {category.id: {
        'id': category.id, 'name': category.name, 'slug': category.slug,
        'description': category.description, 'hero_image': normalize_legacy_media_urls(category.hero_image),
        'parent_id': category.parent_id, 'show_in_database': True,
        'database_order': category.database_order, 'count': category.public_post_count,
        'post_count': category.public_post_count, 'children': [],
    } for category in categories}
    roots = []
    for node in nodes.values():
        if node['parent_id'] is None:
            roots.append(node)
        elif node['parent_id'] in nodes:
            nodes[node['parent_id']]['children'].append(node)
    return JsonResponse({'categories': roots})


@require_GET
def authors_api(request):
    authors = Author.objects.filter(is_active=True).select_related('profile_media').order_by('display_order', 'display_name')
    return JsonResponse({'results': [author_to_public_dict(author) for author in authors]})


@require_GET
def author_detail_api(request, slug):
    author = get_object_or_404(Author.objects.select_related('profile_media'), slug=slug, is_active=True)
    assignments = PostContributor.objects.filter(
        contributor=author, post__status='publish', post__post_type='post', post__published_at__lte=timezone.now(),
    ).select_related('post').order_by('role', 'display_order', '-post__published_at')
    seen, contributions = set(), []
    for assignment in assignments:
        if assignment.post_id in seen:
            continue
        seen.add(assignment.post_id)
        contributions.append({
            'role': assignment.role, 'role_label': assignment.get_role_display(),
            'contribution_note': assignment.contribution_note,
            'post': post_to_dict(assignment.post, request=request),
        })
    # Older articles use the original author fields rather than role credits.
    legacy_posts = Post.objects.filter(
        authors=author, status='publish', post_type='post',
        published_at__lte=timezone.now(),
    ).exclude(pk__in=seen).select_related('author').prefetch_related(
        'categories', 'tags', 'authors', 'contributor_assignments__contributor',
    ).distinct().order_by('-published_at')
    contributions.extend({
        'role': 'author', 'role_label': 'Author', 'contribution_note': '',
        'post': post_to_dict(post, request=request),
    } for post in legacy_posts)
    return JsonResponse({'author': author_to_public_dict(author), 'contributions': contributions})


def public_opportunity_to_dict(item):
    specialty = item.specialty if item.specialty_id else None
    is_closed = item.status == 'closed'
    return {
        'id': item.id,
        'title': item.title,
        'slug': item.slug,
        'organization': item.organization,
        'type': item.opportunity_type,
        'type_label': item.get_opportunity_type_display(),
        'specialty': specialty.name if specialty else item.category,
        'specialty_slug': specialty.slug if specialty else '',
        'location': item.location,
        'is_remote': item.is_remote,
        'deadline': item.deadline.isoformat() if item.deadline else '',
        'short_description': item.summary,
        'full_description': item.description,
        'requirements': item.requirements or item.eligibility,
        'benefits': item.benefits,
        'custom_fields': [field for field in item.custom_fields if field.get('is_public', True)],
        'application_url': item.application_url,
        'contact_email': item.contact_email,
        'is_featured': item.is_featured,
        'status': item.status,
        'is_closed': is_closed,
        'updated_at': item.updated_at.isoformat() if item.updated_at else None,
    }


def public_join_team_to_dict(item):
    return {
        'id': item.id,
        'title': item.title,
        'slug': item.slug,
        'description': item.description,
        'icon_key': item.icon_key,
        'action_label': item.action_label,
        'action_url': item.action_url,
        'seo_title': item.seo_title,
        'seo_description': item.seo_description,
    }


@require_GET
def join_team_entries_api(request):
    qs = JoinTeamEntry.objects.filter(status='published').order_by('sort_order', 'title')
    return JsonResponse({'results': [public_join_team_to_dict(item) for item in qs]})


@require_GET
def opportunities_api(request):
    qs = ResearchOpportunity.objects.filter(
        Q(status='published') | Q(status='closed', show_when_closed=True)
    ).select_related('specialty')
    if request.GET.get('current') == 'true':
        qs = qs.filter(status='published').filter(Q(deadline__isnull=True) | Q(deadline__gte=timezone.localdate()))
    category = request.GET.get('category', '').strip()
    if category:
        qs = qs.filter(Q(category__iexact=category) | Q(specialty__slug=category) | Q(specialty__name__iexact=category))
    opportunity_type = request.GET.get('type', '').strip()
    if opportunity_type:
        qs = qs.filter(opportunity_type=opportunity_type)
    location = request.GET.get('location', '').strip()
    if location:
        qs = qs.filter(location__icontains=location)
    search = request.GET.get('search', request.GET.get('q', '')).strip()
    if search:
        qs = qs.filter(
            Q(title__icontains=search)
            | Q(summary__icontains=search)
            | Q(description__icontains=search)
            | Q(organization__icontains=search)
            | Q(location__icontains=search)
            | Q(specialty__name__icontains=search)
        )
    qs = qs.order_by('-is_featured', 'deadline', '-updated_at')
    try:
        per_page = min(max(int(request.GET.get('per_page', 12) or 12), 1), 50)
    except (TypeError, ValueError):
        per_page = 12
    return JsonResponse(paginated_response(qs, request.GET.get('page'), per_page, public_opportunity_to_dict))


@require_GET
def faq_api(request):
    published_items = Prefetch(
        'items',
        queryset=FAQItem.objects.filter(status='published').order_by('sort_order', 'question'),
        to_attr='published_items',
    )
    categories = FAQCategory.objects.prefetch_related(published_items).order_by('sort_order', 'name')
    payload = []
    for category in categories:
        items = [
            {
                'id': item.id,
                'question': item.question,
                'answer': item.answer,
                'sort_order': item.sort_order,
            }
            for item in category.published_items
        ]
        if items:
            payload.append({
                'id': category.id,
                'name': category.name,
                'slug': category.slug,
                'sort_order': category.sort_order,
                'items': items,
            })
    return JsonResponse({'categories': payload})


PUBLIC_SITE_SETTINGS_CACHE_KEY = 'public-site-settings:v1'


@require_GET
def site_settings_api(request):
    # Every page load reads these public, whitelisted values. A per-IP limit
    # here blocked whole groups of visitors who share an address (campus NAT,
    # mobile carriers, proxies), so the endpoint is not rate limited; instead
    # the payload is served from the shared cache (one DB query per minute,
    # cleared whenever settings are saved in the dashboard).
    payload = cache.get(PUBLIC_SITE_SETTINGS_CACHE_KEY)
    if payload is None:
        settings = SiteSettings.objects.filter(key__in=SiteSettings.PUBLIC_SETTING_KEYS)
        payload = {'settings': {setting.key: setting.value for setting in settings}}
        cache.set(PUBLIC_SITE_SETTINGS_CACHE_KEY, payload, 60)
    response = JsonResponse(payload)
    # Short, so a dashboard edit reaches returning visitors within a minute.
    response['Cache-Control'] = 'public, max-age=30'
    return response


@require_POST
def contact_submit_api(request):
    try:
        if request.content_type == 'application/json':
            payload = json.loads(request.body.decode('utf-8') or '{}')
        else:
            payload = request.POST
    except json.JSONDecodeError:
        return api_error('Invalid request payload.')
    try:
        name = clean_text(payload, 'name', 200, required=True)
        company = clean_text(payload, 'company', 200)
        whatsapp = clean_text(payload, 'whatsapp', 50)
        email = clean_text(payload, 'email', 254, required=True).lower()
        specialization = clean_text(payload, 'specialization', 200)
        message = clean_text(payload, 'message', 5000, required=True)
        validate_email(email)
        validate_optional_phone_number(whatsapp)
    except ValidationError as exc:
        return api_error(' '.join(exc.messages))
    if not rate_limit(request, 'contact-submit-ip', limit=30, window=3600):
        return api_error('Too many requests. Please wait before submitting again.', 429)
    if not rate_limit(request, 'contact-submit-email', email, limit=8, window=3600):
        return api_error('Too many requests from this email. Please try again later.', 429)
    ContactSubmission.objects.create(
        name=name,
        company=company,
        whatsapp=whatsapp,
        email=email,
        specialization=specialization,
        message=message,
    )
    return JsonResponse({'success': True, 'message': 'Contact request submitted successfully.'}, status=201)


@newsletter_enabled_required
@require_POST
def newsletter_subscribe_api(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}') if request.content_type == 'application/json' else request.POST
    except json.JSONDecodeError:
        return api_error('Invalid request payload.')
    try:
        email = clean_text(payload, 'email', 254, required=True).lower()
        validate_email(email)
    except ValidationError as exc:
        return api_error(' '.join(exc.messages) if exc.messages else 'Please enter a valid email address.')
    if not rate_limit(request, 'newsletter-subscribe-ip', limit=20, window=3600):
        return api_error('Too many subscription attempts. Please try again later.', 429)
    if not rate_limit(request, 'newsletter-subscribe-email', email, limit=4, window=3600):
        return api_error('Too many attempts for this email. Please try again later.', 429)
    # Double opt-in (S-16): nobody is subscribed until they click the emailed
    # link, and the answer is the same whatever state the address is in.
    subscriber, created = NewsletterSubscriber.objects.get_or_create(email=email, defaults={'is_active': False})
    if subscriber.is_pending:
        send_newsletter_confirmation(subscriber)
    return JsonResponse({'success': True, 'message': NEWSLETTER_CHECK_INBOX}, status=202)


@newsletter_enabled_required
@require_POST
def newsletter_confirm_api(request):
    import hashlib
    from datetime import timedelta

    if not rate_limit(request, 'newsletter-confirm-ip', limit=30, window=3600):
        return api_error('Too many attempts. Please try again later.', 429)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}') if request.content_type == 'application/json' else request.POST
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}
    token = str(payload.get('token') or '').strip()[:200] if hasattr(payload, 'get') else ''
    subscriber = NewsletterSubscriber.objects.filter(
        confirmation_token_hash=hashlib.sha256(token.encode()).hexdigest(),
        confirmed_at__isnull=True,
    ).first() if token else None
    if not subscriber or not subscriber.confirmation_sent_at or subscriber.confirmation_sent_at < timezone.now() - timedelta(days=7):
        return api_error('This confirmation link is invalid or has expired. Subscribe again to get a new one.')
    subscriber.confirmed_at = timezone.now()
    subscriber.is_active = True
    subscriber.confirmation_token_hash = ''
    subscriber.save(update_fields=['confirmed_at', 'is_active', 'confirmation_token_hash'])
    return JsonResponse({'success': True, 'message': 'Thank you, your subscription to the ResRef newsletter is confirmed.'})


@require_GET
def fetch_reference_api(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'error': 'Please enter a DOI, DOI URL, website URL, or article title.'}, status=400)
    if len(query) > 1200:
        return JsonResponse({'error': 'Search text is too long. Use up to five short lines.'}, status=400)
    if not rate_limit(request, 'reference-lookup', limit=30, window=60):
        return JsonResponse({'error': 'Too many citation searches. Please wait a minute and try again.'}, status=429)
    source_type = request.GET.get('type', '').strip().lower()
    if source_type and source_type not in SOURCE_TYPES:
        return JsonResponse({'error': 'Unknown reference source type.'}, status=400)
    from usage import services as usage

    # Refuse before calling Crossref/OpenAlex when the allowance is already
    # used up; only a successful lookup is charged (T-12).
    refused = usage.precheck(request, 'reference_generator')
    if refused:
        return refused
    results = search_references(query, source_type)
    if not results:
        return JsonResponse({'error': 'No reference metadata was found. Try a DOI or add the source manually.'}, status=404)
    refused = usage.gate(request, 'reference_generator', 'reference_lookup')
    if refused:
        return refused
    primary = results[0]
    authors = ', '.join(
        f"{author.get('last', '')} {author.get('first', '')[:1]}.".strip()
        for author in primary.get('authors', [])
    ) or 'Unknown Author'
    return JsonResponse({
        'success': True,
        'results': results,
        'reference': primary,
        'title': primary.get('title', ''),
        'author': authors,
        'year': primary.get('year', ''),
        'journal': primary.get('journal', ''),
        'doi': primary.get('doi', ''),
        'usage': usage.usage_status(usage.subject_for(request), 'reference_generator'),
    })
