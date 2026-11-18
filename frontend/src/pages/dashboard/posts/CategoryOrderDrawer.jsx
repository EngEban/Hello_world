import { ArrowDown, ArrowUp, ChevronDown, GripVertical, Pin, Save, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { DashboardApi } from '../../../api/dashboardApi';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import { Drawer } from '../../../components/dashboard/DashboardPrimitives';
import { decodeEntities, useUnsavedWarning } from '../media/libraryKit';

// Always highlighted first on the public site, so it is not moved here.
const MAIN_CATEGORY_SLUG = 'mastering-research';

function groupByParent(items) {
  const ids = new Set(items.map(item => item.id));
  const groups = {};
  items.forEach(item => {
    const parent = ids.has(item.parent_id) ? item.parent_id : 'top';
    (groups[parent] ||= []).push(item.id);
  });
  if (groups.top) groups.top.sort((a, b) => Number(items.find(item => item.id === b).slug === MAIN_CATEGORY_SLUG) - Number(items.find(item => item.id === a).slug === MAIN_CATEGORY_SLUG));
  return groups;
}

export default function CategoryOrderDrawer({ open, items, onClose, onSaved }) {
  const byId = useMemo(() => new Map(items.map(item => [item.id, item])), [items]);
  const [groups, setGroups] = useState({});
  const [initial, setInitial] = useState('');
  const [expanded, setExpanded] = useState(() => new Set());
  const [drag, setDrag] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    const next = groupByParent(items);
    setGroups(next); setInitial(JSON.stringify(next)); setExpanded(new Set()); setError('');
  }, [open, items]);

  const dirty = open && JSON.stringify(groups) !== initial;
  useUnsavedWarning(dirty);
  const close = () => { if (dirty && !window.confirm('Discard the new order?')) return; onClose(); };

  const pinned = id => byId.get(id)?.slug === MAIN_CATEGORY_SLUG;
  const move = (group, id, target) => setGroups(current => {
    const list = current[group].filter(item => item !== id);
    list.splice(target, 0, id);
    return { ...current, [group]: list };
  });
  const firstMovable = group => groups[group].filter(pinned).length;

  const save = async () => {
    setSaving(true); setError('');
    try {
      await DashboardApi.reorderCategories(Object.values(groups).flat());
      onSaved();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  };

  const row = (id, group) => {
    const item = byId.get(id);
    const list = groups[group];
    const index = list.indexOf(id);
    const fixed = pinned(id);
    const children = groups[id] || [];
    const isOpen = expanded.has(id);
    const name = decodeEntities(item.name);
    return <li key={id} className={drag?.id === id ? 'is-dragging' : ''}
      onDragOver={event => {
        if (!drag || drag.group !== group || fixed) return;
        event.preventDefault(); event.stopPropagation();
        if (drag.id !== id) move(group, drag.id, index);
      }}>
      <div className="dlib-order-row">
        {fixed
          ? <span className="dlib-order-handle is-fixed" title="Always first on the site"><Pin size={15} aria-hidden="true" /></span>
          : <span className="dlib-order-handle" draggable title="Drag to reorder" aria-hidden="true"
              onDragStart={event => { event.stopPropagation(); event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', String(id)); setDrag({ id, group }); }}
              onDragEnd={() => setDrag(null)}><GripVertical size={16} /></span>}
        <span className="dlib-order-name">
          <strong>{name}</strong>
          <small>{fixed ? 'Highlighted first on the site' : !item.show_in_database ? 'Hidden from the site' : !item.usage_count && !children.length ? 'No articles yet, not shown on the site' : `${item.usage_count || 0} ${item.usage_count === 1 ? 'article' : 'articles'}`}</small>
        </span>
        {children.length > 1 && <button type="button" className="dlib-order-toggle" aria-expanded={isOpen} onClick={() => setExpanded(current => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; })}>{children.length} subcategories<ChevronDown size={14} aria-hidden="true" /></button>}
        {!fixed && <span className="dlib-order-arrows">
          <button type="button" disabled={index <= firstMovable(group)} aria-label={`Move ${name} up`} onClick={() => move(group, id, index - 1)}><ArrowUp size={14} /></button>
          <button type="button" disabled={index === list.length - 1} aria-label={`Move ${name} down`} onClick={() => move(group, id, index + 1)}><ArrowDown size={14} /></button>
        </span>}
      </div>
      {isOpen && <ol className="dlib-order-list is-nested">{children.map(child => row(child, id))}</ol>}
    </li>;
  };

  return (
    <Drawer open={open} onClose={close} width={620} title="Arrange categories" subtitle="Drag a category or use the arrows. The public site follows this order and only shows categories with published articles."
      footer={<>
        <button className="admin-button admin-button-secondary" type="button" onClick={close}><X size={15} /> Cancel</button>
        <button className="admin-button" type="button" disabled={saving || !dirty} onClick={save}><Save size={15} /> {saving ? 'Saving...' : 'Save order'}</button>
      </>}>
      {error && <AdminNotice type="error">{error}</AdminNotice>}
      {groups.top && <ol className="dlib-order-list">{groups.top.map(id => row(id, 'top'))}</ol>}
    </Drawer>
  );
}
