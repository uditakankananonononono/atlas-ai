"""Row 28 rollup DAG-validation NATIVE HTTP candidate. House-side: AST pin
that the route maps ValueError to 422 (source inference only, no HTTP claim).
Native tier (real fastapi+pydantic): TestClient POSTs with cyclic/duplicate/
unknown-ref plans must get 422, a valid plan 200. Skips house-side."""
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
    def test_row28_route_maps_valueerror_to_422(self):
        tree = ast.parse(ROUTES_SRC)
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "row28_rollup")
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
        return TestClient(app)

    def _post(self, plan):
        return self._client().post("/api/modules/20/meta/abstraction/rollup",
                                   json={"goal": "g", "plan": plan, "level": "steps"})

    def test_cycle_422(self):
        plan = [{"id": "a", "title": "x", "depends_on": ["b"]},
                {"id": "b", "title": "y", "depends_on": ["a"]}]
        self.assertEqual(self._post(plan).status_code, 422)

    def test_duplicate_ids_422(self):
        plan = [{"id": "a", "title": "x"}, {"id": "a", "title": "y"}]
        self.assertEqual(self._post(plan).status_code, 422)

    def test_unknown_ref_422(self):
        plan = [{"id": "a", "title": "x", "depends_on": ["ghost"]}]
        self.assertEqual(self._post(plan).status_code, 422)

    def test_valid_200(self):
        plan = [{"id": "a", "title": "x"}, {"id": "b", "title": "y", "depends_on": ["a"]}]
        r = self._post(plan)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["steps"]), 2)


if __name__ == "__main__":
    unittest.main()
