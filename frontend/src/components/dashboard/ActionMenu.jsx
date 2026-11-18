import { useEffect, useId, useRef, useState } from 'react';
import { MoreHorizontal } from 'lucide-react';

/**
 * Compact "more actions" menu for table rows and cards.
 * items: [{ label, icon: Icon, onClick?, href?, external?, danger?, disabled?, divider? }]
 */
export default function ActionMenu({ items, label = 'More actions', align = 'end', icon: Icon = MoreHorizontal }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const buttonRef = useRef(null);
  const menuId = useId();
  const visible = items.filter(Boolean);

  useEffect(() => {
    if (!open) return undefined;
    const onPointer = event => { if (!rootRef.current?.contains(event.target)) setOpen(false); };
    const onKey = event => {
      if (event.key === 'Escape') { setOpen(false); buttonRef.current?.focus(); }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        const entries = [...rootRef.current.querySelectorAll('[role="menuitem"]:not([disabled])')];
        const index = entries.indexOf(document.activeElement);
        entries[(index + (event.key === 'ArrowDown' ? 1 : -1) + entries.length) % entries.length]?.focus();
      }
    };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    requestAnimationFrame(() => rootRef.current?.querySelector('[role="menuitem"]:not([disabled])')?.focus());
    return () => { document.removeEventListener('mousedown', onPointer); document.removeEventListener('keydown', onKey); };
  }, [open]);

  if (!visible.length) return null;
  return (
    <div className="dash-action-menu" ref={rootRef}>
      <button ref={buttonRef} type="button" className="dash-icon-button" aria-label={label} title={label} aria-haspopup="menu" aria-expanded={open} aria-controls={open ? menuId : undefined} onClick={() => setOpen(current => !current)}>
        <Icon size={17} />
      </button>
      {open && (
        <div className={`dash-action-menu-list dash-action-menu-${align}`} role="menu" id={menuId}>
          {visible.map((item, index) => {
            if (item.divider) return <hr key={`divider-${index}`} />;
            const ItemIcon = item.icon;
            const content = <>{ItemIcon && <ItemIcon size={15} />}<span>{item.label}</span></>;
            const className = item.danger ? 'is-danger' : '';
            return item.href
              ? <a key={item.label} role="menuitem" className={className} href={item.href} target={item.external ? '_blank' : undefined} rel={item.external ? 'noreferrer' : undefined} onClick={() => setOpen(false)}>{content}</a>
              : <button key={item.label} type="button" role="menuitem" className={className} disabled={item.disabled} onClick={() => { setOpen(false); item.onClick?.(); }}>{content}</button>;
          })}
        </div>
      )}
    </div>
  );
}
