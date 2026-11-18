"""The public Team page and its dashboard manager. Every write here is for Super
Admins only, and nothing is public until a Super Admin publishes the page."""

from django.core.cache import cache
from django.core.exceptions import BadRequest
from django.core.validators import validate_email
from django.db.models import Max
from urllib.parse import urlsplit

from core.permissions import api_super_admin_required
from resref import seo

from .common import *
from ..models import TeamPageMember, TeamPageSection, TeamPageSettings

MAX_LINKS = 6


def photo_url(member, request):
    return media_to_dict(member.photo, request)['url'] if member.photo_id else ''


def member_to_dict(member, request):
    return {
        'id': member.id,
        'section_id': member.section_id,
        'full_name': member.full_name,
        'role': member.role,
        'department': member.department,
        'bio': member.bio,
        'vision': member.vision,
        'photo_id': member.photo_id,
        'photo_url': photo_url(member, request),
        'links': member.links,
        'status': member.status,
        'updated_at': member.updated_at.isoformat(),
    }


def section_to_dict(section, request):
    return {
        'id': section.id,
        'name': section.name,
        'description': section.description,
        'level': section.level,
        'is_visible': section.is_visible,
        'members': [member_to_dict(member, request) for member in section.members.all()],
    }


def settings_to_dict(page):
    return {
        'hero_title': page.hero_title,
        'hero_text': page.hero_text,
        'is_published': page.is_published,
        'published_at': page.published_at.isoformat() if page.published_at else None,
        'published_by': page.published_by.get_username() if page.published_by_id else '',
    }


def page_content(request, page, include_drafts=False):
    """What visitors get: visible sections holding at least one person, and
    only the fields the page shows."""
    sections = []
    for section in TeamPageSection.objects.filter(is_visible=True).prefetch_related('members__photo'):
        members = [member for member in section.members.all() if include_drafts or member.status == 'published']
        if not members:
            continue
        sections.append({
            'id': section.id,
            'name': section.name,
            'description': section.description,
            'level': section.level,
            'members': [{
                'id': member.id,
                'full_name': member.full_name,
                'role': member.role,
                'department': member.department,
                'bio': member.bio,
                'vision': member.vision if section.level == 'founder' else '',
                'photo_url': photo_url(member, request),
                'links': member.links,
                **({'is_draft': member.status == 'draft'} if include_drafts else {}),
            } for member in members],
        })
    return {'hero_title': page.hero_title, 'hero_text': page.hero_text, 'sections': sections}


def clean_links(raw):
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise BadRequest('Links must be a list.')
    links = []
    for item in raw:
        if not isinstance(item, dict):
            raise BadRequest('Each link needs a label and an address.')
        label = text_field(item, 'label', max_length=60)
        url = text_field(item, 'url', max_length=500)
        if not url and not label:
            continue
        if not url:
            raise BadRequest(f'Add an address for the link "{label}".')
        links.append({'label': label or 'Link', 'url': clean_link_url(url)})
    if len(links) > MAX_LINKS:
        raise BadRequest(f'A member can have up to {MAX_LINKS} links.')
    return links


def clean_link_url(url):
    parts = urlsplit(url)
    if parts.scheme == 'mailto':
        try:
            validate_email(url[len('mailto:'):])
        except ValidationError:
            raise BadRequest(f'"{url}" is not a valid email link.')
        return url
    if parts.scheme not in {'http', 'https'} or not parts.netloc:
        raise BadRequest(f'"{url}" must start with https:// or mailto:')
    return url


def ordered_ids(raw):
    # Whole lists are sent, so parse_id_list's limit of 12 does not apply here.
    return list(dict.fromkeys(filter(None, map(parse_int, raw)))) if isinstance(raw, list) else []


def next_position(queryset):
    return (queryset.aggregate(last=Max('sort_order'))['last'] or 0) + 1


@require_GET
@api_super_admin_required
def team_page_api(request):
    sections = TeamPageSection.objects.prefetch_related('members__photo')
    return JsonResponse({
        'settings': settings_to_dict(TeamPageSettings.load()),
        'sections': [section_to_dict(section, request) for section in sections],
        'levels': [{'id': code, 'label': label} for code, label in TeamPageSection.LEVELS],
    })


@require_POST
@api_super_admin_required
def save_team_page_settings_api(request):
    data = get_payload(request)
    page = TeamPageSettings.load()
    page.hero_title = text_field(data, 'hero_title', page.hero_title, 160) or 'Our Team'
    page.hero_text = text_field(data, 'hero_text', page.hero_text, 600)
    page.save()
    log_activity(request, 'team_page', 'update', 'Updated the Team page introduction', page)
    return JsonResponse({'success': True, 'settings': settings_to_dict(page)})


@require_POST
@api_super_admin_required
def publish_team_page_api(request):
    data = get_payload(request)
    if not isinstance(data.get('published'), bool):
        raise BadRequest('Please choose whether to publish or unpublish.')
    page = TeamPageSettings.load()
    if data['published']:
        if not page_content(request, page)['sections']:
            return error_response('Publish at least one member in a visible section first.')
        page.is_published, page.published_at, page.published_by = True, timezone.now(), request.user
    else:
        page.is_published = False
    page.save()
    # The cached sitemap must not list the page after it is taken down.
    cache.delete(f'seo:sitemap:{seo.site_url()}')
    action = 'Published' if page.is_published else 'Unpublished'
    log_activity(request, 'team_page', 'update', f'{action} the Team page', page)
    return JsonResponse({'success': True, 'settings': settings_to_dict(page)})


@require_GET
@api_super_admin_required
def preview_team_page_api(request):
    page = TeamPageSettings.load()
    include_drafts = parse_boolean(request.GET.get('drafts'))
    return JsonResponse({**page_content(request, page, include_drafts), 'is_published': page.is_published})


@require_GET
def public_team_page_api(request):
    page = TeamPageSettings.objects.filter(pk=1, is_published=True).first()
    if not page:
        return error_response('Page not found.', status=404)
    return JsonResponse(page_content(request, page))


@require_POST
@api_super_admin_required
def save_section_api(request, pk=None):
    data = get_payload(request)
    section = get_object_or_404(TeamPageSection, pk=pk) if pk else TeamPageSection()
    section.name = text_field(data, 'name', section.name, 120)
    if not section.name:
        return error_response('Please give the section a name.')
    section.description = text_field(data, 'description', section.description, 600)
    section.level = choice_field(data, 'level', section.level, TeamPageSection.LEVELS)
    if 'is_visible' in data:
        section.is_visible = parse_boolean(data.get('is_visible'))
    if not pk:
        section.sort_order = next_position(TeamPageSection.objects.all())
    section.save()
    log_activity(request, 'team_page', 'update' if pk else 'create', f'Saved Team page section: {section.name}', section)
    return JsonResponse({'success': True, 'section': {'id': section.id}})


@require_POST
@api_super_admin_required
def delete_section_api(request, pk):
    section = get_object_or_404(TeamPageSection, pk=pk)
    if section.members.exists():
        return error_response('Move or remove the members in this section first.')
    name = section.name
    section.delete()
    log_activity(request, 'team_page', 'delete', f'Deleted Team page section: {name}', metadata={'id': pk})
    return JsonResponse({'success': True})


@require_POST
@api_super_admin_required
def reorder_sections_api(request):
    ids = ordered_ids(get_payload(request).get('ids'))
    sections = TeamPageSection.objects.in_bulk(ids)
    if not sections:
        return error_response('Please send the sections in their new order.')
    for position, pk in enumerate((pk for pk in ids if pk in sections), start=1):
        sections[pk].sort_order = position
    TeamPageSection.objects.bulk_update(sections.values(), ['sort_order'])
    log_activity(request, 'team_page', 'update', f'Reordered {len(sections)} Team page sections')
    return JsonResponse({'success': True})


@require_POST
@api_super_admin_required
def save_member_api(request, pk=None):
    data = get_payload(request)
    member = get_object_or_404(TeamPageMember, pk=pk) if pk else TeamPageMember()
    member.full_name = text_field(data, 'full_name', member.full_name, 150)
    if not member.full_name:
        return error_response('Please enter a name. Everything else can wait while this is a draft.')

    section_id = id_field(data.get('section_id'), 'Section') if 'section_id' in data else member.section_id
    section = TeamPageSection.objects.filter(pk=section_id).first()
    if not section:
        return error_response('Please choose a section.')
    if member.section_id != section.id:
        member.sort_order = next_position(section.members.all())
    member.section = section

    member.role = text_field(data, 'role', member.role, 150)
    member.department = text_field(data, 'department', member.department, 120)
    member.bio = text_field(data, 'bio', member.bio, 2000)
    member.vision = text_field(data, 'vision', member.vision, 2000)
    member.status = choice_field(data, 'status', member.status, TeamPageMember.STATUS)
    if member.status == 'published' and not member.role:
        return error_response('Add a role before publishing this member, or save them as a draft.')
    if 'links' in data:
        member.links = clean_links(data.get('links'))
    if 'photo_id' in data:
        photo_id = id_field(data.get('photo_id'), 'Photo')
        if photo_id and not MediaAsset.objects.filter(pk=photo_id).exists():
            return error_response('That photo is no longer in the Media Library.')
        member.photo_id = photo_id
    member.save()
    log_activity(request, 'team_page', 'update' if pk else 'create', f'Saved Team page member: {member.full_name}', member)
    return JsonResponse({'success': True, 'member': member_to_dict(member, request)})


@require_POST
@api_super_admin_required
def delete_member_api(request, pk):
    member = get_object_or_404(TeamPageMember, pk=pk)
    name = member.full_name
    member.delete()
    log_activity(request, 'team_page', 'delete', f'Removed Team page member: {name}', metadata={'id': pk})
    return JsonResponse({'success': True})


@require_POST
@api_super_admin_required
def arrange_members_api(request):
    """Sets one section's full member list, which also moves anyone arriving from another section."""
    data = get_payload(request)
    section = TeamPageSection.objects.filter(pk=id_field(data.get('section_id'), 'Section')).first()
    if not section:
        return error_response('Please choose a section.')
    ids = ordered_ids(data.get('ids'))
    members = TeamPageMember.objects.in_bulk(ids)
    for position, pk in enumerate((pk for pk in ids if pk in members), start=1):
        members[pk].section = section
        members[pk].sort_order = position
    TeamPageMember.objects.bulk_update(members.values(), ['section', 'sort_order'])
    log_activity(request, 'team_page', 'update', f'Arranged the members of {section.name}', section)
    return JsonResponse({'success': True})
