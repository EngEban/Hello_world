export const CITATION_STYLES = [
  ['vancouver', 'Vancouver'],
  ['apa', 'APA 7'],
  ['mla', 'MLA 9'],
  ['chicago', 'Chicago (Author-Date)'],
  ['ieee', 'IEEE'],
  ['harvard', 'Harvard'],
  ['ama', 'AMA'],
  ['turabian', 'Turabian (Author-Date)'],
  ['acs', 'ACS'],
  ['nature', 'Nature'],
];

// Numbered styles keep the list order; the others are sorted by author.
export const NUMERIC_STYLES = ['vancouver', 'ieee', 'ama', 'acs', 'nature'];

export const SOURCE_TYPES = [
  ['journal', 'Journal Article'],
  ['book', 'Book'],
  ['chapter', 'Book Chapter'],
  ['report', 'Report'],
  ['website', 'Website'],
];

export const FIELDS_BY_TYPE = {
  journal: [['title', 'Title', true], ['journal', 'Journal', true], ['journal_abbrev', 'Journal abbreviation'], ['year', 'Year', true], ['volume', 'Volume'], ['issue', 'Issue'], ['pages', 'Pages'], ['doi', 'DOI'], ['pmid', 'PMID'], ['url', 'URL'], ['authors_text', 'Authors', true]],
  book: [['title', 'Title', true], ['publisher', 'Publisher', true], ['year', 'Year', true], ['edition', 'Edition'], ['isbn', 'ISBN'], ['doi', 'DOI'], ['url', 'URL'], ['authors_text', 'Authors', true]],
  chapter: [['title', 'Chapter title', true], ['booktitle', 'Book title', true], ['editors', 'Editors'], ['publisher', 'Publisher', true], ['year', 'Year', true], ['pages', 'Pages'], ['isbn', 'ISBN'], ['doi', 'DOI'], ['url', 'URL'], ['authors_text', 'Authors', true]],
  report: [['title', 'Title', true], ['org', 'Organization', true], ['year', 'Year', true], ['number', 'Report number'], ['url', 'URL'], ['authors_text', 'Authors']],
  website: [['title', 'Page title', true], ['site', 'Website', true], ['year', 'Year'], ['url', 'URL', true], ['accessed', 'Date accessed'], ['authors_text', 'Authors']],
};

// Italic text is wrapped in these markers; formatCitation strips them and
// citationHtml turns them into <i> for rich copy.
const IT_OPEN = '\u0001';
const IT_CLOSE = '\u0002';
const it = value => (clean(value) ? `${IT_OPEN}${clean(value)}${IT_CLOSE}` : '');
const stripMarks = value => String(value || '').replace(/[\u0001\u0002]/g, '');

const join = values => values.filter(Boolean).join(' ');
const clean = value => String(value || '').replace(/\s+/g, ' ').trim();
const pages = value => clean(value).replace(/^pp?\.?\s*/i, '').replace(/\s*[-–—]+\s*/g, '–');
const bareDoi = ref => clean(ref.doi).replace(/^https?:\/\/(?:dx\.)?doi\.org\//i, '').replace(/^doi:\s*/i, '');
const doiUrl = ref => (bareDoi(ref) ? `https://doi.org/${bareDoi(ref)}` : '');
const link = ref => doiUrl(ref) || clean(ref.url);
const title = value => clean(value).replace(/[.\s]+$/, '');
// Add a full stop unless the text already ends with punctuation.
const dot = value => {
  const text = clean(value);
  if (!text) return '';
  return /[.!?]$/.test(stripMarks(text)) ? text : `${text}.`;
};
const sentence = (...pieces) => pieces.map(dot).filter(Boolean).join(' ');
const quoted = (value, closing = '.') => {
  const text = title(value);
  if (!text) return '';
  return /[!?]$/.test(text) ? `"${text}"` : `"${text}${closing}"`;
};
const authorName = author => join([author.first, author.middle, author.last]);
// Single letters are initials and get a full stop ("J A" -> "J. A.").
const givenNames = author => join([author.first, author.middle].join(' ').split(/\s+/).filter(Boolean).map(part => (/^[A-Z]$/.test(part) ? `${part}.` : part)));
const initialsOf = (value, separator = ' ') => clean(value).split(/[\s.]+/).filter(Boolean).map(part => `${part[0].toUpperCase()}.`).join(separator);
const compactInitials = value => clean(value).split(/[\s.]+/).filter(Boolean).map(part => part[0].toUpperCase()).join('');
const editionText = value => {
  const text = clean(value);
  if (!/^\d+$/.test(text)) return text;
  const n = Number(text);
  const suffix = n % 100 >= 11 && n % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th');
  return `${n}${suffix}`;
};
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function accessedText(value, style) {
  const match = clean(value).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return clean(value);
  const [, year, month, day] = match;
  const name = MONTHS[Number(month) - 1] || '';
  const short = name.slice(0, 3);
  const d = Number(day);
  if (style === 'vancouver') return `${year} ${short} ${d}`;
  if (style === 'mla') return `${d} ${name.length > 4 ? `${short}.` : name} ${year}`;
  if (style === 'harvard') return `${d} ${name} ${year}`;
  if (style === 'ieee') return `${name.length > 4 ? `${short}.` : name} ${d}, ${year}`;
  if (style === 'acs') return `${year}-${month}-${day}`;
  return `${name} ${d}, ${year}`;
}

// Authors -------------------------------------------------------------------

const isOrg = author => !clean(author.first) && !clean(author.middle);
const ORG_WORDS = /\b(organi[sz]ation|ministry|association|society|group|institute|council|committee|department|university|agency|cent(?:er|re)|foundation|collaboration|consortium|network|board|commission|office|federation|college|trust|programme|program|alliance|service)s?\b/i;

export function parseAuthors(value = '') {
  let names = String(value).split(/;|\n/).map(name => name.trim()).filter(Boolean);
  // "Smith JA, Doe B, Lee C" (Vancouver style) is split on commas.
  if (names.length === 1 && names[0].includes(',')) {
    const parts = names[0].split(',').map(part => part.trim()).filter(Boolean);
    if (parts.length > 1 && parts.every(part => /^[\p{L}'’-]+(?:\s[\p{L}'’-]+)*\s[A-Z]{1,3}$/u.test(part))) names = parts;
  }
  return names
    .filter(name => !/^et\.?\s*al\.?$/i.test(name))
    .map(name => name.replace(/,?\s*et\.?\s*al\.?$/i, '').trim())
    .filter(Boolean)
    .map(name => {
      // Organisations ("World Health Organization") are kept whole.
      if (!name.includes(',') && /\s/.test(name) && ORG_WORDS.test(name)) return { first: '', middle: '', last: name };
      if (name.includes(',')) {
        const [last, ...rest] = name.split(',');
        const parts = rest.join(',').trim().split(/\s+/).filter(Boolean);
        return { first: parts.shift() || '', middle: parts.join(' '), last: last.trim() };
      }
      const parts = name.split(/\s+/).filter(Boolean);
      if (parts.length === 1) return { first: '', middle: '', last: parts[0] };
      // "Smith JA": surname followed by initials.
      const tail = parts.at(-1);
      if (/^[A-Z]{1,3}$/.test(tail) && parts.length >= 2) {
        const letters = tail.split('');
        return { first: letters[0], middle: letters.slice(1).join(' '), last: parts.slice(0, -1).join(' ') };
      }
      return { first: parts.shift() || '', middle: parts.slice(0, -1).join(' '), last: parts.pop() || '' };
    });
}

export function authorsToText(authors = []) {
  return authors.map(authorName).filter(Boolean).join('; ');
}

function list(values, { separator = ', ', last = ', and ', two = ' and ' } = {}) {
  if (values.length <= 1) return values[0] || '';
  if (values.length === 2) return values.join(two);
  return `${values.slice(0, -1).join(separator)}${last}${values.at(-1)}`;
}

const invertedInitials = author => (isOrg(author) ? author.last : `${author.last}, ${initialsOf(givenNames(author))}`);

const AUTHOR_FORMATS = {
  vancouver: authors => {
    const values = authors.map(author => (isOrg(author) ? author.last : join([author.last, compactInitials(givenNames(author))])));
    return values.length > 6 ? `${values.slice(0, 6).join(', ')}, et al` : values.join(', ');
  },
  ama: authors => {
    const values = authors.map(author => (isOrg(author) ? author.last : join([author.last, compactInitials(givenNames(author))])));
    return values.length > 6 ? `${values.slice(0, 3).join(', ')}, et al` : values.join(', ');
  },
  apa: authors => {
    const values = authors.map(invertedInitials);
    if (values.length > 20) return `${values.slice(0, 19).join(', ')}, . . . ${values.at(-1)}`;
    return list(values, { last: ', & ', two: ', & ' });
  },
  mla: authors => {
    if (!authors.length) return '';
    const firstAuthor = isOrg(authors[0]) ? authors[0].last : `${authors[0].last}, ${givenNames(authors[0])}`;
    if (authors.length === 1) return firstAuthor;
    if (authors.length === 2) return `${firstAuthor}, and ${authorName(authors[1])}`;
    return `${firstAuthor}, et al.`;
  },
  chicago: authors => {
    const values = authors.map((author, index) => (isOrg(author) ? author.last : index === 0 ? `${author.last}, ${givenNames(author)}` : join([givenNames(author), author.last])));
    if (values.length > 10) return `${values.slice(0, 7).join(', ')}, et al.`;
    return list(values);
  },
  harvard: authors => list(authors.map(author => (isOrg(author) ? author.last : `${author.last}, ${initialsOf(givenNames(author), '')}`)), { last: ' and ' }),
  ieee: authors => {
    const values = authors.map(author => (isOrg(author) ? author.last : join([initialsOf(givenNames(author)), author.last])));
    if (values.length > 6) return `${values[0]} et al.`;
    return list(values);
  },
  acs: authors => authors.map(invertedInitials).join('; '),
  nature: authors => {
    const values = authors.map(invertedInitials);
    if (values.length > 5) return `${values[0]} et al.`;
    return list(values, { last: ' & ', two: ' & ' });
  },
};
AUTHOR_FORMATS.turabian = AUTHOR_FORMATS.chicago;

const authorsFor = (ref, style) => (AUTHOR_FORMATS[style] || AUTHOR_FORMATS.vancouver)(ref.authors || []);
const editorCount = ref => clean(ref.editors).split(/;|\band\b|&/).filter(part => part.trim()).length;
const editorsList = ref => clean(ref.editors).split(/;/).map(part => part.trim()).filter(Boolean).join(', ');

// Journal articles ----------------------------------------------------------

function formatJournal(ref, style) {
  const au = authorsFor(ref, style);
  const t = title(ref.title);
  const full = title(ref.journal);
  const abbrev = title(ref.journal_abbrev) || full;
  const vol = clean(ref.volume);
  const iss = clean(ref.issue);
  const pg = pages(ref.pages);
  const year = clean(ref.year);
  const doi = bareDoi(ref);
  const url = link(ref);
  const pmid = clean(ref.pmid);

  if (style === 'apa') {
    const source = [it(full), vol ? it(vol) + (iss ? `(${iss})` : '') : '', pg].filter(Boolean).join(', ');
    return join([au ? dot(au) : '', `(${year || 'n.d.'}).`, dot(t), dot(source), url]);
  }
  if (style === 'mla') {
    const source = [it(full), vol && `vol. ${vol}`, iss && `no. ${iss}`, year, pg && `pp. ${pg}`].filter(Boolean).join(', ');
    return join([au ? dot(au) : '', quoted(t), dot(source), doi ? `https://doi.org/${doi}.` : (url ? dot(url) : '')]);
  }
  if (style === 'chicago' || style === 'turabian') {
    const source = join([it(full), vol, iss && `(${iss})`]) + (pg ? `: ${pg}` : '');
    return join([au ? dot(au) : '', year ? dot(year) : 'n.d.', quoted(t), dot(source), url ? dot(url) : '']);
  }
  if (style === 'harvard') {
    const source = [it(full), vol ? `${vol}${iss ? `(${iss})` : ''}` : '', pg && `pp. ${pg}`].filter(Boolean).join(', ');
    return join([au, `(${year || 'no date'})`, `'${t}',`, dot(source), url ? `Available at: ${url}.` : '']);
  }
  if (style === 'ieee') {
    const source = [it(abbrev), vol && `vol. ${vol}`, iss && `no. ${iss}`, pg && `pp. ${pg}`, year].filter(Boolean).join(', ');
    return `${au ? `${au}, ` : ''}${/[!?]$/.test(t) ? `"${t}"` : `"${t},"`} ${source}${doi ? `, doi: ${doi}` : ''}.`;
  }
  if (style === 'acs') {
    const source = `${it(abbrev)}${year ? ` ${year}` : ''}${vol ? `, ${it(vol)}` : ''}${iss ? ` (${iss})` : ''}${pg ? `, ${pg}` : ''}`;
    return join([au ? dot(au) : '', dot(t), dot(source), doi ? `DOI: ${doi}.` : '']);
  }
  if (style === 'nature') {
    const source = `${it(abbrev)}${vol ? ` ${vol}` : ''}${pg ? `, ${pg}` : ''}${year ? ` (${year})` : ''}`;
    return join([au ? dot(au) : '', dot(t), dot(source)]);
  }
  // Vancouver (NLM) and AMA.
  const date = `${year}${vol ? `;${vol}` : ''}${iss ? `(${iss})` : ''}${pg ? `:${pg}` : ''}`;
  const journalName = style === 'ama' ? it(abbrev) : abbrev;
  const doiPart = doi ? (style === 'vancouver' ? `doi:${doi}.` : `doi:${doi}`) : '';
  return join([sentence(au, t, journalName, date), doiPart, style === 'vancouver' && pmid ? `PMID: ${pmid}.` : '', !doi && url ? `Available from: ${url}` : '']);
}

// Books, chapters, reports and websites -------------------------------------

function formatBook(ref, style) {
  const au = authorsFor(ref, style);
  const t = title(ref.title);
  const ed = editionText(ref.edition);
  const pub = title(ref.publisher);
  const year = clean(ref.year);
  const url = link(ref);
  if (style === 'apa') return join([au ? dot(au) : '', `(${year || 'n.d.'}).`, dot(`${it(t)}${ed ? ` (${ed} ed.)` : ''}`), dot(pub), url]);
  if (style === 'mla') return join([au ? dot(au) : '', dot(it(t)), dot([ed && `${ed} ed.`, pub, year].filter(Boolean).join(', '))]);
  if (style === 'chicago' || style === 'turabian') return join([au ? dot(au) : '', year ? dot(year) : 'n.d.', dot(it(t)), ed ? `${ed} ed.` : '', dot(pub)]);
  if (style === 'harvard') return join([au, `(${year || 'no date'})`, dot(it(t)), ed ? `${ed} edn.` : '', dot(pub)]);
  if (style === 'ieee') return `${au ? `${au}, ` : ''}${[it(t), ed && `${ed} ed`, pub, year].filter(Boolean).join(', ')}.`;
  if (style === 'acs') return join([au ? dot(au) : '', `${it(t)}${ed ? `, ${ed} ed.` : ''};`, `${[pub, year].filter(Boolean).join(', ')}.`]);
  if (style === 'nature') return join([au ? dot(au) : '', it(t), `(${[pub, year].filter(Boolean).join(', ')}).`]);
  return join([sentence(au, style === 'ama' ? it(t) : t, ed && `${ed} ed`), `${[pub, year].filter(Boolean).join('; ')}.`]);
}

function formatChapter(ref, style) {
  const au = authorsFor(ref, style);
  const t = title(ref.title);
  const book = title(ref.booktitle);
  const eds = editorsList(ref);
  const many = editorCount(ref) > 1;
  const pub = title(ref.publisher);
  const year = clean(ref.year);
  const pg = pages(ref.pages);
  if (style === 'apa') return join([au ? dot(au) : '', `(${year || 'n.d.'}).`, dot(t), `In ${eds ? `${eds} (${many ? 'Eds.' : 'Ed.'}), ` : ''}${it(book)}${pg ? ` (pp. ${pg})` : ''}.`, dot(pub), link(ref)]);
  if (style === 'mla') return join([au ? dot(au) : '', quoted(t), dot([it(book), eds && `edited by ${eds}`, pub, year, pg && `pp. ${pg}`].filter(Boolean).join(', '))]);
  if (style === 'chicago' || style === 'turabian') return join([au ? dot(au) : '', year ? dot(year) : 'n.d.', quoted(t), dot(`In ${[it(book), eds && `edited by ${eds}`, pg].filter(Boolean).join(', ')}`), dot(pub)]);
  if (style === 'harvard') return join([au, `(${year || 'no date'})`, `'${t}', in`, eds ? `${eds} (${many ? 'eds' : 'ed.'})` : '', dot(it(book)), dot([pub, pg && `pp. ${pg}`].filter(Boolean).join(', '))]);
  if (style === 'ieee') return `${au ? `${au}, ` : ''}"${t}," in ${[it(book), eds && `${eds}, ${many ? 'Eds.' : 'Ed.'}`, pub, year, pg && `pp. ${pg}`].filter(Boolean).join(', ')}.`;
  if (style === 'nature') return join([au ? dot(au) : '', `in ${it(book)}`, eds ? `(ed${many ? 's' : ''}. ${eds})` : '', pg, `(${[pub, year].filter(Boolean).join(', ')}).`]);
  if (style === 'acs') return join([au ? dot(au) : '', dot(t), `In ${it(book)};`, eds ? `${eds}, ${many ? 'Eds.' : 'Ed.'};` : '', `${[pub, year].filter(Boolean).join(', ')}${pg ? `; pp ${pg}` : ''}.`]);
  return join([sentence(au, t), `In: ${eds ? `${eds}, ${many ? 'editors' : 'editor'}. ` : ''}${dot(style === 'ama' ? it(book) : book)}`, `${[pub, year].filter(Boolean).join('; ')}.`, pg ? `p. ${pg}.` : '']);
}

function formatReport(ref, style) {
  const au = authorsFor(ref, style);
  const t = title(ref.title);
  const org = title(ref.org);
  const year = clean(ref.year);
  const num = clean(ref.number);
  const url = clean(ref.url);
  const lead = au || org;
  if (style === 'apa') return join([dot(lead), `(${year || 'n.d.'}).`, dot(`${it(t)}${num ? ` (Report No. ${num})` : ''}`), au && org ? dot(org) : '', url]);
  if (style === 'harvard') return join([lead, `(${year || 'no date'})`, dot(it(t)), num ? `Report ${num}.` : '', au && org ? dot(org) : '', url ? `Available at: ${url}.` : '']);
  if (style === 'mla') return join([au ? dot(au) : '', dot(it(t)), num ? `Report ${num}.` : '', dot([org, year].filter(Boolean).join(', ')), url ? dot(url) : '']);
  if (style === 'chicago' || style === 'turabian') return join([dot(lead), year ? dot(year) : 'n.d.', dot(it(t)), num ? `Report ${num}.` : '', au && org ? dot(org) : '', url ? dot(url) : '']);
  if (style === 'ieee') return `${au ? `${au}, ` : ''}"${t}," ${[org, num && `Rep. ${num}`, year].filter(Boolean).join(', ')}.${url ? ` [Online]. Available: ${url}` : ''}`;
  return join([sentence(lead, t, au ? org : '', [year, num && `Report No.: ${num}`].filter(Boolean).join('. ')), url ? `Available from: ${url}` : '']);
}

function formatWebsite(ref, style) {
  const au = authorsFor(ref, style);
  const t = title(ref.title);
  const site = title(ref.site);
  const year = clean(ref.year);
  const url = clean(ref.url);
  const acc = accessedText(ref.accessed, style);
  if (style === 'apa') return join([dot(au || site), `(${year || 'n.d.'}).`, dot(it(t)), au && site ? dot(site) : '', url]);
  if (style === 'mla') return join([au ? dot(au) : '', quoted(t), `${[it(site), year, url.replace(/^https?:\/\//, '')].filter(Boolean).join(', ')}.`, acc ? `Accessed ${acc}.` : '']);
  if (style === 'chicago' || style === 'turabian') return join([dot(au || site), year ? dot(year) : 'n.d.', quoted(t), au ? dot(site) : '', acc ? `Accessed ${acc}.` : '', url ? dot(url) : '']);
  if (style === 'harvard') return join([au || site, `(${year || 'no date'})`, dot(it(t)), url ? `Available at: ${url}` : '', acc ? `(Accessed: ${acc}).` : '']);
  if (style === 'ieee') return `${au ? `${au}, ` : ''}"${t}," ${it(site)}.${acc ? ` Accessed: ${acc}.` : ''} [Online]. Available: ${url}`;
  if (style === 'ama') return join([au ? dot(au) : '', dot(t), dot(it(site)), year ? `Published ${year}.` : '', acc ? `Accessed ${acc}.` : '', url]);
  if (style === 'acs') return join([au ? dot(au) : '', dot(t), dot(site), `${url}${acc ? ` (accessed ${acc})` : ''}.`]);
  if (style === 'nature') return join([au ? dot(au) : '', dot(t), it(site), url, year ? `(${year}).` : '']);
  return join([dot(au || site), `${t} [Internet].`, `${[au ? site : '', year].filter(Boolean).join('; ')}${acc ? ` [cited ${acc}]` : ''}.`, url ? `Available from: ${url}` : '']);
}

function formatMarked(ref, style) {
  if (ref.type === 'website') return formatWebsite(ref, style);
  if (ref.type === 'book') return formatBook(ref, style);
  if (ref.type === 'chapter') return formatChapter(ref, style);
  if (ref.type === 'report') return formatReport(ref, style);
  return formatJournal(ref, style);
}

const tidy = value => String(value || '').replace(/\s+/g, ' ').replace(/\s+([.,;:])/g, '$1').replace(/\.{2,}/g, '.').replace(/,\s*\./g, '.').trim();

export function formatCitation(ref, style = 'vancouver') {
  if (!ref) return '';
  return stripMarks(tidy(formatMarked(ref, style)));
}

const escapeHtml = value => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

export function citationHtml(ref, style = 'vancouver') {
  if (!ref) return '';
  return escapeHtml(tidy(formatMarked(ref, style))).replace(/\u0001/g, '<i>').replace(/\u0002/g, '</i>');
}

// Bibliography order and numbering ------------------------------------------

const sortKey = ref => {
  const first = (ref.authors || [])[0];
  const lead = first ? first.last : (ref.org || ref.site || ref.title);
  return `${clean(lead).toLowerCase()} ${clean(ref.year)} ${clean(ref.title).toLowerCase()}`;
};

export function orderReferences(references, style = 'vancouver') {
  if (NUMERIC_STYLES.includes(style)) return [...references];
  return [...references].sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
}

export function numberLabel(style, index) {
  if (style === 'ieee') return `[${index + 1}]`;
  if (style === 'acs') return `(${index + 1})`;
  return NUMERIC_STYLES.includes(style) ? `${index + 1}.` : '';
}

export function bibliographyEntries(references, style = 'vancouver') {
  return orderReferences(references, style).map((reference, index) => {
    const label = numberLabel(style, index);
    return {
      reference,
      text: `${label ? `${label} ` : ''}${formatCitation(reference, style)}`,
      html: `${label ? `${label} ` : ''}${citationHtml(reference, style)}`,
    };
  });
}

// In-text citations ----------------------------------------------------------

const SUPERSCRIPT = { 0: '⁰', 1: '¹', 2: '²', 3: '³', 4: '⁴', 5: '⁵', 6: '⁶', 7: '⁷', 8: '⁸', 9: '⁹' };

export function formatInText(ref, style = 'vancouver', index = 0) {
  if (style === 'ieee') return `[${index + 1}]`;
  if (style === 'vancouver') return `(${index + 1})`;
  if (NUMERIC_STYLES.includes(style)) return String(index + 1).split('').map(digit => SUPERSCRIPT[digit]).join('');
  const authors = ref.authors || [];
  const year = clean(ref.year) || (style === 'harvard' ? 'no date' : 'n.d.');
  const names = authors.map(author => author.last).filter(Boolean);
  const fallback = clean(ref.org || ref.site) || `“${title(ref.title).split(' ').slice(0, 4).join(' ')}”`;
  let who;
  if (!names.length) who = fallback;
  else if (style === 'apa') who = names.length === 1 ? names[0] : names.length === 2 ? `${names[0]} & ${names[1]}` : `${names[0]} et al.`;
  else if (style === 'mla') who = names.length === 1 ? names[0] : names.length === 2 ? `${names[0]} and ${names[1]}` : `${names[0]} et al.`;
  else if (style === 'chicago' || style === 'turabian') who = names.length <= 3 ? list(names) : `${names[0]} et al.`;
  else who = names.length === 1 ? names[0] : names.length === 2 ? `${names[0]} and ${names[1]}` : `${names[0]} et al.`;
  if (style === 'mla') return `(${who})`;
  if (style === 'chicago' || style === 'turabian') return `(${who} ${year})`;
  return `(${who}, ${year})`;
}

// Checks ---------------------------------------------------------------------

export function validateReference(ref) {
  const fields = FIELDS_BY_TYPE[ref.type] || FIELDS_BY_TYPE.journal;
  return fields.filter(([, , required]) => required).map(([field, label]) => {
    const value = field === 'authors_text' ? ref.authors : ref[field];
    return Array.isArray(value) ? (value.length ? '' : label) : (clean(value) ? '' : label);
  }).filter(Boolean);
}

// Problems that do not block a citation but are worth fixing.
export function referenceWarnings(ref) {
  const warnings = [];
  const year = clean(ref.year);
  if (year && (!/^\d{4}[a-z]?$/.test(year) || Number(year.slice(0, 4)) > new Date().getFullYear() + 1)) warnings.push('Year should be four digits, like 2024.');
  if (clean(ref.doi) && !/^10\.\d{4,9}\/\S+$/i.test(bareDoi(ref))) warnings.push('The DOI looks incomplete. It should start with 10. and contain a slash.');
  if (clean(ref.url) && !/^https?:\/\/\S+\.\S+/i.test(clean(ref.url))) warnings.push('The link should start with https://.');
  if (clean(ref.pmid) && !/^\d{1,9}$/.test(clean(ref.pmid))) warnings.push('A PMID contains digits only.');
  const t = clean(ref.title);
  if (t.length > 12 && t === t.toUpperCase() && /[A-Z]/.test(t)) warnings.push('The title is in capital letters. Most styles expect normal capitalisation.');
  // Whole words only, so names such as "Tsvetalina" or "Metalidis" are not mistaken for "et al.".
  if ((ref.authors || []).some(author => /\bet(\.\s*|\s+)al\b/i.test(authorName(author)))) warnings.push('Remove "et al." from the authors; the style adds it when needed.');
  if (ref.type === 'journal' && !clean(ref.volume) && !clean(ref.pages) && !clean(ref.doi)) warnings.push('Add the volume and pages, or a DOI, so readers can find the article.');
  return warnings;
}

export function createBlankReference(type = 'journal') {
  return { type, title: '', journal: '', journal_abbrev: '', publisher: '', site: '', booktitle: '', editors: '', org: '', number: '', edition: '', year: '', volume: '', issue: '', pages: '', doi: '', pmid: '', isbn: '', url: '', accessed: '', authors: [] };
}
