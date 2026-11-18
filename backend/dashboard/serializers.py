from django.contrib.auth.models import User

from accounts.entitlements import get_profile, serialize_entitlements
from blog.api_views import post_to_dict
from blog.models import Author, Category, MediaAsset, Post, Tag
from .models import (
    ContactSubmission,
    DashboardActivityLog,
    FAQCategory,
    FAQItem,
    JobApplication,
    JoinTeamEntry,
    NewsletterCampaign,
    NewsletterSubscriber,
    ResearchOpportunity,
    ServiceDefinition,
    ServiceRequest,
    SiteSettings,
)
from .permissions import get_dashboard_role, has_dashboard_access, permissions_for_user


def iso(value):
    return value.isoformat() if value else None


def _annotated_count(obj, attr, manager):
    """Use a Count() annotation from the list query when present (no N+1)."""
    value = getattr(obj, attr, None)
    return value if value is not None else manager.count()


def user_to_dict(user, features=None):
    team_member = getattr(user, 'team_member', None)
    profile = get_profile(user)
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'display_name': profile.display_name or user.get_full_name() or user.email or user.username,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'role': get_dashboard_role(user),
        'access_role': profile.access_role,
        'account_role': profile.account_role.code if profile.account_role_id else '',
        'tier': profile.effective_tier,
        'configured_tier': profile.tier,
        'plan': profile.plan.code if profile.plan_id else profile.tier,
        'premium_until': iso(profile.premium_until),
        'email_verified': profile.email_verified,
        'auth_provider': profile.auth_provider,
        'organization': profile.organization,
        'specialization': profile.specialization,
        'country': getattr(profile, 'country', '') or '',
        'phone_number': getattr(profile, 'phone_number', '') or '',
        'department': team_member.department if team_member else '',
        'team_role': team_member.role if team_member else '',
        'can_access_dashboard': has_dashboard_access(user),
        'permissions': permissions_for_user(user),
        'features': serialize_entitlements(profile, features),
        'date_joined': iso(user.date_joined),
        'last_login': iso(user.last_login),
    }


def contact_to_dict(item):
    return {
        'id': item.id,
        'name': item.name,
        'company': item.company,
        'whatsapp': item.whatsapp,
        'email': item.email,
        'specialization': item.specialization,
        'message': item.message,
        'status': item.status,
        'created_at': iso(item.created_at),
    }


def application_to_dict(item):
    return {
        'id': item.id,
        'full_name': item.full_name,
        'email': item.email,
        'whatsapp': item.whatsapp,
        'team': item.team,
        'experience': item.experience,
        'motivation': item.motivation,
        'portfolio': item.portfolio,
        'has_cv': bool(item.cv_file),
        'cv_url': f'/api/dashboard/applications/{item.id}/cv/' if item.cv_file else '',
        'status': item.status,
        'notes': item.notes,
        'created_at': iso(item.created_at),
    }


def category_to_dict(category):
    return {
        'id': category.id,
        'name': category.name,
        'description': category.description,
        'hero_image': category.hero_image,
        'slug': category.slug,
        'parent_id': category.parent_id,
        'show_in_database': category.show_in_database,
        'database_order': category.database_order,
        'usage_count': _annotated_count(category, 'usage_count_annotated', category.post_set),
    }


def team_member_to_dict(user):
    team_member = getattr(user, 'team_member', None)
    profile = get_profile(user)
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'display_name': profile.display_name or user.get_full_name() or user.email or user.username,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'role': team_member.role if team_member else get_dashboard_role(user),
        'department': team_member.department if team_member else '',
        'team_role': team_member.role if team_member else '',
        'date_joined': iso(user.date_joined),
    }


def tag_to_dict(tag):
    return {'id': tag.id, 'name': tag.name, 'slug': tag.slug, 'usage_count': _annotated_count(tag, 'usage_count_annotated', tag.post_set)}


def setting_to_dict(setting):
    return {'id': setting.id, 'key': setting.key, 'value': setting.value, 'label': setting.label, 'group': setting.group}


def author_to_dict(author):
    authored_count = _annotated_count(author, 'authored_count_annotated', author.authored_posts)
    primary_count = _annotated_count(author, 'primary_count_annotated', author.post_set)
    return {
        'id': author.id,
        'login': author.login,
        'display_name': author.display_name,
        'email': author.email,
        'role': author.role,
        'slug': author.slug,
        'prefix': author.prefix,
        'credentials': author.credentials,
        'position': author.position,
        'specialty': author.specialty,
        'institution': author.institution,
        'country': author.country,
        'bio': author.bio,
        'short_bio': author.short_bio,
        'avatar': author.avatar,
        'profile_media_id': author.profile_media_id,
        'profile_image': author.profile_media.source_url() if author.profile_media_id else author.avatar,
        'website': author.website,
        'orcid': author.orcid,
        'google_scholar': author.google_scholar,
        'researchgate': author.researchgate,
        'linkedin': author.linkedin,
        'twitter': author.twitter,
        'display_order': author.display_order,
        'is_active': author.is_active,
        'seo_title': author.seo_title,
        'seo_description': author.seo_description,
        'usage_count': max(primary_count, authored_count, _annotated_count(author, 'contributions_count_annotated', author.contributions)),
        'created_at': iso(author.created_at),
        'updated_at': iso(author.updated_at),
    }


def media_to_dict(asset, request=None):
    url = asset.source_url()
    if request and asset.file and url:
        url = request.build_absolute_uri(url)
    return {
        'id': asset.id,
        'title': asset.title,
        'alt_text': asset.alt_text,
        'caption': asset.caption,
        'url': url,
        'wordpress_id': asset.wordpress_id,
        'created_at': iso(asset.created_at),
    }


def activity_to_dict(item):
    actor_name = ''
    if item.actor_id:
        actor_name = item.actor.get_full_name() or item.actor.email or item.actor.username
    return {
        'id': item.id,
        'actor_id': item.actor_id,
        'actor': actor_name,
        'action': item.action,
        'module': item.module,
        'object_id': item.object_id,
        'object_label': item.object_label,
        'message': item.message,
        'metadata': item.metadata,
        'created_at': iso(item.created_at),
    }


def opportunity_to_dict(item):
    specialty = item.specialty if getattr(item, 'specialty_id', None) else None
    return {
        'id': item.id,
        'title': item.title,
        'slug': item.slug,
        'organization': item.organization,
        'opportunity_type': item.opportunity_type,
        'type': item.opportunity_type,
        'specialty': item.specialty_id,
        'specialty_name': specialty.name if specialty else item.category,
        'specialty_slug': specialty.slug if specialty else '',
        'summary': item.summary,
        'short_description': item.summary,
        'description': item.description,
        'full_description': item.description,
        'category': item.category,
        'status': item.status,
        'priority': item.priority,
        'location': item.location,
        'is_remote': item.is_remote,
        'eligibility': item.eligibility,
        'requirements': item.requirements or item.eligibility,
        'benefits': item.benefits,
        'custom_fields': item.custom_fields,
        'application_url': item.application_url,
        'contact_email': item.contact_email,
        'deadline': item.deadline.isoformat() if item.deadline else '',
        'is_featured': item.is_featured,
        'show_when_closed': item.show_when_closed,
        'assigned_to': item.assigned_to_id,
        'assigned_to_name': item.assigned_to.get_full_name() if item.assigned_to else '',
        'internal_notes': item.internal_notes,
        'seo_title': item.seo_title,
        'seo_description': item.seo_description,
        'created_at': iso(item.created_at),
        'updated_at': iso(item.updated_at),
    }


def join_team_entry_to_dict(item):
    return {
        'id': item.id,
        'title': item.title,
        'slug': item.slug,
        'description': item.description,
        'icon_key': item.icon_key,
        'action_label': item.action_label,
        'action_url': item.action_url,
        'status': item.status,
        'sort_order': item.sort_order,
        'seo_title': item.seo_title,
        'seo_description': item.seo_description,
        'created_at': iso(item.created_at),
        'updated_at': iso(item.updated_at),
    }


def faq_category_to_dict(item, include_counts=False):
    data = {
        'id': item.id,
        'name': item.name,
        'slug': item.slug,
        'sort_order': item.sort_order,
        'created_at': iso(item.created_at),
        'updated_at': iso(item.updated_at),
    }
    if include_counts:
        data['item_count'] = item.items.count()
        data['published_count'] = item.items.filter(status='published').count()
    return data


def faq_item_to_dict(item):
    return {
        'id': item.id,
        'category': item.category_id,
        'category_name': item.category.name if item.category_id else '',
        'question': item.question,
        'answer': item.answer,
        'status': item.status,
        'sort_order': item.sort_order,
        'created_at': iso(item.created_at),
        'updated_at': iso(item.updated_at),
    }


def service_to_dict(item):
    return {
        'id': item.id,
        'title': item.title,
        'slug': item.slug,
        'summary': item.summary,
        'description': item.description,
        'category': item.category,
        'status': item.status,
        'assigned_team': item.assigned_team,
        'price_note': item.price_note,
        'turnaround_time': item.turnaround_time,
        'intake_schema': item.intake_schema,
        'is_featured': item.is_featured,
        'internal_notes': item.internal_notes,
        'request_count': item.requests.count() if hasattr(item, 'requests') else 0,
        'created_at': iso(item.created_at),
        'updated_at': iso(item.updated_at),
    }


def service_request_to_dict(item):
    return {
        'id': item.id,
        'service': item.service_id,
        'service_title': item.service.title if item.service else '',
        'requester_name': item.requester_name,
        'requester_email': item.requester_email,
        'organization': item.organization,
        'subject': item.subject,
        'message': item.message,
        'status': item.status,
        'priority': item.priority,
        'assigned_to': item.assigned_to_id,
        'assigned_to_name': item.assigned_to.get_full_name() if item.assigned_to else '',
        'internal_notes': item.internal_notes,
        'created_at': iso(item.created_at),
        'updated_at': iso(item.updated_at),
    }


EXPORT_SERIALIZERS = {
    'users': (User.objects.all, user_to_dict),
    'posts': (lambda: Post.objects.select_related('author').prefetch_related('categories', 'tags', 'authors').all(), lambda item: post_to_dict(item, include_content=False, include_editor_meta=True)),
    'categories': (Category.objects.all, category_to_dict),
    'tags': (Tag.objects.all, tag_to_dict),
    'authors': (Author.objects.all, author_to_dict),
    'media': (MediaAsset.objects.all, media_to_dict),
    'contacts': (ContactSubmission.objects.all, contact_to_dict),
    'applications': (JobApplication.objects.all, application_to_dict),
    'join-team': (JoinTeamEntry.objects.all, join_team_entry_to_dict),
    'newsletter': (NewsletterSubscriber.objects.all, lambda item: {'id': item.id, 'email': item.email, 'is_active': item.is_active, 'confirmed': item.confirmed_at is not None, 'created_at': iso(item.created_at)}),
    'newsletter-campaigns': (NewsletterCampaign.objects.select_related('sent_by').all, lambda item: {
        'id': item.id,
        'subject': item.subject,
        'status': item.status,
        'recipient_count': item.recipient_count,
        'failed_count': item.failed_count,
        'sent_by': item.sent_by.email if item.sent_by_id else '',
        'sent_at': iso(item.sent_at),
        'created_at': iso(item.created_at),
    }),
    'opportunities': (ResearchOpportunity.objects.all, opportunity_to_dict),
    'faq-categories': (FAQCategory.objects.all, faq_category_to_dict),
    'faq-items': (FAQItem.objects.select_related('category').all, faq_item_to_dict),
    'services': (ServiceDefinition.objects.all, service_to_dict),
    'service-requests': (ServiceRequest.objects.select_related('service', 'assigned_to').all, service_request_to_dict),
    'activity': (DashboardActivityLog.objects.select_related('actor').all, activity_to_dict),
    'settings': (SiteSettings.objects.all, setting_to_dict),
}
