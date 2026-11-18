import { ArrowLeft, ArrowRight, Building2, Download, Inbox, Mail, MailOpen, MessageCircle, RefreshCw, Reply, Search, Stethoscope } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { DashboardApi } from '../../../api/dashboardApi';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import AdminPagination from '../../../components/dashboard/AdminPagination';
import { Drawer, StateBlock, StatusPill, Tabs } from '../../../components/dashboard/DashboardPrimitives';
import '../../../styles/dashboard/dash-engagement.css';
import { Avatar, CopyButton, DetailList, StatusSteps, formatDateTime, mailtoHref, relativeTime, usePermissions, useMediaQuery, whatsappHref } from './engagementKit';

const statuses = ['new', 'read', 'replied', 'archived'];
const tabLabels = { '': 'All', new: 'New', read: 'Read', replied: 'Replied', archived: 'Archived' };

export default function DashboardContactsPage() {
  const { can } = usePermissions();
  const canWrite = can('forms.write');
  const compact = useMediaQuery('(max-width: 1023px)');
  const [contacts, setContacts] = useState([]);
  const [counts, setCounts] = useState({});
  const [pagination, setPagination] = useState(null);
  const [filters, setFilters] = useState({ status: '', q: '', sort: '-created_at', page: 1 });
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async (next = filters) => {
    setLoading(true); setError('');
    try {
      const data = await DashboardApi.getContacts(next);
      setContacts(data.results || []);
      setCounts(data.counts || {});
      setPagination(data.pagination || null);
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { load(filters); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const apply = patch => { const next = { ...filters, page: 1, ...patch }; setFilters(next); load(next); };
  const selected = contacts.find(item => item.id === selectedId) || null;
  const selectedIndex = contacts.findIndex(item => item.id === selectedId);

  const update = async (item, status, message) => {
    if (!canWrite || item.status === status) return;
    setBusy(true); setError('');
    try {
      const data = await DashboardApi.updateContact(item.id, { status });
      setContacts(current => current.map(row => row.id === item.id ? data.contact : row));
      setCounts(current => ({ ...current, [item.status]: Math.max((current[item.status] || 1) - 1, 0), [status]: (current[status] || 0) + 1 }));
      setNotice(message || `Marked “${item.name}” as ${status}.`);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };

  const open = item => {
    setSelectedId(item.id);
    setNotice('');
    // Opening an unread message marks it read, like any mail client; "Mark as new" undoes it.
    if (item.status === 'new' && canWrite) update(item, 'read', `Opened message from ${item.name} — marked as read.`);
  };
  const step = delta => { const next = contacts[selectedIndex + delta]; if (next) open(next); };

  const reading = selected && <ContactReader item={selected} busy={busy} canWrite={canWrite} onStatus={status => update(selected, status)} onStep={step} hasPrev={selectedIndex > 0} hasNext={selectedIndex < contacts.length - 1} />;

  return (
    <div className="eng-page">
      <AdminPageHeader
        eyebrow="Engagement"
        title="Contact Inbox"
        text="Review website messages, consultation requests, and frontend application submissions."
        actions={<>
          <a className="admin-button admin-button-secondary" href={DashboardApi.exportUrl('contacts', 'csv')}><Download size={15} /> Export CSV</a>
          <button type="button" className="admin-button admin-button-secondary" onClick={() => load(filters)} disabled={loading}><RefreshCw size={15} /> Refresh</button>
        </>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}
      {error && <AdminNotice type="error">{error}</AdminNotice>}

      <div className="eng-filterbar">
        <Tabs label="Message status" value={filters.status} onChange={status => apply({ status })} tabs={['', ...statuses].map(id => ({ id, label: tabLabels[id], count: counts[id || 'all'] ?? 0 }))} />
        <form className="eng-filterbar-tools" onSubmit={event => { event.preventDefault(); apply({ q: search.trim() }); }}>
          <label className="dash-search-field"><Search size={16} aria-hidden="true" /><input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search name, email, company or message" aria-label="Search messages" /></label>
          <select value={filters.sort} onChange={event => apply({ sort: event.target.value })} aria-label="Sort messages"><option value="-created_at">Newest first</option><option value="created_at">Oldest first</option></select>
        </form>
      </div>

      <div className={`eng-split ${selected && !compact ? 'has-selection' : ''}`}>
        <section className="eng-list-panel" aria-label="Messages">
          <header className="eng-list-head"><strong>{pagination?.total_items ?? contacts.length} {filters.status ? tabLabels[filters.status].toLowerCase() : ''} message{(pagination?.total_items ?? contacts.length) === 1 ? '' : 's'}</strong>{filters.q && <button type="button" className="eng-link" onClick={() => { setSearch(''); apply({ q: '' }); }}>Clear search “{filters.q}”</button>}</header>
          {loading && !contacts.length ? <StateBlock type="loading" title="Loading messages" /> : contacts.length ? (
            <ul className="eng-list">
              {contacts.map(item => (
                <li key={item.id}>
                  <button type="button" className={`eng-list-item ${item.id === selectedId ? 'is-selected' : ''} ${item.status === 'new' ? 'is-unread' : ''}`} onClick={() => open(item)} aria-current={item.id === selectedId ? 'true' : undefined}>
                    <Avatar name={item.name} />
                    <span className="eng-list-body">
                      <span className="eng-list-top"><strong>{item.name}</strong><time dateTime={item.created_at} title={formatDateTime(item.created_at)}>{relativeTime(item.created_at)}</time></span>
                      <span className="eng-list-sub">{item.email}{item.company ? ` · ${item.company}` : ''}</span>
                      <span className="eng-list-excerpt">{item.message}</span>
                    </span>
                    {item.status === 'new' ? <span className="eng-unread-dot" title="New" aria-label="New" /> : <StatusPill value={item.status} />}
                  </button>
                </li>
              ))}
            </ul>
          ) : <StateBlock type="empty" title={filters.q || filters.status ? 'No matching messages' : 'Inbox is empty'} text={filters.q || filters.status ? 'Try another status tab or search.' : 'New public form submissions will appear here.'} />}
          <AdminPagination pagination={pagination} onPage={page => { const next = { ...filters, page }; setFilters(next); load(next); }} />
        </section>
        {!compact && (
          <section className="eng-reader-panel" aria-label="Selected message">
            {reading || <div className="eng-reader-empty"><MailOpen size={30} aria-hidden="true" /><strong>Select a message</strong><p>Choose a message on the left to read it, reply, and move it through the workflow.</p></div>}
          </section>
        )}
      </div>

      {compact && <Drawer open={Boolean(selected)} title={selected?.name || 'Message'} subtitle={selected?.email} onClose={() => setSelectedId(null)} width={640}>{reading}</Drawer>}
    </div>
  );
}

function ContactReader({ item, busy, canWrite, onStatus, onStep, hasPrev, hasNext }) {
  const replySubject = `Re: Your message to ResRef${item.specialization ? ` (${item.specialization})` : ''}`;
  const whatsapp = whatsappHref(item.whatsapp);
  return (
    <article className="eng-reader">
      <header className="eng-reader-head">
        <Avatar name={item.name} size="lg" />
        <div>
          <h2>{item.name}</h2>
          <p><a href={mailtoHref(item.email)}>{item.email}</a>{item.whatsapp && <> · {item.whatsapp}</>}</p>
          <small>Received {formatDateTime(item.created_at)}</small>
        </div>
        <div className="eng-reader-nav">
          <button type="button" className="dash-icon-button" onClick={() => onStep(-1)} disabled={!hasPrev} aria-label="Previous message" title="Previous message"><ArrowLeft size={16} /></button>
          <button type="button" className="dash-icon-button" onClick={() => onStep(1)} disabled={!hasNext} aria-label="Next message" title="Next message"><ArrowRight size={16} /></button>
        </div>
      </header>

      <div className="eng-reader-actions">
        <a className="admin-button" href={mailtoHref(item.email, replySubject)}><Reply size={15} /> Reply by email</a>
        <CopyButton text={item.email} />
        {whatsapp && <a className="admin-button admin-button-secondary" href={whatsapp} target="_blank" rel="noreferrer"><MessageCircle size={15} /> WhatsApp</a>}
      </div>

      <div className="eng-reader-section">
        <span className="eng-section-label">Workflow status</span>
        <StatusSteps name="Workflow status" statuses={statuses} value={item.status} onChange={onStatus} disabled={busy || !canWrite} />
        {!canWrite && <small className="eng-hint">You can read messages but not change their status.</small>}
        {canWrite && item.status !== 'new' && <small className="eng-hint">After replying, set the status to Replied. <button type="button" className="eng-link" onClick={() => onStatus('new')} disabled={busy}><Mail size={13} /> Mark as new</button></small>}
      </div>

      <DetailList items={[
        ['Company', item.company && <span className="eng-inline-icon"><Building2 size={14} />{item.company}</span>],
        ['Specialization', item.specialization && <span className="eng-inline-icon"><Stethoscope size={14} />{item.specialization}</span>],
        ['WhatsApp', item.whatsapp],
        ['Type', item.company ? 'Organisation enquiry' : 'General contact'],
      ]} />

      <div className="eng-message"><span className="eng-section-label"><Inbox size={14} /> Message</span><p>{item.message}</p></div>
    </article>
  );
}
