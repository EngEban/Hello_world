export default function AdminPagination({ pagination, onPage }) {
  if (!pagination || pagination.total_pages <= 1) return null;
  return <div className="admin-pagination">
    <button type="button" disabled={!pagination.has_previous} onClick={() => onPage(pagination.current_page - 1)}>Previous</button>
    <span>Page {pagination.current_page} of {pagination.total_pages} · {pagination.total_items} items</span>
    <button type="button" disabled={!pagination.has_next} onClick={() => onPage(pagination.current_page + 1)}>Next</button>
  </div>;
}
