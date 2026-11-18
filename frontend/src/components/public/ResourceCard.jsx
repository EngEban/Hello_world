import { Link } from 'react-router-dom';
import { ArrowRight, BookOpen, CalendarDays, Clock3 } from 'lucide-react';
import { useState } from 'react';
import { slugifyCategory } from '../../config/contentStructure';
import { formatArticleDate, plainText } from '../../utils/articleContent';
import { optimizedImageUrl } from '../../utils/optimizedImages';
import '../../styles/pages/resource-card.css';

/**
 * Article card used by the database, Learn, questionnaires, author and related lists.
 * `variant="publication"` is the library card, `variant="feature"` the wide highlighted
 * card, and the default variant the resource card that also lists tags.
 */
export default function ResourceCard({ post, variant }) {
  const [imageFailed, setImageFailed] = useState(false);
  const category = post.categories?.[0];
  const categorySlug = category?.slug || (category?.name ? slugifyCategory(category.name) : 'research');
  const tags = post.tags?.slice(0, 2) || [];
  const hasImage = Boolean(post.featured_image) && !imageFailed;
  const href = `/database/${categorySlug}/${post.slug}`;
  const title = plainText(post.title);
  const topic = plainText(category?.name || 'Research');

  const media = (label, alt) => <Link className={`rp-card-media${hasImage ? '' : ' is-placeholder'}`} to={href} aria-label={label} tabIndex={-1}>
    {hasImage
      ? <img src={optimizedImageUrl(post.featured_image, true)} alt={alt} loading="lazy" decoding="async" onError={() => setImageFailed(true)} />
      : <span className="rp-card-placeholder" aria-hidden="true"><BookOpen size={26} /><span>ResRef</span></span>}
  </Link>;

  if (variant === 'publication' || variant === 'feature') return <article className={`rp-card rp-card-${variant}`}>
    {media(`Read ${title}`, '')}
    <div className="rp-card-body">
      <p className="rp-card-topic"><span className="rh-chip">{topic}</span></p>
      <h3 dir="auto"><Link to={href}>{title}</Link></h3>
      {post.excerpt && <p className="rp-card-excerpt" dir="auto">{plainText(post.excerpt)}</p>}
      <div className="rp-card-meta">
        <span><Clock3 size={14} aria-hidden="true" />{post.read_minutes || 1} min read</span>
        {post.published_at && <span><CalendarDays size={14} aria-hidden="true" /><time dateTime={post.published_at}>{formatArticleDate(post.published_at)}</time></span>}
      </div>
      <Link className="rp-card-read" to={href}>Read article <ArrowRight size={16} aria-hidden="true" /></Link>
    </div>
  </article>;

  return (
    <article className="rp-card rp-card-resource">
      {media(`Open ${post.title}`, post.title)}
      <div className="rp-card-body">
        <header className="rp-card-head">
          <small className="rh-chip">{category?.name || 'Research'}</small>
          <span><Clock3 size={13} aria-hidden="true" /> {post.read_minutes || 1} min</span>
        </header>
        <h3 dir="auto"><Link to={href}>{post.title}</Link></h3>
        <p className="rp-card-excerpt" dir="auto">{post.excerpt || 'Open this resource to learn more.'}</p>
        <footer className="rp-card-foot">
          <span dir="auto">{tags.length ? tags.map(tag => tag.name).join(' / ') : 'Research resource'}</span>
          <Link to={href}>Read <ArrowRight size={14} aria-hidden="true" /></Link>
        </footer>
      </div>
    </article>
  );
}
