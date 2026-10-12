import hashlib, os, subprocess, tempfile, unittest, importlib.util
spec = importlib.util.spec_from_file_location("pe", os.path.join(os.path.dirname(__file__), "..", "app", "modules", "instinct_doc", "program_evidence_g1_16.py"))
import sys
pe = importlib.util.module_from_spec(spec); sys.modules["pe"] = pe; spec.loader.exec_module(pe)

def w(base, name, data):
    p = os.path.join(base, name); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "wb").write(data); return hashlib.sha256(data).hexdigest()

class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
    def test_repo(self):
        r = os.path.join(self.d, "r"); os.makedirs(r)
        self.assertFalse(pe.check_repo(self.d, {"path": "r"})["ok"])
        subprocess.run(["git", "init", "-q", r]); w(r, "a", b"x")
        subprocess.run(["git", "-C", r, "add", "."]); subprocess.run(["git", "-C", r, "-c", "user.name=a", "-c", "user.email=a@b", "commit", "-qm", "m"])
        self.assertTrue(pe.check_repo(self.d, {"path": "r"})["ok"])
    def test_datasets_hash_dedupe_escape(self):
        h = w(self.d, "d1", b"abc")
        w(self.d, "d2", b"abc")
        specs = [{"path": "d1", "sha256": h, "origin": "u"}, {"path": "d2", "sha256": h, "origin": "u"},
                 {"path": "d1", "sha256": "0" * 64, "origin": "u"}, {"path": "../x", "sha256": h, "origin": "u"}]
        r = pe.check_datasets(self.d, specs, 1)
        self.assertEqual(r["verified"], 1); self.assertEqual(len(r["rejected"]), 2)
    def test_tools_need_receipt(self):
        h = w(self.d, "o", b"out")
        ok = {"name": "BLAST", "command": "blast", "exit_code": 0, "output_path": "o", "output_sha256": h}
        self.assertEqual(pe.check_tools(self.d, [ok, dict(ok, name="blast"), dict(ok, name="x", exit_code=1),
                                                  dict(ok, name="y", output_sha256="0")]), {"blast"})
    def test_strict_vs_lenient(self):
        self.assertEqual(pe.STRICT.tools_per_project, 200); self.assertEqual(pe.LENIENT.tools_per_project, 40)
    def test_benchmark_reproduces(self):
        out = b"score 1\n"
        fake = lambda argv: subprocess.CompletedProcess(argv, 0, out, b"")
        good = {"argv": ["x"], "stdout_sha256": hashlib.sha256(out).hexdigest()}
        self.assertTrue(pe.check_benchmarks(self.d, [good], pe.LENIENT, fake)["ok"])
        self.assertFalse(pe.check_benchmarks(self.d, [dict(good, stdout_sha256="0")], pe.LENIENT, fake)["ok"])
    def test_judge_requires_improvement(self):
        h = w(self.d, "j", b"t")
        r = {"transcript_path": "j", "transcript_sha256": h, "before": 1, "after": 2}
        self.assertTrue(pe.check_judge(self.d, [r], pe.LENIENT)["ok"])
        self.assertFalse(pe.check_judge(self.d, [dict(r, after=1)], pe.LENIENT)["ok"])
    def test_empty_project_unsupported_and_program(self):
        rep = pe.verify_program(self.d, [{"id": "p"}])
        self.assertEqual(rep["projects"][0]["verdict"], "UNSUPPORTED"); self.assertEqual(rep["verdict"], "PARTIAL")
        self.assertEqual(pe.verify_program(self.d, [])["verdict"], "UNSUPPORTED")
    def test_paper_missing(self):
        self.assertFalse(pe.check_paper(self.d, {"path": "nope.pdf"}, pe.LENIENT)["ok"])
if __name__ == "__main__":
    unittest.main()
