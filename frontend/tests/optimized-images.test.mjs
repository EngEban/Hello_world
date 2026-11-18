import assert from 'node:assert/strict';
import test from 'node:test';
import manifest from '../src/config/optimizedImages.json' with { type: 'json' };
import { optimizedImageData, optimizedImageUrl } from '../src/utils/optimizedImages.js';
import { mobileHeroImage } from '../src/config/heroImages.js';

test('known source URLs use real WebP files and small card derivatives', () => {
  const source = Object.keys(manifest)[0];
  assert(source, 'The image catalog must not be empty');
  assert.equal(optimizedImageUrl(source), `/optimized-images/${manifest[source].file}`);
  assert.equal(optimizedImageUrl(source, true), `/optimized-images/${manifest[source].small}`);
  assert.equal(optimizedImageUrl(optimizedImageUrl(source), true), optimizedImageUrl(source, true));
});
test('public nested data changes image URLs without altering content or article paths', () => {
  const source = Object.keys(manifest)[0];
  const input = {slug:'original-url',authors:[{avatar:source}],content:`<p>Stored HTML ${source}</p>`};
  const output = optimizedImageData(input);
  assert.equal(output.authors[0].avatar, optimizedImageUrl(source));
  assert.equal(output.slug, input.slug);
  assert.equal(output.content, input.content);
  assert.equal(input.authors[0].avatar, source);
});
test('unknown URLs and vector images remain unchanged rather than guessing extensions', () => {
  for (const value of ['https://example.org/new-image.png','/favicon.svg','/database/original',null]) assert.equal(optimizedImageUrl(value), value);
});
test('mobile hero uses its smaller WebP while custom dashboard URLs are retained', () => {
  assert.equal(mobileHeroImage('/hero-images/tools.webp?v=optimized-1'),'/hero-images/tools-mobile.webp?v=optimized-1');
  assert.equal(mobileHeroImage('https://example.org/banner.webp'),'https://example.org/banner.webp');
});
