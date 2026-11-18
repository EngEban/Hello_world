import { ArrowRight, Bot, CheckCircle2, MessageCircleQuestion, RefreshCw, Search, ShieldAlert, Type } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import { DashboardCard, StateBlock } from '../../../components/dashboard/DashboardPrimitives';
import { BAND_LABELS, CHECK_BY_ID, GROUPS, scoreBand } from '../posts/seoAnalysis';
import '../../../styles/dashboard/dash-optimization.css';

const ICONS = { seo: Search, readability: Type, aeo: MessageCircleQuestion, geo: Bot };
const CRAWLERS = { allow: 'AI crawlers allowed', 'search-only': 'AI search crawlers only', block: 'AI crawlers blocked' };

/** SEO / AEO / GEO health of every article, with the issues worth fixing first. */
export default function OptimizationHealth() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const autoStarted = useRef(false);
  const load = () => { setError(''); return DashboardApi.getSeoOverview().then(next => { setData(next); return next; }).catch(err => { setError(err.message); return null; }); };
  // Scores are calculated on demand and cached, in small batches so no single request runs long.
  const analyseRemaining = async () => {
    setBusy(true); setError('');
    try {
      let previous = Infinity;
      for (let round = 0; round < 50; round += 1) {
        const result = await DashboardApi.refreshSeoReports();
        if (!result.remaining || result.remaining >= previous) break;
        previous = result.remaining;
      }
      await load();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  useEffect(() => {
    load().then(next => { if (next?.pending && !autoStarted.current) { autoStarted.current = true; analyseRemaining(); } });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const actions = <Link to="/dashboard/posts?sort=score">Lowest scores <ArrowRight size={13} /></Link>;
  if (error && !data) return <DashboardCard title="Search & AI visibility" className="dopt-home" actions={actions}><StateBlock type="error" title="Could not load optimization health" text={error} /></DashboardCard>;
  if (!data) return <DashboardCard title="Search & AI visibility" className="dopt-home"><StateBlock type="loading" title="Analysing articles" text="Scoring SEO, answer-engine and AI visibility." /></DashboardCard>;
  const analysed = data.analysed || 0;
  const overall = data.averages.overall;
  const band = scoreBand(overall);
  const share = key => (analysed ? Math.round((data.bands[key] / analysed) * 100) : 0);
  return <DashboardCard title="Search & AI visibility" eyebrow={`SEO · AEO · GEO · ${analysed} of ${data.total} articles analysed`} className="dopt-home" actions={actions}>
    <div className="dopt-home-grid">
      <div className="dopt-home-score">
        <span className={`dopt-home-average is-${band}`}><strong>{overall ?? '–'}</strong><small>average score</small></span>
        <p className={`dopt-band is-${band}`}>{BAND_LABELS[band]}</p>
        <div className="dopt-distribution" role="img" aria-label={`${data.bands.good} good, ${data.bands.ok} need work, ${data.bands.poor} poor`}>
          {['good', 'ok', 'poor'].map(key => <i key={key} className={`is-${key}`} style={{ width: `${share(key)}%` }} />)}
        </div>
        <ul className="dopt-distribution-legend">
          <li className="is-good"><Link to="/dashboard/posts?sort=score_desc">{data.bands.good} good</Link></li>
          <li className="is-ok"><Link to="/dashboard/posts?sort=score">{data.bands.ok} need work</Link></li>
          <li className="is-poor"><Link to="/dashboard/posts?needs=low_score">{data.bands.poor} poor</Link></li>
        </ul>
      </div>
      <div className="dopt-home-lenses">
        {GROUPS.map(group => { const Icon = ICONS[group.key]; const score = data.averages[group.key]; return <Link key={group.key} to={`/dashboard/posts?needs=${group.key}_low`} className={`is-${scoreBand(score)}`} title={`Articles with ${group.label} below 50`}>
          <span><Icon size={15} aria-hidden="true" /> {group.label}<small>{group.description}</small></span>
          <strong>{score ?? '–'}</strong>
          <i aria-hidden="true"><b style={{ width: `${score || 0}%` }} /></i>
        </Link>; })}
      </div>
      <div className="dopt-home-issues">
        <h3>Fix first</h3>
        {data.issues.length ? <ol>{data.issues.slice(0, 6).map(issue => <li key={issue.id}><Link to={`/dashboard/posts?needs=issue:${issue.id}`}>
          <span><strong>{CHECK_BY_ID[issue.id]?.label || issue.id}</strong><small>{GROUPS.find(group => group.key === issue.group)?.short}</small></span>
          <em>{issue.bad ? <b className="is-bad">{issue.bad} problem{issue.bad === 1 ? '' : 's'}</b> : null}{issue.warn ? <b className="is-warn">{issue.warn} to improve</b> : null}</em>
        </Link></li>)}</ol> : <p className="dopt-all-good"><CheckCircle2 size={15} aria-hidden="true" /> No recurring issues.</p>}
      </div>
      <div className="dopt-home-lowest">
        <h3>Lowest scoring</h3>
        {data.lowest.length ? <ul>{data.lowest.map(post => <li key={post.id}><Link to={`/dashboard/posts?${post.post_type === 'page' ? 'type=page&' : ''}edit=${post.id}`}>
          <span className={`dopt-pill is-${scoreBand(post.scores.overall)}`}>{post.scores.overall}</span><span className="dopt-lowest-title">{post.title || 'Untitled'}</span>
        </Link></li>)}</ul> : <p className="dash-card-note">No analysed articles yet.</p>}
      </div>
    </div>
    <footer className="dopt-home-foot">
      <span className={data.signals.indexing_allowed ? 'is-good' : 'is-warn'}>{data.signals.indexing_allowed ? 'Search indexing on' : 'Indexing off (noindex)'}</span>
      <span className={data.signals.ai_crawlers === 'block' ? 'is-warn' : 'is-good'}>{CRAWLERS[data.signals.ai_crawlers] || data.signals.ai_crawlers}</span>
      <span className="is-good">llms.txt & sitemap published</span>
      <span>{data.signals.faq_articles} with FAQ markup · {data.signals.cited_articles} citing sources</span>
      {(data.pending > 0 || busy) && <button type="button" className="admin-button admin-button-secondary" disabled={busy} onClick={analyseRemaining}><RefreshCw size={14} className={busy ? 'spin' : ''} /> {busy ? `Analysing ${data.pending} articles…` : `Analyse ${data.pending} remaining`}</button>}
      {error && <span className="is-warn"><ShieldAlert size={14} aria-hidden="true" /> {error}</span>}
    </footer>
  </DashboardCard>;
}
