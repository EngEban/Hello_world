import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import '../../styles/pages/resource-card.css';

// Page numbers to show around the current page: 1 … 4 5 6 … 12
function pageWindow(current, total) {
  const pages = new Set([1, total, current - 1, current, current + 1]);
  const list = [...pages].filter(page => page >= 1 && page <= total).sort((a, b) => a - b);
  return list.flatMap((page, index) => (index && page - list[index - 1] > 1 ? ['gap', page] : [page]));
}

// Previous/next pager for public listings. `onPage(n)` usually writes ?page=n
// to the URL so the page is shareable and the back button works. Pass
// `hrefFor(n)` instead to render real links (e.g. the database listing).
export default function PublicPagination({ pagination, onPage, hrefFor, label = 'Results pages', className = '' }) {
  if (!pagination || pagination.total_pages <= 1) return null;
  const { current_page: current, total_pages: total } = pagination;
  const step = (enabled, page, children) => {
    if (hrefFor) return enabled ? <Link className="rp-pager-step" to={hrefFor(page)}>{children}</Link> : <span className="rp-pager-step is-disabled" aria-hidden="true">{children}</span>;
    return <button type="button" className="button button-outline rp-pager-step" disabled={!enabled} onClick={() => onPage(page)}>{children}</button>;
  };
  return (
    <nav className={`public-pagination rp-pager ${className}`.trim()} aria-label={label}>
      {step(pagination.has_previous, current - 1, <><ChevronLeft size={16} aria-hidden="true" /> Previous</>)}
      <span className="rp-pager-pages">
        {pageWindow(current, total).map((page, index) => {
          if (page === 'gap') return <span className="rp-pager-gap" aria-hidden="true" key={`gap-${index}`}>…</span>;
          const props = { className: `rp-pager-number${page === current ? ' is-current' : ''}`, 'aria-current': page === current ? 'page' : undefined, 'aria-label': `Page ${page}` };
          return hrefFor
            ? <Link key={page} to={hrefFor(page)} {...props}>{page}</Link>
            : <button type="button" key={page} {...props} onClick={() => page !== current && onPage(page)}>{page}</button>;
        })}
      </span>
      <span className="rp-pager-status" aria-live="polite">Page {current} of {total}</span>
      {step(pagination.has_next, current + 1, <>Next <ChevronRight size={16} aria-hidden="true" /></>)}
    </nav>
  );
}
