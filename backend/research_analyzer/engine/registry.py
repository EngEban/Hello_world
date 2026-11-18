"""Every analysis the Research Analyzer offers: family, level, inputs and the function that runs it.

The interface builds its method library and input forms from ``public_catalog()``; ``run`` executes a
method by id. Basic methods are shown to everyone; advanced ones appear behind "Show advanced".
"""
from __future__ import annotations

import pandas as pd

from research_analyzer.services import stats_service as base

from . import methods as m

NUMERIC = ["numeric", "ordinal", "likert"]
CATEGORY = ["categorical", "ordinal", "likert"]
ANY = ["numeric", "categorical", "ordinal", "likert"]

FAMILIES = [
    {"id": "describe", "label": "Describe", "label_ar": "الوصف", "question": "What does my sample look like?"},
    {"id": "compare", "label": "Compare groups", "label_ar": "مقارنة المجموعات", "question": "Is there a difference between groups or times?"},
    {"id": "categories", "label": "Categories", "label_ar": "المتغيرات الفئوية", "question": "Are two categorical variables related?"},
    {"id": "relationships", "label": "Relationships", "label_ar": "العلاقات", "question": "Do two measures move together?"},
    {"id": "regression", "label": "Regression", "label_ar": "الانحدار", "question": "What predicts an outcome, adjusting for others?"},
    {"id": "reliability", "label": "Reliability & agreement", "label_ar": "الثبات والاتفاق", "question": "Is my questionnaire or rating consistent?"},
    {"id": "diagnostic", "label": "Diagnostic accuracy", "label_ar": "الدقة التشخيصية", "question": "How good is a test against a reference?"},
]


def _field(key, label, kind="variable", types=None, required=True, **extra):
    return {"key": key, "label": label, "kind": kind, "types": types or ANY, "required": required, **extra}


OUTCOME_NUM = _field("outcome", "Outcome", types=NUMERIC)
GROUP = _field("group", "Groups", types=CATEGORY)
PREDICTORS = _field("predictors", "Predictors", kind="variables")
CATEGORICAL_PREDICTORS = _field("categorical_predictors", "Treat as categories", kind="subset", of="predictors", required=False)
PAIR = [_field("var1", "First variable"), _field("var2", "Second variable")]
PRE_POST = [_field("pre", "Before / first", types=NUMERIC), _field("post", "After / second", types=NUMERIC)]

METHODS = [
    # Describe
    {"id": "descriptive", "family": "describe", "level": "basic", "label": "Descriptive statistics", "label_ar": "الإحصاء الوصفي",
     "inputs": [_field("variables", "Variables", kind="variables")], "run": lambda df, p: base.descriptive_stats(df, p.get("variables", []))},
    {"id": "table_one", "family": "describe", "level": "basic", "label": "Table 1 by group", "label_ar": "جدول 1 حسب المجموعة",
     "inputs": [_field("group", "Split by", types=CATEGORY, required=False), _field("variables", "Variables", kind="variables")],
     "run": lambda df, p: m.table_one(df, p.get("group") or None, p.get("variables", []))},
    # Compare groups
    {"id": "ttest", "family": "compare", "level": "basic", "label": "Independent t test", "label_ar": "اختبار (ت) لعينتين مستقلتين",
     "inputs": [OUTCOME_NUM, GROUP], "run": lambda df, p: base.independent_ttest(df, p["outcome"], p["group"], equal_var=True)},
    {"id": "paired_ttest", "family": "compare", "level": "basic", "label": "Paired t test", "label_ar": "اختبار (ت) للعينات المترابطة",
     "inputs": PRE_POST, "run": lambda df, p: base.paired_ttest(df, p["pre"], p["post"])},
    {"id": "one_sample_ttest", "family": "compare", "level": "basic", "label": "One-sample t test", "label_ar": "اختبار (ت) لعينة واحدة",
     "inputs": [_field("variable", "Variable", types=NUMERIC), _field("test_value", "Compare with", kind="number")],
     "run": lambda df, p: m.one_sample_ttest(df, p["variable"], p.get("test_value", 0))},
    {"id": "anova", "family": "compare", "level": "basic", "label": "One-way ANOVA", "label_ar": "تحليل التباين الأحادي",
     "inputs": [OUTCOME_NUM, GROUP, _field("posthoc", "Pairwise method", kind="choice", required=False,
                                          options=["auto", "tukey", "games_howell", "bonferroni", "holm"])],
     "run": lambda df, p: m.anova_full(df, p["outcome"], p["group"], p.get("posthoc", "auto"))},
    {"id": "welch", "family": "compare", "level": "advanced", "label": "Welch t test", "label_ar": "اختبار ويلش",
     "inputs": [OUTCOME_NUM, GROUP], "run": lambda df, p: base.independent_ttest(df, p["outcome"], p["group"], equal_var=False)},
    {"id": "mann_whitney", "family": "compare", "level": "advanced", "label": "Mann-Whitney U", "label_ar": "اختبار مان-ويتني",
     "inputs": [OUTCOME_NUM, GROUP], "run": lambda df, p: base.mann_whitney_u(df, p["outcome"], p["group"])},
    {"id": "wilcoxon", "family": "compare", "level": "advanced", "label": "Wilcoxon signed-rank", "label_ar": "اختبار ويلكوكسون",
     "inputs": PRE_POST, "run": lambda df, p: base.wilcoxon_signed_rank(df, p["pre"], p["post"])},
    {"id": "welch_anova", "family": "compare", "level": "advanced", "label": "Welch ANOVA", "label_ar": "تحليل تباين ويلش",
     "inputs": [OUTCOME_NUM, GROUP], "run": lambda df, p: base.welch_anova(df, p["outcome"], p["group"])},
    {"id": "kruskal", "family": "compare", "level": "advanced", "label": "Kruskal-Wallis + Dunn", "label_ar": "كروسكال-واليس + دن",
     "inputs": [OUTCOME_NUM, GROUP], "run": lambda df, p: m.dunn_posthoc(df, p["outcome"], p["group"])},
    {"id": "factorial_anova", "family": "compare", "level": "advanced", "label": "Factorial ANOVA", "label_ar": "تحليل التباين العاملي",
     "inputs": [OUTCOME_NUM, _field("factors", "Factors (2–3)", kind="variables", types=CATEGORY)],
     "run": lambda df, p: m.factorial_anova(df, p["outcome"], p.get("factors", []))},
    {"id": "ancova", "family": "compare", "level": "advanced", "label": "ANCOVA", "label_ar": "تحليل التغاير",
     "inputs": [OUTCOME_NUM, GROUP, _field("covariates", "Covariates", kind="variables", types=["numeric"])],
     "run": lambda df, p: m.factorial_anova(df, p["outcome"], [p["group"]], p.get("covariates", []))},
    {"id": "repeated_measures_anova", "family": "compare", "level": "advanced", "label": "Repeated-measures ANOVA", "label_ar": "تحليل التباين للقياسات المتكررة",
     "inputs": [_field("measures", "Measurements in time order", kind="variables", types=NUMERIC)],
     "run": lambda df, p: m.repeated_measures_anova(df, p.get("measures", []))},
    {"id": "mixed_anova", "family": "compare", "level": "advanced", "label": "Mixed ANOVA", "label_ar": "تحليل التباين المختلط",
     "inputs": [_field("measures", "Measurements in time order", kind="variables", types=NUMERIC), _field("between", "Groups", types=CATEGORY)],
     "run": lambda df, p: m.repeated_measures_anova(df, p.get("measures", []), p.get("between"))},
    # Categories
    {"id": "chi_square", "family": "categories", "level": "basic", "label": "Chi-square test", "label_ar": "اختبار كاي مربع",
     "inputs": PAIR, "run": lambda df, p: m.chi_square_full(df, p["var1"], p["var2"])},
    {"id": "two_by_two", "family": "categories", "level": "basic", "label": "Risk ratio & odds ratio (2×2)", "label_ar": "نسبة الخطر ونسبة الأرجحية",
     "inputs": [_field("outcome", "Outcome (yes/no)", types=CATEGORY), GROUP, _field("event_level", "Event value", kind="level", of="outcome", required=False),
                _field("reference_group", "Reference group", kind="level", of="group", required=False)],
     "run": lambda df, p: m.two_by_two(df, p["outcome"], p["group"], p.get("event_level"), p.get("reference_group"))},
    {"id": "goodness_of_fit", "family": "categories", "level": "basic", "label": "Goodness of fit", "label_ar": "جودة المطابقة",
     "inputs": [_field("variable", "Variable", types=CATEGORY)], "run": lambda df, p: m.goodness_of_fit(df, p["variable"], p.get("expected_proportions"))},
    {"id": "mcnemar", "family": "categories", "level": "advanced", "label": "McNemar (paired yes/no)", "label_ar": "اختبار ماكنمار",
     "inputs": [_field("pre", "Before", types=CATEGORY), _field("post", "After", types=CATEGORY)], "run": lambda df, p: base.mcnemar_test(df, p["pre"], p["post"])},
    # Relationships
    {"id": "pearson", "family": "relationships", "level": "basic", "label": "Pearson correlation", "label_ar": "ارتباط بيرسون",
     "inputs": PAIR, "run": lambda df, p: base.pearson_correlation(df, p["var1"], p["var2"])},
    {"id": "spearman", "family": "relationships", "level": "basic", "label": "Spearman correlation", "label_ar": "ارتباط سبيرمان",
     "inputs": PAIR, "run": lambda df, p: base.spearman_correlation(df, p["var1"], p["var2"], "spearman")},
    {"id": "kendall", "family": "relationships", "level": "advanced", "label": "Kendall's τ", "label_ar": "تاو كندال",
     "inputs": PAIR, "run": lambda df, p: base.spearman_correlation(df, p["var1"], p["var2"], "kendall")},
    {"id": "partial_correlation", "family": "relationships", "level": "advanced", "label": "Partial correlation", "label_ar": "الارتباط الجزئي",
     "inputs": [*PAIR, _field("covariates", "Control for", kind="variables", types=["numeric"])],
     "run": lambda df, p: m.partial_correlation(df, p["var1"], p["var2"], p.get("covariates", []), p.get("method", "pearson"))},
    {"id": "correlation_matrix", "family": "relationships", "level": "advanced", "label": "Correlation matrix", "label_ar": "مصفوفة الارتباط",
     "inputs": [_field("variables", "Variables (3+)", kind="variables", types=NUMERIC)],
     "run": lambda df, p: m.correlation_matrix(df, [v["name"] if isinstance(v, dict) else v for v in p.get("variables", [])], p.get("method", "pearson"), p.get("padjust", "holm"))},
    # Regression
    {"id": "linear_regression", "family": "regression", "level": "basic", "label": "Linear regression", "label_ar": "الانحدار الخطي",
     "inputs": [OUTCOME_NUM, PREDICTORS, CATEGORICAL_PREDICTORS],
     "run": lambda df, p: m.linear_full(df, p["outcome"], p["predictors"], p.get("categorical_predictors", []), p.get("reference_levels"),
                                        bool(p.get("robust")), p.get("blocks"), p.get("interactions"))},
    {"id": "logistic_regression", "family": "regression", "level": "basic", "label": "Binary logistic regression", "label_ar": "الانحدار اللوجستي الثنائي",
     "inputs": [_field("outcome", "Outcome (yes/no)", types=CATEGORY), PREDICTORS, CATEGORICAL_PREDICTORS,
                _field("event_level", "Event value", kind="level", of="outcome", required=False)],
     "run": lambda df, p: m.logistic_full(df, p["outcome"], p["predictors"], p.get("categorical_predictors", []), p.get("event_level"), p.get("reference_levels"))},
    {"id": "multinomial_logistic", "family": "regression", "level": "advanced", "label": "Multinomial logistic", "label_ar": "اللوجستي متعدد الحدود",
     "inputs": [_field("outcome", "Outcome (3+ categories)", types=CATEGORY), PREDICTORS, CATEGORICAL_PREDICTORS],
     "run": lambda df, p: m.multinomial_logistic(df, p["outcome"], p["predictors"], p.get("categorical_predictors", []), p.get("reference_levels"), p.get("outcome_reference"))},
    {"id": "ordinal_logistic", "family": "regression", "level": "advanced", "label": "Ordinal logistic", "label_ar": "اللوجستي الترتيبي",
     "inputs": [_field("outcome", "Ordered outcome", types=CATEGORY), PREDICTORS, CATEGORICAL_PREDICTORS],
     "run": lambda df, p: m.ordinal_logistic(df, p["outcome"], p["predictors"], p.get("categorical_predictors", []), p.get("reference_levels"), p.get("order"))},
    {"id": "count_regression", "family": "regression", "level": "advanced", "label": "Poisson / negative binomial", "label_ar": "انحدار بواسون",
     "inputs": [_field("outcome", "Count outcome", types=["numeric"]), PREDICTORS, CATEGORICAL_PREDICTORS],
     "run": lambda df, p: m.count_regression(df, p["outcome"], p["predictors"], p.get("categorical_predictors", []), p.get("reference_levels"), p.get("family", "auto"))},
    # Reliability
    {"id": "cronbach", "family": "reliability", "level": "basic", "label": "Cronbach's alpha & items", "label_ar": "ألفا كرونباخ",
     "inputs": [_field("items", "Items", kind="variables", types=NUMERIC), _field("reverse_items", "Reverse-scored items", kind="subset", of="items", required=False)],
     "run": lambda df, p: m.reliability_full(df, p["items"], p.get("reverse_items", []))},
    {"id": "cohens_kappa", "family": "reliability", "level": "advanced", "label": "Cohen's κ (2 raters)", "label_ar": "كابا كوهين",
     "inputs": [_field("var1", "Rater 1"), _field("var2", "Rater 2")], "run": lambda df, p: m.cohens_kappa(df, p["var1"], p["var2"], p.get("weighted"))},
    {"id": "fleiss_kappa", "family": "reliability", "level": "advanced", "label": "Fleiss' κ (3+ raters)", "label_ar": "كابا فلايس",
     "inputs": [_field("raters", "Rater columns", kind="variables")], "run": lambda df, p: m.fleiss_kappa(df, p.get("raters", []))},
    {"id": "icc", "family": "reliability", "level": "advanced", "label": "Intraclass correlation (ICC)", "label_ar": "معامل الارتباط داخل الفئة",
     "inputs": [_field("raters", "Rating columns", kind="variables", types=NUMERIC)], "run": lambda df, p: m.icc(df, p.get("raters", []))},
    # Diagnostic
    {"id": "diagnostic_accuracy", "family": "diagnostic", "level": "basic", "label": "Sensitivity, specificity & ROC", "label_ar": "الحساسية والنوعية",
     "inputs": [_field("test", "Index test"), _field("reference", "Reference standard", types=CATEGORY),
                _field("reference_positive", "Positive value", kind="level", of="reference", required=False)],
     "run": lambda df, p: m.diagnostic_accuracy(df, p["test"], p["reference"], p.get("test_positive"), p.get("reference_positive"))},
]

BY_ID = {method["id"]: method for method in METHODS}

# Older names still accepted by the API.
ALIASES = {"demographic": "table_one", "fisher_exact": "two_by_two", "friedman": "repeated_measures_anova"}


def public_catalog() -> dict:
    return {
        "families": FAMILIES,
        "methods": [{key: value for key, value in method.items() if key != "run"} for method in METHODS],
        "always_included": [
            "Assumption checks with automatic fallback", "Effect sizes with 95% confidence intervals", "Missing values handled per analysis",
            "Multiple-comparison corrections", "Charts", "APA-style text in English and Arabic",
        ],
    }


def label_for(method_id: str) -> str:
    method = BY_ID.get(ALIASES.get(method_id, method_id))
    return method["label"] if method else method_id


def run(method_id: str, df: pd.DataFrame, params: dict) -> dict | None:
    """Run a registered method, or return None when the id is unknown here."""
    method = BY_ID.get(ALIASES.get(method_id, method_id))
    if method is None:
        return None
    if method_id == "demographic":
        return m.table_one(df, None, params.get("variables", []))
    return method["run"](df, params)
