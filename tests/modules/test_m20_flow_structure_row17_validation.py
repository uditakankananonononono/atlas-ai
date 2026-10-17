"""Row 17 flow/structure input-validation repair tests (bounded repair of a
reproduced defect: schema-valid task dicts crashed the mounted route uncoded -
None difficulty -> TypeError, huge int -> OverflowError, non-dict task ->
AttributeError, str difficulty -> builtin ValueError - and bool difficulty was
silently coerced). Guards refuse with coded ValueError BEFORE sorting; valid
behavior byte-preserved (missing difficulty keeps 0.5 default; [0,1] range
matches the existing zone-assessment contract, made early/coded).
House-side: full mechanism tier. Native HTTP candidates skip without real
fastapi/pydantic."""
import unittest

from app.modules.m20_general_cognitive_worker.metacognition import FlowStateManager


class TestFlowStructureValidation(unittest.TestCase):
    def setUp(self):
        self.s = FlowStateManager()

    def test_valid_baseline_unchanged(self):
        out = self.s.structure_work(
            [{"title": "a", "difficulty": 0.3}, {"title": "b"}], skill=0.5)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["title"], "b")  # |0.5-0.5|=0 sorts first
        self.assertNotIn("difficulty", out[0])  # 0.5 default not materialized
        self.assertEqual(out[1]["title"], "a")

    def test_str_difficulty_refused(self):
        with self.assertRaises(ValueError):
            self.s.structure_work([{"title": "a", "difficulty": "hard"}], skill=0.5)

    def test_none_difficulty_refused_coded(self):
        with self.assertRaises(ValueError):  # TypeError on pristine bytes
            self.s.structure_work([{"title": "a", "difficulty": None}], skill=0.5)

    def test_huge_int_difficulty_refused_coded(self):
        with self.assertRaises(ValueError):  # OverflowError on pristine bytes
            self.s.structure_work([{"title": "a", "difficulty": 10**1000}], skill=0.5)

    def test_bool_difficulty_accepted_preserved(self):
        # bool difficulty was accepted on pristine (True coerces to 1.0, a valid
        # challenge for assess()); previously-accepted behavior is preserved.
        out = self.s.structure_work([{"title": "a", "difficulty": True}], skill=0.5)
        self.assertEqual(len(out), 1)
        self.assertIs(out[0]["difficulty"], True)  # entry spread byte-preserved
        self.assertEqual(out[0]["zone"], "anxiety")  # assess(1.0, 0.5)

    def test_non_finite_difficulty_refused(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError, msg=str(bad)):
                self.s.structure_work([{"title": "a", "difficulty": bad}], skill=0.5)

    def test_out_of_range_difficulty_refused(self):
        for bad in (-0.1, 1.1, 2.5):
            with self.assertRaises(ValueError, msg=str(bad)):
                self.s.structure_work([{"title": "a", "difficulty": bad}], skill=0.5)

    def test_non_dict_task_refused_coded(self):
        with self.assertRaises(ValueError):  # AttributeError on pristine bytes
            self.s.structure_work(["not-a-dict"], skill=0.5)

    def test_refusal_atomic_before_sort(self):
        with self.assertRaises(ValueError):
            self.s.structure_work(
                [{"title": "ok", "difficulty": 0.5}, {"title": "bad", "difficulty": None}],
                skill=0.5)

    def test_boundary_values_accepted(self):
        out = self.s.structure_work(
            [{"title": "lo", "difficulty": 0.0}, {"title": "hi", "difficulty": 1.0}],
            skill=0.5)
        self.assertEqual(len(out), 2)

    def test_empty_tasks_accepted(self):
        self.assertEqual(self.s.structure_work([], skill=0.5), [])


class TestFlowStructureRouteContract(unittest.TestCase):
    def test_route_maps_valueerror_to_422(self):
        import ast, pathlib
        src = (pathlib.Path(__file__).resolve().parents[2]
               / "backend" / "app" / "modules" / "m20_general_cognitive_worker" / "routes.py").read_text()
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "row17_flow_structure")
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

    def _post(self, tasks, skill=0.5):
        return self._client().post("/api/modules/20/meta/flow/structure",
                                   json={"tasks": tasks, "skill": skill})

    def test_none_difficulty_422_not_500(self):
        self.assertEqual(self._post([{"title": "a", "difficulty": None}]).status_code, 422)

    def test_str_difficulty_422_not_500(self):
        self.assertEqual(self._post([{"title": "a", "difficulty": "hard"}]).status_code, 422)

    def test_bool_difficulty_200(self):
        # bool difficulty stays accepted (previously accepted behavior preserved)
        self.assertEqual(self._post([{"title": "a", "difficulty": True}]).status_code, 200)

    def test_non_dict_task_422(self):
        self.assertEqual(self._post(["x"]).status_code, 422)

    def test_valid_200(self):
        r = self._post([{"title": "a", "difficulty": 0.3}, {"title": "b"}])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["structured"]), 2)


if __name__ == "__main__":
    unittest.main()
