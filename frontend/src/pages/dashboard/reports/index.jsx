import { Activity, BookOpen, BriefcaseBusiness, ClipboardList, Download, FileJson, FileSpreadsheet, FileText, FolderTree, HelpCircle, Images, Inbox, Lock, PenLine, RefreshCw, Search, Settings, Tags, UserPlus, Users, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import ActionMenu from '../../../components/dashboard/ActionMenu';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import AdminPagination from '../../../components/dashboard/AdminPagination';
import { DashboardCard, DonutSummary, Drawer, SimpleBarChart, StatCard, StateBlock, Tabs, TrendChart } from '../../../components/dashboard/DashboardPrimitives';
import { hasPermission, relativeTime, shortDate } from '../users/adminShared';
import '../../../styles/dashboard/dash-admin.css';

// One entry per export module: label, icon, description and the group it is listed under.
const EXPORTS = {
  posts: ['Posts', BookOpen, 'Articles and pages with status, dates, authors and SEO fields.', 'Content'],
  categories: ['Categories', FolderTree, 'Category names, slugs and article counts.', 'Content'],
  tags: ['Tags', Tags, 'Tag names and slugs.', 'Content'],
  authors: ['Authors', PenLine, 'Author profiles used for article bylines.', 'Content'],
  media: ['Media', Images, 'Media library files, URLs and alt text.', 'Content'],
  'faq-categories': ['FAQ categories', HelpCircle, 'FAQ groups and their order.', 'Content'],
  'faq-items': ['FAQ items', HelpCircle, 'Questions, answers and visibility.', 'Content'],
  users: ['Users', Users, 'Accounts with role, plan, status and last login.', 'People'],
  'join-team': ['Join the team', UserPlus, 'Volunteer and team sign-ups.', 'People'],
  applications: ['Applications', FileText, 'Team applications and their status.', 'People'],
  contacts: ['Contacts', Inbox, 'Contact form messages and their status.', 'Engagement'],
  opportunities: ['Opportunities', BriefcaseBusiness, 'Research opportunities with status and deadlines.', 'Engagement'],
  services: ['Services', ClipboardList, 'Service catalogue entries.', 'Services'],
  'service-requests': ['Service requests', ClipboardList, 'Requests from visitors and their status.', 'Services'],
  activity: ['Activity', Activity, 'The dashboard audit trail.', 'System'],
  settings: ['Settings', Settings, 'Public site settings (no secrets are stored here).', 'System'],
};
const GROUP_ORDER = ['Content', 'People', 'Engagement', 'Services', 'System'];
const ACTIONS = [['create', 'Create'], ['update', 'Update'], ['delete', 'Delete'], ['status', 'Status change'], ['login', 'Login'], ['export', 'Export'], ['system', 'System']];
const KNOWN_MODULES = ['auth', 'content', 'contacts', 'faq', 'forms', 'media', 'newsletter', 'notifications', 'opportunities', 'reports', 'services', 'settings', 'team', 'users'];
const UPPER = { faq: 'FAQ', auth: 'Sign-in' };
const pretty = value => UPPER[value] || String(value || '').replaceAll('_', ' ').replaceAll('-', ' ').replace(/^\w/, letter => letter.toUpperCase());
const statusRows = rows => (rows || []).map(row => ({ status: pretty(row.status), count: row.count }));

export default function DashboardReportsPage() {
  const { user, bootstrap } = useOutletContext() || {};
  const canReadActivity = hasPermission(user, bootstrap, 'activity.view');
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = ['overview', 'exports', 'activity'].includes(searchParams.get('tab')) ? searchParams.get('tab') : 'overview';
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const [exportQuery, setExportQuery] = useState('');

  const load = () => { setError(''); DashboardApi.getReports().then(setReport).catch(err => setError(err.message)); };
  useEffect(() => { load(); }, []);
  const setTab = value => { const params = new URLSearchParams(searchParams); if (value === 'overview') params.delete('tab'); else params.set('tab', value); setSearchParams(params, { replace: true }); };

  const summary = report?.summary || {};
  const exports = useMemo(() => {
    const rows = report?.exports || (report?.export_modules || []).map(module => ({ module, allowed: true }));
    const q = exportQuery.trim().toLowerCase();
    return rows.filter(row => {
      const [label, , text] = EXPORTS[row.module] || [row.module, null, ''];
      return !q || `${label} ${text} ${row.module}`.toLowerCase().includes(q);
    });
  }, [report, exportQuery]);
  const grouped = GROUP_ORDER.map(group => [group, exports.filter(row => (EXPORTS[row.module]?.[3] || 'System') === group)]).filter(([, rows]) => rows.length);
  const signups = (report?.signups_trend || []).map(item => ({ label: shortDate(item.week), count: item.count }));
  const tiers = (report?.users_by_tier || []).map(row => ({ status: pretty(row.membership_profile__tier || 'no profile'), count: row.count }));
  const allowedExports = (report?.exports || []).filter(row => row.allowed).length;

  return (
    <div className="dash-adm-page">
      <AdminPageHeader
        eyebrow="Insights"
        title="Reports and Analytics"
        text="Platform analytics at a glance, data exports for leadership and audit, and the full dashboard activity log."
        actions={<button type="button" className="admin-button admin-button-secondary" onClick={load}><RefreshCw size={15} /> Refresh</button>}
      />
      {error && <AdminNotice type="error">{error}</AdminNotice>}

      <section className="dash-stat-grid dash-adm-stat-6" aria-label="Platform summary">
        <StatCard icon={Users} label="Users" value={summary.users ?? 0} hint={`${summary.active_users || 0} active`} to="/dashboard/users" loading={!report} />
        <StatCard icon={FileText} label="Content" value={summary.content_items ?? 0} hint={`${summary.published_content || 0} published`} to="/dashboard/posts" loading={!report} />
        <StatCard icon={ClipboardList} label="Service requests" value={summary.service_requests ?? 0} hint="All time" to="/dashboard/services?tab=requests" loading={!report} />
        <StatCard icon={BriefcaseBusiness} label="Open opportunities" value={summary.open_opportunities ?? 0} hint="Currently open" to="/dashboard/opportunities" loading={!report} />
        <StatCard icon={Inbox} label="New forms 30d" value={summary.new_forms_30_days ?? 0} hint="Contacts + applications" to="/dashboard/forms" loading={!report} />
        <StatCard icon={Activity} label="Activity 30d" value={report?.activity_30_days ?? 0} hint="Dashboard actions logged" loading={!report} />
      </section>

      <div className="dash-adm-tabbar">
        <Tabs label="Report sections" value={tab} onChange={setTab} tabs={[
          { id: 'overview', label: 'Analytics' },
          { id: 'exports', label: 'Exports', count: report ? (report.exports ? allowedExports : (report.export_modules || []).length) : undefined },
          { id: 'activity', label: 'Activity log' },
        ]} />
      </div>

      {!report && !error && <StateBlock type="loading" title="Loading reports" text="Preparing analytics from backend data..." />}

      {report && tab === 'overview' && (
        <div className="dash-adm-grid">
          <DashboardCard title="New accounts" eyebrow="Sign-ups per week, last 12 weeks" className="dash-adm-span-7">
            <div className="dash-trend-summary">
              <span><strong>{signups.reduce((sum, item) => sum + item.count, 0)}</strong><small>in 12 weeks</small></span>
              <span><strong>{signups.slice(-4).reduce((sum, item) => sum + item.count, 0)}</strong><small>last 4 weeks</small></span>
              <span><strong>{summary.active_users || 0}</strong><small>active accounts</small></span>
            </div>
            {signups.length ? <TrendChart data={signups} label="New accounts per week" /> : <StateBlock type="empty" title="No sign-up data" />}
          </DashboardCard>
          <DashboardCard title="Content by Status" eyebrow="Content analytics" className="dash-adm-span-5">
            <DonutSummary data={statusRows(report.content_by_status)} totalLabel="Content" />
          </DashboardCard>
          <DashboardCard title="Service Requests" eyebrow="Service analytics" className="dash-adm-span-4">
            {report.services_by_status?.length ? <SimpleBarChart data={statusRows(report.services_by_status)} /> : <StateBlock type="empty" title="No service requests yet" />}
          </DashboardCard>
          <DashboardCard title="Research Opportunities" eyebrow="Research analytics" className="dash-adm-span-4">
            {report.opportunities_by_status?.length ? <SimpleBarChart data={statusRows(report.opportunities_by_status)} /> : <StateBlock type="empty" title="No opportunities yet" />}
          </DashboardCard>
          <DashboardCard title="Forms by Status" eyebrow="Forms analytics" className="dash-adm-span-4">
            {report.forms_by_status?.length ? <SimpleBarChart data={statusRows(report.forms_by_status)} /> : <StateBlock type="empty" title="No form submissions yet" />}
          </DashboardCard>
          {tiers.length > 0 && <DashboardCard title="Accounts by plan" eyebrow="Free and Premium" className="dash-adm-span-5">
            <DonutSummary data={tiers} totalLabel="Accounts" />
          </DashboardCard>}
          <DashboardCard title="Where the team works" eyebrow="Dashboard actions by area, last 30 days" className={tiers.length ? 'dash-adm-span-7' : 'dash-adm-span-12'} actions={canReadActivity && <button type="button" className="dash-adm-link" onClick={() => setTab('activity')}>Open activity log</button>}>
            {report.activity_by_module?.length ? <SimpleBarChart data={report.activity_by_module.map(row => ({ status: pretty(row.module), count: row.count }))} /> : <StateBlock type="empty" title="No recent activity" text="Dashboard actions are recorded in the audit trail." />}
          </DashboardCard>
        </div>
      )}

      {report && tab === 'exports' && (
        <section className="dashboard-card dash-adm-card">
          <div className="dash-adm-section-head">
            <div><h2>Exports</h2><p>Download any module as CSV, Excel, JSON or PDF. Up to 2,000 rows per export; every export is recorded in the activity log.</p></div>
            <label className="dash-search-field dash-adm-export-search"><Search size={16} aria-hidden="true" /><input type="search" value={exportQuery} onChange={event => setExportQuery(event.target.value)} placeholder="Find an export" aria-label="Find an export" />{exportQuery && <button type="button" className="dash-adm-clear" onClick={() => setExportQuery('')} aria-label="Clear"><X size={14} /></button>}</label>
          </div>
          {grouped.length === 0 && <StateBlock type="empty" title="No exports match" text="Try a different word." />}
          {grouped.map(([group, rows]) => (
            <div className="dash-adm-export-group" key={group}>
              <h3>{group}</h3>
              <div className="dash-adm-export-grid">
                {rows.map(row => {
                  const [label, Icon = FileSpreadsheet, text] = EXPORTS[row.module] || [pretty(row.module), FileSpreadsheet, ''];
                  return (
                    <article key={row.module} className={row.allowed ? '' : 'is-locked'}>
                      <span className="dash-adm-export-icon" aria-hidden="true"><Icon size={18} /></span>
                      <div className="dash-adm-export-copy"><strong>{label}</strong><small>{text || `Export ${label.toLowerCase()} records.`}</small></div>
                      {row.allowed ? (
                        <div className="dash-adm-export-actions">
                          <a className="admin-button admin-button-secondary" href={DashboardApi.exportUrl(row.module, 'csv')}><Download size={14} /> Export CSV</a>
                          <ActionMenu label={`More formats for ${label}`} items={[
                            { label: 'Excel (.xls)', icon: FileSpreadsheet, href: DashboardApi.exportUrl(row.module, 'excel') },
                            { label: 'JSON', icon: FileJson, href: DashboardApi.exportUrl(row.module, 'json'), external: true },
                            { label: 'PDF (needs reportlab)', icon: FileText, href: DashboardApi.exportUrl(row.module, 'pdf') },
                          ]} />
                        </div>
                      ) : <span className="dash-adm-pill is-off" title={`Requires ${row.permission}`}><Lock size={12} /> Needs {row.permission}</span>}
                    </article>
                  );
                })}
              </div>
            </div>
          ))}
          <p className="editor-hint">PDF export is wired on the backend and becomes active when `reportlab` is installed on the server.</p>
        </section>
      )}

      {tab === 'activity' && (canReadActivity
        ? <ActivityLog moduleOptions={[...new Set([...KNOWN_MODULES, ...(report?.activity_by_module || []).map(row => row.module)])].sort()} />
        : <StateBlock type="empty" title="The activity log is restricted" text="Reading the audit trail needs the activity.read permission (Editor role or above)." />)}
    </div>
  );
}

function ActivityLog({ moduleOptions }) {
  const [filters, setFilters] = useState({ module: '', action: '', q: '', page: 1 });
  const [query, setQuery] = useState('');
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);

  const load = useCallback(() => {
    setLoading(true); setError('');
    DashboardApi.getActivity({ ...filters, per_page: 25 })
      .then(data => { setRows(data.results || []); setPagination(data.pagination); })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [filters]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (query === filters.q) return undefined;
    const timer = setTimeout(() => setFilters(current => ({ ...current, q: query, page: 1 })), 350);
    return () => clearTimeout(timer);
  }, [query, filters.q]);
  const update = patch => setFilters(current => ({ ...current, ...patch, page: patch.page || 1 }));
  const active = ['module', 'action', 'q'].filter(key => filters[key]).length;

  return (
    <section className="dashboard-card dash-adm-card">
      <div className="dash-adm-section-head">
        <div><h2>Activity log</h2><p>Every create, update, status change, export and sign-in recorded by the dashboard.</p></div>
        <a className="admin-button admin-button-secondary" href={DashboardApi.exportUrl('activity', 'csv')}><Download size={15} /> Export CSV</a>
      </div>
      <div className="dash-adm-toolbar dash-adm-toolbar-inline">
        <label className="dash-search-field"><Search size={16} aria-hidden="true" /><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search messages and records" aria-label="Search activity" /></label>
        <div className="dash-adm-filters">
          <label><span>Area</span><select value={filters.module} onChange={event => update({ module: event.target.value })}><option value="">All areas</option>{moduleOptions.map(module => <option key={module} value={module}>{pretty(module)}</option>)}</select></label>
          <label><span>Action</span><select value={filters.action} onChange={event => update({ action: event.target.value })}><option value="">All actions</option>{ACTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        </div>
      </div>
      <div className="dash-adm-resultbar">
        <span>{loading ? 'Loading activity…' : `${pagination?.total_items ?? rows.length} entries`}</span>
        <span className="dash-adm-resultbar-actions">
          {active > 0 && <button type="button" className="dash-adm-link" onClick={() => { setQuery(''); setFilters({ module: '', action: '', q: '', page: 1 }); }}><X size={13} /> Clear filters ({active})</button>}
          <button type="button" className="dash-adm-link" onClick={load}><RefreshCw size={13} /> Refresh</button>
        </span>
      </div>
      {error && <AdminNotice type="error">{error}</AdminNotice>}
      {loading && !rows.length ? <StateBlock type="loading" title="Loading activity" /> : rows.length === 0 ? <StateBlock type="empty" title="No activity found" text={active ? 'Try changing the filters.' : 'Dashboard actions will appear here.'} /> : (
        <ol className="dash-adm-log">
          {rows.map(item => (
            <li key={item.id}>
              <button type="button" onClick={() => setSelected(item)}>
                <span className={`dash-adm-log-dot is-${item.action}`} aria-hidden="true" />
                <span className="dash-adm-log-main">
                  <strong>{item.message}</strong>
                  <small>{item.actor || 'System'} · <time dateTime={item.created_at} title={new Date(item.created_at).toLocaleString()}>{relativeTime(item.created_at)}</time></small>
                </span>
                <span className="dash-adm-log-tags"><span className="dash-adm-pill is-info">{pretty(item.module)}</span><span className={`dash-adm-pill is-action-${item.action}`}>{pretty(item.action)}</span></span>
              </button>
            </li>
          ))}
        </ol>
      )}
      <AdminPagination pagination={pagination} onPage={page => update({ page })} />
      <Drawer open={Boolean(selected)} title="Activity details" subtitle={selected ? new Date(selected.created_at).toLocaleString() : ''} onClose={() => setSelected(null)}>
        {selected && (
          <dl className="dash-adm-details">
            <div><dt>What happened</dt><dd>{selected.message}</dd></div>
            <div><dt>By</dt><dd>{selected.actor || 'System'}</dd></div>
            <div><dt>Area</dt><dd>{pretty(selected.module)}</dd></div>
            <div><dt>Action</dt><dd>{pretty(selected.action)}</dd></div>
            {(selected.object_label || selected.object_id) && <div><dt>Record</dt><dd>{selected.object_label || '—'}{selected.object_id ? ` (#${selected.object_id})` : ''}</dd></div>}
            {selected.metadata && Object.keys(selected.metadata).length > 0 && <div><dt>Details</dt><dd><pre>{JSON.stringify(selected.metadata, null, 2)}</pre></dd></div>}
          </dl>
        )}
      </Drawer>
    </section>
  );
}
