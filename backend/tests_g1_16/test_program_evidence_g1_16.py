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

    # tools: executed here, identity-based
    AL = [(sys.executable, "-c")]

    def test_tool_never_executed_is_not_counted(self):
        h = sh(b"out")
        decl = {"name": "blast", "argv": ["blast"], "output_sha256": h}
        self.assertEqual(pe.check_tools(self.d, [decl]), set())  # no allowlist: nothing runs
        self.assertEqual(pe.check_tools(self.d, [decl], allowlist=self.AL), set())  # prefix not allowlisted

    def test_refused_command_never_touches_caller_files(self):
        keep = os.path.join(self.d, "keep.txt"); w(self.d, "keep.txt", b"precious")
        spec_ = {"name": "t", "argv": ["rm", "keep.txt"], "output_name": "keep.txt", "output_path": "keep.txt", "output_sha256": sh(b"precious")}
        self.assertEqual(pe.check_tools(self.d, [spec_], allowlist=self.AL), set())
        self.assertTrue(os.path.isfile(keep))
        ok_run = dict(spec_, argv=[sys.executable, "-c", "pass"])
        self.assertEqual(pe.check_tools(self.d, [ok_run], allowlist=self.AL), set())  # run did not write it into SC_OUTPUT_DIR
        self.assertTrue(os.path.isfile(keep))

    def test_tool_executes_and_hash_comes_from_run(self):
        out = b"hello\n"
        spec_ = {"name": "Echo", "argv": [sys.executable, "-c", "print('hello')"], "output_sha256": sh(out)}
        self.assertEqual(len(pe.check_tools(self.d, [spec_], allowlist=self.AL)), 1)
        self.assertEqual(pe.check_tools(self.d, [dict(spec_, output_sha256="0")], allowlist=self.AL), set())
        bad = dict(spec_, argv=[sys.executable, "-c", "import sys; print('hello'); sys.exit(3)"])
        self.assertEqual(pe.check_tools(self.d, [bad], allowlist=self.AL), set())

    def test_tool_output_file_comes_from_fresh_dir(self):
        code = "import os; open(os.path.join(os.environ['SC_OUTPUT_DIR'],'o.txt'),'w').write('x')"
        s_ = {"name": "t", "argv": [sys.executable, "-c", code], "output_name": "o.txt", "output_sha256": sh(b"x")}
        self.assertEqual(len(pe.check_tools(self.d, [s_], allowlist=self.AL)), 1)
        for bad in ("../o.txt", "a/o.txt", "", ".."):
            self.assertEqual(pe.check_tools(self.d, [dict(s_, output_name=bad)], allowlist=self.AL), set())

    def test_same_tool_under_many_names_counts_once(self):
        base = {"argv": [sys.executable, "-c", "print('o')"], "output_sha256": sh(b"o\n")}
        specs = [dict(base, name="tool%d" % i) for i in range(40)]
        self.assertEqual(len(pe.check_tools(self.d, specs, allowlist=self.AL)), 1)
        proj = {"id": "p", "tools": specs}
        r = pe.verify_project(self.d, proj, pe.LENIENT, tool_allowlist=self.AL)
        self.assertFalse(r["checks"]["tools"]["ok"]); self.assertEqual(r["checks"]["tools"]["counted"], 1)
        self.assertEqual(len(pe.check_tools(self.d, [dict(base, name="a", argv=[sys.executable, "-c", "print('o')", ]), dict(base, name="b", argv=[sys.executable, "-c", "print( 'o' )"])], allowlist=self.AL)), 2)

    def test_tool_malformed(self):
        self.assertEqual(pe.check_tools(self.d, [None, {}, {"name": 1}, {"name": "a", "argv": "x"}], allowlist=[("x",)]), set())

    # judge: attributable output only
    def judge_runner(self, out):
        return lambda argv: subprocess.CompletedProcess(argv, 0, out, b"")

    def test_judge_self_authored_transcript_file_never_passes(self):
        h = w(self.d, "j", b"JUDGE_SCORE round=1 value=1\nJUDGE_SCORE round=2 value=999\n")
        r = pe.check_judge(self.d, [{"transcript_path": "j", "transcript_sha256": h}], pe.LENIENT)
        self.assertFalse(r["ok"]); self.assertEqual(r["unattributed"], 1)

    def test_judge_stream_from_executed_command(self):
        ok = b"JUDGE_SCORE round=1 value=5.5\nnoise\nJUDGE_SCORE round=2 value=7.0\n"
        r = pe.check_judge(self.d, [{"argv": ["j"]}], pe.LENIENT, runner=self.judge_runner(ok))
        self.assertTrue(r["ok"])
        for bad in (b"no metric here\n", b"JUDGE_SCORE round=1 value=7\nJUDGE_SCORE round=2 value=7\n",
                    b"JUDGE_SCORE round=1 value=1\n",
                    b"JUDGE_SCORE round=1 value=1\nJUDGE_SCORE round=2 value=inf\n",
                    b"JUDGE_SCORE round=1 value=nan\nJUDGE_SCORE round=2 value=3\n",
                    b"JUDGE_SCORE round=1 value=1\nJUDGE_SCORE round=1 value=2\nJUDGE_SCORE round=2 value=3\n",
                    b"JUDGE_SCORE round=-1 value=1\nJUDGE_SCORE round=2 value=3\n"):
            self.assertFalse(pe.check_judge(self.d, [{"argv": ["j"]}], pe.LENIENT, runner=self.judge_runner(bad))["ok"], bad)
        failing = lambda argv: subprocess.CompletedProcess(argv, 1, ok, b"")
        self.assertFalse(pe.check_judge(self.d, [{"argv": ["j"]}], pe.LENIENT, runner=failing)["ok"])

    def test_judge_default_runner_uses_allowlist_and_runs_here(self):
        code = "print('JUDGE_SCORE round=1 value=1'); print('JUDGE_SCORE round=2 value=2')"
        item = {"argv": [sys.executable, "-c", code]}
        self.assertFalse(pe.check_judge(self.d, [item], pe.LENIENT)["ok"])  # not on default allowlist
        self.assertTrue(pe.check_judge(self.d, [item], pe.LENIENT, allowlist=[(sys.executable, "-c")])["ok"])

    def test_judge_duplicates_count_once(self):
        out = b"JUDGE_SCORE round=1 value=1\nJUDGE_SCORE round=2 value=2\n"
        t = pe.Thresholds(judge_rounds=2)
        res = pe.check_judge(self.d, [{"argv": ["j"]}] * 3, t, runner=self.judge_runner(out))
        self.assertEqual(res["rounds"], 1); self.assertFalse(res["ok"])

    def test_judge_malformed(self):
        self.assertEqual(pe.check_judge(self.d, [None, {}, {"argv": 5}], pe.LENIENT)["rounds"], 0)

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
        for argv in (["rm", "-rf", "x"], ["sh", "-c", "echo hi"]):
            s_ = {"argv": argv, "stdout_sha256": sh(b"")}
            self.assertEqual(pe.check_benchmarks(self.d, [s_], pe.LENIENT)["reproduced"], 0)

    def test_benchmark_unittest_allowlisted_runs_in_base(self):
        w(self.d, "test_a.py", b"import unittest\nclass A(unittest.TestCase):\n    def test(self): self.assertTrue(True)\n")
        r = pe._sandbox_run(self.d, ["python3", "-m", "unittest", "test_a"], pe.BENCH_ALLOWED)
        self.assertEqual(r.returncode, 0)

    # leader benchmarks: leader, metric, criterion declared; values from the executed run
    def bench(self, line, **kw):
        spec_ = dict({"argv": ["b"], "leader": "L", "metric": "auc", "higher_is_better": True}, **kw)
        run = lambda argv: subprocess.CompletedProcess(argv, 0, line.encode(), b"")
        return pe.check_leader_benchmarks(self.d, [spec_], run)

    def test_leader_benchmark_criterion(self):
        self.assertTrue(self.bench("BENCH leader=L metric=auc subject=0.9 leader_value=0.8")["ok"])
        self.assertFalse(self.bench("BENCH leader=L metric=auc subject=0.7 leader_value=0.8")["ok"])
        self.assertTrue(self.bench("BENCH leader=L metric=err subject=0.1 leader_value=0.2", metric="err", higher_is_better=False)["ok"])
        self.assertFalse(self.bench("BENCH leader=L metric=err subject=0.3 leader_value=0.2", metric="err", higher_is_better=False)["ok"])

    def test_leader_benchmark_rejects_unrecorded_or_inconsistent(self):
        self.assertEqual(self.bench("BENCH leader=OTHER metric=auc subject=9 leader_value=1")["compared"], 0)
        self.assertEqual(self.bench("BENCH leader=L metric=f1 subject=9 leader_value=1")["compared"], 0)
        two = "BENCH leader=L metric=auc subject=9 leader_value=1\nBENCH leader=L metric=auc subject=9 leader_value=1"
        self.assertEqual(self.bench(two)["compared"], 0)
        self.assertFalse(self.bench("BENCH leader=L metric=auc subject=nan leader_value=1")["ok"])
        self.assertFalse(self.bench("BENCH leader=L metric=auc subject=inf leader_value=1")["ok"])
        self.assertFalse(self.bench("score is great")["ok"])
        for kw in ({"leader": ""}, {"metric": ""}, {"higher_is_better": "yes"}):
            self.assertFalse(self.bench("BENCH leader=L metric=auc subject=9 leader_value=1", **kw)["ok"])

    # module run: executed here, dataset hashed, named in test source
    def run_spec(self, **kw):
        h = w(self.d, "tests/data/a.csv", b"1,2\n")
        w(self.d, "tests/test_m.py", b"open('tests/data/a.csv')\n")
        return dict({"argv": ["pytest", "-q"], "stdout_regex": r"\d+ passed",
                     "datasets": [{"path": "tests/data/a.csv", "sha256": h, "origin": "lab"}],
                     "referenced_in": ["tests/test_m.py"]}, **kw)

    def test_module_run_requires_execution_hash_reference_and_stdout(self):
        ok = lambda argv: subprocess.CompletedProcess(argv, 0, b"3 passed in 0.1s\n", b"")
        self.assertTrue(pe.check_module_run(self.d, self.run_spec(), ok)["ok"])
        r = self.run_spec()
        bad_runs = [lambda a: subprocess.CompletedProcess(a, 1, b"3 passed\n", b""),
                    lambda a: subprocess.CompletedProcess(a, 0, b"", b""),
                    lambda a: subprocess.CompletedProcess(a, 0, b"nothing\n", b"")]
        for run in bad_runs:
            self.assertFalse(pe.check_module_run(self.d, r, run)["ok"])
        self.assertFalse(pe.check_module_run(self.d, dict(r, datasets=[dict(r["datasets"][0], sha256="0")]), ok)["ok"])
        self.assertFalse(pe.check_module_run(self.d, dict(r, datasets=[dict(r["datasets"][0], origin="")]), ok)["ok"])
        w(self.d, "tests/test_other.py", b"print('no file named here')\n")
        self.assertEqual(pe.check_module_run(self.d, dict(r, referenced_in=["tests/test_other.py"]), ok)["reason"], "not_referenced")
        self.assertFalse(pe.check_module_run(self.d, dict(r, datasets=[]), ok)["ok"])
        self.assertFalse(pe.check_module_run(self.d, None, ok)["ok"])
        self.assertFalse(pe.check_module_run(self.d, dict(r, stdout_regex="("), ok)["ok"])

    def test_module_run_default_runner_needs_allowlisted_command(self):
        r = self.run_spec(argv=["sh", "-c", "echo 1 passed"])
        self.assertEqual(pe.check_module_run(self.d, r)["reason"], "run_failed")

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
        names = lambda n: [{"name": "t%d" % i, "argv": ["a%d" % i], "output_sha256": sh(b"o")} for i in range(n)]
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
