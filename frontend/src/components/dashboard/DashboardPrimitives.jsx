import { useEffect, useId, useRef } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, ArrowUpRight, CheckCircle2, Loader2, Search, X } from 'lucide-react';

export function DashboardCard({ title, eyebrow, actions, children, className = '' }) {
  return (
    <section className={`dashboard-card ${className}`}>
      {(title || eyebrow || actions) && (
        <div className="dashboard-card-head">
          <div>
            {eyebrow && <span>{eyebrow}</span>}
            {title && <h2>{title}</h2>}
          </div>
          {actions && <div className="dashboard-card-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function MetricCard({ icon: Icon, label, value, hint, trend, tone = 'blue' }) {
  return (
    <article className={`metric-card metric-${tone}`}>
      {Icon && <span className="metric-icon"><Icon size={19} /></span>}
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        {(hint || trend) && <small className={trend?.startsWith('-') ? 'negative' : ''}>{trend || hint}</small>}
      </div>
    </article>
  );
}

export function DashboardToolbar({ search, onSearch, filters, actions, placeholder = 'Search...' }) {
  return (
    <div className="dashboard-toolbar">
      {onSearch && (
        <label className="dashboard-search">
          <Search size={16} />
          <input value={search || ''} onChange={event => onSearch(event.target.value)} placeholder={placeholder} />
        </label>
      )}
      {filters}
      {actions && <div className="dashboard-toolbar-actions">{actions}</div>}
    </div>
  );
}

export function DashboardTable({ columns, rows, rowKey = 'id', onRowClick, emptyTitle = 'No data found', loading = false }) {
  if (loading) return <StateBlock type="loading" title="Loading data" text="Fetching the latest dashboard records..." />;
  if (!rows?.length) return <StateBlock type="empty" title={emptyTitle} text="Try changing filters or create a new record." />;
  return (
    <div className="dashboard-table-wrap">
      <table className="dashboard-table">
        <thead>
          <tr>{columns.map(column => <th key={column.key}>{column.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row[rowKey]} onClick={onRowClick ? event => { if (!event.target.closest('a, button, input, select, textarea, label, [role="menu"]')) onRowClick(row); } : undefined} className={onRowClick ? 'clickable' : ''}>
              {columns.map(column => <td data-label={column.label} key={column.key}>{column.render ? column.render(row) : row[column.key]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function StateBlock({ type = 'empty', title, text, action }) {
  const Icon = type === 'error' ? AlertCircle : type === 'loading' ? Loader2 : CheckCircle2;
  return (
    <div className={`dashboard-state dashboard-state-${type}`} role={type === 'error' ? 'alert' : 'status'} aria-live={type === 'error' ? 'assertive' : 'polite'} aria-busy={type === 'loading'}>
      <Icon size={24} className={type === 'loading' ? 'spin' : ''} />
      <strong>{title}</strong>
      {text && <p>{text}</p>}
      {action}
    </div>
  );
}

export function SimpleBarChart({ data = [], labelKey = 'status', valueKey = 'count' }) {
  const max = Math.max(...data.map(item => item[valueKey] || 0), 1);
  return (
    <div className="simple-bars">
      {data.map(item => (
        <div className="simple-bar-row" key={item[labelKey]}>
          <span>{item[labelKey]}</span>
          <i><b style={{ width: `${Math.max(6, Math.round(((item[valueKey] || 0) / max) * 100))}%` }} /></i>
          <strong>{item[valueKey] || 0}</strong>
        </div>
      ))}
    </div>
  );
}

export function DonutSummary({ data = [], totalLabel = 'Total' }) {
  const total = data.reduce((sum, item) => sum + (item.count || 0), 0);
  // Slices proportional to the data (an empty set shows a neutral ring).
  let start = 0;
  const slices = data.map((item, index) => {
    const end = start + (total ? ((item.count || 0) / total) * 100 : 0);
    const slice = `var(--chart-${(index % 5) + 1}) ${start.toFixed(2)}% ${end.toFixed(2)}%`;
    start = end;
    return slice;
  });
  const ring = total ? `conic-gradient(${slices.join(', ')})` : 'conic-gradient(#e8eff7 0 100%)';
  return (
    <div className="donut-summary">
      <div className="donut-ring" style={{ background: `radial-gradient(circle, #fff 0 49%, transparent 50%), ${ring}` }}><strong>{total}</strong><span>{totalLabel}</span></div>
      <div className="donut-legend">
        {data.map((item, index) => <span key={item.status || index}><i style={{ '--tone': `var(--chart-${(index % 5) + 1})` }} />{item.status || item.label}: {item.count}</span>)}
      </div>
    </div>
  );
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function DashboardModal({ title, children, onClose, footer }) {
  // Keyboard support for a modal dialog (WCAG 2.1.2 / 2.4.3): move focus
  // into the dialog, keep Tab inside it, close on Escape and give focus back
  // to the control that opened it.
  const dialogRef = useRef(null);
  const closeRef = useRef(onClose);
  useEffect(() => { closeRef.current = onClose; }, [onClose]);
  useEffect(() => {
    const dialog = dialogRef.current;
    const opener = dialog?.contains(document.activeElement) ? null : document.activeElement;
    const items = () => [...(dialog?.querySelectorAll(FOCUSABLE) || [])].filter(item => item.offsetParent !== null);
    const body = dialog?.querySelector('.dashboard-modal-body');
    if (!dialog?.contains(document.activeElement)) {
      (body && [...body.querySelectorAll(FOCUSABLE)].find(item => item.offsetParent !== null) || items()[0] || dialog)?.focus();
    }
    const onKeyDown = event => {
      if (event.key === 'Escape') { event.stopPropagation(); closeRef.current?.(); return; }
      if (event.key !== 'Tab') return;
      const list = items();
      if (!list.length) { event.preventDefault(); return; }
      if (event.shiftKey && document.activeElement === list[0]) { event.preventDefault(); list.at(-1).focus(); }
      else if (!event.shiftKey && document.activeElement === list.at(-1)) { event.preventDefault(); list[0].focus(); }
    };
    dialog?.addEventListener('keydown', onKeyDown);
    return () => {
      dialog?.removeEventListener('keydown', onKeyDown);
      if (opener && typeof opener.focus === 'function' && document.contains(opener)) opener.focus();
    };
  }, []);
  return (
    <div className="dashboard-modal-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={dialogRef} className="dashboard-modal" role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}>
        <header>
          <h2>{title}</h2>
          <button type="button" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </header>
        <div className="dashboard-modal-body">{children}</div>
        {footer && <footer>{footer}</footer>}
      </section>
    </div>
  );
}

export function StatusPill({ value }) {
  return <span className={`status-badge status-${String(value || '').replaceAll('_', '-')}`}>{String(value || 'unknown').replaceAll('_', ' ')}</span>;
}

/** Clickable KPI tile: icon badge, serif value, label and an optional hint/trend. */
export function StatCard({ icon: Icon, label, value, hint, to, onClick, active = false, tone = 'blue', loading = false }) {
  const body = <>
    {Icon && <span className="dash-stat-icon" aria-hidden="true"><Icon size={19} /></span>}
    <span className="dash-stat-copy">
      <small>{label}</small>
      <strong className={loading ? 'is-loading' : ''}>{loading ? '—' : value}</strong>
      {hint && <em>{hint}</em>}
    </span>
    {to && <ArrowUpRight className="dash-stat-arrow" size={16} aria-hidden="true" />}
  </>;
  const className = `dash-stat dash-stat-${tone}${active ? ' is-active' : ''}`;
  if (to) return <Link className={className} to={to}>{body}</Link>;
  if (onClick) return <button type="button" className={className} onClick={onClick} aria-pressed={active}>{body}</button>;
  return <div className={className}>{body}</div>;
}

/** Small SVG area chart for a short series ([{ label, count }]). */
export function TrendChart({ data = [], valueKey = 'count', labelKey = 'label', height = 120, label = 'Trend' }) {
  const gradientId = useId().replace(/:/g, '');
  if (!data.length) return null;
  const values = data.map(item => Number(item[valueKey]) || 0);
  const max = Math.max(...values, 1);
  const width = 100;
  const step = data.length > 1 ? width / (data.length - 1) : width;
  const points = values.map((value, index) => [index * step, height - 8 - (value / max) * (height - 24)]);
  const line = points.map(([x, y], index) => `${index ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
  const total = values.reduce((sum, value) => sum + value, 0);
  return (
    <figure className="dash-trend" aria-label={`${label}: ${total} in total`}>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-hidden="true">
        <defs><linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="var(--rh-sky)" stopOpacity=".45" /><stop offset="100%" stopColor="var(--rh-sky)" stopOpacity="0" /></linearGradient></defs>
        <path d={`${line} L${width},${height} L0,${height} Z`} fill={`url(#${gradientId})`} />
        <path d={line} fill="none" stroke="var(--rh-blue)" strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <div className="dash-trend-points">
        {data.map((item, index) => <span key={item[labelKey] || index} title={`${item[labelKey]}: ${values[index]}`}><i style={{ height: `${Math.max(4, (values[index] / max) * 100)}%` }} /></span>)}
      </div>
      {data.length > 1 && <figcaption><span>{data[0][labelKey]}</span><span>{data[data.length - 1][labelKey]}</span></figcaption>}
    </figure>
  );
}

/** Pill tabs. tabs: [{ id, label, count? }] */
export function Tabs({ tabs, value, onChange, label = 'Sections' }) {
  return (
    <div className="dash-tabs" role="tablist" aria-label={label}>
      {tabs.map(tab => (
        <button key={tab.id} type="button" role="tab" aria-selected={value === tab.id} className={value === tab.id ? 'is-active' : ''} onClick={() => onChange(tab.id)}>
          {tab.label}{tab.count !== undefined && tab.count !== null && <span>{tab.count}</span>}
        </button>
      ))}
    </div>
  );
}

/** Side panel for viewing/editing one record without leaving the list. */
export function Drawer({ open, title, subtitle, onClose, children, footer, width = 520 }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog ref={ref} className="dash-drawer" style={{ '--dash-drawer-width': `${width}px` }} aria-label={title} onClose={onClose} onCancel={onClose}
      onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
      {open && <div className="dash-drawer-panel">
        <header>
          <div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
          <button type="button" className="dash-icon-button" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </header>
        <div className="dash-drawer-body">{children}</div>
        {footer && <footer>{footer}</footer>}
      </div>}
    </dialog>
  );
}

/** Horizontal progress meter with label, e.g. content health. */
export function Meter({ label, value, total, to, tone = 'blue' }) {
  const percent = total ? Math.round((value / total) * 100) : 0;
  const body = <><span className="dash-meter-label">{label}<strong>{value}</strong></span><i className={`dash-meter-track dash-meter-${tone}`}><b style={{ width: `${percent}%` }} /></i></>;
  return to ? <Link className="dash-meter" to={to}>{body}</Link> : <div className="dash-meter">{body}</div>;
}
