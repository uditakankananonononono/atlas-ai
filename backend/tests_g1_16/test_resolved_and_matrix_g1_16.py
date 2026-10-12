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


def make_pdf(path, pages, font="Times-Roman", headings=("Abstract Introduction Methods Results Discussion References",)):
    """Minimal hand-built PDF: one text line per page, base-14 font."""
    objs = []
    kids = " ".join("%d 0 R" % (4 + 2 * i) for i in range(pages))
    objs.append("<< /Type /Catalog /Pages 2 0 R >>")
    objs.append("<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, pages))
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /%s >>" % font)
    for i in range(pages):
        txt = headings[0] if i == 0 else "page %d" % i
        stream = "BT /F1 12 Tf 72 700 Td (%s) Tj ET" % txt
        objs.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents %d 0 R /Resources << /Font << /F1 3 0 R >> >> >>" % (5 + 2 * i))
        objs.append("<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
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

    def test_paper_wrapper_real_pdf(self):
        if not all(__import__("shutil").which(x) for x in ("pdfinfo", "pdffonts", "pdftotext")):
            self.skipTest("poppler missing")
        make_pdf(os.path.join(self.d, "ok.pdf"), 50)
        make_pdf(os.path.join(self.d, "short.pdf"), 10)
        make_pdf(os.path.join(self.d, "helv.pdf"), 50, font="Helvetica")
        make_pdf(os.path.join(self.d, "nosec.pdf"), 50, headings=("Intro only",))
        e = {"id": "a", "project_id": "p", "path": "ok.pdf"}
        reg = rr.append_paper(rr.papers.create_register(), e, self.d)
        row = reg.entries[0]
        self.assertEqual(row[3], 50); self.assertEqual(row[5], "pass")
        for f in ("short.pdf", "helv.pdf", "nosec.pdf", "missing.pdf"):
            with self.assertRaises(ValueError, msg=f):
                rr.append_paper(rr.papers.create_register(), dict(e, path=f), self.d)
        with self.assertRaises(ValueError):
            rr.append_paper(rr.papers.create_register(), None, self.d)

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

    def test_matrix_columns_checked_from_evidence(self):
        out = b"ok\n"
        ds = w(self.d, "d.csv", b"1")
        jt = w(self.d, "j.txt", b"JUDGE_SCORE round=1 value=1\nJUDGE_SCORE round=2 value=3\n")
        fake = lambda argv: subprocess.CompletedProcess(argv, 0, out, b"")
        ev = {"alpha": {"datasets": [{"path": "d.csv", "sha256": ds, "origin": "o"}],
                        "judge_rounds": [{"transcript_path": "j.txt", "transcript_sha256": jt}],
                        "benchmarks": [{"argv": ["x"], "stdout_sha256": sh(out)}],
                        "discovery_claim": "yes"}}
        a = mx.build_matrix(self.d, ev, fake)["rows"][0]
        self.assertEqual(a["columns"]["data_run"], "VERIFIED")
        self.assertEqual(a["columns"]["improvement"], "VERIFIED")
        self.assertEqual(a["columns"]["benchmark_vs_leader"], "VERIFIED")
        self.assertEqual(a["columns"]["discovery"], "CLAIMED_NOT_CHECKABLE")
        self.assertEqual(a["verdict"], "PARTIAL")  # discovery is never checkable by code

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


if __name__ == "__main__":
    unittest.main()
