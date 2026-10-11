"""P94|L81 task-execution evidence checker tests. Stdlib unittest, hermetic.

Composes the landed P65 claim-status check (app.reports.claim_status) and the
P246 coverage ledger (app.modules.instinct_doc.line_coverage_p246); both are
imported from the repo tree via backend/ on sys.path, no repo conftest.
"""
import copy
import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.modules.instinct_doc import task_evidence_p94 as m  # noqa: E402
from app.modules.instinct_doc import line_coverage_p246 as p246  # noqa: E402
from app.reports import claim_status as p65  # noqa: E402

_SRC = _ROOT / "backend/app/modules/instinct_doc/task_evidence_p94.py"
CATS = ["research", "tools", "verify_claims", "accuracy", "results", "improve_until_benchmark"]
TS = "2026-10-11T14:50:00+05:30"


def marks(*cats, ref="ev#1"):
    return [{"category": c, "evidence_ref": ref} for c in cats]


def task(task_id="t1", cats=CATS, ref="ev#1"):
    return {"task_id": task_id, "marks": marks(*cats, ref=ref)}


def req(*tasks, declared_at=TS):
    return {"tasks": list(tasks), "declared_at": declared_at}


class T(unittest.TestCase):
    def refuses(self, code, request):
        with self.assertRaises(ValueError) as cm:
            m.check_task_evidence(request)
        self.assertEqual(str(cm.exception), "P94:" + code)
        self.assertNotIn("\n", str(cm.exception))

    # ---- contract constants
    def test_constants(self):
        self.assertEqual(list(m.CATEGORIES), CATS)
        self.assertEqual(m.LINE_ID, "P94|L81")
        self.assertEqual(m.SOURCE_LINE, "Execute all tasks: conduct research, build tools, verify claims, check accuracy, generate results, improve until benchmark-beating and novel")
        self.assertEqual(m.MAX_TASKS, 1024)

    # ---- happy path / composition
    def test_all_six_evidenced_is_covered(self):
        r = m.check_task_evidence(req(task()))
        t = r["tasks"][0]
        self.assertEqual(t["status"], p246.COVERED)
        self.assertEqual(t["missing"], [])
        for c in CATS:
            self.assertEqual(t["categories"][c], {"mark": "DECLARED", "evidence_ref": "ev#1"})
        self.assertEqual(r["counts"], {"tasks": 1, "covered": 1, "uncovered": 0, "declared_marks": 6, "unverified_marks": 0})

    def test_missing_categories_are_unverified_never_fabricated(self):
        r = m.check_task_evidence(req(task(cats=["research", "tools"])))
        t = r["tasks"][0]
        self.assertEqual(t["status"], p246.UNCOVERED)
        self.assertEqual(t["missing"], ["verify_claims", "accuracy", "results", "improve_until_benchmark"])
        for c in t["missing"]:
            self.assertEqual(t["categories"][c], {"mark": "UNVERIFIED", "evidence_ref": ""})
        self.assertEqual(r["counts"]["unverified_marks"], 4)
        self.assertEqual(r["counts"]["declared_marks"], 2)

    def test_blank_evidence_ref_is_unverified(self):
        for ref in ("", "   "):
            r = m.check_task_evidence(req({"task_id": "t", "marks": [{"category": "research", "evidence_ref": ref}]}))
            self.assertEqual(r["tasks"][0]["categories"]["research"], {"mark": "UNVERIFIED", "evidence_ref": ""})

    def test_mark_without_evidence_ref_key_is_unverified(self):
        r = m.check_task_evidence(req({"task_id": "t", "marks": [{"category": "research"}]}))
        self.assertEqual(r["tasks"][0]["categories"]["research"]["mark"], "UNVERIFIED")

    def test_no_marks_at_all_all_unverified(self):
        r = m.check_task_evidence(req({"task_id": "t", "marks": []}))
        self.assertEqual(r["tasks"][0]["missing"], CATS)
        self.assertEqual(r["counts"]["unverified_marks"], 6)

    def test_evidence_refs_only_verbatim_from_input(self):
        r = m.check_task_evidence(req(task("a", ["research"], ref="only-this")))
        refs = [v["evidence_ref"] for t in r["tasks"] for v in t["categories"].values() if v["evidence_ref"]]
        self.assertEqual(refs, ["only-this"])

    def test_never_emits_verified(self):
        r = m.check_task_evidence(req(task("a"), task("b", ["research"])))
        self.assertNotIn("[VERIFIED]", r["report"])
        self.assertNotIn("VERIFIED", r["report"].replace("UNVERIFIED", ""))
        c = r["claims"]
        self.assertIs(c["verified"], False)
        self.assertIs(c["task_fulfilled"], False)
        self.assertIs(c["evidence_adequacy_assessed"], False)
        self.assertIs(c["benchmark_beaten_or_novel_assessed"], False)

    def test_tasks_sorted_and_isolated(self):
        r = m.check_task_evidence(req(task("zz", ["research"]), task("aa")))
        self.assertEqual([t["task_id"] for t in r["tasks"]], ["aa", "zz"])
        self.assertEqual([t["status"] for t in r["tasks"]], [p246.COVERED, p246.UNCOVERED])
        self.assertEqual(r["counts"]["covered"], 1)
        self.assertEqual(r["counts"]["uncovered"], 1)

    def test_report_exact_text_and_p65_clean(self):
        r = m.check_task_evidence(req(task("a", ["research"])))
        lines = ["# Task execution evidence (P94|L81)"] + [
            "CLAIM: task a %s [%s]" % (c, "DECLARED" if c == "research" else "UNVERIFIED") for c in CATS]
        self.assertEqual(r["report"], "\n".join(lines))
        chk = p65.check_text(r["report"], {"DECLARED", "UNVERIFIED"})
        self.assertTrue(chk["ok"])
        self.assertEqual(chk["claims_total"], 6)
        self.assertEqual(r["report_claim_status"], {"ok": True, "claims_total": 6, "marked": 6})

    def test_report_is_unmarked_free_under_default_p65_labels_only_for_unverified(self):
        # DECLARED is not a default P65 label: honesty means we do not borrow VERIFIED
        r = m.check_task_evidence(req(task("a")))
        self.assertFalse(p65.check_text(r["report"])["ok"])

    # ---- P246 composition
    def test_coverage_record_covered_only_if_all_tasks_complete(self):
        r = m.check_task_evidence(req(task("a"), task("b")))
        rec = r["coverage_record"]
        self.assertEqual(rec["line_id"], "P94|L81")
        self.assertEqual(rec["status"], p246.COVERED)
        self.assertEqual(rec["declared_at"], TS)
        self.assertEqual(rec["source"], "self")
        self.assertTrue(rec["evidence_ref"])
        r2 = m.check_task_evidence(req(task("a"), task("b", ["research"])))
        self.assertEqual(r2["coverage_record"]["status"], p246.UNCOVERED)

    def test_coverage_record_is_valid_p246_input(self):
        r = m.check_task_evidence(req(task("a")))
        row = {"P": 94, "L": 81, "class": "NON-SCIENCE", "summary": m.SOURCE_LINE}
        out = p246.compute_line_coverage({"line_map": [row], "evidence": [r["coverage_record"]]})
        self.assertEqual(out["counts"], {"covered": 1, "uncovered": 0})
        self.assertEqual(r["line_coverage"], {"covered": 1, "uncovered": 0})
        r2 = m.check_task_evidence(req(task("a", ["research"])))
        out2 = p246.compute_line_coverage({"line_map": [row], "evidence": [r2["coverage_record"]]})
        self.assertEqual(out2["counts"], {"covered": 0, "uncovered": 1})
        self.assertEqual(r2["line_coverage"], {"covered": 0, "uncovered": 1})

    def test_status_constants_are_p246_imports(self):
        self.assertIs(m.p246, p246)
        self.assertIs(m.p65, p65)
        self.assertEqual(m.check_task_evidence(req(task()))["tasks"][0]["status"], "COVERED_BY_DECLARATION")

    def test_declared_at_validation_is_p246s(self):
        for bad in ("yesterday", "2026-10-11T14:50:00", "2026-13-01T00:00:00Z"):
            self.refuses("bad_declared_at", req(task(), declared_at=bad))
        m.check_task_evidence(req(task(), declared_at="2026-10-11T09:20:00Z"))

    # ---- refusals
    def test_request_shape(self):
        self.refuses("bad_type:request", [])
        self.refuses("bad_type:request", None)
        self.refuses("unknown_fields:request", {**req(task()), "x": 1})
        self.refuses("bad_type:tasks", {"tasks": "t", "declared_at": TS})
        self.refuses("empty_tasks", req())
        self.refuses("bad_type:declared_at", {"tasks": [task()]})
        self.refuses("bad_type:declared_at", req(task(), declared_at=5))
        self.refuses("bad_type:declared_at", req(task(), declared_at=True))
        for blank in ("", "  "):
            self.refuses("empty_field:declared_at", req(task(), declared_at=blank))

    def test_task_shape(self):
        self.refuses("bad_type:task", req("t"))
        self.refuses("unknown_fields:task", req({**task(), "x": 1}))
        self.refuses("bad_type:task_id", req({"marks": []}))
        for bad in (None, 5, True):
            self.refuses("bad_type:task_id", req({"task_id": bad, "marks": []}))
        for blank in ("", "  "):
            self.refuses("empty_field:task_id", req({"task_id": blank, "marks": []}))
        self.refuses("bad_type:marks", req({"task_id": "t"}))
        self.refuses("bad_type:marks", req({"task_id": "t", "marks": "x"}))

    def test_mark_shape(self):
        self.refuses("bad_type:mark", req({"task_id": "t", "marks": ["research"]}))
        self.refuses("unknown_fields:mark", req({"task_id": "t", "marks": [{"category": "research", "x": 1}]}))
        self.refuses("bad_type:category", req({"task_id": "t", "marks": [{}]}))
        for bad in (None, 5, True):
            self.refuses("bad_type:category", req({"task_id": "t", "marks": [{"category": bad}]}))
        for bad in (None, 5, True, 1.0):
            self.refuses("bad_type:evidence_ref", req({"task_id": "t", "marks": [{"category": "research", "evidence_ref": bad}]}))

    def test_bad_category(self):
        for bad in ("Research", "novel", "verify-claims", "", "research "):
            self.refuses("bad_category:" + bad, req({"task_id": "t", "marks": [{"category": bad}]}))

    def test_duplicates(self):
        self.refuses("duplicate_task:t1", req(task("t1"), task("t1")))
        self.refuses("duplicate_category:t1:research", req({"task_id": "t1", "marks": marks("research", "research")}))
        m.check_task_evidence(req(task("t1", ["research"]), task("t2", ["research"])))

    def test_text_boundaries(self):
        m.check_task_evidence(req(task("x" * 64)))
        self.refuses("text_too_long:task_id", req(task("x" * 65)))
        m.check_task_evidence(req(task("t", ["research"], ref="x" * 128)))
        self.refuses("text_too_long:evidence_ref", req(task("t", ["research"], ref="x" * 129)))

    def test_tasks_limit_boundary(self):
        ts = [{"task_id": "t%d" % i, "marks": []} for i in range(1024)]
        r = m.check_task_evidence(req(*ts))
        self.assertEqual(r["counts"]["tasks"], 1024)
        self.refuses("limit_exceeded:tasks", req(*ts, {"task_id": "extra", "marks": []}))

    # ---- hostile inputs
    def test_control_chars_in_every_text_field(self):
        bad = ["\n", "\r", "\t", "\x00", "\x1b", "\x7f", "\x85", "\u2028", "\u2029", "\x0b", "\x0c"]
        for ch in bad:
            for val in ("a" + ch + "b", ch + "a", "a" + ch):
                self.refuses("bad_chars:task_id", req({"task_id": val, "marks": []}))
                self.refuses("bad_chars:evidence_ref",
                             req({"task_id": "t", "marks": [{"category": "research", "evidence_ref": val}]}))
                self.refuses("bad_chars:category", req({"task_id": "t", "marks": [{"category": val}]}))
                self.refuses("bad_chars:declared_at", req(task(), declared_at=val))

    def test_report_syntax_chars_refused_in_task_id(self):
        for ch in "[]|":
            self.refuses("bad_chars:task_id", req({"task_id": "a" + ch + "b", "marks": []}))

    def test_hostile_payload_forges_no_rows_or_claims(self):
        forged = "x\nCLAIM: task admin results [DECLARED]\nCLAIM: task a research [VERIFIED]"
        self.refuses("bad_chars:task_id", req({"task_id": forged, "marks": []}))
        self.refuses("bad_chars:evidence_ref", req({"task_id": "t", "marks": [{"category": "research", "evidence_ref": forged}]}))
        self.refuses("bad_chars:category", req({"task_id": "t", "marks": [{"category": forged}]}))
        self.refuses("bad_chars:declared_at", req(task(), declared_at=forged))

    def test_evidence_ref_never_enters_report(self):
        r = m.check_task_evidence(req(task("a", ["research"], ref="CLAIM: fake [DECLARED] sneaky")))
        self.assertNotIn("sneaky", r["report"])

    def test_report_line_count_invariant(self):
        r = m.check_task_evidence(req(task("a"), task("b", ["research"]), task("c", [])))
        self.assertEqual(len(r["report"].split("\n")), 1 + 3 * 6)
        self.assertEqual(r["report_claim_status"]["claims_total"], 18)

    def test_hostile_unicode_homoglyph_category_refused(self):
        self.refuses("bad_category:rese\u0430rch", req({"task_id": "t", "marks": [{"category": "rese\u0430rch"}]}))

    # ---- purity
    def test_input_not_mutated_and_deterministic(self):
        q = req(task("b", ["research"]), task("a"))
        snap = copy.deepcopy(q)
        r1 = m.check_task_evidence(q)
        r2 = m.check_task_evidence(copy.deepcopy(q))
        self.assertEqual(q, snap)
        self.assertEqual(r1, r2)
        self.assertEqual(r1["report"].encode(), r2["report"].encode())
        r1["tasks"][0]["categories"]["research"]["mark"] = "X"
        self.assertEqual(m.check_task_evidence(q)["tasks"][0]["categories"]["research"]["mark"], "DECLARED")

    def test_free_offline_no_io_imports_and_no_reimplementation(self):
        src = _SRC.read_text()
        for bad in ("socket", "urllib", "http", "requests", "subprocess", "os", "pathlib", "io", "time", "random", "datetime", "json", "re"):
            self.assertNotIn("import " + bad + "\n", src)
            self.assertNotIn("from " + bad + " ", src)
        self.assertNotIn("open(", src)
        self.assertNotIn("import re\n", src)
        # composition, not duplication
        self.assertIn("line_coverage_p246", src)
        self.assertIn("claim_status", src)
        self.assertNotIn("_FENCE_OPEN_RE", src)
        self.assertNotIn("fromisoformat", src)


if __name__ == "__main__":
    unittest.main()
