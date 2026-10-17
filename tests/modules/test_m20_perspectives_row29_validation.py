"""Row 29 perspectives() input-validation repair tests (bounded repair of a
reproduced defect: schema-valid proposal dicts with non-numeric lens values
crashed with an uncoded TypeError through the mounted route, which had no
error mapping). Guards refuse non-real/non-finite lens values with ValueError
BEFORE any persona evaluation; valid behavior is byte-preserved (huge ints
compare fine and stay valid; bool stays accepted as its numeric value -
previously accepted behavior preserved).
House-side: full mechanism tier. Native HTTP candidates skip without real
fastapi/pydantic."""
import math
import unittest

from app.modules.m20_general_cognitive_worker.metacognition import PerspectiveSimulator

VALID = {"evidence_count": 3, "risk": "read", "upside": 8, "timeline_days": 10,
         "evidence": ["a", "b", "c"], "externally_visible": False}


class TestPerspectivesValidation(unittest.TestCase):
    def setUp(self):
        self.s = PerspectiveSimulator()

    def test_valid_baseline_unchanged(self):
        views = self.s.evaluate(VALID)
        self.assertEqual(len(views), 5)
        self.assertEqual([v.persona for v in views],
                         ["analyst", "skeptic", "optimist", "operator", "guardian"])

    def test_empty_proposal_defaults_accepted(self):
        self.assertEqual(len(self.s.evaluate({})), 5)

    def test_non_numeric_lens_values_refused(self):
        for key in ("evidence_count", "upside", "timeline_days"):
            for bad in ("high", None, [1, 2], {"x": 1}):
                with self.assertRaises(ValueError, msg=f"{key}={bad!r}"):
                    self.s.evaluate({key: bad})

    def test_bool_lens_values_accepted_preserved(self):
        # bool lens values were accepted on pristine (coerced to 1 in numeric
        # comparisons); previously accepted behavior is preserved.
        for key in ("evidence_count", "upside", "timeline_days"):
            views = self.s.evaluate({key: True})
            self.assertEqual(len(views), 5, msg=key)

    def test_non_finite_lens_values_refused(self):
        for key in ("evidence_count", "upside", "timeline_days"):
            for bad in (float("nan"), float("inf"), float("-inf")):
                with self.assertRaises(ValueError, msg=f"{key}={bad}"):
                    self.s.evaluate({key: bad})

    def test_huge_int_lens_values_accepted(self):
        for key in ("evidence_count", "upside", "timeline_days"):
            views = self.s.evaluate({key: 10**1000})
            self.assertEqual(len(views), 5, msg=key)

    def test_refusal_is_atomic_before_personas(self):
        # both a bad lens value and a crash-order trap: refusal must happen
        # before ANY persona lens is invoked
        with self.assertRaises(ValueError):
            self.s.evaluate({"upside": "high", "evidence_count": "many"})

    def test_risk_and_visibility_any_value_accepted(self):
        # risk uses membership (no crash class); externally_visible truthiness
        views = self.s.evaluate({"risk": 9000, "externally_visible": "yes"})
        self.assertEqual(len(views), 5)


class TestPerspectivesRouteContract(unittest.TestCase):
    def test_route_maps_valueerror_to_422(self):
        import ast, pathlib
        src = (pathlib.Path(__file__).resolve().parents[2]
               / "backend" / "app" / "modules" / "m20_general_cognitive_worker" / "routes.py").read_text()
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "row29_perspectives")
        fsrc = ast.get_source_segment(src, fn)
        self.assertIn("except ValueError", fsrc)
        self.assertIn("422", fsrc)


def _real_deps():
    try:
        import fastapi, pydantic
        return getattr(pydantic, "VERSION", None) is not None
    except ImportError:
        return False


@unittest.skipUnless(_real_deps(), "native HTTP candidate: real fastapi+pydantic required")
class TestNativeHttpCandidate(unittest.TestCase):
    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.modules.m20_general_cognitive_worker.routes import router, get_service
        from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_service] = lambda: CognitiveWorkerService()
        return TestClient(app)

    def _post(self, proposal):
        return self._client().post("/api/modules/20/meta/perspectives",
                                   json={"proposal": proposal})

    def test_str_lens_422_not_500(self):
        self.assertEqual(self._post({"upside": "high"}).status_code, 422)

    def test_nan_lens_422_not_500(self):
        # client-side json.dumps cannot encode NaN; send the raw JSON body so the
        # NaN reaches the server parser and exercises the route, not the client
        r = self._client().post(
            "/api/modules/20/meta/perspectives",
            content=b'{"proposal": {"timeline_days": NaN}}',
            headers={"content-type": "application/json"})
        self.assertEqual(r.status_code, 422)

    def test_bool_lens_200(self):
        self.assertEqual(self._post({"evidence_count": True}).status_code, 200)

    def test_valid_200(self):
        r = self._post(VALID)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["perspectives"]), 5)

    def test_empty_200(self):
        self.assertEqual(self._post({}).status_code, 200)


if __name__ == "__main__":
    unittest.main()
