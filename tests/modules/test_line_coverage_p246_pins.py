"""P246|L194 line coverage: test-only pins for boundaries the first suite left open.

Offline, standard library only. Loads the module through the package when available,
otherwise straight from its file path (the namespace directory has no __init__.py).
"""
import importlib
import importlib.util
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_NAME = "app.modules.instinct_doc.line_coverage_p246"
_PATH = _ROOT / "backend/app/modules/instinct_doc/line_coverage_p246.py"


def _load():
    try:
        return importlib.import_module(_NAME)
    except ModuleNotFoundError as exc:
        if exc.name == _NAME:
            raise
    spec = importlib.util.spec_from_file_location("line_coverage_p246_pins_target", _PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_m = _load()
compute = _m.compute_line_coverage
LineCoverageError = _m.LineCoverageError
AT = "2026-10-11T12:00:00+05:30"


def row(p, l, cls="NON-SCIENCE", dup="", summary="s", mission="m"):
    return {"P": p, "L": l, "class": cls, "mission": mission, "summary": summary, "dup_of": dup}


def ev(line_id, status="COVERED_BY_DECLARATION", ref="docs/x.md", source="audit", at=AT):
    return {"line_id": line_id, "status": status, "evidence_ref": ref, "declared_at": at, "source": source}


def run(evidence, line_map=None, **kw):
    req = {"line_map": [row(1, 1)] if line_map is None else line_map, "evidence": evidence}
    req.update(kw)
    return compute(req)


def refusal(evidence, line_map=None):
    with_ = None
    try:
        run(evidence, line_map)
    except LineCoverageError as exc:
        with_ = str(exc)
    return with_


TIME_MSG = "evidence 0 declared_at must be an ISO-8601 timestamp with timezone"


class DeclaredAtPins(unittest.TestCase):
    # group 1: non-string and empty declared_at are refused with the exact error
    def test_integer_declared_at_is_refused_with_the_exact_error(self):
        for bad in (123, 0, 1.5, True, ["2026-10-11T12:00:00+05:30"], {"a": 1}, None):
            self.assertEqual(refusal([ev("P1|L1", at=bad)]), TIME_MSG, repr(bad))

    def test_empty_declared_at_is_refused_with_the_exact_error(self):
        self.assertEqual(refusal([ev("P1|L1", at="")]), TIME_MSG)

    def test_missing_declared_at_is_refused(self):
        e = ev("P1|L1")
        del e["declared_at"]
        self.assertEqual(refusal([e]), TIME_MSG)

    # group 2: a Z suffix is accepted and the slice keeps every other character
    def test_z_suffix_is_accepted_and_echoed_unchanged(self):
        for at in ("2026-01-01T00:00:00Z", "2026-10-11T12:00:00Z"):
            res = run([ev("P1|L1", at=at)])
            self.assertEqual(res["counts"], {"covered": 1, "uncovered": 0})
            self.assertEqual(res["covered"][0]["evidence"][0]["declared_at"], at)

    def test_offset_forms_are_accepted_and_naive_or_malformed_are_refused(self):
        for at in ("2026-10-11T12:00:00+05:30", "2026-10-11T12:00:00-07:00", "2026-10-11T12:00:00+00:00"):
            self.assertEqual(run([ev("P1|L1", at=at)])["counts"]["covered"], 1, at)
        for at in ("2026-10-11T12:00:00", "2026-10-11", "Z", "2026-01-01T00:00:0Z",
                   "not a time", "2026-13-01T00:00:00Z"):
            self.assertEqual(refusal([ev("P1|L1", at=at)]), TIME_MSG, at)


class MissionPins(unittest.TestCase):
    # group 3: mission type and length
    def _msg(self, mission):
        try:
            compute({"line_map": [row(1, 1, mission=mission)], "evidence": []})
        except LineCoverageError as exc:
            return str(exc)
        return None

    def test_non_string_mission_is_refused_with_the_exact_error(self):
        want = "line_map row 0 mission must be a string up to 2000 chars"
        for bad in (["m"], 5, 1.5, {"a": 1}, True, None):
            self.assertEqual(self._msg(bad), want, repr(bad))

    def test_mission_length_2000_accepted_2001_refused(self):
        self.assertIsNone(self._msg("x" * 2000))
        self.assertEqual(self._msg("x" * 2001), "line_map row 0 mission must be a string up to 2000 chars")
        self.assertIsNone(self._msg(""))

    def test_absent_mission_is_allowed(self):
        r = row(1, 1)
        del r["mission"]
        self.assertEqual(compute({"line_map": [r], "evidence": []})["denominator"]["distinct_requirements"], 1)


class EvidenceRefPins(unittest.TestCase):
    # group 4: evidence_ref length
    def test_ref_2048_accepted_2049_refused(self):
        ok = run([ev("P1|L1", ref="r" * 2048)])
        self.assertEqual(ok["counts"]["covered"], 1)
        self.assertEqual(len(ok["covered"][0]["evidence"][0]["evidence_ref"]), 2048)
        msg = refusal([ev("P1|L1", ref="r" * 2049)])
        self.assertEqual(msg, "evidence 0 evidence_ref must be a non-empty string up to 2048 chars when COVERED_BY_DECLARATION")

    def test_ref_length_bound_applies_to_uncovered_declarations_too(self):
        self.assertEqual(run([ev("P1|L1", status="UNCOVERED", ref="r" * 2048)])["declared_uncovered"], ["P1|L1"])
        self.assertIsNotNone(refusal([ev("P1|L1", status="UNCOVERED", ref="r" * 2049)]))

    def test_non_string_ref_is_refused_and_empty_ref_only_for_covered(self):
        for bad in (5, None, ["x"]):
            self.assertIsNotNone(refusal([ev("P1|L1", ref=bad)]), repr(bad))
        self.assertIsNotNone(refusal([ev("P1|L1", ref="")]))
        self.assertEqual(run([ev("P1|L1", status="UNCOVERED", ref="")])["counts"], {"covered": 0, "uncovered": 1})


class ExactOutputListPins(unittest.TestCase):
    # group 5: exact lists with an out-of-scope class present
    MAP = [row(1, 1), row(1, 2), row(1, 3, cls="SCIENCE"), row(1, 4, cls="SCIENCE")]

    def test_exact_lists_for_uncovered_covered_and_out_of_scope_coverage(self):
        res = run([ev("P1|L1", status="UNCOVERED"), ev("P1|L2"), ev("P1|L4")], self.MAP)
        self.assertEqual(res["conflicting_declarations"], [])
        self.assertEqual(res["declared_uncovered"], ["P1|L1"])
        self.assertEqual([c["line_id"] for c in res["covered"]], ["P1|L2"])
        self.assertEqual([u["line_id"] for u in res["uncovered"]], ["P1|L1"])
        self.assertEqual([c["line_id"] for c in res["other_class_covered"]], ["P1|L4"])
        self.assertEqual(res["other_class_requirements"], {"SCIENCE": ["P1|L3", "P1|L4"]})
        self.assertEqual(res["counts"], {"covered": 1, "uncovered": 1})
        self.assertEqual(res["denominator"], {"classes": ["NON-SCIENCE"], "distinct_requirements": 2})
        self.assertEqual((res["self_declared_only"], res["unknown_line_evidence"], res["evidence_rolled_up"],
                          res["evidence_on_non_requirement_rows"], res["cross_class_duplicates"]), ([], [], [], [], []))

    def test_out_of_scope_uncovered_or_conflicting_declarations_never_enter_in_scope_lists(self):
        ev_ = [ev("P1|L3", status="UNCOVERED"), ev("P1|L4"), ev("P1|L4", status="UNCOVERED")]
        res = run(ev_, self.MAP)
        self.assertEqual(res["declared_uncovered"], [])
        self.assertEqual(res["conflicting_declarations"], [])
        self.assertEqual([u["line_id"] for u in res["uncovered"]], ["P1|L1", "P1|L2"])
        self.assertEqual(res["other_class_covered"], [])
        self.assertEqual(res["counts"], {"covered": 0, "uncovered": 2})

    def test_in_scope_conflict_is_listed_once_and_only_for_that_line(self):
        res = run([ev("P1|L1"), ev("P1|L1", status="UNCOVERED"), ev("P1|L2"), ev("P1|L4")], self.MAP)
        self.assertEqual(res["conflicting_declarations"], ["P1|L1"])
        self.assertEqual(res["declared_uncovered"], ["P1|L1"])
        self.assertEqual([c["line_id"] for c in res["covered"]], ["P1|L2"])
        self.assertEqual([c["line_id"] for c in res["other_class_covered"]], ["P1|L4"])

    def test_including_science_moves_it_in_scope_and_empties_other_class_lists(self):
        res = run([ev("P1|L1", status="UNCOVERED"), ev("P1|L2"), ev("P1|L4")], self.MAP,
                  include_classes=["NON-SCIENCE", "SCIENCE"])
        self.assertEqual([c["line_id"] for c in res["covered"]], ["P1|L2", "P1|L4"])
        self.assertEqual([u["line_id"] for u in res["uncovered"]], ["P1|L1", "P1|L3"])
        self.assertEqual((res["other_class_covered"], res["other_class_requirements"]), ([], {}))


if __name__ == "__main__":
    unittest.main()
