import assert from 'node:assert/strict';
import test from 'node:test';
import { publicationReadingStyle } from '../src/config/contentDesign.js';
import { researchCategory, researchTopics } from '../src/utils/libraryTopics.js';

test('legacy article typography cannot change the published reading font or scale', () => {
  const before = { font_family: 'Georgia, serif', font_size: 29, line_height: 1.1, text_color: '#ffffff' };
  const style = publicationReadingStyle({ design_settings: before });
  assert.equal(style.fontFamily, 'Roboto, Arial, sans-serif');
  assert.equal(style.fontSize, '18px');
  assert.equal(style.lineHeight, 1.85);
  assert.notEqual(style.color, '#ffffff');
  assert.equal(before.font_family, 'Georgia, serif');
});

test('Learn contains only its configured research branch, including nested topics', () => {
  const categories = [{ slug: 'cardiology' }, { slug: 'education', children: [
    { slug: 'mastering-research', children: [{ slug: 'case-reports' }] },
  ] }, { slug: 'dermatology' }];
  const topics = researchTopics(categories, 'mastering-research');
  assert.deepEqual(topics.map(topic => [topic.slug, topic.depth]), [['mastering-research', 0], ['case-reports', 1]]);
  assert.equal(researchCategory('cardiology', topics, 'mastering-research'), 'mastering-research');
  assert.equal(researchCategory('case-reports', topics, 'mastering-research'), 'case-reports');
  assert.equal(categories.length, 3);
});

test('Learn fails closed while its research category has not loaded', () => {
  assert.deepEqual(researchTopics([], 'research'), []);
  assert.equal(researchCategory('cardiology', [], 'research'), 'research');
});
