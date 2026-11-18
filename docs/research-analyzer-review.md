# Research Analyzer — Review and Rebuild Plan

_Review date: 23 October 2026. Branch `resref-workspace`._

## 1. Verdict in one paragraph

The calculations at the heart of the analyzer are mostly correct. t tests, ANOVA, chi-square,
correlation, Cronbach's alpha and regression coefficients match scipy, statsmodels and pingouin.
What is wrong is everything **around** the calculations:

- the tool does not know what study the researcher is doing
- it lets people pick tests that do not fit their data
- it misreads some data silently
- the written output is generic

So the owner's impression is right: it is not organised around how a researcher works. Keep the
maths, fix the bugs below, and rebuild the flow, test choice and reporting around a **study design**
and a **research question**.

## 2. How it was reviewed

- **Code review** of the engine:
  - `backend/research_analyzer/services/stats_service.py` (1,413 lines)
  - `data_service.py` (477 lines)
  - `views.py`
  - the React feature (about 2,600 lines of JSX plus a 2,341-line CSS file)
- **Numbers checked against reference libraries** (scipy / statsmodels / pingouin).
- **Three realistic users run end to end in a real browser**, with about 45 screenshots kept locally
  (not in the repo):

  | User | Dataset |
  |---|---|
  | Student | `survey_burnout.csv`: 120 respondents, 5 Likert items (one reverse-worded), sleep hours, year of study |
  | Clinician | `trial_htn.csv`: 80-patient hypertension trial, two drugs, baseline and week-12 blood pressure, adverse events |
  | Researcher | `diagnostic_rapid.csv`: 150 cases, rapid test vs PCR, Ct value only recorded for positives |

## 3. What actually went wrong for real users

| # | What the user did | What happened | Why it matters |
|---|---|---|---|
| 1 | Student ran Cronbach's alpha | The default item list included **respondent ID and sleep hours**. The reverse-worded item was not flagged; α = 0.425 "unacceptable". | A wrong conclusion about the questionnaire. The tool should have asked "is q5 reverse-worded?" (its item-total r was −0.77). |
| 2 | Student compared one Likert item by gender | A t test ran on a 1–5 item and the complete-case count showed "—". | Ordinal data treated as continuous, plus a display bug. |
| 3 | Student ran ANOVA | ω² = 0.024 was labelled a **"large effect"**. | Effect-size labels are shifted by one band. |
| 4 | Clinician ran chi-square on drug × adverse event | A cell had only 2 events; χ² gave p = .051. No Fisher test, odds ratio or risk ratio was offered. | Exactly what a journal reviewer asks for. Fisher is listed in the UI but does not exist. |
| 5 | Clinician ran logistic regression for adverse events | It modelled **"No" as the event**. VIF showed 21–22 for age and BMI, a false collinearity alarm. Sensitivity was 100% and specificity 9%. | Odds ratios are inverted. VIF is computed without an intercept. |
| 6 | Clinician made "Table 1" | One overall column only: no split by treatment arm and no p-values. | The most common table in a clinical paper is not really produced. |
| 7 | Clinician opened Master Report | Header said **7 analyses**; the body listed 5, plus extra tests the user never asked for. | Confusing, and it adds tests silently. |
| 8 | Researcher used "Exclude rows with missing values" | **96 of 150 rows deleted**, because Ct is missing for every negative case. The next test then failed with an error. | One click destroyed the dataset. There was no warning and no undo. |
| 9 | Researcher looked for sensitivity / specificity | Not available. | Diagnostic accuracy studies cannot be analysed at all. |
| 10 | Several uploads in a few minutes | "Too many uploads" (HTTP 429). | The limit is too tight for normal trial-and-error. |
| 11 | Semicolon-separated CSV | Read as **one column**, with no error. | Common in Europe and the Middle East. There is no delimiter detection. |
| 12 | Arabic Excel-exported CSV (cp1256) | Text corrupted. | Breaks the Arabic audience the site targets. |
| 13 | Roles auto-detected | `bp_controlled` was guessed as a *grouping* variable, not an outcome, and `sbp_week12` was left unspecified. The auto plan then used these guesses as if confirmed, and picked `sex` as the comparison group instead of `treatment_group`. | The wrong study gets analysed automatically. |
| 14 | Every result page | The Methods text reads like "Test X was used to analyse burnout_q1, gender…". | Not manuscript-ready. The study design field is collected but never used. |

## 4. Engine bugs (from the code review)

**Fix first (wrong numbers or wrong conclusions)**

1. VIF computed without an intercept, giving false multicollinearity warnings (`stats_service.py` ≈ 728–739).
2. The logistic "event" category depends on row order, so ORs can be inverted (≈ 818, 823).
3. Perfect separation reports "success" with absurd ORs instead of a warning (≈ 831–834).
4. Effect-size labels shifted one band (≈ 913, 979, 1027).
5. The automatic plan uses unconfirmed suggested roles and picks the first grouping variable.
6. cp1256 / Windows-Arabic CSVs corrupted (`data_service.py` ≈ 200); no delimiter sniffing.
7. "Drop missing" applies to every column, not just the analysed ones.

**Fix soon (misleading but less dangerous)**

- Silent switch from Student's to Welch's t test, without saying so in the text.
- Cramér's V computed from the Yates-corrected χ².
- Sparse r×c tables are not flagged and there is no exact or Monte Carlo alternative.
- Reference levels follow row order, not a choice the user makes.
- The plan counts group levels before removing incomplete cases.
- p-value rounding is inconsistent with the "significant" wording near .05.
- SPSS value labels are lost on import.
- Columns containing "code" are typed as ID.
- "Prepare" overwrites roles the user already set.
- The report is recomputed every time it opens.
- Slow synchronous OLS on large files.

**UI defects:** `studyDesign` collected but unused. Cronbach defaults to all numeric columns.
Planned predictors are not passed to the analysis. `fisher_exact` is offered but does not exist.

**Tests:** 30 backend tests exist, but **none checks a statistical value**. They only check that
endpoints answer.

## 5. What to keep

- The core statistical functions, which are accurate.
- The visitor/member session model and the usage limits.
- Bilingual reporting (English/Arabic) as a concept.
- The step layout (Upload → Prepare → Variables → Analyse → Results → Report), as a skeleton.
- The cautious interpretation sentences ("does not prove causation", "not proof of no difference").

## 6. Proposed new flow

```
1. Upload      → auto-detect encoding and delimiter, show a preview, read SPSS labels
2. Study       → choose the design: survey / RCT / cohort / case-control /
                 cross-sectional / diagnostic accuracy / pre-post / questionnaire validation
3. Question    → "What do you want to find out?" in plain words:
                 compare groups · relationship · predict an outcome · change over time ·
                 test accuracy · scale reliability
4. Variables   → the user confirms each role (outcome, exposure/group, covariates, ID, time)
                 and its level (binary / categorical / ordinal / continuous).
                 Guesses are shown as suggestions, never used until confirmed.
5. Data check  → missing data per analysed variable only. Warns before rows are lost.
                 Recode / reverse-code / combine categories, with every step logged and undoable.
6. Plan        → the tool recommends the test and explains WHY in one sentence
                 ("binary outcome + 2 groups + small cells → Fisher's exact; report OR and RR").
                 It shows the alternatives and when to use them. The user can override, and the
                 reason is recorded.
7. Assumptions → checked automatically. Explained in plain words, with the fallback test applied
                 and disclosed.
8. Results     → the key number first (effect + 95% CI), then the table and chart,
                 then a plain-language meaning.
9. Write-up    → design-specific Methods paragraph, Results paragraph, Table 1 by group,
                 regression table, in English and Arabic. Exports to DOCX / XLSX / PDF.
                 Includes reporting-guideline hints (CONSORT, STROBE, STARD).
```

The test choice (point 6) becomes a **rule table** in one file:
design × question × outcome type × groups × sample size → test. It is reviewable and testable,
and replaces logic spread across the current React components.

## 7. Missing analyses (by priority)

- **P0, needed for most medical papers:**
  - Table 1 by group with p-values / SMDs
  - 2×2 analysis (Fisher, OR, RR, risk difference)
  - diagnostic accuracy (sensitivity, specificity, PPV, NPV, likelihood ratios, ROC/AUC)
  - proper multivariable linear and logistic regression (adjusted ORs)
  - survival (Kaplan–Meier, log-rank, Cox)
- **P1:**
  - post-hoc tests (Tukey / Games-Howell / Dunn)
  - repeated measures / mixed ANOVA
  - Mann-Whitney / Wilcoxon / Kruskal on ordinal outcomes by default
  - kappa and ICC
  - ANCOVA
  - sample-size / power calculator
- **P2:**
  - Poisson / negative binomial
  - propensity scores
  - multiple imputation
  - meta-analysis

## 8. Proposed backend structure

```
backend/research_analyzer/engine/
  io/          read CSV/XLSX/SAV with encoding + delimiter detection, labels
  prep/        transformations with an undo log (recode, reverse, filter, missing)
  design/      StudyDesign + ResearchQuestion + confirmed variable roles
  selection/   rule table: (design, question, variable types) -> recommended test + reasons
  methods/     one module per analysis, each returning a typed Result object
  reporting/   sentence catalogues en/ar, Table 1, DOCX/XLSX export
  validation/  golden datasets with reference values from R; row-order invariance tests
```

## 9. Phased plan

| Phase | Content | Size |
|---|---|---|
| **1. Safety fixes** | The 7 "fix first" bugs. Drop-missing limited to analysed columns, with a warning. Remove the fake Fisher option. Fix the "—" complete-case count. Loosen the upload limit. Add the first value-checking tests. | Small (days) |
| **2. Guided flow** | Study + question steps. Confirmed roles only. Rule-table test selection with reasons. Reverse-coding prompt for scales. Undoable prep log. | Medium |
| **3. Manuscript output** | Design-aware Methods and Results text. Table 1 by group. Regression tables. DOCX/XLSX export. Arabic parity. | Medium |
| **4. P0 analyses** | 2×2 OR/RR, diagnostic accuracy + ROC, adjusted regression, survival. | Medium–large |
| **5. Validation suite** | A golden corpus checked against R. Property tests (row order, encoding). Runs in CI. | Ongoing |

Phase 1 can ship on its own while the new flow is designed. Phases 2–3 are the "build from
scratch" part the owner asked about. They reuse the existing calculations but replace the screens,
test selection and reporting.

## 10. Build status (23 October 2026)

**Phase 1 — safety fixes:** done and pushed (`bcc4c66`). It covers:
- VIF with an intercept
- logistic event choice
- the separation check
- effect-size bands
- Arabic and semicolon CSV import
- safe "remove missing rows"
- role suggestions
- n on every result
- value-checking tests

**New engine** (`backend/research_analyzer/engine/`):
- `registry.py` — 34 methods (15 basic, 19 advanced) in 7 families, each marked basic or advanced, with declared inputs (served at `/methods/`).
- `selection.py` — rule table from question type to recommended method, with reasons, warnings and the valid alternatives (served at `/recommend/`).
- `methods.py` — the new and extended analyses:
  - 2×2 risk difference (Newcombe), risk ratio and odds ratio, with Fisher's test
  - chi-square adjusted-residual post-hoc
  - goodness of fit
  - one-sample t test
  - ANOVA with automatic Welch switch, Tukey / Games-Howell / Holm comparisons and a Kruskal check
  - Kruskal-Wallis with Dunn's test
  - factorial ANOVA and ANCOVA
  - repeated-measures and mixed ANOVA (sphericity, Greenhouse-Geisser, Friedman)
  - partial correlation and correlation matrix
  - linear regression with robust standard errors, interactions and hierarchical blocks
  - logistic regression with AUC and Hosmer-Lemeshow
  - multinomial, ordinal and Poisson / negative binomial regression
  - reliability with ω, split-half and reverse-item detection
  - Cohen's and Fleiss' κ, ICC
  - diagnostic accuracy with ROC and Youden cut-off
  - Table 1 by group with p-values and SMDs
- `report_docx.py` — Word export, including right-to-left Arabic (served at `/report/docx/`).

**New interface** (`frontend/src/features/researchAnalyzer/studio/`) — the approved three-step design:
- **Upload**, with example datasets.
- **Analyse:**
  - question → recommendation with reasons → Run
  - advanced options
  - methods library
  - Simple / Full results
  - suggestions
- **Report:**
  - reorder
  - English / Arabic
  - Word, print and copy

The old six-step screens and their stylesheet were removed.

**Tests:** value tests check against scipy, statsmodels, pingouin and sklearn, plus the published Newcombe example. Selection rules and the new API endpoints are tested too.

**Known limits / next:**
- The reasons behind a recommendation, and table column headers, are still English inside the Arabic interface.
- Not built yet:
  - survival analysis (Kaplan-Meier / Cox)
  - mediation
  - multiple imputation
  - power analysis
