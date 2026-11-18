import { ArrowUpRight, BarChart3, Briefcase, Code2, Download, ExternalLink, FileText, Megaphone, Palette, PenLine, Plus, RefreshCw, Reply, Save, Search, SearchCheck, Trash2, UserRoundSearch, Users } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import ActionMenu from '../../../components/dashboard/ActionMenu';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import AdminPagination from '../../../components/dashboard/AdminPagination';
import { Drawer, StateBlock, StatusPill, Tabs } from '../../../components/dashboard/DashboardPrimitives';
import '../../../styles/dashboard/dash-engagement.css';
import { safeHref } from '../../../utils/safeHref';
import { Avatar, CopyButton, DetailList, StatusSteps, formatDate, formatDateTime, label, mailtoHref, relativeTime, usePermissions, useMediaQuery, whatsappHref } from './engagementKit';

const applicationStatuses = ['new', 'reviewing', 'interview', 'accepted', 'rejected'];
const teamStatuses = ['published', 'draft', 'archived'];
const iconOptions = [
  ['pen', 'Education / writing', PenLine],
  ['megaphone', 'Media', Megaphone],
  ['palette', 'Design', Palette],
  ['code', 'Technology', Code2],
  ['chart', 'Data', BarChart3],
  ['search', 'Quality control', SearchCheck],
  ['users', 'Web / SEO', Users],
  ['briefcase', 'General role', Briefcase],
];
const iconFor = key => (iconOptions.find(([value]) => value === key) || iconOptions[7])[2];

const emptyTeamEntry = {
  title: '',
  slug: '',
  description: '',
  icon_key: 'briefcase',
  action_label: 'Apply to join',
  action_url: '#team-application',
  status: 'published',
  sort_order: 0,
  seo_title: '',
  seo_description: '',
};

export default function DashboardApplicationsPage() {
  const [searchParams] = useSearchParams();
  const { can } = usePermissions();
  const canWrite = can('forms.write');
  const compact = useMediaQuery('(max-width: 1023px)');
  const [view, setView] = useState(searchParams.get('tab') === 'cards' ? 'cards' : 'applications');
  // The sidebar link opens this tab even when the page is already open.
  useEffect(() => { if (searchParams.get('tab') === 'cards') setView('cards'); }, [searchParams]);
  const [applications, setApplications] = useState([]);
  const [counts, setCounts] = useState({});
  const [teams, setTeams] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [filters, setFilters] = useState({ status: '', team: '', q: '', page: 1 });
  const [search, setSearch] = useState('');
  const [teamEntries, setTeamEntries] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [editingTeam, setEditingTeam] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const loadApplications = async (next = filters) => {
    const data = await DashboardApi.getApplications(next);
    setApplications(data.results || []);
    setCounts(data.counts || {});
    setTeams(data.teams || []);
    setPagination(data.pagination || null);
  };
  const loadTeamEntries = async () => {
    const data = await DashboardApi.getJoinTeamEntries({ per_page: 80 });
    setTeamEntries(data.results || []);
  };
  const loadAll = async () => {
    setError(''); setLoading(true);
    try { await Promise.all([loadApplications(), loadTeamEntries()]); } catch (err) { setError(err.message); } finally { setLoading(false); }
  };
  useEffect(() => { loadAll(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const applyFilters = patch => {
    const next = { ...filters, page: 1, ...patch };
    setFilters(next); setLoading(true);
    loadApplications(next).catch(err => setError(err.message)).finally(() => setLoading(false));
  };
  const selected = applications.find(item => item.id === selectedId) || null;
  const teamName = value => teams.find(team => team.value === value)?.label || label(value);

  const saveApplication = async (item, patch) => {
    setBusy(true); setError(''); setNotice('');
    try {
      const data = await DashboardApi.updateApplication(item.id, { status: item.status, notes: item.notes || '', ...patch });
      setApplications(current => current.map(row => row.id === item.id ? data.application : row));
      if (patch.status && patch.status !== item.status) setCounts(current => ({ ...current, [item.status]: Math.max((current[item.status] || 1) - 1, 0), [patch.status]: (current[patch.status] || 0) + 1 }));
      setNotice(patch.notes !== undefined ? 'Application review saved.' : `${item.full_name} moved to ${label(patch.status).toLowerCase()}.`);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };

  const updateTeam = event => {
    const { name, value } = event.target;
    setEditingTeam(current => ({ ...current, [name]: name === 'sort_order' ? Number(value) : value }));
  };
  const saveTeam = async event => {
    event.preventDefault();
    setError('');
    try {
      const data = await DashboardApi.saveJoinTeamEntry({ ...editingTeam, action_url: (editingTeam.action_url || '').trim() || '#team-application' }, editingTeam.id);
      setEditingTeam(data.entry);
      setNotice('Join Our Team card saved.');
      await loadTeamEntries();
    } catch (err) { setError(err.message); }
  };
  const deleteTeam = async (entry = editingTeam) => {
    if (!entry?.id || !window.confirm(`Delete "${entry.title}" from the Join Our Team page?`)) return;
    setError('');
    try {
      await DashboardApi.deleteJoinTeamEntry(entry.id);
      if (editingTeam?.id === entry.id) setEditingTeam(null);
      setNotice('Join Our Team card deleted.');
      await loadTeamEntries();
    } catch (err) { setError(err.message); }
  };
  const setTeamStatus = async (entry, status) => {
    setError('');
    try { await DashboardApi.saveJoinTeamEntry({ ...entry, status }, entry.id); setNotice(`“${entry.title}” is now ${status}.`); await loadTeamEntries(); }
    catch (err) { setError(err.message); }
  };

  const reader = selected && <ApplicationReader key={selected.id} item={selected} teamName={teamName} busy={busy} canWrite={canWrite} onSave={patch => saveApplication(selected, patch)} />;
  const publishedCards = teamEntries.filter(entry => entry.status === 'published').length;

  return (
    <div className="eng-page">
      <AdminPageHeader
        eyebrow="Engagement"
        title="Join Our Team Manager"
        text="Edit public team cards, external Google Form links, SEO copy, and submitted team applications from one secure dashboard screen."
        actions={<>
          <a className="admin-button admin-button-secondary" href="/join" target="_blank" rel="noreferrer"><ExternalLink size={15} /> View Join page</a>
          <ActionMenu label="Exports" icon={Download} items={[
            { label: 'Export applications (CSV)', icon: Download, href: DashboardApi.exportUrl('applications', 'csv') },
            { label: 'Export team cards (CSV)', icon: Download, href: DashboardApi.exportUrl('join-team', 'csv') },
          ]} />
          <button type="button" className="admin-button admin-button-secondary" onClick={loadAll} disabled={loading}><RefreshCw size={15} /> Refresh</button>
        </>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}
      {error && <AdminNotice type="error">{error}</AdminNotice>}

      <Tabs label="Join Our Team sections" value={view} onChange={setView} tabs={[
        { id: 'applications', label: 'Submitted applications', count: counts.all ?? 0 },
        { id: 'cards', label: 'Public team cards', count: teamEntries.length },
      ]} />

      {view === 'applications' && <>
        <div className="eng-filterbar">
          <Tabs label="Application status" value={filters.status} onChange={status => applyFilters({ status })} tabs={['', ...applicationStatuses].map(id => ({ id, label: id ? label(id) : 'All', count: counts[id || 'all'] ?? 0 }))} />
          <form className="eng-filterbar-tools" onSubmit={event => { event.preventDefault(); applyFilters({ q: search.trim() }); }}>
            <label className="dash-search-field"><Search size={16} aria-hidden="true" /><input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search name, email, motivation" aria-label="Search applications" /></label>
            <select value={filters.team} onChange={event => applyFilters({ team: event.target.value })} aria-label="Filter by team"><option value="">All teams</option>{teams.map(team => <option key={team.value} value={team.value}>{team.label}</option>)}</select>
          </form>
        </div>
        <div className="eng-split">
          <section className="eng-list-panel" aria-label="Applications">
            <header className="eng-list-head"><strong>{pagination?.total_items ?? applications.length} application{(pagination?.total_items ?? applications.length) === 1 ? '' : 's'}</strong>{(filters.q || filters.team) && <button type="button" className="eng-link" onClick={() => { setSearch(''); applyFilters({ q: '', team: '' }); }}>Clear filters</button>}</header>
            {loading && !applications.length ? <StateBlock type="loading" title="Loading applications" /> : applications.length ? (
              <ul className="eng-list">
                {applications.map(item => (
                  <li key={item.id}>
                    <button type="button" className={`eng-list-item ${item.id === selectedId ? 'is-selected' : ''} ${item.status === 'new' ? 'is-unread' : ''}`} onClick={() => setSelectedId(item.id)} aria-current={item.id === selectedId ? 'true' : undefined}>
                      <Avatar name={item.full_name} />
                      <span className="eng-list-body">
                        <span className="eng-list-top"><strong>{item.full_name}</strong><time dateTime={item.created_at} title={formatDateTime(item.created_at)}>{relativeTime(item.created_at)}</time></span>
                        <span className="eng-list-sub">{item.email}</span>
                        <span className="eng-list-tags"><span className="eng-type-tag"><Users size={12} />{teamName(item.team)}</span>{item.has_cv && <span className="eng-type-tag"><FileText size={12} />CV</span>}<StatusPill value={item.status} /></span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : <StateBlock type="empty" title="No applications found" text="Try another status, team or search." />}
            <AdminPagination pagination={pagination} onPage={page => applyFilters({ page })} />
          </section>
          {!compact && <section className="eng-reader-panel" aria-label="Selected application">{reader || <div className="eng-reader-empty"><UserRoundSearch size={30} aria-hidden="true" /><strong>Choose an application</strong><p>Select a candidate from the left to review details, download the CV and add notes.</p></div>}</section>}
        </div>
        {compact && <Drawer open={Boolean(selected)} title={selected?.full_name || 'Application'} subtitle={selected ? teamName(selected.team) : ''} onClose={() => setSelectedId(null)} width={640}>{reader}</Drawer>}
      </>}

      {view === 'cards' && (
        <section className="eng-card">
          <div className="eng-card-head">
            <div><span className="dash-eyebrow">Public Join Page</span><h2>Editable team cards and form links</h2><p>{publishedCards} of {teamEntries.length} cards are published on the Join Our Team page. Cards are shown in sort order.</p></div>
            {canWrite && <button type="button" className="admin-button" onClick={() => setEditingTeam(emptyTeamEntry)}><Plus size={15} /> Add Team Card</button>}
          </div>
          {loading && !teamEntries.length ? <StateBlock type="loading" title="Loading team cards" /> : teamEntries.length ? (
            <div className="eng-card-grid">
              {teamEntries.map(entry => {
                const Icon = iconFor(entry.icon_key);
                const external = /^https?:\/\//i.test(entry.action_url || '');
                return (
                  <article key={entry.id} className={`eng-tile ${entry.status !== 'published' ? 'is-muted' : ''}`}>
                    <button type="button" className="eng-tile-open" onClick={() => setEditingTeam(entry)} aria-label={`Edit ${entry.title}`} />
                    <div className="eng-tile-head"><span className="eng-tile-icon"><Icon size={20} /></span><div><strong>{entry.title}</strong><small>{entry.action_label}</small></div></div>
                    <p>{entry.description}</p>
                    <div className="eng-tile-meta"><StatusPill value={entry.status} /><span>#{entry.sort_order}</span><span>{external ? 'Google Form linked' : 'No form link yet'}</span></div>
                    <ActionMenu label={`Actions for ${entry.title}`} items={[
                      { label: canWrite ? 'Edit card' : 'View card', icon: PenLine, onClick: () => setEditingTeam(entry) },
                      external && { label: 'Test form link', icon: ExternalLink, href: entry.action_url, external: true },
                      canWrite && { divider: true },
                      ...(canWrite ? teamStatuses.filter(status => status !== entry.status).map(status => ({ label: `Set ${status}`, icon: ArrowUpRight, onClick: () => setTeamStatus(entry, status) })) : []),
                      canWrite && { divider: true },
                      canWrite && { label: 'Delete card', icon: Trash2, danger: true, onClick: () => deleteTeam(entry) },
                    ]} />
                  </article>
                );
              })}
            </div>
          ) : <StateBlock type="empty" title="No team cards yet" text="Add the first public team card for the Join Our Team page." />}
        </section>
      )}

      <Drawer open={Boolean(editingTeam)} title={editingTeam?.id ? 'Edit team card' : 'New team card'} subtitle="Shown on the public Join Our Team page" onClose={() => setEditingTeam(null)} width={640}
        footer={editingTeam && <>
          {editingTeam.id && canWrite && <button type="button" className="admin-button admin-button-danger" onClick={() => deleteTeam()}><Trash2 size={15} /> Delete</button>}
          <span className="eng-drawer-footer-spacer" />
          <button type="button" className="admin-button admin-button-secondary" onClick={() => setEditingTeam(null)}>Close</button>
          {canWrite && <button className="admin-button" form="team-card-editor"><Save size={15} /> Save Team Card</button>}
        </>}>
        {editingTeam && (
          <form id="team-card-editor" className="eng-form" onSubmit={saveTeam}>
            <fieldset className="eng-fieldset" disabled={!canWrite}>
              <legend>Card</legend>
              <div className="eng-form-grid">
                <label>Team title<input required name="title" value={editingTeam.title || ''} onChange={updateTeam} maxLength="120" /></label>
                <label>Slug<input name="slug" value={editingTeam.slug || ''} onChange={updateTeam} placeholder="Auto-generated when empty" /></label>
                <label>Icon<select name="icon_key" value={editingTeam.icon_key || 'briefcase'} onChange={updateTeam}>{iconOptions.map(([value, text]) => <option value={value} key={value}>{text}</option>)}</select></label>
                <label>Status<select name="status" value={editingTeam.status || 'published'} onChange={updateTeam}>{teamStatuses.map(status => <option value={status} key={status}>{status}</option>)}</select></label>
                <label>Sort order<input type="number" name="sort_order" value={editingTeam.sort_order ?? 0} onChange={updateTeam} min="0" /></label>
              </div>
              <label>Description <small>{(editingTeam.description || '').length}/500</small><textarea required name="description" value={editingTeam.description || ''} onChange={updateTeam} rows="4" maxLength="500" /></label>
            </fieldset>
            <fieldset className="eng-fieldset" disabled={!canWrite}>
              <legend>Button and form link</legend>
              <div className="eng-form-grid">
                <label>Button label<input required name="action_label" value={editingTeam.action_label || ''} onChange={updateTeam} maxLength="80" /></label>
                <label>Google Form link<input name="action_url" value={(editingTeam.action_url || '').startsWith('#') ? '' : editingTeam.action_url || ''} onChange={updateTeam} placeholder="https://docs.google.com/forms/d/e/.../viewform" /></label>
              </div>
              <p className="admin-form-help">Paste the full link ending in /viewform and the form opens inside the site. Other links open in a new tab. Leave it empty and the card says “Applications opening soon”.</p>
              {editingTeam.action_url && /^https?:\/\//i.test(editingTeam.action_url) && <a className="admin-button admin-button-secondary" href={editingTeam.action_url} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Test Link</a>}
            </fieldset>
            <fieldset className="eng-fieldset" disabled={!canWrite}>
              <legend>Search appearance</legend>
              <label>SEO title <small>{(editingTeam.seo_title || '').length}/70</small><input name="seo_title" value={editingTeam.seo_title || ''} onChange={updateTeam} maxLength="70" /></label>
              <label>SEO description <small>{(editingTeam.seo_description || '').length}/170</small><input name="seo_description" value={editingTeam.seo_description || ''} onChange={updateTeam} maxLength="170" /></label>
            </fieldset>
            {editingTeam.updated_at && <small className="eng-hint">Last updated {formatDate(editingTeam.updated_at)}</small>}
          </form>
        )}
      </Drawer>
    </div>
  );
}

function ApplicationReader({ item, teamName, busy, canWrite, onSave }) {
  const [notes, setNotes] = useState(item.notes || '');
  const whatsapp = whatsappHref(item.whatsapp);
  return (
    <article className="eng-reader">
      <header className="eng-reader-head">
        <Avatar name={item.full_name} size="lg" />
        <div>
          <h2>{item.full_name}</h2>
          <p><a href={mailtoHref(item.email)}>{item.email}</a>{item.whatsapp && <> · {item.whatsapp}</>}</p>
          <small>Applied {formatDateTime(item.created_at)} · {teamName(item.team)}</small>
        </div>
      </header>
      <div className="eng-reader-actions">
        <a className="admin-button" href={mailtoHref(item.email, 'Your ResRef team application')}><Reply size={15} /> Reply by email</a>
        <CopyButton text={item.email} />
        {whatsapp && <a className="admin-button admin-button-secondary" href={whatsapp} target="_blank" rel="noreferrer">WhatsApp</a>}
      </div>
      {item.cv_url
        ? <div className="eng-cv-card"><FileText size={26} /><div><strong>Applicant CV</strong><small>Private file — downloads are logged.</small></div><a className="admin-button" href={item.cv_url} download><Download size={15} /> Download CV</a></div>
        : <div className="eng-cv-card is-missing"><FileText size={26} /><div><strong>No CV uploaded</strong><small>This applicant did not attach a CV.</small></div></div>}
      <div className="eng-reader-section">
        <span className="eng-section-label">Status</span>
        <StatusSteps name="Application status" statuses={applicationStatuses} value={item.status} onChange={status => onSave({ status })} disabled={busy || !canWrite} />
      </div>
      <DetailList items={[
        ['Email', item.email],
        ['WhatsApp', item.whatsapp || '-'],
        ['Team', teamName(item.team)],
        ['Portfolio', item.portfolio && <a href={safeHref(item.portfolio)} target="_blank" rel="noreferrer">Open portfolio <ArrowUpRight size={12} /></a>],
      ]} />
      <div className="eng-message"><span className="eng-section-label">Experience</span><p>{item.experience || '-'}</p></div>
      <div className="eng-message"><span className="eng-section-label">Motivation</span><p>{item.motivation || '-'}</p></div>
      <form className="eng-note-form" onSubmit={event => { event.preventDefault(); onSave({ notes }); }}>
        <label>Private Review Notes<textarea value={notes} onChange={event => setNotes(event.target.value)} rows="6" disabled={!canWrite} placeholder="Only visible to the dashboard team" /></label>
        <div className="eng-note-actions"><small className="eng-hint">Never shown to the applicant.</small>{canWrite && <button className="admin-button" disabled={busy}><Save size={15} /> Save Review</button>}</div>
      </form>
    </article>
  );
}
