export default function StatusBadge({ value = 'unknown' }) {
  const labels={publish:'Published',draft:'Draft',pending:'In review',scheduled:'Scheduled',private:'Private',trash:'Trash'};
  return <span className={`status-badge status-${String(value).replaceAll('_', '-')}`}>{labels[value] || String(value).replaceAll('_', ' ')}</span>;
}
