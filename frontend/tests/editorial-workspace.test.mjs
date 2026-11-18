import assert from 'node:assert/strict';
import test from 'node:test';
import { articleFilters, articlePath, editorialStatus, localScheduleToISO, readinessIssues } from '../src/pages/dashboard/posts/workspace.js';

test('dashboard deep links retain search, workflow and taxonomy filters',()=>{
 const filters=articleFilters(new URLSearchParams('q=clinical&status=scheduled&category=8&author=2&page=3'));
 assert.equal(filters.q,'clinical');assert.equal(filters.status,'scheduled');assert.equal(filters.page,3);assert.equal(filters.category,'8');assert.equal(filters.author,'2');assert.equal(filters.per_page,'20');
 assert.equal(articleFilters(new URLSearchParams('per_page=1000&type=invalid')).per_page,'20');
});
test('scheduled status is a derived state without replacing existing publication models',()=>{
 assert.equal(editorialStatus({status:'publish',published_at:'2030-01-01T00:00:00Z'},Date.parse('2026-01-01')),'scheduled');
 assert.equal(editorialStatus({status:'draft',published_at:'2030-01-01T00:00:00Z'},Date.parse('2026-01-01')),'draft');
 assert.equal(editorialStatus({status:'publish',published_at:'2025-01-01T00:00:00Z'},Date.parse('2026-01-01')),'publish');
});
test('article links preserve the existing database and page routes',()=>{
 assert.equal(articlePath({post_type:'post',slug:'existing-slug',categories:[{slug:'research'}]}),'/database/research/existing-slug');
 assert.equal(articlePath({post_type:'page',slug:'existing-page'}),'/page/existing-page');
});
test('editorial checks report real missing metadata, not invented performance scores',()=>{
 assert.equal(readinessIssues({}).length,4);
 assert.equal(readinessIssues({excerpt:'Summary',featured_image:'/image.webp',seo_title:'Title',seo_description:'Description',categories:[1]}).length,0);
 assert.equal(localScheduleToISO('not-a-date'),'');
 assert.equal(localScheduleToISO('2030-01-01T00:00:00Z'),'2030-01-01T00:00:00.000Z');
});
