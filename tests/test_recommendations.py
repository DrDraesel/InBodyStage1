import copy
import unittest

from backend.recommendations import build_plan, validate_context
from backend.server import Application
from tests import test_stage1 as fixtures


class RecommendationPlans(unittest.TestCase):
    setUp = fixtures.Stage1.setUp
    tearDown = fixtures.Stage1.tearDown
    payload = fixtures.Stage1.payload

    def test_segmental_pair_is_observation_not_weakness_or_dose(self):
        payload = self.payload()
        payload['measurements'] += [{'metric': 'right_arm_lean_mass', 'value': 4, 'unit': 'kg'},
                                    {'metric': 'left_arm_lean_mass', 'value': 3.6, 'unit': 'kg'}]
        result = self.s.import_result('SYN-1', payload, 'test', 'mock_api')
        plan = result['analyses'][0]['recommendation_plan']
        self.assertEqual(plan['segmental_observations'][0]['difference_percent_of_larger'], 10)
        self.assertIsNone(plan['segmental_observations'][0]['clinical_threshold'])
        arm = next(d for d in plan['domains'] if d['id'] == 'arm_training')
        self.assertEqual(arm['status'], 'assessment_required')
        self.assertIn('does not prove greater strength', arm['rationale'])
        peptides = next(d for d in plan['domains'] if d['id'] == 'peptides')
        self.assertEqual(peptides['status'], 'prescriber_review_required')
        self.assertIn('No peptide, dose or protocol', peptides['rationale'])
        self.assertTrue(all(not d['is_treatment_order'] for d in plan['domains']))

    def test_unverified_and_mismatched_units_never_create_asymmetry(self):
        result = {'id': 'test', 'test_timestamp': '2026-10-08T10:00:00-04:00',
                  'measurements': [{'metric': 'right_leg_lean_mass', 'value': 10, 'unit': 'kg', 'status': 'unverified'},
                                   {'metric': 'left_leg_lean_mass', 'value': 9, 'unit': 'kg', 'status': 'verified'}]}
        patient = {'dob': '1980-01-01'}
        plan = build_plan(result, patient, {})
        self.assertTrue(plan['source_confirmation_required'])
        self.assertEqual(plan['segmental_observations'], [])
        result['measurements'][0]['status'] = 'verified'
        result['measurements'][0]['unit'] = 'lb'
        self.assertEqual(build_plan(result, patient, {})['segmental_observations'], [])

    def test_context_regenerates_analysis_and_preserves_earlier_snapshot(self):
        result = self.s.import_result('SYN-1', self.payload(), 'test', 'mock_api')
        original = copy.deepcopy(result['analyses'][0])
        app = Application(self.s)
        context = {'goals': 'Synthetic goal: safer walking', 'cardiovascular_symptoms': 'yes',
                   'falls_or_balance_concern': 'yes', 'pain_present': 'yes'}
        code, current = app.route('POST', '/patients/SYN-1/inbody/'+result['id']+'/analyze',
                                  {'recommendation_context': context}, None, 'clinician')
        self.assertEqual(code, 201)
        self.assertNotEqual(current['id'], original['id'])
        plan = current['recommendation_plan']
        self.assertEqual(plan['context']['goals'], context['goals'])
        activity = next(d for d in plan['domains'] if d['id'] == 'activity')
        self.assertEqual(activity['status'], 'assessment_required')
        self.assertIn('Cardiovascular symptoms were reported', activity['rationale'])
        saved = self.s.detail('SYN-1', result['id'])
        earlier = next(a for a in saved['analyses'] if a['id'] == original['id'])
        self.assertEqual(earlier['recommendation_plan'], original['recommendation_plan'])
        self.assertEqual(plan['source_result_id'], result['id'])

    def test_unknown_age_and_invalid_context_not_treated_as_clearance(self):
        result = {'id': 'test', 'test_timestamp': '2026-10-08T10:00:00-04:00', 'measurements': []}
        plan = build_plan(result, {}, {})
        activity = next(d for d in plan['domains'] if d['id'] == 'activity')
        self.assertNotIn('150 minutes', ' '.join(activity['options_to_discuss']))
        self.assertIn('cardiovascular_symptoms', plan['missing_context'])
        for invalid in ({'clinical_history_reviewed': 'yes'}, {'pain_present': 'cleared'}, {'goals': 'x'*501}, {'diagnosis': 'invented'}):
            with self.assertRaises(ValueError): validate_context(invalid)
