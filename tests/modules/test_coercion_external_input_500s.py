"""Systemic external-input coercion repair: m15 design_support 333-359,
m15 creative_production 306-332, m21 owner_workflow 279-329.
RED on pristine: bare int()/float() on externally supplied fields raises
uncaught TypeError (non-scalar), OverflowError (non-finite int target) or
in creative's case even bare ValueError, escaping each route's coded
refusal mapping -> HTTP 500. Repair: file-local _fnum/_inum helpers
raising each file's own coded refusal type (ValueError; CreativeError for
creative_production, whose route maps only that type). Valid coercions
(numeric strings, bools, truncating floats, accepted non-finite floats)
preserved."""
import unittest

from app.modules.m15_document_generator.design_support_333_359 import design_support_333_359 as ds
from app.modules.m15_document_generator.creative_production_306_332 import CreativeError, plan
from app.modules.m21_claire.owner_workflow_279_329 import (
    claire_owner_workflow_279_329 as ow, preference_feedback_4_6_9 as pf)

BASE = {'brief': 'b', 'decision_owner': 'o'}
SAFETY = {'requirements': ['r'], 'hazards': [{'id': 'h', 'severity': 3, 'likelihood': 2}]}
GAME = {'gameplay_loops': ['x'], 'content_nodes': ['n']}
STAKE = {'stakeholders': ['s'], 'evidence': ['e'], 'criteria': [{'id': 'k', 'weight': 1}],
         'ideas': [{'id': 'i', 'scores': {'k': 2}}]}
SRC = [{'source_id': 's', 'observed_at': 'now'}]
PREF = {'consent': {'status': 'granted', 'scope': 's'}, 'provenance': ['p'],
        'examples': [{'id': 'e', 'purpose': 'help'}],
        'holdout': [{'baseline_score': 1, 'candidate_score': 2}]}
INF = float('inf')  # what a JSON parser yields for a literal like 1e999


class TestDesignCoercion(unittest.TestCase):
    def test_hazards_severity_non_scalar(self):
        with self.assertRaises(ValueError):
            ds(334, {**BASE, 'requirements': ['r'],
                     'hazards': [{'id': 'h', 'severity': {'s': 1}, 'likelihood': 2}]})

    def test_hazards_likelihood_non_finite(self):
        with self.assertRaises(ValueError):
            ds(334, {**BASE, 'requirements': ['r'],
                     'hazards': [{'id': 'h', 'severity': 3, 'likelihood': INF}]})

    def test_playtests_rate_non_scalar(self):
        with self.assertRaises(ValueError):
            ds(342, {**BASE, **GAME, 'playtests': [{'completion_rate': {'c': 1}}]})

    def test_economy_amount_non_scalar(self):
        with self.assertRaises(ValueError):
            ds(342, {**BASE, **GAME, 'economy': {'sources': [{'amount': {'s': 1}}]}})

    def test_weighted_score_and_weight_non_scalar(self):
        with self.assertRaises(ValueError):
            ds(355, {**BASE, **STAKE, 'ideas': [{'id': 'i', 'scores': {'k': {'v': 1}}}]})
        with self.assertRaises(ValueError):
            ds(355, {**BASE, **STAKE, 'criteria': [{'id': 'k', 'weight': {'w': 1}}]})

    def test_marine_displacement_non_scalar(self):
        with self.assertRaises(ValueError):
            ds(333, {**BASE, **SAFETY, 'displacement_kg': {'x': 1}, 'hull_volume_m3': 5})

    def test_toy_diameter_non_scalar(self):
        with self.assertRaises(ValueError):
            ds(334, {**BASE, **SAFETY, 'age_range': [3, 6], 'parts': [{'diameter_mm': {'b': 1}}]})

    def test_economy_339_amount_non_scalar(self):
        with self.assertRaises(ValueError):
            ds(339, {**BASE, **GAME, 'economy': {'sources': [{'amount': {'s': 1}}]}})


class TestCreativeCoercion(unittest.TestCase):
    def test_sample_rate_non_scalar_is_creative_error(self):
        with self.assertRaises(CreativeError):
            plan(306, {'tracks': ['t'], 'sample_rate': {'x': 1},
                       'target_platform': 'p', 'sources': SRC})

    def test_sample_rate_bad_string_is_creative_error(self):
        # route maps CreativeError only; a bare ValueError here was a 500
        with self.assertRaises(CreativeError):
            plan(306, {'tracks': ['t'], 'sample_rate': 'abc',
                       'target_platform': 'p', 'sources': SRC})

    def test_tolerance_non_scalar_is_creative_error(self):
        with self.assertRaises(CreativeError):
            plan(321, {'object': 'o', 'dimensions': [{'tolerance': {'x': 1}}],
                       'standard': 's', 'sources': SRC, 'human_review': True})


class TestOwnerWorkflowCoercion(unittest.TestCase):
    def test_budget_value_non_scalar(self):
        with self.assertRaises(ValueError):
            ow(313, {'goal': 'g', 'acceptance_criteria': ['c'],
                     'approval_request': {'id': 'a', 'operation': 'op'},
                     'budget': {'seconds': {'x': 1}}})

    def test_candidate_score_non_scalar(self):
        with self.assertRaises(ValueError):
            pf(6, {**PREF, 'candidates': [{'id': 'c', 'score': {'x': 1}}]})

    def test_holdout_score_non_scalar(self):
        with self.assertRaises(ValueError):
            pf(6, {**PREF, 'holdout': [{'baseline_score': {'x': 1}, 'candidate_score': 2}]})

    def test_refusal_messages_field_static(self):
        try:
            ds(342, {**BASE, **GAME, 'economy': {'sources': [{'amount': 'zz-sentinel'}]}})
        except ValueError as e:
            self.assertNotIn('zz-sentinel', str(e))
            self.assertIn('economy.sources.amount', str(e))
        else:
            self.fail('expected ValueError')


class TestPreviouslyValidPreserved(unittest.TestCase):
    def test_design_string_and_truncating_float(self):
        ds(334, {**BASE, 'requirements': ['r'],
                 'hazards': [{'id': 'h', 'severity': '3', 'likelihood': 2.9}]})

    def test_design_playtest_strings(self):
        ds(342, {**BASE, **GAME, 'playtests': [{'completion_rate': '.8', 'duration_minutes': 10}]})

    def test_creative_int_sample_rate(self):
        plan(306, {'tracks': ['t'], 'sample_rate': 48000,
                   'target_platform': 'p', 'sources': SRC})

    def test_owner_budget_absent_limits_keeps_infinite_default(self):
        ow(313, {'goal': 'g', 'acceptance_criteria': ['c'],
                 'approval_request': {'id': 'a', 'operation': 'op'},
                 'budget': {'seconds': 5}})

    def test_owner_score_strings(self):
        pf(6, {**PREF, 'holdout': [{'baseline_score': '1', 'candidate_score': 2}]})


def _real_deps():
    try:
        import fastapi, pydantic
        return getattr(pydantic, 'VERSION', None) is not None
    except ImportError:
        return False


@unittest.skipUnless(_real_deps(), 'native HTTP candidate: real fastapi+pydantic required')
class TestNativeHttp(unittest.TestCase):
    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.auth import context as authctx
        from app.auth.context import TenantContext
        from app.modules.m15_document_generator.routes import router as m15
        from app.modules.m21_claire.routes import router as m21
        app = FastAPI()
        app.include_router(m15, prefix='/api/v1')
        app.include_router(m21, prefix='/api/v1')
        app.dependency_overrides[authctx.require_tenant] = lambda: TenantContext('t1', 'a1')
        return TestClient(app, raise_server_exceptions=False)

    def test_design_garbage_422_not_500(self):
        c = self._client()
        r = c.post('/api/v1/document-generator/design-333-359/support', json={
            'feature_id': 334, 'data': {**BASE, 'requirements': ['r'],
                                        'hazards': [{'id': 'h', 'severity': {'s': 1}, 'likelihood': 2}]}})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()['detail'], 'hazards.severity must be an integer')

    def test_creative_garbage_422_not_500(self):
        c = self._client()
        for sr in ({'x': 1}, 'abc'):
            r = c.post('/api/v1/document-generator/creative-production-306-332/306', json={
                'tracks': ['t'], 'sample_rate': sr, 'target_platform': 'p', 'sources': SRC})
            self.assertEqual(r.status_code, 422, sr)
            self.assertEqual(r.json()['detail'], 'sample_rate must be a number')

    def test_owner_workflow_garbage_422_not_500(self):
        c = self._client()
        r = c.post('/api/v1/claire/owner-workflow-279-329', json={
            'row_id': 313, 'data': {'goal': 'g', 'acceptance_criteria': ['c'],
                                    'approval_request': {'id': 'a', 'operation': 'op'},
                                    'budget': {'seconds': {'x': 1}}}})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()['detail'], 'budget.seconds must be a number')

    def test_valid_coercions_200(self):
        c = self._client()
        r = c.post('/api/v1/document-generator/design-333-359/support', json={
            'feature_id': 334, 'data': {**BASE, 'requirements': ['r'],
                                        'hazards': [{'id': 'h', 'severity': '3', 'likelihood': 2}]}})
        self.assertEqual(r.status_code, 200)
        r = c.post('/api/v1/document-generator/creative-production-306-332/306', json={
            'tracks': ['t'], 'sample_rate': '48000', 'target_platform': 'p', 'sources': SRC})
        self.assertEqual(r.status_code, 200)


if __name__ == '__main__':
    unittest.main()
