import { CalendarDays, Clock3, Download, Monitor, Smartphone, Tag, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { publicationReadingStyle } from '../../../config/contentDesign';
import { formatArticleDate, plainText, prepareArticleContent } from '../../../utils/articleContent';
import '../../../styles/pages/publication.css';
import { readMinutes } from './workspace';

const roleLabels = { author: 'Author', co_author: 'Co-author', editor: 'Editor', reviewer: 'Reviewer', translator: 'Translator', formatter: 'Formatter' };

/**
 * Renders the editor's current (unsaved) state with the public article styles,
 * so drafts and scheduled content can be checked before anyone else sees them.
 */
export default function ArticlePreview({ open, onClose, post, categories, tags, authors }) {
  const ref = useRef(null);
  const [device, setDevice] = useState('desktop');
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  const credits = (post?.contributors || []).map(credit => ({ ...credit, author: authors.find(item => Number(item.id) === Number(credit.contributor_id)) })).filter(credit => credit.author);
  const byline = credits.filter(credit => ['author', 'co_author'].includes(credit.role || 'author'));
  const category = categories.find(item => item.id === post?.categories?.[0]);
  const postTags = tags.filter(item => post?.tags?.includes(item.id));
  const content = useMemo(() => open && post ? prepareArticleContent(post.content || '', { excludeLegacyAuthorship: credits.length > 0 }) : { html: '' }, [open, post, credits.length]);
  const readingStyle = post ? publicationReadingStyle({ ...post, design_settings: { content_width: 750, text_color: '#29394d', ...post.design_settings } }) : {};
  const showCards = post?.design_settings?.author_section_enabled === 'auto' && credits.length > 0;

  return (
    <dialog ref={ref} className="dart-preview" aria-labelledby="dart-preview-heading" onClose={onClose} onCancel={onClose}>
      {open && post && <div className="dart-preview-panel">
        <header className="dart-preview-bar">
          <div>
            <strong id="dart-preview-heading">Preview</strong>
            <span>Includes unsaved changes · not visible to the public</span>
          </div>
          <div className="dart-preview-devices" role="group" aria-label="Preview width">
            <button type="button" aria-pressed={device === 'desktop'} onClick={() => setDevice('desktop')}><Monitor size={15} /> Desktop</button>
            <button type="button" aria-pressed={device === 'mobile'} onClick={() => setDevice('mobile')}><Smartphone size={15} /> Mobile</button>
          </div>
          <button type="button" className="dash-icon-button" onClick={onClose} aria-label="Close preview"><X size={18} /></button>
        </header>
        <div className="dart-preview-scroll">
          <div className={`dart-preview-frame is-${device}`}>
            <div className="publication-page rp-article">
              <header className="rp-article-hero">
                <div className="publication-container">
                  <div className="publication-header">
                    {post.post_type !== 'page' && category && <span className="publication-topic">{plainText(category.name)}</span>}
                    <h2 className="dart-preview-title" dir="auto">{plainText(post.title) || 'Untitled draft'}</h2>
                    {post.excerpt && <p className="publication-deck" dir="auto">{plainText(post.excerpt)}</p>}
                    {byline.length > 0 && <p className="dart-preview-byline">By {byline.map(credit => plainText(credit.author.display_name)).join(', ')}</p>}
                    <div className="publication-dates">
                      <span><CalendarDays size={15} aria-hidden="true" />{post.published_at ? formatArticleDate(post.published_at) : 'Publication date not set'}</span>
                      <span><Clock3 size={15} aria-hidden="true" />{readMinutes(post.content)} min read</span>
                    </div>
                  </div>
                </div>
              </header>
              <div className="publication-container">
                <div className="publication-reading-column dart-preview-column">
                  {post.featured_image && <figure className="publication-hero"><img src={post.featured_image} alt="" /></figure>}
                  <div className="publication-body" style={readingStyle} dangerouslySetInnerHTML={{ __html: content.html }} />
                  {post.pdf_url && <aside className="publication-download"><span className="publication-download-icon"><Download size={22} aria-hidden="true" /></span><div><h3>{post.pdf_title || 'Downloadable resource'}</h3><p>PDF for offline reading and reference.</p></div></aside>}
                  {postTags.length > 0 && <div className="publication-tags"><Tag size={15} aria-hidden="true" />{postTags.map(tag => <span key={tag.id}>{plainText(tag.name)}</span>)}</div>}
                  {showCards && <section className="publication-contributors">
                    {post.design_settings.author_section_label && <p className="publication-card-topic">{post.design_settings.author_section_label}</p>}
                    <h3>{post.design_settings.author_section_title || 'Authors and contributors'}</h3>
                    {post.design_settings.author_section_intro && <p>{plainText(post.design_settings.author_section_intro)}</p>}
                    <ul className="dart-preview-credits">{credits.map((credit, index) => <li key={`${credit.contributor_id}-${index}`}><strong>{plainText(credit.author.display_name)}</strong><span>{roleLabels[credit.role] || 'Author'}</span></li>)}</ul>
                  </section>}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>}
    </dialog>
  );
}
