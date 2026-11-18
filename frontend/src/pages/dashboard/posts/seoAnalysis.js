/**
 * Search (SEO), answer-engine (AEO) and generative-engine (GEO) analysis for
 * the article editor.
 *
 * The same rules run on the server in backend/blog/seo_analysis.py, so the
 * dashboard overview and this real-time panel always agree. Both read the
 * shared cases in backend/blog/seo_analysis_cases.json in their tests: change
 * a rule in one file, change it in the other and refresh the cases.
 *
 * Thresholds follow published guidance rather than house rules:
 * - Yoast SEO's analysis (text length, keyphrase placement and density,
 *   subheading/paragraph/sentence length, transition words, passive voice,
 *   images, links, single H1). Cornerstone thresholds also follow Yoast.
 * - Google Search Central (title links and snippets, URL structure, image alt
 *   text, Article structured data, "who/how/why" people-first content).
 * - Featured-snippet research (SEMrush/Ahrefs): paragraph answers cluster
 *   around 40-60 words.
 * - "GEO: Generative Engine Optimization" (Aggarwal et al., KDD 2024): citing
 *   sources, adding statistics and quotations raised visibility in AI answers.
 *
 * Every check returns good / warn / bad (or na when it does not apply);
 * weights express how much the check matters within its group.
 */

export const ANALYSIS_VERSION = 1;
export const TITLE_SUFFIX = ' | ResRef';
export const GROUPS = [
  { key: 'seo', label: 'Search', short: 'SEO', description: 'Google and other search engines' },
  { key: 'readability', label: 'Readability', short: 'Read', description: 'Easy to scan and understand' },
  { key: 'aeo', label: 'Answers', short: 'AEO', description: 'Featured snippets, voice and direct answers' },
  { key: 'geo', label: 'AI visibility', short: 'GEO', description: 'Content AI search can trust, cite and surface' },
];
// Overall score: search stays the largest share, the other lenses split the rest.
export const GROUP_WEIGHTS = { seo: 0.4, readability: 0.2, aeo: 0.2, geo: 0.2 };

/* ------------------------------------------------------------------ check catalogue */
// target: element id the editor focuses when the user clicks "Fix".
export const CHECKS = [
  ['keyphrase', 'seo', 4, 'Focus keyphrase', 'article-field-keyphrase'],
  ['keyphrase_length', 'seo', 1, 'Keyphrase length', 'article-field-keyphrase'],
  ['keyphrase_in_title', 'seo', 3, 'Keyphrase in SEO title', 'article-field-seo-title'],
  ['keyphrase_in_description', 'seo', 2, 'Keyphrase in meta description', 'article-field-seo-description'],
  ['keyphrase_in_intro', 'seo', 2, 'Keyphrase in introduction', 'article-section-body'],
  ['keyphrase_in_slug', 'seo', 1, 'Keyphrase in URL', 'article-field-slug'],
  ['keyphrase_density', 'seo', 2, 'Keyphrase frequency', 'article-section-body'],
  ['keyphrase_in_subheadings', 'seo', 2, 'Keyphrase in subheadings', 'article-section-body'],
  ['keyphrase_in_alt', 'seo', 1, 'Keyphrase in image alt text', 'article-section-body'],
  ['seo_title', 'seo', 2, 'Dedicated SEO title', 'article-field-seo-title'],
  ['title_length', 'seo', 2, 'SEO title width', 'article-field-seo-title'],
  ['meta_description', 'seo', 3, 'Meta description', 'article-field-seo-description'],
  ['slug', 'seo', 1, 'URL slug', 'article-field-slug'],
  ['text_length', 'seo', 3, 'Text length', 'article-section-body'],
  ['single_h1', 'seo', 2, 'Single H1 title', 'article-section-body'],
  ['internal_links', 'seo', 2, 'Internal links', 'article-section-body'],
  ['outbound_links', 'seo', 1, 'Outbound links', 'article-section-body'],
  ['link_health', 'seo', 2, 'Link health', 'article-section-body'],
  ['featured_image', 'seo', 2, 'Featured image', 'article-section-media'],
  ['images', 'seo', 1, 'Images in the text', 'article-section-body'],
  ['image_alt', 'seo', 2, 'Image alt text', 'article-section-body'],
  ['subheading_distribution', 'readability', 2, 'Subheading distribution', 'article-section-body'],
  ['paragraph_length', 'readability', 2, 'Paragraph length', 'article-section-body'],
  ['sentence_length', 'readability', 2, 'Sentence length', 'article-section-body'],
  ['transition_words', 'readability', 1, 'Transition words', 'article-section-body'],
  ['passive_voice', 'readability', 1, 'Passive voice', 'article-section-body'],
  ['sentence_variety', 'readability', 1, 'Varied sentence openings', 'article-section-body'],
  ['reading_ease', 'readability', 1, 'Reading ease', 'article-section-body'],
  ['direct_answer', 'aeo', 3, 'Answer-first introduction', 'article-section-body'],
  ['questions', 'aeo', 2, 'Questions readers ask', 'article-section-body'],
  ['concise_answers', 'aeo', 2, 'Snippet-ready answers', 'article-section-body'],
  ['faq', 'aeo', 2, 'FAQ section', 'article-section-body'],
  ['lists_tables', 'aeo', 2, 'Lists and tables', 'article-section-body'],
  ['definition', 'aeo', 1, 'Clear definition', 'article-section-body'],
  ['citations', 'geo', 3, 'Cited sources', 'article-section-body'],
  ['source_quality', 'geo', 1, 'Authoritative sources', 'article-section-body'],
  ['statistics', 'geo', 2, 'Facts and figures', 'article-section-body'],
  ['quotations', 'geo', 1, 'Expert quotations', 'article-section-body'],
  ['author', 'geo', 2, 'Named contributors', 'article-section-taxonomy'],
  ['freshness', 'geo', 1, 'Publication and update dates', 'article-field-date'],
  ['sections', 'geo', 2, 'Self-contained sections', 'article-section-body'],
  ['summary', 'geo', 1, 'Summary or key takeaways', 'article-section-body'],
  ['topics', 'geo', 1, 'Topic signals', 'article-section-taxonomy'],
  ['excerpt', 'geo', 1, 'Summary excerpt', 'article-field-excerpt'],
  ['structured_data', 'geo', 1, 'Article structured data', 'article-section-media'],
].map(([id, group, weight, label, target]) => ({ id, group, weight, label, target }));
export const CHECK_BY_ID = Object.fromEntries(CHECKS.map(check => [check.id, check]));
const KEYPHRASE_CHECKS = new Set(['keyphrase_length', 'keyphrase_in_title', 'keyphrase_in_description', 'keyphrase_in_intro', 'keyphrase_in_slug', 'keyphrase_density', 'keyphrase_in_subheadings', 'keyphrase_in_alt']);

/* ------------------------------------------------------------------ word lists */
const STOP_WORDS = new Set('a an and are as at be but by for from has have how i if in into is it its of on or our so than that the their them there these this those to was we were what when where which who why will with you your can do does vs about after before over under between'.split(' '));
const QUESTION_STARTERS = new Set('what how why when where who whom whose which can could does do did is are should will would was were'.split(' '));
const TRANSITIONS = ['accordingly', 'additionally', 'afterwards', 'also', 'although', 'besides', 'because', 'consequently', 'conversely', 'finally', 'first', 'firstly', 'second', 'secondly', 'third', 'furthermore', 'hence', 'however', 'indeed', 'instead', 'likewise', 'meanwhile', 'moreover', 'nevertheless', 'nonetheless', 'otherwise', 'overall', 'similarly', 'specifically', 'subsequently', 'then', 'therefore', 'thus', 'ultimately', 'whereas', 'while', 'yet', 'for example', 'for instance', 'in addition', 'in contrast', 'in fact', 'in particular', 'in short', 'in summary', 'in conclusion', 'as a result', 'on the other hand', 'such as', 'to illustrate', 'that is', 'in other words', 'as well as', 'even though', 'due to', 'because of', 'above all', 'after all', 'by contrast', 'in turn', 'to summarize', 'notably', 'importantly'];
const IRREGULAR_PARTICIPLES = 'been begun bitten blown born borne bought brought built caught chosen done drawn driven eaten fallen felt found forgotten forgiven frozen given gone grown held hidden hit hurt kept known laid led left lent lost made meant met paid put read risen run said seen sent set shown shut sold spent spoken spread stolen struck sung taken taught thought thrown told understood withdrawn won worn written'.split(' ');
const PASSIVE_PATTERN = new RegExp(`\\b(?:am|is|are|was|were|be|been|being|get|gets|got|gotten)\\s+(?:\\w+ly\\s+)?(?:\\w+ed|${IRREGULAR_PARTICIPLES.join('|')})\\b`);
const SUMMARY_HEADINGS = ['key takeaways', 'key takeaway', 'takeaways', 'summary', 'conclusion', 'conclusions', 'tl dr', 'tldr', 'bottom line', 'final thoughts', 'in brief', 'key points', 'a word from', 'wrapping up'];
const DEFINITION_VERBS = new Set('is are was were refers means describes defined measures assesses evaluates represents involves'.split(' '));
const AUTHORITATIVE_HOSTS = ['doi.org', 'ncbi.nlm.nih.gov', 'nih.gov', 'who.int', 'cdc.gov', 'europepmc.org', 'cochranelibrary.com', 'nature.com', 'sciencedirect.com', 'springer.com', 'wiley.com', 'thelancet.com', 'nejm.org', 'bmj.com', 'jamanetwork.com', 'plos.org', 'frontiersin.org', 'tandfonline.com', 'sagepub.com', 'oup.com', 'cambridge.org', 'apa.org', 'elsevier.com', 'cell.com', 'science.org', 'pnas.org', 'arxiv.org', 'jstor.org', 'scholar.google.com'];

/* ------------------------------------------------------------------ text helpers */
const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', ndash: '–', mdash: '—', hellip: '…', rsquo: '’', lsquo: '‘', ldquo: '“', rdquo: '”', laquo: '«', raquo: '»', copy: '©', reg: '®', deg: '°', times: '×', middot: '·', bull: '•' };
const decode = value => value.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (match, code) => {
  if (code[0] === '#') {
    const number = code[1].toLowerCase() === 'x' ? parseInt(code.slice(2), 16) : parseInt(code.slice(1), 10);
    try { return String.fromCodePoint(number); } catch { return match; }
  }
  return ENTITIES[code.toLowerCase()] ?? match;
});
const INVISIBLE = /[​-‍﻿]/g;
const squash = value => String(value || '').replace(INVISIBLE, '').replace(/\s+/g, ' ').trim();
export const stripPlaceholders = value => squash(String(value || '').replace(/%{1,2}[a-z_]+%{1,2}/gi, '')).replace(/^[\s|:–—-]+|[\s|:–—-]+$/g, '').trim();

export function normalize(value) {
  return String(value || '').toLowerCase().normalize('NFKD').replace(/\p{M}/gu, '').replace(INVISIBLE, '').replace(/['’]/g, '').replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
}
export const tokens = value => { const text = normalize(value); return text ? text.split(' ') : []; };
export function stem(word) {
  if (word.length > 4 && word.endsWith('ies')) return `${word.slice(0, -3)}y`;
  if (word.length > 3 && word.endsWith('s') && !word.endsWith('ss')) return word.slice(0, -1);
  return word;
}
const contentWords = phrase => { const all = tokens(phrase); const kept = all.filter(word => !STOP_WORDS.has(word)); return (kept.length ? kept : all).map(stem); };
export const countWords = value => squash(value).split(' ').filter(word => /[\p{L}\p{N}]/u.test(word)).length;
const sentencesOf = text => squash(text).split(/(?<=[.!?؟])\s+/).filter(sentence => tokens(sentence).length);
const round = value => Math.round(value);
const pct = (part, whole) => (whole ? (part / whole) * 100 : 0);

/** 'exact' when the stemmed phrase appears contiguously, 'all' when every content word appears, else 'none'. */
export function phraseMatch(text, phrase) {
  const words = tokens(text).map(stem);
  const wanted = tokens(phrase).map(stem);
  if (!wanted.length || !words.length) return 'none';
  if (` ${words.join(' ')} `.includes(` ${wanted.join(' ')} `)) return 'exact';
  const present = new Set(words);
  return contentWords(phrase).every(word => present.has(word)) ? 'all' : 'none';
}
const matchesAny = (text, phrases) => phrases.some(phrase => phraseMatch(text, phrase) !== 'none');
function overlap(text, reference) {
  const wanted = Array.from(new Set(contentWords(text)));
  if (!wanted.length) return 1;
  const present = new Set(tokens(reference).map(stem));
  return wanted.filter(word => present.has(word)).length / wanted.length;
}

/** Suggest a keyphrase from the title: the part before a colon or dash, without "(abbreviations)", when short. */
export function suggestKeyphrase(title) {
  const head = squash((squash(title).split(/\s*[:|–—]\s*|\s+-\s+/)[0] || '').replace(/\([^)]*\)/g, ' '));
  return countWords(head) >= 1 && countWords(head) <= 6 ? head : '';
}

/* ------------------------------------------------------------------ HTML parsing */
// Mirrors seo.py's text extractor: block tags start a new text block, skipped
// tags are ignored, <br> splits blocks. Images and links are collected too.
const BLOCK_TAGS = new Set(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'blockquote', 'td', 'th', 'dt', 'dd', 'figcaption', 'div', 'section', 'br', 'tr']);
const SKIP_TAGS = new Set(['script', 'style', 'noscript', 'iframe', 'svg', 'button', 'form', 'select', 'textarea', 'template', 'object']);
const KEPT_TAGS = new Set(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']);
const CELL_TAGS = new Set(['td', 'th']);

function attributes(source) {
  const result = {};
  const pattern = /([^\s=/"'>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g;
  let match;
  while ((match = pattern.exec(source))) {
    const name = match[1].toLowerCase();
    if (!(name in result)) result[name] = match[2] ?? match[3] ?? match[4] ?? null;
    if (result[name] !== null) result[name] = decode(result[name]);
  }
  return result;
}

export function parseHtml(html) {
  const doc = { blocks: [], images: [], links: [], lists: 0, tables: 0, blockquotes: 0 };
  let buffer = []; let tag = 'p'; let skip = 0; let link = null;
  const flush = () => {
    const text = squash(buffer.join(''));
    if (text) doc.blocks.push({ tag, text });
    buffer = [];
  };
  const pattern = /<!--[\s\S]*?-->|<[!?][^>]*>|<(\/?)([a-zA-Z][a-zA-Z0-9]*)((?:"[^"]*"|'[^']*'|[^'">])*)>|([^<]+)|</g;
  let match;
  while ((match = pattern.exec(String(html || '')))) {
    const [raw, closing, rawName, rest, text] = match;
    if (text !== undefined || raw === '<') { if (!skip) { buffer.push(decode(text ?? raw)); if (link) link.text += decode(text ?? raw); } continue; }
    if (!rawName) continue; // comment, doctype or processing instruction
    const name = rawName.toLowerCase();
    const selfClosing = /\/\s*$/.test(rest || '');
    const start = () => {
      if (SKIP_TAGS.has(name)) { skip += 1; return; }
      if (skip) return;
      if (BLOCK_TAGS.has(name)) { flush(); tag = KEPT_TAGS.has(name) ? name : CELL_TAGS.has(name) ? 'cell' : 'p'; }
      if (name === 'ul' || name === 'ol') doc.lists += 1;
      if (name === 'table') doc.tables += 1;
      if (name === 'blockquote') doc.blockquotes += 1;
      if (name === 'img') { const attrs = attributes(rest); doc.images.push({ src: attrs.src || '', alt: squash(attrs.alt || '') }); }
      if (name === 'a') { const attrs = attributes(rest); if (attrs.href) { link = { href: attrs.href.trim(), rel: (attrs.rel || '').toLowerCase(), text: '', block: doc.blocks.length }; doc.links.push(link); } }
    };
    const end = () => {
      if (SKIP_TAGS.has(name)) { skip = Math.max(0, skip - 1); return; }
      if (skip) return;
      if (name === 'a') link = null;
      if (BLOCK_TAGS.has(name)) { flush(); tag = 'p'; }
    };
    if (closing) end(); else { start(); if (selfClosing) end(); }
  }
  flush();
  doc.links.forEach(item => { item.text = squash(item.text); });
  return doc;
}

/* ------------------------------------------------------------------ document facts */
const isHeading = block => /^h[1-6]$/.test(block.tag);
const headingLevel = block => Number(block.tag[1]);
const isQuestion = text => /[?؟]\s*$/.test(text) || QUESTION_STARTERS.has(tokens(text)[0]);
const hostOf = href => { try { return new URL(href).host.toLowerCase().replace(/^www\./, ''); } catch { return ''; } };

// Links to a development machine (e.g. WordPress exports pointing at resres.local) or with a malformed host
// ("https://doi:10.1037/…") are broken for readers and crawlers.
const DEV_HOST = /^(localhost|127\.0\.0\.1|\[::1\]|0\.0\.0\.0)(:\d+)?$|\.(local|localhost|test|invalid)(:\d+)?$/;
function classifyLink(href, siteHost) {
  const value = href.trim().toLowerCase();
  if (!value || value.startsWith('#') || /^(mailto|tel|javascript|data|sms|whatsapp):/.test(value)) return 'other';
  if (/^https?:\/\//.test(value) || value.startsWith('//')) {
    const host = hostOf(value.startsWith('//') ? `https:${value}` : value);
    if (host && (host === siteHost || host.endsWith(`.${siteHost}`))) return 'internal';
    return !host || DEV_HOST.test(host) ? 'broken' : 'external';
  }
  return 'internal';
}
const authoritative = host => /\.(gov|edu|int)$/.test(host) || /\.(gov|edu|ac)\.[a-z]{2}$/.test(host) || AUTHORITATIVE_HOSTS.some(item => host === item || host.endsWith(`.${item}`));

/** Section after a heading whose normalised text matches `test`, up to the next heading of the same or higher level. */
function findSection(blocks, test) {
  const index = blocks.findIndex(block => isHeading(block) && headingLevel(block) >= 2 && test(` ${normalize(block.text)} `));
  if (index < 0) return null;
  const level = headingLevel(blocks[index]);
  let end = index + 1;
  while (end < blocks.length && !(isHeading(blocks[end]) && headingLevel(blocks[end]) <= level)) end += 1;
  return { start: index, end, blocks: blocks.slice(index + 1, end) };
}

/** Question/answer pairs inside a "Frequently asked questions" section. */
export function extractFaq(blocks) {
  const section = findSection(blocks, text => text.includes(' faq') || text.includes(' frequently asked '));
  if (!section) return { found: false, items: [] };
  const items = [];
  let current = null;
  for (const block of section.blocks) {
    let text = block.text;
    let answer = '';
    const mark = text.search(/[?؟]/);
    const ends = /[?؟]\s*$/.test(text);
    // "Question? Answer…" on one line also counts, unless it continues an unanswered question.
    if (ends || (mark > 0 && countWords(text.slice(0, mark + 1)) <= 25 && (isHeading(block) || !current || current.answer))) {
      if (!ends) { answer = squash(text.slice(mark + 1)); text = text.slice(0, mark + 1); }
      const question = squash(text.replace(/^\s*(?:q(?:uestion)?\s*\d*\s*[:.)-]|\d+\s*[.)-])\s*/i, ''));
      current = { question, answer, first: answer };
      items.push(current);
    } else if (current) {
      current.answer = squash(`${current.answer} ${text}`);
      if (!current.first) current.first = text;
    }
  }
  return { found: true, items: items.filter(item => item.question && item.answer).map(item => ({ question: item.question, answer: item.answer.slice(0, 2000), first: item.first })) };
}

export function extractReferences(blocks, links) {
  const section = findSection(blocks, text => /^ (references?|sources?|bibliography|works cited|citations?|further reading|reference list|literature cited)\b/.test(text));
  if (!section) return { found: false, items: 0, links: [] };
  const inside = links.filter(link => link.block > section.start && link.block < section.end && /^https?:\/\//i.test(link.href));
  return { found: true, items: section.blocks.filter(block => countWords(block.text) >= 3).length, links: inside.map(link => link.href) };
}

function languageOf(text) {
  const arabic = (text.match(/[؀-ۿ]/g) || []).length;
  const latin = (text.match(/[a-z]/gi) || []).length;
  return arabic > latin ? 'ar' : 'en';
}

function syllables(word) {
  let value = word.toLowerCase().replace(/[^a-z]/g, '');
  if (!value) return 0;
  if (value.length <= 3) return 1;
  value = value.replace(/(?:[^laeiouy]es|ed|[^laeiouy]e)$/, '').replace(/^y/, '');
  return Math.max(1, (value.match(/[aeiouy]{1,2}/g) || []).length);
}

/** Measurements both implementations must agree on. */
export function measure(input) {
  const doc = parseHtml(input.content);
  const blocks = doc.blocks;
  const prose = blocks.filter(block => block.tag === 'p' || block.tag === 'li');
  const paragraphs = blocks.filter(block => block.tag === 'p');
  const bodyText = blocks.map(block => block.text).join(' ');
  const words = blocks.reduce((sum, block) => sum + countWords(block.text), 0);
  const sentences = prose.flatMap(block => sentencesOf(block.text));
  const headings = blocks.filter(block => isHeading(block) && headingLevel(block) >= 2);
  const subheadings = headings.filter(block => headingLevel(block) <= 3);
  const intro = paragraphs.find(block => countWords(block.text) >= 5)?.text || '';
  const siteHost = String(input.site_host || 'resref.com').toLowerCase().replace(/^www\./, '');
  const internal = doc.links.filter(link => classifyLink(link.href, siteHost) === 'internal');
  const external = doc.links.filter(link => classifyLink(link.href, siteHost) === 'external');
  const broken = doc.links.filter(link => classifyLink(link.href, siteHost) === 'broken');
  const externalHosts = Array.from(new Set(external.map(link => hostOf(link.href.startsWith('//') ? `https:${link.href}` : link.href)).filter(Boolean)));

  // Words between subheadings (the text before the first heading counts as a section).
  const sectionWords = [0];
  blocks.forEach(block => { if (isHeading(block)) sectionWords.push(0); else sectionWords[sectionWords.length - 1] += countWords(block.text); });

  const sentenceWords = sentences.map(countWords);
  const starts = sentences.map(sentence => tokens(sentence)[0] || '');
  let repeatedRuns = 0;
  for (let index = 0, run = 1; index < starts.length; index += 1) {
    run = index && starts[index] && starts[index] === starts[index - 1] ? run + 1 : 1;
    if (run === 3) repeatedRuns += 1;
  }
  const joined = sentences.map(sentence => ` ${tokens(sentence).join(' ')} `);
  // Transition words are measured in running paragraphs; list items and references are naturally terse.
  const paragraphSentences = paragraphs.flatMap(block => sentencesOf(block.text)).map(sentence => ` ${tokens(sentence).join(' ')} `);
  const flesch = (() => {
    const letterWords = sentences.flatMap(sentence => tokens(sentence)).filter(word => /[a-z]/.test(word));
    if (!sentences.length || !letterWords.length) return null;
    const syllableCount = letterWords.reduce((sum, word) => sum + syllables(word), 0);
    return 206.835 - 1.015 * (letterWords.length / sentences.length) - 84.6 * (syllableCount / letterWords.length);
  })();
  const questionHeadings = headings.filter(block => isQuestion(block.text));
  const faq = extractFaq(blocks);
  const references = extractReferences(blocks, doc.links);
  const answerAfter = index => { const next = blocks.slice(index + 1).find(block => !isHeading(block) || headingLevel(block) <= headingLevel(blocks[index])); return next && !isHeading(next) ? next.text : ''; };
  const answers = [
    ...blocks.map((block, index) => (isHeading(block) && headingLevel(block) >= 2 && isQuestion(block.text) ? answerAfter(index) : null)).filter(value => value !== null),
    ...faq.items.map(item => item.first),
  ];
  return {
    doc, blocks, intro, bodyText, words, sentences, headings, subheadings, paragraphs, internal, external, externalHosts, broken,
    language: languageOf(bodyText),
    h1: blocks.filter(block => block.tag === 'h1').length,
    maxSectionWords: Math.max(...sectionWords),
    longParagraphs: paragraphs.filter(block => countWords(block.text) > 150).length,
    veryLongParagraphs: paragraphs.filter(block => countWords(block.text) > 200).length,
    longSentencePct: pct(sentenceWords.filter(count => count > 20).length, sentences.length),
    transitionPct: pct(paragraphSentences.filter(text => TRANSITIONS.some(word => text.includes(` ${word} `))).length, paragraphSentences.length),
    paragraphSentences: paragraphSentences.length,
    passivePct: pct(joined.filter(text => PASSIVE_PATTERN.test(text)).length, sentences.length),
    repeatedRuns, flesch,
    questions: questionHeadings.length + faq.items.length,
    conciseAnswers: answers.filter(text => { const count = countWords(text); return count >= 20 && count <= 80; }).length,
    answerCount: answers.length,
    faq, references,
    statistics: sentences.concat(blocks.filter(block => block.tag === 'cell').map(block => block.text)).filter(text => /\d+(?:[.,]\d+)?\s?%|\d+\.\d+|\b\d{2,}\b/.test(text)).length,
    quotes: doc.blockquotes + (bodyText.match(/“[^”]{20,}”|"[^"]{20,}"/g) || []).length,
    summary: headings.some(block => SUMMARY_HEADINGS.some(phrase => ` ${normalize(block.text)} `.includes(` ${phrase} `))),
    authoritativeHosts: externalHosts.filter(authoritative).length,
  };
}

/* ------------------------------------------------------------------ rules */
const result = (status, message, fix = '') => ({ status, message, fix });
const NA = message => result('na', message);
const plural = (count, word, many = `${word}s`) => `${count.toLocaleString('en-US')} ${count === 1 ? word : many}`;

export function analyzeArticle(raw) {
  const input = { title: '', seo_title: '', seo_description: '', excerpt: '', slug: '', content: '', post_type: 'post', featured_image: '', categories: 0, tags: 0, contributors: 0, focus_keyphrase: '', related_keyphrases: [], cornerstone: false, ...raw };
  const facts = measure(input);
  const isPage = input.post_type === 'page';
  const now = input.now ? new Date(input.now) : new Date();
  const keyphrase = squash(input.focus_keyphrase);
  const synonyms = (input.related_keyphrases || []).map(squash).filter(Boolean).slice(0, 4);
  const phrases = [keyphrase, ...synonyms].filter(Boolean);
  const title = squash(input.title);
  const customTitle = stripPlaceholders(input.seo_title);
  const seoTitle = customTitle || title;
  const renderedTitle = `${seoTitle}${TITLE_SUFFIX}`;
  const description = stripPlaceholders(input.seo_description);
  const excerpt = squash(input.excerpt);
  const slug = String(input.slug || '').trim();
  const english = facts.language === 'en';
  const reference = [title, excerpt, facts.intro, ...facts.headings.map(block => block.text)].join(' ');
  const keyWords = keyphrase ? contentWords(keyphrase) : [];
  const out = {};

  /* --- search --- */
  out.keyphrase = keyphrase
    ? result('good', `Optimising for “${keyphrase}”${synonyms.length ? ` plus ${plural(synonyms.length, 'related keyphrase')}` : ''}.`)
    : result('bad', 'No focus keyphrase is set, so keyphrase checks cannot run.', 'Enter the main search query this article should rank and be cited for.');
  if (keyphrase) {
    const count = keyWords.length;
    out.keyphrase_length = count <= 4 ? result('good', `${plural(count, 'content word')} — focused.`)
      : count <= 8 ? result('warn', `${count} content words is long for a keyphrase.`, 'Aim for 1–4 content words; move extra terms into related keyphrases.')
        : result('bad', `${count} content words is too long to match real searches.`, 'Shorten the keyphrase to the core 1–4 words people actually search for.');
    const inTitle = phraseMatch(seoTitle, keyphrase);
    const titleStart = normalize(seoTitle).startsWith(normalize(keyphrase));
    out.keyphrase_in_title = inTitle === 'exact' && titleStart ? result('good', 'The SEO title starts with the keyphrase.')
      : inTitle !== 'none' ? result('warn', 'The keyphrase is in the SEO title, but not at the start.', 'Move the keyphrase towards the beginning of the SEO title; searchers scan the first words.')
        : result('bad', 'The SEO title does not contain the keyphrase.', 'Rewrite the SEO title so it includes the exact keyphrase, ideally at the start.');
    const descriptionText = description || excerpt;
    const descriptionHits = sentencesOf(descriptionText).filter(sentence => phraseMatch(sentence, keyphrase) !== 'none').length;
    out.keyphrase_in_description = !descriptionText ? result('bad', 'There is no meta description to check.', 'Write a meta description that uses the keyphrase once or twice.')
      : descriptionHits === 0 ? result('bad', 'The meta description does not mention the keyphrase.', 'Use the keyphrase in the meta description; Google bolds matching words in results.')
        : descriptionHits <= 2 ? result('good', 'The meta description uses the keyphrase.')
          : result('warn', `The keyphrase appears ${descriptionHits} times in the meta description.`, 'Use it once or twice; repeating it reads as spam.');
    const introMatch = facts.intro ? sentencesOf(facts.intro).some(sentence => matchesAny(sentence, phrases)) : false;
    out.keyphrase_in_intro = !facts.intro ? result('bad', 'The article has no introduction paragraph yet.', 'Open with a paragraph that names the keyphrase and answers the main question.')
      : introMatch ? result('good', 'The introduction mentions the keyphrase.')
        : matchesAny(facts.intro, phrases) ? result('warn', 'The keyphrase words are in the introduction, but not in one sentence.', 'Use the keyphrase together in one sentence of the first paragraph.')
          : result('bad', 'The first paragraph does not mention the keyphrase.', 'Mention the keyphrase in the first paragraph so readers and search engines see the topic straight away.');
    const slugWords = new Set(tokens(slug.replace(/-/g, ' ')).map(stem));
    const slugHits = keyWords.filter(word => slugWords.has(word)).length;
    out.keyphrase_in_slug = slugHits === keyWords.length ? result('good', 'The URL contains the keyphrase.')
      : slugHits ? result('warn', 'The URL contains only part of the keyphrase.', 'Include all keyphrase words in the slug, separated by hyphens.')
        : result('bad', 'The URL does not contain the keyphrase.', 'Edit the slug to include the keyphrase. Avoid changing slugs of published articles without a redirect.');
    const hits = facts.sentences.filter(sentence => phraseMatch(sentence, keyphrase) !== 'none').length;
    const density = pct(hits, facts.words);
    const minimum = Math.max(1, Math.ceil(facts.words * 0.005));
    out.keyphrase_density = !facts.words ? NA('Add body text to measure keyphrase use.')
      : density > 3 ? result('bad', `The keyphrase appears ${plural(hits, 'time')} (${density.toFixed(1)}%), above the 3% maximum.`, 'Replace some repetitions with synonyms or pronouns; over-use looks like keyword stuffing.')
        : hits >= minimum ? result('good', `The keyphrase appears ${plural(hits, 'time')} (${density.toFixed(1)}%).`)
          : result('warn', `The keyphrase appears ${plural(hits, 'time')}; aim for at least ${minimum} in a text of this length (0.5–3%).`, 'Use the keyphrase or its words naturally in a few more sentences.');
    const withKeyphrase = facts.subheadings.filter(block => matchesAny(block.text, phrases)).length;
    const share = pct(withKeyphrase, facts.subheadings.length);
    out.keyphrase_in_subheadings = !facts.subheadings.length ? NA('No H2/H3 subheadings yet.')
      : share > 75 ? result('warn', `${round(share)}% of subheadings repeat the keyphrase.`, 'Keep it in 30–75% of H2/H3 subheadings; vary the rest so they describe each section.')
        : share >= 30 || (withKeyphrase >= 1 && facts.subheadings.length < 4) ? result('good', `${plural(withKeyphrase, 'subheading')} of ${facts.subheadings.length} reflect the keyphrase.`)
          : withKeyphrase ? result('warn', `Only ${withKeyphrase} of ${facts.subheadings.length} subheadings reflect the keyphrase.`, 'Use the keyphrase or a related keyphrase in more H2/H3 subheadings (30–75%).')
            : result('bad', 'No subheading reflects the keyphrase.', 'Use the keyphrase or a related keyphrase in at least one H2 or H3.');
    const images = facts.doc.images;
    const altHits = images.filter(image => matchesAny(image.alt, phrases)).length;
    const altShare = pct(altHits, images.length);
    out.keyphrase_in_alt = !images.length ? NA('No images in the text.')
      : images.length < 5 ? (altHits ? result('good', 'An image alt text reflects the keyphrase.') : result('warn', 'No image alt text reflects the keyphrase.', 'Describe one relevant image using the keyphrase in its alt text.'))
        : altShare > 70 ? result('warn', `${round(altShare)}% of image alt texts repeat the keyphrase.`, 'Keep alt text descriptive; use the keyphrase in 30–70% of images.')
          : altShare >= 30 ? result('good', `${altHits} of ${images.length} image alt texts reflect the keyphrase.`)
            : result('warn', `Only ${altHits} of ${images.length} image alt texts reflect the keyphrase.`, 'Use the keyphrase in 30–70% of image alt texts where it describes the image.');
  } else {
    KEYPHRASE_CHECKS.forEach(id => { out[id] = NA('Set a focus keyphrase to run this check.'); });
  }

  out.seo_title = !customTitle ? result('warn', 'No custom SEO title; the article title is used.', 'Write an SEO title that leads with the keyphrase and fits the search result.')
    : overlap(customTitle, reference) < 0.3 ? result('bad', 'The SEO title does not match this article’s topic — it may have been copied from another article.', 'Rewrite the SEO title so it describes this article.')
      : result('good', 'A dedicated SEO title is set.');
  // Google truncates title links at about 600px, roughly 50–60 characters.
  const titleChars = renderedTitle.length;
  out.title_length = titleChars > 60 ? result('warn', `The search title is ${titleChars} characters including “${TITLE_SUFFIX.trim()}”; Google may cut it off after about 60.`, 'Shorten the SEO title so the important words come first.')
    : titleChars < 30 ? result('warn', `The search title is only ${titleChars} characters.`, 'Use the space: add a benefit or qualifier (e.g. “guide”, “scoring”, “examples”).')
      : result('good', `${titleChars} characters including “${TITLE_SUFFIX.trim()}” — fits the result.`);
  // Yoast: 120–156 characters; Google shows roughly 150–160 on desktop.
  out.meta_description = !description ? result('bad', excerpt ? 'No meta description; search engines will use the excerpt or page text.' : 'No meta description; search engines will pick text from the page.', 'Write a 120–156 character summary that answers the searcher’s question and includes the keyphrase.')
    : overlap(description, reference) < 0.3 && contentWords(description).length >= 5 ? result('bad', 'The meta description does not match this article’s topic — it may belong to another article.', 'Rewrite the meta description for this article.')
      : description.length > 156 ? result('warn', `${description.length} characters; Google may cut it after about 156.`, 'Trim the meta description to 120–156 characters.')
        : description.length < 120 ? result('warn', `${description.length} characters; there is room for more detail.`, 'Expand the meta description to 120–156 characters.')
          : result('good', `${description.length} characters — a complete snippet.`);
  out.slug = !slug ? result('bad', 'The URL slug is empty.', 'Add a short, descriptive slug.')
    : !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug) ? result('warn', 'The slug has capitals, underscores or other symbols.', 'Use lowercase words separated by hyphens.')
      : slug.length > 75 ? result('warn', `The slug is ${slug.length} characters long.`, 'Keep slugs short and readable (under 75 characters, a few key words).')
        : result('good', 'Short, readable URL.');
  // Yoast: 300+ words for posts and pages; 900+ for cornerstone content.
  const [goodWords, okWords] = input.cornerstone ? [900, 400] : [300, 250];
  out.text_length = facts.words >= goodWords ? result('good', `${plural(facts.words, 'word')}${input.cornerstone ? ' — enough for cornerstone content' : ''}.`)
    : facts.words >= okWords ? result('warn', `${plural(facts.words, 'word')}, slightly below the recommended ${goodWords}.`, `Add depth until the text reaches ${goodWords}+ words${input.cornerstone ? ' (cornerstone content)' : ''}.`)
      : result('bad', `${plural(facts.words, 'word')}, below the recommended ${goodWords}.`, `Expand the article to at least ${goodWords} words with useful detail, examples and sources.`);
  out.single_h1 = facts.h1 ? result('bad', `The text contains ${plural(facts.h1, 'H1 heading')}; the title is already the page’s H1.`, 'Change body headings to H2 or H3.') : result('good', 'Only the title is an H1.');
  out.internal_links = facts.internal.length ? result('good', `${plural(facts.internal.length, 'internal link')}.`)
    : result('bad', 'No links to other ResRef pages.', 'Link to related ResRef articles, tools or database pages so readers and crawlers find them.');
  out.outbound_links = facts.external.length ? result('good', `${plural(facts.external.length, 'outbound link')}.`)
    : result('warn', 'No links to external sources.', 'Link to the studies, guidelines or tools you mention.');
  out.link_health = !facts.doc.links.length ? NA('No links yet.')
    : facts.broken.length ? result('bad', `${plural(facts.broken.length, 'link')} point${facts.broken.length === 1 ? 's' : ''} to a development or malformed address (e.g. ${facts.broken[0].href.slice(0, 60)}).`, 'Fix them: use the live resref.com address or a relative link (/database/…), and https://doi.org/… for DOIs. Readers and crawlers cannot open these links.')
      : result('good', 'No broken development or malformed links.');
  out.featured_image = input.featured_image ? result('good', 'A featured image is set for results, social shares and Discover.')
    : result('bad', 'No featured image.', 'Add a featured image (ideally 1200px wide or more) — Google uses it for Article results and Discover.');
  out.images = facts.doc.images.length ? result('good', `${plural(facts.doc.images.length, 'image')} in the text.`)
    : result('warn', 'There are no images in the text.', 'Add a figure, diagram or table image that explains a key point.');
  const missingAlt = facts.doc.images.filter(image => !image.alt).length;
  out.image_alt = !facts.doc.images.length ? NA('No images in the text.')
    : !missingAlt ? result('good', 'Every image has alt text.')
      : missingAlt === facts.doc.images.length ? result('bad', 'No image has alt text.', 'Describe each image in its alt text for accessibility and Google Images.')
        : result('warn', `${plural(missingAlt, 'image')} without alt text.`, 'Add alt text that describes each image.');

  /* --- readability --- */
  out.subheading_distribution = facts.words <= 300 && !facts.headings.length ? result('good', 'Short text; subheadings are optional.')
    : facts.maxSectionWords > 350 ? result('bad', `A section runs ${facts.maxSectionWords} words without a subheading.`, 'Break long sections with H2/H3 subheadings at least every 300 words.')
      : facts.maxSectionWords > 300 ? result('warn', `A section runs ${facts.maxSectionWords} words without a subheading.`, 'Add a subheading so no section is longer than 300 words.')
        : result('good', 'Subheadings are well distributed.');
  out.paragraph_length = facts.veryLongParagraphs ? result('bad', `${plural(facts.veryLongParagraphs, 'paragraph')} over 200 words.`, 'Split long paragraphs; keep them under 150 words.')
    : facts.longParagraphs ? result('warn', `${plural(facts.longParagraphs, 'paragraph')} over 150 words.`, 'Split paragraphs longer than 150 words.')
      : facts.paragraphs.length ? result('good', 'Paragraphs are a comfortable length.') : NA('No paragraphs yet.');
  out.sentence_length = !facts.sentences.length ? NA('No sentences yet.')
    : facts.longSentencePct > 35 ? result('bad', `${round(facts.longSentencePct)}% of sentences are longer than 20 words.`, 'Shorten or split sentences until no more than 25% exceed 20 words.')
      : facts.longSentencePct > 25 ? result('warn', `${round(facts.longSentencePct)}% of sentences are longer than 20 words.`, 'Aim for no more than 25% of sentences above 20 words.')
        : result('good', `${round(facts.longSentencePct)}% of sentences are long — easy to follow.`);
  const englishOnly = message => (english ? null : NA(`${message} is measured for English text only.`));
  out.transition_words = englishOnly('Transition-word use') || (facts.paragraphSentences < 5 ? NA('Too few sentences to measure.')
    : facts.transitionPct >= 30 ? result('good', `${round(facts.transitionPct)}% of sentences use transition words.`)
      : facts.transitionPct >= 20 ? result('warn', `${round(facts.transitionPct)}% of sentences use transition words.`, 'Connect ideas with words like “however”, “for example” or “as a result” (aim for 30%).')
        : result('bad', `Only ${round(facts.transitionPct)}% of sentences use transition words.`, 'Link sentences with transition words so the argument is easy to follow (aim for 30%).'));
  out.passive_voice = englishOnly('Passive voice') || (!facts.sentences.length ? NA('No sentences yet.')
    : facts.passivePct > 15 ? result('bad', `${round(facts.passivePct)}% of sentences use the passive voice.`, 'Rewrite some sentences actively (“researchers measured…” instead of “was measured”); aim for 10% or less.')
      : facts.passivePct > 10 ? result('warn', `${round(facts.passivePct)}% of sentences use the passive voice.`, 'Aim for no more than 10% passive sentences.')
        : result('good', `${round(facts.passivePct)}% passive sentences.`));
  out.sentence_variety = !facts.sentences.length ? NA('No sentences yet.')
    : facts.repeatedRuns ? result('warn', `${plural(facts.repeatedRuns, 'run')} of 3+ sentences start with the same word.`, 'Vary how consecutive sentences begin.')
      : result('good', 'Sentence openings are varied.');
  // Flesch reading ease. Yoast targets 60+ for general audiences; ResRef
  // writes for researchers and clinicians, so 50+ (college level) is good and
  // below 30 (very difficult) is flagged.
  out.reading_ease = englishOnly('Reading ease') || (facts.flesch === null || facts.sentences.length < 5 ? NA('Too little text to score.')
    : facts.flesch >= 50 ? result('good', `Flesch reading ease ${round(facts.flesch)} — clear for a professional audience.`)
      : facts.flesch >= 30 ? result('warn', `Flesch reading ease ${round(facts.flesch)} — fairly difficult.`, 'Use shorter sentences and plainer words where precision allows.')
        : result('bad', `Flesch reading ease ${round(facts.flesch)} — very difficult.`, 'Simplify: shorter sentences, fewer long words, explain jargon once.'));

  if (facts.words < 50) ['subheading_distribution', 'paragraph_length', 'sentence_length', 'transition_words', 'passive_voice', 'sentence_variety', 'reading_ease'].forEach(id => { out[id] = NA('Write at least 50 words to measure readability.'); });

  /* --- answers (AEO) --- */
  const introWords = countWords(facts.intro);
  // Featured-snippet paragraphs average 40–60 words.
  out.direct_answer = !facts.intro ? result('bad', 'There is no opening paragraph to use as a direct answer.', 'Start with a 40–60 word paragraph that directly answers the main question.')
    : introWords >= 40 && introWords <= 60 ? result('good', `The opening paragraph is ${introWords} words — snippet length.`)
      : introWords >= 25 && introWords <= 100 ? result('warn', `The opening paragraph is ${introWords} words.`, 'Make the first paragraph a self-contained 40–60 word answer; move detail to the next paragraph.')
        : result('bad', `The opening paragraph is ${introWords} words — ${introWords < 25 ? 'too short to answer the question' : 'too long to be quoted as an answer'}.`, 'Rewrite the opening as a 40–60 word direct answer to the main question.');
  const wantQuestions = facts.words >= 600 ? 2 : 1;
  out.questions = facts.questions >= wantQuestions ? result('good', `${plural(facts.questions, 'question')} that match how people search and ask voice assistants.`)
    : facts.questions ? result('warn', `${plural(facts.questions, 'question')} found.`, 'Phrase more subheadings or FAQ entries as the questions readers ask (“What is…?”, “How do you…?”).')
      : result(facts.words >= 600 ? 'bad' : 'warn', 'No question-style subheadings or FAQ questions.', 'Add H2/H3 subheadings phrased as real questions, each answered directly underneath.');
  out.concise_answers = !facts.answerCount ? NA('No questions to answer yet.')
    : facts.conciseAnswers / facts.answerCount >= 0.5 ? result('good', `${facts.conciseAnswers} of ${facts.answerCount} questions are answered in 20–80 words right below.`)
      : facts.conciseAnswers ? result('warn', `Only ${facts.conciseAnswers} of ${facts.answerCount} questions have a concise answer right below.`, 'Answer each question in 20–80 words immediately after it, then add detail.')
        : result('bad', 'Questions are not followed by a concise answer.', 'Put a 20–80 word answer directly under each question.');
  out.faq = facts.faq.items.length >= 2 ? result('good', `${plural(facts.faq.items.length, 'FAQ question')} detected — published as FAQ structured data.`)
    : facts.faq.found ? result('warn', `The FAQ section has ${plural(facts.faq.items.length, 'recognisable question')}.`, 'Write each FAQ question on its own line ending with “?”, followed by its answer.')
      : result('warn', 'No FAQ section.', 'Add a “Frequently Asked Questions” H2 with 3–5 real questions and short answers.');
  const structured = facts.doc.lists + facts.doc.tables;
  out.lists_tables = facts.words < 300 ? NA('Short text; lists are optional.')
    : structured ? result('good', `${plural(facts.doc.lists, 'list')}${facts.doc.tables ? ` and ${plural(facts.doc.tables, 'table')}` : ''} — easy to lift into list and table snippets.`)
      : result('warn', 'No lists or tables.', 'Present steps, criteria or comparisons as a list or table.');
  const subject = keyphrase || suggestKeyphrase(title);
  const firstSentence = sentencesOf(facts.intro)[0] || '';
  const definesSubject = subject && phraseMatch(firstSentence, subject) !== 'none';
  out.definition = !facts.intro || !subject ? NA('Add an introduction and keyphrase to check.')
    : definesSubject && tokens(firstSentence).some(word => DEFINITION_VERBS.has(word)) ? result('good', 'The first sentence defines the topic.')
      : result('warn', 'The first sentence does not define the topic.', `Open with a plain definition, e.g. “${subject} is …”, which answer engines quote directly.`);

  /* --- AI visibility (GEO) --- */
  const refs = facts.references;
  out.citations = (refs.found && (refs.items >= 3 || refs.links.length >= 1)) || facts.externalHosts.length >= 3
    ? result('good', refs.found ? `A references section with ${plural(refs.items, 'entry', 'entries')}.` : `Cites ${plural(facts.externalHosts.length, 'external source')}.`)
    : refs.found || facts.external.length ? result('warn', 'Few sources are cited.', 'Add a “References” section that links to the studies and guidelines behind your claims.')
      : result('bad', 'No sources are cited.', 'Cite your sources with links and a “References” section; AI answer engines favour verifiable content.');
  out.source_quality = !facts.external.length ? NA('No outbound links yet.')
    : facts.authoritativeHosts ? result('good', `Links to ${plural(facts.authoritativeHosts, 'authoritative source')} (DOI, journals, .gov/.edu).`)
      : result('warn', 'No links to journals, DOIs or official bodies.', 'Prefer DOI links, journal pages and official (.gov, .edu, WHO) sources.');
  out.statistics = facts.statistics >= 3 ? result('good', `${plural(facts.statistics, 'sentence')} with concrete figures.`)
    : result('warn', facts.statistics ? `Only ${plural(facts.statistics, 'sentence')} with figures.` : 'No statistics or figures.', 'Add specific numbers (sample sizes, percentages, years, scores) with their source.');
  out.quotations = facts.quotes ? result('good', `${plural(facts.quotes, 'quotation')}.`)
    : result('warn', 'No quotations.', 'Quote an expert, guideline or original paper (use a blockquote) to add authority.');
  out.author = isPage ? NA('Pages do not show contributor credits.')
    : input.contributors ? result('good', `${plural(input.contributors, 'credited contributor')} — shown as the article’s authors.`)
      : result('bad', 'No contributor is credited.', 'Credit the author, editor or reviewer so readers and AI systems can see who stands behind the content.');
  const updated = input.updated_at ? new Date(input.updated_at) : now;
  const ageDays = (now - updated) / 864e5;
  out.freshness = !input.published_at ? result(isPage ? 'warn' : 'bad', 'No publication date.', 'Set a publication date; it is published as datePublished.')
    : ageDays > 365 ? result('warn', `Last updated ${Math.floor(ageDays / 30)} months ago.`, 'Review facts and references, then save to publish an updated dateModified.')
      : result('good', 'Dated and recently updated.');
  const h2 = facts.blocks.filter(block => block.tag === 'h2').length;
  out.sections = facts.words >= 600 ? (h2 >= 3 ? result('good', `${plural(h2, 'H2 section')} that AI systems can quote on their own.`) : h2 ? result('warn', `Only ${plural(h2, 'H2 section')} for ${plural(facts.words, 'word')}.`, 'Split the article into clearly titled H2 sections, each covering one idea.') : result('bad', 'No H2 sections.', 'Organise the text into H2 sections with descriptive titles.'))
    : h2 ? result('good', 'Organised into sections.') : result('warn', 'No H2 sections.', 'Add at least one H2 section heading.');
  out.summary = facts.summary ? result('good', 'Includes a summary or conclusion section.')
    : result('warn', 'No summary, conclusion or key takeaways section.', 'End with “Key takeaways” or a short conclusion that restates the main answer.');
  out.topics = isPage ? NA('Pages do not use categories and tags.')
    : input.categories && input.tags ? result('good', 'Category and tags describe the topic.')
      : input.categories || input.tags ? result('warn', input.categories ? 'No tags yet.' : 'No category yet.', 'Add a category and 2–5 specific tags; they are published as articleSection and keywords.')
        : result('bad', 'No category or tags.', 'Choose a category and add specific tags.');
  out.excerpt = excerpt.length >= 70 ? result('good', 'A summary excerpt is set (used in cards and llms.txt).')
    : excerpt ? result('warn', `The excerpt is only ${excerpt.length} characters.`, 'Write a 1–2 sentence summary (70+ characters).')
      : result('bad', 'No excerpt.', 'Write a 1–2 sentence summary; it appears in cards, llms.txt and as a fallback description.');
  const missing = [!input.featured_image && 'image', !input.published_at && 'datePublished', !isPage && !input.contributors && 'author', title.length > 110 && 'headline ≤ 110 characters'].filter(Boolean);
  out.structured_data = isPage ? NA('Pages publish WebPage structured data.')
    : missing.length ? result('warn', `Article schema is missing: ${missing.join(', ')}.`, 'Fill in the missing fields so the Article markup is complete.')
      : result('good', 'Article schema has headline, image, dates and author.');

  /* --- scoring --- */
  const checks = CHECKS.map(check => ({ ...check, ...out[check.id] }));
  const scores = scoreChecks(checks.map(check => [check.id, check.status]));
  return {
    version: ANALYSIS_VERSION, language: facts.language, words: facts.words, scores, checks,
    faq: facts.faq.items.map(({ question, answer }) => ({ question, answer })),
    references: facts.references.links,
    suggestion: keyphrase ? '' : suggestKeyphrase(title),
    rendered_title: renderedTitle,
    schema: [isPage ? 'WebPage' : 'Article', facts.faq.items.length >= 2 && 'FAQPage', 'BreadcrumbList'].filter(Boolean),
  };
}

const POINTS = { good: 1, warn: 0.5, bad: 0 };
/** Weighted group scores (0–100) from [id, status] pairs; na checks are left out. */
export function scoreChecks(pairs) {
  const totals = {};
  pairs.forEach(([id, status]) => {
    const check = CHECK_BY_ID[id];
    if (!check || !(status in POINTS)) return;
    const group = totals[check.group] || (totals[check.group] = { earned: 0, possible: 0 });
    group.earned += check.weight * POINTS[status];
    group.possible += check.weight;
  });
  const scores = {};
  GROUPS.forEach(({ key }) => { scores[key] = totals[key]?.possible ? round((100 * totals[key].earned) / totals[key].possible) : null; });
  const used = GROUPS.filter(({ key }) => scores[key] !== null);
  const share = used.reduce((sum, { key }) => sum + GROUP_WEIGHTS[key], 0);
  scores.overall = share ? round(used.reduce((sum, { key }) => sum + scores[key] * GROUP_WEIGHTS[key], 0) / share) : null;
  return scores;
}

// Lighthouse-style bands.
export const scoreBand = score => (score === null || score === undefined ? 'none' : score >= 80 ? 'good' : score >= 50 ? 'ok' : 'poor');
export const BAND_LABELS = { good: 'Good', ok: 'Needs work', poor: 'Poor', none: 'Not scored' };

/** Editor record → analyzer input. */
export function analysisInput(editing, { now, siteHost } = {}) {
  const settings = editing.seo_settings || {};
  return {
    title: editing.title, seo_title: editing.seo_title, seo_description: editing.seo_description, excerpt: editing.excerpt,
    slug: editing.slug, content: editing.content, post_type: editing.post_type, featured_image: editing.featured_image,
    published_at: editing.published_at, updated_at: editing.updated_at, categories: (editing.categories || []).length,
    tags: (editing.tags || []).length, contributors: (editing.contributors || []).length,
    focus_keyphrase: settings.focus_keyphrase || '', related_keyphrases: settings.related_keyphrases || [], cornerstone: Boolean(settings.cornerstone),
    now, site_host: siteHost,
  };
}
