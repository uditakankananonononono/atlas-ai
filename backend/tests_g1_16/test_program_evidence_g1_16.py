import hashlib, os, subprocess, sys, tempfile, unittest, importlib.util
spec = importlib.util.spec_from_file_location("pe", os.path.join(os.path.dirname(__file__), "..", "app", "modules", "instinct_doc", "program_evidence_g1_16.py"))
pe = importlib.util.module_from_spec(spec); sys.modules["pe"] = pe; spec.loader.exec_module(pe)


def w(base, name, data):
    p = os.path.join(base, name); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)
    return hashlib.sha256(data).hexdigest()


def sh(b):
    return hashlib.sha256(b).hexdigest()


def git_repo(path):
    os.makedirs(path, exist_ok=True)
    subprocess.run(["git", "init", "-q", path]); w(path, "a", b"x")
    subprocess.run(["git", "-C", path, "add", "."])
    subprocess.run(["git", "-C", path, "-c", "user.name=a", "-c", "user.email=a@b", "commit", "-qm", "m"])


class Cp(subprocess.CompletedProcess):
    pass


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    # repo
    def test_repo_toplevel_ok_and_subdir_of_parent_rejected(self):
        git_repo(os.path.join(self.d, "r"))
        self.assertTrue(pe.check_repo(self.d, {"path": "r"})["ok"])
        os.makedirs(os.path.join(self.d, "r", "sub"))
        r = pe.check_repo(self.d, {"path": "r/sub"})
        self.assertFalse(r["ok"]); self.assertEqual(r["reason"], "not_toplevel")

    def test_repo_nonrepo_and_missing(self):
        os.makedirs(os.path.join(self.d, "plain"))
        self.assertFalse(pe.check_repo(self.d, {"path": "plain"})["ok"])
        self.assertFalse(pe.check_repo(self.d, {"path": "nope"})["ok"])
        self.assertFalse(pe.check_repo(self.d, None)["ok"])

    def test_repo_remote_probe(self):
        git_repo(os.path.join(self.d, "r"))
        head = subprocess.run(["git", "-C", os.path.join(self.d, "r"), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        spec_ = {"path": "r", "remote": "https://example.invalid/r"}
        self.assertTrue(pe.check_repo(self.d, spec_, lambda u: head)["ok"])
        self.assertEqual(pe.check_repo(self.d, spec_, lambda u: "deadbeef")["reason"], "remote_head_mismatch")

    # datasets
    def test_datasets_hash_dedupe_escape_malformed(self):
        h = w(self.d, "d1", b"abc"); w(self.d, "d2", b"abc")
        specs = [{"path": "d1", "sha256": h, "origin": "u"}, {"path": "d2", "sha256": h, "origin": "u"},
                 {"path": "d1", "sha256": "0" * 64, "origin": "u"}, {"path": "../x", "sha256": h, "origin": "u"},
                 None, "str", 7, {"path": 5}, {}]
        r = pe.check_datasets(self.d, specs, 1)
        self.assertEqual(r["counted"], 1); self.assertEqual(len(r["rejected"]), 7)

    # tools: executed, not declared
    def test_tool_never_executed_is_not_counted(self):
        h = w(self.d, "o", b"out")
        decl = {"name": "blast", "argv": ["blast"], "exit_code": 0, "output_path": "o", "output_sha256": h}
        self.assertEqual(pe.check_tools(self.d, [decl]), set())  # no allowlist: nothing runs
        self.assertEqual(pe.check_tools(self.d, [decl], allowlist=[("python3", "-c")]), set())  # not allowlisted prefix

    def test_tool_executes_and_hash_comes_from_run(self):
        out = b"hello\n"
        spec_ = {"name": "Echo", "argv": [sys.executable, "-c", "print('hello')"], "output_sha256": sh(out)}
        al = [(sys.executable, "-c")]
        self.assertEqual(pe.check_tools(self.d, [spec_], allowlist=al), {"echo"})
        self.assertEqual(pe.check_tools(self.d, [dict(spec_, output_sha256="0")], allowlist=al), set())
        bad = dict(spec_, argv=[sys.executable, "-c", "import sys; print('hello'); sys.exit(3)"])
        self.assertEqual(pe.check_tools(self.d, [bad], allowlist=al), set())

    def test_tool_output_file_produced_by_run(self):
        code = "open('o.txt','w').write('x')"
        s_ = {"name": "t", "argv": [sys.executable, "-c", code], "output_path": "o.txt", "output_sha256": sh(b"x")}
        self.assertEqual(pe.check_tools(self.d, [s_], allowlist=[(sys.executable, "-c")]), {"t"})
        pre = w(self.d, "pre.txt", b"x")  # caller-planted file; the run does not write it
        s2 = {"name": "u", "argv": [sys.executable, "-c", "pass"], "output_path": "pre.txt", "output_sha256": pre}
        self.assertEqual(pe.check_tools(self.d, [s2], allowlist=[(sys.executable, "-c")]), set())

    def test_tool_malformed(self):
        self.assertEqual(pe.check_tools(self.d, [None, {}, {"name": 1}, {"name": "a", "argv": "x"}], allowlist=[("x",)]), set())

    # judge: parsed from transcript
    def test_judge_metric_free_transcript_rejected(self):
        h = w(self.d, "j", b"the model said it improved a lot\n")
        self.assertFalse(pe.check_judge(self.d, [{"transcript_path": "j", "transcript_sha256": h, "before": 1, "after": 9}], pe.LENIENT)["ok"])

    def test_judge_improvement_from_transcript(self):
        h = w(self.d, "j", b"JUDGE_SCORE round=1 value=5.5\nnoise\nJUDGE_SCORE round=2 value=7.0\n")
        r = {"transcript_path": "j", "transcript_sha256": h}
        self.assertTrue(pe.check_judge(self.d, [r], pe.LENIENT)["ok"])
        h2 = w(self.d, "k", b"JUDGE_SCORE round=1 value=7\nJUDGE_SCORE round=2 value=7\n")
        self.assertFalse(pe.check_judge(self.d, [{"transcript_path": "k", "transcript_sha256": h2}], pe.LENIENT)["ok"])
        h3 = w(self.d, "m", b"JUDGE_SCORE round=1 value=1\n")
        self.assertFalse(pe.check_judge(self.d, [{"transcript_path": "m", "transcript_sha256": h3}], pe.LENIENT)["ok"])

    def test_judge_duplicates_count_once(self):
        h = w(self.d, "j", b"JUDGE_SCORE round=1 value=1\nJUDGE_SCORE round=2 value=2\n")
        r = {"transcript_path": "j", "transcript_sha256": h}
        t = pe.Thresholds(judge_rounds=2)
        res = pe.check_judge(self.d, [r, dict(r), dict(r)], t)
        self.assertEqual(res["rounds"], 1); self.assertFalse(res["ok"])

    def test_judge_hash_mismatch_and_malformed(self):
        w(self.d, "j", b"JUDGE_SCORE round=1 value=1\nJUDGE_SCORE round=2 value=2\n")
        self.assertEqual(pe.check_judge(self.d, [{"transcript_path": "j", "transcript_sha256": "0"}, None, {}], pe.LENIENT)["rounds"], 0)

    # benchmarks
    def test_benchmark_reproduces_and_dedupes(self):
        out = b"score 1\n"
        fake = lambda argv: subprocess.CompletedProcess(argv, 0, out, b"")
        good = {"argv": ["x"], "stdout_sha256": sh(out)}
        self.assertTrue(pe.check_benchmarks(self.d, [good], pe.LENIENT, fake)["ok"])
        self.assertFalse(pe.check_benchmarks(self.d, [dict(good, stdout_sha256="0")], pe.LENIENT, fake)["ok"])
        t2 = pe.Thresholds(benchmarks_per_project=2)
        self.assertEqual(pe.check_benchmarks(self.d, [good, dict(good), dict(good)], t2, fake)["reproduced"], 1)

    def test_benchmark_default_runner_rejects_non_allowlisted(self):
        s_ = {"argv": ["rm", "-rf", "x"], "stdout_sha256": sh(b"")}
        self.assertEqual(pe.check_benchmarks(self.d, [s_], pe.LENIENT)["reproduced"], 0)
        s2 = {"argv": ["sh", "-c", "echo hi"], "stdout_sha256": sh(b"hi\n")}
        self.assertEqual(pe.check_benchmarks(self.d, [s2], pe.LENIENT)["reproduced"], 0)

    def test_benchmark_unittest_allowlisted_runs_in_base(self):
        w(self.d, "test_a.py", b"import unittest\nclass A(unittest.TestCase):\n    def test(self): self.assertTrue(True)\n")
        r = pe._sandbox_run(self.d, ["python3", "-m", "unittest", "test_a"], pe.BENCH_ALLOWED)
        self.assertEqual(r.returncode, 0)

    # paper
    def test_paper_missing_and_not_pdf(self):
        self.assertFalse(pe.check_paper(self.d, {"path": "nope.pdf"}, pe.LENIENT)["ok"])
        w(self.d, "x.pdf", b"not a pdf")
        self.assertFalse(pe.check_paper(self.d, {"path": "x.pdf"}, pe.LENIENT)["ok"])
        self.assertFalse(pe.check_paper(self.d, None, pe.LENIENT)["ok"])

    # thresholds / program
    def test_strict_vs_lenient(self):
        self.assertEqual(pe.STRICT.tools_per_project, 200); self.assertEqual(pe.LENIENT.tools_per_project, 40)

    def test_non_distinct_program_counts_total(self):
        names = lambda n: [{"name": "t%d" % i, "argv": ["a"], "output_sha256": sh(b"o")} for i in range(n)]
        fake = lambda argv: subprocess.CompletedProcess(argv, 0, b"o", b"")
        projs = [{"id": "a", "tools": names(3)}, {"id": "b", "tools": names(3)}]
        t = pe.Thresholds(tools_program=6, tools_distinct_program=False)
        rep = pe.verify_program(self.d, projs, t, runner=fake)
        self.assertTrue(rep["program_tools_ok"]); self.assertEqual(rep["program_distinct_tools_verified"], 3)
        t2 = pe.Thresholds(tools_program=6, tools_distinct_program=True)
        self.assertFalse(pe.verify_program(self.d, projs, t2, runner=fake)["program_tools_ok"])

    def test_empty_project_unsupported_and_program(self):
        rep = pe.verify_program(self.d, [{"id": "p"}])
        self.assertEqual(rep["projects"][0]["verdict"], "UNSUPPORTED"); self.assertEqual(rep["verdict"], "PARTIAL")
        self.assertEqual(pe.verify_program(self.d, [])["verdict"], "UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
