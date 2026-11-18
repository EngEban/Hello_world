const publicBase = import.meta.env?.BASE_URL || '/';
const asset = name => `${publicBase}hero-images/${name}.webp?v=optimized-1`;

export function mobileHeroImage(url) {
  return url?.includes('/hero-images/') ? url.replace(/\.webp(?=\?|$)/, '-mobile.webp') : url;
}

export const HERO_IMAGES = {
  database: asset('database'), learn: asset('learn'), tools: asset('tools'),
  opportunities: asset('opportunities'), join: asset('join'), about: asset('about'),
  consultation: asset('consultation'), contact: asset('contact'), faq: asset('faq'),
  questionnaires: asset('questionnaires'), journal_finder: asset('journal-finder'),
  sample_size: asset('sample-size'), reference_generator: asset('references'),
  legal: asset('legal'), not_found: asset('not-found'),
};

// Replace the old repeated placeholder, but never overwrite a custom image.
const legacyBanner = 'https://resref.com/wp-content/uploads/2026/05/hand-medical-glove-pointing-virtual-screen-medical-technology-1.jpg';

export function pageHeroImage(settings, prefix = '', imageUrl = '', pathname = '') {
  const selected = imageUrl || settings[`${prefix}_hero_image_url`];
  if (selected && selected !== legacyBanner) return selected;
  if (settings.page_banner_image_url && settings.page_banner_image_url !== legacyBanner) return settings.page_banner_image_url;
  const inferred = pathname.startsWith('/articles') ? 'learn'
    : /privacy|terms|disclaimer|cookies/.test(pathname) ? 'legal' : 'database';
  return HERO_IMAGES[prefix] || HERO_IMAGES[inferred];
}
