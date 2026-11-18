import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { safeHref } from '../../utils/safeHref';
import { optimizedImageUrl } from '../../utils/optimizedImages';

export function HomeLink({ to: rawTo, variant = 'primary', className = '', children }) {
  const to = safeHref(rawTo, '/');
  const isExternal = /^(https?:)?\/\//.test(to) || to?.startsWith('mailto:') || to?.startsWith('tel:');
  const classNames = `rh-button rh-button-${variant} ${className}`.trim();
  const content = <><span>{children}</span><ArrowRight className="rh-button-icon" size={17} aria-hidden="true" /></>;
  if (isExternal) {
    return <a className={classNames} href={to} target={to?.startsWith('http') ? '_blank' : undefined} rel={to?.startsWith('http') ? 'noopener noreferrer' : undefined}>{content}</a>;
  }
  return <Link className={classNames} to={to}>{content}</Link>;
}

export function SectionIntro({ id, label, title, text, align = 'left', children }) {
  return <header className={`rh-intro rh-intro-${align}`} data-reveal>
    <span className="rh-label">{label}</span>
    <h2 id={id}>{title}</h2>
    {text && <p>{text}</p>}
    {children}
  </header>;
}

export function PreviewState({ state, onRetry, loading, error }) {
  if (state.status === 'ready') return null;
  return <div className={`rh-preview-state ${state.status === 'loading' ? 'is-loading' : ''}`} role="status"><p>{state.status === 'loading' ? loading : error}</p>{state.status === 'error' && <button type="button" onClick={onRetry}>Try again</button>}</div>;
}

export function ArticlePreview({ post, categoryLabel, categorySlug }) {
  const [failed, setFailed] = useState(false);
  const category = post.categories?.[0];
  const href = `/database/${categorySlug || category?.slug || 'research'}/${post.slug}`;
  return <article className="rh-article" data-reveal>
    <Link className="rh-article-image" to={href} tabIndex={-1} aria-hidden="true">
      {post.featured_image && !failed
        ? <img src={optimizedImageUrl(post.featured_image, true)} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)} />
        : <span className="rh-article-placeholder">ResRef<small>Research library</small></span>}
    </Link>
    <div className="rh-article-body">
      <span className="rh-chip">{categoryLabel || category?.name || 'Research'}</span>
      <h3><Link to={href}>{post.title}</Link></h3>
      {post.excerpt && <p>{post.excerpt}</p>}
      <div className="rh-article-footer">
        {post.read_minutes ? <span className="rh-meta">{post.read_minutes} min read</span> : <span />}
        <HomeLink to={href} variant="text">Read article</HomeLink>
      </div>
    </div>
  </article>;
}

/**
 * Adds `is-revealed` to `[data-reveal]` elements as they scroll into view.
 * Elements are only hidden once this runs (class `rh-motion` on the root), so
 * content stays visible without JavaScript; reduced-motion users get no motion.
 */
export function useReveal(deps = []) {
  const ref = useRef(null);
  useEffect(() => {
    const root = ref.current;
    if (!root) return undefined;
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const pending = () => [...root.querySelectorAll('[data-reveal]:not(.is-revealed)')];
    if (reduced || typeof IntersectionObserver === 'undefined') {
      pending().forEach(node => node.classList.add('is-revealed'));
      return undefined;
    }
    root.classList.add('rh-motion');
    const revealed = new WeakSet();
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-revealed');
          revealed.add(entry.target);
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -6% 0px', threshold: 0 });
    pending().forEach(node => observer.observe(node));
    // Content that loads later (API results, tabs) is picked up as it appears.
    // React drops `is-revealed` when it rewrites a className (a card becoming
    // selected), so anything already revealed gets it back before the next paint.
    const mutations = typeof MutationObserver === 'undefined' ? null : new MutationObserver(() => pending().forEach(node => {
      if (revealed.has(node)) node.classList.add('is-revealed');
      else observer.observe(node);
    }));
    mutations?.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
    return () => { observer.disconnect(); mutations?.disconnect(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return ref;
}
