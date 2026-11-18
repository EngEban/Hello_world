export const STATUS_VIEWS = [
  ['', 'All content', 'total'], ['publish', 'Published', 'published'], ['draft', 'Drafts', 'draft'],
  ['pending', 'In review', 'pending'], ['scheduled', 'Scheduled', 'scheduled'], ['private', 'Private', 'private'], ['trash', 'Trash', 'trash'],
];

/** "Needs attention" shortcuts: key = backend needs= filter. */
export const NEEDS_FILTERS = [
  ['low_score', 'Low optimization score'], ['keyphrase', 'No focus keyphrase'],
  ['seo', 'Missing SEO'], ['image', 'Missing image'], ['excerpt', 'Missing excerpt'], ['category', 'No category'], ['contributors', 'No contributors'],
];
/** Extra "Editorial checks" options (not shown as attention shortcuts). */
export const SCORE_FILTERS = [
  ['seo_low', 'Search (SEO) score below 50'], ['readability_low', 'Readability score below 50'], ['aeo_low', 'Answers (AEO) score below 50'], ['geo_low', 'AI visibility (GEO) score below 50'],
];

export const LIST_KEYS = ['q', 'type', 'status', 'category', 'tag', 'author', 'sort', 'featured', 'needs', 'date_from', 'date_to', 'per_page', 'page'];

export function articleFilters(params) {
  const value = Object.fromEntries(LIST_KEYS.map(key => [key, params.get(key) || '']));
  return { ...value, type: value.type === 'page' ? 'page' : 'post', sort: value.sort || 'updated', per_page: ['20', '50', '100'].includes(value.per_page) ? value.per_page : '20', page: Math.max(1, Number(value.page) || 1) };
}

export function editorialStatus(post, now = Date.now()) {
  return post.status === 'publish' && post.published_at && new Date(post.published_at).getTime() > now ? 'scheduled' : post.status;
}

export function articlePath(post) {
  return post.post_type === 'page' ? `/page/${post.slug}` : `/database/${post.categories?.[0]?.slug || 'research'}/${post.slug}`;
}

/** Row-level readiness used by the library (works on summary records). */
export const ROW_CHECKS = [
  { key: 'excerpt', label: 'Excerpt', test: post => Boolean(String(post.excerpt || '').trim()) },
  { key: 'image', label: 'Featured image', test: post => Boolean(post.featured_image) },
  { key: 'seo', label: 'SEO title and description', test: post => Boolean(post.seo_title && post.seo_description) },
  { key: 'category', label: 'Category', test: post => Boolean(post.categories?.length), postsOnly: true },
  { key: 'contributors', label: 'Contributors', test: post => Boolean(post.authors?.length || post.contributors?.length || post.author), postsOnly: true },
];

export function rowReadiness(post) {
  const checks = ROW_CHECKS.filter(check => !check.postsOnly || post.post_type !== 'page');
  const results = checks.map(check => ({ ...check, done: check.test(post) }));
  return { results, done: results.filter(item => item.done).length, total: results.length };
}

export function readinessIssues(post) {
  return [!post.excerpt && 'Excerpt missing', !post.featured_image && 'Image missing', (!post.seo_title || !post.seo_description) && 'SEO incomplete', !post.categories?.length && 'No category'].filter(Boolean);
}

export function localScheduleToISO(value) {
  const date = new Date(value);
  return value && !Number.isNaN(date.getTime()) ? date.toISOString() : '';
}

export const slugify = value => String(value || '').toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
export const stripHtml = value => String(value || '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
export const wordCount = value => stripHtml(value).split(/\s+/).filter(Boolean).length;
export const readMinutes = value => Math.max(1, Math.round(wordCount(value) / 220));
export const isFuturePublication = value => Boolean(value && new Date(value) > new Date());

export function relativeTime(value) {
  if (!value) return '';
  const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  return days < 30 ? `${days} d ago` : new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

/* ---------- local backup of unsaved editor changes (per browser, per article) ---------- */
const backupKey = (userId, post) => `resref.article-backup.v1.${userId || 'local'}.${post?.id || `new-${post?.post_type || 'post'}`}`;

export function readBackup(userId, post) {
  try {
    const saved = JSON.parse(localStorage.getItem(backupKey(userId, post)) || 'null');
    return saved && saved.post && saved.savedAt ? saved : null;
  } catch { return null; }
}

export function writeBackup(userId, post, baseUpdatedAt) {
  try { localStorage.setItem(backupKey(userId, post), JSON.stringify({ savedAt: new Date().toISOString(), baseUpdatedAt: baseUpdatedAt || null, post })); } catch { /* storage unavailable: backup is best-effort */ }
}

export function clearBackup(userId, post) {
  try { localStorage.removeItem(backupKey(userId, post)); } catch { /* ignore */ }
}
