import { ArrowDown, ArrowUp, ExternalLink, Eye, EyeOff, GripVertical, HelpCircle, Loader2, Pencil, Plus, RefreshCw, Save, Search, Trash2, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { DashboardApi } from '../../../api/dashboardApi';
import ActionMenu from '../../../components/dashboard/ActionMenu';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import AdminPagination from '../../../components/dashboard/AdminPagination';
import { Drawer, StatCard, StateBlock, StatusPill } from '../../../components/dashboard/DashboardPrimitives';
import { Segmented, slugify, useLibraryPermissions, useUnsavedWarning } from '../media/libraryKit';
import '../../../styles/dashboard/dash-library.css';

const emptyCategory = { name: '', slug: '', sort_order: 0 };
const emptyItem = { question: '', answer: '', category: '', status: 'published', sort_order: 0 };
const faqApiMessage = error => {
  const message = error?.message || 'FAQ data could not be loaded.';
  if (message.includes('404')) return 'FAQ dashboard API was not found. Restart the Django server so the latest dashboard routes are loaded.';
  return message;
};
const plain = text => String(text || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();

export default function DashboardFaqPage() {
  const { canCreate, canWrite, canDelete } = useLibraryPermissions('faq');
  const [categories, setCategories] = useState([]);
  const [items, setItems] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [activeCategory, setActiveCategory] = useState('');
  const [filters, setFilters] = useState({ q: '', status: '', page: 1 });
  const [search, setSearch] = useState('');
  const [categoryEditing, setCategoryEditing] = useState(null);
  const [itemEditing, setItemEditing] = useState(null);
  const [itemOriginal, setItemOriginal] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const dragId = useRef(null);
  const [dragOver, setDragOver] = useState(null);

  const selectedCategory = useMemo(() => categories.find(item => String(item.id) === String(activeCategory)), [categories, activeCategory]);
  const totals = useMemo(() => categories.reduce((sum, item) => ({ items: sum.items + (item.item_count || 0), published: sum.published + (item.published_count || 0) }), { items: 0, published: 0 }), [categories]);
  const canReorder = canWrite && !filters.q && !filters.status && (!pagination || pagination.total_pages <= 1);

  const loadCategories = async () => {
    const data = await DashboardApi.getFaqCategories();
    const next = [...(data.results || [])].sort((a, b) => (a.sort_order - b.sort_order) || a.name.localeCompare(b.name));
    setCategories(next);
    if (!activeCategory && next.length) setActiveCategory(String(next[0].id));
    return next;
  };

  const loadItems = async (nextFilters = filters, categoryId = activeCategory) => {
    setLoading(true);
    setError('');
    if (!categoryId) { setItems([]); setPagination(null); setLoading(false); return; }
    try {
      const data = await DashboardApi.getFaqItems({ ...nextFilters, category: categoryId, per_page: 100, sort: 'sort_order' });
      setItems(data.results || []);
      setPagination(data.pagination);
    } catch (err) {
      setError(faqApiMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCategories()
      .then(next => {
        const firstCategory = activeCategory || next[0]?.id || '';
        if (firstCategory) return loadItems(filters, firstCategory);
        setLoading(false);
        return null;
      })
      .catch(err => { setError(faqApiMessage(err)); setLoading(false); });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (activeCategory) loadItems({ ...filters, page: 1 }, activeCategory);
  }, [activeCategory]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const timer = setTimeout(() => { if (search.trim() !== filters.q) updateFilter({ q: search.trim() }); }, 300);
    return () => clearTimeout(timer);
  }, [search]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateFilter = patch => { const next = { ...filters, ...patch, page: 1 }; setFilters(next); loadItems(next); };
  const changePage = page => { const next = { ...filters, page }; setFilters(next); loadItems(next); };
  const refresh = async () => { await loadCategories(); await loadItems(); };

  const updateCategory = event => {
    const { name, value } = event.target;
    setCategoryEditing(current => ({ ...current, [name]: value, ...(name === 'name' && !current.id && !current.slugTouched ? { slug: slugify(value) } : {}), ...(name === 'slug' ? { slugTouched: true } : {}) }));
  };
  const updateItem = event => { const { name, value } = event.target; setItemEditing(current => ({ ...current, [name]: value })); };

  const saveCategory = async event => {
    event.preventDefault(); setError('');
    const { slugTouched: _slugTouched, ...payload } = categoryEditing;
    try {
      const result = await DashboardApi.saveFaqCategory(payload, payload.id);
      setNotice('FAQ category saved.');
      setCategoryEditing(null);
      await loadCategories();
      if (result.category?.id) setActiveCategory(String(result.category.id));
    } catch (err) { setError(err.message); }
  };
  const deleteCategory = async item => {
    if (!window.confirm(`Delete FAQ category "${item.name}"? Only empty categories can be deleted.`)) return;
    try {
      await DashboardApi.deleteFaqCategory(item.id);
      setNotice('FAQ category deleted.');
      setCategoryEditing(null);
      const next = await loadCategories();
      setActiveCategory(next[0]?.id ? String(next[0].id) : '');
    } catch (err) { setError(err.message); }
  };

  const startItem = item => {
    const lastOrder = items.reduce((max, row) => Math.max(max, row.sort_order || 0), 0);
    const next = { ...emptyItem, category: activeCategory, sort_order: item?.id ? item.sort_order : lastOrder + 10, ...(item || {}) };
    setItemEditing(next);
    setItemOriginal(JSON.stringify(next));
  };
  const itemDirty = Boolean(itemEditing) && JSON.stringify(itemEditing) !== itemOriginal;
  useUnsavedWarning(itemDirty);
  const closeItem = () => { if (itemDirty && !window.confirm('Discard unsaved changes to this question?')) return; setItemEditing(null); };

  const saveItem = async event => {
    event.preventDefault(); setError('');
    try {
      await DashboardApi.saveFaqItem(itemEditing, itemEditing.id);
      setNotice('FAQ item saved.');
      setItemEditing(null);
      await loadItems();
      await loadCategories();
    } catch (err) { setError(err.message); }
  };
  const hideItem = async item => {
    if (!window.confirm(`Hide FAQ item "${item.question}" from the public website?`)) return;
    try {
      await DashboardApi.hideFaqItem(item.id);
      setNotice('FAQ item hidden.');
      setItemEditing(null);
      await loadItems();
      await loadCategories();
    } catch (err) { setError(err.message); }
  };
  const showItem = async item => {
    try {
      await DashboardApi.saveFaqItem({ ...item, status: 'published' }, item.id);
      setNotice('FAQ item is visible on the public website again.');
      await loadItems();
      await loadCategories();
    } catch (err) { setError(err.message); }
  };

  /** Persist a new order as 10, 20, 30… so there is room to insert items later. */
  const persistOrder = async ordered => {
    const changed = ordered.map((item, index) => ({ ...item, sort_order: (index + 1) * 10 })).filter((item, index) => item.sort_order !== ordered[index].sort_order);
    setItems(ordered.map((item, index) => ({ ...item, sort_order: (index + 1) * 10 })));
    if (!changed.length) return;
    setBusy(true);
    try {
      for (const item of changed) await DashboardApi.saveFaqItem({ category: item.category, question: item.question, answer: item.answer, status: item.status, sort_order: item.sort_order }, item.id);
      setNotice('FAQ order saved. The public FAQ uses this order.');
    } catch (err) { setError(err.message); await loadItems(); }
    finally { setBusy(false); }
  };
  const moveItem = (index, delta) => {
    const target = index + delta;
    if (target < 0 || target >= items.length) return;
    const next = [...items];
    [next[index], next[target]] = [next[target], next[index]];
    persistOrder(next);
  };
  const dropOn = targetId => {
    const fromId = dragId.current;
    dragId.current = null; setDragOver(null);
    if (!fromId || fromId === targetId) return;
    const next = [...items];
    const from = next.findIndex(item => item.id === fromId);
    const [moved] = next.splice(from, 1);
    next.splice(next.findIndex(item => item.id === targetId), 0, moved);
    persistOrder(next);
  };
  const moveCategory = async (index, delta) => {
    const target = index + delta;
    if (target < 0 || target >= categories.length) return;
    const next = [...categories];
    [next[index], next[target]] = [next[target], next[index]];
    const renumbered = next.map((item, position) => ({ ...item, sort_order: (position + 1) * 10 }));
    setCategories(renumbered);
    setBusy(true);
    try {
      for (const item of renumbered.filter((item, position) => item.sort_order !== next[position].sort_order)) await DashboardApi.saveFaqCategory({ name: item.name, slug: item.slug, sort_order: item.sort_order }, item.id);
      setNotice('FAQ category order saved.');
    } catch (err) { setError(err.message); await loadCategories(); }
    finally { setBusy(false); }
  };

  return (
    <div className="dlib-page">
      <AdminPageHeader
        eyebrow="Content library"
        title="FAQ Manager"
        text="Manage public FAQ categories and questions safely. Hidden items stay in the dashboard but disappear from the public website."
        actions={<>
          <a className="admin-button admin-button-secondary" href="/faq" target="_blank" rel="noreferrer"><ExternalLink size={15} /> Preview FAQ</a>
          {canCreate && <button className="admin-button" onClick={() => setCategoryEditing(emptyCategory)}><Plus size={15} /> Add Category</button>}
        </>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}
      {error && <AdminNotice type="error">{error}</AdminNotice>}

      <section className="dash-stat-grid dlib-stats" aria-label="FAQ overview">
        <StatCard icon={HelpCircle} label="Questions" value={totals.items} hint={`${categories.length} categories`} />
        <StatCard icon={Eye} label="Published" value={totals.published} hint="Visible on /faq" />
        <StatCard icon={EyeOff} label="Hidden" value={totals.items - totals.published} hint="Kept in the dashboard only" tone={totals.items - totals.published ? 'amber' : 'blue'} />
        <StatCard icon={Pencil} label="This category" value={selectedCategory?.item_count ?? 0} hint={selectedCategory ? selectedCategory.name : 'Choose a category'} />
      </section>

      <div className="dlib-faq-layout">
        <section className="dashboard-card dlib-faq-categories" aria-label="FAQ categories">
          <div className="dlib-card-head"><h2>Categories</h2><span className="dlib-muted">{categories.length}</span></div>
          {categories.length ? (
            <ul className="dlib-faq-cat-list">
              {categories.map((category, index) => {
                const active = String(category.id) === String(activeCategory);
                const hidden = category.hidden_count ?? ((category.item_count || 0) - (category.published_count || 0));
                return (
                  <li key={category.id} className={active ? 'is-active' : ''}>
                    <button type="button" className="dlib-faq-cat" aria-current={active ? 'true' : undefined} onClick={() => setActiveCategory(String(category.id))}>
                      <strong>{category.name}</strong>
                      <small>{category.published_count || 0} published / {category.item_count || 0} total{hidden ? ` · ${hidden} hidden` : ''}</small>
                    </button>
                    {canWrite && <span className="dlib-faq-cat-move">
                      <button type="button" onClick={() => moveCategory(index, -1)} disabled={busy || index === 0} aria-label={`Move ${category.name} up`}><ArrowUp size={13} /></button>
                      <button type="button" onClick={() => moveCategory(index, 1)} disabled={busy || index === categories.length - 1} aria-label={`Move ${category.name} down`}><ArrowDown size={13} /></button>
                    </span>}
                  </li>
                );
              })}
            </ul>
          ) : <StateBlock type="empty" title="No FAQ categories" text="Create a category to start adding questions." />}
        </section>

        <section className="dashboard-card dlib-faq-items">
          <div className="dlib-faq-head">
            <div>
              <span className="dash-eyebrow">{selectedCategory ? `Order ${selectedCategory.sort_order} · /${selectedCategory.slug}` : 'FAQ items'}</span>
              <h2>{selectedCategory?.name || 'Questions and answers'}</h2>
            </div>
            <div className="dlib-inline-actions">
              {selectedCategory && (canWrite || canDelete) && <ActionMenu label="Category actions" items={[
                canWrite && { label: 'Edit category', icon: Pencil, onClick: () => setCategoryEditing(selectedCategory) },
                { label: 'Preview on site', icon: ExternalLink, href: '/faq', external: true },
                canDelete && { divider: true },
                canDelete && { label: 'Delete category', icon: Trash2, danger: true, onClick: () => deleteCategory(selectedCategory) },
              ].filter(Boolean)} />}
              {canCreate && <button className="admin-button" onClick={() => startItem(null)} disabled={!activeCategory}><Plus size={15} /> Add Question</button>}
            </div>
          </div>
          <div className="dlib-toolbar">
            <label className="dash-search-field"><Search size={16} aria-hidden="true" /><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search FAQ items" aria-label="Search FAQ items" />{search && <button type="button" className="dlib-clear" onClick={() => setSearch('')} aria-label="Clear search"><X size={14} /></button>}</label>
            <Segmented label="Status" value={filters.status} onChange={status => updateFilter({ status })} options={[{ id: '', label: 'All status' }, { id: 'published', label: 'Published' }, { id: 'hidden', label: 'Hidden' }]} />
            <button type="button" className="dash-icon-button" onClick={refresh} aria-label="Refresh" title="Refresh"><RefreshCw size={15} /></button>
          </div>
          <p className="dlib-hint-line" role="status">{busy ? <><Loader2 size={13} className="spin" /> Saving order…</> : canReorder ? 'Drag questions by the handle, or use the arrows, to change the order on the public FAQ.' : canWrite ? 'Clear the search and status filter to reorder questions.' : ''}</p>

          {loading ? <StateBlock type="loading" title="Loading questions" />
            : !items.length ? <StateBlock type="empty" title="No FAQ items found" text={filters.q || filters.status ? 'Try changing the search or status filter.' : 'This category has no questions yet.'} action={!filters.q && !filters.status && activeCategory && canWrite && <button type="button" className="admin-button admin-button-secondary" onClick={() => startItem(null)}><Plus size={15} /> Write the first one</button>} />
            : (
              <ol className="dlib-faq-list">
                {items.map((row, index) => (
                  <li key={row.id} className={`${row.status === 'hidden' ? 'is-hidden' : ''} ${dragOver === row.id ? 'is-drop-target' : ''}`}
                    draggable={canReorder && !busy}
                    onDragStart={event => { dragId.current = row.id; event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', String(row.id)); }}
                    onDragOver={event => { if (dragId.current) { event.preventDefault(); setDragOver(row.id); } }}
                    onDragLeave={() => setDragOver(current => current === row.id ? null : current)}
                    onDrop={event => { event.preventDefault(); dropOn(row.id); }}
                    onDragEnd={() => { dragId.current = null; setDragOver(null); }}>
                    {canReorder && <span className="dlib-faq-handle" aria-hidden="true"><GripVertical size={16} /></span>}
                    <button type="button" className="dlib-faq-q" onClick={() => startItem(row)}>
                      <strong>{row.question}</strong>
                      <small>{plain(row.answer).slice(0, 160)}{plain(row.answer).length > 160 ? '…' : ''}</small>
                    </button>
                    <div className="dlib-faq-meta">
                      <StatusPill value={row.status} />
                      <small>#{row.sort_order} · {row.updated_at ? new Date(row.updated_at).toLocaleDateString() : '—'}</small>
                    </div>
                    <div className="dlib-faq-actions">
                      {canWrite && <button type="button" role="switch" aria-checked={row.status === 'published'} className={`dlib-toggle ${row.status === 'published' ? 'is-on' : ''}`} onClick={() => (row.status === 'published' ? hideItem(row) : showItem(row))} aria-label={`${row.status === 'published' ? 'Hide' : 'Show'} “${row.question}” on the public FAQ`} title={row.status === 'published' ? 'Visible · click to hide' : 'Hidden · click to show'}><span /></button>}
                      {canReorder && <>
                        <button type="button" className="dash-icon-button dlib-mini" onClick={() => moveItem(index, -1)} disabled={busy || index === 0} aria-label={`Move “${row.question}” up`}><ArrowUp size={14} /></button>
                        <button type="button" className="dash-icon-button dlib-mini" onClick={() => moveItem(index, 1)} disabled={busy || index === items.length - 1} aria-label={`Move “${row.question}” down`}><ArrowDown size={14} /></button>
                      </>}
                      {canWrite && <button type="button" className="dash-icon-button dlib-mini" onClick={() => startItem(row)} aria-label={`Edit “${row.question}”`}><Pencil size={14} /></button>}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          <AdminPagination pagination={pagination} onPage={changePage} />
        </section>
      </div>

      <Drawer open={Boolean(categoryEditing)} onClose={() => setCategoryEditing(null)} width={480} title={categoryEditing?.id ? 'Edit FAQ Category' : 'New FAQ Category'} subtitle={categoryEditing?.id ? `${categoryEditing.item_count || 0} questions` : 'Groups questions on the public FAQ'}
        footer={categoryEditing && <>
          {categoryEditing.id && <button type="button" className="admin-button admin-button-danger dlib-footer-start" onClick={() => deleteCategory(categoryEditing)}><Trash2 size={15} /> Delete</button>}
          <button type="button" className="admin-button admin-button-secondary" onClick={() => setCategoryEditing(null)}>Cancel</button>
          <button className="admin-button" form="faq-category-editor"><Save size={15} /> Save</button>
        </>}>
        {categoryEditing && (
          <form id="faq-category-editor" className="dlib-form" onSubmit={saveCategory}>
            <label>Name<input required name="name" value={categoryEditing.name || ''} onChange={updateCategory} /></label>
            <label>Slug<input name="slug" value={categoryEditing.slug || ''} onChange={updateCategory} placeholder="Auto-generated when empty" /></label>
            <label>Sort order<input type="number" name="sort_order" value={categoryEditing.sort_order || 0} onChange={updateCategory} /><small>Lower numbers appear first. You can also use the arrows in the category list.</small></label>
            {categoryEditing.id && categoryEditing.item_count > 0 && <p className="dlib-muted">Only empty categories can be deleted. Move or hide its questions first.</p>}
          </form>
        )}
      </Drawer>

      <Drawer open={Boolean(itemEditing)} onClose={closeItem} width={620} title={itemEditing?.id ? 'Edit FAQ Item' : 'New FAQ Item'} subtitle={itemEditing?.id ? `Last updated ${itemEditing.updated_at ? new Date(itemEditing.updated_at).toLocaleString() : '—'}` : selectedCategory?.name}
        footer={itemEditing && <>
          <button type="button" className="admin-button admin-button-secondary" onClick={closeItem}><X size={15} /> Cancel</button>
          {itemEditing.id && itemEditing.status !== 'hidden' && <button type="button" className="admin-button admin-button-secondary" onClick={() => hideItem(itemEditing)}><EyeOff size={15} /> Hide</button>}
          <button className="admin-button" form="faq-item-editor"><Save size={15} /> Save</button>
        </>}>
        {itemEditing && (
          <form id="faq-item-editor" className="dlib-form" onSubmit={saveItem}>
            <div className="dlib-form-grid dlib-form-grid-3">
              <label>Category<select name="category" value={itemEditing.category || ''} onChange={updateItem} required><option value="" disabled>Choose a category</option>{categories.map(category => <option value={category.id} key={category.id}>{category.name}</option>)}</select></label>
              <label>Status<select name="status" value={itemEditing.status || 'published'} onChange={updateItem}><option value="published">published</option><option value="hidden">hidden</option></select></label>
              <label>Sort order<input type="number" name="sort_order" value={itemEditing.sort_order || 0} onChange={updateItem} /></label>
            </div>
            <label>Question<input required name="question" value={itemEditing.question || ''} onChange={updateItem} maxLength="255" /><small>{(itemEditing.question || '').length}/255</small></label>
            <label>Answer<textarea required name="answer" value={itemEditing.answer || ''} onChange={updateItem} rows="9" /></label>
            {itemEditing.status === 'hidden' && <p className="dlib-muted"><EyeOff size={13} aria-hidden="true" /> Hidden questions stay here but are not shown on the public FAQ.</p>}
            {itemDirty && <p className="dlib-dirty-note" role="status">Unsaved changes</p>}
          </form>
        )}
      </Drawer>
    </div>
  );
}
