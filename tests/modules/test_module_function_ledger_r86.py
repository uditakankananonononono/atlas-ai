"""Row 86 ledger tests. Hermetic: builds a temp git repo."""
import importlib.util, pathlib, subprocess, sys, tempfile, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/instinct_doc/module_function_ledger_r86.py"
_spec = importlib.util.spec_from_file_location("ledger_r86", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["ledger_r86"] = m
_spec.loader.exec_module(m)


def sh(d, *a):
    subprocess.run(["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t"] + list(a),
                   check=True, capture_output=True)


class Ledger(unittest.TestCase):
    def test_counts_added_public_only(self):
        with tempfile.TemporaryDirectory() as d:
            sh(d, "init", "-q")
            import os
            os.makedirs(d + "/mods/a"); os.makedirs(d + "/mods/b")
            open(d + "/mods/a/x.py", "w").write("def old():\n    pass\n")
            open(d + "/mods/b/y.py", "w").write("def keep():\n    pass\n")
            sh(d, "add", "-A"); sh(d, "commit", "-qm", "base")
            open(d + "/mods/a/x.py", "w").write(
                "def old():\n    pass\n" + "".join("def f%d():\n    pass\n" % i for i in range(3))
                + "def _private():\n    pass\nclass C:\n    def meth(self):\n        pass\n")
            open(d + "/mods/b/bad.py", "w").write("def (:\n")
            sh(d, "add", "-A"); sh(d, "commit", "-qm", "head")
            out = m.build(d, "HEAD~1", "HEAD", "mods", target=4)
            rows = {r["module"]: r for r in out["rows"]}
            self.assertEqual(rows["a"]["added_public_functions"], 4)  # f0-f2 + C.meth
            self.assertEqual(rows["a"]["verdict"], "AT_OR_ABOVE_TARGET")
            self.assertEqual(rows["b"]["added_public_functions"], 0)
            self.assertEqual(rows["b"]["shortfall"], 4)
            self.assertFalse(out["complete"])
            self.assertEqual(out["unparsed_files"], ["mods/b/bad.py"])

    def test_complete_requires_known_coverage(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            sh(d, "init", "-q")
            os.makedirs(d + "/mods/a")
            open(d + "/mods/a/x.py", "w").write("def old():\n    pass\n")
            sh(d, "add", "-A"); sh(d, "commit", "-qm", "base")
            open(d + "/mods/a/x.py", "w").write("def old():\n    pass\ndef n1():\n    pass\n")
            open(d + "/mods/a/bad.py", "w").write("def (:\n")
            sh(d, "add", "-A"); sh(d, "commit", "-qm", "head")
            out = m.build(d, "HEAD~1", "HEAD", "mods", target=1)
            self.assertEqual(out["below_target"], 0)
            self.assertFalse(out["coverage_known"])
            self.assertFalse(out["complete"])  # unparsed file means unknown coverage
        out = m.build(".", "HEAD", "HEAD", "no_such_dir", target=1)
        self.assertFalse(out["complete"])  # zero modules is not complete

    def test_bad_target_refused(self):
        with self.assertRaises(ValueError):
            m.build(".", "HEAD", "HEAD", "x", target=True)


if __name__ == "__main__":
    unittest.main()
