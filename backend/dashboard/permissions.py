"""Dashboard roles and permissions.

A permission is ``<module>.<action>``: the module is one entry of
``DASHBOARD_MODULES`` and the action one of ``ACTIONS``. What each role may
do is stored on ``accounts.AccountRole.dashboard_permissions`` and edited from
the dashboard's Roles & Permissions page, so no code change is needed to
adjust a role. ``DEFAULT_ROLE_PERMISSIONS`` only seeds those rows and covers
a built-in role whose row has been removed.
"""

from django.db.models import Q

from accounts.entitlements import get_profile


ACTIONS = ['view', 'create', 'edit', 'delete', 'manage']

ACTION_LABELS = {
    'view': 'View',
    'create': 'Create',
    'edit': 'Edit',
    'delete': 'Delete',
    'manage': 'Manage',
}


DASHBOARD_MODULES = [
    {
        'id': 'dashboard',
        'label': 'Overview',
        'group': 'Workspace',
        'routes': ['/dashboard'],
        'description': 'Open the dashboard and its overview statistics. Every dashboard role has this.',
        'actions': {'view': 'Open the dashboard'},
    },
    {
        'id': 'content',
        'label': 'Articles and Pages',
        'group': 'Content',
        'routes': ['/dashboard/posts'],
        'description': 'Articles, pages, PDFs and SEO reports.',
        'actions': {
            'view': 'See articles, pages and SEO reports',
            'create': 'Write new articles and pages',
            'edit': 'Edit existing articles and pages',
            'delete': 'Move articles and pages to the trash and delete them',
            'manage': 'Quick publish and status actions, bulk actions and SEO report refresh',
        },
    },
    {
        'id': 'media',
        'label': 'Media Library',
        'group': 'Content',
        'routes': ['/dashboard/media'],
        'description': 'Images and files used on the site.',
        'actions': {
            'view': 'Browse the media library',
            'create': 'Upload media',
            'edit': 'Edit media details',
            'delete': 'Delete media',
        },
    },
    {
        'id': 'taxonomy',
        'label': 'Categories, Tags and Authors',
        'group': 'Content',
        'routes': ['/dashboard/categories', '/dashboard/tags', '/dashboard/authors'],
        'description': 'How articles are organised and credited.',
        'actions': {
            'view': 'See categories, tags and authors',
            'create': 'Add categories, tags and authors',
            'edit': 'Edit categories, tags and authors',
            'delete': 'Delete categories, tags and authors',
        },
    },
    {
        'id': 'faq',
        'label': 'FAQ Manager',
        'group': 'Content',
        'routes': ['/dashboard/faq'],
        'description': 'FAQ categories, questions, answers and ordering.',
        'actions': {
            'view': 'See FAQ categories and questions',
            'create': 'Add FAQ categories and questions',
            'edit': 'Edit FAQ categories and questions',
            'delete': 'Hide questions and delete categories',
        },
    },
    {
        'id': 'forms',
        'label': 'Inbox, Forms and Applications',
        'group': 'Engagement',
        'routes': ['/dashboard/contacts', '/dashboard/forms', '/dashboard/applications'],
        'description': 'Contact messages, team applications and Join Our Team entries.',
        'actions': {
            'view': 'Read messages, applications and CVs',
            'create': 'Add Join Our Team entries',
            'edit': 'Update message and application status and notes',
            'delete': 'Delete Join Our Team entries',
        },
    },
    {
        'id': 'opportunities',
        'label': 'Research Opportunities',
        'group': 'Engagement',
        'routes': ['/dashboard/opportunities'],
        'description': 'Opportunities, deadlines and publishing status.',
        'actions': {
            'view': 'See opportunities',
            'create': 'Add opportunities',
            'edit': 'Edit opportunities',
            'delete': 'Delete opportunities',
            'manage': 'Publish, close and change status',
        },
    },
    {
        'id': 'services',
        'label': 'Services',
        'group': 'Engagement',
        'routes': ['/dashboard/services'],
        'description': 'Service definitions and incoming service requests.',
        'actions': {
            'view': 'See services and requests',
            'create': 'Add services and requests',
            'edit': 'Edit services and handle requests',
            'delete': 'Delete services',
        },
    },
    {
        'id': 'users',
        'label': 'Users',
        'group': 'People',
        'routes': ['/dashboard/users'],
        'description': 'Accounts, dashboard access, plans and account status.',
        'actions': {
            'view': 'See user accounts',
            'create': 'Create user accounts',
            'edit': 'Edit user accounts',
        },
    },
    {
        'id': 'team',
        'label': 'Team and Volunteers',
        'group': 'People',
        'routes': ['/dashboard/team'],
        'description': 'The team and volunteer directory.',
        'actions': {'view': 'See the team directory'},
    },
    {
        'id': 'reports',
        'label': 'Reports',
        'group': 'Insights and tools',
        'routes': ['/dashboard/reports'],
        'description': 'Analytics and data exports. Exports also need View on the exported module.',
        'actions': {
            'view': 'See reports',
            'manage': 'Export data (CSV, Excel, JSON, PDF)',
        },
    },
    {
        'id': 'activity',
        'label': 'Activity Log',
        'group': 'Insights and tools',
        'routes': [],
        'description': 'The audit log of dashboard changes.',
        'actions': {'view': 'Read the audit log'},
    },
    {
        'id': 'premium',
        'label': 'Premium Controls and Research Analyzer',
        'group': 'Insights and tools',
        'routes': ['/dashboard/premium-controls', '/dashboard/research-analyzer'],
        'description': 'Free and premium features, subscription plans and usage limits.',
        'actions': {
            'view': 'See features, plans and usage limits',
            'create': 'Add features, plans and usage limits',
            'edit': 'Change features, plans and usage limits',
        },
    },
    {
        'id': 'notifications',
        'label': 'Notifications',
        'group': 'System',
        'routes': ['/dashboard/notifications'],
        'description': 'Account notifications sent to members.',
        'actions': {
            'view': 'See sent notifications',
            'create': 'Send notifications',
        },
    },
    {
        'id': 'settings',
        'label': 'Settings and Website Content',
        'group': 'System',
        'routes': ['/dashboard/settings', '/dashboard/content-studio'],
        'description': 'Site-wide settings, page text and images, and API docs.',
        'actions': {
            'view': 'See settings and website content',
            'edit': 'Change settings and website content',
        },
    },
    {
        'id': 'roles',
        'label': 'Roles and Permissions',
        'group': 'System',
        'routes': ['/dashboard/roles'],
        'description': 'Which sections and actions each dashboard role has.',
        'actions': {
            'view': 'See roles and their permissions',
            'create': 'Add roles',
            'edit': 'Change role permissions',
            'delete': 'Delete custom roles',
            'manage': 'Assign roles to people',
        },
    },
]

for _module in DASHBOARD_MODULES:
    # Older callers (API docs, the previous settings page) read these two keys.
    _module['route'] = _module['routes'][0] if _module['routes'] else ''
    _module['permissions'] = [f"{_module['id']}.{action}" for action in _module['actions']]

ALL_PERMISSIONS = [permission for module in DASHBOARD_MODULES for permission in module['permissions']]
ALL_PERMISSION_SET = frozenset(ALL_PERMISSIONS)

# Every dashboard role can open the dashboard; the roles page cannot remove it.
BASE_PERMISSION = 'dashboard.view'

# Permission names used before per-action permissions existed. Code that still
# checks one of these is answered with the permission that replaced it.
LEGACY_ALIASES = {
    'activity.read': 'activity.view',
    'content.read': 'content.view',
    'content.write': 'content.edit',
    'forms.read': 'forms.view',
    'forms.write': 'forms.edit',
    'opportunities.read': 'opportunities.view',
    'opportunities.write': 'opportunities.edit',
    'reports.read': 'reports.view',
    'reports.export': 'reports.manage',
    'services.read': 'services.view',
    'services.write': 'services.edit',
    'settings.read': 'settings.view',
    'settings.write': 'settings.edit',
    'team.read': 'team.view',
    'team.write': 'team.view',
    'users.read': 'users.view',
    'users.write': 'users.edit',
}

# What each previous permission granted, written as new permissions. Used to
# give users who already had a role exactly the access they had before.
LEGACY_TRANSLATION = {
    'dashboard.view': ['dashboard.view'],
    'activity.read': ['activity.view'],
    'content.read': ['content.view', 'media.view', 'taxonomy.view', 'faq.view'],
    'content.write': [
        'content.create', 'content.edit', 'content.manage',
        'media.create', 'media.edit',
        'taxonomy.create', 'taxonomy.edit',
        'faq.create', 'faq.edit', 'faq.delete',
    ],
    'content.delete': ['content.delete', 'media.delete', 'taxonomy.delete'],
    'forms.read': ['forms.view'],
    'forms.write': ['forms.create', 'forms.edit', 'forms.delete'],
    'opportunities.read': ['opportunities.view'],
    'opportunities.write': ['opportunities.create', 'opportunities.edit', 'opportunities.manage'],
    'opportunities.delete': ['opportunities.delete'],
    'reports.read': ['reports.view'],
    'reports.export': ['reports.manage'],
    'services.read': ['services.view'],
    'services.write': ['services.create', 'services.edit'],
    'services.delete': ['services.delete'],
    'team.read': ['team.view'],
    'users.read': ['users.view'],
    'users.write': ['users.create', 'users.edit'],
}

# Permission sets the editor and contributor roles had before roles became
# editable. The migration keeps these for users who already held those roles.
PREVIOUS_ROLE_PERMISSIONS = {
    'contributor': [
        'dashboard.view', 'content.read', 'content.write', 'forms.read',
        'opportunities.read', 'services.read', 'team.read',
    ],
    'editor': [
        'dashboard.view', 'activity.read', 'content.read', 'content.write',
        'forms.read', 'forms.write', 'opportunities.read', 'opportunities.write',
        'reports.read', 'reports.export', 'services.read', 'services.write',
        'team.read', 'users.read',
    ],
}


def translate_legacy_permissions(old_permissions):
    result = set()
    for permission in old_permissions:
        result.update(LEGACY_TRANSLATION.get(permission, []))
    return sorted(result)


# Roles that always have every permission. Their rows cannot be edited.
FULL_ACCESS_ROLE_CODES = frozenset({'admin', 'super_admin'})
# Website-account roles; they never open the dashboard and are not listed on
# the roles page.
MEMBER_ROLE_CODES = frozenset({'free', 'premium'})
# Roles the role resolver falls back to (team role / access role), plus the
# seeded defaults. They can be edited but not deleted.
BUILTIN_ROLE_CODES = frozenset({'admin', 'super_admin', 'developer', 'manager', 'editor', 'contributor', 'viewer'})
# Roles a TeamMember or MembershipProfile.access_role can name directly.
FALLBACK_ROLE_ORDER = ['admin', 'editor', 'contributor', 'viewer']


DEFAULT_ROLES = [
    # code, label, description, permissions
    ('admin', 'Admin', 'Full administration: every section and action, including users, settings and roles.', ['*']),
    ('developer', 'Developer / Programmer', 'Technical and system sections: settings, website content, premium controls, the Research Analyzer, notifications, the audit log and reports.', [
        'dashboard.view',
        'settings.view', 'settings.edit',
        'premium.view', 'premium.create', 'premium.edit',
        'notifications.view',
        'activity.view',
        'reports.view',
        'roles.view',
    ]),
    ('manager', 'Manager', 'Management and reporting: reports and exports, the audit log, people, forms, opportunities and services. Read-only access to content.', [
        'dashboard.view',
        'reports.view', 'reports.manage',
        'activity.view',
        'users.view', 'team.view',
        'forms.view', 'forms.edit',
        'opportunities.view', 'opportunities.create', 'opportunities.edit', 'opportunities.manage',
        'services.view', 'services.create', 'services.edit',
        'content.view', 'media.view', 'taxonomy.view', 'faq.view',
        'notifications.view', 'notifications.create',
    ]),
    ('editor', 'Editor', 'Articles and related content only: articles, pages, media, categories, tags, authors and the FAQ. No users or admin sections.', [
        'dashboard.view',
        'content.view', 'content.create', 'content.edit', 'content.manage',
        'media.view', 'media.create', 'media.edit',
        'taxonomy.view', 'taxonomy.create', 'taxonomy.edit',
        'faq.view', 'faq.create', 'faq.edit',
    ]),
    ('contributor', 'Contributor', 'Writes and edits articles and uploads media. Can see, but not change, categories, tags, authors and the FAQ.', [
        'dashboard.view',
        'content.view', 'content.create', 'content.edit',
        'media.view', 'media.create',
        'taxonomy.view',
        'faq.view',
    ]),
    ('viewer', 'Viewer', 'Read-only access to content, forms, opportunities, services, the team and reports.', [
        'dashboard.view',
        'content.view', 'media.view', 'taxonomy.view', 'faq.view',
        'forms.view', 'opportunities.view', 'services.view', 'team.view', 'reports.view',
    ]),
]

DEFAULT_ROLE_PERMISSIONS = {code: set(permissions) for code, _label, _description, permissions in DEFAULT_ROLES}
DEFAULT_ROLE_PERMISSIONS['super_admin'] = {'*'}
# Kept for older imports; the stored role rows are authoritative.
ROLE_PERMISSIONS = DEFAULT_ROLE_PERMISSIONS


def clean_permissions(permissions):
    """Known permission codes only, sorted, always including the base one."""
    cleaned = {permission for permission in permissions or [] if permission in ALL_PERMISSION_SET}
    cleaned.add(BASE_PERMISSION)
    return sorted(cleaned)


ROLE_CACHE_ATTR = '_resref_dashboard_role'
PERMISSION_CACHE_ATTR = '_resref_dashboard_permissions'


def clear_role_cache(user):
    if user is None:
        return
    for attr in (ROLE_CACHE_ATTR, PERMISSION_CACHE_ATTR):
        if hasattr(user, attr):
            delattr(user, attr)


def get_dashboard_role(user):
    """Role used for dashboard permissions; memoized on the user object for
    the rest of the request (call ``clear_role_cache`` after changing it)."""
    if not user or not user.is_authenticated:
        return 'anonymous'
    cached = getattr(user, ROLE_CACHE_ATTR, None)
    if cached is not None:
        return cached
    role = _compute_dashboard_role(user)
    setattr(user, ROLE_CACHE_ATTR, role)
    return role


def _compute_dashboard_role(user):
    if user.is_superuser:
        return 'admin'

    team_member = getattr(user, 'team_member', None)
    profile = get_profile(user)
    if profile.account_role_id and profile.account_role.is_active:
        if profile.account_role.is_super_admin or profile.account_role.code == 'admin':
            return 'admin'
        if profile.account_role.can_access_dashboard:
            return profile.account_role.code
    candidates = []
    if team_member and team_member.is_active:
        candidates.append(team_member.role)
    if profile.access_role == 'admin':
        candidates.append('admin')
    elif profile.access_role == 'editor':
        candidates.append('editor')
    for role in FALLBACK_ROLE_ORDER:
        if role in candidates:
            return role
    return 'member'


def dashboard_role_q(role):
    """ORM filter for users whose ``get_dashboard_role`` equals ``role``.

    Mirrors ``_compute_dashboard_role`` so the user list can filter by role in
    SQL. Negations are written out with explicit ``isnull`` checks because SQL
    ``NOT`` over a missing (NULL) related row would silently drop users.
    """
    ar = 'membership_profile__account_role__'
    account_role_active = Q(**{f'{ar}is_active': True})
    account_role_silent = (
        Q(**{f'{ar}isnull': True})
        | Q(**{f'{ar}is_active': False})
        | (
            Q(**{f'{ar}is_super_admin': False})
            & ~Q(**{f'{ar}code': 'admin'})
            & Q(**{f'{ar}can_access_dashboard': False})
        )
    )
    undecided = Q(is_superuser=False) & account_role_silent

    def team(code):
        return Q(team_member__is_active=True, team_member__role=code)

    def not_team(code):
        return Q(team_member__isnull=True) | Q(team_member__is_active=False) | ~Q(team_member__role=code)

    def access(code):
        return Q(membership_profile__access_role=code)

    has = {
        'admin': team('admin') | access('admin'),
        'editor': team('editor') | access('editor'),
        'contributor': team('contributor'),
        'viewer': team('viewer'),
    }
    lacks = {
        'admin': not_team('admin') & ~access('admin'),
        'editor': not_team('editor') & ~access('editor'),
        'contributor': not_team('contributor'),
        'viewer': not_team('viewer'),
    }

    if role == 'admin':
        by_account_role = account_role_active & (Q(**{f'{ar}is_super_admin': True}) | Q(**{f'{ar}code': 'admin'}))
        return Q(is_superuser=True) | (Q(is_superuser=False) & by_account_role) | (undecided & has['admin'])
    if role == 'member':
        result = undecided
        for code in FALLBACK_ROLE_ORDER:
            result &= lacks[code]
        return result
    if not role or role == 'anonymous':
        return Q(pk__in=[])
    by_account_role = (
        Q(is_superuser=False) & account_role_active
        & Q(**{f'{ar}is_super_admin': False}, **{f'{ar}can_access_dashboard': True}, **{f'{ar}code': role})
    )
    if role not in FALLBACK_ROLE_ORDER:
        return by_account_role
    by_fallback = undecided & has[role]
    for higher in FALLBACK_ROLE_ORDER[:FALLBACK_ROLE_ORDER.index(role)]:
        by_fallback &= lacks[higher]
    return by_account_role | by_fallback


def role_permission_set(code, account_role=None, rows=None):
    """Permissions stored for role ``code``. ``account_role`` may be the
    already-loaded row, and ``rows`` every role row by code; either saves a
    query."""
    from accounts.models import AccountRole

    if code in FULL_ACCESS_ROLE_CODES:
        return {'*'}
    if code in {'member', 'anonymous', ''} or code in MEMBER_ROLE_CODES:
        return set()
    if account_role is not None and account_role.code == code:
        row = account_role
    elif rows is not None:
        row = rows.get(code)
    else:
        row = AccountRole.objects.filter(code=code).first()
    if row is None:
        return set(DEFAULT_ROLE_PERMISSIONS.get(code, ()))
    if not row.is_active:
        return set()
    if row.is_super_admin:
        return {'*'}
    return set(row.dashboard_permissions or [])


def _permission_set(user, rows=None):
    if not user or not user.is_authenticated:
        return set()
    cached = getattr(user, PERMISSION_CACHE_ATTR, None)
    if cached is not None:
        return cached
    if user.is_superuser:
        permissions = {'*'}
    else:
        role = get_dashboard_role(user)
        profile = get_profile(user)
        permissions = role_permission_set(role, profile.account_role if profile.account_role_id else None, rows)
    setattr(user, PERMISSION_CACHE_ATTR, permissions)
    return permissions


def role_rows_by_code():
    """Every role row by code, for listing many users with one query."""
    from accounts.models import AccountRole

    return {role.code: role for role in AccountRole.objects.all()}


def prime_permissions(user, rows):
    """Resolve ``user``'s permissions from preloaded ``rows`` (see role_rows_by_code)."""
    _permission_set(user, rows)


def is_super_admin(user):
    """Super Admins only: Django superusers and active super-admin roles. The
    regular Admin role does not count, although it holds every permission."""
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    profile = get_profile(user)
    role = profile.account_role if profile.account_role_id else None
    return bool(role and role.is_active and role.is_super_admin)


def has_dashboard_access(user):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    if get_dashboard_role(user) == 'member' or not _permission_set(user):
        return False
    profile = get_profile(user)
    if profile.account_role_id and profile.account_role.is_active and profile.account_role.can_access_dashboard:
        return True
    return user.is_staff


def permissions_for_user(user):
    permissions = _permission_set(user)
    if '*' in permissions:
        return list(ALL_PERMISSIONS)
    return sorted(permissions)


def has_dashboard_permission(user, permission):
    permissions = _permission_set(user)
    if '*' in permissions:
        return True
    return LEGACY_ALIASES.get(permission, permission) in permissions


def has_full_access(user):
    return '*' in _permission_set(user)


def module_registry_for_user(user):
    permissions = _permission_set(user)
    full = '*' in permissions
    return [
        {**module, 'enabled': full or f"{module['id']}.view" in permissions}
        for module in DASHBOARD_MODULES
    ]
