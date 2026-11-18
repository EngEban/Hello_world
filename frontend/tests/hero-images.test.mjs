import assert from 'node:assert/strict';
import test from 'node:test';
import { HERO_IMAGES, pageHeroImage } from '../src/config/heroImages.js';

test('page-specific photos replace the old repeated placeholder', () => {
  const old = 'https://resref.com/wp-content/uploads/2026/05/hand-medical-glove-pointing-virtual-screen-medical-technology-1.jpg';
  assert.equal(pageHeroImage({tools_hero_image_url:old,page_banner_image_url:old},'tools'), HERO_IMAGES.tools);
  assert.notEqual(pageHeroImage({},'about'),pageHeroImage({},'opportunities'));
});
test('dashboard page, category and shared custom images still win', () => {
  assert.equal(pageHeroImage({about_hero_image_url:'/custom.webp'},'about'),'/custom.webp');
  assert.equal(pageHeroImage({page_banner_image_url:'/shared.webp'},'tools'),'/shared.webp');
  assert.equal(pageHeroImage({},'database','/category.webp'),'/category.webp');
});
test('category and policy pages have appropriate fallback photos', () => {
  assert.equal(pageHeroImage({},'', '', '/database/cardiology'),HERO_IMAGES.database);
  assert.equal(pageHeroImage({},'', '', '/privacy-policy'),HERO_IMAGES.legal);
});
