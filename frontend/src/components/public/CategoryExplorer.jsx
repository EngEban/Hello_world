import { ArrowRight, ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { plainText } from '../../utils/articleContent';

const articleCount = item => item.count || item.post_count || 0;

/** Every published category: the main one first, then the rest as an index, in the dashboard's order. */
export default function CategoryExplorer({ categories, featuredSlug, featuredText, hrefFor }) {
  const [expanded, setExpanded] = useState(false);
  const featured = categories.find(item => item.slug === featuredSlug);
  const specialties = categories.filter(item => item.slug !== featuredSlug);
  if (!categories.length) return null;

  return <div className="rp-cx">
    {featured && <div className="rp-cx-featured">
      <div className="rp-cx-featured-main">
        <span className="rp-cx-kicker">Start here</span>
        <h2><Link to={hrefFor(featured)}>{plainText(featured.name)}<ArrowRight size={20} aria-hidden="true" /></Link></h2>
        <p>{plainText(featured.description) || featuredText}</p>
        {articleCount(featured) > 0 && <small>{articleCount(featured)} {articleCount(featured) === 1 ? 'article' : 'articles'}</small>}
      </div>
      {featured.children?.length > 0 && <ul aria-label={`${plainText(featured.name)} topics`}>
        {featured.children.map(item => <li key={item.id}><Link to={hrefFor(item)}><span>{plainText(item.name)}</span>{articleCount(item) > 0 && <small>{articleCount(item)}</small>}</Link></li>)}
      </ul>}
    </div>}

    {specialties.length > 0 && <>
      <div className="rp-cx-head"><h2>Browse by specialty</h2><span>{specialties.length} {specialties.length === 1 ? 'specialty' : 'specialties'}</span></div>
      <ul className={`rp-cx-index${expanded ? '' : ' is-collapsed'}`}>
        {specialties.map(item => <li key={item.id}>
          <Link className="rp-cx-parent" to={hrefFor(item)}><span>{plainText(item.name)}</span><i aria-hidden="true" />{articleCount(item) > 0 && <small>{articleCount(item)}</small>}</Link>
        </li>)}
      </ul>
      {specialties.length > 6 && <button type="button" className="rp-cx-more" aria-expanded={expanded} onClick={() => setExpanded(open => !open)}>{expanded ? 'Show fewer specialties' : `Show all ${specialties.length} specialties`}<ChevronDown size={16} aria-hidden="true" /></button>}
    </>}
  </div>;
}
