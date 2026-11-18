"""Sample size engine: results pinned to G*Power 3.1 and published reference values, plus the API."""
import json

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from accounts.models import FeatureEntitlement
from research_analyzer.engine.sample_size import PlanningError, calculate, catalog


def completers(design, inputs, mode='n'):
    return [group['completers'] for group in calculate(design, mode, inputs)['per_group']]


class ReferenceValueTests(SimpleTestCase):
    """Each expected number is what G*Power 3.1 or the cited paper gives for the same inputs."""

    def test_t_tests_match_g_power(self):
        self.assertEqual(completers('two_means', {'difference': 5, 'sd': 10}), [64, 64])  # d = 0.5
        self.assertEqual(completers('two_means', {'difference': 5, 'sd': 10, 'power': 90}), [86, 86])
        self.assertEqual(completers('two_means', {'difference': 5, 'sd': 10, 'ratio': 2}), [48, 96])
        self.assertEqual(completers('paired_means', {'difference': 5, 'sd_diff': 10}), [34])  # dz = 0.5

    def test_f_tests_match_g_power(self):
        self.assertEqual(sum(completers('anova', {'f': 0.25, 'groups': 3})), 159)
        self.assertEqual(completers('regression', {'f2': 0.15, 'tested_predictors': 5, 'total_predictors': 5}), [92])

    def test_two_proportions_with_and_without_continuity_correction(self):
        self.assertEqual(completers('two_proportions', {'p1': 40, 'p2': 55}), [173, 173])
        self.assertEqual(completers('two_proportions', {'p1': 40, 'p2': 55, 'continuity': '1'}), [186, 186])

    def test_survival_events_follow_schoenfeld(self):
        result = calculate('logrank', 'n', {'hazard_ratio': 0.7, 'event_probability': 50})
        self.assertEqual(result['total']['events'], 247)
        self.assertEqual(result['total']['completers'], 494)

    def test_estimation_designs(self):
        self.assertEqual(completers('single_proportion', {'proportion': 50, 'margin': 5}), [385])
        self.assertEqual(completers('diagnostic', {'sensitivity': 85, 'specificity': 90, 'prevalence': 20, 'margin': 5}), [980])
        self.assertEqual(completers('correlation', {'r': 0.3}), [85])

    def test_riley_prediction_model_example(self):
        # Riley et al. BMJ 2020: 24 parameters, prevalence 0.174, Cox-Snell R² 0.288 → 662 participants.
        result = calculate('prediction', 'n', {'parameters': 24, 'prevalence': 17.4, 'r2_cs': 0.288})
        self.assertEqual(result['total']['completers'], 662)

    def test_power_and_detectable_effect_invert_the_sample_size(self):
        power = calculate('two_means', 'power', {'difference': 5, 'sd': 12, 'n_available': 92})['power']
        self.assertAlmostEqual(power, 0.80, places=2)
        detectable = calculate('two_means', 'mde', {'difference': 5, 'sd': 12, 'n_available': 92})['answer']['value']
        self.assertAlmostEqual(detectable, 5.0, delta=0.05)
        with60 = calculate('two_means', 'power', {'difference': 5, 'sd': 12, 'n_available': 60})['power']
        self.assertAlmostEqual(with60, 0.619, places=3)


class AdjustmentTests(SimpleTestCase):
    def test_dropout_rounds_up_per_group(self):
        result = calculate('two_means', 'n', {'difference': 5, 'sd': 12, 'dropout': 10})
        self.assertEqual((result['per_group'][0]['completers'], result['per_group'][0]['recruit']), (92, 103))
        self.assertEqual(result['total']['recruit'], 206)

    def test_response_rate_population_and_steps(self):
        result = calculate('single_proportion', 'n', {'proportion': 50, 'margin': 5, 'population': 2000, 'response_rate': 80})
        self.assertEqual([step['n'] for step in result['steps']], [385, 323, 404])
        self.assertEqual(result['total'], {'completers': 323, 'recruit': 404})
        self.assertIn('response rate of 80%', result['writeup_en'])

    def test_cohort_relative_risk_and_case_control_odds_ratio_inputs(self):
        cohort = calculate('two_proportions', 'n', {'p1': 10, 'relative_risk': 2})
        self.assertEqual(cohort['per_group'][0]['completers'], calculate('two_proportions', 'n', {'p1': 10, 'p2': 20})['per_group'][0]['completers'])
        self.assertIn('relative risk of 2', cohort['writeup_en'])
        case_control = calculate('two_proportions', 'n', {'p1': 20, 'odds_ratio_exposure': 2})
        self.assertAlmostEqual(case_control['effect'], 1 / 3, places=6)  # odds 0.25 × 2 = 0.5 → 33.3%
        self.assertIn('odds ratio of 2', case_control['writeup_en'])
        with self.assertRaises(PlanningError):
            calculate('two_proportions', 'n', {'p1': 60, 'relative_risk': 2})

    def test_population_correction_is_applied_after_the_design_effect(self):
        result = calculate('single_proportion', 'n', {'proportion': 50, 'margin': 5, 'population': 100, 'design_effect': 2})
        self.assertLessEqual(result['total']['completers'], 100)

    def test_cluster_design_effect(self):
        result = calculate('two_means', 'n', {'difference': 5, 'sd': 12, 'icc': 0.05, 'cluster_size': 20})
        self.assertAlmostEqual(result['settings']['design_effect'], 1.95)
        self.assertEqual(result['total']['clusters'], [9, 9])

    def test_warnings(self):
        self.assertTrue(calculate('single_proportion', 'n', {'proportion': 2, 'margin': 5})['warnings'])
        self.assertTrue(calculate('two_means', 'power', {'difference': 5, 'sd': 12, 'n_available': 30})['warnings'])

    def test_bad_inputs_raise_a_readable_error(self):
        with self.assertRaises(PlanningError):
            calculate('two_proportions', 'n', {'p1': 40, 'p2': 40})
        with self.assertRaises(PlanningError):
            calculate('two_means', 'n', {'difference': 5})
        with self.assertRaises(PlanningError):
            calculate('noninferiority', 'mde', {'margin': 5, 'sd': 10, 'n_available': 50})

    def test_every_design_calculates_with_typical_inputs(self):
        typical = {
            'single_proportion': {'proportion': 30, 'margin': 5}, 'single_mean': {'sd': 10, 'margin': 2},
            'two_proportions': {'p1': 40, 'p2': 55}, 'two_means': {'difference': 5, 'sd': 12}, 'anova': {'f': 0.25, 'groups': 3},
            'paired_means': {'difference': 5, 'sd': 10}, 'mcnemar': {'p10': 20, 'p01': 10}, 'correlation': {'r': 0.3},
            'regression': {'f2': 0.15, 'tested_predictors': 2, 'total_predictors': 4}, 'logistic': {'odds_ratio': 1.5, 'event_rate': 20},
            'logrank': {'hazard_ratio': 0.7, 'event_probability': 50}, 'noninferiority': {'margin': 5, 'true_difference': 0, 'sd': 12},
            'diagnostic': {'sensitivity': 85, 'specificity': 90, 'prevalence': 20, 'margin': 5}, 'auc': {'auc': 0.75},
            'prediction': {'parameters': 10, 'prevalence': 20}, 'pilot': {'pilot_rule': 'medium', 'arms': 2},
        }
        designs = {design['id']: design for design in catalog()['designs']}
        self.assertEqual(set(typical), set(designs))
        for design_id, inputs in typical.items():
            for mode in designs[design_id]['modes']:
                extra = {'n_available': 120} if mode != 'n' else {}
                result = calculate(design_id, mode, {**inputs, **extra})
                self.assertGreater(result['total']['completers'], 0, (design_id, mode))
                self.assertTrue(result['writeup_en'], (design_id, mode))


class SampleSizeApiTests(TestCase):
    def setUp(self):
        cache.clear()
        FeatureEntitlement.objects.update_or_create(code='sample_size_calculator', defaults={'label': 'Sample Size Calculator', 'free_enabled': True, 'is_active': True})

    def post(self, path, payload):
        return self.client.post(f'/api/sample-size/{path}', json.dumps(payload), content_type='application/json')

    def test_designs_and_calculation(self):
        self.assertIn('two_means', [design['id'] for design in self.client.get('/api/sample-size/designs/').json()['designs']])
        response = self.post('calculate/', {'design': 'two_means', 'mode': 'n', 'inputs': {'difference': 5, 'sd': 10}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total']['completers'], 128)

    def test_planning_errors_are_422(self):
        response = self.post('calculate/', {'design': 'two_means', 'mode': 'n', 'inputs': {'difference': 5}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['code'], 'planning')

    def test_word_export(self):
        response = self.post('docx/', {'report': {'title': 'Sample size', 'sections': [{'heading': 'Sample size', 'paragraphs': ['A sample of 64 per group.']}]}})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'PK'))
