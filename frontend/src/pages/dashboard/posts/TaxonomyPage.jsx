import { ArrowUpDown, CheckSquare, ExternalLink, EyeOff, FileText, FolderTree, Image as ImageIcon, ImagePlus, ListTree, Pencil, Plus, Save, Search, Square, Tag as TagIcon, Trash2, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import ActionMenu from '../../../components/dashboard/ActionMenu';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import { Drawer, StatCard, StateBlock } from '../../../components/dashboard/DashboardPrimitives';
import MediaPicker from '../../../components/dashboard/MediaPicker';
import CategoryOrderDrawer from './CategoryOrderDrawer';
import { Segmented, decodeEntities, slugify, useLibraryPermissions, useUnsavedWarning } from '../media/libraryKit';
import '../../../styles/dashboard/dash-library.css';

/** Categories in tree order (parent, then its children), each with its depth and ancestor path. */
function buildTree(items) {
  const byParent = new Map();
  const ids = new Set(items.map(item => item.id));
  items.forEach(item => {
    const parent = ids.has(item.parent_id) ? item.parent_id : null;
    if (!byParent.has(parent)) byParent.set(parent, []);
    byParent.get(parent).push(item);
  });
  const ordered = [];
  const seen = new Set();
  const walk = (parent, depth, path) => (byParent.get(parent) || []).forEach(item => {
    if (seen.has(item.id)) return;
    seen.add(item.id);
    ordered.push({ ...item, depth, path });
    walk(item.id, depth + 1, [...path, item.name]);
  });
  walk(null, 0, []);
  items.forEach(item => { if (!seen.has(item.id)) ordered.push({ ...item, depth: 0, path: [] }); });
  return ordered;
}

function descendantIds(items, id) {
  const result = new Set();
  const visit = parent => items.forEach(item => { if (item.parent_id === parent && !result.has(item.id)) { result.add(item.id); visit(item.id); } });
  visit(id);
  return result;
}

export default function DashboardTaxonomyPage({ type }) {
  const isCategory = type === 'categories';
  const label = isCategory ? 'Category' : 'Tag';
  const { canCreate, canWrite: canEdit, canDelete } = useLibraryPermissions('taxonomy');
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState('loading');
  const [editing, setEditing] = useState(null);
  // The open form needs create rights for a new item and edit rights otherwise.
  const canWrite = editing && !editing.id ? canCreate : canEdit;
  const [original, setOriginal] = useState('');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState(isCategory ? 'tree' : 'name');
  const [selection, setSelection] = useState(() => new Set());
  const [picker, setPicker] = useState(false);
  const [arranging, setArranging] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = async () => {
    try { const data = await (isCategory ? DashboardApi.getCategories() : DashboardApi.getTags()); setItems(data.results || []); }
    catch (err) { setError(err.message); }
    finally { setStatus('ready'); }
  };
  useEffect(() => {
    setStatus('loading'); setEditing(null); setQuery(''); setFilter('all'); setSort(isCategory ? 'tree' : 'name'); setSelection(new Set()); setNotice(''); setError('');
    load();
  }, [type]); // eslint-disable-line react-hooks/exhaustive-deps

  const tree = useMemo(() => (isCategory ? buildTree(items) : items.map(item => ({ ...item, depth: 0, path: [] }))), [items, isCategory]);
  const childCounts = useMemo(() => items.reduce((map, item) => { if (item.parent_id) map.set(item.parent_id, (map.get(item.parent_id) || 0) + 1); return map; }, new Map()), [items]);
  const counts = useMemo(() => ({
    all: items.length,
    visible: items.filter(item => item.show_in_database).length,
    hidden: items.filter(item => isCategory && !item.show_in_database).length,
    unused: items.filter(item => !item.usage_count).length,
    top: isCategory ? items.filter(item => !item.parent_id).length : 0,
  }), [items, isCategory]);
  const totalUses = items.reduce((sum, item) => sum + (item.usage_count || 0), 0);
  const mostUsed = useMemo(() => [...items].sort((a, b) => (b.usage_count || 0) - (a.usage_count || 0))[0], [items]);

  const rows = useMemo(() => {
    const text = query.trim().toLowerCase();
    let list = tree.filter(item => {
      if (filter === 'visible' && !item.show_in_database) return false;
      if (filter === 'hidden' && item.show_in_database) return false;
      if (filter === 'unused' && item.usage_count) return false;
      return !text || `${item.name} ${item.slug} ${item.description || ''}`.toLowerCase().includes(text);
    });
    const flat = Boolean(text) || filter !== 'all' || sort !== 'tree';
    if (sort === 'name') list = [...list].sort((a, b) => a.name.localeCompare(b.name));
    if (sort === 'usage') list = [...list].sort((a, b) => (b.usage_count || 0) - (a.usage_count || 0) || a.name.localeCompare(b.name));
    return list.map(item => ({ ...item, displayDepth: flat ? 0 : item.depth, showPath: flat && item.path.length > 0 }));
  }, [tree, query, filter, sort]);

  const blank = () => ({ name: '', slug: '', ...(isCategory ? { parent_id: '', description: '', hero_image: '', show_in_database: true, database_order: 0 } : {}) });
  const open = item => { const next = item || blank(); setEditing(next); setOriginal(JSON.stringify(next)); };
  const dirty = Boolean(editing) && JSON.stringify(editing) !== original;
  useUnsavedWarning(dirty);
  const close = () => { if (dirty && !window.confirm('Discard unsaved changes?')) return; setEditing(null); };

  const update = event => {
    const { name, value, checked, type: inputType } = event.target;
    setEditing(current => ({ ...current, [name]: inputType === 'checkbox' ? checked : value, ...(name === 'name' && !current.id && !current.slugTouched ? { slug: slugify(value) } : {}), ...(name === 'slug' ? { slugTouched: true } : {}) }));
  };
  const save = async event => {
    event.preventDefault(); setError(''); setSaving(true);
    const { slugTouched: _slugTouched, depth: _depth, path: _path, displayDepth: _displayDepth, showPath: _showPath, ...payload } = editing;
    try {
      await (isCategory ? DashboardApi.saveCategory(payload, payload.id) : DashboardApi.saveTag(payload, payload.id));
      setEditing(null); setNotice(`${label} saved.`); await load();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  };
  const remove = async item => {
    const children = childCounts.get(item.id) || 0;
    const childText = children ? ` Its ${children} ${children === 1 ? 'subcategory' : 'subcategories'} will move to the top level.` : '';
    if (!window.confirm(`Delete ${label.toLowerCase()} "${item.name}"? Existing content will keep working, but this classification will be removed.${childText}`)) return;
    try {
      await (isCategory ? DashboardApi.deleteCategory(item.id) : DashboardApi.deleteTag(item.id));
      setNotice(`${label} deleted.`); setEditing(null); await load();
    } catch (err) { setError(err.message); }
  };
  const toggleSelect = id => setSelection(current => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const allSelected = rows.length > 0 && rows.every(row => selection.has(row.id));
  const bulkDelete = async () => {
    const chosen = items.filter(item => selection.has(item.id));
    const used = chosen.reduce((sum, item) => sum + (item.usage_count || 0), 0);
    if (!chosen.length || !window.confirm(`Delete ${chosen.length} selected ${chosen.length === 1 ? label.toLowerCase() : type}?${used ? ` They are attached to ${used} items; that content keeps working but loses these classifications.` : ''}`)) return;
    let failed = 0;
    for (const item of chosen) { try { await (isCategory ? DashboardApi.deleteCategory(item.id) : DashboardApi.deleteTag(item.id)); } catch { failed += 1; } }
    setSelection(new Set());
    if (failed) setError(`${failed} could not be deleted.`); else setNotice(`${chosen.length} ${chosen.length === 1 ? label.toLowerCase() : type} deleted.`);
    load();
  };

  const filterKey = isCategory ? 'category' : 'tag';
  const siteUrl = item => isCategory ? `/database/${item.slug}` : `/database?tag=${encodeURIComponent(item.slug)}`;
  const articlesUrl = item => `/dashboard/posts?${filterKey}=${item.id}`;
  const excluded = editing?.id ? descendantIds(items, editing.id) : new Set();
  const parentOptions = tree.filter(item => item.id !== editing?.id && !excluded.has(item.id));
  const editingUsage = editing?.id ? items.find(item => item.id === editing.id)?.usage_count || 0 : 0;

  const menuFor = item => [
    { label: 'View articles', icon: FileText, href: articlesUrl(item) },
    { label: 'View on site', icon: ExternalLink, href: siteUrl(item), external: true },
    isCategory && canCreate && { label: 'Add subcategory', icon: Plus, onClick: () => open({ ...blank(), parent_id: item.id }) },
    canDelete && { divider: true },
    canDelete && { label: 'Delete', icon: Trash2, danger: true, onClick: () => remove(item) },
  ];

  return (
    <div className="dlib-page">
      <AdminPageHeader
        eyebrow="Content library"
        title={`${label} Management`}
        text={`Create and organize ${type} used by posts, pages, and database search.${isCategory ? ' Choose a parent to nest one category under another.' : ''}`}
        actions={<>
          <Link className="admin-button admin-button-secondary" to={isCategory ? '/dashboard/tags' : '/dashboard/categories'}>{isCategory ? <TagIcon size={15} /> : <FolderTree size={15} />} {isCategory ? 'Tags' : 'Categories'}</Link>
          {isCategory && canEdit && <button className="admin-button admin-button-secondary" onClick={() => setArranging(true)} disabled={!items.length}><ArrowUpDown size={15} /> Arrange order</button>}
          {canCreate && <button className="admin-button" onClick={() => open()}><Plus size={15} /> New {label}</button>}
        </>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}{error && <AdminNotice type="error">{error}</AdminNotice>}

      <section className="dash-stat-grid dlib-stats" aria-label={`${label} overview`}>
        <StatCard icon={isCategory ? FolderTree : TagIcon} label={isCategory ? 'Categories' : 'Tags'} value={counts.all} hint={isCategory ? `${counts.top} top-level` : `${totalUses} assignments`} loading={status === 'loading'} />
        {isCategory
          ? <StatCard icon={ListTree} label="In public database" value={counts.visible} hint={`${counts.hidden} hidden`} loading={status === 'loading'} />
          : <StatCard icon={FileText} label="Most used" value={mostUsed?.usage_count ?? 0} hint={mostUsed ? decodeEntities(mostUsed.name) : 'No tags yet'} to={mostUsed ? articlesUrl(mostUsed) : undefined} loading={status === 'loading'} />}
        <StatCard icon={EyeOff} label="Unused" value={counts.unused} hint="Not attached to any content" tone={counts.unused ? 'amber' : 'blue'} loading={status === 'loading'} />
        <StatCard icon={FileText} label="Assignments" value={totalUses} hint={`Items classified with ${type}`} to="/dashboard/posts" loading={status === 'loading'} />
      </section>

      <section className="dashboard-card dlib-library">
        <div className="dlib-toolbar">
          <label className="dash-search-field"><Search size={16} aria-hidden="true" /><input value={query} onChange={event => setQuery(event.target.value)} placeholder={`Search ${type} by name, slug${isCategory ? ' or introduction' : ''}`} aria-label={`Search ${type}`} />{query && <button type="button" className="dlib-clear" onClick={() => setQuery('')} aria-label="Clear search"><X size={14} /></button>}</label>
          <Segmented label="Filter" value={filter} onChange={setFilter} options={[
            { id: 'all', label: 'All', count: counts.all },
            ...(isCategory ? [{ id: 'visible', label: 'Public', count: counts.visible }, { id: 'hidden', label: 'Hidden', count: counts.hidden }] : []),
            { id: 'unused', label: 'Unused', count: counts.unused },
          ]} />
          <select value={sort} onChange={event => setSort(event.target.value)} aria-label="Sort">
            {isCategory && <option value="tree">Hierarchy</option>}
            <option value="name">Name A–Z</option>
            <option value="usage">Most used</option>
          </select>
        </div>
        {canDelete && rows.length > 0 && (
          <div className={`dlib-selectbar ${selection.size ? 'has-selection' : ''}`}>
            <button type="button" className="dlib-link-button" onClick={() => setSelection(allSelected ? new Set() : new Set(rows.map(row => row.id)))}>{allSelected ? <CheckSquare size={15} /> : <Square size={15} />} {allSelected ? 'Clear selection' : 'Select all shown'}</button>
            <span role="status">{selection.size ? `${selection.size} selected` : `${rows.length} shown`}</span>
            {selection.size > 0 && <button type="button" className="admin-button admin-button-danger" onClick={bulkDelete}><Trash2 size={14} /> Delete selected</button>}
          </div>
        )}
        {status === 'loading' ? <StateBlock type="loading" title={`Loading ${type}`} />
          : !rows.length ? <StateBlock type="empty" title={items.length ? `No ${type} match` : `No ${type} yet`} text={items.length ? 'Change the search or filter.' : `Create your first ${label.toLowerCase()} to organize website content.`} action={!items.length && canWrite && <button type="button" className="admin-button" onClick={() => open()}><Plus size={15} /> Create the first {label.toLowerCase()}</button>} />
          : (
            <div className="dashboard-table-wrap">
              <table className="dashboard-table dlib-table dlib-taxonomy-table">
                <thead><tr>
                  {canDelete && <th className="dlib-col-check"><span className="dlib-sr">Select</span></th>}
                  <th>Name</th><th>Slug</th>
                  {isCategory && <th>Public database</th>}
                  <th className="dlib-num">Articles</th><th><span className="dlib-sr">Actions</span></th>
                </tr></thead>
                <tbody>
                  {rows.map(item => (
                    <tr key={item.id} className={selection.has(item.id) ? 'is-selected' : ''}>
                      {canDelete && <td className="dlib-col-check"><input type="checkbox" checked={selection.has(item.id)} onChange={() => toggleSelect(item.id)} aria-label={`Select ${item.name}`} /></td>}
                      <td data-label="Name" className="dlib-cell-main">
                        <button type="button" className="dlib-tree-name" style={{ '--depth': item.displayDepth }} onClick={() => open(item)}>
                          {item.displayDepth > 0 && <span className="dlib-tree-elbow" aria-hidden="true" />}
                          <span>
                            <strong>{decodeEntities(item.name)}</strong>
                            {item.showPath && <small>in {decodeEntities(item.path.join(' › '))}</small>}
                            {isCategory && !item.showPath && (childCounts.get(item.id) ? <small>{childCounts.get(item.id)} {childCounts.get(item.id) === 1 ? 'subcategory' : 'subcategories'}</small> : item.description ? <small className="dlib-clamp">{item.description}</small> : null)}
                          </span>
                        </button>
                      </td>
                      <td data-label="Slug"><code>{item.slug}</code></td>
                      {isCategory && <td data-label="Public database"><span className={item.show_in_database ? 'dlib-pill dlib-pill-ok' : 'dlib-pill'}>{item.show_in_database ? `Visible · order ${item.database_order || 0}` : 'Hidden'}</span></td>}
                      <td data-label="Articles" className="dlib-num">{item.usage_count ? <Link to={articlesUrl(item)} className="dlib-count-link" title={`View articles in this ${label.toLowerCase()}`}>{item.usage_count}</Link> : <span className="dlib-muted">0</span>}</td>
                      <td className="dlib-row-actions">
                        {canWrite && <button type="button" className="dlib-icon-text" onClick={() => open(item)}><Pencil size={14} /> Edit</button>}
                        <ActionMenu label={`More actions for ${item.name}`} items={menuFor(item)} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </section>

      <Drawer open={Boolean(editing)} onClose={close} width={560}
        title={editing?.id ? `Edit ${label.toLowerCase()}` : `New ${label.toLowerCase()}`}
        subtitle={editing?.id ? decodeEntities(editing.name) : `Used by posts, pages and database search`}
        footer={editing && <>
          {editing.id && canDelete && <button type="button" className="admin-button admin-button-danger dlib-footer-start" onClick={() => remove(editing)}><Trash2 size={15} /> Delete</button>}
          <button className="admin-button admin-button-secondary" type="button" onClick={close}><X size={15} /> Cancel</button>
          {canWrite && <button className="admin-button" form="dlib-taxonomy-form" disabled={saving}><Save size={15} /> Save {label}</button>}
        </>}>
        {editing && (
          <form id="dlib-taxonomy-form" className="dlib-form" onSubmit={save}>
            {editing.id && (
              <div className="dlib-quicklinks">
                <Link to={articlesUrl(editing)}><FileText size={15} /> View articles in this {label.toLowerCase()} <em>{editingUsage}</em></Link>
                <a href={siteUrl(editing)} target="_blank" rel="noreferrer"><ExternalLink size={15} /> View on site</a>
              </div>
            )}
            <div className="dlib-form-grid">
              <label>Name<input required name="name" value={editing.name} onChange={update} disabled={!canWrite} /></label>
              <label>Slug<input required name="slug" value={editing.slug} onChange={update} disabled={!canWrite} /><small>Public address: {isCategory ? `/database/${editing.slug || '…'}` : `/database?tag=${editing.slug || '…'}`}</small></label>
            </div>
            {isCategory && <>
              <label>Parent Category<select name="parent_id" value={editing.parent_id || ''} onChange={update} disabled={!canWrite}><option value="">No parent (top level)</option>{parentOptions.map(item => <option value={item.id} key={item.id}>{`${'— '.repeat(item.depth)}${decodeEntities(item.name)}`}</option>)}</select><small>A category cannot be placed inside one of its own subcategories.</small></label>
              <fieldset className="dlib-fieldset">
                <legend>Public database</legend>
                <label className="admin-check admin-check-inline dlib-switch"><input type="checkbox" name="show_in_database" checked={editing.show_in_database !== false} onChange={update} disabled={!canWrite} /> Show in public database navigation</label>
                <label>Database Order<input type="number" min="0" step="1" name="database_order" value={editing.database_order || 0} onChange={update} disabled={!canWrite} /><small>Lower numbers appear first in the public database.</small></label>
              </fieldset>
              <label>Category introduction<textarea name="description" value={editing.description || ''} onChange={update} rows="4" placeholder="Introduction shown on this category’s public page" disabled={!canWrite} /></label>
              <div className="dlib-image-field">
                <label>Category hero image URL<input name="hero_image" value={editing.hero_image || ''} onChange={update} placeholder="https://..." disabled={!canWrite} /></label>
                <div className="dlib-image-field-row">
                  <span className="dlib-image-thumb">{editing.hero_image ? <img src={editing.hero_image} alt="" /> : <ImageIcon size={20} aria-hidden="true" />}</span>
                  <div>
                    {canWrite && <button type="button" className="admin-button admin-button-secondary" onClick={() => setPicker(true)}><ImagePlus size={15} /> Choose from Media Library</button>}
                    {canWrite && editing.hero_image && <button type="button" className="admin-button admin-button-secondary" onClick={() => setEditing(current => ({ ...current, hero_image: '' }))}>Clear</button>}
                    <small>Leave blank to use the shared hero image.</small>
                  </div>
                </div>
              </div>
            </>}
            {dirty && <p className="dlib-dirty-note" role="status">Unsaved changes</p>}
          </form>
        )}
      </Drawer>
      {isCategory && <CategoryOrderDrawer open={arranging} items={items} onClose={() => setArranging(false)} onSaved={async () => { setArranging(false); setNotice('Category order saved. The public site now follows it.'); await load(); }} />}
      {isCategory && <MediaPicker open={picker} onClose={() => setPicker(false)} title="Choose a category hero image" onSelect={asset => setEditing(current => current ? { ...current, hero_image: asset.url } : current)} />}
    </div>
  );
}
