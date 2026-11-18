import { ArrowDown, ArrowUp, ChevronDown, Download, ExternalLink, FileText, ImagePlus, Link2, Save, Trash2, Upload, UserRoundPlus, X } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import ChipPicker from '../../../components/dashboard/ChipPicker';
import { optimizedImageUrl } from '../../../utils/optimizedImages';
import { CONTRIBUTOR_ROLES } from './editorModel';

const initials = name => String(name || '?').trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();

/** Collapsible settings card. `hint` is a short status shown in the summary row. */
export function EditorSection({ id, icon: Icon, title, hint, tone = '', defaultOpen = false, children }) {
  return <details className="editor-section dart-section" id={id} open={defaultOpen}>
    <summary><span className="dart-section-icon" aria-hidden="true">{Icon && <Icon size={16} />}</span><span className="dart-section-title">{title}</span>{hint && <span className={`dart-section-hint ${tone}`}>{hint}</span>}<ChevronDown className="dart-section-chevron" size={17} aria-hidden="true" /></summary>
    <div className="editor-section-body dart-section-body">{children}</div>
  </details>;
}

// Good inside [min, max]; short below, over above.
function counterTone(length, min, max) {
  if (!length) return 'is-empty';
  if (length > max) return 'is-over';
  return length >= min ? 'is-good' : 'is-short';
}

export function SeoFields({ editing, update, publicUrl, renderedTitle }) {
  const title = renderedTitle || editing.seo_title || editing.title || 'Untitled draft';
  const description = editing.seo_description || editing.excerpt || 'Add a meta description to control the text search engines show under your title.';
  // The public page appends " | ResRef", so the visible search title is longer than the field.
  const titleLength = (renderedTitle || editing.seo_title || editing.title).length;
  const descriptionLength = (editing.seo_description || editing.excerpt).length;
  let host = 'resref.com';
  let crumbs = [];
  try { const url = new URL(publicUrl); host = url.host; crumbs = url.pathname.split('/').filter(Boolean); } catch { /* keep defaults */ }
  return <div className="dart-seo">
    <figure className="dart-serp" aria-label="Search result preview">
      <figcaption>Search result preview</figcaption>
      <div className="dart-serp-site"><span className="dart-serp-favicon" aria-hidden="true">R</span><span><strong>ResRef</strong><small>{[host, ...crumbs].join(' › ')}</small></span></div>
      <p className="dart-serp-title">{title.length > 62 ? `${title.slice(0, 60)}…` : title}</p>
      <p className="dart-serp-text">{description.length > 158 ? `${description.slice(0, 155)}…` : description}</p>
    </figure>
    <label>SEO Title<input id="article-field-seo-title" name="seo_title" value={editing.seo_title || ''} onChange={update} placeholder="Lead with the keyphrase; the article title is used when empty" dir="auto" /><small className={`dart-counter ${counterTone(titleLength, 30, 60)}`}>{titleLength}/60 characters shown in Google, including “| ResRef”{!editing.seo_title && editing.title ? ' · using the article title' : ''}</small></label>
    <label>Meta Description<textarea id="article-field-seo-description" name="seo_description" value={editing.seo_description || ''} onChange={update} rows="3" placeholder="A 120–156 character answer to the searcher’s question, with the keyphrase" dir="auto" /><small className={`dart-counter ${counterTone(editing.seo_description ? descriptionLength : 0, 120, 156)}`}>{descriptionLength}/156 characters · 120–156 recommended{!editing.seo_description && editing.excerpt ? ' · search engines will use the excerpt' : ''}</small></label>
  </div>;
}

export function MediaFields({ editing, update, setField, onPickImage, pdfUploading, uploadPdf, removePdf }) {
  const [showUrl, setShowUrl] = useState(false);
  return <div className="dart-media">
    <div className="dart-image-field">
      <span className="dart-field-label">Featured image</span>
      {editing.featured_image
        ? <figure className="dart-image-preview"><img src={optimizedImageUrl(editing.featured_image, true)} alt="Featured image preview" /><figcaption><button type="button" className="admin-button admin-button-secondary" onClick={onPickImage}><ImagePlus size={15} /> Replace image</button><button type="button" className="admin-button admin-button-secondary" onClick={() => setField('featured_image', '')}><X size={15} /> Remove</button></figcaption></figure>
        : <button type="button" className="dart-image-empty" onClick={onPickImage}><ImagePlus size={24} /><strong>Choose from Media Library</strong><small>Or upload a new image. Shown on cards, social shares and the article header.</small></button>}
      {(showUrl || editing.featured_image) ? <label>Featured Image URL<input name="featured_image" value={editing.featured_image} onChange={update} placeholder="https://… or copy a URL from Media Library" /></label> : <button type="button" className="dart-link-button" onClick={() => setShowUrl(true)}><Link2 size={14} /> Paste an image URL instead</button>}
      <p className="editor-hint"><Link to="/dashboard/media" target="_blank" rel="noreferrer">Open Media Library</Link> to manage images and alt text.</p>
    </div>
    <div className="post-pdf-panel dart-pdf">
      <span className="dart-field-label">Downloadable PDF</span>
      <label>PDF Display Title<input name="pdf_title" value={editing.pdf_title || ''} onChange={update} placeholder="Optional title shown to readers" /></label>
      {editing.id ? <>
        <div className={editing.pdf_url ? 'post-pdf-current dart-pdf-current active' : 'post-pdf-current dart-pdf-current'}><FileText size={18} /><span>{editing.pdf_url ? (editing.pdf_title || 'Downloadable PDF attached') : 'No downloadable PDF attached'}</span>{editing.pdf_url && <a href={editing.pdf_url} target="_blank" rel="noreferrer" download><Download size={15} /> Download</a>}</div>
        <div className="dart-pdf-actions">
          <label className="admin-file-drop post-pdf-upload dart-pdf-upload"><Upload size={17} /><span>{pdfUploading ? 'Uploading...' : editing.pdf_url ? 'Replace PDF' : 'Upload downloadable PDF'}</span><input type="file" accept="application/pdf,.pdf" disabled={pdfUploading} onChange={uploadPdf} /></label>
          {editing.pdf_url && <button className="admin-button admin-button-secondary" type="button" disabled={pdfUploading} onClick={removePdf}><Trash2 size={15} /> Remove PDF</button>}
        </div>
        <p className="editor-hint">PDF changes are saved immediately. Maximum 12 MB.</p>
      </> : <p className="editor-hint">Save the article before attaching a downloadable PDF.</p>}
    </div>
  </div>;
}

export function TaxonomyFields({ editing, categories, tags, authors, canWrite, setField, onCreateTag, contributor }) {
  const { showDraft, setShowDraft, draft, updateDraft, saving, saveDraft, resetDraft, add, updateCredit, removeCredit, moveCredit } = contributor;
  const categoryOptions = categories.map(category => ({ id: category.id, label: category.name, hint: category.show_in_database === false ? 'Hidden from database' : undefined }));
  const tagOptions = tags.map(tag => ({ id: tag.id, label: tag.name }));
  const assigned = new Set((editing.contributors || []).map(item => Number(item.contributor_id)));
  return <div className="dart-taxonomy">
    <div className="dart-taxonomy-grid">
      <ChipPicker label="Categories" options={categoryOptions} value={editing.categories} onChange={value => setField('categories', value)} disabled={!canWrite} placeholder="Search categories…" emptyText="No category selected." />
      <ChipPicker label="Tags" options={tagOptions} value={editing.tags} onChange={value => setField('tags', value)} onCreate={canWrite ? onCreateTag : undefined} disabled={!canWrite} placeholder={canWrite ? 'Search or create tags…' : 'Search tags…'} emptyText="No tags yet." />
    </div>
    <fieldset className="contributor-selector dart-contributors">
      <legend>Article Contributors</legend>
      <p className="editor-hint">These profiles appear in the article-end author cards. They are content credits, not the uploader account.</p>
      {authors.length ? <>
        <ol className="dart-credit-list">
          {(editing.contributors || []).map((credit, index) => {
            const author = authors.find(item => Number(item.id) === Number(credit.contributor_id));
            return <li className="dart-credit" key={`${credit.contributor_id}-${index}`}>
              <span className="dart-credit-avatar" aria-hidden="true">{author?.avatar ? <img src={optimizedImageUrl(author.avatar, true)} alt="" /> : initials(author?.display_name)}</span>
              <span className="dart-credit-name"><strong>{author?.display_name || 'Contributor'}</strong>{author?.credentials && <small>{author.credentials}</small>}</span>
              <select aria-label={`Role for ${author?.display_name || 'contributor'}`} value={credit.role || 'author'} onChange={event => updateCredit(index, 'role', event.target.value)}>{CONTRIBUTOR_ROLES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select>
              <span className="dart-credit-actions">
                <button className="dash-icon-button" type="button" onClick={() => moveCredit(index, -1)} disabled={!index} aria-label="Move up" title="Move up"><ArrowUp size={14} /></button>
                <button className="dash-icon-button" type="button" onClick={() => moveCredit(index, 1)} disabled={index === editing.contributors.length - 1} aria-label="Move down" title="Move down"><ArrowDown size={14} /></button>
                <button className="dash-icon-button dart-danger-icon" type="button" onClick={() => removeCredit(index)} aria-label={`Remove ${author?.display_name || 'contributor'}`} title="Remove"><X size={14} /></button>
              </span>
            </li>;
          })}
        </ol>
        {!(editing.contributors || []).length && <p className="dart-muted-box">No contributors credited yet. Add an existing profile below.</p>}
        <label>Add an existing contributor<select aria-label="Add an existing contributor" value="" onChange={event => { if (event.target.value) add(event.target.value); }}><option value="">Select a contributor…</option>{authors.filter(author => author.is_active && !assigned.has(Number(author.id))).map(author => <option value={author.id} key={author.id}>{author.display_name}{author.credentials ? `, ${author.credentials}` : ''}</option>)}</select></label>
      </> : <div className="contributor-empty dart-muted-box">No contributor profiles yet. Add the first author, editor, or translator below.</div>}
      <div className="contributor-selector-actions dart-inline-actions">
        <button className="admin-button admin-button-secondary" type="button" onClick={() => setShowDraft(value => !value)} aria-expanded={showDraft}><UserRoundPlus size={15} /> {showDraft ? 'Close profile form' : 'Add contributor profile'}</button>
        <Link className="admin-button admin-button-secondary" to="/dashboard/authors" target="_blank" rel="noreferrer"><ExternalLink size={15} /> Manage authors</Link>
      </div>
      {showDraft && <div className="contributor-inline-form dart-inline-form">
        <div className="admin-form-grid">
          <label>Display Name<input name="display_name" value={draft.display_name} onChange={updateDraft} placeholder="Dr. Rawan Daaboul" aria-required="true" /></label>
          <label>Public Role<input name="role" value={draft.role} onChange={updateDraft} placeholder="Author, Editor, Translator..." /></label>
          <label>Email<input type="email" name="email" value={draft.email} onChange={updateDraft} placeholder="Optional internal reference" /></label>
        </div>
        <label>Portrait Image URL<input name="avatar" value={draft.avatar} onChange={updateDraft} placeholder="Copy a portrait URL from Media Library" /></label>
        <label>Short Biography<textarea name="bio" value={draft.bio} onChange={updateDraft} rows="3" placeholder="Public biography shown on the article page" /></label>
        <div className="admin-form-grid">
          <label>Website<input name="website" value={draft.website} onChange={updateDraft} placeholder="https://..." /></label>
          <label>LinkedIn<input name="linkedin" value={draft.linkedin} onChange={updateDraft} placeholder="https://..." /></label>
          <label>X / Twitter<input name="twitter" value={draft.twitter} onChange={updateDraft} placeholder="https://..." /></label>
        </div>
        <div className="admin-editor-actions">
          <button className="admin-button" type="button" disabled={saving} onClick={saveDraft}><Save size={15} /> {saving ? 'Saving...' : 'Save and Select'}</button>
          <button className="admin-button admin-button-secondary" type="button" onClick={resetDraft}><X size={15} /> Cancel</button>
        </div>
      </div>}
    </fieldset>
  </div>;
}

export function AuthorSectionFields({ editing, updateDesign }) {
  const enabled = editing.design_settings.author_section_enabled === 'auto';
  return <div className="author-section-editor dart-author-section">
    <label className="admin-check dart-switch"><input type="checkbox" checked={enabled} onChange={event => updateDesign({ target: { name: 'author_section_enabled', value: event.target.checked ? 'auto' : 'hidden' } })} /><span className="dart-switch-track" aria-hidden="true" /> Show clickable author/contributor cards at the end of this article</label>
    <p className="editor-hint">Optional for each article. Assign author profiles above first. Turning cards off does not remove assigned authors or their public profiles. The uploading account is never credited automatically.</p>
    <div className={enabled ? 'dart-author-fields' : 'dart-author-fields is-muted'}>
      <div className="admin-form-grid">
        <label>Small Label<input name="author_section_label" value={editing.design_settings.author_section_label || ''} onChange={updateDesign} placeholder="Authorship" /></label>
        <label>Section Title<input name="author_section_title" value={editing.design_settings.author_section_title || ''} onChange={updateDesign} placeholder="Authorship and Contributions" /></label>
      </div>
      <label>Intro Text<textarea name="author_section_intro" value={editing.design_settings.author_section_intro || ''} onChange={updateDesign} rows="4" placeholder="Describe author, editor, translator, and formatter contributions." /></label>
    </div>
    <p className="editor-hint">Create or update profiles in Authors &amp; Contributors. You can keep authors assigned and switch only the end cards off.</p>
  </div>;
}

export function DesignFields({ editing, updateDesign }) {
  const design = editing.design_settings;
  return <div className="dart-design">
    <div className="dart-design-grid">
      <label>Font Family<select name="font_family" value={design.font_family} onChange={updateDesign}><option>Arial, sans-serif</option><option>Georgia, serif</option><option>Comfortaa, Arial, sans-serif</option><option>Tahoma, sans-serif</option><option>"Times New Roman", serif</option></select></label>
      <label>Content Width (px)<input type="number" min="560" max="1400" name="content_width" value={design.content_width} onChange={updateDesign} /></label>
      <label>Font Size (px)<input type="number" min="12" max="30" name="font_size" value={design.font_size} onChange={updateDesign} /></label>
      <label>Line Height<input type="number" min="1" max="3" step=".05" name="line_height" value={design.line_height} onChange={updateDesign} /></label>
    </div>
    <div className="dart-color-grid">
      <label className="dart-color">Text Color<span><input type="color" name="text_color" value={design.text_color} onChange={updateDesign} /><code>{design.text_color}</code></span></label>
      <label className="dart-color">Accent Color<span><input type="color" name="accent_color" value={design.accent_color} onChange={updateDesign} /><code>{design.accent_color}</code></span></label>
      <label className="dart-color">Background Color<span><input type="color" name="background_color" value={design.background_color} onChange={updateDesign} /><code>{design.background_color}</code></span></label>
    </div>
    <div className="dart-design-sample" style={{ background: design.background_color, color: design.text_color, fontFamily: design.font_family, fontSize: `${Math.min(Number(design.font_size) || 18, 22)}px`, lineHeight: design.line_height }} aria-hidden="true">
      <strong style={{ color: design.accent_color }}>Sample heading</strong> Research methods turn questions into evidence. This sample uses the colours and spacing above.
    </div>
    <p className="editor-hint">Public reading pages use the shared editorial typeface; colours, width and other supported options are applied. Low-contrast text colours are corrected automatically.</p>
  </div>;
}

export function SourceInfo({ editing }) {
  return <div className="source-meta dart-source">
    <strong>Imported from WordPress #{editing.wordpress_id}</strong>
    {editing.wordpress_url && <a href={editing.wordpress_url} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Open original URL</a>}
    <span>{editing.elementor_data ? 'Elementor source metadata preserved.' : 'Standard WordPress content.'}</span>
    {editing.page_template && <span>Template: {editing.page_template}</span>}
  </div>;
}
