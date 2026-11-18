/**
 * Study-type driven sample size: the researcher picks the type of study; ResRef picks the calculation,
 * shows only the simple information that study needs, and keeps the statistical settings under
 * "Advanced options". Each study type (or its outcome variant) maps to one engine design.
 */

const pct = { kind: 'percent' };

/** Every field the page can show. `simple` fields appear by default; the rest are advanced. */
export const STUDY_FIELDS = {
  population: { kind: 'number', en: 'Estimated population size', ar: 'حجم المجتمع التقديري', step: 1, optional: true,
    help: { en: 'How many people are in the group you are studying (e.g. 2,000 students). Leave empty if very large or unknown.', ar: 'عدد أفراد المجتمع المستهدف (مثلاً 2000 طالب). اتركه فارغاً إذا كان كبيراً جداً أو غير معروف.' } },
  proportion: { ...pct, en: 'Expected percentage', ar: 'النسبة المتوقعة',
    help: { en: 'Your best guess of the percentage with the answer or condition. If unsure, use 50% — it gives the safest (largest) sample.', ar: 'أفضل تقدير للنسبة. إذا لم تكن متأكداً استخدم 50% (أكبر عينة وأكثرها أماناً).' } },
  prevalence_expected: { key: 'proportion', ...pct, en: 'Expected prevalence', ar: 'الانتشار المتوقع',
    help: { en: 'From a previous study or national data. If unsure, use 50%.', ar: 'من دراسة سابقة أو بيانات وطنية. إذا لم تكن متأكداً استخدم 50%.' } },
  margin_pct: { key: 'margin', ...pct, en: 'Margin of error (±)', ar: 'هامش الخطأ (±)',
    help: { en: 'How close your result should be to the true value. 5% is common; use 3% for more precision.', ar: 'مدى قرب نتيجتك من القيمة الحقيقية. 5% شائع، و3% لدقة أعلى.' } },
  confidence: { kind: 'select', en: 'Confidence level', ar: 'مستوى الثقة', options: [['95', '95% (standard)'], ['90', '90%'], ['99', '99%']] },
  response_rate: { ...pct, en: 'Expected response rate', ar: 'معدل الاستجابة المتوقع',
    help: { en: 'The share of people you invite who will answer. Online surveys often get 30–60%.', ar: 'نسبة من سيجيبون من المدعوين. الاستبيانات الإلكترونية غالباً 30–60%.' } },
  dropout: { ...pct, en: 'Expected dropout / loss to follow-up', ar: 'نسبة الانسحاب أو الفقد المتوقعة',
    help: { en: 'Participants who may leave before the end. 10–20% is typical.', ar: 'المشاركون الذين قد ينسحبون قبل النهاية. عادة 10–20%.' } },
  sd: { kind: 'number', en: 'Standard deviation (spread)', ar: 'الانحراف المعياري', unit: true, helper: 'sd',
    help: { en: 'How much the values vary between people — from a similar published study.', ar: 'مدى تباين القيم بين الأشخاص — من دراسة منشورة مشابهة.' } },
  margin_num: { key: 'margin', kind: 'number', en: 'Margin of error (±)', ar: 'هامش الخطأ (±)', unit: true,
    help: { en: 'How close the average should be to the true average, in the same unit.', ar: 'مدى قرب المتوسط من القيمة الحقيقية، بنفس الوحدة.' } },
  unit: { kind: 'text', en: 'Unit of measurement', ar: 'وحدة القياس', placeholder: 'e.g. mmHg, kg, points', optional: true },
  p1_unexposed: { key: 'p1', ...pct, en: 'Risk of the outcome in the unexposed group', ar: 'خطر النتيجة لدى غير المعرّضين',
    help: { en: 'E.g. 10% of non-smokers develop the disease during follow-up.', ar: 'مثلاً 10% من غير المدخنين يصابون بالمرض.' } },
  relative_risk: { kind: 'number', en: 'Relative risk you want to detect', ar: 'الخطر النسبي المراد اكتشافه',
    help: { en: '2 means the exposed group has twice the risk.', ar: '2 تعني أن الخطر لدى المعرّضين ضعف الخطر لدى غيرهم.' } },
  p1_controls: { key: 'p1', ...pct, en: 'Exposure among controls', ar: 'نسبة التعرض لدى الضوابط',
    help: { en: 'The percentage of people without the disease who have the exposure (e.g. 20% smoke).', ar: 'نسبة التعرض لدى غير المصابين (مثلاً 20% مدخنون).' } },
  odds_ratio_exposure: { kind: 'number', en: 'Odds ratio you want to detect', ar: 'نسبة الأرجحية المراد اكتشافها',
    help: { en: '2 means cases have twice the odds of exposure. Use a value from the literature.', ar: '2 تعني أن أرجحية التعرض لدى الحالات ضعفها لدى الضوابط.' } },
  p1_control_arm: { key: 'p1', ...pct, en: 'Expected rate in the control group', ar: 'المعدل المتوقع في المجموعة الضابطة', help: { en: 'E.g. 40% recover with usual care.', ar: 'مثلاً 40% يتعافون بالرعاية المعتادة.' } },
  p2_treatment_arm: { key: 'p2', ...pct, en: 'Expected rate in the new-treatment group', ar: 'المعدل المتوقع في مجموعة العلاج الجديد', help: { en: 'E.g. 55% recover with the new treatment.', ar: 'مثلاً 55% يتعافون بالعلاج الجديد.' } },
  p1_group: { key: 'p1', ...pct, en: 'Percentage in group 1', ar: 'النسبة في المجموعة 1' },
  p2_group: { key: 'p2', ...pct, en: 'Percentage in group 2', ar: 'النسبة في المجموعة 2' },
  difference: { kind: 'number', en: 'Smallest difference that matters', ar: 'أصغر فرق ذي أهمية', unit: true,
    help: { en: 'The difference between group averages that would be clinically important.', ar: 'الفرق بين متوسطي المجموعتين الذي له أهمية سريرية.' } },
  change: { key: 'difference', kind: 'number', en: 'Smallest change that matters', ar: 'أصغر تغير ذي أهمية', unit: true },
  sd_diff: { kind: 'number', en: 'Spread (SD) of the changes', ar: 'الانحراف المعياري للتغيرات', unit: true, helper: 'sd',
    help: { en: 'How much the before–after change varies between people.', ar: 'مدى تباين التغير بين الأشخاص.' } },
  p10: { ...pct, en: 'People changing from “no” to “yes”', ar: 'نسبة من تغيروا من «لا» إلى «نعم»' },
  p01: { ...pct, en: 'People changing from “yes” to “no”', ar: 'نسبة من تغيروا من «نعم» إلى «لا»' },
  hazard_ratio: { kind: 'number', en: 'Hazard ratio you want to detect', ar: 'نسبة الخطر المراد اكتشافها', help: { en: '0.7 means 30% fewer events with the new treatment.', ar: '0.7 تعني أحداثاً أقل بنسبة 30%.' } },
  event_probability: { ...pct, en: 'Share expected to have the event during follow-up', ar: 'نسبة من يُتوقع حدوث الحدث لهم' },
  margin_ni: { key: 'margin', kind: 'number', en: 'Non-inferiority margin', ar: 'هامش عدم الأدنوية', unit: true, help: { en: 'The largest loss of effect you would still accept.', ar: 'أكبر نقص مقبول في الأثر.' } },
  groups: { kind: 'number', en: 'Number of groups', ar: 'عدد المجموعات', step: 1 },
  f: { kind: 'select', en: 'Expected size of the differences', ar: 'حجم الفروق المتوقع', options: [['0.1', 'Small'], ['0.25', 'Medium (common choice)'], ['0.4', 'Large']] },
  r: { kind: 'select', en: 'Expected strength of the relationship', ar: 'قوة العلاقة المتوقعة', options: [['0.1', 'Weak (r = 0.1)'], ['0.2', 'Weak–moderate (r = 0.2)'], ['0.3', 'Moderate (r = 0.3)'], ['0.5', 'Strong (r = 0.5)']] },
  tested_predictors: { kind: 'number', en: 'Number of predictors (factors) in the model', ar: 'عدد المتنبئات في النموذج', step: 1 },
  f2: { kind: 'select', en: 'Expected strength of the predictors', ar: 'قوة المتنبئات المتوقعة', options: [['0.02', 'Small'], ['0.15', 'Medium (common choice)'], ['0.35', 'Large']] },
  parameters: { kind: 'number', en: 'Number of candidate predictors', ar: 'عدد المتنبئات المرشحة', step: 1, help: { en: 'Count each category beyond the first (a 3-level predictor counts as 2).', ar: 'احسب كل فئة بعد الأولى.' } },
  outcome_prevalence: { key: 'prevalence', ...pct, en: 'How common is the outcome?', ar: 'ما مدى شيوع النتيجة؟' },
  sensitivity: { ...pct, en: 'Expected sensitivity', ar: 'الحساسية المتوقعة', help: { en: 'From previous studies of the test.', ar: 'من دراسات سابقة للاختبار.' } },
  specificity: { ...pct, en: 'Expected specificity', ar: 'النوعية المتوقعة' },
  prevalence: { ...pct, en: 'Prevalence of the disease in your setting', ar: 'انتشار المرض في مكان الدراسة' },
  auc: { kind: 'number', en: 'Expected area under the ROC curve (AUC)', ar: 'المساحة المتوقعة تحت منحنى ROC', help: { en: '0.75 is a common expectation for a useful test.', ar: '0.75 توقع شائع لاختبار مفيد.' } },
  pilot_rule: { kind: 'select', en: 'Effect expected in the main study later', ar: 'الأثر المتوقع في الدراسة الرئيسية', options: [['medium', 'Medium — 15 per group'], ['small', 'Small — 25 per group'], ['extra_small', 'Very small — 75 per group'], ['large', 'Large — 10 per group'], ['julious', 'Julious rule — 12 per group']] },
  arms: { kind: 'number', en: 'Number of groups', ar: 'عدد المجموعات', step: 1 },
  // Advanced
  power: { kind: 'select', en: 'Statistical power', ar: 'القوة الإحصائية', options: [['80', '80% (standard)'], ['85', '85%'], ['90', '90%'], ['95', '95%']],
    help: { en: 'The chance of finding the effect if it is real.', ar: 'احتمال اكتشاف الأثر إن كان موجوداً.' } },
  significance: { kind: 'select', en: 'Significance level (α)', ar: 'مستوى الدلالة', options: [['0.05|2', '0.05, two-sided (standard)'], ['0.05|1', '0.05, one-sided'], ['0.01|2', '0.01, two-sided'], ['0.025|1', '0.025, one-sided']] },
  ratio: { kind: 'number', en: 'Allocation ratio (group 2 : group 1)', ar: 'نسبة التوزيع', help: { en: '1 = equal groups. In a case-control study, controls per case.', ar: '1 = مجموعات متساوية.' } },
  design_effect: { kind: 'number', en: 'Design effect', ar: 'تأثير التصميم', help: { en: 'For cluster or multi-stage sampling (often 1.5–2).', ar: 'للعينات العنقودية (غالباً 1.5–2).' } },
  icc: { kind: 'number', en: 'Intraclass correlation (cluster studies)', ar: 'معامل الارتباط داخل العنقود' },
  cluster_size: { kind: 'number', en: 'People per cluster', ar: 'عدد الأفراد في العنقود', step: 1 },
  continuity: { kind: 'select', en: 'Continuity correction', ar: 'تصحيح الاستمرارية', options: [['', 'No'], ['1', 'Yes (more conservative)']] },
  p2_direct: { key: 'p2', ...pct, en: 'Percentage in the comparison group (instead of a ratio)', ar: 'النسبة في المجموعة المقارنة' },
  f_exact: { key: 'f', kind: 'number', en: 'Exact effect size f', ar: 'حجم الأثر f' },
  r_exact: { key: 'r', kind: 'number', en: 'Exact correlation r', ar: 'معامل الارتباط r' },
  f2_exact: { key: 'f2', kind: 'number', en: 'Exact effect size f²', ar: 'حجم الأثر f²' },
  total_predictors: { kind: 'number', en: 'Total predictors including controls', ar: 'إجمالي المتنبئات', step: 1 },
  r2_cs: { kind: 'number', en: 'Anticipated Cox-Snell R²', ar: 'R² المتوقع', optional: true },
  auc_null: { kind: 'number', en: 'AUC under the null', ar: 'AUC في الفرضية الصفرية' },
};

const COMMON_ADVANCED = ['power', 'significance'];

/** Study types. A type with `variants` asks one extra plain question (what is measured). */
export const STUDY_TYPES = [
  { id: 'survey', en: 'Survey / questionnaire', ar: 'استبيان', desc: { en: 'Ask a group of people questions and report percentages.', ar: 'طرح أسئلة على مجموعة وعرض النسب.' },
    design: 'single_proportion', simple: ['population', 'proportion', 'margin_pct', 'response_rate'], advanced: ['confidence', 'design_effect'],
    defaults: { proportion: 50, margin: 5, response_rate: 70, confidence: '95' } },
  { id: 'prevalence', en: 'Prevalence study', ar: 'دراسة انتشار', desc: { en: 'How common is a disease or condition?', ar: 'ما مدى شيوع مرض أو حالة؟' },
    design: 'single_proportion', simple: ['population', 'prevalence_expected', 'margin_pct', 'response_rate'], advanced: ['confidence', 'design_effect'],
    defaults: { proportion: 50, margin: 5, response_rate: 90, confidence: '95' } },
  { id: 'cross_sectional', en: 'Cross-sectional study', ar: 'دراسة مقطعية', desc: { en: 'Measure something once in a population.', ar: 'قياس متغير مرة واحدة في مجتمع.' },
    variants: [
      { id: 'percent', en: 'A percentage', ar: 'نسبة مئوية', design: 'single_proportion', simple: ['population', 'proportion', 'margin_pct', 'response_rate'], advanced: ['confidence', 'design_effect'], defaults: { proportion: 50, margin: 5, response_rate: 90, confidence: '95' } },
      { id: 'average', en: 'An average', ar: 'متوسط', design: 'single_mean', simple: ['population', 'sd', 'margin_num', 'unit', 'response_rate'], advanced: ['confidence', 'design_effect'], defaults: { sd: 10, margin: 2, response_rate: 90, confidence: '95' } },
    ] },
  { id: 'cohort', groups: { en: ['unexposed', 'exposed'], ar: ['غير المعرّضين', 'المعرّضين'] }, en: 'Cohort study', ar: 'دراسة أترابية', desc: { en: 'Follow exposed and unexposed people over time.', ar: 'متابعة المعرّضين وغير المعرّضين عبر الزمن.' },
    design: 'two_proportions', simple: ['p1_unexposed', 'relative_risk', 'dropout'], advanced: [...COMMON_ADVANCED, 'ratio', 'continuity'],
    defaults: { p1: 10, relative_risk: 2, dropout: 15 } },
  { id: 'case_control', groups: { en: ['controls', 'cases'], ar: ['الضوابط', 'الحالات'] }, en: 'Case-control study', ar: 'دراسة الحالات والشواهد', desc: { en: 'Compare people with and without a disease.', ar: 'مقارنة المصابين بغير المصابين.' },
    design: 'two_proportions', simple: ['p1_controls', 'odds_ratio_exposure'], advanced: [...COMMON_ADVANCED, 'ratio', 'continuity', 'dropout'],
    defaults: { p1: 20, odds_ratio_exposure: 2 } },
  { id: 'rct', groups: { en: ['control', 'treatment'], ar: ['الضابطة', 'العلاج'] }, en: 'Randomized controlled trial', ar: 'تجربة عشوائية محكومة', desc: { en: 'Compare a new treatment with a control.', ar: 'مقارنة علاج جديد بمجموعة ضابطة.' },
    variants: [
      { id: 'yesno', en: 'Yes / no outcome', ar: 'نتيجة نعم / لا', design: 'two_proportions', simple: ['p1_control_arm', 'p2_treatment_arm', 'dropout'], advanced: [...COMMON_ADVANCED, 'ratio', 'continuity', 'icc', 'cluster_size'], defaults: { p1: 40, p2: 55, dropout: 10 } },
      { id: 'number', en: 'A measurement', ar: 'قياس رقمي', design: 'two_means', simple: ['difference', 'sd', 'unit', 'dropout'], advanced: [...COMMON_ADVANCED, 'ratio', 'icc', 'cluster_size'], defaults: { difference: 5, sd: 12, unit: '', dropout: 10 } },
      { id: 'time', en: 'Time to an event', ar: 'الزمن حتى حدث', design: 'logrank', simple: ['hazard_ratio', 'event_probability', 'dropout'], advanced: [...COMMON_ADVANCED, 'ratio'], defaults: { hazard_ratio: 0.7, event_probability: 50, dropout: 10 } },
      { id: 'noninferiority', en: 'Show it is not worse', ar: 'إثبات أنه ليس أسوأ', design: 'noninferiority', simple: ['margin_ni', 'sd', 'unit', 'dropout'], advanced: ['power', 'ratio'], defaults: { margin: 5, sd: 12, true_difference: 0, outcome: 'mean', hypothesis: 'noninferiority', significance: '0.025|1', dropout: 10 } },
    ] },
  { id: 'comparative', groups: { en: ['in group 1', 'in group 2'], ar: ['في المجموعة 1', 'في المجموعة 2'] }, en: 'Comparative study', ar: 'دراسة مقارنة', desc: { en: 'Compare two or more existing groups.', ar: 'مقارنة مجموعتين أو أكثر.' },
    variants: [
      { id: 'yesno', en: 'Percentages', ar: 'نسب', design: 'two_proportions', simple: ['p1_group', 'p2_group', 'dropout'], advanced: [...COMMON_ADVANCED, 'ratio', 'continuity'], defaults: { p1: 30, p2: 45, dropout: 0 } },
      { id: 'number', en: 'Averages', ar: 'متوسطات', design: 'two_means', simple: ['difference', 'sd', 'unit', 'dropout'], advanced: [...COMMON_ADVANCED, 'ratio'], defaults: { difference: 5, sd: 12, unit: '', dropout: 0 } },
      { id: 'groups', en: 'Averages, 3+ groups', ar: 'متوسطات، 3 مجموعات فأكثر', design: 'anova', simple: ['groups', 'f', 'dropout'], advanced: [...COMMON_ADVANCED, 'f_exact'], defaults: { groups: 3, f: '0.25', dropout: 0 } },
    ] },
  { id: 'diagnostic', en: 'Diagnostic accuracy study', ar: 'دراسة دقة تشخيصية', desc: { en: 'How well does a test detect a disease?', ar: 'ما مدى دقة اختبار في كشف مرض؟' },
    variants: [
      { id: 'sens', en: 'Sensitivity & specificity', ar: 'الحساسية والنوعية', design: 'diagnostic', simple: ['sensitivity', 'specificity', 'prevalence', 'margin_pct', 'dropout'], advanced: ['confidence'], defaults: { sensitivity: 85, specificity: 90, prevalence: 20, margin: 5, confidence: '95', dropout: 0 } },
      { id: 'auc', en: 'ROC curve (AUC)', ar: 'منحنى ROC', design: 'auc', simple: ['auc', 'dropout'], advanced: [...COMMON_ADVANCED, 'ratio', 'auc_null'], defaults: { auc: 0.75, auc_null: 0.5, dropout: 0 } },
    ] },
  { id: 'correlation', en: 'Correlation study', ar: 'دراسة ارتباطية', desc: { en: 'Are two measurements related?', ar: 'هل يرتبط قياسان؟' },
    design: 'correlation', simple: ['r', 'dropout'], advanced: [...COMMON_ADVANCED, 'r_exact'], defaults: { r: '0.3', dropout: 0 } },
  { id: 'regression', en: 'Regression-based study', ar: 'دراسة قائمة على الانحدار', desc: { en: 'Find which factors predict an outcome.', ar: 'تحديد العوامل التي تتنبأ بنتيجة.' },
    variants: [
      { id: 'number', en: 'A measured outcome', ar: 'نتيجة رقمية', design: 'regression', simple: ['tested_predictors', 'f2', 'dropout'], advanced: [...COMMON_ADVANCED, 'f2_exact', 'total_predictors'], defaults: { tested_predictors: 5, total_predictors: 5, f2: '0.15', dropout: 0 } },
      { id: 'yesno', en: 'A yes / no outcome', ar: 'نتيجة نعم / لا', design: 'prediction', simple: ['parameters', 'outcome_prevalence', 'dropout'], advanced: ['r2_cs'], defaults: { parameters: 10, prevalence: 20, dropout: 0 } },
    ] },
  { id: 'before_after', en: 'Before–after study', ar: 'دراسة قبل وبعد', desc: { en: 'Measure the same people twice.', ar: 'قياس نفس الأشخاص مرتين.' },
    variants: [
      { id: 'number', en: 'A measurement', ar: 'قياس رقمي', design: 'paired_means', simple: ['change', 'sd_diff', 'unit', 'dropout'], advanced: COMMON_ADVANCED, defaults: { difference: 5, sd_diff: 10, unit: '', dropout: 10 } },
      { id: 'yesno', en: 'Yes / no', ar: 'نعم / لا', design: 'mcnemar', simple: ['p10', 'p01', 'dropout'], advanced: COMMON_ADVANCED, defaults: { p10: 20, p01: 10, dropout: 10 } },
    ] },
  { id: 'pilot', en: 'Pilot / feasibility study', ar: 'دراسة تجريبية', desc: { en: 'A small study before the main one.', ar: 'دراسة صغيرة قبل الدراسة الرئيسية.' },
    design: 'pilot', simple: ['arms', 'pilot_rule', 'dropout'], advanced: [], defaults: { arms: 2, pilot_rule: 'medium', dropout: 10 } },
];

export function studySpec(typeId, variantId) {
  const type = STUDY_TYPES.find((item) => item.id === typeId) || STUDY_TYPES[0];
  const variant = type.variants ? (type.variants.find((item) => item.id === variantId) || type.variants[0]) : null;
  return { type, variant, groups: type.groups || null, ...(variant || type) };
}

/** Starting form for a study type: its defaults plus the standard power and significance. */
export function startForm(typeId, variantId) {
  const spec = studySpec(typeId, variantId);
  return { studyType: spec.type.id, variant: spec.variant?.id || null, design: spec.design, mode: 'n', significance: '0.05|2', power: '80', ...spec.defaults };
}

export function fieldKeyOf(name) {
  return STUDY_FIELDS[name]?.key || name;
}

/** Labels for the "how we got this number" steps. */
export function stepLabel(step, lang, form) {
  const ar = lang === 'ar';
  if (step.key === 'base') return ar ? 'الحجم الأساسي المطلوب' : form.population ? 'Basic sample size (very large population)' : 'Basic sample size';
  if (step.key === 'design_effect') return ar ? `بعد تأثير التصميم (×${step.factor})` : `After the design effect (×${step.factor})`;
  if (step.key === 'population') return ar ? `بعد التعديل لحجم المجتمع (${Number(form.population).toLocaleString()})` : `Adjusted for your population of ${Number(form.population).toLocaleString()}`;
  const parts = [];
  if (step.response < 1) parts.push(ar ? `استجابة ${Math.round(step.response * 100)}%` : `${Math.round(step.response * 100)}% response`);
  if (step.dropout > 0) parts.push(ar ? `انسحاب ${Math.round(step.dropout * 100)}%` : `${Math.round(step.dropout * 100)}% dropout`);
  return ar ? `بعد احتساب ${parts.join(' و')}` : `Allowing for ${parts.join(' and ')}`;
}
