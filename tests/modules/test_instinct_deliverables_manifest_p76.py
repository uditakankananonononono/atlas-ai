"""P76|L64 deliverables manifest validator tests. Stdlib unittest, hermetic."""
import importlib.util
import pathlib
import sys
import unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/instinct_doc/deliverables_manifest_p76.py"
_spec = importlib.util.spec_from_file_location("deliverables_manifest_p76", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["deliverables_manifest_p76"] = m
_spec.loader.exec_module(m)

KINDS = ("project", "task", "module", "tool", "research_project")


def D(number, evidence_ref="ref"):
    return {"number": number, "evidence_ref": evidence_ref}


def MANIFEST(numbers=range(1, 16), kind="project", project_id="proj-1"):
    return {"project_id": project_id, "kind": kind,
            "deliverables": [D(n, "ref-%s" % n) for n in numbers]}


class Base(unittest.TestCase):
    def refuses(self, code, fn, *a):
        with self.assertRaises(ValueError) as cm:
            fn(*a)
        self.assertEqual(str(cm.exception), "P76:" + code)


class DeliverablesList(Base):
    def test_fifteen_pinned_verbatim_order(self):
        self.assertEqual(len(m.DELIVERABLES), 15)
        self.assertEqual(m.DELIVERABLES[0], "a separate repository per project")
        self.assertEqual(m.DELIVERABLES[4], "vast code, tests, verification scripts, mathematical formulas")
        self.assertEqual(m.DELIVERABLES[8], "50+ page research paper, Times New Roman, good formatting")
        self.assertEqual(m.DELIVERABLES[14], "beat all relevant world benchmarks, best in world per field")


class Acceptance(Base):
    def test_valid_manifest_all_kinds(self):
        for kind in KINDS:
            r = m.validate_manifest(MANIFEST(kind=kind))
            self.assertEqual(r["project_id"], "proj-1")
            self.assertEqual(r["kind"], kind)
            self.assertEqual(r["deliverable_count"], 15)
            self.assertIs(r["complete"], True)
            self.assertEqual([d["number"] for d in r["deliverables"]], list(range(1, 16)))

    def test_canonical_sort_and_input_never_mutated(self):
        man = MANIFEST(numbers=list(range(15, 0, -1)))
        snap = {"project_id": man["project_id"], "kind": man["kind"],
                "deliverables": [dict(d) for d in man["deliverables"]]}
        r = m.validate_manifest(man)
        self.assertEqual([d["number"] for d in r["deliverables"]], list(range(1, 16)))
        self.assertEqual(man, snap)
        self.assertEqual(r, m.validate_manifest(MANIFEST()))

    def test_honesty_flags_and_boundary(self):
        r = m.validate_manifest(MANIFEST())
        self.assertEqual(r["status"], "declared_manifest_only")
        self.assertIs(r["evidence_verified"], False)
        self.assertIs(r["deliverables_produced"], False)
        self.assertEqual(r["boundary"],
                         "Only the supplied manifest is checked. All 15 deliverables are caller "
                         "declarations; declaration is not production, evidence refs are recorded "
                         "but never resolved, and validation never touches a repository, dataset, "
                         "tool or paper.")


class Incompleteness(Base):
    def test_missing_single_and_many_exact_code(self):
        self.refuses("missing_deliverables:7", m.validate_manifest,
                     MANIFEST(numbers=[n for n in range(1, 16) if n != 7]))
        self.refuses("missing_deliverables:1,2,15", m.validate_manifest,
                     MANIFEST(numbers=range(3, 15)))
        self.refuses("missing_deliverables:1,2,3,4,5,6,7,8,9,10,11,12,13,14,15",
                     m.validate_manifest, MANIFEST(numbers=[]))

    def test_duplicate_exact_code(self):
        self.refuses("duplicate_deliverable:3", m.validate_manifest,
                     MANIFEST(numbers=list(range(1, 15)) + [3]))

    def test_number_range_and_type(self):
        for bad in (0, 16, -1):
            self.refuses("number_out_of_range:number", m.validate_manifest,
                         MANIFEST(numbers=list(range(1, 15)) + [bad]))
        for bad in (True, 1.5, "3", None):
            self.refuses("bad_type:number", m.validate_manifest,
                         MANIFEST(numbers=list(range(1, 15)) + [bad]))

    def test_int_subclass_refused_exact_type(self):
        class MyInt(int):
            pass
        self.refuses("bad_type:number", m.validate_manifest,
                     MANIFEST(numbers=list(range(1, 15)) + [MyInt(15)]))
        man = MANIFEST()
        man["deliverables"][0]["number"] = MyInt(1)
        self.refuses("bad_type:number", m.validate_manifest, man)


class Refusals(Base):
    def test_manifest_shape(self):
        self.refuses("bad_type:manifest", m.validate_manifest, None)
        self.refuses("bad_type:manifest", m.validate_manifest, [1])
        self.refuses("unknown_fields:manifest", m.validate_manifest,
                     dict(MANIFEST(), extra=1))
        man = MANIFEST()
        del man["kind"]
        self.refuses("empty_field:kind", m.validate_manifest, man)

    def test_project_id_and_kind(self):
        self.refuses("bad_type:project_id", m.validate_manifest, MANIFEST(project_id=True))
        self.refuses("empty_field:project_id", m.validate_manifest, MANIFEST(project_id="  "))
        self.refuses("bad_type:kind", m.validate_manifest, MANIFEST(kind=7))
        self.refuses("bad_kind:org", m.validate_manifest, MANIFEST(kind="org"))

    def test_text_limits_n_nplus1(self):
        m.validate_manifest(MANIFEST(project_id="x" * 64))
        self.refuses("text_too_long:project_id", m.validate_manifest,
                     MANIFEST(project_id="x" * 65))
        man = MANIFEST()
        man["deliverables"][0]["evidence_ref"] = "x" * 128
        m.validate_manifest(man)
        man["deliverables"][0]["evidence_ref"] += "x"
        self.refuses("text_too_long:evidence_ref", m.validate_manifest, man)

    def test_deliverable_record_shape(self):
        man = MANIFEST()
        man["deliverables"][0] = "broken"
        self.refuses("bad_type:deliverable", m.validate_manifest, man)
        man = MANIFEST()
        man["deliverables"][0]["extra"] = 1
        self.refuses("unknown_fields:deliverable", m.validate_manifest, man)
        man = MANIFEST()
        del man["deliverables"][0]["evidence_ref"]
        self.refuses("empty_field:evidence_ref", m.validate_manifest, man)
        self.refuses("bad_type:deliverables", m.validate_manifest,
                     dict(MANIFEST(), deliverables="all"))


class HostileInputs(Base):
    def test_control_chars_refused_in_text_fields(self):
        for field in ("project_id", "evidence_ref"):
            for payload in ("a\nb", "a\rb", "x\u2028", "x\u2029",
                            "x\u0085", "null\x00", "esc\x1b[0m", "del\x7f"):
                man = MANIFEST()
                if field == "project_id":
                    man["project_id"] = payload
                else:
                    man["deliverables"][0]["evidence_ref"] = payload
                self.refuses("unsafe_chars:" + field, m.validate_manifest, man)

    def test_refusal_changes_nothing(self):
        man = MANIFEST(numbers=[1])
        try:
            m.validate_manifest(man)
        except ValueError:
            pass
        self.assertEqual(man, MANIFEST(numbers=[1]))


if __name__ == "__main__":
    unittest.main()
