import { ArrowRight, BarChart3, BellRing, BookOpen, Code2, ExternalLink, Images, Inbox, Keyboard, LayoutDashboard, LifeBuoy, Search, Settings, Sparkles, UserCog, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import '../../../styles/dashboard/dash-admin.css';

// Task-based help topics. Each one: what it is for, how to do the common tasks, and where to go.
const TOPICS = [
  {
    id: 'start', icon: LayoutDashboard, title: 'Getting around the dashboard',
    summary: 'The Overview shows what needs attention; the sidebar groups every area by job.',
    steps: [
      'Open the command palette with Ctrl+K (⌘K on Mac) to jump to any page or search articles by title.',
      'Use the Quick Action button in the top bar for frequent jobs: new article, new page, upload media, new opportunity or service.',
      'Numbers on sidebar items count work waiting for you, such as unread messages or articles in review.',
      'The account menu (top right) holds your profile, the public website link and sign out.',
    ],
    links: [['Overview', '/dashboard'], ['Reports', '/dashboard/reports']],
  },
  {
    id: 'articles', icon: BookOpen, title: 'Write and publish articles',
    summary: 'Blog posts, database resources and standalone pages are all managed in Posts & Pages.',
    steps: [
      'Start a new article from Quick Action or Articles → New article. Pages use the Pages view.',
      'Use Visual mode for normal writing, HTML mode for precise markup, and Preview mode to check content.',
      'Choose the workflow status: Draft keeps it private, In review asks an editor to approve, Scheduled publishes automatically at the chosen time, Published makes it live.',
      'Fill in the excerpt, featured image, categories, tags and SEO title/description — the Overview’s Content health card lists articles missing them.',
      'Save at any time with Ctrl+S (⌘S on Mac) while the editor is open.',
    ],
    links: [['New article', '/dashboard/posts?new=post'], ['All articles', '/dashboard/posts'], ['Categories', '/dashboard/categories'], ['Tags', '/dashboard/tags'], ['Authors', '/dashboard/authors'], ['FAQ manager', '/dashboard/faq']],
  },
  {
    id: 'media', icon: Images, title: 'Images and uploads',
    summary: 'The Media Library holds every image used on the site.',
    steps: [
      'Upload an image file or register an external image URL.',
      'Pick images straight from the library in the article editor and image settings, or copy an image URL for featured images, article images and author photos.',
      'Add alt text so images are accessible and searchable.',
    ],
    links: [['Media library', '/dashboard/media']],
  },
  {
    id: 'site', icon: Settings, title: 'Website text, images and settings',
    summary: 'Common frontend text and images are editable without touching code.',
    steps: [
      'Website content edits page sections visually (hero text, images and calls to action).',
      'Settings holds every public site setting — homepage hero, contact details, navigation labels, footer description and page headers — grouped into sections with a search box.',
      'Changed fields are highlighted; the save bar shows how many changes are unsaved. Save with the button or Ctrl+S (⌘S).',
      'Links must be http(s), mailto or tel links, or paths starting with "/". Secrets and API keys never go in settings.',
    ],
    links: [['Website content', '/dashboard/content-studio'], ['Settings', '/dashboard/settings']],
  },
  {
    id: 'engagement', icon: Inbox, title: 'Messages, forms and opportunities',
    summary: 'Everything visitors send you, and everything you publish for them to apply to.',
    steps: [
      'Inbox collects contact messages; Forms & Applications holds team applications (with CV downloads) and other submissions.',
      'Update each item’s status so the team knows what has been handled.',
      'Research Opportunities and Services are created, published and closed from their own pages; service requests appear on the Services page.',
    ],
    links: [['Inbox', '/dashboard/contacts'], ['Forms & applications', '/dashboard/forms'], ['Opportunities', '/dashboard/opportunities'], ['Services', '/dashboard/services']],
  },
  {
    id: 'people', icon: UserCog, title: 'Users, roles and permissions',
    summary: 'Give people the access they need and nothing more.',
    steps: [
      'Users lists every account with role, plan, dashboard access and status. Click a row (or its ⋯ menu) to edit in a side panel.',
      'Roles: Viewer reads; Contributor also writes content; Editor runs publishing, forms, opportunities, services, exports and the audit log; Administrator can do everything, including users and settings. Members have no dashboard access.',
      'The editor explains exactly what the chosen role allows before you save. The server checks every change again: you cannot grant more than your own role, and only super administrators change billing or super-admin accounts.',
      'Team / Volunteers manages the public team directory.',
    ],
    links: [['Users', '/dashboard/users'], ['Add a user', '/dashboard/users?new=1'], ['Team', '/dashboard/team'], ['Roles reference', '/dashboard/settings']],
  },
  {
    id: 'premium', icon: Sparkles, title: 'Premium access, plans and tool limits',
    summary: 'Decide which tools are free, premium-only or limited.',
    steps: [
      'Premium controls → Features: switch Free or Premium access per tool; switches save immediately.',
      'Plans prepares Free and Premium plans. Stripe price IDs are references only; card details are never stored.',
      'Usage limits cap expensive tools per tier and period, e.g. 50 Journal Finder searches per day for Free users.',
      'Research Analyzer has its own page for access, quotas and plans.',
    ],
    links: [['Premium controls', '/dashboard/premium-controls'], ['Usage limits', '/dashboard/premium-controls?tab=limits'], ['Research Analyzer', '/dashboard/research-analyzer']],
  },
  {
    id: 'reports', icon: BarChart3, title: 'Reports, exports and the audit trail',
    summary: 'Numbers for leadership, files for analysis and a record of every change.',
    steps: [
      'Reports → Analytics charts users, content, requests, opportunities, forms and team activity.',
      'Reports → Exports downloads any module as CSV (or Excel, JSON, PDF from the ⋯ menu). Exports only include data your role can read.',
      'Reports → Activity log filters every dashboard action by area, action and text; click an entry for details.',
    ],
    links: [['Analytics', '/dashboard/reports'], ['Exports', '/dashboard/reports?tab=exports'], ['Activity log', '/dashboard/reports?tab=activity']],
  },
  {
    id: 'notifications', icon: BellRing, title: 'Account notifications',
    summary: 'Send in-account notices to everyone, a group, or chosen people.',
    steps: [
      'Pick an audience (the count shows how many active accounts it reaches), a type, a title and the message; add an optional internal or HTTPS link.',
      'Check the live preview, then send — you are asked to confirm because notifications cannot be recalled.',
      'History shows read progress per campaign; reuse a past notification as a starting point.',
    ],
    links: [['Notifications', '/dashboard/notifications']],
  },
];

// The original "map of the application", kept for developers and advanced edits.
const AREAS = [
  ['Blog posts and database resources', 'Dashboard → Posts & Pages', 'Use Visual mode for normal writing, HTML mode for precise markup, Preview mode to check content, and the workflow selector for drafts or published content.'],
  ['Images and uploads', 'Dashboard → Media Library', 'Upload an image file or register an external image URL. Copy its URL for featured images, article images, and author photos.'],
  ['Blog bylines', 'Dashboard → Authors', 'Create and update the author names shown on published articles.'],
  ['Common frontend text', 'Dashboard → Site Settings', 'Edit homepage hero text, contact details, and footer description.'],
  ['Page layouts and design sections', 'frontend/src/pages/site/', 'Edit the separate React page file when you want to rearrange sections or add a new visual block.'],
  ['Shared frontend navigation and assets', 'frontend/src/config/site.js and frontend/src/siteData.js', 'Use these files for routes, menu labels, image URLs, partner logos, and social links.'],
  ['Backend data models and advanced administration', 'backend/blog/ and backend/dashboard/', 'Use the custom dashboard for daily work. Use Django admin or backend development when adding new database fields, permission rules, or advanced workflows.'],
];

const SHORTCUTS = [
  [['Ctrl', 'K'], 'Open the command palette: jump to a page or find an article', 'Anywhere'],
  [['⌘', 'K'], 'Same on Mac', 'Anywhere'],
  [['Ctrl', 'S'], 'Save (⌘S on Mac)', 'Article editor, Website content, Settings'],
  [['Esc'], 'Close the palette, menus, side panels and dialogs', 'Anywhere'],
  [['↑', '↓'], 'Move through palette results and ⋯ menus', 'Palette, menus'],
  [['Enter'], 'Open the highlighted palette result', 'Palette'],
];

const POPULAR = [
  ['Write a new article', '/dashboard/posts?new=post'],
  ['Upload an image', '/dashboard/media'],
  ['Change homepage text', '/dashboard/settings'],
  ['Add a user', '/dashboard/users?new=1'],
  ['Export data as CSV', '/dashboard/reports?tab=exports'],
  ['Make a tool premium-only', '/dashboard/premium-controls'],
];

export default function DashboardGuidePage() {
  const [query, setQuery] = useState('');
  const q = query.trim().toLowerCase();
  const topics = useMemo(() => TOPICS.filter(topic => !q || [topic.title, topic.summary, ...topic.steps, ...topic.links.map(([label]) => label)].join(' ').toLowerCase().includes(q)), [q]);
  const areas = AREAS.filter(row => !q || row.join(' ').toLowerCase().includes(q));
  const shortcuts = SHORTCUTS.filter(row => !q || `${row[0].join(' ')} ${row[1]} ${row[2]} shortcut keyboard`.toLowerCase().includes(q));
  const nothing = !topics.length && !areas.length && !shortcuts.length;

  return (
    <div className="dash-adm-page dash-adm-guide">
      <AdminPageHeader eyebrow="Help centre" title="Editing Guide" text="How to get everyday work done in the dashboard, where each setting lives, and a map of the application so simple edits stay simple and advanced changes remain organized." actions={<a className="admin-button admin-button-secondary" href="/" target="_blank" rel="noreferrer"><ExternalLink size={15} /> Open Website</a>} />

      <section className="dash-adm-guide-hero">
        <div>
          <span className="dash-adm-guide-icon" aria-hidden="true"><LifeBuoy size={22} /></span>
          <h2>What do you want to do?</h2>
          <label className="dash-search-field"><Search size={17} aria-hidden="true" /><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search the guide, e.g. “schedule”, “export”, “premium”" aria-label="Search the guide" />{query && <button type="button" className="dash-adm-clear" onClick={() => setQuery('')} aria-label="Clear search"><X size={14} /></button>}</label>
          <div className="dash-adm-guide-popular">{POPULAR.map(([label, to]) => <Link key={label} to={to}>{label} <ArrowRight size={13} /></Link>)}</div>
        </div>
      </section>

      {!q && <nav className="dash-adm-guide-toc" aria-label="Guide topics">{TOPICS.map(topic => { const Icon = topic.icon; return <a key={topic.id} href={`#guide-${topic.id}`}><Icon size={15} /> {topic.title}</a>; })}<a href="#guide-shortcuts"><Keyboard size={15} /> Keyboard shortcuts</a><a href="#guide-map"><Code2 size={15} /> Application map</a></nav>}

      {nothing && <div className="dashboard-card dash-adm-card"><p className="dash-adm-hint">Nothing in the guide matches “{query}”. Try another word, or press Ctrl+K to search pages and articles.</p></div>}

      <div className="dash-adm-guide-topics">
        {topics.map(topic => {
          const Icon = topic.icon;
          return (
            <article className="dashboard-card dash-adm-guide-topic" id={`guide-${topic.id}`} key={topic.id}>
              <header><span className="dash-adm-guide-icon" aria-hidden="true"><Icon size={18} /></span><div><h2>{topic.title}</h2><p>{topic.summary}</p></div></header>
              <ol>{topic.steps.map(step => <li key={step}>{step}</li>)}</ol>
              <div className="dash-adm-guide-links">{topic.links.map(([label, to]) => <Link key={to} to={to}>{label} <ArrowRight size={13} /></Link>)}</div>
            </article>
          );
        })}
      </div>

      {shortcuts.length > 0 && (
        <section className="dashboard-card dash-adm-card" id="guide-shortcuts">
          <div className="dash-adm-section-head"><div><h2>Keyboard shortcuts</h2><p>Work faster without leaving the keyboard.</p></div></div>
          <ul className="dash-adm-shortcuts">
            {shortcuts.map(([keys, text, where]) => <li key={`${keys.join('+')}-${text}`}><span className="dash-adm-keys">{keys.map(key => <kbd className="dash-adm-kbd" key={key}>{key}</kbd>)}</span><span><strong>{text}</strong><small>{where}</small></span></li>)}
          </ul>
        </section>
      )}

      {areas.length > 0 && (
        <section className="dashboard-card dash-adm-card" id="guide-map">
          <div className="dash-adm-section-head"><div><h2>Application map</h2><p>Where each kind of change is made — in the dashboard or in the code.</p></div></div>
          <div className="dash-adm-guide-map">{areas.map(([title, location, text]) => <article key={title}><h3>{title}</h3><code>{location}</code><p>{text}</p></article>)}</div>
          <div className="dash-adm-boundary"><h3>Important boundary</h3><p>The React dashboard can manage users, content, services, opportunities, forms, reports, and saved settings exposed by the API. Changing database schema, adding new permission families, or installing new export engines belongs in backend development.</p></div>
        </section>
      )}
    </div>
  );
}
