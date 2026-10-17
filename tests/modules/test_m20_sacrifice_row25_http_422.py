"""Row 25 opportunity-cost route HTTP 422 mapping candidate. The delivered
consolidated repair added coded finite/missing/bool ValueError refusals to
quantify_sacrifice, but the row-25 route had no except mapping, so those
coded refusals surfaced as HTTP 500 while sibling rows 24/26 map ValueError
to 422. AST pin (source inference only, no HTTP claim) plus native tier
(real fastapi+pydantic TestClient): inf/bool/missing-value payloads must get
422 with no input echo; a valid payload still gets 200. Skips house-side."""
import ast
import pathlib
import unittest

ROUTES_SRC = (pathlib.Path(__file__).resolve().parents[2]
              / "backend" / "app" / "modules" / "m20_general_cognitive_worker" / "routes.py").read_text()


def _real_deps():
    try:
        import fastapi, pydantic
        return getattr(pydantic, "VERSION", None) is not None
    except ImportError:
        return False


class TestRouteMappingContract(unittest.TestCase):
    def test_row25_route_maps_valueerror_to_422(self):
        tree = ast.parse(ROUTES_SRC)
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "row25_opportunity_cost")
        src = ast.get_source_segment(ROUTES_SRC, fn)
        self.assertIn("except ValueError", src)
        self.assertIn("422", src)


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
        return TestClient(app, raise_server_exceptions=False)

    def _post(self, payload):
        return self._client().post("/api/modules/20/meta/decisions/opportunity-cost", json=payload)

    def test_inf_value_422(self):
        # TestClient json= cannot encode inf; send the raw JSON body, which
        # stdlib json.loads (Starlette request parsing) accepts as Infinity.
        r = self._client().post(
            "/api/modules/20/meta/decisions/opportunity-cost",
            content='{"chosen": {"name": "x", "value": 1.0}, '
                    '"alternatives": [{"name": "y", "value": Infinity}]}',
            headers={"content-type": "application/json"})
        self.assertEqual(r.status_code, 422)

    def test_bool_value_422(self):
        r = self._post({"chosen": {"name": "x", "value": True}, "alternatives": []})
        self.assertEqual(r.status_code, 422)

    def test_missing_value_key_422(self):
        r = self._post({"chosen": {"name": "x", "value": 1.0},
                        "alternatives": [{"name": "y"}]})
        self.assertEqual(r.status_code, 422)

    def test_refusal_body_has_no_input_echo(self):
        r = self._post({"chosen": {"name": "x", "value": True}, "alternatives": []})
        self.assertEqual(r.status_code, 422)
        self.assertNotIn("true", r.text.lower())
        self.assertNotIn('"x"', r.text)

    def test_static_detail_pinned(self):
        r = self._post({"chosen": {"name": "x", "value": True}, "alternatives": []})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"], "chosen requires a finite numeric 'value'")

    def test_unexpected_internal_exception_remains_500(self):
        # Kills a broadened `except Exception` mutant at runtime: an internal
        # fault (not a coded client-input ValueError) must not become 422.
        import app.modules.m20_general_cognitive_worker.metacognition as meta
        original = meta.quantify_sacrifice
        def _fault(chosen, alternatives):
            raise RuntimeError("simulated internal fault")
        meta.quantify_sacrifice = _fault
        try:
            r = self._post({"chosen": {"name": "x", "value": 1.0}, "alternatives": []})
        finally:
            meta.quantify_sacrifice = original
        self.assertEqual(r.status_code, 500)

    def test_valid_200(self):
        r = self._post({"chosen": {"name": "x", "value": 1.0},
                        "alternatives": [{"name": "y", "value": 0.5}, {"name": "z", "value": 0.75}]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["best_foregone"]["name"], "z")
        self.assertEqual(body["opportunity_cost"], -0.25)


if __name__ == "__main__":
    unittest.main()
