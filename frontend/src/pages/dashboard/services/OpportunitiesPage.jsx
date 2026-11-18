import { AlarmClock, Archive, CheckCircle2, CircleSlash, Copy, Download, ExternalLink, FilePen, Globe2, PenLine, Plus, RefreshCw, Save, Search, Send, Star, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import ActionMenu from '../../../components/dashboard/ActionMenu';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import AdminPagination from '../../../components/dashboard/AdminPagination';
import { Drawer, StatCard, StateBlock, StatusPill, Tabs } from '../../../components/dashboard/DashboardPrimitives';
import '../../../styles/dashboard/dash-engagement.css';
import { formatDate, label, usePermissions } from '../contacts/engagementKit';

const statuses = ['', 'draft', 'published', 'closed', 'archived'];
const opportunityTypes = ['', 'position', 'collaboration', 'programme'];
const editorTabs = ['Basic Info', 'Description & Requirements', 'Application & Contact', 'Custom Fields', 'Publishing'];
const statusActions = { draft: ['Move to draft', FilePen], published: ['Publish', Send], closed: ['Close applications', CircleSlash], archived: ['Set archived', Archive] };
const emptyOpportunity = {
  title: '',
  slug: '',
  organization: '',
  opportunity_type: 'position',
  specialty: '',
  category: '',
  location: '',
  is_remote: false,
  deadline: '',
  short_description: '',
  full_description: '',
  requirements: '',
  eligibility: '',
  benefits: '',
  custom_fields: [],
  application_url: '',
  contact_email: '',
  status: 'draft',
  priority: 'normal',
  is_featured: false,
  show_when_closed: false,
  internal_notes: '',
  seo_title: '',
  seo_description: '',
};

function normalizedEditor(item) {
  return {
    ...emptyOpportunity,
    ...item,
    specialty: item?.specialty || '',
    short_description: item?.short_description || item?.summary || '',
    full_description: item?.full_description || item?.description || '',
    requirements: item?.requirements || item?.eligibility || '',
    eligibility: item?.eligibility || '',
    custom_fields: Array.isArray(item?.custom_fields) ? item.custom_fields : [],
  };
}

function validateOpportunity(item) {
  const errors = {};
  if (!item.title?.trim()) errors.title = 'A clear opportunity title is required.';
  if ((item.short_description || '').length > 280) errors.short_description = 'Keep the short description to 280 characters or fewer.';
  if (item.application_url && !/^https:\/\//i.test(item.application_url)) errors.application_url = 'Use a full HTTPS application URL.';
  if (item.contact_email && !/^\S+@\S+\.\S+$/.test(item.contact_email)) errors.contact_email = 'Enter a valid contact email.';
  return errors;
}

const errorTab = { title: 'Basic Info', short_description: 'Description & Requirements', application_url: 'Application & Contact', contact_email: 'Application & Contact' };

/** Deadline state for highlighting: expired / closing soon (≤ 14 days) / open. */
function deadlineState(item, soonDays = 14) {
  if (!item.deadline) return null;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const deadline = new Date(`${item.deadline}T00:00:00`);
  const days = Math.round((deadline - today) / 86400000);
  if (days < 0) return { tone: 'expired', text: item.status === 'published' ? 'Expired — still published' : 'Deadline passed', days };
  if (days <= soonDays) return { tone: 'soon', text: days === 0 ? 'Closes today' : `Closes in ${days} day${days === 1 ? '' : 's'}`, days };
  return { tone: 'ok', text: `${days} days left`, days };
}

const publicUrl = item => `/opportunities?search=${encodeURIComponent(item.title)}`;
const isPublic = item => item.status === 'published' || (item.status === 'closed' && item.show_when_closed);

export default function DashboardOpportunitiesPage() {
  const [searchParams] = useSearchParams();
  const { can } = usePermissions();
  const canCreate = can('opportunities.create');
  const canEdit = can('opportunities.edit');
  const canManage = can('opportunities.manage');
  const canDelete = can('opportunities.delete');
  const [items, setItems] = useState([]);
  const [counts, setCounts] = useState({});
  const [deadlineCounts, setDeadlineCounts] = useState({});
  const [soonDays, setSoonDays] = useState(14);
  const [categories, setCategories] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [filters, setFilters] = useState({ q: '', status: '', category: '', type: '', deadline: '', page: 1 });
  const [editing, setEditing] = useState(searchParams.get('new') ? emptyOpportunity : null);
  // The editor saves a new opportunity with create rights and an existing one with edit rights.
  const canWrite = editing && !editing.id ? canCreate : canEdit;
  const [activeTab, setActiveTab] = useState(editorTabs[0]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});

  const categoryOptions = useMemo(() => [...categories].sort((a, b) => a.name.localeCompare(b.name)), [categories]);

  const load = async (next = filters) => {
    setLoading(true);
    setError('');
    try {
      const data = await DashboardApi.getOpportunities(next);
      setItems(data.results || []);
      setPagination(data.pagination);
      setCounts(data.counts || {});
      setDeadlineCounts(data.deadline_counts || {});
      if (data.closing_soon_days) setSoonDays(data.closing_soon_days);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    DashboardApi.getCategories().then(data => setCategories(data.results || [])).catch(() => setCategories([]));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const openEditor = item => {
    setActiveTab(editorTabs[0]);
    const next = normalizedEditor(item);
    setEditing(next);
    setFieldErrors(item?.id ? validateOpportunity(next) : {});
  };

  const updateFilter = patch => { const next = { ...filters, ...patch, page: 1 }; setFilters(next); load(next); };
  const changePage = page => { const next = { ...filters, page }; setFilters(next); load(next); };
  const update = event => {
    const { name, value, type, checked } = event.target;
    const next = { ...editing, [name]: type === 'checkbox' ? checked : value };
    setEditing(next);
    setFieldErrors(validateOpportunity(next));
  };
  const updateCustomField = (index, patch) => {
    setEditing(current => ({ ...current, custom_fields: current.custom_fields.map((field, fieldIndex) => fieldIndex === index ? { ...field, ...patch } : field) }));
  };
  const addCustomField = () => {
    setEditing(current => ({ ...current, custom_fields: [...current.custom_fields, { label: '', type: 'text', value: '', help_text: '', options: [], is_public: true, is_required: false }] }));
  };
  const removeCustomField = index => {
    setEditing(current => ({ ...current, custom_fields: current.custom_fields.filter((_, fieldIndex) => fieldIndex !== index) }));
  };
  const save = async event => {
    event.preventDefault();
    setError('');
    const validationErrors = validateOpportunity(editing);
    setFieldErrors(validationErrors);
    if (Object.keys(validationErrors).length) {
      setActiveTab(validationErrors.title ? 'Basic Info' : validationErrors.application_url || validationErrors.contact_email ? 'Application & Contact' : 'Description & Requirements');
      return;
    }
    setSaving(true);
    try {
      await DashboardApi.saveOpportunity(editing, editing.id);
      setNotice('Research opportunity saved.');
      setEditing(null);
      await load();
    } catch (err) {
      setError(err.message);
    } finally { setSaving(false); }
  };
  const archive = async (item = editing) => {
    if (!item?.id || !window.confirm(`Archive "${item.title}"? It will disappear from public listings.`)) return;
    try {
      await DashboardApi.deleteOpportunity(item.id);
      setNotice('Research opportunity archived.');
      if (editing?.id === item.id) setEditing(null);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };
  const duplicate = (source = editing) => {
    if (!source) return;
    const { id, created_at, updated_at, ...rest } = normalizedEditor(source);
    const copy = {
      ...rest,
      title: `Copy of ${source.title}`,
      slug: '',
      status: 'draft',
      is_featured: false,
      custom_fields: (rest.custom_fields || []).map(field => ({ ...field, options: [...(field.options || [])] })),
    };
    setEditing(copy);
    setActiveTab('Basic Info');
    setFieldErrors({});
    setNotice('Draft copy created. Review it and save when ready.');
  };
  const quickStatus = async (item, status) => {
    if (status === 'published' && !window.confirm(`Publish "${item.title}"? It becomes visible on the public opportunities page and subscribers may be notified.`)) return;
    try {
      await DashboardApi.updateOpportunityStatus(item.id, status);
      setNotice(`Status updated for ${item.title}.`);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const errorTabs = new Set(Object.keys(fieldErrors).map(key => errorTab[key]).filter(Boolean));
  const editingDeadline = editing && deadlineState(editing, soonDays);

  return (
    <div className="eng-page">
      <AdminPageHeader
        eyebrow="Operations"
        title="Research Opportunities"
        text="Create, publish, organize, and archive research opportunities without exposing drafts or internal notes publicly."
        actions={<>
          <a className="admin-button admin-button-secondary" href="/opportunities" target="_blank" rel="noreferrer"><ExternalLink size={15} /> View on site</a>
          <a className="admin-button admin-button-secondary" href={DashboardApi.exportUrl('opportunities', 'csv')}><Download size={15} /> Export CSV</a>
          {canCreate && <button type="button" className="admin-button" onClick={() => openEditor(emptyOpportunity)}><Plus size={15} /> New Opportunity</button>}
        </>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}
      {error && <AdminNotice type="error">{error}</AdminNotice>}

      <section className="dash-stat-grid" aria-label="Opportunity summary">
        <StatCard icon={Send} label="Published" value={counts.published ?? 0} hint="Visible on the website" loading={loading && !items.length} />
        <StatCard icon={FilePen} label="Drafts" value={counts.draft ?? 0} hint="Not yet public" loading={loading && !items.length} />
        <StatCard icon={AlarmClock} label="Closing soon" value={deadlineCounts.closing_soon ?? 0} hint={`Published, deadline within ${soonDays} days`} tone={deadlineCounts.closing_soon ? 'amber' : 'blue'} loading={loading && !items.length} />
        <StatCard icon={CircleSlash} label="Expired" value={deadlineCounts.expired ?? 0} hint="Deadline passed but still published" tone={deadlineCounts.expired ? 'amber' : 'blue'} loading={loading && !items.length} />
      </section>

      <section className="eng-card">
        <div className="eng-filterbar eng-filterbar-in-card">
          <Tabs label="Opportunity status" value={filters.status} onChange={status => updateFilter({ status })} tabs={statuses.map(status => ({ id: status, label: status ? label(status) : 'All', count: counts[status || 'all'] ?? 0 }))} />
          <div className="eng-chips" role="group" aria-label="Quick filters">
            {[['closing_soon', 'Closing soon', 'is-warn'], ['expired', 'Expired', 'is-danger'], ['featured', 'Featured', '']].map(([id, text, tone]) => (
              <button key={id} type="button" className={`eng-chip ${tone} ${filters.deadline === id ? 'is-active' : ''}`} aria-pressed={filters.deadline === id} onClick={() => updateFilter({ deadline: filters.deadline === id ? '' : id })}>{text}<b>{deadlineCounts[id] ?? 0}</b></button>
            ))}
          </div>
        </div>
        <form className="eng-table-tools" onSubmit={event => { event.preventDefault(); updateFilter({}); }}>
          <label className="dash-search-field"><Search size={16} aria-hidden="true" /><input type="search" value={filters.q} onChange={event => setFilters(current => ({ ...current, q: event.target.value }))} placeholder="Search opportunities" aria-label="Search opportunities" /></label>
          <select value={filters.type} onChange={event => updateFilter({ type: event.target.value })} aria-label="Filter by type">
            {opportunityTypes.map(type => <option value={type} key={type}>{type ? label(type) : 'All types'}</option>)}
          </select>
          <input value={filters.category} onChange={event => setFilters(current => ({ ...current, category: event.target.value }))} placeholder="Specialty or category" aria-label="Specialty or category" />
          <button type="button" className="admin-button admin-button-secondary" onClick={() => load()} disabled={loading}><RefreshCw size={15} /> Refresh</button>
          <button type="submit" className="admin-button">Search</button>
        </form>

        {loading && !items.length ? <StateBlock type="loading" title="Loading opportunities" /> : items.length ? (
          <div className="eng-table-wrap">
            <table className="eng-table eng-table-responsive">
              <thead><tr><th>Opportunity</th><th>Type</th><th>Specialty</th><th>Deadline</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {items.map(row => {
                  const state = deadlineState(row, soonDays);
                  return (
                    <tr key={row.id} className="is-clickable" onClick={() => openEditor(row)}>
                      <td className="eng-cell-main">
                        <div className="eng-row-title">
                          <strong>{row.is_featured && <Star size={14} fill="currentColor" className="eng-featured" aria-label="Featured" />} {row.title}</strong>
                          <small>{[row.organization, row.is_remote ? 'Remote' : row.location].filter(Boolean).join(' · ') || 'No organization or location yet'}</small>
                        </div>
                      </td>
                      <td data-label="Type">{label(row.opportunity_type || 'position')}</td>
                      <td data-label="Specialty">{row.specialty_name || row.category || 'General'}</td>
                      <td data-label="Deadline">
                        {row.deadline ? <span className="eng-deadline"><span>{formatDate(`${row.deadline}T00:00:00`)}</span>{state && (state.tone !== 'ok' || row.status === 'published') && <em className={`is-${state.tone}`}>{state.text}</em>}</span> : <span className="eng-muted">No deadline</span>}
                      </td>
                      <td data-label="Status"><StatusPill value={row.status} /></td>
                      <td className="eng-cell-actions" onClick={event => event.stopPropagation()}>
                        <ActionMenu label={`Actions for ${row.title}`} items={[
                          { label: canEdit ? 'Edit' : 'View details', icon: PenLine, onClick: () => openEditor(row) },
                          isPublic(row) && { label: 'View on site', icon: ExternalLink, href: publicUrl(row), external: true },
                          canCreate && { label: 'Duplicate as draft', icon: Copy, onClick: () => duplicate(row) },
                          canManage && { divider: true },
                          ...(canManage ? statuses.filter(status => status && status !== row.status && status !== 'archived').map(status => ({ label: statusActions[status][0], icon: statusActions[status][1], onClick: () => quickStatus(row, status) })) : []),
                          canDelete && row.status !== 'archived' && { divider: true },
                          canDelete && row.status !== 'archived' && { label: 'Archive', icon: Archive, danger: true, onClick: () => archive(row) },
                        ]} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : <StateBlock type="empty" title="No research opportunities found" text="Try changing filters or create a new opportunity." />}
        <AdminPagination pagination={pagination} onPage={changePage} />
      </section>

      <Drawer
        open={Boolean(editing)}
        width={780}
        title={editing?.id ? 'Edit Research Opportunity' : 'New Research Opportunity'}
        subtitle={editing ? [label(editing.status || 'draft'), editingDeadline?.text, editing.id && editing.updated_at ? `updated ${formatDate(editing.updated_at)}` : ''].filter(Boolean).join(' · ') : ''}
        onClose={() => setEditing(null)}
        footer={editing && (
          <>
            {editing.id && canDelete && <button type="button" className="admin-button admin-button-danger" onClick={() => archive()}><Archive size={15} /> Archive</button>}
            {editing.id && canCreate && <button type="button" className="admin-button admin-button-secondary" onClick={() => duplicate()}><Copy size={15} /> Duplicate</button>}
            {editing.id && isPublic(editing) && <a className="admin-button admin-button-secondary" href={publicUrl(editing)} target="_blank" rel="noreferrer"><ExternalLink size={15} /> View</a>}
            <span className="eng-drawer-footer-spacer" />
            <button type="button" className="admin-button admin-button-secondary" onClick={() => setEditing(null)}>Cancel</button>
            {canWrite && <button className="admin-button" form="opportunity-editor" disabled={saving}><Save size={15} /> Save</button>}
          </>
        )}
      >
        {editing && <>
          <nav className="eng-editor-nav" aria-label="Opportunity editor sections">
            {editorTabs.map(tab => (
              <button type="button" className={activeTab === tab ? 'active' : ''} aria-current={activeTab === tab ? 'step' : undefined} key={tab} onClick={() => setActiveTab(tab)}>{tab}{errorTabs.has(tab) && <span className="eng-error-dot" aria-label="has errors" />}</button>
            ))}
          </nav>
          <form id="opportunity-editor" className="eng-form" onSubmit={save}>
            <fieldset className="eng-plain-fieldset" disabled={!canWrite}>
              {activeTab === 'Basic Info' && (
                <div className="eng-form-grid">
                  <label className="eng-span-2">Title<input required name="title" value={editing.title || ''} onChange={update} aria-invalid={Boolean(fieldErrors.title)} />{fieldErrors.title && <small className="form-field-error">{fieldErrors.title}</small>}</label>
                  <label>Slug<input name="slug" value={editing.slug || ''} onChange={update} placeholder="Auto-generated when empty" /></label>
                  <label>Organization<input name="organization" value={editing.organization || ''} onChange={update} placeholder="e.g. Cairo University Hospital" /></label>
                  <label>Type<select name="opportunity_type" value={editing.opportunity_type || 'position'} onChange={update}>{opportunityTypes.filter(Boolean).map(type => <option value={type} key={type}>{type}</option>)}</select></label>
                  <label>Specialty<select name="specialty" value={editing.specialty || ''} onChange={update}><option value="">No specialty</option>{categoryOptions.map(category => <option value={category.id} key={category.id}>{category.name}</option>)}</select></label>
                  <label>Legacy category<input name="category" value={editing.category || ''} onChange={update} placeholder="Optional fallback category" /></label>
                  <label>Location<input name="location" value={editing.location || ''} onChange={update} /></label>
                  <label>Deadline<input type="date" name="deadline" value={editing.deadline || ''} onChange={update} />{editingDeadline && <small className="eng-deadline"><em className={`is-${editingDeadline.tone}`}>{editingDeadline.text}</em></small>}</label>
                  <label className="admin-check"><input type="checkbox" name="is_remote" checked={Boolean(editing.is_remote)} onChange={update} />Remote opportunity</label>
                </div>
              )}

              {activeTab === 'Description & Requirements' && (
                <>
                  <p className="admin-form-help">Give applicants enough context to decide whether this opportunity is right for them. Only the short description and full description appear on the public listing.</p>
                  <label>Short description <small>{(editing.short_description || '').length}/280</small><textarea name="short_description" value={editing.short_description || ''} onChange={update} rows="3" maxLength="280" placeholder="A concise public overview of the role, project, or programme." aria-invalid={Boolean(fieldErrors.short_description)} />{fieldErrors.short_description && <small className="form-field-error">{fieldErrors.short_description}</small>}</label>
                  <label>Full description<textarea name="full_description" value={editing.full_description || ''} onChange={update} rows="6" placeholder="Explain the research context, responsibilities, expected commitment, and what the participant will do." /></label>
                  <label>Eligibility<textarea name="eligibility" value={editing.eligibility || ''} onChange={update} rows="4" placeholder="Who can apply? Include discipline, level of study, location, or experience where relevant." /></label>
                  <label>Requirements<textarea name="requirements" value={editing.requirements || ''} onChange={update} rows="5" placeholder="List the essential skills, documents, time commitment, or selection criteria." /></label>
                  <label>Benefits<textarea name="benefits" value={editing.benefits || ''} onChange={update} rows="5" placeholder="Describe mentorship, authorship, training, compensation, networking, or other benefits." /></label>
                </>
              )}

              {activeTab === 'Application & Contact' && (
                <div className="eng-form-grid">
                  <label>Application URL<input name="application_url" value={editing.application_url || ''} onChange={update} placeholder="https://..." aria-invalid={Boolean(fieldErrors.application_url || fieldErrors.application)} />{fieldErrors.application_url && <small className="form-field-error">{fieldErrors.application_url}</small>}</label>
                  <label>Contact email<input name="contact_email" value={editing.contact_email || ''} onChange={update} aria-invalid={Boolean(fieldErrors.contact_email || fieldErrors.application)} />{fieldErrors.contact_email && <small className="form-field-error">{fieldErrors.contact_email}</small>}</label>
                  <p className="admin-form-help eng-span-2">Both application methods are optional. If you leave them empty, visitors will be guided to contact ResRef instead.</p>
                </div>
              )}

              {activeTab === 'Custom Fields' && (
                <section className="eng-form" aria-label="Custom opportunity information">
                  <div className="eng-fieldset-head"><div><h3>Custom information</h3><p>Add only the information this opportunity needs. These fields are optional and can be shown publicly or kept for the dashboard.</p></div><button type="button" className="admin-button admin-button-secondary" onClick={addCustomField}><Plus size={15} /> Add field</button></div>
                  {!editing.custom_fields.length && <p className="admin-form-help">No custom fields yet. Add one for information such as study phase, workload, funding, duration, or required documents.</p>}
                  {editing.custom_fields.map((field, index) => (
                    <fieldset className="eng-fieldset" key={index}>
                      <legend>Field {index + 1}{field.label ? ` · ${field.label}` : ''}</legend>
                      <div className="eng-form-grid">
                        <label>Label<input value={field.label || ''} onChange={event => updateCustomField(index, { label: event.target.value })} placeholder="e.g. Expected weekly commitment" /></label>
                        <label>Field type<select value={field.type || 'text'} onChange={event => updateCustomField(index, { type: event.target.value })}><option value="text">Short text</option><option value="textarea">Long text</option><option value="select">Select / options</option><option value="checkbox">Yes / no</option><option value="email">Email</option><option value="url">Website link</option><option value="date">Date</option></select></label>
                        <label>Value<input value={field.value || ''} onChange={event => updateCustomField(index, { value: event.target.value })} placeholder="The information visitors should see" /></label>
                        <label>Helper text<input value={field.help_text || ''} onChange={event => updateCustomField(index, { help_text: event.target.value })} placeholder="Optional explanation" /></label>
                        {field.type === 'select' && <label className="eng-span-2">Options<input value={(field.options || []).join(', ')} onChange={event => updateCustomField(index, { options: event.target.value.split(',').map(option => option.trim()).filter(Boolean) })} placeholder="Option one, option two" /></label>}
                        <label className="admin-check"><input type="checkbox" checked={field.is_public !== false} onChange={event => updateCustomField(index, { is_public: event.target.checked })} />Show publicly</label>
                        <label className="admin-check"><input type="checkbox" checked={Boolean(field.is_required)} onChange={event => updateCustomField(index, { is_required: event.target.checked })} />Mark as required</label>
                      </div>
                      <button type="button" className="admin-button admin-button-danger" onClick={() => removeCustomField(index)}><Trash2 size={15} /> Remove field</button>
                    </fieldset>
                  ))}
                </section>
              )}

              {activeTab === 'Publishing' && (
                <>
                  <div className="eng-form-grid">
                    <label>Status<select name="status" value={editing.status || 'draft'} onChange={update}>{statuses.filter(Boolean).map(status => <option value={status} key={status}>{status}</option>)}</select></label>
                    <label>Priority<select name="priority" value={editing.priority || 'normal'} onChange={update}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></label>
                    <label className="eng-span-2">SEO title <small>{(editing.seo_title || '').length}/60</small><input name="seo_title" value={editing.seo_title || ''} onChange={update} maxLength="60" /></label>
                    <label className="admin-check"><input type="checkbox" name="is_featured" checked={Boolean(editing.is_featured)} onChange={update} />Feature this opportunity</label>
                    <label className="admin-check"><input type="checkbox" name="show_when_closed" checked={Boolean(editing.show_when_closed)} onChange={update} />Keep visible after closing</label>
                  </div>
                  {isPublic(editing) && editing.slug && <a className="admin-button admin-button-secondary eng-self-start" href={publicUrl(editing)} target="_blank" rel="noreferrer"><ExternalLink size={15} /> View Public Listing</a>}
                  <p className="admin-form-help">Closed opportunities are hidden by default. Enable “Keep visible after closing” when visitors should still be able to read the opportunity and its details; application actions will be marked as closed.</p>
                  <label>SEO description <small>{(editing.seo_description || '').length}/160</small><textarea name="seo_description" value={editing.seo_description || ''} onChange={update} rows="3" maxLength="160" /></label>
                  <label>Internal notes<textarea name="internal_notes" value={editing.internal_notes || ''} onChange={update} rows="4" /></label>
                  {editing.status === 'published' && (
                    <div className="eng-callout" role="status"><CheckCircle2 size={16} /> Publishing checklist: title is ready. Add any public description, application details, deadline, or custom information only when it is useful for this opportunity.</div>
                  )}
                  {editingDeadline?.tone === 'expired' && editing.status === 'published' && <div className="eng-callout is-warn"><AlarmClock size={16} /> The deadline has passed. Consider setting the status to closed.</div>}
                </>
              )}
            </fieldset>
          </form>
          {!canWrite && <p className="eng-hint"><Globe2 size={13} /> You have read-only access to opportunities.</p>}
        </>}
      </Drawer>
    </div>
  );
}
