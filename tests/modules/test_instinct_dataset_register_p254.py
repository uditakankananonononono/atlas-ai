"""P254|L201 dataset register tests. Stdlib unittest, hermetic, no repo conftest."""
import importlib.util
import pathlib
import sys
import unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/instinct_doc/dataset_register_p254.py"
_spec = importlib.util.spec_from_file_location("dataset_register_p254", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["dataset_register_p254"] = m
_spec.loader.exec_module(m)


def E(id="e1", project_id="p1", dataset="gsm8k", records=10, source="openai/gsm8k", source_ref="hf:gsm8k"):
    return {"id": id, "project_id": project_id, "dataset": dataset,
            "records": records, "source": source, "source_ref": source_ref}


def build(*entries):
    reg = m.create_register()
    for e in entries:
        reg = m.add_entry(reg, e)
    return reg


class Base(unittest.TestCase):
    def refuses(self, code, fn, *a):
        with self.assertRaises(ValueError) as cm:
            fn(*a)
        self.assertEqual(str(cm.exception), "P254:" + code)


class RoundTrip(Base):
    def test_render_exact_text_and_order_independence(self):
        reg = build(E("b", "p2", "math", 5, "hendrycks/math", "hf:math"),
                    E("a", "p1"), E("c", "p1", "arc", 7, "allenai/arc", "hf:arc"))
        self.assertEqual(m.render(reg),
                         "project p1 (2 entries, 17 records)\n"
                         "a gsm8k 10 records from openai/gsm8k [hf:gsm8k]\n"
                         "c arc 7 records from allenai/arc [hf:arc]\n"
                         "project p2 (1 entries, 5 records)\n"
                         "b math 5 records from hendrycks/math [hf:math]")
        same = build(E("c", "p1", "arc", 7, "allenai/arc", "hf:arc"),
                     E("a", "p1"), E("b", "p2", "math", 5, "hendrycks/math", "hf:math"))
        self.assertEqual(m.render(reg), m.render(same))

    def test_single_project_render_and_unknown(self):
        reg = build(E("a", "p1"), E("b", "p2"))
        self.assertEqual(m.render(reg, "p2"),
                         "project p2 (1 entries, 10 records)\n"
                         "b gsm8k 10 records from openai/gsm8k [hf:gsm8k]")
        self.refuses("unknown_project:ghost", m.render, reg, "ghost")
        self.refuses("bad_type:project_id", m.render, reg, True)
        self.refuses("bad_type:register", m.render, "not-a-register")
        self.refuses("bad_type:register", m.summary, None)

    def test_empty_register(self):
        reg = m.create_register()
        self.assertEqual(m.render(reg), "")
        s = m.summary(reg)
        self.assertEqual(s["projects"], {})
        self.assertEqual(s["entry_count"], 0)
        self.assertEqual(s["total_records"], 0)
        self.assertIs(s["completeness_verified"], False)


class LineCountInvariant(Base):
    def test_render_line_count_is_projects_plus_entries(self):
        cases = [[], [E("a")], [E("a"), E("b", "p1"), E("c", "p2"), E("d", "p3")]]
        for entries in cases:
            reg = build(*entries)
            projects = len({e["project_id"] for e in entries})
            out = m.render(reg)
            got = 0 if out == "" else len(out.split("\n"))
            self.assertEqual(got, projects + len(entries))
            self.assertFalse(out.endswith("\n"))
            self.assertNotIn("\r", out)

    def test_refused_payloads_cannot_forge_lines(self):
        reg = build(E("ok1"), E("ok2", "p2"))
        before = m.render(reg)
        for field in ("id", "project_id", "dataset", "source", "source_ref"):
            for payload in ("x\nforged line", "a\r\nb", "a\rb",
                            "x\u2028", "x\u2029", "x\u0085",
                            "null\x00byte", "esc\x1b[31mred", "del\x7f"):
                entry = E("evil")
                entry[field] = payload
                self.refuses("unsafe_chars:" + field, m.add_entry, reg, entry)
        self.assertEqual(m.render(reg), before)
        self.assertEqual(len(before.split("\n")), 4)


class Refusals(Base):
    def test_shape_and_types(self):
        reg = m.create_register()
        self.refuses("bad_type:register", m.add_entry, None, E())
        self.refuses("bad_type:entry", m.add_entry, reg, "x")
        self.refuses("unknown_fields:entry", m.add_entry, reg, dict(E(), extra=1))
        missing = E()
        del missing["source"]
        self.refuses("empty_field:source", m.add_entry, reg, missing)
        for field in ("id", "project_id", "dataset", "source", "source_ref"):
            self.refuses("bad_type:" + field, m.add_entry, reg, E(**{field: True}))
            self.refuses("bad_type:" + field, m.add_entry, reg, E(**{field: 7}))
            self.refuses("empty_field:" + field, m.add_entry, reg, E(**{field: "   "}))

    def test_text_limits_n_nplus1(self):
        reg = m.create_register()
        for field, limit in (("id", 64), ("project_id", 64), ("dataset", 128),
                             ("source", 256), ("source_ref", 256)):
            m.add_entry(reg, E(**{field: "x" * limit}))
            self.refuses("text_too_long:" + field, m.add_entry, reg, E(**{field: "x" * (limit + 1)}))

    def test_records_bounds_n_nplus1(self):
        reg = m.create_register()
        m.add_entry(reg, E(records=0))
        m.add_entry(reg, E(records=10**15))
        self.refuses("count_out_of_range:records", m.add_entry, reg, E(records=10**15 + 1))
        self.refuses("count_out_of_range:records", m.add_entry, reg, E(records=-1))
        for bad in (True, 1.5, "10", None):
            self.refuses("bad_type:records", m.add_entry, reg, E(records=bad))

    def test_int_subclass_refused_exact_type(self):
        class MyInt(int):
            pass
        reg = m.create_register()
        self.refuses("bad_type:records", m.add_entry, reg, E(records=MyInt(3)))
        self.refuses("bad_type:records", m.add_entry, reg, E(records=MyInt(0)))

    def test_duplicate_id_exact(self):
        reg = build(E("dup"))
        self.refuses("duplicate_id:dup", m.add_entry, reg, E("dup", "p9"))

    def test_entry_cap_n_nplus1(self):
        reg = build(*(E("e%05d" % i) for i in range(4096)))
        self.refuses("limit_exceeded:entries", m.add_entry, reg, E("overflow"))


class Honesty(Base):
    def test_summary_rollup_and_flags(self):
        s = m.summary(build(E("b", "p2", "math", 5, "hendrycks/math", "hf:math"),
                            E("a", "p1"), E("c", "p1", "arc", 7, "allenai/arc", "hf:arc")))
        self.assertEqual(s["projects"], {
            "p1": {"entries": 2, "records": 17, "datasets": ["arc", "gsm8k"]},
            "p2": {"entries": 1, "records": 5, "datasets": ["math"]}})
        self.assertEqual(s["entry_count"], 3)
        self.assertEqual(s["total_records"], 22)
        self.assertEqual(s["status"], "declared_register_only")
        self.assertIs(s["counts_verified"], False)
        self.assertIs(s["sources_resolved"], False)
        self.assertIs(s["completeness_verified"], False)
        self.assertEqual(s["boundary"],
                         "Only supplied entries are recorded. Counts are caller declarations, "
                         "named sources are stored verbatim and never resolved or authenticated, "
                         "and an empty register does not prove the absence of datasets.")

    def test_immutability(self):
        reg = build(E("a"))
        snap_entries = reg.entries
        reg2 = m.add_entry(reg, E("b"))
        self.assertEqual(reg.entries, snap_entries)
        self.assertEqual(len(reg2.entries), 2)
        entry = E("c")
        frozen = dict(entry)
        m.add_entry(reg, entry)
        self.assertEqual(entry, frozen)


if __name__ == "__main__":
    unittest.main()
