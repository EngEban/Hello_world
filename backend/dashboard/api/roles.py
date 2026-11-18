"""Roles & Permissions: list dashboard roles and change what each may do.

Guards, all checked here on the server:
- Admin and Super Admin always have full access and cannot be changed.
- Nobody changes, deactivates or deletes the role they hold themselves
  (superusers excepted: they keep full access whatever their role says), so
  an administrator cannot lock themselves out.
- A role can only be given permissions the person editing it already has.
- Built-in roles cannot be deleted, and no role is deleted while users hold it.
- People can only be moved into or out of a role that grants nothing beyond
  the assigner's own permissions, never themselves, and never a superuser or
  super administrator.
"""

from .common import *
from accounts.models import AccountRole
from ..permissions import (
    ACTION_LABELS,
    ACTIONS,
    ALL_PERMISSION_SET,
    ALL_PERMISSIONS,
    BUILTIN_ROLE_CODES,
    FULL_ACCESS_ROLE_CODES,
    MEMBER_ROLE_CODES,
    clean_permissions,
    clear_role_cache,
    dashboard_role_q,
    has_full_access,
)


RESERVED_CODES = BUILTIN_ROLE_CODES | MEMBER_ROLE_CODES | {'member', 'anonymous', 'superuser'}
ROLE_ORDER = ['admin', 'super_admin', 'developer', 'manager', 'editor', 'contributor', 'viewer']


def _dashboard_roles():
    roles = AccountRole.objects.filter(Q(can_access_dashboard=True) | Q(is_super_admin=True)).exclude(code__in=MEMBER_ROLE_CODES)
    return sorted(roles, key=lambda role: (ROLE_ORDER.index(role.code) if role.code in ROLE_ORDER else len(ROLE_ORDER), role.label.lower()))


def _holds_role(user, role):
    if role.is_super_admin:
        return get_profile(user).account_role_id == role.pk
    return get_dashboard_role(user) == role.code


def role_to_dict(role, request, with_members=True):
    full_access = role.code in FULL_ACCESS_ROLE_CODES or role.is_super_admin
    data = {
        'id': role.id,
        'code': role.code,
        'label': role.label,
        'description': role.description,
        'is_active': role.is_active,
        'full_access': full_access,
        'locked': full_access,
        'builtin': role.code in BUILTIN_ROLE_CODES,
        'is_current': _holds_role(request.user, role),
        'permissions': list(ALL_PERMISSIONS) if full_access else sorted(role.dashboard_permissions or []),
        'updated_at': role.updated_at.isoformat() if role.updated_at else None,
    }
    if with_members:
        if role.is_super_admin:
            holders = User.objects.filter(membership_profile__account_role=role)
        else:
            holders = User.objects.filter(dashboard_role_q(role.code))
        holders = holders.order_by('-is_active', 'username').distinct()
        data['member_count'] = holders.count()
        data['members'] = [
            {'id': user.id, 'name': user.get_full_name() or user.username, 'email': user.email, 'is_active': user.is_active}
            for user in holders[:50]
        ]
    return data


def _can(request, action):
    return has_dashboard_permission(request.user, f'roles.{action}')


@require_GET
@api_permission_required('roles.view')
def roles_permissions_api(request):
    return JsonResponse({
        'actions': [{'id': action, 'label': ACTION_LABELS[action]} for action in ACTIONS],
        'modules': DASHBOARD_MODULES,
        'roles': [role_to_dict(role, request) for role in _dashboard_roles()],
        'current_role': get_dashboard_role(request.user),
        'current_permissions': permissions_for_user(request.user),
        'is_superuser': request.user.is_superuser,
        'can': {action: _can(request, action) for action in ('create', 'edit', 'delete', 'manage')},
    })


def _requested_permissions(data):
    raw = data.get('permissions')
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise BadRequest('Send permissions as a list of permission codes.')
    unknown = sorted(set(raw) - ALL_PERMISSION_SET)
    if unknown:
        raise BadRequest(f'Unknown permission: {", ".join(unknown[:5])}')
    return clean_permissions(raw)


def _escalation_error(request, before, after):
    """Only permissions the editor holds can be added to a role."""
    if has_full_access(request.user):
        return None
    own = set(permissions_for_user(request.user))
    beyond = sorted(set(after) - set(before) - own)
    if beyond:
        return error_response(f'You can only grant permissions your own role has. Not allowed: {", ".join(beyond[:6])}.', 403)
    return None


def _own_role_error(request, role):
    if request.user.is_superuser or not _holds_role(request.user, role):
        return None
    return error_response('You cannot change the access of the role you hold yourself. Ask another administrator to do it.', 403)


@require_POST
@api_save_permission_required('roles')
def save_role_api(request, pk=None):
    data = get_payload(request)
    role = get_object_or_404(AccountRole, pk=pk) if pk else None
    if role and (role.code in MEMBER_ROLE_CODES or not (role.can_access_dashboard or role.is_super_admin)):
        return error_response('Only dashboard roles are edited here.', 404)

    label = str(data.get('label', role.label if role else '') or '').strip()[:120]
    description = str(data.get('description', role.description if role else '') or '').strip()[:1000]
    if not label:
        return error_response('Give the role a name.')
    try:
        permissions = _requested_permissions(data) if ('permissions' in data or not role) else None
    except BadRequest as exc:
        return error_response(str(exc))
    is_active = parse_boolean(data.get('is_active'), role.is_active if role else True)

    if role is None:
        code = slugify(str(data.get('code') or label)).replace('-', '_')[:50]
        if not code:
            return error_response('Give the role a name that contains letters or numbers.')
        if code in RESERVED_CODES or AccountRole.objects.filter(code=code).exists():
            return error_response(f'A role with the code "{code}" already exists. Choose another name.')
        rejection = _escalation_error(request, [], permissions)
        if rejection:
            return rejection
        role = AccountRole.objects.create(
            code=code, label=label, description=description, can_access_dashboard=True,
            is_active=is_active, dashboard_permissions=permissions,
        )
        log_activity(request, 'roles', 'create', f'Created role: {role.label}', role, {'permissions': permissions})
        return JsonResponse({'success': True, 'role': role_to_dict(role, request)})

    if role.code in FULL_ACCESS_ROLE_CODES or role.is_super_admin:
        if permissions is not None or not is_active or label != role.label:
            return error_response(f'{role.label} always has full access and cannot be changed.', 403)
    before = sorted(role.dashboard_permissions or [])
    access_changes = (permissions is not None and permissions != before) or is_active != role.is_active
    if access_changes:
        rejection = _own_role_error(request, role)
        if rejection:
            return rejection
    if permissions is not None:
        rejection = _escalation_error(request, before, permissions)
        if rejection:
            return rejection
        role.dashboard_permissions = permissions
    if not role.is_active and is_active:
        # Reactivating grants the stored permissions again: same rule.
        rejection = _escalation_error(request, [], role.dashboard_permissions or [])
        if rejection:
            return rejection
    role.label = label
    role.description = description
    role.is_active = is_active
    role.save()
    clear_role_cache(request.user)
    log_activity(
        request, 'roles', 'update', f'Updated role: {role.label}', role,
        {'before': before, 'after': sorted(role.dashboard_permissions or []), 'is_active': role.is_active},
    )
    return JsonResponse({'success': True, 'role': role_to_dict(role, request)})


@require_POST
@api_permission_required('roles.delete')
def delete_role_api(request, pk):
    role = get_object_or_404(AccountRole, pk=pk)
    if role.code in BUILTIN_ROLE_CODES or role.code in MEMBER_ROLE_CODES or role.is_super_admin:
        return error_response(f'{role.label} is a built-in role and cannot be deleted. You can change its permissions or deactivate it instead.', 400)
    rejection = _own_role_error(request, role)
    if rejection:
        return rejection
    holders = User.objects.filter(Q(membership_profile__account_role=role) | dashboard_role_q(role.code)).distinct().count()
    if holders:
        return error_response(f'{holders} user{"s" if holders != 1 else ""} still {"have" if holders != 1 else "has"} this role. Move them to another role on the Users page first.', 400)
    label = role.label
    role.delete()
    log_activity(request, 'roles', 'delete', f'Deleted role: {label}', metadata={'code': role.code})
    return JsonResponse({'success': True})


def _grants_beyond_actor(request, permissions):
    if has_full_access(request.user):
        return False
    return not set(permissions) <= set(permissions_for_user(request.user))


@require_POST
@api_permission_required('roles.manage')
def role_members_api(request, pk):
    """Add a user to a role, or take them out of it (back to their plan role)."""
    role = get_object_or_404(AccountRole, pk=pk)
    if role.code in MEMBER_ROLE_CODES or not (role.can_access_dashboard or role.is_super_admin):
        return error_response('Only dashboard roles can be assigned here.', 404)
    data = get_payload(request)
    action = data.get('action')
    if action not in {'add', 'remove'}:
        return error_response('Choose whether to add or remove the user.')
    try:
        target = User.objects.select_related('membership_profile__account_role').get(pk=int(data.get('user_id')))
    except (TypeError, ValueError, User.DoesNotExist):
        return error_response('User not found.', 404)

    if target.pk == request.user.pk:
        return error_response('You cannot change your own role. Ask another administrator to do it.', 403)
    profile = get_profile(target)
    if target.is_superuser or (profile.account_role_id and profile.account_role.is_super_admin):
        return error_response('Superuser and super administrator accounts are managed by a super administrator.', 403)
    if role.is_super_admin and not request.user.is_superuser:
        return error_response('Only a superuser can assign the super administrator role.', 403)
    # Neither the role given nor the role taken away may outrank the assigner.
    role_permissions = ALL_PERMISSIONS if role.code in FULL_ACCESS_ROLE_CODES else (role.dashboard_permissions or [])
    current_permissions = permissions_for_user(target) if has_dashboard_access(target) else []
    if _grants_beyond_actor(request, role_permissions) or _grants_beyond_actor(request, current_permissions):
        return error_response('You can only assign roles, and change people, whose access does not go beyond your own.', 403)

    if action == 'add':
        profile.account_role = role
    else:
        if profile.account_role_id != role.pk:
            return error_response('This user does not hold that role directly. Change their team or access role on the Users page.', 400)
        profile.account_role = AccountRole.objects.filter(code=profile.tier, is_active=True).first()
    profile.save(update_fields=['account_role', 'updated_at'])
    clear_role_cache(target)
    log_activity(
        request, 'roles', 'update',
        f"{'Assigned' if action == 'add' else 'Removed'} {target.email or target.username} {'to' if action == 'add' else 'from'} role {role.label}",
        target, {'role': role.code, 'action': action},
    )
    return JsonResponse({'success': True, 'role': role_to_dict(role, request)})
