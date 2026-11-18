import { BellRing, CheckCircle2, Copy, Download, Info, Lock, Mail, Pencil, Plus, RefreshCw, Save, Search, ShieldCheck, SlidersHorizontal, Sparkles, UserCheck, UserCog, Users, UserX, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useOutletContext, useSearchParams } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import ActionMenu from '../../../components/dashboard/ActionMenu';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import AdminPagination from '../../../components/dashboard/AdminPagination';
import { DashboardModal, DashboardTable, Drawer, StatCard } from '../../../components/dashboard/DashboardPrimitives';
import { hasPermission, initials, permissionLabel, relativeTime, ROLE_SUMMARIES } from './adminShared';
import '../../../styles/dashboard/dash-admin.css';

const emptyUser = { email: '', username: '', first_name: '', last_name: '', display_name: '', is_active: true, is_staff: true, access_role: 'editor', tier: 'free', premium_until: '', email_verified: false, organization: '', specialization: '', team_role: 'viewer', department: '' };
const FILTER_DEFAULTS = { q: '', status: '', access_role: '', tier: '', dashboard_access: '', role: '', sort: '-date_joined', per_page: '25', page: '1' };
const ROLE_LABELS = { member: 'Member', viewer: 'Viewer', contributor: 'Contributor', editor: 'Editor', admin: 'Administrator' };
const ROLE_ORDER = ['member', 'viewer', 'contributor', 'editor', 'admin'];

const PRESETS = {
  free: { label: 'Free', icon: UserCheck, patch: () => ({ tier: 'free', configured_tier: 'free', premium_until: '' }) },
  premium: { label: 'Premium 1 year', icon: Sparkles, patch: () => { const next = new Date(); next.setFullYear(next.getFullYear() + 1); const until = next.toISOString().slice(0, 10); return { tier: 'premium', configured_tier: 'premium', premium_until: until }; } },
  dashboardEditor: { label: 'Editor access', icon: ShieldCheck, patch: () => ({ is_staff: true, is_active: true, access_role: 'editor', team_role: 'editor' }) },
  dashboardAdmin: { label: 'Admin access', icon: Lock, patch: () => ({ is_staff: true, is_active: true, access_role: 'admin', team_role: 'admin' }) },
  revokeDashboard: { label: 'Revoke dashboard', icon: UserX, patch: () => ({ is_staff: false, access_role: 'member', team_role: 'viewer' }) },
  deactivate: { label: 'Deactivate', icon: UserX, danger: true, patch: () => ({ is_active: false, is_staff: false, access_role: 'member', team_role: 'viewer' }) },
};

const roleOf = row => (row.is_superuser ? 'superadmin' : row.role || row.access_role || 'member');
const roleLabel = (row, roles) => (row.is_superuser ? 'Super admin' : roleName(roles, roleOf(row)));
const displayName = row => row.display_name || [row.first_name, row.last_name].filter(Boolean).join(' ') || row.email || row.username;

export default function DashboardUsersPage() {
  const { user: me, bootstrap } = useOutletContext() || {};
  const canWrite = hasPermission(me, bootstrap, 'users.edit');
  const canCreate = hasPermission(me, bootstrap, 'users.create');
  const canExport = hasPermission(me, bootstrap, 'reports.manage');
  const canNotify = hasPermission(me, bootstrap, 'notifications.create');
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(() => Object.fromEntries(Object.entries(FILTER_DEFAULTS).map(([key, fallback]) => [key, searchParams.get(key) || fallback])), [searchParams]);
  const filterKey = JSON.stringify(filters);
  const [query, setQuery] = useState(filters.q);
  const [users, setUsers] = useState([]);
  const [summary, setSummary] = useState(null);
  const [pagination, setPagination] = useState(null);
  const [editing, setEditing] = useState(searchParams.get('new') ? emptyUser : null);
  const [original, setOriginal] = useState(searchParams.get('new') ? JSON.stringify(emptyUser) : null);
  const [featureRules, setFeatureRules] = useState([]);
  const [roles, setRoles] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [showRoles, setShowRoles] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const requestRef = useRef(0);

  const load = useCallback(async (next = filters) => {
    const request = ++requestRef.current;
    setLoading(true); setError('');
    try {
      const data = await DashboardApi.getUsers(next);
      if (request !== requestRef.current) return;
      setUsers(data.results || []);
      setPagination(data.pagination);
      if (data.summary) setSummary(data.summary);
    } catch (err) {
      if (request === requestRef.current) setError(err.message);
    } finally {
      if (request === requestRef.current) setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterKey]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    DashboardApi.getFeatureEntitlements().then(data => setFeatureRules(data.results || [])).catch(() => setFeatureRules([]));
    DashboardApi.getRolesPermissions().then(setRoles).catch(() => setRoles(null));
  }, []);
  useEffect(() => { setQuery(filters.q); }, [filters.q]);
  // Search as you type (debounced); the Search button applies immediately.
  useEffect(() => {
    if (query === filters.q) return undefined;
    const timer = setTimeout(() => updateFilter({ q: query }), 350);
    return () => clearTimeout(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const updateFilter = patch => {
    const next = { ...filters, ...patch, page: patch.page || '1' };
    const params = new URLSearchParams();
    Object.entries(next).forEach(([key, value]) => { if (value && value !== FILTER_DEFAULTS[key]) params.set(key, value); });
    setSearchParams(params, { replace: true });
  };
  const clearFilters = () => { setQuery(''); setSearchParams(new URLSearchParams(), { replace: true }); };
  const activeFilterCount = ['q', 'status', 'access_role', 'tier', 'dashboard_access', 'role'].filter(key => filters[key]).length;

  const openEditor = row => { setEditing(row); setOriginal(JSON.stringify(row)); };
  const dirty = editing && original !== JSON.stringify(editing);
  const closeEditor = () => {
    if (dirty && !window.confirm('Discard the unsaved changes to this user?')) return;
    setEditing(null); setOriginal(null);
    if (searchParams.get('new')) { const params = new URLSearchParams(searchParams); params.delete('new'); setSearchParams(params, { replace: true }); }
  };
  const update = event => {
    const { name, value, type, checked } = event.target;
    setEditing(current => ({
      ...current,
      [name]: type === 'checkbox' ? checked : value,
      ...(name === 'tier' ? { configured_tier: value } : {}),
    }));
  };
  const applyPreset = preset => setEditing(current => ({ ...current, ...(PRESETS[preset]?.patch() || {}) }));

  const effectivePreviewTier = useMemo(() => {
    if (!editing) return 'free';
    const tier = editing.configured_tier || editing.tier || 'free';
    if (tier !== 'premium') return 'free';
    if (!editing.premium_until) return 'premium';
    const expiry = new Date(`${String(editing.premium_until).slice(0, 10)}T23:59:59`);
    return expiry.getTime() >= Date.now() ? 'premium' : 'free';
  }, [editing]);
  const featurePreview = useMemo(() => {
    if (!editing) return [];
    if (featureRules.length > 0) {
      return featureRules.filter(feature => feature.is_active).map(feature => ({
        code: feature.code, label: feature.label, description: feature.description,
        allowed: effectivePreviewTier === 'premium' ? feature.premium_enabled : feature.free_enabled,
      }));
    }
    return Object.entries(editing.features || {}).map(([code, feature]) => ({ code, ...feature }));
  }, [editing, effectivePreviewTier, featureRules]);

  // Mirrors the backend's role resolution closely enough to explain what the form will grant.
  const previewRole = useMemo(() => {
    if (!editing) return 'member';
    if (editing.is_superuser) return 'admin';
    // A dashboard role assigned on the Roles & Permissions page decides on its own.
    const assigned = (roles?.roles || []).find(role => role.code === editing.account_role && role.is_active);
    if (editing.is_active && assigned) return assigned.full_access ? 'admin' : assigned.code;
    if (!editing.is_active || !editing.is_staff) return 'member';
    const candidates = [editing.team_role || 'viewer'];
    if (editing.access_role === 'admin' || editing.access_role === 'editor') candidates.push(editing.access_role);
    return ['admin', 'editor', 'contributor', 'viewer'].find(role => candidates.includes(role)) || 'member';
  }, [editing, roles]);
  const rolePermissions = useMemo(() => {
    const map = Object.fromEntries((roles?.roles || []).map(role => [role.code, role.permissions]));
    return id => map[id] || (id === 'member' ? [] : null);
  }, [roles]);

  const persist = async (payload, message) => {
    setSaving(true); setError(''); setNotice('');
    try {
      const data = await DashboardApi.saveUser(payload, payload.id);
      setNotice(message ? message(data.user) : `User saved: ${data.user.email}`);
      await load();
      return data.user;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setSaving(false);
    }
  };
  const save = async event => {
    event.preventDefault();
    const saved = await persist(editing);
    if (saved) { setEditing(null); setOriginal(null); if (searchParams.get('new')) { const params = new URLSearchParams(searchParams); params.delete('new'); setSearchParams(params, { replace: true }); } }
  };

  const quickAction = (row, preset) => setPendingAction({ row, preset });
  const runPendingAction = async () => {
    const { row, preset } = pendingAction;
    const patch = preset === 'activate' ? { is_active: true } : PRESETS[preset].patch();
    setPendingAction(null);
    await persist({ ...row, ...patch }, saved => `${displayName(saved)} updated: ${preset === 'activate' ? 'account activated' : PRESETS[preset].label.toLowerCase()}.`);
  };
  const copyEmail = async row => {
    try { await navigator.clipboard.writeText(row.email); setNotice(`Copied ${row.email}`); } catch { setError('Copying is not available in this browser.'); }
  };

  const rowActions = row => [
    { label: canWrite ? 'Edit user' : 'View user', icon: Pencil, onClick: () => openEditor(row) },
    canWrite && (row.is_active
      ? { label: 'Deactivate account', icon: UserX, danger: true, onClick: () => quickAction(row, 'deactivate'), disabled: row.id === me?.id }
      : { label: 'Activate account', icon: UserCheck, onClick: () => quickAction(row, 'activate') }),
    canWrite && { divider: true },
    canWrite && { label: 'Role: Editor access', icon: ShieldCheck, onClick: () => quickAction(row, 'dashboardEditor'), disabled: row.id === me?.id },
    canWrite && { label: 'Role: Admin access', icon: Lock, onClick: () => quickAction(row, 'dashboardAdmin'), disabled: row.id === me?.id },
    canWrite && { label: 'Role: Member (no dashboard)', icon: UserX, onClick: () => quickAction(row, 'revokeDashboard'), disabled: row.id === me?.id },
    { divider: true },
    { label: 'Copy email', icon: Copy, onClick: () => copyEmail(row) },
    { label: 'Email user', icon: Mail, href: `mailto:${row.email}` },
    canNotify && row.is_active && { label: 'Send a notification', icon: BellRing, href: `/dashboard/notifications?user=${row.id}` },
  ];

  const columns = [
    { key: 'display_name', label: 'User', render: row => (
      <span className="dash-adm-person">
        <span className={`dash-adm-avatar ${row.is_active ? '' : 'is-muted'}`} aria-hidden="true">{initials(displayName(row))}</span>
        <span><strong>{displayName(row)}</strong><small>{row.email}</small></span>
      </span>
    ) },
    { key: 'role', label: 'Role', render: row => (
      <span className="dash-adm-stack">
        <span className={`dash-adm-pill is-role-${roleOf(row)}`}>{roleLabel(row, roles)}</span>
        {row.department && <small>{row.department}</small>}
      </span>
    ) },
    { key: 'tier', label: 'Plan', render: row => (
      <span className="dash-adm-stack">
        <span className={`dash-adm-pill ${row.tier === 'premium' ? 'is-premium' : 'is-free'}`}>{row.tier === 'premium' ? <><Sparkles size={12} /> Premium</> : 'Free'}</span>
        {row.premium_until && <small>until {new Date(row.premium_until).toLocaleDateString()}</small>}
      </span>
    ) },
    { key: 'can_access_dashboard', label: 'Dashboard', render: row => <span className={`dash-adm-pill ${row.can_access_dashboard && row.is_active ? 'is-ok' : 'is-off'}`}>{row.can_access_dashboard && row.is_active ? 'Allowed' : 'No access'}</span> },
    { key: 'is_active', label: 'Status', render: row => <span className={`dash-adm-status ${row.is_active ? 'is-active' : 'is-inactive'}`}><i aria-hidden="true" />{row.is_active ? 'Active' : 'Inactive'}{row.is_active && !row.email_verified && <small>Email not verified</small>}</span> },
    { key: 'last_login', label: 'Last login', render: row => <span className="dash-adm-muted" title={row.last_login ? new Date(row.last_login).toLocaleString() : ''}>{row.last_login ? relativeTime(row.last_login) : 'Never'}</span> },
    { key: 'actions', label: 'Actions', render: row => <span className="dash-adm-row-actions" onClick={event => event.stopPropagation()} onKeyDown={event => event.stopPropagation()}><ActionMenu items={rowActions(row)} label={`Actions for ${displayName(row)}`} /></span> },
  ];

  const s = summary || {};
  const editingRole = editing ? (editing.id ? roleOf(editing) : previewRole) : 'member';
  const shownPermissions = editing ? rolePermissions(previewRole) : null;

  return (
    <div className="dash-adm-page">
      <AdminPageHeader
        eyebrow="People"
        title="User Management"
        text="Manage dashboard access, roles, account status, departments and Free/Premium plans from one place."
        actions={<>
          {canExport && <a className="admin-button admin-button-secondary" href={DashboardApi.exportUrl('users', 'csv')}><Download size={15} /> Export CSV</a>}
          {canCreate && <button type="button" className="admin-button" onClick={() => openEditor(emptyUser)}><Plus size={15} /> Add User</button>}
        </>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}
      {error && <AdminNotice type="error">{error}</AdminNotice>}

      <section className="dash-stat-grid" aria-label="User summary">
        <StatCard icon={Users} label="Total users" value={s.total ?? 0} hint={summary ? `${s.joined_30_days || 0} joined in 30 days` : ''} to="/dashboard/users" loading={!summary} />
        <StatCard icon={CheckCircle2} label="Active" value={s.active ?? 0} hint={summary ? `${s.inactive || 0} inactive` : ''} to="/dashboard/users?status=active" loading={!summary} tone={s.inactive ? 'amber' : 'blue'} />
        <StatCard icon={ShieldCheck} label="Dashboard access" value={s.dashboard_access ?? 0} hint={summary ? `${s.admins || 0} administrators` : ''} to="/dashboard/users?dashboard_access=yes" loading={!summary} />
        <StatCard icon={Sparkles} label="Premium" value={s.premium ?? 0} hint="Members on a Premium plan" to="/dashboard/users?tier=premium" loading={!summary} />
      </section>

      <section className="dashboard-card dash-adm-card dash-adm-cards dash-adm-users">
        <div className="dash-adm-toolbar">
          <form className="dash-search-field" role="search" onSubmit={event => { event.preventDefault(); updateFilter({ q: query }); }}>
            <Search size={16} aria-hidden="true" />
            <input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search by name, email, username or organization" aria-label="Search users" />
            {query && <button type="button" className="dash-adm-clear" onClick={() => { setQuery(''); updateFilter({ q: '' }); }} aria-label="Clear search"><X size={14} /></button>}
            <button type="submit" className="admin-button dash-adm-search-btn">Search</button>
          </form>
          <button type="button" className="dash-adm-filter-toggle" aria-expanded={filtersOpen} aria-controls="user-filters" onClick={() => setFiltersOpen(current => !current)}><SlidersHorizontal size={15} /> Filters and sort{activeFilterCount ? ` (${activeFilterCount})` : ''}</button>
          <div id="user-filters" className={`dash-adm-filters ${filtersOpen ? 'is-open' : ''}`}>
            <label><span>Status</span><select value={filters.status} onChange={event => updateFilter({ status: event.target.value })}><option value="">All status</option><option value="active">Active</option><option value="inactive">Inactive</option></select></label>
            <label><span>Effective role</span><select value={filters.role} onChange={event => updateFilter({ role: event.target.value })}><option value="">All roles</option>{['member', ...(roles?.roles?.length ? roles.roles.map(role => role.code) : ROLE_ORDER.slice(1))].map(role => <option key={role} value={role}>{roleName(roles, role)}</option>)}</select></label>
            <label><span>Access role</span><select value={filters.access_role} onChange={event => updateFilter({ access_role: event.target.value })}><option value="">All access roles</option><option value="member">Member</option><option value="editor">Editor</option><option value="admin">Administrator</option></select></label>
            <label><span>Plan</span><select value={filters.tier} onChange={event => updateFilter({ tier: event.target.value })}><option value="">All tiers</option><option value="free">Free</option><option value="premium">Premium</option></select></label>
            <label><span>Dashboard</span><select value={filters.dashboard_access} onChange={event => updateFilter({ dashboard_access: event.target.value })}><option value="">Dashboard access</option><option value="yes">Can access</option><option value="no">No access</option></select></label>
            <label><span>Sort</span><select value={filters.sort} onChange={event => updateFilter({ sort: event.target.value })}><option value="-date_joined">Newest first</option><option value="date_joined">Oldest first</option><option value="-last_login">Recent login</option><option value="email">Email A–Z</option></select></label>
          </div>
        </div>
        <div className="dash-adm-resultbar">
          <span>{loading ? 'Loading users…' : `${pagination?.total_items ?? users.length} ${(pagination?.total_items ?? users.length) === 1 ? 'user' : 'users'}${activeFilterCount ? ' match your filters' : ''}`}</span>
          <span className="dash-adm-resultbar-actions">
            {activeFilterCount > 0 && <button type="button" className="dash-adm-link" onClick={clearFilters}><X size={13} /> Clear filters ({activeFilterCount})</button>}
            <button type="button" className="dash-adm-link" onClick={() => setShowRoles(current => !current)} aria-expanded={showRoles}><Info size={13} /> {showRoles ? 'Hide' : 'What can each role do?'}</button>
            <button type="button" className="dash-adm-link" onClick={() => load()}><RefreshCw size={13} /> Refresh</button>
          </span>
        </div>
        {showRoles && <RoleGuide roles={roles} />}
        <DashboardTable loading={loading && !users.length} rows={users} onRowClick={openEditor} emptyTitle={activeFilterCount ? 'No users match these filters' : 'No users yet'} columns={columns} />
        <div className="dash-adm-footer-row">
          <label className="dash-adm-perpage"><span>Rows per page</span><select value={filters.per_page} onChange={event => updateFilter({ per_page: event.target.value })}><option value="25">25</option><option value="50">50</option><option value="100">100</option></select></label>
          <AdminPagination pagination={pagination} onPage={page => updateFilter({ page: String(page) })} />
        </div>
      </section>

      <Drawer
        open={Boolean(editing)}
        width={640}
        title={editing?.id ? (canWrite ? 'Edit User' : 'User details') : 'Add User'}
        subtitle={editing?.id ? `${editing.email} · joined ${editing.date_joined ? new Date(editing.date_joined).toLocaleDateString() : '—'}${editing.last_login ? ` · last login ${relativeTime(editing.last_login)}` : ''}` : 'Create a dashboard or member account.'}
        onClose={closeEditor}
        footer={<>
          {dirty && <span className="dash-adm-unsaved"><i aria-hidden="true" />Unsaved changes</span>}
          <button className="admin-button admin-button-secondary" type="button" onClick={closeEditor}>Cancel</button>
          {(editing?.id ? canWrite : canCreate) && <button className="admin-button" type="submit" form="user-editor" disabled={saving}><Save size={15} /> {saving ? 'Saving…' : 'Save User'}</button>}
        </>}
      >
        {editing && (
          <form id="user-editor" className="dashboard-form dash-adm-form" onSubmit={save}>
            {editing.id && (
              <div className="dash-adm-identity">
                <span className={`dash-adm-avatar is-large ${editing.is_active ? '' : 'is-muted'}`} aria-hidden="true">{initials(displayName(editing))}</span>
                <div>
                  <strong>{displayName(editing)}</strong>
                  <span className="dash-adm-identity-pills">
                    <span className={`dash-adm-pill is-role-${editingRole}`}>{roleLabel(editing, roles)}</span>
                    <span className={`dash-adm-pill ${editing.tier === 'premium' ? 'is-premium' : 'is-free'}`}>{editing.tier === 'premium' ? 'Premium' : 'Free'}</span>
                    <span className={`dash-adm-status ${editing.is_active ? 'is-active' : 'is-inactive'}`}><i aria-hidden="true" />{editing.is_active ? 'Active' : 'Inactive'}</span>
                    <span className={`dash-adm-pill ${editing.can_access_dashboard && editing.is_active ? 'is-ok' : 'is-off'}`}>{editing.can_access_dashboard && editing.is_active ? 'Dashboard allowed' : 'No dashboard access'}</span>
                    {editing.auth_provider && editing.auth_provider !== 'password' && <span className="dash-adm-pill is-free">Signs in with {editing.auth_provider}</span>}
                  </span>
                </div>
              </div>
            )}
            <fieldset disabled={!(editing?.id ? canWrite : canCreate)} className="dash-adm-fieldset">
              <section className="dash-adm-form-section">
                <h3>Account identity</h3>
                <div className="admin-form-grid">
                  <label>Email<input required type="email" name="email" value={editing.email || ''} onChange={update} autoComplete="off" /></label>
                  <label>Username<input name="username" value={editing.username || ''} onChange={update} placeholder="Defaults to email" autoComplete="off" /></label>
                  <label>First name<input name="first_name" value={editing.first_name || ''} onChange={update} /></label>
                  <label>Last name<input name="last_name" value={editing.last_name || ''} onChange={update} /></label>
                  <label>Display name<input name="display_name" value={editing.display_name || ''} onChange={update} /></label>
                  <label>Organization<input name="organization" value={editing.organization || ''} onChange={update} /></label>
                  <label>Specialization<input name="specialization" value={editing.specialization || ''} onChange={update} /></label>
                  {editing.id && <p className="editor-hint">Country: <strong>{editing.country || 'Not given'}</strong> · Phone: <strong>{editing.phone_number || 'Not given'}</strong> (members edit these on their account page)</p>}
                  {!editing.id && <label>Temporary password<input type="password" name="password" value={editing.password || ''} onChange={update} placeholder="Optional; otherwise unusable password" autoComplete="new-password" /></label>}
                </div>
              </section>
              <section className="dash-adm-form-section">
                <h3>Access and plan</h3>
                <p className="dash-adm-hint">Presets fill in the fields below; nothing changes until you save.</p>
                <div className="user-preset-row dash-adm-presets">
                  {Object.entries(PRESETS).map(([key, preset]) => { const Icon = preset.icon; return <button key={key} className={preset.danger ? 'danger' : ''} type="button" onClick={() => applyPreset(key)}><Icon size={14} /> {preset.label}</button>; })}
                </div>
                <div className="admin-form-grid">
                  <label>Department<input name="department" value={editing.department || ''} onChange={update} /></label>
                  <label>Dashboard role<select name="access_role" value={editing.access_role || 'editor'} onChange={update}><option value="member">Member</option><option value="editor">Editor</option><option value="admin">Administrator</option></select></label>
                  <label>Team role<select name="team_role" value={editing.team_role || editing.role || 'viewer'} onChange={update}><option value="viewer">Viewer</option><option value="contributor">Contributor</option><option value="editor">Editor</option><option value="admin">Admin</option></select></label>
                  <label>Account tier<select name="tier" value={editing.configured_tier || editing.tier || 'free'} onChange={update}><option value="free">Free</option><option value="premium">Premium</option></select></label>
                  <label>Premium until<input type="date" name="premium_until" value={(editing.premium_until || '').slice(0, 10)} onChange={update} /></label>
                </div>
                <div className="dash-adm-switches">
                  <label className="admin-check"><input type="checkbox" name="is_staff" checked={Boolean(editing.is_staff)} onChange={update} /><span>Allow dashboard staff access<small>Required to sign in to this dashboard.</small></span></label>
                  <label className="admin-check"><input type="checkbox" name="is_active" checked={Boolean(editing.is_active)} onChange={update} /><span>Active user<small>Inactive accounts cannot sign in anywhere.</small></span></label>
                  <label className="admin-check"><input type="checkbox" name="email_verified" checked={Boolean(editing.email_verified)} onChange={update} /><span>Email verified</span></label>
                </div>
              </section>
            </fieldset>

            <section className="dash-adm-form-section dash-adm-permissions">
              <h3>What this account can do in the dashboard</h3>
              <p className="dash-adm-hint">
                {editing.is_superuser ? 'Super administrators always have every permission.' : <>With these settings the effective role is <strong>{roleName(roles, previewRole)}</strong>. {roleSummary(roles, previewRole)} <Link to={`/dashboard/roles?role=${previewRole}`}>Roles &amp; Permissions</Link></>}
              </p>
              {editing.is_superuser || previewRole === 'admin'
                ? <p className="dash-adm-allperms"><ShieldCheck size={15} /> {permissionLabel('*')}</p>
                : previewRole === 'member'
                  ? <p className="dash-adm-allperms is-off"><UserX size={15} /> No dashboard access. The account can still use the public website{editing.is_active ? '' : ' once it is active again'}.</p>
                  : shownPermissions
                    ? <ul className="dash-adm-permlist">{shownPermissions.filter(code => code !== 'dashboard.view').map(code => <li key={code}><CheckCircle2 size={14} />{actionLabel(roles, code)}</li>)}</ul>
                    : <p className="dash-adm-hint">Role details are visible to administrators with settings access.</p>}
            </section>

            {featurePreview.length > 0 && (
              <section className="user-feature-preview dash-adm-form-section">
                <h3>Feature access preview</h3>
                <p>Previewing the <strong>{effectivePreviewTier}</strong> tier from the current form values and the Free/Premium rules in <Link to="/dashboard/premium-controls">Premium controls</Link>.</p>
                <div>
                  {featurePreview.map(feature => (
                    <span className={feature.allowed ? 'allowed' : 'blocked'} key={feature.code} title={feature.description || ''}>
                      {feature.label}
                      <small>{feature.allowed ? 'Allowed' : 'Blocked'}</small>
                    </span>
                  ))}
                </div>
              </section>
            )}
            <p className="editor-hint"><ShieldCheck size={14} /> Permissions are role-based and checked again on the server: you cannot grant more access than your own role allows, and only a super administrator can change billing or super-admin accounts.</p>
          </form>
        )}
      </Drawer>

      {pendingAction && (() => {
        const { row, preset } = pendingAction;
        const isActivate = preset === 'activate';
        const meta = isActivate ? { label: 'Activate account' } : PRESETS[preset];
        const descriptions = {
          activate: 'The account can sign in again. Its role and plan are unchanged.',
          deactivate: 'The account is signed out of everything, loses dashboard staff access and becomes a Member. You can reactivate it later.',
          dashboardEditor: 'Grants dashboard staff access with the Editor role (publishing, forms, opportunities, services, exports).',
          dashboardAdmin: 'Grants full dashboard administration, including users and settings.',
          revokeDashboard: 'Removes dashboard staff access. The website account and plan stay as they are.',
        };
        return (
          <DashboardModal title={`${meta.label}?`} onClose={() => setPendingAction(null)} footer={<>
            <button type="button" className="admin-button admin-button-secondary" onClick={() => setPendingAction(null)}>Cancel</button>
            <button type="button" className={`admin-button ${preset === 'deactivate' ? 'admin-button-danger' : ''}`} onClick={runPendingAction} disabled={saving}>{meta.label}</button>
          </>}>
            <div className="dash-adm-confirm">
              <span className="dash-adm-person"><span className="dash-adm-avatar" aria-hidden="true">{initials(displayName(row))}</span><span><strong>{displayName(row)}</strong><small>{row.email}</small></span></span>
              <p>{descriptions[preset]}</p>
            </div>
          </DashboardModal>
        );
      })()}
    </div>
  );
}

// Role names, summaries and action labels come from the Roles & Permissions data when it loaded.
function roleName(roles, code) {
  return roles?.roles?.find(role => role.code === code)?.label || ROLE_LABELS[code] || code;
}

function roleSummary(roles, code) {
  return roles?.roles?.find(role => role.code === code)?.description || ROLE_SUMMARIES[code] || '';
}

function actionLabel(roles, code) {
  const [moduleId, action] = code.split('.');
  const module = roles?.modules?.find(item => item.id === moduleId);
  return module?.actions?.[action] ? `${module.label}: ${module.actions[action]}` : permissionLabel(code);
}

function RoleGuide({ roles }) {
  const list = [{ code: 'member', label: ROLE_LABELS.member, description: ROLE_SUMMARIES.member, permissions: [] }, ...(roles?.roles || [])];
  return (
    <div className="dash-adm-roleguide" aria-label="Role permissions">
      {list.map(role => (
        <article key={role.code}>
          <header><UserCog size={15} /><strong>{role.label}</strong></header>
          <p>{role.description}</p>
          {role.full_access
            ? <small className="dash-adm-allperms"><ShieldCheck size={13} /> All permissions</small>
            : role.permissions.length > 0 && <ul>{role.permissions.filter(code => code !== 'dashboard.view').map(code => <li key={code}>{actionLabel(roles, code)}</li>)}</ul>}
        </article>
      ))}
    </div>
  );
}
