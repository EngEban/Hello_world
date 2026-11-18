"""Where imported WordPress content lives in the new site (mirrors the React routes)."""

WP_UPLOADS_STORAGE_PREFIX = 'wp-content/uploads/'

# First path segments that belong to the new site's own routes (frontend/src/main.jsx
# and resref/urls.py). The importer never creates redirects for them, so an old
# WordPress page such as /journal-finder/ cannot hijack a live route. Staff can
# still add such a redirect by hand in Django admin. Keep in sync with main.jsx.
RESERVED_FIRST_SEGMENTS = {
    'api', 'admin', 'static', 'media', 'assets', 'dashboard', 'home', 'homepage', 'database', 'articles',
    'advanced-search', 'questionnaires', 'questionnaires-2', 'journal-finder', 'tools', 'sample-size-calculator',
    'reference-generator', 'research-analyzer', 'consultation', 'expert-consultation', 'opportunities',
    'research-opportunities', 'join', 'join-our-team', 'about', 'about-us', 'contact', 'contact-us', 'faq',
    'terms-of-use', 'privacy-policy', 'cookie-policy', 'sign-in', 'auth', 'register', 'account', 'newsletter',
    'authors', 'page',
}
# Segments whose whole sub-tree belongs to the new site.
RESERVED_PREFIXES = {'api', 'admin', 'static', 'media', 'assets', 'dashboard', 'database', 'tools', 'authors', 'page', 'account'}


def post_public_path(post):
    """Same rule as ``articlePath`` in frontend/src/utils/articleContent.js."""
    if post.post_type == 'page':
        return f'/{post.slug}'
    category = post.categories.all().first()
    return f'/database/{category.slug if category else "research"}/{post.slug}'
