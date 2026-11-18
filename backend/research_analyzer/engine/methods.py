"""Additional and extended analyses for the Research Analyzer.

Every function takes the session DataFrame plus plain parameters and returns a JSON-ready dict with
the same conventions as ``services.stats_service``: ``test``, ``n``, the statistics, ``effect_size``
labels, ``assumptions`` / ``checks``, and ``apa_en`` / ``apa_ar`` write-ups. Errors are returned as
``{"error": message}`` so the API can show them to the researcher.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pingouin as pg
import scipy.stats as stats
import statsmodels.api as sm

from research_analyzer.services import stats_service as base
from research_analyzer.services.stats_service import _p_fmt, _round

Z95 = stats.norm.ppf(0.975)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce")


def _require_columns(df: pd.DataFrame, columns) -> str | None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        return f"Not in this dataset: {', '.join(map(str, missing))}."
    return None


def _wilson(successes: int, total: int) -> tuple[float, float]:
    """Wilson score 95% interval for a proportion (good coverage for small samples)."""
    if total == 0:
        return (np.nan, np.nan)
    p = successes / total
    denominator = 1 + Z95 ** 2 / total
    centre = (p + Z95 ** 2 / (2 * total)) / denominator
    half = Z95 * np.sqrt(p * (1 - p) / total + Z95 ** 2 / (4 * total ** 2)) / denominator
    return (max(0.0, centre - half), min(1.0, centre + half))


def _holm(p_values: list[float]) -> list[float]:
    """Holm step-down adjusted p-values (keeps input order)."""
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    adjusted = np.empty_like(p)
    running = 0.0
    m = len(p)
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[index]))
        adjusted[index] = running
    return adjusted.tolist()


def _ci(values, digits=3):
    return [_round(values[0], digits), _round(values[1], digits)]


def _two_levels(series: pd.Series, preferred: str | None, label: str) -> tuple[list[str] | None, str | None, str | None]:
    """Return (levels, chosen, error) for a binary variable, choosing the event/positive level."""
    levels = [str(level) for level in base._sorted_levels(series.astype(str))]
    if len(levels) != 2:
        return None, None, f"{label} must have exactly two categories (found {len(levels)})."
    chosen, error = base._binary_event_level(levels, preferred)
    return levels, chosen, error


def _significance_word(p: float) -> tuple[str, str]:
    return ("statistically significant", "دالة إحصائياً") if p < 0.05 else ("not statistically significant", "غير دالة إحصائياً")


# ── One-sample tests ──────────────────────────────────────────────────────────

def one_sample_ttest(df: pd.DataFrame, variable: str, test_value: float = 0.0) -> dict:
    error = _require_columns(df, [variable])
    if error:
        return {"error": error}
    try:
        mu = float(test_value)
    except (TypeError, ValueError):
        return {"error": "The comparison value must be a number."}
    values = _numeric(df, variable).dropna().to_numpy(dtype=float)
    n = len(values)
    if n < 3:
        return {"error": "At least 3 numeric values are needed for a one-sample test."}
    sd = values.std(ddof=1)
    if sd == 0:
        return {"error": "All values are identical, so the test cannot be computed."}
    result = stats.ttest_1samp(values, mu)
    difference = values.mean() - mu
    se = sd / np.sqrt(n)
    critical = stats.t.ppf(0.975, n - 1)
    d = difference / sd
    g = d * (1 - 3 / (4 * (n - 1) - 1))
    suitability = base.assess_parametric_suitability(pd.Series(values))
    wilcoxon = stats.wilcoxon(values - mu) if np.any(values != mu) else None
    p = float(result.pvalue)
    sig_en, sig_ar = _significance_word(p)
    return {
        "test": "one_sample_ttest", "variables": [variable], "n": n, "test_value": mu,
        "mean": _round(values.mean(), 4), "sd": _round(sd, 4), "mean_difference": _round(difference, 4),
        "ci_95": _ci([difference - critical * se, difference + critical * se], 4),
        "t": _round(result.statistic, 4), "df": n - 1, "p": _round(p, 4),
        "hedges_g": _round(g, 4), "effect_size": base._standardized_mean_effect_label(g),
        "assumptions": {"parametric_suitability": suitability},
        "alternative": {"test": "Wilcoxon signed-rank (one sample)", "statistic": _round(wilcoxon.statistic, 3) if wilcoxon else None,
                        "p": _round(wilcoxon.pvalue, 4) if wilcoxon else None},
        "apa_en": (f"A one-sample t test compared the mean {variable} (M = {values.mean():.2f}, SD = {sd:.2f}, n = {n}) with {mu:g}. "
                   f"The difference of {difference:.2f} (95% CI {difference - critical * se:.2f} to {difference + critical * se:.2f}) was {sig_en}, "
                   f"t({n - 1}) = {result.statistic:.2f}, p {_p_fmt(p)}, Hedges' g = {g:.2f}."),
        "apa_ar": (f"قارن اختبار (ت) لعينة واحدة متوسط {variable} (م = {values.mean():.2f}، ع = {sd:.2f}، ن = {n}) بالقيمة {mu:g}. "
                   f"كان الفرق {difference:.2f} (فترة ثقة 95%: {difference - critical * se:.2f} إلى {difference + critical * se:.2f}) {sig_ar}، "
                   f"t({n - 1}) = {result.statistic:.2f}، p {_p_fmt(p)}، g لهيدجز = {g:.2f}."),
    }


# ── 2×2 tables: risks, risk difference, risk ratio, odds ratio ────────────────

def two_by_two(df: pd.DataFrame, outcome: str, group: str, event_level: str | None = None, reference_group: str | None = None) -> dict:
    """Event proportions by group with RD (Newcombe), RR and OR (log CIs), Fisher and chi-square p-values."""
    error = _require_columns(df, [outcome, group])
    if error:
        return {"error": error}
    data = df[[outcome, group]].dropna().astype(str)
    outcome_levels, event, error = _two_levels(data[outcome], event_level, "The outcome")
    if error:
        return {"error": error}
    group_levels = [str(level) for level in base._sorted_levels(data[group])]
    if len(group_levels) != 2:
        return {"error": f"Risk ratios need exactly two groups (found {len(group_levels)}). Use the chi-square test instead."}
    if reference_group is not None and str(reference_group) not in group_levels:
        return {"error": f"Reference group {reference_group!r} is not a value of {group!r}."}
    reference = str(reference_group) if reference_group is not None else group_levels[0]
    exposed = next(level for level in group_levels if level != reference)

    def counts(level):
        rows = data[data[group] == level]
        return int((rows[outcome] == event).sum()), int(len(rows))

    a, n1 = counts(exposed)
    c, n0 = counts(reference)
    b, d = n1 - a, n0 - c
    if min(n1, n0) == 0:
        return {"error": "Each group needs at least one record."}
    p1, p0 = a / n1, c / n0
    rd = p1 - p0
    l1, u1 = _wilson(a, n1)
    l0, u0 = _wilson(c, n0)
    rd_ci = (rd - np.sqrt((p1 - l1) ** 2 + (u0 - p0) ** 2), rd + np.sqrt((u1 - p1) ** 2 + (p0 - l0) ** 2))

    zero_cell = 0 in (a, b, c, d)
    aa, bb, cc, dd = (x + 0.5 for x in (a, b, c, d)) if zero_cell else (a, b, c, d)
    rr = (aa / (aa + bb)) / (cc / (cc + dd))
    rr_se = np.sqrt(1 / aa - 1 / (aa + bb) + 1 / cc - 1 / (cc + dd))
    odds_ratio = (aa * dd) / (bb * cc)
    or_se = np.sqrt(1 / aa + 1 / bb + 1 / cc + 1 / dd)
    table = np.array([[a, b], [c, d]])
    fisher_p = float(stats.fisher_exact(table)[1])
    expected = stats.contingency.expected_freq(table)
    chi2, chi_p = (np.nan, np.nan)
    if np.all(table.sum(axis=0) > 0) and np.all(table.sum(axis=1) > 0):
        chi2, chi_p, _, _ = stats.chi2_contingency(table, correction=True)
    use_fisher = bool(np.any(expected < 5))
    p = fisher_p if use_fisher else float(chi_p)
    method = "Fisher's exact test" if use_fisher else "chi-square test (Yates-corrected)"
    method_ar = "اختبار فيشر الدقيق" if use_fisher else "اختبار كاي مربع (مع تصحيح ييتس)"
    nnt = 1 / abs(rd) if rd else None
    sig_en, sig_ar = _significance_word(p)
    rr_ci = (np.exp(np.log(rr) - Z95 * rr_se), np.exp(np.log(rr) + Z95 * rr_se))
    or_ci = (np.exp(np.log(odds_ratio) - Z95 * or_se), np.exp(np.log(odds_ratio) + Z95 * or_se))
    reasons = ["Fisher's exact test was used because at least one expected count is below 5."] if use_fisher else []
    if zero_cell:
        reasons.append("A zero cell was found, so 0.5 was added to every cell for the risk and odds ratios (Haldane correction).")
    return {
        "test": "two_by_two", "variables": [outcome, group], "outcome": outcome, "grouping": group,
        "n": int(n1 + n0), "event": event, "non_event": next(level for level in outcome_levels if level != event),
        "exposed_group": exposed, "reference_group": reference,
        "table": {"columns": [event, "Other"], "rows": [
            {"group": exposed, "events": a, "non_events": b, "total": n1, "risk": _round(p1, 4), "risk_ci_95": _ci((l1, u1), 4)},
            {"group": reference, "events": c, "non_events": d, "total": n0, "risk": _round(p0, 4), "risk_ci_95": _ci((l0, u0), 4)},
        ]},
        "risk_difference": _round(rd, 4), "risk_difference_ci_95": _ci(rd_ci, 4),
        "risk_ratio": _round(rr, 4), "risk_ratio_ci_95": _ci(rr_ci, 4),
        "odds_ratio": _round(odds_ratio, 4), "odds_ratio_ci_95": _ci(or_ci, 4),
        "number_needed": {"value": _round(nnt, 1), "kind": "harm" if rd > 0 else "treat"} if nnt else None,
        "fisher_p": _round(fisher_p, 4), "chi_square": _round(chi2, 4), "chi_square_p": _round(chi_p, 4),
        "p": _round(p, 4), "method": method, "method_ar": method_ar, "min_expected": _round(float(expected.min()), 2),
        "notes": reasons,
        "apa_en": (f"Events ({outcome} = {event}) occurred in {a} of {n1} ({p1:.1%}) in the {exposed} group and {c} of {n0} ({p0:.1%}) in the {reference} group "
                   f"(risk difference {rd * 100:.1f} percentage points, 95% CI {rd_ci[0] * 100:.1f} to {rd_ci[1] * 100:.1f}; "
                   f"risk ratio {rr:.2f}, 95% CI {rr_ci[0]:.2f} to {rr_ci[1]:.2f}; odds ratio {odds_ratio:.2f}, 95% CI {or_ci[0]:.2f} to {or_ci[1]:.2f}; "
                   f"{method.split(' (')[0][0].upper()}{method.split(' (')[0][1:]} p {_p_fmt(p)})."),
        "apa_ar": (f"حدث ({outcome} = {event}) لدى {a} من {n1} ({p1:.1%}) في مجموعة {exposed} و{c} من {n0} ({p0:.1%}) في مجموعة {reference} "
                   f"(فرق الخطر {rd * 100:.1f} نقطة مئوية، فترة ثقة 95%: {rd_ci[0] * 100:.1f} إلى {rd_ci[1] * 100:.1f}؛ "
                   f"نسبة الخطر {rr:.2f}، فترة ثقة 95%: {rr_ci[0]:.2f} إلى {rr_ci[1]:.2f}؛ نسبة الأرجحية {odds_ratio:.2f}، فترة ثقة 95%: {or_ci[0]:.2f} إلى {or_ci[1]:.2f}؛ "
                   f"قيمة p {_p_fmt(p)}، النتيجة {sig_ar})."),
    }


# ── Chi-square extensions ─────────────────────────────────────────────────────

def chi_square_full(df: pd.DataFrame, var1: str, var2: str) -> dict:
    """The validated chi-square result plus adjusted-residual post-hoc cells for tables larger than 2×2."""
    result = base.chi_square(df, var1, var2)
    if "error" in result:
        return result
    data = df[[var1, var2]].dropna()
    table = pd.crosstab(base._category_labels(data[var1]), base._category_labels(data[var2]))
    observed = table.to_numpy(dtype=float)
    n = observed.sum()
    expected = stats.contingency.expected_freq(observed)
    row_share = observed.sum(axis=1, keepdims=True) / n
    col_share = observed.sum(axis=0, keepdims=True) / n
    with np.errstate(divide="ignore", invalid="ignore"):
        residuals = (observed - expected) / np.sqrt(expected * (1 - row_share) * (1 - col_share))
    cells = []
    if table.shape != (2, 2):
        raw_p = (2 * stats.norm.sf(np.abs(residuals))).ravel()
        bonferroni = np.minimum(1.0, raw_p * raw_p.size)
        for index, (row, column) in enumerate((r, c) for r in table.index for c in table.columns):
            value = residuals.ravel()[index]
            cells.append({"row": row, "column": column, "observed": int(observed.ravel()[index]),
                          "expected": _round(expected.ravel()[index], 2), "adjusted_residual": _round(value, 3),
                          "p_adjusted": _round(bonferroni[index], 4), "significant": bool(bonferroni[index] < 0.05)})
    row_percent = (table.div(table.sum(axis=1), axis=0) * 100).round(1)
    result.update({
        "row_percentages": row_percent.to_dict(),
        "posthoc_cells": cells,
        "posthoc_method": "Adjusted standardised residuals (Bonferroni)" if cells else None,
        "phi": _round(result["cramer_v"], 4) if table.shape == (2, 2) else None,
    })
    return result


def goodness_of_fit(df: pd.DataFrame, variable: str, expected_proportions: dict | None = None) -> dict:
    error = _require_columns(df, [variable])
    if error:
        return {"error": error}
    counts = base._category_labels(df[variable].dropna()).value_counts().sort_index()
    if len(counts) < 2:
        return {"error": "At least two categories are needed."}
    n = int(counts.sum())
    if expected_proportions:
        try:
            shares = np.array([float(expected_proportions.get(level, 0)) for level in counts.index])
        except (TypeError, ValueError):
            return {"error": "Expected proportions must be numbers."}
        if shares.sum() <= 0:
            return {"error": "Expected proportions must add up to more than zero."}
        shares = shares / shares.sum()
    else:
        shares = np.full(len(counts), 1 / len(counts))
    expected = shares * n
    chi2, p = stats.chisquare(counts.to_numpy(), expected)
    w = np.sqrt(chi2 / n)
    return {
        "test": "goodness_of_fit", "variables": [variable], "n": n, "chi2": _round(chi2, 4), "dof": len(counts) - 1, "p": _round(p, 4),
        "cohens_w": _round(w, 4), "effect_size": base._correlation_effect_label(w),
        "categories": [{"category": level, "observed": int(count), "expected": _round(exp, 2)} for level, count, exp in zip(counts.index, counts, expected)],
        "assumption_check": {"cells_below_5": int((expected < 5).sum()), "passed": bool((expected >= 5).all())},
        "apa_en": f"A chi-square goodness-of-fit test compared the observed {variable} categories with the expected distribution, χ²({len(counts) - 1}, N = {n}) = {chi2:.2f}, p {_p_fmt(p)}, w = {w:.2f}.",
        "apa_ar": f"قارن اختبار كاي مربع لجودة المطابقة توزيع فئات {variable} المشاهد بالتوزيع المتوقع، χ²({len(counts) - 1}، ن = {n}) = {chi2:.2f}، p {_p_fmt(p)}، w = {w:.2f}.",
    }


# ── Group comparisons beyond one-way ──────────────────────────────────────────

def _pairwise_rows(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for _, row in frame.iterrows():
        p_adjusted = row.get("p_corr", row.get("p_unc"))
        rows.append({
            "factor": str(row.get("Contrast", "")), "group1": str(row["A"]), "group2": str(row["B"]),
            "statistic": _round(row.get("T", row.get("U_val", row.get("W_val"))), 3),
            "p": _round(row.get("p_unc"), 4), "p_adjusted": _round(p_adjusted, 4),
            "effect": _round(row.get("hedges"), 3), "significant": bool(p_adjusted is not None and p_adjusted < 0.05),
        })
    return rows


def anova_full(df: pd.DataFrame, outcome: str, group: str, posthoc: str = "auto") -> dict:
    """One-way ANOVA with automatic Welch switch, Kruskal-Wallis sensitivity check and pairwise comparisons.

    ``posthoc``: ``auto`` (Tukey when variances are equal, otherwise Games-Howell), ``tukey``,
    ``games_howell``, ``bonferroni`` or ``holm``.
    """
    classic = base.one_way_anova(df, outcome, group)
    if "error" in classic:
        return classic
    equal_variances = classic["assumptions"]["levene"]["equal_var_assumed"]
    welch = base.welch_anova(df, outcome, group)
    kruskal = base.kruskal_wallis(df, outcome, group)
    data, _ = base._grouped_numeric_data(df, outcome, group)
    data = data.assign(**{group: data[group].astype(str)})
    method = posthoc if posthoc in {"tukey", "games_howell", "bonferroni", "holm"} else ("tukey" if equal_variances else "games_howell")
    if method == "tukey":
        frame = pg.pairwise_tukey(data=data, dv=outcome, between=group, effsize="hedges")
        pairs = [{"group1": str(r["A"]), "group2": str(r["B"]), "mean_difference": _round(r["diff"], 3), "p_adjusted": _round(r["p_tukey"], 4),
                  "effect": _round(r["hedges"], 3), "significant": bool(r["p_tukey"] < 0.05)} for _, r in frame.iterrows()]
    elif method == "games_howell":
        frame = pg.pairwise_gameshowell(data=data, dv=outcome, between=group, effsize="hedges")
        pairs = [{"group1": str(r["A"]), "group2": str(r["B"]), "mean_difference": _round(r["diff"], 3), "p_adjusted": _round(r["pval"], 4),
                  "effect": _round(r["hedges"], 3), "significant": bool(r["pval"] < 0.05)} for _, r in frame.iterrows()]
    else:
        frame = pg.pairwise_tests(data=data, dv=outcome, between=group, padjust="bonf" if method == "bonferroni" else "holm", effsize="hedges")
        pairs = _pairwise_rows(frame)
    main = welch if (not equal_variances and "error" not in welch) else classic
    labels = {"tukey": "Tukey HSD", "games_howell": "Games-Howell", "bonferroni": "Bonferroni", "holm": "Holm"}
    decision = ("Variances were similar (Levene p " + _p_fmt(classic["assumptions"]["levene"]["p"]) + "), so the classic ANOVA is reported."
                if equal_variances else
                "Variances differed (Levene p " + _p_fmt(classic["assumptions"]["levene"]["p"]) + "), so Welch's ANOVA is reported.")
    result = {**main}
    result.update({
        "test": "anova_full", "reported_test": main["test"], "decision": decision,
        "classic": {key: classic.get(key) for key in ("f", "df_between", "df_within", "p", "eta_squared", "omega_squared")},
        "welch": {key: welch.get(key) for key in ("f", "df_between", "df_within", "p", "eta_squared")} if "error" not in welch else None,
        "kruskal": {key: kruskal.get(key) for key in ("h", "p", "epsilon_squared")} if "error" not in kruskal else None,
        "omega_squared": classic.get("omega_squared"), "effect_size": classic.get("effect_size"),
        "assumptions": classic["assumptions"],
        "posthoc": pairs, "posthoc_method": labels[method],
        "posthoc_note": None if main["p"] < 0.05 else "The overall test was not significant; treat pairwise differences as exploratory.",
        "groups": classic["groups"], "n": int(len(data)),
    })
    result["apa_en"] = f"{decision} {main['apa_en']}"
    result["apa_ar"] = main["apa_ar"]
    return result


def factorial_anova(df: pd.DataFrame, outcome: str, factors: list[str], covariates: list[str] | None = None) -> dict:
    """Two- or three-way between-subjects ANOVA (type II sums of squares), or ANCOVA when covariates are given."""
    factors = list(dict.fromkeys(factors or []))
    covariates = list(dict.fromkeys(covariates or []))
    if not factors or len(factors) > 3:
        return {"error": "Choose one to three grouping factors."}
    error = _require_columns(df, [outcome, *factors, *covariates])
    if error:
        return {"error": error}
    data = df[[outcome, *factors, *covariates]].copy()
    data[outcome] = _numeric(data, outcome)
    for covariate in covariates:
        data[covariate] = _numeric(data, covariate)
    data = data.dropna()
    for factor in factors:
        data[factor] = data[factor].astype(str)
        if data[factor].nunique() < 2:
            return {"error": f"{factor!r} needs at least two groups with data."}
    cells = data.groupby(factors).size()
    if len(data) < 6 or cells.min() < 2:
        return {"error": "Every combination of groups needs at least 2 records. Combine small groups first."}
    if covariates:
        if len(factors) != 1:
            return {"error": "ANCOVA supports one grouping factor with one or more covariates."}
        table = pg.ancova(data=data, dv=outcome, between=factors[0], covar=covariates, effsize="np2")
        test = "ancova"
        adjusted = []
        model = sm.OLS.from_formula(f"Q('{outcome}') ~ C(Q('{factors[0]}')) + " + " + ".join(f"Q('{c}')" for c in covariates), data=data).fit()
        means = data[covariates].mean()
        for level in sorted(data[factors[0]].unique()):
            frame = pd.DataFrame({factors[0]: [level], **{c: [means[c]] for c in covariates}})
            adjusted.append({"group": level, "adjusted_mean": _round(float(model.predict(frame).iloc[0]), 3)})
    else:
        table = pg.anova(data=data, dv=outcome, between=factors, ss_type=2, detailed=True, effsize="np2")
        test = "factorial_anova"
        adjusted = None
    rows = []
    for _, row in table.iterrows():
        source = str(row["Source"])
        if source in {"Residual", "Within"}:
            continue
        rows.append({"source": source.replace(" * ", " × "), "ss": _round(row.get("SS"), 3), "df": _round(row.get("DF", row.get("ddof1")), 2),
                     "f": _round(row.get("F"), 3), "p": _round(row.get("p_unc"), 4), "partial_eta_squared": _round(row.get("np2"), 4),
                     "effect_size": base._variance_explained_effect_label(row.get("np2") or 0)})
    residual = table[table["Source"].isin(["Residual", "Within"])]
    df_resid = _round(residual.iloc[0].get("DF"), 0) if len(residual) else None
    levene = stats.levene(*[group[outcome].to_numpy() for _, group in data.groupby(factors)], center="median")
    descriptives = (data.groupby(factors)[outcome].agg(["count", "mean", "std"]).reset_index()
                    .rename(columns={"count": "n", "std": "sd"}))
    cell_means = [{**{f: str(r[f]) for f in factors}, "n": int(r["n"]), "mean": _round(r["mean"], 3), "sd": _round(r["sd"], 3)} for _, r in descriptives.iterrows()]
    effects_en = "; ".join(f"{r['source']}: F({r['df']:.0f}, {df_resid:.0f}) = {r['f']:.2f}, p {_p_fmt(r['p'])}, ηp² = {r['partial_eta_squared']:.3f}"
                           for r in rows if r["f"] is not None and df_resid is not None)
    title = "An ANCOVA" if covariates else f"A {len(factors)}-way ANOVA"
    adjusted_for = f" adjusting for {', '.join(covariates)}" if covariates else ""
    return {
        "test": test, "outcome": outcome, "factors": factors, "covariates": covariates, "n": int(len(data)),
        "effects": rows, "df_residual": df_resid, "cell_means": cell_means, "adjusted_means": adjusted,
        "assumptions": {"levene": {"stat": _round(levene.statistic, 3), "p": _round(levene.pvalue, 4), "equal_var_assumed": bool(levene.pvalue > 0.05)}},
        "apa_en": f"{title} examined {outcome} by {' and '.join(factors)}{adjusted_for} (n = {len(data)}). {effects_en}.",
        "apa_ar": f"فحص تحليل التباين {outcome} حسب {' و'.join(factors)}{' مع ضبط ' + '، '.join(covariates) if covariates else ''} (ن = {len(data)}). {effects_en}.",
    }


def _wide_to_long(df: pd.DataFrame, measures: list[str], between: str | None = None) -> pd.DataFrame:
    columns = [*measures, *([between] if between else [])]
    data = df[columns].copy()
    for measure in measures:
        data[measure] = _numeric(data, measure)
    data = data.dropna().reset_index(drop=True)
    data["_subject"] = np.arange(len(data))
    long = data.melt(id_vars=["_subject", *([between] if between else [])], value_vars=measures, var_name="_time", value_name="_value")
    long["_time"] = pd.Categorical(long["_time"], categories=measures, ordered=True)
    return long


def repeated_measures_anova(df: pd.DataFrame, measures: list[str], between: str | None = None) -> dict:
    """Repeated-measures (or mixed) ANOVA on 2+ columns measured on the same records, with Friedman as the rank-based check."""
    measures = list(dict.fromkeys(measures or []))
    if len(measures) < 2:
        return {"error": "Choose at least two measurement columns (e.g. baseline, week 6, week 12)."}
    error = _require_columns(df, [*measures, *([between] if between else [])])
    if error:
        return {"error": error}
    long = _wide_to_long(df, measures, between)
    subjects = long["_subject"].nunique()
    if subjects < 3:
        return {"error": "At least 3 records with all measurements are needed."}
    means = long.groupby("_time", observed=True)["_value"].agg(["count", "mean", "std"])
    time_means = [{"time": str(index), "n": int(row["count"]), "mean": _round(row["mean"], 3), "sd": _round(row["std"], 3)} for index, row in means.iterrows()]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if between:
            long[between] = long[between].astype(str)
            table = pg.mixed_anova(data=long, dv="_value", within="_time", between=between, subject="_subject", correction=True)
        else:
            table = pg.rm_anova(data=long, dv="_value", within="_time", subject="_subject", correction=True, detailed=True)
        posthoc = pg.pairwise_tests(data=long, dv="_value", within="_time", subject="_subject", padjust="holm", effsize="hedges")
    effects = []
    error_rows = table[table["Source"] == "Error"]
    error_df = float(error_rows["DF"].iloc[0]) if len(error_rows) and "DF" in error_rows else None
    for _, row in table.iterrows():
        source = str(row["Source"])
        if source == "Error":
            continue
        p_gg = row.get("p_GG_corr")
        df1 = row.get("DF1", row.get("DF"))
        df2 = row.get("DF2", error_df)
        effects.append({
            "source": "Time" if source == "_time" else ("Time × " + between if source == "Interaction" else source),
            "f": _round(row.get("F"), 3), "df1": _round(df1, 2), "df2": _round(df2, 2),
            "p": _round(row.get("p_unc"), 4), "p_greenhouse_geisser": _round(p_gg, 4) if p_gg is not None else None,
            "epsilon": _round(row.get("eps"), 3), "effect": _round(row.get("np2", row.get("ng2")), 4),
            "sphericity_p": _round(row.get("p_spher"), 4) if "p_spher" in row else None,
        })
    friedman = None
    if not between and len(measures) >= 3:
        fr = pg.friedman(data=long, dv="_value", within="_time", subject="_subject")
        friedman = {"q": _round(fr["Q"].iloc[0], 3), "p": _round(fr["p_unc"].iloc[0], 4), "kendalls_w": _round(fr["W"].iloc[0], 3)}
    time_effect = next((e for e in effects if e["source"] == "Time"), effects[0] if effects else None)
    corrected = time_effect and time_effect.get("sphericity_p") is not None and time_effect["sphericity_p"] < 0.05
    p_report = time_effect["p_greenhouse_geisser"] if corrected and time_effect.get("p_greenhouse_geisser") is not None else (time_effect or {}).get("p")
    pairs = [row for row in _pairwise_rows(posthoc) if row["factor"] in {"_time", ""}]
    sig_en, sig_ar = _significance_word(p_report if p_report is not None else 1)
    correction_en = " with the Greenhouse-Geisser correction (sphericity was not supported)" if corrected else ""
    interaction = next((e for e in effects if e["source"].startswith("Time × ")), None)
    interaction_en = (f" The change over time {'differed' if interaction['p'] < 0.05 else 'did not differ significantly'} between {between} groups, "
                      f"F({interaction['df1']:g}, {interaction['df2']:g}) = {interaction['f']:.2f}, p {_p_fmt(interaction['p'])}."
                      if interaction and interaction.get("df2") is not None and interaction.get("p") is not None else "")
    return {
        "test": "mixed_anova" if between else "repeated_measures_anova", "measures": measures, "between": between, "n": int(subjects),
        "time_means": time_means, "effects": effects, "p": _round(p_report, 4) if p_report is not None else None,
        "sphericity_corrected": bool(corrected), "posthoc": pairs, "posthoc_method": "Paired t tests (Holm)", "friedman": friedman,
        "apa_en": (f"A {'mixed' if between else 'repeated-measures'} ANOVA{correction_en} examined change across {', '.join(measures)} (n = {subjects}). "
                   f"The effect of time was {sig_en}, F({time_effect['df1']:g}, {time_effect['df2']:g}) = {time_effect['f']:.2f}, p {_p_fmt(p_report)}.{interaction_en}"
                   if time_effect and time_effect.get("df2") is not None else f"A repeated-measures ANOVA examined {', '.join(measures)} (n = {subjects})."),
        "apa_ar": (f"فحص تحليل التباين للقياسات المتكررة التغير عبر {'، '.join(measures)} (ن = {subjects}). "
                   f"كان أثر الزمن {sig_ar}، p {_p_fmt(p_report)}." if p_report is not None else ""),
    }


def dunn_posthoc(df: pd.DataFrame, outcome: str, group: str) -> dict:
    """Kruskal-Wallis followed by Dunn's pairwise tests (tie-corrected, Holm-adjusted)."""
    overall = base.kruskal_wallis(df, outcome, group)
    if "error" in overall:
        return overall
    data, grouped = base._grouped_numeric_data(df, outcome, group)
    ranks = stats.rankdata(data[outcome].to_numpy())
    data = data.assign(_rank=ranks, _group=data[group].astype(str))
    n = len(data)
    _, tie_counts = np.unique(data[outcome], return_counts=True)
    tie_term = (tie_counts ** 3 - tie_counts).sum() / (12 * (n - 1))
    mean_rank = data.groupby("_group")["_rank"].mean()
    sizes = data.groupby("_group").size()
    names = list(grouped.keys())
    pairs, raw = [], []
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            se = np.sqrt((n * (n + 1) / 12 - tie_term) * (1 / sizes[first] + 1 / sizes[second]))
            z = (mean_rank[first] - mean_rank[second]) / se
            p = 2 * stats.norm.sf(abs(z))
            pairs.append({"group1": first, "group2": second, "z": _round(z, 3), "p": _round(p, 4)})
            raw.append(p)
    for pair, adjusted in zip(pairs, _holm(raw)):
        pair["p_adjusted"] = _round(adjusted, 4)
        pair["significant"] = adjusted < 0.05
    return {**overall, "test": "kruskal_dunn", "posthoc": pairs, "posthoc_method": "Dunn (Holm)", "n": int(n)}


# ── Correlation extensions ────────────────────────────────────────────────────

def partial_correlation(df: pd.DataFrame, var1: str, var2: str, covariates: list[str], method: str = "pearson") -> dict:
    covariates = list(dict.fromkeys(covariates or []))
    if not covariates:
        return {"error": "Choose at least one variable to control for."}
    error = _require_columns(df, [var1, var2, *covariates])
    if error:
        return {"error": error}
    data = df[[var1, var2, *covariates]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(data) < len(covariates) + 5:
        return {"error": "Too few complete records for a partial correlation."}
    result = pg.partial_corr(data=data, x=var1, y=var2, covar=covariates, method="spearman" if method == "spearman" else "pearson").iloc[0]
    r, p = float(result["r"]), float(result["p_val"])
    ci = result["CI95"]
    return {
        "test": "partial_correlation", "variables": [var1, var2], "covariates": covariates, "n": int(result["n"]),
        "r": _round(r, 4), "ci_95": _ci(ci, 3), "p": _round(p, 4), "method": method, "effect_size": base._correlation_effect_label(r),
        "apa_en": f"Controlling for {', '.join(covariates)}, the partial {method.capitalize()} correlation between {var1} and {var2} was r = {r:.2f}, 95% CI [{ci[0]:.2f}, {ci[1]:.2f}], p {_p_fmt(p)} (n = {int(result['n'])}).",
        "apa_ar": f"بعد ضبط {'، '.join(covariates)}، بلغ معامل الارتباط الجزئي بين {var1} و{var2} r = {r:.2f}، فترة ثقة 95% [{ci[0]:.2f}، {ci[1]:.2f}]، p {_p_fmt(p)} (ن = {int(result['n'])}).",
    }


def correlation_matrix(df: pd.DataFrame, variables: list[str], method: str = "pearson", padjust: str = "holm") -> dict:
    variables = list(dict.fromkeys(variables or []))
    if len(variables) < 3:
        return {"error": "Choose at least three numeric variables for a correlation matrix."}
    if len(variables) > 20:
        return {"error": "A correlation matrix is limited to 20 variables."}
    error = _require_columns(df, variables)
    if error:
        return {"error": error}
    data = df[variables].apply(pd.to_numeric, errors="coerce")
    method = "spearman" if method == "spearman" else "pearson"
    frame = pg.pairwise_corr(data=data, columns=variables, method=method, padjust="bonf" if padjust == "bonferroni" else "holm")
    pairs = [{"var1": str(r["X"]), "var2": str(r["Y"]), "n": int(r["n"]), "r": _round(r["r"], 3), "p": _round(r["p_unc"], 4),
              "p_adjusted": _round(r.get("p_corr", r["p_unc"]), 4)} for _, r in frame.iterrows()]
    matrix = data.corr(method=method).round(3)
    return {
        "test": "correlation_matrix", "variables": variables, "method": method, "padjust": padjust, "n": int(data.dropna().shape[0]),
        "matrix": {row: {column: _round(matrix.loc[row, column], 3) for column in variables} for row in variables}, "pairs": pairs,
        "apa_en": f"{method.capitalize()} correlations among {len(variables)} variables are shown with {padjust.capitalize()}-adjusted p-values.",
        "apa_ar": f"تُعرض معاملات ارتباط {method} بين {len(variables)} متغيرات مع تصحيح قيم p بطريقة {padjust}.",
    }


# ── Regression extensions ─────────────────────────────────────────────────────

def _design(df: pd.DataFrame, outcome: str, predictors: list[str], categorical: list[str] | None, reference_levels: dict | None):
    error = _require_columns(df, [outcome, *predictors])
    if error:
        return None, None, None, error
    if not predictors:
        return None, None, None, "Choose at least one predictor."
    raw = df[[outcome, *predictors]].dropna().copy()
    features, specification, error = base._build_predictor_matrix(raw, predictors, categorical, reference_levels)
    if error:
        return None, None, None, error
    return raw.loc[features.index, outcome], features, specification, None


def _coefficient_rows(model, exponentiate: bool, label: str) -> list[dict]:
    rows = []
    intervals = model.conf_int()
    for term in model.params.index:
        low, high = intervals.loc[term]
        row = {"term": "Intercept" if term == "const" else str(term), "b": _round(model.params[term], 4), "se": _round(model.bse[term], 4),
               "z": _round(model.tvalues[term], 4), "p": _round(model.pvalues[term], 4), "ci_95": [_round(low, 4), _round(high, 4)]}
        if exponentiate:
            row[label] = _round(np.exp(model.params[term]), 4)
            row[f"{label}_ci_95"] = [_round(np.exp(low), 4), _round(np.exp(high), 4)]
        rows.append(row)
    return rows


def count_regression(df: pd.DataFrame, outcome: str, predictors: list[str], categorical_predictors: list[str] | None = None,
                     reference_levels: dict | None = None, family: str = "auto") -> dict:
    """Poisson or negative-binomial regression for counts, reporting incidence-rate ratios."""
    y, features, specification, error = _design(df, outcome, predictors, categorical_predictors, reference_levels)
    if error:
        return {"error": error}
    y = pd.to_numeric(y, errors="coerce")
    if y.isna().any() or (y < 0).any() or (y % 1 != 0).any():
        return {"error": "A count outcome must contain whole numbers of zero or more."}
    x = sm.add_constant(features, has_constant="add")
    poisson = sm.GLM(y, x, family=sm.families.Poisson()).fit()
    dispersion = float(poisson.pearson_chi2 / poisson.df_resid) if poisson.df_resid else np.nan
    use_nb = family == "negative_binomial" or (family == "auto" and dispersion > 1.5)
    model = sm.NegativeBinomial(y, x).fit(disp=0) if use_nb else poisson
    rows = [row for row in _coefficient_rows(model, True, "irr") if row["term"] != "alpha"]
    name = "Negative binomial" if use_nb else "Poisson"
    return {
        "test": "count_regression", "family": name.lower().replace(" ", "_"), "outcome": outcome, "predictors": predictors, "n": int(len(y)),
        "model_specification": specification, "coefficients": rows, "dispersion": _round(dispersion, 3),
        "model_fit": {"aic": _round(model.aic, 2), "log_likelihood": _round(model.llf, 2)},
        "checks": [{"name": "Overdispersion", "passed": dispersion <= 1.5,
                    "detail": f"Pearson χ²/df = {dispersion:.2f}; {'negative binomial used' if use_nb else 'Poisson is adequate'}."}],
        "apa_en": f"A {name.lower()} regression modelled {outcome} from {', '.join(predictors)} (n = {len(y)}); coefficients are reported as incidence-rate ratios with 95% CIs.",
        "apa_ar": f"نمذج انحدار {('ذو الحدين السالب' if use_nb else 'بواسون')} المتغير {outcome} من {'، '.join(predictors)} (ن = {len(y)})، مع عرض نسب معدلات الحدوث بفترات ثقة 95%.",
    }


def multinomial_logistic(df: pd.DataFrame, outcome: str, predictors: list[str], categorical_predictors: list[str] | None = None,
                         reference_levels: dict | None = None, outcome_reference: str | None = None) -> dict:
    y, features, specification, error = _design(df, outcome, predictors, categorical_predictors, reference_levels)
    if error:
        return {"error": error}
    levels = [str(level) for level in base._sorted_levels(y.astype(str))]
    if len(levels) < 3:
        return {"error": "Multinomial regression needs an outcome with three or more categories; use binary logistic for two."}
    reference = str(outcome_reference) if outcome_reference is not None else levels[0]
    if reference not in levels:
        return {"error": f"{outcome_reference!r} is not a category of {outcome!r}."}
    order = [reference, *[level for level in levels if level != reference]]
    codes = pd.Categorical(y.astype(str), categories=order).codes
    x = sm.add_constant(features, has_constant="add")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = sm.MNLogit(codes, x).fit(disp=0, maxiter=200)
    outcomes = []
    intervals = model.conf_int()
    for index, level in enumerate(order[1:]):
        rows = []
        for term in x.columns:
            b = model.params.iloc[:, index][term]
            low, high = intervals.loc[(str(index + 1), term)] if (str(index + 1), term) in intervals.index else intervals.loc[(index + 1, term)]
            rows.append({"term": "Intercept" if term == "const" else term, "b": _round(b, 4), "p": _round(model.pvalues.iloc[:, index][term], 4),
                         "rrr": _round(np.exp(b), 4), "rrr_ci_95": [_round(np.exp(low), 4), _round(np.exp(high), 4)]})
        outcomes.append({"category": level, "coefficients": rows})
    return {
        "test": "multinomial_logistic", "outcome": outcome, "outcome_reference": reference, "predictors": predictors, "n": int(len(y)),
        "model_specification": specification, "equations": outcomes, "p": _round(model.llr_pvalue, 4), "chi2": _round(model.llr, 3),
        "pseudo_r_squared": _round(model.prsquared, 4), "model_fit": {"aic": _round(model.aic, 2)},
        "apa_en": f"A multinomial logistic regression modelled {outcome} (reference: {reference}) from {', '.join(predictors)}, χ²({model.df_model:.0f}) = {model.llr:.2f}, p {_p_fmt(model.llr_pvalue)}, McFadden R² = {model.prsquared:.3f} (n = {len(y)}).",
        "apa_ar": f"نمذج انحدار لوجستي متعدد الحدود {outcome} (المرجع: {reference}) من {'، '.join(predictors)}، χ²({model.df_model:.0f}) = {model.llr:.2f}، p {_p_fmt(model.llr_pvalue)} (ن = {len(y)}).",
    }


def ordinal_logistic(df: pd.DataFrame, outcome: str, predictors: list[str], categorical_predictors: list[str] | None = None,
                     reference_levels: dict | None = None, order: list | None = None) -> dict:
    from statsmodels.miscmodels.ordinal_model import OrderedModel

    y, features, specification, error = _design(df, outcome, predictors, categorical_predictors, reference_levels)
    if error:
        return {"error": error}
    levels = [str(level) for level in (order or base._sorted_levels(y))]
    if len(levels) < 3:
        return {"error": "Ordinal regression needs an outcome with three or more ordered levels."}
    y_codes = pd.Categorical(y.astype(str), categories=levels, ordered=True)
    if pd.isna(y_codes).any():
        return {"error": "Some outcome values are not in the stated order."}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = OrderedModel(pd.Series(y_codes, index=features.index), features, distr="logit").fit(method="bfgs", disp=0, maxiter=500)
    rows = []
    intervals = model.conf_int()
    for term in features.columns:
        low, high = intervals.loc[term]
        rows.append({"term": term, "b": _round(model.params[term], 4), "se": _round(model.bse[term], 4), "p": _round(model.pvalues[term], 4),
                     "odds_ratio": _round(np.exp(model.params[term]), 4), "odds_ratio_ci_95": [_round(np.exp(low), 4), _round(np.exp(high), 4)]})
    return {
        "test": "ordinal_logistic", "outcome": outcome, "levels": levels, "predictors": predictors, "n": int(len(y)),
        "model_specification": specification, "coefficients": rows, "model_fit": {"aic": _round(model.aic, 2), "log_likelihood": _round(model.llf, 2)},
        "apa_en": f"An ordinal (proportional-odds) logistic regression modelled {outcome} ({' < '.join(levels)}) from {', '.join(predictors)} (n = {len(y)}). Odds ratios above 1 indicate higher {outcome} categories.",
        "apa_ar": f"نمذج انحدار لوجستي ترتيبي {outcome} ({' < '.join(levels)}) من {'، '.join(predictors)} (ن = {len(y)}). تشير نسب الأرجحية الأكبر من 1 إلى فئات أعلى.",
    }


def _auc_with_ci(scores: np.ndarray, truth: np.ndarray) -> tuple[float, tuple[float, float]]:
    """AUC (Mann-Whitney) with the Hanley-McNeil 95% CI."""
    positives, negatives = scores[truth == 1], scores[truth == 0]
    n1, n0 = len(positives), len(negatives)
    u = stats.mannwhitneyu(positives, negatives, alternative="two-sided").statistic
    auc = u / (n1 * n0)
    q1, q2 = auc / (2 - auc), 2 * auc ** 2 / (1 + auc)
    se = np.sqrt((auc * (1 - auc) + (n1 - 1) * (q1 - auc ** 2) + (n0 - 1) * (q2 - auc ** 2)) / (n1 * n0))
    return float(auc), (max(0.0, auc - Z95 * se), min(1.0, auc + Z95 * se))


def logistic_full(df: pd.DataFrame, outcome: str, predictors: list[str], categorical_predictors: list[str] | None = None,
                  event_level: str | None = None, reference_levels: dict | None = None) -> dict:
    """Binary logistic regression with discrimination (AUC) and calibration (Hosmer-Lemeshow) checks."""
    result = base.logistic_regression(df, outcome, predictors, categorical_predictors, event_level, reference_levels)
    if "error" in result:
        return result
    raw = df[[outcome, *predictors]].dropna()
    features, _, _ = base._build_predictor_matrix(raw, predictors, categorical_predictors, reference_levels)
    y = (raw.loc[features.index, outcome].astype(str) == result["outcome_event"]).astype(int).to_numpy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = sm.Logit(y, sm.add_constant(features, has_constant="add")).fit(disp=0)
    probability = np.asarray(model.predict())
    auc, auc_ci = _auc_with_ci(probability, y)
    groups = pd.qcut(probability, 10, duplicates="drop")
    summary = pd.DataFrame({"y": y, "p": probability, "g": groups}).groupby("g", observed=True).agg(o=("y", "sum"), e=("p", "sum"), n=("y", "size"))
    with np.errstate(divide="ignore", invalid="ignore"):
        hl = float((((summary.o - summary.e) ** 2) / (summary.e * (1 - summary.e / summary.n))).sum())
    hl_df = max(1, len(summary) - 2)
    hl_p = float(stats.chi2.sf(hl, hl_df))
    result["model_fit"].update({"auc": _round(auc, 3), "auc_ci_95": _ci(auc_ci, 3), "hosmer_lemeshow": {"chi2": _round(hl, 3), "df": hl_df, "p": _round(hl_p, 4)}})
    result["assumptions"]["calibration"] = {"passed": hl_p > 0.05, "note": f"Hosmer-Lemeshow p = {hl_p:.3f}"}
    result["assumptions"]["discrimination"] = {"passed": auc >= 0.7, "note": f"AUC = {auc:.2f} (95% CI {auc_ci[0]:.2f} to {auc_ci[1]:.2f})"}
    return result


def linear_full(df: pd.DataFrame, outcome: str, predictors: list[str], categorical_predictors: list[str] | None = None,
                reference_levels: dict | None = None, robust: bool = False, blocks: list[list[str]] | None = None,
                interactions: list[list[str]] | None = None) -> dict:
    """Multiple linear regression with optional HC3 robust errors, interaction terms and hierarchical blocks (ΔR²)."""
    working = df.copy()
    extra_terms = []
    for pair in interactions or []:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            return {"error": "Each interaction must name two predictors."}
        first, second = map(str, pair)
        if first not in predictors or second not in predictors:
            return {"error": "Interaction terms must use predictors already in the model."}
        if first in (categorical_predictors or []) or second in (categorical_predictors or []):
            return {"error": "Interactions are supported between numeric predictors; recode a binary group as 0/1 first."}
        name = f"{first} × {second}"
        a, b = _numeric(working, first), _numeric(working, second)
        working[name] = (a - a.mean()) * (b - b.mean())
        extra_terms.append(name)
    all_predictors = [*predictors, *extra_terms]
    result = base.linear_regression(working, outcome, all_predictors, categorical_predictors, reference_levels)
    if "error" in result:
        return result
    if extra_terms:
        result["interactions"] = extra_terms
        result["notes"] = ["Interaction terms use mean-centred predictors, so main effects are interpreted at the average of the other variable."]
    if robust:
        y, features, _, _ = _design(working, outcome, all_predictors, categorical_predictors, reference_levels)
        model = sm.OLS(pd.to_numeric(y), sm.add_constant(features, has_constant="add")).fit(cov_type="HC3")
        intervals = model.conf_int()
        for row in result["coefficients"]:
            term = "const" if row["term"] == "Intercept" else row["term"]
            row["robust_se"] = _round(model.bse[term], 4)
            row["robust_p"] = _round(model.pvalues[term], 4)
            row["robust_ci_95"] = [_round(intervals.loc[term][0], 4), _round(intervals.loc[term][1], 4)]
        result["robust_errors"] = "HC3"
    if blocks:
        steps, previous = [], None
        cumulative: list[str] = []
        for index, block in enumerate(blocks, start=1):
            cumulative = [*cumulative, *[term for term in block if term not in cumulative]]
            y, features, _, error = _design(working, outcome, cumulative, [c for c in (categorical_predictors or []) if c in cumulative], reference_levels)
            if error:
                return {"error": f"Block {index}: {error}"}
            model = sm.OLS(pd.to_numeric(y), sm.add_constant(features, has_constant="add")).fit()
            step = {"block": index, "predictors": list(cumulative), "n": int(model.nobs), "r_squared": _round(model.rsquared, 4), "adjusted_r_squared": _round(model.rsquared_adj, 4)}
            if previous is not None:
                comparison = model.compare_f_test(previous)
                step.update({"delta_r_squared": _round(model.rsquared - previous.rsquared, 4), "f_change": _round(comparison[0], 3), "p_change": _round(comparison[1], 4)})
            steps.append(step)
            previous = model
        result["hierarchical"] = steps
    standardized = {row["term"]: row.get("standardized_beta") for row in result["coefficients"]}
    result["largest_effect"] = max((term for term in standardized if term != "Intercept" and standardized[term] is not None),
                                   key=lambda term: abs(standardized[term]), default=None)
    return result


# ── Reliability and agreement ─────────────────────────────────────────────────

def reliability_full(df: pd.DataFrame, items: list[str], reverse_items: list[str] | None = None) -> dict:
    """Cronbach's alpha plus McDonald's ω, split-half reliability, inter-item r and a reverse-item check."""
    result = base.cronbach_alpha(df, items, reverse_items)
    if "error" in result:
        return result
    data = df[items].apply(pd.to_numeric, errors="coerce").dropna()
    for column in reverse_items or []:
        data[column] = data[column].min() + data[column].max() - data[column]
    standardized = (data - data.mean()) / data.std(ddof=1)
    correlations = data.corr().to_numpy()
    k = len(items)
    mean_inter_item = float(correlations[np.triu_indices(k, 1)].mean())
    eigenvalues = np.sort(np.linalg.eigvalsh(correlations))[::-1]
    omega = None
    if k >= 3 and len(data) > k:
        from sklearn.decomposition import FactorAnalysis

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fa = FactorAnalysis(n_components=1, random_state=0).fit(standardized.to_numpy())
        loadings = np.abs(fa.components_[0])
        uniqueness = fa.noise_variance_
        omega = float(loadings.sum() ** 2 / (loadings.sum() ** 2 + uniqueness.sum()))
    odd, even = data.iloc[:, ::2].sum(axis=1), data.iloc[:, 1::2].sum(axis=1)
    half_r = float(np.corrcoef(odd, even)[0, 1]) if k >= 2 else np.nan
    split_half = 2 * half_r / (1 + half_r) if np.isfinite(half_r) and half_r > -1 else np.nan
    suspected = [row["item"] for row in result["item_statistics"] if (row["item_total_r"] or 0) < 0 and row["item"] not in (reverse_items or [])]
    weak = [row["item"] for row in result["item_statistics"] if row["item_total_r"] is not None and 0 <= row["item_total_r"] < 0.3]
    result.update({
        "test": "reliability", "omega": _round(omega, 4), "split_half": _round(split_half, 4), "mean_inter_item_r": _round(mean_inter_item, 4),
        "first_eigenvalue": _round(eigenvalues[0], 3), "first_factor_share": _round(eigenvalues[0] / k, 3),
        "unidimensional": bool(eigenvalues[0] / k >= 0.4 and (k < 2 or eigenvalues[1] < 1)),
        "suspected_reverse_items": suspected, "weak_items": weak,
    })
    if suspected:
        result["notes"] = [f"{', '.join(suspected)} correlate negatively with the other items and may be reverse-worded. Reverse-score and re-run if so."]
    if omega is not None:
        result["apa_en"] += f" McDonald's ω = {omega:.2f}."
        result["apa_ar"] += f" ω لماكدونالد = {omega:.2f}."
    if reverse_items:
        result["apa_en"] += f" {', '.join(reverse_items)} {'was' if len(reverse_items) == 1 else 'were'} reverse-scored before analysis."
        result["apa_ar"] += f" عُكست درجات {'، '.join(reverse_items)} قبل التحليل."
    return result


def cohens_kappa(df: pd.DataFrame, rater1: str, rater2: str, weighted: str | None = None) -> dict:
    from sklearn.metrics import cohen_kappa_score

    error = _require_columns(df, [rater1, rater2])
    if error:
        return {"error": error}
    data = df[[rater1, rater2]].dropna().astype(str)
    n = len(data)
    if n < 5:
        return {"error": "At least 5 records rated by both raters are needed."}
    labels = sorted(set(data[rater1]) | set(data[rater2]))
    weights = weighted if weighted in {"linear", "quadratic"} else None
    kappa = float(cohen_kappa_score(data[rater1], data[rater2], labels=labels, weights=weights))
    table = pd.crosstab(data[rater1], data[rater2]).reindex(index=labels, columns=labels, fill_value=0).to_numpy(dtype=float)
    po = np.trace(table) / n
    pe = float((table.sum(axis=1) * table.sum(axis=0)).sum() / n ** 2)
    se = np.sqrt(po * (1 - po) / (n * (1 - pe) ** 2)) if pe < 1 else np.nan
    label = ("poor" if kappa < 0 else "slight" if kappa <= 0.2 else "fair" if kappa <= 0.4 else "moderate" if kappa <= 0.6
             else "substantial" if kappa <= 0.8 else "almost perfect")
    return {
        "test": "cohens_kappa", "variables": [rater1, rater2], "n": n, "kappa": _round(kappa, 4), "weights": weights or "none",
        "ci_95": _ci((kappa - Z95 * se, kappa + Z95 * se), 3), "observed_agreement": _round(po, 4), "agreement": label,
        "apa_en": f"Agreement between {rater1} and {rater2} was {label}, Cohen's κ = {kappa:.2f}, 95% CI [{kappa - Z95 * se:.2f}, {kappa + Z95 * se:.2f}] (observed agreement {po:.0%}, n = {n}).",
        "apa_ar": f"كان الاتفاق بين {rater1} و{rater2} بدرجة ({label})، κ لكوهين = {kappa:.2f}، فترة ثقة 95% [{kappa - Z95 * se:.2f}، {kappa + Z95 * se:.2f}] (نسبة الاتفاق {po:.0%}، ن = {n}).",
    }


def fleiss_kappa(df: pd.DataFrame, raters: list[str]) -> dict:
    from statsmodels.stats.inter_rater import aggregate_raters, fleiss_kappa as statsmodels_fleiss

    raters = list(dict.fromkeys(raters or []))
    if len(raters) < 3:
        return {"error": "Fleiss' κ needs three or more rater columns; use Cohen's κ for two."}
    error = _require_columns(df, raters)
    if error:
        return {"error": error}
    data = df[raters].dropna().astype(str)
    counts, _ = aggregate_raters(data.to_numpy())
    kappa = float(statsmodels_fleiss(counts))
    return {
        "test": "fleiss_kappa", "variables": raters, "n": int(len(data)), "kappa": _round(kappa, 4),
        "apa_en": f"Agreement among {len(raters)} raters was Fleiss' κ = {kappa:.2f} (n = {len(data)}).",
        "apa_ar": f"بلغ الاتفاق بين {len(raters)} مقيّمين κ لفلايس = {kappa:.2f} (ن = {len(data)}).",
    }


def icc(df: pd.DataFrame, raters: list[str]) -> dict:
    raters = list(dict.fromkeys(raters or []))
    if len(raters) < 2:
        return {"error": "Choose two or more columns holding ratings of the same records."}
    error = _require_columns(df, raters)
    if error:
        return {"error": error}
    long = _wide_to_long(df, raters)
    table = pg.intraclass_corr(data=long, targets="_subject", raters="_time", ratings="_value")
    # Pingouin 0.6 labels: ICC(1,1), ICC(A,1), ICC(C,1) and the ",k" averages (older versions: ICC1, ICC2, ICC3...).
    descriptions = {
        "ICC(1,1)": "One-way random, single rater", "ICC(A,1)": "Two-way random, absolute agreement, single rater",
        "ICC(C,1)": "Two-way mixed, consistency, single rater", "ICC(1,k)": "One-way random, average of raters",
        "ICC(A,k)": "Two-way random, absolute agreement, average of raters", "ICC(C,k)": "Two-way mixed, consistency, average of raters",
        "ICC1": "One-way random, single rater", "ICC2": "Two-way random, absolute agreement, single rater",
        "ICC3": "Two-way mixed, consistency, single rater", "ICC1k": "One-way random, average of raters",
        "ICC2k": "Two-way random, absolute agreement, average of raters", "ICC3k": "Two-way mixed, consistency, average of raters",
    }
    rows = [{"type": str(r["Type"]), "description": descriptions.get(str(r["Type"]), str(r["Type"])), "icc": _round(r["ICC"], 4),
             "ci_95": _ci(r["CI95"], 3), "p": _round(r["pval"], 4)} for _, r in table.iterrows()]
    two_way = next(row for row in rows if row["type"] in {"ICC(A,1)", "ICC2"})
    return {
        "test": "icc", "variables": raters, "n": int(long["_subject"].nunique()), "icc_table": rows, "icc": two_way["icc"], "ci_95": two_way["ci_95"],
        "apa_en": f"Inter-rater reliability (two-way random effects, absolute agreement, single rater) was ICC = {two_way['icc']:.2f}, 95% CI [{two_way['ci_95'][0]:.2f}, {two_way['ci_95'][1]:.2f}].",
        "apa_ar": f"بلغت موثوقية التقييم بين المقيّمين ICC = {two_way['icc']:.2f}، فترة ثقة 95% [{two_way['ci_95'][0]:.2f}، {two_way['ci_95'][1]:.2f}].",
    }


# ── Diagnostic accuracy ───────────────────────────────────────────────────────

def diagnostic_accuracy(df: pd.DataFrame, test: str, reference: str, test_positive: str | None = None,
                        reference_positive: str | None = None) -> dict:
    """Sensitivity, specificity, predictive values and likelihood ratios with Wilson CIs; ROC/AUC for numeric tests."""
    error = _require_columns(df, [test, reference])
    if error:
        return {"error": error}
    data = df[[test, reference]].dropna()
    _, reference_event, error = _two_levels(data[reference].astype(str), reference_positive, "The reference standard")
    if error:
        return {"error": error}
    truth = (data[reference].astype(str) == reference_event).astype(int).to_numpy()
    numeric_test = pd.to_numeric(data[test], errors="coerce")
    roc = None
    if numeric_test.notna().all() and numeric_test.nunique() > 2:
        scores = numeric_test.to_numpy(dtype=float)
        auc, auc_ci = _auc_with_ci(scores, truth)
        direction = 1
        if auc < 0.5:
            scores, auc, auc_ci, direction = -scores, 1 - auc, (1 - auc_ci[1], 1 - auc_ci[0]), -1
        thresholds = np.unique(scores)
        points, best = [], None
        for threshold in thresholds:
            predicted = scores >= threshold
            sens = (predicted & (truth == 1)).sum() / max(1, (truth == 1).sum())
            spec = (~predicted & (truth == 0)).sum() / max(1, (truth == 0).sum())
            points.append({"threshold": _round(direction * threshold, 4), "sensitivity": _round(sens, 4), "specificity": _round(spec, 4)})
            youden = sens + spec - 1
            if best is None or youden > best[0]:
                best = (youden, direction * threshold)
        step = max(1, len(points) // 200)
        roc = {"auc": _round(auc, 4), "auc_ci_95": _ci(auc_ci, 3), "points": points[::step], "direction": "higher = positive" if direction == 1 else "lower = positive",
               "optimal_cutoff": _round(best[1], 4), "youden_j": _round(best[0], 4)}
        original = numeric_test.to_numpy(dtype=float)
        cutoff = best[1]
        predicted_positive = original >= cutoff if direction == 1 else original <= cutoff
        test_event = f"≥ {cutoff:g}" if direction == 1 else f"≤ {cutoff:g}"
    else:
        _, test_event, error = _two_levels(data[test].astype(str), test_positive, "The index test")
        if error:
            return {"error": error}
        predicted_positive = (data[test].astype(str) == test_event).to_numpy()
    tp = int((predicted_positive & (truth == 1)).sum())
    fn = int((~predicted_positive & (truth == 1)).sum())
    fp = int((predicted_positive & (truth == 0)).sum())
    tn = int((~predicted_positive & (truth == 0)).sum())
    n = tp + fn + fp + tn

    def proportion(successes, total):
        value = successes / total if total else np.nan
        return {"value": _round(value, 4), "ci_95": _ci(_wilson(successes, total), 4)}

    sensitivity = tp / (tp + fn) if tp + fn else np.nan
    specificity = tn / (tn + fp) if tn + fp else np.nan
    lr_positive = sensitivity / (1 - specificity) if specificity < 1 else np.inf
    lr_negative = (1 - sensitivity) / specificity if specificity > 0 else np.inf
    po = (tp + tn) / n
    pe = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / n ** 2
    kappa = (po - pe) / (1 - pe) if pe < 1 else np.nan
    sens_ci, spec_ci = _wilson(tp, tp + fn), _wilson(tn, tn + fp)
    return {
        "test": "diagnostic_accuracy", "variables": [test, reference], "n": n, "positive_reference": reference_event, "positive_test": str(test_event),
        "table": {"true_positive": tp, "false_negative": fn, "false_positive": fp, "true_negative": tn},
        "sensitivity": proportion(tp, tp + fn), "specificity": proportion(tn, tn + fp),
        "ppv": proportion(tp, tp + fp), "npv": proportion(tn, tn + fn), "accuracy": proportion(tp + tn, n), "prevalence": proportion(tp + fn, n),
        "lr_positive": _round(lr_positive, 3), "lr_negative": _round(lr_negative, 3), "kappa": _round(kappa, 4), "roc": roc,
        "notes": ["PPV and NPV depend on prevalence in this sample; they change in populations with a different prevalence."],
        "apa_en": (f"Against {reference} ({reference_event} = positive), {test} ({test_event} = positive) had a sensitivity of {sensitivity:.1%} "
                   f"(95% CI {sens_ci[0]:.1%} to {sens_ci[1]:.1%}) and a specificity of {specificity:.1%} (95% CI {spec_ci[0]:.1%} to {spec_ci[1]:.1%}); "
                   f"LR+ = {lr_positive:.2f}, LR− = {lr_negative:.2f} (n = {n})." + (f" The area under the ROC curve was {roc['auc']:.2f} (95% CI {roc['auc_ci_95'][0]:.2f} to {roc['auc_ci_95'][1]:.2f})." if roc else "")),
        "apa_ar": (f"مقارنةً بالمعيار المرجعي {reference}، بلغت حساسية {test} {sensitivity:.1%} (فترة ثقة 95%: {sens_ci[0]:.1%} إلى {sens_ci[1]:.1%}) "
                   f"ونوعيته {specificity:.1%} (فترة ثقة 95%: {spec_ci[0]:.1%} إلى {spec_ci[1]:.1%})؛ LR+ = {lr_positive:.2f}، LR− = {lr_negative:.2f} (ن = {n})."
                   + (f" وبلغت المساحة تحت منحنى ROC {roc['auc']:.2f}." if roc else "")),
    }


# ── Table 1 by group ──────────────────────────────────────────────────────────

def table_one(df: pd.DataFrame, group: str | None, variables: list[dict]) -> dict:
    """Publication Table 1: mean (SD) or median [IQR] by distribution, n (%) for categories, p-values and SMDs."""
    if group is not None:
        error = _require_columns(df, [group])
        if error:
            return {"error": error}
    data = df.copy()
    groups = base._sorted_labels(data[group]) if group else []
    if group and len(groups) < 2:
        return {"error": "The grouping variable needs at least two groups."}
    if group:
        data = data[data[group].notna()]
        data = data.assign(**{group: base._category_labels(data[group])})
    rows = []
    for variable in variables:
        name, kind = variable.get("name"), variable.get("type", "numeric")
        if name not in data.columns or name == group or kind in {"id", "text", "date"}:
            continue
        if kind in {"numeric"}:
            values = _numeric(data, name)
            skewed = abs(stats.skew(values.dropna())) > 1 if values.notna().sum() > 2 else False
            def summarize(series):
                series = series.dropna()
                if series.empty:
                    return "—"
                if skewed:
                    q1, q3 = series.quantile([0.25, 0.75])
                    return f"{series.median():.1f} [{q1:.1f}, {q3:.1f}]"
                return f"{series.mean():.1f} ({series.std(ddof=1):.1f})"
            row = {"variable": name, "kind": "continuous", "statistic": "median [IQR]" if skewed else "mean (SD)",
                   "overall": summarize(values), "missing": int(values.isna().sum())}
            if group:
                samples = [values[data[group] == level].dropna() for level in groups]
                row["by_group"] = {level: summarize(values[data[group] == level]) for level in groups}
                valid = [sample for sample in samples if len(sample) >= 2]
                if len(valid) == len(groups):
                    if skewed:
                        test = stats.mannwhitneyu(*samples) if len(groups) == 2 else stats.kruskal(*samples)
                        row["test"] = "Mann-Whitney U" if len(groups) == 2 else "Kruskal-Wallis"
                    else:
                        test = stats.ttest_ind(*samples, equal_var=False) if len(groups) == 2 else stats.f_oneway(*samples)
                        row["test"] = "Welch t test" if len(groups) == 2 else "ANOVA"
                    row["p"] = _round(test.pvalue, 4)
                    if len(groups) == 2:
                        pooled = np.sqrt((samples[0].var(ddof=1) + samples[1].var(ddof=1)) / 2)
                        row["smd"] = _round(abs(samples[0].mean() - samples[1].mean()) / pooled, 3) if pooled else None
            rows.append(row)
        else:
            values = base._category_labels(data[name])
            levels = base._sorted_labels(data[name])
            if len(levels) > 15:
                continue
            row = {"variable": name, "kind": "categorical", "statistic": "n (%)", "missing": int(data[name].isna().sum()), "levels": []}
            present = values.dropna()
            for level in levels:
                entry = {"level": level, "overall": f"{int((present == level).sum())} ({(present == level).mean() * 100:.1f})"}
                if group:
                    entry["by_group"] = {}
                    for g in groups:
                        subset = values[data[group] == g].dropna()
                        count = int((subset == level).sum())
                        entry["by_group"][g] = f"{count} ({count / len(subset) * 100:.1f})" if len(subset) else "—"
                row["levels"].append(entry)
            if group:
                table = pd.crosstab(values, data[group])  # blanks are left out, not counted as a category
                if table.shape[0] >= 2 and table.shape[1] >= 2:
                    expected = stats.contingency.expected_freq(table)
                    if table.shape == (2, 2) and (expected < 5).any():
                        row["p"], row["test"] = _round(stats.fisher_exact(table.to_numpy())[1], 4), "Fisher's exact"
                    else:
                        row["p"], row["test"] = _round(stats.chi2_contingency(table)[1], 4), "Chi-square"
                    if len(groups) == 2 and table.shape[0] == 2:
                        shares = table.div(table.sum(axis=0), axis=1).iloc[1]
                        p1, p2 = shares.iloc[0], shares.iloc[1]
                        pooled = np.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / 2)
                        row["smd"] = _round(abs(p1 - p2) / pooled, 3) if pooled else None
            rows.append(row)
    counts = {level: int((data[group] == level).sum()) for level in groups} if group else {}
    return {
        "test": "table_one", "grouping": group, "groups": groups, "group_n": counts, "n": int(len(data)), "rows": rows,
        "notes": ["Continuous variables: mean (SD), or median [IQR] when skewed (|skewness| > 1). Categorical: n (%). "
                  "SMD > 0.1 suggests a meaningful imbalance between two groups."],
        "apa_en": (f"Table 1 shows participant characteristics{' by ' + group if group else ''} (N = {len(data)}"
                   + (", " + ", ".join(f"{g}: n = {c}" for g, c in counts.items()) if counts else "") + ")."),
        "apa_ar": f"يعرض الجدول 1 خصائص المشاركين{' حسب ' + group if group else ''} (ن = {len(data)}).",
    }
