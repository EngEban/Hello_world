import { Navigate, useLocation } from 'react-router-dom';
import LoadingState from '../common/LoadingState';
import { useAccount } from '../../contexts/AccountContext';

/** Gate server-backed platform tools behind the authenticated account session. */
export default function RequireAccount({ children }) {
  const { account, loading } = useAccount();
  const location = useLocation();
  if (loading) return <section className="section"><div className="site-container"><LoadingState /></div></section>;
  if (!account) {
    const next = `${location.pathname}${location.search || ''}`;
    return <Navigate to={`/sign-in?next=${encodeURIComponent(next)}`} replace state={{ from: location }} />;
  }
  return children;
}
