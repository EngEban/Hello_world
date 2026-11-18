import '../../styles/pages/loading-state.css';

// Small, neutral loading indicator used on public pages and inside the dashboard.
export default function LoadingState({ label = 'Loading...' }) {
  return <p className="muted rr-loading-state" role="status" aria-live="polite"><span className="rr-loading-spinner" aria-hidden="true" />{label}</p>;
}
