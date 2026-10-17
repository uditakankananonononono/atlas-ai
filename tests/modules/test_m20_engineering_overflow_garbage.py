"""Engineering workbench 1510-1559: derived-overflow and degenerate-input
repair (ledger rows 1510-1559, verified-pushed family).
RED on pristine: Arrhenius acceleration factor with valid positive finite
inputs overflows math.exp -> uncoded OverflowError -> HTTP 500 (route maps
ValueError/KeyError/TypeError/ZeroDivisionError but NOT OverflowError).
Repair: coded ValueError before the exp dispatch; valid
behavior byte-preserved. The vibration degenerate case was investigated and
CLOSED as pinned intended behavior (reference-diagnostics envelope, pinned by
test_m20_engineering_1510_1559.py::test_engineering_reference_diagnostics...)."""
import math
import unittest

from app.modules.m20_general_cognitive_worker.engineering_1510_1559 import (
    engineering_support_1510_1559 as run)


class TestDerivedOverflow(unittest.TestCase):
    def test_arrhenius_overflow_refused_coded(self):
        # valid positive finite inputs whose exponent exceeds float range
        with self.assertRaises(ValueError):
            run('accelerated_life_testing', {
                'activation_energy_ev': 50.0, 'use_temperature_k': 1.0,
                'test_temperature_k': 300.0})

    def test_arrhenius_near_boundary_still_accepted(self):
        # exponents up to log(sys.float_info.max) ~ 709.7827 are representable
        # and MUST stay accepted: a conservative cutoff (e.g. 709.0) would
        # refuse previously valid inputs. ex ~ 709.5 here.
        kb = 8.617333262e-5
        ea = 709.5 * kb / (1 / 1.0 - 1 / 2.0)
        r = run('accelerated_life_testing', {
            'activation_energy_ev': ea, 'use_temperature_k': 1.0,
            'test_temperature_k': 2.0})
        self.assertTrue(math.isfinite(r['result']['acceleration_factor']))

    def test_arrhenius_just_past_boundary_refused(self):
        # ex ~ 709.79 > log(max float): result not representable
        kb = 8.617333262e-5
        ea = 709.79 * kb / (1 / 1.0 - 1 / 2.0)
        with self.assertRaises(ValueError):
            run('accelerated_life_testing', {
                'activation_energy_ev': ea, 'use_temperature_k': 1.0,
                'test_temperature_k': 2.0})

    def test_arrhenius_valid_unchanged(self):
        r = run('accelerated_life_testing', {
            'activation_energy_ev': 0.5, 'use_temperature_k': 300.0,
            'test_temperature_k': 400.0})
        self.assertIn('acceleration_factor', r['result'])
        self.assertTrue(math.isfinite(r['result']['acceleration_factor']))


class TestDegenerateGarbage(unittest.TestCase):
    def test_vibration_empty_diagnostics_preserved(self):
        # pinned contract (test_m20_engineering_1510_1559.py): vibration_testing
        # is a reference-diagnostics method; empty data returns the template
        # envelope, test_executed False - preserved, NOT a defect
        out = run('vibration_testing', {})
        self.assertEqual(out['status'], 'supplied_diagnostics_or_template_only')
        self.assertIs(out['named_capability_executed'], False)

    def test_vibration_valid_unchanged(self):
        r = run('vibration_testing', {'psd_points': [
            {'frequency_hz': 10, 'psd_g2_per_hz': 0.1},
            {'frequency_hz': 20, 'psd_g2_per_hz': 0.2}]})
        self.assertGreater(r['result']['grms'], 0)


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
        from app.modules.m20_general_cognitive_worker.engineering_routes_1510_1559 import router
        from app.auth import context as authctx
        from app.auth.context import TenantContext
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[authctx.require_tenant] = (
            lambda: TenantContext(tenant_id='t1', actor_id='a1'))
        return TestClient(app, raise_server_exceptions=False)

    def _post(self, method, data):
        return self._client().post('/engineering/1510-1559/analyze',
                                   json={'method': method, 'data': data})

    def test_alt_overflow_422_not_500(self):
        r = self._post('accelerated_life_testing', {
            'activation_energy_ev': 50.0, 'use_temperature_k': 1.0,
            'test_temperature_k': 300.0})
        self.assertEqual(r.status_code, 422)

    def test_near_boundary_200(self):
        kb = 8.617333262e-5
        ea = 709.5 * kb / (1 / 1.0 - 1 / 2.0)
        r = self._post('accelerated_life_testing', {
            'activation_energy_ev': ea, 'use_temperature_k': 1.0,
            'test_temperature_k': 2.0})
        self.assertEqual(r.status_code, 200)

    def test_valid_200(self):
        r = self._post('accelerated_life_testing', {
            'activation_energy_ev': 0.5, 'use_temperature_k': 300.0,
            'test_temperature_k': 400.0})
        self.assertEqual(r.status_code, 200)


if __name__ == '__main__':
    unittest.main()
