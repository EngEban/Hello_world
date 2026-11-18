import { ArrowLeft, ArrowUpRight, Eye } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { DashboardApi } from '../../api/dashboardApi';
import { PublicWebsiteApi } from '../../api/publicWebsiteApi';
import LoadingState from '../../components/common/LoadingState';
import PageHero from '../../components/public/PageHero';
import { SEO } from '../../config/contentStructure';
import { safeHref } from '../../utils/safeHref';
import { usePageMeta } from '../../utils/seo';
import NotFoundPage from './NotFoundPage';
import '../../styles/pages/team.css';

const initials = name => String(name || '').trim().split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0].toUpperCase()).join('');

function Portrait({ member, className }) {
  return <span className={`rp-team-portrait ${className}`}>
    {member.photo_url ? <img src={member.photo_url} alt={member.full_name} loading="lazy" decoding="async" /> : <span aria-hidden="true">{initials(member.full_name)}</span>}
  </span>;
}

function Name({ member, as: Tag = 'h3' }) {
  return <Tag className="rp-team-name">{member.full_name}{member.is_draft && <span className="rp-team-draft">Draft</span>}</Tag>;
}

function Role({ member }) {
  const text = [member.role, member.department].filter(Boolean).join(' · ');
  return text ? <p className="rp-team-role">{text}</p> : null;
}

function Links({ member }) {
  if (!member.links?.length) return null;
  return <ul className="rp-team-links">
    {member.links.map(link => <li key={link.url}><a href={safeHref(link.url)} target="_blank" rel="noopener noreferrer">{link.label}<ArrowUpRight size={14} aria-hidden="true" /></a></li>)}
  </ul>;
}

function SectionHead({ section, id }) {
  return <header className="rp-team-head">
    <h2 id={id}>{section.name}</h2>
    {section.description && <p>{section.description}</p>}
  </header>;
}

function FounderSection({ section, id }) {
  return <section className="rh-section rp-team-founder" aria-labelledby={id}>
    <div className="rh-container">
      {section.members.map((member, index) => <article className="rp-team-founder-layout" key={member.id}>
        <div className="rp-team-founder-visual"><Portrait member={member} className="is-founder" /></div>
        <div className="rp-team-founder-copy">
          <span className="rh-label" id={index === 0 ? id : undefined}>{section.name}</span>
          <Name member={member} as="h2" />
          <Role member={member} />
          {member.bio && <p className="rp-team-founder-bio">{member.bio}</p>}
          {member.vision && <blockquote className="rp-team-vision">{member.vision}</blockquote>}
          <Links member={member} />
        </div>
      </article>)}
    </div>
  </section>;
}

function LeadershipSection({ section, id }) {
  return <section className="rh-section rp-team-leadership" aria-labelledby={id}>
    <div className="rh-container">
      <SectionHead section={section} id={id} />
      <ul className="rp-team-leader-grid">
        {section.members.map(member => <li key={member.id}>
          <Portrait member={member} className="is-leader" />
          <Name member={member} />
          <Role member={member} />
          {member.bio && <p className="rp-team-bio">{member.bio}</p>}
          <Links member={member} />
        </li>)}
      </ul>
    </div>
  </section>;
}

function DirectorsSection({ section, id }) {
  return <section className="rh-section rp-team-directors" aria-labelledby={id}>
    <div className="rh-container">
      <SectionHead section={section} id={id} />
      <ul className="rp-team-director-grid">
        {section.members.map(member => <li key={member.id}>
          <Portrait member={member} className="is-director" />
          <div>
            <Name member={member} />
            <Role member={member} />
            {member.bio && <p className="rp-team-bio">{member.bio}</p>}
            <Links member={member} />
          </div>
        </li>)}
      </ul>
    </div>
  </section>;
}

function TeamSection({ section, id }) {
  return <section className="rp-team-unit" aria-labelledby={id}>
    <div className="rh-container rp-team-unit-layout">
      <SectionHead section={section} id={id} />
      <ul className="rp-team-member-grid">
        {section.members.map(member => <li key={member.id}>
          <Portrait member={member} className="is-member" />
          <div>
            <Name member={member} />
            <Role member={member} />
            {(member.bio || member.links?.length > 0) && <details className="rp-team-more">
              <summary>About {member.full_name.split(' ')[0]}</summary>
              {member.bio && <p className="rp-team-bio">{member.bio}</p>}
              <Links member={member} />
            </details>}
          </div>
        </li>)}
      </ul>
    </div>
  </section>;
}

const LAYOUTS = { founder: FounderSection, leadership: LeadershipSection, directors: DirectorsSection, team: TeamSection };

/** The Team page. `preview` shows it to Super Admins before it is published, with drafts on request. */
export default function TeamPage({ preview = false }) {
  const [params, setParams] = useSearchParams();
  const drafts = preview && params.get('drafts') === '1';
  const [state, setState] = useState({ status: 'loading', data: null });
  usePageMeta(preview ? SEO.teamPreview : state.status === 'ready' ? SEO.team : null);

  useEffect(() => {
    let active = true;
    const request = preview ? DashboardApi.getTeamPagePreview({ drafts: drafts ? 1 : '' }) : PublicWebsiteApi.getTeamPage();
    request
      .then(data => { if (active) setState({ status: 'ready', data }); })
      .catch(error => { if (active) setState({ status: [401, 403, 404].includes(error.status) ? 'missing' : 'error', data: null }); });
    return () => { active = false; };
  }, [preview, drafts]);

  if (state.status === 'missing') return <NotFoundPage />;
  if (state.status === 'loading') return <LoadingState label="Loading the team" />;
  if (state.status === 'error') return <div className="rh-page"><div className="rh-container rp-team-message"><h1>The team could not be loaded</h1><p>Please refresh the page and try again.</p></div></div>;

  const { hero_title: title, hero_text: text, sections } = state.data;
  return (
    <div className="rh-page rp-team">
      {preview && <div className="rp-team-preview" role="status">
        <div className="rh-container rp-team-preview-inner">
          <span><Eye size={16} aria-hidden="true" /><strong>Private preview.</strong> {state.data.is_published ? 'This page is live.' : 'This page is not published, so only Super Admins can see it.'}</span>
          <label><input type="checkbox" checked={drafts} onChange={event => setParams(event.target.checked ? { drafts: '1' } : {}, { replace: true })} /> Include drafts</label>
          <Link to="/dashboard/team-page"><ArrowLeft size={15} aria-hidden="true" /> Back to dashboard</Link>
        </div>
      </div>}
      <PageHero title={title} text={text} breadcrumb={[[title]]} />
      {sections.map((section, index) => {
        const Layout = LAYOUTS[section.level] || TeamSection;
        return <Layout key={section.id} section={section} id={`team-section-${index}`} />;
      })}
      {!sections.length && <div className="rh-container rp-team-message"><h2>Nothing to show yet</h2><p>Publish a member in a visible section, or turn on “Include drafts” above.</p></div>}
    </div>
  );
}
