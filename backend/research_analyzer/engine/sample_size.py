"""Sample size, power and detectable-effect calculations for study planning.

Every design defines ``n_for(inputs, effect, power)``: the (continuous) number of completers needed in
the first / reference group, before design effect and dropout. From that one function the engine
answers all three questions:

* ``n``      – sample size for the planned effect and power;
* ``power``  – power for the number of participants you can recruit;
* ``mde``    – the smallest effect detectable with that number at the planned power.

Exact t and noncentral-F calculations are used where G*Power uses them (two means, paired means,
ANOVA, multiple regression), so results match G*Power 3.1. Estimation designs (a single proportion or
mean, diagnostic accuracy) answer ``n`` or ``precision`` instead of power.

Adjustments, in this order: per-group n → × design effect (or cluster ICC) → finite population
correction (estimation designs only) → ÷ (1 − dropout) → rounded up.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import optimize, stats

Z = stats.norm.ppf


class PlanningError(ValueError):
    pass


# ── Input helpers ─────────────────────────────────────────────────────────────

def _num(inputs, key, default=None, low=None, high=None, label=None):
    value = inputs.get(key, default)
    if value in (None, ""):
        if default is None:
            raise PlanningError(f"Enter {label or key.replace('_', ' ')}.")
        value = default
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise PlanningError(f"{label or key.replace('_', ' ').capitalize()} must be a number.") from None
    if not math.isfinite(value) or (low is not None and value <= low) or (high is not None and value >= high):
        bounds = f" between {low:g} and {high:g}" if low is not None and high is not None else (f" above {low:g}" if low is not None else "")
        raise PlanningError(f"{label or key.replace('_', ' ').capitalize()} must be{bounds}.")
    return value


def _pct(inputs, key, default=None, label=None):
    return _num(inputs, key, default, 0, 100, label) / 100


def _common(inputs):
    alpha = _num(inputs, "alpha", 0.05, 0, 0.5, "The significance level")
    sides = 1 if str(inputs.get("sides", "2")) == "1" else 2
    power = _pct(inputs, "power", 80, "Power")
    ratio = _num(inputs, "ratio", 1, 0, 20, "The allocation ratio")
    dropout = _num(inputs, "dropout", 0, -0.0001, 90, "Dropout") / 100
    response = _num(inputs, "response_rate", 100, 0, 100.0001, "The expected response rate") / 100
    icc = inputs.get("icc")
    cluster = inputs.get("cluster_size")
    if icc not in (None, "") and cluster not in (None, ""):
        icc_value = _num(inputs, "icc", None, -0.0001, 1, "The ICC")
        size = _num(inputs, "cluster_size", None, 0, 100000, "The cluster size")
        deff = 1 + (size - 1) * icc_value
        cluster_info = {"icc": icc_value, "cluster_size": size}
    else:
        deff = _num(inputs, "design_effect", 1, 0.9999, 50, "The design effect")
        cluster_info = None
    return {"alpha": alpha, "sides": sides, "power": power, "ratio": ratio, "dropout": dropout, "response": response,
            "keep": (1 - dropout) * response, "deff": max(1.0, deff), "cluster": cluster_info}


def _z_alpha(c):
    return Z(1 - c["alpha"] / c["sides"])


# ── Designs ───────────────────────────────────────────────────────────────────
# Each design: label, family, level, kind ("power" or "precision"), groups (1 or 2), inputs,
# effect key and natural bounds for the detectable-effect search, and n_for().

def _two_means(inputs, c):
    sd = _num(inputs, "sd", None, 0, None, "The standard deviation")
    rho = inputs.get("baseline_correlation")
    factor = 1.0
    if rho not in (None, ""):
        r = _num(inputs, "baseline_correlation", None, -1, 1, "The baseline correlation")
        factor = 1 - r ** 2  # ANCOVA adjustment for the baseline measurement
    return sd * math.sqrt(factor)


def _t_power(ncp, df, c):
    """Power of a t test with noncentrality ncp (exact noncentral t, as in G*Power)."""
    if ncp > 38:  # power is 1 to machine precision; the noncentral t would overflow
        return 1.0
    crit = stats.t.ppf(1 - c["alpha"] / c["sides"], df)
    power = stats.nct.sf(crit, df, ncp)
    if c["sides"] == 2:
        power += stats.nct.cdf(-crit, df, ncp)
    return float(power)


def _solve_n(power_at, target, low):
    """Smallest continuous n with power_at(n) >= target (power rises with n)."""
    if power_at(low) >= target:
        return low
    high = max(low * 2, 10.0)
    while power_at(high) < target:
        high *= 2
        if high > 1e8:
            raise PlanningError("The effect is too small to detect with any realistic sample.")
    return optimize.brentq(lambda n: power_at(n) - target, low, high, xtol=1e-6)


def n_two_means(inputs, c, effect, power):
    sd = _two_means(inputs, c)
    d = abs(effect) / sd
    if d <= 0:
        raise PlanningError("The difference to detect must be above 0.")
    k = c["ratio"]
    return _solve_n(lambda n1: _t_power(d * math.sqrt(n1 * k * n1 / (n1 + k * n1)), n1 + k * n1 - 2, c), power, 2.0)


def power_two_means(inputs, c, effect, n1):
    d = abs(effect) / _two_means(inputs, c)
    k = c["ratio"]
    return _t_power(d * math.sqrt(n1 * k * n1 / (n1 + k * n1)), max(1.0, n1 + k * n1 - 2), c)


def _sd_diff(inputs):
    sd_diff = inputs.get("sd_diff")
    if sd_diff in (None, ""):
        sd = _num(inputs, "sd", None, 0, None, "The standard deviation")
        r = _num(inputs, "pre_post_correlation", 0.5, -1, 1, "The before–after correlation")
        return sd * math.sqrt(2 * (1 - r))
    return _num(inputs, "sd_diff", None, 0, None, "The SD of the differences")


def power_paired_means(inputs, c, effect, n):
    return _t_power(abs(effect) / _sd_diff(inputs) * math.sqrt(n), max(1.0, n - 1), c)


def n_paired_means(inputs, c, effect, power):
    dz = abs(effect) / _sd_diff(inputs)
    if dz <= 0:
        raise PlanningError("The change to detect must be above 0.")
    return _solve_n(lambda n: _t_power(dz * math.sqrt(n), n - 1, c), power, 2.0)


def _prop_pair(inputs, effect):
    p1 = _pct(inputs, "p1", None, "The control-group proportion")
    p2 = effect
    if not 0 < p2 < 1:
        raise PlanningError("The proportions must be between 0% and 100%.")
    return p1, p2


def n_two_proportions(inputs, c, effect, power):
    p1, p2 = _prop_pair(inputs, effect)
    delta = abs(p2 - p1)
    if delta < 1e-6:
        raise PlanningError("The two proportions must differ.")
    k = c["ratio"]
    pbar = (p1 + k * p2) / (1 + k)
    za, zb = _z_alpha(c), Z(power)
    n = (za * math.sqrt(pbar * (1 - pbar) * (1 + 1 / k)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2) / k)) ** 2 / delta ** 2
    if str(inputs.get("continuity", "")).lower() in {"1", "true", "yes"}:
        n = n / 4 * (1 + math.sqrt(1 + 2 * (k + 1) / (k * n * delta))) ** 2
    return n


def power_anova(inputs, c, effect, n_per_group):
    groups = int(_num(inputs, "groups", 3, 1.5, 21, "The number of groups"))
    total = max(n_per_group * groups, groups + 1.01)
    df2 = total - groups
    crit = stats.f.ppf(1 - c["alpha"], groups - 1, df2)
    return float(stats.ncf.sf(crit, groups - 1, df2, effect * effect * total))


def n_anova(inputs, c, effect, power):
    groups = int(_num(inputs, "groups", 3, 1.5, 21, "The number of groups"))
    if abs(effect) <= 0:
        raise PlanningError("The effect size f must be above 0.")
    return _solve_n(lambda n: power_anova(inputs, c, abs(effect), n), power, (groups + 1.01) / groups)


def n_correlation(inputs, c, effect, power):
    r = abs(effect)
    if not 0 < r < 1:
        raise PlanningError("The correlation must be between 0 and 1.")
    return ((_z_alpha(c) + Z(power)) / math.atanh(r)) ** 2 + 3


def _predictor_counts(inputs):
    tested = int(_num(inputs, "tested_predictors", 1, 0.5, 200, "The number of predictors tested"))
    total_predictors = int(_num(inputs, "total_predictors", tested, tested - 0.5, 500, "The total number of predictors"))
    return tested, total_predictors


def power_regression(inputs, c, effect, n):
    tested, total_predictors = _predictor_counts(inputs)
    n = max(n, total_predictors + 2.01)
    df2 = n - total_predictors - 1
    crit = stats.f.ppf(1 - c["alpha"], tested, df2)
    return float(stats.ncf.sf(crit, tested, df2, abs(effect) * n))


def n_regression(inputs, c, effect, power):
    _, total_predictors = _predictor_counts(inputs)
    if abs(effect) <= 0:
        raise PlanningError("The effect size f² must be above 0.")
    return _solve_n(lambda n: power_regression(inputs, c, effect, n), power, total_predictors + 2.01)


def n_logistic(inputs, c, effect, power):
    odds_ratio = effect
    if odds_ratio <= 0 or abs(math.log(odds_ratio)) < 1e-6:
        raise PlanningError("The odds ratio must be above 0 and not equal to 1.")
    event_rate = _pct(inputs, "event_rate", None, "The event rate")
    r2 = _num(inputs, "r2_other", 0, -0.0001, 1, "R² with the other predictors")
    beta = math.log(odds_ratio)
    if str(inputs.get("predictor_type", "continuous")) == "binary":
        # Hsieh (1998) formula for a binary predictor with prevalence b.
        b = _pct(inputs, "predictor_prevalence", 50, "The predictor prevalence")
        p_bar = event_rate
        # Probabilities in unexposed (p0) and exposed (p1) giving the overall event rate.
        p0 = optimize.brentq(lambda x: (1 - b) * x + b * (odds_ratio * x / (1 - x + odds_ratio * x)) - p_bar, 1e-9, 1 - 1e-9)
        p1 = odds_ratio * p0 / (1 - p0 + odds_ratio * p0)
        n = ((_z_alpha(c) * math.sqrt(p_bar * (1 - p_bar) / b) + Z(power) * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1) * (1 - b) / b)) ** 2
             / ((p0 - p1) ** 2 * (1 - b)))
    else:
        n = (_z_alpha(c) + Z(power)) ** 2 / (event_rate * (1 - event_rate) * beta ** 2)
    return n / (1 - r2)


def n_logrank(inputs, c, effect, power):
    hazard_ratio = effect
    if hazard_ratio <= 0 or abs(math.log(hazard_ratio)) < 1e-6:
        raise PlanningError("The hazard ratio must be above 0 and not equal to 1.")
    k = c["ratio"]
    share = 1 / (1 + k)  # proportion in the reference group
    events = (_z_alpha(c) + Z(power)) ** 2 / (share * (1 - share) * math.log(hazard_ratio) ** 2)
    event_probability = _pct(inputs, "event_probability", None, "The proportion who will have the event during follow-up")
    return events / event_probability / (1 + k)


def n_mcnemar(inputs, c, effect, power):
    p10 = _pct(inputs, "p10", None, "The proportion changing from no to yes")
    p01 = effect
    psi = p10 + p01
    delta = abs(p10 - p01)
    if delta < 1e-6 or psi >= 1:
        raise PlanningError("The two discordant proportions must differ and add up to less than 100%.")
    return (_z_alpha(c) * math.sqrt(psi) + Z(power) * math.sqrt(psi - delta ** 2)) ** 2 / delta ** 2


def n_margin_trial(inputs, c, effect, power):
    """Non-inferiority (one margin) or equivalence (both margins) trials, mean or proportion outcome."""
    margin = _num(inputs, "margin", None, 0, None, "The margin")
    hypothesis = str(inputs.get("hypothesis", "noninferiority"))
    true_difference = effect
    if hypothesis == "equivalence":
        gap = margin - abs(true_difference)
        zb = Z(1 - (1 - power) / 2)
    else:
        gap = true_difference + margin
        zb = Z(power)
    if gap <= 0:
        raise PlanningError("The expected difference must lie inside the margin.")
    za = Z(1 - c["alpha"])  # one-sided by convention for these trials
    k = c["ratio"]
    if str(inputs.get("outcome", "mean")) == "proportion":
        p_control = _pct(inputs, "p_control", None, "The control proportion")
        p_new = p_control + true_difference / 100
        if not 0 < p_new < 1:
            raise PlanningError("The expected new-treatment proportion must be between 0% and 100%.")
        variance = p_new * (1 - p_new) + p_control * (1 - p_control) / k
        gap = gap / 100
    else:
        sd = _num(inputs, "sd", None, 0, None, "The standard deviation")
        variance = sd ** 2 * (1 + 1 / k)
    return (za + zb) ** 2 * variance / gap ** 2


def _auc_variance(a, n1, n0):
    q1, q2 = a / (2 - a), 2 * a * a / (1 + a)
    return (a * (1 - a) + (n1 - 1) * (q1 - a * a) + (n0 - 1) * (q2 - a * a)) / (n1 * n0)


def power_auc(inputs, c, effect, n_positive):
    auc0 = _num(inputs, "auc_null", 0.5, 0.4999, 0.99, "The null AUC")
    if not auc0 < effect < 1:
        raise PlanningError("The expected AUC must be above the null AUC and below 1.")
    n1 = max(n_positive, 2.0)
    n0 = c["ratio"] * n1  # negatives per positive
    z = (effect - auc0 - _z_alpha(c) * math.sqrt(_auc_variance(auc0, n1, n0))) / math.sqrt(_auc_variance(effect, n1, n0))
    return float(stats.norm.cdf(z))


def n_auc(inputs, c, effect, power):
    return _solve_n(lambda n: power_auc(inputs, c, effect, n), power, 2.0)


def n_single_proportion(inputs, c, effect, precision_level):
    p = _pct(inputs, "proportion", 50, "The expected proportion")
    z = Z(1 - (1 - precision_level) / 2)
    return z ** 2 * p * (1 - p) / effect ** 2


def n_single_mean(inputs, c, effect, precision_level):
    sd = _num(inputs, "sd", None, 0, None, "The standard deviation")
    z = Z(1 - (1 - precision_level) / 2)
    n = (z * sd / effect) ** 2
    for _ in range(50):  # replace z by t with n − 1 degrees of freedom
        t = stats.t.ppf(1 - (1 - precision_level) / 2, max(1, n - 1))
        updated = (t * sd / effect) ** 2
        if abs(updated - n) < 1e-6:
            break
        n = updated
    return n


def n_diagnostic(inputs, c, effect, precision_level):
    sensitivity = _pct(inputs, "sensitivity", None, "The expected sensitivity")
    specificity = _pct(inputs, "specificity", None, "The expected specificity")
    prevalence = _pct(inputs, "prevalence", None, "The prevalence")
    z = Z(1 - (1 - precision_level) / 2)
    for_sensitivity = z ** 2 * sensitivity * (1 - sensitivity) / effect ** 2 / prevalence
    for_specificity = z ** 2 * specificity * (1 - specificity) / effect ** 2 / (1 - prevalence)
    return max(for_sensitivity, for_specificity)


def riley_prediction(inputs, c):
    """Riley et al. (2019/2020) minimum sample size for a binary-outcome prediction model."""
    parameters = _num(inputs, "parameters", None, 0, 1000, "The number of predictor parameters")
    phi = _pct(inputs, "prevalence", None, "The outcome prevalence")
    shrinkage = _num(inputs, "shrinkage", 0.9, 0.5, 1, "The target shrinkage")
    ln_null = phi * math.log(phi) + (1 - phi) * math.log(1 - phi)
    max_r2 = 1 - math.exp(2 * ln_null)
    r2 = inputs.get("r2_cs")
    r2 = _num(inputs, "r2_cs", None, 0, max_r2, "The anticipated Cox-Snell R²") if r2 not in (None, "") else 0.15 * max_r2
    n1 = parameters / ((shrinkage - 1) * math.log(1 - r2 / shrinkage))
    delta = 0.05
    s2 = r2 / (r2 + delta * max_r2)
    n2 = parameters / ((s2 - 1) * math.log(1 - r2 / s2))
    n3 = (1.96 / 0.05) ** 2 * phi * (1 - phi)
    n = max(n1, n2, n3)
    return {"criteria": [{"name": "Shrinkage ≤ 10%", "n": math.ceil(n1)}, {"name": "Optimism in R² ≤ 0.05", "n": math.ceil(n2)},
                         {"name": "Precise overall risk (±0.05)", "n": math.ceil(n3)}],
            "n": n, "r2_cs": r2, "max_r2": max_r2, "events": math.ceil(n) * phi, "events_per_parameter": math.ceil(n) * phi / parameters}


PILOT_RULES = {"extra_small": 75, "small": 25, "medium": 15, "large": 10, "julious": 12}


DESIGNS = {
    "single_proportion": {"family": "estimate", "level": "basic", "kind": "precision", "groups": 1, "label": "Single proportion (prevalence)", "label_ar": "نسبة واحدة (الانتشار)",
                          "effect": "margin", "effect_label": "Margin of error", "unit": "%", "n_for": n_single_proportion, "fpc": True,
                          "inputs": ["proportion", "margin", "confidence", "population"], "method": "Precision of a single proportion (Wald / Cochran)",
                          "reference": "Cochran WG. Sampling Techniques. 3rd ed. Wiley; 1977."},
    "single_mean": {"family": "estimate", "level": "basic", "kind": "precision", "groups": 1, "label": "Single mean", "label_ar": "متوسط واحد",
                    "effect": "margin", "effect_label": "Margin of error", "unit": "", "n_for": n_single_mean, "fpc": True,
                    "inputs": ["sd", "margin", "confidence", "population"], "method": "Precision of a single mean (t-based)",
                    "reference": "Cochran WG. Sampling Techniques. 3rd ed. Wiley; 1977."},
    "two_proportions": {"family": "compare", "level": "basic", "kind": "power", "groups": 2, "label": "Two proportions", "label_ar": "نسبتان",
                        "effect": "p2", "effect_label": "Expected proportion in the comparison group", "unit": "%", "percent_effect": True, "bounds": (0.0001, 0.9999),
                        "n_for": n_two_proportions, "inputs": ["p1", "p2"], "method": "Two independent proportions (normal approximation, Fleiss)",
                        "reference": "Fleiss JL, Levin B, Paik MC. Statistical Methods for Rates and Proportions. 3rd ed. Wiley; 2003."},
    "two_means": {"family": "compare", "level": "basic", "kind": "power", "groups": 2, "label": "Two means", "label_ar": "متوسطان",
                  "effect": "difference", "effect_label": "Difference to detect", "unit": "", "bounds": (1e-6, 1e6), "n_for": n_two_means, "power_fn": power_two_means,
                  "inputs": ["difference", "sd"], "method": "Two-sample t test (as in G*Power)",
                  "reference": "Faul F, et al. G*Power 3.1. Behav Res Methods. 2009;41:1149-60."},
    "anova": {"family": "compare", "level": "advanced", "kind": "power", "groups": "k", "label": "Three or more groups (ANOVA)", "label_ar": "ثلاث مجموعات أو أكثر",
              "effect": "f", "effect_label": "Effect size f", "unit": "", "bounds": (1e-4, 5), "n_for": n_anova, "power_fn": power_anova,
              "inputs": ["groups", "f"], "method": "One-way ANOVA, noncentral F (as in G*Power)",
              "reference": "Cohen J. Statistical Power Analysis for the Behavioral Sciences. 2nd ed. 1988."},
    "paired_means": {"family": "change", "level": "basic", "kind": "power", "groups": 1, "label": "Before–after (paired means)", "label_ar": "قبل وبعد (متوسطات مترابطة)",
                     "effect": "difference", "effect_label": "Mean change to detect", "unit": "", "bounds": (1e-6, 1e6), "n_for": n_paired_means, "power_fn": power_paired_means,
                     "inputs": ["difference", "sd_diff"], "method": "Paired t test (as in G*Power)",
                     "reference": "Faul F, et al. G*Power 3.1. Behav Res Methods. 2009;41:1149-60."},
    "mcnemar": {"family": "change", "level": "advanced", "kind": "power", "groups": 1, "label": "Paired proportions (McNemar)", "label_ar": "نسب مترابطة (ماكنمار)",
                "effect": "p01", "effect_label": "Proportion changing from yes to no", "unit": "%", "percent_effect": True, "bounds": (0.0001, 0.9999),
                "n_for": n_mcnemar, "inputs": ["p10", "p01"], "method": "McNemar test (Connor 1987)",
                "reference": "Connor RJ. Sample size for testing differences in proportions for the paired-sample design. Biometrics. 1987;43:207-11."},
    "correlation": {"family": "relate", "level": "basic", "kind": "power", "groups": 1, "label": "Correlation", "label_ar": "الارتباط",
                    "effect": "r", "effect_label": "Correlation to detect", "unit": "", "bounds": (0.001, 0.999), "n_for": n_correlation,
                    "inputs": ["r"], "method": "Pearson correlation (Fisher z)",
                    "reference": "Hulley SB, et al. Designing Clinical Research. 4th ed. 2013."},
    "regression": {"family": "relate", "level": "advanced", "kind": "power", "groups": 1, "label": "Multiple regression (f²)", "label_ar": "الانحدار المتعدد",
                   "effect": "f2", "effect_label": "Effect size f²", "unit": "", "bounds": (1e-4, 10), "n_for": n_regression, "power_fn": power_regression,
                   "inputs": ["f2", "tested_predictors", "total_predictors"], "method": "Linear multiple regression, noncentral F (as in G*Power)",
                   "reference": "Cohen J. Statistical Power Analysis for the Behavioral Sciences. 2nd ed. 1988."},
    "logistic": {"family": "relate", "level": "advanced", "kind": "power", "groups": 1, "label": "Logistic regression (Hsieh)", "label_ar": "الانحدار اللوجستي",
                 "effect": "odds_ratio", "effect_label": "Odds ratio to detect", "unit": "", "bounds": (1.0001, 100), "n_for": n_logistic,
                 "inputs": ["odds_ratio", "event_rate", "predictor_type", "r2_other"], "method": "Logistic regression (Hsieh, Bloch and Larsen 1998)",
                 "reference": "Hsieh FY, Bloch DA, Larsen MD. A simple method of sample size calculation for linear and logistic regression. Stat Med. 1998;17:1623-34."},
    "logrank": {"family": "survival", "level": "basic", "kind": "power", "groups": 2, "label": "Time to event (log-rank)", "label_ar": "الزمن حتى الحدث",
                "effect": "hazard_ratio", "effect_label": "Hazard ratio to detect", "unit": "", "bounds": (0.01, 0.9999), "n_for": n_logrank,
                "inputs": ["hazard_ratio", "event_probability"], "method": "Log-rank test (Schoenfeld)",
                "reference": "Schoenfeld DA. Sample-size formula for the proportional-hazards regression model. Biometrics. 1983;39:499-503."},
    "noninferiority": {"family": "trial", "level": "advanced", "kind": "power", "groups": 2, "label": "Non-inferiority / equivalence", "label_ar": "عدم الأدنوية / التكافؤ",
                       "effect": "true_difference", "effect_label": "Expected true difference", "unit": "", "bounds": None, "n_for": n_margin_trial,
                       "inputs": ["hypothesis", "outcome", "margin", "true_difference", "sd", "p_control"], "method": "Non-inferiority / equivalence (one-sided α)",
                       "reference": "Julious SA. Sample sizes for clinical trials with normal data. Stat Med. 2004;23:1921-86."},
    "diagnostic": {"family": "diagnostic", "level": "basic", "kind": "precision", "groups": 1, "label": "Sensitivity & specificity", "label_ar": "الحساسية والنوعية",
                   "effect": "margin", "effect_label": "Margin of error", "unit": "%", "n_for": n_diagnostic,
                   "inputs": ["sensitivity", "specificity", "prevalence", "margin", "confidence"], "method": "Diagnostic accuracy precision (Buderer)",
                   "reference": "Buderer NM. Statistical methodology: incorporating the prevalence of disease. Acad Emerg Med. 1996;3:895-900."},
    "auc": {"family": "diagnostic", "level": "advanced", "kind": "power", "groups": 2, "label": "ROC / AUC", "label_ar": "منحنى ROC",
            "effect": "auc", "effect_label": "Expected AUC", "unit": "", "bounds": None, "n_for": n_auc, "power_fn": power_auc,
            "inputs": ["auc", "auc_null"], "method": "AUC compared with a null value (Hanley-McNeil)",
            "reference": "Hanley JA, McNeil BJ. The meaning and use of the area under a ROC curve. Radiology. 1982;143:29-36."},
    "prediction": {"family": "diagnostic", "level": "advanced", "kind": "rule", "groups": 1, "label": "Prediction model (Riley)", "label_ar": "نموذج تنبؤي (رايلي)",
                   "inputs": ["parameters", "prevalence", "r2_cs"], "method": "Minimum sample size for a binary-outcome prediction model (Riley et al.)",
                   "reference": "Riley RD, et al. Calculating the sample size required for developing a clinical prediction model. BMJ. 2020;368:m441."},
    "pilot": {"family": "pilot", "level": "basic", "kind": "rule", "groups": "arms", "label": "Pilot study", "label_ar": "دراسة تجريبية",
              "inputs": ["pilot_rule", "arms"], "method": "Pilot trial sample size (Whitehead 2016; Julious 2005)",
              "reference": "Whitehead AL, et al. Estimating the sample size for a pilot randomised trial. Stat Methods Med Res. 2016;25:1057-73."},
}

FAMILIES = [
    {"id": "estimate", "label": "Estimate", "label_ar": "التقدير"},
    {"id": "compare", "label": "Compare groups", "label_ar": "مقارنة المجموعات"},
    {"id": "trial", "label": "Clinical trials", "label_ar": "التجارب السريرية"},
    {"id": "change", "label": "Before–after", "label_ar": "قبل وبعد"},
    {"id": "relate", "label": "Relationships", "label_ar": "العلاقات"},
    {"id": "survival", "label": "Time to event", "label_ar": "الزمن حتى الحدث"},
    {"id": "diagnostic", "label": "Diagnostic & prediction", "label_ar": "التشخيص والتنبؤ"},
    {"id": "pilot", "label": "Pilot & feasibility", "label_ar": "الدراسات التجريبية"},
]


def design_modes(design):
    if design["kind"] == "rule":
        return ["n"]
    if design["kind"] == "precision":
        return ["n", "precision"]
    if design["effect"] == "true_difference":
        return ["n", "power"]
    return ["n", "power", "mde"]


def catalog():
    return {"families": FAMILIES, "designs": [
        {"id": key, "modes": design_modes(design), **{k: v for k, v in design.items() if k not in {"n_for", "bounds", "power_fn"}}} for key, design in DESIGNS.items()]}


# ── Solving ───────────────────────────────────────────────────────────────────

def _effect_value(design, inputs):
    key = design["effect"]
    if key == "p2" and inputs.get("relative_risk") not in (None, ""):
        p1 = _pct(inputs, "p1", None, "The risk in the unexposed group")
        p2 = p1 * _num(inputs, "relative_risk", None, 0, None, "The relative risk")
        if not 0 < p2 < 1:
            raise PlanningError("This relative risk gives a risk above 100% in the exposed group. Use a smaller relative risk.")
        return p2
    if key == "p2" and inputs.get("odds_ratio_exposure") not in (None, ""):
        p1 = _pct(inputs, "p1", None, "The exposure among controls")
        odds = _num(inputs, "odds_ratio_exposure", None, 0, None, "The odds ratio") * p1 / (1 - p1)
        return odds / (1 + odds)
    if design.get("percent_effect"):
        return _pct(inputs, key, None, design["effect_label"])
    if key == "margin" and design["unit"] == "%":
        return _pct(inputs, key, None, "The margin of error")
    if key == "true_difference":
        return _num(inputs, key, 0, label=design["effect_label"])
    return _num(inputs, key, None, label=design["effect_label"])


def _groups(design, inputs, c):
    if design["groups"] == "k":
        return int(_num(inputs, "groups", 3, 1.5, 21, "The number of groups"))
    return design["groups"] if isinstance(design["groups"], int) else 1


def _allocate(design, inputs, c, n_first):
    """Completers per group from the first-group n (before design effect and dropout)."""
    groups = _groups(design, inputs, c)
    if design["groups"] == 2:
        return [n_first, n_first * c["ratio"]]
    return [n_first] * groups


def _adjust(design, inputs, c, completers):
    """Round up completers, then apply design effect, finite population correction, response rate and dropout.

    Each group also records its intermediate numbers so the page can show how the answer was reached.
    """
    population = inputs.get("population")
    per_group = []
    for value in completers:
        base = math.ceil(value - 1e-9)
        n = value * c["deff"]
        after_deff = math.ceil(n - 1e-9)
        after_population = None
        if design.get("fpc") and population not in (None, ""):
            size = _num(inputs, "population", None, 1, None, "The population size")
            n = n / (1 + (n - 1) / size)
            after_population = math.ceil(n - 1e-9)
        completing = math.ceil(n - 1e-9)
        recruited = math.ceil(completing / c["keep"] - 1e-9)
        per_group.append({"completers": completing, "recruit": recruited, "base": base,
                          "after_design_effect": after_deff, "after_population": after_population})
    return per_group


def _steps(c, per_group):
    """How the total was reached, for display: base, design effect, population, response and dropout."""
    def total(key):
        return sum(g[key] for g in per_group if g.get(key) is not None)

    steps = [{"key": "base", "n": total("base")}]
    if c["deff"] > 1:
        steps.append({"key": "design_effect", "n": total("after_design_effect"), "factor": round(c["deff"], 3)})
    if any(g.get("after_population") is not None for g in per_group):
        steps.append({"key": "population", "n": total("after_population")})
    if c["response"] < 1 or c["dropout"] > 0:
        steps.append({"key": "loss", "n": total("recruit"), "response": c["response"], "dropout": c["dropout"]})
    return steps


def _search_effect(design, inputs, c, n_first, power):
    """Smallest effect detectable with n_first completers in the first group."""
    def n_for(inputs, c, effect, power):
        try:
            return design["n_for"](inputs, c, effect, power)
        except PlanningError:
            return 1e12

    if design.get("power_fn"):
        if design["effect"] == "auc":
            low, high = _num(inputs, "auc_null", 0.5, 0.4999, 0.99) + 1e-4, 0.9999
        else:
            low = design["bounds"][0]
            high = max(abs(_effect_value(design, inputs)), low * 10)
            for _ in range(80):  # widen until the effect is large enough to reach the target power
                if design["power_fn"](inputs, c, high, n_first) >= power or high >= design["bounds"][1]:
                    break
                high = min(high * 2, design["bounds"][1])
        g = lambda e: design["power_fn"](inputs, c, e, n_first) - power
        if g(high) < 0:
            return None
        if g(low) >= 0:
            return low
        return optimize.brentq(g, low, high)
    key = design["effect"]
    if key == "p2" or key == "p01":
        base = _pct(inputs, "p1" if key == "p2" else "p10", None)
        planned = _effect_value(design, inputs)
        direction = 1 if planned >= base else -1
        lower, upper = (base + 1e-4, 0.9999) if direction == 1 else (1e-4, base - 1e-4)
        f = lambda e: n_for(inputs, c, e, power) - n_first
        if f(upper if direction == 1 else lower) > 0:
            return None
        return optimize.brentq(f, lower, upper)
    if key == "hazard_ratio":
        f = lambda e: n_for(inputs, c, e, power) - n_first
        return optimize.brentq(f, 1e-3, 0.9999) if f(1e-3) < 0 else None
    if key == "odds_ratio":
        f = lambda e: n_for(inputs, c, e, power) - n_first
        return optimize.brentq(f, 1.0001, 1000) if f(1000) < 0 else None
    if key == "auc":
        auc0 = _num(inputs, "auc_null", 0.5, 0.4999, 0.99)
        f = lambda e: n_for(inputs, c, e, power) - n_first
        return optimize.brentq(f, auc0 + 1e-4, 0.9999) if f(0.9999) < 0 else None
    if key == "true_difference":
        return None
    low, high = design["bounds"]
    f = lambda e: n_for(inputs, c, e, power) - n_first
    if f(high) > 0:
        return None
    return optimize.brentq(f, low, high)


def _power_for(design, inputs, c, n_first, effect):
    if design.get("power_fn"):
        return design["power_fn"](inputs, c, effect, max(n_first, 2.0))
    def f(p):
        try:
            return design["n_for"](inputs, c, effect, p) - n_first
        except (PlanningError, ValueError):
            return 1e12
    low, high = c["alpha"] / c["sides"] + 1e-6, 0.999999
    if f(low) >= 0:
        return c["alpha"] / c["sides"]
    if f(high) <= 0:
        return high
    return optimize.brentq(f, low, high)


def _precision_for(design, inputs, c, n_first, level):
    n_for = design["n_for"]
    f = lambda e: n_for(inputs, c, e, level) - n_first
    return optimize.brentq(f, 1e-6, 1e6 if design["unit"] != "%" else 0.9999)


def _recruit_to_completers(c, recruit):
    return recruit * c["keep"] / c["deff"]


def calculate(design_id: str, mode: str, inputs: dict) -> dict:
    design = DESIGNS.get(design_id)
    if design is None:
        raise PlanningError("Unknown design.")
    c = _common(inputs)
    warnings = []
    if design["kind"] == "rule":
        return _rule_design(design_id, design, inputs, c)

    if design["kind"] == "precision":
        level = _pct(inputs, "confidence", 95, "The confidence level")
        if mode == "precision":
            recruit = _num(inputs, "n_available", None, 1, None, "The number of participants")
            n_first = _recruit_to_completers(c, recruit)
            margin = _precision_for(design, inputs, c, n_first, level)
            effect_out = margin
            per_group = _adjust(design, inputs, c, [n_first])
            answer = {"kind": "precision", "value": margin}
        else:
            margin = _effect_value(design, inputs)
            n_first = design["n_for"](inputs, c, margin, level)
            per_group = _adjust(design, inputs, c, [n_first])
            effect_out = margin
            answer = {"kind": "n"}
        if design_id == "single_proportion":
            p = _pct(inputs, "proportion", 50)
            if effect_out >= min(p, 1 - p):
                warnings.append("The margin of error is as large as the expected proportion, so the interval would cross 0% or 100%. Use a smaller margin or a relative precision.")
        population = inputs.get("population")
        if population not in (None, "") and sum(g["recruit"] for g in per_group) > float(population):
            warnings.append("The required sample is larger than the population: survey everyone.")
        result = _assemble(design_id, design, inputs, c, mode, per_group, effect_out, None, answer, warnings, level=level)
        return result

    planned_power = c["power"]
    if mode == "power":
        recruit = _num(inputs, "n_available", None, 1, None, "The number of participants per group")
        n_first = _recruit_to_completers(c, recruit)
        effect = _effect_value(design, inputs)
        achieved = _power_for(design, inputs, c, n_first, effect)
        per_group = _adjust(design, inputs, c, _allocate(design, inputs, c, n_first))
        needed = design["n_for"](inputs, c, effect, planned_power)
        answer = {"kind": "power", "value": achieved, "needed": _adjust(design, inputs, c, _allocate(design, inputs, c, needed))}
        if achieved < 0.8:
            warnings.append(f"Power is below 80%: there is a {1 - achieved:.0%} chance of missing a true effect of this size.")
        effect_out, power_out = effect, achieved
    elif mode == "mde":
        if "mde" not in design_modes(design):
            raise PlanningError("For this design, calculate the sample size or the power.")
        recruit = _num(inputs, "n_available", None, 1, None, "The number of participants per group")
        n_first = _recruit_to_completers(c, recruit)
        detectable = _search_effect(design, inputs, c, n_first, planned_power)
        if detectable is None:
            raise PlanningError("No effect within a realistic range can be detected with this number of participants.")
        per_group = _adjust(design, inputs, c, _allocate(design, inputs, c, n_first))
        answer = {"kind": "mde", "value": detectable}
        effect_out, power_out = detectable, planned_power
    else:
        effect = _effect_value(design, inputs)
        n_first = design["n_for"](inputs, c, effect, planned_power)
        per_group = _adjust(design, inputs, c, _allocate(design, inputs, c, n_first))
        answer = {"kind": "n"}
        effect_out, power_out = effect, planned_power
    return _assemble(design_id, design, inputs, c, mode, per_group, effect_out, power_out, answer, warnings)


def _standardized(design_id, inputs, effect):
    try:
        if design_id == "two_means":
            return {"label": "Cohen's d", "value": abs(effect) / _two_means(inputs, None)}
        if design_id == "paired_means":
            sd_diff = inputs.get("sd_diff")
            if sd_diff in (None, ""):
                sd_diff = float(inputs["sd"]) * math.sqrt(2 * (1 - float(inputs.get("pre_post_correlation", 0.5))))
            return {"label": "Cohen's dz", "value": abs(effect) / float(sd_diff)}
        if design_id == "two_proportions":
            p1 = float(inputs["p1"]) / 100
            return {"label": "Cohen's h", "value": abs(2 * math.asin(math.sqrt(effect)) - 2 * math.asin(math.sqrt(p1)))}
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    return None


def _curve(design, inputs, c, effect, per_group):
    """Power against recruited participants per group, for the chart."""
    if design["kind"] != "power" or effect is None:
        return []
    target = per_group[0]["recruit"]
    points = []
    for recruit in np.unique(np.linspace(max(2, target * 0.2), target * 2, 24).round().astype(int)):
        try:
            power = _power_for(design, inputs, c, _recruit_to_completers(c, float(recruit)), effect)
        except (PlanningError, ValueError, ZeroDivisionError):
            continue
        points.append({"n": int(recruit), "power": round(float(power), 4)})
    return points


def _scenarios(design_id, design, inputs, c, effect):
    if design["kind"] != "power" or effect is None or design["effect"] in {"true_difference"}:
        return None
    if design.get("percent_effect"):
        base = _pct(inputs, "p1" if design["effect"] == "p2" else "p10", None)
        gap = effect - base
        values = [base + gap * factor for factor in (0.8, 1.0, 1.2)]
    elif design["effect"] in {"hazard_ratio", "odds_ratio"}:
        log = math.log(effect)
        values = [math.exp(log * factor) for factor in (0.8, 1.0, 1.2)]
    elif design["effect"] == "auc":
        auc0 = _num(inputs, "auc_null", 0.5, 0.4999, 0.99)
        values = [auc0 + (effect - auc0) * factor for factor in (0.8, 1.0, 1.2)]
    else:
        values = [effect * factor for factor in (0.8, 1.0, 1.2)]
    rows = []
    for value in values:
        row = {"effect": value, "current": abs(value - effect) < 1e-12}
        for power in (0.8, 0.9):
            try:
                completers = _allocate(design, inputs, c, design["n_for"](inputs, c, value, power))
                row[f"p{int(power * 100)}"] = math.ceil(completers[0] - 1e-9)
            except (PlanningError, ValueError, ZeroDivisionError):
                row[f"p{int(power * 100)}"] = None
        rows.append(row)
    return rows


def _rule_design(design_id, design, inputs, c):
    if design_id == "prediction":
        riley = riley_prediction(inputs, c)
        completers = math.ceil(riley["n"])
        recruit = math.ceil(completers / c["keep"])
        result = {"design": design_id, "label": design["label"], "label_ar": design["label_ar"], "mode": "n", "method": design["method"],
                  "reference": design["reference"], "per_group": [{"completers": completers, "recruit": recruit}],
                  "total": {"completers": completers, "recruit": recruit}, "answer": {"kind": "n"}, "criteria": riley["criteria"],
                  "extra": {"events": round(riley["events"], 1), "events_per_parameter": round(riley["events_per_parameter"], 1),
                            "r2_cs": round(riley["r2_cs"], 4), "max_r2": round(riley["max_r2"], 4)},
                  "warnings": [] if inputs.get("r2_cs") not in (None, "") else ["No Cox-Snell R² was entered, so 15% of the maximum possible was assumed (a conservative default)."],
                  "curve": [], "scenarios": None}
        result.update(_writeup(design_id, design, inputs, c, result, None, None))
        return result
    rule = str(inputs.get("pilot_rule", "medium"))
    per_arm = PILOT_RULES.get(rule, 15)
    arms = int(_num(inputs, "arms", 2, 0.5, 10, "The number of arms"))
    recruit = math.ceil(per_arm / c["keep"])
    result = {"design": design_id, "label": design["label"], "label_ar": design["label_ar"], "mode": "n", "method": design["method"], "reference": design["reference"],
              "per_group": [{"completers": per_arm, "recruit": recruit} for _ in range(arms)],
              "total": {"completers": per_arm * arms, "recruit": recruit * arms}, "answer": {"kind": "n"}, "warnings": [], "curve": [], "scenarios": None,
              "extra": {"rule": rule, "per_arm": per_arm, "arms": arms}}
    result.update(_writeup(design_id, design, inputs, c, result, None, None))
    return result


def _assemble(design_id, design, inputs, c, mode, per_group, effect, power, answer, warnings, level=None):
    total = {"completers": sum(g["completers"] for g in per_group), "recruit": sum(g["recruit"] for g in per_group)}
    if c["cluster"]:
        size = c["cluster"]["cluster_size"]
        total["clusters"] = [math.ceil(g["recruit"] / size) for g in per_group]
    if design_id == "logrank":
        share = 1 / (1 + c["ratio"])
        events = (_z_alpha(c) + Z(power or c["power"])) ** 2 / (share * (1 - share) * math.log(effect) ** 2)
        total["events"] = math.ceil(events)
    result = {
        "design": design_id, "label": design["label"], "label_ar": design["label_ar"], "mode": mode, "method": design["method"], "reference": design["reference"],
        "per_group": per_group, "total": total, "steps": _steps(c, per_group), "answer": answer, "effect": effect, "power": power, "confidence": level,
        "standardized": _standardized(design_id, inputs, effect) if effect is not None else None,
        "settings": {"alpha": c["alpha"], "sides": c["sides"], "ratio": c["ratio"], "dropout": c["dropout"], "design_effect": round(c["deff"], 4), "cluster": c["cluster"]},
        "warnings": warnings,
        "curve": _curve(design, inputs, c, effect, per_group),
        "scenarios": _scenarios(design_id, design, inputs, c, effect) if mode == "n" else None,
    }
    if c["sides"] == 1 and design["kind"] == "power" and design_id != "noninferiority":
        warnings.append("A one-sided test needs a strong justification in the protocol; most journals expect two-sided tests.")
    result.update(_writeup(design_id, design, inputs, c, result, effect, power))
    return result


# ── Write-up ──────────────────────────────────────────────────────────────────

def _fmt(value, digits=2):
    text = f"{value:.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _effect_text(design_id, inputs, effect, lang):
    unit = str(inputs.get("unit", "")).strip()
    unit_text = f" {unit}" if unit else ""
    if design_id == "two_means":
        sd = _num(inputs, "sd", None)
        return (f"a difference of {_fmt(effect)}{unit_text} (SD {_fmt(sd)}{unit_text})" if lang == "en"
                else f"فرق مقداره {_fmt(effect)}{unit_text} (انحراف معياري {_fmt(sd)}{unit_text})")
    if design_id == "paired_means":
        return (f"a mean change of {_fmt(effect)}{unit_text}" if lang == "en" else f"تغير متوسط مقداره {_fmt(effect)}{unit_text}")
    if design_id == "two_proportions":
        p1 = _pct(inputs, "p1", None)
        if inputs.get("relative_risk") not in (None, ""):
            rr = effect / p1
            return (f"a relative risk of {_fmt(rr)} (risk {p1:.1%} in the unexposed and {effect:.1%} in the exposed group)" if lang == "en"
                    else f"خطر نسبي مقداره {_fmt(rr)} (الخطر {p1:.1%} لدى غير المعرّضين و{effect:.1%} لدى المعرّضين)")
        if inputs.get("odds_ratio_exposure") not in (None, ""):
            odds_ratio = (effect / (1 - effect)) / (p1 / (1 - p1))
            return (f"an odds ratio of {_fmt(odds_ratio)} (exposure {p1:.1%} among controls and {effect:.1%} among cases)" if lang == "en"
                    else f"نسبة أرجحية مقدارها {_fmt(odds_ratio)} (التعرض {p1:.1%} لدى الضوابط و{effect:.1%} لدى الحالات)")
        return (f"a difference between {p1:.0%} and {effect:.0%}" if lang == "en" else f"فرق بين {p1:.0%} و{effect:.0%}")
    if design_id == "anova":
        return f"an effect size f of {_fmt(effect)}" if lang == "en" else f"حجم أثر f مقداره {_fmt(effect)}"
    if design_id == "correlation":
        return f"a correlation of r = {_fmt(effect)}" if lang == "en" else f"ارتباط مقداره r = {_fmt(effect)}"
    if design_id == "regression":
        return f"an effect size f² of {_fmt(effect, 3)}" if lang == "en" else f"حجم أثر f² مقداره {_fmt(effect, 3)}"
    if design_id == "logistic":
        return f"an odds ratio of {_fmt(effect)}" if lang == "en" else f"نسبة أرجحية مقدارها {_fmt(effect)}"
    if design_id == "logrank":
        return f"a hazard ratio of {_fmt(effect)}" if lang == "en" else f"نسبة خطر مقدارها {_fmt(effect)}"
    if design_id == "mcnemar":
        return f"discordant proportions of {_pct(inputs, 'p10', None):.0%} and {effect:.0%}" if lang == "en" else "نسبتي التغير المتوقعتين"
    if design_id == "auc":
        return f"an AUC of {_fmt(effect)}" if lang == "en" else f"مساحة تحت المنحنى مقدارها {_fmt(effect)}"
    if design_id == "noninferiority":
        return (f"a true difference of {_fmt(effect)} with a margin of {_fmt(_num(inputs, 'margin', None))}" if lang == "en"
                else f"فرق حقيقي مقداره {_fmt(effect)} مع هامش {_fmt(_num(inputs, 'margin', None))}")
    return ""


def _group_names(inputs, count):
    """Optional plain names for the groups, in engine order (e.g. "controls,cases")."""
    raw = str(inputs.get("group_names", "") or "")
    names = [name.strip() for name in raw.split(",") if name.strip()][:count]
    return names if len(names) == count else None


def _writeup(design_id, design, inputs, c, result, effect, power):
    text = _writeup_text(design_id, design, inputs, c, result, effect, power)
    method_en = f" Method: {design['method']}; {design['reference']}"
    return {"writeup_en": text["writeup_en"] + method_en, "writeup_ar": text["writeup_ar"]}


def _writeup_text(design_id, design, inputs, c, result, effect, power):
    per_group = result["per_group"]
    total = result["total"]
    dropout = c["dropout"]
    groups_en = "per group" if len(per_group) > 1 else "participants"
    alpha_en = f"{'two' if c['sides'] == 2 else 'one'}-sided α of {_fmt(c['alpha'], 3)}"
    alpha_ar = f"مستوى دلالة {_fmt(c['alpha'], 3)} ({'ثنائي' if c['sides'] == 2 else 'أحادي'} الطرف)"
    parts_en = [f"a response rate of {c['response']:.0%}" if c["response"] < 1 else "", f"{dropout:.0%} dropout" if dropout > 0 else ""]
    parts_ar = [f"معدل استجابة {c['response']:.0%}" if c["response"] < 1 else "", f"نسبة انسحاب {dropout:.0%}" if dropout > 0 else ""]
    losses_en = " and ".join(part for part in parts_en if part)
    losses_ar = " و".join(part for part in parts_ar if part)
    invite = "invited" if c["response"] < 1 else "recruited"
    names = _group_names(inputs, len(per_group))
    if len(per_group) > 1 and names:
        per_group_text = " (" + " and ".join(f"{g['recruit']} {name}" for g, name in zip(per_group, names)) + ")."
    else:
        per_group_text = f" ({per_group[0]['recruit']} per group)." if len(per_group) > 1 else "."
    drop_en = f" Allowing for {losses_en}, {total['recruit']} participants will be {invite}{per_group_text}" if losses_en else ""
    drop_ar = f" ومع احتساب {losses_ar}، سيُدعى {total['recruit']} مشاركاً." if losses_ar else ""
    deff_en = f" A design effect of {_fmt(c['deff'])} was applied" + (f" (ICC {_fmt(c['cluster']['icc'], 3)}, {_fmt(c['cluster']['cluster_size'], 0)} per cluster)." if c["cluster"] else ".") if c["deff"] > 1 else ""
    reference = ""
    if design_id == "prediction":
        extra = result["extra"]
        en = (f"Following Riley et al., a prediction model with {_fmt(_num(inputs, 'parameters', None), 0)} candidate parameters, an outcome prevalence of "
              f"{_pct(inputs, 'prevalence', None):.1%} and an anticipated Cox-Snell R² of {extra['r2_cs']:.3f} requires at least {per_group[0]['completers']} participants "
              f"({extra['events']:.0f} events; {extra['events_per_parameter']:.1f} events per parameter).{drop_en}")
        ar = f"وفقاً لرايلي وزملائه، يتطلب النموذج التنبؤي {per_group[0]['completers']} مشاركاً على الأقل ({extra['events']:.0f} حدثاً).{drop_ar}"
        return {"writeup_en": en, "writeup_ar": ar}
    if design_id == "pilot":
        extra = result["extra"]
        en = (f"For this pilot study, {extra['per_arm']} participants per arm ({extra['per_arm'] * extra['arms']} in total across {extra['arms']} arm"
              f"{'s' if extra['arms'] != 1 else ''}) were planned, following published guidance for pilot trials{reference}.{drop_en}")
        ar = f"خُطط لـ {extra['per_arm']} مشاركاً في كل ذراع ({extra['per_arm'] * extra['arms']} إجمالاً) وفق الإرشادات المنشورة للدراسات التجريبية.{drop_ar}"
        return {"writeup_en": en, "writeup_ar": ar}
    if design["kind"] == "precision":
        level = result["confidence"]
        margin = result["effect"]
        margin_text = f"±{margin:.1%}" if design["unit"] == "%" else f"±{_fmt(margin)}"
        if design_id == "single_proportion":
            basis = f"an expected proportion of {_pct(inputs, 'proportion', 50):.0%}"
        elif design_id == "single_mean":
            basis = f"a standard deviation of {_fmt(_num(inputs, 'sd', None))}"
        else:
            basis = (f"an expected sensitivity of {_pct(inputs, 'sensitivity', None):.0%}, specificity of {_pct(inputs, 'specificity', None):.0%} "
                     f"and prevalence of {_pct(inputs, 'prevalence', None):.0%}")
        en = (f"A sample of {total['completers']} participants gives a {level:.0%} confidence interval of {margin_text}, assuming {basis}"
              f"{reference}.{deff_en}{drop_en}")
        ar = f"يُعطي حجم عينة قدره {total['completers']} مشاركاً فترة ثقة {level:.0%} بهامش {margin_text}.{drop_ar}"
        return {"writeup_en": en, "writeup_ar": ar}
    effect_en = _effect_text(design_id, inputs, effect, "en")
    effect_ar = _effect_text(design_id, inputs, effect, "ar")
    names = _group_names(inputs, len(per_group))
    if len(per_group) > 1 and names:
        size_en = " and ".join(f"{g['completers']} {name}" for g, name in zip(per_group, names)) + f" ({total['completers']} in total)"
    elif len(per_group) > 1 and len(set(g['completers'] for g in per_group)) == 1:
        size_en = f"{per_group[0]['completers']} participants per group ({total['completers']} in total)"
    elif len(per_group) > 1:
        size_en = ", ".join(f"{g['completers']}" for g in per_group) + f" participants in the {len(per_group)} groups ({total['completers']} in total)"
    else:
        size_en = f"{total['completers']} participants"
    if design_id == "logrank":
        size_en += f", with {total['events']} events required"
    en = f"A sample of {size_en} provides {power:.0%} power to detect {effect_en}, with a {alpha_en}{reference}.{deff_en}{drop_en}"
    ar = f"يوفّر حجم عينة قدره {total['completers']} مشاركاً قوة إحصائية {power:.0%} لاكتشاف {effect_ar}، عند {alpha_ar}.{drop_ar}"
    if result["mode"] == "power":
        en = f"With {size_en}, the study has {power:.0%} power to detect {effect_en} ({alpha_en}){reference}.{deff_en}"
        ar = f"مع {total['completers']} مشاركاً، تبلغ القوة الإحصائية للدراسة {power:.0%} لاكتشاف {effect_ar}."
    if result["mode"] == "mde":
        en = f"With {size_en}, the study has {power:.0%} power to detect {effect_en} or larger ({alpha_en}){reference}.{deff_en}"
        ar = f"مع {total['completers']} مشاركاً، تستطيع الدراسة بقوة {power:.0%} اكتشاف {effect_ar} أو أكبر."
    return {"writeup_en": en, "writeup_ar": ar}
