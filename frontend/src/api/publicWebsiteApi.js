import { get as rawGet, post, upload } from './apiClient';
import { optimizedImageData } from '../utils/optimizedImages';

const get = async (path, options) => optimizedImageData(await rawGet(path, options));

function makeQuery(params) {
  if (typeof params === 'string') return params;
  const query = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== '' && value !== null && value !== undefined) query.set(key, value);
  });
  const text = query.toString();
  return text ? `?${text}` : '';
}

function normalizeReferenceQuery(query) {
  return query.trim().split(/\r?\n/).map(line => {
    const value = line.trim();
    const doi = value.match(/10\.\d{4,9}\/[-._;()/:A-Z0-9]+/i);
    return doi ? doi[0] : value;
  }).filter(Boolean).join('\n');
}

const searchReferences = (query, sourceType = '') => get(`/references/fetch/${makeQuery({ q: normalizeReferenceQuery(query), type: sourceType })}`);

export const PublicWebsiteApi = {
  getHomeContent: () => get('/home/'),
  getPosts: (params = '', options) => get(`/posts/${makeQuery(params)}`, options),
  getOpportunities: (params = '', options) => get(`/opportunities/${makeQuery(params)}`, options),
  getJoinTeamEntries: () => get('/join-team/'),
  getPostBySlug: (slug, options) => get(`/posts/${encodeURIComponent(slug)}/`, options),
  getPageBySlug: (slug, options) => get(`/pages/${encodeURIComponent(slug)}/`, options),
  getAuthorBySlug: (slug, options) => get(`/authors/${encodeURIComponent(slug)}/`, options),
  getCategories: options => get('/categories/', options),
  getFaq: () => get('/faq/'),
  getTeamPage: () => get('/team/'),
  getSiteSettings: () => get('/site-settings/'),
  universalSearch: (params = '') => get(`/search/${makeQuery(params)}`),
  submitContactForm: (payload) => post('/contact/', payload),
  submitServiceRequest: (requestType, payload) => post('/service-requests/', { ...payload, request_type: requestType }),
  submitApplication: (payload, cvFile) => {
    const body = new FormData();
    Object.entries(payload).forEach(([key, value]) => body.append(key, value ?? ''));
    if (cvFile) body.append('cv', cvFile);
    return upload('/applications/', body);
  },
  searchReferences,
  fetchReference: async (query) => (await searchReferences(query)).reference,
};
