import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  BookCheck,
  BookOpen,
  BriefcaseBusiness,
  Calculator,
  FileSearch,
  FileText,
  Globe2,
  Layers3,
  Library,
  Mail,
  MapPin,
  Microscope,
  PenLine,
  Search,
  Send,
  Sigma,
  Users,
  Wrench,
} from 'lucide-react';
import { useAccount } from '../../contexts/AccountContext';
import { useSiteSettings } from '../../contexts/SiteSettingsContext';
import { SOCIAL_LINKS } from '../../siteData';
import { SEO } from '../../config/contentStructure';
import { usePageMeta } from '../../utils/seo';
import { useHomeResources } from '../../components/home/useHomeResources';
import { ArticlePreview, HomeLink, PreviewState, SectionIntro, useReveal } from '../../components/home/HomePrimitives';
import globalResearchMapHero from '../../assets/homepage/global-research-atlas-hero-1920.webp';
import globalResearchMapHeroSmall from '../../assets/homepage/global-research-atlas-hero-640.webp';
import globalResearchMapHeroMedium from '../../assets/homepage/global-research-atlas-hero-1280.webp';
import telegramArchiveNetwork from '../../assets/homepage/telegram-archive-network.webp';
import '../../styles/pages/home.css';

const researchToolDefaults = [
  { Icon: Calculator, title: 'Sample Size Calculator', text: 'Plan recruitment around your study design, assumptions, and required precision.', href: '/tools/sample-size-calculator', action: 'Plan your study' },
  { Icon: FileText, title: 'Reference Generator', text: 'Find references, format citations, and build a bibliography for your manuscript.', href: '/tools/reference-generator', action: 'Build your references' },
  { Icon: FileSearch, title: 'Journal Finder', text: 'Explore journals by subject fit, access, publication costs, and other priorities.', href: '/tools/journal-finder', action: 'Find a journal' },
  { Icon: BarChart3, title: 'ResRef Analyzer', text: 'Prepare research data, run statistical analyses, and produce structured reports.', href: '/tools/research-analyzer', action: 'Work with your data' },
];

const consultationDefaults = [
  [Microscope, 'Methods', 'Study design and research planning'],
  [Sigma, 'Statistics', 'Sample size and analysis planning'],
  [PenLine, 'Scientific writing', 'Proposals, abstracts, and manuscripts'],
  [BookCheck, 'Publication support', 'References and journal selection'],
];

function settingValue(settings, key, fallback, { preserveEmpty = false } = {}) {
  const value = settings[key];
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  return preserveEmpty || trimmed ? trimmed : fallback;
}

function isVisible(settings, key) {
  const value = settings[key];
  return value === undefined || value === null || value === '' || String(value).toLowerCase() !== 'false';
}

function sectionOrder(settings, key, fallback) {
  const value = Number(settings[key]);
  return Number.isFinite(value) ? value : fallback;
}

function formatCounter(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString() : '—';
}

export default function HomePage() {
  usePageMeta(SEO.home);
  const navigate = useNavigate();
  const settings = useSiteSettings();
  const { account } = useAccount();
  const { library, opportunities, reloadLibrary, reloadOpportunities } = useHomeResources();
  const [activeToolIndex, setActiveToolIndex] = useState(0);
  // Hovering waits a moment before swapping the spotlight, so sweeping the cursor across the list does not flicker through every tool.
  const toolHoverTimer = useRef(null);
  useEffect(() => () => clearTimeout(toolHoverTimer.current), []);
  const previewToolSoon = index => { clearTimeout(toolHoverTimer.current); toolHoverTimer.current = setTimeout(() => setActiveToolIndex(index), 140); };
  const revealRef = useReveal([library.status, opportunities.status]);
  const text = (key, fallback) => settingValue(settings, key, fallback, { preserveEmpty: true });
  const asset = (key, fallback) => settingValue(settings, key, fallback);
  const accountPath = account ? '/account' : '/sign-in?next=%2Faccount';
  const telegram = text('homepage_telegram_button_url', settings.telegram_url || SOCIAL_LINKS.telegram);
  const telegramBot = text('homepage_telegram_bot_url', 'https://t.me/resrefbot');
  const heroImage = asset('homepage_hero_image_url', globalResearchMapHero);
  const telegramImage = asset('homepage_telegram_image_url', telegramArchiveNetwork);
  const researchTools = researchToolDefaults.map((tool, index) => ({
    ...tool,
    title: text(`homepage_tools_${index + 1}_title`, tool.title),
    text: text(`homepage_tools_${index + 1}_text`, tool.text),
    href: text(`homepage_tools_${index + 1}_url`, tool.href),
    action: text(`homepage_tools_${index + 1}_action`, tool.action),
  }));
  const activeTool = researchTools[activeToolIndex] || researchTools[0];
  const ActiveToolIcon = activeTool.Icon;
  const submitDatabaseSearch = event => {
    event.preventDefault();
    const query = String(new FormData(event.currentTarget).get('q') || '').trim();
    navigate(query ? `/database?q=${encodeURIComponent(query)}` : '/database');
  };
  const learningPosts = (library.data?.learning_posts || []).filter(post => post.excerpt?.trim()).slice(0, 3);
  const opportunityItems = (opportunities.data?.results || []).slice(0, 3);
  const heroStyle = {
    '--rh-hero-title-size': settings.homepage_hero_title_size || undefined,
    '--rh-hero-text-size': settings.homepage_hero_text_size || undefined,
    '--rh-hero-title-weight': settings.homepage_hero_title_weight || undefined,
  };
  const databaseCounters = [
    { Icon: Library, value: library.data?.resource_count, label: text('homepage_database_resource_label', 'Research resources') },
    { Icon: Layers3, value: library.data?.category_count, label: text('homepage_database_category_label', 'Research categories') },
    { Icon: Wrench, value: researchTools.length, label: text('homepage_database_tools_label', 'Research tools') },
  ];
  const ecosystem = [
    {
      Icon: FileText,
      title: text('homepage_ecosystem_workspace_title', 'Your research workspace'),
      text: text('homepage_ecosystem_workspace_text', 'Keep tool workspaces, account details, and notifications connected to your account.'),
      action: text('homepage_ecosystem_workspace_action_label', account ? 'Open your account' : 'Sign in to your account'),
      href: text('homepage_ecosystem_workspace_action_url', accountPath),
    },
    {
      Icon: BookOpen,
      title: text('homepage_ecosystem_learning_title', 'Research learning'),
      text: text('homepage_ecosystem_learning_text', 'Browse research categories, methodology articles, and practical reading for the work ahead.'),
      action: text('homepage_ecosystem_learning_action_label', 'Browse research categories'),
      href: text('homepage_ecosystem_learning_action_url', '/database/mastering-research'),
    },
    {
      Icon: Users,
      title: text('homepage_ecosystem_contribute_title', 'Contribute to ResRef'),
      text: text('homepage_ecosystem_contribute_text', 'Explore team roles and apply to contribute your research, education, or technical skills.'),
      action: text('homepage_ecosystem_contribute_action_label', 'Join our team'),
      href: text('homepage_ecosystem_contribute_action_url', '/join'),
    },
  ];
  const heroKicker = text('homepage_hero_kicker', 'Research resources, tools, and guidance');
  const heroFootnote = text('homepage_hero_footnote', 'A global research ecosystem for work that needs to be clear, credible, and connected.');

  const sections = [
    {
      key: 'hero',
      order: sectionOrder(settings, 'homepage_hero_order', 10),
      visible: isVisible(settings, 'homepage_hero_visible'),
      node: <section key="hero" className="rh-hero" aria-labelledby="home-title" style={heroStyle}>
        <div className="rh-hero-backdrop" aria-hidden="true"><span className="rh-hero-glow rh-hero-glow-a" /><span className="rh-hero-glow rh-hero-glow-b" /></div>
        <img className="rh-hero-art" src={heroImage} srcSet={heroImage === globalResearchMapHero ? `${globalResearchMapHeroSmall} 640w, ${globalResearchMapHeroMedium} 1280w, ${globalResearchMapHero} 1920w` : undefined} sizes="(max-width: 900px) 100vw, 70vw" alt="" aria-hidden="true" width="1920" height="1080" loading="eager" decoding="async" fetchpriority="high" />
        <div className="rh-container rh-hero-layout">
          <div className="rh-hero-copy">
            {heroKicker && <span className="rh-hero-kicker"><span className="rh-pulse" aria-hidden="true" />{heroKicker}</span>}
            <h1 id="home-title">{text('homepage_hero_title', settings.home_gateway_title || 'Research starts with the right resources.')}</h1>
            <p className="rh-hero-lead">{text('homepage_hero_text', settings.home_gateway_text || 'A connected home for students, clinicians, and researchers: discover resources, use practical tools, and find support for your next study.')}</p>
            <div className="rh-actions">
              <HomeLink to={text('homepage_hero_primary_url', '/database')} variant="light">{text('homepage_hero_primary_label', 'Explore the database')}</HomeLink>
              <HomeLink to={text('homepage_hero_secondary_url', '/tools')} variant="ghost">{text('homepage_hero_secondary_label', 'View research tools')}</HomeLink>
            </div>
            {heroFootnote && <p className="rh-hero-footnote"><Globe2 size={16} aria-hidden="true" />{heroFootnote}</p>}
          </div>
        </div>
      </section>,
    },
    {
      key: 'database',
      order: sectionOrder(settings, 'homepage_database_order', 20),
      visible: isVisible(settings, 'homepage_database_visible'),
      node: <section key="database" id="home-database" className="rh-database" aria-labelledby="home-database-title">
        <div className="rh-container">
          <div className="rh-database-card" data-reveal>
            <div className="rh-database-intro">
              <span className="rh-label">{text('homepage_database_label', 'Research database')}</span>
              <h2 id="home-database-title">{text('homepage_database_title', 'Find a Stronger Starting Point.')}</h2>
              <p>{text('homepage_database_text', 'Search questionnaires, scales, articles, and methodology resources by topic or specialty.')}</p>
            </div>
            <div className="rh-database-explorer">
              <form className="rh-search" onSubmit={submitDatabaseSearch} role="search" aria-label="Research database search">
                <label htmlFor="home-query" className="rh-visually-hidden">Search the research database</label>
                <Search className="rh-search-icon" size={21} aria-hidden="true" />
                <input id="home-query" name="q" type="search" placeholder={text('homepage_database_search_placeholder', 'Search questionnaires, topics, or methods')} maxLength={200} />
                <button type="submit"><span>{text('homepage_database_search_button_label', 'Search database')}</span><ArrowRight size={17} aria-hidden="true" /></button>
              </form>
              <div className="rh-database-support" role={library.status === 'error' ? 'status' : undefined}>
                <span>{library.status === 'error' ? text('homepage_database_unavailable_text', 'Resource counts are temporarily unavailable.') : text('homepage_database_support_text', 'Start with a research question, study design, or specialty.')}</span>
                {library.status === 'error' && <button type="button" onClick={reloadLibrary}>{text('homepage_database_retry_label', 'Refresh counts')}</button>}
              </div>
              <dl className="rh-stats" aria-label="Research database overview" aria-live="polite">
                {databaseCounters.map(({ Icon, value, label }) => <div className={`rh-stat ${library.status === 'loading' ? 'is-loading' : ''}`} key={label}>
                  <span className="rh-stat-icon" aria-hidden="true"><Icon size={20} /></span>
                  <dd>{formatCounter(value)}</dd>
                  <dt>{label}</dt>
                </div>)}
              </dl>
            </div>
          </div>
        </div>
      </section>,
    },
    {
      key: 'tools',
      order: sectionOrder(settings, 'homepage_tools_order', 30),
      visible: isVisible(settings, 'homepage_tools_visible'),
      node: <section key="tools" className="rh-section rh-tools" id="home-tools" aria-labelledby="home-tools-title">
        <div className="rh-container">
          <div className="rh-split-heading">
            <SectionIntro id="home-tools-title" label={text('homepage_tools_label', 'Research tools')} title={text('homepage_tools_title', 'Practical tools for the work in front of you.')} />
            <div className="rh-split-aside" data-reveal>
              <p>{text('homepage_tools_text', 'Plan, write, analyze, and prepare to publish with tools built around real research tasks.')}</p>
              <HomeLink to={text('homepage_tools_action_url', '/tools')} variant="text">{text('homepage_tools_action_label', 'View all tools')}</HomeLink>
            </div>
          </div>
          <div className="rh-tool-console" data-reveal>
            <div className="rh-tool-list" role="list">
              {researchTools.map((tool, index) => {
                const Icon = tool.Icon;
                const selected = index === activeToolIndex;
                return <Link role="listitem" className={`rh-tool-row ${selected ? 'is-active' : ''}`} to={tool.href} key={`${tool.href}-${index}`} aria-current={selected ? 'true' : undefined} onMouseEnter={() => previewToolSoon(index)} onMouseLeave={() => clearTimeout(toolHoverTimer.current)} onFocus={() => setActiveToolIndex(index)}>
                  <span className="rh-tool-icon" aria-hidden="true"><Icon size={22} /></span>
                  <span className="rh-tool-copy"><strong>{tool.title}</strong><small>{tool.text}</small></span>
                  <ArrowUpRight className="rh-tool-arrow" size={19} aria-hidden="true" />
                </Link>;
              })}
            </div>
            <div className="rh-tool-spotlight" aria-live="polite">
              <div className="rh-tool-spotlight-art" key={`art-${activeTool.title}`} aria-hidden="true"><ActiveToolIcon size={56} strokeWidth={1.4} /></div>
              <span className="rh-label rh-label-light">{text('homepage_tools_detail_label', 'Selected tool')}</span>
              <h3 key={activeTool.title}>{activeTool.title}</h3>
              <p key={`text-${activeTool.title}`}>{activeTool.text}</p>
              <HomeLink to={activeTool.href} variant="light">{activeTool.action}</HomeLink>
              <small>{account ? text('homepage_tools_signed_in_note', 'Your work is linked to your account.') : text('homepage_tools_signed_out_note', 'Sign in to use tools and save your work.')}</small>
            </div>
          </div>
        </div>
      </section>,
    },
    {
      key: 'ecosystem',
      order: sectionOrder(settings, 'homepage_ecosystem_order', 40),
      visible: isVisible(settings, 'homepage_ecosystem_visible'),
      node: <section key="ecosystem" className="rh-section rh-ecosystem" id="home-ecosystem" aria-labelledby="home-ecosystem-title"><div className="rh-container">
        <SectionIntro id="home-ecosystem-title" align="center" label={text('homepage_ecosystem_label', 'The ResRef ecosystem')} title={text('homepage_ecosystem_title', 'Support at every stage.')} text={text('homepage_ecosystem_text', 'Bring your resources, research work, and next steps together.')} />
        <div className="rh-card-grid rh-card-grid-3">
          {ecosystem.map(({ Icon, title, text: description, action, href }, index) => <article className="rh-card" key={title} data-reveal style={{ '--rh-delay': `${index * 90}ms` }}>
            <span className="rh-card-icon" aria-hidden="true"><Icon size={24} /></span>
            <h3>{title}</h3>
            <p>{description}</p>
            <div className="rh-card-actions">
              <HomeLink to={href} variant="text">{action}</HomeLink>
              {index === 0 && account?.can_access_dashboard && <HomeLink to="/dashboard" variant="text">Open dashboard</HomeLink>}
            </div>
          </article>)}
        </div>
      </div></section>,
    },
    {
      key: 'opportunities',
      order: sectionOrder(settings, 'homepage_opportunities_order', 50),
      visible: isVisible(settings, 'homepage_opportunities_visible'),
      node: <section key="opportunities" id="home-opportunities" className="rh-section rh-opportunities" aria-labelledby="home-opportunities-title"><div className="rh-container rh-opportunities-layout">
        <div className="rh-opportunities-intro">
          <SectionIntro id="home-opportunities-title" label={text('homepage_opportunities_label', 'Research opportunities')} title={text('homepage_opportunities_title', 'Find your next research connection.')} text={text('homepage_opportunities_text', 'Explore published research positions, collaborations, and programmes.')}>
            <HomeLink to={text('homepage_opportunities_action_url', '/opportunities')}>{text('homepage_opportunities_action_label', 'Explore all opportunities')}</HomeLink>
          </SectionIntro>
        </div>
        <div className="rh-opportunities-board" data-reveal>
          <div className="rh-board-head"><span>{text('homepage_opportunities_board_label', 'Opportunities board')}</span><span className="rh-board-count">{opportunities.status === 'ready' ? `${opportunityItems.length} selected opportunities` : text('homepage_opportunities_updated_label', 'Updated research pathways')}</span></div>
          <PreviewState state={opportunities} onRetry={reloadOpportunities} loading="Loading current opportunities…" error="Opportunity previews are temporarily unavailable." />
          {opportunities.status === 'ready' && !opportunityItems.length && <div className="rh-empty"><BriefcaseBusiness size={25} aria-hidden="true" /><div><h3>{text('homepage_opportunities_empty_title', 'No current opportunities to preview')}</h3><p>{text('homepage_opportunities_empty_text', 'Explore the opportunities page to share your interests, or apply to join the ResRef team.')}</p></div></div>}
          <div className="rh-opportunity-list">{opportunityItems.map(item => <Link key={item.id} to={`/opportunities?search=${encodeURIComponent(item.title)}`} className="rh-opportunity">
            <div className="rh-opportunity-copy">
              <span className="rh-opportunity-meta"><span className="rh-chip">{item.type_label || 'Research opportunity'}</span>{item.organization && <span className="rh-opportunity-org">{item.organization}</span>}</span>
              <h3>{item.title}</h3>
              <p>{item.short_description || text('homepage_opportunities_fallback_text', 'View the opportunity for requirements, eligibility, and application details.')}</p>
            </div>
            <div className="rh-opportunity-side">
              <span className="rh-opportunity-location"><MapPin size={15} aria-hidden="true" />{item.is_remote ? text('homepage_opportunities_remote_label', 'Remote') : item.location || text('homepage_opportunities_location_fallback', 'Location TBA')}</span>
              <span className="rh-circle-arrow" aria-label={`View ${item.title}`}><ArrowUpRight size={18} aria-hidden="true" /></span>
            </div>
          </Link>)}</div>
        </div>
      </div></section>,
    },
    {
      key: 'telegram',
      order: sectionOrder(settings, 'homepage_telegram_order', 60),
      visible: isVisible(settings, 'homepage_telegram_visible'),
      node: <section key="telegram" className="rh-band rh-telegram" id="home-telegram" aria-labelledby="telegram-title"><div className="rh-container">
        <div className="rh-band-panel rh-telegram-layout">
          <div className="rh-telegram-copy" data-reveal>
            <span className="rh-label rh-label-light">{text('homepage_telegram_label', 'ResRef on Telegram')}</span>
            <h2 id="telegram-title">{text('homepage_telegram_title', 'Keep useful information within reach.')}</h2>
            <p>{text('homepage_telegram_text', 'Use Telegram to archive and access useful information, stay in touch, and contact ResRef.')}</p>
            <ul className="rh-telegram-list">
              <li><span aria-hidden="true"><Send size={17} /></span>{text('homepage_telegram_point_1', 'Archive useful research information')}</li>
              <li><span aria-hidden="true"><BookOpen size={17} /></span>{text('homepage_telegram_point_2', 'Return to information when you need it')}</li>
              <li><span aria-hidden="true"><Users size={17} /></span>{text('homepage_telegram_point_3', 'Communicate with ResRef')}</li>
            </ul>
            <div className="rh-actions">
              <HomeLink to={telegram} variant="light">{text('homepage_telegram_button_label', 'Telegram channel')}</HomeLink>
              <HomeLink to={telegramBot} variant="ghost">{text('homepage_telegram_bot_label', 'Message @resrefbot')}</HomeLink>
            </div>
          </div>
          <figure className="rh-telegram-visual" data-reveal>
            <img src={telegramImage} alt={text('homepage_telegram_image_alt', 'Illustration of a connected research information archive')} width="1536" height="1024" loading="lazy" decoding="async" />
          </figure>
        </div>
      </div></section>,
    },
    {
      key: 'consultations',
      order: sectionOrder(settings, 'homepage_consultations_order', 70),
      visible: isVisible(settings, 'homepage_consultations_visible'),
      node: <section key="consultations" id="home-consultations" className="rh-section rh-consultations" aria-labelledby="home-consultations-title"><div className="rh-container">
        <SectionIntro id="home-consultations-title" align="center" label={text('homepage_consultations_label', 'Consultations')} title={text('homepage_consultations_title', 'A clearer path through your research.')} text={text('homepage_consultations_text', 'Share your research question, current stage, and the support you need. The team reviews your request and helps clarify the next steps.')} />
        <div className="rh-card-grid rh-card-grid-4">
          {consultationDefaults.map(([Icon, title, description], index) => <article className="rh-card rh-card-compact" key={title} data-reveal style={{ '--rh-delay': `${index * 80}ms` }}>
            <span className="rh-card-icon" aria-hidden="true"><Icon size={22} /></span>
            <h3>{text(`homepage_consultations_${index + 1}_title`, title)}</h3>
            <p>{text(`homepage_consultations_${index + 1}_text`, description)}</p>
          </article>)}
        </div>
        <div className="rh-center-action" data-reveal><HomeLink to={text('homepage_consultations_action_url', '/consultation')}>{text('homepage_consultations_action_label', 'Request a consultation')}</HomeLink></div>
      </div></section>,
    },
    {
      key: 'learning',
      order: sectionOrder(settings, 'homepage_learning_order', 80),
      visible: isVisible(settings, 'homepage_learning_visible'),
      node: <section key="learning" id="home-learning" className="rh-section rh-learning" aria-labelledby="home-learning-title"><div className="rh-container">
        <div className="rh-split-heading">
          <SectionIntro id="home-learning-title" label={text('homepage_learning_label', 'Research categories')} title={text('homepage_learning_title', 'Explore Our Learning Articles')} text={text('homepage_learning_text', 'Practical methodology and research articles selected from the Mastering Research category.')} />
          <div className="rh-split-aside rh-split-aside-end" data-reveal><HomeLink to={text('homepage_learning_action_url', '/database/mastering-research')} variant="outline">{text('homepage_learning_action_label', 'Browse research categories')}</HomeLink></div>
        </div>
        <PreviewState state={library} onRetry={reloadLibrary} loading="Loading research-category articles…" error="Research-category articles are temporarily unavailable. Browse the category for more resources." />
        {library.status === 'ready' && <div className="rh-articles">{learningPosts.map(post => <ArticlePreview key={post.id} post={post} categoryLabel="Mastering Research" categorySlug="mastering-research" />)}</div>}
        {library.status === 'ready' && !learningPosts.length && <div className="rh-empty"><BookOpen size={24} aria-hidden="true" /><p>{text('homepage_learning_empty_text', 'Learning articles from this research category will appear here as they are published.')}</p></div>}
      </div></section>,
    },
    {
      key: 'community',
      order: sectionOrder(settings, 'homepage_community_order', 90),
      visible: isVisible(settings, 'homepage_community_visible'),
      node: <section key="community" id="home-community" className="rh-band rh-community" aria-labelledby="home-community-title"><div className="rh-container">
        <div className="rh-band-panel rh-community-layout">
          <div className="rh-community-copy" data-reveal>
            <span className="rh-label rh-label-light">{text('homepage_community_label', 'Community')}</span>
            <h2 id="home-community-title">{text('homepage_community_title', 'Research is better connected.')}</h2>
            <p>{text('homepage_community_text', 'For students finding their first research question, clinicians building evidence, and researchers moving a project forward.')}</p>
            <div className="rh-actions">
              <HomeLink to={text('homepage_community_primary_url', '/join')} variant="light">{text('homepage_community_primary_label', 'Join our team')}</HomeLink>
              <HomeLink to={text('homepage_community_secondary_url', '/about')} variant="ghost">{text('homepage_community_secondary_label', 'About ResRef')}</HomeLink>
            </div>
          </div>
          <svg className="rh-network" viewBox="0 0 470 250" role="img" aria-label={text('homepage_community_diagram_label', 'Connected research network')} data-reveal>
            <g className="rh-network-lines" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M52 151 142 64 235 128 357 52 433 117M142 64l3 135 90-71 121 68 77-79M52 151l93 48 112-25 99 22" /></g>
            <g className="rh-network-nodes">
              <circle cx="52" cy="151" r="8" /><circle cx="142" cy="64" r="10" /><circle cx="145" cy="199" r="8" /><circle className="rh-node-core" cx="235" cy="128" r="13" /><circle cx="257" cy="174" r="7" /><circle cx="357" cy="52" r="9" /><circle cx="356" cy="196" r="11" /><circle cx="433" cy="117" r="8" />
            </g>
            <text x="42" y="181">{text('homepage_community_diagram_question', 'QUESTION')}</text><text x="112" y="44">{text('homepage_community_diagram_evidence', 'EVIDENCE')}</text><text x="206" y="105">{text('homepage_community_diagram_method', 'METHOD')}</text><text x="324" y="32">{text('homepage_community_diagram_collaboration', 'COLLABORATION')}</text><text x="322" y="228">{text('homepage_community_diagram_impact', 'IMPACT')}</text>
          </svg>
        </div>
      </div></section>,
    },
    {
      key: 'contact',
      order: sectionOrder(settings, 'homepage_contact_order', 100),
      visible: isVisible(settings, 'homepage_contact_visible'),
      node: <section key="contact" className="rh-section rh-contact" aria-labelledby="home-contact-title"><div className="rh-container">
        <div className="rh-contact-card" data-reveal>
          <div className="rh-contact-copy">
            <span className="rh-label">{text('homepage_contact_label', 'Contact ResRef')}</span>
            <h2 id="home-contact-title">{text('homepage_contact_title', 'What are you working on?')}</h2>
            <p>{text('homepage_contact_text', 'Find a resource, choose a tool, or talk to ResRef about your next step.')}</p>
            {settings.contact_email && <a className="rh-contact-email" href={`mailto:${settings.contact_email}`}><Mail size={17} aria-hidden="true" />{settings.contact_email}</a>}
          </div>
          <div className="rh-contact-actions">
            <HomeLink to={text('homepage_contact_primary_url', '/contact')}>{text('homepage_contact_primary_label', 'Contact ResRef')}</HomeLink>
            <HomeLink to={text('homepage_contact_secondary_url', '/database')} variant="outline">{text('homepage_contact_secondary_label', 'Explore the database')}</HomeLink>
          </div>
        </div>
      </div></section>,
    },
  ];

  return <div className="rr-home" ref={revealRef}>{sections.filter(section => section.visible).sort((left, right) => left.order - right.order).map(section => section.node)}</div>;
}
