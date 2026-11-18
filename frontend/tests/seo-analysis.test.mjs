import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { analyzeArticle, CHECKS, extractFaq, parseHtml, phraseMatch, scoreBand, scoreChecks, suggestKeyphrase } from '../src/pages/dashboard/posts/seoAnalysis.js';

// Shared with backend/blog/test_seo_analysis.py: the editor and the dashboard must agree.
const cases = JSON.parse(readFileSync(new URL('../../backend/blog/seo_analysis_cases.json', import.meta.url), 'utf8'));
const base = { now: '2026-10-27T00:00:00Z', updated_at: '2026-10-27T00:00:00Z', published_at: '2026-10-01T00:00:00Z', site_host: 'resref.com' };
const statusOf = (input, id) => analyzeArticle({ ...base, ...input }).checks.find(check => check.id === id).status;

test('browser analysis matches the shared server cases', () => {
  for (const item of cases) {
    const report = analyzeArticle(item.input);
    assert.deepEqual(Object.fromEntries(report.checks.map(check => [check.id, check.status])), item.expected.checks, item.name);
    assert.deepEqual(report.scores, item.expected.scores, item.name);
    assert.equal(report.words, item.expected.words, item.name);
    assert.equal(report.faq.length, item.expected.faq, item.name);
  }
});

test('every check explains itself and failing checks say how to fix them', () => {
  const report = analyzeArticle({ ...base, title: 'Draft', content: '<p>Short.</p>' });
  assert.equal(report.checks.length, CHECKS.length);
  for (const check of report.checks) {
    assert.ok(check.message, check.id);
    if (check.status === 'bad' || check.status === 'warn') assert.ok(check.fix, `${check.id} needs a fix`);
  }
});

test('text length uses the Yoast minimums (300 words, 900 for cornerstone)', () => {
  const text = count => `<p>${Array.from({ length: count }, () => 'word').join(' ')}</p>`;
  assert.equal(statusOf({ content: text(300) }, 'text_length'), 'good');
  assert.equal(statusOf({ content: text(250) }, 'text_length'), 'warn');
  assert.equal(statusOf({ content: text(200) }, 'text_length'), 'bad');
  assert.equal(statusOf({ content: text(500), cornerstone: true }, 'text_length'), 'warn');
});

test('the search title counts the " | ResRef" suffix and the description window is 120-156', () => {
  assert.equal(statusOf({ title: 'x'.repeat(51) }, 'title_length'), 'good');
  assert.equal(statusOf({ title: 'x'.repeat(52) }, 'title_length'), 'warn');
  const intro = '<p>Cohort studies follow groups of people over time to compare outcomes between exposures.</p>';
  const description = 'Cohort studies follow groups of people over time to compare outcomes between exposures so readers can weigh risks and results.';
  assert.equal(statusOf({ title: 'Cohort studies', content: intro, seo_description: description }, 'meta_description'), 'good');
  assert.equal(statusOf({ title: 'Cohort studies', content: intro, seo_description: description.slice(0, 90) }, 'meta_description'), 'warn');
});

test('keyphrase matching tolerates plurals and word order but density catches stuffing', () => {
  assert.equal(phraseMatch('How cohort studies work', 'cohort study'), 'exact');
  assert.equal(phraseMatch('Studies of a cohort', 'cohort study'), 'all');
  assert.equal(phraseMatch('Case reports', 'cohort study'), 'none');
  assert.equal(statusOf({ title: 'Sample size', focus_keyphrase: 'sample size', content: `<p>${'Sample size matters. '.repeat(50)}</p>` }, 'keyphrase_density'), 'bad');
});

test('FAQ questions written as bold lines with answers are detected', () => {
  const html = '<h2>Frequently Asked Questions (FAQ)</h2><p><strong>1. What does it mean?</strong><br />It means a careful review.</p><p><strong>Is it free?</strong> Yes, for research.</p>';
  const faq = extractFaq(parseHtml(html).blocks);
  assert.deepEqual(faq.items.map(item => [item.question, item.answer]), [['What does it mean?', 'It means a careful review.'], ['Is it free?', 'Yes, for research.']]);
});

test('links to development hosts and malformed DOIs are reported as broken', () => {
  assert.equal(statusOf({ content: '<p><a href="http://resres.local/a">x</a></p>' }, 'link_health'), 'bad');
  assert.equal(statusOf({ content: '<p><a href="https://doi:10.1037/abc">x</a></p>' }, 'link_health'), 'bad');
  assert.equal(statusOf({ content: '<p><a href="https://doi.org/10.1037/abc">x</a></p>' }, 'link_health'), 'good');
});

test('scores are weighted, skip checks that do not apply and use Lighthouse-style bands', () => {
  assert.deepEqual(scoreChecks([['keyphrase', 'good'], ['featured_image', 'bad'], ['images', 'na']]), { seo: 67, readability: null, aeo: null, geo: null, overall: 67 });
  assert.equal(scoreBand(80), 'good');
  assert.equal(scoreBand(79), 'ok');
  assert.equal(scoreBand(49), 'poor');
  assert.equal(suggestKeyphrase('Valued Living Questionnaire (VLQ-2): A Full Guide'), 'Valued Living Questionnaire');
});
