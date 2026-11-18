// Country names come from react-phone-number-input's bundled English labels,
// so the list stays in step with the phone-number library. The backend accepts
// the same set: ISO 3166-1 alpha-2 codes plus XK (Kosovo).
import labels from 'react-phone-number-input/locale/en.json';

// ZZ = "International", XA/XO = non-ISO regions, AC/TA = phone-only regions
// (Ascension, Tristan da Cunha) that ISO files under SH.
const EXCLUDED = new Set(['ZZ', 'XA', 'XO', 'AC', 'TA']);

export const COUNTRY_OPTIONS = Object.entries(labels)
  .filter(([code]) => /^[A-Z]{2}$/.test(code) && !EXCLUDED.has(code))
  .map(([code, name]) => ({ code, name }))
  .sort((a, b) => a.name.localeCompare(b.name, 'en'));

const COUNTRY_CODES = new Set(COUNTRY_OPTIONS.map(option => option.code));

export function isCountryCode(value) {
  return COUNTRY_CODES.has(String(value || '').toUpperCase());
}

// Best guess from the browser language (en-GB -> GB); never from IP lookups.
export function guessCountry() {
  try {
    const languages = navigator.languages?.length ? navigator.languages : [navigator.language];
    for (const language of languages) {
      const region = language ? new Intl.Locale(language).region : '';
      if (region && isCountryCode(region)) return region.toUpperCase();
    }
  } catch { /* unsupported Intl.Locale or invalid tag */ }
  return '';
}
