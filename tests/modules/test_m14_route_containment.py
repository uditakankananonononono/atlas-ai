"""M14 route-error containment pins (stdlib only, no third-party imports).

Runs anywhere via `python -m unittest` or pytest without installing Atlas deps:
it compiles the touched modules and inspects their AST. Runtime HTTP behaviour
is NOT exercised here; these tests pin the structural contract of the patch.
"""
import ast
import py_compile
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "backend" / "app" / "modules" / "m14_project_builder"


def _tree(name):
    return ast.parse((MODULE / name).read_text(), filename=name)


def _route_def(tree, fn_name):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == fn_name:
            return node
    raise AssertionError(f"route function {fn_name} not found")


def _handlers(fn):
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Try):
            for h in node.handlers:
                out.append(ast.unparse(h.type) if h.type is not None else "*")
    return out


def _handler_status_pairs(fn):
    pairs = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Try):
            for h in node.handlers:
                name = ast.unparse(h.type) if h.type is not None else "*"
                status = None
                for stmt in h.body:
                    for sub in ast.walk(stmt):
                        if isinstance(sub, ast.Call) and "HTTPException" in ast.unparse(sub.func):
                            if sub.args and isinstance(sub.args[0], ast.Constant):
                                status = sub.args[0].value
                pairs.append((name, status))
    return pairs


class CompileTest(unittest.TestCase):
    def test_all_touched_modules_compile(self):
        for name in ("routes.py", "service.py", "errors.py", "sql_repository.py"):
            py_compile.compile(str(MODULE / name), cfile=tempfile.mktemp(), doraise=True)


class RouteMappingTest(unittest.TestCase):
    def test_propose_maps_revision_conflict_409(self):
        pairs = _handler_status_pairs(_route_def(_tree("routes.py"), "propose"))
        self.assertIn(("ProjectRevisionConflict", 409), pairs)

    def test_scope_maps_revision_conflict_409(self):
        pairs = _handler_status_pairs(_route_def(_tree("routes.py"), "scope"))
        self.assertIn(("ProjectRevisionConflict", 409), pairs)

    def test_register_artifact_maps_artifact_conflict_409(self):
        pairs = _handler_status_pairs(_route_def(_tree("routes.py"), "register_artifact"))
        self.assertIn(("ArtifactIdConflict", 409), pairs)

    def test_feedback_maps_provider_faults(self):
        pairs = _handler_status_pairs(_route_def(_tree("routes.py"), "feedback"))
        self.assertIn(("PlannerUnavailable", 503), pairs)
        self.assertIn(("ProviderOutcomeUnknown", 409), pairs)

    def test_feedback_planner_output_invalid_precedes_value_error(self):
        handlers = _handlers(_route_def(_tree("routes.py"), "feedback"))
        self.assertIn("PlannerOutputInvalid", handlers)
        self.assertIn("ValueError", handlers)
        self.assertLess(handlers.index("PlannerOutputInvalid"), handlers.index("ValueError"))

    def test_plan_route_mapping_unchanged(self):
        pairs = _handler_status_pairs(_route_def(_tree("routes.py"), "plan"))
        for expected in (("PlannerUnavailable", 503), ("ProviderOutcomeUnknown", 409),
                         ("PlannerOutputInvalid", 502), ("ProjectRevisionConflict", 409)):
            self.assertIn(expected, pairs)


class FeedbackServiceWrapTest(unittest.TestCase):
    def test_apply_feedback_wraps_generate(self):
        tree = _tree("service.py")
        service = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Service")
        fn = next(n for n in service.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "apply_feedback")
        wraps = []
        for node in ast.walk(fn):
            if isinstance(node, ast.Try):
                src = [ast.unparse(h.type) if h.type is not None else "*" for h in node.handlers]
                if "_generate(" in ast.unparse(node):
                    wraps.append(src)
        self.assertTrue(any("ProviderOutcomeUnknown" in w and "ProviderError" in w for w in wraps),
                        f"no try around _generate with both provider handlers: {wraps}")

    def test_planner_plan_still_catches_decode_faults(self):
        tree = _tree("service.py")
        service = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Service")
        fn = next(n for n in service.body if isinstance(n, ast.FunctionDef) and n.name == "_planner_plan")
        text = ast.unparse(fn)
        self.assertIn("ValueError", text)
        self.assertIn("RecursionError", text)


class ErrorsModuleTest(unittest.TestCase):
    def test_typed_errors_semantics(self):
        ns = {}
        exec((MODULE / "errors.py").read_text(), ns)
        poi = ns["PlannerOutputInvalid"]
        self.assertTrue(issubclass(poi, ValueError))
        self.assertEqual(str(poi()), "planner output invalid")
        self.assertTrue(issubclass(ns["ProjectRevisionConflict"], RuntimeError))
        self.assertTrue(issubclass(ns["ArtifactIdConflict"], RuntimeError))


if __name__ == "__main__":
    unittest.main(verbosity=2)
