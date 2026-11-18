"""Seed the editable dashboard roles and keep every existing user's access.

The Editor and Contributor defaults are narrower than what those roles allowed
before. Users who already held one of them with dashboard access are moved to
a "previous access" copy of their old permissions, so nobody loses (or gains)
access through this migration.
"""

from django.db import migrations

from dashboard.permissions import (
    DEFAULT_ROLES,
    PREVIOUS_ROLE_PERMISSIONS,
    clean_permissions,
    translate_legacy_permissions,
)


OLD_ROLE_CODES = {'viewer', 'contributor', 'editor', 'admin'}

PREVIOUS_ACCESS_ROLES = {
    'editor': ('editor_previous', 'Editor (previous access)', 'The access the Editor role had before roles became editable: content, forms, opportunities, services, reports and exports, the audit log and reading users. Kept for users who already had it; move them to another role when ready.'),
    'contributor': ('contributor_previous', 'Contributor (previous access)', 'The access the Contributor role had before roles became editable: writing content and reading forms, opportunities, services and the team. Kept for users who already had it; move them to another role when ready.'),
}


def _old_role(user, profile, team_member):
    """``get_dashboard_role`` as it worked before this migration."""
    if user.is_superuser:
        return 'admin'
    role = profile.account_role if profile and profile.account_role_id else None
    if role is not None and role.is_active:
        if role.is_super_admin or role.code == 'admin':
            return 'admin'
        if role.code in OLD_ROLE_CODES:
            return role.code
    candidates = []
    if team_member is not None and team_member.is_active:
        candidates.append(team_member.role)
    if profile is not None and profile.access_role in {'admin', 'editor'}:
        candidates.append(profile.access_role)
    for code in ['admin', 'editor', 'contributor', 'viewer']:
        if code in candidates:
            return code
    return 'member'


def _old_access(user, profile, role_code):
    if not user.is_active:
        return False
    if user.is_superuser:
        return True
    role = profile.account_role if profile and profile.account_role_id else None
    if role is not None and role.is_active and role.can_access_dashboard:
        return role_code in OLD_ROLE_CODES
    return user.is_staff and role_code in OLD_ROLE_CODES


def seed_roles(apps, schema_editor):
    AccountRole = apps.get_model('accounts', 'AccountRole')
    MembershipProfile = apps.get_model('accounts', 'MembershipProfile')
    TeamMember = apps.get_model('dashboard', 'TeamMember')
    User = apps.get_model('auth', 'User')

    # Find who held which role before any row changes.
    profiles = {profile.user_id: profile for profile in MembershipProfile.objects.select_related('account_role')}
    team_members = {member.user_id: member for member in TeamMember.objects.all()}
    keep_previous = {'editor': [], 'contributor': []}
    for user in User.objects.filter(is_superuser=False):
        profile = profiles.get(user.id)
        role_code = _old_role(user, profile, team_members.get(user.id))
        if role_code in keep_previous and profile is not None and _old_access(user, profile, role_code):
            keep_previous[role_code].append(profile)

    for code, label, description, permissions in DEFAULT_ROLES:
        role, created = AccountRole.objects.get_or_create(
            code=code,
            defaults={'label': label, 'description': description, 'can_access_dashboard': True},
        )
        role.label = label
        role.description = description
        role.can_access_dashboard = True
        role.dashboard_permissions = [] if permissions == ['*'] else clean_permissions(permissions)
        role.save()

    for old_code, profiles_to_move in keep_previous.items():
        if not profiles_to_move:
            continue
        code, label, description = PREVIOUS_ACCESS_ROLES[old_code]
        role, _ = AccountRole.objects.get_or_create(
            code=code,
            defaults={'label': label, 'description': description, 'can_access_dashboard': True},
        )
        role.dashboard_permissions = clean_permissions(translate_legacy_permissions(PREVIOUS_ROLE_PERMISSIONS[old_code]))
        role.can_access_dashboard = True
        role.is_active = True
        role.save()
        MembershipProfile.objects.filter(pk__in=[profile.pk for profile in profiles_to_move]).update(account_role=role)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0014_accountrole_dashboard_permissions'),
        ('dashboard', '0013_newsletter_double_opt_in'),
    ]

    operations = [
        migrations.RunPython(seed_roles, migrations.RunPython.noop),
    ]
