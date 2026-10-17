"""Row 28 rollup ROUTE schema-error repair tests v2 (bounded caller repair:
schema-invalid plan entries crashed with an uncoded 500 - PlanNode
construction ran before the route's try - AND the first repair leaked raw
caller values via str(ValidationError). v2: schema errors map to coded 422
with structured field/type ONLY (loc+type, never input/msg/ctx/values);
non-mapping entries and keyword-type failures get a fixed safe 422; the
bounded mechanism (guard) ValueError contract detail=str(exc) is preserved).
House-side: AST pins only (source structure, no HTTP claim). Native tier
(real fastapi+pydantic): TestClient POSTs prove 422s, privacy non-echo, and
unchanged 200/valid behavior. Skips house-side."""
import ast
import pathlib
import unittest

ROUTES_SRC = (pathlib.Path(__file__).resolve().parents[2]
              / "backend" / "app" / "modules" / "m20_general_cognitive_worker" / "routes.py").read_text()


def _route_fn():
    tree = ast.parse(ROUTES_SRC)
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "row28_rollup")


def _validationerror_handler_src():
    tree = ast.parse(ROUTES_SRC)
    fn = _route_fn()
    for node in ast.walk(fn):
        if isinstance(node, ast.ExceptHandler) and node.type and "ValidationError" in ast.dump(node.type):
            return "".join(ast.get_source_segment(ROUTES_SRC, s) for s in node.body)
    raise AssertionError("no ValidationError handler in row28_rollup")


class TestRouteSchema422Structure(unittest.TestCase):
    def test_schema_errors_handled_with_structured_field_type_only(self):
        handler = _validationerror_handler_src()
        self.assertIn("422", handler)
        self.assertIn('"loc"', handler)
        self.assertIn('"type"', handler)
        # privacy: the schema-error branch must not echo exception text,
        # message strings, inputs, or context values
        self.assertNotIn("str(exc)", handler)
        self.assertNotIn('"msg"', handler)
        self.assertNotIn('"input"', handler)
        self.assertNotIn('"ctx"', handler)

    def test_plannode_construction_guarded(self):
        fn = _route_fn()
        src = ast.get_source_segment(ROUTES_SRC, fn)
        self.assertIn("isinstance(n, dict)", src)
        # construction sits inside a try whose handlers include ValidationError
        self.assertIn("_PlanNode(**n)", src)
        _validationerror_handler_src()

    def test_mechanism_valueerror_contract_preserved(self):
        src = ast.get_source_segment(ROUTES_SRC, _route_fn())
        self.assertIn("except ValueError", src)
        self.assertIn("detail=str(exc)", src)


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

    def _post(self, plan, level="steps"):
        return self._client().post("/api/modules/20/meta/abstraction/rollup",
                                   json={"goal": "g", "plan": plan, "level": level})

    def test_missing_title_422_no_value_echo(self):
        r = self._post([{"id": "a"}, {"id": "b", "title": "pr1vate-marker-title"}])
        self.assertEqual(r.status_code, 422)
        self.assertNotIn("pr1vate-marker-title", r.text)

    def test_bad_risk_422_no_value_echo(self):
        r = self._post([{"id": "a", "title": "pr1vate-marker-title", "risk": "explode-now"}])
        self.assertEqual(r.status_code, 422)
        self.assertNotIn("pr1vate-marker-title", r.text)
        self.assertNotIn("explode-now", r.text)

    def test_non_object_entry_422(self):
        r = self._post(["not-a-mapping"])
        self.assertEqual(r.status_code, 422)

    def test_cycle_still_422(self):
        plan = [{"id": "a", "title": "x", "depends_on": ["b"]},
                {"id": "b", "title": "y", "depends_on": ["a"]}]
        self.assertEqual(self._post(plan).status_code, 422)

    def test_unknown_level_422(self):
        r = self._post([{"id": "a", "title": "x"}], level="quantum")
        self.assertEqual(r.status_code, 422)

    def test_duplicate_titles_distinct_ids_accepted(self):
        plan = [{"id": "a", "title": "same"}, {"id": "b", "title": "same", "depends_on": ["a"]}]
        r = self._post(plan)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["steps"]), 2)

    def test_valid_200(self):
        plan = [{"id": "a", "title": "x"}, {"id": "b", "title": "y", "depends_on": ["a"]}]
        r = self._post(plan)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["steps"]), 2)


if __name__ == "__main__":
    unittest.main()
