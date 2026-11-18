import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';
import { PublicWebsiteApi } from '../../api/publicWebsiteApi';
import ManagedContentPage from '../../components/public/ManagedContentPage';
import { plainText } from '../../utils/articleContent';
import '../../styles/pages/publication.css';
import { usePageMeta } from '../../utils/seo';

export default function StaticContentPage() {
  const { slug } = useParams();
  const [page, setPage] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true; setPage(null); setError('');
    PublicWebsiteApi.getPageBySlug(slug).then(data => { if (active) setPage(data.page); }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [slug]);
  const meta = useMemo(() => page ? { title: `${plainText(page.seo_title || page.title)} | ResRef`, description: plainText(page.seo_description || page.excerpt) } : null, [page]);
  usePageMeta(meta);
  if (error) return <div className="publication-page"><div className="publication-container rp-reader-state"><div className="publication-empty" role="alert"><span className="rp-state-icon"><AlertTriangle size={26} aria-hidden="true" /></span><h1>Page unavailable</h1><p>{error}</p><div className="publication-empty-actions"><Link className="button" to="/">Back to Home</Link></div></div></div></div>;
  if (!page) return <div className="publication-page"><div className="publication-container rp-reader-skeleton" role="status" aria-label="Loading..."><span /><span /><span /><div className="rp-reader-skeleton-lines" aria-hidden="true"><span /><span /><span /><span /><span /></div><span className="rh-visually-hidden">Loading...</span></div></div>;
  return <ManagedContentPage item={page} />;
}
