import { ArrowRight, Columns3, Download, Inbox, LayoutList, Mail, PenLine, Plus, RefreshCw, Save, Search, Star, Trash2, UserRound } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import ActionMenu from '../../../components/dashboard/ActionMenu';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import AdminPagination from '../../../components/dashboard/AdminPagination';
import { Drawer, StateBlock, StatusPill, Tabs } from '../../../components/dashboard/DashboardPrimitives';
import '../../../styles/dashboard/dash-engagement.css';
import { CopyButton, formatDate, formatDateTime, label, mailtoHref, relativeTime, usePermissions, useMediaQuery } from '../contacts/engagementKit';

const emptyService = { title: '', slug: '', summary: '', description: '', category: '', status: 'active', assigned_team: '', price_note: '', turnaround_time: '', is_featured: false, internal_notes: '' };
const emptyRequest = { requester_name: '', requester_email: '', organization: '', subject: '', message: '', status: 'new', priority: 'normal', internal_notes: '', service: '', assigned_to: '' };
const serviceStatuses = ['active', 'paused', 'archived'];
const requestStatuses = ['new', 'reviewing', 'assigned', 'in_progress', 'completed', 'archived'];
const priorities = ['low', 'normal', 'high', 'urgent'];
const BOARD_PAGE_SIZE = 100;

export default function DashboardServicesPage() {
  const [searchParams] = useSearchParams();
  const { can } = usePermissions();
  const canCreate = can('services.create');
  const canWrite = can('services.edit');
  const canDelete = can('services.delete');
  const mobile = useMediaQuery('(max-width: 900px)');
  const [tab, setTab] = useState(searchParams.get('tab') === 'requests' ? 'requests' : 'services');
  const [requestView, setRequestView] = useState('board');
  const [showArchived, setShowArchived] = useState(false);
  const [services, setServices] = useState([]);
  const [allServices, setAllServices] = useState([]);
  const [requests, setRequests] = useState([]);
  const [serviceCounts, setServiceCounts] = useState({});
  const [requestCounts, setRequestCounts] = useState({});
  const [assignees, setAssignees] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [filters, setFilters] = useState({ q: '', status: '', page: 1, service: '', priority: '', assigned_to: '' });
  const [editing, setEditing] = useState(searchParams.get('new') ? emptyService : null);
  const [requestEditing, setRequestEditing] = useState(null);
  // A drawer saves a new record with create rights and an existing one with edit rights.
  const canSaveService = editing && !editing.id ? canCreate : canWrite;
  const canSaveRequest = requestEditing && !requestEditing.id ? canCreate : canWrite;
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const board = tab === 'requests' && requestView === 'board';
  const load = async (next = filters, nextTab = tab, nextBoard = board) => {
    setLoading(true); setError('');
    try {
      if (nextTab === 'requests') {
        const params = nextBoard ? { ...next, status: '', page: 1, per_page: BOARD_PAGE_SIZE } : next;
        const data = await DashboardApi.getServiceRequests(params);
        setRequests(data.results || []);
        setRequestCounts(data.counts || {});
        if (data.assignees) setAssignees(data.assignees);
        setPagination(nextBoard ? null : data.pagination);
      } else {
        const data = await DashboardApi.getServices(next);
        setServices(data.results || []);
        setServiceCounts(data.counts || {});
        setPagination(data.pagination);
      }
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  };
  const loadAllServices = () => DashboardApi.getServices({ per_page: 100 }).then(data => { setAllServices(data.results || []); setServiceCounts(data.counts || {}); }).catch(() => {});
  useEffect(() => {
    load();
    loadAllServices();
    // Counts for the other tab so both tab badges are filled.
    if (tab === 'services') DashboardApi.getServiceRequests({ per_page: 1 }).then(data => { setRequestCounts(data.counts || {}); setAssignees(data.assignees || []); }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const emptyFilters = { q: '', status: '', page: 1, service: '', priority: '', assigned_to: '' };
  const switchTab = value => { setTab(value); setFilters(emptyFilters); load(emptyFilters, value, value === 'requests' && requestView === 'board'); };
  const switchView = value => { setRequestView(value); const next = { ...filters, page: 1 }; setFilters(next); load(next, 'requests', value === 'board'); };
  const updateFilter = patch => { const next = { ...filters, ...patch, page: 1 }; setFilters(next); load(next); };
  const changePage = page => { const next = { ...filters, page }; setFilters(next); load(next); };
  const updateService = event => {
    const { name, value, type, checked } = event.target;
    setEditing(current => ({ ...current, [name]: type === 'checkbox' ? checked : value }));
  };
  const updateRequest = event => {
    const { name, value } = event.target;
    setRequestEditing(current => ({ ...current, [name]: value }));
  };
  const saveService = async event => {
    event.preventDefault();
    setSaving(true);
    try { await DashboardApi.saveService(editing, editing.id); setNotice('Service saved.'); setEditing(null); await load(filters, 'services'); loadAllServices(); }
    catch (err) { setError(err.message); } finally { setSaving(false); }
  };
  const saveRequest = async event => {
    event.preventDefault();
    setSaving(true);
    try { await DashboardApi.saveServiceRequest(requestEditing, requestEditing.id); setNotice('Service request saved.'); setRequestEditing(null); await load(filters, 'requests'); }
    catch (err) { setError(err.message); } finally { setSaving(false); }
  };
  const deleteService = async (item = editing) => {
    if (!item?.id || !window.confirm(`Delete "${item.title}"?`)) return;
    try { await DashboardApi.deleteService(item.id); setNotice('Service deleted.'); if (editing?.id === item.id) setEditing(null); await load(filters, 'services'); loadAllServices(); }
    catch (err) { setError(err.message); }
  };
  const setServiceStatus = async (item, status) => {
    try { await DashboardApi.saveService({ ...item, status }, item.id); setNotice(`“${item.title}” is now ${status}.`); await load(filters, 'services'); }
    catch (err) { setError(err.message); }
  };
  const moveRequest = async (item, status) => {
    setError('');
    setRequests(current => current.map(row => row.id === item.id ? { ...row, status } : row));
    try {
      await DashboardApi.saveServiceRequest({ status }, item.id);
      setRequestCounts(current => ({ ...current, [item.status]: Math.max((current[item.status] || 1) - 1, 0), [status]: (current[status] || 0) + 1 }));
      setNotice(`“${item.subject}” moved to ${label(status).toLowerCase()}.`);
      if (!board) load(filters, 'requests');
    } catch (err) { setError(err.message); setRequests(current => current.map(row => row.id === item.id ? item : row)); }
  };
  const viewServiceRequests = service => { setTab('requests'); const next = { ...emptyFilters, service: String(service.id) }; setFilters(next); load(next, 'requests', requestView === 'board'); };

  const requestMenu = row => [
    { label: canWrite ? 'Open and edit' : 'View request', icon: PenLine, onClick: () => setRequestEditing(row) },
    { label: 'Email requester', icon: Mail, href: mailtoHref(row.requester_email, `Re: ${row.subject}`) },
    canWrite && { divider: true },
    ...(canWrite ? requestStatuses.filter(status => status !== row.status).map(status => ({ label: `Move to ${label(status).toLowerCase()}`, icon: ArrowRight, onClick: () => moveRequest(row, status) })) : []),
  ];
  const narrowed = Boolean(filters.q || filters.service || filters.priority || filters.assigned_to);
  const visibleColumns = requestStatuses.filter(status => showArchived || status !== 'archived');
  const assigneeName = id => assignees.find(user => String(user.id) === String(id))?.name || '';

  return (
    <div className="eng-page">
      <AdminPageHeader
        eyebrow="Operations"
        title="Services Management"
        text="Manage service definitions and track service requests, statuses, notes, priorities, and staff ownership."
        actions={<>
          <ActionMenu label="Exports" icon={Download} items={[
            { label: 'Export services (CSV)', icon: Download, href: DashboardApi.exportUrl('services', 'csv') },
            { label: 'Export service requests (CSV)', icon: Download, href: DashboardApi.exportUrl('service-requests', 'csv') },
          ]} />
          <button type="button" className="admin-button admin-button-secondary" onClick={() => load()} disabled={loading}><RefreshCw size={15} /> Refresh</button>
          {canCreate && <button type="button" className="admin-button" onClick={() => tab === 'services' ? setEditing(emptyService) : setRequestEditing(emptyRequest)}><Plus size={15} /> New {tab === 'services' ? 'Service' : 'Request'}</button>}
        </>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}{error && <AdminNotice type="error">{error}</AdminNotice>}

      <div className="eng-filterbar">
        <Tabs label="Services sections" value={tab} onChange={switchTab} tabs={[{ id: 'services', label: 'Services', count: serviceCounts.all ?? 0 }, { id: 'requests', label: 'Service Requests', count: requestCounts.all ?? 0 }]} />
        {tab === 'requests' && <div className="eng-view-toggle" role="group" aria-label="Request layout">
          <button type="button" aria-pressed={requestView === 'board'} onClick={() => switchView('board')}><Columns3 size={15} /> Board</button>
          <button type="button" aria-pressed={requestView === 'list'} onClick={() => switchView('list')}><LayoutList size={15} /> List</button>
        </div>}
      </div>

      <section className="eng-card">
        <form className="eng-table-tools" onSubmit={event => { event.preventDefault(); updateFilter({}); }}>
          <label className="dash-search-field"><Search size={16} aria-hidden="true" /><input type="search" value={filters.q} onChange={event => setFilters(current => ({ ...current, q: event.target.value }))} placeholder={tab === 'services' ? 'Search services' : 'Search requests, requesters, organisations'} aria-label={`Search ${tab}`} /></label>
          {!board && <select value={filters.status} onChange={event => updateFilter({ status: event.target.value })} aria-label="Filter by status"><option value="">All status</option>{(tab === 'services' ? serviceStatuses : requestStatuses).map(status => <option key={status} value={status}>{label(status)}{(tab === 'services' ? serviceCounts : requestCounts)[status] !== undefined ? ` (${(tab === 'services' ? serviceCounts : requestCounts)[status]})` : ''}</option>)}</select>}
          {tab === 'requests' && <>
            <select value={filters.service} onChange={event => updateFilter({ service: event.target.value })} aria-label="Filter by service"><option value="">All services</option>{allServices.map(service => <option key={service.id} value={service.id}>{service.title}</option>)}</select>
            <select value={filters.priority} onChange={event => updateFilter({ priority: event.target.value })} aria-label="Filter by priority"><option value="">Any priority</option>{priorities.map(priority => <option key={priority} value={priority}>{label(priority)}</option>)}</select>
            <select value={filters.assigned_to} onChange={event => updateFilter({ assigned_to: event.target.value })} aria-label="Filter by assignee"><option value="">Anyone</option><option value="none">Unassigned</option>{assignees.map(user => <option key={user.id} value={user.id}>{user.name}</option>)}</select>
          </>}
          <button type="submit" className="admin-button">Search</button>
        </form>

        {tab === 'services' && (loading && !services.length ? <StateBlock type="loading" title="Loading services" /> : services.length ? (
          <div className="eng-table-wrap">
            <table className="eng-table eng-table-responsive">
              <thead><tr><th>Service</th><th>Status</th><th>Team</th><th>Turnaround</th><th>Requests</th><th>Updated</th><th><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {services.map(row => (
                  <tr key={row.id} className="is-clickable" onClick={() => setEditing(row)}>
                    <td className="eng-cell-main"><div className="eng-row-title"><strong>{row.is_featured && <Star size={14} fill="currentColor" className="eng-featured" aria-label="Featured" />} {row.title}</strong><small>{[row.category, row.price_note].filter(Boolean).join(' · ') || row.summary || 'No category'}</small></div></td>
                    <td data-label="Status"><StatusPill value={row.status} /></td>
                    <td data-label="Team">{row.assigned_team || <span className="eng-muted">Unassigned</span>}</td>
                    <td data-label="Turnaround">{row.turnaround_time || <span className="eng-muted">—</span>}</td>
                    <td data-label="Requests"><button type="button" className="eng-link" onClick={event => { event.stopPropagation(); viewServiceRequests(row); }}>{row.request_count} <ArrowRight size={12} /></button></td>
                    <td data-label="Updated" className="eng-cell-nowrap">{row.updated_at ? formatDate(row.updated_at) : '—'}</td>
                    <td className="eng-cell-actions" onClick={event => event.stopPropagation()}>
                      <ActionMenu label={`Actions for ${row.title}`} items={[
                        { label: canWrite ? 'Edit service' : 'View service', icon: PenLine, onClick: () => setEditing(row) },
                        { label: 'View requests', icon: Inbox, onClick: () => viewServiceRequests(row) },
                        canWrite && { divider: true },
                        ...(canWrite ? serviceStatuses.filter(status => status !== row.status).map(status => ({ label: `Set ${status}`, icon: ArrowRight, onClick: () => setServiceStatus(row, status) })) : []),
                        canDelete && { divider: true },
                        canDelete && { label: 'Delete', icon: Trash2, danger: true, onClick: () => deleteService(row) },
                      ]} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <StateBlock type="empty" title="No services found" text="Try changing filters or create a new service." />)}

        {tab === 'requests' && !board && (loading && !requests.length ? <StateBlock type="loading" title="Loading requests" /> : requests.length ? (
          <div className="eng-table-wrap">
            <table className="eng-table eng-table-responsive">
              <thead><tr><th>Request</th><th>Service</th><th>Status</th><th>Priority</th><th>Assigned</th><th>Created</th><th><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {requests.map(row => (
                  <tr key={row.id} className="is-clickable" onClick={() => setRequestEditing(row)}>
                    <td className="eng-cell-main"><div className="eng-row-title"><strong>{row.subject}</strong><small>{row.requester_name}{row.organization ? ` · ${row.organization}` : ''}</small></div></td>
                    <td data-label="Service">{row.service_title || 'General'}</td>
                    <td data-label="Status"><StatusPill value={row.status} /></td>
                    <td data-label="Priority"><StatusPill value={row.priority} /></td>
                    <td data-label="Assigned">{row.assigned_to_name || assigneeName(row.assigned_to) || <span className="eng-muted">Unassigned</span>}</td>
                    <td data-label="Created" className="eng-cell-nowrap">{row.created_at ? formatDate(row.created_at) : '—'}</td>
                    <td className="eng-cell-actions" onClick={event => event.stopPropagation()}><ActionMenu label={`Actions for ${row.subject}`} items={requestMenu(row)} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <StateBlock type="empty" title="No service requests found" text="Try changing filters or add a request." />)}

        {board && (loading && !requests.length ? <StateBlock type="loading" title="Loading requests" /> : <>
          <div className="eng-board" aria-label="Service requests by status">
            {visibleColumns.map(status => {
              const cards = requests.filter(row => row.status === status);
              return (
                <section key={status} className="eng-board-col" aria-label={`${label(status)} requests`}>
                  <header><span className={`eng-dot eng-dot-${status.replaceAll('_', '-')}`} aria-hidden="true" />{label(status)}<b title={narrowed ? 'Matching requests' : 'Total with this status'}>{narrowed ? cards.length : requestCounts[status] ?? cards.length}</b></header>
                  <div className="eng-board-cards">
                    {cards.length ? cards.map(row => (
                      <article key={row.id} className={`eng-req-card is-${row.priority}`}>
                        <button type="button" className="eng-req-open" onClick={() => setRequestEditing(row)}>
                          <strong>{row.subject}</strong>
                          <small>{row.requester_name}{row.organization ? ` · ${row.organization}` : ''}</small>
                        </button>
                        <div className="eng-req-meta">
                          {row.priority !== 'normal' && <StatusPill value={row.priority} />}
                          <span>{row.service_title || 'General'}</span>
                          <span>· {relativeTime(row.created_at)}</span>
                          {(row.assigned_to_name || row.assigned_to) && <span className="eng-assignee"><UserRound size={12} />{row.assigned_to_name || assigneeName(row.assigned_to)}</span>}
                        </div>
                        <ActionMenu label={`Actions for ${row.subject}`} items={requestMenu(row)} />
                      </article>
                    )) : <p className="eng-board-empty">No requests</p>}
                  </div>
                </section>
              );
            })}
          </div>
          <div className="eng-note-actions">
            <small className="eng-hint">{mobile ? 'Grouped by status.' : 'Columns show requests grouped by status; use a card’s menu to move it.'} {requests.length >= BOARD_PAGE_SIZE ? `Showing the latest ${BOARD_PAGE_SIZE} matching requests — switch to List for older ones.` : ''}</small>
            <label className="admin-check eng-inline-icon"><input type="checkbox" checked={showArchived} onChange={event => setShowArchived(event.target.checked)} /> Show archived column</label>
          </div>
        </>)}
        <AdminPagination pagination={pagination} onPage={changePage} />
      </section>

      <Drawer open={Boolean(editing)} title={editing?.id ? 'Edit Service' : 'New Service'} subtitle={editing?.id ? `${editing.request_count ?? 0} requests · updated ${formatDate(editing.updated_at)}` : 'Defines a service people can request'} onClose={() => setEditing(null)} width={680}
        footer={editing && <>
          {editing.id && canDelete && <button type="button" className="admin-button admin-button-danger" onClick={() => deleteService()}><Trash2 size={15} /> Delete</button>}
          <span className="eng-drawer-footer-spacer" />
          <button type="button" className="admin-button admin-button-secondary" onClick={() => setEditing(null)}>Cancel</button>
          {canSaveService && <button className="admin-button" form="service-editor" disabled={saving}><Save size={15} /> Save</button>}
        </>}>
        {editing && <form id="service-editor" className="eng-form" onSubmit={saveService}>
          <fieldset className="eng-fieldset" disabled={!canSaveService}>
            <legend>Service</legend>
            <div className="eng-form-grid">
              <label className="eng-span-2">Title<input required name="title" value={editing.title || ''} onChange={updateService} /></label>
              <label>Slug<input name="slug" value={editing.slug || ''} onChange={updateService} placeholder="Auto-generated when empty" /></label>
              <label>Category<input name="category" value={editing.category || ''} onChange={updateService} /></label>
              <label>Status<select name="status" value={editing.status || 'active'} onChange={updateService}>{serviceStatuses.map(status => <option key={status}>{status}</option>)}</select></label>
              <label className="admin-check"><input type="checkbox" name="is_featured" checked={Boolean(editing.is_featured)} onChange={updateService} />Feature this service</label>
            </div>
            <label>Summary<textarea name="summary" value={editing.summary || ''} onChange={updateService} rows="3" /></label>
            <label>Description<textarea name="description" value={editing.description || ''} onChange={updateService} rows="5" /></label>
          </fieldset>
          <fieldset className="eng-fieldset" disabled={!canSaveService}>
            <legend>Delivery</legend>
            <div className="eng-form-grid">
              <label>Assigned team<input name="assigned_team" value={editing.assigned_team || ''} onChange={updateService} /></label>
              <label>Turnaround<input name="turnaround_time" value={editing.turnaround_time || ''} onChange={updateService} /></label>
              <label className="eng-span-2">Price note<input name="price_note" value={editing.price_note || ''} onChange={updateService} /></label>
            </div>
            <label>Internal notes<textarea name="internal_notes" value={editing.internal_notes || ''} onChange={updateService} rows="3" /></label>
          </fieldset>
        </form>}
      </Drawer>

      <Drawer open={Boolean(requestEditing)} title={requestEditing?.id ? 'Edit Service Request' : 'New Service Request'} subtitle={requestEditing?.id ? `Received ${formatDateTime(requestEditing.created_at)}` : 'Log a request received outside the website'} onClose={() => setRequestEditing(null)} width={680}
        footer={requestEditing && <>
          <span className="eng-drawer-footer-spacer" />
          <button type="button" className="admin-button admin-button-secondary" onClick={() => setRequestEditing(null)}>Cancel</button>
          {canSaveRequest && <button className="admin-button" form="request-editor" disabled={saving}><Save size={15} /> Save</button>}
        </>}>
        {requestEditing && <form id="request-editor" className="eng-form" onSubmit={saveRequest}>
          {requestEditing.id && <div className="eng-reader-actions">
            <a className="admin-button admin-button-secondary" href={mailtoHref(requestEditing.requester_email, `Re: ${requestEditing.subject}`)}><Mail size={15} /> Reply by email</a>
            <CopyButton text={requestEditing.requester_email} />
          </div>}
          <fieldset className="eng-fieldset" disabled={!canSaveRequest}>
            <legend>Workflow</legend>
            <div className="eng-form-grid">
              <label>Status<select name="status" value={requestEditing.status || 'new'} onChange={updateRequest}>{requestStatuses.map(status => <option key={status} value={status}>{status}</option>)}</select></label>
              <label>Priority<select name="priority" value={requestEditing.priority || 'normal'} onChange={updateRequest}>{priorities.map(priority => <option key={priority}>{priority}</option>)}</select></label>
              <label>Service<select name="service" value={requestEditing.service || ''} onChange={updateRequest}><option value="">General request</option>{allServices.map(service => <option value={service.id} key={service.id}>{service.title}</option>)}</select></label>
              <label>Assigned to<select name="assigned_to" value={requestEditing.assigned_to || ''} onChange={updateRequest}><option value="">Unassigned</option>{assignees.map(user => <option key={user.id} value={user.id}>{user.name}</option>)}{requestEditing.assigned_to && !assigneeName(requestEditing.assigned_to) && <option value={requestEditing.assigned_to}>{requestEditing.assigned_to_name || `User #${requestEditing.assigned_to}`}</option>}</select></label>
            </div>
          </fieldset>
          <fieldset className="eng-fieldset" disabled={!canSaveRequest}>
            <legend>Requester</legend>
            <div className="eng-form-grid">
              <label>Requester name<input required name="requester_name" value={requestEditing.requester_name || ''} onChange={updateRequest} /></label>
              <label>Requester email<input required name="requester_email" value={requestEditing.requester_email || ''} onChange={updateRequest} /></label>
              <label className="eng-span-2">Organization<input name="organization" value={requestEditing.organization || ''} onChange={updateRequest} /></label>
            </div>
          </fieldset>
          <fieldset className="eng-fieldset" disabled={!canSaveRequest}>
            <legend>Request</legend>
            <label>Subject<input required name="subject" value={requestEditing.subject || ''} onChange={updateRequest} /></label>
            <label>Message<textarea name="message" value={requestEditing.message || ''} onChange={updateRequest} rows="5" /></label>
            <label>Internal notes<textarea name="internal_notes" value={requestEditing.internal_notes || ''} onChange={updateRequest} rows="4" /></label>
          </fieldset>
        </form>}
      </Drawer>
    </div>
  );
}
