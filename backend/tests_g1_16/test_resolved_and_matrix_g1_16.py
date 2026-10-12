import hashlib, json, os, subprocess, sys, tempfile, unittest, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "..", "app", "modules", "instinct_doc")


def load(name):
    s = importlib.util.spec_from_file_location("t_" + name, os.path.join(MOD, name + ".py"))
    m = importlib.util.module_from_spec(s); sys.modules["t_" + name] = m; s.loader.exec_module(m); return m


rr = load("resolved_registers_g1_16")
mx = load("sugarcode_matrix_g16")
pe = rr.pe


def sh(b):
    return hashlib.sha256(b).hexdigest()


def w(base, name, data):
    p = os.path.join(base, name); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)
    return sh(data)


def make_pdf(path, pages, font="Times-Roman"):
    """Hand-built PDF. pages: list of pages, each a list of text lines (base-14 font)."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join("%d 0 R" % (4 + 2 * i) for i in range(len(pages)))
    objs.append("<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(pages)))
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /%s >>" % font)
    for i, lines in enumerate(pages):
        body = "BT /F1 10 Tf 72 740 Td 12 TL " + " T* ".join("(%s) Tj" % l.replace("(", "").replace(")", "") for l in lines) + " ET"
        objs.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents %d 0 R /Resources << /Font << /F1 3 0 R >> >> >>" % (5 + 2 * i))
        objs.append("<< /Length %d >>\nstream\n%s\nendstream" % (len(body), body))
    out = b"%PDF-1.4\n"; offs = []
    for i, o in enumerate(objs):
        offs.append(len(out)); out += ("%d 0 obj\n%s\nendobj\n" % (i + 1, o)).encode()
    x = len(out)
    out += ("xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)).encode()
    for o in offs:
        out += ("%010d 00000 n \n" % o).encode()
    out += ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)).encode()
    with open(path, "wb") as f:
        f.write(out)


SECTIONS = ("Abstract", "Introduction", "Methods", "Results", "Discussion", "References")
WORDS = "the study recorded sample outcomes under fixed conditions and reported each estimate with its interval".split()


def body_lines(n_lines):
    return [" ".join(WORDS[(i + j) % len(WORDS)] for j in range(12)) for i in range(n_lines)]


def good_pages(total=50, sections=SECTIONS):
    """total pages; each section heading on its own line followed by body text."""
    per = total // len(sections)
    pages = []
    for k in range(total):
        sec = min(k // per, len(sections) - 1)
        lines = ([sections[sec]] if k % per == 0 else []) + body_lines(40)
        pages.append(lines)
    return pages


class R(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_dataset_wrapper(self):
        h = w(self.d, "data/a.csv", b"1,2\n")
        e = {"id": "d1", "project_id": "p", "dataset": "A", "records": 1, "source": "lab", "source_ref": "data/a.csv"}
        reg = rr.add_dataset(rr.datasets.create_register(), e, self.d, h)
        self.assertEqual(len(reg.entries), 1)
        for bad_h in ("0" * 64,):
            with self.assertRaises(ValueError):
                rr.add_dataset(rr.datasets.create_register(), e, self.d, bad_h)
        with self.assertRaises(ValueError):
            rr.add_dataset(rr.datasets.create_register(), dict(e, source_ref="../x"), self.d, h)
        with self.assertRaises(ValueError):
            rr.add_dataset(rr.datasets.create_register(), None, self.d, h)

    def test_integration_active_needs_execution(self):
        e = {"id": "i1", "project_id": "p", "name": "echo", "purpose": "x", "status": "active"}
        run = {"argv": [sys.executable, "-c", "print('hi')"], "output_sha256": sh(b"hi\n")}
        al = [(sys.executable, "-c")]
        reg = rr.append_integration(rr.integrations.create_register(), e, self.d, run, al)
        self.assertEqual(len(reg.entries), 1)
        with self.assertRaises(ValueError):  # never executed: no allowlist
            rr.append_integration(rr.integrations.create_register(), e, self.d, run, [])
        with self.assertRaises(ValueError):  # wrong output hash
            rr.append_integration(rr.integrations.create_register(), e, self.d, dict(run, output_sha256="0"), al)
        planned = dict(e, status="planned")  # a plan makes no run claim
        self.assertEqual(len(rr.append_integration(rr.integrations.create_register(), planned, self.d, None, []).entries), 1)

    def test_paper_wrapper_pdf(self):
        if not all(__import__("shutil").which(x) for x in ("pdfinfo", "pdffonts", "pdftotext")):
            self.skipTest("poppler missing")
        make_pdf(os.path.join(self.d, "ok.pdf"), good_pages())
        e = {"id": "a", "project_id": "p", "path": "ok.pdf"}
        row = rr.append_paper(rr.papers.create_register(), e, self.d).entries[0]
        self.assertEqual(row[3], 50); self.assertEqual(row[5], "pass")

    def test_paper_gate_regressions(self):
        """Every one of these must fail. The first is the synthetic that passed before tightening."""
        if not all(__import__("shutil").which(x) for x in ("pdfinfo", "pdffonts", "pdftotext")):
            self.skipTest("poppler missing")
        sec_page = list(SECTIONS)
        cases = {
            "filler.pdf": [sec_page] + [["page %d" % i] for i in range(1, 50)],
            "buried.pdf": [["we cover the abstract and the introduction and methods and results and discussion and references here"] + body_lines(40)] + [body_lines(40) for _ in range(49)],
            "short.pdf": good_pages(12),
            "blank_tail.pdf": good_pages(30) + [[] for _ in range(20)],
            "thin.pdf": [[s_] + body_lines(1) for s_ in SECTIONS] + [body_lines(40) for _ in range(44)],
            "order.pdf": good_pages(50, tuple(reversed(SECTIONS))),
            "nodisc.pdf": good_pages(50, SECTIONS[:4] + ("Appendix", "References")),
        }
        for name, pg in cases.items():
            make_pdf(os.path.join(self.d, name), pg)
        make_pdf(os.path.join(self.d, "helv.pdf"), good_pages(), font="Helvetica")
        names = list(cases) + ["helv.pdf", "missing.pdf"]
        e = {"id": "a", "project_id": "p", "path": "x"}
        for f in names:
            self.assertFalse(pe.check_paper(self.d, {"path": f}, pe.LENIENT)["ok"], f)
            with self.assertRaises(ValueError, msg=f):
                rr.append_paper(rr.papers.create_register(), dict(e, path=f), self.d)
        with self.assertRaises(ValueError):
            rr.append_paper(rr.papers.create_register(), None, self.d)
        ok = pe.check_paper(self.d, {"path": "ok.pdf"}, pe.LENIENT) if os.path.exists(os.path.join(self.d, "ok.pdf")) else None
        self.assertIsNone(ok)

    def test_resolved_counts_empty(self):
        self.assertEqual(rr.resolved_counts([], self.d)["program_verdict"], "UNSUPPORTED")


class M(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        idx = [{"_note": "n"}, {"name": "A", "slug": "alpha"}, {"name": "B", "slug": "beta"}, {"slug": "../evil"}, {"name": "x"}]
        w(self.d, "spec/index.json", json.dumps(idx).encode())
        w(self.d, "spec/alpha.md", b"spec")
        w(self.d, "src/sugarcode/modules/alpha/core.py", b"x=1\n")
        w(self.d, "tests/test_alpha_core.py", b"")

    def test_matrix_structure_only_is_partial_never_verified(self):
        m = mx.build_matrix(self.d)
        self.assertEqual(m["modules"], 2)  # evil slug dropped
        by = {r["slug"]: r for r in m["rows"]}
        self.assertEqual(by["alpha"]["verdict"], "PARTIAL")
        self.assertEqual(by["beta"]["verdict"], "UNSUPPORTED")
        self.assertTrue(all(v == "UNVERIFIED" for v in by["alpha"]["columns"].values()))
        self.assertEqual(m["counts"], {"VERIFIED": 0, "PARTIAL": 1, "UNSUPPORTED": 1})

    def test_matrix_columns_need_executed_runs(self):
        ds = w(self.d, "tests/data/a.csv", b"1")
        w(self.d, "tests/test_alpha_core.py", b"open('tests/data/a.csv')\n")
        def run(argv):
            out = {"mod": b"2 passed\n", "judge": b"JUDGE_SCORE round=1 value=1\nJUDGE_SCORE round=2 value=3\n",
                   "bench": b"BENCH leader=L metric=m subject=2 leader_value=1\n"}[argv[0]]
            return subprocess.CompletedProcess(argv, 0, out, b"")
        ev = {"alpha": {"module_run": {"argv": ["mod"], "stdout_regex": r"\d+ passed",
                                       "datasets": [{"path": "tests/data/a.csv", "sha256": ds, "origin": "o"}],
                                       "referenced_in": ["tests/test_alpha_core.py"]},
                        "judge_rounds": [{"argv": ["judge"]}],
                        "leader_benchmarks": [{"argv": ["bench"], "leader": "L", "metric": "m", "higher_is_better": True}],
                        "discovery_claim": "yes"}}
        a = mx.build_matrix(self.d, ev, run)["rows"][0]
        self.assertEqual(a["columns"]["data_run"], "VERIFIED")
        self.assertEqual(a["columns"]["improvement"], "VERIFIED")
        self.assertEqual(a["columns"]["benchmark_vs_leader"], "VERIFIED")
        self.assertEqual(a["columns"]["discovery"], "CLAIMED_NOT_CHECKABLE")
        self.assertEqual(a["verdict"], "PARTIAL")  # discovery is never checkable by code

    def test_matrix_hashed_file_or_stdout_alone_is_not_enough(self):
        ds = w(self.d, "tests/data/a.csv", b"1")
        ev = {"alpha": {"module_run": {"argv": ["pytest"], "stdout_regex": "x", "datasets": [{"path": "tests/data/a.csv", "sha256": ds, "origin": "o"}], "referenced_in": []},
                        "judge_rounds": [{"transcript_path": "j", "transcript_sha256": "0"}],
                        "benchmarks": [{"argv": ["x"], "stdout_sha256": "0"}]}}
        a = mx.build_matrix(self.d, ev)["rows"][0]
        self.assertTrue(all(v == "UNVERIFIED" for v in a["columns"].values()))

    def test_matrix_bad_evidence_ignored(self):
        for ev in (None, [], {"alpha": None}, {"alpha": {"datasets": [None]}}):
            self.assertEqual(mx.build_matrix(self.d, ev)["rows"][0]["verdict"], "PARTIAL")

    def test_matrix_on_pinned_sugarcode_if_present(self):
        root = os.environ.get("SUGARCODE_ROOT")
        if not root:
            self.skipTest("set SUGARCODE_ROOT")
        m = mx.build_matrix(root)
        self.assertEqual(m["modules"], 77)
        self.assertEqual(m["counts"]["VERIFIED"], 0)



gen = load("sugarcode_evidence_gen_g16")


class G(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        w(self.d, "spec/index.json", json.dumps([{"slug": "alpha"}, {"slug": "beta"}]).encode())
        w(self.d, "tests/data/a.csv", b"1,2\n")
        w(self.d, "tests/data/b.csv", b"3\n")
        w(self.d, "tests/test_alpha_x.py", b"open('tests/data/a.csv'); open('tests/data/b.csv')\n")
        w(self.d, "tests/test_beta_x.py", b"open('tests/data/b.csv')\n")
        w(self.d, "PROVENANCE.md", b"- tests/data/a.csv: copied from a public archive\n")

    def test_only_provenance_listed_fixtures_named_in_tests(self):
        g = gen.generate(self.d)
        self.assertEqual(sorted(g["evidence"]), ["alpha"])
        ds = g["evidence"]["alpha"]["module_run"]["datasets"]
        self.assertEqual([d["path"] for d in ds], ["tests/data/a.csv"])  # b.csv is not in PROVENANCE.md
        self.assertEqual(g["skipped"]["beta"], "no_provenance_listed_fixture_named_in_tests")

    def test_no_provenance_file_means_no_entries(self):
        os.remove(os.path.join(self.d, "PROVENANCE.md"))
        self.assertEqual(gen.generate(self.d)["evidence"], {})

    def test_generated_entry_is_not_vouched_for(self):
        g = gen.generate(self.d)
        fail = lambda argv: subprocess.CompletedProcess(argv, 1, b"1 failed\n", b"")
        a = mx.build_matrix(self.d, g["evidence"], fail)["rows"]
        self.assertTrue(all(r["columns"]["data_run"] == "UNVERIFIED" for r in a))
        ok = lambda argv: subprocess.CompletedProcess(argv, 0, b"2 passed in 0.1s\n", b"")
        self.assertEqual({r["slug"]: r["columns"]["data_run"] for r in mx.build_matrix(self.d, g["evidence"], ok)["rows"]}["alpha"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()
