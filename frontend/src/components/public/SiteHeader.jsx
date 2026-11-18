import {
  BookMarked,
  BookOpen,
  BriefcaseBusiness,
  Bell,
  Bot,
  BarChart3,
  Calculator,
  ChevronDown,
  ChevronRight,
  Database,
  FileSearch,
  FileText,
  HelpCircle,
  Home,
  LogIn,
  Mail,
  Menu,
  MessageCircle,
  Phone,
  ShieldCheck,
  Search,
  UserRound,
  Users,
  X,
} from 'lucide-react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import { AccountApi } from '../../api/accountApi';
import { PATHS } from '../../config/site';
import { useAccount } from '../../contexts/AccountContext';
import { useSiteSettings } from '../../contexts/SiteSettingsContext';
import { ASSETS, SOCIAL_LINKS } from '../../siteData';
import UniversalSearch from './UniversalSearch';
import SocialLinks from './SocialLinks';
import '../../styles/global/site-navigation.css';

const navClass = ({ isActive }) => isActive ? 'active' : '';

const TOOL_LINKS = [
  [Calculator, PATHS.sampleSize, 'Sample Size Calculator', 'Plan recruitment for your study design'],
  [FileText, PATHS.referenceGenerator, 'Reference Generator', 'Find, format and export citations'],
  [FileSearch, PATHS.journalFinder, 'Journal Finder', 'Match your manuscript to journals'],
  [BarChart3, PATHS.researchAnalyzer, 'ResRef Analyzer', 'Analyze data and build reports'],
];

/** "Tools" in the main navigation: the label opens the tools page; hover or the arrow shows the four tools. */
function ToolsMenu({ label }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const hoverTimer = useRef(null);
  const { pathname } = useLocation();
  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    if (!open) return undefined;
    const onPointer = event => { if (!rootRef.current?.contains(event.target)) setOpen(false); };
    const onKey = event => {
      if (event.key === 'Escape') { setOpen(false); rootRef.current?.querySelector('button')?.focus(); }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        const links = [...rootRef.current.querySelectorAll('.rr-tools-menu a')];
        if (!links.length) return;
        event.preventDefault();
        const index = links.indexOf(document.activeElement);
        links[(index + (event.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length].focus();
      }
    };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onPointer); document.removeEventListener('keydown', onKey); };
  }, [open]);
  useEffect(() => () => clearTimeout(hoverTimer.current), []);
  // The pause keeps the menu shut when the cursor only passes over "Tools" on its way elsewhere.
  const openSoon = () => { clearTimeout(hoverTimer.current); if (!open) hoverTimer.current = setTimeout(() => setOpen(true), 200); };
  const closeSoon = () => { clearTimeout(hoverTimer.current); if (open) hoverTimer.current = setTimeout(() => setOpen(false), 220); };
  return (
    <div className={`rr-tools-dropdown${open ? ' is-open' : ''}`} ref={rootRef} onMouseEnter={openSoon} onMouseLeave={closeSoon}>
      <NavLink className={navClass} to={PATHS.tools}>{label}</NavLink>
      <button type="button" className="rr-tools-toggle" aria-label={`Show ${label} menu`} aria-expanded={open} aria-haspopup="true" aria-controls="rr-tools-menu" onClick={() => { clearTimeout(hoverTimer.current); setOpen(current => !current); }}>
        <ChevronDown size={15} aria-hidden="true" className="rr-tools-chevron" />
      </button>
      {open && (
        <div className="rr-tools-menu" id="rr-tools-menu">
          <ul>
            {TOOL_LINKS.map(([Icon, to, name, text]) => (
              <li key={to}>
                <NavLink to={to} className={navClass}>
                  <span className="rr-tools-icon" aria-hidden="true"><Icon size={18} /></span>
                  <span className="rr-tools-copy"><strong>{name}</strong><small>{text}</small></span>
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

const navGroups = [
  {
    label: 'Platform',
    links: [
      [Home, PATHS.home, 'Home', true],
      [Database, PATHS.database, 'Research Database'],
      [BookMarked, PATHS.tools, 'Research Tools'],
      [ShieldCheck, PATHS.consultation, 'Expert Consultation'],
    ],
  },
  {
    label: 'Research Tools',
    links: [
      [Calculator, PATHS.sampleSize, 'Sample Size Calculator'],
      [FileText, PATHS.referenceGenerator, 'Reference Generator'],
      [FileSearch, PATHS.journalFinder, 'Journal Finder'],
      [BarChart3, PATHS.researchAnalyzer, 'ResRef Analyzer'],
    ],
  },
  {
    label: 'Community',
    links: [
      [BriefcaseBusiness, PATHS.opportunities, 'Research Opportunities'],
      [Users, PATHS.joinTeam, 'Join Our Team'],
      [BookOpen, PATHS.about, 'About ResRef'],
      [Mail, PATHS.contact, 'Contact Us'],
      [HelpCircle, PATHS.faq, 'FAQ'],
    ],
  },
];

const mobileLinks = [
  [Home, PATHS.home, 'Home', true],
  [Database, PATHS.database, 'Database'],
  [Calculator, PATHS.tools, 'Tools'],
];

function accountName(account) {
  if (!account) return '';
  const fullName = [account.first_name, account.last_name].filter(Boolean).join(' ').trim();
  return account.display_name || fullName || account.email || account.username || 'Profile';
}

function firstNameLabel(name) {
  const first = String(name || 'Profile').trim().split(/\s+/)[0] || 'Profile';
  // An email address is too long for the bottom bar.
  return first.includes('@') ? 'Account' : first;
}

function SidebarNav({ onNavigate }) {
  return (
    <nav className="app-sidebar-nav" aria-label="Primary navigation">
      {navGroups.map(group => (
        <section key={group.label}>
          <small>{group.label}</small>
          {group.links.map(([Icon, to, text, end]) => (
            <NavLink end={end} className={navClass} to={to} key={to} onClick={onNavigate}>
              <Icon size={18} />
              <span>{text}</span>
              <ChevronRight className="app-sidebar-chevron" size={15} />
            </NavLink>
          ))}
        </section>
      ))}
    </nav>
  );
}

export default function SiteHeader() {
  const [open, setOpen] = useState(false);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const notificationRef = useRef(null);
  const drawerRef = useRef(null);
  const menuRef = useRef(null);
  const location = useLocation();
  const settings = useSiteSettings();
  const { account } = useAccount();

  const closeDrawer = () => setOpen(false);
  const unreadCount = notifications.filter(item => !item.is_read).length;
  const signedInName = accountName(account);
  const currentPath = `${location.pathname}${location.search || ''}`;
  const signInPath = ['/sign-in', '/register', '/auth'].includes(location.pathname)
    ? '/sign-in'
    : `/sign-in?next=${encodeURIComponent(currentPath || '/')}`;

  useEffect(() => { setOpen(false); setNotificationOpen(false); }, [location.pathname]);

  useEffect(() => {
    if (!open) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusable = () => [...drawerRef.current.querySelectorAll('a[href],button:not([disabled])')];
    focusable()[0]?.focus();
    const handleKey = event => {
      if (event.key === 'Escape') setOpen(false);
      if (event.key !== 'Tab') return;
      const items = focusable();
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener('keydown', handleKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleKey);
      menuRef.current?.focus();
    };
  }, [open]);

  useEffect(() => {
    if (!account) {
      setNotifications([]);
      setNotificationOpen(false);
      return;
    }
    let active = true;
    const loadNotifications = () => {
      setNotificationsLoading(true);
      AccountApi.getNotifications()
        .then(data => { if (active) setNotifications(data.results || []); })
        .catch(() => { if (active) setNotifications([]); })
        .finally(() => { if (active) setNotificationsLoading(false); });
    };
    loadNotifications();
    // Lightweight polling keeps account notifications current without a
    // persistent WebSocket connection on the free hosting tier.
    const interval = window.setInterval(loadNotifications, 60000);
    return () => { active = false; window.clearInterval(interval); };
  }, [account]);

  useEffect(() => {
    if (!notificationOpen) return undefined;
    const closeOnOutside = event => {
      if (notificationRef.current && !notificationRef.current.contains(event.target)) {
        setNotificationOpen(false);
      }
    };
    document.addEventListener('mousedown', closeOnOutside);
    return () => document.removeEventListener('mousedown', closeOnOutside);
  }, [notificationOpen]);

  const markNotificationRead = async notification => {
    if (!notification?.id || notification.is_read) return;
    try {
      const data = await AccountApi.markNotificationRead(notification.id);
      setNotifications(items => items.map(item => (item.id === notification.id ? data.notification : item)));
    } catch {
      // Keep the header quiet; the account page shows fuller notification errors.
    }
  };

  return (
    <>
      <a href="#public-content" className="rr-skip-link">Skip to content</a>
      <div className="rr-contact-strip" aria-label="ResRef contact and social links">
        <div className="rr-contact-strip-inner">
          <a className="rr-bot-link" href={settings.homepage_telegram_bot_url || 'https://t.me/resrefbot'} target="_blank" rel="noopener noreferrer">
            <Bot size={18} aria-hidden="true" /> <span>@resrefbot</span>
          </a>
          <div className="rr-strip-contact">
            <a href={`tel:${String(settings.contact_phone || settings.whatsapp_label).replace(/[^+\d]/g, '')}`}>
              <Phone size={16} aria-hidden="true" /> <span>{settings.contact_phone || settings.whatsapp_label}</span>
            </a>
            <a href={`mailto:${settings.contact_email}`}><Mail size={17} aria-hidden="true" /> <span>{settings.contact_email}</span></a>
          </div>
          <SocialLinks light />
        </div>
      </div>
      <header className="app-topbar rr-navigation">
        <button ref={menuRef} className="app-menu-button" type="button" onClick={() => setOpen(current => !current)} aria-label={open ? 'Close navigation' : 'Open navigation'} aria-expanded={open} aria-controls="site-navigation-drawer">
          <Menu size={22} />
        </button>

        <Link className="app-mobile-brand" to="/" aria-label="ResRef home">
          <img hidden={Boolean(settings.logo_url)} className="app-mobile-logo-mark" src={ASSETS.logo} alt="" />
          <img className="app-mobile-logo-wordmark" src={settings.logo_url || ASSETS.logoWordmark} alt={settings.site_name} />
        </Link>

        <nav className="rr-primary-nav" aria-label="Main navigation">
          <NavLink className={navClass} to={PATHS.database}>{settings.nav_database_label || 'Database'}</NavLink>
          <ToolsMenu label={settings.nav_tools_label || 'Tools'} />
          {[[PATHS.opportunities, settings.nav_opportunities_label || 'Opportunities'], [PATHS.consultation, settings.nav_consultation_label || 'Consultations'], ['/articles', settings.nav_learn_label || 'Learn']].map(([to, label]) => <NavLink className={navClass} to={to} key={to}>{label}</NavLink>)}
          <NavLink className={({ isActive }) => `${navClass({ isActive })} rr-utility-nav-link`.trim()} to={PATHS.joinTeam}>{settings.nav_join_label || 'Join our team'}</NavLink>
          <NavLink className={({ isActive }) => `${navClass({ isActive })} rr-utility-nav-link`.trim()} to={PATHS.contact}>{settings.nav_contact_label || 'Contact us'}</NavLink>
          <NavLink className={({ isActive }) => `${navClass({ isActive })} rr-utility-nav-link`.trim()} to={PATHS.about}>{settings.nav_about_label || 'About us'}</NavLink>
        </nav>
        <button type="button" className="rr-nav-search" aria-label="Search ResRef" onClick={() => window.dispatchEvent(new Event('resref:open-search'))}><Search size={19} /></button>
        <UniversalSearch />

        <div className="app-topbar-actions">
          <a className="app-contact-chip" href={`mailto:${settings.contact_email}`}>
            <Mail size={16} />
            <span>{settings.contact_email}</span>
          </a>
          <a className="app-contact-chip app-contact-chip-mobile-hidden" href={settings.whatsapp_url}>
            <MessageCircle size={16} />
            <span>{settings.whatsapp_label}</span>
          </a>
          {account && (
            <div className="app-notification-wrap" ref={notificationRef}>
              <button
                className="app-notification-button"
                type="button"
                onClick={() => setNotificationOpen(current => !current)}
                aria-label="Open notifications"
                aria-expanded={notificationOpen}
              >
                <Bell size={17} />
                {unreadCount > 0 && <span>{unreadCount > 9 ? '9+' : unreadCount}</span>}
              </button>
              {notificationOpen && (
                <div className="app-notification-menu" role="dialog" aria-label="Notifications">
                  <div className="app-notification-head">
                    <strong>Notifications</strong>
                    <Link to="/account" onClick={() => setNotificationOpen(false)}>View all</Link>
                  </div>
                  {notificationsLoading ? (
                    <p className="app-notification-empty">Loading notifications...</p>
                  ) : notifications.length === 0 ? (
                    <p className="app-notification-empty">No notifications yet.</p>
                  ) : (
                    <div className="app-notification-list">
                      {notifications.slice(0, 4).map(item => (
                        <article className={item.is_read ? 'read' : 'unread'} key={item.id}>
                          <small>{item.type}</small>
                          <strong>{item.title}</strong>
                          <p>{item.message}</p>
                          <div>
                            {item.action_url && (
                              <Link to={item.action_url} onClick={() => {
                                markNotificationRead(item);
                                setNotificationOpen(false);
                              }}>
                                Open
                              </Link>
                            )}
                            {!item.is_read && (
                              <button type="button" onClick={() => markNotificationRead(item)}>Mark read</button>
                            )}
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
          <Link className="app-account-button" to={account ? (account.can_access_dashboard ? '/dashboard' : '/account') : signInPath} state={account ? undefined : { from: location }} title={account ? signedInName : 'Sign in'}>
            {account ? <UserRound size={17} /> : <LogIn size={17} />}
            <span>{account ? (account.can_access_dashboard ? 'Dashboard' : 'My account') : 'Sign In'}</span>
          </Link>
        </div>
      </header>

      <div className={open ? 'app-mobile-drawer app-mobile-drawer-open' : 'app-mobile-drawer'} aria-hidden={!open}>
        <button className="app-mobile-backdrop" type="button" onClick={closeDrawer} aria-label="Close navigation" />
        <aside ref={drawerRef} id="site-navigation-drawer" className="app-mobile-panel" role="dialog" aria-modal={open ? 'true' : undefined} aria-label="Site navigation">
          <div className="app-mobile-panel-head">
            <Link className="app-sidebar-brand" to="/" onClick={closeDrawer} aria-label="ResRef home">
              <img src={settings.footer_logo_url || settings.logo_url || ASSETS.whiteLogo || ASSETS.logo} alt={settings.site_name} />
              <span>
                <strong>{settings.site_name}</strong>
                <small>Research Reference Platform</small>
              </span>
            </Link>
            <button type="button" onClick={closeDrawer} aria-label="Close navigation"><X size={20} /></button>
          </div>
          <Link className="app-sidebar-cta" to={PATHS.consultation} onClick={closeDrawer}>
            <ShieldCheck size={18} />
            Request Free Consultation
          </Link>
          <SidebarNav onNavigate={closeDrawer} />
          <div className="rr-drawer-extra"><Link to="/articles" onClick={closeDrawer}>Articles & learning <BookOpen size={18} /></Link><a href={settings.telegram_url || SOCIAL_LINKS.telegram} target="_blank" rel="noopener noreferrer" onClick={closeDrawer}>Connect on Telegram <MessageCircle size={18} /></a></div>
          <div className="app-sidebar-support">
            <strong>Need research help?</strong>
            <p>Use ResRef tools or request guided academic support from the team.</p>
            <a href={settings.whatsapp_url}><MessageCircle size={15} /> {settings.whatsapp_label}</a>
          </div>
        </aside>
      </div>

      <nav className="app-mobile-bottom-nav" aria-label="Mobile quick navigation">
        {mobileLinks.map(([Icon, to, text, end]) => (
          <NavLink end={end} className={navClass} to={to} key={to}>
            <Icon size={20} />
            <span>{text}</span>
          </NavLink>
        ))}
        <button type="button" onClick={() => window.dispatchEvent(new Event('resref:open-search'))}>
          <FileSearch size={20} />
          <span>Search</span>
        </button>
        <NavLink className={navClass} to={account ? '/account' : signInPath}>
          <UserRound size={20} />
          <span>{account ? firstNameLabel(signedInName) : 'Sign In'}</span>
        </NavLink>
      </nav>
    </>
  );
}
