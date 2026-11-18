import manifest from '../config/optimizedImages.json' with { type: 'json' };

const base = import.meta.env?.BASE_URL || '/';
const byFile = new Map(Object.values(manifest).flatMap(entry => [[entry.file, entry], [entry.small, entry]]));

/** Catalog entry ({ file, small, width, height, … }) for a known image URL, or null. */
export function optimizedImageEntry(value) {
  if (typeof value !== 'string' || !/^(https?:\/\/|\/)/i.test(value)) return null;
  try {
    const url = new URL(value, 'https://resref.com');
    const host = ['resres.local', 'resref.local', 'www.resref.com'].includes(url.hostname) ? 'resref.com' : url.hostname;
    return manifest[`https://${host}${url.pathname}`] || (url.pathname.includes('/optimized-images/') ? byFile.get(url.pathname.split('/').pop()) : undefined) || null;
  } catch { return null; }
}

export function optimizedImageUrl(value, thumbnail = false) {
  const entry = optimizedImageEntry(value);
  return entry ? `${base}optimized-images/${thumbnail ? entry.small : entry.file}` : value;
}

export function optimizedImageData(value) {
  if (Array.isArray(value)) return value.map(optimizedImageData);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, optimizedImageData(item)]));
  return typeof value === 'string' ? optimizedImageUrl(value) : value;
}
