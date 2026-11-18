// Small helpers shared by the People, Insights and System dashboard pages.

// Permission names from before per-action permissions, mapped to their replacement.
const LEGACY_PERMISSIONS = {
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
  'users.read': 'users.view',
  'users.write': 'users.edit',
};

/** True when a permission list grants `permission` (`module.action`). */
export function permissionsAllow(permissions, permission, isSuperuser = false) {
  const list = permissions || [];
  return Boolean(isSuperuser || list.includes('*') || list.includes(LEGACY_PERMISSIONS[permission] || permission));
}

/** True when the signed-in dashboard user holds `permission` (or full access). */
export function hasPermission(user, bootstrap, permission) {
  return permissionsAllow(bootstrap?.permissions, permission, user?.is_superuser);
}

export function relativeTime(value) {
  if (!value) return '';
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return '';
  const minutes = Math.round((Date.now() - time) / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} d ago`;
  return new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

export const shortDate = value => (value ? new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) : '');

export function initials(name = '') {
  const parts = String(name).replace(/@.*/, '').split(/[\s._-]+/).filter(Boolean);
  return (parts.length > 1 ? parts[0][0] + parts[1][0] : (parts[0] || '?').slice(0, 2)).toUpperCase();
}

/** Plain-language names for dashboard permission codes. */
export const PERMISSION_LABELS = {
  'dashboard.view': 'Open the dashboard',
  'content.read': 'View articles, pages and media',
  'content.write': 'Create and edit content',
  'content.delete': 'Delete content',
  'forms.read': 'Read messages and form submissions',
  'forms.write': 'Update messages and forms',
  'opportunities.read': 'View research opportunities',
  'opportunities.write': 'Create and publish opportunities',
  'services.read': 'View services and requests',
  'services.write': 'Manage services and requests',
  'reports.read': 'View reports',
  'reports.export': 'Export data (CSV, Excel, JSON)',
  'team.read': 'View the team directory',
  'team.write': 'Manage team members',
  'users.read': 'View user accounts',
  'users.write': 'Create and edit user accounts',
  'activity.read': 'Read the audit log',
  'settings.read': 'View settings and premium controls',
  'settings.write': 'Change settings, premium controls and notifications',
  '*': 'Everything, including users, settings and billing controls',
};

export const permissionLabel = code => PERMISSION_LABELS[code] || code;

export const ROLE_SUMMARIES = {
  member: 'A website account without dashboard access. Uses the public site and member tools.',
  viewer: 'Read-only dashboard access to content, forms, opportunities, services and reports.',
  contributor: 'Can write and edit content, and read everything a viewer can.',
  editor: 'Runs day-to-day publishing: content, forms, opportunities, services, exports and the audit log.',
  admin: 'Full administration, including users, settings, premium controls and notifications.',
};
