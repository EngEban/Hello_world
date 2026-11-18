import { createBlankReference, parseAuthors } from './citationStyles.js';

const clean = value => String(value || '').replace(/\r?\n/g, ' ').replace(/\s+/g, ' ').trim();
const pages = value => clean(value).replace(/^pp?\.?\s*/i, '').replace(/\s*[-–—]+\s*/g, '-');
const bibValue = value => clean(value).replace(/[{}]/g, '').replace(/([&%$#_])/g, '\\$1');
const year = value => clean(value).match(/\d{4}/)?.[0] || '';
const authorName = author => [author.first, author.middle].filter(Boolean).join(' ');

function bibKey(ref, index) {
  const author = ref.authors?.[0]?.last || 'reference';
  return `${author}${ref.year || ''}${index + 1}`.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '');
}

// Export ---------------------------------------------------------------------

export function toBibTeX(ref, index = 0) {
  const type = { journal: 'article', book: 'book', chapter: 'incollection', report: 'techreport', website: 'misc' }[ref.type] || 'misc';
  const fields = {
    author: (ref.authors || []).map(author => (author.first || author.middle ? `${author.last}, ${authorName(author)}` : `{${author.last}}`)).join(' and '),
    title: ref.title,
    journal: ref.journal,
    booktitle: ref.booktitle,
    editor: ref.editors ? ref.editors.split(';').map(name => name.trim()).filter(Boolean).join(' and ') : '',
    publisher: ref.publisher,
    institution: ref.org,
    howpublished: ref.type === 'website' ? ref.site : '',
    year: ref.year,
    volume: ref.volume,
    number: ref.issue || ref.number,
    pages: pages(ref.pages).replace('-', '--'),
    edition: ref.edition,
    isbn: ref.isbn,
    doi: ref.doi,
    pmid: ref.pmid,
    url: ref.url,
    urldate: ref.accessed,
  };
  const lines = Object.entries(fields).filter(([, value]) => value).map(([key, value]) => {
    // Author lists keep the braces that protect organisation names.
    const text = key === 'author' ? clean(value).replace(/([&%$#_])/g, '\\$1') : bibValue(value);
    return `  ${key} = {${text}}`;
  });
  return `@${type}{${bibKey(ref, index)},\n${lines.join(',\n')}\n}`;
}

function risType(type) {
  return { journal: 'JOUR', book: 'BOOK', chapter: 'CHAP', report: 'RPRT', website: 'ELEC' }[type] || 'GEN';
}

export function toRIS(ref) {
  const lines = [`TY  - ${risType(ref.type)}`];
  (ref.authors || []).forEach(author => lines.push(`AU  - ${author.first || author.middle ? `${author.last}, ${authorName(author)}` : author.last}`));
  (ref.editors || '').split(';').map(name => name.trim()).filter(Boolean).forEach(name => lines.push(`ED  - ${name}`));
  if (ref.year) lines.push(`PY  - ${ref.year}`);
  if (ref.title) lines.push(`TI  - ${clean(ref.title)}`);
  if (ref.journal) lines.push(`T2  - ${clean(ref.journal)}`);
  if (ref.journal_abbrev) lines.push(`J2  - ${clean(ref.journal_abbrev)}`);
  if (ref.booktitle) lines.push(`T2  - ${clean(ref.booktitle)}`);
  if (ref.site) lines.push(`T2  - ${clean(ref.site)}`);
  if (ref.publisher || ref.org) lines.push(`PB  - ${clean(ref.publisher || ref.org)}`);
  if (ref.volume) lines.push(`VL  - ${clean(ref.volume)}`);
  if (ref.issue) lines.push(`IS  - ${clean(ref.issue)}`);
  if (ref.number) lines.push(`M1  - ${clean(ref.number)}`);
  if (ref.edition) lines.push(`ET  - ${clean(ref.edition)}`);
  const [startPage, endPage] = pages(ref.pages).split('-');
  if (startPage) lines.push(`SP  - ${startPage}`);
  if (endPage) lines.push(`EP  - ${endPage}`);
  if (ref.isbn) lines.push(`SN  - ${clean(ref.isbn)}`);
  if (ref.doi) lines.push(`DO  - ${clean(ref.doi)}`);
  if (ref.pmid) lines.push(`AN  - ${clean(ref.pmid)}`);
  if (ref.url) lines.push(`UR  - ${clean(ref.url)}`);
  if (ref.accessed) lines.push(`Y2  - ${clean(ref.accessed)}`);
  lines.push('ER  - ');
  return lines.join('\n');
}

const CSL_TYPES = { journal: 'article-journal', book: 'book', chapter: 'chapter', report: 'report', website: 'webpage' };

export function toCslJson(references) {
  return JSON.stringify(references.map(ref => {
    const item = { id: ref.id, type: CSL_TYPES[ref.type] || 'article' };
    if (ref.title) item.title = ref.title;
    if (ref.authors?.length) item.author = ref.authors.map(author => (author.first || author.middle ? { family: author.last, given: authorName(author) } : { literal: author.last }));
    if (ref.editors) item.editor = ref.editors.split(';').map(name => name.trim()).filter(Boolean).map(name => ({ literal: name }));
    const container = ref.journal || ref.booktitle || ref.site;
    if (container) item['container-title'] = container;
    if (ref.journal_abbrev) item['container-title-short'] = ref.journal_abbrev;
    if (ref.publisher || ref.org) item.publisher = ref.publisher || ref.org;
    if (ref.year) item.issued = { 'date-parts': [[Number(year(ref.year)) || ref.year]] };
    if (ref.accessed) item.accessed = { raw: ref.accessed };
    ['volume', 'issue', 'edition', 'number'].forEach(field => { if (ref[field]) item[field] = ref[field]; });
    if (ref.pages) item.page = pages(ref.pages);
    if (ref.doi) item.DOI = ref.doi;
    if (ref.pmid) item.PMID = ref.pmid;
    if (ref.isbn) item.ISBN = ref.isbn;
    if (ref.url) item.URL = ref.url;
    return item;
  }), null, 2);
}

// Import ---------------------------------------------------------------------

const LATEX = [
  [/\\&/g, '&'], [/\\%/g, '%'], [/\\_/g, '_'], [/\\\$/g, '$'], [/\\#/g, '#'], [/--/g, '–'], [/~/g, ' '],
  [/\\["]\{?([aeiouAEIOU])\}?/g, (_, c) => ({ a: 'ä', e: 'ë', i: 'ï', o: 'ö', u: 'ü', A: 'Ä', E: 'Ë', I: 'Ï', O: 'Ö', U: 'Ü' }[c])],
  [/\\[']\{?([aeiouyAEIOUYcn])\}?/g, (_, c) => ({ a: 'á', e: 'é', i: 'í', o: 'ó', u: 'ú', y: 'ý', A: 'Á', E: 'É', I: 'Í', O: 'Ó', U: 'Ú', Y: 'Ý', c: 'ć', n: 'ń' }[c])],
  [/\\[`]\{?([aeiouAEIOU])\}?/g, (_, c) => ({ a: 'à', e: 'è', i: 'ì', o: 'ò', u: 'ù', A: 'À', E: 'È', I: 'Ì', O: 'Ò', U: 'Ù' }[c])],
  [/\\\^\{?([aeiouAEIOU])\}?/g, (_, c) => ({ a: 'â', e: 'ê', i: 'î', o: 'ô', u: 'û', A: 'Â', E: 'Ê', I: 'Î', O: 'Ô', U: 'Û' }[c])],
  [/\\~\{?([nNaoAO])\}?/g, (_, c) => ({ n: 'ñ', N: 'Ñ', a: 'ã', o: 'õ', A: 'Ã', O: 'Õ' }[c])],
  [/\\c\{?([cC])\}?/g, (_, c) => (c === 'c' ? 'ç' : 'Ç')],
  [/\\ss\b\{?\}?/g, 'ß'],
  [/\\textendash\b\{?\}?/g, '–'], [/\\textemdash\b\{?\}?/g, '—'],
];

function delatex(value) {
  let text = String(value || '');
  LATEX.forEach(([pattern, replacement]) => { text = text.replace(pattern, replacement); });
  return clean(text.replace(/[{}]/g, ''));
}

// Reads one BibTeX value starting at `start`: {nested {braces}}, "quoted" or bare.
function readBibValue(text, start) {
  let index = start;
  while (/\s/.test(text[index] || '')) index += 1;
  const opener = text[index];
  if (opener === '{' || opener === '"') {
    let depth = 0;
    for (let cursor = index; cursor < text.length; cursor += 1) {
      const char = text[cursor];
      if (char === '\\') { cursor += 1; continue; }
      if (char === '{') depth += 1;
      else if (char === '}') depth -= 1;
      if (opener === '{' && depth === 0) return [text.slice(index + 1, cursor), cursor + 1];
      if (opener === '"' && char === '"' && cursor > index && depth === 0) return [text.slice(index + 1, cursor), cursor + 1];
    }
    return [text.slice(index + 1), text.length];
  }
  const match = text.slice(index).match(/^[^,}\n]*/);
  return [match[0].trim(), index + match[0].length];
}

const BIB_TYPES = {
  article: 'journal', book: 'book', booklet: 'book', inbook: 'chapter', incollection: 'chapter', inproceedings: 'chapter', conference: 'chapter',
  techreport: 'report', report: 'report', phdthesis: 'report', mastersthesis: 'report', thesis: 'report',
  misc: 'website', online: 'website', electronic: 'website', www: 'website', webpage: 'website',
};

export function parseBibTeX(text) {
  const records = [];
  const entryPattern = /@(\w+)\s*\{\s*([^,\s]*)\s*,/g;
  let match;
  while ((match = entryPattern.exec(text))) {
    const kind = match[1].toLowerCase();
    if (['comment', 'preamble', 'string'].includes(kind)) continue;
    const ref = createBlankReference(BIB_TYPES[kind] || 'website');
    let cursor = entryPattern.lastIndex;
    while (cursor < text.length) {
      const fieldMatch = text.slice(cursor).match(/^\s*([A-Za-z][\w-]*)\s*=\s*/);
      if (!fieldMatch) break;
      const key = fieldMatch[1].toLowerCase();
      const [raw, end] = readBibValue(text, cursor + fieldMatch[0].length);
      cursor = end;
      const value = key === 'author' || key === 'editor' ? clean(raw) : delatex(raw);
      if (key === 'author') ref.authors = parseBibNames(raw);
      else if (key === 'editor') ref.editors = parseBibNames(raw).map(author => [author.first, author.middle, author.last].filter(Boolean).join(' ')).join('; ');
      else if (key === 'journal' || key === 'journaltitle') ref.journal = value;
      else if (key === 'shortjournal') ref.journal_abbrev = value;
      else if (key === 'number') ref[ref.type === 'report' ? 'number' : 'issue'] = value;
      else if (key === 'institution' || key === 'school' || key === 'organization') ref.org = ref.org || value;
      else if (key === 'howpublished' && ref.type === 'website') ref.site = value.replace(/^\\url/, '');
      else if (key === 'date') ref.year = ref.year || year(value);
      else if (key === 'year') ref.year = year(value) || value;
      else if (key === 'urldate') ref.accessed = value;
      else if (key === 'url') ref.url = clean(raw);
      else if (key === 'doi') ref.doi = clean(raw);
      else if (['title', 'booktitle', 'publisher', 'volume', 'pages', 'edition', 'isbn', 'pmid'].includes(key)) ref[key] = value;
      cursor = (text.slice(cursor).match(/^\s*,?/) || [''])[0].length + cursor;
    }
    entryPattern.lastIndex = cursor;
    if (ref.type === 'report' && !ref.org && ref.publisher) ref.org = ref.publisher;
    if (ref.type === 'website' && !ref.site && ref.url) ref.site = hostOf(ref.url);
    if (ref.title) records.push(ref);
  }
  return records;
}

function parseBibNames(raw) {
  return raw.split(/\s+and\s+/i).map(name => name.trim()).filter(Boolean).map(name => {
    // {World Health Organization} is a single organisation name.
    if (/^\{[^{}]+\}$/.test(name)) return { first: '', middle: '', last: delatex(name) };
    return parseAuthors(delatex(name))[0];
  }).filter(Boolean);
}

const hostOf = url => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return ''; } };

const RIS_TYPES = {
  JOUR: 'journal', JFULL: 'journal', MGZN: 'journal', NEWS: 'journal', EJOUR: 'journal', ABST: 'journal',
  BOOK: 'book', EBOOK: 'book', EDBOOK: 'book',
  CHAP: 'chapter', ECHAP: 'chapter', CONF: 'chapter', CPAPER: 'chapter',
  RPRT: 'report', THES: 'report', GOVDOC: 'report',
  ELEC: 'website', WEB: 'website', BLOG: 'website', DATA: 'website',
};

export function parseRIS(text) {
  const records = [];
  let ref = null;
  let startPage = '';
  let endPage = '';
  let container = '';
  const push = () => {
    if (!ref) return;
    ref.pages = startPage && endPage ? `${startPage}-${endPage}` : startPage;
    if (container) {
      if (ref.type === 'chapter') ref.booktitle = ref.booktitle || container;
      else if (ref.type === 'website') ref.site = ref.site || container;
      else if (ref.type === 'journal') ref.journal = ref.journal || container;
    }
    if (ref.type === 'report' && !ref.org) ref.org = ref.publisher;
    if (ref.title) records.push(ref);
    ref = null;
    startPage = '';
    endPage = '';
    container = '';
  };
  text.replace(/^﻿/, '').split(/\r?\n/).forEach(line => {
    const match = line.match(/^([A-Z][A-Z0-9])\s{1,2}-\s?(.*)$/);
    if (!match) return;
    const [, tag, rawValue] = match;
    const value = rawValue.trim();
    if (tag === 'TY') {
      push();
      ref = createBlankReference(RIS_TYPES[value.toUpperCase()] || 'website');
      return;
    }
    if (tag === 'ER') {
      push();
      return;
    }
    if (!ref || !value) return;
    if (['AU', 'A1'].includes(tag)) ref.authors.push(...parseAuthors(value.includes(',') ? value : value.replace(/,/g, '')));
    else if (['ED', 'A2', 'A3'].includes(tag)) ref.editors = [ref.editors, value].filter(Boolean).join('; ');
    else if (['TI', 'T1'].includes(tag) && !ref.title) ref.title = value;
    else if (['T2', 'BT'].includes(tag)) container = container || value;
    else if (['JO', 'JF'].includes(tag)) ref.journal = value;
    else if (['JA', 'J2'].includes(tag)) ref.journal_abbrev = value;
    else if (tag === 'PB') ref.publisher = value;
    else if (['PY', 'Y1', 'DA'].includes(tag)) ref.year = ref.year || year(value);
    else if (tag === 'Y2') ref.accessed = value;
    else if (tag === 'VL') ref.volume = value;
    else if (['IS', 'CP'].includes(tag)) ref.issue = value;
    else if (tag === 'M1' && ref.type === 'report') ref.number = value;
    else if (tag === 'ET') ref.edition = value;
    else if (tag === 'SP') startPage = value;
    else if (tag === 'EP') endPage = value;
    else if (tag === 'SN' && /^[\d-]{10,17}[\dX]?$/i.test(value.split(/\s/)[0])) ref.isbn = value.split(/\s/)[0];
    else if (tag === 'DO') ref.doi = value;
    else if (tag === 'AN' && /^\d{5,9}$/.test(value)) ref.pmid = value;
    else if (tag === 'UR' && !ref.url) ref.url = value;
  });
  push();
  return records;
}

// PubMed "MEDLINE" export (.nbib / .txt from "Send to: Citation manager").
export function parseMedline(text) {
  const records = [];
  let fields = null;
  let lastTag = '';
  const push = () => {
    if (!fields) return;
    const get = tag => (fields[tag] || [])[0] || '';
    const ref = createBlankReference(/book/i.test((fields.PT || []).join(' ')) ? 'book' : 'journal');
    ref.title = get('TI').replace(/\.$/, '');
    ref.journal = get('JT');
    ref.journal_abbrev = get('TA');
    ref.year = year(get('DP'));
    ref.volume = get('VI');
    ref.issue = get('IP');
    ref.pages = get('PG');
    ref.pmid = get('PMID');
    const ids = [...(fields.LID || []), ...(fields.AID || [])];
    ref.doi = (ids.find(id => /\[doi\]/.test(id)) || '').replace(/\s*\[doi\]/, '');
    const names = (fields.FAU || []).length ? fields.FAU : (fields.AU || []);
    ref.authors = names.flatMap(name => parseAuthors(name));
    if ((fields.CN || []).length) ref.authors.push(...fields.CN.map(name => ({ first: '', middle: '', last: name })));
    ref.url = ref.doi ? `https://doi.org/${ref.doi}` : (ref.pmid ? `https://pubmed.ncbi.nlm.nih.gov/${ref.pmid}/` : '');
    if (ref.title) records.push(ref);
    fields = null;
  };
  text.replace(/^﻿/, '').split(/\r?\n/).forEach(line => {
    const match = line.match(/^([A-Z]{2,4})\s*-\s(.*)$/);
    if (match) {
      const [, tag, value] = match;
      if (tag === 'PMID') { push(); fields = {}; }
      if (!fields) return;
      fields[tag] = [...(fields[tag] || []), value.trim()];
      lastTag = tag;
    } else if (fields && /^\s{6}\S/.test(line) && lastTag) {
      const values = fields[lastTag];
      values[values.length - 1] = `${values[values.length - 1]} ${line.trim()}`;
    }
  });
  push();
  return records;
}

const CSL_TO_TYPE = { 'article-journal': 'journal', article: 'journal', 'article-magazine': 'journal', 'article-newspaper': 'journal', book: 'book', chapter: 'chapter', 'paper-conference': 'chapter', report: 'report', thesis: 'report', webpage: 'website', 'post-weblog': 'website', dataset: 'website' };

export function parseCslJson(text) {
  let data;
  try { data = JSON.parse(text); } catch { return []; }
  const items = Array.isArray(data) ? data : (Array.isArray(data?.items) ? data.items : [data]);
  return items.filter(item => item && typeof item === 'object').map(item => {
    const ref = createBlankReference(CSL_TO_TYPE[item.type] || 'journal');
    ref.title = clean(item.title);
    const container = clean(Array.isArray(item['container-title']) ? item['container-title'][0] : item['container-title']);
    if (ref.type === 'chapter') ref.booktitle = container;
    else if (ref.type === 'website') ref.site = container;
    else ref.journal = container;
    ref.journal_abbrev = clean(item['container-title-short'] || item.journalAbbreviation);
    ref.publisher = clean(item.publisher);
    if (ref.type === 'report') ref.org = ref.publisher;
    const issued = item.issued?.['date-parts']?.[0]?.[0] || item.issued?.raw || item.issued?.literal;
    ref.year = year(issued);
    ['volume', 'issue', 'edition', 'number'].forEach(field => { if (item[field]) ref[field] = clean(item[field]); });
    ref.pages = clean(item.page);
    ref.doi = clean(item.DOI);
    ref.pmid = clean(item.PMID);
    ref.isbn = clean(item.ISBN).split(/\s/)[0];
    ref.url = clean(item.URL);
    ref.accessed = clean(item.accessed?.raw || (item.accessed?.['date-parts']?.[0] || []).map(part => String(part).padStart(2, '0')).join('-'));
    const toPerson = person => (person.literal ? { first: '', middle: '', last: clean(person.literal) } : parseAuthors(`${clean(person.family)}, ${clean(person.given)}`)[0]);
    ref.authors = (item.author || []).map(toPerson).filter(Boolean);
    ref.editors = (item.editor || []).map(toPerson).filter(Boolean).map(author => [author.first, author.middle, author.last].filter(Boolean).join(' ')).join('; ');
    return ref;
  }).filter(ref => ref.title);
}

export function parseReferenceFile(fileName, text) {
  const name = fileName.toLowerCase();
  const body = text.replace(/^﻿/, '');
  if (name.endsWith('.json') || /^\s*[[{]/.test(body)) return parseCslJson(body);
  if (name.endsWith('.nbib') || /^PMID-\s/m.test(body)) return parseMedline(body);
  if (name.endsWith('.ris') || /^TY\s{1,2}-/m.test(body)) return parseRIS(body);
  return parseBibTeX(body);
}

export function downloadText(fileName, text, type = 'text/plain') {
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }));
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  window.setTimeout(() => {
    URL.revokeObjectURL(link.href);
    link.remove();
  }, 0);
}
