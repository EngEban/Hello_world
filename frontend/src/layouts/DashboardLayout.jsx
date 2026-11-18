import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import {
  BarChart3,
  Contact,
  Bell,
  BookOpen,
  Blocks,
  BriefcaseBusiness,
  ChevronDown,
  ChevronLeft,
  ClipboardList,
  ExternalLink,
  FilePlus2,
  FileStack,
  FileText,
  FolderTree,
  HelpCircle,
  Images,
  Inbox,
  KeyRound,
  Keyboard,
  LifeBuoy,
  LineChart,
  LayoutDashboard,
  LogOut,
  Menu,
  PenLine,
  PencilLine,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Tags,
  UserCog,
  Upload,
  UserPlus,
  Users,
  X,
} from 'lucide-react';
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { DashboardApi } from '../api/dashboardApi';
import { UNAUTHORIZED_EVENT } from '../api/apiClient';
import { permissionsAllow } from '../pages/dashboard/users/adminShared';
import LoadingState from '../components/common/LoadingState';
import { ASSETS } from '../siteData';
import '../styles/dashboard/dashboard-workspace.css';
import '../styles/dashboard/dashboard-brand.css';
import '../styles/dashboard/dashboard-ui.css';

const navGroups = [
  {
    label: 'Workspace',
    links: [
      [LayoutDashboard, '/dashboard', 'Overview', true],
    ],
  },
  {
    label: 'Content',
    links: [
      [BookOpen, '/dashboard/posts', 'Articles'],
      [FileStack, '/dashboard/posts?type=page', 'Pages'],
      [Images, '/dashboard/media', 'Media Library'],
      [FolderTree, '/dashboard/categories', 'Categories'],
      [Tags, '/dashboard/tags', 'Tags'],
      [PenLine, '/dashboard/authors', 'Authors'],
      [HelpCircle, '/dashboard/faq', 'FAQ Manager'],
      [Blocks, '/dashboard/content-studio', 'Website content'],
      [Contact, '/dashboard/team-page', 'Team Page'],
    ],
  },
  {
    label: 'Engagement',
    links: [
      [Inbox, '/dashboard/contacts', 'Inbox'],
      [FileText, '/dashboard/forms', 'Forms & Applications'],
      [UserPlus, '/dashboard/applications?tab=cards', 'Join Our Team'],
      [BriefcaseBusiness, '/dashboard/opportunities', 'Research Opportunities'],
      [ClipboardList, '/dashboard/services', 'Services'],
    ],
  },
  {
    label: 'People',
    links: [
      [UserCog, '/dashboard/users', 'Users'],
      [Users, '/dashboard/team', 'Team / Volunteers'],
    ],
  },
  {
    label: 'Insights & tools',
    links: [
      [LineChart, '/dashboard/reports', 'Reports'],
      [BarChart3, '/dashboard/research-analyzer', 'Research Analyzer'],
      [Sparkles, '/dashboard/premium-controls', 'Premium Controls'],
    ],
  },
  {
    label: 'System',
    links: [
      [Bell, '/dashboard/notifications', 'Notifications'],
      [ShieldCheck, '/dashboard/settings', 'Settings'],
      [KeyRound, '/dashboard/roles', 'Roles & Permissions'],
      [LifeBuoy, '/dashboard/guide', 'Guide'],
    ],
  },
];

// Frequently used create/manage actions, shown in the Quick Action menu and the command palette,
// each with the permission it needs.
const QUICK_ACTIONS = [
  [PencilLine, '/dashboard/posts?new=post', 'New article', 'content.create'],
  [FilePlus2, '/dashboard/posts?new=page', 'New page', 'content.create'],
  [Upload, '/dashboard/media', 'Upload media', 'media.create'],
  [BriefcaseBusiness, '/dashboard/opportunities?new=1', 'New research opportunity', 'opportunities.create'],
  [ClipboardList, '/dashboard/services?new=1', 'New service', 'services.create'],
  [FolderTree, '/dashboard/categories', 'Manage categories', 'taxonomy.edit'],
];

const routePath = to => to.split('?')[0];
const routeType = to => new URLSearchParams(to.split('?')[1] || '').get('type') || '';

// Routes reachable from inside pages rather than the sidebar, so the breadcrumb still names them.
const EXTRA_SECTION_LABELS = { '/dashboard/applications': 'Team applications' };

const ALWAYS_ENABLED_ROUTES = new Set(['/dashboard', '/dashboard/guide']);
// Not part of the editable roles, so even the regular Admin role does not see them.
const SUPER_ADMIN_ROUTES = new Set(['/dashboard/team-page']);

// Each permission module lists the routes it opens; a module is enabled when the role can view it.
function canOpenDashboardRoute(target, enabledRoutes, knownRoutes) {
  const to = routePath(target).replace(/\/$/, '') || '/dashboard';
  if (enabledRoutes.has(to) || ALWAYS_ENABLED_ROUTES.has(to)) return true;
  // A route no module claims (e.g. an unknown URL) is left to the page's own 404 handling.
  return !knownRoutes.has(to);
}

export default function DashboardLayout() {
  const [auth, setAuth] = useState({ status: 'loading', user: null, bootstrap: null });
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('resref_dashboard_sidebar') === 'collapsed');
  const [search, setSearch] = useState('');
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState('');
  const [commandIndex, setCommandIndex] = useState(0);
  const [articleResults, setArticleResults] = useState([]);
  const commandInputRef = useRef(null);
  const sidebarRef = useRef(null);
  const mobileMenuRef = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();
  const [loadAttempt, setLoadAttempt] = useState(0);
  useEffect(() => {
    if(!mobileOpen) return undefined;
    const previous=document.body.style.overflow;
    const menuButton=mobileMenuRef.current;
    document.body.style.overflow='hidden';
    const focusable=()=>[...sidebarRef.current.querySelectorAll('a[href],button:not([disabled])')];
    focusable()[0]?.focus();
    const handleKey=event=>{
      if(event.key==='Escape')setMobileOpen(false);
      if(event.key==='Tab'){const items=focusable();if(event.shiftKey&&document.activeElement===items[0]){event.preventDefault();items.at(-1)?.focus();}else if(!event.shiftKey&&document.activeElement===items.at(-1)){event.preventDefault();items[0]?.focus();}}
    };
    document.addEventListener('keydown',handleKey);
    return ()=>{document.body.style.overflow=previous;document.removeEventListener('keydown',handleKey);menuButton?.focus();};
  },[mobileOpen]);

  // "Add to Home Screen" from the dashboard should reopen the dashboard as an app.
  useEffect(() => {
    const link=document.querySelector('link[rel="manifest"]');
    if(!link) return undefined;
    const previous=link.getAttribute('href');
    link.setAttribute('href',`${import.meta.env.BASE_URL}dashboard.webmanifest`);
    return ()=>link.setAttribute('href',previous);
  },[]);

  useEffect(() => {
    const controller = new AbortController();
    DashboardApi.getBootstrap({ signal: controller.signal })
      .then(data => setAuth({ status: 'ready', user: data.user, bootstrap: data }))
      .catch(error => {
        if (error.name === 'AbortError') return;
        // Only an auth answer means "sign in"; a network/server error must not
        // throw the user out of the dashboard.
        if (error.status === 401 || error.status === 403) setAuth({ status: 'login', user: null, bootstrap: null });
        else setAuth({ status: 'error', user: null, bootstrap: null, message: error.message });
      });
    return () => controller.abort();
  }, [loadAttempt]);

  useEffect(() => {
    const onUnauthorized = event => {
      if (event.detail?.area === 'dashboard') setAuth({ status: 'login', user: null, bootstrap: null });
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  useEffect(() => {
    localStorage.setItem('resref_dashboard_sidebar', collapsed ? 'collapsed' : 'open');
  }, [collapsed]);

  useEffect(() => {
    const onKeyDown = event => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setCommandOpen(open => !open);
      }
      if (event.key === 'Escape') setCommandOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  useEffect(() => {
    setCommandOpen(false);
    setCommandQuery('');
  }, [location.pathname]);

  const notifications = auth.bootstrap?.notifications || [];
  const badges = auth.bootstrap?.badges || {};
  const currentType = new URLSearchParams(location.search).get('type') || '';
  const isActiveLink = (to, end) => routePath(to) === location.pathname
    ? (routePath(to) !== '/dashboard/posts' || routeType(to) === (currentType === 'page' ? 'page' : ''))
    : !end && location.pathname.startsWith(`${routePath(to)}/`);
  const currentSection = navGroups.flatMap(group=>group.links).find(([,to,,end])=>isActiveLink(to,end))?.[2] || EXTRA_SECTION_LABELS[location.pathname] || 'Overview';
  const knownRoutes = useMemo(() => new Set((auth.bootstrap?.modules || []).flatMap(item => item.routes || [item.route])), [auth.bootstrap]);
  const enabledRoutes = useMemo(() => new Set((auth.bootstrap?.modules || []).filter(item => item.enabled !== false).flatMap(item => item.routes || [item.route])), [auth.bootstrap]);
  const quickActions = useMemo(() => QUICK_ACTIONS.filter(([, to, , permission]) => canOpenDashboardRoute(to, enabledRoutes, knownRoutes)
    && permissionsAllow(auth.bootstrap?.permissions, permission, auth.user?.is_superuser)), [enabledRoutes, knownRoutes, auth]);
  const visibleGroups = useMemo(() => navGroups
    .map(group => ({ ...group, links: group.links.filter(([, to]) => canOpenDashboardRoute(to, enabledRoutes, knownRoutes) && (!SUPER_ADMIN_ROUTES.has(to) || auth.bootstrap?.is_super_admin)) }))
    .filter(group => group.links.length), [enabledRoutes, knownRoutes, auth.bootstrap]);
  const routeAllowed = canOpenDashboardRoute(location.pathname, enabledRoutes, knownRoutes);
  const commandItems = useMemo(() => {
    const term = commandQuery.trim().toLowerCase();
    const matches = item => `${item.label} ${item.group}`.toLowerCase().includes(term);
    const actions = quickActions.map(([Icon, to, label]) => ({ Icon, to, label, group: 'Create' })).filter(matches);
    const sections = visibleGroups.flatMap(group => group.links
      .map(([Icon, to, label]) => ({ Icon, to, label, group: group.label }))).filter(matches);
    const articles = articleResults.map(post => ({ Icon: post.post_type === 'page' ? FileStack : BookOpen, to: `/dashboard/posts?${post.post_type === 'page' ? 'type=page&' : ''}edit=${post.id}`, label: post.title || 'Untitled', group: post.post_type === 'page' ? 'Page' : 'Article', key: `post-${post.id}` }));
    return term ? [...articles, ...actions, ...sections] : [...actions.slice(0, 4), ...sections];
  }, [commandQuery, visibleGroups, quickActions, articleResults]);

  useEffect(() => setCommandIndex(0), [commandQuery, articleResults]);

  // Live article/page search inside the command palette.
  useEffect(() => {
    const term = commandQuery.trim();
    if (!commandOpen || term.length < 2 || !enabledRoutes.has('/dashboard/posts')) { setArticleResults([]); return undefined; }
    let active = true;
    const timer = setTimeout(() => {
      Promise.all(['post', 'page'].map(type => DashboardApi.getPosts({ q: term, type, summary_only: 'true', per_page: 5 }).catch(() => ({ results: [] }))))
        .then(([postsData, pagesData]) => { if (active) setArticleResults([...(postsData.results || []).slice(0, 5), ...(pagesData.results || []).slice(0, 3)]); });
    }, 220);
    return () => { active = false; clearTimeout(timer); };
  }, [commandQuery, commandOpen, enabledRoutes]);

  const selectCommand = item => {
    if (!item) return;
    navigate(item.to);
    setCommandOpen(false);
    setCommandQuery('');
  };

  const handleCommandKeys = event => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!commandItems.length) return;
      setCommandIndex(current => (current + (event.key === 'ArrowDown' ? 1 : -1) + commandItems.length) % commandItems.length);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      selectCommand(commandItems[commandIndex]);
    }
  };

  const logout = async () => {
    try {
      await DashboardApi.logout();
    } finally {
      navigate('/dashboard/login');
    }
  };

  const runSearch = event => {
    event.preventDefault();
    const query = search.trim();
    if (!query) return;
    navigate(`/dashboard/posts?q=${encodeURIComponent(query)}`);
  };

  if (auth.status === 'loading') return <main className="login-page rh-tokens rh-dash-login rh-dash-state"><LoadingState /></main>;
  if (auth.status === 'error') {
    return (
      <main className="login-page rh-tokens rh-dash-login rh-dash-state">
        <div className="route-error-card" role="alert">
          <h1>The dashboard could not load</h1>
          <p>{auth.message || 'Please check your connection and try again.'}</p>
          <button type="button" className="admin-button" onClick={() => { setAuth({ status: 'loading', user: null, bootstrap: null }); setLoadAttempt(current => current + 1); }}>Try again</button>
        </div>
      </main>
    );
  }
  if (auth.status === 'login' || !auth.user) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/dashboard/login?next=${encodeURIComponent(next)}`} replace />;
  }

  return (
    <div className={`admin-shell admin-workspace rh-tokens rh-dash ${collapsed ? 'admin-shell-collapsed' : ''} ${mobileOpen ? 'admin-mobile-open' : ''}`}>
      {mobileOpen&&<button className="admin-workspace-backdrop" aria-label="Close dashboard menu" onClick={()=>setMobileOpen(false)}/>}
      <aside ref={sidebarRef} className="admin-sidebar" id="dashboard-navigation" role={mobileOpen?'dialog':undefined} aria-modal={mobileOpen?'true':undefined} aria-label="Dashboard navigation panel">
        <div className="admin-brand">
          <img className="admin-brand-emblem" src={ASSETS.logo} alt="" />
          <div className="admin-brand-lockup">
            <img className="admin-brand-wordmark" src={ASSETS.logoWordmark} alt="ResRef" />
            <span>Editorial workspace</span>
          </div>
          <button
            type="button"
            onClick={() => window.matchMedia('(max-width:1100px)').matches ? setMobileOpen(false) : setCollapsed(current => !current)}
            aria-label={mobileOpen ? 'Close menu' : collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={mobileOpen ? 'Close menu' : collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {mobileOpen ? <X size={18} /> : <ChevronLeft size={16} />}
          </button>
        </div>

        <nav className="admin-nav" aria-label="Dashboard navigation">
          {visibleGroups.map(group => (
            <section key={group.label}>
              <small>{group.label}</small>
              {group.links.map(([Icon, to, text, end]) => {
                const active = isActiveLink(to, end);
                const badge = routeType(to) ? 0 : badges[to];
                return (
                  <Link
                    className={active ? 'active' : ''}
                    aria-current={active ? 'page' : undefined}
                    to={to}
                    key={to}
                    title={badge ? `${text} (${badge} waiting)` : text}
                    onClick={() => setMobileOpen(false)}
                  >
                    <Icon size={17} />
                    <span>{text}</span>
                    {badge > 0 && <em className="admin-nav-badge" aria-label={`${badge} waiting`}>{badge > 99 ? '99+' : badge}</em>}
                  </Link>
                );
              })}
            </section>
          ))}
        </nav>


        <div className="admin-sidebar-footer">
          <a href="/" target="_blank" rel="noreferrer"><ExternalLink size={15} /><span>View Website</span></a>
          <button type="button" onClick={logout}><LogOut size={15} /><span>Log Out</span></button>
        </div>
      </aside>

      <div className="admin-main">
        <header className="admin-topbar">
          <button ref={mobileMenuRef} type="button" className="admin-mobile-menu" onClick={() => setMobileOpen(current => !current)} aria-label={mobileOpen?'Close dashboard menu':'Open dashboard menu'} aria-expanded={mobileOpen} aria-controls="dashboard-navigation">{mobileOpen?<X size={20}/>:<Menu size={20}/>}</button>
          <nav className="admin-workspace-breadcrumb" aria-label="Dashboard breadcrumb"><NavLink to="/dashboard">Workspace</NavLink><span>/</span><strong>{currentSection}</strong></nav>
          <form className="admin-global-search" onSubmit={runSearch}>
            <Search size={17} />
            <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search articles and pages..." aria-label="Search articles and pages" />
            <kbd>Enter</kbd>
          </form>
          <div className="admin-topbar-actions">
            <button type="button" className="admin-command-button" onClick={() => setCommandOpen(true)} aria-label="Open dashboard search">
              <Search size={16} /><span>Go to</span><kbd>Ctrl K</kbd>
            </button>
            <button type="button" className="admin-notification-button" title="Notifications" onClick={() => navigate('/dashboard/notifications')}>
              <Bell size={18} />
              {notifications.length > 0 && <span>{notifications.length}</span>}
            </button>
            {quickActions.length > 0 && <details className="admin-quick-actions">
              <summary className="admin-button"><Plus size={16} /> <span>Quick Action</span></summary>
              <div className="admin-quick-actions-menu" role="menu" aria-label="Create or manage">
                {quickActions.map(([Icon, to, label]) => (
                  <button type="button" role="menuitem" key={to} onClick={event => { event.currentTarget.closest('details')?.removeAttribute('open'); navigate(to); }}>
                    <Icon size={15} />{label}
                  </button>
                ))}
              </div>
            </details>}
            <details className="admin-user-menu">
              <summary className="admin-user-chip" aria-label="Account menu">
                <span>{(auth.user.display_name || auth.user.first_name || auth.user.username || 'U').slice(0, 1).toUpperCase()}</span>
                <div>
                  <strong>{auth.user.display_name || auth.user.first_name || auth.user.username}</strong>
                  <small>{auth.user.role || (auth.user.is_superuser ? 'admin' : 'team member')}</small>
                </div>
                <ChevronDown size={15} className="admin-user-chevron" />
              </summary>
              <div className="admin-quick-actions-menu admin-user-menu-list" role="menu" aria-label="Account">
                <a role="menuitem" href="/" target="_blank" rel="noreferrer"><ExternalLink size={15} />View website</a>
                <button type="button" role="menuitem" onClick={event => { event.currentTarget.closest('details')?.removeAttribute('open'); navigate('/dashboard/guide'); }}><LifeBuoy size={15} />Dashboard guide</button>
                <button type="button" role="menuitem" onClick={event => { event.currentTarget.closest('details')?.removeAttribute('open'); setCommandOpen(true); }}><Keyboard size={15} />Search &amp; shortcuts (Ctrl K)</button>
                <hr />
                <button type="button" role="menuitem" className="is-danger" onClick={logout}><LogOut size={15} />Log out</button>
              </div>
            </details>
          </div>
        </header>
        <main className="admin-content">
          {routeAllowed
            ? <Suspense fallback={<LoadingState />}><Outlet context={{ user: auth.user, bootstrap: auth.bootstrap }} /></Suspense>
            : <div className="route-error-card admin-no-access" role="alert">
                <KeyRound size={22} aria-hidden="true" />
                <h1>This section is not part of your role</h1>
                <p>Your role does not include {currentSection}. Ask an administrator to change your role if you need it.</p>
                <Link className="admin-button" to="/dashboard">Back to the overview</Link>
              </div>}
        </main>
      </div>
      {commandOpen && (
        <div className="admin-command-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) setCommandOpen(false); }}>
          <section className="admin-command-dialog" role="dialog" aria-modal="true" aria-label="Find a dashboard section" onKeyDown={handleCommandKeys}>
            <div className="admin-command-search"><Search size={19} /><input ref={commandInputRef} autoFocus value={commandQuery} onChange={event => setCommandQuery(event.target.value)} placeholder="Search articles, pages, sections or actions…" aria-label="Find a dashboard section" /><kbd>ESC</kbd></div>
            <div className="admin-command-results">
              {commandItems.length ? commandItems.map((item, index) => (
                <button type="button" key={item.key || `${item.group}-${item.to}`} className={index === commandIndex ? 'active' : ''} onMouseEnter={() => setCommandIndex(index)} onClick={() => selectCommand(item)}>
                  <item.Icon size={17} /><span>{item.label}</span><small>{item.group}</small><kbd>↵</kbd>
                </button>
              )) : <p>No permitted dashboard sections match “{commandQuery}”.</p>}
            </div>
            <footer><span>Search articles, open sections, create content</span><span><kbd>↑</kbd><kbd>↓</kbd> move <kbd>↵</kbd> open</span></footer>
          </section>
        </div>
      )}
    </div>
  );
}
