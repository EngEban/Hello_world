import DOMPurify from 'dompurify';
import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  Bold,
  Code2,
  Columns2,
  Eye,
  Heading1,
  Heading2,
  Heading3,
  Heading4,
  Table2,
  BookOpen,
  Highlighter,
  ImagePlus,
  Italic,
  Link,
  List,
  ListOrdered,
  Minus,
  Pilcrow,
  Quote,
  RemoveFormatting,
  Type,
  Underline,
  Wand2,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

const modes = [['visual', Type, 'Visual'], ['html', Code2, 'HTML'], ['preview', Eye, 'Preview']];
const sanitizeHtml = html => DOMPurify.sanitize(html || '');
const escapeHtml = value => String(value || '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char]));

export default function VisualContentEditor({ value, onChange, readOnly = false }) {
  const editor = useRef(null);
  const [mode, setMode] = useState('visual');
  const [lastAction, setLastAction] = useState('Ready');

  useEffect(() => {
    if (mode === 'visual' && editor.current) {
      const safeValue = sanitizeHtml(value);
      if (editor.current.innerHTML !== safeValue) editor.current.innerHTML = safeValue;
    }
  }, [mode, value]);

  const sync = (message = 'Content updated') => {
    onChange(sanitizeHtml(editor.current?.innerHTML || ''));
    setLastAction(message);
  };
  const command = (name, argument = null, message = 'Formatting applied') => {
    editor.current?.focus();
    document.execCommand(name, false, argument);
    editor.current?.focus();
    sync(message);
  };
  const insertHtml = (html, message = 'Block inserted') => {
    editor.current?.focus();
    document.execCommand('insertHTML', false, sanitizeHtml(html));
    sync(message);
  };
  const isValidUrl = (url) => {
    try { const parsed = new URL(url); return parsed.protocol === 'http:' || parsed.protocol === 'https:'; }
    catch { return false; }
  };
  const promptLink = () => {
    const url = window.prompt('Enter the link URL (must start with http:// or https://)');
    if (url && isValidUrl(url)) command('createLink', url, 'Link added');
    else if (url) alert('Only http:// and https:// URLs are allowed.');
  };
  const promptImage = () => {
    const url = window.prompt('Enter an image URL from Media Library or another website');
    if (url && isValidUrl(url)) {
      const caption = window.prompt('Optional image caption') || '';
      const alt = window.prompt('Describe the image for screen readers (leave empty if decorative)') || '';
      insertHtml(`<figure class="content-image-block"><img src="${escapeHtml(url)}" alt="${escapeHtml(alt)}" loading="lazy" decoding="async"><figcaption>${escapeHtml(caption)}</figcaption></figure><p><br></p>`, 'Image block inserted');
    }
    else if (url) alert('Only http:// and https:// image URLs are allowed.');
  };
  const promptSection = () => {
    const title = window.prompt('Section title') || 'New section title';
    insertHtml(`<h2>${escapeHtml(title)}</h2><p>Write the key explanation for this section.</p>`, 'Section heading inserted');
  };
  const insertCallout = () => insertHtml('<aside class="content-callout"><strong>Key point</strong><p>Add the important note, interpretation, or clinical/research guidance here.</p></aside><p><br></p>', 'Callout inserted');
  const insertTable = () => {
    const rowValue = window.prompt('Number of data rows (1–20)', '3');
    if (rowValue === null) return;
    const columnValue = window.prompt('Number of columns (1–8)', '3');
    if (columnValue === null) return;
    const rows = Number(rowValue); const columns = Number(columnValue);
    if (!Number.isInteger(rows) || rows < 1 || rows > 20 || !Number.isInteger(columns) || columns < 1 || columns > 8) {
      window.alert('Use 1–20 rows and 1–8 columns.'); return;
    }
    insertHtml(`<table><caption>Table title</caption><thead><tr>${Array.from({ length: columns }, (_, index) => `<th scope="col">Column ${index + 1}</th>`).join('')}</tr></thead><tbody>${Array.from({ length: rows }, () => `<tr>${'<td>…</td>'.repeat(columns)}</tr>`).join('')}</tbody></table><p><br></p>`, 'Editable table inserted');
  };
  const insertReferences = () => insertHtml('<h2>References</h2><ol><li>Author(s). Article title. Journal. Year;volume:pages. DOI or source URL.</li></ol><p><br></p>', 'References section inserted');
  const insertColumns = () => insertHtml('<div class="content-layout content-layout-two"><div><h3>Column title</h3><p>Add the first idea, step, or comparison point.</p></div><div><h3>Column title</h3><p>Add the second idea, step, or comparison point.</p></div></div><p><br></p>', 'Two-column layout inserted');
  const insertImageText = () => {
    const url = window.prompt('Enter an image URL from Media Library for the image + text block');
    if (!url) return;
    if (!isValidUrl(url)) {
      alert('Only http:// and https:// image URLs are allowed.');
      return;
    }
    insertHtml(`<div class="content-layout content-image-text"><figure class="content-image-block"><img src="${escapeHtml(url)}" alt="" loading="lazy" decoding="async"><figcaption>Optional caption</figcaption></figure><div><h3>Image and explanation</h3><p>Use this layout when an article needs a visual next to a short explanation.</p></div></div><p><br></p>`, 'Image and text layout inserted');
  };
  const handlePaste = event => {
    event.preventDefault();
    const html = event.clipboardData.getData('text/html');
    const text = event.clipboardData.getData('text/plain');
    insertHtml(html || `<p>${escapeHtml(text).replace(/\n{2,}/g, '</p><p>').replace(/\n/g, '<br>')}</p>`, 'Pasted content cleaned');
  };
  const tool = (label, Icon, action) => <button type="button" title={label} aria-label={label} onMouseDown={event => { event.preventDefault(); action(); }}><Icon size={15} /></button>;

  return <div className="visual-editor">
    <div className="visual-editor-tabs">{modes.map(([key, Icon, label]) => <button type="button" className={mode === key ? 'active' : ''} onClick={() => setMode(key)} key={key}><Icon size={14} /> {label}</button>)}</div>
    {mode === 'visual' && <>
      <div className="visual-editor-insertbar" aria-label="Insert article blocks">
        <span><Wand2 size={14} /> Add block</span>
        <button type="button" onMouseDown={event => { event.preventDefault(); promptSection(); }}><Heading2 size={14} /> Section</button>
        <button type="button" onMouseDown={event => { event.preventDefault(); insertCallout(); }}><Highlighter size={14} /> Note</button>
        <button type="button" onMouseDown={event => { event.preventDefault(); promptImage(); }}><ImagePlus size={14} /> Image</button>
        <button type="button" onMouseDown={event => { event.preventDefault(); insertTable(); }}><Table2 size={14} /> Table</button>
        <button type="button" onMouseDown={event => { event.preventDefault(); insertReferences(); }}><BookOpen size={14} /> References</button>
        <button type="button" onMouseDown={event => { event.preventDefault(); insertImageText(); }}><ImagePlus size={14} /> Image + text</button>
        <button type="button" onMouseDown={event => { event.preventDefault(); insertColumns(); }}><Columns2 size={14} /> Columns</button>
      </div>
      <div className="visual-editor-toolbar" aria-label="Format selected content">
        <div className="visual-editor-toolgroup">
          {tool('Paragraph', Pilcrow, () => command('formatBlock', 'p', 'Paragraph style applied'))}
          {tool('Article title', Heading1, () => command('formatBlock', 'h1', 'Title style applied'))}
          {tool('Section heading', Heading2, () => command('formatBlock', 'h2', 'Heading style applied'))}
          {tool('Subheading', Heading3, () => command('formatBlock', 'h3', 'Subheading style applied'))}
          {tool('Minor heading', Heading4, () => command('formatBlock', 'h4', 'Minor heading style applied'))}
          {tool('Quote', Quote, () => command('formatBlock', 'blockquote', 'Quote style applied'))}
        </div>
        <div className="visual-editor-toolgroup">
          <button type="button" title="Small text" aria-label="Small text" onMouseDown={event => { event.preventDefault(); command('fontSize', '2', 'Small text applied'); }}>S</button>
          <button type="button" title="Normal text" aria-label="Normal text" onMouseDown={event => { event.preventDefault(); command('fontSize', '3', 'Normal text applied'); }}>M</button>
          <button type="button" title="Large text" aria-label="Large text" onMouseDown={event => { event.preventDefault(); command('fontSize', '5', 'Large text applied'); }}>L</button>
        </div>
        <div className="visual-editor-toolgroup">
          {tool('Bold', Bold, () => command('bold', null, 'Bold applied'))}
          {tool('Italic', Italic, () => command('italic', null, 'Italic applied'))}
          {tool('Underline', Underline, () => command('underline', null, 'Underline applied'))}
          {tool('Bulleted list', List, () => command('insertUnorderedList', null, 'Bulleted list inserted'))}
          {tool('Numbered list', ListOrdered, () => command('insertOrderedList', null, 'Numbered list inserted'))}
        </div>
        <div className="visual-editor-toolgroup">
          {tool('Align left', AlignLeft, () => command('justifyLeft', null, 'Aligned left'))}
          {tool('Align center', AlignCenter, () => command('justifyCenter', null, 'Aligned center'))}
          {tool('Align right', AlignRight, () => command('justifyRight', null, 'Aligned right'))}
          {tool('Divider', Minus, () => insertHtml('<hr class="content-divider"><p><br></p>', 'Divider inserted'))}
          {tool('Add link', Link, promptLink)}
          {tool('Clear formatting', RemoveFormatting, () => command('removeFormat', null, 'Formatting cleared'))}
        </div>
      </div>
      <div
        className="visual-editor-canvas"
        contentEditable={!readOnly}
        suppressContentEditableWarning
        ref={editor}
        data-placeholder="Start writing, paste content, or add a block from the toolbar..."
        onInput={event => {
          onChange(sanitizeHtml(event.currentTarget.innerHTML));
          setLastAction('Writing');
        }}
        onPaste={handlePaste}
      />
      <div className="visual-editor-status" aria-live="polite">
        <span>{lastAction}</span>
        <span>{sanitizeHtml(value).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().split(/\s+/).filter(Boolean).length} words</span>
      </div>
    </>}
    {mode === 'html' && <textarea className="html-editor" value={value} onChange={event => onChange(sanitizeHtml(event.target.value))} rows="20" />}
    {mode === 'preview' && <article className="visual-editor-preview content-article" dangerouslySetInnerHTML={{ __html: sanitizeHtml(value) }} />}
  </div>;
}
