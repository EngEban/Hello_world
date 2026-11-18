import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import manifest from '../src/config/optimizedImages.json' with { type: 'json' };
import { optimizedImageEntry, optimizedImageUrl } from '../src/utils/optimizedImages.js';
import * as finder from '../src/data/journalFinder/matching_logic.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const walk = dir => fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? walk(path.join(dir, entry.name)) : [path.join(dir, entry.name)]);

test('the journal list is static JSON fetched by the Journal Finder only, never bundled as JavaScript', () => {
  assert.ok(fs.existsSync(path.join(root, 'src/data/journalFinder/journals_db.json')));
  assert.ok(!fs.existsSync(path.join(root, 'src/data/journalFinder/journals_db.js')), 'the old 2.7 MB JS module must stay removed');
  const importers = walk(path.join(root, 'src')).filter(file => /\.(jsx?|mjs)$/.test(file) && /journals_db/.test(fs.readFileSync(file, 'utf8')));
  assert.deepEqual(importers.map(file => path.relative(root, file).replaceAll('\\', '/')), ['src/features/journalFinder/journalFinderModel.js']);
  assert.match(read('src/features/journalFinder/journalFinderModel.js'), /journals_db\.json\?url/);
});

test('journal matching works once the fetched list is handed over', () => {
  assert.equal(finder.hasJournalDatabase(), false);
  const journals = JSON.parse(read('src/data/journalFinder/journals_db.json'));
  assert.ok(journals.length > 5000);
  finder.setJournalDatabase(journals);
  assert.equal(finder.hasJournalDatabase(), true);
  const results = finder.match_categories_to_journals('Randomized controlled trial of metformin in type 2 diabetes mellitus', {
    abstract: 'Glycaemic control, HbA1c and insulin resistance in adults with diabetes.', keywords: 'diabetes, endocrinology',
  });
  assert.ok(Array.isArray(results) && results.length > 0, 'a diabetes manuscript must match journals');
});

test('image catalog entries expose intrinsic sizes for layout-shift-free article images', () => {
  const source = Object.keys(manifest)[0];
  const entry = optimizedImageEntry(source);
  assert.ok(entry && entry.width > 0 && entry.height > 0);
  assert.equal(optimizedImageEntry(optimizedImageUrl(source)), entry);
  assert.equal(optimizedImageEntry('https://example.org/unknown.png'), null);
  assert.equal(optimizedImageEntry(null), null);
});

test('React and the router are split into a long-cacheable vendor chunk', () => {
  assert.match(read('vite.config.js'), /name: 'react-vendor'/);
});

test('pages do not nest a second <main> inside the public layout', () => {
  for (const file of ['src/pages/site/HomePage.jsx', 'src/components/common/RouteErrorBoundary.jsx']) {
    assert.doesNotMatch(read(file), /<main (className|ref|role)=/, `${file} renders inside the layout's <main>`);
  }
});
