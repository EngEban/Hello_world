from .common import *
from django.core.validators import validate_email
from accounts.entitlements import active_features
from accounts.identity import find_user_by_identifier, normalize_email
from accounts.models import AccountRole, MembershipProfile, SubscriptionPlan
from accounts.passwords import PASSWORD_REUSE_MESSAGE, password_was_used, set_password_with_history
from ..permissions import clear_role_cache, dashboard_role_q, prime_permissions, role_rows_by_code


def _text(data, key, fallback='', max_length=150):
    value = data.get(key, fallback)
    value = str(value or '').strip()
    return value[:max_length]


class _Reject(Exception):
    """Raised inside a transaction so every rejected save rolls back fully."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def _is_super_admin(user):
    if not user or not user.pk:
        return False
    if user.is_superuser:
        return True
    profile = get_profile(user)
    return bool(profile.account_role_id and profile.account_role.is_active and profile.account_role.is_super_admin)


def _can_manage_super_admin(request):
    return _is_super_admin(request.user)


def _privilege_level(user):
    """3 = super admin, 2 = dashboard admin, 1 = other dashboard roles, 0 = member/new."""
    if not user or not user.pk:
        return 0
    if _is_super_admin(user):
        return 3
    role = get_dashboard_role(user)
    if role == 'admin':
        return 2
    if role not in {'member', 'anonymous'}:
        return 1
    return 0


def _sensitive_changes(existing, data, email, username):
    """True when the payload would change identity or access of `existing`.

    The dashboard editor always sends the whole user object, so compare values
    instead of checking which keys are present.
    """
    profile = get_profile(existing)
    team_member = getattr(existing, 'team_member', None)
    if 'email' in data and email != normalize_email(existing.email or ''):
        return True
    if 'username' in data and username != existing.username:
        return True
    if data.get('password'):
        return True
    if parse_boolean(data.get('is_active'), existing.is_active) != existing.is_active:
        return True
    if parse_boolean(data.get('is_staff'), existing.is_staff) != existing.is_staff:
        return True
    if 'access_role' in data and data.get('access_role') != profile.access_role:
        return True
    current_role_code = profile.account_role.code if profile.account_role_id else ''
    if data.get('account_role') and data.get('account_role') != current_role_code:
        return True
    team_role = data.get('team_role') or data.get('role')
    if team_role in dict(TeamMember.ROLES):
        current_team_role = team_member.role if team_member else None
        if current_team_role is None and team_role in {'viewer', get_dashboard_role(existing)}:
            return False
        if team_role != current_team_role:
            return True
    return False




def _role_rank(role, roles):
    ranks = {'member': 0, 'viewer': 0, 'contributor': 1, 'editor': 2, 'admin': 3}
    return ranks.get(role, -1) if role in dict(roles) else -1


def _reject_sensitive_user_change(request, user, fields, message):
    log_activity(
        request,
        'users',
        'system',
        f'Rejected sensitive user change for {user.email or user.username}: {", ".join(fields)}',
        user,
        {'rejected_fields': fields},
    )
    return error_response(message, 403)


def _authorize_sensitive_user_changes(request, data, user, profile, can_manage_super_admin, is_create):
    """Authorize all privilege and billing mutations before any write occurs."""
    # Compare values, not key presence: the dashboard editor always sends the
    # whole user object, so an unchanged field must not count as a change.
    current_values = {
        'is_staff': user.is_staff if not is_create else False,
        'access_role': profile.access_role if not is_create else 'member',
        'account_role': (profile.account_role.code if profile.account_role_id else '') if not is_create else '',
        'tier': profile.tier if not is_create else 'free',
        'plan': (profile.plan.code if profile.plan_id else profile.tier) if not is_create else '',
        'premium_until': profile.premium_until.date().isoformat() if (not is_create and profile.premium_until) else '',
    }

    def changed(field):
        if field not in data:
            return False
        value = data.get(field)
        if field == 'is_staff':
            return parse_boolean(value, current_values[field]) != current_values[field]
        if field == 'premium_until':
            return str(value or '')[:10] != current_values[field]
        if field in {'plan', 'account_role'} and value in (None, ''):
            return False
        if field == 'tier' and not is_create and value in {profile.tier, profile.effective_tier}:
            return False  # the user list shows the effective tier
        return (value or '') != current_values[field]

    protected_self_fields = {'is_staff', 'access_role', 'account_role'}
    if not can_manage_super_admin and not is_create and user.pk == request.user.pk:
        attempted_self_fields = sorted(field for field in protected_self_fields if changed(field))
        if attempted_self_fields:
            return _reject_sensitive_user_change(
                request, user, attempted_self_fields,
                'Only a super administrator can change their own privileged account fields.',
            )

    target_is_super_admin = bool(
        user.is_superuser or (
            profile.account_role_id and profile.account_role.is_super_admin
        )
    )
    if target_is_super_admin and not can_manage_super_admin:
        return _reject_sensitive_user_change(
            request, user, ['super_admin_target'],
            'Only a super administrator can modify a super-admin account.',
        )

    billing_fields = sorted(field for field in ('tier', 'plan', 'premium_until') if changed(field))
    if billing_fields and not can_manage_super_admin:
        return _reject_sensitive_user_change(
            request, user, billing_fields,
            'Only a super administrator can change billing entitlements.',
        )

    if can_manage_super_admin:
        return None

    requested_is_staff = parse_boolean(data.get('is_staff'), user.is_staff if not is_create else False)
    requested_access_role = data.get('access_role', profile.access_role if not is_create else 'member')
    requested_account_role = data.get('account_role')
    requested_team_role = data.get('team_role') or data.get('role')
    current_team_member = getattr(user, 'team_member', None) if not is_create else None
    current_team_role = current_team_member.role if current_team_member else 'viewer'
    if not current_team_member and not is_create and not data.get('team_role') and requested_team_role == get_dashboard_role(user):
        # The user list returns the derived dashboard role as `role`; sending
        # it back unchanged is not a team-role request.
        requested_team_role = None
    current_team_active = current_team_member.is_active if current_team_member else False
    updates_team_member = requested_team_role in dict(TeamMember.ROLES) or bool(_text(data, 'department', max_length=100))
    requested_team_active = parse_boolean(
        data.get('team_active'), current_team_active if current_team_member else True,
    )

    privileged_fields = []
    if requested_is_staff and not user.is_staff:
        privileged_fields.append('is_staff')
    if requested_access_role in dict(profile.ROLES) and _role_rank(requested_access_role, profile.ROLES) > _role_rank(profile.access_role if not is_create else 'member', profile.ROLES):
        privileged_fields.append('access_role')
    if requested_team_role in dict(TeamMember.ROLES) and _role_rank(requested_team_role, TeamMember.ROLES) > _role_rank(current_team_role, TeamMember.ROLES):
        privileged_fields.append('team_role')
    if updates_team_member and requested_team_active and not current_team_active:
        privileged_fields.append('team_active')
    if updates_team_member and current_team_member and not current_team_active:
        # An inactive team member cannot be changed through an incidental
        # department/role update by a non-super-admin. This prevents an
        # inactive privileged dashboard identity from being modified outside
        # the explicit super-admin recovery workflow.
        privileged_fields.append('inactive_team_member')

    selected_role = AccountRole.objects.filter(code=requested_account_role, is_active=True).first() if requested_account_role else None
    if selected_role:
        current_role = profile.account_role if not is_create else None
        if selected_role.is_super_admin or (
            selected_role.can_access_dashboard and (
                not current_role or current_role.code != selected_role.code
            )
        ):
            privileged_fields.append('account_role')

    # Creating a normal editor is an existing users.write workflow. It cannot
    # grant users.write because only the admin dashboard role has that power.
    normal_editor_creation = (
        is_create
        and set(privileged_fields).issubset({'is_staff', 'access_role', 'team_role', 'team_active', 'account_role'})
        and requested_access_role == 'editor'
        and requested_account_role in {None, '', 'editor'}
        and requested_team_role in {None, '', 'viewer', 'contributor', 'editor'}
    )
    if privileged_fields and not normal_editor_creation:
        return _reject_sensitive_user_change(
            request, user, sorted(set(privileged_fields)),
            'Only a super administrator can grant privileged account access.',
        )
    return None


@require_GET
@api_permission_required('users.view')
def users_api(request):
    qs = User.objects.select_related(
        'membership_profile', 'membership_profile__account_role', 'membership_profile__plan', 'team_member',
    ).all()
    if request.GET.get('status') == 'active':
        qs = qs.filter(is_active=True)
    elif request.GET.get('status') == 'inactive':
        qs = qs.filter(is_active=False)
    tier = request.GET.get('tier')
    if tier in {'free', 'premium'}:
        qs = qs.filter(membership_profile__tier=tier)
    access_role = request.GET.get('access_role')
    if access_role in {'member', 'editor', 'admin'}:
        qs = qs.filter(membership_profile__access_role=access_role)
    dashboard_access = request.GET.get('dashboard_access')
    if dashboard_access == 'yes':
        qs = qs.filter(is_staff=True, is_active=True)
    elif dashboard_access == 'no':
        qs = qs.filter(Q(is_staff=False) | Q(is_active=False))
    role = request.GET.get('role')
    if role:
        qs = qs.filter(dashboard_role_q(role))
    qs = apply_common_filters(
        qs, request,
        ['username', 'email', 'first_name', 'last_name', 'membership_profile__display_name', 'membership_profile__organization'],
        ['date_joined', 'last_login', 'email'], '-date_joined',
    )
    features = active_features()
    role_rows = role_rows_by_code()

    def serialize(user):
        prime_permissions(user, role_rows)
        return user_to_dict(user, features)

    payload = paginate(qs, request, serialize, 25)
    payload['summary'] = _user_summary()
    return JsonResponse(payload)


def _user_summary():
    """Whole-directory counts for the stat cards; independent of the current filters."""
    everyone = User.objects.all()
    return {
        'total': everyone.count(),
        'active': everyone.filter(is_active=True).count(),
        'inactive': everyone.filter(is_active=False).count(),
        'dashboard_access': everyone.filter(is_staff=True, is_active=True).count(),
        'admins': everyone.filter(Q(is_superuser=True) | Q(membership_profile__access_role='admin')).distinct().count(),
        'premium': everyone.filter(membership_profile__tier='premium').count(),
        'joined_30_days': everyone.filter(date_joined__gte=timezone.now() - timedelta(days=30)).count(),
    }

@require_POST
@api_save_permission_required('users')
def save_user_api(request, pk=None):
    data = get_payload(request)
    if not isinstance(data, dict) and not hasattr(data, 'get'):
        return error_response('Invalid request body.')
    email = normalize_email(_text(data, 'email', max_length=150))
    username = _text(data, 'username', email, 150) or email
    if '@' in username:
        username = normalize_email(username)
    if not email:
        return error_response('Email is required.')
    try:
        validate_email(email)
    except ValidationError as exc:
        return error_response(' '.join(exc.messages))
    other_users = User.objects.exclude(pk=pk)
    if find_user_by_identifier(email, other_users) or other_users.filter(username__iexact=username).exists():
        return error_response('A user with this email or username already exists.')

    existing = get_object_or_404(User, pk=pk) if pk else None
    actor_level = _privilege_level(request.user)
    can_manage_super_admin = actor_level >= 3
    editing_self = bool(existing and existing.pk == request.user.pk)
    was_super_admin = _is_super_admin(existing)

    # --- Authorization: decided entirely before anything is written. ---
    if existing and not editing_self:
        target_level = _privilege_level(existing)
        if target_level >= 3 and not can_manage_super_admin:
            return error_response('Only a super administrator can edit a super administrator account.', 403)
        if target_level >= actor_level:
            changes_sensitive = _sensitive_changes(existing, data, email, username)
            if changes_sensitive:
                return error_response('You cannot change the access, email or password of an account at your own level or above.', 403)
    requested_role_code = data.get('account_role')
    requested_role = AccountRole.objects.filter(code=requested_role_code, is_active=True).first() if requested_role_code else None
    if requested_role and requested_role.is_super_admin and not can_manage_super_admin:
        return error_response('Only a super administrator can assign the super-admin role.', 403)
    target_for_checks = existing or User(username=username, email=email)
    profile_for_checks = get_profile(existing) if existing else MembershipProfile(user=target_for_checks)
    rejection = _authorize_sensitive_user_changes(
        request, data, target_for_checks, profile_for_checks, can_manage_super_admin, not bool(pk),
    )
    if rejection:
        return rejection
    if editing_self and not can_manage_super_admin:
        own_profile = get_profile(request.user)
        if requested_role and requested_role.pk != own_profile.account_role_id:
            return error_response('You cannot change your own role.', 403)
        if 'access_role' in data and data.get('access_role') != own_profile.access_role:
            return error_response('You cannot change your own role.', 403)

    try:
        with transaction.atomic():
            user = existing or User(username=username, email=email)
            user.username = username
            user.email = email
            user.first_name = _text(data, 'first_name', user.first_name if pk else '', 150)
            user.last_name = _text(data, 'last_name', user.last_name if pk else '', 150)
            requested_is_active = parse_boolean(data.get('is_active'), user.is_active if pk else True)
            requested_is_staff = parse_boolean(data.get('is_staff'), user.is_staff if pk else False)
            if editing_self and not requested_is_active:
                raise _Reject('You cannot deactivate your own dashboard account.', 400)
            user.is_active = requested_is_active
            user.is_staff = requested_is_staff
            new_password = data.get('password')
            if new_password:
                if not isinstance(new_password, str) or len(new_password) > 256:
                    raise _Reject('Password must be 256 characters or fewer.')
                if pk and password_was_used(user, new_password):
                    raise _Reject(PASSWORD_REUSE_MESSAGE)
                try:
                    validate_password(new_password, user=user)
                except ValidationError as exc:
                    raise _Reject(' '.join(exc.messages))
                if pk:
                    if not set_password_with_history(user, new_password, save=False):
                        raise _Reject(PASSWORD_REUSE_MESSAGE)
                else:
                    user.set_password(new_password)
            elif not pk:
                user.set_unusable_password()
            user.save()

            profile = get_profile(user)
            # Only touch tier/plan/role when the request actually sends them, so
            # saving a name never resets a paid plan or a custom role (B-19).
            if 'access_role' in data and data.get('access_role') in dict(profile.ROLES):
                profile.access_role = data.get('access_role')
            if 'tier' in data and data.get('tier') in dict(profile.TIERS) and data.get('tier') != profile.tier:
                profile.tier = data.get('tier')
                profile.plan = SubscriptionPlan.objects.filter(code=profile.tier, is_active=True).first()
            plan = data.get('plan')
            if plan:
                selected_plan = SubscriptionPlan.objects.filter(code=plan, is_active=True).first()
                if selected_plan:
                    profile.plan = selected_plan
                    profile.tier = selected_plan.tier
            if requested_role:
                profile.account_role = requested_role
                if requested_role.code in dict(profile.ROLES):
                    profile.access_role = requested_role.code
            elif not pk or 'access_role' in data or 'tier' in data or 'account_role' in data:
                if profile.access_role in {'editor', 'admin'}:
                    profile.account_role = AccountRole.objects.filter(code=profile.access_role, is_active=True).first()
                else:
                    profile.account_role = AccountRole.objects.filter(code=profile.tier, is_active=True).first()
            premium_until = data.get('premium_until')
            if premium_until is not None:
                parsed_premium_until = parse_datetime(premium_until) if premium_until else None
                if premium_until and parsed_premium_until is None:
                    parsed_date = parse_date(premium_until)
                    parsed_premium_until = timezone.make_aware(
                        timezone.datetime.combine(parsed_date, timezone.datetime.max.time())
                    ) if parsed_date else None
                profile.premium_until = parsed_premium_until
            profile.email_verified = parse_boolean(data.get('email_verified'), profile.email_verified)
            profile.display_name = _text(data, 'display_name', profile.display_name or user.get_full_name(), 200)
            profile.organization = _text(data, 'organization', profile.organization, 250)
            profile.specialization = _text(data, 'specialization', profile.specialization, 250)
            profile.save()

            # Final guard: nobody below super admin may end up creating a super admin.
            if not can_manage_super_admin and _is_super_admin(user) and not was_super_admin:
                raise _Reject('Only a super administrator can assign the super-admin role.', 403)

            team_role = data.get('team_role') or data.get('role')
            department = _text(data, 'department', max_length=100)
            if team_role in dict(TeamMember.ROLES) or department:
                team_member, team_member_created = TeamMember.objects.get_or_create(user=user)
                if team_role in dict(TeamMember.ROLES):
                    team_member.role = team_role
                team_member.department = department
                team_member.is_active = parse_boolean(data.get('team_active'), True if team_member_created else team_member.is_active)
                team_member.save()
    except _Reject as rejection:
        return error_response(rejection.message, rejection.status)
    clear_role_cache(user)
    log_activity(request, 'users', 'update' if pk else 'create', f'Saved user: {user.email}', user)
    return JsonResponse({'success': True, 'user': user_to_dict(user)})
