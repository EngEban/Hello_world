import { ArrowUp, Bookmark, BookmarkCheck, CalendarDays, ChevronDown, ChevronRight, Clock3, Copy, Download, ListTree, Printer, RefreshCw, Share2, ShieldCheck, Tag } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import ContributorCard, { ContributorAvatar } from './ContributorCard';
import ResourceCard from './ResourceCard';
import { useSiteSettings } from '../../contexts/SiteSettingsContext';
import { publicationReadingStyle } from '../../config/contentDesign';
import { articlePath, cleanSeoText, formatArticleDate, plainText, prepareArticleContent } from '../../utils/articleContent';
import { usePageMeta } from '../../utils/seo';
import '../../styles/pages/publication.css';

const savedKey = 'resref_saved_posts';
function savedPosts() {
  try { const value = JSON.parse(localStorage.getItem(savedKey) || '[]'); return Array.isArray(value) ? value : []; } catch { return []; }
}
function Contents({ items, activeId, onSelect }) {
  return <nav aria-label="Article contents"><ol>{items.map(heading => <li className={`publication-toc-${heading.level}`} key={heading.id}><a href={`#${heading.id}`} onClick={() => onSelect(heading.id)} aria-current={activeId === heading.id ? 'location' : undefined}>{heading.text}</a></li>)}</ol></nav>;
}
export default function ArticleReader({ item, related }) {
  const settings = useSiteSettings();
  const title = plainText(item.title);
  const excerpt = plainText(item.excerpt);
  const category = item.categories?.[0];
  const canonical = new URL(articlePath(item), window.location.origin).href;
  const authors = item.authors || [];
  const visibleAuthors = item.design_settings?.author_section_enabled === 'auto' ? authors : [];
  const byline = authors.filter(author => !author.role_label || ['author', 'co_author'].includes(author.role));
  const reviewers = authors.filter(author => author.role_label && author.role === 'reviewer');
  const content = useMemo(() => prepareArticleContent(item.content, { excludeLegacyAuthorship: authors.length > 0 }), [item.content, authors.length]);
  const readingStyle = publicationReadingStyle({ ...item, design_settings: { content_width: 750, text_color: '#29394d', ...item.design_settings } });
  const [activeId, setActiveId] = useState('');
  const [saved, setSaved] = useState(() => savedPosts().includes(item.slug));
  const [feedback, setFeedback] = useState('');
  const bodyRef = useRef(null);
  const mobileToc = useRef(null);
  const progressRef = useRef(null);
  const updated = item.updated_at && item.published_at && new Date(item.updated_at).toDateString() !== new Date(item.published_at).toDateString();
  const meta = useMemo(() => ({
    title: `${cleanSeoText(item.seo_title) || title} | ResRef`,
    description: (cleanSeoText(item.seo_description) || excerpt).slice(0, 300), canonical, image: item.featured_image, type: 'article',
    structuredData: [{ '@context': 'https://schema.org', '@type': 'Article', headline: title,
      description: excerpt, mainEntityOfPage: canonical, url: canonical,
      ...(item.published_at ? { datePublished: item.published_at } : {}),
      ...(item.updated_at ? { dateModified: item.updated_at } : {}),
      ...(item.featured_image ? { image: [item.featured_image] } : {}),
      author: byline.map(author => ({ '@type': 'Person', name: plainText(author.display_name), ...(author.slug ? { url: new URL(`/authors/${author.slug}`, canonical).href } : {}) })),
      publisher: { '@type': 'Organization', name: 'ResRef' }, articleSection: category?.name,
    }, { '@context': 'https://schema.org', '@type': 'BreadcrumbList', itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Database', item: new URL('/database', canonical).href },
      ...(category ? [{ '@type': 'ListItem', position: 2, name: category.name, item: new URL(`/database/${category.slug}`, canonical).href }] : []),
      { '@type': 'ListItem', position: category ? 3 : 2, name: title, item: canonical },
    ] }],
  }), [item, canonical, title, excerpt]);
  usePageMeta(meta);
  useEffect(() => {
    const headings = bodyRef.current?.querySelectorAll('h2[id],h3[id],h4[id]') || [];
    let frame;
    const updateActiveHeading = () => {
      const body = bodyRef.current;
      if (body && progressRef.current) {
        const rect = body.getBoundingClientRect();
        const total = Math.max(1, rect.height - window.innerHeight * .6);
        progressRef.current.style.transform = `scaleX(${Math.min(1, Math.max(0, -rect.top / total))})`;
      }
      let current = headings[0]?.id || '';
      for (const heading of headings) {
        if (heading.getBoundingClientRect().top > 145) break;
        current = heading.id;
      }
      setActiveId(previous => previous === current ? previous : current);
    };
    const onScroll = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(updateActiveHeading); };
    window.addEventListener('scroll', onScroll, { passive: true });
    if (window.location.hash) {
      try { document.getElementById(decodeURIComponent(window.location.hash.slice(1)))?.scrollIntoView(); } catch { /* Keep malformed fragments harmless. */ }
    }
    updateActiveHeading();
    return () => { cancelAnimationFrame(frame); window.removeEventListener('scroll', onScroll); };
  }, [content]);
  const copyLink = async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(canonical);
      else {
        const text = document.createElement('textarea'); text.value = canonical; text.style.position = 'fixed'; text.style.opacity = '0';
        document.body.appendChild(text); text.select(); const success = document.execCommand('copy'); text.remove();
        if (!success) throw new Error('Clipboard unavailable');
      }
      setFeedback('Article link copied.');
    } catch { setFeedback(`Copy this link: ${canonical}`); }
  };
  const toggleSave = () => {
    try { const values = new Set(savedPosts()); if (values.has(item.slug)) values.delete(item.slug); else values.add(item.slug);
      localStorage.setItem(savedKey, JSON.stringify([...values])); setSaved(values.has(item.slug));
      setFeedback(values.has(item.slug) ? 'Saved on this device.' : 'Removed from saved articles.');
    } catch { setFeedback('This browser could not save the article.'); }
  };
  const share = async () => {
    if (!navigator.share) return copyLink();
    try { await navigator.share({ title, text: excerpt, url: canonical }); } catch (error) { if (error.name !== 'AbortError') setFeedback('Sharing is unavailable. Use Copy link instead.'); }
  };
  return <div className="publication-page rp-article">
    <div className="rp-article-progress" aria-hidden="true"><span ref={progressRef} /></div>
    <article>
      <header className="rp-article-hero">
        <div className="publication-container rp-article-hero-inner">
          <nav className="publication-breadcrumbs" aria-label="Breadcrumb"><Link to="/database">Database</Link><ChevronRight size={13} aria-hidden="true" />{category && <><Link to={`/database/${category.slug}`}>{plainText(category.name)}</Link><ChevronRight size={13} aria-hidden="true" /></>}<span aria-current="page">Article</span></nav>
          <div className="publication-header">
            {category && <Link className="publication-topic" to={`/database/${category.slug}`}>{plainText(category.name)}</Link>}
            <h1 dir="auto">{title}</h1>
            {excerpt && <p className="publication-deck" dir="auto">{excerpt}</p>}
            {byline.length > 0 && <div className="publication-byline">{byline.map((author, index) => <div key={`${author.id}-${index}`}><ContributorAvatar author={author} /><span>{author.slug ? <Link to={`/authors/${author.slug}`}>{[author.prefix, plainText(author.display_name)].filter(Boolean).join(' ')}</Link> : plainText(author.display_name)}{author.credentials && `, ${plainText(author.credentials)}`}<small>{[author.position, author.institution].filter(Boolean).join(' · ') || author.role_label || 'Author'}</small></span></div>)}</div>}
            {reviewers.length > 0 && <p className="publication-reviewers"><ShieldCheck size={15} aria-hidden="true" />Reviewed by {reviewers.map(author => [author.display_name, author.credentials].filter(Boolean).join(', ')).join(' · ')}</p>}
            <div className="publication-utility-row"><div className="publication-dates">{item.published_at && <span><CalendarDays size={15} aria-hidden="true" />Published <time dateTime={item.published_at}>{formatArticleDate(item.published_at)}</time></span>}{updated && <span><RefreshCw size={14} aria-hidden="true" />Updated <time dateTime={item.updated_at}>{formatArticleDate(item.updated_at)}</time></span>}<span><Clock3 size={15} aria-hidden="true" />{item.read_minutes || 1} min read</span></div>
              <div className="publication-tools" aria-label="Reading tools"><button type="button" onClick={toggleSave} aria-pressed={saved}>{saved ? <BookmarkCheck size={17} /> : <Bookmark size={17} />}{saved ? 'Saved' : 'Save'}</button><button type="button" onClick={copyLink}><Copy size={16} />Copy link</button><button type="button" onClick={share}><Share2 size={16} />Share</button><button type="button" onClick={() => window.print()}><Printer size={17} />Print</button></div>
            </div><p className="publication-feedback" role="status" aria-live="polite">{feedback}</p>
          </div>
        </div>
      </header>
      <div className="publication-container">
        <div className={`publication-reading-layout ${content.toc.length ? '' : 'publication-without-toc'}`}>
          {content.toc.length > 0 && <aside className="publication-rail"><div className="publication-sticky-toc"><h2><ListTree size={17} aria-hidden="true" />{settings.article_toc_title || 'On this page'}</h2><Contents items={content.toc} activeId={activeId} onSelect={setActiveId} /><a className="publication-back-top" href="#public-content"><ArrowUp size={14} aria-hidden="true" />Back to top</a></div></aside>}
          <div className="publication-reading-column">
            {content.toc.length > 0 && <details ref={mobileToc} className="publication-mobile-toc"><summary><ListTree size={17} aria-hidden="true" />{settings.article_toc_title || 'On this page'}<ChevronDown className="publication-mobile-toc-chevron" size={17} aria-hidden="true" /></summary><Contents items={content.toc} activeId={activeId} onSelect={id => { setActiveId(id); if (mobileToc.current) mobileToc.current.open = false; }} /></details>}
            {item.featured_image && <figure className="publication-hero"><img src={item.featured_image} alt="" fetchpriority="high" decoding="async" onError={event => { event.currentTarget.parentElement.hidden = true; }} /></figure>}
            <div className="publication-body" style={readingStyle} ref={bodyRef} dangerouslySetInnerHTML={{ __html: content.html }} />
            {item.pdf_url && <aside className="publication-download"><span className="publication-download-icon"><Download size={22} aria-hidden="true" /></span><div><h2>{item.pdf_title || 'Downloadable resource'}</h2><p>{settings.article_download_text || 'PDF for offline reading and reference.'}</p></div><a href={item.pdf_url} target="_blank" rel="noopener noreferrer" download>Download PDF <Download size={16} /></a></aside>}
            {item.tags?.length > 0 && <nav className="publication-tags" aria-label="Article topics"><Tag size={15} aria-hidden="true" />{item.tags.map(tag => <Link to={`/database?tag=${encodeURIComponent(tag.slug)}`} key={tag.id}>{plainText(tag.name)}</Link>)}</nav>}
            {visibleAuthors.length > 0 && <section className="publication-contributors" aria-labelledby="publication-contributors-title">{item.design_settings?.author_section_label && <p className="publication-card-topic">{item.design_settings.author_section_label}</p>}<h2 id="publication-contributors-title">{item.design_settings?.author_section_title || 'Authors and contributors'}</h2>{item.design_settings?.author_section_intro && <p>{plainText(item.design_settings.author_section_intro)}</p>}{visibleAuthors.map((author, index) => <ContributorCard author={author} key={`${author.id}-${index}`} />)}</section>}
          </div>
        </div>
      </div>
    </article>
    {related.length > 0 && <section className="publication-related" aria-labelledby="publication-related-title"><div className="publication-container"><div className="publication-section-heading"><div><p className="rh-label">Continue exploring</p><h2 id="publication-related-title">{settings.article_related_title || 'Related reading'}</h2></div>{category && <Link className="rh-button rh-button-outline" to={`/database/${category.slug}`}>All in {plainText(category.name)} <ChevronRight size={16} /></Link>}</div><div className="rp-card-grid publication-card-grid">{related.map(post => <ResourceCard post={post} variant="publication" key={post.id} />)}</div></div></section>}
  </div>;
}
