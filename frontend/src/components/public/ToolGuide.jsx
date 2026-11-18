import { ChevronDown } from 'lucide-react';
import GUIDES from '../../data/toolGuides.json';
import '../../styles/pages/tool-guide.css';

/**
 * "How to use" steps, coverage and FAQ under a research tool. The same text is
 * server-rendered for crawlers (backend/resref/seo.py reads toolGuides.json),
 * so what visitors see and what search engines index stay identical.
 */
export default function ToolGuide({ path }) {
  const guide = GUIDES[path];
  if (!guide) return null;
  const id = `tool-guide-${path.split('/').pop()}`;
  return (
    <section className="rp-tool-guide" aria-labelledby={id}>
      <div className="rp-tool-guide-inner">
        <div className="rp-tool-guide-intro">
          <h2 id={id}>How to use the {guide.name}</h2>
          <p>{guide.summary}</p>
          <ol className="rp-tool-guide-steps">
            {guide.steps.map((step, index) => <li key={index}><span aria-hidden="true">{index + 1}</span><p>{step}</p></li>)}
          </ol>
        </div>
        <div className="rp-tool-guide-covers">
          <h3>What it covers</h3>
          <ul>{guide.features.map(feature => <li key={feature}>{feature}</li>)}</ul>
        </div>
        <div className="rp-tool-guide-faq">
          <h2>Frequently asked questions</h2>
          {guide.faq.map(item => (
            <details key={item.q}>
              <summary>{item.q}<ChevronDown size={18} aria-hidden="true" /></summary>
              <p>{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
