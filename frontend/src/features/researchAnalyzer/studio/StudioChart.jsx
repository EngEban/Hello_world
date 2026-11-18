/** Charts for result cards: interval plots (dots / forest), bars, lines, scatter and ROC. */
import React, { useRef } from 'react';
import { Bar, BarChart, CartesianGrid, ErrorBar, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ReferenceLine } from 'recharts';
import { Download } from 'lucide-react';
import { num } from './resultModel';

const INK = '#062b80';
const ACCENT = '#126ac6';
const MUTED = '#8b97ab';
const AXIS = { fontSize: 11, fill: '#5b6b86' };

function downloadSvg(container, name) {
  const svg = container?.querySelector('svg');
  if (!svg) return;
  const data = new XMLSerializer().serializeToString(svg);
  const { width, height } = svg.getBoundingClientRect();
  const canvas = document.createElement('canvas');
  canvas.width = width * 2;
  canvas.height = height * 2;
  const context = canvas.getContext('2d');
  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, canvas.width, canvas.height);
  const image = new Image();
  image.onload = () => {
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const link = document.createElement('a');
    link.download = `${name}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  };
  image.src = `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(data)))}`;
}

/** Interval rows drawn in HTML so long labels wrap and the plot works in RTL. */
function IntervalPlot({ data, log = false, reference, unit }) {
  const values = data.flatMap((d) => [d.low, d.high, d.value]).filter((v) => v !== null && v !== undefined && Number.isFinite(v) && (!log || v > 0));
  if (!values.length) return null;
  const transform = (v) => (log ? Math.log(v) : v);
  let min = Math.min(...values.map(transform), reference !== undefined ? transform(reference) : Infinity);
  let max = Math.max(...values.map(transform), reference !== undefined ? transform(reference) : -Infinity);
  const pad = (max - min) * 0.08 || 1;
  min -= pad;
  max += pad;
  const position = (v) => `${(((transform(v) - min) / (max - min)) * 100).toFixed(2)}%`;
  const tick = (v) => (log ? num(Math.exp(v), 2) : num(v, Math.abs(max - min) < 10 ? 2 : 1));
  return (
    <div className="ras-interval" role="img" aria-label={`Estimates with 95% confidence intervals${unit ? ` (${unit})` : ''}`}>
      {data.map((d) => {
        const valid = d.low !== null && d.low !== undefined && d.high !== null && d.high !== undefined && (!log || (d.low > 0 && d.high > 0));
        const excludes = reference !== undefined && valid && (d.low > reference || d.high < reference);
        return (
          <div className="ras-interval-row" key={d.name}>
            <span className="ras-interval-label" title={d.name}>{d.name}</span>
            <span className="ras-interval-track">
              {reference !== undefined && <span className="ras-interval-ref" style={{ insetInlineStart: position(reference) }} />}
              {valid && <span className="ras-interval-line" style={{ insetInlineStart: position(d.low), width: `calc(${position(d.high)} - ${position(d.low)})`, background: reference === undefined || excludes ? ACCENT : MUTED }} />}
              {d.value !== null && d.value !== undefined && (!log || d.value > 0) && (
                <span className="ras-interval-dot" style={{ insetInlineStart: position(d.value), background: reference === undefined || excludes ? INK : MUTED }} />
              )}
            </span>
            <span className="ras-interval-value">{num(d.value)}{valid ? ` [${num(d.low)}, ${num(d.high)}]` : ''}</span>
          </div>
        );
      })}
      <div className="ras-interval-axis"><span />
        <span className="ras-interval-ticks"><span>{tick(min)}</span><span>{tick((min + max) / 2)}</span><span>{tick(max)}</span></span><span />
      </div>
    </div>
  );
}

export default function StudioChart({ chart, name = 'chart' }) {
  const ref = useRef(null);
  if (!chart?.data?.length) return null;
  let body = null;
  if (chart.kind === 'dots' || chart.kind === 'forest') {
    body = <IntervalPlot data={chart.data} log={chart.log} reference={chart.ref} unit={chart.unit} />;
  } else if (chart.kind === 'bars') {
    const data = chart.data.map((d) => ({ ...d, error: d.low !== undefined && d.low !== null ? [d.value - d.low, d.high - d.value] : 0 }));
    body = (
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e4e8f0" vertical={false} />
          <XAxis dataKey="name" tick={AXIS} axisLine={false} tickLine={false} />
          <YAxis tick={AXIS} axisLine={false} tickLine={false} unit={chart.unit || ''} />
          <Tooltip formatter={(value) => [num(value), '']} />
          <Bar dataKey="value" fill={ACCENT} radius={[6, 6, 0, 0]} maxBarSize={64} isAnimationActive={false}>
            <ErrorBar dataKey="error" width={6} strokeWidth={2} stroke={INK} direction="y" />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  } else if (chart.kind === 'line') {
    body = (
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chart.data} margin={{ top: 14, right: 20, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e4e8f0" vertical={false} />
          <XAxis dataKey="name" tick={AXIS} axisLine={false} tickLine={false} />
          <YAxis tick={AXIS} axisLine={false} tickLine={false} domain={['auto', 'auto']} />
          <Tooltip formatter={(value) => [num(value), 'Mean']} />
          <Line dataKey="value" stroke={ACCENT} strokeWidth={3} dot={{ r: 5, fill: INK, strokeWidth: 0 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    );
  } else if (chart.kind === 'scatter') {
    body = (
      <ResponsiveContainer width="100%" height={240}>
        <ScatterChart margin={{ top: 10, right: 16, bottom: 18, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e4e8f0" />
          <XAxis dataKey="x" type="number" name={chart.x} tick={AXIS} domain={['auto', 'auto']} label={{ value: chart.x, position: 'insideBottom', offset: -10, fontSize: 11 }} />
          <YAxis dataKey="y" type="number" name={chart.y} tick={AXIS} domain={['auto', 'auto']} />
          <Tooltip formatter={(value) => num(value)} />
          <Scatter data={chart.data} fill={ACCENT} fillOpacity={0.65} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    );
  } else if (chart.kind === 'roc') {
    const data = [...chart.data].map((p) => ({ fpr: 1 - p.specificity, tpr: p.sensitivity })).sort((a, b) => a.fpr - b.fpr || a.tpr - b.tpr);
    body = (
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={[{ fpr: 0, tpr: 0 }, ...data, { fpr: 1, tpr: 1 }]} margin={{ top: 10, right: 16, bottom: 18, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e4e8f0" />
          <XAxis dataKey="fpr" type="number" domain={[0, 1]} tick={AXIS} label={{ value: '1 − specificity', position: 'insideBottom', offset: -10, fontSize: 11 }} />
          <YAxis dataKey="tpr" type="number" domain={[0, 1]} tick={AXIS} />
          <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke={MUTED} strokeDasharray="4 4" />
          <Line dataKey="tpr" stroke={ACCENT} strokeWidth={2.5} dot={false} type="stepAfter" isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    );
  }
  if (!body) return null;
  return (
    <figure className="ras-chart" ref={ref}>
      {body}
      {chart.kind !== 'dots' && chart.kind !== 'forest' && (
        <button type="button" className="ras-chip-button" onClick={() => downloadSvg(ref.current, name)}><Download size={13} aria-hidden="true" /> PNG</button>
      )}
    </figure>
  );
}
