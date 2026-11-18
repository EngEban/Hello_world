import { categories_data } from './Category_to_keyword.js';

const matched_categories = new Map();

// British spellings are mapped to the American forms used in the keyword list, so "glycaemic",
// "anaemia" or "paediatric" match "glycemic", "anemia" and "pediatric". Only stems that cannot
// change other words are listed (e.g. not "organis", which would also rewrite "organism").
const UK_TO_US_STEMS = {
    haem: 'hem', anaem: 'anem', glycaem: 'glycem', ischaem: 'ischem', leukaem: 'leukem', septicaem: 'septicem',
    oedem: 'edem', oesoph: 'esoph', oestr: 'estr', foet: 'fet', paed: 'ped', anaesth: 'anesth', gynaec: 'gynec',
    caesar: 'cesar', diarrhoea: 'diarrhea', dyspnoea: 'dyspnea', apnoea: 'apnea', coeliac: 'celiac',
    tumour: 'tumor', behaviour: 'behavior', labour: 'labor', programme: 'program', centre: 'center', fibre: 'fiber',
    litre: 'liter', ageing: 'aging', randomis: 'randomiz', hospitalis: 'hospitaliz', immunis: 'immuniz',
    standardis: 'standardiz', optimis: 'optimiz', utilis: 'utiliz', minimis: 'minimiz', recognis: 'recogniz',
    generalis: 'generaliz', normalis: 'normaliz', visualis: 'visualiz', categoris: 'categoriz', prioritis: 'prioritiz',
    summaris: 'summariz', catheteris: 'catheteriz', sensitis: 'sensitiz'
};
const UK_TO_US_PATTERN = new RegExp(Object.keys(UK_TO_US_STEMS).sort((a, b) => b.length - a.length).join('|'), 'g');

const GENERIC_TOKENS = new Set([
    'analysis', 'article', 'care', 'data', 'effect', 'health', 'medicine', 'medical', 'method', 'methods',
    'model', 'models', 'paper', 'patient', 'patients', 'research', 'result', 'results', 'study', 'system', 'systems'
]);

const PUBLISHER_PRIORITY_ORDER = [
    'BMC',
    'BMJ',
    'SAGE',
    'Wiley',
    'Elsevier',
    'Oxford',
    'Cambridge',
    'Wolters Kluwer'
];

const PUBLISHER_PRIORITY_LIMIT = 3;
const PUBLISHER_PRIORITY_MIN_SCORE_RATIO = 0.2;
const CASE_REPORT_JOURNAL_BONUS = 120;

const CATEGORY_ALIASES = {
    'emergency care': 'Emergency Medicine',
    'emergency medicine': 'Emergency Medicine',
    'critical care medicine': 'Critical Care and Intensive Care Medicine',
    'critical care': 'Critical Care and Intensive Care Medicine',
    'internal medicine': 'Internal Medicine',
    'cardiology': 'Cardiology and Cardiovascular Medicine',
    'oncology': 'Oncology',
    'cancer research': 'Cancer Research',
    'endocrinology': 'Endocrinology',
    'diabetes metabolism': 'Endocrinology, Diabetes and Metabolism',
    'infectious disease': 'Infectious Diseases',
    'infectious diseases': 'Infectious Diseases',
    'public health': 'Public Health, Environmental and Occupational Health',
    'pulmonary medicine': 'Pulmonary and Respiratory Medicine',
    'respiratory medicine': 'Pulmonary and Respiratory Medicine',
    'health informatics': 'Health Informatics',
    'medical informatics': 'Health Informatics',
    'medical laboratory': 'Medical Laboratory Technology',
    'mental health': 'Psychiatry and Mental Health',
    'clinical psychology': 'Clinical Psychology',
    'neurology': 'Neurology',
    'clinical neurology': 'Neurology (clinical)',
    'obgyn': 'Obstetrics and Gynecology',
    'obstetrics gynecology': 'Obstetrics and Gynecology',
    'pediatrics': 'Pediatrics',
    'perinatology': 'Pediatrics, Perinatology and Child Health',
    'geriatrics': 'Geriatrics and Gerontology',
    'otolaryngology': 'Otorhinolaryngology',
    'ent': 'Otorhinolaryngology',
    'orthopedics': 'Orthopedics and Sports Medicine',
    'physical therapy': 'Physical Therapy, Sports Therapy and Rehabilitation',
    'first aid': 'Emergency Medicine',
    'primary health': 'Public Health, Environmental and Occupational Health',
    'medical student': 'Health Professions (miscellaneous)',
    'health education': 'Public Health, Environmental and Occupational Health',
    'pharmacology medical': 'Pharmacology (medical)',
    'pharmacology nursing': 'Pharmacology (nursing)'
};

const CROSS_SPECIALTY = {
    'Emergency Medicine': ['Critical Care and Intensive Care Medicine', 'Emergency Medical Services', 'Emergency Nursing', 'Surgery', 'Orthopedics and Sports Medicine'],
    'Critical Care and Intensive Care Medicine': ['Emergency Medicine', 'Pulmonary and Respiratory Medicine', 'Critical Care Nursing', 'Anesthesiology and Pain Medicine'],
    'Internal Medicine': ['Cardiology and Cardiovascular Medicine', 'Endocrinology, Diabetes and Metabolism', 'Nephrology', 'Pulmonary and Respiratory Medicine', 'Family Practice'],
    'Cardiology and Cardiovascular Medicine': ['Internal Medicine', 'Critical Care and Intensive Care Medicine'],
    'Endocrinology, Diabetes and Metabolism': ['Endocrinology', 'Internal Medicine', 'Nephrology', 'Pediatrics'],
    'Infectious Diseases': ['Microbiology (medical)', 'Microbiology', 'Epidemiology', 'Public Health, Environmental and Occupational Health', 'Dermatology'],
    'Oncology': ['Cancer Research', 'Hematology', 'Molecular Medicine', 'Oncology (nursing)'],
    'Cancer Research': ['Oncology', 'Molecular Medicine', 'Genetics (clinical)'],
    'Neurology': ['Neurology (clinical)', 'Neuroscience (miscellaneous)', 'Cellular and Molecular Neuroscience', 'Psychiatry and Mental Health'],
    'Psychiatry and Mental Health': ['Clinical Psychology', 'Biological Psychiatry', 'Neuropsychology and Physiological Psychology'],
    'Obstetrics and Gynecology': ['Reproductive Medicine', 'Maternity and Midwifery', 'Pediatrics, Perinatology and Child Health'],
    'Pediatrics': ['Pediatrics, Perinatology and Child Health', 'Infectious Diseases', 'Endocrinology, Diabetes and Metabolism'],
    'Orthopedics and Sports Medicine': ['Surgery', 'Rehabilitation', 'Physical Therapy, Sports Therapy and Rehabilitation'],
    'Pulmonary and Respiratory Medicine': ['Respiratory Care', 'Critical Care and Intensive Care Medicine', 'Infectious Diseases'],
    'Dermatology': ['Infectious Diseases', 'Immunology and Allergy'],
    'Health Informatics': ['Health Information Management', 'Artificial Intelligence', 'Computer Science Applications'],
    'Public Health, Environmental and Occupational Health': ['Epidemiology', 'Health Policy', 'Health (social science)', 'Infectious Diseases'],
    'Transplantation': ['Immunology', 'Nephrology', 'Hepatology']
};

const SYRIAN_TRENDS = {
    'syria': ['Public Health, Environmental and Occupational Health', 'Health (social science)', 'Epidemiology'],
    'first aid': ['Emergency Medicine', 'Emergency Medical Services', 'Public Health, Environmental and Occupational Health'],
    'students': ['Education', 'Health Professions (miscellaneous)', 'Public Health, Environmental and Occupational Health'],
    'leishmaniasis': ['Infectious Diseases', 'Dermatology', 'Public Health, Environmental and Occupational Health'],
    'brucellosis': ['Infectious Diseases', 'Public Health, Environmental and Occupational Health'],
    'thalassemia': ['Hematology', 'Pediatrics'],
    'blast injury': ['Emergency Medicine', 'Surgery', 'Orthopedics and Sports Medicine'],
    'crush syndrome': ['Emergency Medicine', 'Nephrology', 'Critical Care and Intensive Care Medicine'],
    'war trauma': ['Emergency Medicine', 'Surgery', 'Psychiatry and Mental Health', 'Rehabilitation'],
    'refugee health': ['Public Health, Environmental and Occupational Health', 'Health (social science)', 'Epidemiology'],
    'displacement': ['Public Health, Environmental and Occupational Health', 'Psychiatry and Mental Health'],
    'antimicrobial resistance': ['Infectious Diseases', 'Microbiology (medical)', 'Public Health, Environmental and Occupational Health'],
    'hepatitis': ['Infectious Diseases', 'Hepatology'],
    'tuberculosis': ['Infectious Diseases', 'Pulmonary and Respiratory Medicine'],
    'maternal mortality': ['Obstetrics and Gynecology', 'Maternity and Midwifery', 'Public Health, Environmental and Occupational Health'],
    'neonatal sepsis': ['Pediatrics', 'Pediatrics, Perinatology and Child Health', 'Infectious Diseases'],
    'posttraumatic stress': ['Psychiatry and Mental Health', 'Clinical Psychology']
};

const CATEGORY_LOOKUP = buildCategoryLookup(categories_data);
const KEYWORD_INDEX = buildKeywordIndex(categories_data);
// The journal list (~2.7 MB) is fetched as static JSON only when the Journal
// Finder opens (see features/journalFinder/journalFinderModel.js) and handed
// to setJournalDatabase(), so it is never part of a JavaScript bundle.
let JOURNALS_PREPARED = [];

export function setJournalDatabase(journals) {
    JOURNALS_PREPARED = prepareJournals(Array.isArray(journals) ? journals : []);
}

export function hasJournalDatabase() {
    return JOURNALS_PREPARED.length > 0;
}


function normalize_text(value) {
    return String(value || '').toLowerCase()
        .replace(UK_TO_US_PATTERN, stem => UK_TO_US_STEMS[stem])
        .replace(/[^a-z0-9\s]+/g, ' ').replace(/\s+/g, ' ').trim()
        // "type 2 diabetes" and "type-2 diabetes" match the keyword "type2 diabetes".
        .replace(/\btype ([12])\b/g, 'type$1');
}

function singularize(token) {
    if (token.length > 4 && token.endsWith('ies')) return token.slice(0, -3) + 'y';
    if (token.length > 4 && token.endsWith('es')) return token.slice(0, -2);
    if (token.length > 3 && token.endsWith('s') && !token.endsWith('ss')) return token.slice(0, -1);
    return token;
}

function buildCategoryLookup(data) {
    const lookup = new Map();
    for (const category of Object.keys(data)) {
        lookup.set(normalize_text(category), category);
    }
    for (const alias of Object.keys(CATEGORY_ALIASES)) {
        lookup.set(normalize_text(alias), CATEGORY_ALIASES[alias]);
    }
    return lookup;
}

function canonicalCategory(category) {
    return CATEGORY_LOOKUP.get(normalize_text(category || '')) || null;
}

function buildKeywordIndex(data) {
    const tokenMap = new Map();
    const phraseList = [];

    for (const category of Object.keys(data)) {
        const keywords = data[category] || [];
        for (const keyword of keywords) {
            const normalized = normalize_text(keyword);
            if (!normalized) continue;
            const words = normalized.split(' ').map(singularize);
            if (words.length === 1) {
                addTokenLink(tokenMap, words[0], category, 1);
            } else if (words.length === 2) {
                phraseList.push({ category, phrase: words.join(' '), words, weight: 1.4 });
                addTokenLink(tokenMap, words[0], category, 0.35);
                addTokenLink(tokenMap, words[1], category, 0.35);
            }
        }
    }

    return { tokenMap, phraseList };
}

function addTokenLink(map, token, category, weight) {
    if (!token || token.length < 3 || GENERIC_TOKENS.has(token)) return;
    if (!map.has(token)) map.set(token, []);
    map.get(token).push({ category, weight });
}

function entriesFromTokens(tokens) {
    const entries = [];

    if (!tokens) return entries;

    if (tokens instanceof Map) {
        for (const [key, value] of tokens.entries()) entries.push([key, value]);
        return entries;
    }

    if (Array.isArray(tokens)) {
        for (const item of tokens) {
            if (Array.isArray(item) && item.length >= 2) entries.push([item[0], item[1]]);
            else if (typeof item === 'string') entries.push([item, 1]);
        }
        return entries;
    }

    if (typeof tokens === 'object') {
        for (const key of Object.keys(tokens)) entries.push([key, tokens[key]]);
    }

    return entries;
}

function normalizeTokenMap(tokens) {
    const tokenMap = new Map();
    const entries = entriesFromTokens(tokens);

    for (const [rawKey, rawValue] of entries) {
        const normalizedKey = normalize_text(rawKey);
        if (!normalizedKey) continue;

        const count = Number(rawValue) > 0 ? Number(rawValue) : 1;
        const words = normalizedKey.split(' ');

        for (const rawWord of words) {
            const token = singularize(rawWord);
            if (!token || token.length < 3 || GENERIC_TOKENS.has(token)) continue;
            tokenMap.set(token, (tokenMap.get(token) || 0) + count);
        }

        if (words.length === 2) {
            const phrase = singularize(words[0]) + ' ' + singularize(words[1]);
            tokenMap.set(phrase, (tokenMap.get(phrase) || 0) + count);
        }
    }

    return tokenMap;
}

function tokenizeTextToMap(text) {
    const tokenMap = new Map();
    const normalized = normalize_text(text);
    if (!normalized) return tokenMap;

    const words = normalized.split(' ');
    for (let i = 0; i < words.length; i += 1) {
        const token = singularize(words[i]);
        if (!token || token.length < 3 || GENERIC_TOKENS.has(token)) continue;
        tokenMap.set(token, (tokenMap.get(token) || 0) + 1);

        if (i < words.length - 1) {
            const bigram = token + ' ' + singularize(words[i + 1]);
            tokenMap.set(bigram, (tokenMap.get(bigram) || 0) + 1);
        }
    }

    return tokenMap;
}

function normalizePublisher(publisher) {
    const normalized = normalize_text(publisher);
    if (!normalized) return 'Other';
    if (normalized.includes('biomed central') || normalized.includes('bmc')) return 'BMC';
    if (normalized.includes('bmj')) return 'BMJ';
    if (normalized.includes('sage')) return 'SAGE';
    if (normalized.includes('wiley')) return 'Wiley';
    if (normalized.includes('elsevier') || normalized.includes('saunders') || normalized.includes('cell press')) return 'Elsevier';
    if (normalized.includes('oxford')) return 'Oxford';
    if (normalized.includes('cambridge')) return 'Cambridge';
    if (normalized.includes('wolters') || normalized.includes('lippincott')) return 'Wolters Kluwer';
    return 'Other';
}

function normalizePublisherKey(publisher) {
    return normalize_text(publisher);
}

function normalizePublisherFilter(filter) {
    if (!filter) return { canonical: [], raw: [] };

    const values = Array.isArray(filter) ? filter : [filter];
    const canonical = [];
    const raw = [];

    for (const value of values) {
        if (!value) continue;
        const parts = String(value).split(',').map(part => part.trim()).filter(Boolean);

        for (const rawValue of parts) {
            const normalizedRaw = normalize_text(rawValue);
            if (!normalizedRaw || ['any', 'all', 'any publisher', 'publisher'].includes(normalizedRaw)) continue;

            const normalized = normalizePublisher(rawValue);
            if (normalized !== 'Other') {
                if (!canonical.includes(normalized)) canonical.push(normalized);
                continue;
            }

            if (!raw.includes(normalizedRaw)) raw.push(normalizedRaw);
        }
    }

    return { canonical, raw };
}

function normalizeQuartileFilter(filter) {
    if (!filter) return [];
    const values = Array.isArray(filter) ? filter : [filter];
    const out = [];

    for (const value of values) {
        const parts = String(value || '').split(',');
        for (const part of parts) {
            const normalized = String(part || '').toUpperCase().trim();
            if (!/^Q[1-4]$/.test(normalized)) continue;
            if (!out.includes(normalized)) out.push(normalized);
        }
    }

    return out;
}

function parseMinHIndex(value) {
    if (value === undefined || value === null || value === '') return null;
    const raw = String(value).replace(/,/g, '').trim();
    if (!raw) return null;

    const numericMatch = raw.match(/-?\d+(\.\d+)?/);
    if (!numericMatch) return null;

    const num = Number(numericMatch[0]);
    if (!Number.isFinite(num) || num < 0) return null;
    return num;
}

function normalizeOpenAccessFilter(value) {
    if (value === undefined || value === null) return null;
    const normalized = String(value).toLowerCase().trim();
    if (['true', '1', 'yes', 'open', 'open access', 'open-access', 'openaccess', 'oa', 'only_oa', 'open_only', 'oa only', 'open only', 'open access only', 'open-access only'].includes(normalized)) return true;
    if (['false', '0', 'no', 'closed', 'subscription', 'subscription only', 'non oa', 'non-oa', 'not open access', 'closed access'].includes(normalized)) return false;
    if (['any', 'all'].includes(normalized)) return null;
    return null;
}

function pickFirstDefined(...values) {
    for (const value of values) {
        if (value === undefined || value === null) continue;
        if (typeof value === 'string' && value.trim() === '') continue;
        return value;
    }
    return undefined;
}

function readDOMFilterOptions() {
    if (typeof document === 'undefined') return {};

    const readValue = (selectorList) => {
        for (const selector of selectorList) {
            const el = document.querySelector(selector);
            if (!el) continue;
            const value = String(el.value || '').trim();
            if (value !== '') return value;
        }
        return '';
    };

    return {
        publisher: readValue([
            'select[name=\"publisher\"]',
            'select[name=\"publisher_filter\"]',
            'select[name=\"publisherFilter\"]',
            'select[id=\"publisherFilter\"]',
            'select[id*=\"publisher-filter\"]',
            'select[id*=\"publisherfilter\"]',
            'select[class*=\"publisher\"]',
            'select[id*=\"publisher\"]'
        ]),
        quartile: readValue([
            'select[name=\"quartile\"]',
            'select[name=\"quartile_filter\"]',
            'select[name=\"quartileFilter\"]',
            'select[id=\"quartileFilter\"]',
            'select[id*=\"quartile-filter\"]',
            'select[id*=\"quartilefilter\"]',
            'select[id*=\"quartile\"]'
        ]),
        openAccess: readValue([
            'select[name=\"open_access\"]',
            'select[name=\"open_access_filter\"]',
            'select[name=\"openAccess\"]',
            'select[name=\"openAccessFilter\"]',
            'select[name=\"oa_preference\"]',
            'select[id=\"openAccess\"]',
            'select[id=\"openAccessFilter\"]',
            'select[id*=\"open_access\"]',
            'select[id*=\"open-access\"]',
            'select[id*=\"openaccess\"]',
            'select[id*=\"oa\"]'
        ]),
        minHIndex: readValue([
            'input[name=\"min_h_index\"]',
            'input[name=\"minHIndex\"]',
            'input[name=\"min-h-index\"]',
            'input[name=\"h_index_min\"]',
            'input[id=\"minHIndex\"]',
            'input[id=\"min-h-index\"]',
            'input[id*=\"h_index\"]',
            'input[id*=\"h-index\"]',
            'input[id*=\"hindex\"]'
        ]),
        maxResults: readValue([
            'input[name=\"max_results\"]',
            'input[name=\"result_limit\"]',
            'input[name=\"maxResults\"]',
            'input[name=\"max-results\"]',
            'select[name=\"max_results\"]',
            'select[name=\"maxResults\"]',
            'input[id=\"maxResults\"]',
            'input[id=\"max-results\"]',
            'input[id*=\"max_results\"]',
            'input[id*=\"max-results\"]',
            'input[id*=\"result_limit\"]',
            'input[id*=\"result-limit\"]',
            'input[id*=\"maxresults\"]',
            'select[id*=\"max_results\"]',
            'select[id*=\"max-results\"]',
            'select[id*=\"maxresults\"]'
        ])
    };
}

function isMedicalCategory(category) {
    if (!category) return false;
    if (categories_data[category]) return true;

    const normalized = normalize_text(category);
    return normalized.includes('medicine')
        || normalized.includes('nursing')
        || normalized.includes('health')
        || normalized.includes('clinical')
        || normalized.includes('surgery')
        || normalized.includes('pharmac')
        || normalized.includes('toxicology')
        || normalized.includes('epidemiology')
        || normalized.includes('oncology')
        || normalized.includes('neurology')
        || normalized.includes('cardio')
        || normalized.includes('pediatric')
        || normalized.includes('gyne')
        || normalized.includes('microbiology');
}

function prepareJournals(journals) {
    const prepared = [];

    for (const journal of journals) {
        const categories = [];
        const sourceCategories = Array.isArray(journal.categories) ? journal.categories : [];

        for (const rawCategory of sourceCategories) {
            const canonical = canonicalCategory(rawCategory) || rawCategory.trim();
            if (isMedicalCategory(canonical)) categories.push(canonical);
        }

        if (!categories.length) continue;

        prepared.push({
            journal,
            categories,
            publisherCanonical: normalizePublisher(journal.publisher),
            publisherKey: normalizePublisherKey(journal.publisher),
            titleTokens: tokenizeTextToMap(journal.title),
            categoryText: normalize_text(categories.join(' '))
        });
    }

    return prepared;
}

function addScore(map, category, amount) {
    if (!category || amount <= 0) return;
    map.set(category, (map.get(category) || 0) + amount);
}

export function match_tokens_to_keywords(tokens) {
    matched_categories.clear();

    const tokenMap = normalizeTokenMap(tokens);
    const scoreMap = new Map();
    const hitCount = new Map();

    for (const [token, frequency] of tokenMap.entries()) {
        const links = KEYWORD_INDEX.tokenMap.get(token);
        if (!links) continue;

        for (const link of links) {
            const score = (8 + token.length * 0.2) * frequency * link.weight;
            addScore(scoreMap, link.category, score);
            hitCount.set(link.category, (hitCount.get(link.category) || 0) + 1);
        }
    }

    for (const item of KEYWORD_INDEX.phraseList) {
        const leftCount = tokenMap.get(item.words[0]) || 0;
        const rightCount = tokenMap.get(item.words[1]) || 0;

        if (leftCount > 0 && rightCount > 0) {
            const phraseCount = Math.min(leftCount, rightCount);
            addScore(scoreMap, item.category, (16 + item.phrase.length * 0.15) * item.weight * phraseCount);
            hitCount.set(item.category, (hitCount.get(item.category) || 0) + 1);
        } else if (tokenMap.has(item.phrase)) {
            addScore(scoreMap, item.category, 18 * item.weight * tokenMap.get(item.phrase));
            hitCount.set(item.category, (hitCount.get(item.category) || 0) + 1);
        }
    }

    for (const trendKey of Object.keys(SYRIAN_TRENDS)) {
        const words = trendKey.split(' ').map(singularize);
        let present = true;
        for (const word of words) {
            if (!tokenMap.has(word)) {
                present = false;
                break;
            }
        }

        if (!present) continue;
        for (const category of SYRIAN_TRENDS[trendKey]) {
            addScore(scoreMap, category, 26);
            hitCount.set(category, (hitCount.get(category) || 0) + 1);
        }
    }

    const baseSnapshot = Array.from(scoreMap.entries());
    for (const [category, score] of baseSnapshot) {
        if (score < 24) continue;
        const related = CROSS_SPECIALTY[category] || [];
        for (const relatedCategory of related) {
            addScore(scoreMap, relatedCategory, score * 0.18);
        }
    }

    for (const [category, score] of scoreMap.entries()) {
        const hits = hitCount.get(category) || 0;
        const synergy = hits >= 3 ? Math.min(1.45, 1 + (hits - 2) * 0.14) : 1;
        const finalScore = score * synergy;
        if (finalScore > 0) matched_categories.set(category, finalScore);
    }

    const ranked = Array.from(matched_categories.entries());
    ranked.sort((a, b) => b[1] - a[1]);
    return ranked;
}

function queryHasTrend(tokenMap, trendKey) {
    const words = trendKey.split(' ').map(singularize);
    for (const word of words) {
        if (!tokenMap.has(word)) return false;
    }
    return true;
}

function journalTouchesCategories(journalCategories, categories) {
    for (const category of categories) {
        if (journalCategories.includes(category)) return true;
    }
    return false;
}

function isCaseReportContext(queryText, opts = {}, filterOptions = {}) {
    const normalized = normalize_text([
        queryText,
        opts.articleType,
        opts.article_type,
        opts.studyDesign,
        opts.study_design,
        filterOptions.articleType,
        filterOptions.article_type
    ].filter(Boolean).join(' '));

    if (!normalized) return false;
    if (normalized.includes('case control') && !normalized.includes('case report')) return false;
    return normalized.includes('case report')
        || normalized.includes('case reports')
        || normalized.includes('clinical case')
        || normalized.includes('case series');
}

function isCaseReportJournal(journal) {
    const normalized = normalize_text([
        journal && journal.title,
        journal && journal.publisher,
        ...((journal && journal.categories) || [])
    ].filter(Boolean).join(' '));

    return normalized.includes('case report')
        || normalized.includes('case reports')
        || normalized.includes('case studies')
        || normalized.includes('medical cases')
        || normalized.includes('case lessons');
}

function inferCategoriesFromText(text) {
    const inferred = new Map();
    const normalized = normalize_text(text);
    if (!normalized) return inferred;

    const aliasEntries = Object.entries(CATEGORY_ALIASES);
    aliasEntries.sort((a, b) => b[0].length - a[0].length);
    for (const [alias, category] of aliasEntries) {
        const aliasNorm = normalize_text(alias);
        if (!aliasNorm) continue;
        if (!normalized.includes(aliasNorm)) continue;
        const aliasWeight = aliasNorm.includes(' ') ? 18 : 10;
        addScore(inferred, category, aliasWeight);
    }

    for (const trendKey of Object.keys(SYRIAN_TRENDS)) {
        const trendNorm = normalize_text(trendKey);
        if (!trendNorm || !normalized.includes(trendNorm)) continue;
        for (const category of SYRIAN_TRENDS[trendKey]) addScore(inferred, category, 9);
    }

    return inferred;
}

function buildQueryText(paper_title, opts, filterOptions) {
    const keywordText = Array.isArray(pickFirstDefined(opts.keywords, filterOptions.keywords))
        ? pickFirstDefined(opts.keywords, filterOptions.keywords).join(' ')
        : pickFirstDefined(opts.keywords, filterOptions.keywords, opts.keywordText, opts.keyword_text, filterOptions.keywordText, filterOptions.keyword_text);
    return [
        paper_title || '',
        pickFirstDefined(opts.abstract, opts.paper_abstract, opts.paperAbstract, opts.summary, filterOptions.abstract, filterOptions.paper_abstract, filterOptions.paperAbstract),
        keywordText,
        pickFirstDefined(opts.articleType, opts.article_type, filterOptions.articleType, filterOptions.article_type),
        pickFirstDefined(opts.studyDesign, opts.study_design, filterOptions.studyDesign, filterOptions.study_design),
        pickFirstDefined(opts.targetAudience, opts.target_audience, filterOptions.targetAudience, filterOptions.target_audience)
    ].filter(Boolean).join(' ');
}

function compareJournalFit(a, b, caseReportRequested) {
    if (caseReportRequested) {
        const caseDelta = Number(isCaseReportJournal(b[0])) - Number(isCaseReportJournal(a[0]));
        if (caseDelta !== 0) return caseDelta;
    }

    if (b[1] !== a[1]) return b[1] - a[1];

    const hA = Number(a[0].h_index) || 0;
    const hB = Number(b[0].h_index) || 0;
    return hB - hA;
}

function applyPublisherPriorityBuckets(entries, caseReportRequested) {
    const qualitySorted = [...entries].sort((a, b) => compareJournalFit(a, b, caseReportRequested));
    const highestScore = qualitySorted.reduce((max, [, score]) => Math.max(max, score), 0);
    const priorityScoreCutoff = highestScore * PUBLISHER_PRIORITY_MIN_SCORE_RATIO;
    const pickedIndexes = new Set();
    const prioritized = [];

    for (const publisher of PUBLISHER_PRIORITY_ORDER) {
        let pickedForPublisher = 0;

        for (let index = 0; index < qualitySorted.length && pickedForPublisher < PUBLISHER_PRIORITY_LIMIT; index += 1) {
            if (pickedIndexes.has(index)) continue;

            const [journal] = qualitySorted[index];
            if (qualitySorted[index][1] < priorityScoreCutoff) continue;
            if (normalizePublisher(journal.publisher) !== publisher) continue;

            prioritized.push(qualitySorted[index]);
            pickedIndexes.add(index);
            pickedForPublisher += 1;
        }
    }

    return [
        ...prioritized,
        ...qualitySorted.filter((_, index) => !pickedIndexes.has(index))
    ];
}

export function analyze_manuscript_categories(paper_title, options = {}) {
    const filterOptions = Object.assign({}, options.filters || {}, options.filter || {});
    const queryText = buildQueryText(paper_title, options || {}, filterOptions);
    return match_tokens_to_keywords(tokenizeTextToMap(queryText || paper_title || ''));
}

export function match_categories_to_journals(paper_title, options = {}) {
    const domOptions = readDOMFilterOptions();
    const opts = Object.assign({}, domOptions, options || {});
    const journal_scores = new Map();
    const filterOptions = Object.assign({}, opts.filters || {}, opts.filter || {});
    const queryText = buildQueryText(paper_title, opts, filterOptions);

    const titleTokenMap = tokenizeTextToMap(queryText || paper_title || '');
    if (!matched_categories.size) {
        match_tokens_to_keywords(titleTokenMap);
    }
    const inferredCategories = inferCategoriesFromText(queryText || paper_title || '');
    const effectiveCategoryScores = new Map(matched_categories);
    for (const [category, amount] of inferredCategories.entries()) addScore(effectiveCategoryScores, category, amount);

    const rankedCategories = Array.from(effectiveCategoryScores.entries()).sort((a, b) => b[1] - a[1]);
    const strongestCategoryScore = rankedCategories.length ? rankedCategories[0][1] : 0;
    const categoryCutoff = strongestCategoryScore > 0 ? Math.max(4, strongestCategoryScore * 0.28) : 0;
    const caseReportRequested = isCaseReportContext(queryText, opts, filterOptions);
    const activeCategoryScores = new Map();
    for (const [category, score] of rankedCategories) {
        if (score >= categoryCutoff || activeCategoryScores.size < 4) {
            activeCategoryScores.set(category, score);
        }
    }

    const preferredPublishers = normalizePublisherFilter(
        pickFirstDefined(
            opts.publisherFilter,
            opts.publisher_filter,
            opts.publishers,
            opts.publisher,
            filterOptions.publisherFilter,
            filterOptions.publisher_filter,
            filterOptions.publishers,
            filterOptions.publisher
        )
    );
    const preferredQuartiles = normalizeQuartileFilter(
        pickFirstDefined(
            opts.quartileFilter,
            opts.quartile_filter,
            opts.quartiles,
            opts.quartile,
            filterOptions.quartileFilter,
            filterOptions.quartile_filter,
            filterOptions.quartiles,
            filterOptions.quartile
        )
    );
    const minHIndex = parseMinHIndex(
        pickFirstDefined(
            opts.minHIndex,
            opts.min_h_index,
            opts.minH,
            opts.h_index_min,
            opts.hIndexMin,
            filterOptions.minHIndex,
            filterOptions.min_h_index,
            filterOptions.minH,
            filterOptions.h_index_min,
            filterOptions.hIndexMin
        )
    );
    const oaPreference = normalizeOpenAccessFilter(
        pickFirstDefined(
            opts.oaOnly,
            opts.oa_only,
            opts.openAccess,
            opts.open_access,
            filterOptions.oaOnly,
            filterOptions.oa_only,
            filterOptions.openAccess,
            filterOptions.open_access
        )
    );
    const maxResults = parseMinHIndex(
        pickFirstDefined(
            opts.maxResults,
            opts.max_results,
            opts.limit,
            filterOptions.maxResults,
            filterOptions.max_results,
            filterOptions.limit
        )
    );

    for (const entry of JOURNALS_PREPARED) {
        const journal = entry.journal;
        const publisherCanonical = entry.publisherCanonical;
        const publisherKey = entry.publisherKey;

        if (
            (preferredPublishers.canonical.length > 0 || preferredPublishers.raw.length > 0)
            && !preferredPublishers.canonical.includes(publisherCanonical)
            && !preferredPublishers.raw.includes(publisherKey)
        ) continue;
        if (preferredQuartiles.length > 0 && !preferredQuartiles.includes(String(journal.quartile || '').toUpperCase())) continue;
        if (minHIndex !== null && (Number(journal.h_index) || 0) < minHIndex) continue;
        if (oaPreference === true && !journal.is_oa) continue;
        if (oaPreference === false && journal.is_oa) continue;

        let score = 0;
        let matchedCount = 0;
        let titleHitCount = 0;
        let trendHits = 0;

        for (const category of entry.categories) {
            const categoryScore = activeCategoryScores.get(category);
            if (!categoryScore) continue;
            score += categoryScore;
            matchedCount += 1;
        }

        if (matchedCount >= 2) {
            score *= Math.min(1.5, 1 + (matchedCount - 1) * 0.16);
        }

        for (const [token, frequency] of titleTokenMap.entries()) {
            if (token.includes(' ')) continue;
            if (entry.titleTokens.has(token)) {
                score += 18 * frequency;
                titleHitCount += frequency;
            } else if (entry.categoryText.includes(token)) {
                score += 5 * frequency;
                titleHitCount += 1;
            }
        }

        for (const trendKey of Object.keys(SYRIAN_TRENDS)) {
            if (!queryHasTrend(titleTokenMap, trendKey)) continue;
            if (journalTouchesCategories(entry.categories, SYRIAN_TRENDS[trendKey])) {
                score += 20;
                trendHits += 1;
            }
        }

        const hasDirectRelevance = matchedCount > 0 || titleHitCount > 0 || trendHits > 0;
        if (!hasDirectRelevance) continue;

        if (matchedCount === 0 && trendHits === 0) {
            if (titleHitCount < 3) continue;
            score *= 0.82;
        }
        if (caseReportRequested && isCaseReportJournal(journal)) {
            score += CASE_REPORT_JOURNAL_BONUS;
        }

        if (matchedCount === 0 && titleHitCount < 2 && trendHits === 0) continue;
        if (matchedCount === 1 && titleHitCount === 0 && trendHits === 0 && score < 35) continue;

        if (score > 0) {
            journal_scores.set(journal, score);
        }
    }
    
    const ranked = Array.from(journal_scores.entries());
    const priorityRanked = applyPublisherPriorityBuckets(ranked, caseReportRequested);

    matched_categories.clear();
    if (maxResults !== null && maxResults > 0) return priorityRanked.slice(0, Math.floor(maxResults));
    return priorityRanked;
}

export function filterByPublisher(results, publisherName) {
    const needle = normalize_text(publisherName);
    if (!needle) return results;
    return (results || []).filter(([journal]) => normalize_text(journal && journal.publisher).includes(needle));
}
