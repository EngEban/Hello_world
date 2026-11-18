# Sample Size Calculator — Review and Rebuild Plan

_Review date: 23 October 2026. Branch `resref-workspace`._

## 1. Verdict

The calculator covers the common cases. Most formulas are standard textbook ones and give the
expected answers for proportions, correlation and diagnostic accuracy.

Its problems are the same kind as the old analyzer's: it is organised around formula names
("Compare 2 proportions", "Paired mean") rather than the researcher's question. It also shows the
same result in three places before the results step, and it only answers one question: "how many
people do I need?".

Researchers also need answers to:
- "What power will I have with the 120 patients I can get?"
- "What is the smallest difference I can detect?"

Several designs that medical researchers use often are missing. A few results are slightly wrong,
and two of the errors make the required sample too small.

## 2. How it was reviewed

- I read the full calculator code: `frontend/src/features/sampleSizeCalculator/sampleSizeCalculator.js` (581 lines) and the page (636 lines).
- I compared results with reference values from statsmodels and G*Power-equivalent t-based power.
- I opened the page in the browser at desktop size.

## 3. Wrong or risky results

| # | Problem | Example | Effect |
|---|---|---|---|
| 1 | Two independent means use the normal (z) formula, but the page says "G*Power-style". G*Power uses the t distribution. | d = 0.5, α = .05, power 80% → **63 per group**; G*Power / t-based gives **64** | Sample slightly **too small**; reviewers who check with G*Power get a different number |
| 2 | Paired means: same issue | dz = 0.5 → **32**; t-based gives **34** | Too small |
| 3 | The finite population correction is applied **before** the design effect | Population 100, design effect 2 → asks for **160 people out of 100** | Impossible answer |
| 4 | No warning when the margin of error is larger than the expected proportion | p = 2%, ±5% → 31 people; the interval would go below 0% | Misleading precision |
| 5 | Linear regression only uses Green's rule of thumb | 8 predictors → 114 | No proper power (f²) option |
| 6 | Logistic regression only uses 10 events per variable | Outdated for prediction models | Riley et al. (2019) criteria are now expected |
| 7 | Two proportions has no continuity-correction option | 40% vs 55% → 173 per group (186 with correction) | Fine, but it should be stated and selectable |

Values that are correct: single proportion with Cochran's formula and finite population
correction, single mean, two proportions without correction, correlation (Fisher z), diagnostic
accuracy (Buderer), the dropout adjustment, and the pilot rules.

## 4. What is missing

- **Reverse calculations:**
  - power for a given sample size
  - minimum detectable effect for a given sample size
- **Planning options:**
  - unequal group sizes (e.g. 2:1)
  - one-sided tests
  - effect-size helpers (from means and SDs in a published paper, from an odds ratio or risk ratio)
- **Designs often needed in medical research:**
  - ANOVA with 3 or more groups
  - chi-square with more than 2 categories
  - non-inferiority and equivalence trials
  - survival / time-to-event (log-rank, Schoenfeld)
  - cluster-randomised trials (ICC → design effect)
  - repeated measures and before–after with a control group (ANCOVA)
  - McNemar for paired proportions
  - ROC / AUC
  - multiple regression power (f²)
  - logistic regression power (Hsieh)
  - prediction models (Riley)
- **Output:**
  - a power curve chart
  - Arabic write-up
  - a Word / protocol export
  - a sample-size table for several scenarios at once

## 5. What makes it hard to use

- A large hero banner and four summary cards push the tool below the first screen.
- The same number appears three times (summary card, live preview and results step), so it is
  unclear when the answer is final.
- The first choice requires statistical vocabulary ("Compare 2 proportions"), not the question
  the researcher has.
- The results step is crowded: four main panels plus four side panels.
- Help for estimating inputs is missing ("Where do I get the SD from?").

## 6. What to keep

- The correct formulas listed in section 3.
- Dropout and design-effect adjustment.
- Sensitivity scenarios.
- Manuscript wording.
- Account-synced history.
- References to cite.
- The usage-allowance check.

## 7. Proposed design (same approach as the new analyzer)

One screen, three areas:

1. **Question**:
   - "What are you planning?"
   - Choices: estimate a rate or mean · compare groups · relationship · before–after · diagnostic test · prediction model · pilot
   - Then pick the outcome type (yes/no, number, time to event).
2. **Inputs**:
   - Only the inputs needed, each with a "Help me estimate" link (from a published paper, from a pilot, or typical values).
   - A **Calculate** switch: sample size | power | detectable effect.
   - Advanced options are folded away: allocation ratio, one-sided test, continuity correction, cluster design, dropout.
3. **Answer** (updates live; one place only):
   - big number with per-group split
   - power curve
   - scenario table
   - checks and warnings
   - write-up in English and Arabic
   - copy, Word and save

The method is chosen automatically from the question and outcome, with the reason shown, as in
the analyzer. A methods library lists every design for experienced users.

## 8. Plan

| Phase | Content |
|---|---|
| 1 | Fix the results in section 3 (t-based means, adjustment order, warnings) and add value tests against statsmodels / G*Power tables |
| 2 | New engine: power, sample size and detectable-effect solvers; allocation ratio; one-sided tests; new designs |
| 3 | New one-screen interface, power curve, bilingual write-up, Word export |

## 9. Build status (23 October 2026)

**Engine.** It lives in `backend/research_analyzer/engine/sample_size.py` and is served at `/api/sample-size/designs/`, `/calculate/` and `/docx/`.

- **16 designs:** single proportion and single mean, two proportions (optional continuity correction), two means, ANOVA, before–after (paired means), McNemar, correlation, multiple regression (f²), logistic regression (Hsieh), log-rank (Schoenfeld), non-inferiority and equivalence, diagnostic accuracy (Buderer), ROC/AUC (Hanley-McNeil), prediction models (Riley) and pilot studies (Whitehead).
- **Three answers:** sample size, power and detectable effect (precision for estimation designs).
- **Adjustments:** allocation ratio, one- or two-sided tests, cluster ICC or design effect, finite population correction and dropout, applied in that order.
- **G*Power methods:** two means, paired means, ANOVA and regression use the exact noncentral t and F distributions, as G*Power does.

**Fixes from section 3.**

- **Fixed:** two and paired means now give 64 and 34 (was 63 and 32).
- **Fixed:** a population of 100 with a design effect of 2 can no longer ask for more than 100 people.
- **Fixed:** there is now a warning when the margin of error is larger than the expected proportion.
- **Now offered:** regression power (f²), Hsieh logistic, the Riley criteria and a continuity-correction option.

**Interface.** The approved one-screen design.

- **Question and outcome:** the method is chosen with its reason shown.
- **Inputs:** advanced options stay folded away. There is a sample size / power / detectable effect switch and an SD helper (pooled SD, from a 95% CI, or from the IQR).
- **Live answer:** includes a power curve, a scenario table, warnings, and a write-up in English and Arabic.
- **Output:** copy, Word, save, history and CSV export.
- **Library:** all designs, basic first.

The usage allowance counts once per result when it is copied, exported or saved, as agreed.

**Tests.** `research_analyzer/tests/test_sample_size.py` pins results to G*Power 3.1, Fleiss, Schoenfeld and the published Riley example. It also checks that every design and mode works and covers the API.

**Not built yet:**
- cross-over trials
- repeated measures
- incidence rates
- relative precision
- kappa / ICC planning
