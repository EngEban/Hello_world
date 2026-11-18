import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import test from 'node:test';

const source = new URL('../src/', import.meta.url);
const read = file => readFileSync(new URL(file, source), 'utf8');

test('one approved navy, blue and light-blue palette backs legacy aliases', () => {
  const css = read('styles/global/design-system.css');
  assert.match(css, /--rr-primary:\s*#062b80;/i);
  assert.match(css, /--rr-primary-strong:\s*var\(--rr-primary\);/);
  assert.match(css, /--rr-secondary:\s*#126ac6;/i);
  assert.match(css, /--rr-accent:\s*#4fb9fc;/i);
  // Status semantics remain independent of the brand palette.
  assert.match(css, /--rr-success:\s*#087f5b;/i);
  assert.match(css, /--rr-danger:\s*#c92a2a;/i);
});

test('homepage, shared brand UI and publication color aliases inherit shared brand tokens', () => {
  // brand-ui.css defines the --rh-* tokens every public page (About included) uses.
  assert.match(read('styles/global/brand-ui.css'), /--rh-navy:\s*var\(--rr-primary\)/);
  assert.match(read('styles/global/brand-ui.css'), /--rh-blue:\s*var\(--rr-secondary\)/);
  assert.match(read('styles/global/brand-ui.css'), /--rh-sky:\s*var\(--rr-accent\)/);
  assert.match(read('styles/pages/publication.css'), /--pub-navy:\s*var\(--rh-navy, var\(--rr-primary\)\);\s*--pub-blue:\s*var\(--rh-blue, var\(--rr-secondary\)\)/);
  assert.match(read('styles/pages/home.css'), /--rh-navy:\s*var\(--rr-primary\)/);
  assert.match(read('styles/pages/home.css'), /--rh-sky:\s*var\(--rr-accent\)/);
});

test('retired primary brand shades cannot return in public, dashboard or tool styles', () => {
  function check(dir) {
    for (const file of readdirSync(dir, { withFileTypes: true })) {
      const url = new URL(file.name + (file.isDirectory() ? '/' : ''), dir);
      if (file.isDirectory()) check(url);
      else if (file.name.endsWith('.css')) {
        assert.doesNotMatch(readFileSync(url, 'utf8'), /#(?:0c2c59|09265b|001855|08275f|041d4a|081c39|145ecc|1769c2|48b4ff)\b|rgba?\(\s*0\s*,\s*24\s*,\s*85\b/i, url.pathname);
      }
    }
  }
  check(source);
});

test('approved text/action combinations retain AA contrast on white', () => {
  function luminance(hex) {
    const channels = [0,2,4].map(i => parseInt(hex.slice(i,i+2),16)/255).map(v => v <= .04045 ? v/12.92 : ((v+.055)/1.055)**2.4);
    return channels[0]*.2126 + channels[1]*.7152 + channels[2]*.0722;
  }
  for (const color of ['062b80','126ac6']) assert.ok(1.05/(luminance(color)+.05) >= 4.5);
});
