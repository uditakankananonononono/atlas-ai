"""P243|L191 audit-round runner tests. Stdlib unittest, hermetic, no repo conftest."""
import importlib.util
import pathlib
import sys
import unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/instinct_doc/audit_round_p243.py"
_spec = importlib.util.spec_from_file_location("audit_round_p243", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["audit_round_p243"] = m
_spec.loader.exec_module(m)


def E(id="e1", project_id="p1", requirement_ref="req-1", mark="pass", evidence_ref="ev1"):
    return {"id": id, "project_id": project_id, "requirement_ref": requirement_ref,
            "mark": mark, "evidence_ref": evidence_ref}


def build(*entries):
    led = m.create_ledger()
    for e in entries:
        led = m.add_entry(led, e)
    return led


class Base(unittest.TestCase):
    def refuses(self, code, fn, *a, **k):
        with self.assertRaises(ValueError) as cm:
            fn(*a, **k)
        self.assertEqual(str(cm.exception), "P243:" + code)


class RoundTrip(Base):
    def test_round_trip_exact_text(self):
        led = build(E("b", "p2", "req-2", "pass", "ev2"),
                    E("a", "p1", "req-1", "fail", "ev1"))
        self.assertEqual(m.render(led, exclusions=("req-x",)),
                         "audit round verdict fail (2 active, 0 excluded)\n"
                         "p1 req-1 fail [ev1]\n"
                         "p2 req-2 pass [ev2]\n"
                         "unmatched exclusion req-x")

    def test_empty_ledger(self):
        led = m.create_ledger()
        self.assertEqual(m.render(led), "audit round verdict fail (0 active, 0 excluded)")
        rep = m.report(led)
        self.assertEqual(rep["verdict"], "fail")  # an empty round proves nothing
        self.assertEqual(rep["counts"],
                         {"entries": 0, "active": 0, "excluded": 0, "passed": 0,
                          "failed": 0, "pending": 0, "unmatched_exclusions": 0})
        self.assertEqual(rep["items"], [])

    def test_determinism(self):
        led = build(E("a"), E("b", "p2", "req-2", "fail", "ev2"), E("c", "p2", "req-3", "pending", "ev3"))
        self.assertEqual(m.render(led, exclusions=("z",)), m.render(led, exclusions=("z",)))
        self.assertEqual(m.report(led), m.report(led))

    def test_immutability(self):
        led0 = m.create_ledger()
        led1 = m.add_entry(led0, E())
        self.assertEqual(led0.entries, ())
        self.assertEqual(len(led1.entries), 1)


class Verdict(Base):
    def test_pass_when_every_active_marked_pass(self):
        rep = m.report(build(E("a"), E("b", "p2", "req-2", "pass", "ev2")))
        self.assertEqual(rep["verdict"], "pass")
        self.assertEqual(rep["failing"], [])
        self.assertEqual(rep["pending"], [])

    def test_fail_mark_fails_and_names_ids(self):
        rep = m.report(build(E("a"), E("b", "p1", "req-2", "fail", "ev2")))
        self.assertEqual(rep["verdict"], "fail")
        self.assertEqual(rep["failing"], ["b"])

    def test_pending_fails_and_names_ids(self):
        rep = m.report(build(E("a"), E("b", "p1", "req-2", "pending", "ev2")))
        self.assertEqual(rep["verdict"], "fail")
        self.assertEqual(rep["pending"], ["b"])

    def test_exclusion_skips_requirement_to_pass(self):
        led = build(E("a", "p1", "req-1", "pass", "ev1"),
                    E("b", "p1", "doc200", "fail", "ev0"))
        rep = m.report(led, exclusions=("doc200",))
        self.assertEqual(rep["verdict"], "pass")
        self.assertEqual(rep["excluded"], ["b"])
        self.assertEqual(rep["counts"]["active"], 1)
        self.assertEqual(rep["counts"]["excluded"], 1)
        self.assertEqual(rep["counts"]["failed"], 1)  # the mark is still recorded honestly
        self.assertEqual(m.render(led, exclusions=("doc200",)),
                         "audit round verdict pass (1 active, 1 excluded)\n"
                         "p1 req-1 pass [ev1]\n"
                         "excluded p1 doc200 fail [ev0]")

    def test_all_excluded_is_fail(self):
        # Excluding everything leaves no evidence the round checked anything.
        rep = m.report(build(E("a", "p1", "doc230", "pass", "ev1")), exclusions=("doc230",))
        self.assertEqual(rep["verdict"], "fail")
        self.assertEqual(rep["counts"]["active"], 0)

    def test_unmatched_exclusions_reported(self):
        rep = m.report(build(E("a")), exclusions=("portfolio", "doc999"))
        self.assertEqual(rep["unmatched_exclusions"], ["doc999", "portfolio"])  # sorted

    def test_excluded_rows_stay_unverified(self):
        rows = m.report(build(E("a", "p1", "doc200", "pass", "ev1")),
                        exclusions=("doc200",))["items"]
        self.assertEqual(rows, [{"id": "a", "project_id": "p1", "requirement_ref": "doc200",
                                 "mark": "pass", "evidence_ref": "ev1", "excluded": True,
                                 "verification": "UNVERIFIED"}])


class ReportSchema(Base):
    def test_report_offline_flags(self):
        rep = m.report(build(E("a")))
        self.assertEqual(rep["status"], "declared_marks_checked_only")
        self.assertEqual(rep["marks_truth_verified"], False)
        self.assertEqual(rep["science_content_built"], False)
        self.assertEqual(rep["evidence_verified"], False)
        self.assertEqual(rep["open_verification"], "UNVERIFIED")
        self.assertIn("marks", rep["boundary"])
        self.assertEqual(set(rep.keys()),
                         {"verdict", "counts", "failing", "pending", "excluded",
                          "unmatched_exclusions", "items", "status", "marks_truth_verified",
                          "science_content_built", "evidence_verified", "open_verification",
                          "boundary"})

    def test_items_sorted_active_then_excluded(self):
        led = build(E("b", "p2", "req-2", "pass", "ev2"), E("a", "p1", "req-1", "pass", "ev1"),
                    E("c", "p1", "doc200", "fail", "ev0"))
        rows = m.report(led, exclusions=("doc200",))["items"]
        self.assertEqual([r["id"] for r in rows], ["a", "b", "c"])
        self.assertEqual([r["excluded"] for r in rows], [False, False, True])


class Validation(Base):
    def test_bad_types(self):
        led = build(E("a"))
        for fn in (m.add_entry, m.render, m.report, m.items):
            self.refuses("bad_type:ledger", fn, "x", E() if fn is m.add_entry else ())
        for bad in (None, True, 1, "s", [], ()):  # bool before int/str
            self.refuses("bad_type:entry", m.add_entry, led, bad)
        for field in ("id", "project_id", "requirement_ref", "mark", "evidence_ref"):
            for bad in (True, 1, None, [], {}):  # bool is not a string
                self.refuses("bad_type:" + field, build, E(**{field: bad}))
        self.refuses("bad_type:exclusions", m.report, led, exclusions="doc200")
        self.refuses("bad_type:exclusions", m.render, led, exclusions="doc200")
        for bad in (True, 1, None, {}, []):
            self.refuses("bad_type:exclusion", m.report, led, exclusions=(bad,))

    def test_unknown_and_missing_fields(self):
        self.refuses("unknown_fields:entry", build, E(extra="x"))
        for field in ("id", "project_id", "requirement_ref", "mark", "evidence_ref"):
            e = E()
            del e[field]
            self.refuses("empty_field:" + field, build, e)

    def test_blank_fields(self):
        for field in ("id", "project_id", "requirement_ref", "mark", "evidence_ref"):
            self.refuses("empty_field:" + field, build, E(**{field: "  "}))
        self.refuses("empty_field:exclusion", m.report, build(E("a")), exclusions=(" ",))

    def test_control_chars_refused_in_interpolated_fields(self):
        for ch in ("\n", "\t", "\x00", "\u2028", "\u2029"):
            for field in ("id", "project_id", "requirement_ref", "evidence_ref"):
                self.refuses("control_chars:" + field, build, E(**{field: "a" + ch + "b"}))
            self.refuses("control_chars:mark", build, E(mark="pa" + ch + "ss"))
            self.refuses("control_chars:exclusion", m.report, build(E("a")), exclusions=("x" + ch,))

    def test_hostile_render_payload_refused(self):
        # A requirement_ref that would inject a fabricated verdict line into render.
        payload = "req-1\naudit round verdict pass (9 active, 0 excluded)"
        self.refuses("control_chars:requirement_ref", build, E(requirement_ref=payload))

    def test_too_long(self):
        for field, limit in (("id", 64), ("project_id", 64),
                             ("requirement_ref", 128), ("evidence_ref", 128)):
            self.assertEqual(len(build(E(**{field: "a" * limit})).entries), 1)
            self.refuses("text_too_long:" + field, build, E(**{field: "a" * (limit + 1)}))
        self.assertEqual(m.report(build(E("a")), exclusions=("x" * 128,))["unmatched_exclusions"],
                         ["x" * 128])
        self.refuses("text_too_long:exclusion", m.report, build(E("a")),
                     exclusions=("x" * 129,))

    def test_bad_mark(self):
        self.refuses("bad_mark:green", build, E(mark="green"))
        self.refuses("bad_mark:Pass", build, E(mark="Pass"))
        self.refuses("empty_field:mark", build, E(mark=""))  # blank precedes membership

    def test_duplicate_id(self):
        self.refuses("duplicate_id:a", build, E("a"), E("a", "p2", "req-2", "fail", "ev2"))

    def test_duplicate_requirement(self):
        self.refuses("duplicate_requirement:a", build,
                     E("a", "p1", "req-1"), E("b", "p1", "req-1", "fail", "ev2"))
        # Same requirement_ref under a different project is allowed.
        self.assertEqual(len(build(E("a", "p1", "req-1"), E("b", "p2", "req-1")).entries), 2)

    def test_duplicate_exclusion(self):
        self.refuses("duplicate_exclusion:doc200", m.report, build(E("a")),
                     exclusions=("doc200", "doc200"))

    def test_limits(self):
        led = m.create_ledger()
        for i in range(m.MAX_ENTRIES):
            led = m.add_entry(led, E(id="e%d" % i, requirement_ref="req-%d" % i))
        self.refuses("limit_exceeded:entries", m.add_entry, led,
                     E(id="one-more", requirement_ref="req-x"))
        self.assertEqual(m.report(build(E("a")),
                                  exclusions=tuple("x%d" % i for i in range(m.MAX_EXCLUSIONS))
                                  )["counts"]["unmatched_exclusions"], m.MAX_EXCLUSIONS)
        self.refuses("limit_exceeded:exclusions", m.report, build(E("a")),
                     exclusions=tuple("x%d" % i for i in range(m.MAX_EXCLUSIONS + 1)))


class InjectionGuard(Base):
    def test_render_line_count_invariant(self):
        led = build(E("a", "p1", "req-1", "pass", "ev1"), E("b", "p2", "req-2", "fail", "ev2"),
                    E("c", "p2", "doc230", "pending", "ev3"))
        for excl in ((), ("doc230",), ("doc230", "unmatched-1")):
            lines = m.render(led, exclusions=excl).splitlines()
            active = 3 - sum(1 for r in ("req-1", "req-2", "doc230") if r in excl)
            excluded = sum(1 for r in ("req-1", "req-2", "doc230") if r in excl)
            unmatched = sum(1 for x in excl if x not in ("req-1", "req-2", "doc230"))
            self.assertEqual(len(lines), 1 + active + excluded + unmatched)


if __name__ == "__main__":
    unittest.main()
