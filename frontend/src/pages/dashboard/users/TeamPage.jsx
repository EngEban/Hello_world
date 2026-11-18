import { Building2, CalendarDays, Copy, ExternalLink, Mail, Search, ShieldCheck, UserCog, Users } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import ActionMenu from '../../../components/dashboard/ActionMenu';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import { StatCard, StateBlock, StatusPill, Tabs } from '../../../components/dashboard/DashboardPrimitives';
import '../../../styles/dashboard/dash-engagement.css';
import { Avatar, formatDate } from '../contacts/engagementKit';

const isLocalFrontend = ['127.0.0.1', 'localhost'].includes(window.location.hostname);
const DJANGO_USERS_URL = import.meta.env.VITE_DJANGO_ADMIN_USERS_URL || (isLocalFrontend ? 'http://127.0.0.1:8000/admin/auth/user/' : '');

const accessOf = user => (user.is_superuser ? 'superuser' : user.is_staff ? 'staff' : 'member');
const nameOf = user => (user.first_name || user.last_name ? `${user.first_name} ${user.last_name}`.trim() : user.display_name || user.username);

export default function DashboardTeamPage() {
  const [members, setMembers] = useState([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [access, setAccess] = useState('');
  const [department, setDepartment] = useState('');

  useEffect(() => {
    DashboardApi.getTeamMembers().then(data => setMembers(data.results || [])).catch(err => setError(err.message)).finally(() => setLoading(false));
  }, []);

  const counts = useMemo(() => members.reduce((acc, user) => {
    acc[accessOf(user)] += 1;
    if (!user.is_active) acc.inactive += 1;
    return acc;
  }, { superuser: 0, staff: 0, member: 0, inactive: 0 }), [members]);
  const departments = useMemo(() => [...new Set(members.map(user => user.department).filter(Boolean))].sort(), [members]);
  const visible = members.filter(user => {
    if (access === 'inactive' ? user.is_active : access && accessOf(user) !== access) return false;
    if (department && user.department !== department) return false;
    if (!query) return true;
    const haystack = `${nameOf(user)} ${user.username} ${user.email} ${user.role} ${user.department}`.toLowerCase();
    return haystack.includes(query.toLowerCase());
  });
  const copy = async email => {
    try { await navigator.clipboard.writeText(email); setNotice(`${email} copied.`); } catch { setError('Could not copy from this browser.'); }
  };

  return (
    <div className="eng-page">
      <AdminPageHeader
        eyebrow="People"
        title="Team Members"
        text="Review team members and volunteer profiles. Use User Management for dashboard access, staff roles, and account status."
        actions={<>
          <Link className="admin-button" to="/dashboard/users"><UserCog size={15} /> User Management</Link>
          {DJANGO_USERS_URL && <a className="admin-button admin-button-secondary" href={DJANGO_USERS_URL} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Django Users</a>}
        </>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}
      {error && <AdminNotice type="error">{error}</AdminNotice>}

      <section className="dash-stat-grid" aria-label="Team summary">
        <StatCard icon={Users} label="People" value={members.length} hint="All accounts" loading={loading} />
        <StatCard icon={ShieldCheck} label="Superusers" value={counts.superuser} hint="Full access" loading={loading} />
        <StatCard icon={UserCog} label="Staff" value={counts.staff} hint="Dashboard staff" loading={loading} />
        <StatCard icon={Building2} label="Departments" value={departments.length} hint={counts.inactive ? `${counts.inactive} inactive accounts` : 'With assigned members'} loading={loading} />
      </section>

      <div className="eng-filterbar">
        <Tabs label="Access level" value={access} onChange={setAccess} tabs={[
          { id: '', label: 'Everyone', count: members.length },
          { id: 'superuser', label: 'Superusers', count: counts.superuser },
          { id: 'staff', label: 'Staff', count: counts.staff },
          { id: 'member', label: 'Members', count: counts.member },
          ...(counts.inactive ? [{ id: 'inactive', label: 'Inactive', count: counts.inactive }] : []),
        ]} />
        <div className="eng-filterbar-tools">
          <label className="dash-search-field"><Search size={16} aria-hidden="true" /><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search name, email, role" aria-label="Search team members" /></label>
          {departments.length > 0 && <select value={department} onChange={event => setDepartment(event.target.value)} aria-label="Filter by department"><option value="">All departments</option>{departments.map(item => <option key={item}>{item}</option>)}</select>}
        </div>
      </div>

      {loading ? <StateBlock type="loading" title="Loading team" /> : visible.length ? (
        <div className="eng-card-grid">
          {visible.map(user => (
            <article key={user.id} className={`eng-tile ${user.is_active ? '' : 'is-muted'}`}>
              <div className="eng-tile-head">
                <Avatar name={nameOf(user)} size="lg" />
                <div><strong title={nameOf(user)}>{nameOf(user)}</strong><small title={user.username}>@{user.username}</small></div>
              </div>
              <div className="eng-member-roles">
                <span className="eng-role">{user.role || (user.is_superuser ? 'admin' : 'member')}</span>
                <StatusPill value={accessOf(user)} />
                {!user.is_active && <StatusPill value="inactive" />}
              </div>
              <div className="eng-tile-meta">
                <span><Mail size={13} />{user.email || '—'}</span>
                <span><Building2 size={13} />{user.department || 'No department'}</span>
                {user.date_joined && <span><CalendarDays size={13} />Joined {formatDate(user.date_joined)}</span>}
              </div>
              <ActionMenu label={`Actions for ${nameOf(user)}`} items={[
                user.email && { label: 'Send email', icon: Mail, href: `mailto:${user.email}` },
                user.email && { label: 'Copy email', icon: Copy, onClick: () => copy(user.email) },
                { divider: true },
                { label: 'Manage access in User Management', icon: UserCog, href: '/dashboard/users' },
              ]} />
            </article>
          ))}
        </div>
      ) : <StateBlock type="empty" title={members.length ? 'No matching people' : 'No users found'} text={members.length ? 'Try another access level, department or search.' : ''} />}
    </div>
  );
}
