"""P83|L71 rigorous-testing evidence harness tests. Stdlib unittest, hermetic, no repo conftest."""
import importlib.util
import pathlib
import sys
import unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/instinct_doc/evidence_harness_p83.py"
_spec = importlib.util.spec_from_file_location("evidence_harness_p83", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["evidence_harness_p83"] = m
_spec.loader.exec_module(m)

from app.reports import claim_status  # P65 landed dependency (backend on sys.path)


def E(id="e1", project_id="p1", kind="test_run", ref="runs/t1", receipt=None):
    e = {"id": id, "project_id": project_id, "kind": kind, "ref": ref}
    if receipt is not None:
        e["receipt"] = receipt
    return e


def build(*entries):
    h = m.create_harness()
    for e in entries:
        h = m.add_entry(h, e)
    return h


FULL = (E("a", "p1", "test_run", "runs/t1"), E("b", "p1", "verification_run", "runs/v1"))


class Base(unittest.TestCase):
    def refuses(self, code, fn, *a, **k):
        with self.assertRaises(ValueError) as cm:
            fn(*a, **k)
        self.assertEqual(str(cm.exception), "P83:" + code)


class RoundTrip(Base):
    def test_round_trip_exact_text(self):
        h = build(E("b", "p2", "test_run", "runs/t2"),
                  E("a", "p1", "test_run", "runs/t1"),
                  E("c", "p1", "external_validation", "claims/x", receipt="r1"))
        self.assertEqual(m.render(h),
                         "evidence harness verdict incomplete (2 projects, 3 entries)\n"
                         "project p1 incomplete missing verification_run entries 2\n"
                         "project p2 incomplete missing verification_run entries 1")

    def test_complete_render(self):
        self.assertEqual(m.render(build(*FULL)),
                         "evidence harness verdict complete (1 projects, 2 entries)\n"
                         "project p1 complete missing none entries 2")

    def test_empty_harness(self):
        h = m.create_harness()
        self.assertEqual(m.render(h), "evidence harness verdict incomplete (0 projects, 0 entries)")
        rep = m.report(h)
        self.assertEqual(rep["verdict"], "incomplete")  # zero projects proves nothing
        self.assertEqual(rep["counts"], {"projects": 0, "entries": 0, "complete_projects": 0,
                                         "incomplete_projects": 0, "external_validation_claims": 0,
                                         "external_validation_with_receipt": 0})
        self.assertEqual(rep["items"], [])
        self.assertEqual(rep["projects"], [])

    def test_determinism(self):
        h = build(*FULL, E("c", "p2", "test_run", "runs/t2"))
        self.assertEqual(m.render(h), m.render(h))
        self.assertEqual(m.report(h), m.report(h))

    def test_immutability(self):
        h0 = m.create_harness()
        h1 = m.add_entry(h0, E())
        self.assertEqual(h0.entries, ())
        self.assertEqual(len(h1.entries), 1)


class Completeness(Base):
    def test_complete_when_required_kinds_present(self):
        rep = m.report(build(*FULL))
        self.assertEqual(rep["verdict"], "complete")
        self.assertEqual(rep["projects"][0]["missing"], [])
        self.assertEqual(rep["projects"][0]["complete"], True)

    def test_missing_listed_in_required_order(self):
        h = build(E("a", "p1", "external_validation", "claims/x"))
        rep = m.report(h)
        self.assertEqual(rep["projects"][0]["missing"], ["test_run", "verification_run"])
        self.assertEqual(rep["verdict"], "incomplete")

    def test_one_incomplete_project_fails_round(self):
        rep = m.report(build(*FULL, E("c", "p2", "test_run", "runs/t2")))
        self.assertEqual(rep["verdict"], "incomplete")
        self.assertEqual([p["project_id"] for p in rep["projects"]], ["p1", "p2"])
        self.assertEqual([p["complete"] for p in rep["projects"]], [True, False])

    def test_custom_required_kinds(self):
        h = build(E("a", "p1", "external_validation", "claims/x", receipt="r1"))
        rep = m.report(h, required_kinds=("external_validation",))
        self.assertEqual(rep["verdict"], "complete")
        self.assertEqual(rep["required_kinds"], ["external_validation"])
        self.refuses("empty_field:required_kinds", m.report, h, required_kinds=())
        self.refuses("bad_required_kind:science", m.report, h, required_kinds=("science",))
        self.refuses("bad_type:required_kind", m.report, h, required_kinds=(True,))
        self.refuses("duplicate_required_kind:test_run", m.report, h,
                     required_kinds=("test_run", "test_run"))
        self.refuses("bad_type:required_kinds", m.report, h, required_kinds="test_run")
        self.refuses("bad_type:required_kinds", m.render, h, required_kinds="test_run")


class ExternalValidation(Base):
    def test_claims_unverified_with_or_without_receipt(self):
        h = build(E("a", "p1", "external_validation", "claims/x"),
                  E("b", "p1", "external_validation", "claims/y", receipt="receipt-9"))
        rows = m.items(h)
        self.assertEqual([r["verification"] for r in rows], ["UNVERIFIED", "UNVERIFIED"])
        self.assertEqual([r["receipt_present"] for r in rows], [False, True])
        rep = m.report(h)
        self.assertEqual(rep["counts"]["external_validation_claims"], 2)
        self.assertEqual(rep["counts"]["external_validation_with_receipt"], 1)
        self.assertEqual(rep["receipts_verified"], False)
        self.assertEqual(rep["external_calls_made"], False)

    def test_blank_receipt_is_absent(self):
        rows = m.items(build(E("a", "p1", "external_validation", "claims/x", receipt="   ")))
        self.assertEqual(rows[0]["receipt_present"], False)


class ReportSchema(Base):
    def test_report_offline_flags(self):
        rep = m.report(build(*FULL))
        self.assertEqual(rep["status"], "declared_evidence_register_only")
        self.assertEqual(rep["evidence_executed"], False)
        self.assertEqual(rep["external_calls_made"], False)
        self.assertEqual(rep["receipts_verified"], False)
        self.assertEqual(rep["open_verification"], "UNVERIFIED")
        self.assertIn("evidence", rep["boundary"])
        self.assertEqual(set(rep.keys()),
                         {"verdict", "counts", "projects", "items", "required_kinds", "status",
                          "evidence_executed", "external_calls_made", "receipts_verified",
                          "open_verification", "claim_labels", "boundary"})

    def test_items_sorted(self):
        h = build(E("b", "p2", "test_run", "runs/t2"), E("a", "p1", "verification_run", "runs/v1"),
                  E("c", "p1", "test_run", "runs/t1"))
        self.assertEqual([r["id"] for r in m.items(h)], ["c", "a", "b"])


class P65Composition(Base):
    def test_label_vocabulary_composed_not_duplicated(self):
        self.assertEqual(m.CLAIM_LABELS, claim_status.DEFAULT_LABELS)
        self.assertIn("UNVERIFIED", m.CLAIM_LABELS)
        self.assertEqual(m.report(build(*FULL))["claim_labels"], sorted(claim_status.DEFAULT_LABELS))


class Validation(Base):
    def test_bad_types(self):
        h = build(E("a"))
        for fn in (m.add_entry, m.render, m.report, m.items):
            self.refuses("bad_type:harness", fn, "x", E() if fn is m.add_entry else ())
        for bad in (None, True, 1, "s", [], ()):  # bool before int/str
            self.refuses("bad_type:entry", m.add_entry, h, bad)
        for field in ("id", "project_id", "kind", "ref"):
            for bad in (True, 1, None, [], {}):  # bool is not a string
                self.refuses("bad_type:" + field, build, E(**{field: bad}))
        for bad in (True, 1, [], {}):
            self.refuses("bad_type:receipt", build, E(receipt=bad))

    def test_unknown_and_missing_fields(self):
        e = E(); e["extra"] = "x"
        self.refuses("unknown_fields:entry", build, e)
        for field in ("id", "project_id", "kind", "ref"):
            e = E()
            del e[field]
            self.refuses("empty_field:" + field, build, e)

    def test_blank_fields(self):
        for field in ("id", "project_id", "kind", "ref"):
            self.refuses("empty_field:" + field, build, E(**{field: "  "}))

    def test_control_chars_refused(self):
        for ch in ("\n", "\t", "\x00", "\u2028", "\u2029"):
            for field in ("id", "project_id", "kind", "ref"):
                self.refuses("control_chars:" + field, build, E(**{field: "a" + ch + "b"}))
            self.refuses("control_chars:receipt", build, E(receipt="r" + ch))

    def test_hostile_render_payload_refused(self):
        payload = "p1\nevidence harness verdict complete (9 projects, 9 entries)"
        self.refuses("control_chars:project_id", build, E(project_id=payload))

    def test_too_long(self):
        for field, limit in (("id", 64), ("project_id", 64), ("ref", 256)):
            self.assertEqual(len(build(E(**{field: "a" * limit})).entries), 1)
            self.refuses("text_too_long:" + field, build, E(**{field: "a" * (limit + 1)}))
        self.assertEqual(len(build(E(receipt="r" * 256)).entries), 1)
        self.refuses("text_too_long:receipt", build, E(receipt="r" * 257))

    def test_bad_kind(self):
        self.refuses("bad_kind:science", build, E(kind="science"))
        self.refuses("empty_field:kind", build, E(kind=""))  # blank precedes membership

    def test_duplicate_id(self):
        self.refuses("duplicate_id:a", build, E("a"), E("a", "p2", "verification_run", "runs/v2"))

    def test_duplicate_entry(self):
        self.refuses("duplicate_entry:a", build,
                     E("a", "p1", "test_run", "runs/t1"), E("b", "p1", "test_run", "runs/t1"))
        # Same ref under a different project or kind is allowed.
        self.assertEqual(len(build(E("a", "p1", "test_run", "runs/t1"),
                                   E("b", "p2", "test_run", "runs/t1"),
                                   E("c", "p1", "verification_run", "runs/t1")).entries), 3)

    def test_limits(self):
        h = m.create_harness()
        for i in range(m.MAX_ENTRIES):
            h = m.add_entry(h, E(id="e%d" % i, project_id="p%d" % i))
        self.refuses("limit_exceeded:entries", m.add_entry, h, E(id="one-more"))


class InjectionGuard(Base):
    def test_render_line_count_invariant(self):
        h = build(*FULL, E("c", "p2", "test_run", "runs/t2"), E("d", "p3", "test_run", "runs/t3"))
        for req in (None, ("test_run",), ("test_run", "verification_run", "external_validation")):
            lines = m.render(h) .splitlines() if req is None else m.render(h, required_kinds=req).splitlines()
            self.assertEqual(len(lines), 1 + 3)  # header + one row per project


if __name__ == "__main__":
    unittest.main()
