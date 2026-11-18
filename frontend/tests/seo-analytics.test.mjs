import assert from 'node:assert/strict';
import test from 'node:test';
import { safePagePath } from '../src/utils/analytics.js';

test('analytics page paths drop tokens, emails and search terms', () => {
  assert.equal(safePagePath({ pathname: '/account/reset-password', search: '?token=abc&uid=9' }), '/account/reset-password');
  assert.equal(safePagePath({ pathname: '/database', search: '?q=jane%40example.com&cat=cardiology&page=2' }), '/database?cat=cardiology&page=2');
  assert.equal(safePagePath({ pathname: '/about', search: '' }), '/about');
});
