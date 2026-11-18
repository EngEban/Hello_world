"""The analysis engine: new methods checked against reference values, selection rules, and the API."""
import io
import json

import numpy as np
import pandas as pd
import pingouin as pg
import scipy.stats as stats
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase

from accounts.models import FeatureEntitlement
from research_analyzer.engine import methods, registry, selection
from research_analyzer.services import stats_service
from research_analyzer.tests.test_api import TempStorageMixin
from research_analyzer.tests.test_statistics_values import trial_data


def two_arm(events_a, n_a, events_b, n_b):
    rows = ([('A', 'Yes')] * events_a + [('A', 'No')] * (n_a - events_a)
            + [('B', 'Yes')] * events_b + [('B', 'No')] * (n_b - events_b))
    return pd.DataFrame(rows, columns=['arm', 'event'])


class TwoByTwoTests(SimpleTestCase):
    def test_newcombe_interval_matches_the_published_example(self):
        # Newcombe (1998), Statistics in Medicine 17:873, example (a): 56/70 vs 48/80 → 0.2000 (0.0524, 0.3339).
        result = methods.two_by_two(two_arm(56, 70, 48, 80), 'event', 'arm', reference_group='B')
        self.assertAlmostEqual(result['risk_difference'], 0.2, places=4)
        self.assertAlmostEqual(result['risk_difference_ci_95'][0], 0.0524, places=3)
        self.assertAlmostEqual(result['risk_difference_ci_95'][1], 0.3339, places=3)

    def test_ratios_and_fisher_match_textbook_formulas(self):
        result = methods.two_by_two(two_arm(9, 40, 2, 40), 'event', 'arm', reference_group='B')
        self.assertEqual((result['exposed_group'], result['reference_group'], result['event']), ('A', 'B', 'Yes'))
        self.assertAlmostEqual(result['risk_ratio'], (9 / 40) / (2 / 40), places=3)
        self.assertAlmostEqual(result['odds_ratio'], (9 * 38) / (31 * 2), places=3)
        log_se = np.sqrt(1 / 9 - 1 / 40 + 1 / 2 - 1 / 40)
        self.assertAlmostEqual(result['risk_ratio_ci_95'][0], np.exp(np.log(4.5) - 1.959964 * log_se), places=3)
        self.assertAlmostEqual(result['fisher_p'], stats.fisher_exact([[9, 31], [2, 38]])[1], places=4)
        self.assertEqual(result['number_needed']['kind'], 'harm')

    def test_zero_cell_uses_haldane_correction(self):
        result = methods.two_by_two(two_arm(5, 20, 0, 20), 'event', 'arm', reference_group='B')
        self.assertIsNotNone(result['risk_ratio'])
        self.assertTrue(any('Haldane' in note for note in result['notes']))
        self.assertEqual(result['method'], "Fisher's exact test")


class OtherMethodTests(SimpleTestCase):
    def test_one_sample_t_matches_scipy(self):
        data = trial_data()
        result = methods.one_sample_ttest(data, 'age', 50)
        expected = stats.ttest_1samp(data['age'], 50)
        self.assertAlmostEqual(result['t'], expected.statistic, places=3)
        self.assertAlmostEqual(result['p'], expected.pvalue, places=4)

    def test_anova_full_switches_to_welch_when_spreads_differ(self):
        rng = np.random.default_rng(1)
        data = pd.DataFrame({'g': np.repeat(['a', 'b', 'c'], 30), 'y': np.concatenate([rng.normal(0, 1, 30), rng.normal(0.5, 4, 30), rng.normal(1, 8, 30)])})
        result = methods.anova_full(data, 'y', 'g')
        self.assertEqual(result['reported_test'], 'welch_anova')
        self.assertEqual(result['posthoc_method'], 'Games-Howell')
        self.assertEqual(len(result['posthoc']), 3)
        self.assertAlmostEqual(result['p'], pg.welch_anova(data=data, dv='y', between='g')['p_unc'].iloc[0], places=4)

    def test_repeated_measures_matches_pingouin(self):
        rng = np.random.default_rng(2)
        base = rng.normal(10, 2, 40)
        wide = pd.DataFrame({'t0': base, 't1': base + rng.normal(0.5, 1, 40), 't2': base + rng.normal(1.0, 1, 40)})
        result = methods.repeated_measures_anova(wide, ['t0', 't1', 't2'])
        long = wide.reset_index().melt(id_vars='index', var_name='t', value_name='v')
        expected = pg.rm_anova(data=long, dv='v', within='t', subject='index')
        self.assertAlmostEqual(result['effects'][0]['f'], expected['F'].iloc[0], places=3)
        self.assertEqual(result['effects'][0]['df2'], 78)
        self.assertIsNotNone(result['friedman'])
        self.assertIn('F(2, 78)', result['apa_en'])

    def test_diagnostic_accuracy_counts_and_wilson_intervals(self):
        rows = [('Pos', 'Pos')] * 40 + [('Neg', 'Pos')] * 10 + [('Pos', 'Neg')] * 5 + [('Neg', 'Neg')] * 45
        data = pd.DataFrame(rows, columns=['test', 'ref'])
        result = methods.diagnostic_accuracy(data, 'test', 'ref', 'Pos', 'Pos')
        self.assertEqual(result['table'], {'true_positive': 40, 'false_negative': 10, 'false_positive': 5, 'true_negative': 45})
        self.assertAlmostEqual(result['sensitivity']['value'], 0.8, places=4)
        self.assertAlmostEqual(result['specificity']['value'], 0.9, places=4)
        self.assertAlmostEqual(result['lr_positive'], 8.0, places=3)
        # Wilson interval for 40/50.
        self.assertAlmostEqual(result['sensitivity']['ci_95'][0], 0.6696, places=3)

    def test_roc_for_a_numeric_test(self):
        rng = np.random.default_rng(4)
        data = pd.DataFrame({'score': np.concatenate([rng.normal(2, 1, 60), rng.normal(0, 1, 60)]), 'disease': ['yes'] * 60 + ['no'] * 60})
        result = methods.diagnostic_accuracy(data, 'score', 'disease')
        manual = stats.mannwhitneyu(data.score[:60], data.score[60:]).statistic / 3600
        self.assertAlmostEqual(result['roc']['auc'], manual, places=4)
        self.assertGreater(result['roc']['auc'], 0.8)

    def test_reliability_flags_reverse_worded_items_and_reports_omega(self):
        rng = np.random.default_rng(5)
        trait = rng.normal(0, 1, 200)
        items = {f'q{i}': np.clip(np.round(3 + trait + rng.normal(0, 0.7, 200)), 1, 5) for i in range(1, 5)}
        items['q5'] = 6 - np.clip(np.round(3 + trait + rng.normal(0, 0.7, 200)), 1, 5)
        data = pd.DataFrame(items)
        raw = methods.reliability_full(data, list(items))
        self.assertEqual(raw['suspected_reverse_items'], ['q5'])
        fixed = methods.reliability_full(data, list(items), ['q5'])
        self.assertGreater(fixed['alpha'], 0.8)
        self.assertGreater(fixed['omega'], 0.8)
        self.assertAlmostEqual(fixed['alpha'], pg.cronbach_alpha(data.assign(q5=6 - data.q5))[0], places=3)

    def test_table_one_by_group(self):
        result = methods.table_one(trial_data(), 'arm', [{'name': 'age', 'type': 'numeric'}, {'name': 'sex', 'type': 'categorical'}])
        self.assertEqual(result['groups'], ['Drug A', 'Drug B'])
        age = next(row for row in result['rows'] if row['variable'] == 'age')
        self.assertEqual(set(age['by_group']), {'Drug A', 'Drug B'})
        self.assertIn('p', age)
        self.assertIn('smd', age)

    def test_table_one_shows_whole_number_scores_with_blanks_as_integers(self):
        # Blanks make pandas read a 1–5 score as float; its levels must still read 1, 2 … not 1.0, 2.0.
        data = pd.DataFrame({'arm': ['A', 'B'] * 6, 'score': [1, 2, None, 3, 5, 10, 1, 2, 3, None, 5, 10],
                             'dose': [0.5, 1.5, 0.5, 1.5, 0.5, 1.5, 0.5, 1.5, 0.5, 1.5, 0.5, 1.5]})
        result = methods.table_one(data, 'arm', [{'name': 'score', 'type': 'likert'}, {'name': 'dose', 'type': 'categorical'}])
        score = next(row for row in result['rows'] if row['variable'] == 'score')
        self.assertEqual([level['level'] for level in score['levels']], ['1', '2', '3', '5', '10'])
        dose = next(row for row in result['rows'] if row['variable'] == 'dose')
        self.assertEqual([level['level'] for level in dose['levels']], ['0.5', '1.5'])
        # Percentages and the p-value use answered rows only; blanks are not an extra category.
        self.assertEqual(score['levels'][0]['overall'], '2 (20.0)')
        answered = data.dropna(subset=['score'])
        expected_p = stats.chi2_contingency(pd.crosstab(answered['score'], answered['arm']))[1]
        self.assertAlmostEqual(score['p'], expected_p, places=4)

    def test_table_one_numeric_group_codes_with_blanks_read_as_integers(self):
        data = pd.DataFrame({'arm': [1, 2, 1, 2, None, 1, 2, 1, 2, 1], 'age': [30, 40, 35, 45, 50, 32, 41, 36, 44, 31]})
        result = methods.table_one(data, 'arm', [{'name': 'age', 'type': 'numeric'}])
        self.assertEqual(result['groups'], ['1', '2'])
        self.assertEqual(set(result['rows'][0]['by_group']), {'1', '2'})

    def test_frequency_labels_drop_the_trailing_decimal(self):
        data = pd.DataFrame({'q': [1, 2, None, 2, 3]})
        self.assertEqual(list(stats_service._category_labels(data['q']).dropna()), ['1', '2', '2', '3'])
        counts = methods.goodness_of_fit(data, 'q')
        self.assertEqual(counts['n'], 4)

    def test_kappa_matches_sklearn(self):
        from sklearn.metrics import cohen_kappa_score
        data = pd.DataFrame({'a': list('xxyyzzxyzx' * 3), 'b': list('xxyzzzxyyx' * 3)})
        self.assertAlmostEqual(methods.cohens_kappa(data, 'a', 'b')['kappa'], cohen_kappa_score(data.a, data.b), places=4)

    def test_icc_matches_pingouin_two_way_absolute_agreement(self):
        rng = np.random.default_rng(6)
        truth = rng.normal(50, 10, 30)
        wide = pd.DataFrame({f'r{i}': truth + rng.normal(0, 4, 30) for i in range(3)})
        result = methods.icc(wide, ['r0', 'r1', 'r2'])
        long = wide.reset_index().melt(id_vars='index', var_name='rater', value_name='score')
        table = pg.intraclass_corr(data=long, targets='index', raters='rater', ratings='score').set_index('Type')
        expected = table.loc['ICC(A,1)' if 'ICC(A,1)' in table.index else 'ICC2', 'ICC']
        self.assertAlmostEqual(result['icc'], expected, places=3)

    def test_every_registered_method_has_a_runner_and_inputs(self):
        for method in registry.METHODS:
            self.assertTrue(callable(method['run']), method['id'])
            self.assertIn(method['family'], {family['id'] for family in registry.FAMILIES})
            self.assertIn(method['level'], {'basic', 'advanced'})
        self.assertNotIn('run', registry.public_catalog()['methods'][0])


class SelectionRuleTests(SimpleTestCase):
    types = [{'name': n, 'type': t} for n, t in [('arm', 'categorical'), ('age', 'numeric'), ('bmi', 'numeric'), ('sex', 'categorical'),
                                                 ('sbp_baseline', 'numeric'), ('sbp_week12', 'numeric'), ('adverse_event', 'categorical')]]

    def recommend(self, question, **fields):
        return selection.recommend(trial_data(), self.types, question, fields)

    def test_rules(self):
        self.assertEqual(self.recommend('compare', outcome='adverse_event', group='arm')['method'], 'two_by_two')
        self.assertEqual(self.recommend('compare', outcome='sbp_week12', group='arm')['method'], 'ttest')
        self.assertEqual(self.recommend('compare', outcome='sbp_week12', group='arm', covariates=['sbp_baseline'])['method'], 'ancova')
        self.assertEqual(self.recommend('compare', outcome='adverse_event', group='arm', covariates=['age'])['method'], 'logistic_regression')
        self.assertEqual(self.recommend('relate', var1='age', var2='bmi')['method'], 'pearson')
        self.assertEqual(self.recommend('relate', variables=['age', 'bmi', 'sbp_baseline'])['method'], 'correlation_matrix')
        self.assertEqual(self.recommend('predict', outcome='sbp_week12', predictors=['arm', 'age'])['method'], 'linear_regression')
        self.assertEqual(self.recommend('predict', outcome='adverse_event', predictors=['arm', 'age'])['method'], 'logistic_regression')
        self.assertEqual(self.recommend('change', measures=['sbp_baseline', 'sbp_week12'])['method'], 'paired_ttest')
        self.assertEqual(self.recommend('change', measures=['sbp_baseline', 'sbp_week12'], between='arm')['method'], 'mixed_anova')
        self.assertEqual(self.recommend('describe', group='arm')['method'], 'table_one')

    def test_skewed_groups_get_a_rank_test(self):
        rng = np.random.default_rng(9)
        data = pd.DataFrame({'g': np.repeat(['a', 'b'], 40), 'y': np.concatenate([rng.exponential(1, 40) ** 3, rng.exponential(2, 40) ** 3])})
        result = selection.recommend(data, [{'name': 'g', 'type': 'categorical'}, {'name': 'y', 'type': 'numeric'}], 'compare', {'outcome': 'y', 'group': 'g'})
        self.assertEqual(result['method'], 'mann_whitney')

    def test_every_recommendation_runs(self):
        cases = [('compare', {'outcome': 'adverse_event', 'group': 'arm'}), ('compare', {'outcome': 'sbp_week12', 'group': 'arm', 'covariates': ['sbp_baseline']}),
                 ('predict', {'outcome': 'adverse_event', 'predictors': ['arm', 'age']}), ('change', {'measures': ['sbp_baseline', 'sbp_week12'], 'between': 'arm'}),
                 ('describe', {'group': 'arm'})]
        for question, fields in cases:
            recommendation = selection.recommend(trial_data(), self.types, question, fields)
            for method in [recommendation['method']]:
                result = stats_service.run_test(method, trial_data(), recommendation['params'])
                self.assertNotIn('error', result, (question, method, result.get('error')))

    def test_bad_questions_are_explained(self):
        with self.assertRaises(selection.SelectionError):
            self.recommend('compare', outcome='age')
        with self.assertRaises(selection.SelectionError):
            self.recommend('teleport')


class EngineApiTests(TempStorageMixin, TestCase):
    def setUp(self):
        super().setUp()
        FeatureEntitlement.objects.update_or_create(code='research_analyzer', defaults={'label': 'Research Analyzer', 'free_enabled': True, 'is_active': True})
        buffer = io.StringIO()
        trial_data().to_csv(buffer, index=False)
        upload = self.client.post('/api/research-analyzer/upload/', {'file': SimpleUploadedFile('trial.csv', buffer.getvalue().encode(), content_type='text/csv')})
        self.session_id = upload.json()['session_id']

    def post(self, path, payload):
        return self.client.post(f'/api/research-analyzer/{path}', json.dumps({'session_id': self.session_id, **payload}), content_type='application/json')

    def test_catalog_recommend_levels_and_run(self):
        catalog = self.client.get('/api/research-analyzer/methods/').json()
        self.assertIn('two_by_two', [method['id'] for method in catalog['methods']])
        recommendation = self.post('recommend/', {'question': 'compare', 'fields': {'outcome': 'adverse_event', 'group': 'arm'}}).json()
        self.assertEqual(recommendation['method'], 'two_by_two')
        self.assertTrue(recommendation['reasons'])
        levels = self.client.get(f'/api/research-analyzer/levels/?session_id={self.session_id}&variable=arm').json()
        self.assertEqual([level['value'] for level in levels['levels']], ['Drug A', 'Drug B'])
        run = self.post('analyze/', {'test': recommendation['method'], 'params': recommendation['params']})
        self.assertEqual(run.status_code, 200)
        self.assertIn('risk_ratio', run.json())

    def test_selection_errors_are_422(self):
        response = self.post('recommend/', {'question': 'compare', 'fields': {'outcome': 'age'}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['code'], 'selection')

    def test_word_export(self):
        report = {'title': 'Trial', 'lang': 'en', 'sections': [{'heading': 'Results', 'paragraphs': ['Adverse events were rare.'],
                                                             'tables': [{'caption': 'Table 1', 'columns': ['Variable', 'A', 'B'], 'rows': [['Age', '55 (12)', '57 (10)']]}]}]}
        response = self.post('report/docx/', {'report': report})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'PK'))
        arabic = self.post('report/docx/', {'report': {**report, 'lang': 'ar', 'title': 'تقرير'}})
        self.assertEqual(arabic.status_code, 200)
