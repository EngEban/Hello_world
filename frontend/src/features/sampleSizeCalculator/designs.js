/**
 * Sample size studio: plain-language aims → designs, the inputs each design needs, defaults,
 * interface text (English / Arabic), the SD helper maths and workspace storage.
 * Calculations themselves run on the server (/api/sample-size/), which uses the same exact t and F
 * methods as G*Power.
 */

export const TOOL_KEY = 'sample-size-calculator';
export const STORAGE_KEY = 'resref_sample_size_workspace_v3';

/** "What are you planning?" → outcome choices → design id. */
export const AIMS = [
  { id: 'estimate', en: 'Estimate a rate or mean', ar: 'تقدير نسبة أو متوسط', options: [
    { design: 'single_proportion', en: 'Yes / no (a rate)', ar: 'نعم / لا (نسبة)' },
    { design: 'single_mean', en: 'A number (a mean)', ar: 'رقم (متوسط)' },
  ] },
  { id: 'compare', en: 'Compare groups', ar: 'مقارنة مجموعات', options: [
    { design: 'two_proportions', en: 'Yes / no', ar: 'نعم / لا' },
    { design: 'two_means', en: 'A number', ar: 'رقم' },
    { design: 'logrank', en: 'Time to event', ar: 'الزمن حتى الحدث' },
    { design: 'anova', en: 'A number, 3+ groups', ar: 'رقم، 3 مجموعات أو أكثر' },
    { design: 'noninferiority', en: 'Show “not worse”', ar: 'إثبات «ليس أسوأ»' },
  ] },
  { id: 'relate', en: 'Relationship', ar: 'العلاقة', options: [
    { design: 'correlation', en: 'Two numbers (correlation)', ar: 'رقمان (ارتباط)' },
    { design: 'regression', en: 'Several predictors (regression)', ar: 'عدة متنبئات (انحدار)' },
    { design: 'logistic', en: 'Yes / no outcome (logistic)', ar: 'نتيجة نعم / لا (لوجستي)' },
  ] },
  { id: 'change', en: 'Before–after', ar: 'قبل وبعد', options: [
    { design: 'paired_means', en: 'A number', ar: 'رقم' },
    { design: 'mcnemar', en: 'Yes / no', ar: 'نعم / لا' },
  ] },
  { id: 'diagnostic', en: 'Diagnostic test', ar: 'اختبار تشخيصي', options: [
    { design: 'diagnostic', en: 'Sensitivity & specificity', ar: 'الحساسية والنوعية' },
    { design: 'auc', en: 'ROC / AUC', ar: 'منحنى ROC' },
  ] },
  { id: 'predict', en: 'Prediction model', ar: 'نموذج تنبؤي', options: [{ design: 'prediction', en: 'Yes / no outcome', ar: 'نتيجة نعم / لا' }] },
  { id: 'pilot', en: 'Pilot study', ar: 'دراسة تجريبية', options: [{ design: 'pilot', en: 'Feasibility / pilot trial', ar: 'دراسة جدوى' }] },
];

export const DESIGN_TO_AIM = Object.fromEntries(AIMS.flatMap((aim) => aim.options.map((option) => [option.design, aim.id])));

/** Field definitions. kind: number | percent | select | text. */
export const FIELDS = {
  proportion: { kind: 'percent', en: 'Expected proportion', ar: 'النسبة المتوقعة', help: { en: 'Use 50% if unknown — it gives the largest sample.', ar: 'استخدم 50% إذا لم تكن معروفة.' } },
  margin_pct: { key: 'margin', kind: 'percent', en: 'Margin of error (±)', ar: 'هامش الخطأ (±)', help: { en: 'Half the width of the confidence interval.', ar: 'نصف عرض فترة الثقة.' } },
  margin_num: { key: 'margin', kind: 'number', en: 'Margin of error (±)', ar: 'هامش الخطأ (±)', unit: true, help: { en: 'In the same unit as the outcome.', ar: 'بنفس وحدة القياس.' } },
  sd: { kind: 'number', en: 'Standard deviation', ar: 'الانحراف المعياري', unit: true, helper: 'sd' },
  difference: { kind: 'number', en: 'Difference to detect', ar: 'الفرق المراد اكتشافه', unit: true, help: { en: 'The smallest difference that matters to patients.', ar: 'أصغر فرق له أهمية سريرية.' } },
  change: { key: 'difference', kind: 'number', en: 'Mean change to detect', ar: 'التغير المراد اكتشافه', unit: true },
  sd_diff: { kind: 'number', en: 'SD of the before–after differences', ar: 'الانحراف المعياري للفروق', unit: true, helper: 'sd' },
  p1: { kind: 'percent', en: 'Proportion in the control / reference group', ar: 'النسبة في المجموعة الضابطة' },
  p2: { kind: 'percent', en: 'Proportion in the comparison group', ar: 'النسبة في المجموعة المقارنة' },
  groups: { kind: 'number', en: 'Number of groups', ar: 'عدد المجموعات', step: 1 },
  f: { kind: 'number', en: 'Effect size f', ar: 'حجم الأثر f', presets: [[0.1, 'small'], [0.25, 'medium'], [0.4, 'large']] },
  p10: { kind: 'percent', en: 'Change from no to yes', ar: 'التغير من لا إلى نعم' },
  p01: { kind: 'percent', en: 'Change from yes to no', ar: 'التغير من نعم إلى لا' },
  r: { kind: 'number', en: 'Correlation to detect (r)', ar: 'معامل الارتباط (r)', presets: [[0.1, 'small'], [0.3, 'medium'], [0.5, 'large']] },
  f2: { kind: 'number', en: 'Effect size f²', ar: 'حجم الأثر f²', presets: [[0.02, 'small'], [0.15, 'medium'], [0.35, 'large']] },
  tested_predictors: { kind: 'number', en: 'Predictors being tested', ar: 'المتنبئات المختبرة', step: 1 },
  total_predictors: { kind: 'number', en: 'Total predictors in the model', ar: 'إجمالي المتنبئات', step: 1 },
  odds_ratio: { kind: 'number', en: 'Odds ratio to detect', ar: 'نسبة الأرجحية' },
  event_rate: { kind: 'percent', en: 'Overall event rate', ar: 'معدل الحدث الكلي' },
  predictor_type: { kind: 'select', en: 'The predictor is', ar: 'المتنبئ', options: [['continuous', { en: 'A number (OR per 1 SD)', ar: 'رقم' }], ['binary', { en: 'Yes / no', ar: 'نعم / لا' }]] },
  predictor_prevalence: { kind: 'percent', en: 'Share with the predictor', ar: 'نسبة من لديهم المتنبئ', when: { predictor_type: 'binary' } },
  hazard_ratio: { kind: 'number', en: 'Hazard ratio to detect', ar: 'نسبة الخطر' },
  event_probability: { kind: 'percent', en: 'Share who will have the event during follow-up', ar: 'نسبة من سيحدث لهم الحدث' },
  hypothesis: { kind: 'select', en: 'Aim', ar: 'الهدف', options: [['noninferiority', { en: 'Non-inferiority (not worse)', ar: 'عدم الأدنوية' }], ['equivalence', { en: 'Equivalence', ar: 'التكافؤ' }]] },
  outcome: { kind: 'select', en: 'Outcome', ar: 'النتيجة', options: [['mean', { en: 'A number', ar: 'رقم' }], ['proportion', { en: 'Yes / no (percentage points)', ar: 'نعم / لا' }]] },
  margin: { kind: 'number', en: 'Non-inferiority margin', ar: 'هامش عدم الأدنوية', unit: true },
  true_difference: { kind: 'number', en: 'Expected true difference (new − standard)', ar: 'الفرق الحقيقي المتوقع', unit: true },
  p_control: { kind: 'percent', en: 'Proportion with the standard treatment', ar: 'النسبة مع العلاج القياسي', when: { outcome: 'proportion' } },
  sd_ni: { key: 'sd', kind: 'number', en: 'Standard deviation', ar: 'الانحراف المعياري', unit: true, helper: 'sd', when: { outcome: 'mean' } },
  sensitivity: { kind: 'percent', en: 'Expected sensitivity', ar: 'الحساسية المتوقعة' },
  specificity: { kind: 'percent', en: 'Expected specificity', ar: 'النوعية المتوقعة' },
  prevalence: { kind: 'percent', en: 'Prevalence in the study population', ar: 'الانتشار في مجتمع الدراسة' },
  auc: { kind: 'number', en: 'Expected AUC', ar: 'المساحة المتوقعة تحت المنحنى' },
  parameters: { kind: 'number', en: 'Candidate predictor parameters', ar: 'عدد معاملات المتنبئات', step: 1, help: { en: 'Count every coefficient (a 3-category predictor counts as 2).', ar: 'احسب كل معامل.' } },
  outcome_prevalence: { key: 'prevalence', kind: 'percent', en: 'Outcome prevalence', ar: 'انتشار النتيجة' },
  pilot_rule: { kind: 'select', en: 'Planned main-trial effect', ar: 'الأثر المتوقع في الدراسة الرئيسية', options: [
    ['extra_small', { en: 'Very small (d ≈ 0.1) — 75 per arm', ar: 'صغير جداً — 75 لكل ذراع' }], ['small', { en: 'Small (d ≈ 0.2) — 25 per arm', ar: 'صغير — 25' }],
    ['medium', { en: 'Medium (d ≈ 0.5) — 15 per arm', ar: 'متوسط — 15' }], ['large', { en: 'Large (d ≈ 0.8) — 10 per arm', ar: 'كبير — 10' }], ['julious', { en: 'Julious rule — 12 per arm', ar: 'قاعدة جوليوس — 12' }]] },
  arms: { kind: 'number', en: 'Number of arms', ar: 'عدد الأذرع', step: 1 },
  // Shared
  confidence: { kind: 'select', en: 'Confidence level', ar: 'مستوى الثقة', options: [['90', { en: '90%', ar: '90%' }], ['95', { en: '95%', ar: '95%' }], ['99', { en: '99%', ar: '99%' }]] },
  significance: { kind: 'select', en: 'Significance level', ar: 'مستوى الدلالة', options: [['0.05|2', { en: '0.05 (two-sided)', ar: '0.05 (ثنائي الطرف)' }], ['0.05|1', { en: '0.05 (one-sided)', ar: '0.05 (أحادي الطرف)' }], ['0.01|2', { en: '0.01 (two-sided)', ar: '0.01 (ثنائي الطرف)' }], ['0.025|1', { en: '0.025 (one-sided)', ar: '0.025 (أحادي الطرف)' }]] },
  power: { kind: 'select', en: 'Power', ar: 'القوة الإحصائية', options: [['80', { en: '80%', ar: '80%' }], ['85', { en: '85%', ar: '85%' }], ['90', { en: '90%', ar: '90%' }], ['95', { en: '95%', ar: '95%' }]] },
  dropout: { kind: 'percent', en: 'Expected dropout', ar: 'نسبة الانسحاب المتوقعة' },
  n_available: { kind: 'number', en: 'Participants you can recruit', ar: 'عدد المشاركين المتاح', step: 1 },
  ratio: { kind: 'number', en: 'Allocation ratio (group 2 : group 1)', ar: 'نسبة التوزيع', help: { en: '1 = equal groups; 2 = twice as many in group 2.', ar: '1 = مجموعات متساوية.' } },
  icc: { kind: 'number', en: 'Cluster ICC', ar: 'معامل الارتباط داخل العنقود' },
  cluster_size: { kind: 'number', en: 'Average cluster size', ar: 'متوسط حجم العنقود', step: 1 },
  design_effect: { kind: 'number', en: 'Design effect', ar: 'تأثير التصميم' },
  population: { kind: 'number', en: 'Population size (optional)', ar: 'حجم المجتمع (اختياري)', step: 1 },
  continuity: { kind: 'select', en: 'Continuity correction', ar: 'تصحيح الاستمرارية', options: [['', { en: 'No', ar: 'لا' }], ['1', { en: 'Yes', ar: 'نعم' }]] },
  baseline_correlation: { kind: 'number', en: 'Correlation with baseline (ANCOVA, optional)', ar: 'الارتباط مع القياس القبلي (اختياري)' },
  pre_post_correlation: { kind: 'number', en: 'Before–after correlation', ar: 'الارتباط قبل/بعد' },
  r2_other: { kind: 'number', en: 'R² with other predictors (optional)', ar: 'R² مع المتنبئات الأخرى' },
  auc_null: { kind: 'number', en: 'AUC under the null', ar: 'AUC في الفرضية الصفرية' },
  r2_cs: { kind: 'number', en: 'Anticipated Cox-Snell R² (optional)', ar: 'R² المتوقع (اختياري)' },
  unit: { kind: 'text', en: 'Unit (for the write-up)', ar: 'وحدة القياس', placeholder: 'e.g. mmHg' },
};

/** Per design: main inputs, advanced inputs and starting values. */
export const DESIGN_FORMS = {
  single_proportion: { main: ['proportion', 'margin_pct', 'confidence'], advanced: ['population', 'design_effect', 'dropout'], defaults: { proportion: 50, margin: 5, confidence: '95', dropout: 10 } },
  single_mean: { main: ['sd', 'margin_num', 'confidence'], advanced: ['population', 'design_effect', 'unit', 'dropout'], defaults: { sd: 10, margin: 2, confidence: '95', dropout: 10 } },
  two_proportions: { main: ['p1', 'p2'], advanced: ['ratio', 'continuity', 'icc', 'cluster_size'], defaults: { p1: 40, p2: 55, dropout: 10 } },
  two_means: { main: ['difference', 'sd'], advanced: ['unit', 'ratio', 'baseline_correlation', 'icc', 'cluster_size'], defaults: { difference: 5, sd: 12, unit: 'mmHg', dropout: 10 } },
  anova: { main: ['groups', 'f'], advanced: [], defaults: { groups: 3, f: 0.25, dropout: 10 } },
  logrank: { main: ['hazard_ratio', 'event_probability'], advanced: ['ratio'], defaults: { hazard_ratio: 0.7, event_probability: 50, dropout: 10 } },
  noninferiority: { main: ['hypothesis', 'outcome', 'margin', 'true_difference', 'sd_ni', 'p_control'], advanced: ['unit', 'ratio'], defaults: { hypothesis: 'noninferiority', outcome: 'mean', margin: 5, true_difference: 0, sd: 12, p_control: 80, significance: '0.025|1', dropout: 10 } },
  paired_means: { main: ['change', 'sd_diff'], advanced: ['unit'], defaults: { difference: 5, sd_diff: 10, dropout: 10 } },
  mcnemar: { main: ['p10', 'p01'], advanced: [], defaults: { p10: 20, p01: 10, dropout: 10 } },
  correlation: { main: ['r'], advanced: [], defaults: { r: 0.3, dropout: 10 } },
  regression: { main: ['f2', 'tested_predictors', 'total_predictors'], advanced: [], defaults: { f2: 0.15, tested_predictors: 1, total_predictors: 5, dropout: 10 } },
  logistic: { main: ['odds_ratio', 'event_rate', 'predictor_type', 'predictor_prevalence'], advanced: ['r2_other'], defaults: { odds_ratio: 1.5, event_rate: 20, predictor_type: 'continuous', predictor_prevalence: 50, dropout: 10 } },
  diagnostic: { main: ['sensitivity', 'specificity', 'prevalence', 'margin_pct', 'confidence'], advanced: ['dropout'], defaults: { sensitivity: 85, specificity: 90, prevalence: 20, margin: 5, confidence: '95', dropout: 10 } },
  auc: { main: ['auc'], advanced: ['ratio', 'auc_null'], defaults: { auc: 0.75, auc_null: 0.5, dropout: 10 } },
  prediction: { main: ['parameters', 'outcome_prevalence'], advanced: ['r2_cs', 'dropout'], defaults: { parameters: 10, prevalence: 20, dropout: 10 } },
  pilot: { main: ['pilot_rule', 'arms'], advanced: ['dropout'], defaults: { pilot_rule: 'medium', arms: 2, dropout: 10 } },
};

export const MODE_LABELS = {
  n: { en: 'Sample size', ar: 'حجم العينة' },
  power: { en: 'Power', ar: 'القوة' },
  mde: { en: 'Detectable effect', ar: 'الأثر القابل للاكتشاف' },
  precision: { en: 'Precision', ar: 'الدقة' },
};

export const TEXT = {
  en: {
    brand: 'Sample Size', allDesigns: 'All designs', planning: 'What are you planning?', outcome: 'The main outcome is', method: 'Method',
    assumptions: 'Your assumptions', calculate: 'Calculate', advanced: 'Advanced options', estimate: 'Help me estimate this →',
    youNeed: 'You need', participants: 'participants', perGroup: 'per group', completers: 'must complete the study', withDropout: 'including dropout',
    powerWith: 'With this sample you have', powerUnit: 'power', mdeWith: 'With this sample you can detect', precisionWith: 'With this sample the margin of error is',
    curve: 'Power by number recruited per group', scenarios: 'If your assumptions change (per group, before dropout)', effect: 'Effect', writeUp: 'Write-up',
    copy: 'Copy write-up', copied: 'Copied', word: 'Word', save: 'Save', saved: 'Saved', history: 'Saved calculations', noHistory: 'No saved calculations yet.',
    restore: 'Open', remove: 'Remove', exportCsv: 'Export CSV', checking: 'Calculating…', reference: 'Reference', criteria: 'Riley criteria',
    needed80: 'Needed for target power', events: 'events needed', clusters: 'clusters per group', standardized: 'Standardised effect',
    library: 'All designs', libraryCopy: 'Answering “What are you planning?” picks the design for you. Choose one directly here if you know it.',
    showAdvanced: 'Show advanced designs', close: 'Close', basic: 'Basic', adv: 'Advanced',
    helperTitle: 'Help me estimate the standard deviation', helperCopy: 'Use what a similar published study reports. ResRef converts it for you.',
    useValue: 'Use this value', source: 'Source (added to your write-up)',
  },
  ar: {
    brand: 'حجم العينة', allDesigns: 'كل التصاميم', planning: 'ماذا تخطط؟', outcome: 'النتيجة الرئيسية', method: 'الطريقة',
    assumptions: 'افتراضاتك', calculate: 'احسب', advanced: 'خيارات متقدمة', estimate: 'ساعدني في تقدير هذه القيمة ←',
    youNeed: 'تحتاج إلى', participants: 'مشاركاً', perGroup: 'لكل مجموعة', completers: 'يجب أن يُكملوا الدراسة', withDropout: 'مع احتساب الانسحاب',
    powerWith: 'مع هذه العينة لديك', powerUnit: 'قوة إحصائية', mdeWith: 'مع هذه العينة يمكنك اكتشاف', precisionWith: 'مع هذه العينة يبلغ هامش الخطأ',
    curve: 'القوة حسب عدد المشاركين في كل مجموعة', scenarios: 'إذا تغيرت افتراضاتك (لكل مجموعة، قبل الانسحاب)', effect: 'الأثر', writeUp: 'الصياغة',
    copy: 'نسخ الصياغة', copied: 'تم النسخ', word: 'Word', save: 'حفظ', saved: 'تم الحفظ', history: 'الحسابات المحفوظة', noHistory: 'لا توجد حسابات محفوظة.',
    restore: 'فتح', remove: 'حذف', exportCsv: 'تصدير CSV', checking: 'جارٍ الحساب…', reference: 'المرجع', criteria: 'معايير رايلي',
    needed80: 'المطلوب للقوة المستهدفة', events: 'حدثاً مطلوباً', clusters: 'عنقوداً لكل مجموعة', standardized: 'الأثر المعياري',
    library: 'كل التصاميم', libraryCopy: 'الإجابة عن «ماذا تخطط؟» تختار التصميم لك. يمكنك أيضاً الاختيار مباشرة.',
    showAdvanced: 'إظهار التصاميم المتقدمة', close: 'إغلاق', basic: 'أساسي', adv: 'متقدم',
    helperTitle: 'ساعدني في تقدير الانحراف المعياري', helperCopy: 'استخدم ما تذكره دراسة منشورة مشابهة.',
    useValue: 'استخدم هذه القيمة', source: 'المصدر (يُضاف إلى الصياغة)',
  },
};

/** Request inputs for the API from the form state (splits the significance choice, maps field keys). */
export function apiInputs(form) {
  const inputs = { ...form };
  const [alpha, sides] = String(form.significance || '0.05|2').split('|');
  inputs.alpha = alpha;
  inputs.sides = sides;
  delete inputs.significance;
  return inputs;
}

export function fieldKey(name) {
  return FIELDS[name]?.key || name;
}

export function fieldVisible(name, form) {
  const condition = FIELDS[name]?.when;
  return !condition || Object.entries(condition).every(([key, value]) => (form[key] ?? DESIGN_FORMS[form.design]?.defaults?.[key]) === value);
}

// ── SD helper ────────────────────────────────────────────────────────────────

function tQuantile975(df) {
  // Cornish-Fisher expansion of the t quantile; accurate to 3 decimals for df ≥ 3.
  const z = 1.959964;
  return z + (z ** 3 + z) / (4 * df) + (5 * z ** 5 + 16 * z ** 3 + 3 * z) / (96 * df ** 2) + (3 * z ** 7 + 19 * z ** 5 + 17 * z ** 3 - 15 * z) / (384 * df ** 3);
}

export function pooledSd(sd1, n1, sd2, n2) {
  if (!(sd1 > 0 && sd2 > 0 && n1 > 1 && n2 > 1)) return null;
  return Math.sqrt(((n1 - 1) * sd1 ** 2 + (n2 - 1) * sd2 ** 2) / (n1 + n2 - 2));
}

export function sdFromCi(lower, upper, n) {
  if (!(upper > lower && n > 2)) return null;
  return (Math.sqrt(n) * (upper - lower)) / (2 * tQuantile975(n - 1));
}

export function sdFromIqr(q1, q3) {
  if (!(q3 > q1)) return null;
  return (q3 - q1) / 1.35;
}

// ── Workspace ────────────────────────────────────────────────────────────────

export function normalizeWorkspace(workspace = {}) {
  const calculations = Array.isArray(workspace.calculations) ? workspace.calculations.filter((item) => item && item.design).slice(0, 40) : [];
  const last = workspace.last && workspace.last.design ? workspace.last : null;
  return { calculations, last };
}

export function loadWorkspace() {
  try { return normalizeWorkspace(JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')); } catch { return normalizeWorkspace(); }
}

export function saveWorkspace(workspace) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizeWorkspace(workspace))); } catch { /* storage blocked */ }
}

export function workspaceHasContent(workspace) {
  return normalizeWorkspace(workspace).calculations.length > 0;
}

export function calculationsCsv(calculations) {
  const escape = (value) => `"${String(value ?? '').replace(/"/g, '""')}"`;
  return [['Date', 'Design', 'Mode', 'Answer', 'Write-up'].map(escape).join(','),
    ...calculations.map((item) => [new Date(item.createdAt).toLocaleString(), item.label, item.mode, item.summary, item.writeup].map(escape).join(','))].join('\n');
}
