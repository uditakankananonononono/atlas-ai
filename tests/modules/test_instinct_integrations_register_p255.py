"""P255|L202 external tool integrations register tests. Stdlib unittest, hermetic."""
import importlib.util
import pathlib
import sys
import unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/instinct_doc/integrations_register_p255.py"
_spec = importlib.util.spec_from_file_location("integrations_register_p255", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["integrations_register_p255"] = m
_spec.loader.exec_module(m)


def E(id="i1", project_id="p1", name="Stripe", purpose="payments", status="declared", evidence_ref=None):
    e = {"id": id, "project_id": project_id, "name": name, "purpose": purpose, "status": status}
    if evidence_ref is not None:
        e["evidence_ref"] = evidence_ref
    return e


def build(*entries):
    r = m.create_register()
    for e in entries:
        r = m.append(r, e)
    return r


class T(unittest.TestCase):
    def refuses(self, code, fn, *a):
        with self.assertRaises(ValueError) as cm:
            fn(*a)
        self.assertEqual(str(cm.exception), "P255:" + code)

    def test_round_trip_unverified_default(self):
        r = build(E())
        self.assertEqual(m.render(r), "project p1 (1 integrations)\nStripe declared payments UNVERIFIED")

    def test_evidence_ref_rendered_in_brackets(self):
        r = build(E(evidence_ref="doc#4"))
        self.assertEqual(m.render(r), "project p1 (1 integrations)\nStripe declared payments [doc#4]")

    def test_blank_evidence_is_unverified_and_stored_empty(self):
        for ev in ("", "   "):
            r = build(E(evidence_ref=ev))
            self.assertTrue(m.render(r).endswith(" UNVERIFIED"))
            self.assertEqual(r.entries[0][5], "")

    def test_missing_evidence_ref_ok(self):
        self.assertEqual(len(build(E()).entries), 1)

    def test_sorting_projects_and_names(self):
        r = build(E("a", "pb", "Zed"), E("b", "pa", "Slack"), E("c", "pb", "Algolia", status="active"))
        self.assertEqual(m.render(r),
                         "project pa (1 integrations)\nSlack declared payments UNVERIFIED\n"
                         "project pb (2 integrations)\nAlgolia active payments UNVERIFIED\nZed declared payments UNVERIFIED")
        self.assertEqual(m.render(r, "pa"), "project pa (1 integrations)\nSlack declared payments UNVERIFIED")

    def test_empty_register(self):
        self.assertEqual(m.render(m.create_register()), "")

    def test_all_statuses_accepted(self):
        for i, st in enumerate(("declared", "planned", "active", "deprecated")):
            build(E(status=st))
        self.refuses("bad_status:connected", m.append, m.create_register(), E(status="connected"))
        self.refuses("bad_status:verified", m.append, m.create_register(), E(status="verified"))
        self.refuses("bad_status:Active", m.append, m.create_register(), E(status="Active"))

    def test_no_connected_or_verified_claim(self):
        out = m.render(build(E(status="active"), E("j", "p1", "Slack")))
        self.assertNotIn("connected", out)
        self.assertNotIn("verified", out)

    def test_duplicate_id_global(self):
        self.refuses("duplicate_id:i1", m.append, build(E()), E("i1", "p2", "Other"))

    def test_duplicate_name_within_project_only(self):
        r = build(E())
        self.refuses("duplicate_name:Stripe", m.append, r, E("i2", "p1", "Stripe"))
        m.append(r, E("i2", "p2", "Stripe"))

    def test_unknown_fields_and_missing(self):
        e = E(); e["extra"] = 1
        self.refuses("unknown_fields:entry", m.append, m.create_register(), e)
        for name in ("id", "project_id", "name", "purpose", "status"):
            e = E(); del e[name]
            self.refuses("empty_field:" + name, m.append, m.create_register(), e)
        self.refuses("bad_type:entry", m.append, m.create_register(), [E()])

    def test_empty_fields(self):
        for name in ("id", "project_id", "name", "purpose"):
            for blank in ("", "  "):
                self.refuses("empty_field:" + name, m.append, m.create_register(), E(**{name: blank}))

    def test_bad_types(self):
        r = m.create_register()
        for name in ("id", "project_id", "name", "purpose", "status"):
            for bad in (None, 5, True, 1.5):
                self.refuses("bad_type:" + name, m.append, r, E(**{name: bad}))
        e = E(); e["evidence_ref"] = None
        self.refuses("bad_type:evidence_ref", m.append, r, e)
        self.refuses("bad_type:evidence_ref", m.append, r, E(evidence_ref=5))
        self.refuses("bad_type:evidence_ref", m.append, r, E(evidence_ref=False))
        self.refuses("bad_type:register", m.append, None, E())
        self.refuses("bad_type:register", m.render, None)

    def test_text_boundaries(self):
        for name, n in (("id", 64), ("project_id", 64), ("name", 64), ("purpose", 256), ("evidence_ref", 128)):
            m.append(m.create_register(), E(**{name: "x" * n}))
            self.refuses("text_too_long:" + name, m.append, m.create_register(), E(**{name: "x" * (n + 1)}))

    def test_integrations_per_project_boundary(self):
        r = m.create_register()
        for i in range(256):
            r = m.append(r, E("e%d" % i, "p1", "n%d" % i))
        self.refuses("limit_exceeded:integrations_per_project", m.append, r, E("z", "p1", "extra"))
        m.append(r, E("z", "p2", "extra"))

    def test_projects_boundary(self):
        r = m.create_register()
        for i in range(1024):
            r = m.append(r, E("e%d" % i, "p%d" % i))
        self.refuses("limit_exceeded:projects", m.append, r, E("z", "new"))
        m.append(r, E("z", "p0", "second"))

    def test_render_unknown_project(self):
        self.refuses("unknown_project:nope", m.render, build(E()), "nope")
        self.refuses("bad_type:project_id", m.render, build(E()), 5)
        self.refuses("bad_type:project_id", m.render, build(E()), True)

    def test_mutation_free_and_atomic(self):
        r = build(E())
        e = E("i2", "p1", "Slack"); snap = dict(e)
        new = m.append(r, e)
        self.assertEqual(e, snap)
        self.assertEqual((len(r.entries), len(new.entries)), (1, 2))
        self.refuses("duplicate_id:i1", m.append, r, E("i1", "p1", "Q"))
        self.assertEqual(len(r.entries), 1)

    def test_determinism(self):
        seq = [E("a", "p2", "B"), E("b", "p1", "A", evidence_ref="r")]
        self.assertEqual(m.render(build(*seq)).encode(), m.render(build(*seq)).encode())

    def test_constants_pinned(self):
        self.assertEqual(m.STATUSES, ("declared", "planned", "active", "deprecated"))
        self.assertEqual(m.FIELDS, ("id", "project_id", "name", "purpose", "status", "evidence_ref"))

    def test_module_has_no_network_or_io_imports(self):
        src = _P.read_text()
        for bad in ("socket", "urllib", "http", "requests", "subprocess", "open(", "time", "random", "datetime"):
            self.assertNotIn("import " + bad, src)
            self.assertNotIn("from " + bad, src)


if __name__ == "__main__":
    unittest.main()
