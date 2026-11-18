export function flattenTopics(categories, depth = 0) {
  return categories.flatMap(item => [{ ...item, depth }, ...flattenTopics(item.children || [], depth + 1)]);
}

// Only categories with a published article, directly or in a subcategory.
export function publishedTopics(categories) {
  return categories.flatMap(item => {
    const children = publishedTopics(item.children || []);
    return (item.count || item.post_count || children.length) ? [{ ...item, children }] : [];
  });
}

export function researchTopics(categories, rootSlug) {
  const root = flattenTopics(categories).find(topic => topic.slug === rootSlug);
  return root ? flattenTopics([root]) : [];
}

export function researchCategory(requested, topics, rootSlug) {
  return topics.some(topic => topic.slug === requested) ? requested : rootSlug;
}
