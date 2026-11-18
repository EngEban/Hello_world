export const SEO = {
  home: {
    title: 'ResRef — Research Resources, Tools & Support',
    description: 'Research tools, articles and questionnaire guides, plus consultation support for students, clinicians and researchers.',
  },
  database: {
    title: 'Research Database — Validated Questionnaires & Scales | ResRef',
    description: 'Browse 1,000+ peer-reviewed medical questionnaires and research tools across 15+ specialties. Free access for researchers, students, and clinicians.',
  },
  tools: {
    title: 'Research Tools — Free Calculators & Generators | ResRef',
    description: 'Free interactive research tools for academics and clinicians. Sample size calculator, reference generator, and more built for real research workflows.',
  },
  researchAnalyzer: {
    title: 'ResRef Analyzer — Statistical Analysis & Reports | ResRef',
    description: 'Upload research data, prepare variables, run statistical tests, and generate structured analysis reports with ResRef Research Analyzer.',
  },
  consultation: {
    title: 'Free Expert Research Consultation | ResRef',
    description: 'Get personalised, free research consultation from ResRef expert team. Support for study design, data analysis, literature review, methodology, and more.',
  },
  opportunities: {
    title: 'Research Opportunities — Open Positions & Collaborations | ResRef',
    description: 'Discover open research positions, academic collaborations, and clinical study opportunities. Updated regularly by the ResRef community.',
  },
  join: {
    title: 'Join the ResRef Team — Volunteer Roles in Research & Technology',
    description: 'Contribute to a growing research platform. Open volunteer roles in education, design, technology, data, media, and quality control.',
  },
  about: {
    title: 'About ResRef — Our Mission, Team & Platform Story',
    description: 'ResRef is a research reference platform built to make the research journey clearer, more organised, and more connected for students, clinicians, and institutions.',
  },
  contact: {
    title: 'Contact Us | ResRef',
    description: 'Contact ResRef for research questions, expert consultation, platform support, collaborations, and institutional partnership enquiries.',
  },
  faq: {
    title: 'Frequently Asked Questions | ResRef',
    description: 'Find answers to common questions about ResRef, including the database, tools, consultation service, team roles, and platform access.',
  },
  team: {
    title: 'Our Team | ResRef',
    description: 'Meet the founder, leadership, directors and teams behind ResRef.',
  },
  teamPreview: {
    title: 'Team page preview | ResRef',
    description: 'Private preview of the ResRef Team page.',
    robots: 'noindex, nofollow',
  },
  notFound: {
    title: 'Page Not Found | ResRef',
    description: 'Find your way back to ResRef home, research database, tools, or contact support.',
  },
};

export const GUIDE_NAV_ITEMS = [
  { label: 'Home', path: '/' },
  { label: 'Research Database', path: '/database' },
  { label: 'Research Tools', path: '/tools' },
  { label: 'Expert Consultation', path: '/consultation' },
  { label: 'Research Opportunities', path: '/opportunities' },
  { label: 'Join Our Team', path: '/join' },
  { label: 'About ResRef', path: '/about' },
  { label: 'Contact Us', path: '/contact' },
  { label: 'FAQ', path: '/faq' },
];

export const DATABASE_CATEGORY_GROUPS = [
  {
    title: 'Medical Specialties',
    categories: [
      'Cardiology',
      'Dermatology',
      'Endocrinology',
      'Gastroenterology & Hepatology',
      'Nephrology & Urology',
      'Neurology',
      'Obstetrics & Gynecology',
      'Oncology',
      'Ophthalmology',
      'Orthopedics & Physical Medicine',
      'Otolaryngology (ENT)',
      'Pediatrics',
      'Psychiatry & Mental Health',
      'Pulmonology & Respiratory',
      'Rheumatology & Immunology',
    ],
  },
  {
    title: 'Health & Research Areas',
    categories: [
      'Geriatrics & Aging',
      'Nutrition & Dietetics',
      'Pain Management',
      'Palliative & Supportive Care',
      'Pharmacy & Pharmacology',
      'Public Health & Epidemiology',
      'Rehabilitation & Physiotherapy',
      'Sports Medicine',
      'Surgery & Perioperative Care',
      'Generic / Cross-specialty',
    ],
  },
  {
    title: 'Mastering Research',
    categories: [
      'Introduction to Research',
      'Study Design & Methodology',
      'Scientific Writing & Publishing',
      'Case Reports',
      'Cross-Sectional Studies',
      'Special Topics & Advanced Themes',
    ],
  },
];

export const TOOL_HUB_ITEMS = [
  {
    title: 'Sample Size Calculator',
    description: 'Calculate the statistically appropriate sample size for your study. Supports common study designs including cross-sectional, cohort, and case-control.',
    path: '/tools/sample-size-calculator',
    cta: 'Open Calculator',
    status: 'available',
  },
  {
    title: 'Reference Generator',
    description: 'Generate accurate citations in APA, Vancouver, and other formats. Paste a DOI or fill in source details and prepare references quickly.',
    path: '/tools/reference-generator',
    cta: 'Generate References',
    status: 'available',
  },
  {
    title: 'Journal Finder',
    description: 'Match manuscripts with journals using subject fit, publisher priority, case-report routing, open-access signals, APC budget, review speed, and saved shortlists.',
    path: '/tools/journal-finder',
    cta: 'Find Journals',
    status: 'available',
  },
  {
    title: 'ResRef Analyzer',
    description: 'Upload study data, confirm variables, run guided statistical tests, and generate a clean master analysis report.',
    path: '/tools/research-analyzer',
    cta: 'Analyze Data',
    status: 'available',
  },
];

export const FAQ_CATEGORIES = ['All', 'About the Platform', 'Research Database', 'Research Tools', 'Expert Consultation', 'Join Our Team', 'Technical'];

export const GUIDE_FAQS = [
  ['About the Platform', 'What is ResRef?', 'ResRef is a professional research reference platform that brings together validated questionnaires, methodology content, interactive tools, research opportunities, and expert support.'],
  ['About the Platform', 'Who is ResRef for?', 'ResRef is built for medical students, residents, clinicians, researchers, faculty members, and institutional research teams.'],
  ['About the Platform', 'Is ResRef free?', 'Core database browsing, tools, and expert consultation pathways are free for users. Future account features may add optional advanced access.'],
  ['Research Database', 'How do I find a questionnaire?', 'Use the database search bar to search by questionnaire name, topic, specialty, or keyword, then refine results using category filters.'],
  ['Research Database', 'Are resources peer-reviewed?', 'ResRef prioritizes validated and source-linked questionnaires and research materials. Users should still verify final use against their institution or journal requirements.'],
  ['Research Tools', 'What tools are available?', 'The current tool hub includes the Sample Size Calculator, Reference Generator, Journal Finder, and ResRef Analyzer.'],
  ['Research Tools', 'Are the tools free?', 'Yes. The research tools are designed as free support for students, clinicians, and researchers.'],
  ['Expert Consultation', 'Is consultation really free?', 'Yes. ResRef expert consultation is free for users at all research levels.'],
  ['Expert Consultation', 'How long does it take?', 'The team aims to respond within 48–72 hours depending on the request type and volume.'],
  ['Expert Consultation', 'What types of research do you support?', 'ResRef can support medical, health science, educational, public health, social, and related research projects.'],
  ['Join Our Team', 'What roles are available?', 'Open pathways include Education, Media, Design, IT, Data Entry, Quality Control, and Research Support roles.'],
  ['Join Our Team', 'Do I need experience?', 'Some roles are beginner-friendly, while others need specialized research, design, technology, or quality review experience.'],
  ['Technical', 'I found an error in a questionnaire. How do I report it?', 'Use the Contact Us page and include the resource title, link, and the correction or concern you noticed.'],
  ['Technical', "The website isn't loading. What should I do?", 'Refresh the page, check your connection, and contact ResRef if the issue continues. Include the page URL and a short description.'],
];

export const HOME_PILLARS = [
  ['Research Database', 'Browse 1,000+ validated questionnaires across 15+ specialties.', '/database'],
  ['Research Tools', 'Interactive calculators and generators built for real research workflows.', '/tools'],
  ['Expert Consultation', 'Get personalised guidance from our research team, free of charge.', '/consultation'],
  ['Research Opportunities', 'Discover open research positions and collaboration projects.', '/opportunities'],
];

export function slugifyCategory(name) {
  return name.toLowerCase().replace(/&/g, 'and').replace(/\//g, ' ').replace(/\([^)]*\)/g, '').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
}
