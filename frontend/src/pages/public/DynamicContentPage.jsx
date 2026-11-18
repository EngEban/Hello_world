import ManagedContentPage from '../../components/public/ManagedContentPage';
import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AlertTriangle, ArrowRight, FileQuestion } from 'lucide-react';
import { PublicWebsiteApi } from '../../api/publicWebsiteApi';
import ArticleReader from '../../components/public/ArticleReader';
import { usePageMeta } from '../../utils/seo';

export default function DynamicContentPage() {
  const { slug } = useParams();
  const [item, setItem] = useState(null);
  const [related, setRelated] = useState([]);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const meta = useMemo(() => item?.content_kind === 'page' ? { title: `${item.seo_title || item.title} | ResRef`, description: item.seo_description || item.excerpt } : null, [item]);
  usePageMeta(meta);
  useEffect(() => {
    let active = true; setItem(null); setRelated([]); setError(null);
    async function load() {
      try {
        let data;
        try { data = await PublicWebsiteApi.getPostBySlug(slug); }
        catch (err) { if (err.status !== 404) throw err; data = await PublicWebsiteApi.getPageBySlug(slug); }
        if (active) { setItem({ ...(data.post || data.page), content_kind: data.post ? 'post' : 'page' }); setRelated(data.related_posts || []); }
      } catch (err) { if (active) setError(err); }
    }
    load(); return () => { active = false; };
  }, [slug, attempt]);
  if (error) return <div className="publication-page"><div className="publication-container rp-reader-state"><div className="publication-empty" role="alert"><span className="rp-state-icon">{error.status === 404 ? <FileQuestion size={26} aria-hidden="true" /> : <AlertTriangle size={26} aria-hidden="true" />}</span><h1>{error.status === 404 ? 'Article not found' : 'Unable to load this article'}</h1><p>{error.status === 404 ? 'This article may be unpublished or its address may have changed.' : error.message}</p><div className="publication-empty-actions"><button className="button" onClick={() => setAttempt(value => value + 1)}>Try again</button> <Link className="rh-button rh-button-text" to="/database"><span>Browse the database</span> <ArrowRight size={15} aria-hidden="true" /></Link></div></div></div></div>;
  if (!item) return <div className="publication-page"><div className="publication-container rp-reader-skeleton" role="status" aria-label="Loading article…"><span /><span /><span /><div className="rp-reader-skeleton-lines" aria-hidden="true"><span /><span /><span /><span /><span /><span /></div><span className="rh-visually-hidden">Loading article…</span></div></div>;
  if (item.content_kind === 'post') return <ArticleReader key={item.slug} item={item} related={related} />;
  return <ManagedContentPage item={item} />;
}
