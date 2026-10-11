"""Row 707 Naming Conventions: bounded AST identifier inspection against explicit rules.

Stdlib only. The module under test is loaded by file path so these tests do not
need the web framework that the package __init__ imports.
"""
import ast
import hashlib
import importlib.util
import itertools
import json
import os
import random
import re
import unittest

_CORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend", "app",
                     "modules", "m20_general_cognitive_worker", "naming_checker707.py")


def load():
    spec = importlib.util.spec_from_file_location("naming_checker707_under_test", _CORE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


N = load()
ALL_KINDS = ["function", "method", "class", "parameter", "local", "module_variable",
             "class_attribute", "import_alias"]


def rule(rid, kinds, style, **kw):
    return {"id": rid, "kinds": kinds, "style": style, **kw}


def rules(*rs, **kw):
    return {"rules": list(rs), **kw}


def col(src, line, name, nth=0):
    """1-based code-point column of the nth occurrence of name on a 1-based line."""
    text = src.split("\n")[line - 1]
    i = -1
    for _ in range(nth + 1):
        i = text.index(name, i + 1)
    return i + 1


def tup(f):
    return (f["line"], f["col"], f["rule_id"], f["kind"], f["name"], f["reason"])


def findings(src, rs):
    return [tup(f) for f in N.check_naming(src, rs)["findings"]]


def refusal(src, rs):
    try:
        N.check_naming(src, rs)
    except N.NamingRefusal as exc:
        return exc
    raise AssertionError("expected NamingRefusal")


STD = rules(
    rule("F", ["function", "method", "parameter", "local", "module_variable", "class_attribute"], "snake_case"),
    rule("C", ["class"], "PascalCase"),
    rule("A", ["import_alias"], "snake_case"),
)


class Symbols(unittest.TestCase):
    def test_every_symbol_kind_exact_positions_and_rule_ids(self):
        src = (
            "import os as OsMod\n"
            "from sys import path as PathAlias\n"
            "BadVar = 1\n"
            "def BadFunc(Arg, *VarArgs, kw_ok=1, **KwArgs):\n"
            "    LocalX = Arg\n"
            "    for Item in []:\n"
            "        pass\n"
            "    return LocalX\n"
            "class bad_class:\n"
            "    ClassAttr = 1\n"
            "    def BadMethod(self):\n"
            "        pass\n"
        )
        got = findings(src, STD)
        sm = "style_mismatch"
        self.assertEqual(got, [
            (1, col(src, 1, "OsMod"), "A", "import_alias", "OsMod", sm),
            (2, col(src, 2, "PathAlias"), "A", "import_alias", "PathAlias", sm),
            (3, 1, "F", "module_variable", "BadVar", sm),
            (4, col(src, 4, "BadFunc"), "F", "function", "BadFunc", sm),
            (4, col(src, 4, "Arg"), "F", "parameter", "Arg", sm),
            (4, col(src, 4, "VarArgs"), "F", "parameter", "VarArgs", sm),
            (4, col(src, 4, "KwArgs"), "F", "parameter", "KwArgs", sm),
            (5, 5, "F", "local", "LocalX", sm),
            (6, 9, "F", "local", "Item", sm),
            (9, col(src, 9, "bad_class"), "C", "class", "bad_class", sm),
            (10, 5, "F", "class_attribute", "ClassAttr", sm),
            (11, col(src, 11, "BadMethod"), "F", "method", "BadMethod", sm),
        ])

    def test_end_columns_and_clean_source(self):
        res = N.check_naming("def Bad(): pass\n", STD)
        f = res["findings"][0]
        self.assertEqual((f["line"], f["col"], f["end_line"], f["end_col"]), (1, 5, 1, 8))
        clean = N.check_naming("def ok_name(a_b):\n    c_d = a_b\n    return c_d\n", STD)
        self.assertEqual(clean["findings"], [])
        self.assertTrue(clean["compliant"])
        self.assertEqual(clean["checked_count"], 3)

    def test_kinds_not_covered_by_a_rule_are_not_reported(self):
        only_funcs = rules(rule("F", ["function"], "snake_case"))
        self.assertEqual(findings("class BadName:\n    X = 1\ndef Bad(): pass\n", only_funcs),
                         [(3, 5, "F", "function", "Bad", "style_mismatch")])

    def test_scope_filter_and_rebinding_first_binding_only(self):
        rs = rules(rule("M", ["module_variable"], "UPPER_SNAKE"))
        self.assertEqual(findings("lower = 1\nlower = 2\n", rs),
                         [(1, 1, "M", "module_variable", "lower", "style_mismatch")])
        rs2 = rules(rule("L", ["local"], "snake_case", scope="function"))
        self.assertEqual(findings("def f():\n    Bad = 1\n    Bad = 2\n", rs2),
                         [(2, 5, "L", "local", "Bad", "style_mismatch")])

    def test_comprehension_lambda_walrus_except_with(self):
        rs = rules(rule("F", ["local", "parameter", "module_variable"], "snake_case"))
        src = (
            "Q = [Bx for Bx in range(3)]\n"
            "f = lambda Zed: Zed\n"
            "def g():\n"
            "    if (Walrus := 1):\n"
            "        pass\n"
            "    try:\n"
            "        pass\n"
            "    except ValueError as Err:\n"
            "        pass\n"
            "    with open('x') as FileH:\n"
            "        pass\n"
        )
        got = findings(src, rs)
        sm = "style_mismatch"
        self.assertEqual(got, [
            (1, 1, "F", "module_variable", "Q", sm),
            (1, col(src, 1, "Bx", 1), "F", "local", "Bx", sm),
            (2, col(src, 2, "Zed"), "F", "parameter", "Zed", sm),
            (4, col(src, 4, "Walrus"), "F", "local", "Walrus", sm),
            (8, col(src, 8, "Err", 1), "F", "local", "Err", sm),
            (10, col(src, 10, "FileH"), "F", "local", "FileH", sm),
        ])

    def test_comprehension_walrus_binds_in_enclosing_scope(self):
        rs = rules(rule("M", ["module_variable"], "snake_case"))
        src = "z = []\nr = [x for x in z if (Bad := x)]\n"
        self.assertEqual(findings(src, rs), [(2, col(src, 2, "Bad"), "M", "module_variable", "Bad", "style_mismatch")])

    def test_global_declaration_is_not_a_local_binding(self):
        rs = rules(rule("L", ["local"], "snake_case"))
        self.assertEqual(findings("def f():\n    global Gx\n    Gx = 1\n", rs), [])

    def test_unrenamed_imports_and_attribute_targets_are_not_inspected(self):
        rs = rules(rule("A", ["import_alias"], "snake_case"), rule("M", ["module_variable"], "snake_case"))
        res = N.check_naming("import OsX\nfrom a import B\nobj.Attr = 1\n", rs)
        self.assertEqual(res["findings"], [])
        self.assertEqual(res["checked_count"], 0)


class Unicode(unittest.TestCase):
    def test_columns_are_code_points_not_bytes_or_utf16(self):
        src = 's = "\U0001F600\u00e9"; BadName = 2\n'
        col = src.index("BadName") + 1
        self.assertNotEqual(col, len(src.encode()[: src.encode().index(b"BadName")]) + 1)
        got = findings(src, STD)
        self.assertEqual(got, [(1, col, "F", "module_variable", "BadName", "style_mismatch")])

    def test_non_ascii_identifiers(self):
        src = "def \u00fcber_ok(): pass\ndef \u00dcberBad(): pass\n\u53d8\u91cf = 1\n"
        self.assertEqual(findings(src, STD), [(2, 5, "F", "function", "\u00dcberBad", "style_mismatch")])
        res = N.check_naming(src, STD)
        self.assertEqual(res["findings"][0]["end_col"] - res["findings"][0]["col"], len("\u00dcberBad"))

    def test_crlf_cr_and_formfeed_line_numbers_follow_python(self):
        src = "x = 1\r\ndef Bad(): pass\rdef Bad2(): pass\n\x0cdef Bad3(): pass\n"
        got = [(l, c, n) for (l, c, _, _, n, _) in findings(src, STD)]
        self.assertEqual(got, [(2, 5, "Bad"), (3, 5, "Bad2"), (4, 6, "Bad3")])

    def test_nfkc_normalized_source_text_is_reported_verbatim(self):
        src = "def \uff22ad(): pass\n"  # fullwidth B, Python normalizes to B
        got = N.check_naming(src, STD)["findings"]
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["name"], "\uff22ad")
        self.assertEqual(got[0]["end_col"] - got[0]["col"], 3)


class Underscores(unittest.TestCase):
    def test_leading_trailing_dunder_placeholder(self):
        rs = rules(rule("F", ["function", "local"], "snake_case"))
        src = "def _priv(): pass\ndef __mangle(): pass\ndef trail_(): pass\ndef __init__(): pass\ndef ___triple(): pass\ndef _(): pass\ndef __(): pass\n"
        self.assertEqual(findings(src, rs), [
            (1, 5, "F", "function", "_priv", "leading_underscore"),
            (2, 5, "F", "function", "__mangle", "leading_underscore"),
            (3, 5, "F", "function", "trail_", "trailing_underscore"),
            (4, 5, "F", "function", "__init__", "dunder"),
            (5, 5, "F", "function", "___triple", "leading_underscore"),
            (7, 5, "F", "function", "__", "no_letters"),
        ])
        res = N.check_naming(src, rs)
        self.assertEqual(res["exempt_count"], 1)

    def test_allow_options(self):
        rs = rules(rule("F", ["function"], "snake_case", allow_leading_underscore=True,
                        allow_trailing_underscore=True, dunder="exempt"))
        src = "def _priv(): pass\ndef __mangle(): pass\ndef trail_(): pass\ndef __init__(): pass\ndef ___triple(): pass\ndef _Bad(): pass\n"
        self.assertEqual(findings(src, rs), [
            (5, 5, "F", "function", "___triple", "leading_underscore"),
            (6, 5, "F", "function", "_Bad", "style_mismatch"),
        ])

    def test_dunder_requires_both_ends_and_length(self):
        rs = rules(rule("F", ["function"], "snake_case"))
        self.assertEqual(findings("def __a__(): pass\n", rs), [(1, 5, "F", "function", "__a__", "dunder")])
        self.assertEqual(findings("def ____(): pass\n", rs), [(1, 5, "F", "function", "____", "no_letters")])


class Acronyms(unittest.TestCase):
    def test_declared_and_undeclared_acronyms(self):
        rs = rules(rule("C", ["class"], "PascalCase", acronyms=["HTTP", "IO"]))
        src = "class HTTPServer: pass\nclass IOError2: pass\nclass XMLParser: pass\nclass UserID: pass\nclass Abc: pass\n"
        res = N.check_naming(src, rs)
        self.assertEqual([tup(f) for f in res["findings"]], [
            (3, 7, "C", "class", "XMLParser", "undeclared_acronym"),
            (4, 7, "C", "class", "UserID", "undeclared_acronym"),
        ])
        self.assertEqual([f["detail"] for f in res["findings"]], ["XML", "ID"])

    def test_top_level_acronyms_apply_to_all_rules_and_camel(self):
        rs = rules(rule("F", ["function"], "camelCase"), rule("C", ["class"], "PascalCase"), acronyms=["URL"])
        src = "def parseURLNow(): pass\ndef parseXMLNow(): pass\nclass URLThing: pass\ndef Upper(): pass\n"
        self.assertEqual(findings(src, rs), [
            (2, 5, "F", "function", "parseXMLNow", "undeclared_acronym"),
            (4, 5, "F", "function", "Upper", "style_mismatch"),
        ])

    def test_acronym_followed_by_digit_and_pair_followed_by_lower(self):
        rs = rules(rule("C", ["class"], "PascalCase", acronyms=["HTTP"]))
        self.assertEqual(findings("class HTTP2Server: pass\nclass ABc: pass\nclass ABCd: pass\n", rs),
                         [(3, 7, "C", "class", "ABCd", "undeclared_acronym")])

    def test_snake_and_upper_styles_ignore_acronym_declarations(self):
        rs = rules(rule("F", ["function"], "snake_case"), rule("M", ["module_variable"], "UPPER_SNAKE"), acronyms=["HTTP"])
        self.assertEqual(findings("def http_get(): pass\nMAX_HTTP = 1\nmax_http = 2\n", rs),
                         [(3, 1, "M", "module_variable", "max_http", "style_mismatch")])


class Shadowing(unittest.TestCase):
    def test_shadowing_reported_when_enabled(self):
        rs = rules(rule("F", ["function", "parameter", "local"], "snake_case"), forbid_shadowing=True)
        src = (
            "value = 1\n"
            "def outer(x):\n"
            "    inner = 2\n"
            "    def deep(value, inner):\n"
            "        x = 3\n"
            "        return value\n"
            "    return deep\n"
        )
        got = [(l, c, r, k, n, why) for (l, c, r, k, n, why) in findings(src, rs)]
        self.assertEqual(got, [
            (4, 14, "SHADOW", "parameter", "value", "shadows_enclosing"),
            (4, 21, "SHADOW", "parameter", "inner", "shadows_enclosing"),
            (5, 9, "SHADOW", "local", "x", "shadows_enclosing"),
        ])
        res = N.check_naming(src, rs)
        self.assertEqual([f["detail"] for f in res["findings"]], ["line 1", "line 3", "line 2"])

    def test_findings_at_one_position_sort_by_rule_id(self):
        rs = rules(rule("T", ["parameter"], "PascalCase"), rule("A", ["parameter"], "PascalCase"), forbid_shadowing=True)
        got = [f["rule_id"] for f in N.check_naming("v = 1\ndef f(v): pass\n", rs)["findings"]]
        self.assertEqual(got, ["A", "SHADOW", "T"])

    def test_class_scope_names_do_not_shadow_and_off_by_default(self):
        rs = rules(rule("F", ["parameter", "local"], "snake_case"), forbid_shadowing=True)
        self.assertEqual(findings("class K:\n    a = 1\n    def m(self):\n        a = 2\n", rs), [])
        rs_off = rules(rule("F", ["parameter", "local"], "snake_case"))
        self.assertEqual(findings("v = 1\ndef f(v): pass\n", rs_off), [])

    def test_placeholder_and_global_are_not_shadowing(self):
        rs = rules(rule("F", ["local"], "snake_case"), forbid_shadowing=True)
        self.assertEqual(findings("_ = 1\ng = 1\ndef f():\n    global g\n    g = 2\n    _ = 3\n", rs), [])


class Refusals(unittest.TestCase):
    def test_syntax_error_refused_with_position(self):
        exc = refusal("def f(:\n", STD)
        self.assertEqual(exc.code, "syntax_error")
        self.assertEqual(exc.detail["line"], 1)
        self.assertEqual(str(exc), "source is not valid Python syntax at line 1")

    def test_deep_nesting_refused(self):
        exc = refusal("x = " + "(" * 500 + "1" + ")" * 500 + "\n", STD)
        self.assertIn(exc.code, ("syntax_error", "resource_limit"))

    def test_very_deep_expression_is_refused_not_crashed(self):
        exc = refusal("x = a" + "+a" * 3000 + "\n", STD)
        self.assertEqual(exc.code, "resource_limit")
        self.assertEqual(str(exc), "source nesting exceeds analysis limits")

    def test_null_byte_and_type_errors(self):
        self.assertEqual(refusal("x = 1\x00\n", STD).code, "invalid_source")
        for bad in (None, 5, b"x=1"):
            exc = refusal(bad, STD)
            self.assertEqual((exc.code, str(exc)), ("invalid_source", "source must be str"))

    def test_source_size_bounds_exact(self):
        n = N.MAX_SOURCE_BYTES
        self.assertEqual(n, 262144)
        ok = "#" * (n - 1) + "\n"
        self.assertEqual(len(ok.encode()), n)
        self.assertTrue(N.check_naming(ok, STD)["compliant"])
        over = "#" * n + "\n"
        exc = refusal(over, STD)
        self.assertEqual((exc.code, str(exc)), ("resource_limit", "source is 262145 bytes, limit is 262144"))
        multibyte = "#" + "\u00e9" * 131071 + "\n"  # 1+262142+1 = 262144 bytes
        self.assertEqual(len(multibyte.encode()), n)
        self.assertTrue(N.check_naming(multibyte, STD)["compliant"])
        self.assertEqual(refusal(multibyte + "#", STD).code, "resource_limit")

    def test_node_count_bounds_exact(self):
        limit = N.MAX_NODES
        self.assertEqual(limit, 20000)
        at = "pass\n" * (limit - 1)
        self.assertEqual(sum(1 for _ in ast.walk(ast.parse(at))), limit)
        self.assertTrue(N.check_naming(at, STD)["compliant"])
        over = "pass\n" * limit
        self.assertEqual(sum(1 for _ in ast.walk(ast.parse(over))), limit + 1)
        exc = refusal(over, STD)
        self.assertEqual((exc.code, str(exc)), ("resource_limit", "source has 20001 syntax nodes, limit is 20000"))

    def test_source_is_never_executed_or_imported(self):
        marker = os.path.join(os.path.dirname(_CORE), "..", "..", "..", "..", "naming707_marker.txt")
        src = "import os\nopen(%r, 'w').write('x')\n__import__('sys').exit(3)\n" % marker
        N.check_naming(src, STD)
        self.assertFalse(os.path.exists(marker))


class RuleErrors(unittest.TestCase):
    def err(self, rs):
        exc = refusal("x = 1\n", rs)
        self.assertEqual(exc.code, "invalid_rules")
        return str(exc)

    def test_exact_messages_for_fresh_unknown_ids(self):
        self.assertEqual(self.err(rules(rule("R1", ["widget"], "snake_case"))),
                         "rule 'R1' has unknown kind 'widget'")
        self.assertEqual(self.err(rules(rule("R1", ["local"], "kebab-case"))),
                         "rule 'R1' has unknown style 'kebab-case'")
        self.assertEqual(self.err(rules(rule("R1", ["local"], "snake_case"), rule("R1", ["local"], "camelCase"))),
                         "duplicate rule id 'R1'")
        self.assertEqual(self.err(rules(rule("R1", ["local"], "snake_case", scope="galaxy"))),
                         "rule 'R1' has unknown scope 'galaxy'")
        self.assertEqual(self.err(rules(rule("R1", ["local"], "snake_case", flavor=1))),
                         "rule 'R1' has unknown key 'flavor'")
        self.assertEqual(self.err({"rules": [rule("R1", ["local"], "snake_case")], "mystery": 1}),
                         "rules has unknown key 'mystery'")
        self.assertEqual(self.err(rules(rule("SHADOW", ["local"], "snake_case"))),
                         "rule id 'SHADOW' is reserved")

    def test_missing_and_mistyped_fields(self):
        self.assertEqual(self.err({"rules": []}), "rules must be a non-empty list")
        self.assertEqual(self.err({}), "rules must be a non-empty list")
        self.assertEqual(self.err([1]), "rules must be a dict")
        self.assertEqual(self.err(rules({"kinds": ["local"], "style": "snake_case"})), "rule #1 is missing 'id'")
        self.assertEqual(self.err(rules({"id": "R", "style": "snake_case"})), "rule 'R' is missing 'kinds'")
        self.assertEqual(self.err(rules({"id": "R", "kinds": ["local"]})), "rule 'R' is missing 'style'")
        self.assertEqual(self.err(rules(rule("R", [], "snake_case"))), "rule 'R' kinds must be a non-empty list")
        self.assertEqual(self.err(rules(rule("R", ["local", "local"], "snake_case"))),
                         "rule 'R' has duplicate kind 'local'")
        self.assertEqual(self.err(rules(rule("", ["local"], "snake_case"))), "rule #1 id must be a non-empty str")
        self.assertEqual(self.err(rules(rule("R", ["local"], "snake_case", allow_leading_underscore=1))),
                         "rule 'R' allow_leading_underscore must be bool")
        self.assertEqual(self.err(rules(rule("R", ["local"], "snake_case", dunder="maybe"))),
                         "rule 'R' dunder must be 'flag' or 'exempt'")
        self.assertEqual(self.err(rules(rule("R", ["local"], "snake_case"), forbid_shadowing="yes")),
                         "forbid_shadowing must be bool")
        self.assertEqual(self.err(rules(rule("R", ["local"], "PascalCase", acronyms=["http"]))),
                         "rule 'R' has invalid acronym 'http'")
        self.assertEqual(self.err(rules(rule("R", ["local"], "PascalCase"), acronyms=["A"])),
                         "rules has invalid acronym 'A'")
        self.assertEqual(self.err(rules(rule("R", ["local"], "PascalCase", acronyms="HTTP"))),
                         "rule 'R' acronyms must be a list")

    def test_rule_count_bounds_exact(self):
        self.assertEqual(N.MAX_RULES, 32)
        mk = lambda n: rules(*[rule("R%d" % i, ["local"], "snake_case") for i in range(n)])
        self.assertTrue(N.check_naming("x = 1\n", mk(32))["compliant"])
        self.assertEqual(self.err(mk(33)), "rules has 33 entries, limit is 32")

    def test_acronym_count_bounds_exact(self):
        self.assertEqual(N.MAX_ACRONYMS, 64)
        names = ["XY" + chr(65 + i // 26) + chr(65 + i % 26) for i in range(65)]
        ok = rules(rule("R", ["local"], "PascalCase"), acronyms=names[:64])
        self.assertTrue(N.check_naming("x = 1\n", ok)["compliant"])
        bad = rules(rule("R", ["local"], "PascalCase"), acronyms=names[:65])
        self.assertEqual(self.err(bad), "rules has 65 acronyms, limit is 64")
        dup = rules(rule("R", ["local"], "PascalCase"), acronyms=["HTTP", "HTTP"])
        self.assertEqual(self.err(dup), "rules has duplicate acronym 'HTTP'")

    def test_rule_id_length_bounds_exact(self):
        self.assertEqual(N.MAX_ID_LEN, 64)
        self.assertTrue(N.check_naming("x = 1\n", rules(rule("r" * 64, ["local"], "snake_case")))["compliant"])
        self.assertEqual(self.err(rules(rule("r" * 65, ["local"], "snake_case"))),
                         "rule #1 id is 65 characters, limit is 64")


class Determinism(unittest.TestCase):
    SRC = "import os as OsMod\nBadVar = 1\ndef BadFunc(Arg):\n    return HTTPThing\nclass bad:\n    pass\n"

    def test_input_order_of_rules_kinds_and_acronyms_does_not_change_output(self):
        base_rules = [rule("F", ["function", "parameter", "module_variable"], "snake_case"),
                      rule("C", ["class"], "PascalCase", acronyms=["HTTP", "IO"]),
                      rule("A", ["import_alias"], "snake_case"),
                      rule("U", ["module_variable"], "UPPER_SNAKE")]
        want = json.dumps(N.check_naming(self.SRC, {"rules": base_rules, "acronyms": ["URL", "XML"]}), sort_keys=False)
        rng = random.Random(7)
        for _ in range(25):
            rs = [dict(r, kinds=rng.sample(r["kinds"], len(r["kinds"]))) for r in base_rules]
            for r in rs:
                if "acronyms" in r:
                    r["acronyms"] = rng.sample(r["acronyms"], len(r["acronyms"]))
            rng.shuffle(rs)
            got = json.dumps(N.check_naming(self.SRC, {"acronyms": rng.sample(["URL", "XML"], 2), "rules": rs}), sort_keys=False)
            self.assertEqual(got, want)

    def test_findings_sorted_and_repeatable_and_input_not_mutated(self):
        rs = {"rules": [rule("F", ["function", "local"], "snake_case"), rule("G", ["function"], "UPPER_SNAKE")]}
        import copy
        before = copy.deepcopy(rs)
        a = N.check_naming(self.SRC + "def ZZ(): pass\n", rs)
        b = N.check_naming(self.SRC + "def ZZ(): pass\n", rs)
        self.assertEqual(a, b)
        self.assertEqual(rs, before)
        keys = [(f["line"], f["col"], f["rule_id"]) for f in a["findings"]]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(a["source_sha256"], hashlib.sha256((self.SRC + "def ZZ(): pass\n").encode()).hexdigest())

    def test_declaration_order_in_source_does_not_change_set_of_findings(self):
        blocks = ["def Aa(): pass\n", "class bb: pass\n", "Cc = 1\n"]
        seen = set()
        for perm in itertools.permutations(blocks):
            res = N.check_naming("".join(perm), STD)
            seen.add(frozenset((f["name"], f["rule_id"], f["reason"]) for f in res["findings"]))
        self.assertEqual(len(seen), 1)


class Report(unittest.TestCase):
    def test_report_shape_and_statements(self):
        res = N.check_naming("def Bad(): pass\n", STD)
        self.assertEqual(res["schema"], "naming707/1")
        self.assertEqual(res["rules_applied"], ["A", "C", "F"])
        self.assertIs(res["style_inferred"], False)
        self.assertIs(res["compliant"], False)
        self.assertEqual(res["position_unit"], "1-based line; 1-based column in Unicode code points; end_col exclusive")
        self.assertIn("match_patterns", res["not_inspected"])
        self.assertIn("attribute_targets", res["not_inspected"])
        self.assertEqual(res["checked"][0]["rule_ids"], ["F"])
        self.assertNotIn("proves", json.dumps(res).lower())


def oracle_ok(name, style, allow_lead, allow_trail, dunder):
    if name == "_":
        return True
    if len(name) > 4 and name.startswith("__") and name.endswith("__"):
        return dunder == "exempt"
    core = name
    lead = len(core) - len(core.lstrip("_"))
    if lead:
        if not allow_lead or lead > 2:
            return False
        core = core.lstrip("_")
    if core.endswith("_"):
        if not allow_trail:
            return False
        core = core[:-1]
        if core.endswith("_"):
            return False
    if not core:
        return False
    if style == "snake_case":
        return re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", core) is not None
    if style == "UPPER_SNAKE":
        return re.fullmatch(r"[A-Z0-9]+(?:_[A-Z0-9]+)*", core) is not None
    if "_" in core:
        return False
    if style == "PascalCase" and not core[0].isupper():
        return False
    if style == "camelCase" and not core[0].islower():
        return False
    for is_up, grp in itertools.groupby(enumerate(core), key=lambda p: p[1].isupper()):
        grp = list(grp)
        if is_up and len(grp) >= 2:
            end = grp[-1][0] + 1
            followed_lower = end < len(core) and core[end].islower()
            if not (len(grp) == 2 and followed_lower):
                return False
            if grp[0][0] == 0 and style == "camelCase":
                return False
    return True


class ExhaustiveOracle(unittest.TestCase):
    def test_all_short_names_against_independent_oracle(self):
        names = []
        for n in range(1, 6):
            for tup_ in itertools.product("aA_1", repeat=n):
                s = "".join(tup_)
                if s[0] != "1":
                    names.append(s)
        names = list(dict.fromkeys(names))
        src = "".join("def %s(): pass\n" % s for s in names)
        for style in ("snake_case", "UPPER_SNAKE", "PascalCase", "camelCase"):
            for lead, trail, dun in itertools.product((False, True), (False, True), ("flag", "exempt")):
                rs = rules(rule("R", ["function"], style, allow_leading_underscore=lead,
                                allow_trailing_underscore=trail, dunder=dun))
                res = N.check_naming(src, rs)
                bad = {f["name"] for f in res["findings"]}
                want = {s for s in names if not oracle_ok(s, style, lead, trail, dun)}
                self.assertEqual(bad - want, set(), (style, lead, trail, dun, sorted(bad - want)[:5]))
                self.assertEqual(want - bad, set(), (style, lead, trail, dun, sorted(want - bad)[:5]))
                self.assertEqual(len(res["findings"]), len(bad))
                self.assertEqual(res["checked_count"] + res["exempt_count"], len(names))


if __name__ == "__main__":
    unittest.main()
