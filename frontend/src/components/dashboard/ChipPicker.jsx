import { useId, useMemo, useRef, useState } from 'react';
import { Check, Plus, Search, X } from 'lucide-react';

/**
 * Searchable multi-select shown as removable chips. Replaces long checkbox
 * lists (categories, tags, …). `options` = [{ id, label, hint? }], `value` =
 * array of ids. Optional `onCreate(label)` adds "Create “…”" for new items and
 * should resolve to the new option's id.
 */
export default function ChipPicker({ label, options, value = [], onChange, onCreate, placeholder = 'Search…', disabled = false, emptyText = 'Nothing selected yet.' }) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [creating, setCreating] = useState(false);
  const listId = useId();
  const inputRef = useRef(null);
  const selected = useMemo(() => value.map(id => options.find(option => option.id === id)).filter(Boolean), [options, value]);
  const term = query.trim().toLowerCase();
  const matches = useMemo(() => options.filter(option => !term || option.label.toLowerCase().includes(term)).slice(0, 40), [options, term]);
  const exact = options.some(option => option.label.toLowerCase() === term);
  const canCreate = Boolean(onCreate && term && !exact);
  const toggle = id => onChange(value.includes(id) ? value.filter(item => item !== id) : [...value, id]);
  const create = async () => {
    if (!canCreate || creating) return;
    setCreating(true);
    try {
      const id = await onCreate(query.trim());
      if (id) onChange([...value, id]);
      setQuery('');
    } finally {
      setCreating(false);
    }
  };
  const onKeyDown = event => {
    const total = matches.length + (canCreate ? 1 : 0);
    if (event.key === 'ArrowDown') { event.preventDefault(); setOpen(true); setActive(current => (current + 1) % Math.max(total, 1)); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); setActive(current => (current - 1 + Math.max(total, 1)) % Math.max(total, 1)); }
    else if (event.key === 'Enter') {
      event.preventDefault();
      if (active < matches.length && matches[active]) toggle(matches[active].id);
      else create();
    } else if (event.key === 'Escape') setOpen(false);
    else if (event.key === 'Backspace' && !query && value.length) onChange(value.slice(0, -1));
  };

  return (
    <div className={`dash-chip-picker ${disabled ? 'is-disabled' : ''}`} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
      {label && <span className="dash-chip-picker-label">{label}</span>}
      <div className="dash-chip-picker-chips">
        {selected.length ? selected.map(option => (
          <span className="dash-chip" key={option.id}>
            {option.label}
            {!disabled && <button type="button" onClick={() => toggle(option.id)} aria-label={`Remove ${option.label}`}><X size={12} /></button>}
          </span>
        )) : <span className="dash-chip-picker-empty">{emptyText}</span>}
      </div>
      {!disabled && (
        <div className="dash-chip-picker-field">
          <Search size={15} aria-hidden="true" />
          <input
            ref={inputRef}
            role="combobox"
            aria-expanded={open}
            aria-controls={listId}
            aria-label={label ? `Search ${label.toLowerCase()}` : placeholder}
            value={query}
            placeholder={placeholder}
            onFocus={() => setOpen(true)}
            onChange={event => { setQuery(event.target.value); setOpen(true); setActive(0); }}
            onKeyDown={onKeyDown}
          />
        </div>
      )}
      {open && !disabled && (
        <ul className="dash-chip-picker-menu" id={listId} role="listbox" aria-multiselectable="true">
          {matches.map((option, index) => {
            const isSelected = value.includes(option.id);
            return (
              <li key={option.id} role="option" aria-selected={isSelected}>
                <button type="button" tabIndex={-1} className={index === active ? 'is-active' : ''} onMouseEnter={() => setActive(index)} onMouseDown={event => event.preventDefault()} onClick={() => toggle(option.id)}>
                  <span className="dash-chip-picker-check">{isSelected && <Check size={13} />}</span>
                  <span>{option.label}</span>
                  {option.hint && <small>{option.hint}</small>}
                </button>
              </li>
            );
          })}
          {canCreate && (
            <li role="option" aria-selected="false">
              <button type="button" tabIndex={-1} className={active === matches.length ? 'is-active' : ''} onMouseDown={event => event.preventDefault()} onClick={create} disabled={creating}>
                <span className="dash-chip-picker-check"><Plus size={13} /></span>
                <span>{creating ? 'Creating…' : `Create “${query.trim()}”`}</span>
              </button>
            </li>
          )}
          {!matches.length && !canCreate && <li className="dash-chip-picker-none">No matches</li>}
        </ul>
      )}
    </div>
  );
}
