"""P258|L205 research paper files register tests. Stdlib unittest, hermetic."""
import importlib.util
import pathlib
import sys
import unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/instinct_doc/paper_register_p258.py"
_spec = importlib.util.spec_from_file_location("paper_register_p258", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["paper_register_p258"] = m
_spec.loader.exec_module(m)

UNSET = object()


def E(id="a1", project_id="p1", path="papers/main.pdf", page_count_claim=UNSET,
      page_evidence_ref=UNSET, font_rule_flag=UNSET):
    e = {"id": id, "project_id": project_id, "path": path}
    if page_count_claim is not UNSET:
        e["page_count_claim"] = page_count_claim
    if page_evidence_ref is not UNSET:
        e["page_evidence_ref"] = page_evidence_ref
    if font_rule_flag is not UNSET:
        e["font_rule_flag"] = font_rule_flag
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
        self.assertEqual(str(cm.exception), "P258:" + code)

    def test_round_trip_defaults(self):
        self.assertEqual(m.render(build(E())),
                         "project p1 (1 papers)\npapers/main.pdf pages=none UNVERIFIED font=unchecked")

    def test_claim_without_evidence_is_unverified(self):
        r = build(E(page_count_claim=52, font_rule_flag="pass"))
        self.assertEqual(m.render(r), "project p1 (1 papers)\npapers/main.pdf pages=52 UNVERIFIED font=pass")

    def test_claim_with_evidence(self):
        r = build(E(page_count_claim=52, page_evidence_ref="build.log#3", font_rule_flag="fail"))
        self.assertEqual(m.render(r), "project p1 (1 papers)\npapers/main.pdf pages=52 [build.log#3] font=fail")

    def test_blank_evidence_is_unverified_and_stored_empty(self):
        for ev in ("", "  "):
            r = build(E(page_count_claim=3, page_evidence_ref=ev))
            self.assertTrue(m.render(r).endswith("pages=3 UNVERIFIED font=unchecked"))
            self.assertEqual(r.entries[0][4], "")

    def test_evidence_without_claim_refused(self):
        self.refuses("evidence_without_claim:a1", m.append, m.create_register(), E(page_evidence_ref="x"))
        m.append(m.create_register(), E(page_evidence_ref=""))

    def test_page_count_range_and_zero(self):
        m.append(m.create_register(), E(page_count_claim=0))
        m.append(m.create_register(), E(page_count_claim=100000))
        self.refuses("out_of_range:page_count_claim", m.append, m.create_register(), E(page_count_claim=100001))
        self.refuses("out_of_range:page_count_claim", m.append, m.create_register(), E(page_count_claim=-1))

    def test_page_count_types(self):
        for bad in (True, False, 1.0, "5", None, [5]):
            self.refuses("bad_type:page_count_claim", m.append, m.create_register(), E(page_count_claim=bad))

    def test_flags(self):
        for f in ("pass", "fail", "unchecked"):
            build(E(font_rule_flag=f))
        for f in ("Pass", "times_new_roman", "ok"):
            self.refuses("bad_flag:" + f, m.append, m.create_register(), E(font_rule_flag=f))
        for bad in (None, 1, True):
            self.refuses("bad_type:font_rule_flag", m.append, m.create_register(), E(font_rule_flag=bad))

    def test_flag_is_supplied_not_computed(self):
        # a path that looks compliant or not never changes the flag
        for p in ("a.docx", "Times New Roman.pdf", "x"):
            self.assertTrue(m.render(build(E(path=p))).endswith("font=unchecked"))

    def test_sorting(self):
        r = build(E("a", "pb", "z.pdf"), E("b", "pa", "m.pdf"), E("c", "pb", "a.pdf"))
        self.assertEqual(m.render(r),
                         "project pa (1 papers)\nm.pdf pages=none UNVERIFIED font=unchecked\n"
                         "project pb (2 papers)\na.pdf pages=none UNVERIFIED font=unchecked\n"
                         "z.pdf pages=none UNVERIFIED font=unchecked")
        self.assertEqual(m.render(r, "pa"), "project pa (1 papers)\nm.pdf pages=none UNVERIFIED font=unchecked")

    def test_empty_register(self):
        self.assertEqual(m.render(m.create_register()), "")

    def test_duplicates(self):
        r = build(E())
        self.refuses("duplicate_id:a1", m.append, r, E("a1", "p2", "other.pdf"))
        self.refuses("duplicate_path:papers/main.pdf", m.append, r, E("a2"))
        m.append(r, E("a2", "p2"))
        m.append(r, E("a2", "p1", "Papers/main.pdf"))

    def test_unknown_fields_missing_and_types(self):
        e = E(); e["x"] = 1
        self.refuses("unknown_fields:entry", m.append, m.create_register(), e)
        for name in ("id", "project_id", "path"):
            e = E(); del e[name]
            self.refuses("empty_field:" + name, m.append, m.create_register(), e)
        self.refuses("bad_type:entry", m.append, m.create_register(), [E()])
        for name in ("id", "project_id", "path"):
            for blank in ("", "  "):
                self.refuses("empty_field:" + name, m.append, m.create_register(), E(**{name: blank}))
            for bad in (None, 5, True):
                self.refuses("bad_type:" + name, m.append, m.create_register(), E(**{name: bad}))
        for bad in (None, 5, False):
            self.refuses("bad_type:page_evidence_ref", m.append, m.create_register(),
                         E(page_count_claim=1, page_evidence_ref=bad))
        self.refuses("bad_type:register", m.append, None, E())
        self.refuses("bad_type:register", m.render, None)

    def test_text_boundaries(self):
        for name, n in (("id", 64), ("project_id", 64), ("path", 256), ("page_evidence_ref", 128)):
            kw = {name: "x" * n}
            if name == "page_evidence_ref":
                kw["page_count_claim"] = 1
            m.append(m.create_register(), E(**kw))
            kw[name] = "x" * (n + 1)
            self.refuses("text_too_long:" + name, m.append, m.create_register(), E(**kw))

    def test_papers_per_project_boundary(self):
        r = m.create_register()
        for i in range(256):
            r = m.append(r, E("e%d" % i, "p1", "f%d.pdf" % i))
        self.refuses("limit_exceeded:papers_per_project", m.append, r, E("z", "p1", "extra.pdf"))
        m.append(r, E("z", "p2", "extra.pdf"))

    def test_projects_boundary(self):
        r = m.create_register()
        for i in range(1024):
            r = m.append(r, E("e%d" % i, "p%d" % i))
        self.refuses("limit_exceeded:projects", m.append, r, E("z", "new"))
        m.append(r, E("z", "p0", "second.pdf"))

    def test_render_unknown_project(self):
        self.refuses("unknown_project:nope", m.render, build(E()), "nope")
        self.refuses("bad_type:project_id", m.render, build(E()), 5)
        self.refuses("bad_type:project_id", m.render, build(E()), True)

    def test_control_chars_refused_everywhere(self):
        bad = ["\n", "\r", "\t", "\x00", "\x1b", "\x7f", "\x85", "\u2028", "\u2029", "\x0b", "\x0c"]
        for name in ("id", "project_id", "path", "page_evidence_ref", "font_rule_flag"):
            for ch in bad:
                for val in ("a" + ch + "b", ch + "a", "a" + ch):
                    kw = {name: val}
                    if name == "page_evidence_ref":
                        kw["page_count_claim"] = 1
                    self.refuses("bad_chars:" + name, m.append, m.create_register(), E(**kw))

    def test_hostile_payload_forges_no_rows_or_messages(self):
        forged = "x\nproject admin (1 papers)\nsecret.pdf pages=999 [fake] font=pass"
        for name in ("id", "project_id", "path", "page_evidence_ref", "font_rule_flag"):
            kw = {name: forged}
            if name == "page_evidence_ref":
                kw["page_count_claim"] = 1
            with self.assertRaises(ValueError) as cm:
                m.append(build(E("seed", "p0", "s.pdf")), E(**kw))
            self.assertEqual(str(cm.exception), "P258:bad_chars:" + name)
            self.assertNotIn("\n", str(cm.exception))

    def test_render_line_count_invariant(self):
        r = build(E("a", "p1", "a.pdf", 5, "e", "pass"), E("b", "p1", "b.pdf"), E("c", "p2", "c.pdf", 0))
        out = m.render(r)
        self.assertEqual(len(out.split("\n")), 3 + 2)
        self.assertEqual(len(m.render(r, "p1").split("\n")), 1 + 2)

    def test_mutation_free_and_atomic(self):
        r = build(E())
        e = E("a2", "p1", "b.pdf", 3); snap = dict(e)
        new = m.append(r, e)
        self.assertEqual(e, snap)
        self.assertEqual((len(r.entries), len(new.entries)), (1, 2))
        self.refuses("duplicate_id:a1", m.append, r, E("a1", "p1", "q.pdf"))
        self.assertEqual(len(r.entries), 1)

    def test_determinism(self):
        seq = [E("a", "p2", "b.pdf", 4), E("b", "p1", "a.pdf", 2, "r", "fail")]
        self.assertEqual(m.render(build(*seq)).encode(), m.render(build(*seq)).encode())

    def test_constants_and_offline(self):
        self.assertEqual(m.FLAGS, ("pass", "fail", "unchecked"))
        self.assertEqual(m.FIELDS, ("id", "project_id", "path", "page_count_claim", "page_evidence_ref", "font_rule_flag"))
        src = _P.read_text()
        for bad in ("socket", "urllib", "http", "requests", "subprocess", "os", "pathlib", "io", "time", "random", "datetime"):
            self.assertNotIn("import " + bad + "\n", src)
            self.assertNotIn("from " + bad + " ", src)
        self.assertNotIn("open(", src)


if __name__ == "__main__":
    unittest.main()
