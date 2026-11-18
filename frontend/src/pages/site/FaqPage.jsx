import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, ChevronDown, HelpCircle, LifeBuoy, Mail, MessageCircle, Search, ShieldCheck, Sparkles, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PublicWebsiteApi } from '../../api/publicWebsiteApi';
import PageHero from '../../components/public/PageHero';
import SectionHeading from '../../components/public/SectionHeading';
import { FAQ_CATEGORIES, GUIDE_FAQS, SEO } from '../../config/contentStructure';
import { useSiteSettings } from '../../contexts/SiteSettingsContext';
import { usePageMeta } from '../../utils/seo';
import '../../styles/pages/faq.css';

const supportCards = [
  [LifeBuoy, 'Need platform help?', 'Send a clear message and we will route it to the right support pathway.', '/contact'],
  [MessageCircle, 'Have a research question?', 'Use consultation when you need project-specific academic guidance.', '/consultation'],
  [ShieldCheck, 'Policy questions?', 'Review privacy, cookies, and terms from the legal links in the footer.', '/privacy-policy'],
];

export default function FaqPage() {
  usePageMeta(SEO.faq);
  const settings = useSiteSettings();
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('All');
  const [open, setOpen] = useState(0);
  const [faqRows, setFaqRows] = useState(GUIDE_FAQS);
  const [categories, setCategories] = useState(FAQ_CATEGORIES);

  useEffect(() => {
    let active = true;
    PublicWebsiteApi.getFaq()
      .then(data => {
        if (!active || !data.categories?.length) return;
        const dynamicRows = data.categories.flatMap(group => group.items.map(item => [group.name, item.question, item.answer]));
        setFaqRows(dynamicRows);
        setCategories(['All', ...data.categories.map(group => group.name)]);
      })
      .catch(() => {
        setFaqRows(GUIDE_FAQS);
        setCategories(FAQ_CATEGORIES);
      });
    return () => { active = false; };
  }, []);

  const filteredQuestions = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return faqRows.filter(([itemCategory, question, answer]) => {
      const matchesCategory = category === 'All' || itemCategory === category;
      const matchesQuery = !normalizedQuery || `${question} ${answer}`.toLowerCase().includes(normalizedQuery);
      return matchesCategory && matchesQuery;
    });
  }, [category, query, faqRows]);

  const categoryCounts = useMemo(() => faqRows.reduce((counts, [itemCategory]) => {
    counts[itemCategory] = (counts[itemCategory] || 0) + 1;
    return counts;
  }, { All: faqRows.length }), [faqRows]);

  return (
    <div className="rh-page rp-faq">
      <PageHero title="Frequently Asked Questions" text="Find answers to common questions about ResRef, including the database, tools, consultation service, team roles, and platform access." settingPrefix="faq" breadcrumb="FAQ" />

      <section className="rh-section rp-faq-main">
        <div className="rh-container rp-faq-layout">
          <aside className="rp-faq-sidebar">
            <div className="rp-faq-sidebar-inner">
              <SectionHeading eyebrow={settings.faq_command_eyebrow} title={settings.faq_command_title} text={settings.faq_command_text} />
              <div className="rp-faq-search">
                <Search size={18} aria-hidden="true" />
                <input type="search" value={query} onChange={event => { setQuery(event.target.value); setOpen(0); }} placeholder={settings.faq_search_placeholder} aria-label="Search FAQ" />
                {query && <button type="button" onClick={() => { setQuery(''); setOpen(0); }} aria-label="Clear FAQ search"><X size={16} /></button>}
              </div>
              <div className="rp-faq-categories" role="group" aria-label="FAQ categories">
                {categories.map(item => (
                  <button className={category === item ? 'rp-faq-category is-active' : 'rp-faq-category'} aria-pressed={category === item} type="button" key={item} onClick={() => { setCategory(item); setOpen(0); }}>
                    {item}
                    {categoryCounts[item] ? <span aria-hidden="true">{categoryCounts[item]}</span> : null}
                  </button>
                ))}
              </div>
              <Link className="rp-faq-sidebar-contact" to="/contact">
                <span aria-hidden="true"><Mail size={18} /></span>
                <span><strong>Can't find an answer?</strong><small>Contact the ResRef team</small></span>
                <ArrowRight size={16} aria-hidden="true" />
              </Link>
            </div>
          </aside>

          <div className="rp-faq-answers">
            <p className="rp-faq-count" aria-live="polite">
              <strong>{filteredQuestions.length}</strong> {filteredQuestions.length === 1 ? 'question' : 'questions'}
              {category !== 'All' && <> in <em>{category}</em></>}
              {query.trim() && <> matching “{query.trim()}”</>}
            </p>
            {filteredQuestions.length ? (
              <div className="rp-faq-list">
                {filteredQuestions.map(([itemCategory, question, answer], index) => {
                  const isOpen = open === index;
                  const panelId = `faq-answer-${index}`;
                  return (
                    <article className={`rp-faq-item${isOpen ? ' is-open' : ''}`} key={`${itemCategory}-${question}`}>
                      <h3>
                        <button type="button" aria-expanded={isOpen} aria-controls={panelId} id={`${panelId}-button`} onClick={() => setOpen(isOpen ? -1 : index)}>
                          <span className="rp-faq-question"><small>{itemCategory}</small>{question}</span>
                          <span className="rp-faq-toggle" aria-hidden="true"><ChevronDown size={18} /></span>
                        </button>
                      </h3>
                      <div className="rp-faq-panel" id={panelId} role="region" aria-labelledby={`${panelId}-button`} aria-hidden={!isOpen}>
                        <div><p>{answer}</p></div>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="rp-faq-empty">
                <span aria-hidden="true"><HelpCircle size={24} /></span>
                <h3>No matching questions found</h3>
                <p>Try another keyword or contact ResRef for direct support.</p>
                {(query || category !== 'All') && <button type="button" className="button button-outline" onClick={() => { setQuery(''); setCategory('All'); setOpen(0); }}>Show all questions</button>}
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="rh-section rh-surface-mist rp-faq-support">
        <div className="rh-container">
          <SectionHeading eyebrow={settings.faq_support_eyebrow} title={settings.faq_support_title} text={settings.faq_support_text} align="center" />
          <div className="rh-card-grid rh-card-grid-3">
            {supportCards.map(([Icon, title, text, href], index) => (
              <Link className="rh-card rp-faq-support-card" to={href} key={title} data-reveal style={{ '--rh-delay': `${index * 80}ms` }}>
                <span className="rh-card-icon" aria-hidden="true"><Icon size={22} /></span>
                <h3>{title}</h3>
                <p>{text}</p>
                <strong className="rp-faq-support-cta"><span>Open pathway</span> <ArrowRight size={15} aria-hidden="true" /></strong>
              </Link>
            ))}
          </div>
          <div className="rp-faq-trust" data-reveal>
            <span aria-hidden="true"><Sparkles size={20} /></span>
            <p>ResRef keeps support language simple, direct, and practical so non-technical users can move through research tasks with confidence.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
