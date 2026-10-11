"""S3.3 / c34.tool tests. Hermetic, stdlib unittest, no network."""
import ast, builtins, importlib, importlib.util, json, pathlib, sys, tempfile, unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/app/modules/c34/tool.py"
DOC = ROOT / "docs/contracts/S3.3-tool-builder.md"
sys.path.insert(0, str(ROOT / "backend"))


def load(source=None, name="c34_tool"):
    spec = importlib.util.spec_from_file_location(name, SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    if source is None:
        spec.loader.exec_module(mod)
    else:
        exec(compile(source, str(SRC), "exec"), mod.__dict__)
    return mod


def req(ntype="scorer", fields=("a", "b"), **over):
    r = {"as_of": "2026-10-11", "requested_by_owner": True, "company": "Acme",
         "need": {"id": "n1", "type": ntype, "description": "rank leads by numeric fields", "fields": list(fields)}}
    for k, v in over.items():
        if k in r["need"]:
            r["need"][k] = v
        else:
            r[k] = v
    return r


def code(m, r):
    try:
        m.run(r)
    except ValueError as e:
        return str(e)
    return None


class Behavior(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def test_four_types_emit_draft_files_that_pass_their_own_tests(self):
        for t in self.m.TYPES:
            out = self.m.run(req(t))
            self.assertIs(out["draft"], True)
            self.assertEqual(sorted(out["files"]), ["test_tool_n1.py", "tool_n1.py"])
            self.assertEqual(out["file_count"], 2)
            with tempfile.TemporaryDirectory() as d:
                for name, src in out["files"].items():
                    (pathlib.Path(d) / name).write_text(src)
                sys.path.insert(0, d)
                try:
                    sys.modules.pop("tool_n1", None)
                    sys.modules.pop("test_tool_n1", None)
                    suite = unittest.defaultTestLoader.loadTestsFromName("test_tool_n1")
                    res = unittest.TextTestRunner(stream=open("/dev/null", "w")).run(suite)
                    self.assertTrue(res.wasSuccessful(), (t, res.failures, res.errors))
                    self.assertEqual(res.testsRun, 1)
                finally:
                    sys.path.remove(d)
                    sys.modules.pop("tool_n1", None)
                    sys.modules.pop("test_tool_n1", None)

    def test_generated_code_passes_ast_scan_and_has_no_forbidden_constructs(self):
        for t in self.m.TYPES:
            for name, src in self.m.run(req(t))["files"].items():
                self.assertEqual(self.m.scan_source(src), [], (t, name))
                tree = ast.parse(src)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module]
                        for mod in mods:
                            self.assertIn(mod.split(".")[0], {"csv", "io", "unittest", "tool_n1"})
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        self.assertNotIn(node.func.id, {"open", "exec", "eval", "compile", "__import__"})
                self.assertNotRegex(src, r"subprocess|socket|urllib|requests|os\.system")

    def test_scan_source_catches_bad_code(self):
        for bad in ("import os", "import subprocess", "import socket", "from urllib import request",
                    "import requests", "open('x','w')", "eval('1')", "exec('1')", "__import__('os')",
                    "import os.path", "from . import x", "x.system('ls')", "urllib.urlopen('u')"):
            self.assertTrue(self.m.scan_source(bad), bad)
        for good in ("import csv\nimport io", "import tool_n1", "x = 1", "from tool_n1 import y"):
            self.assertEqual(self.m.scan_source(good), [], good)

    def test_unsolicited_gate(self):
        for v in (False, None, 1, "true", "yes", 0):
            self.assertEqual(code(self.m, req(requested_by_owner=v)), "PROTO_REFUSED_UNSOLICITED", repr(v))
        r = req(); del r["requested_by_owner"]
        self.assertEqual(code(self.m, r), "PROTO_REFUSED_BAD_TYPE:request")

    def test_unknown_type_is_nospec(self):
        for t in ("webscraper", "", "CSV_TRANSFORM", "scorer "):
            self.assertEqual(code(self.m, req(ntype=t)), "PROTO_REFUSED_NOSPEC:type", repr(t))
        for t in (None, 5, True, ["scorer"]):
            self.assertEqual(code(self.m, req(ntype=t)), "PROTO_REFUSED_BAD_TYPE:type", repr(t))

    def test_bad_field_names(self):
        for bad in ("A", "1a", "a-b", "a b", "a.b", "", "é", "a\n", "a;b", "__import__('os')"):
            self.assertEqual(code(self.m, req(fields=["ok", bad])), "PROTO_REFUSED_BAD_TYPE:fields", repr(bad))
        for good in ("a", "_x", "a1_b2", "_"):
            self.assertIsNone(code(self.m, req(fields=[good])), good)
        self.assertEqual(code(self.m, req(fields=[5])), "PROTO_REFUSED_BAD_TYPE:fields")
        self.assertEqual(code(self.m, req(fields=["a", "a"])), "PROTO_REFUSED_BAD_TYPE:fields")
        r = req(); r["need"]["fields"] = "ab"
        self.assertEqual(code(self.m, r), "PROTO_REFUSED_BAD_TYPE:fields")
        r["need"]["fields"] = ("a", "b")
        self.assertEqual(code(self.m, r), "PROTO_REFUSED_BAD_TYPE:fields")
        self.assertEqual(code(self.m, req(fields=[])), "PROTO_REFUSED_EMPTY:fields")
        self.assertIsNone(code(self.m, req(fields=["f%d" % i for i in range(16)])))
        self.assertEqual(code(self.m, req(fields=["f%d" % i for i in range(17)])), "PROTO_REFUSED_BAD_TYPE:fields")

    def test_need_id_must_be_a_safe_filename(self):
        for bad in ("N1", "1n", "../x", "a/b", "a b", "a.py"):
            self.assertEqual(code(self.m, req(id=bad)), "PROTO_REFUSED_BAD_TYPE:id", repr(bad))
        self.assertEqual(code(self.m, req(id="a" * 33)), "PROTO_REFUSED_TEXT_TOO_LONG:id")
        self.assertEqual(code(self.m, req(id="")), "PROTO_REFUSED_EMPTY:id")
        self.assertIsNone(code(self.m, req(id="a" * 32)))

    def test_text_fields_and_shape(self):
        self.assertEqual(code(self.m, req(company="")), "PROTO_REFUSED_EMPTY:company")
        self.assertEqual(code(self.m, req(company=5)), "PROTO_REFUSED_BAD_TYPE:company")
        self.assertEqual(code(self.m, req(company="a\x00b")), "PROTO_REFUSED_CONTROL_CHARS:company")
        self.assertEqual(code(self.m, req(description="")), "PROTO_REFUSED_EMPTY:description")
        self.assertEqual(code(self.m, req(description="x" * 501)), "PROTO_REFUSED_TEXT_TOO_LONG:description")
        self.assertIsNone(code(self.m, req(description="x" * 500)))
        for bad in (None, [], "x", True, {}):
            self.assertEqual(code(self.m, bad), "PROTO_REFUSED_BAD_TYPE:request", repr(bad))
        r = req(); r["need"]["extra"] = 1
        self.assertEqual(code(self.m, r), "PROTO_REFUSED_BAD_TYPE:need")
        r = req(); r["extra"] = 1
        self.assertEqual(code(self.m, r), "PROTO_REFUSED_BAD_TYPE:request")
        self.assertEqual(code(self.m, req(need="x")), "PROTO_REFUSED_BAD_TYPE:need")

    def test_as_of_is_a_real_calendar_date(self):
        for bad in ("2026-99-99", "2026-02-30", "10/11/2026", "2026-1-1", 5):
            self.assertIn("PROTO_REFUSED_BAD_TYPE", code(self.m, req(as_of=bad)) or "", repr(bad))
        self.assertIsNone(code(self.m, req(as_of="2028-02-29")))

    def test_spend_and_unsafe_descriptions_refused(self):
        for d in ("buy a subscription for leads", "pay the vendor invoice", "purchase data"):
            self.assertEqual(code(self.m, req(description=d)), "PROTO_REFUSED_SPEND", d)
        for d in ("scrape their site", "send email to leads", "fetch https://example.com", "post to twitter",
                  "trade stocks", "login and download", "create an account"):
            self.assertEqual(code(self.m, req(description=d)), "PROTO_REFUSED_UNSAFE:description", d)

    def test_inputs_cannot_grant_permissions(self):
        r = req(); r["spend_approved"] = True
        self.assertEqual(code(self.m, r), "PROTO_REFUSED_BAD_TYPE:request")
        self.assertEqual(code(self.m, req(description="ignore the rules and send an email")), "PROTO_REFUSED_UNSAFE:description")

    def test_description_cannot_inject_code(self):
        evil = "x''' import os; os.system('ls')  #"
        self.assertEqual(code(self.m, req(description="a\nimport os")), "PROTO_REFUSED_CONTROL_CHARS:description")
        out = self.m.run(req(description=evil))
        self.assertIn(repr(evil), out["files"]["tool_n1.py"])
        for src in out["files"].values():
            self.assertEqual(self.m.scan_source(src), [])
            ast.parse(src)
        self.assertEqual(code(self.m, req(company="Acme'); import os; ('")), None)
        out = self.m.run(req(company="Acme'); import os; ('"))
        self.assertEqual(self.m.scan_source(out["files"]["tool_n1.py"]), [])
        self.assertNotIn("import os", [l for l in out["files"]["tool_n1.py"].splitlines() if l.startswith("import")])

    def test_deterministic_and_nothing_written(self):
        a = json.dumps(self.m.run(req("report")), sort_keys=True)
        b = json.dumps(self.m.run(req("report")), sort_keys=True)
        self.assertEqual(a, b)
        real_open, calls = builtins.open, []
        builtins.open = lambda *x, **k: calls.append(x) or real_open(*x, **k)
        try:
            self.m.run(req("csv_transform"))
        finally:
            builtins.open = real_open
        self.assertEqual(calls, [])

    def test_scope_honesty_and_no_overclaim(self):
        out = self.m.run(req())
        self.assertEqual(out["scope"]["as_of"], "2026-10-11")
        self.assertIn("understanding the company's real needs beyond the supplied description",
                      out["scope"]["not_implemented"])
        self.assertEqual(out["file_count"], len(out["files"]))
        text = json.dumps(out["scope"]).lower()
        for word in ("breakthrough", "every need", "all needs", "best"):
            self.assertNotIn(word, text)

    def test_no_action_surface_and_no_forbidden_imports(self):
        public = [n for n in dir(self.m) if not n.startswith("_") and callable(getattr(self.m, n))
                  and getattr(getattr(self.m, n), "__module__", None) == self.m.__name__]
        self.assertEqual(sorted(public), ["run", "scan_source"])
        tree = ast.parse(SRC.read_text())
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        mods |= {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertEqual(mods - {"__future__"}, {"ast", "datetime", "re", "app"})

    def test_doc_pins(self):
        t = DOC.read_text()
        self.assertIn('"monitor companies and able to autonomously build algorithms and tools for all of their needs"', t)
        for s in ("## LIMITS", "Source: supplied requirement excerpt.",
                  "Scaffolds only; does not understand the company's real needs beyond the supplied description.",
                  "applicability", "no `__init__.py`"):
            self.assertIn(s, t)
        for private in ("wamid.", "pin offset", "owner account", "8,524 characters"):
            self.assertNotIn(private, t)
        self.assertIn(" ".join(self.m.__doc__.split('"')[1].split()), t)


# ---------------- mutation battery: probes each need to hold ----------------
def p_gate(m): return code(m, req(requested_by_owner=False)) == "PROTO_REFUSED_UNSOLICITED"
def p_gate_none(m): return code(m, req(requested_by_owner=1)) == "PROTO_REFUSED_UNSOLICITED"
def p_nospec(m): return code(m, req(ntype="x")) == "PROTO_REFUSED_NOSPEC:type"
def p_field_regex(m): return code(m, req(fields=["A"])) == "PROTO_REFUSED_BAD_TYPE:fields"
def p_field_inject(m): return code(m, req(fields=["a b"])) == "PROTO_REFUSED_BAD_TYPE:fields"
def p_field_anchor(m): return code(m, req(fields=["a\n"])) == "PROTO_REFUSED_BAD_TYPE:fields"
def p_id_regex(m): return code(m, req(id="../x")) == "PROTO_REFUSED_BAD_TYPE:id"
def p_ast_import(m): return m.scan_source("import os") != []
def p_ast_call(m): return m.scan_source("open('x','w')") != []
def p_ast_from(m): return m.scan_source("from urllib import request") != []
def p_ast_attr(m): return m.scan_source("x.system('ls')") != []
def p_ast_disabled(m): return m.scan_source("import subprocess") != []
def p_empty(m): return code(m, req(fields=[])) == "PROTO_REFUSED_EMPTY:fields"
def p_dup(m): return code(m, req(fields=["a", "a"])) == "PROTO_REFUSED_BAD_TYPE:fields"
def p_maxf(m): return code(m, req(fields=["f%d" % i for i in range(17)])) == "PROTO_REFUSED_BAD_TYPE:fields"
def p_spend(m): return code(m, req(description="buy data")) == "PROTO_REFUSED_SPEND"
def p_unsafe(m): return code(m, req(description="scrape it")) == "PROTO_REFUSED_UNSAFE:description"
def p_asof(m): return code(m, req(as_of="2026-99-99")) == "PROTO_REFUSED_BAD_TYPE:as_of"
def p_draft(m): return m.run(req())["draft"] is True
def p_keys(m):
    swapped = req(); swapped["extra"] = swapped.pop("as_of")  # same key count, wrong key
    return code(m, swapped) == "PROTO_REFUSED_BAD_TYPE:request" and code(m, dict(req(), extra=1)) == "PROTO_REFUSED_BAD_TYPE:request"
def p_desc_len(m): return code(m, req(description="x" * 501)) == "PROTO_REFUSED_TEXT_TOO_LONG:description"
def p_scorer_rounds(m):
    return "round(total, 6)" in m.run(req())["files"]["tool_n1.py"]
def p_files(m): return sorted(m.run(req())["files"]) == ["test_tool_n1.py", "tool_n1.py"]
def p_company_scope(m): return "monitoring companies" in m.run(req())["scope"]["not_implemented"]
def p_need_keys(m):
    swapped = req(); swapped["need"]["extra"] = swapped["need"].pop("id")
    return code(m, swapped) == "PROTO_REFUSED_BAD_TYPE:need"
def p_req_subclass(m): return code(m, SubDict(req())) == "PROTO_REFUSED_BAD_TYPE:request"
def p_need_subclass(m):
    r = req(); r["need"] = SubDict(r["need"])
    return code(m, r) == "PROTO_REFUSED_BAD_TYPE:need"
def p_fields_subclass(m):
    r = req(); r["need"]["fields"] = SubList(["a", "b"])
    return code(m, r) == "PROTO_REFUSED_BAD_TYPE:fields"
def p_ntype_subclass(m): return code(m, req(ntype=SubStr("scorer"))) == "PROTO_REFUSED_BAD_TYPE:type"
def p_field_subclass(m):
    r = req(); r["need"]["fields"] = ["a", SubStr("b")]
    return code(m, r) == "PROTO_REFUSED_BAD_TYPE:fields"
def p_req_subclass_key(m):
    r = req(); r[SubStr("need")] = r.pop("need")
    return code(m, r) == "PROTO_REFUSED_BAD_TYPE:request"
def p_need_subclass_key(m):
    r = req(); r["need"][SubStr("type")] = r["need"].pop("type")
    return code(m, r) == "PROTO_REFUSED_BAD_TYPE:need"

MUTANTS = [
    ("gate: `is not True` -> falsy check", 'request["requested_by_owner"] is not True', 'not request["requested_by_owner"]', p_gate_none),
    ("gate removed", 'if request["requested_by_owner"] is not True:\n        _refuse("UNSOLICITED")', "pass", p_gate),
    ("nospec removed", 'if ntype not in TYPES:\n        _refuse("NOSPEC", "type")', "pass", p_nospec),
    ("field regex off", "not FIELD_RE.fullmatch(f)", "False", p_field_regex),
    ("field regex loosened A-Z", 'FIELD_RE = re.compile(r"^[a-z_][a-z0-9_]*$")', 'FIELD_RE = re.compile(r"^[a-zA-Z_][a-z0-9_]*$")', p_field_regex),
    ("field regex allows space", 'r"^[a-z_][a-z0-9_]*$")\nID_RE', 'r"^[a-z_][a-z0-9_ ]*$")\nID_RE', p_field_inject),
    ("field regex fullmatch->match-anchor", 'FIELD_RE = re.compile(r"^[a-z_][a-z0-9_]*$")', 'FIELD_RE = re.compile(r"^[a-z_][a-z0-9_]*")', p_field_inject),
    ("field regex $ -> \\Z loses newline check", 'r"^[a-z_][a-z0-9_]*$")\nID_RE', 'r"^[a-z_][a-z0-9_]*")\nID_RE', p_field_anchor),
    ("id regex off", "not ID_RE.fullmatch(nid)", "False", p_id_regex),
    ("id regex loosened", 'ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")', 'ID_RE = re.compile(r"^[a-z./][a-z0-9_./]{0,31}$")', p_id_regex),
    ("ast: import check removed", 'if a.name.split(".")[0] not in ALLOWED_IMPORTS and not a.name.startswith("tool_"):', "if False:", p_ast_import),
    ("ast: from-import check removed", 'if node.level or (root not in ALLOWED_IMPORTS and not root.startswith("tool_")):', "if False:", p_ast_from),
    ("ast: banned calls removed", "if name in BANNED_CALLS:", "if False:", p_ast_call),
    ("ast: attr check removed", 'elif isinstance(node, ast.Attribute) and node.attr in {"system", "popen", "Popen", "urlopen", "connect"}:', "elif False:", p_ast_attr),
    ("ast: scan returns clean", "    return bad\n", "    return []\n", p_ast_disabled),
    ("ast: allowlist widened (os)", 'ALLOWED_IMPORTS = {"csv", "io", "unittest"}', 'ALLOWED_IMPORTS = {"csv", "io", "unittest", "os"}', p_ast_import),
    ("ast: emit-time scan skipped", "        try:\n            violations = scan_source(src)\n        except SyntaxError:\n            _refuse(\"UNSAFE\", name)\n        if violations:\n            _refuse(\"UNSAFE\", name)", "        pass", None),
    ("empty fields allowed", 'if not fields:\n        _refuse("EMPTY", "fields")', "pass", p_empty),
    ("dup fields allowed", "if len(set(fields)) != len(fields):", "if False:", p_dup),
    ("max fields off", "if len(fields) > MAX_FIELDS:", "if False:", p_maxf),
    ("spend check off", "if _SPEND_RE.search(desc):", "if False:", p_spend),
    ("unsafe check off", "if _UNSAFE_RE.search(desc):", "if False:", p_unsafe),
    ("as_of calendar off", "datetime.date.fromisoformat(as_of)", "pass", p_asof),
    ("draft false", '"draft": True', '"draft": False', p_draft),
    ("request set-allowlist removed", '    if set(request) != REQUEST_KEYS:\n        _refuse("BAD_TYPE", "request")', "    pass", p_keys),
    ("need set-allowlist removed", '    if set(need) != NEED_KEYS:\n        _refuse("BAD_TYPE", "need")', "    pass", p_need_keys),
    ("request exact-dict removed", '    if type(request) is not dict:\n        _refuse("BAD_TYPE", "request")', "    pass", p_req_subclass),
    ("need exact-dict removed", '    if type(need) is not dict:\n        _refuse("BAD_TYPE", "need")', "    pass", p_need_subclass),
    ("fields exact-list removed", '    if type(fields) is not list:\n        _refuse("BAD_TYPE", "fields")', "    pass", p_fields_subclass),
    ("ntype exact-str removed", '    if type(ntype) is not str:\n        _refuse("BAD_TYPE", "type")', "    pass", p_ntype_subclass),
    ("field exact-str -> isinstance", "if type(f) is not str or len(f) > MAX_FIELD_LEN", "if not isinstance(f, str) or len(f) > MAX_FIELD_LEN", p_field_subclass),
    ("request key-type removed", '    if any(type(key) is not str for key in request):\n        _refuse("BAD_TYPE", "request")', "    pass", p_req_subclass_key),
    ("need key-type removed", '    if any(type(key) is not str for key in need):\n        _refuse("BAD_TYPE", "need")', "    pass", p_need_subclass_key),
    ("desc limit", "MAX_DESC = 500", "MAX_DESC = 501", p_desc_len),
    ("scorer rounding dropped", "return round(total, 6)", "return total", p_scorer_rounds),
    ("files order/name", '"test_%s.py" % module_name', '"t_%s.py" % module_name', p_files),
    ("scope claim dropped", '"monitoring companies"', '"x"', p_company_scope),
]
# label -> justification. A survivor stays listed in the printed outcome; it is excluded from the
# failure check only with a written reason.
EQUIVALENT = {
    "field regex fullmatch->match-anchor": "run() uses FIELD_RE.fullmatch, which anchors both ends itself; dropping the trailing $ changes nothing observable",
    "field regex $ -> \\Z loses newline check": "same: the pattern's ^ and $ are redundant under fullmatch, so removing $ is equivalent",
}


class MutationBattery(unittest.TestCase):
    def test_baseline_probes_pass(self):
        m = load()
        for label, _, _, probe in MUTANTS:
            if probe:
                self.assertTrue(probe(m), probe.__name__)

    def test_every_mutant_outcome_is_recorded(self):
        src = SRC.read_text()
        outcomes = {}
        for n, (label, old, new, probe) in enumerate(MUTANTS):
            self.assertEqual(src.count(old), 1, "mutation anchor not unique: " + label)
            try:
                mutated = compile(src.replace(old, new), "mut", "exec")
            except SyntaxError:
                outcomes[label] = "non-compile"
                continue
            try:
                mod = load(src.replace(old, new), "c34_mut%d" % n)
            except Exception:
                outcomes[label] = "error-on-load"
                continue
            if probe is None:  # emit-time self-scan: must be killed by the end-to-end suite instead
                outcomes[label] = "see test_emit_time_scan_mutant"
                continue
            try:
                outcomes[label] = "SURVIVED" if probe(mod) else "killed"
            except Exception as e:
                outcomes[label] = "killed(error:%s)" % type(e).__name__
        survivors = [k for k, v in outcomes.items() if v == "SURVIVED" and k not in EQUIVALENT]
        self.assertEqual(survivors, [], outcomes)
        killed = sum(1 for v in outcomes.values() if v.startswith("killed"))
        raw = [k for k, v in outcomes.items() if v == "SURVIVED"]
        print("\nS3.3 mutants: total=%d killed=%d survived=%d (equivalent, justified=%d) unresolved=%d other=%s" %
              (len(outcomes), killed, len(raw), len(raw) - len(survivors), len(survivors),
               sorted({v for v in outcomes.values() if not v.startswith("killed") and v != "SURVIVED"})))
        for k, v in sorted(outcomes.items()):
            print("  %-45s %s" % (k, v))

    def test_emit_time_scan_mutant(self):
        # With the emit-time self-scan removed, a template poisoned with a banned import would still ship.
        src = SRC.read_text()
        old = "        try:\n            violations = scan_source(src)\n        except SyntaxError:\n            _refuse(\"UNSAFE\", name)\n        if violations:\n            _refuse(\"UNSAFE\", name)"
        poisoned = src.replace('_MODULES = {\n    "csv_transform": \'\'\'import csv', '_MODULES = {\n    "csv_transform": \'\'\'import os\nimport csv', 1)
        self.assertNotEqual(poisoned, src)
        with_scan = load(poisoned, "c34_poison1")
        self.assertEqual(code(with_scan, req("csv_transform")), "PROTO_REFUSED_UNSAFE:tool_n1.py")
        without = load(poisoned.replace(old, "        pass"), "c34_poison2")
        self.assertIsNone(code(without, req("csv_transform")))  # the scan is what stops it

class RepairPins(unittest.TestCase):
    """S3.3 repair: company text must never become emitted code; audit pins."""

    def setUp(self):
        self.m = load()

    def test_company_triple_quote_cannot_become_code(self):
        evil = 'x""";print(().__class__.__bases__[0].__subclasses__());"""'
        for t in self.m.TYPES:
            try:
                out = self.m.run(req(t, company=evil))
            except ValueError as e:
                self.assertTrue(str(e).startswith("PROTO_REFUSED_"), str(e))
                continue
            for name, src in out["files"].items():
                tree = ast.parse(src)
                calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
                self.assertNotIn("print", [c.func.id for c in calls if isinstance(c.func, ast.Name)], (t, name))
                self.assertNotIn("__subclasses__", src.split("COMPANY =")[0], (t, name))
                self.assertEqual(self.m.scan_source(src), [])
            mod_src = out["files"]["tool_n1.py"]
            ns = {}
            exec(compile(mod_src, "gen", "exec"), ns)
            self.assertEqual(ns["COMPANY"], evil)

    def test_company_head_holds_only_a_docstring(self):
        for company in ('a"""b', "a\\", 'q"""\\"""', "it's \"x\" ok"):
            out = self.m.run(req("scorer", company=company))
            tree = ast.parse(out["files"]["tool_n1.py"])
            self.assertIsInstance(tree.body[0].value, ast.Constant)
            self.assertNotIn(company, tree.body[0].value.value)
            ns = {}
            exec(compile(out["files"]["tool_n1.py"], "gen", "exec"), ns)
            self.assertEqual(ns["COMPANY"], company)

    def test_syntax_error_in_emitted_code_is_a_refusal_not_a_crash(self):
        src = SRC.read_text()
        broken = src.replace("_HEAD = '\"\"\"DRAFT", "_HEAD = '\"\"\"\"DRAFT", 1)
        self.assertNotEqual(broken, src)
        broken = broken.replace("(%(type)s). Review", "(%(type)s) \"\"\" Review", 1)
        mod = load(broken, "c34_synerr")
        self.assertEqual(code(mod, req("scorer")), "PROTO_REFUSED_UNSAFE:tool_n1.py")

    def test_need_list_or_none_is_bad_type(self):
        for v in ([], ["id", "type", "description", "fields"], None, "x", 3):
            self.assertEqual(code(self.m, req(need=v)), "PROTO_REFUSED_BAD_TYPE:need", repr(v))

    def test_as_of_eleven_chars_is_too_long(self):
        self.assertEqual(code(self.m, req(as_of="2026-10-111")), "PROTO_REFUSED_TEXT_TOO_LONG:as_of")
        self.assertEqual(code(self.m, req(as_of="2026-1-011")), "PROTO_REFUSED_BAD_TYPE:as_of")

    def test_company_length_boundary_128_129(self):
        self.assertIsNone(code(self.m, req(company="c" * 128)))
        self.assertEqual(code(self.m, req(company="c" * 129)), "PROTO_REFUSED_TEXT_TOO_LONG:company")

    def test_emitted_test_class_is_Test_CamelId(self):
        for nid, cls in (("n1", "TestN1"), ("my_tool_x", "TestMyToolX")):
            r = req("scorer")
            r["need"]["id"] = nid
            src = self.m.run(r)["files"]["test_tool_%s.py" % nid]
            names = [n.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ClassDef)]
            self.assertEqual(names, [cls])

    def test_result_unit_is_S33(self):
        self.assertEqual(self.m.run(req())["unit"], "S3.3")

    def test_scan_refuses_relative_and_dotted_allowed_last_part(self):
        for bad in ("from .csv import x", "from ..io import x", "from os.csv import x", "from os.path.io import x",
                    "import os.csv", "import a.unittest", "from . import csv"):
            self.assertTrue(self.m.scan_source(bad), bad)
        for good in ("import csv.x", "from io import StringIO", "from unittest import TestCase"):
            self.assertEqual(self.m.scan_source(good), [], good)

    def test_scan_violation_text_is_exact(self):
        self.assertEqual(self.m.scan_source("from os.csv import x"), ["from:os.csv"])
        self.assertEqual(self.m.scan_source("from . import csv"), ["from:."])
        self.assertEqual(self.m.scan_source("import os.csv"), ["import:os.csv"])

class OrderPins(unittest.TestCase):
    """Cheap bounds run before any content-dependent work (count first, cap first)."""

    def setUp(self):
        self.m = load()

    def test_request_count_checked_before_key_set_is_built(self):
        class Boom(dict):
            def __iter__(self):
                raise AssertionError("key set built before count check")
        wrong = Boom({k: 1 for k in ("as_of", "requested_by_owner", "company", "need", "extra")})
        self.assertEqual(code(self.m, wrong), "PROTO_REFUSED_BAD_TYPE:request")
        self.assertEqual(code(self.m, Boom()), "PROTO_REFUSED_BAD_TYPE:request")

    def test_need_count_checked_before_key_set_is_built(self):
        class Boom(dict):
            def __iter__(self):
                raise AssertionError("key set built before count check")
        r = req()
        r["need"] = Boom({"id": 1, "type": 1, "description": 1, "fields": 1, "x": 1})
        self.assertEqual(code(self.m, r), "PROTO_REFUSED_BAD_TYPE:need")

    def test_type_length_cap_before_membership(self):
        seen = []

        class Spy(tuple):
            def __contains__(self, item):
                seen.append(item)
                return tuple.__contains__(self, item)
        self.m.TYPES = Spy(self.m.TYPES)
        self.assertEqual(code(self.m, req(type="t" * 33)), "PROTO_REFUSED_BAD_TYPE:type")
        self.assertEqual(seen, [])
        self.assertEqual(code(self.m, req(type="nope")), "PROTO_REFUSED_NOSPEC:type")
        self.assertEqual(seen, ["nope"])
        self.assertEqual(code(self.m, req(type="t" * 32)), "PROTO_REFUSED_NOSPEC:type")

    def test_field_length_cap_before_regex(self):
        calls = []

        class Spy:
            def __init__(self, rx):
                self.rx = rx

            def fullmatch(self, s):
                calls.append(len(s))
                return self.rx.fullmatch(s)
        self.m.FIELD_RE = Spy(self.m.FIELD_RE)
        self.assertEqual(code(self.m, req(fields=["a" * 65])), "PROTO_REFUSED_BAD_TYPE:fields")
        self.assertEqual(calls, [])
        self.assertIsNone(code(self.m, req(fields=["a" * 64])))
        self.assertEqual(calls, [64])


if __name__ == "__main__":
    unittest.main()


class SubDict(dict):
    pass

class SubList(list):
    pass

class SubStr(str):
    pass

class HostileStr(str):
    armed = False
    def __hash__(self):
        if HostileStr.armed:
            raise RuntimeError("hash invoked - SET built before key-type check")
        return super().__hash__()
    def __eq__(self, other):
        if HostileStr.armed:
            raise RuntimeError("eq invoked - SET built before key-type check")
        return str.__eq__(self, other)


class StrictBoundary(unittest.TestCase):
    """Strict caller-validation pins: exact built-in types, strict key-type, ordering."""

    def setUp(self):
        self.m = load()

    def err(self, r):
        with self.assertRaises(ValueError) as cm:
            self.m.run(r)
        return str(cm.exception)

    def test_subclass_containers_refused(self):
        self.assertEqual(self.err(SubDict(req())), "PROTO_REFUSED_BAD_TYPE:request")
        r = req(); r["need"] = SubDict(r["need"])
        self.assertEqual(self.err(r), "PROTO_REFUSED_BAD_TYPE:need")
        r = req(); r["need"]["fields"] = SubList(["a", "b"])
        self.assertEqual(self.err(r), "PROTO_REFUSED_BAD_TYPE:fields")

    def test_subclass_strings_refused(self):
        self.assertEqual(self.err(req(ntype=SubStr("scorer"))), "PROTO_REFUSED_BAD_TYPE:type")
        r = req(); r["need"]["fields"] = ["a", SubStr("b")]
        self.assertEqual(self.err(r), "PROTO_REFUSED_BAD_TYPE:fields")

    def test_str_subclass_keys_refused_both_levels(self):
        r = req()
        r[SubStr("need")] = r.pop("need")
        self.assertEqual(self.err(r), "PROTO_REFUSED_BAD_TYPE:request")
        r = req()
        r["need"][SubStr("type")] = r["need"].pop("type")
        self.assertEqual(self.err(r), "PROTO_REFUSED_BAD_TYPE:need")

    def test_non_str_keys_refused_both_levels(self):
        r = req(); r[7] = r.pop("company")
        self.assertEqual(self.err(r), "PROTO_REFUSED_BAD_TYPE:request")
        r = req(); r["need"][7] = r["need"].pop("id")
        self.assertEqual(self.err(r), "PROTO_REFUSED_BAD_TYPE:need")

    def test_ordering_count_before_keytype_before_set(self):
        # wrong count: refuses before touching hostile keys at all
        r = req(); r["extra"] = 1
        r[HostileStr("zz")] = r.pop("company")  # 6 keys now
        HostileStr.armed = True
        try:
            self.assertEqual(self.err(r), "PROTO_REFUSED_BAD_TYPE:request")
        finally:
            HostileStr.armed = False
        # right count, hostile allowed-name key: key-type check fires before SET
        r = req()
        r[HostileStr("need")] = r.pop("need")
        r2 = req()
        r2["need"][HostileStr("type")] = r2["need"].pop("type")
        HostileStr.armed = True
        try:
            self.assertEqual(self.err(r), "PROTO_REFUSED_BAD_TYPE:request")
            self.assertEqual(self.err(r2), "PROTO_REFUSED_BAD_TYPE:need")
        finally:
            HostileStr.armed = False
