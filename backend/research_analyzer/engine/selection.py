"""Turn a plain-language research question into a recommended method, with reasons and alternatives.

``recommend`` looks at the question type, the variables' confirmed types and the data itself (number
of groups, expected counts, distribution shape, number of events) and returns:

    {"method", "label", "params", "reasons": [...], "alternatives": [{"method", "label", "when"}], "warnings": [...]}

Only methods that can run on these variables are offered as alternatives.
"""
from __future__ import annotations

import pandas as pd
import scipy.stats as stats

from research_analyzer.services import stats_service as base

from .registry import label_for

QUESTIONS = ["describe", "compare", "relate", "predict", "change", "accuracy", "reliability", "one_sample"]
NUMERIC_TYPES = {"numeric"}
ORDERED_TYPES = {"ordinal", "likert"}


class SelectionError(ValueError):
    pass


def _kind(name: str, df: pd.DataFrame, types: dict) -> str:
    """numeric | ordinal | binary | categorical, from the confirmed type plus the observed levels."""
    declared = types.get(name)
    levels = df[name].dropna().nunique()
    if declared in ORDERED_TYPES:
        return "binary" if levels == 2 else "ordinal"
    if declared in NUMERIC_TYPES:
        return "binary" if levels == 2 else "numeric"
    if declared in {"id", "text", "date"}:
        raise SelectionError(f"{name!r} is marked as {declared}; it cannot be analysed this way.")
    return "binary" if levels == 2 else "categorical"


def _alt(method: str, when: str) -> dict:
    return {"method": method, "label": label_for(method), "when": when}


def _result(method, params, reasons, alternatives=(), warnings=()):
    return {"method": method, "label": label_for(method), "params": params, "reasons": list(reasons),
            "alternatives": list(alternatives), "warnings": [w for w in warnings if w]}


def _normal_enough(values) -> bool:
    series = pd.Series(values).dropna()
    if len(series) < 3:
        return False
    return base.assess_parametric_suitability(series).get("parametric_supported") is not False


def _need(fields: dict, *keys):
    missing = [key for key in keys if not fields.get(key)]
    if missing:
        raise SelectionError("Choose " + " and ".join(missing).replace("_", " ") + ".")


def _check_columns(df, names):
    unknown = [name for name in names if name not in df.columns]
    if unknown:
        raise SelectionError(f"Not in this dataset: {', '.join(unknown)}.")


def _compare(df, types, fields):
    _need(fields, "outcome", "group")
    outcome, group = fields["outcome"], fields["group"]
    covariates = [c for c in fields.get("covariates") or [] if c not in (outcome, group)]
    _check_columns(df, [outcome, group, *covariates])
    out_kind = _kind(outcome, df, types)
    data = df[[outcome, group]].dropna()
    n_groups = data[group].nunique()
    if n_groups < 2:
        raise SelectionError(f"{group!r} has fewer than two groups with data.")
    if n_groups > 20:
        raise SelectionError(f"{group!r} has {n_groups} values; choose a grouping variable with fewer categories.")

    if out_kind in {"numeric", "ordinal"}:
        if covariates and out_kind == "numeric":
            return _result("ancova", {"outcome": outcome, "group": group, "covariates": covariates},
                           [f"{outcome} is a number and you asked to adjust for {', '.join(covariates)}.",
                            "ANCOVA compares group means after accounting for the covariates."],
                           [_alt("linear_regression", "Same model written as a regression, with coefficients for every term.")])
        numeric = pd.to_numeric(data[outcome], errors="coerce")
        samples = [numeric[data[group] == level].dropna() for level in sorted(data[group].unique(), key=str)]
        if min(len(sample) for sample in samples) < 2:
            raise SelectionError("Every group needs at least two values.")
        shape_ok = out_kind == "numeric" and all(_normal_enough(sample) for sample in samples)
        if n_groups == 2:
            if shape_ok:
                return _result("ttest", {"outcome": outcome, "group": group},
                               [f"{outcome} is a number and {group} has 2 independent groups.",
                                "Each group's distribution supports comparing means.",
                                "If the spreads differ (Levene's test), Welch's version is used and stated in the write-up."],
                               [_alt("mann_whitney", "When values are skewed, ranked or have outliers."),
                                _alt("welch", "To always allow unequal spreads.")])
            reason = "the values are ordered categories" if out_kind == "ordinal" else "at least one group is skewed or has outliers"
            return _result("mann_whitney", {"outcome": outcome, "group": group},
                           [f"{group} has 2 independent groups.", f"A rank-based test is safer because {reason}."],
                           [_alt("ttest", "When both groups are roughly symmetric.")])
        if shape_ok:
            return _result("anova", {"outcome": outcome, "group": group},
                           [f"{outcome} is a number and {group} has {n_groups} independent groups.",
                            "Each group's distribution supports comparing means.",
                            "If the spreads differ, Welch's ANOVA with Games-Howell comparisons is used automatically."],
                           [_alt("kruskal", "When values are skewed, ranked or have outliers."),
                            _alt("factorial_anova", "To add a second grouping factor (e.g. treatment × sex).")])
        reason = "the values are ordered categories" if out_kind == "ordinal" else "at least one group is skewed or has outliers"
        return _result("kruskal", {"outcome": outcome, "group": group},
                       [f"{group} has {n_groups} independent groups.", f"A rank-based test is safer because {reason}.",
                        "Dunn's pairwise tests (Holm-adjusted) show which groups differ."],
                       [_alt("anova", "When every group is roughly symmetric.")])

    # Categorical outcome
    if covariates:
        method = "logistic_regression" if out_kind == "binary" else "multinomial_logistic"
        return _result(method, {"outcome": outcome, "predictors": [group, *covariates], "categorical_predictors": [group]},
                       [f"{outcome} is a category and you asked to adjust for {', '.join(covariates)}.",
                        "A regression gives the group effect adjusted for those factors."],
                       [_alt("two_by_two" if out_kind == "binary" and n_groups == 2 else "chi_square", "Unadjusted comparison.")])
    table = pd.crosstab(data[outcome].astype(str), data[group].astype(str))
    expected = stats.contingency.expected_freq(table.to_numpy())
    events = int(table.to_numpy().min())
    if out_kind == "binary" and n_groups == 2:
        exact = bool((expected < 5).any())
        return _result("two_by_two", {"outcome": outcome, "group": group},
                       [f"{outcome} is yes/no and {group} has 2 independent groups.",
                        "Reports the event rate in each group with the risk difference, risk ratio and odds ratio (95% CI).",
                        ("Fisher's exact test is used because some expected counts are below 5." if exact
                         else "All expected counts are at least 5, so the chi-square p-value is reliable.")],
                       [_alt("chi_square", "When you only need the test of association."),
                        _alt("logistic_regression", "To adjust for other factors.")],
                       [f"The smallest cell has only {events} records; confidence intervals will be wide." if events < 5 else None])
    sparse = float((expected < 5).mean())
    return _result("chi_square", {"var1": outcome, "var2": group},
                   [f"Both {outcome} and {group} are categories.",
                    "Adjusted residuals show which cells differ when the overall test is significant."],
                   [_alt("logistic_regression" if out_kind == "binary" else "multinomial_logistic", "To adjust for other factors.")],
                   [f"{sparse:.0%} of expected counts are below 5; consider combining rare categories." if sparse > 0.2 else None])


def _relate(df, types, fields):
    variables = [v for v in fields.get("variables") or [] if v]
    if len(variables) >= 3:
        _check_columns(df, variables)
        all_normal = all(_normal_enough(pd.to_numeric(df[v], errors="coerce")) for v in variables)
        method = "pearson" if all_normal else "spearman"
        return _result("correlation_matrix", {"variables": variables, "method": method, "padjust": "holm"},
                       [f"{len(variables)} measures were chosen, so every pair is correlated.",
                        f"{method.capitalize()} correlations are used{' because all variables look roughly normal' if all_normal else ' because some variables are skewed'}.",
                        "p-values are Holm-adjusted for the number of pairs."])
    _need(fields, "var1", "var2")
    a, b = fields["var1"], fields["var2"]
    covariates = [c for c in fields.get("covariates") or [] if c not in (a, b)]
    _check_columns(df, [a, b, *covariates])
    kinds = {_kind(a, df, types), _kind(b, df, types)}
    if kinds <= {"numeric"}:
        normal = _normal_enough(pd.to_numeric(df[a], errors="coerce")) and _normal_enough(pd.to_numeric(df[b], errors="coerce"))
        if covariates:
            return _result("partial_correlation", {"var1": a, "var2": b, "covariates": covariates, "method": "pearson" if normal else "spearman"},
                           [f"Both are numbers and you asked to control for {', '.join(covariates)}."], [_alt("linear_regression", "To model one as the outcome.")])
        if normal:
            return _result("pearson", {"var1": a, "var2": b}, ["Both variables are numbers with roughly symmetric distributions."],
                           [_alt("spearman", "When the relationship is curved but steady, or values are skewed."), _alt("linear_regression", "To predict one from the other.")])
        return _result("spearman", {"var1": a, "var2": b}, ["Both variables are numbers, but at least one is skewed or has outliers, so a rank correlation is safer."],
                       [_alt("pearson", "When both are roughly symmetric."), _alt("kendall", "For small samples with many tied values.")])
    if kinds & {"ordinal"} and kinds <= {"numeric", "ordinal"}:
        return _result("spearman", {"var1": a, "var2": b}, ["At least one variable is ordered (e.g. a Likert item), so a rank correlation is used."],
                       [_alt("kendall", "For small samples with many tied values.")])
    if kinds <= {"binary", "categorical", "ordinal"}:
        return _compare(df, types, {"outcome": a, "group": b})
    # One category, one number: a group comparison answers the question.
    numeric, category = (a, b) if _kind(a, df, types) in {"numeric", "ordinal"} else (b, a)
    recommendation = _compare(df, types, {"outcome": numeric, "group": category})
    recommendation["reasons"].insert(0, f"{category} is a category, so the relationship is tested as a difference in {numeric} between its groups.")
    return recommendation


def _predict(df, types, fields):
    _need(fields, "outcome", "predictors")
    outcome = fields["outcome"]
    predictors = [p for p in fields["predictors"] if p != outcome]
    if not predictors:
        raise SelectionError("Choose at least one predictor other than the outcome.")
    _check_columns(df, [outcome, *predictors])
    categorical = [p for p in predictors if _kind(p, df, types) in {"binary", "categorical"}]
    params = {"outcome": outcome, "predictors": predictors, "categorical_predictors": categorical}
    kind = _kind(outcome, df, types)
    terms = len(predictors) + sum(max(0, df[p].nunique() - 2) for p in categorical)
    complete = df[[outcome, *predictors]].dropna()
    if kind == "binary":
        smaller = int(complete[outcome].value_counts().min()) if len(complete) else 0
        epv = smaller / max(1, terms)
        return _result("logistic_regression", params,
                       [f"{outcome} is yes/no, so binary logistic regression gives odds ratios for each predictor.",
                        "The event value is chosen automatically (e.g. “Yes”) and can be changed."],
                       [_alt("two_by_two", "For one yes/no predictor without adjustment.")],
                       [f"Only {epv:.1f} events per predictor (aim for 10 or more); use fewer predictors." if epv < 10 else None])
    if kind == "categorical":
        return _result("multinomial_logistic", params, [f"{outcome} has {df[outcome].nunique()} unordered categories."],
                       [_alt("ordinal_logistic", "If the categories have a natural order.")])
    if kind == "ordinal":
        return _result("ordinal_logistic", params, [f"{outcome} is an ordered category (e.g. mild < moderate < severe)."],
                       [_alt("linear_regression", "If the scale has many points and behaves like a number.")])
    values = pd.to_numeric(complete[outcome], errors="coerce").dropna()
    looks_count = len(values) and (values >= 0).all() and (values % 1 == 0).all() and values.max() <= 1000 and stats.skew(values) > 1
    if looks_count:
        return _result("count_regression", params, [f"{outcome} is a skewed count (whole numbers from 0), so Poisson/negative binomial regression fits better.",
                                                     "Overdispersion is checked and negative binomial is used when needed."],
                       [_alt("linear_regression", "If the counts are large and roughly symmetric.")])
    warnings = []
    if len(complete) < 10 * terms:
        warnings.append(f"{len(complete)} complete records for {terms} terms; estimates may be unstable (aim for 10–20 per term).")
    return _result("linear_regression", params,
                   [f"{outcome} is a number, so linear regression estimates how much it changes with each predictor.",
                    "Residuals, equal spread, independence, multicollinearity (VIF) and influential points are checked."],
                   [_alt("ancova", "When the main predictor is a group and the rest are covariates.")], warnings)


def _change(df, types, fields):
    measures = [m for m in fields.get("measures") or [] if m]
    if not measures and fields.get("pre") and fields.get("post"):
        measures = [fields["pre"], fields["post"]]
    if len(measures) < 2:
        raise SelectionError("Choose the measurements in time order (at least two).")
    _check_columns(df, measures)
    between = fields.get("between") or fields.get("group")
    kinds = {_kind(m, df, types) for m in measures}
    if kinds <= {"binary"} and len(measures) == 2:
        return _result("mcnemar", {"pre": measures[0], "post": measures[1]}, ["Both measurements are yes/no on the same records."])
    if between:
        return _result("mixed_anova", {"measures": measures, "between": between},
                       [f"The same records were measured {len(measures)} times and compared between {between} groups.",
                        "The Time × group interaction shows whether change differs between groups."],
                       [_alt("ancova", "With two time points: compare the follow-up between groups adjusting for baseline.")])
    if len(measures) == 2:
        pre, post = measures
        paired = df[[pre, post]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(paired) < 3:
            raise SelectionError("Fewer than 3 records have both measurements.")
        if _normal_enough(paired[post] - paired[pre]):
            return _result("paired_ttest", {"pre": pre, "post": post},
                           ["The same records were measured twice, so the change within each record is analysed.",
                            "The change scores are roughly symmetric, so the mean change is tested."],
                           [_alt("wilcoxon", "When the changes are skewed or have outliers.")])
        return _result("wilcoxon", {"pre": pre, "post": post},
                       ["The same records were measured twice.", "The change scores are skewed or have outliers, so a rank-based test is used."],
                       [_alt("paired_ttest", "When the changes are roughly symmetric.")])
    return _result("repeated_measures_anova", {"measures": measures},
                   [f"The same records were measured {len(measures)} times.",
                    "Sphericity is checked (Mauchly) and the Greenhouse-Geisser correction applied when needed.",
                    "Holm-adjusted paired comparisons and a Friedman test are included."])


def _accuracy(df, types, fields):
    _need(fields, "test", "reference")
    _check_columns(df, [fields["test"], fields["reference"]])
    if df[fields["reference"]].dropna().nunique() != 2:
        raise SelectionError("The reference standard must have exactly two values (positive / negative).")
    complete = df[[fields["test"], fields["reference"]]].dropna()
    if complete[fields["reference"]].nunique() != 2:
        raise SelectionError(f"{fields['test']} is only recorded for one reference group (e.g. positives), so accuracy cannot be estimated from it.")
    numeric_test = pd.to_numeric(df[fields["test"]], errors="coerce").notna().mean() > 0.95 and df[fields["test"]].nunique() > 2
    reasons = ["Accuracy is measured against the reference standard: sensitivity, specificity, PPV, NPV and likelihood ratios with 95% CIs."]
    if numeric_test:
        reasons.append("The index test is a number, so the ROC curve, AUC and the best cut-off (Youden) are added.")
    return _result("diagnostic_accuracy", {"test": fields["test"], "reference": fields["reference"]}, reasons)


def _reliability(df, types, fields):
    items = [i for i in fields.get("items") or [] if i]
    if len(items) < 2:
        raise SelectionError("Choose two or more items or rating columns.")
    _check_columns(df, items)
    kinds = {_kind(i, df, types) for i in items}
    if fields.get("mode") == "raters" or kinds <= {"binary", "categorical"}:
        if len(items) == 2:
            return _result("cohens_kappa", {"var1": items[0], "var2": items[1]}, ["Two raters assigned categories to the same records."],
                           [_alt("icc", "If the ratings are numbers.")])
        if kinds <= {"binary", "categorical"}:
            return _result("fleiss_kappa", {"raters": items}, [f"{len(items)} raters assigned categories to the same records."])
        return _result("icc", {"raters": items}, [f"{len(items)} numeric ratings of the same records."])
    return _result("cronbach", {"items": items, "reverse_items": fields.get("reverse_items") or []},
                   [f"{len(items)} questionnaire items measuring one idea.",
                    "Includes McDonald's ω, split-half reliability, item statistics and a check for reverse-worded items."])


def _describe(df, types, fields):
    variables = [{"name": name, "type": types.get(name, "numeric")} for name in (fields.get("variables") or [n for n, t in types.items() if t not in {"id", "text", "date"}])
                 if name in df.columns]
    group = fields.get("group") or None
    return _result("table_one", {"group": group, "variables": variables},
                   [f"Table 1 summarises {len(variables)} variables{' by ' + group if group else ''}: mean (SD) or median [IQR], and n (%)."])


def _one_sample(df, types, fields):
    _need(fields, "variable")
    _check_columns(df, [fields["variable"]])
    value = fields.get("test_value", 0)
    values = pd.to_numeric(df[fields["variable"]], errors="coerce").dropna()
    reasons = [f"Compares the average {fields['variable']} with {value}."]
    warnings = [] if _normal_enough(values) else ["The values are skewed; the Wilcoxon one-sample result is included as a check."]
    return _result("one_sample_ttest", {"variable": fields["variable"], "test_value": value}, reasons, [], warnings)


HANDLERS = {"compare": _compare, "relate": _relate, "predict": _predict, "change": _change, "accuracy": _accuracy,
            "reliability": _reliability, "describe": _describe, "one_sample": _one_sample}


def recommend(df: pd.DataFrame, variables: list[dict], question: str, fields: dict) -> dict:
    if question not in HANDLERS:
        raise SelectionError(f"Unknown question type {question!r}.")
    types = {item["name"]: item.get("type", "numeric") for item in variables if isinstance(item, dict) and item.get("name")}
    for name in df.columns:
        types.setdefault(name, "numeric" if pd.api.types.is_numeric_dtype(df[name]) else "categorical")
    return HANDLERS[question](df, types, fields or {})
