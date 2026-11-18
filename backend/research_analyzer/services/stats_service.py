"""
analyzer/services/stats_service.py
All statistical tests with full assumption checks, effect sizes, and APA text.
"""
from __future__ import annotations

import re
import warnings

import numpy as np
import pandas as pd
import pingouin as pg
import scipy.stats as stats
from scipy.stats import shapiro, levene, mannwhitneyu, kruskal, fisher_exact
import statsmodels.api as sm
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.stats.contingency_tables import mcnemar as statsmodels_mcnemar
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.tools.sm_exceptions import ConvergenceWarning, PerfectSeparationError, PerfectSeparationWarning

MAX_CONTINGENCY_CELLS = 10_000
MAX_REGRESSION_TERMS = 50

# ── Helpers ───────────────────────────────────────────────────────────────────

def _p_fmt(p: float) -> str:
    if p < 0.001:
        return "< .001"
    text = f"{p:.3f}"
    # Never print "p = .050" beside "significant": show one more decimal at the boundary.
    if (p < 0.05) != (float(text) < 0.05):
        text = f"{p:.4f}"
    return f"= {text}".replace("0.", ".", 1)

def _round(v: float | None, d: int = 3) -> float | None:
    """Return a JSON-safe rounded number, never NaN or infinity."""
    if v is None or not np.isfinite(v):
        return None
    return round(float(v), d)


def _correlation_effect_label(value: float) -> str:
    magnitude = abs(value)
    if magnitude < 0.1:
        return "negligible"
    if magnitude < 0.3:
        return "small"
    if magnitude < 0.5:
        return "medium"
    return "large"


def _standardized_mean_effect_label(value: float) -> str:
    magnitude = abs(value)
    if magnitude < 0.2:
        return "negligible"
    if magnitude < 0.5:
        return "small"
    if magnitude < 0.8:
        return "medium"
    return "large"


def _variance_explained_effect_label(value: float, medium: float = 0.06, large: float = 0.14) -> str:
    """Cohen's bands for η²/ω² (.01 / .06 / .14); ε² uses .01 / .08 / .26."""
    if value < 0.01:
        return "negligible"
    if value < medium:
        return "small"
    if value < large:
        return "medium"
    return "large"


def _sorted_levels(values) -> list:
    """Category order that does not depend on row order (numbers numerically, text alphabetically)."""
    levels = list(pd.unique(pd.Series(values).dropna()))
    try:
        return sorted(levels)
    except TypeError:
        return sorted(levels, key=str)


def _category_labels(values) -> pd.Series:
    """Category values as text, with missing values left missing.

    A whole-number column with blanks (a 1–5 score, a 0/1 code) is read as float, so ``str`` would
    print its levels as 1.0, 2.0; they are shown as 1, 2 instead. Real decimals are unchanged.
    """
    series = pd.Series(values)
    whole = False
    if pd.api.types.is_float_dtype(series):
        present = series.dropna()
        whole = not present.empty and bool(np.isfinite(present).all()) and bool((present % 1 == 0).all())
    return series.map(lambda value: value if pd.isna(value) else str(int(value)) if whole else str(value))


def _sorted_labels(values) -> list[str]:
    """``_sorted_levels`` (numbers in numeric order) written as ``_category_labels``."""
    return list(_category_labels(pd.Series(_sorted_levels(values), dtype=pd.Series(values).dtype)))


_EVENT_TOKENS = {"yes", "y", "1", "1.0", "true", "positive", "pos", "present", "event", "case", "died", "dead", "death", "success", "نعم", "إيجابي"}


def _binary_event_level(levels: list[str], requested: str | None = None) -> tuple[str | None, str | None]:
    """Pick which of two outcome levels is the modelled event, independent of row order."""
    if requested is not None:
        requested = str(requested)
        if requested not in levels:
            return None, f"The event value {requested!r} is not one of the outcome categories ({', '.join(levels)})."
        return requested, None
    matches = [level for level in levels if level.strip().lower() in _EVENT_TOKENS]
    if len(matches) == 1:
        return matches[0], None
    return sorted(levels)[1], None


def _grouped_numeric_data(df: pd.DataFrame, outcome_var: str, group_var: str) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    """Return complete-case numeric outcome data grouped without coercing missing labels to strings."""
    data = df[[outcome_var, group_var]].copy()
    data[outcome_var] = pd.to_numeric(data[outcome_var], errors="coerce")
    data = data.dropna(subset=[outcome_var, group_var])
    # Sorted groups keep results (and the "first" group in a t test) independent of row order.
    grouped = {
        str(name): values[outcome_var].to_numpy(dtype=float)
        for name, values in data.groupby(group_var, sort=True)
    }
    return data, grouped


def _group_summary(groups: dict[str, np.ndarray], statistic: str = "mean") -> dict:
    summary = {}
    for name, values in groups.items():
        n = len(values)
        mean = float(np.mean(values))
        sd = float(np.std(values, ddof=1)) if n > 1 else np.nan
        if statistic == "mean" and n > 1:
            critical_t = stats.t.ppf(0.975, n - 1)
            ci_95 = [mean - critical_t * sd / np.sqrt(n), mean + critical_t * sd / np.sqrt(n)]
        else:
            ci_95 = [np.nan, np.nan]
        summary[name] = {
            statistic: _round(mean if statistic == "mean" else np.median(values), 3),
            "sd": _round(sd, 3), "n": int(n),
            "ci_95": [_round(ci_95[0], 3), _round(ci_95[1], 3)],
        }
    return summary

def _normality_check(series: pd.Series) -> dict:
    """Shapiro-Wilk (n ≤ 5000) or D'Agostino-Pearson for larger samples."""
    s = series.dropna().values
    n = len(s)
    if n < 3:
        return {"test": "n/a", "stat": None, "p": None, "passed": None,
                "note": "Sample too small for normality check."}
    if pd.Series(s).nunique() < 2:
        return {"test": "n/a", "stat": None, "p": None, "passed": False,
                "note": "Normality cannot be assessed because all values are identical."}
    if n <= 5000:
        stat, p = shapiro(s)
        test_name = "Shapiro-Wilk"
    else:
        stat, p = stats.normaltest(s)
        test_name = "D'Agostino-Pearson"
    return {"test": test_name, "stat": _round(stat, 3), "p": _round(p, 4),
            "passed": bool(p > 0.05),
            "note": "Normality not violated." if p > 0.05 else "Normality violated — consider non-parametric alternative."}


def assess_parametric_suitability(series: pd.Series) -> dict:
    """Assess whether a mean-based analysis is reasonable without treating normality p as a veto.

    A significant normality test is common in large samples, including distributions that are
    sufficiently symmetric for many mean-based procedures. This helper deliberately combines
    sample size, shape indices, the formal test, and an explicit visual-review reminder.
    """
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    n = len(numeric)
    normality = _normality_check(numeric)
    skewness = float(numeric.skew()) if n >= 3 else np.nan
    kurtosis = float(numeric.kurtosis()) if n >= 4 else np.nan  # excess kurtosis
    shape_reasonable = bool(np.isfinite(skewness) and np.isfinite(kurtosis) and abs(skewness) <= 2 and abs(kurtosis) <= 7)
    outliers = _outlier_check(numeric) if n >= 4 else {"n_outliers": 0, "passed": None, "note": "Too few observations for an IQR outlier screen."}

    if n < 3 or numeric.nunique() < 2:
        supported = None
        decision = "Not enough variation or observations to judge a mean-based analysis."
    elif n >= 100:
        supported = shape_reasonable
        decision = (
            "Large-sample decision: the formal normality p-value is not used on its own. "
            "The Central Limit Theorem, skewness/kurtosis, group sizes, and a histogram/Q–Q plot should guide the choice."
            if supported else
            "Large-sample caution: the sample is large, but the distribution is markedly skewed or heavy-tailed. Review the histogram/Q–Q plot and consider a robust or rank-based sensitivity analysis."
        )
    elif n >= 30:
        supported = bool(normality.get("passed") is True or shape_reasonable)
        decision = (
            "Moderate-sample decision: the shape looks acceptable for a mean-based analysis, but inspect the distribution and influential values."
            if supported else
            "Moderate-sample caution: the formal normality check and distribution shape do not support a simple mean-based analysis; consider a rank-based alternative."
        )
    else:
        supported = bool(normality.get("passed") is True and shape_reasonable)
        decision = (
            "Small-sample decision: the distribution screen supports a mean-based analysis, subject to visual review."
            if supported else
            "Small-sample caution: use a rank-based/exact alternative or justify a robust method unless a visual check is reassuring."
        )

    return {
        "n": int(n),
        "normality_test": normality,
        "skewness": _round(skewness, 3),
        "excess_kurtosis": _round(kurtosis, 3),
        "shape_reasonable": shape_reasonable if n >= 4 else None,
        "outliers": outliers,
        "central_limit_theorem_considered": bool(n >= 100),
        "visual_review_required": True,
        "parametric_supported": supported,
        "recommendation": decision,
    }


def _histogram_bins(series: pd.Series, max_bins: int = 16) -> list[dict]:
    """Compact histogram payload for a truthful client-side distribution view."""
    values = pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype=float)
    if len(values) < 2 or np.all(values == values[0]):
        return []
    bins = min(max_bins, max(5, int(np.sqrt(len(values)))))
    counts, edges = np.histogram(values, bins=bins)
    return [{"from": _round(edges[index], 3), "to": _round(edges[index + 1], 3), "n": int(count)} for index, count in enumerate(counts)]

def _outlier_check(series: pd.Series) -> dict:
    s = series.dropna()
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = s[(s < lower) | (s > upper)]
    return {"n_outliers": int(len(outliers)), "lower_fence": _round(lower), "upper_fence": _round(upper),
            "passed": len(outliers) == 0,
            "note": f"{len(outliers)} outlier(s) detected (IQR method)." if outliers.size else "No outliers detected."}


# ── Descriptive Statistics ────────────────────────────────────────────────────

def descriptive_stats(df: pd.DataFrame, variables: list[dict]) -> dict:
    results = []
    for var in variables:
        col = var["name"]
        vtype = var.get("type", "numeric")
        if col not in df.columns:
            continue

        if vtype in ("numeric", "ordinal", "likert"):
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            if s.empty:
                continue
            n = len(s)
            mean = s.mean()
            sd = s.std(ddof=1) if n > 1 else np.nan
            se = sd / np.sqrt(n) if n > 1 else np.nan
            critical_t = stats.t.ppf(0.975, n - 1) if n > 1 else np.nan
            ci_low = mean - critical_t * se if n > 1 else np.nan
            ci_high = mean + critical_t * se if n > 1 else np.nan
            suitability = assess_parametric_suitability(s)
            recommended_summary = "Mean (SD)" if suitability.get("parametric_supported") else "Median (IQR)"
            shape_text = (
                "The distribution is reasonably symmetric for a mean-based summary."
                if suitability.get("shape_reasonable") else
                "The distribution may be asymmetric; show the median and IQR alongside the mean and SD."
            )
            results.append({
                "variable": col, "type": vtype, "n": n,
                "mean": _round(mean, 2), "sd": _round(sd, 2),
                "median": _round(s.median(), 2), "mode": _round(float(s.mode().iloc[0]), 2) if not s.mode().empty else None,
                "variance": _round(s.var(ddof=1) if n > 1 else np.nan, 3), "min": _round(s.min(), 2), "max": _round(s.max(), 2),
                "range": _round(s.max() - s.min(), 2),
                "q1": _round(s.quantile(0.25), 2), "q3": _round(s.quantile(0.75), 2),
                "iqr": _round(s.quantile(0.75) - s.quantile(0.25), 2),
                "skewness": _round(float(s.skew()) if n >= 3 else np.nan, 3), "kurtosis": _round(float(s.kurtosis()) if n >= 4 else np.nan, 3),
                "ci_95_low": _round(ci_low, 2), "ci_95_high": _round(ci_high, 2),
                "missing": int(df[col].isna().sum()),
                "missing_pct": _round(df[col].isna().mean() * 100, 1),
                "distribution": suitability,
                "histogram": _histogram_bins(s),
                "recommended_summary": recommended_summary,
                "interpretation": f"{col}: {shape_text} {suitability['recommendation']}",
            })
        elif vtype == "categorical":
            s = _category_labels(df[col].dropna())
            freq = s.value_counts()
            pct = (freq / len(s) * 100).round(1)
            results.append({
                "variable": col, "type": "categorical", "n": len(s),
                "frequencies": [{"value": str(k), "n": int(v), "pct": float(pct[k])} for k, v in freq.items()],
                "missing": int(df[col].isna().sum()),
                "missing_pct": _round(df[col].isna().mean() * 100, 1),
                "top_category": str(freq.index[0]) if not freq.empty else None,
                "interpretation": (
                    f"{col}: the most frequently observed category was {freq.index[0]} "
                    f"({int(freq.iloc[0])} of {len(s)}, {float(pct.iloc[0]):.1f}%)."
                    if not freq.empty else f"{col}: no non-missing categories were available."
                ),
            })

    missing_fields = sorted(results, key=lambda item: item.get("missing_pct", 0), reverse=True)
    return {
        "test": "descriptive",
        "results": results,
        "data_quality": {
            "rows": int(len(df)),
            "fields_summarised": int(len(results)),
            "highest_missingness": [
                {"variable": item["variable"], "missing_pct": item.get("missing_pct", 0)}
                for item in missing_fields[:3] if item.get("missing_pct", 0) > 0
            ],
            "note": "All summaries use available observations for that field. Inferential analyses use complete cases for their selected variables.",
        },
    }


# ── Pearson Correlation ───────────────────────────────────────────────────────

def pearson_correlation(df: pd.DataFrame, var1: str, var2: str) -> dict:
    s1 = pd.to_numeric(df[var1], errors="coerce")
    s2 = pd.to_numeric(df[var2], errors="coerce")
    valid = pd.concat([s1, s2], axis=1).dropna()
    n = len(valid)

    if n < 5:
        return {"error": "Insufficient data (n < 5)."}
    if valid.iloc[:, 0].nunique() < 2 or valid.iloc[:, 1].nunique() < 2:
        return {"error": "Both variables must contain at least two distinct numeric values."}

    norm1 = _normality_check(valid.iloc[:, 0])
    norm2 = _normality_check(valid.iloc[:, 1])
    suitability1 = assess_parametric_suitability(valid.iloc[:, 0])
    suitability2 = assess_parametric_suitability(valid.iloc[:, 1])
    out1 = _outlier_check(valid.iloc[:, 0])
    out2 = _outlier_check(valid.iloc[:, 1])
    both_normal = all(item.get("parametric_supported") is not False for item in (suitability1, suitability2))

    r, p = stats.pearsonr(valid.iloc[:, 0], valid.iloc[:, 1])
    r2 = r ** 2
    # Fisher r-to-z CI
    fisher_z = np.arctanh(r)
    se = 1 / np.sqrt(n - 3)
    ci_low = float(np.tanh(fisher_z - 1.96 * se))
    ci_high = float(np.tanh(fisher_z + 1.96 * se))

    effect_label = _correlation_effect_label(r)

    recommend_spearman = not both_normal or out1["n_outliers"] > 0 or out2["n_outliers"] > 0

    apa_en = (
        f"A Pearson correlation was conducted to examine the relationship between {var1} and {var2} "
        f"(n = {n}). There was a {'significant' if p < 0.05 else 'non-significant'} "
        f"{'positive' if r >= 0 else 'negative'} correlation between the two variables, "
        f"r({n - 2}) = {r:.3f}, p {_p_fmt(p)}, 95% CI [{ci_low:.3f}, {ci_high:.3f}]. "
        f"The coefficient of determination indicated that {var1} explained {r2 * 100:.1f}% of "
        f"the variance in {var2} (R² = {r2:.3f})."
    )

    apa_ar = (
        f"أُجري اختبار ارتباط بيرسون لفحص العلاقة بين {var1} و{var2} (ن = {n}). "
        f"أظهرت النتائج {'ارتباطاً دالاً إحصائياً' if p < 0.05 else 'ارتباطاً غير دال'} "
        f"{'موجباً' if r >= 0 else 'سالباً'} بين المتغيرين، "
        f"r({n - 2}) = {r:.3f}، p {_p_fmt(p)}، CI 95% [{ci_low:.3f}، {ci_high:.3f}]. "
        f"أوضح معامل التحديد أن {var1} يُفسّر {r2 * 100:.1f}% من التباين في {var2} (R² = {r2:.3f})."
    )

    return {
        "test": "pearson",
        "variables": [var1, var2],
        "n": n,
        "r": _round(r, 4), "r_squared": _round(r2, 4), "p": _round(p, 4),
        "ci_95": [_round(ci_low, 4), _round(ci_high, 4)],
        "effect_size": effect_label,
        "plot_points": [{"x": _round(row.iloc[0], 4), "y": _round(row.iloc[1], 4)} for _, row in valid.iloc[:500].iterrows()],
        "plot_points_truncated": len(valid) > 500,
        "assumptions": {
            f"normality_{var1}": norm1, f"normality_{var2}": norm2,
            f"parametric_suitability_{var1}": suitability1, f"parametric_suitability_{var2}": suitability2,
            f"outliers_{var1}": out1, f"outliers_{var2}": out2,
            "linearity": {
                "passed": None,
                "note": "Inspect the scatter plot for a linear relationship; this cannot be established from a normality test.",
            },
        },
        "recommend_spearman": recommend_spearman,
        "apa_en": apa_en, "apa_ar": apa_ar,
    }


# ── Spearman / Kendall ────────────────────────────────────────────────────────

def spearman_correlation(df, var1, var2, method="spearman"):
    s1 = pd.to_numeric(df[var1], errors="coerce")
    s2 = pd.to_numeric(df[var2], errors="coerce")
    valid = pd.concat([s1, s2], axis=1).dropna()
    n = len(valid)
    if n < 5:
        return {"error": "Insufficient data."}
    if valid.iloc[:, 0].nunique() < 2 or valid.iloc[:, 1].nunique() < 2:
        return {"error": "Both variables must contain at least two distinct numeric values."}

    if method == "kendall":
        r, p = stats.kendalltau(valid.iloc[:, 0], valid.iloc[:, 1])
        test_name = "Kendall's Tau"
        symbol = "τ"
    else:
        r, p = stats.spearmanr(valid.iloc[:, 0], valid.iloc[:, 1])
        test_name = "Spearman's Rho"
        symbol = "ρ"

    effect_label = _correlation_effect_label(r)

    apa_en = (
        f"A {test_name} rank correlation was computed to assess the relationship between {var1} and {var2}. "
        f"There was a {'statistically significant' if p < 0.05 else 'non-significant'} "
        f"{'positive' if r >= 0 else 'negative'} correlation, {symbol}({n}) = {r:.3f}, p {_p_fmt(p)}. "
        f"The association was characterised as {effect_label} in magnitude."
    )

    apa_ar = (
        f"حُسب معامل ارتباط الرتب ({test_name}) لتقييم العلاقة بين {var1} و{var2}. "
        f"أظهرت النتائج {'ارتباطاً دالاً إحصائياً' if p < 0.05 else 'ارتباطاً غير دال'} "
        f"{'موجباً' if r >= 0 else 'سالباً'}، {symbol}({n}) = {r:.3f}، p {_p_fmt(p)}. "
        f"تُصنَّف قوة الارتباط بأنها {effect_label}."
    )

    return {
        "test": method, "variables": [var1, var2], "n": n,
        "statistic": _round(r, 4), "p": _round(p, 4), "effect_size": effect_label,
        "plot_points": [{"x": _round(row.iloc[0], 4), "y": _round(row.iloc[1], 4)} for _, row in valid.iloc[:500].iterrows()],
        "plot_points_truncated": len(valid) > 500,
        "apa_en": apa_en, "apa_ar": apa_ar,
    }


# ── Independent T-test (Student & Welch) ─────────────────────────────────────

def independent_ttest(df, outcome_var, group_var, equal_var=True):
    _, grouped = _grouped_numeric_data(df, outcome_var, group_var)
    group_names = list(grouped.keys())
    if len(group_names) != 2:
        return {"error": f"T-test requires exactly 2 groups; found {len(group_names)}."}

    g1, g2 = grouped[group_names[0]], grouped[group_names[1]]
    n1, n2 = len(g1), len(g2)
    if n1 < 2 or n2 < 2:
        return {"error": "Each group must have at least 2 observations."}
    if np.std(g1, ddof=1) == 0 and np.std(g2, ddof=1) == 0:
        return {"error": "A t-test cannot be computed because both groups have zero variance."}

    norm1 = _normality_check(pd.Series(g1))
    norm2 = _normality_check(pd.Series(g2))
    suitability1 = assess_parametric_suitability(pd.Series(g1))
    suitability2 = assess_parametric_suitability(pd.Series(g2))
    out1 = _outlier_check(pd.Series(g1))
    out2 = _outlier_check(pd.Series(g2))
    lev_stat, lev_p = levene(g1, g2, center="median")
    equal_var_assumed = lev_p > 0.05

    use_student = equal_var and equal_var_assumed
    test_type = "Student" if use_student else "Welch"
    mean_difference = float(np.mean(g1) - np.mean(g2))
    variance1, variance2 = np.var(g1, ddof=1), np.var(g2, ddof=1)
    if use_student:
        df_val = n1 + n2 - 2
        pooled_variance = ((n1 - 1) * variance1 + (n2 - 1) * variance2) / df_val
        standard_error = np.sqrt(pooled_variance * (1 / n1 + 1 / n2))
    else:
        variance_terms = variance1 / n1 + variance2 / n2
        standard_error = np.sqrt(variance_terms)
        df_val = variance_terms ** 2 / (
            ((variance1 / n1) ** 2 / (n1 - 1)) + ((variance2 / n2) ** 2 / (n2 - 1))
        )

    if standard_error == 0 or not np.isfinite(standard_error):
        return {"error": "A t-test cannot be computed because the standard error is zero or undefined."}

    t = mean_difference / standard_error
    p = 2 * stats.t.sf(abs(t), df_val)
    critical_t = stats.t.ppf(0.975, df_val)
    ci_95 = [mean_difference - critical_t * standard_error, mean_difference + critical_t * standard_error]

    pooled_sd = np.sqrt(((n1 - 1) * variance1 + (n2 - 1) * variance2) / (n1 + n2 - 2))
    cohens_d = mean_difference / pooled_sd if pooled_sd else 0.0
    correction = 1 - (3 / (4 * (n1 + n2) - 9))
    hedges_g = correction * cohens_d
    effect_label = _standardized_mean_effect_label(hedges_g)

    recommend_mwu = any(item.get("parametric_supported") is False for item in (suitability1, suitability2))

    df_text = f"{df_val:.0f}" if use_student else f"{df_val:.2f}"
    lev_note = (f"Levene's test did not indicate unequal variances (p {_p_fmt(lev_p)})."
                if equal_var_assumed else f"Welch's correction was used because Levene's test indicated unequal variances (p {_p_fmt(lev_p)}).")
    apa_en = (
        f"An independent-samples {test_type} t-test was conducted to compare {outcome_var} "
        f"between {group_names[0]} (M = {np.mean(g1):.2f}, SD = {np.std(g1, ddof=1):.2f}, n = {n1}) "
        f"and {group_names[1]} (M = {np.mean(g2):.2f}, SD = {np.std(g2, ddof=1):.2f}, n = {n2}). "
        f"{'A ' if p < 0.05 else 'No '}significant difference was found; "
        f"t({df_text}) = {t:.3f}, p {_p_fmt(p)}, Hedges' g = {hedges_g:.3f} "
        f"({effect_label} effect), 95% CI for the mean difference [{ci_95[0]:.3f}, {ci_95[1]:.3f}]. "
        f"{lev_note}"
    )

    apa_ar = (
        f"أُجري اختبار t للعينات المستقلة ({test_type}) لمقارنة {outcome_var} "
        f"بين {group_names[0]} (م = {np.mean(g1):.2f}، ع = {np.std(g1, ddof=1):.2f}، ن = {n1}) "
        f"و{group_names[1]} (م = {np.mean(g2):.2f}، ع = {np.std(g2, ddof=1):.2f}، ن = {n2}). "
        f"{'أظهرت النتائج فرقاً داّلاً إحصائياً' if p < 0.05 else 'لم يكن الفرق داّلاً إحصائياً'}؛ "
        f"t({df_text}) = {t:.3f}، p {_p_fmt(p)}، g لهيدجز = {hedges_g:.3f} "
        f"(حجم أثر {effect_label})، وفاصل الثقة 95% لفرق المتوسط [{ci_95[0]:.3f}، {ci_95[1]:.3f}]."
    )

    return {
        "test": f"ttest_{test_type.lower()}", "outcome": outcome_var, "grouping": group_var, "n": int(n1 + n2),
        "groups": _group_summary(grouped),
        "t": _round(t, 4), "df": _round(df_val, 3), "p": _round(p, 4),
        "mean_difference": _round(mean_difference, 4), "ci_95": [_round(ci_95[0], 4), _round(ci_95[1], 4)],
        "cohens_d": _round(cohens_d, 4), "hedges_g": _round(hedges_g, 4), "effect_size": effect_label,
        "assumptions": {
            "normality_g1": norm1, "normality_g2": norm2,
            "parametric_suitability_g1": suitability1,
            "parametric_suitability_g2": suitability2,
            "outliers_g1": out1, "outliers_g2": out2,
            "levene": {"stat": _round(lev_stat, 3), "p": _round(lev_p, 3),
                       "equal_var_assumed": equal_var_assumed},
        },
        "recommend_mwu": recommend_mwu,
        "apa_en": apa_en, "apa_ar": apa_ar,
    }


# ── Mann-Whitney U ────────────────────────────────────────────────────────────

def mann_whitney_u(df, outcome_var, group_var):
    _, grouped_mwu = _grouped_numeric_data(df, outcome_var, group_var)
    gnames = list(grouped_mwu.keys())
    if len(gnames) != 2:
        return {"error": "Mann-Whitney U requires exactly 2 groups."}
    g1, g2 = grouped_mwu[gnames[0]], grouped_mwu[gnames[1]]
    if len(g1) == 0 or len(g2) == 0:
        return {"error": "Each group must have at least one numeric observation."}
    u, p = mannwhitneyu(g1, g2, alternative="two-sided", method="auto")

    # Rank-biserial correlation preserves the direction of the group difference.
    rank_biserial = (2 * u / (len(g1) * len(g2))) - 1
    n = len(g1) + len(g2)
    tie_counts = pd.Series(np.concatenate([g1, g2])).value_counts().to_numpy()
    tie_correction = np.sum(tie_counts ** 3 - tie_counts)
    variance_u = (len(g1) * len(g2) / 12) * ((n + 1) - tie_correction / (n * (n - 1)))
    z = (u - (len(g1) * len(g2) / 2)) / np.sqrt(variance_u) if variance_u > 0 else np.nan
    r = abs(z) / np.sqrt(n) if np.isfinite(z) else np.nan
    effect_label = _correlation_effect_label(rank_biserial)

    apa_en = (
        f"A Mann-Whitney U test indicated that {outcome_var} scores "
        f"{'differed significantly' if p < 0.05 else 'did not differ significantly'} "
        f"between {gnames[0]} and {gnames[1]}, U = {u:.1f}, p {_p_fmt(p)}, "
        f"rank-biserial r = {rank_biserial:.3f} ({effect_label} effect)."
    )
    apa_ar = (
        f"أظهر اختبار مان-ويتني U أن درجات {outcome_var} "
        f"{'تختلف اختلافاً داّلاً إحصائياً' if p < 0.05 else 'لا تختلف بشكل دال'} "
        f"بين {gnames[0]} و{gnames[1]}، U = {u:.1f}، p {_p_fmt(p)}، "
        f"r ثنائي الرتبة = {rank_biserial:.3f} (حجم أثر {effect_label})."
    )

    return {
        "test": "mann_whitney_u", "outcome": outcome_var, "grouping": group_var,
        "groups": _group_summary(grouped_mwu, statistic="median"),
        "u": _round(u, 1), "p": _round(p, 4), "r": _round(r, 4),
        "rank_biserial": _round(rank_biserial, 4), "effect_size": effect_label,
        "apa_en": apa_en, "apa_ar": apa_ar,
    }


# ── Paired / Pre-post analyses ──────────────────────────────────────────────

def _paired_numeric_data(df: pd.DataFrame, pre_var: str, post_var: str) -> pd.DataFrame:
    """Return matched numeric pairs in their original participant order."""
    data = df[[pre_var, post_var]].copy()
    data[pre_var] = pd.to_numeric(data[pre_var], errors="coerce")
    data[post_var] = pd.to_numeric(data[post_var], errors="coerce")
    return data.dropna()


def paired_ttest(df, pre_var: str, post_var: str):
    if pre_var == post_var:
        return {"error": "Choose two different measurements for a paired t-test."}
    data = _paired_numeric_data(df, pre_var, post_var)
    n = len(data)
    if n < 3:
        return {"error": "A paired t-test requires at least 3 complete paired observations."}

    differences = data[post_var] - data[pre_var]
    if differences.nunique() < 2:
        return {"error": "A paired t-test cannot be computed because every change score is identical."}

    t_stat, p = stats.ttest_rel(data[post_var], data[pre_var])
    df_val = n - 1
    mean_difference = float(differences.mean())
    sd_difference = float(differences.std(ddof=1))
    se = sd_difference / np.sqrt(n)
    critical_t = stats.t.ppf(0.975, df_val)
    ci_95 = [mean_difference - critical_t * se, mean_difference + critical_t * se]
    cohens_dz = mean_difference / sd_difference if sd_difference else 0.0
    correction = 1 - (3 / (4 * n - 5)) if n > 2 else 1.0
    hedges_gz = correction * cohens_dz
    effect_label = _standardized_mean_effect_label(hedges_gz)
    normality = _normality_check(differences)
    suitability = assess_parametric_suitability(differences)
    outliers = _outlier_check(differences)

    apa_en = (
        f"A paired-samples t-test compared {pre_var} with {post_var} for {n} matched observations. "
        f"The average change (post − pre) was {mean_difference:.3f}. "
        f"The change was {'statistically significant' if p < 0.05 else 'not statistically significant'}, "
        f"t({df_val}) = {t_stat:.3f}, p {_p_fmt(p)}, Hedges' g_z = {hedges_gz:.3f} "
        f"({effect_label} effect), 95% CI [{ci_95[0]:.3f}, {ci_95[1]:.3f}]."
    )
    apa_ar = (
        f"قارن اختبار t للعينات المترابطة بين {pre_var} و{post_var} لدى {n} ملاحظة مترابطة. "
        f"كان متوسط التغير (بعد − قبل) = {mean_difference:.3f}. "
        f"كان التغير {'دالاً إحصائياً' if p < 0.05 else 'غير دال إحصائياً'}، "
        f"t({df_val}) = {t_stat:.3f}، p {_p_fmt(p)}، g_z لهيدجز = {hedges_gz:.3f} "
        f"(حجم أثر {effect_label})، وفاصل الثقة 95% [{ci_95[0]:.3f}، {ci_95[1]:.3f}]."
    )
    return {
        "test": "paired_ttest", "pre": pre_var, "post": post_var, "n": n,
        "means": {"pre": _round(data[pre_var].mean(), 3), "post": _round(data[post_var].mean(), 3)},
        "t": _round(t_stat, 4), "df": df_val, "p": _round(p, 4),
        "mean_difference": _round(mean_difference, 4), "ci_95": [_round(ci_95[0], 4), _round(ci_95[1], 4)],
        "cohens_dz": _round(cohens_dz, 4), "hedges_gz": _round(hedges_gz, 4), "effect_size": effect_label,
        "assumptions": {"normality_of_change": normality, "parametric_suitability_of_change": suitability, "outliers_in_change": outliers},
        "recommend_wilcoxon": suitability.get("parametric_supported") is False,
        "apa_en": apa_en, "apa_ar": apa_ar,
    }


def wilcoxon_signed_rank(df, pre_var: str, post_var: str):
    if pre_var == post_var:
        return {"error": "Choose two different measurements for a Wilcoxon signed-rank test."}
    data = _paired_numeric_data(df, pre_var, post_var)
    differences = (data[post_var] - data[pre_var]).to_numpy(dtype=float)
    nonzero = differences[differences != 0]
    if len(nonzero) < 5:
        return {"error": "Wilcoxon signed-rank requires at least 5 non-zero paired differences."}

    result = stats.wilcoxon(nonzero, alternative="two-sided", zero_method="wilcox", method="auto")
    ranks = stats.rankdata(np.abs(nonzero))
    positive_ranks = float(ranks[nonzero > 0].sum())
    negative_ranks = float(ranks[nonzero < 0].sum())
    total_rank = len(nonzero) * (len(nonzero) + 1) / 2
    rank_biserial = (positive_ranks - negative_ranks) / total_rank
    tie_counts = pd.Series(np.abs(nonzero)).value_counts().to_numpy()
    variance = (len(nonzero) * (len(nonzero) + 1) * (2 * len(nonzero) + 1) / 24
                - np.sum(tie_counts ** 3 - tie_counts) / 48)
    z = (positive_ranks - len(nonzero) * (len(nonzero) + 1) / 4) / np.sqrt(variance) if variance > 0 else np.nan
    effect_r = abs(z) / np.sqrt(len(nonzero)) if np.isfinite(z) else np.nan
    effect_label = _correlation_effect_label(rank_biserial)
    median_change = float(np.median(nonzero))
    p = float(result.pvalue)

    apa_en = (
        f"A Wilcoxon signed-rank test compared {pre_var} with {post_var} for {len(nonzero)} non-zero paired differences. "
        f"The median change (post − pre) was {median_change:.3f}. The result was "
        f"{'statistically significant' if p < 0.05 else 'not statistically significant'}, "
        f"W = {result.statistic:.3f}, p {_p_fmt(p)}, rank-biserial r = {rank_biserial:.3f} ({effect_label} effect)."
    )
    apa_ar = (
        f"قارن اختبار ويلكوكسون للرتب الموقعة بين {pre_var} و{post_var} لدى {len(nonzero)} فرق مترابط غير صفري. "
        f"كان وسيط التغير (بعد − قبل) = {median_change:.3f}. كانت النتيجة "
        f"{'دالة إحصائياً' if p < 0.05 else 'غير دالة إحصائياً'}، "
        f"W = {result.statistic:.3f}، p {_p_fmt(p)}، r ثنائي الرتبة = {rank_biserial:.3f} (حجم أثر {effect_label})."
    )
    return {
        "test": "wilcoxon_signed_rank", "pre": pre_var, "post": post_var, "n": int(len(data)),
        "n_nonzero": int(len(nonzero)), "median_change": _round(median_change, 4),
        "w": _round(result.statistic, 4), "p": _round(p, 4), "rank_biserial": _round(rank_biserial, 4),
        "r": _round(effect_r, 4), "effect_size": effect_label,
        "assumptions": {"paired_observations": {"passed": True, "note": "Rows were analysed as matched pairs; zero differences are excluded by the Wilcoxon convention."}},
        "apa_en": apa_en, "apa_ar": apa_ar,
    }


def mcnemar_test(df, pre_var: str, post_var: str):
    if pre_var == post_var:
        return {"error": "Choose two different binary measurements for McNemar's test."}
    data = df[[pre_var, post_var]].dropna().astype(str)
    categories = list(dict.fromkeys([*data[pre_var].tolist(), *data[post_var].tolist()]))
    if len(categories) != 2:
        return {"error": "McNemar's test requires exactly two categories in the paired measurements."}
    table = pd.crosstab(data[pre_var], data[post_var]).reindex(index=categories, columns=categories, fill_value=0)
    discordant = int(table.iloc[0, 1] + table.iloc[1, 0])
    if discordant == 0:
        return {"error": "McNemar's test cannot be computed because no participants changed category."}
    use_exact = discordant < 25
    result = statsmodels_mcnemar(table.to_numpy(), exact=use_exact, correction=not use_exact)
    p = float(result.pvalue)
    b, c = int(table.iloc[0, 1]), int(table.iloc[1, 0])
    paired_odds = b / c if c else None
    method_note = "exact binomial McNemar test" if use_exact else "continuity-corrected McNemar chi-square test"
    apa_en = (
        f"A {method_note} assessed whether the paired binary responses changed from {pre_var} to {post_var}. "
        f"The result was {'statistically significant' if p < 0.05 else 'not statistically significant'}, "
        f"statistic = {result.statistic:.3f}, p {_p_fmt(p)} (n = {len(data)}, discordant pairs = {discordant})."
    )
    apa_ar = (
        f"فحص اختبار مكنمار {'الدقيق' if use_exact else 'مع تصحيح الاستمرارية'} تغير الاستجابات الثنائية المترابطة من {pre_var} إلى {post_var}. "
        f"كانت النتيجة {'دالة إحصائياً' if p < 0.05 else 'غير دالة إحصائياً'}، "
        f"الإحصاء = {result.statistic:.3f}، p {_p_fmt(p)} (ن = {len(data)}، الأزواج المختلفة = {discordant})."
    )
    return {
        "test": "mcnemar", "pre": pre_var, "post": post_var, "n": int(len(data)),
        "categories": categories, "contingency_table": table.to_dict(), "statistic": _round(result.statistic, 4),
        "p": _round(p, 4), "discordant_pairs": discordant, "b": b, "c": c,
        "paired_odds_ratio": _round(paired_odds, 4) if paired_odds is not None else None,
        "method": method_note, "apa_en": apa_en, "apa_ar": apa_ar,
    }


# ── Regression ───────────────────────────────────────────────────────────────

def _build_predictor_matrix(
    raw: pd.DataFrame, predictors: list[str], categorical_predictors: list[str] | None = None,
    reference_levels: dict | None = None,
) -> tuple[pd.DataFrame | None, dict, str | None]:
    """Create an interpretable dummy-coded predictor matrix and retain reference categories."""
    categorical_predictors = list(dict.fromkeys(categorical_predictors or []))
    unknown = set(categorical_predictors) - set(predictors)
    if unknown:
        return None, {}, "Categorical predictors must also be included in the predictor list."

    matrix = pd.DataFrame(index=raw.index)
    specification = {"numeric_predictors": [], "categorical_predictors": [], "reference_categories": {}}
    for predictor in predictors:
        if predictor in categorical_predictors:
            values = raw[predictor].astype(str)
            levels = [str(level) for level in _sorted_levels(raw[predictor])]
            if len(levels) < 2:
                return None, {}, f"{predictor!r} has only one observed category in the complete-case data."
            if len(levels) > MAX_REGRESSION_TERMS:
                return None, {}, f"{predictor!r} has too many categories for regression. Combine rare categories before analysis."
            requested_reference = (reference_levels or {}).get(predictor)
            if requested_reference is not None and str(requested_reference) not in levels:
                return None, {}, f"Reference category {requested_reference!r} is not a value of {predictor!r}."
            reference = str(requested_reference) if requested_reference is not None else levels[0]
            ordered = pd.Categorical(values, categories=[reference, *[level for level in levels if level != reference]])
            dummies = pd.get_dummies(ordered, prefix=predictor, prefix_sep=" [", drop_first=True, dtype=float)
            dummies.index = raw.index
            dummies.columns = [f"{column}]" for column in dummies.columns]
            matrix = pd.concat([matrix, dummies], axis=1)
            specification["categorical_predictors"].append(predictor)
            specification["reference_categories"][predictor] = reference
        else:
            numeric = pd.to_numeric(raw[predictor], errors="coerce")
            if numeric.nunique(dropna=True) < 2:
                return None, {}, f"{predictor!r} must contain at least two distinct numeric values."
            matrix[predictor] = numeric
            specification["numeric_predictors"].append(predictor)
        if matrix.shape[1] > MAX_REGRESSION_TERMS:
            return None, {}, f"Regression is limited to {MAX_REGRESSION_TERMS} encoded predictor terms. Reduce predictors or combine categories."
    matrix = matrix.replace([np.inf, -np.inf], np.nan).dropna()
    if matrix.empty:
        return None, {}, "No complete observations were available for the selected predictors."
    return matrix.astype(float), specification, None


def _linear_regression_data(
    df: pd.DataFrame, outcome_var: str, predictors: list[str], categorical_predictors: list[str] | None = None,
    reference_levels: dict | None = None,
) -> tuple[pd.Series | None, pd.DataFrame | None, dict, str | None]:
    if not predictors:
        return None, None, {}, "Choose at least one predictor."
    if outcome_var in predictors:
        return None, None, {}, "The outcome cannot also be a predictor."
    requested = [outcome_var, *predictors]
    if any(column not in df.columns for column in requested):
        return None, None, {}, "One or more selected variables are not in this dataset."
    raw = df[requested].dropna().copy()
    outcome = pd.to_numeric(raw[outcome_var], errors="coerce")
    features, specification, error = _build_predictor_matrix(raw, predictors, categorical_predictors, reference_levels)
    if error:
        return None, None, {}, error
    joined = pd.concat([outcome.rename("_outcome"), features], axis=1).dropna()
    if joined.empty or joined["_outcome"].nunique() < 2:
        return None, None, {}, "The continuous outcome needs at least two distinct complete values."
    specification["outcome"] = outcome_var
    specification["original_predictors"] = predictors
    return joined["_outcome"], joined.drop(columns="_outcome"), specification, None


def _vif_rows(features: pd.DataFrame) -> list[dict]:
    if features.shape[1] < 2:
        return [{"predictor": features.columns[0], "vif": 1.0}]
    # VIF must be computed with an intercept in the design matrix; without one, predictors with
    # large means (age, BMI, blood pressure) show huge false VIFs.
    values = sm.add_constant(features, has_constant="add").to_numpy(dtype=float)
    rows = []
    for index, column in enumerate(features.columns, start=1):
        try:
            with np.errstate(divide="ignore", invalid="ignore"):
                value = variance_inflation_factor(values, index)
        except (np.linalg.LinAlgError, ValueError):
            value = np.inf
        rows.append({"predictor": column, "vif": _round(value, 3)})
    return rows


def linear_regression(df, outcome_var: str, predictors: list[str], categorical_predictors: list[str] | None = None,
                      reference_levels: dict | None = None):
    outcome, features, specification, error = _linear_regression_data(df, outcome_var, predictors, categorical_predictors, reference_levels)
    if error:
        return {"error": error}
    if len(features) < max(12, features.shape[1] + 5):
        return {"error": "Too few complete observations for the requested linear regression model."}
    x = sm.add_constant(features, has_constant="add")
    model = sm.OLS(outcome, x).fit()
    coefficients = []
    for term in model.params.index:
        ci_low, ci_high = model.conf_int().loc[term]
        standardised = None if term == "const" else model.params[term] * (features[term].std(ddof=1) / outcome.std(ddof=1))
        coefficients.append({
            "term": "Intercept" if term == "const" else term, "b": _round(model.params[term], 4),
            "se": _round(model.bse[term], 4), "t": _round(model.tvalues[term], 4), "p": _round(model.pvalues[term], 4),
            "ci_95": [_round(ci_low, 4), _round(ci_high, 4)],
            "standardized_beta": _round(standardised, 4),
        })
    residuals = pd.Series(model.resid)
    normality = assess_parametric_suitability(residuals)
    vif = _vif_rows(features)
    high_vif = any(row["vif"] is None or row["vif"] >= 5 for row in vif)
    try:
        bp_stat, bp_p, _, _ = het_breuschpagan(model.resid, x)
    except (ValueError, np.linalg.LinAlgError):
        bp_stat, bp_p = np.nan, np.nan
    cooks_distance = model.get_influence().cooks_distance[0]
    cook_threshold = 4 / len(features)
    influential = int(np.sum(cooks_distance > cook_threshold))
    durbin_watson = sm.stats.stattools.durbin_watson(model.resid)
    p = float(model.f_pvalue)
    apa_en = (
        f"A multiple linear regression predicted {outcome_var} from {', '.join(predictors)} (n = {len(features)}). "
        f"The model was {'statistically significant' if p < 0.05 else 'not statistically significant'}, "
        f"F({model.df_model:.0f}, {model.df_resid:.0f}) = {model.fvalue:.3f}, p {_p_fmt(p)}, "
        f"R² = {model.rsquared:.3f}, adjusted R² = {model.rsquared_adj:.3f}."
    )
    apa_ar = (
        f"تنبأ انحدار خطي متعدد بـ {outcome_var} من {', '.join(predictors)} (ن = {len(features)}). "
        f"كان النموذج {'دالاً إحصائياً' if p < 0.05 else 'غير دال إحصائياً'}، "
        f"F({model.df_model:.0f}، {model.df_resid:.0f}) = {model.fvalue:.3f}، p {_p_fmt(p)}، "
        f"R² = {model.rsquared:.3f}، R² المعدل = {model.rsquared_adj:.3f}."
    )
    return {
        "test": "linear_regression", "outcome": outcome_var, "predictors": predictors, "n": int(len(features)),
        "model_specification": specification,
        "r_squared": _round(model.rsquared, 4), "adjusted_r_squared": _round(model.rsquared_adj, 4),
        "f": _round(model.fvalue, 4), "df_model": _round(model.df_model, 3), "df_resid": _round(model.df_resid, 3),
        "p": _round(p, 4), "coefficients": coefficients, "vif": vif,
        "model_fit": {"aic": _round(model.aic, 3), "bic": _round(model.bic, 3), "rmse": _round(np.sqrt(np.mean(model.resid ** 2)), 3)},
        "residual_diagnostics": {
            "durbin_watson": _round(durbin_watson, 3),
            "breusch_pagan": {"stat": _round(bp_stat, 3), "p": _round(bp_p, 4), "passed": None if not np.isfinite(bp_p) else bool(bp_p > 0.05)},
            "influential_cases": {"n": influential, "threshold": _round(cook_threshold, 4), "note": "Cook's distance flags observations worth checking; it does not automatically justify deletion."},
            "residual_points": [{"fitted": _round(fitted, 4), "residual": _round(residual, 4)} for fitted, residual in zip(model.fittedvalues.iloc[:500], model.resid.iloc[:500])],
        },
        "assumptions": {
            "residual_distribution": normality,
            "multicollinearity": {"passed": not high_vif, "note": "No VIF was 5 or higher." if not high_vif else "One or more VIF values are 5 or higher; coefficients may be unstable."},
        },
        "recommendations": [
            "Review residual-versus-fitted values for curvature or a changing spread.",
            "Interpret adjusted coefficients as associations conditional on the selected model, not proof of causation.",
            "Report confidence intervals and the model fit alongside individual p-values.",
        ],
        "apa_en": apa_en, "apa_ar": apa_ar,
    }


def _separating_predictor(features: pd.DataFrame, outcome: pd.Series) -> bool:
    """True when one predictor alone splits events from non-events (odds ratio would be infinite)."""
    events = outcome.to_numpy() == 1
    for column in features.columns:
        values = features[column].to_numpy(dtype=float)
        with_event, without_event = values[events], values[~events]
        if with_event.min() >= without_event.max() or with_event.max() <= without_event.min():
            return True
    return False


def logistic_regression(df, outcome_var: str, predictors: list[str], categorical_predictors: list[str] | None = None,
                        event_level: str | None = None, reference_levels: dict | None = None):
    if not predictors:
        return {"error": "Choose at least one predictor."}
    if outcome_var in predictors or outcome_var not in df.columns or any(column not in df.columns for column in predictors):
        return {"error": "Check the selected outcome and predictor variables."}
    raw = df[[outcome_var, *predictors]].copy().dropna()
    levels = [str(level) for level in _sorted_levels(raw[outcome_var])]
    if len(levels) != 2:
        return {"error": "Logistic regression requires an outcome with exactly two categories."}
    event, error = _binary_event_level(levels, event_level)
    if error:
        return {"error": error}
    # categories[1] is the modelled event, categories[0] the reference, whatever the row order.
    categories = [next(level for level in levels if level != event), event]
    features, specification, error = _build_predictor_matrix(raw, predictors, categorical_predictors, reference_levels)
    if error:
        return {"error": error}
    y = (raw[outcome_var].astype(str) == categories[1]).astype(int)
    data = pd.concat([y.rename("_outcome"), features], axis=1).dropna()
    events = int(data["_outcome"].sum())
    non_events = int(len(data) - events)
    if len(data) < 10 or min(events, non_events) < 3:
        return {"error": "Logistic regression needs at least 10 complete records and at least 3 observations in each outcome category."}
    if data.drop(columns="_outcome").shape[1] == 0:
        return {"error": "No usable predictors remained after coding the selected variables."}
    separation_error = {"error": (
        "Logistic regression cannot give trustworthy odds ratios here: a predictor (almost) perfectly separates "
        f"{categories[1]!r} from {categories[0]!r}. Combine categories, remove that predictor, or use Fisher's exact test."
    ), "code": "perfect_separation"}
    if _separating_predictor(data.drop(columns="_outcome"), data["_outcome"]):
        return separation_error
    try:
        with warnings.catch_warnings(), np.errstate(over="ignore", divide="ignore", invalid="ignore"):
            warnings.simplefilter("error", PerfectSeparationWarning)
            warnings.simplefilter("ignore", ConvergenceWarning)
            warnings.simplefilter("ignore", RuntimeWarning)
            model = sm.Logit(data["_outcome"], sm.add_constant(data.drop(columns="_outcome"), has_constant="add")).fit(disp=0, maxiter=100)
    except (PerfectSeparationWarning, PerfectSeparationError):
        return separation_error
    except (np.linalg.LinAlgError, ValueError) as exc:
        return {"error": f"Logistic regression could not be fitted: {exc}"}
    fitted_probability = np.asarray(model.predict())
    quasi_separated = (
        not model.mle_retvals.get("converged", True)
        or not np.all(np.isfinite(model.bse))
        or np.any(np.abs(model.params.drop("const", errors="ignore")) > 15)
        or np.mean((fitted_probability < 1e-6) | (fitted_probability > 1 - 1e-6)) > 0.5
    )
    if quasi_separated:
        return separation_error
    coefficients = []
    for term in model.params.index:
        ci_low, ci_high = model.conf_int().loc[term]
        coefficients.append({
            "term": "Intercept" if term == "const" else term, "b": _round(model.params[term], 4),
            "se": _round(model.bse[term], 4), "z": _round(model.tvalues[term], 4), "p": _round(model.pvalues[term], 4),
            "ci_95": [_round(ci_low, 4), _round(ci_high, 4)], "odds_ratio": _round(np.exp(model.params[term]), 4),
            "or_ci_95": [_round(np.exp(ci_low), 4), _round(np.exp(ci_high), 4)],
        })
    feature_data = data.drop(columns="_outcome")
    vif = _vif_rows(feature_data)
    high_vif = any(row["vif"] is None or row["vif"] >= 5 for row in vif)
    p = float(model.llr_pvalue)
    events_per_predictor = min(events, non_events) / feature_data.shape[1]
    probability = model.predict(sm.add_constant(feature_data, has_constant="add"))
    predicted = (probability >= 0.5).astype(int)
    true_positive = int(((predicted == 1) & (data["_outcome"] == 1)).sum())
    true_negative = int(((predicted == 0) & (data["_outcome"] == 0)).sum())
    false_positive = int(((predicted == 1) & (data["_outcome"] == 0)).sum())
    false_negative = int(((predicted == 0) & (data["_outcome"] == 1)).sum())
    apa_en = (
        f"A binary logistic regression predicted {outcome_var} ({categories[1]} versus {categories[0]}) from {', '.join(predictors)} "
        f"(n = {len(data)}). The likelihood-ratio model test was {'statistically significant' if p < 0.05 else 'not statistically significant'}, "
        f"χ²({model.df_model:.0f}) = {model.llr:.3f}, p {_p_fmt(p)}, McFadden R² = {model.prsquared:.3f}."
    )
    apa_ar = (
        f"تنبأ انحدار لوجستي ثنائي بـ {outcome_var} ({categories[1]} مقابل {categories[0]}) من {', '.join(predictors)} "
        f"(ن = {len(data)}). كان اختبار نسبة الاحتمال للنموذج {'دالاً إحصائياً' if p < 0.05 else 'غير دال إحصائياً'}، "
        f"χ²({model.df_model:.0f}) = {model.llr:.3f}، p {_p_fmt(p)}، R² لماكفادن = {model.prsquared:.3f}."
    )
    return {
        "test": "logistic_regression", "outcome": outcome_var, "outcome_reference": categories[0], "outcome_event": categories[1],
        "predictors": predictors, "n": int(len(data)), "events": events, "non_events": non_events,
        "model_specification": {**specification, "outcome": outcome_var, "original_predictors": predictors},
        "pseudo_r_squared": _round(model.prsquared, 4), "chi2": _round(model.llr, 4), "df_model": _round(model.df_model, 3),
        "p": _round(p, 4), "coefficients": coefficients, "vif": vif,
        "model_fit": {
            "aic": _round(model.aic, 3), "bic": _round(model.bic, 3), "brier_score": _round(np.mean((data["_outcome"] - probability) ** 2), 4),
            "accuracy": _round((true_positive + true_negative) / len(data), 3),
            "sensitivity": _round(true_positive / events if events else np.nan, 3),
            "specificity": _round(true_negative / non_events if non_events else np.nan, 3),
            "classification_table": {"true_positive": true_positive, "true_negative": true_negative, "false_positive": false_positive, "false_negative": false_negative},
        },
        "assumptions": {
            "events_per_predictor": {"passed": events_per_predictor >= 10, "note": f"Smaller outcome class has {events_per_predictor:.1f} observations per predictor; 10 or more is a common stability target."},
            "multicollinearity": {"passed": not high_vif, "note": "No VIF was 5 or higher." if not high_vif else "One or more VIF values are 5 or higher; coefficients may be unstable."},
        },
        "recommendations": [
            "Check that the outcome coding and reference category match the research question before reporting odds ratios.",
            "Treat classification accuracy as descriptive; assess calibration and external validation before clinical prediction use.",
            "Interpret odds ratios as adjusted associations, not causal effects, unless the study design supports causal inference.",
        ],
        "apa_en": apa_en, "apa_ar": apa_ar,
    }


# ── One-Way ANOVA ─────────────────────────────────────────────────────────────

def one_way_anova(df, outcome_var, group_var):
    data, grp_data = _grouped_numeric_data(df, outcome_var, group_var)
    groups = list(grp_data.values())
    gnames = list(grp_data.keys())

    if len(groups) < 3:
        return {"error": "ANOVA requires 3 or more groups."}
    if any(len(g) < 2 for g in groups):
        return {"error": "Each group must have at least 2 observations."}

    f, p = stats.f_oneway(*groups)
    # Eta-squared and omega-squared quantify the proportion of variance explained.
    grand_mean = np.concatenate(groups).mean()
    ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in groups)
    ss_total = sum(((v - grand_mean) ** 2).sum() for v in groups)
    eta2 = ss_between / ss_total if ss_total else 0
    df_between = len(groups) - 1
    df_within = sum(len(g) for g in groups) - len(groups)
    ms_within = (ss_total - ss_between) / df_within if df_within else np.nan
    omega2 = max(0.0, (ss_between - df_between * ms_within) / (ss_total + ms_within)) if ss_total and np.isfinite(ms_within) else 0.0
    # ω² is the less biased estimate, so it sets the label.
    effect_label = _variance_explained_effect_label(omega2)

    # Levene's for equal variance
    lev_stat, lev_p = levene(*groups, center="median")
    norm_checks = {gnames[i]: _normality_check(pd.Series(g)) for i, g in enumerate(groups)}
    suitability_checks = {gnames[i]: assess_parametric_suitability(pd.Series(g)) for i, g in enumerate(groups)}
    all_normal = all(check.get("parametric_supported") is not False for check in suitability_checks.values())

    # Tukey HSD is used only when the standard ANOVA assumptions support it.
    posthoc = []
    posthoc_method = None
    if p < 0.05 and lev_p > 0.05:
        tukey = pairwise_tukeyhsd(data[outcome_var], data[group_var].astype(str))
        for group1, group2, mean_difference, p_adjusted, lower, upper, significant in tukey._results_table.data[1:]:
            posthoc.append({
                "group1": str(group1), "group2": str(group2),
                "mean_difference": _round(mean_difference, 3),
                "ci_95": [_round(lower, 3), _round(upper, 3)],
                "p_adjusted": _round(p_adjusted, 4), "significant": bool(significant),
            })
        posthoc_method = "Tukey HSD"

    apa_en = (
        f"A one-way ANOVA examined the effect of {group_var} on {outcome_var}. "
        f"The result was {'statistically significant' if p < 0.05 else 'not statistically significant'}, "
        f"F({df_between}, {df_within}) = {f:.3f}, "
        f"p {_p_fmt(p)}, η² = {eta2:.3f}, ω² = {omega2:.3f} ({effect_label} effect)."
    )
    apa_ar = (
        f"أُجري تحليل التباين أحادي الاتجاه لفحص تأثير {group_var} على {outcome_var}. "
        f"كانت النتيجة {'دالة إحصائياً' if p < 0.05 else 'غير دالة إحصائياً'}، "
        f"F({df_between}، {df_within}) = {f:.3f}، "
        f"p {_p_fmt(p)}، η² = {eta2:.3f}، ω² = {omega2:.3f} (حجم أثر {effect_label})."
    )

    return {
        "test": "anova", "outcome": outcome_var, "grouping": group_var,
        "groups": _group_summary(grp_data),
        "f": _round(f, 4), "df_between": df_between, "df_within": df_within, "p": _round(p, 4),
        "eta_squared": _round(eta2, 4), "omega_squared": _round(omega2, 4),
        "effect_size": effect_label,
        "assumptions": {"levene": {"stat": _round(lev_stat, 3), "p": _round(lev_p, 3),
                                    "equal_var_assumed": lev_p > 0.05},
                        "normality": norm_checks,
                        "parametric_suitability": suitability_checks},
        "posthoc": posthoc, "posthoc_method": posthoc_method,
        "recommend_welch_anova": lev_p <= 0.05,
        "recommend_kruskal": not all_normal,
        "apa_en": apa_en, "apa_ar": apa_ar,
    }


def welch_anova(df, outcome_var, group_var):
    """Welch's ANOVA with Games-Howell post-hoc comparisons when appropriate."""
    data, grouped = _grouped_numeric_data(df, outcome_var, group_var)
    if len(grouped) < 3:
        return {"error": "Welch's ANOVA requires 3 or more groups."}
    if any(len(values) < 2 for values in grouped.values()):
        return {"error": "Each group must have at least 2 observations."}

    analysis = pg.welch_anova(data=data, dv=outcome_var, between=group_var).iloc[0]
    f = float(analysis["F"])
    p = float(analysis["p_unc"])
    df_between = float(analysis["ddof1"])
    df_within = float(analysis["ddof2"])
    eta2 = float(analysis["np2"])
    effect_label = _variance_explained_effect_label(eta2)

    posthoc = []
    if p < 0.05:
        games_howell = pg.pairwise_gameshowell(data=data, dv=outcome_var, between=group_var)
        for _, row in games_howell.iterrows():
            posthoc.append({
                "group1": str(row["A"]), "group2": str(row["B"]),
                "mean_difference": _round(row["diff"], 3),
                "p_adjusted": _round(row["pval"], 4),
                "hedges_g": _round(row["hedges"], 3),
                "significant": bool(row["pval"] < 0.05),
            })

    apa_en = (
        f"A Welch one-way ANOVA examined differences in {outcome_var} across {group_var} groups. "
        f"The result was {'statistically significant' if p < 0.05 else 'not statistically significant'}, "
        f"F({df_between:.0f}, {df_within:.2f}) = {f:.3f}, p {_p_fmt(p)}, η² = {eta2:.3f} ({effect_label} effect)."
    )
    apa_ar = (
        f"أُجري تحليل تباين ويلش أحادي الاتجاه لفحص الفروق في {outcome_var} بين مجموعات {group_var}. "
        f"كانت النتيجة {'دالة إحصائياً' if p < 0.05 else 'غير دالة إحصائياً'}، "
        f"F({df_between:.0f}، {df_within:.2f}) = {f:.3f}، p {_p_fmt(p)}، η² = {eta2:.3f} (حجم أثر {effect_label})."
    )
    return {
        "test": "welch_anova", "outcome": outcome_var, "grouping": group_var,
        "groups": _group_summary(grouped), "f": _round(f, 4),
        "df_between": _round(df_between, 3), "df_within": _round(df_within, 3),
        "p": _round(p, 4), "eta_squared": _round(eta2, 4), "effect_size": effect_label,
        "posthoc": posthoc, "posthoc_method": "Games-Howell" if posthoc else None,
        "assumptions": {"variance": {"passed": False, "note": "Welch's ANOVA does not assume equal group variances."}},
        "apa_en": apa_en, "apa_ar": apa_ar,
    }


# ── Kruskal-Wallis ────────────────────────────────────────────────────────────

def kruskal_wallis(df, outcome_var, group_var):
    _, grp_data = _grouped_numeric_data(df, outcome_var, group_var)
    gnames, groups = list(grp_data.keys()), list(grp_data.values())
    if len(groups) < 3:
        return {"error": "Kruskal-Wallis requires 3 or more groups."}
    if any(len(group) < 2 for group in groups):
        return {"error": "Each group must have at least 2 numeric observations."}

    h, p = kruskal(*groups)
    n_total = sum(len(g) for g in groups)
    epsilon_squared = max(0.0, (h - len(groups) + 1) / (n_total - len(groups)))
    effect_label = _variance_explained_effect_label(epsilon_squared, medium=0.08, large=0.26)

    apa_en = (
        f"A Kruskal-Wallis H test was conducted to examine differences in {outcome_var} across {group_var} groups. "
        f"The test {'revealed a statistically significant' if p < 0.05 else 'did not reveal a significant'} difference, "
        f"H({len(groups) - 1}) = {h:.3f}, p {_p_fmt(p)}, ε² = {epsilon_squared:.3f} ({effect_label} effect)."
    )
    apa_ar = (
        f"أُجري اختبار كروسكال-واليس لفحص الفروق في {outcome_var} بين مجموعات {group_var}. "
        f"{'أظهر الاختبار فروقاً دالة إحصائياً' if p < 0.05 else 'لم يُظهر الاختبار فروقاً دالة'}، "
        f"H({len(groups) - 1}) = {h:.3f}، p {_p_fmt(p)}، ε² = {epsilon_squared:.3f} (حجم أثر {effect_label})."
    )

    return {
        "test": "kruskal_wallis", "outcome": outcome_var, "grouping": group_var,
        "groups": _group_summary(grp_data, statistic="median"),
        "h": _round(h, 4), "p": _round(p, 4), "epsilon_squared": _round(epsilon_squared, 4),
        "effect_size": effect_label,
        "apa_en": apa_en, "apa_ar": apa_ar,
    }


# ── Chi-Square & Fisher's Exact ───────────────────────────────────────────────

def chi_square(df, var1, var2):
    data = df[[var1, var2]].dropna()
    levels_1 = int(data[var1].nunique(dropna=True))
    levels_2 = int(data[var2].nunique(dropna=True))
    if levels_1 * levels_2 > MAX_CONTINGENCY_CELLS:
        return {"error": "The contingency table is too large. Combine rare categories before running chi-square."}
    ct = pd.crosstab(_category_labels(data[var1]), _category_labels(data[var2]))
    if ct.shape[0] < 2 or ct.shape[1] < 2:
        return {"error": "Chi-square requires at least two non-missing categories in each variable."}
    chi2, chi_p, dof, expected = stats.chi2_contingency(ct, correction=(ct.shape == (2, 2)))
    n = ct.values.sum()

    # Cramér's V uses the uncorrected χ²; Yates' correction is only for the 2×2 p-value.
    min_dim = min(ct.shape) - 1
    chi2_uncorrected = stats.chi2_contingency(ct, correction=False)[0]
    cramer_v = float(np.sqrt(chi2_uncorrected / (n * min_dim))) if min_dim > 0 else 0
    effect_label = _correlation_effect_label(cramer_v)

    # Expected cell count assumption
    cells_below_5 = int((expected < 5).sum())
    cells_below_1 = int((expected < 1).sum())
    pct_below_5 = round(cells_below_5 / expected.size * 100, 1)
    chi_square_valid = cells_below_1 == 0 and pct_below_5 <= 20

    # For sparse 2×2 tables, Fisher's exact test is the primary inferential result.
    can_fisher = ct.shape == (2, 2)
    fisher_result = None
    preferred_test = "chi_square"
    p = chi_p
    if can_fisher and cells_below_5 > 0:
        odds_r, fisher_p = fisher_exact(ct.values)
        fisher_result = {"odds_ratio": _round(odds_r, 4), "p": _round(fisher_p, 4)}
        preferred_test = "fisher_exact"
        p = fisher_p

    if preferred_test == "fisher_exact":
        apa_en = (
            f"Fisher's exact test examined the association between {var1} and {var2}. "
            f"The association was {'statistically significant' if p < 0.05 else 'not significant'}, "
            f"odds ratio = {odds_r:.3f}, p {_p_fmt(p)}, Cramér's V = {cramer_v:.3f} ({effect_label} effect, N = {n})."
        )
        apa_ar = (
            f"فحص اختبار فيشر الدقيق العلاقة بين {var1} و{var2}. "
            f"كانت العلاقة {'دالة إحصائياً' if p < 0.05 else 'غير دالة'}، "
            f"نسبة الأرجحية = {odds_r:.3f}، p {_p_fmt(p)}، V لكرامر = {cramer_v:.3f} (حجم أثر {effect_label}، N = {n})."
        )
    else:
        apa_en = (
            f"A chi-square test of independence examined the association between {var1} and {var2}. "
            f"The association was {'statistically significant' if p < 0.05 else 'not significant'}, "
            f"χ²({dof}) = {chi2:.3f}, p {_p_fmt(p)}, Cramér's V = {cramer_v:.3f} ({effect_label} effect, N = {n})."
        )
        apa_ar = (
            f"أُجري اختبار كاي-تربيع للاستقلالية لفحص العلاقة بين {var1} و{var2}. "
            f"كانت العلاقة {'دالة إحصائياً' if p < 0.05 else 'غير دالة'}، "
            f"χ²({dof}) = {chi2:.3f}، p {_p_fmt(p)}، V لكرامر = {cramer_v:.3f} (حجم أثر {effect_label}، N = {n})."
        )

    return {
        "test": "chi_square", "variables": [var1, var2],
        "chi2": _round(chi2, 4), "dof": dof, "p": _round(p, 4), "chi_square_p": _round(chi_p, 4),
        "cramer_v": _round(cramer_v, 4), "effect_size": effect_label, "n": int(n),
        "contingency_table": ct.to_dict(),
        "expected_table": pd.DataFrame(expected, index=ct.index, columns=ct.columns).round(2).to_dict(),
        "assumption_check": {"cells_below_1": cells_below_1, "cells_below_5": cells_below_5, "pct_below_5": pct_below_5,
                              "passed": chi_square_valid, "violated": not chi_square_valid},
        "fisher_exact": fisher_result, "preferred_test": preferred_test,
        "apa_en": apa_en, "apa_ar": apa_ar,
    }


# ── Cronbach's Alpha ──────────────────────────────────────────────────────────

def cronbach_alpha(df, item_columns: list[str], reverse_items: list[str] | None = None) -> dict:
    reverse_items = reverse_items or []
    if not set(reverse_items).issubset(item_columns):
        return {"error": "Reverse-scored items must also be selected as scale items."}
    data = df[item_columns].apply(pd.to_numeric, errors="coerce").dropna()
    n_items = len(item_columns)
    if n_items < 2:
        return {"error": "At least 2 items are required for Cronbach's Alpha."}
    if len(data) < 5:
        return {"error": "Insufficient observations."}

    for column in reverse_items:
        minimum, maximum = data[column].min(), data[column].max()
        if minimum == maximum:
            return {"error": f"Reverse scoring cannot be applied to {column!r} because it has no variation."}
        data[column] = minimum + maximum - data[column]

    k = n_items
    item_variances = data.var(axis=0, ddof=1)
    total_variance = data.sum(axis=1).var(ddof=1)
    if not np.isfinite(total_variance) or total_variance <= 0:
        return {"error": "Cronbach's Alpha cannot be computed because the total score has no variance."}
    alpha = (k / (k - 1)) * (1 - item_variances.sum() / total_variance)
    _, alpha_ci = pg.cronbach_alpha(data=data, ci=0.95)

    # Item-total correlations and alpha-if-deleted
    item_stats = []
    for col in item_columns:
        rest = data.drop(columns=[col]).sum(axis=1)
        r_it, _ = stats.pearsonr(data[col], rest) if rest.nunique() > 1 and data[col].nunique() > 1 else (np.nan, np.nan)
        # Alpha if deleted
        sub = data.drop(columns=[col])
        k2 = k - 1
        iv2 = sub.var(axis=0, ddof=1)
        tv2 = sub.sum(axis=1).var(ddof=1)
        alpha_if_del = (k2 / (k2 - 1)) * (1 - iv2.sum() / tv2) if k2 > 1 and tv2 else None
        item_stats.append({"item": col, "mean": _round(data[col].mean(), 3),
                            "sd": _round(data[col].std(), 3),
                            "item_total_r": _round(r_it, 3),
                            "alpha_if_deleted": _round(alpha_if_del, 3) if alpha_if_del is not None else None})

    interp = ("unacceptable (α < .60)" if alpha < 0.6
               else "questionable (.60–.69)" if alpha < 0.7
               else "acceptable (.70–.79)" if alpha < 0.8
               else "good (.80–.89)" if alpha < 0.9
               else "excellent (α ≥ .90)")

    apa_en = (
        f"Cronbach's alpha was calculated to assess the internal consistency of the {k}-item scale. "
        f"The scale demonstrated {interp} internal consistency, α = {alpha:.3f}, "
        f"95% CI [{alpha_ci[0]:.3f}, {alpha_ci[1]:.3f}] (n = {len(data)})."
    )
    apa_ar = (
        f"حُسب معامل ألفا كرونباخ لتقييم الاتساق الداخلي للمقياس المكوّن من {k} فقرات. "
        f"أظهر المقياس اتساقاً داخلياً {interp}، α = {alpha:.3f}، "
        f"وفاصل الثقة 95% [{alpha_ci[0]:.3f}، {alpha_ci[1]:.3f}] (ن = {len(data)})."
    )

    return {
        "test": "cronbach_alpha", "items": item_columns, "reverse_items": reverse_items, "n": len(data), "k": k,
        "alpha": _round(alpha, 4), "alpha_ci_95": [_round(alpha_ci[0], 4), _round(alpha_ci[1], 4)], "interpretation": interp,
        "item_statistics": item_stats,
        "apa_en": apa_en, "apa_ar": apa_ar,
    }


# ── Demographic Table ─────────────────────────────────────────────────────────

def demographic_table(df, variables: list[dict]) -> dict:
    rows = []
    for var in variables:
        col = var["name"]
        vtype = var.get("type", "numeric")
        if col not in df.columns:
            continue

        if vtype in ("numeric", "ordinal"):
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            rows.append({"variable": col, "type": "continuous",
                         "summary": f"M = {s.mean():.2f}, SD = {s.std():.2f}",
                         "n": len(s), "missing": int(df[col].isna().sum()),
                         "sub_rows": []})
        elif vtype in ("categorical", "likert"):
            s = _category_labels(df[col].dropna())
            freq = s.value_counts()
            pct = (freq / len(s) * 100).round(1)
            sub_rows = [{"label": str(k), "n": int(freq[k]), "pct": float(pct[k])} for k in freq.index]
            rows.append({"variable": col, "type": "categorical",
                         "summary": "", "n": len(s),
                         "missing": int(df[col].isna().sum()), "sub_rows": sub_rows})

    return {"test": "demographic_table", "table": rows, "total_n": len(df)}


# ── Role-led analysis plan / automatic master report ─────────────────────────

_PLAN_NUMERIC_TYPES = {"numeric", "ordinal", "likert"}


def build_analysis_plan(df: pd.DataFrame, variables: list[dict]) -> dict:
    """Create a conservative plan from researcher-confirmed roles.

    This purposefully does *not* test every possible column pairing. The plan only uses fields
    the researcher has assigned an analysis role, and records why a method is selected or held
    back. It is therefore a report assistant, not an uncontrolled p-value generator.
    """
    # Context-only fields should still be described in a report, but they should not drive
    # automatic inferential test selection. Keep those two purposes separate.
    reportable = [
        v for v in variables
        if v.get("name") in df.columns
        and v.get("role") not in {"identifier", "ignore"}
        and v.get("type") not in {"id", "text", "date"}
    ]
    usable = [v for v in reportable if v.get("role") != "unspecified"]
    by_role: dict[str, list[dict]] = {}
    for variable in usable:
        by_role.setdefault(variable.get("role", "unspecified"), []).append(variable)

    numeric_types = {"numeric", "ordinal", "likert"}
    numeric_outcomes = [v for v in by_role.get("outcome", []) if v.get("type") in numeric_types]
    categorical_outcomes = [v for v in by_role.get("outcome", []) if v.get("type") == "categorical"]
    # A study arm is the comparison of interest, so it goes first when several groupings exist.
    groups = sorted(by_role.get("grouping", []), key=lambda v: not re.search(r"arm|treat|interven|alloc|group", v["name"], re.I))
    predictors = by_role.get("predictor", []) + by_role.get("covariate", [])
    # Adjusted models must include the main comparison (e.g. the treatment arm), not only covariates.
    if predictors and groups and all(v["name"] != groups[0]["name"] for v in predictors):
        predictors = [{**groups[0], "type": "categorical" if groups[0].get("type") not in _PLAN_NUMERIC_TYPES else groups[0]["type"]}, *predictors]
    scale_items = by_role.get("scale_item", [])
    pre_measures = by_role.get("pre_measure", [])
    post_measures = by_role.get("post_measure", [])

    entries: list[dict] = [{
        "id": "descriptive", "test": "descriptive", "purpose": "Describe the sample, missingness, and distribution of each analysis field before inference.",
        "variables": [v["name"] for v in reportable], "params": {"variables": [{"name": v["name"], "type": v.get("type", "numeric")} for v in reportable]},
        "decision": "Always included as the first stage of a complete report.", "alternatives": [],
    }]
    categorical_fields = [v for v in reportable if v.get("type") in {"categorical", "ordinal", "likert"}]
    if categorical_fields:
        entries.append({
            "id": "demographics", "test": "demographic", "purpose": "Create a publication-ready table of participant and field characteristics.",
            "variables": [v["name"] for v in reportable], "params": {"variables": [{"name": v["name"], "type": v.get("type", "numeric")} for v in reportable]},
            "decision": "Included because the dataset contains categorical or ordered fields.", "alternatives": [],
        })

    if len(scale_items) >= 2:
        entries.append({
            "id": "reliability", "test": "cronbach", "purpose": "Assess internal consistency of the researcher-confirmed questionnaire scale.",
            "variables": [v["name"] for v in scale_items], "params": {"items": [v["name"] for v in scale_items], "reverse_items": []},
            "decision": "Two or more questionnaire items were confirmed. Reverse scoring is not guessed and must be specified separately.", "alternatives": [],
        })

    if pre_measures and post_measures:
        pre, post = pre_measures[0], post_measures[0]
        if pre.get("type") in numeric_types and post.get("type") in numeric_types:
            paired = _paired_numeric_data(df, pre["name"], post["name"])
            suitability = assess_parametric_suitability(paired[post["name"]] - paired[pre["name"]]) if len(paired) >= 3 else None
            chosen = "paired_ttest" if suitability and suitability.get("parametric_supported") is not False else "wilcoxon"
            entries.append({
                "id": "paired_change", "test": chosen, "purpose": "Estimate change between matched before and after measurements from the same records.",
                "variables": [pre["name"], post["name"]], "params": {"pre": pre["name"], "post": post["name"]},
                "decision": "Paired t-test selected after the change-score distribution screen." if chosen == "paired_ttest" else "Wilcoxon selected because the change-score screen does not support a simple mean-based test.",
                "alternatives": ["wilcoxon" if chosen == "paired_ttest" else "paired_ttest"], "readiness": suitability,
            })

    if groups:
        group = groups[0]
        group_levels = int(df[group["name"]].dropna().nunique())
        for outcome in numeric_outcomes:
            _, grouped = _grouped_numeric_data(df, outcome["name"], group["name"])
            if len(grouped) < 2:
                continue
            suitability = {name: assess_parametric_suitability(pd.Series(values)) for name, values in grouped.items()}
            parametric_ok = all(item.get("parametric_supported") is not False for item in suitability.values())
            values = list(grouped.values())
            variance_p = float(levene(*values, center="median").pvalue) if len(values) >= 2 and all(len(value) >= 2 for value in values) else np.nan
            if group_levels == 2:
                chosen = "ttest" if parametric_ok else "mann_whitney"
                alternatives = ["mann_whitney"] if chosen == "ttest" else ["ttest"]
                if chosen == "ttest" and np.isfinite(variance_p) and variance_p <= 0.05:
                    chosen, alternatives = "welch", ["mann_whitney", "ttest"]
                decision = "Mean-based comparison supported by the distribution screen." if chosen in {"ttest", "welch"} else "Rank-based comparison selected because at least one group needs a distribution-robust analysis."
            else:
                chosen = "anova" if parametric_ok else "kruskal"
                alternatives = ["kruskal"] if chosen == "anova" else ["anova"]
                if chosen == "anova" and np.isfinite(variance_p) and variance_p <= 0.05:
                    chosen, alternatives = "welch_anova", ["kruskal", "anova"]
                decision = "Mean-based multi-group comparison supported by the distribution screen." if chosen in {"anova", "welch_anova"} else "Kruskal-Wallis selected because at least one group needs a distribution-robust analysis."
            entries.append({
                "id": f"group_{outcome['name']}", "test": chosen,
                "purpose": f"Compare {outcome['name']} across the researcher-confirmed {group['name']} groups.",
                "variables": [outcome["name"], group["name"]], "params": {"outcome": outcome["name"], "group": group["name"]},
                "decision": decision, "alternatives": alternatives,
                "readiness": {"group_count": group_levels, "variance_p": _round(variance_p, 4), "parametric_suitability": suitability},
            })

        for outcome in categorical_outcomes:
            if group_levels >= 2:
                entries.append({
                    "id": f"categorical_{outcome['name']}", "test": "chi_square",
                    "purpose": f"Assess the association between {outcome['name']} and the researcher-confirmed grouping variable {group['name']}.",
                    "variables": [outcome["name"], group["name"]], "params": {"var1": outcome["name"], "var2": group["name"]},
                    "decision": "The result will switch to Fisher's exact test for sparse 2×2 expected counts.", "alternatives": [],
                })

    if predictors:
        predictor_names = [v["name"] for v in predictors]
        categorical_predictors = [v["name"] for v in predictors if v.get("type") == "categorical"]
        numeric_predictors = [v for v in predictors if v.get("type") in numeric_types]
        # A focused bivariate association is useful when one outcome and one exposure are named.
        # We do not automatically create every pairwise correlation in a wide dataset.
        if len(numeric_outcomes) == 1 and len(numeric_predictors) == 1:
            outcome, predictor = numeric_outcomes[0], numeric_predictors[0]
            suitability_outcome = assess_parametric_suitability(pd.to_numeric(df[outcome["name"]], errors="coerce"))
            suitability_predictor = assess_parametric_suitability(pd.to_numeric(df[predictor["name"]], errors="coerce"))
            selected = "pearson" if all(item.get("parametric_supported") is not False for item in (suitability_outcome, suitability_predictor)) else "spearman"
            entries.append({
                "id": f"association_{outcome['name']}_{predictor['name']}", "test": selected,
                "purpose": f"Describe the association between the confirmed outcome {outcome['name']} and predictor {predictor['name']}.",
                "variables": [outcome["name"], predictor["name"]], "params": {"var1": outcome["name"], "var2": predictor["name"]},
                "decision": "Pearson selected after the distribution screen." if selected == "pearson" else "Spearman selected because a rank-based association is more robust for the observed distributions.",
                "alternatives": ["spearman"] if selected == "pearson" else ["pearson"],
                "readiness": {"outcome": suitability_outcome, "predictor": suitability_predictor},
            })
        for outcome in numeric_outcomes:
            entries.append({
                "id": f"linear_{outcome['name']}", "test": "linear_regression",
                "purpose": f"Model adjusted associations with {outcome['name']} while reporting fit, residual, and collinearity diagnostics.",
                "variables": [outcome["name"], *predictor_names],
                "params": {"outcome": outcome["name"], "predictors": predictor_names, "categorical_predictors": categorical_predictors},
                "decision": "Selected because a continuous outcome and researcher-confirmed predictors/covariates are available.", "alternatives": [],
            })
        for outcome in categorical_outcomes:
            if int(df[outcome["name"]].dropna().nunique()) == 2:
                entries.append({
                    "id": f"logistic_{outcome['name']}", "test": "logistic_regression",
                    "purpose": f"Model adjusted odds of the binary outcome {outcome['name']} with discrimination and stability checks.",
                    "variables": [outcome["name"], *predictor_names],
                    "params": {"outcome": outcome["name"], "predictors": predictor_names, "categorical_predictors": categorical_predictors},
                    "decision": "Selected because the confirmed outcome has two observed categories.", "alternatives": [],
                })

    omissions = []
    if not numeric_outcomes and not categorical_outcomes:
        omissions.append("No outcome has been confirmed, so no outcome-focused comparison or regression is proposed.")
    if not groups:
        omissions.append("No grouping/study-arm field has been confirmed, so no independent-group comparison is proposed.")
    if not predictors:
        omissions.append("No predictor or covariate has been confirmed, so no adjusted regression model is proposed.")

    return {
        "sample_size": int(len(df)), "entries": entries, "omissions": omissions,
        "role_summary": {role: [v["name"] for v in fields] for role, fields in by_role.items()},
        "method_note": "Formal normality tests are combined with sample size, skewness, kurtosis, visual review, and Central Limit Theorem guidance. They are not used as a single automatic veto in large samples.",
    }


def run_analysis_plan(df: pd.DataFrame, variables: list[dict]) -> tuple[dict, list[dict]]:
    plan = build_analysis_plan(df, variables)
    executed = []
    for entry in plan["entries"]:
        result = run_test(entry["test"], df, entry["params"])
        executed.append({**entry, "result": result, "status": "completed" if "error" not in result else "not_run"})
    return plan, executed


# ── Test dispatcher ───────────────────────────────────────────────────────────

def run_test(test_name: str, df: pd.DataFrame, params: dict) -> dict:
    # The engine registry holds the extended versions of these tests plus the advanced methods;
    # the table below remains the fallback for internal names the registry does not list.
    from research_analyzer.engine import registry

    if registry.BY_ID.get(registry.ALIASES.get(test_name, test_name)) is not None:
        try:
            result = registry.run(test_name, df, params)
        except KeyError as exc:
            return {"error": f"Missing required parameter: {exc}"}
        except Exception as exc:
            return {"error": f"Analysis failed: {exc}"}
        return _with_n(result)
    dispatch = {
        "descriptive": lambda: descriptive_stats(df, params.get("variables", [])),
        "pearson": lambda: pearson_correlation(df, params["var1"], params["var2"]),
        "spearman": lambda: spearman_correlation(df, params["var1"], params["var2"], "spearman"),
        "kendall": lambda: spearman_correlation(df, params["var1"], params["var2"], "kendall"),
        "ttest": lambda: independent_ttest(df, params["outcome"], params["group"], equal_var=True),
        "welch": lambda: independent_ttest(df, params["outcome"], params["group"], equal_var=False),
        "mann_whitney": lambda: mann_whitney_u(df, params["outcome"], params["group"]),
        "paired_ttest": lambda: paired_ttest(df, params["pre"], params["post"]),
        "wilcoxon": lambda: wilcoxon_signed_rank(df, params["pre"], params["post"]),
        "mcnemar": lambda: mcnemar_test(df, params["pre"], params["post"]),
        "anova": lambda: one_way_anova(df, params["outcome"], params["group"]),
        "welch_anova": lambda: welch_anova(df, params["outcome"], params["group"]),
        "kruskal": lambda: kruskal_wallis(df, params["outcome"], params["group"]),
        "chi_square": lambda: chi_square(df, params["var1"], params["var2"]),
        "cronbach": lambda: cronbach_alpha(df, params["items"], params.get("reverse_items", [])),
        "linear_regression": lambda: linear_regression(df, params["outcome"], params["predictors"], params.get("categorical_predictors", []),
                                                       params.get("reference_levels")),
        "logistic_regression": lambda: logistic_regression(df, params["outcome"], params["predictors"], params.get("categorical_predictors", []),
                                                           params.get("event_level"), params.get("reference_levels")),
        "demographic": lambda: demographic_table(df, params.get("variables", [])),
    }
    fn = dispatch.get(test_name)
    if fn is None:
        return {"error": f"Unknown test: {test_name}"}
    try:
        result = fn()
    except KeyError as exc:
        return {"error": f"Missing required parameter: {exc}"}
    except Exception as exc:
        return {"error": f"Analysis failed: {exc}"}
    return _with_n(result)


def _with_n(result):
    # Every result reports the number of records it used, so the page never shows "—".
    if isinstance(result, dict) and "error" not in result and result.get("n") is None:
        if isinstance(result.get("groups"), dict):
            result["n"] = int(sum(group.get("n", 0) for group in result["groups"].values()))
        elif result.get("total_n") is not None:
            result["n"] = int(result["total_n"])
    return result
