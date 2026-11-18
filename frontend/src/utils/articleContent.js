import DOMPurify from 'dompurify';
import { optimizedImageEntry, optimizedImageUrl } from './optimizedImages';

export function plainText(value = '') {
  const doc = new DOMParser().parseFromString(DOMPurify.sanitize(String(value)), 'text/html');
  return doc.body.textContent.trim();
}

export function cleanSeoText(value = '') {
  return plainText(value).replace(/%{1,2}[a-z_]+%{1,2}/gi, '').replace(/\s+/g, ' ').replace(/^[\s|:–—-]+|[\s|:–—-]+$/g, '').trim();
}

export const articlePath = post => `/database/${post.categories?.[0]?.slug || 'research'}/${post.slug}`;
export const formatArticleDate = value => value && Number.isFinite(Date.parse(value))
  ? new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(value)) : '';
export const initials = name => plainText(name).split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase();
export function safeExternalUrl(value) {
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : ''; } catch { return ''; }
}

// Presentation only: the original HTML stored by the dashboard is never changed.
export function prepareArticleContent(content = '', { excludeLegacyAuthorship = false } = {}) {
  const clean = DOMPurify.sanitize(content, {
    FORBID_TAGS: ['svg', 'iframe', 'object', 'embed', 'script', 'style', 'form', 'input', 'button'],
    FORBID_ATTR: ['style', 'width', 'height', 'color', 'bgcolor', 'face'],
  });
  const doc = new DOMParser().parseFromString(clean, 'text/html');
  // Old Elementor team popups repeat the same credits inside the article body.
  // When explicit profile cards own authorship, omit only this recognised
  // metadata section from the reader. The stored HTML is never changed.
  if (excludeLegacyAuthorship) {
    const marker = Array.from(doc.body.children).find(node => /^H[23]$/.test(node.tagName) && /^authorship and contributions\s*$/i.test(node.textContent.trim()));
    const isProfileHeading = node => /^H[23]$/.test(node.tagName) && /^(author|co-author|editor|reviewer|translator|formatter)(\s*[&/]\s*(translator|formatter))?$/i.test(node.nextElementSibling?.textContent.trim() || '');
    if (marker && Array.from(doc.body.children).slice(Array.from(doc.body.children).indexOf(marker) + 1).some(isProfileHeading)) {
      let node = marker;
      while (node) {
        const next = node.nextSibling;
        if (node !== marker && node.nodeType === 1 && /^H[123]$/.test(node.tagName) && node.textContent.trim() && !isProfileHeading(node)) break;
        node.remove(); node = next;
      }
    }
  }
  const used = new Set(Array.from(doc.querySelectorAll('[id]'), node => node.id));
  const toc = Array.from(doc.body.querySelectorAll('h1,h2,h3,h4')).map((node, index) => {
    // The article title is the only H1; legacy body H1s become sections.
    if (node.tagName === 'H1') {
      const replacement = doc.createElement('h2');
      for (const attr of node.attributes) replacement.setAttribute(attr.name, attr.value);
      replacement.innerHTML = node.innerHTML;
      node.replaceWith(replacement);
      node = replacement;
    }
    const text = node.textContent.trim();
    if (!node.id) {
      const base = text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '') || `section-${index + 1}`;
      let id = base; let number = 2;
      while (used.has(id)) id = `${base}-${number++}`;
      node.id = id; used.add(id);
    }
    if (/^(references|bibliography|sources|المراجع)\s*:?$/i.test(text)) node.classList.add('publication-reference-heading');
    return { id: node.id, text, level: node.tagName.toLowerCase() };
  }).filter(item => item.text);
  doc.querySelectorAll('img').forEach(image => {
    const original = image.getAttribute('src');
    const optimized = optimizedImageUrl(original);
    if (optimized !== original) {
      image.setAttribute('src', optimized);
      image.removeAttribute('srcset'); image.removeAttribute('sizes');
      image.closest('picture')?.querySelectorAll('source').forEach(source => source.remove());
    }
    // Intrinsic size from the image catalog lets the browser reserve space
    // before the file loads (no layout shift); CSS keeps height:auto.
    const entry = optimizedImageEntry(optimized);
    if (entry?.width && entry?.height) { image.setAttribute('width', String(entry.width)); image.setAttribute('height', String(entry.height)); }
    image.setAttribute('loading', 'lazy'); image.setAttribute('decoding', 'async');
    if (!image.hasAttribute('alt')) image.setAttribute('alt', '');
  });
  doc.querySelectorAll('a[href]').forEach(link => {
    // Imported posts link images to the old WordPress uploads; point those
    // links at the self-hosted copy so they keep working after the move.
    let href = link.getAttribute('href').trim();
    // Imported content sometimes has bare e-mail addresses or "www." hosts as
    // the href, which browsers resolve as broken relative ResRef pages.
    if (/^[^\s@/:?#]+@[^\s@/:?#]+\.[a-z]{2,}$/i.test(href)) { href = `mailto:${href}`; link.setAttribute('href', href); }
    else if (/^www\.[^\s/]+\.[a-z]{2,}/i.test(href)) { href = `https://${href}`; link.setAttribute('href', href); }
    const optimized = optimizedImageUrl(href);
    if (optimized !== href) link.setAttribute('href', optimized);
    // A link that only wraps an image with empty alt text has no accessible
    // name (WCAG 2.4.4 / 4.1.2): describe what it opens.
    if (!link.textContent.trim() && !link.getAttribute('aria-label') && link.querySelector('img')) {
      const named = Array.from(link.querySelectorAll('img')).map(image => image.getAttribute('alt')?.trim()).find(Boolean);
      if (!named) {
        const caption = link.closest('figure')?.querySelector('figcaption')?.textContent.trim();
        link.setAttribute('aria-label', caption ? `Open image: ${caption.slice(0, 120)}` : 'Open full-size image');
      }
    }
  });
  doc.querySelectorAll('a[target="_blank"]').forEach(link => link.setAttribute('rel', 'noopener noreferrer'));
  doc.querySelectorAll('table').forEach(table => {
    const firstRow = table.rows[0];
    if (!table.querySelector('th') && firstRow?.cells.length && Array.from(firstRow.cells).every(cell => {
      const bold = cell.querySelector('strong,b');
      return bold && bold.textContent.trim() === cell.textContent.trim();
    })) {
      Array.from(firstRow.cells).forEach(cell => {
        const header = doc.createElement('th');
        for (const attr of cell.attributes) header.setAttribute(attr.name, attr.value);
        header.scope = 'col'; header.innerHTML = cell.innerHTML; cell.replaceWith(header);
      });
    }
    const wrapper = doc.createElement('div'); wrapper.className = 'publication-table-scroll';
    wrapper.setAttribute('tabindex', '0'); wrapper.setAttribute('role', 'region');
    wrapper.setAttribute('aria-label', table.caption?.textContent || 'Article table, scroll horizontally for more columns');
    table.replaceWith(wrapper); wrapper.appendChild(table);
  });
  // Flatten empty WordPress list wrappers, retaining every actual list item.
  Array.from(doc.querySelectorAll('li')).reverse().forEach(li => {
    if (li.children.length === 1 && /^(UL|OL)$/.test(li.firstElementChild.tagName) && !Array.from(li.childNodes).some(n => n.nodeType === 3 && n.textContent.trim())) {
      const inner = li.firstElementChild;
      if (li.parentElement.tagName === inner.tagName) li.replaceWith(...inner.children);
    }
  });
  return { html: doc.body.innerHTML, toc };
}
