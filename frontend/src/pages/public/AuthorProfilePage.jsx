import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AlertTriangle, ArrowRight, BookOpenText, ChevronRight, ChevronDown, UserRound } from 'lucide-react';
import { PublicWebsiteApi } from '../../api/publicWebsiteApi';
import ContributorCard from '../../components/public/ContributorCard';
import ResourceCard from '../../components/public/ResourceCard';
import { cleanSeoText, plainText } from '../../utils/articleContent';
import { usePageMeta } from '../../utils/seo';
import '../../styles/pages/publication.css';
import '../../styles/pages/author-profile.css';

export default function AuthorProfilePage() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [visibleCount, setVisibleCount] = useState(12);
  useEffect(() => {
    let active = true; setData(null); setError(''); setVisibleCount(12);
    PublicWebsiteApi.getAuthorBySlug(slug).then(result => { if (active) setData(result); })
      .catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [slug, attempt]);
  const meta = useMemo(() => data ? {
    title: `${cleanSeoText(data.author.seo_title) || plainText(data.author.display_name)} | Contributors | ResRef`,
    description: cleanSeoText(data.author.seo_description) || plainText(data.author.short_bio || data.author.bio),
    canonical: new URL(`/authors/${slug}`, window.location.origin).href,
    structuredData: { '@context': 'https://schema.org', '@type': 'ProfilePage', mainEntity: {
      '@type': 'Person', name: plainText(data.author.display_name), ...(data.author.avatar ? { image: data.author.avatar } : {}),
      jobTitle: data.author.position || undefined,
      ...(data.author.institution ? { affiliation: { '@type': 'Organization', name: data.author.institution } } : {}),
    } },
  } : null, [data, slug]);
  usePageMeta(meta);
  if (error) return <div className="publication-page"><div className="publication-container rp-reader-state"><div className="publication-empty" role="alert"><span className="rp-state-icon"><AlertTriangle size={26} aria-hidden="true" /></span><h1>Contributor unavailable</h1><p>{error}</p><div className="publication-empty-actions"><button className="publication-primary-button" onClick={() => setAttempt(value => value + 1)}>Try again</button> <Link className="rh-button rh-button-text" to="/database"><span>Browse articles</span> <ArrowRight size={15} aria-hidden="true" /></Link></div></div></div></div>;
  if (!data) return <div className="publication-page rp-author"><section className="rp-author-band" aria-hidden="true" /><div className="publication-container"><div className="rp-author-card rp-author-card-loading rh-hero-follow" role="status" aria-label="Loading contributor…"><span className="rp-author-skel-avatar" /><div><span /><span /><span /></div><span className="rh-visually-hidden">Loading contributor…</span></div></div></div>;
  const { author, contributions } = data;
  const roles = [...new Set(contributions.map(item => item.role_label).filter(Boolean))];
  return <div className="publication-page rp-author">
    <section className="rp-author-band">
      <div className="publication-container">
        <nav className="publication-breadcrumbs rp-author-crumbs" aria-label="Breadcrumb"><Link to="/database">Database</Link><ChevronRight size={13} aria-hidden="true" /><span>Contributors</span><ChevronRight size={13} aria-hidden="true" /><span aria-current="page">{plainText(author.display_name)}</span></nav>
        <span className="rh-label rh-label-light"><UserRound size={14} aria-hidden="true" />Contributor profile</span>
      </div>
    </section>
    <div className="publication-container">
      <header className="publication-author-header rp-author-card rh-hero-follow">
        <ContributorCard headingLevel="h1" author={{ ...author, short_bio: author.bio || author.short_bio }} />
        <dl className="rp-author-stats">
          <div><dt>Published contributions</dt><dd>{contributions.length}</dd></div>
          {roles.length > 0 && <div><dt>{roles.length === 1 ? 'Role' : 'Roles'}</dt><dd className="rp-author-roles">{roles.join(' · ')}</dd></div>}
        </dl>
      </header>
      <section className="rp-author-works" aria-labelledby="contributor-articles-title"><div className="publication-section-heading"><div><p className="rh-label">Library</p><h2 id="contributor-articles-title">Published contributions</h2></div><span>{contributions.length} {contributions.length === 1 ? 'article' : 'articles'}</span></div>
        {contributions.length ? <><div className="rp-card-grid publication-card-grid rp-author-grid">{contributions.slice(0, visibleCount).map(item => <div className="rp-author-item" key={item.post.id}><p className="publication-card-topic rp-author-role"><BookOpenText size={14} aria-hidden="true" />{item.role_label}</p><ResourceCard variant="publication" post={item.post} />{item.contribution_note && <p className="rp-author-note">{item.contribution_note}</p>}</div>)}</div>{visibleCount < contributions.length && <div className="publication-pagination rp-author-more"><span>Showing {visibleCount} of {contributions.length}</span><button className="publication-primary-button" onClick={() => setVisibleCount(value => value + 12)}>Show more articles <ChevronDown size={16} aria-hidden="true" /></button></div>}</> : <div className="publication-empty"><span className="rp-state-icon"><BookOpenText size={26} aria-hidden="true" /></span><p>No published contributions yet.</p><Link className="rh-button rh-button-outline" to="/database">Explore the database</Link></div>}
      </section>
    </div>
  </div>;
}
