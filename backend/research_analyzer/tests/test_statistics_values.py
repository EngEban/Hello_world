"""Statistical values checked against independent reference implementations.

These tests pin the numbers researchers copy into manuscripts, not just that the endpoints answer.
Reference values come from scipy/statsmodels computed directly in each test, or from textbook
formulas, so a regression in the analyzer shows up as a wrong number.
"""

import numpy as np
import pandas as pd
import scipy.stats as stats
import statsmodels.api as sm
from django.test import SimpleTestCase
from statsmodels.stats.outliers_influence import variance_inflation_factor

from research_analyzer.services import data_service, stats_service


def trial_data(seed=7, n=120):
    """Two-arm trial with a rare binary event and continuous covariates on realistic scales."""
    rng = np.random.default_rng(seed)
    arm = np.where(rng.random(n) < 0.5, 'Drug A', 'Drug B')
    age = rng.normal(56, 12, n).round()
    bmi = rng.normal(28, 4, n).round(1)
    sex = np.where(rng.random(n) < 0.5, 'Male', 'Female')
    baseline = rng.normal(152, 13, n).round()
    week12 = (baseline - np.where(arm == 'Drug A', 13, 8) + rng.normal(0, 7, n)).round()
    risk = 1 / (1 + np.exp(-(-2.2 + 1.2 * (arm == 'Drug A') + 0.02 * (age - 56))))
    event = np.where(rng.random(n) < risk, 'Yes', 'No')
    return pd.DataFrame({'arm': arm, 'age': age, 'bmi': bmi, 'sex': sex, 'sbp_baseline': baseline,
                         'sbp_week12': week12, 'adverse_event': event})


class ProbeFile:
    def __init__(self, content):
        self.content, self.size = content, len(content)

    def read(self, _limit):
        return self.content


class RegressionValueTests(SimpleTestCase):
    def test_vif_includes_an_intercept(self):
        data = trial_data()
        result = stats_service.linear_regression(data, 'sbp_week12', ['age', 'bmi', 'sbp_baseline'])
        design = sm.add_constant(data[['age', 'bmi', 'sbp_baseline']].astype(float))
        expected = [variance_inflation_factor(design.to_numpy(), index) for index in range(1, 4)]
        self.assertEqual([row['vif'] for row in result['vif']], [round(value, 3) for value in expected])
        # Unrelated predictors with large means must not trigger a false collinearity warning.
        self.assertTrue(all(row['vif'] < 1.5 for row in result['vif']))
        self.assertTrue(result['assumptions']['multicollinearity']['passed'])

    def test_linear_coefficients_match_statsmodels(self):
        data = trial_data()
        result = stats_service.linear_regression(data, 'sbp_week12', ['arm', 'sbp_baseline'], ['arm'])
        x = sm.add_constant(pd.DataFrame({'arm [Drug B]': (data['arm'] == 'Drug B').astype(float), 'sbp_baseline': data['sbp_baseline']}))
        model = sm.OLS(data['sbp_week12'], x).fit()
        terms = {row['term']: row for row in result['coefficients']}
        self.assertAlmostEqual(terms['arm [Drug B]']['b'], model.params['arm [Drug B]'], places=3)
        self.assertAlmostEqual(result['r_squared'], model.rsquared, places=3)
        self.assertEqual(result['model_specification']['reference_categories'], {'arm': 'Drug A'})

    def test_reference_category_can_be_chosen(self):
        result = stats_service.linear_regression(trial_data(), 'sbp_week12', ['arm'], ['arm'], reference_levels={'arm': 'Drug B'})
        self.assertIn('arm [Drug A]', [row['term'] for row in result['coefficients']])
        self.assertIn('error', stats_service.linear_regression(trial_data(), 'sbp_week12', ['arm'], ['arm'], reference_levels={'arm': 'Drug C'}))

    def test_logistic_event_is_yes_whatever_the_row_order(self):
        data = trial_data()
        shuffled = data.sample(frac=1, random_state=1).sort_values('adverse_event')  # "No" rows first
        first = stats_service.logistic_regression(data, 'adverse_event', ['arm', 'age'], ['arm'])
        second = stats_service.logistic_regression(shuffled, 'adverse_event', ['arm', 'age'], ['arm'])
        self.assertEqual(first['outcome_event'], 'Yes')
        self.assertEqual(first['outcome_reference'], 'No')
        self.assertEqual([row['odds_ratio'] for row in first['coefficients']], [row['odds_ratio'] for row in second['coefficients']])
        y = (data['adverse_event'] == 'Yes').astype(int)
        x = sm.add_constant(pd.DataFrame({'arm [Drug B]': (data['arm'] == 'Drug B').astype(float), 'age': data['age']}))
        expected = np.exp(sm.Logit(y, x).fit(disp=0).params['arm [Drug B]'])
        terms = {row['term']: row for row in first['coefficients']}
        self.assertAlmostEqual(terms['arm [Drug B]']['odds_ratio'], expected, places=3)

    def test_logistic_event_can_be_chosen(self):
        result = stats_service.logistic_regression(trial_data(), 'adverse_event', ['age'], event_level='No')
        self.assertEqual(result['outcome_event'], 'No')
        self.assertIn('error', stats_service.logistic_regression(trial_data(), 'adverse_event', ['age'], event_level='Maybe'))

    def test_perfect_separation_is_refused_not_reported(self):
        separated = pd.DataFrame({'y': ['Yes'] * 12 + ['No'] * 12, 'x': list(range(20, 32)) + list(range(12))})
        result = stats_service.logistic_regression(separated, 'y', ['x'])
        self.assertEqual(result.get('code'), 'perfect_separation')
        zero_cell = pd.DataFrame({'y': ['Yes'] * 6 + ['No'] * 18, 'g': ['A'] * 6 + ['A'] * 6 + ['B'] * 12})
        self.assertEqual(stats_service.logistic_regression(zero_cell, 'y', ['g'], ['g']).get('code'), 'perfect_separation')


class GroupComparisonValueTests(SimpleTestCase):
    def test_student_t_matches_scipy_and_reports_n(self):
        data = trial_data()
        result = stats_service.run_test('ttest', data, {'outcome': 'sbp_week12', 'group': 'arm'})
        groups = [data.loc[data['arm'] == name, 'sbp_week12'] for name in ('Drug A', 'Drug B')]
        expected = stats.ttest_ind(*groups, equal_var=True)
        self.assertEqual(result['n'], len(data))
        if result['test'] == 'ttest_student':
            self.assertAlmostEqual(result['t'], expected.statistic, places=3)
            self.assertIn(f"t({len(data) - 2})", result['apa_en'])

    def test_anova_effect_size_bands(self):
        rng = np.random.default_rng(3)
        data = pd.DataFrame({'g': np.repeat(['a', 'b', 'c'], 40), 'y': rng.normal(0, 1, 120) + np.repeat([0, 0.15, 0.3], 40)})
        result = stats_service.run_test('anova', data, {'outcome': 'y', 'group': 'g'})
        self.assertEqual(result['effect_size'], stats_service._variance_explained_effect_label(result['omega_squared']))
        self.assertEqual(result['n'], 120)
        self.assertEqual(stats_service._variance_explained_effect_label(0.005), 'negligible')
        self.assertEqual(stats_service._variance_explained_effect_label(0.024), 'small')
        self.assertEqual(stats_service._variance_explained_effect_label(0.065), 'medium')
        self.assertEqual(stats_service._variance_explained_effect_label(0.2), 'large')

    def test_groups_are_reported_in_sorted_order(self):
        data = pd.DataFrame({'g': ['Year 3', 'Year 1', 'Year 2'] * 5, 'y': range(15)})
        result = stats_service.run_test('anova', data, {'outcome': 'y', 'group': 'g'})
        self.assertEqual(list(result['groups']), ['Year 1', 'Year 2', 'Year 3'])


class CategoricalValueTests(SimpleTestCase):
    def test_cramers_v_uses_uncorrected_chi_square(self):
        data = pd.DataFrame({'a': ['x'] * 30 + ['y'] * 30, 'b': ['p'] * 20 + ['q'] * 10 + ['p'] * 10 + ['q'] * 20})
        result = stats_service.chi_square(data, 'a', 'b')
        table = pd.crosstab(data['a'], data['b'])
        chi2_plain = stats.chi2_contingency(table, correction=False)[0]
        self.assertAlmostEqual(result['cramer_v'], np.sqrt(chi2_plain / 60), places=3)
        self.assertAlmostEqual(result['chi2'], stats.chi2_contingency(table, correction=True)[0], places=3)

    def test_plan_never_offers_a_test_that_does_not_exist(self):
        variables = [{'name': 'adverse_event', 'type': 'categorical', 'role': 'outcome'}, {'name': 'arm', 'type': 'categorical', 'role': 'grouping'}]
        plan = stats_service.build_analysis_plan(trial_data(), variables)
        offered = {test for entry in plan['entries'] for test in [entry['test'], *entry['alternatives']]}
        for test in offered:
            self.assertNotEqual(stats_service.run_test(test, pd.DataFrame(), {}).get('error'), f'Unknown test: {test}')

    def test_adjusted_models_include_the_treatment_arm(self):
        variables = [
            {'name': 'adverse_event', 'type': 'categorical', 'role': 'outcome'},
            {'name': 'sex', 'type': 'categorical', 'role': 'grouping'},
            {'name': 'arm', 'type': 'categorical', 'role': 'grouping'},
            {'name': 'age', 'type': 'numeric', 'role': 'covariate'},
        ]
        plan = stats_service.build_analysis_plan(trial_data(), variables)
        logistic = next(entry for entry in plan['entries'] if entry['test'] == 'logistic_regression')
        self.assertEqual(logistic['params']['predictors'][0], 'arm')
        comparison = next(entry for entry in plan['entries'] if entry['test'] == 'chi_square')
        self.assertEqual(comparison['params']['var2'], 'arm')


class ReportingFormatTests(SimpleTestCase):
    def test_p_value_text_agrees_with_significance(self):
        self.assertEqual(stats_service._p_fmt(0.0496), '= .0496')
        self.assertEqual(stats_service._p_fmt(0.0504), '= .050')
        self.assertEqual(stats_service._p_fmt(0.1234), '= .123')
        self.assertEqual(stats_service._p_fmt(0.0004), '< .001')


class DataImportTests(SimpleTestCase):
    def test_windows_arabic_csv_is_decoded(self):
        content = 'الاسم,العمر,المجموعة\nأحمد,30,أ\nسارة,41,ب\n'.encode('cp1256')
        df = data_service.parse_uploaded_file(ProbeFile(content), 'study.csv')
        self.assertEqual(list(df.columns), ['الاسم', 'العمر', 'المجموعة'])
        self.assertEqual(df.iloc[1, 0], 'سارة')

    def test_semicolon_csv_with_decimal_commas(self):
        df = data_service.parse_uploaded_file(ProbeFile(b'id;score;group\n1;1,5;a\n2;2,25;b\n'), 'eu.csv')
        self.assertEqual(list(df.columns), ['id', 'score', 'group'])
        self.assertEqual(df['score'].tolist(), [1.5, 2.25])

    def test_drop_missing_refuses_to_delete_most_of_the_data(self):
        df = pd.DataFrame({'pcr': ['Pos'] * 4 + ['Neg'] * 6, 'ct': [20, 22, 25, 30] + [None] * 6, 'age': range(10)})
        kept, log, warnings = data_service.apply_preparation(df, {'drop_missing': True})
        self.assertEqual(len(kept), 10)
        self.assertEqual(log, [])
        self.assertIn('6 of 10 rows', warnings[0])
        scoped, log, _ = data_service.apply_preparation(df, {'drop_missing': True, 'missing_columns': ['age', 'pcr']})
        self.assertEqual(len(scoped), 10)
        confirmed, _, _ = data_service.apply_preparation(df, {'drop_missing': True, 'confirm_drop_missing': True})
        self.assertEqual(len(confirmed), 4)

    def test_role_suggestions_for_a_typical_trial(self):
        df = trial_data().assign(patient_id=[f'P{i:03d}' for i in range(120)], respondent=range(1, 121))
        roles = {row['name']: (row['type'], row['suggested_role']) for row in data_service.detect_all_variables(df)}
        self.assertEqual(roles['patient_id'][1], 'identifier')
        self.assertEqual(roles['respondent'], ('id', 'identifier'))
        self.assertEqual(roles['arm'][1], 'grouping')
        self.assertEqual(roles['adverse_event'][1], 'outcome')
        self.assertEqual(roles['sex'][1], 'covariate')
        self.assertEqual(roles['sbp_baseline'][1], 'pre_measure')
        self.assertEqual(roles['sbp_week12'][1], 'post_measure')
        year = data_service.detect_variable_type(pd.Series(['Year 1', 'Year 2'] * 10, name='year_of_study'))
        self.assertEqual(year['suggested_role'], 'grouping')
