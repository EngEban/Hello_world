import { useMemo } from 'react';
import PageHero from './PageHero';
import { plainText, prepareArticleContent } from '../../utils/articleContent';
import { publicationReadingStyle } from '../../config/contentDesign';
import '../../styles/pages/publication.css';

// CMS pages (e.g. /page/:slug): brand page header, then the content on a raised reading panel.
export default function ManagedContentPage({ item }) {
  const content = useMemo(() => prepareArticleContent(item.content), [item.content]);
  const title = plainText(item.title);
  return <div className="publication-page rp-managed">
    <PageHero title={title} text={item.excerpt ? plainText(item.excerpt) : ''} breadcrumb={[[title]]} />
    <div className="publication-container">
      <article className="publication-reading-column rp-managed-panel rh-hero-follow" style={{ marginInline: 'auto' }}>
        {item.featured_image && <figure className="publication-hero"><img src={item.featured_image} alt="" decoding="async" /></figure>}
        <div className="publication-body" style={publicationReadingStyle(item)} dangerouslySetInnerHTML={{ __html: content.html }} />
      </article>
    </div>
  </div>;
}
