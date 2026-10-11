"""Tests for ledger row 694 (Legacy Code Modernization) modernizer.

The module under test is loaded by file path so these tests need only the
standard library and pytest. Run with: pytest --noconftest <this file>
"""
import importlib.util
import pathlib

import pytest

_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "backend/app/modules/m20_general_cognitive_worker/legacy_modernizer694.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("legacy_modernizer694_under_test", _PATH)
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


M = _load()
modernize = M.modernize


def out(src, **kw):
    return modernize(src, **kw)


# ---- has_key -------------------------------------------------------------
def test_has_key_basic():
    r = out("if d.has_key(k):\n    pass\n")
    assert r.modernized == "if k in d:\n    pass\n"
    assert [(c.rule, c.line) for c in r.changes] == [("has_key", 1)]


def test_has_key_parens_in_comparison_context():
    r = out("x = d.has_key(k) == True\n")
    assert r.modernized == "x = (k in d) == True\n"


def test_has_key_complex_operands_wrapped():
    r = out("y = (a or b).has_key(k1 + k2)\n")
    assert r.modernized == "y = (k1 + k2) in (a or b)\n"
    ns = {"a": {}, "b": {3: 1}, "k1": 1, "k2": 2}
    exec(r.modernized, ns)
    assert ns["y"] is True


def test_has_key_wrong_arity_refused():
    r = out("d.has_key(a, b)\nd.has_key()\n")
    assert r.modernized == "d.has_key(a, b)\nd.has_key()\n"
    assert {x.rule for x in r.refusals} == {"has_key"}
    assert len(r.refusals) == 2


def test_has_key_starred_refused():
    r = out("d.has_key(*a)\n")
    assert r.modernized == "d.has_key(*a)\n"
    assert len(r.refusals) == 1


def test_has_key_not_context():
    r = out("if not d.has_key(k):\n    pass\n")
    assert r.modernized == "if not k in d:\n    pass\n"


def test_has_key_as_call_argument_not_parenthesized():
    r = out("f(d.has_key(k))\n")
    assert r.modernized == "f(k in d)\n"


def test_has_key_nested_fixpoint():
    r = out("d.has_key(e.has_key(k))\n")
    assert r.modernized == "(k in e) in d\n"
    ns = {"d": {True: 1}, "e": {5: 1}, "k": 5}
    exec(r.modernized, ns)
    assert r.passes >= 2


# ---- unittest aliases ----------------------------------------------------
def test_unittest_aliases():
    src = (
        "class T(unittest.TestCase):\n"
        "    def t(self):\n"
        "        self.assertEquals(1, 1)\n"
        "        self.assertNotEquals(1, 2)\n"
        "        self.assert_(True)\n"
        "        self.failUnless(True)\n"
        "        self.failIf(False)\n"
        "        self.assertRegexpMatches('a', 'a')\n"
        "        self.assertRaisesRegexp(ValueError, 'x', f)\n"
        "        self.assertAlmostEquals(1, 1)\n"
    )
    r = out(src)
    assert r.modernized == (
        "class T(unittest.TestCase):\n"
        "    def t(self):\n"
        "        self.assertEqual(1, 1)\n"
        "        self.assertNotEqual(1, 2)\n"
        "        self.assertTrue(True)\n"
        "        self.assertTrue(True)\n"
        "        self.assertFalse(False)\n"
        "        self.assertRegex('a', 'a')\n"
        "        self.assertRaisesRegex(ValueError, 'x', f)\n"
        "        self.assertAlmostEqual(1, 1)\n"
    )
    assert len(r.changes) == 8


def test_unittest_alias_only_on_self():
    r = out("other.assertEquals(1, 1)\n")
    assert r.modernized == "other.assertEquals(1, 1)\n"
    assert r.changes == []


# ---- collections ABCs ----------------------------------------------------
def test_collections_abc_import():
    r = out("from collections import Mapping, Sequence\n")
    assert r.modernized == "from collections.abc import Mapping, Sequence\n"


def test_collections_mixed_names_refused():
    src = "from collections import Mapping, OrderedDict\n"
    r = out(src)
    assert r.modernized == src
    assert [x.rule for x in r.refusals] == ["collections_abc"]


def test_collections_non_abc_untouched():
    src = "from collections import OrderedDict\n"
    r = out(src)
    assert r.modernized == src and not r.refusals and not r.changes


def test_collections_attribute_form_refused_needs_import():
    src = "import collections\nx = collections.Mapping\n"
    r = out(src)
    assert r.modernized == src
    assert [x.rule for x in r.refusals] == ["collections_abc"]
    assert r.refusals[0].line == 2


# ---- string module ---------------------------------------------------------
def test_string_functions():
    src = "import string\na = string.lower(x)\nb = string.upper(x)\nc = string.strip(x)\nd = string.join(w, ',')\ne = string.join(w)\n"
    r = out(src)
    assert r.modernized == (
        "import string\na = x.lower()\nb = x.upper()\nc = x.strip()\nd = ','.join(w)\ne = ' '.join(w)\n"
    )


def test_string_join_complex_receiver():
    r = out("import string\ns = string.lower(a + b)\n")
    assert r.modernized == "import string\ns = (a + b).lower()\n"


def test_string_extra_args_refused():
    src = "import string\nstring.strip(x, 'ab')\n"
    r = out(src)
    assert r.modernized == src
    assert [x.rule for x in r.refusals] == ["string_module"]


def test_string_not_imported_untouched():
    src = "a = string.lower(x)\n"
    r = out(src)
    assert r.modernized == src and not r.changes and not r.refusals


def test_string_rebound_untouched():
    src = "import string\nstring = Foo()\na = string.lower(x)\n"
    r = out(src)
    assert r.modernized == src and not r.changes


# ---- os.getcwdu / xrange -----------------------------------------------------
def test_getcwdu():
    r = out("import os\np = os.getcwdu()\n")
    assert r.modernized == "import os\np = os.getcwd()\n"


def test_getcwdu_requires_import_os():
    src = "p = os.getcwdu()\n"
    assert out(src).modernized == src


def test_xrange():
    r = out("for i in xrange(10):\n    pass\nxs = [j for j in xrange(3)]\n")
    assert r.modernized == "for i in range(10):\n    pass\nxs = [j for j in range(3)]\n"
    assert len(r.changes) == 2


def test_xrange_shadowed_not_rewritten():
    src = "def xrange(n):\n    return n\nxrange(3)\n"
    r = out(src)
    assert r.modernized == src and not r.changes


# ---- iteritems family ----------------------------------------------------
def test_iteritems_in_for_and_comprehension():
    src = "for k, v in d.iteritems():\n    pass\nz = [k for k in d.iterkeys()]\nw = sorted(d.itervalues())\n"
    r = out(src)
    assert r.modernized == "for k, v in d.items():\n    pass\nz = [k for k in d.keys()]\nw = sorted(d.values())\n"


def test_iteritems_ambiguous_refused():
    src = "it = d.iteritems()\nnext(it)\n"
    r = out(src)
    assert r.modernized == src
    assert [x.rule for x in r.refusals] == ["dict_iter"]
    assert r.refusals[0].line == 1


def test_iteritems_with_args_refused():
    src = "for a in d.iteritems(1):\n    pass\n"
    r = out(src)
    assert r.modernized == src and len(r.refusals) == 1


# ---- result semantics ----------------------------------------------------
def test_python2_syntax_reported_not_rewritten():
    src = "print 'hi'\n"
    r = out(src)
    assert r.modernized == src
    assert r.compiled_ok is False and r.verified is False
    assert [x.rule for x in r.refusals] == ["syntax_error"]
    assert r.refusals[0].line == 1


def test_idempotent():
    src = "import string\nfor k in d.iteritems():\n    if d.has_key(k):\n        x = xrange(3)\n        y = string.lower(k)\n"
    first = out(src)
    second = out(first.modernized)
    assert second.changes == [] and second.modernized == first.modernized


def test_lines_reported_in_single_pass_are_original_lines():
    src = "a = 1\nb = d.has_key(\n    k\n)\nc = xrange(2)\n"
    r = out(src)
    assert all(c.pass_no == 1 for c in r.changes)
    assert r.modernized == "a = 1\nb = k in d\nc = range(2)\n"
    lines = {c.rule: c.line for c in r.changes}
    assert lines == {"has_key": 2, "xrange": 5}
    compile(r.modernized, "x", "exec")


def test_non_ascii_offsets():
    src = "s = 'héllo wörld ✓'; t = d.has_key('ü')\n"
    r = out(src)
    assert r.modernized == "s = 'héllo wörld ✓'; t = 'ü' in d\n"


def test_verified_requires_check():
    r = out("x = xrange(3)\n")
    assert r.compiled_ok is True
    assert r.check_passed is None
    assert r.verified is False


def test_characterization_pass_and_fail():
    src = "def f(n):\n    return list(xrange(n))\n"
    good = M.characterization([("f", (3,), [0, 1, 2])])
    bad = M.characterization([("f", (3,), [9])])
    r1 = out(src, check=good)
    assert r1.check_passed is True and r1.verified is True
    r2 = out(src, check=bad)
    assert r2.check_passed is False and r2.verified is False


def test_check_exception_recorded():
    def boom(_):
        raise RuntimeError("nope")
    r = out("x = 1\n", check=boom)
    assert r.check_passed is False and "RuntimeError" in r.check_error and r.verified is False


def test_characterization_missing_function_fails():
    chk = M.characterization([("nothing", (), 1)])
    assert chk("x = 1\n") is False


def test_rules_subset():
    r = out("x = xrange(3)\nd.has_key(k)\n", rules={"xrange"})
    assert r.modernized == "x = range(3)\nd.has_key(k)\n"


def test_unknown_rule_rejected():
    with pytest.raises(ValueError):
        out("x = 1\n", rules={"bogus"})


def test_non_str_rejected():
    with pytest.raises(TypeError):
        modernize(b"x = 1")


def test_unchanged_source_unchanged():
    src = "x = 1\n"
    r = out(src)
    assert r.modernized == src and r.changes == [] and r.refusals == []
    assert r.compiled_ok is True


def test_result_to_dict_is_plain_data():
    import json
    r = out("x = xrange(3)\nit = d.iteritems()\n")
    d = r.to_dict()
    json.dumps(d)
    assert d["changes"][0]["rule"] == "xrange"
    assert d["refusals"][0]["rule"] == "dict_iter"
    assert "modernized" in d
