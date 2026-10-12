"""Row 75 / c31.adapter_runtime tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, shutil, sys, unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(_ROOT))
_P = _ROOT / "app/modules/c31/adapter_runtime.py"
_spec = importlib.util.spec_from_file_location("c31_adapter_runtime", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c31_adapter_runtime"] = m
_spec.loader.exec_module(m)

CAT = shutil.which("cat")
SLEEP = shutil.which("sleep")


def spec(**kw):
    d = {"name": "cat", "executable": CAT, "caller_marked_reviewed": True, "args": []}
    d.update(kw)
    return d


class AdapterRuntime(unittest.TestCase):
    def test_runs_and_pipes_stdin(self):
        out = m.run(spec(), [CAT], "hello")
        self.assertEqual((out["exit_code"], out["stdout"], out["timed_out"]), (0, "hello", False))

    def test_unreviewed_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.run(spec(caller_marked_reviewed=False), [CAT])
        self.assertIn("NOT_MARKED_REVIEWED", str(cm.exception))

    def test_not_allowlisted_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.run(spec(), [])
        self.assertIn("NOT_ALLOWLISTED", str(cm.exception))

    def test_paid_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.run(spec(paid=True), [CAT])
        self.assertIn("SPEND", str(cm.exception))

    def test_relative_path_refused(self):
        with self.assertRaises(ValueError):
            m.run(spec(executable="cat"), ["cat"])

    def test_timeout(self):
        out = m.run(spec(name="sleep", executable=SLEEP, args=["5"], timeout=0.3), [SLEEP])
        self.assertTrue(out["timed_out"])
        self.assertIsNone(out["exit_code"])

    def test_output_cap_bounds_capture_and_reports_truncation(self):
        PY = shutil.which("python3")
        out = m.run(spec(name="py", executable=PY,
                         args=["-c", "import sys; sys.stdout.write('x' * 500000)"], timeout=20), [PY])
        self.assertEqual(len(out["stdout"]), m.MAX_OUT)
        self.assertTrue(out["truncated"])
        self.assertEqual(out["exit_code"], 0)

    def test_small_output_not_truncated(self):
        self.assertFalse(m.run(spec(), [CAT], "hi")["truncated"])

    def test_no_shell_metachar_expansion(self):
        out = m.run(spec(args=["/nonexistent;echo pwned"]), [CAT])
        self.assertNotIn("pwned", out["stdout"])
        self.assertNotEqual(out["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
