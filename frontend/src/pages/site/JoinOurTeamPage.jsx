import { useEffect, useState } from 'react';
import { Award, ArrowRight, BarChart3, BriefcaseBusiness, Clock, Code2, Megaphone, Palette, PenTool, PlayCircle, SearchCheck, Users } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PublicWebsiteApi } from '../../api/publicWebsiteApi';
import GoogleFormDialog, { googleFormEmbedUrl } from '../../components/public/GoogleFormDialog';
import PageHero from '../../components/public/PageHero';
import SectionHeading from '../../components/public/SectionHeading';
import { useSiteSettings } from '../../contexts/SiteSettingsContext';
import { SEO } from '../../config/contentStructure';
import { usePageMeta } from '../../utils/seo';
import '../../styles/pages/join-team.css';

const iconMap = {
  pen: PenTool,
  megaphone: Megaphone,
  palette: Palette,
  code: Code2,
  chart: BarChart3,
  search: SearchCheck,
  users: Users,
  briefcase: BriefcaseBusiness,
};

const fallbackTeams = [
  { icon_key: 'pen', title: 'Education Team', description: 'Create educational materials and help make research knowledge easier to access.' },
  { icon_key: 'megaphone', title: 'Media Team', description: 'Share ResRef activities and research content with a growing community.' },
  { icon_key: 'users', title: 'Community Team', description: 'Welcome researchers, coordinate community conversations, and help members find the right ResRef support path.' },
  { icon_key: 'palette', title: 'Design Team', description: 'Transform ideas into clear, engaging, and useful visual materials.' },
  { icon_key: 'code', title: 'IT Team', description: 'Build and improve the digital tools behind the ResRef platform.' },
  { icon_key: 'chart', title: 'Data Entry Team', description: 'Organize resources and keep the database accurate and accessible.' },
  { icon_key: 'search', title: 'Quality Control Team', description: 'Review content and support a consistent standard of quality.' },
  { icon_key: 'users', title: 'Web & SEO Team', description: 'Help researchers discover valuable content through a stronger web presence.' },
  { icon_key: 'users', title: 'Community Team', description: 'Build connections with researchers, support conversations, and strengthen the ResRef community.' },
];

const expectations = [
  [Clock, 'join_expect_1'],
  [PlayCircle, 'join_expect_2'],
  [Award, 'join_expect_3'],
];

export default function JoinOurTeamPage() {
  usePageMeta(SEO.join);
  const settings = useSiteSettings();
  const [openForm, setOpenForm] = useState(null);
  const [remoteTeams, setRemoteTeams] = useState([]);
  const teamActionUrl = settings.join_team_action_url || '';
  const teams = remoteTeams.length ? remoteTeams : fallbackTeams;

  useEffect(() => {
    let active = true;
    PublicWebsiteApi.getJoinTeamEntries()
      .then(data => {
        if (active) setRemoteTeams(data.results || []);
      })
      .catch(() => {});
    return () => { active = false; };
  }, []);

  return (
    <div className="rh-page rp-join">
      <PageHero
        title="Join the ResRef Team"
        text="Contribute to a growing research platform through education, media, design, technology, data, quality control, and research support roles."
        settingPrefix="join"
      >
        <a className="rh-button rh-button-light" href="#join-teams"><span>Apply now</span><ArrowRight className="rh-button-icon" size={17} aria-hidden="true" /></a>
      </PageHero>

      <section className="rh-section rp-join-teams" id="join-teams" aria-labelledby="join-teams-title">
        <div className="rh-container">
          <SectionHeading
            id="join-teams-title"
            eyebrow={settings.join_teams_eyebrow}
            title={settings.join_teams_title}
            text={settings.join_teams_text}
            align="center"
          />
          <div className="rp-join-grid">
            {teams.map((team, index) => {
              const Icon = iconMap[team.icon_key] || BriefcaseBusiness;
              const href = team.action_url || teamActionUrl;
              const opensExternalForm = /^https?:\/\//i.test(href);
              // Older cards still hold the removed form's #team-application address.
              if (!href || href.startsWith('#')) {
                return (
                  <article className="rp-join-card is-soon" key={`${team.slug || team.title}-${index}`} data-reveal style={{ '--rh-delay': `${(index % 3) * 80}ms` }}>
                    <span className="rh-card-icon" aria-hidden="true"><Icon size={24} /></span>
                    <h3>{team.title}</h3>
                    <p>{team.description}</p>
                    <span className="rp-join-card-action"><Clock size={15} aria-hidden="true" />Applications opening soon</span>
                  </article>
                );
              }
              return (
              <a
                className="rp-join-card"
                key={`${team.slug || team.title}-${index}`}
                href={href}
                target={opensExternalForm ? '_blank' : undefined}
                rel={opensExternalForm ? 'noreferrer' : undefined}
                aria-label={`${team.action_label || settings.join_team_action_label} for ${team.title}`}
                onClick={event => {
                  const embedUrl = googleFormEmbedUrl(href);
                  // A modified click still opens a new tab, as with any link.
                  if (embedUrl && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
                    event.preventDefault();
                    setOpenForm({ title: team.title, href, embedUrl });
                  }
                }}
                data-reveal
                style={{ '--rh-delay': `${(index % 3) * 80}ms` }}
              >
                <span className="rh-card-icon" aria-hidden="true"><Icon size={24} /></span>
                <h3>{team.title}</h3>
                <p>{team.description}</p>
                <span className="rp-join-card-action">{team.action_label || settings.join_team_action_label}<ArrowRight size={15} aria-hidden="true" /></span>
              </a>
              );
            })}
          </div>
        </div>
      </section>

      <section className="rh-section rh-surface-mist rp-join-expect" aria-labelledby="join-expect-title">
        <div className="rh-container">
          <h2 id="join-expect-title">{settings.join_expect_title}</h2>
          <ul>
            {expectations.map(([Icon, key]) => (
              <li key={key}>
                <span className="rh-card-icon" aria-hidden="true"><Icon size={22} /></span>
                <div>
                  <h3>{settings[`${key}_title`]}</h3>
                  <p>{settings[`${key}_text`]}</p>
                </div>
              </li>
            ))}
          </ul>
          <p className="rp-join-expect-help">{settings.join_expect_help_text} <Link to="/contact">{settings.join_expect_help_link}</Link></p>
        </div>
      </section>
      <GoogleFormDialog form={openForm} onClose={() => setOpenForm(null)} />
    </div>
  );
}
