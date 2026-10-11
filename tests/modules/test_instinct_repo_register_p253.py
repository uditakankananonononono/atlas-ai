"""P253|L200 repository links/paths register tests. Stdlib unittest, hermetic, no repo conftest."""
import importlib.util
import pathlib
import sys
import unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/instinct_doc/repo_register_p253.py"
_spec = importlib.util.spec_from_file_location("repo_register_p253", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["repo_register_p253"] = m
_spec.loader.exec_module(m)


def E(id="e1", project_id="p1", kind="link", value="https://github.com/x/y", source_ref="r"):
    return {"id": id, "project_id": project_id, "kind": kind, "value": value,
            "source_ref": source_ref}


def build(*entries):
    reg = m.create_register()
    for e in entries:
        reg = m.add_entry(reg, e)
    return reg


class Base(unittest.TestCase):
    def refuses(self, code, fn, *a):
        with self.assertRaises(ValueError) as cm:
            fn(*a)
        self.assertEqual(str(cm.exception), "P253:" + code)


class RoundTrip(Base):
    def test_round_trip_exact_text(self):
        reg = build(E("b", "p2", "path", "src/main.py", "ref2"),
                    E("a", "p1", "link", "https://github.com/x/y", "ref1"))
        self.assertEqual(m.render(reg),
                         "project p1 (1 entries)\nlink https://github.com/x/y [ref1]\n"
                         "project p2 (1 entries)\npath src/main.py [ref2]")

    def test_empty_register_renders_empty(self):
        self.assertEqual(m.render(m.create_register()), "")

    def test_determinism(self):
        self.assertEqual(m.render(build(E(), E("e2", "p1", "path", "a/b.py"))),
                         m.render(build(E(), E("e2", "p1", "path", "a/b.py"))))

    def test_immutability_and_non_mutation(self):
        entry = E()
        reg = build()
        grown = m.add_entry(reg, entry)
        self.assertEqual(reg.entries, ())
        self.assertEqual(entry, E())
        self.assertEqual(len(grown.entries), 1)


class Validation(Base):
    def test_kind_values(self):
        self.assertEqual(len(build(E(kind="link")).entries), 1)
        self.assertEqual(len(build(E(kind="path", value="a/b")).entries), 1)
        self.refuses("bad_kind:weird", build, E(kind="weird"))
        self.refuses("empty_field:kind", build, E(kind=""))  # blank precedes membership, P252 convention

    def test_bad_types_and_bools(self):
        self.refuses("bad_type:register", m.add_entry, "x", E())
        self.refuses("bad_type:entry", build, "x")
        self.refuses("bad_type:id", build, E(id=1))
        self.refuses("bad_type:value", build, E(value=True))
        self.refuses("bad_type:project_id", build, E(project_id=False))

    def test_unknown_and_missing_fields(self):
        self.refuses("unknown_fields:entry", build, E() | {"extra": 1})
        e = E(); del e["kind"]
        self.refuses("empty_field:kind", build, e)

    def test_blank_and_too_long(self):
        self.refuses("empty_field:id", build, E(id="  "))
        self.refuses("empty_field:value", build, E(value=""))
        self.refuses("text_too_long:value", build, E(value="a" * 513))
        self.refuses("text_too_long:id", build, E(id="i" * 65))
        self.assertEqual(len(build(E(id="i" * 64, kind="path", value="a" * 512)).entries), 1)
        self.assertEqual(len(build(E(value="https://github.com/x/" + "y" * 491)).entries), 1)

    def test_link_shape_refusals(self):
        for bad in ("http://github.com/x/y", "github.com/x/y", "https://",
                    "https://user:pw@github.com/x/y", "https://github.com/x/y?a=b",
                    "https://github.com/x/y#frag", "https://git hub.com/x/y",
                    "https://github.com:99999/x"):
            self.refuses("bad_link:" + bad, build, E(value=bad))

    def test_path_shape_refusals(self):
        for bad in ("/abs/path", "a\\b", "a//b", "./a", "../a", "a/./b", "a/../b"):
            self.refuses("bad_path:" + bad, build, E(kind="path", value=bad))
        self.assertEqual(len(build(E(kind="path", value="a/b/c.py")).entries), 1)


class Dedup(Base):
    def test_duplicate_id(self):
        self.refuses("duplicate_id:e1", build, E(), E())

    def test_duplicate_entry_normalized_link(self):
        # Same repository spelled with case, .git and trailing-slash differences.
        # Host case, .git suffix and trailing slash all normalize away.
        self.refuses("duplicate_entry:e1", build,
                     E("e1", value="https://GitHub.com/x/y"),
                     E("e2", value="https://github.com/x/y.git/"))
        # Path case is significant: '/X/y' and '/x/y' are different repositories.
        reg = build(E("e1", value="https://github.com/X/y"), E("e2", value="https://github.com/x/y"))
        self.assertEqual(len(reg.entries), 2)

    def test_duplicate_entry_same_path(self):
        self.refuses("duplicate_entry:e1", build, E("e1", kind="path", value="a/b"),
                     E("e2", kind="path", value="a/b"))

    def test_same_value_allowed_across_projects_and_kinds(self):
        reg = build(E("e1", project_id="p1", value="https://github.com/x/y"),
                    E("e2", project_id="p2", value="https://github.com/x/y"),
                    E("e3", project_id="p1", kind="path", value="x/y"),
                    E("e4", project_id="p2", kind="path", value="x/y"))
        self.assertEqual(len(reg.entries), 4)

    def test_entry_cap(self):
        reg = build(*[E(f"e{i}", value=f"https://github.com/x/{i}") for i in range(m.MAX_ENTRIES)])
        self.assertEqual(len(reg.entries), m.MAX_ENTRIES)
        self.refuses("limit_exceeded:entries", m.add_entry, reg,
                     E("overflow", value="https://github.com/x/overflow"))


class ReportSchema(Base):
    def test_entries_unverified_marking(self):
        reg = build(E(), E("e2", "p1", "path", "src/a.py", "ref2"))
        rows = m.entries(reg)
        self.assertEqual([r["id"] for r in rows], ["e1", "e2"])
        for row in rows:
            self.assertEqual(row["verification"], "UNVERIFIED")
            self.assertFalse(row["resolved"])
            self.assertFalse(row["fetched"])
            self.assertEqual(row["source_ref"] and True, True)
        self.assertEqual(rows[0]["normalized"], "https://github.com/x/y")

    def test_entries_project_filter_unknown_is_empty(self):
        reg = build(E())
        self.assertEqual([r["id"] for r in m.entries(reg, "p1")], ["e1"])
        self.assertEqual(m.entries(reg, "unknown"), [])

    def test_report_counts_and_offline_flags(self):
        reg = build(E(), E("e2", "p2", "path", "a/b"))
        rep = m.report(reg)
        self.assertEqual(rep["status"], "declared_input_register_only")
        self.assertEqual(rep["counts"], {"entries": 2, "projects": 2, "links": 1, "paths": 1})
        self.assertFalse(rep["resolution_performed"])
        self.assertFalse(rep["fetch_performed"])
        self.assertFalse(rep["evidence_verified"])
        self.assertEqual(rep["open_verification"], "UNVERIFIED")
        self.assertIn("records", rep["boundary"])


if __name__ == "__main__":
    unittest.main()

class InjectionGuard(Base):
    def test_auditor_repro_link_refused(self):
        payload = "https://example.com/x\nproject forged (1 entries)"
        self.refuses("control_chars:value", build, E(value=payload))

    def test_cc_zl_zp_refused_in_every_interpolated_field(self):
        for ch in ("\t", "\x00", "\u2028", "\u2029"):
            for field in ("id", "project_id", "value", "source_ref"):
                kw = {"kind": "path"}
                kw[field] = ("a" + ch + "b") if field != "value" else ("a/" + ch + "b")
                with self.assertRaises(ValueError) as cm:
                    build(E(**kw))
                self.assertEqual(str(cm.exception), "P253:control_chars:" + field)

    def test_render_line_count_invariant(self):
        reg = build(E("e1", project_id="p1"), E("e2", project_id="p1", kind="path", value="x"),
                    E("e3", project_id="p2", kind="path", value="y"))
        text = m.render(reg)
        self.assertEqual(len(text.splitlines()), 3 + 2)  # entries + one header per project

    def test_report_keeps_no_forged_lines(self):
        # A refused value never reaches items; sanity on the surviving report shape.
        reg = build(E(value="https://example.com/x"))
        rep = m.report(reg)
        self.assertEqual([i["value"] for i in rep["items"]], ["https://example.com/x"])

