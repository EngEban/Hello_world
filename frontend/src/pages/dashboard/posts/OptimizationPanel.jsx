import { AlertTriangle, ArrowRight, Bot, CheckCircle2, ChevronDown, CircleMinus, Code2, Lightbulb, MessageCircleQuestion, Search, Sparkles, Type, XCircle } from 'lucide-react';
import { BAND_LABELS, GROUPS, scoreBand } from './seoAnalysis';
import { SeoFields } from './EditorSections';
import '../../../styles/dashboard/dash-optimization.css';

export const GROUP_ICONS = { seo: Search, readability: Type, aeo: MessageCircleQuestion, geo: Bot };
const STATUS_ORDER = { bad: 0, warn: 1, good: 2, na: 3 };
const STATUS_ICON = { bad: XCircle, warn: AlertTriangle, good: CheckCircle2, na: CircleMinus };
const STATUS_LABEL = { bad: 'Problem', warn: 'Improve', good: 'Passed', na: 'Not applicable' };

/** Score ring coloured by band (good ≥ 80, needs work ≥ 50, poor < 50). */
export function ScoreDial({ score, size = 64, label }) {
  const radius = size / 2 - 5;
  const circumference = 2 * Math.PI * radius;
  const band = scoreBand(score);
  return <span className={`dopt-dial is-${band}`} style={{ width: size, height: size }} role="img" aria-label={`${label ? `${label}: ` : ''}${score ?? 'not scored'}${score === null || score === undefined ? '' : ' out of 100'}, ${BAND_LABELS[band]}`}>
    <svg viewBox={`0 0 ${size} ${size}`} aria-hidden="true"><circle cx={size / 2} cy={size / 2} r={radius} /><circle cx={size / 2} cy={size / 2} r={radius} className="is-value" strokeDasharray={circumference} strokeDashoffset={circumference * (1 - (score || 0) / 100)} /></svg>
    <strong aria-hidden="true">{score ?? '–'}</strong>
  </span>;
}

/** Most valuable fixes first: problems before improvements, heavier checks first. */
export function topFixes(analysis, limit = 3) {
  return analysis.checks.filter(check => check.status === 'bad' || check.status === 'warn')
    .sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status] || b.weight - a.weight)
    .slice(0, limit);
}

/** Sidebar summary: overall score, the four lenses and the next fixes. */
export function OptimizationSummary({ analysis, onOpenGroup, onFix }) {
  const fixes = topFixes(analysis);
  const band = scoreBand(analysis.scores.overall);
  return <section className="dart-card dopt-summary" aria-label="Search and AI optimization">
    <div className="dopt-summary-head">
      <ScoreDial score={analysis.scores.overall} label="Optimization score" />
      <div><h2>Optimization score</h2><p className={`dopt-band is-${band}`}>{BAND_LABELS[band]} · updates as you type</p></div>
    </div>
    <div className="dopt-lenses">
      {GROUPS.map(group => { const Icon = GROUP_ICONS[group.key]; const score = analysis.scores[group.key]; return <button type="button" key={group.key} className={`is-${scoreBand(score)}`} onClick={() => onOpenGroup(group.key)} title={group.description}>
        <Icon size={14} aria-hidden="true" /><span>{group.label}</span><strong>{score ?? '–'}</strong>
      </button>; })}
    </div>
    {fixes.length ? <div className="dopt-next">
      <span className="dopt-next-label"><Lightbulb size={13} aria-hidden="true" /> Next best fixes</span>
      <ul>{fixes.map(check => <li key={check.id}><button type="button" onClick={() => onFix(check)}>
        <StatusIcon status={check.status} /><span><strong>{check.label}</strong><small>{check.fix || check.message}</small></span><ArrowRight size={13} aria-hidden="true" />
      </button></li>)}</ul>
    </div> : <p className="dopt-all-good"><Sparkles size={15} aria-hidden="true" /> Every check passes. Nice work.</p>}
    <button type="button" className="dart-link-button dopt-open" onClick={() => onOpenGroup('seo')}>Open full analysis</button>
  </section>;
}

function StatusIcon({ status }) {
  const Icon = STATUS_ICON[status];
  return <Icon size={15} className={`dopt-status is-${status}`} aria-label={STATUS_LABEL[status]} />;
}

function CheckRow({ check, onFix }) {
  return <li className={`dopt-check is-${check.status}`}>
    <StatusIcon status={check.status} />
    <div>
      <strong>{check.label}</strong>
      <p>{check.message}</p>
      {check.fix && check.status !== 'good' && <p className="dopt-fix"><Lightbulb size={13} aria-hidden="true" /> {check.fix}</p>}
    </div>
    {check.status !== 'good' && check.status !== 'na' && check.target && <button type="button" className="dopt-go" onClick={() => onFix(check)}>Fix <ArrowRight size={13} aria-hidden="true" /></button>}
  </li>;
}

function CheckList({ checks, onFix }) {
  const open = checks.filter(check => check.status === 'bad' || check.status === 'warn').sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status] || b.weight - a.weight);
  const passed = checks.filter(check => check.status === 'good');
  const skipped = checks.filter(check => check.status === 'na');
  return <div className="dopt-checks">
    {open.length ? <ul>{open.map(check => <CheckRow key={check.id} check={check} onFix={onFix} />)}</ul> : <p className="dopt-all-good"><Sparkles size={15} aria-hidden="true" /> Nothing to fix in this lens.</p>}
    {passed.length > 0 && <details className="dopt-more"><summary>{passed.length} passed <ChevronDown size={14} aria-hidden="true" /></summary><ul>{passed.map(check => <CheckRow key={check.id} check={check} onFix={onFix} />)}</ul></details>}
    {skipped.length > 0 && <details className="dopt-more"><summary>{skipped.length} not applicable yet <ChevronDown size={14} aria-hidden="true" /></summary><ul>{skipped.map(check => <CheckRow key={check.id} check={check} onFix={onFix} />)}</ul></details>}
  </div>;
}

function KeyphraseFields({ editing, setSeoSetting, suggestion }) {
  const settings = editing.seo_settings || {};
  const related = (settings.related_keyphrases || []).join(', ');
  return <div className="dopt-keyphrase">
    <label>Focus keyphrase
      <span className="dopt-input-row">
        <input id="article-field-keyphrase" value={settings.focus_keyphrase || ''} onChange={event => setSeoSetting('focus_keyphrase', event.target.value)} placeholder="The main query this article should rank and be cited for" dir="auto" />
        {suggestion && <button type="button" className="admin-button admin-button-secondary" onClick={() => setSeoSetting('focus_keyphrase', suggestion)} title="Use a keyphrase taken from the title"><Sparkles size={14} /> Use “{suggestion}”</button>}
      </span>
      <small>1–4 words people actually search for. It is added to the article’s structured-data keywords.</small>
    </label>
    <label>Related keyphrases
      <input value={related} onChange={event => setSeoSetting('related_keyphrases', event.target.value.split(',').map(item => item.trimStart()).slice(0, 4))} placeholder="Synonyms or abbreviations, separated by commas (up to 4)" dir="auto" />
      <small>Counted in the introduction, subheadings and image alt text, so you can vary wording naturally.</small>
    </label>
    <label className="admin-check dart-switch"><input type="checkbox" checked={settings.cornerstone === true} onChange={event => setSeoSetting('cornerstone', event.target.checked)} /><span className="dart-switch-track" aria-hidden="true" /> Cornerstone content — a pillar guide others link to (expects 900+ words)</label>
  </div>;
}

function PublishedSignals({ analysis }) {
  return <div className="dopt-signals">
    <span className="dart-field-label"><Code2 size={13} aria-hidden="true" /> Published for search and AI engines</span>
    <ul>
      <li><strong>Title tag</strong><span>{analysis.rendered_title}</span></li>
      <li><strong>Structured data</strong><span>{analysis.schema.join(' · ')}{analysis.references.length ? ` · ${analysis.references.length} citation${analysis.references.length === 1 ? '' : 's'}` : ''}</span></li>
      <li><strong>FAQ answers</strong><span>{analysis.faq.length ? `${analysis.faq.length} question${analysis.faq.length === 1 ? '' : 's'} detected` : 'None detected'}</span></li>
    </ul>
    {analysis.faq.length > 0 && <details className="dopt-more"><summary>Show detected questions <ChevronDown size={14} aria-hidden="true" /></summary><ol className="dopt-faq">{analysis.faq.map(item => <li key={item.question}><strong>{item.question}</strong><span>{item.answer.length > 180 ? `${item.answer.slice(0, 177)}…` : item.answer}</span></li>)}</ol></details>}
  </div>;
}

/** Main editor panel: keyphrase, search appearance, then the four analysis lenses. */
export default function OptimizationPanel({ editing, update, setSeoSetting, publicUrl, analysis, group, onGroup, onFix }) {
  const active = GROUPS.find(item => item.key === group) || GROUPS[0];
  const checks = analysis.checks.filter(check => check.group === active.key);
  return <div className="dopt-panel">
    <KeyphraseFields editing={editing} setSeoSetting={setSeoSetting} suggestion={analysis.suggestion} />
    <SeoFields editing={editing} update={update} publicUrl={publicUrl} renderedTitle={analysis.rendered_title} />
    <div className="dopt-analysis">
      <div className="dopt-tabs" role="tablist" aria-label="Analysis lenses">
        {GROUPS.map(item => { const Icon = GROUP_ICONS[item.key]; const score = analysis.scores[item.key]; const open = analysis.checks.filter(check => check.group === item.key && (check.status === 'bad' || check.status === 'warn')).length; return <button type="button" role="tab" id={`dopt-tab-${item.key}`} aria-controls="dopt-tabpanel" aria-selected={item.key === active.key} key={item.key} className={`is-${scoreBand(score)}`} onClick={() => onGroup(item.key)}>
          <span className="dopt-tab-top"><Icon size={15} aria-hidden="true" />{item.label}<strong>{score ?? '–'}</strong></span>
          <small>{item.short} · {open ? `${open} to review` : 'all clear'}</small>
        </button>; })}
      </div>
      <div className="dopt-tabpanel" id="dopt-tabpanel" role="tabpanel" aria-labelledby={`dopt-tab-${active.key}`}>
        <p className="dopt-lens-intro">{active.description}.{active.key === 'aeo' ? ' “People also ask” boxes and voice assistants quote short, direct answers to real questions.' : active.key === 'geo' ? ' AI search tools such as Google AI Overviews, ChatGPT and Perplexity favour clearly structured, sourced, attributable content.' : active.key === 'readability' ? (analysis.language === 'en' ? ' Easy text keeps readers on the page and is easier to quote.' : ' Some readability checks are measured for English text only.') : ' Placement of the keyphrase, title and description, links and images.'}</p>
        <CheckList checks={checks} onFix={onFix} />
      </div>
    </div>
    <PublishedSignals analysis={analysis} />
  </div>;
}
