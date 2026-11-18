import { ArrowUpRight, ClipboardList, Download, ExternalLink, FileDown, FileText, Inbox, MailOpen, RefreshCw, Reply, Save, Search, Users } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import ActionMenu from '../../../components/dashboard/ActionMenu';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import { Drawer, StatCard, StateBlock, StatusPill, Tabs } from '../../../components/dashboard/DashboardPrimitives';
import '../../../styles/dashboard/dash-engagement.css';
import { safeHref } from '../../../utils/safeHref';
import { Avatar, CopyButton, DetailList, StatusSteps, formatDateTime, label, mailtoHref, relativeTime, usePermissions, useMediaQuery, whatsappHref } from './engagementKit';

const typeLabels = { contact: 'Contact', team_application: 'Team Application', service_request: 'Service Request' };
const typeIcons = { contact: Inbox, team_application: Users, service_request: ClipboardList };
const fallbackStatuses = {
  contact: ['new', 'read', 'replied', 'archived'],
  team_application: ['new', 'reviewing', 'interview', 'accepted', 'rejected'],
  service_request: ['new', 'reviewing', 'assigned', 'in_progress', 'completed', 'archived'],
};

export default function DashboardFormsPage() {
  const [searchParams] = useSearchParams();
  const { can } = usePermissions();
  const compact = useMediaQuery('(max-width: 1023px)');
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState({});
  const [statusMap, setStatusMap] = useState(fallbackStatuses);
  const [filters, setFilters] = useState({ q: '', type: searchParams.get('type') || '', status: '' });
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = async (next = filters) => {
    setLoading(true); setError('');
    try {
      const data = await DashboardApi.getFormsOverview(next);
      setItems(data.results || []);
      setSummary(data.summary || {});
      if (data.statuses) setStatusMap(data.statuses);
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const updateFilter = patch => { const next = { ...filters, ...patch }; setFilters(next); load(next); };
  const selected = items.find(item => item.id === selectedId) || null;
  const canWriteType = type => can(type === 'service_request' ? 'services.write' : 'forms.write');

  const saveItem = async (item, patch) => {
    setBusy(true); setError(''); setNotice('');
    try {
      if (item.type === 'contact') await DashboardApi.updateContact(item.record_id, { status: patch.status });
      if (item.type === 'team_application') await DashboardApi.updateApplication(item.record_id, { status: patch.status ?? item.status, notes: patch.notes ?? item.notes ?? '' });
      if (item.type === 'service_request') await DashboardApi.saveServiceRequest({ status: patch.status ?? item.status, internal_notes: patch.notes ?? item.notes ?? '' }, item.record_id);
      setItems(current => current.map(row => row.id === item.id ? { ...row, ...(patch.status ? { status: patch.status } : {}), ...(patch.notes !== undefined ? { notes: patch.notes } : {}) } : row));
      setNotice(patch.notes !== undefined ? `Notes saved for ${item.title}.` : `${typeLabels[item.type]} “${item.title}” is now ${label(patch.status).toLowerCase()}.`);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };

  const total = (summary.contacts || 0) + (summary.team_applications || 0) + (summary.service_requests || 0);
  const tabs = [
    { id: '', label: 'All forms', count: total },
    { id: 'contact', label: 'Contacts', count: summary.contacts || 0 },
    { id: 'team_application', label: 'Team applications', count: summary.team_applications || 0 },
    { id: 'service_request', label: 'Service requests', count: summary.service_requests || 0 },
  ];
  const statusOptions = filters.type ? statusMap[filters.type] || [] : [...new Set(Object.values(statusMap).flat())];
  const reader = selected && <SubmissionReader key={selected.id} item={selected} statuses={statusMap[selected.type] || []} busy={busy} canWrite={canWriteType(selected.type)} onSave={patch => saveItem(selected, patch)} />;

  return (
    <div className="eng-page">
      <AdminPageHeader
        eyebrow="Engagement"
        title="Forms and Applications"
        text="Search, filter, track, and export submitted contacts, team applications, and service requests from one operational inbox."
        actions={<>
          <a className="admin-button admin-button-secondary" href={DashboardApi.exportUrl('contacts', 'csv')}><Download size={15} /> Export Contacts</a>
          <ActionMenu label="More exports" icon={FileDown} items={[
            { label: 'Export team applications (CSV)', icon: Download, href: DashboardApi.exportUrl('applications', 'csv') },
            { label: 'Export service requests (CSV)', icon: Download, href: DashboardApi.exportUrl('service-requests', 'csv') },
          ]} />
          <button type="button" className="admin-button admin-button-secondary" onClick={() => load()} disabled={loading}><RefreshCw size={15} /> Refresh</button>
        </>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}
      {error && <AdminNotice type="error">{error}</AdminNotice>}

      <section className="dash-stat-grid" aria-label="Submission summary">
        <StatCard icon={Inbox} label="Contacts" value={summary.contacts || 0} hint={`${summary.new_contacts || 0} new · Contact form submissions`} to="/dashboard/contacts" tone={summary.new_contacts ? 'amber' : 'blue'} loading={loading && !items.length} />
        <StatCard icon={Users} label="Team applications" value={summary.team_applications || 0} hint={`${summary.new_team_applications || 0} new · Volunteer/team forms`} to="/dashboard/applications" tone={summary.new_team_applications ? 'amber' : 'blue'} loading={loading && !items.length} />
        <StatCard icon={ClipboardList} label="Service requests" value={summary.service_requests || 0} hint={`${summary.new_service_requests || 0} new · Service intake requests`} to="/dashboard/services?tab=requests" tone={summary.new_service_requests ? 'amber' : 'blue'} loading={loading && !items.length} />
      </section>

      <div className="eng-filterbar">
        <Tabs label="Form type" value={filters.type} onChange={type => { setSelectedId(null); updateFilter({ type, status: '' }); }} tabs={tabs} />
        <form className="eng-filterbar-tools" onSubmit={event => { event.preventDefault(); updateFilter({ q: search.trim() }); }}>
          <label className="dash-search-field"><Search size={16} aria-hidden="true" /><input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search submissions" aria-label="Search submissions" /></label>
          <select value={filters.status} onChange={event => updateFilter({ status: event.target.value })} aria-label="Filter by status"><option value="">All statuses</option>{statusOptions.map(status => <option key={status} value={status}>{label(status)}</option>)}</select>
          <button type="submit" className="admin-button">Search</button>
        </form>
      </div>

      <div className="eng-split">
        <section className="eng-list-panel" aria-label="Submissions">
          <header className="eng-list-head"><strong>{items.length} submission{items.length === 1 ? '' : 's'}{items.length >= 50 ? ' (latest 50)' : ''}</strong>{(filters.q || filters.status) && <button type="button" className="eng-link" onClick={() => { setSearch(''); updateFilter({ q: '', status: '' }); }}>Clear filters</button>}</header>
          {loading && !items.length ? <StateBlock type="loading" title="Loading submissions" /> : items.length ? (
            <ul className="eng-list">
              {items.map(item => {
                const Icon = typeIcons[item.type] || FileText;
                return (
                  <li key={item.id}>
                    <button type="button" className={`eng-list-item ${item.id === selectedId ? 'is-selected' : ''} ${item.status === 'new' ? 'is-unread' : ''}`} onClick={() => setSelectedId(item.id)} aria-current={item.id === selectedId ? 'true' : undefined}>
                      <Avatar name={item.title} />
                      <span className="eng-list-body">
                        <span className="eng-list-top"><strong>{item.title}</strong><time dateTime={item.created_at} title={formatDateTime(item.created_at)}>{relativeTime(item.created_at)}</time></span>
                        <span className="eng-list-sub">{item.email}</span>
                        {item.excerpt && <span className="eng-list-excerpt">{item.excerpt}</span>}
                        <span className="eng-list-tags"><span className="eng-type-tag"><Icon size={12} />{typeLabels[item.type] || item.type}</span>{item.has_cv && <span className="eng-type-tag"><FileText size={12} />CV</span>}<StatusPill value={item.status} /></span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : <StateBlock type="empty" title="No submissions found" text="Try another form type, status or search." />}
        </section>
        {!compact && <section className="eng-reader-panel" aria-label="Selected submission">{reader || <div className="eng-reader-empty"><MailOpen size={30} aria-hidden="true" /><strong>Select a submission</strong><p>Read the full submission, update its status, add notes, and download CVs without leaving this page.</p></div>}</section>}
      </div>
      {compact && <Drawer open={Boolean(selected)} title={selected?.title || 'Submission'} subtitle={selected ? `${typeLabels[selected.type]} · ${selected.email}` : ''} onClose={() => setSelectedId(null)} width={640}>{reader}</Drawer>}
    </div>
  );
}

function SubmissionReader({ item, statuses, busy, canWrite, onSave }) {
  const [notes, setNotes] = useState(item.notes || '');
  const Icon = typeIcons[item.type] || FileText;
  const whatsapp = whatsappHref(item.phone);
  const subject = item.type === 'team_application' ? 'Your ResRef team application' : item.type === 'service_request' ? `Re: ${item.title}` : 'Re: Your message to ResRef';
  const details = Object.entries(item.details || {}).map(([key, value]) => [key, key === 'Portfolio' && value ? <a href={safeHref(value)} target="_blank" rel="noreferrer">Open portfolio <ArrowUpRight size={12} /></a> : value]);
  const hasNotes = item.type !== 'contact';
  return (
    <article className="eng-reader">
      <header className="eng-reader-head">
        <Avatar name={item.title} size="lg" />
        <div>
          <h2>{item.title}</h2>
          <p><a href={mailtoHref(item.email)}>{item.email}</a></p>
          <small><span className="eng-inline-icon"><Icon size={13} />{typeLabels[item.type]}</span> · Received {formatDateTime(item.created_at)}</small>
        </div>
      </header>
      <div className="eng-reader-actions">
        <a className="admin-button" href={mailtoHref(item.email, subject)}><Reply size={15} /> Reply by email</a>
        <CopyButton text={item.email} />
        {whatsapp && <a className="admin-button admin-button-secondary" href={whatsapp} target="_blank" rel="noreferrer">WhatsApp</a>}
        <Link className="admin-button admin-button-secondary" to={item.route}><ExternalLink size={15} /> Open</Link>
      </div>
      {item.type === 'team_application' && (item.cv_url
        ? <div className="eng-cv-card"><FileText size={26} /><div><strong>Applicant CV</strong><small>Private file — downloads are logged.</small></div><a className="admin-button" href={item.cv_url} download><Download size={15} /> Download CV</a></div>
        : <div className="eng-cv-card is-missing"><FileText size={26} /><div><strong>No CV uploaded</strong><small>This applicant did not attach a CV.</small></div></div>)}
      <div className="eng-reader-section">
        <span className="eng-section-label">Status</span>
        <StatusSteps name="Status" statuses={statuses} value={item.status} onChange={status => onSave({ status })} disabled={busy || !canWrite} />
      </div>
      <DetailList items={details} />
      {item.message && <div className="eng-message"><span className="eng-section-label">{item.type === 'team_application' ? 'Motivation' : 'Message'}</span><p>{item.message}</p></div>}
      {hasNotes && (
        <form className="eng-note-form" onSubmit={event => { event.preventDefault(); onSave({ notes }); }}>
          <label>{item.type === 'team_application' ? 'Private review notes' : 'Internal notes'}<textarea value={notes} onChange={event => setNotes(event.target.value)} rows="4" disabled={!canWrite} placeholder="Only visible to the dashboard team" /></label>
          <div className="eng-note-actions"><small className="eng-hint">Notes are never shown to the person who submitted the form.</small>{canWrite && <button className="admin-button" disabled={busy || notes === (item.notes || '')}><Save size={15} /> Save notes</button>}</div>
        </form>
      )}
    </article>
  );
}
