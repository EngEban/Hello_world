import { isRouteErrorResponse, Link, useRouteError } from 'react-router-dom';
import { ArrowRight, Compass, RefreshCw, TriangleAlert } from 'lucide-react';
import '../../styles/pages/route-error.css';

const RELOAD_FLAG = 'resref_chunk_reload_at';

// After a deploy, an open tab still references the old hashed chunk files,
// which no longer exist. The browser reports that with one of these messages.
function isChunkLoadError(error) {
  const message = String(error?.message || error || '');
  return /dynamically imported module|Importing a module script failed|error loading dynamically imported module|ChunkLoadError|Loading chunk \d+ failed/i.test(message);
}

function reloadOnce() {
  try {
    const last = Number(sessionStorage.getItem(RELOAD_FLAG) || 0);
    if (Date.now() - last < 30000) return false; // already tried: avoid a reload loop
    sessionStorage.setItem(RELOAD_FLAG, String(Date.now()));
  } catch {
    // Storage blocked: still reload once; the browser keeps us out of a loop
    // because a fresh page load fetches the new chunk names.
  }
  window.location.reload();
  return true;
}

export default function RouteErrorBoundary() {
  const error = useRouteError();

  if (isChunkLoadError(error) && reloadOnce()) {
    return null;
  }

  const notFound = isRouteErrorResponse(error) && error.status === 404;
  if (!notFound && import.meta.env.DEV) console.error(error);

  const Icon = notFound ? Compass : TriangleAlert;

  // A <div>, not <main>: inside the public layout this renders within its
  // <main id="public-content">, and nested main landmarks confuse screen readers.
  return (
    <div className="route-error rh-tokens rp-route-error" role="alert">
      <div className="route-error-card rp-route-error-card">
        <span className="rp-route-error-icon" aria-hidden="true"><Icon size={28} /></span>
        <span className="route-error-eyebrow">{notFound ? '404' : 'Something went wrong'}</span>
        <h1>{notFound ? 'Page not found' : 'This page could not be displayed'}</h1>
        <p>
          {notFound
            ? 'The link may be outdated or the page may have moved.'
            : 'A new version of ResRef may have been released, or the connection was interrupted. Reloading usually fixes it.'}
        </p>
        <div className="route-error-actions">
          {!notFound && <button type="button" className="button rp-route-error-primary" onClick={() => window.location.reload()}><RefreshCw size={16} aria-hidden="true" /> Reload page</button>}
          <Link className={notFound ? 'button rp-route-error-primary' : 'button button-outline rp-route-error-secondary'} to="/">Go to the homepage <ArrowRight size={16} aria-hidden="true" /></Link>
        </div>
      </div>
    </div>
  );
}
