/**
 * Turn any analyzer result into one display model used by result cards, the report and Word export:
 *
 *   { title, meta, headline: {en, ar}, kpis: [{label, value, sub}], tables: [{caption, columns, rows, note, full}],
 *     checks: [{name, ok, detail}], notes: [], chart, text: {en, ar}, methods: {en, ar} }
 *
 * Tables marked `full: true` only appear in the Full view.
 */

export const num = (value, digits = 2) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return Number(value).toFixed(digits);
};

export const pText = (p) => {
  if (p === null || p === undefined) return '—';
  if (p < 0.001) return '< .001';
  let text = Number(p).toFixed(3);
  if ((p < 0.05) !== (Number(text) < 0.05)) text = Number(p).toFixed(4);
  return text.replace(/^0\./, '.');
};

const ci = (pair, digits = 2, sep = ' to ') => (pair && pair[0] !== null && pair[0] !== undefined ? `${num(pair[0], digits)}${sep}${num(pair[1], digits)}` : '—');
const pct = (value, digits = 1) => (value === null || value === undefined ? '—' : `${(value * 100).toFixed(digits)}%`);
const sigWord = (p) => (p !== null && p !== undefined && p < 0.05);

const LABELS = {
  two_by_two: 'Risk ratio & odds ratio (2×2)', chi_square: 'Chi-square test', ttest_student: 'Independent t test', ttest_welch: 'Welch t test',
  mann_whitney_u: 'Mann-Whitney U', anova_full: 'One-way ANOVA', welch_anova: 'Welch ANOVA', anova: 'One-way ANOVA', kruskal_dunn: 'Kruskal-Wallis + Dunn',
  kruskal_wallis: 'Kruskal-Wallis', paired_ttest: 'Paired t test', wilcoxon_signed_rank: 'Wilcoxon signed-rank', one_sample_ttest: 'One-sample t test',
  pearson: 'Pearson correlation', spearman: 'Spearman correlation', kendall: "Kendall's τ", partial_correlation: 'Partial correlation',
  correlation_matrix: 'Correlation matrix', linear_regression: 'Linear regression', logistic_regression: 'Binary logistic regression',
  multinomial_logistic: 'Multinomial logistic regression', ordinal_logistic: 'Ordinal logistic regression', count_regression: 'Count regression',
  factorial_anova: 'Factorial ANOVA', ancova: 'ANCOVA', repeated_measures_anova: 'Repeated-measures ANOVA', mixed_anova: 'Mixed ANOVA',
  reliability: "Cronbach's alpha", cronbach_alpha: "Cronbach's alpha", cohens_kappa: "Cohen's κ", fleiss_kappa: "Fleiss' κ", icc: 'Intraclass correlation',
  diagnostic_accuracy: 'Diagnostic accuracy', table_one: 'Table 1', descriptive: 'Descriptive statistics', goodness_of_fit: 'Goodness of fit', mcnemar: 'McNemar test',
};

export const methodLabel = (result) => LABELS[result?.test] || result?.test || 'Analysis';

function coefficientTable(rows, { estimate = 'b', estimateLabel = 'B', ciKey = 'ci_95', extra = [] }) {
  return {
    columns: ['Predictor', estimateLabel, '95% CI', ...extra.map((e) => e.label), 'p'],
    rows: rows.filter((row) => row.term !== 'Intercept').map((row) => [
      row.term, num(row[estimate], 2), ci(row[ciKey], 2), ...extra.map((e) => e.get(row)), pText(row.p),
    ]),
  };
}

function groupTable(groups, caption = 'Groups') {
  const entries = Object.entries(groups || {});
  if (!entries.length) return null;
  const median = entries.some(([, g]) => g.median !== undefined);
  return {
    caption,
    columns: ['Group', 'n', median ? 'Median' : 'Mean', median ? '' : 'SD', median ? '' : '95% CI'].filter(Boolean),
    rows: entries.map(([name, g]) => (median ? [name, g.n, num(g.median)] : [name, g.n, num(g.mean), num(g.sd), ci(g.ci_95, 2, ', ')])),
  };
}

function pairwiseTable(pairs, method, full = true) {
  if (!pairs?.length) return null;
  return {
    caption: `Pairwise comparisons (${method})`, full,
    columns: ['Comparison', 'Difference', 'Effect', 'Adjusted p'],
    rows: pairs.map((pair) => [`${pair.group1} vs ${pair.group2}`, num(pair.mean_difference ?? pair.z, 2), num(pair.effect, 2), pText(pair.p_adjusted)]),
  };
}

function assumptionChecks(assumptions = {}) {
  const checks = [];
  if (assumptions.levene) checks.push({ name: 'Equal spread (Levene)', ok: assumptions.levene.equal_var_assumed, detail: `p = ${pText(assumptions.levene.p)}` });
  if (assumptions.multicollinearity) checks.push({ name: 'No multicollinearity (VIF)', ok: assumptions.multicollinearity.passed, detail: assumptions.multicollinearity.note });
  if (assumptions.events_per_predictor) checks.push({ name: 'Events per predictor', ok: assumptions.events_per_predictor.passed, detail: assumptions.events_per_predictor.note });
  if (assumptions.calibration) checks.push({ name: 'Calibration (Hosmer-Lemeshow)', ok: assumptions.calibration.passed, detail: assumptions.calibration.note });
  if (assumptions.discrimination) checks.push({ name: 'Discrimination (AUC)', ok: assumptions.discrimination.passed, detail: assumptions.discrimination.note });
  if (assumptions.residual_distribution) {
    const r = assumptions.residual_distribution;
    checks.push({ name: 'Residual distribution', ok: r.parametric_supported !== false, detail: r.summary || r.note || '' });
  }
  return checks;
}

function contingencyRows(table) {
  // Backend tables are column-major ({column: {row: count}}).
  const columns = Object.keys(table || {});
  const rows = [...new Set(columns.flatMap((c) => Object.keys(table[c])))];
  return { columns, rows: rows.map((r) => [r, ...columns.map((c) => table[c][r] ?? 0)]) };
}

const builders = {
  two_by_two(r) {
    const [exposed, reference] = r.table.rows;
    return {
      meta: `${r.outcome} × ${r.grouping} · ${r.method} · n = ${r.n}`,
      headline: {
        en: `${r.outcome} = ${r.event}: ${pct(exposed.risk)} with ${exposed.group} vs ${pct(reference.risk)} with ${reference.group}.`,
        ar: `${r.outcome} = ${r.event}: ${pct(exposed.risk)} في ${exposed.group} مقابل ${pct(reference.risk)} في ${reference.group}.`,
      },
      kpis: [
        { label: 'Risk difference', value: `${num(r.risk_difference * 100, 1)} pts`, sub: `95% CI ${ci(r.risk_difference_ci_95.map((v) => v * 100), 1)}` },
        { label: 'Risk ratio', value: num(r.risk_ratio), sub: `95% CI ${ci(r.risk_ratio_ci_95)}` },
        { label: 'Odds ratio', value: num(r.odds_ratio), sub: `95% CI ${ci(r.odds_ratio_ci_95)}` },
        { label: r.method.startsWith('Fisher') ? "Fisher's exact p" : 'Chi-square p', value: pText(r.p), sub: 'two-sided' },
      ],
      tables: [{
        caption: `${r.outcome} by ${r.grouping}`, columns: [r.grouping, `${r.event}, n (%)`, 'Other', 'Total'],
        rows: r.table.rows.map((row) => [`${row.group}${row.group === r.reference_group ? ' (reference)' : ''}`, `${row.events} (${(row.risk * 100).toFixed(1)})`, row.non_events, row.total]),
      }],
      notes: [...(r.notes || []), r.number_needed ? `Number needed to ${r.number_needed.kind}: ${Math.ceil(r.number_needed.value)} (one extra event for every ${Math.ceil(r.number_needed.value)} people treated with ${r.exposed_group} instead of ${r.reference_group}).` : null].filter(Boolean),
      checks: [{ name: 'Expected counts', ok: r.min_expected >= 5, detail: `Smallest expected count ${num(r.min_expected, 1)}` }],
      chart: { kind: 'bars', unit: '%', data: r.table.rows.map((row) => ({ name: row.group, value: row.risk * 100, low: row.risk_ci_95[0] * 100, high: row.risk_ci_95[1] * 100 })) },
      methods: { en: `Proportions were compared with ${r.method}; the risk difference (Newcombe 95% CI), risk ratio and odds ratio are reported with ${r.reference_group} as the reference.`,
                 ar: `قورنت النسب باستخدام ${r.method_ar || r.method}، مع عرض فرق الخطر ونسبة الخطر ونسبة الأرجحية بفترات ثقة 95% واعتبار ${r.reference_group} مرجعاً.` },
    };
  },
  chi_square(r) {
    const table = contingencyRows(r.contingency_table);
    const fisher = r.preferred_test === 'fisher_exact';
    return {
      meta: `${r.variables.join(' × ')} · ${fisher ? "Fisher's exact test" : 'χ² test'} · n = ${r.n}`,
      headline: sigWord(r.p)
        ? { en: `${r.variables[0]} and ${r.variables[1]} are associated.`, ar: `توجد علاقة بين ${r.variables[0]} و${r.variables[1]}.` }
        : { en: `No clear association between ${r.variables[0]} and ${r.variables[1]}.`, ar: `لا توجد علاقة واضحة بين ${r.variables[0]} و${r.variables[1]}.` },
      kpis: [
        { label: fisher ? "Fisher's exact p" : `χ²(${r.dof})`, value: fisher ? pText(r.p) : num(r.chi2), sub: fisher ? '' : `p = ${pText(r.p)}` },
        { label: "Cramér's V", value: num(r.cramer_v), sub: r.effect_size },
        { label: 'n', value: r.n, sub: '' },
      ],
      tables: [
        { caption: `${r.variables[0]} × ${r.variables[1]} (counts)`, columns: [r.variables[0], ...table.columns], rows: table.rows },
        r.posthoc_cells?.length ? { caption: 'Cells that differ (adjusted residuals, Bonferroni)', full: true, columns: ['Cell', 'Observed', 'Expected', 'Residual', 'Adjusted p'],
          rows: r.posthoc_cells.map((c) => [`${c.row} / ${c.column}`, c.observed, num(c.expected, 1), num(c.adjusted_residual), pText(c.p_adjusted)]) } : null,
      ].filter(Boolean),
      checks: [{ name: 'Expected counts ≥ 5', ok: r.assumption_check?.passed, detail: `${r.assumption_check?.pct_below_5 ?? 0}% of cells below 5` }],
      methods: { en: `The association was tested with ${fisher ? "Fisher's exact test" : 'the chi-square test of independence'}; Cramér's V is reported as the effect size.`,
                 ar: `اختُبرت العلاقة باستخدام ${fisher ? 'اختبار فيشر الدقيق' : 'اختبار كاي مربع للاستقلالية'} مع عرض V لكرامر حجماً للأثر.` },
    };
  },
  ttest_student(r) { return builders._ttest(r, 'Student'); },
  ttest_welch(r) { return builders._ttest(r, 'Welch'); },
  _ttest(r, kind) {
    const names = Object.keys(r.groups || {});
    const [a, b] = names.map((n) => r.groups[n]);
    return {
      meta: `${r.outcome} by ${r.grouping} · ${kind} t test · n = ${r.n}`,
      headline: sigWord(r.p)
        ? { en: `${r.outcome} differed between groups: ${names[0]} ${num(a?.mean)} vs ${names[1]} ${num(b?.mean)}.`, ar: `اختلف ${r.outcome} بين المجموعتين: ${names[0]} ${num(a?.mean)} مقابل ${names[1]} ${num(b?.mean)}.` }
        : { en: `No clear difference in ${r.outcome} between ${names.join(' and ')}.`, ar: `لا يوجد فرق واضح في ${r.outcome} بين ${names.join(' و')}.` },
      kpis: [
        { label: 'Mean difference', value: num(r.mean_difference), sub: `95% CI ${ci(r.ci_95)}` },
        { label: `t(${kind === 'Student' ? num(r.df, 0) : num(r.df, 1)})`, value: num(r.t), sub: `p = ${pText(r.p)}` },
        { label: "Hedges' g", value: num(r.hedges_g), sub: r.effect_size },
      ],
      tables: [groupTable(r.groups, 'Group summary')].filter(Boolean),
      checks: assumptionChecks(r.assumptions),
      notes: r.recommend_mwu ? ['At least one group is skewed; the Mann-Whitney U test is a useful check.'] : [],
      chart: { kind: 'bars', data: names.map((n) => ({ name: n, value: r.groups[n].mean, low: r.groups[n].ci_95?.[0], high: r.groups[n].ci_95?.[1] })) },
      methods: { en: `${r.outcome} was compared between groups with ${kind === 'Welch' ? "Welch's t test (unequal variances)" : "Student's t test"}; Hedges' g is the effect size.`,
                 ar: `قورن ${r.outcome} بين المجموعتين باختبار (ت) ${kind === 'Welch' ? 'لويلش' : 'لستيودنت'} مع g لهيدجز حجماً للأثر.` },
    };
  },
  mann_whitney_u(r) {
    return {
      meta: `${r.outcome} by ${r.grouping} · Mann-Whitney U · n = ${r.n}`,
      headline: sigWord(r.p) ? { en: `${r.outcome} differed between groups (rank-based).`, ar: `اختلف ${r.outcome} بين المجموعتين.` }
        : { en: `No clear difference in ${r.outcome} between groups.`, ar: `لا يوجد فرق واضح في ${r.outcome}.` },
      kpis: [{ label: 'U', value: num(r.u, 1), sub: `p = ${pText(r.p)}` }, { label: 'Rank-biserial r', value: num(r.rank_biserial), sub: r.effect_size }],
      tables: [groupTable(r.groups, 'Group medians')].filter(Boolean),
      methods: { en: `${r.outcome} was compared with the Mann-Whitney U test; the rank-biserial correlation is the effect size.`, ar: `قورن ${r.outcome} باختبار مان-ويتني.` },
    };
  },
  anova_full(r) {
    const names = Object.keys(r.groups || {});
    const means = names.map((n) => r.groups[n].mean).filter((v) => v !== null && v !== undefined);
    const welch = r.reported_test === 'welch_anova';
    return {
      meta: `${r.outcome} by ${r.grouping} · ${welch ? "Welch's ANOVA" : 'One-way ANOVA'} · n = ${r.n}`,
      decision: r.decision,
      headline: sigWord(r.p)
        ? { en: `${r.outcome} differed across ${r.grouping} (means ${num(Math.min(...means))} to ${num(Math.max(...means))}).`, ar: `اختلف ${r.outcome} بين مجموعات ${r.grouping}.` }
        : { en: `${r.outcome} did not differ clearly across ${r.grouping} (means ${num(Math.min(...means))} to ${num(Math.max(...means))}).`, ar: `لم يختلف ${r.outcome} بوضوح بين مجموعات ${r.grouping}.` },
      kpis: [
        { label: welch ? "Welch's F" : 'F', value: `F(${num(r.df_between, 0)}, ${num(r.df_within, welch ? 1 : 0)}) = ${num(r.f)}`, sub: `p = ${pText(r.p)}` },
        { label: 'Effect size', value: `ω² = ${num(r.omega_squared)}`, sub: `${r.effect_size} · η² = ${num(r.eta_squared ?? r.classic?.eta_squared)}` },
        r.kruskal ? { label: 'Rank-based check', value: `H = ${num(r.kruskal.h)}`, sub: `Kruskal-Wallis p = ${pText(r.kruskal.p)}` } : null,
      ].filter(Boolean),
      tables: [
        groupTable(r.groups, 'Group means'),
        pairwiseTable(r.posthoc, r.posthoc_method),
        { caption: 'Assumptions & alternatives', full: true, columns: ['Check / test', 'Result', 'Used'], rows: [
          ['Equal variances (Levene)', `p = ${pText(r.assumptions?.levene?.p)}`, r.assumptions?.levene?.equal_var_assumed ? 'Met' : 'Not met → Welch'],
          ['Classic ANOVA', `F = ${num(r.classic?.f)}, p = ${pText(r.classic?.p)}`, welch ? 'Reference' : 'Main result'],
          r.welch ? ["Welch's ANOVA", `F = ${num(r.welch.f)}, p = ${pText(r.welch.p)}`, welch ? 'Main result' : 'Reference'] : null,
          r.kruskal ? ['Kruskal-Wallis', `H = ${num(r.kruskal.h)}, p = ${pText(r.kruskal.p)}`, 'Sensitivity check'] : null,
        ].filter(Boolean) },
      ].filter(Boolean),
      notes: [r.posthoc_note].filter(Boolean),
      chart: { kind: 'dots', data: names.map((n) => ({ name: n, value: r.groups[n].mean, low: r.groups[n].ci_95?.[0], high: r.groups[n].ci_95?.[1] })) },
      methods: { en: `${r.outcome} was compared across ${r.grouping} groups with ${welch ? "Welch's ANOVA because variances differed" : 'one-way ANOVA'}, followed by ${r.posthoc_method} pairwise comparisons; ω² is the effect size and Kruskal-Wallis a sensitivity check.`,
                 ar: `قورن ${r.outcome} بين مجموعات ${r.grouping} باستخدام ${welch ? 'تحليل تباين ويلش لاختلاف التباينات' : 'تحليل التباين الأحادي'}، ثم مقارنات ${r.posthoc_method} الثنائية.` },
    };
  },
  welch_anova(r) { return builders.anova_full({ ...r, reported_test: 'welch_anova', omega_squared: null }); },
  kruskal_dunn(r) {
    return {
      meta: `${r.outcome} by ${r.grouping} · Kruskal-Wallis · n = ${r.n}`,
      headline: sigWord(r.p) ? { en: `${r.outcome} differed across groups (rank-based).`, ar: `اختلف ${r.outcome} بين المجموعات.` } : { en: `No clear difference in ${r.outcome} across groups.`, ar: `لا يوجد فرق واضح في ${r.outcome}.` },
      kpis: [{ label: `H(${Object.keys(r.groups || {}).length - 1})`, value: num(r.h), sub: `p = ${pText(r.p)}` }, { label: 'ε²', value: num(r.epsilon_squared), sub: r.effect_size }],
      tables: [groupTable(r.groups, 'Group medians'), r.posthoc?.length ? { caption: `Pairwise comparisons (${r.posthoc_method})`, full: true, columns: ['Comparison', 'z', 'Adjusted p'],
        rows: r.posthoc.map((p) => [`${p.group1} vs ${p.group2}`, num(p.z), pText(p.p_adjusted)]) } : null].filter(Boolean),
      methods: { en: `${r.outcome} was compared with the Kruskal-Wallis test and Dunn's pairwise tests (Holm-adjusted).`, ar: `قورن ${r.outcome} باختبار كروسكال-واليس ومقارنات دن الثنائية.` },
    };
  },
  paired_ttest(r) {
    return {
      meta: `${r.pre} → ${r.post} · Paired t test · n = ${r.n}`,
      headline: sigWord(r.p) ? { en: `${r.post} was ${r.mean_difference < 0 ? 'lower' : 'higher'} than ${r.pre} by ${num(Math.abs(r.mean_difference))} on average.`, ar: `تغيّر المتوسط بمقدار ${num(r.mean_difference)} بين ${r.pre} و${r.post}.` }
        : { en: `No clear change from ${r.pre} to ${r.post}.`, ar: `لا يوجد تغير واضح بين ${r.pre} و${r.post}.` },
      kpis: [{ label: 'Mean change', value: num(r.mean_difference), sub: `95% CI ${ci(r.ci_95)}` }, { label: `t(${r.df})`, value: num(r.t), sub: `p = ${pText(r.p)}` }, { label: "Hedges' g_z", value: num(r.hedges_gz), sub: r.effect_size }],
      chart: r.means ? { kind: 'line', data: [{ name: r.pre, value: r.means.pre }, { name: r.post, value: r.means.post }] } : null,
      methods: { en: `Change from ${r.pre} to ${r.post} was tested with a paired t test.`, ar: `اختُبر التغير من ${r.pre} إلى ${r.post} باختبار (ت) للعينات المترابطة.` },
    };
  },
  wilcoxon_signed_rank(r) {
    return {
      meta: `${r.pre} → ${r.post} · Wilcoxon signed-rank · n = ${r.n}`,
      headline: sigWord(r.p) ? { en: `There was a change from ${r.pre} to ${r.post} (median change ${num(r.median_change)}).`, ar: `يوجد تغير بين ${r.pre} و${r.post}.` } : { en: `No clear change from ${r.pre} to ${r.post}.`, ar: 'لا يوجد تغير واضح.' },
      kpis: [{ label: 'Median change', value: num(r.median_change), sub: '' }, { label: 'W', value: num(r.w, 1), sub: `p = ${pText(r.p)}` }, { label: 'Rank-biserial r', value: num(r.rank_biserial), sub: r.effect_size }],
      methods: { en: `Change from ${r.pre} to ${r.post} was tested with the Wilcoxon signed-rank test.`, ar: `اختُبر التغير باختبار ويلكوكسون.` },
    };
  },
  one_sample_ttest(r) {
    return {
      meta: `${r.variables[0]} vs ${r.test_value} · One-sample t test · n = ${r.n}`,
      headline: sigWord(r.p) ? { en: `The average ${r.variables[0]} (${num(r.mean)}) differs from ${r.test_value}.`, ar: `يختلف متوسط ${r.variables[0]} عن ${r.test_value}.` } : { en: `The average ${r.variables[0]} is not clearly different from ${r.test_value}.`, ar: `لا يختلف المتوسط بوضوح عن ${r.test_value}.` },
      kpis: [{ label: 'Difference', value: num(r.mean_difference), sub: `95% CI ${ci(r.ci_95)}` }, { label: `t(${r.df})`, value: num(r.t), sub: `p = ${pText(r.p)}` }, { label: "Hedges' g", value: num(r.hedges_g), sub: r.effect_size }],
      notes: r.alternative?.p != null ? [`Wilcoxon one-sample check: p = ${pText(r.alternative.p)}.`] : [],
      methods: { en: `The mean ${r.variables[0]} was compared with ${r.test_value} using a one-sample t test.`, ar: `قورن متوسط ${r.variables[0]} بالقيمة ${r.test_value}.` },
    };
  },
  pearson(r) { return builders._corr(r, 'Pearson', r.r); },
  spearman(r) { return builders._corr(r, 'Spearman', r.statistic); },
  kendall(r) { return builders._corr(r, "Kendall's τ", r.statistic); },
  _corr(r, name, value) {
    const [a, b] = r.variables || [];
    return {
      meta: `${a} and ${b} · ${name} · n = ${r.n}`,
      headline: sigWord(r.p) ? { en: `${a} and ${b} move ${value > 0 ? 'together' : 'in opposite directions'} (${r.effect_size}).`, ar: `يرتبط ${a} و${b} ${value > 0 ? 'طردياً' : 'عكسياً'}.` }
        : { en: `No clear relationship between ${a} and ${b}.`, ar: `لا توجد علاقة واضحة بين ${a} و${b}.` },
      kpis: [{ label: name === 'Pearson' ? 'r' : name === 'Spearman' ? 'ρ' : 'τ', value: num(value), sub: r.ci_95 ? `95% CI ${ci(r.ci_95)}` : r.effect_size }, { label: 'p', value: pText(r.p), sub: `n = ${r.n}` }],
      chart: r.plot_points?.length ? { kind: 'scatter', x: a, y: b, data: r.plot_points } : null,
      methods: { en: `The association between ${a} and ${b} was assessed with ${name} correlation.`, ar: `قُيّمت العلاقة بين ${a} و${b} بمعامل ارتباط ${name}.` },
    };
  },
  partial_correlation(r) {
    return { meta: `${r.variables.join(' and ')} controlling for ${r.covariates.join(', ')} · n = ${r.n}`,
      headline: { en: `Partial r = ${num(r.r)} after controlling for ${r.covariates.join(', ')}.`, ar: `r الجزئي = ${num(r.r)} بعد الضبط.` },
      kpis: [{ label: 'Partial r', value: num(r.r), sub: `95% CI ${ci(r.ci_95)}` }, { label: 'p', value: pText(r.p), sub: '' }],
      methods: { en: `A partial correlation controlling for ${r.covariates.join(', ')} was computed.`, ar: 'حُسب معامل الارتباط الجزئي.' } };
  },
  correlation_matrix(r) {
    return { meta: `${r.variables.length} variables · ${r.method} · Holm-adjusted`,
      headline: { en: `${r.pairs.filter((p) => p.p_adjusted < 0.05).length} of ${r.pairs.length} pairs are significantly correlated after adjustment.`, ar: `${r.pairs.filter((p) => p.p_adjusted < 0.05).length} من ${r.pairs.length} أزواج مرتبطة بدلالة.` },
      kpis: [], tables: [{ caption: 'Correlation matrix', columns: ['', ...r.variables], rows: r.variables.map((v) => [v, ...r.variables.map((w) => (v === w ? '1' : num(r.matrix[v][w])))]) },
        { caption: 'All pairs', full: true, columns: ['Pair', 'r', 'n', 'Adjusted p'], rows: r.pairs.map((p) => [`${p.var1} – ${p.var2}`, num(p.r), p.n, pText(p.p_adjusted)]) }],
      methods: { en: `${r.method} correlations were computed with Holm-adjusted p-values.`, ar: 'حُسبت معاملات الارتباط مع تصحيح هولم.' } };
  },
  linear_regression(r) {
    const main = r.coefficients.find((c) => c.term !== 'Intercept' && c.p !== null && c.p < 0.05);
    const robust = Boolean(r.robust_errors);
    return {
      meta: `${r.outcome} · Multiple linear regression · n = ${r.n}`,
      headline: { en: `The model explains ${num(r.r_squared * 100, 0)}% of the variation in ${r.outcome}${main ? `; ${main.term} changes it by ${num(main.b)} per unit` : ''}.`,
                  ar: `يفسر النموذج ${num(r.r_squared * 100, 0)}% من التباين في ${r.outcome}.` },
      kpis: [{ label: 'R²', value: num(r.r_squared), sub: `adjusted ${num(r.adjusted_r_squared)}` }, { label: `F(${num(r.df_model, 0)}, ${num(r.df_resid, 0)})`, value: num(r.f, 1), sub: `p = ${pText(r.p)}` },
        { label: 'RMSE', value: num(r.model_fit?.rmse), sub: `AIC ${num(r.model_fit?.aic, 1)}` }],
      tables: [
        { caption: 'Coefficients', ...coefficientTable(r.coefficients, { extra: [{ label: 'β', get: (row) => num(row.standardized_beta) }] }) },
        { caption: 'Full coefficients', full: true, columns: ['Predictor', 'B', 'SE', 't', robust ? 'Robust SE' : 'VIF', 'p'],
          rows: r.coefficients.map((c) => [c.term, num(c.b, 3), num(c.se, 3), num(c.t, 2), robust ? num(c.robust_se, 3) : num(r.vif?.find((v) => v.predictor === c.term)?.vif), pText(robust ? c.robust_p ?? c.p : c.p)]) },
        r.hierarchical ? { caption: 'Hierarchical steps', full: true, columns: ['Block', 'R²', 'ΔR²', 'F change', 'p'],
          rows: r.hierarchical.map((s) => [s.block, num(s.r_squared, 3), num(s.delta_r_squared, 3), num(s.f_change), pText(s.p_change)]) } : null,
      ].filter(Boolean),
      checks: [...assumptionChecks(r.assumptions),
        r.residual_diagnostics?.breusch_pagan ? { name: 'Equal spread of residuals (Breusch-Pagan)', ok: r.residual_diagnostics.breusch_pagan.passed, detail: `p = ${pText(r.residual_diagnostics.breusch_pagan.p)}` } : null,
        r.residual_diagnostics ? { name: 'Independent errors (Durbin-Watson)', ok: r.residual_diagnostics.durbin_watson > 1.5 && r.residual_diagnostics.durbin_watson < 2.5, detail: `DW = ${num(r.residual_diagnostics.durbin_watson)}` } : null,
        r.residual_diagnostics?.influential_cases ? { name: "Influential points (Cook's distance)", ok: true, detail: `${r.residual_diagnostics.influential_cases.n} above 4/n` } : null,
      ].filter(Boolean),
      notes: r.notes || [],
      chart: { kind: 'forest', unit: r.outcome, ref: 0, data: r.coefficients.filter((c) => c.term !== 'Intercept').map((c) => ({ name: c.term, value: c.b, low: c.ci_95[0], high: c.ci_95[1] })) },
      residuals: r.residual_diagnostics?.residual_points,
      methods: { en: `${r.outcome} was modelled with multiple linear regression${robust ? ' with HC3 robust standard errors' : ''}; residual normality, equal spread, independence, multicollinearity (VIF) and influential points were checked.`,
                 ar: `نُمذج ${r.outcome} بالانحدار الخطي المتعدد مع فحص البواقي والتعدد الخطي والنقاط المؤثرة.` },
    };
  },
  logistic_regression(r) {
    const fit = r.model_fit || {};
    return {
      meta: `${r.outcome} (${r.outcome_event} vs ${r.outcome_reference}) · Binary logistic regression · n = ${r.n} · ${r.events} events`,
      headline: sigWord(r.p) ? { en: `The predictors together are associated with ${r.outcome} = ${r.outcome_event}.`, ar: `ترتبط المتنبئات مجتمعة بـ ${r.outcome} = ${r.outcome_event}.` }
        : { en: `The predictors did not clearly predict ${r.outcome} = ${r.outcome_event}.`, ar: `لم تتنبأ المتنبئات بوضوح بـ ${r.outcome}.` },
      kpis: [{ label: `χ²(${num(r.df_model, 0)})`, value: num(r.chi2), sub: `p = ${pText(r.p)}` }, { label: 'Pseudo R²', value: num(r.pseudo_r_squared), sub: 'McFadden' },
        fit.auc != null ? { label: 'AUC', value: num(fit.auc), sub: `95% CI ${ci(fit.auc_ci_95)}` } : null].filter(Boolean),
      tables: [{ caption: 'Odds ratios', ...coefficientTable(r.coefficients, { estimate: 'odds_ratio', estimateLabel: 'OR', ciKey: 'or_ci_95' }) },
        { caption: 'Full coefficients', full: true, columns: ['Predictor', 'B (log-odds)', 'SE', 'z', 'VIF', 'p'],
          rows: r.coefficients.map((c) => [c.term, num(c.b, 3), num(c.se, 3), num(c.z, 2), num(r.vif?.find((v) => v.predictor === c.term)?.vif), pText(c.p)]) }],
      checks: assumptionChecks(r.assumptions),
      chart: { kind: 'forest', log: true, ref: 1, data: r.coefficients.filter((c) => c.term !== 'Intercept').map((c) => ({ name: c.term, value: c.odds_ratio, low: c.or_ci_95[0], high: c.or_ci_95[1] })) },
      methods: { en: `${r.outcome} (${r.outcome_event} = event) was modelled with binary logistic regression; odds ratios with 95% CIs, discrimination (AUC) and calibration (Hosmer-Lemeshow) are reported.`,
                 ar: `نُمذج ${r.outcome} (${r.outcome_event} = حدث) بالانحدار اللوجستي الثنائي مع عرض نسب الأرجحية.` },
    };
  },
  multinomial_logistic(r) {
    return { meta: `${r.outcome} (reference ${r.outcome_reference}) · n = ${r.n}`, headline: { en: `Model test p = ${pText(r.p)}.`, ar: `p = ${pText(r.p)}.` },
      kpis: [{ label: 'χ²', value: num(r.chi2), sub: `p = ${pText(r.p)}` }, { label: 'Pseudo R²', value: num(r.pseudo_r_squared), sub: 'McFadden' }],
      tables: r.equations.map((eq) => ({ caption: `${eq.category} vs ${r.outcome_reference} (relative risk ratios)`, ...coefficientTable(eq.coefficients, { estimate: 'rrr', estimateLabel: 'RRR', ciKey: 'rrr_ci_95' }) })),
      methods: { en: `${r.outcome} was modelled with multinomial logistic regression (reference ${r.outcome_reference}).`, ar: 'استُخدم الانحدار اللوجستي متعدد الحدود.' } };
  },
  ordinal_logistic(r) {
    return { meta: `${r.outcome} (${r.levels.join(' < ')}) · n = ${r.n}`, headline: { en: 'Odds ratios above 1 mean higher categories are more likely.', ar: 'نسب الأرجحية الأكبر من 1 تعني فئات أعلى.' },
      kpis: [{ label: 'AIC', value: num(r.model_fit?.aic, 1), sub: '' }],
      tables: [{ caption: 'Odds ratios (proportional odds)', ...coefficientTable(r.coefficients, { estimate: 'odds_ratio', estimateLabel: 'OR', ciKey: 'odds_ratio_ci_95' }) }],
      methods: { en: `${r.outcome} was modelled with ordinal (proportional-odds) logistic regression.`, ar: 'استُخدم الانحدار اللوجستي الترتيبي.' } };
  },
  count_regression(r) {
    return { meta: `${r.outcome} · ${r.family.replace('_', ' ')} regression · n = ${r.n}`, headline: { en: 'Incidence-rate ratios above 1 mean higher counts.', ar: 'نسب المعدلات الأكبر من 1 تعني أعداداً أعلى.' },
      kpis: [{ label: 'Dispersion', value: num(r.dispersion), sub: r.family.replace('_', ' ') }],
      tables: [{ caption: 'Incidence-rate ratios', ...coefficientTable(r.coefficients, { estimate: 'irr', estimateLabel: 'IRR', ciKey: 'irr_ci_95' }) }],
      checks: (r.checks || []).map((c) => ({ name: c.name, ok: c.passed, detail: c.detail })),
      methods: { en: `${r.outcome} was modelled with ${r.family.replace('_', ' ')} regression.`, ar: 'استُخدم انحدار الأعداد.' } };
  },
  factorial_anova(r) {
    return { meta: `${r.outcome} by ${r.factors.join(' × ')}${r.covariates?.length ? ` adjusting for ${r.covariates.join(', ')}` : ''} · n = ${r.n}`,
      headline: (() => {
        const significant = r.effects.filter((e) => e.p !== null && e.p < 0.05).map((e) => e.source);
        if (!significant.length) return { en: 'None of the effects was statistically significant.', ar: 'لم يكن أي من الآثار دالاً إحصائياً.' };
        return { en: `Statistically significant: ${significant.join(', ')}.`, ar: `آثار دالة إحصائياً: ${significant.join('، ')}.` };
      })(),
      kpis: r.effects.slice(0, 3).map((e) => ({ label: e.source, value: `F = ${num(e.f)}`, sub: `p = ${pText(e.p)} · ηp² = ${num(e.partial_eta_squared)}` })),
      tables: [{ caption: 'Effects', columns: ['Source', 'df', 'F', 'p', 'ηp²'], rows: r.effects.map((e) => [e.source, num(e.df, 0), num(e.f), pText(e.p), num(e.partial_eta_squared, 3)]) },
        r.adjusted_means ? { caption: 'Adjusted means', columns: ['Group', 'Adjusted mean'], rows: r.adjusted_means.map((a) => [a.group, num(a.adjusted_mean)]) } : null,
        { caption: 'Cell means', full: true, columns: [...r.factors, 'n', 'Mean', 'SD'], rows: r.cell_means.map((c) => [...r.factors.map((f) => c[f]), c.n, num(c.mean), num(c.sd)]) }].filter(Boolean),
      checks: assumptionChecks(r.assumptions),
      methods: { en: r.covariates?.length ? `${r.outcome} was compared between ${r.factors[0]} groups with ANCOVA adjusting for ${r.covariates.join(', ')}.` : `${r.outcome} was analysed with a ${r.factors.length}-way ANOVA (type II sums of squares).`,
                 ar: 'استُخدم تحليل التباين العاملي.' } };
  },
  ancova(r) { return builders.factorial_anova(r); },
  repeated_measures_anova(r) {
    return { meta: `${r.measures.join(' → ')}${r.between ? ` by ${r.between}` : ''} · n = ${r.n}`,
      headline: sigWord(r.p) ? { en: 'The measurements changed over time.', ar: 'تغيرت القياسات عبر الزمن.' } : { en: 'No clear change over time.', ar: 'لا يوجد تغير واضح عبر الزمن.' },
      kpis: r.effects.map((e) => ({ label: e.source, value: `F(${num(e.df1, 0)}, ${num(e.df2, 0)}) = ${num(e.f)}`, sub: `p = ${pText(e.p_greenhouse_geisser ?? e.p)}` })),
      tables: [{ caption: 'Means over time', columns: ['Time', 'n', 'Mean', 'SD'], rows: r.time_means.map((t) => [t.time, t.n, num(t.mean), num(t.sd)]) },
        pairwiseTable(r.posthoc?.map((p) => ({ ...p, mean_difference: p.statistic })), r.posthoc_method)].filter(Boolean),
      notes: [r.sphericity_corrected ? 'Sphericity was not supported, so the Greenhouse-Geisser correction was applied.' : null, r.friedman ? `Friedman check: p = ${pText(r.friedman.p)}.` : null].filter(Boolean),
      chart: { kind: 'line', data: r.time_means.map((t) => ({ name: t.time, value: t.mean })) },
      methods: { en: `Change across ${r.measures.join(', ')} was analysed with ${r.between ? 'a mixed' : 'a repeated-measures'} ANOVA (Mauchly's test; Greenhouse-Geisser when needed) and Holm-adjusted paired comparisons.`, ar: 'استُخدم تحليل التباين للقياسات المتكررة.' } };
  },
  mixed_anova(r) { return builders.repeated_measures_anova(r); },
  reliability(r) {
    return {
      meta: `${r.k} items · Cronbach's alpha · n = ${r.n}`,
      headline: { en: `${r.interpretation.split(' (')[0].replace(/^./, (c) => c.toUpperCase())} internal consistency (α = ${num(r.alpha)}).`, ar: `اتساق داخلي (α = ${num(r.alpha)}).` },
      alert: r.suspected_reverse_items?.length ? { kind: 'reverse', items: r.suspected_reverse_items } : null,
      kpis: [{ label: "Cronbach's α", value: num(r.alpha), sub: `95% CI ${ci(r.alpha_ci_95)}` }, { label: "McDonald's ω", value: num(r.omega), sub: 'one factor' },
        { label: 'Split-half', value: num(r.split_half), sub: 'Spearman-Brown' }],
      tables: [{ caption: 'Items', columns: ['Item', 'Mean', 'SD', 'Item–total r', 'α if deleted'], rows: r.item_statistics.map((i) => [i.item, num(i.mean), num(i.sd), num(i.item_total_r), num(i.alpha_if_deleted)]) },
        { caption: 'More reliability statistics', full: true, columns: ['Statistic', 'Value'], rows: [['Mean inter-item r', num(r.mean_inter_item_r)], ['First eigenvalue', num(r.first_eigenvalue)],
          ['Variance on first factor', pct(r.first_factor_share, 0)], ['One dimension?', r.unidimensional ? 'Yes' : 'Check factor structure']] }],
      notes: r.notes || [],
      methods: { en: `Internal consistency of the ${r.k}-item scale was assessed with Cronbach's α and McDonald's ω${r.reverse_items?.length ? ` after reverse-scoring ${r.reverse_items.join(', ')}` : ''}.`,
                 ar: `قُيّم الاتساق الداخلي للمقياس بمعامل ألفا كرونباخ وأوميغا ماكدونالد.` },
    };
  },
  cohens_kappa(r) {
    return { meta: `${r.variables.join(' vs ')} · n = ${r.n}`, headline: { en: `Agreement was ${r.agreement} (κ = ${num(r.kappa)}).`, ar: `الاتفاق (κ = ${num(r.kappa)}).` },
      kpis: [{ label: "Cohen's κ", value: num(r.kappa), sub: `95% CI ${ci(r.ci_95)}` }, { label: 'Observed agreement', value: pct(r.observed_agreement, 0), sub: '' }],
      methods: { en: `Agreement between ${r.variables.join(' and ')} was measured with Cohen's κ.`, ar: 'قيس الاتفاق بمعامل كابا كوهين.' } };
  },
  fleiss_kappa(r) {
    return { meta: `${r.variables.length} raters · n = ${r.n}`, headline: { en: `Fleiss' κ = ${num(r.kappa)}.`, ar: `κ = ${num(r.kappa)}.` }, kpis: [{ label: "Fleiss' κ", value: num(r.kappa), sub: '' }],
      methods: { en: "Agreement among raters was measured with Fleiss' κ.", ar: 'قيس الاتفاق بمعامل كابا فلايس.' } };
  },
  icc(r) {
    return { meta: `${r.variables.length} rating columns · n = ${r.n}`, headline: { en: `ICC = ${num(r.icc)} (two-way random, absolute agreement).`, ar: `ICC = ${num(r.icc)}.` },
      kpis: [{ label: 'ICC(A,1)', value: num(r.icc), sub: `95% CI ${ci(r.ci_95)}` }],
      tables: [{ caption: 'All ICC forms', full: true, columns: ['Type', 'Description', 'ICC', '95% CI'], rows: r.icc_table.map((i) => [i.type, i.description, num(i.icc), ci(i.ci_95)]) }],
      methods: { en: 'Inter-rater reliability was assessed with the intraclass correlation (two-way random effects, absolute agreement).', ar: 'قُيّمت الموثوقية بمعامل الارتباط داخل الفئة.' } };
  },
  diagnostic_accuracy(r) {
    const s = (k) => `${pct(r[k].value)} (${pct(r[k].ci_95[0])}–${pct(r[k].ci_95[1])})`;
    return {
      meta: `${r.variables[0]} against ${r.variables[1]} · n = ${r.n}`,
      headline: { en: `Sensitivity ${pct(r.sensitivity.value)}, specificity ${pct(r.specificity.value)}.`, ar: `الحساسية ${pct(r.sensitivity.value)}، النوعية ${pct(r.specificity.value)}.` },
      kpis: [{ label: 'Sensitivity', value: pct(r.sensitivity.value), sub: `95% CI ${pct(r.sensitivity.ci_95[0])}–${pct(r.sensitivity.ci_95[1])}` },
        { label: 'Specificity', value: pct(r.specificity.value), sub: `95% CI ${pct(r.specificity.ci_95[0])}–${pct(r.specificity.ci_95[1])}` },
        { label: 'LR+ / LR−', value: `${num(r.lr_positive)} / ${num(r.lr_negative)}`, sub: '' },
        r.roc ? { label: 'AUC', value: num(r.roc.auc), sub: `95% CI ${ci(r.roc.auc_ci_95)}` } : null].filter(Boolean),
      tables: [{ caption: `${r.variables[0]} vs ${r.variables[1]}`, columns: ['', `Reference ${r.positive_reference}`, 'Reference other'],
        rows: [[`Test ${r.positive_test}`, r.table.true_positive, r.table.false_positive], ['Test other', r.table.false_negative, r.table.true_negative]] },
        { caption: 'Accuracy measures', columns: ['Measure', 'Value (95% CI)'], rows: [['Sensitivity', s('sensitivity')], ['Specificity', s('specificity')], ['PPV', s('ppv')], ['NPV', s('npv')], ['Accuracy', s('accuracy')], ['Prevalence', s('prevalence')]] },
        r.roc ? { caption: 'Best cut-off (Youden)', full: true, columns: ['Cut-off', 'Youden J', 'Direction'], rows: [[num(r.roc.optimal_cutoff), num(r.roc.youden_j), r.roc.direction]] } : null].filter(Boolean),
      notes: r.notes || [],
      chart: r.roc ? { kind: 'roc', data: r.roc.points } : null,
      methods: { en: `Accuracy of ${r.variables[0]} against ${r.variables[1]} was summarised as sensitivity, specificity, predictive values and likelihood ratios with Wilson 95% CIs${r.roc ? ', and the ROC curve with AUC (Hanley-McNeil CI)' : ''}.`,
                 ar: 'لُخّصت الدقة التشخيصية بالحساسية والنوعية والقيم التنبؤية.' },
    };
  },
  table_one(r) {
    const groups = r.groups || [];
    const rows = [];
    r.rows.forEach((row) => {
      if (row.kind === 'continuous') {
        rows.push([`${row.variable}, ${row.statistic}`, ...(groups.length ? groups.map((g) => row.by_group?.[g] ?? '—') : [row.overall]), ...(groups.length ? [pText(row.p), num(row.smd)] : [])]);
      } else {
        rows.push([`${row.variable}, n (%)`, ...(groups.length ? groups.map(() => '') : ['']), ...(groups.length ? [pText(row.p), num(row.smd)] : [])]);
        row.levels.forEach((level) => rows.push([`   ${level.level}`, ...(groups.length ? groups.map((g) => level.by_group?.[g] ?? '—') : [level.overall]), ...(groups.length ? ['', ''] : [])]));
      }
    });
    return {
      meta: `${r.grouping ? `By ${r.grouping} · ` : ''}N = ${r.n}`,
      headline: { en: r.grouping ? `Characteristics of ${r.n} participants by ${r.grouping}.` : `Characteristics of ${r.n} participants.`, ar: `خصائص ${r.n} مشاركاً.` },
      kpis: groups.map((g) => ({ label: g, value: `n = ${r.group_n[g]}`, sub: '' })),
      tables: [{ caption: `Table 1. Characteristics${r.grouping ? ` by ${r.grouping}` : ''}`, columns: ['Characteristic', ...(groups.length ? groups.map((g) => `${g} (n = ${r.group_n[g]})`) : ['Overall']), ...(groups.length ? ['p', 'SMD'] : [])], rows, note: r.notes?.[0] }],
      methods: { en: 'Continuous variables are summarised as mean (SD) or median [IQR] when skewed, and categorical variables as n (%); groups were compared with t / ANOVA or Mann-Whitney / Kruskal-Wallis, and chi-square or Fisher tests.',
                 ar: 'لُخّصت المتغيرات المستمرة بالمتوسط (الانحراف المعياري) أو الوسيط، والفئوية بالعدد (النسبة).' },
    };
  },
  descriptive(r) {
    const items = r.results || [];
    return { meta: `${items.length} variables · ${r.data_quality?.rows ?? ''} rows`, headline: { en: 'Summary of every variable.', ar: 'ملخص كل متغير.' }, kpis: [],
      tables: [{ caption: 'Descriptive statistics', columns: ['Variable', 'Valid n', 'Missing', 'Summary'], rows: items.map((i) => [i.variable, i.n ?? i.valid_n ?? '—', `${i.missing_pct ?? 0}%`,
        i.type === 'numeric' || i.mean !== undefined ? `M = ${num(i.mean)}, SD = ${num(i.sd)}; Mdn = ${num(i.median)}` : (i.top_category ? `Most common: ${i.top_category}` : '—')]) }],
      methods: { en: 'Descriptive statistics were computed for every variable.', ar: 'حُسب الإحصاء الوصفي لكل متغير.' } };
  },
  goodness_of_fit(r) {
    return { meta: `${r.variables[0]} · n = ${r.n}`, headline: sigWord(r.p) ? { en: 'The categories differ from the expected distribution.', ar: 'تختلف الفئات عن التوزيع المتوقع.' } : { en: 'The categories match the expected distribution.', ar: 'تتطابق الفئات مع التوزيع المتوقع.' },
      kpis: [{ label: `χ²(${r.dof})`, value: num(r.chi2), sub: `p = ${pText(r.p)}` }, { label: "Cohen's w", value: num(r.cohens_w), sub: r.effect_size }],
      tables: [{ caption: 'Observed vs expected', columns: ['Category', 'Observed', 'Expected'], rows: r.categories.map((c) => [c.category, c.observed, num(c.expected, 1)]) }],
      methods: { en: 'A chi-square goodness-of-fit test was used.', ar: 'استُخدم اختبار جودة المطابقة.' } };
  },
  mcnemar(r) {
    return { meta: `${r.pre} → ${r.post} · n = ${r.n}`, headline: sigWord(r.p) ? { en: 'The proportion changed between the two measurements.', ar: 'تغيّرت النسبة بين القياسين.' } : { en: 'No clear change in the proportion.', ar: 'لا يوجد تغير واضح في النسبة.' },
      kpis: [{ label: 'Changed category', value: r.discordant_pairs, sub: '' }, { label: 'p', value: pText(r.p), sub: r.method }],
      methods: { en: 'Paired proportions were compared with the McNemar test.', ar: 'قورنت النسب المترابطة باختبار ماكنمار.' } };
  },
};
builders.kruskal_wallis = builders.kruskal_dunn;
builders.anova = builders.anova_full;
builders.cronbach_alpha = builders.reliability;

export function describeResult(result) {
  if (!result || result.error) return null;
  const builder = builders[result.test];
  const model = builder ? builder(result) : { meta: '', headline: { en: '', ar: '' }, kpis: [] };
  return {
    title: methodLabel(result),
    tables: [], checks: [], notes: [], chart: null,
    ...model,
    text: { en: result.apa_en || '', ar: result.apa_ar || '' },
  };
}
