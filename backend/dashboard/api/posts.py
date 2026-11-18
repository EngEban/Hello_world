from pathlib import Path

from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Case, IntegerField, Max, When

from blog.seo_analysis import SETTINGS_KEY, cached_reports, clean_seo_settings
from resref.indexnow import notify_posts

from .common import *
from .seo import REFRESH_BATCH, is_score_need, optimization_summary, report_matches, valid_score_need

ALLOWED_PDF_TYPES = {'application/pdf', 'application/x-pdf'}
MAX_PDF_UPLOAD_SIZE = 12 * 1024 * 1024
validate_http_url = URLValidator(schemes=['http', 'https'])


def parse_id_list(value):
    if not isinstance(value, (list, tuple)):
        return []
    ids = []
    for item in value:
        parsed = parse_int(item)
        if parsed and parsed not in ids:
            ids.append(parsed)
    return ids[:12]


def parse_contributors(value):
    if not isinstance(value, list):
        return None
    if len(value) > 12:
        raise ValidationError('An article can have up to 12 contributor credits.')
    allowed_roles = {choice[0] for choice in PostContributor.ROLE_CHOICES}
    result, seen = [], set()
    for position, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValidationError('Each contributor credit must be an object.')
        contributor_id = parse_int(item.get('contributor_id'))
        role = str(item.get('role') or PostContributor.ROLE_AUTHOR).strip()
        if not contributor_id or role not in allowed_roles:
            raise ValidationError('Choose a valid contributor and contribution role.')
        key = (contributor_id, role)
        if key in seen:
            raise ValidationError('The same contributor cannot have the same role twice on an article.')
        seen.add(key)
        note = str(item.get('contribution_note') or '').strip()
        if len(note) > 2000:
            raise ValidationError('A contribution note must be 2,000 characters or fewer.')
        result.append({'contributor_id': contributor_id, 'role': role, 'display_order': position, 'contribution_note': note})
    active_ids = set(Author.objects.filter(id__in=[item['contributor_id'] for item in result], is_active=True).values_list('id', flat=True))
    if len(active_ids) != len({item['contributor_id'] for item in result}):
        raise ValidationError('Inactive or missing contributors cannot be assigned to an article.')
    return result


def validate_uploaded_pdf(uploaded_file):
    if uploaded_file.size > MAX_PDF_UPLOAD_SIZE:
        return 'PDF uploads must be smaller than 12 MB.'
    extension = Path(uploaded_file.name or '').suffix.lower()
    if extension != '.pdf':
        return 'Upload a PDF file.'
    if (uploaded_file.content_type or '').lower() not in ALLOWED_PDF_TYPES:
        return 'Upload a valid PDF file.'
    uploaded_file.seek(0)
    header = uploaded_file.read(5)
    uploaded_file.seek(0)
    if header != b'%PDF-':
        return 'The uploaded file is not a valid PDF.'
    return ''

@require_GET
@api_permission_required('content.view')
def dashboard_posts_api(request):
    q = request.GET.get('q', '')
    ptype = request.GET.get('type', 'post')
    qs = Post.objects.filter(post_type=ptype).select_related('author').prefetch_related('categories', 'tags', 'authors', 'contributor_assignments__contributor')
    now = timezone.now()
    summary = qs.aggregate(
        total=Count('id', filter=~Q(status='trash')), published=Count('id', filter=Q(status='publish', published_at__lte=now)),
        scheduled=Count('id', filter=Q(status='publish', published_at__gt=now)),
        draft=Count('id', filter=Q(status='draft')), pending=Count('id', filter=Q(status='pending')),
        private=Count('id', filter=Q(status='private')), trash=Count('id', filter=Q(status='trash')),
    )
    status = request.GET.get('status')
    if status == 'scheduled':
        qs = qs.filter(status='publish', published_at__gt=now)
    elif status == 'publish':
        qs = qs.filter(status='publish', published_at__lte=now)
    elif status:
        qs = qs.filter(status=status)
    else:
        qs = qs.exclude(status='trash')
    if request.GET.get('category'):
        qs = qs.filter(categories__id=parse_int(request.GET.get('category')))
    if request.GET.get('tag'):
        qs = qs.filter(tags__id=parse_int(request.GET.get('tag')))
    if request.GET.get('author'):
        author_id = parse_int(request.GET.get('author'))
        qs = qs.filter(Q(author_id=author_id) | Q(authors__id=author_id) | Q(contributor_assignments__contributor_id=author_id))
    if request.GET.get('featured') == 'true':
        qs = qs.filter(design_settings__is_featured=True)
    if request.GET.get('id'):
        qs = qs.filter(pk=parse_int(request.GET['id']))
    if request.GET.get('needs') == 'seo':
        qs = qs.filter(Q(seo_title='') | Q(seo_description=''))
    elif request.GET.get('needs') == 'image':
        qs = qs.filter(featured_image='')
    elif request.GET.get('needs') == 'contributors':
        qs = qs.filter(authors__isnull=True, contributor_assignments__isnull=True)
    elif request.GET.get('needs') == 'excerpt':
        qs = qs.filter(excerpt='')
    elif request.GET.get('needs') == 'category':
        qs = qs.filter(categories__isnull=True)
    need = request.GET.get('needs', '')
    if is_score_need(need) and not valid_score_need(need):
        return error_response('Unknown optimization check.')
    for field, lookup in [('date_from', 'updated_at__date__gte'), ('date_to', 'updated_at__date__lte')]:
        if request.GET.get(field):
            try:
                value = parse_date(request.GET[field])
            except ValueError:
                value = None
            if not value:
                return error_response('Enter a valid date filter.')
            qs = qs.filter(**{lookup: value})
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(content__icontains=q) | Q(excerpt__icontains=q))
    ordering = {'updated': '-updated_at', 'published': '-published_at', 'oldest': 'published_at', 'title': 'title', 'scheduled': 'published_at'}
    full_content = request.GET.get('summary_only') != 'true' or bool(request.GET.get('id'))
    sort = request.GET.get('sort')
    qs = qs.order_by(ordering.get(sort, '-updated_at'), '-id').distinct()
    pending = 0
    if is_score_need(need) or sort in {'score', 'score_desc'}:
        # Scores are not database columns: filter and sort on cached reports.
        reports, pending = cached_reports(qs, budget=REFRESH_BATCH)
        ids = [pk for pk in qs.values_list('pk', flat=True) if pk in reports and (not need or not is_score_need(need) or report_matches(reports[pk], need))]
        if sort in {'score', 'score_desc'}:
            ids.sort(key=lambda pk: reports[pk]['scores']['overall'] if reports[pk]['scores']['overall'] is not None else 101, reverse=sort == 'score_desc')
        qs = Post.objects.filter(pk__in=ids).select_related('author').prefetch_related('categories', 'tags', 'authors', 'contributor_assignments__contributor').order_by(
            Case(*[When(pk=pk, then=index) for index, pk in enumerate(ids)], output_field=IntegerField())) if ids else qs.none()
    page_ids = paginate(qs.values_list('pk', flat=True), request, lambda pk: pk)['results']
    row_reports, _rest = cached_reports(Post.objects.filter(pk__in=page_ids))

    def row(post):
        data = post_to_dict(post, include_content=full_content, include_editor_meta=full_content, request=request)
        data['optimization'] = optimization_summary(row_reports.get(post.pk))
        return data

    payload = paginate(qs, request, row)
    payload['summary'] = summary
    if not request.GET.get('id'):
        # Counts behind the library's "Needs attention" shortcuts. They use the
        # same rules as the needs= filters and ignore trashed records.
        base = Post.objects.filter(post_type=ptype).exclude(status='trash')
        payload['attention'] = {
            'seo': base.filter(Q(seo_title='') | Q(seo_description='')).count(),
            'image': base.filter(featured_image='').count(),
            'excerpt': base.filter(excerpt='').count(),
            'category': base.filter(categories__isnull=True).distinct().count(),
            'contributors': base.filter(authors__isnull=True, contributor_assignments__isnull=True).distinct().count(),
        }
        base_reports, base_pending = cached_reports(base, budget=REFRESH_BATCH)
        payload['attention']['keyphrase'] = sum(1 for report in base_reports.values() if report_matches(report, 'keyphrase'))
        payload['attention']['low_score'] = sum(1 for report in base_reports.values() if report_matches(report, 'low_score'))
        pending = max(pending, base_pending)
    payload['optimization_pending'] = pending
    return JsonResponse(payload)


@require_POST
@api_permission_required('content.manage')
@transaction.atomic
def bulk_posts_api(request):
    """Explicit, bounded operations; never hard-delete or infer authorship."""
    data = get_payload(request)
    if not isinstance(data, dict):
        return error_response('The request must be a JSON object.')
    ids = data.get('ids')
    if not isinstance(ids, list) or not ids or len(ids) > 100 or any(type(pk) is not int or pk <= 0 for pk in ids):
        return error_response('Select between 1 and 100 valid content records.')
    action = data.get('action')
    allowed = {'draft', 'pending', 'private', 'trash', 'restore', 'publish', 'schedule', 'feature', 'unfeature', 'duplicate'}
    if action not in allowed:
        return error_response('Unknown content action.')
    if action == 'trash' and not has_dashboard_permission(request.user, 'content.delete'):
        return error_response('Content delete permission is required to move items to trash.', 403)
    if action == 'duplicate' and len(ids) != 1:
        return error_response('Duplicate one article at a time.')
    selected = list(Post.objects.select_for_update().filter(pk__in=ids))
    if len(selected) != len(set(ids)):
        return error_response('Some selected records no longer exist. Refresh the list.', 409)
    now = timezone.now()
    scheduled = None
    if action == 'schedule':
        try:
            scheduled = parse_datetime(str(data.get('published_at') or ''))
        except ValueError:
            scheduled = None
        if scheduled and timezone.is_naive(scheduled):
            scheduled = timezone.make_aware(scheduled)
        if not scheduled or scheduled <= now:
            return error_response('Choose a publication date and time in the future.')
    if action in {'publish', 'schedule'} and any(not p.title.strip() or not p.slug or not p.content.strip() for p in selected):
        return error_response('Every article needs a title, slug and content before publication.')
    created = None
    for post in selected:
        if action == 'duplicate':
            base = f'{post.slug[:465]}-copy'
            slug, index = base, 2
            while Post.objects.filter(slug=slug).exists():
                slug, index = f'{base}-{index}', index + 1
            created = Post.objects.create(
                title=f'{post.title[:493]} (copy)', slug=slug, post_type=post.post_type, status='draft',
                content=post.content, excerpt=post.excerpt, featured_image=post.featured_image,
                seo_title=post.seo_title, seo_description=post.seo_description,
                design_settings={**post.design_settings, 'is_featured': False},
            )
            # No shared uploaded PDF file reference: removing a copy must never delete the original file.
            created.categories.set(post.categories.all())
            created.tags.set(post.tags.all())
            created.authors.set(post.authors.all())
            created.author = post.author
            created.save(update_fields=['author'])
            PostContributor.objects.bulk_create([
                PostContributor(post=created, contributor=credit.contributor, role=credit.role,
                                display_order=credit.display_order, contribution_note=credit.contribution_note)
                for credit in post.contributor_assignments.all()
            ])
        else:
            if action in {'feature', 'unfeature'}:
                post.design_settings = {**post.design_settings, 'is_featured': action == 'feature'}
            else:
                post.status = 'draft' if action == 'restore' else 'publish' if action in {'publish', 'schedule'} else action
                if action in {'publish', 'schedule'}:
                    post.published_at = scheduled if action == 'schedule' else (post.published_at if post.published_at and post.published_at <= now else now)
            post.save(update_fields=['status', 'published_at', 'design_settings', 'updated_at'])
        log_activity(request, 'content', 'create' if created else 'update', f'{action.capitalize()}: {post.title}', created or post, metadata={'action': action, 'source_id': post.pk})
    notify_posts(selected)
    result = {'success': True, 'updated': len(selected)}
    if created:
        result['post'] = post_to_dict(created, include_content=True, include_editor_meta=True, request=request)
    return JsonResponse(result)

@require_POST
@api_save_permission_required('content')
@transaction.atomic
def save_post_api(request, pk=None):
    data = get_payload(request)
    # New content starts as a draft unless the editor says otherwise.
    post = get_object_or_404(Post.objects.select_for_update(), pk=pk) if pk else Post(published_at=timezone.now(), status='draft')
    # Moving content to Trash needs content.delete, as in bulk_posts_api;
    # the editor's status field must not be a way around that check.
    if data.get('status') == 'trash' and post.status != 'trash' and not has_dashboard_permission(request.user, 'content.delete'):
        return error_response('Content delete permission is required to move items to trash.', 403)
    if pk and data.get('expected_updated_at') and data['expected_updated_at'] != post.updated_at.isoformat():
        return error_response('This article was changed by another editor. Reopen the latest version before saving.', 409)
    post.title = text_field(data, 'title', post.title)
    post.slug = text_field(data, 'slug', post.slug) or slugify(post.title)
    post.content = text_field(data, 'content', post.content)
    post.excerpt = text_field(data, 'excerpt', post.excerpt)
    post.post_type = data.get('post_type', post.post_type or 'post')
    post.status = data.get('status', post.status)
    post.featured_image = text_field(data, 'featured_image', post.featured_image)
    post.pdf_title = text_field(data, 'pdf_title', post.pdf_title, 255)
    post.seo_title = text_field(data, 'seo_title', post.seo_title)
    post.seo_description = text_field(data, 'seo_description', post.seo_description)
    if 'design_settings' in data:
        # design_settings['seo'] holds the SEO settings; only seo_settings may change them.
        previous = post.design_settings if isinstance(post.design_settings, dict) else {}
        incoming = dict(data['design_settings']) if isinstance(data['design_settings'], dict) else {}
        incoming.pop(SETTINGS_KEY, None)
        if SETTINGS_KEY in previous:
            incoming[SETTINGS_KEY] = previous[SETTINGS_KEY]
        post.design_settings = incoming
    if 'seo_settings' in data:
        post.design_settings = {**(post.design_settings if isinstance(post.design_settings, dict) else {}), SETTINGS_KEY: clean_seo_settings(data['seo_settings'])}
    if not post.title:
        return error_response('Title is required.')
    if not post.slug:
        return error_response('Please enter a title or slug.')
    if post.post_type not in dict(Post.POST_TYPES):
        return error_response('Content type must be post or page.')
    if post.status not in dict(Post.STATUSES):
        return error_response('Unknown publication status.')
    if Post.objects.exclude(pk=post.pk).filter(slug=post.slug).exists():
        return error_response('This slug is already used by another post or page.')
    # A dashboard user can explicitly publish immediately.  Use server time so
    # a browser's locale or clock cannot accidentally schedule the article.
    if parse_boolean(data.get('publish_now'), False):
        post.status = 'publish'
        post.published_at = timezone.now()
    elif 'published_at' in data:
        published_at = parse_datetime(data.get('published_at', '')) if data.get('published_at') else None
        if data.get('published_at') and not published_at:
            return error_response('Publication date is not valid.')
        post.published_at = timezone.make_aware(published_at) if published_at and timezone.is_naive(published_at) else published_at
    if post.status == 'publish' and not post.published_at:
        post.published_at = timezone.now()
    if 'author_id' in data:
        author_id = id_field(data.get('author_id'), 'author_id')
        post.author = Author.objects.filter(pk=author_id).first() if author_id else None
    author_ids = parse_id_list(data.get('author_ids', []))
    try:
        contributors = parse_contributors(data['contributors']) if 'contributors' in data else None
    except ValidationError as exc:
        return error_response(' '.join(exc.messages))
    with transaction.atomic():
        post.save()
        # The structured relationship is canonical.  Keep the old M2M in sync
        # so existing exports, legacy clients, and gradually migrated records
        # continue to work without duplicating profile data in a post.
        if contributors is not None:
            PostContributor.objects.filter(post=post).delete()
            PostContributor.objects.bulk_create([PostContributor(post=post, **item) for item in contributors])
            post.authors.set(Author.objects.filter(pk__in=[item['contributor_id'] for item in contributors]))
        elif 'author_ids' in data:
            post.authors.set(Author.objects.filter(pk__in=author_ids))
            PostContributor.objects.filter(post=post).delete()
            PostContributor.objects.bulk_create([
                PostContributor(post=post, contributor_id=author_id, role=PostContributor.ROLE_AUTHOR, display_order=index)
                for index, author_id in enumerate(author_ids)
            ])
        if 'categories' in data:
            post.categories.set(Category.objects.filter(pk__in=parse_id_list(data.get('categories', []))))
        if 'tags' in data:
            post.tags.set(Tag.objects.filter(pk__in=parse_id_list(data.get('tags', []))))
    log_activity(request, 'content', 'update' if pk else 'create', f'Saved content: {post.title}', post)
    notify_posts([post])
    return JsonResponse({'success': True, 'post': post_to_dict(post, include_content=True, include_editor_meta=True, request=request)})


@require_POST
@api_permission_required('content.edit')
def upload_post_pdf_api(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if parse_boolean(request.POST.get('remove'), False):
        if post.pdf_file:
            post.pdf_file.delete(save=False)
        post.pdf_file = None
        post.pdf_title = ''
        post.save(update_fields=['pdf_file', 'pdf_title', 'updated_at'])
        log_activity(request, 'content', 'update', f'Removed PDF attachment: {post.title}', post)
        return JsonResponse({'success': True, 'post': post_to_dict(post, include_content=True, include_editor_meta=True, request=request)})

    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return error_response('Choose a PDF file to upload.')
    upload_error = validate_uploaded_pdf(uploaded_file)
    if upload_error:
        return error_response(upload_error)
    if post.pdf_file:
        post.pdf_file.delete(save=False)
    title = request.POST.get('title', '').strip()[:255] or Path(uploaded_file.name).stem[:255] or 'Article PDF'
    post.pdf_file = uploaded_file
    post.pdf_title = title
    post.save(update_fields=['pdf_file', 'pdf_title', 'updated_at'])
    log_activity(request, 'content', 'update', f'Uploaded PDF attachment: {post.title}', post)
    return JsonResponse({'success': True, 'post': post_to_dict(post, include_content=True, include_editor_meta=True, request=request)})

@require_POST
@api_permission_required('content.delete')
def delete_post_api(request, pk):
    post = get_object_or_404(Post, pk=pk)
    # Permanent deletion is the last step after Trash, never a shortcut past it.
    if post.status != 'trash':
        return error_response('Move this content to Trash before deleting it permanently.', 409)
    title = post.title
    post.delete()
    log_activity(request, 'content', 'delete', f'Deleted content: {title}', metadata={'id': pk})
    return JsonResponse({'success': True})

@require_GET
@api_permission_required('taxonomy.view')
def categories_api(request):
    categories = Category.objects.select_related('parent').annotate(usage_count_annotated=Count('post', distinct=True)).order_by('database_order', 'name')
    return JsonResponse({'results': [category_to_dict(category) for category in categories]})

@require_POST
@api_save_permission_required('taxonomy')
def save_category_api(request, pk=None):
    data = get_payload(request)
    category = get_object_or_404(Category, pk=pk) if pk else Category()
    category.name = text_field(data, 'name', category.name)
    category.description = text_field(data, 'description', category.description)
    category.hero_image = text_field(data, 'hero_image', category.hero_image)
    if category.hero_image:
        try:
            validate_http_url(category.hero_image)
        except ValidationError:
            return error_response('Category hero image must be an http:// or https:// image URL.')
    category.slug = text_field(data, 'slug', category.slug) or slugify(category.name)
    category.show_in_database = parse_boolean(data.get('show_in_database'), category.show_in_database if category.pk else True)
    category.database_order = max(parse_int(data.get('database_order'), category.database_order if category.pk else 0) or 0, 0)
    parent_id = data.get('parent_id')
    if not category.name:
        return error_response('Category name is required.')
    if not category.slug:
        return error_response('Please enter a category name or slug.')
    if Category.objects.exclude(pk=category.pk).filter(slug=category.slug).exists():
        return error_response('This category slug is already in use.')
    parent = Category.objects.filter(pk=parent_id).first() if parent_id else None
    if category.pk and parent:
        ancestor = parent
        seen = set()
        while ancestor and ancestor.pk not in seen:
            if ancestor.pk == category.pk:
                return error_response('A category cannot be assigned to one of its own subcategories.')
            seen.add(ancestor.pk)
            ancestor = ancestor.parent
    category.parent = parent
    if not category.pk and not category.database_order:
        # A new category joins the end of its group instead of jumping to the top.
        last = Category.objects.filter(parent=parent).aggregate(last=Max('database_order'))['last'] or 0
        category.database_order = last + 1
    category.save()
    log_activity(request, 'content', 'update' if pk else 'create', f'Saved category: {category.name}', category)
    return JsonResponse({'success': True, 'category': category_to_dict(category)})

@require_POST
@api_permission_required('taxonomy.edit')
def reorder_categories_api(request):
    # Every category is sent, so parse_id_list's limit of 12 does not apply here.
    raw_ids = get_payload(request).get('ids')
    ids = list(dict.fromkeys(filter(None, map(parse_int, raw_ids)))) if isinstance(raw_ids, list) else []
    categories = {category.pk: category for category in Category.objects.filter(pk__in=ids)}
    if not categories:
        return error_response('Please send the categories in their new order.')
    # Positions count separately inside each parent.
    positions = {}
    for pk in ids:
        category = categories.get(pk)
        if category:
            positions[category.parent_id] = positions.get(category.parent_id, 0) + 1
            category.database_order = positions[category.parent_id]
    Category.objects.bulk_update(categories.values(), ['database_order'])
    log_activity(request, 'content', 'update', f'Reordered {len(categories)} categories', metadata={'count': len(categories)})
    return JsonResponse({'success': True})

@require_POST
@api_permission_required('taxonomy.delete')
def delete_category_api(request, pk):
    category = get_object_or_404(Category, pk=pk)
    name = category.name
    category.delete()
    log_activity(request, 'content', 'delete', f'Deleted category: {name}', metadata={'id': pk})
    return JsonResponse({'success': True})

@require_GET
@api_permission_required('taxonomy.view')
def tags_api(request):
    tags = Tag.objects.annotate(usage_count_annotated=Count('post', distinct=True)).order_by('name')
    return JsonResponse({'results': [tag_to_dict(tag) for tag in tags]})

@require_POST
@api_save_permission_required('taxonomy')
def save_tag_api(request, pk=None):
    data = get_payload(request)
    tag = get_object_or_404(Tag, pk=pk) if pk else Tag()
    tag.name = text_field(data, 'name', tag.name)
    tag.slug = text_field(data, 'slug', tag.slug) or slugify(tag.name)
    if not tag.name:
        return error_response('Tag name is required.')
    if not tag.slug:
        return error_response('Please enter a tag name or slug.')
    if Tag.objects.exclude(pk=tag.pk).filter(slug=tag.slug).exists():
        return error_response('This tag slug is already in use.')
    tag.save()
    log_activity(request, 'content', 'update' if pk else 'create', f'Saved tag: {tag.name}', tag)
    return JsonResponse({'success': True, 'tag': tag_to_dict(tag)})

@require_POST
@api_permission_required('taxonomy.delete')
def delete_tag_api(request, pk):
    tag = get_object_or_404(Tag, pk=pk)
    name = tag.name
    tag.delete()
    log_activity(request, 'content', 'delete', f'Deleted tag: {name}', metadata={'id': pk})
    return JsonResponse({'success': True})

@require_GET
@api_permission_required('taxonomy.view')
def authors_api(request):
    authors = Author.objects.select_related('profile_media').annotate(
        primary_count_annotated=Count('post', distinct=True),
        authored_count_annotated=Count('authored_posts', distinct=True),
        contributions_count_annotated=Count('contributions', distinct=True),
    ).order_by('display_order', 'display_name', 'login')
    q = request.GET.get('q', '').strip()
    if q:
        authors = authors.filter(Q(display_name__icontains=q) | Q(login__icontains=q) | Q(institution__icontains=q) | Q(specialty__icontains=q))
    if request.GET.get('active') in {'true', 'false'}:
        authors = authors.filter(is_active=request.GET['active'] == 'true')
    return JsonResponse({'results': [author_to_dict(author) for author in authors]})

@require_POST
@api_save_permission_required('taxonomy')
def save_author_api(request, pk=None):
    data = get_payload(request)
    author = get_object_or_404(Author, pk=pk) if pk else Author()
    # This is a content profile key, never an authentication account.
    author.login = text_field(data, 'login', author.login) or author.login or slugify(text_field(data, 'slug') or text_field(data, 'display_name'))[:100]
    author.display_name = text_field(data, 'display_name', author.display_name)
    author.email = text_field(data, 'email', author.email)
    author.role = text_field(data, 'role', author.role, 120)
    author.bio = text_field(data, 'bio', author.bio)
    author.short_bio = text_field(data, 'short_bio', author.short_bio)
    author.slug = text_field(data, 'slug', author.slug) or slugify(author.display_name)
    author.prefix = text_field(data, 'prefix', author.prefix, 40)
    author.credentials = text_field(data, 'credentials', author.credentials, 160)
    author.position = text_field(data, 'position', author.position, 200)
    author.specialty = text_field(data, 'specialty', author.specialty, 200)
    author.institution = text_field(data, 'institution', author.institution, 250)
    author.country = text_field(data, 'country', author.country, 120)
    author.display_order = max(parse_int(data.get('display_order'), author.display_order if author.pk else 0) or 0, 0)
    author.is_active = parse_boolean(data.get('is_active'), author.is_active if author.pk else True)
    author.seo_title = text_field(data, 'seo_title', author.seo_title, 500)
    author.seo_description = text_field(data, 'seo_description', author.seo_description)
    author.avatar = text_field(data, 'avatar', author.avatar)
    author.website = text_field(data, 'website', author.website)
    author.linkedin = text_field(data, 'linkedin', author.linkedin)
    author.twitter = text_field(data, 'twitter', author.twitter)
    author.orcid = text_field(data, 'orcid', author.orcid)
    author.google_scholar = text_field(data, 'google_scholar', author.google_scholar)
    author.researchgate = text_field(data, 'researchgate', author.researchgate)
    if 'profile_media_id' in data:
        profile_media_id = id_field(data.get('profile_media_id'), 'profile_media_id')
        author.profile_media = MediaAsset.objects.filter(pk=profile_media_id).first() if profile_media_id else None
    if not author.login:
        return error_response('Author login is required.')
    if not author.display_name:
        return error_response('Author display name is required.')
    if Author.objects.exclude(pk=author.pk).filter(login=author.login).exists():
        return error_response('This author login is already in use.')
    if not author.slug:
        return error_response('Please enter a contributor name or slug.')
    if Author.objects.exclude(pk=author.pk).filter(slug=author.slug).exists():
        return error_response('This contributor URL slug is already in use.')
    for field, label in (
        ('avatar', 'Avatar URL'),
        ('website', 'Website URL'),
        ('linkedin', 'LinkedIn URL'),
        ('twitter', 'X profile URL'),
        ('orcid', 'ORCID URL'),
        ('google_scholar', 'Google Scholar URL'),
        ('researchgate', 'ResearchGate URL'),
    ):
        value = getattr(author, field)
        if not value:
            continue
        try:
            validate_http_url(value)
        except ValidationError:
            return error_response(f'{label} must start with http:// or https://.')
    try:
        author.full_clean(exclude=['wordpress_id'])
    except ValidationError as exc:
        return error_response(' '.join(exc.messages))
    author.save()
    log_activity(request, 'content', 'update' if pk else 'create', f'Saved author: {author.display_name}', author)
    return JsonResponse({'success': True, 'author': author_to_dict(author)})

@require_POST
@api_permission_required('taxonomy.delete')
def delete_author_api(request, pk):
    author = get_object_or_404(Author, pk=pk)
    contribution_count = author.contributions.count()
    legacy_count = author.post_set.count() + author.authored_posts.count()
    if contribution_count or legacy_count:
        return error_response('This contributor is assigned to existing content. Remove the article credits first, or deactivate the profile instead.')
    name = author.display_name
    author.delete()
    log_activity(request, 'content', 'delete', f'Deleted author: {name}', metadata={'id': pk})
    return JsonResponse({'success': True})
