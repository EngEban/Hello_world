import { isFuturePublication, wordCount } from './workspace';

export const defaultDesign = {
  font_family: 'Arial, sans-serif',
  font_size: '18',
  line_height: '1.85',
  text_color: '#29394d',
  accent_color: '#126ac6',
  background_color: '#ffffff',
  content_width: '750',
  author_section_enabled: 'hidden',
  author_section_label: 'Authorship',
  author_section_title: 'Authorship and Contributions',
  author_section_intro: 'The following section acknowledges the individuals who contributed to the authorship, editing, translation, and preparation of this article, ensuring its academic integrity and clarity.',
};

export const emptySeoSettings = { focus_keyphrase: '', related_keyphrases: [], cornerstone: false };
export const emptyContributor = { login: '', display_name: '', email: '', role: 'Author', bio: '', avatar: '', website: '', linkedin: '', twitter: '' };
export const CONTRIBUTOR_ROLES = [['author', 'Author'], ['co_author', 'Co-author'], ['editor', 'Editor'], ['reviewer', 'Reviewer'], ['translator', 'Translator'], ['formatter', 'Formatter']];

const localInput = date => new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
export const currentDatetimeLocal = () => localInput(new Date());
export const toDatetimeLocal = value => (value ? localInput(new Date(value)) : '');
export const tomorrowMorningLocal = () => { const date = new Date(); date.setDate(date.getDate() + 1); date.setHours(9, 0, 0, 0); return localInput(date); };
// datetime-local has no timezone. Convert it into an explicit UTC instant
// before it crosses the API boundary; otherwise Django reads a Dubai time as
// UTC and unintentionally schedules a just-published article four hours later.
export const toApiDatetime = value => {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toISOString();
};

export const createEmptyPost = type => ({ title: '', slug: '', excerpt: '', content: '<p>Start writing here...</p>', post_type: type === 'page' ? 'page' : 'post', status: 'draft', featured_image: '', published_at: '', author_id: '', author_ids: [], contributors: [], categories: [], tags: [], pdf_title: '', pdf_url: '', seo_title: '', seo_description: '', seo_settings: { ...emptySeoSettings }, design_settings: { ...defaultDesign } });

export function normalizePost(post) {
  const authorIds = (post.author_ids?.length ? post.author_ids : (post.authors || []).map(item => item.id)).map(Number).filter(Boolean);
  const contributors = post.contributors?.length ? post.contributors : authorIds.map((contributor_id, display_order) => ({ contributor_id, role: 'author', display_order, contribution_note: '' }));
  return { ...post, published_at: toDatetimeLocal(post.published_at), author_id: post.author_id || '', author_ids: authorIds, contributors, pdf_title: post.pdf_title || '', pdf_url: post.pdf_url || '', seo_settings: { ...emptySeoSettings, ...(post.seo_settings || {}) }, design_settings: { ...defaultDesign, ...(post.design_settings || {}) }, categories: (post.categories || []).map(item => (typeof item === 'object' ? item.id : item)), tags: (post.tags || []).map(item => (typeof item === 'object' ? item.id : item)) };
}

export const payloadForSave = post => ({ ...post, expected_updated_at: post.updated_at, published_at: toApiDatetime(post.published_at), author_ids: post.author_ids || [], contributors: post.contributors || [] });

export function buildChecklist(editing) {
  if (!editing) return [];
  const isPage = editing.post_type === 'page';
  return [
    { label: 'Title is clear', done: editing.title.trim().length >= 12, target: 'article-field-title' },
    { label: 'Slug is ready', done: editing.slug.trim().length >= 4, target: 'article-field-slug' },
    { label: 'Excerpt supports cards/search', done: editing.excerpt.trim().length >= 70, target: 'article-field-excerpt' },
    // 300 words: Yoast's minimum for posts and pages.
    { label: 'Article has enough body copy (300+ words)', done: wordCount(editing.content) >= 300, target: 'article-section-body' },
    !isPage && { label: 'Category selected', done: editing.categories.length > 0, target: 'article-section-taxonomy' },
    !isPage && { label: 'Contributor credited', done: (editing.contributors || []).length > 0, target: 'article-section-taxonomy' },
    { label: 'Featured image added', done: Boolean(editing.featured_image), target: 'article-section-media' },
    { label: 'SEO title and description added', done: Boolean(editing.seo_title && editing.seo_description), target: 'article-section-seo' },
    { label: 'Publication date is set', done: Boolean(editing.published_at), target: 'article-field-date' },
  ].filter(Boolean);
}

export function publishVisibilityIssues(editing, categories) {
  if (!editing || editing.status !== 'publish') return [];
  const issues = [];
  if (editing.post_type !== 'post') issues.push('This is saved as a backend page, not a database article.');
  if (!editing.published_at) {
    issues.push('Publication date is empty.');
  } else if (isFuturePublication(editing.published_at)) {
    issues.push(`Publication date is scheduled for ${new Date(editing.published_at).toLocaleString()}; it will not open publicly until then.`);
  }
  if (editing.post_type === 'post') {
    if (!editing.categories.length) {
      issues.push('No category is selected, so it will only appear in all database results.');
    } else {
      const selectedCategories = categories.filter(category => editing.categories.includes(category.id));
      if (selectedCategories.length && !selectedCategories.some(category => category.show_in_database !== false)) {
        issues.push('Selected categories are hidden from the public database category list.');
      }
    }
  }
  return issues;
}

export function displayStatus(post) {
  return post.status === 'publish' && isFuturePublication(post.published_at) ? 'scheduled' : post.status;
}

export function publicPreviewPath(editing, categories) {
  if (!editing) return '';
  if (editing.post_type === 'page') return `/page/${editing.slug}`;
  const categorySlug = editing.categories?.[0] ? categories.find(item => item.id === editing.categories[0])?.slug || 'research' : 'research';
  return `/database/${categorySlug}/${editing.slug}`;
}
