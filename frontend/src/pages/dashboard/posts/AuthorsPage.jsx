import { BadgeCheck, Building2, ExternalLink, FileText, ImageOff, ImagePlus, LayoutGrid, List, Pencil, Plus, Save, Search, Trash2, UserRound, Users, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import ActionMenu from '../../../components/dashboard/ActionMenu';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import { Drawer, StatCard, StateBlock } from '../../../components/dashboard/DashboardPrimitives';
import MediaPicker from '../../../components/dashboard/MediaPicker';
import { Segmented, initials, readStored, slugify, useLibraryPermissions, useUnsavedWarning, writeStored } from '../media/libraryKit';
import '../../../styles/dashboard/dash-library.css';

const blank = { login: '', display_name: '', slug: '', prefix: '', credentials: '', position: '', specialty: '', institution: '', country: '', email: '', role: '', short_bio: '', bio: '', profile_media_id: '', avatar: '', website: '', orcid: '', google_scholar: '', researchgate: '', linkedin: '', twitter: '', seo_title: '', seo_description: '', display_order: 0, is_active: true };
const sections = [
  ['Professional details', [['prefix', 'Prefix', 'text', 'Dr., Prof.'], ['credentials', 'Credentials', 'text', 'MD, PhD'], ['position', 'Position'], ['role', 'Default public title'], ['specialty', 'Specialty'], ['institution', 'Institution'], ['country', 'Country'], ['email', 'Email (private)', 'email']]],
  ['Profiles and links', [['website', 'Website'], ['orcid', 'ORCID'], ['google_scholar', 'Google Scholar'], ['researchgate', 'ResearchGate'], ['linkedin', 'LinkedIn'], ['twitter', 'X / Twitter']]],
];
const URL_FIELDS = new Set(['website', 'orcid', 'google_scholar', 'researchgate', 'linkedin', 'twitter']);
const fullName = author => [author.prefix, author.display_name].filter(Boolean).join(' ');

export default function DashboardAuthorsPage() {
  const { canCreate, canWrite: canEdit, canDelete } = useLibraryPermissions('taxonomy');
  const [authors, setAuthors] = useState([]);
  const [status, setStatus] = useState('loading');
  const [editing, setEditing] = useState(null);
  // The open form needs create rights for a new contributor and edit rights otherwise.
  const canWrite = editing && !editing.id ? canCreate : canEdit;
  const [original, setOriginal] = useState('');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState('order');
  const [view, setView] = useState(() => readStored('resref.authors.view', 'cards'));
  const [picker, setPicker] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [slugEdited, setSlugEdited] = useState(false);

  const load = async () => {
    try { const data = await DashboardApi.getAuthors(); setAuthors(data.results || []); }
    catch (err) { setError(err.message); }
    finally { setStatus('ready'); }
  };
  useEffect(() => { load(); }, []);

  const counts = useMemo(() => ({
    all: authors.length,
    active: authors.filter(a => a.is_active).length,
    inactive: authors.filter(a => !a.is_active).length,
    incomplete: authors.filter(a => !a.profile_image || !(a.short_bio || a.bio)).length,
    credited: authors.reduce((sum, a) => sum + (a.usage_count || 0), 0),
  }), [authors]);

  const visible = useMemo(() => {
    const text = query.trim().toLowerCase();
    let list = authors.filter(a => {
      if (filter === 'active' && !a.is_active) return false;
      if (filter === 'inactive' && a.is_active) return false;
      if (filter === 'incomplete' && a.profile_image && (a.short_bio || a.bio)) return false;
      return !text || `${a.display_name} ${a.institution} ${a.specialty} ${a.position} ${a.role} ${a.country} ${a.slug}`.toLowerCase().includes(text);
    });
    if (sort === 'name') list = [...list].sort((a, b) => a.display_name.localeCompare(b.display_name));
    if (sort === 'articles') list = [...list].sort((a, b) => (b.usage_count || 0) - (a.usage_count || 0));
    return list;
  }, [authors, query, filter, sort]);

  const open = author => {
    const next = author ? { ...author } : { ...blank };
    setSlugEdited(Boolean(author));
    setEditing(next);
    setOriginal(JSON.stringify(next));
  };
  const dirty = Boolean(editing) && JSON.stringify(editing) !== original;
  useUnsavedWarning(dirty);
  const close = () => { if (dirty && !window.confirm('Discard unsaved changes to this contributor?')) return; setEditing(null); };
  const update = ({ target }) => {
    if (target.name === 'slug') setSlugEdited(true);
    setEditing(current => ({ ...current, [target.name]: target.type === 'checkbox' ? target.checked : target.value, ...(target.name === 'display_name' && !current.id && !slugEdited ? { slug: slugify(target.value) } : {}) }));
  };
  const save = async event => {
    event.preventDefault(); setError(''); setSaving(true);
    try { await DashboardApi.saveAuthor(editing, editing.id); setEditing(null); setNotice('Contributor profile saved.'); await load(); }
    catch (err) { setError(err.message); }
    finally { setSaving(false); }
  };
  const remove = async a => {
    if (!window.confirm(`Delete contributor "${a.display_name}"? Profiles already credited on articles are protected.`)) return;
    try { await DashboardApi.deleteAuthor(a.id); setNotice('Contributor deleted.'); setEditing(null); await load(); }
    catch (err) { setError(err.message); }
  };
  const toggleActive = async a => {
    try { await DashboardApi.saveAuthor({ ...a, is_active: !a.is_active }, a.id); setNotice(`${a.display_name} is now ${a.is_active ? 'inactive and hidden from the public site' : 'active and publicly visible'}.`); await load(); }
    catch (err) { setError(err.message); }
  };

  const photo = editing ? (editing.profile_media_id ? editing._picked_url || editing.profile_image : '') || editing.avatar || '' : '';
  const menuFor = a => [
    { label: 'View public profile', icon: ExternalLink, href: `/authors/${a.slug}`, external: true },
    { label: 'View their articles', icon: FileText, href: `/dashboard/posts?author=${a.id}` },
    canWrite && { label: a.is_active ? 'Mark inactive' : 'Mark active', icon: BadgeCheck, onClick: () => toggleActive(a) },
    canDelete && { divider: true },
    canDelete && { label: 'Delete', icon: Trash2, danger: true, onClick: () => remove(a) },
  ];
  const avatar = (a, size = 'md') => (
    <span className={`dlib-avatar dlib-avatar-${size}`}>{a.profile_image ? <img src={a.profile_image} alt="" loading="lazy" /> : <span>{initials(a.display_name)}</span>}</span>
  );

  return (
    <div className="dlib-page">
      <AdminPageHeader
        eyebrow="Content library"
        title="Authors & Contributors"
        text="Create public author profiles, then assign them to articles. These profiles are separate from dashboard sign-in accounts."
        actions={canCreate && <button className="admin-button" onClick={() => open()}><Plus size={15} /> Add Contributor</button>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}{error && <AdminNotice type="error">{error}</AdminNotice>}

      <section className="dash-stat-grid dlib-stats" aria-label="Contributor overview">
        <StatCard icon={Users} label="Contributors" value={counts.all} hint={`${counts.active} active · ${counts.inactive} inactive`} loading={status === 'loading'} />
        <StatCard icon={BadgeCheck} label="Publicly visible" value={counts.active} hint="Active profiles" loading={status === 'loading'} />
        <StatCard icon={UserRound} label="Incomplete profiles" value={counts.incomplete} hint="Missing photo or biography" tone={counts.incomplete ? 'amber' : 'blue'} loading={status === 'loading'} />
        <StatCard icon={FileText} label="Article credits" value={counts.credited} hint="Across all contributors" to="/dashboard/posts" loading={status === 'loading'} />
      </section>

      <section className="dashboard-card dlib-library">
        <div className="dlib-toolbar">
          <label className="dash-search-field"><Search size={16} aria-hidden="true" /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search name, institution, specialty" aria-label="Search contributors" />{query && <button type="button" className="dlib-clear" onClick={() => setQuery('')} aria-label="Clear search"><X size={14} /></button>}</label>
          <Segmented label="Status" value={filter} onChange={setFilter} options={[{ id: 'all', label: 'All', count: counts.all }, { id: 'active', label: 'Active', count: counts.active }, { id: 'inactive', label: 'Inactive', count: counts.inactive }, { id: 'incomplete', label: 'Incomplete', count: counts.incomplete }]} />
          <select value={sort} onChange={event => setSort(event.target.value)} aria-label="Sort contributors"><option value="order">Display order</option><option value="name">Name A–Z</option><option value="articles">Most articles</option></select>
          <Segmented label="Layout" value={view} onChange={next => { setView(next); writeStored('resref.authors.view', next); }} options={[{ id: 'cards', label: 'Cards', icon: LayoutGrid, iconOnly: true }, { id: 'table', label: 'Table', icon: List, iconOnly: true }]} />
        </div>

        {status === 'loading' ? <StateBlock type="loading" title="Loading contributors" />
          : !visible.length ? <StateBlock type="empty" title="No contributors found" text="Create a contributor profile or adjust the search." />
          : view === 'cards' ? (
            <div className="dlib-author-grid">
              {visible.map(a => (
                <article className={`dlib-author-card ${a.is_active ? '' : 'is-inactive'}`} key={a.id}>
                  <div className="dlib-author-top">
                    {avatar(a, 'lg')}
                    <ActionMenu label={`More actions for ${a.display_name}`} items={menuFor(a)} />
                  </div>
                  <button type="button" className="dlib-author-name" onClick={() => open(a)}>
                    <strong>{fullName(a)}</strong>
                    {a.credentials && <span>{a.credentials}</span>}
                  </button>
                  <p className={`dlib-author-role ${a.position || a.role ? '' : 'is-empty'}`}>{a.position || a.role || 'No position set'}</p>
                  {(a.institution || a.country) && <p className="dlib-author-inst"><Building2 size={13} aria-hidden="true" /> {[a.institution, a.country].filter(Boolean).join(' · ')}</p>}
                  {a.specialty && <p className="dlib-author-spec">{a.specialty}</p>}
                  <div className="dlib-author-foot">
                    <span className={`dlib-pill ${a.is_active ? 'dlib-pill-ok' : ''}`}>{a.is_active ? 'Active' : 'Inactive'}</span>
                    <Link to={`/dashboard/posts?author=${a.id}`} className="dlib-author-count" title="View their articles"><FileText size={13} aria-hidden="true" /> {a.usage_count || 0} {a.usage_count === 1 ? 'article' : 'articles'}</Link>
                    {canWrite && <button type="button" className="dlib-icon-text" onClick={() => open(a)}><Pencil size={14} /> Edit</button>}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="dashboard-table-wrap">
              <table className="dashboard-table dlib-table">
                <thead><tr><th>Contributor</th><th>Institution / Specialty</th><th>Status</th><th className="dlib-num">Contributions</th><th className="dlib-num">Order</th><th><span className="dlib-sr">Actions</span></th></tr></thead>
                <tbody>{visible.map(a => (
                  <tr key={a.id}>
                    <td data-label="Contributor" className="dlib-cell-main"><button type="button" className="dlib-row-title" onClick={() => open(a)}>{avatar(a, 'sm')}<span><strong>{fullName(a)}</strong><small>/authors/{a.slug}</small></span></button></td>
                    <td data-label="Institution / Specialty">{a.institution || a.specialty || '—'}</td>
                    <td data-label="Status"><span className={`dlib-pill ${a.is_active ? 'dlib-pill-ok' : ''}`}>{a.is_active ? 'Active' : 'Inactive'}</span></td>
                    <td data-label="Contributions" className="dlib-num"><Link className="dlib-count-link" to={`/dashboard/posts?author=${a.id}`}>{a.usage_count} articles</Link></td>
                    <td data-label="Order" className="dlib-num">{a.display_order || 0}</td>
                    <td className="dlib-row-actions">{canWrite && <button type="button" className="dlib-icon-text" onClick={() => open(a)}><Pencil size={14} /> Edit</button>}<ActionMenu label={`More actions for ${a.display_name}`} items={menuFor(a)} /></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
      </section>

      <Drawer open={Boolean(editing)} onClose={close} width={720}
        title={editing?.id ? 'Edit contributor' : 'New contributor'}
        subtitle={editing?.id ? `${fullName(editing)} · ${editing.usage_count || 0} credited articles` : 'Public author profile, separate from sign-in accounts'}
        footer={editing && <>
          {editing.id && canDelete && <button type="button" className="admin-button admin-button-danger dlib-footer-start" onClick={() => remove(editing)}><Trash2 size={15} /> Delete</button>}
          <button className="admin-button admin-button-secondary" type="button" onClick={close}><X size={15} /> Cancel</button>
          {canWrite && <button className="admin-button" form="dlib-author-form" disabled={saving}><Save size={15} /> Save Contributor</button>}
        </>}>
        {editing && (
          <form id="dlib-author-form" className="dlib-form" onSubmit={save}>
            {editing.id && <div className="dlib-quicklinks">
              <a href={`/authors/${editing.slug}`} target="_blank" rel="noreferrer"><ExternalLink size={15} /> View public profile</a>
              <Link to={`/dashboard/posts?author=${editing.id}`}><FileText size={15} /> View their articles <em>{editing.usage_count || 0}</em></Link>
            </div>}

            <div className="dlib-author-photo">
              <span className="dlib-avatar dlib-avatar-xl">{photo ? <img src={photo} alt="Selected profile" /> : <span>{editing.display_name ? initials(editing.display_name) : <ImageOff size={24} aria-hidden="true" />}</span>}</span>
              <div>
                <strong>Profile photo</strong>
                <small>{editing.profile_media_id ? 'From the Media Library' : editing.avatar ? 'From an external / legacy URL' : 'No photo yet — initials are shown instead.'}</small>
                {canWrite && <div className="dlib-inline-actions">
                  <button type="button" className="admin-button admin-button-secondary" onClick={() => setPicker(true)}><ImagePlus size={15} /> Choose from Media Library</button>
                  {editing.profile_media_id && <button type="button" className="admin-button admin-button-secondary" onClick={() => setEditing(current => ({ ...current, profile_media_id: '', _picked_url: '' }))}>Remove library photo</button>}
                </div>}
                <input type="hidden" name="profile_media_id" value={editing.profile_media_id || ''} />
              </div>
            </div>

            <fieldset className="dlib-fieldset">
              <legend>Identity</legend>
              <div className="dlib-form-grid">
                <label>Full Name<input required name="display_name" value={editing.display_name} onChange={update} disabled={!canWrite} /></label>
                <label>Public URL Slug<input required name="slug" value={editing.slug || ''} onChange={update} disabled={!canWrite} /><small>/authors/{editing.slug || '…'}</small></label>
                <label>Display Order<input min="0" type="number" name="display_order" value={editing.display_order || 0} onChange={update} disabled={!canWrite} /><small>Lower numbers are listed first.</small></label>
                <label className="admin-check dlib-switch dlib-check-cell"><input type="checkbox" name="is_active" checked={Boolean(editing.is_active)} onChange={update} disabled={!canWrite} /> Active and publicly visible</label>
              </div>
            </fieldset>

            {sections.map(([title, fields]) => (
              <fieldset className="dlib-fieldset" key={title}>
                <legend>{title}</legend>
                <div className="dlib-form-grid">
                  {fields.map(([name, label, type, placeholder]) => <label key={name}>{label}<input type={type || 'text'} name={name} value={editing[name] || ''} onChange={update} placeholder={URL_FIELDS.has(name) ? 'https://...' : placeholder || ''} disabled={!canWrite} /></label>)}
                  {title === 'Profiles and links' && <label>Legacy / External Photo URL<input name="avatar" value={editing.avatar || ''} onChange={update} placeholder="https://..." disabled={!canWrite} /><small>Used when no Media Library photo is selected.</small></label>}
                </div>
              </fieldset>
            ))}

            <fieldset className="dlib-fieldset">
              <legend>Biography</legend>
              <label>Short Biography<textarea name="short_bio" value={editing.short_bio || ''} onChange={update} rows="3" disabled={!canWrite} /><small>Shown on article bylines and contributor cards.</small></label>
              <label>Full Biography<textarea name="bio" value={editing.bio || ''} onChange={update} rows="6" disabled={!canWrite} /></label>
            </fieldset>

            <fieldset className="dlib-fieldset">
              <legend>Search appearance (optional)</legend>
              <label>SEO title<input name="seo_title" value={editing.seo_title || ''} onChange={update} maxLength={500} disabled={!canWrite} /></label>
              <label>SEO description<textarea name="seo_description" value={editing.seo_description || ''} onChange={update} rows="2" disabled={!canWrite} /></label>
            </fieldset>
            {dirty && <p className="dlib-dirty-note" role="status">Unsaved changes</p>}
          </form>
        )}
      </Drawer>
      <MediaPicker open={picker} onClose={() => setPicker(false)} title="Choose a profile photo" onSelect={asset => setEditing(current => current ? { ...current, profile_media_id: asset.id, _picked_url: asset.url } : current)} />
    </div>
  );
}
