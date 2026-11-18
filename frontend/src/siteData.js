import { optimizedImageUrl } from './utils/optimizedImages';

export const ASSETS = Object.fromEntries(Object.entries({
  // Vite prefixes these public files with /static/ in the bundled Django
  // deployment and with / in local/standalone builds.
  logo: `${import.meta.env.BASE_URL}resref-logo-mark.webp`,
  logoWordmark: `${import.meta.env.BASE_URL}resref-logo-wordmark-light.webp`,
  whiteLogo: 'https://resref.com/wp-content/uploads/2025/03/White-Logo-2-300x103.png',
  hero: 'https://resref.com/wp-content/uploads/2025/12/Home-Page-05-01-1024x794.png',
  about: 'https://resref.com/wp-content/uploads/2026/05/medical-banner-with-doctor-wearing-goggles-1024x682.webp',
  consultation: 'https://resref.com/wp-content/uploads/2026/05/medical-scientist-in-hazmat-suit-working-with-microscope-and-laptop-computer-inside-laboratory.webp',
  pageBanner: 'https://resref.com/wp-content/uploads/2026/05/hand-medical-glove-pointing-virtual-screen-medical-technology-1.jpg',
  pattern: 'https://resref.com/wp-content/uploads/2025/02/Network-04-01-2-scaled.webp',
}).map(([key, url]) => [key, optimizedImageUrl(url)]));

export const SOCIAL_LINKS = {
  facebook: 'https://www.facebook.com/ResRefcom/',
  twitter: 'https://x.com/ResRefcom',
  youtube: 'https://www.youtube.com/@ResRefcom',
  instagram: 'https://www.instagram.com/resrefcom',
  linkedin: 'https://www.linkedin.com/company/resrefcom/',
  telegram: 'https://t.me/ResRefcom',
  whatsapp: 'https://whatsapp.com/channel/0029Vb6FwrR8qIzmMiGMeA1x',
};

export const PARTNER_LOGOS = [
  ['Picture1', 'https://resref.com/wp-content/uploads/2025/11/Picture1.webp'],
  ['Logo 01', 'https://resref.com/wp-content/uploads/2025/05/logo-01.png'],
  ['Picsart', 'https://resref.com/wp-content/uploads/2025/11/Picsart_25-09-05_13-47-51-922.webp'],
  ['IMG 1625', 'https://resref.com/wp-content/uploads/2025/04/IMG_1625.png'],
  ['IMG 4013', 'https://resref.com/wp-content/uploads/2025/11/IMG_4013.webp'],
  ['ReneurAI', 'https://resref.com/wp-content/uploads/2025/05/ReneurAI.png'],
  ['Damascus', 'https://resref.com/wp-content/uploads/2025/11/Damasucs-removebg-preview.webp'],
  ['GeekyDocs', 'https://resref.com/wp-content/uploads/2025/03/GeekyDocs-Logo.png'],
].map(([label, url]) => [label, optimizedImageUrl(url)]);

export const SOCIAL_ITEMS = [
  ['facebook', 'f'],
  ['twitter', 'X'],
  ['youtube', 'Y'],
  ['instagram', 'I'],
  ['linkedin', 'in'],
  ['telegram', 'T'],
  ['whatsapp', 'W'],
];

