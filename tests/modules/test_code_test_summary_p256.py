"""P256|L203 code/test summary tests. Stdlib unittest, hermetic, no repo conftest."""
import importlib.util
import pathlib
import sys
import unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/instinct_doc/code_test_summary_p256.py"
_spec = importlib.util.spec_from_file_location("code_test_summary_p256", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["code_test_summary_p256"] = m
_spec.loader.exec_module(m)


def P(id="a", coverage_percent=None, source_refs=(), **counts):
    base = dict(code_files=2, code_lines=80, test_files=1, test_lines=30, test_cases=5)
    base.update(counts)
    return dict(id=id, coverage_percent=coverage_percent,
                source_refs=list(source_refs) if isinstance(source_refs,(list,tuple)) else source_refs, **base)


class Base(unittest.TestCase):
    def refuses(self, code, value):
        with self.assertRaises(ValueError) as cm:
            m.summarize_projects(value)
        self.assertEqual(str(cm.exception), "P256:" + code)


class CanonicalForm(Base):
    def test_sort_totals_and_order_independence(self):
        rows = [P("z", test_cases=7), P("a", code_lines=10), P("m", 90.0, ["r2", "r1"])]
        r = m.summarize_projects(rows)
        self.assertEqual([p["id"] for p in r["projects"]], ["a", "m", "z"])
        self.assertEqual(r, m.summarize_projects(list(reversed(rows))))
        self.assertEqual(r["totals"], dict(code_files=6, code_lines=170,
                                           test_files=3, test_lines=90, test_cases=17))
        self.assertEqual(r["projects"][1]["coverage"]["source_refs"], ["r1", "r2"])

    def test_exact_full_shape(self):
        r = m.summarize_projects([P("only")])
        self.assertEqual(set(r), {"projects", "totals", "coverage_counts",
                                  "unverified_coverage_project_ids", "status",
                                  "stats_measured", "coverage_measured",
                                  "evidence_verified", "completeness_verified",
                                  "boundary"})
        row = r["projects"][0]
        self.assertEqual(set(row), {"id", "code_files", "code_lines", "test_files",
                                    "test_lines", "test_cases", "coverage",
                                    "stats_are_caller_supplied"})
        self.assertEqual(set(row["coverage"]),
                         {"percent", "status", "source_refs", "caller_declared"})

    def test_input_never_mutated(self):
        row = P("a", 50, ["z", "a"])
        snapshot = dict(row, source_refs=list(row["source_refs"]))
        m.summarize_projects([row])
        self.assertEqual(row, snapshot)


class HonestyShape(Base):
    def test_coverage_marking_three_way(self):
        r = m.summarize_projects([P("no-claim"), P("bare", 80),
                                  P("evidenced", 91.5, ["cov.xml"])])
        cov = {p["id"]: p["coverage"] for p in r["projects"]}
        self.assertEqual(cov["no-claim"]["status"], "NO_CLAIM")
        self.assertIsNone(cov["no-claim"]["percent"])
        self.assertEqual(cov["bare"]["status"], "UNVERIFIED")
        self.assertEqual(cov["evidenced"]["status"], "EVIDENCE_DECLARED")
        self.assertEqual(r["coverage_counts"],
                         {"NO_CLAIM": 1, "UNVERIFIED": 1, "EVIDENCE_DECLARED": 1})
        self.assertEqual(r["unverified_coverage_project_ids"], ["bare"])
        for c in cov.values():
            self.assertIs(c["caller_declared"], True)

    def test_unverified_mandatory_without_refs(self):
        r = m.summarize_projects([P(str(i), 100) for i in range(3)])
        self.assertEqual(r["unverified_coverage_project_ids"], ["0", "1", "2"])
        self.assertEqual(r["coverage_counts"]["UNVERIFIED"], 3)

    def test_refs_never_verify(self):
        r = m.summarize_projects([P("a", 100, ["proof"])])
        self.assertIs(r["evidence_verified"], False)
        self.assertIs(r["coverage_measured"], False)
        self.assertIs(r["stats_measured"], False)
        self.assertIs(r["completeness_verified"], False)
        self.assertEqual(r["status"], "supplied_stats_summary_only")
        self.assertIs(r["projects"][0]["stats_are_caller_supplied"], True)

    def test_empty_is_valid_not_completeness(self):
        r = m.summarize_projects([])
        self.assertEqual(r["projects"], [])
        self.assertEqual(r["totals"], dict(code_files=0, code_lines=0, test_files=0,
                                           test_lines=0, test_cases=0))
        self.assertEqual(r["coverage_counts"],
                         {"NO_CLAIM": 0, "UNVERIFIED": 0, "EVIDENCE_DECLARED": 0})
        self.assertIs(r["completeness_verified"], False)

    def test_boundary_verbatim(self):
        self.assertEqual(m.summarize_projects([])["boundary"],
                         "Only supplied stats are summarized. Nothing is measured: no "
                         "code is read, no tests are run and no coverage is computed. "
                         "Coverage claims are caller declarations marked UNVERIFIED "
                         "without supplied source refs; refs are recorded, never "
                         "authenticated, and never verify a claim. An empty summary "
                         "does not prove the absence of projects.")


class Bounds(Base):
    def test_project_count_n_nplus1(self):
        m.summarize_projects([P(str(i)) for i in range(256)])
        self.refuses("projects: expected list of at most 256 records",
                     [P(str(i)) for i in range(257)])

    def test_id_length_n_nplus1(self):
        m.summarize_projects([P("x" * 128)])
        self.refuses("id: expected nonblank string of length 1..128", [P("x" * 129)])

    def test_count_limit_n_nplus1_and_negative(self):
        m.summarize_projects([P("a", code_lines=10000000)])
        self.refuses("code_lines: expected integer 0..10000000",
                     [P("a", code_lines=10000001)])
        self.refuses("code_lines: expected integer 0..10000000",
                     [P("a", code_lines=-1)])

    def test_percent_edges(self):
        m.summarize_projects([P("lo", 0), P("hi", 100)])
        for bad in (-0.5, 100.0001):
            self.refuses("coverage_percent: expected null or number 0..100",
                         [P("a", bad)])

    def test_refs_count_and_length_n_nplus1(self):
        m.summarize_projects([P("a", source_refs=[str(i) for i in range(16)])])
        self.refuses("source_refs: expected list of at most 16 references",
                     [P("a", source_refs=[str(i) for i in range(17)])])
        m.summarize_projects([P("a", source_refs=["x" * 256])])
        self.refuses("source_ref: expected nonblank string of length 1..256",
                     [P("a", source_refs=["x" * 257])])


class Refusals(Base):
    def test_non_list_and_non_dict(self):
        for bad in (None, {}, "x", True, ()):
            self.refuses("projects: expected list of at most 256 records", bad)
        self.refuses("project: exactly id,code_files,code_lines,test_files,"
                     "test_lines,test_cases,coverage_percent,source_refs required",
                     [None])
        self.refuses("project: exactly id,code_files,code_lines,test_files,"
                     "test_lines,test_cases,coverage_percent,source_refs required",
                     [dict(P("a"), extra=1)])
        missing = P("a")
        del missing["test_cases"]
        self.refuses("project: exactly id,code_files,code_lines,test_files,"
                     "test_lines,test_cases,coverage_percent,source_refs required",
                     [missing])

    def test_duplicate_id_exact(self):
        self.refuses("duplicate project id: same", [P("same"), P("same")])
        self.refuses("duplicate source_ref: r", [P("a", source_refs=["r", "r"])])

    def test_strict_types(self):
        for name in ("code_files", "code_lines", "test_files", "test_lines", "test_cases"):
            for bad in (True, 1.5, "3", None):
                self.refuses(f"{name}: expected integer 0..10000000", [P("a", **{name: bad})])
        for bad in (True, "80", float("nan"), float("inf"), -float("inf")):
            self.refuses("coverage_percent: expected null or number 0..100", [P("a", bad)])
        for bad in (None, "r", {}):
            self.refuses("source_refs: expected list of at most 16 references",
                         [P("a", source_refs=bad)])
        for bad in ("", "   ", None, 1, True):
            self.refuses("id: expected nonblank string of length 1..128",
                         [P(bad)] if isinstance(bad, str) else [dict(P("a"), id=bad)])

    def test_blank_and_typed_refs(self):
        self.refuses("source_ref: expected nonblank string of length 1..256",
                     [P("a", source_refs=["  "])])
        self.refuses("source_ref: expected nonblank string of length 1..256",
                     [P("a", source_refs=[7])])


if __name__ == "__main__":
    unittest.main()
