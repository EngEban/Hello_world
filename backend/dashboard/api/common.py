import csv
import json
import logging
from datetime import timedelta
from functools import wraps


logger = logging.getLogger(__name__)

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import BadRequest, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from accounts.entitlements import get_profile
# Shared helpers live in core/; re-exported here because every dashboard API
# module does `from .common import *`.
from core.errors import error_response
from core.pagination import MAX_PER_PAGE, apply_common_filters, paginate
from core.payload import choice_field, get_payload, id_field, parse_boolean, parse_int, text_field
from core.permissions import api_login_required, api_permission_required, api_save_permission_required
from accounts.security import client_ip as get_client_ip
from blog.api_views import post_to_dict
from blog.models import Author, Category, MediaAsset, Post, PostContributor, Tag
from ..models import (
    ContactSubmission,
    DashboardActivityLog,
    JobApplication,
    JoinTeamEntry,
    NewsletterCampaign,
    NewsletterSubscriber,
    ResearchOpportunity,
    ServiceDefinition,
    ServiceRequest,
    SiteSettings,
    TeamMember,
)
from ..permissions import (
    DASHBOARD_MODULES,
    ROLE_PERMISSIONS,
    get_dashboard_role,
    has_dashboard_access,
    has_dashboard_permission,
    is_super_admin,
    module_registry_for_user,
    permissions_for_user,
)
from ..serializers import (
    EXPORT_SERIALIZERS,
    activity_to_dict,
    application_to_dict,
    author_to_dict,
    category_to_dict,
    contact_to_dict,
    join_team_entry_to_dict,
    media_to_dict,
    opportunity_to_dict,
    service_request_to_dict,
    service_to_dict,
    setting_to_dict,
    tag_to_dict,
    team_member_to_dict,
    user_to_dict,
)


def log_activity(request, module, action, message, obj=None, metadata=None):
    try:
        DashboardActivityLog.objects.create(
            actor=request.user if request.user.is_authenticated else None,
            action=action,
            module=module,
            object_id=str(getattr(obj, 'pk', '') or ''),
            object_label=str(obj or '')[:255],
            message=message[:500],
            metadata=metadata or {},
            ip_address=get_client_ip(request),
            user_agent=(request.META.get('HTTP_USER_AGENT', '') or '')[:500],
        )
    except Exception:
        logger.exception('Audit log write failed (non-blocking)')


