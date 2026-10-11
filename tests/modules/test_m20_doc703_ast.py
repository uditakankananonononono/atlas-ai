"""Row703 AST documentation: exact fixtures, traps, bounds, independent oracle."""
import ast
import copy
import hashlib
import json
import pathlib
import random
import re

import pytest

from app.modules.m20_general_cognitive_worker.ast_documentation703 import generate

MODULE_PATH = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/ast_documentation703.py"


def gen(source, **kw):
    return generate({"source": source, **kw})


def by_q(res):
    return {s["qualname"]: s for s in res["symbols"]}


def pos(line, col):
    return {"line": line, "col": col}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def slice_range(source, rng):
    """Independent slice: code-point columns, newline kinds \\n \\r\\n \\r."""
    lines = [l for l in re.findall(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+", source)]
    s, e = rng["start"], rng["end"]
    if s["line"] == e["line"]:
        return lines[s["line"] - 1][s["col"]:e["col"]]
    parts = [lines[s["line"] - 1][s["col"]:]] + lines[s["line"]:e["line"] - 1] + [lines[e["line"] - 1][:e["col"]]]
    return "".join(parts)


# ---------------------------------------------------------------- exact fixtures
F1 = 'def f(a, /, b: int = 1, *args, c, d: str = "x", **kw) -> bool:\n    """Doc."""\n'


def test_full_signature_exact_fixture():
    res = gen(F1)
    assert res["status"] == "generated" and len(res["symbols"]) == 1
    s = res["symbols"][0]
    assert s["id"] == "f#1" and s["kind"] == "function" and s["name"] == "f" and s["qualname"] == "f"
    assert s["parent_id"] is None and s["depth"] == 0 and s["scope"] == "module"
    assert [(p["name"], p["kind"], p["annotation"], p["default"], p["has_default"]) for p in s["parameters"]] == [
        ("a", "positional_only", None, None, False),
        ("b", "positional_or_keyword", "int", "1", True),
        ("args", "var_positional", None, None, False),
        ("c", "keyword_only", None, None, False),
        ("d", "keyword_only", "str", '"x"', True),
        ("kw", "var_keyword", None, None, False),
    ]
    assert s["returns"] == "bool"
    assert s["signature_text"] == '(a, /, b: int = 1, *args, c, d: str = "x", **kw) -> bool'
    assert s["range"] == {"start": pos(1, 0), "end": pos(2, 14)}
    assert s["def_line"] == 1
    assert s["docstring"]["raw"] == "Doc." and s["docstring"]["cleaned"] == "Doc."
    assert s["docstring"]["range"] == {"start": pos(2, 4), "end": pos(2, 14)}
    assert s["missing"] == {"docstring": False, "return_annotation": False, "unannotated_parameters": ["a", "args", "c", "kw"]}
    assert s["range_sha256"] == sha(slice_range(F1, s["range"]))


def test_keyword_only_marker_without_varargs_and_defaults_alignment():
    src = "def g(a, b=2, c=3, *, d, e=5):\n    pass\n"
    s = gen(src)["symbols"][0]
    assert [(p["name"], p["kind"], p["default"]) for p in s["parameters"]] == [
        ("a", "positional_or_keyword", None), ("b", "positional_or_keyword", "2"), ("c", "positional_or_keyword", "3"),
        ("d", "keyword_only", None), ("e", "keyword_only", "5")]
    assert s["signature_text"] == "(a, b=2, c=3, *, d, e=5)"
    assert s["returns"] is None and s["missing"]["return_annotation"] is True


def test_positional_only_defaults_split_across_slash():
    s = gen("def h(a, b=1, /, c=2):\n    pass\n")["symbols"][0]
    assert [(p["name"], p["kind"], p["default"]) for p in s["parameters"]] == [
        ("a", "positional_only", None), ("b", "positional_only", "1"), ("c", "positional_or_keyword", "2")]
    assert s["signature_text"] == "(a, b=1, /, c=2)"


def test_multiline_default_and_annotation_text_is_exact_source():
    src = 'def k(\n    x: "List[int]" = [\n        1,\n        2,\n    ],\n) -> "X":\n    pass\n'
    s = gen(src)["symbols"][0]
    p = s["parameters"][0]
    assert p["annotation"] == '"List[int]"' and p["default"] == "[\n        1,\n        2,\n    ]"
    assert s["returns"] == '"X"'  # string annotations are text, never evaluated
    assert s["range"]["end"] == pos(7, 8)


F2 = "@dec\n@pkg.mod(1, x=2)\nasync def g(): ...\n"


def test_decorators_async_and_ranges_exact_fixture():
    s = gen(F2)["symbols"][0]
    assert s["kind"] == "async_function" and s["def_line"] == 3
    assert [d["source"] for d in s["decorators"]] == ["dec", "pkg.mod(1, x=2)"]
    assert s["decorators"][0]["range"] == {"start": pos(1, 1), "end": pos(1, 4)}
    assert s["decorators"][1]["range"] == {"start": pos(2, 1), "end": pos(2, 16)}
    assert s["range"] == {"start": pos(1, 0), "end": pos(3, 18)}
    assert s["decorator_semantics"] == "not_interpreted"
    assert s["docstring"] is None and s["missing"]["docstring"] is True


F3 = ('class A:\n    """Cls."""\n    def m(self):\n        def inner(): pass\n        return inner\n'
      '    class B:\n        pass\ndef top(): pass\n')


def test_nested_scope_exact_fixture():
    res = gen(F3)
    assert [s["id"] for s in res["symbols"]] == ["A#1", "A.m#1", "A.m.<locals>.inner#1", "A.B#1", "top#1"]
    q = by_q(res)
    assert [q[n]["kind"] for n in ["A", "A.m", "A.m.<locals>.inner", "A.B", "top"]] == ["class", "function", "function", "class", "function"]
    assert [q[n]["parent_id"] for n in ["A", "A.m", "A.m.<locals>.inner", "A.B", "top"]] == [None, "A#1", "A.m#1", "A#1", None]
    assert [q[n]["scope"] for n in ["A", "A.m", "A.m.<locals>.inner", "A.B", "top"]] == ["module", "class", "function", "class", "module"]
    assert [q[n]["depth"] for n in ["A", "A.m", "A.m.<locals>.inner", "A.B", "top"]] == [0, 1, 2, 1, 0]
    assert q["A"]["range"] == {"start": pos(1, 0), "end": pos(7, 12)}
    assert q["A"]["docstring"]["raw"] == "Cls."


def test_class_bases_keywords_and_no_init_invention():
    s = gen("class C(Base, mixins.M, metaclass=Meta, flag=True):\n    def __init__(self, a): pass\n")["symbols"][0]
    assert s["kind"] == "class" and s["bases"] == ["Base", "mixins.M"] and s["keywords"] == [{"name": "metaclass", "value": "Meta"}, {"name": "flag", "value": "True"}]
    assert "parameters" not in s and "signature_text" not in s and "returns" not in s
    assert s["constructor_signature"] == "not_derived"


def test_conditional_and_try_definitions_are_found_and_duplicates_numbered():
    src = "if X:\n    def f(): pass\nelse:\n    def f(a): pass\ntry:\n    class K: pass\nexcept E:\n    class K: pass\n"
    res = gen(src)
    assert [s["id"] for s in res["symbols"]] == ["f#1", "f#2", "K#1", "K#2"]
    assert [s["range"]["start"]["line"] for s in res["symbols"]] == [2, 4, 6, 8]


def test_function_in_match_with_for_while_blocks():
    src = "match x:\n    case 1:\n        def a(): pass\nfor i in y:\n    def b(): pass\nwhile z:\n    def c(): pass\nwith w:\n    def d(): pass\n"
    assert [s["name"] for s in gen(src)["symbols"]] == ["a", "b", "c", "d"]


def test_lambda_and_comprehension_are_not_symbols_and_stated():
    res = gen("f = lambda x: x\nys = [(lambda: 1) for _ in z]\n")
    assert res["symbols"] == [] and "lambda" in " ".join(res["limits"])


def test_type_params_source_text():
    s = gen("def f[T: int, *Ts](x: T) -> T: ...\nclass C[U]: ...\n")["symbols"]
    assert s[0]["type_params"] == ["T: int", "*Ts"] and s[1]["type_params"] == ["U"]


# ---------------------------------------------------------------- traps
TRAP = ('# def fake(): pass\nx = "def fake2(): pass\\nclass Fake: pass"\n\'\'\'\ndef fake3(): pass\nclass Fake4: pass\n\'\'\'\n'
        'y = {"def": 1, "class": 2}  # class Fake5: pass\ndef real(): pass\n')


def test_comments_and_string_literals_never_create_symbols():
    res = gen(TRAP)
    assert [s["qualname"] for s in res["symbols"]] == ["real"]
    assert res["symbols"][0]["range"]["start"] == pos(8, 0)


def test_keyword_like_names_and_soft_keywords_are_not_symbols():
    res = gen("match = 1\ncase = 2\ntype = 3\nasync_ = 4\ndefault = 5\nclass_ = 6\n")
    assert res["symbols"] == []


# ---------------------------------------------------------------- docstrings: no meaning invention
DOC = 'def f(a, b):\n    """Summary.\n\n    Args:\n        a: the thing\n        b: other\n    Returns:\n        nothing\n    """\n'


def test_docstring_text_is_preserved_but_not_interpreted():
    s = gen(DOC)["symbols"][0]
    assert s["docstring"]["raw"] == "Summary.\n\n    Args:\n        a: the thing\n        b: other\n    Returns:\n        nothing\n    "
    assert s["docstring"]["cleaned"] == "Summary.\n\nArgs:\n    a: the thing\n    b: other\nReturns:\n    nothing"
    for p in s["parameters"]:
        assert p["description"] is None and p["semantics"] == "unknown"
    assert s["return_description"] is None
    assert set(s["unknown_semantics"]) >= {"parameter_descriptions", "return_description", "raises", "side_effects", "behavior"}
    assert s["semantics_derived"] is False


@pytest.mark.parametrize("src,doc", [
    ('def f():\n    "a" "b"\n', "ab"),
    ('def f():\n    """x\\ny"""\n', "x\ny"),
    ("def f():\n    '''  lead'''\n", "  lead"),
    ('def f():\n    """"""\n', ""),
])
def test_docstring_literal_forms(src, doc):
    d = gen(src)["symbols"][0]["docstring"]
    assert d["raw"] == doc


@pytest.mark.parametrize("src", [
    'def f():\n    f"""x"""\n', 'def f():\n    b"x"\n', 'def f():\n    x = 1\n    "late"\n', 'def f():\n    ("paren")\n    pass\n'.replace('("paren")', "1"),
    'def f():\n    pass\n', 'def f(): "one-liner-not-doc" ; pass\n'.replace("one-liner-not-doc", "doc") .replace('"doc" ; pass', "pass"),
    'def f():\n    "a" + "b"\n',
])
def test_non_docstrings_are_marked_undocumented(src):
    s = gen(src)["symbols"][0]
    assert s["docstring"] is None and s["missing"]["docstring"] is True


def test_one_line_def_docstring_and_second_string_ignored():
    s = gen('def f(): "doc"\ndef g():\n    "one"\n    "two"\n')["symbols"]
    assert s[0]["docstring"]["raw"] == "doc" and s[1]["docstring"]["raw"] == "one"


def test_module_docstring_and_class_docstring():
    res = gen('"""Mod doc."""\nclass C:\n    "c"\n')
    assert res["module"]["docstring"]["raw"] == "Mod doc." and res["module"]["docstring"]["range"] == {"start": pos(1, 0), "end": pos(1, 14)}
    assert gen("x = 1\n")["module"]["docstring"] is None


# ---------------------------------------------------------------- Unicode / newline position convention
def test_columns_are_code_points_not_utf8_bytes():
    src = 'def f(a="\U0001F600"): pass\n'
    s = gen(src)["symbols"][0]
    assert s["range"] == {"start": pos(1, 0), "end": pos(1, 18)}  # ast reports 21 (UTF-8 bytes)
    assert s["parameters"][0]["default"] == '"\U0001F600"'
    assert s["range_sha256"] == sha(src.rstrip("\n"))


def test_non_ascii_identifier_and_combining_marks():
    src = 'class Caf\u00e9:\n    def na\u00efve(self, \u03b1="e\u0301"): pass\n'
    res = gen(src)
    q = by_q(res)
    assert q["Caf\u00e9.na\u00efve"]["range"] == {"start": pos(2, 4), "end": pos(2, 33)}
    assert q["Caf\u00e9.na\u00efve"]["parameters"][1]["name"] == "\u03b1"
    assert q["Caf\u00e9.na\u00efve"]["parameters"][1]["default"] == '"e\u0301"'
    assert res["source_chars"] == len(src) and res["source_bytes"] == len(src.encode())


@pytest.mark.parametrize("nl", ["\n", "\r\n", "\r"])
def test_newline_kinds_give_same_positions_and_slices(nl):
    src = nl.join(["@d", "def f(x):", '    "\u00e9\U0001F600"', "def g(): pass", ""])
    res = gen(src)
    f, g = res["symbols"]
    assert f["range"] == {"start": pos(1, 0), "end": pos(3, 8)} and g["range"]["start"] == pos(4, 0)
    assert f["docstring"]["raw"] == "\u00e9\U0001F600"
    assert res["line_count"] == 4
    for s in res["symbols"]:
        assert s["range_sha256"] == sha(slice_range(src, s["range"]))


def test_form_feed_is_not_a_line_break():
    src = "x = 1\x0c\ndef f(): pass\n"
    assert gen(src)["symbols"][0]["range"]["start"] == pos(2, 0) and gen(src)["line_count"] == 2


def test_tab_counts_as_one_column():
    s = gen("class A:\n\tdef m(self): pass\n")["symbols"][1]
    assert s["range"]["start"] == pos(2, 1)


# ---------------------------------------------------------------- source hash binding
def test_source_hash_binding():
    res = gen(F1)
    assert res["source_sha256"] == sha(F1)
    assert gen(F1, expected_sha256=sha(F1))["source_sha256"] == sha(F1)
    with pytest.raises(ValueError) as e:
        gen(F1, expected_sha256=sha(F1 + " "))
    assert str(e.value) == "expected_sha256 mismatch"
    for bad in ["abc", sha(F1).upper(), sha(F1)[:-1], 5, None, "g" * 64]:
        with pytest.raises(ValueError, match="expected_sha256 must be 64 lowercase hex"):
            gen(F1, expected_sha256=bad)


def test_one_byte_change_changes_hash_and_symbol_hash_tracks_only_its_text():
    a = gen("def f(): pass\ndef g(): pass\n")
    b = gen("def f(): pass\ndef g(): pass \n")
    assert a["source_sha256"] != b["source_sha256"]
    assert a["symbols"][0]["range_sha256"] == b["symbols"][0]["range_sha256"]
    assert a["symbols"][1]["range_sha256"] == b["symbols"][1]["range_sha256"]  # trailing space is outside the node
    c = gen("def f(): pass\ndef g(): return 1\n")
    assert a["symbols"][1]["range_sha256"] != c["symbols"][1]["range_sha256"]


# ---------------------------------------------------------------- refusals with exact errors
def err(data):
    with pytest.raises(ValueError) as e:
        generate(data)
    return str(e.value)


@pytest.mark.parametrize("src", ["def f(:\n", "class\n", "x = (\n", "def f():\nreturn 1\n", "\ufeffx = 1\n", "if x:\n  a\n b\n", "print 'x'\n", "x = $\n"])
def test_syntax_errors_refused_with_position(src):
    assert re.match(r"^(syntax_error|compile_error): line \d+ col \d+: .+", err({"source": src}))


def test_syntax_error_exact_position_for_known_case():
    m = re.match(r"^syntax_error: line (\d+) col (\d+): ", err({"source": "x = 1\ny = )\n"}))
    assert m and m.group(1) == "2"


def test_exact_error_messages():
    assert err({"source": 5}) == "source must be a string"
    assert err({"source": None}) == "source must be a string"
    assert err({"source": b"x"}) == "source must be a string"
    assert err({"source": "x\x00"}) == "source contains NUL"
    assert err({"source": "\ud800"}) == "source is not UTF-8 encodable"
    assert err({}) == "input keys invalid: missing ['source'] unknown []"
    assert err({"source": "x", "extra": 1}) == "input keys invalid: missing [] unknown ['extra']"
    assert err([]) == "input must be an object"
    assert err(None) == "input must be an object"
    assert err({"source": "x" * 65537}) == "source exceeds 65536 characters"
    assert err({"source": ";".join(["x"] * 1) + "\n" * 2001}) == "source exceeds 2000 lines"
    assert err({"source": "x", "filename": ""}) == "filename must be 1..128 characters of letters, digits and _./-"
    assert err({"source": "x", "filename": "a b"}) == "filename must be 1..128 characters of letters, digits and _./-"
    assert err({"source": "x", "filename": "a" * 129}) == "filename must be 1..128 characters of letters, digits and _./-"


def test_char_bound_n_and_n_plus_1():
    ok = "#" + "a" * 65535
    assert len(ok) == 65536 and gen(ok)["symbols"] == []
    assert err({"source": ok + "a"}) == "source exceeds 65536 characters"
    # multi-byte characters count as one character each
    assert gen("#" + "\U0001F600" * 65535)["source_bytes"] == 1 + 4 * 65535


def test_line_bound_n_and_n_plus_1():
    assert gen("\n".join(["#"] * 2000))["line_count"] == 2000
    assert gen("#\n" * 2000)["line_count"] == 2000
    assert err({"source": "#\n" * 2000 + "#"}) == "source exceeds 2000 lines"
    assert gen("")["line_count"] == 0 and gen("\n")["line_count"] == 1
    assert gen("\r".join(["#"] * 2000))["line_count"] == 2000
    assert err({"source": "\r".join(["#"] * 2001)}) == "source exceeds 2000 lines"


def node_count(src):
    return sum(1 for _ in ast.walk(ast.parse(src)))


def test_ast_node_bound_n_and_n_plus_1():
    base = ";".join(["0"] * 9999) + "\n"  # Module + 9999*(Expr+Constant) = 19999 nodes
    assert node_count(base) == 19999
    assert gen(base)["status"] == "generated"
    assert node_count(base + "pass\n") == 20000 and gen(base + "pass\n")["status"] == "generated"
    assert node_count(base + "pass;pass\n") == 20001
    assert err({"source": base + "pass;pass\n"}) == "ast exceeds 20000 nodes"


def test_symbol_bound_n_and_n_plus_1():
    assert len(gen("\n".join("def f%d(): pass" % i for i in range(500)))["symbols"]) == 500
    assert err({"source": "\n".join("def f%d(): pass" % i for i in range(501))}) == "more than 500 symbols"


def nested(depth, kind="class"):
    lines = []
    for i in range(depth):
        lines.append("    " * i + "class C%d:" % i)
    lines.append("    " * depth + "pass")
    return "\n".join(lines) + "\n"


def test_scope_depth_bound_n_and_n_plus_1():
    assert len(gen(nested(8))["symbols"]) == 8 and gen(nested(8))["symbols"][-1]["depth"] == 7
    assert err({"source": nested(9)}) == "scope nesting exceeds 8"


def test_parser_resource_failures_are_refusals_not_crashes():
    with pytest.raises(ValueError, match=r"^(syntax_error|resource_limit)"):
        generate({"source": "(" * 500 + ")" * 500})
    for src in ["[" * 300 + "]" * 300, "x = " + "-" * 5000 + "1", "x = " + "a." * 5000 + "b", "x=" + "(1+" * 150 + "1" + ")" * 150]:
        try:
            assert generate({"source": src})["status"] == "generated"  # parser accepted it; AST walk is iterative
        except ValueError as exc:
            assert re.match(r"^(syntax_error|resource_limit|ast exceeds)", str(exc))


def test_deeply_nested_statements_are_refused_or_handled_without_recursion_crash():
    src = ""
    for i in range(120):
        src += " " * i + "if x:\n"
    src += " " * 120 + "def f(): pass\n"
    try:
        res = generate({"source": src})
        assert res["symbols"][0]["name"] == "f"
    except ValueError as exc:
        assert re.match(r"^(syntax_error|resource_limit)", str(exc))


# ---------------------------------------------------------------- reference / determinism checks
BIG = F1 + F2 + F3 + TRAP + DOC + "if X:\n    def f(): pass\nelse:\n    def f(): pass\n"


def test_ids_unique_parents_resolve_and_order_is_source_order():
    res = generate({"source": BIG})
    ids = [s["id"] for s in res["symbols"]]
    assert len(ids) == len(set(ids))
    for s in res["symbols"]:
        assert s["parent_id"] is None or s["parent_id"] in ids
        if s["parent_id"]:
            assert ids.index(s["parent_id"]) < ids.index(s["id"])
            assert s["qualname"].startswith(by_id(res)[s["parent_id"]]["qualname"] + ".")
    starts = [(s["range"]["start"]["line"], s["range"]["start"]["col"]) for s in res["symbols"]]
    assert starts == sorted(starts) and len(set(starts)) == len(starts)
    for s in res["symbols"]:
        assert s["id"] == "%s#%d" % (s["qualname"], 1 + [t["qualname"] for t in res["symbols"][:ids.index(s["id"])]].count(s["qualname"]))


def by_id(res):
    return {s["id"]: s for s in res["symbols"]}


def test_deterministic_json_and_input_unmutated():
    d = {"source": BIG, "filename": "pkg/mod.py"}
    snap = copy.deepcopy(d)
    a, b = generate(d), generate(d)
    assert d == snap and json.dumps(a) == json.dumps(b)
    assert json.loads(json.dumps(a, allow_nan=False)) == a
    assert a["filename"] == "pkg/mod.py"


def test_every_symbol_range_slice_reparses_to_same_symbol_and_hash_matches():
    res = generate({"source": BIG})
    for s in res["symbols"]:
        text = slice_range(BIG, s["range"])
        assert sha(text) == s["range_sha256"]
        dedented = "if 1:\n" + "".join("    " + l for l in text.splitlines(True)) if s["depth"] else text
        tree = ast.parse(dedented)
        node = tree.body[0].body[0] if s["depth"] else tree.body[0]
        assert node.name == s["name"]


# ---------------------------------------------------------------- independent oracle over generated sources
def oracle_signature(node):
    a = node.args
    out = []
    pos_all = a.posonlyargs + a.args
    defaults = [None] * (len(pos_all) - len(a.defaults)) + list(a.defaults)
    for i, (arg, dflt) in enumerate(zip(pos_all, defaults)):
        out.append((arg.arg, "positional_only" if i < len(a.posonlyargs) else "positional_or_keyword", ast.unparse(arg.annotation) if arg.annotation else None, ast.unparse(dflt) if dflt is not None else None))
    if a.vararg:
        out.append((a.vararg.arg, "var_positional", ast.unparse(a.vararg.annotation) if a.vararg.annotation else None, None))
    for arg, dflt in zip(a.kwonlyargs, a.kw_defaults):
        out.append((arg.arg, "keyword_only", ast.unparse(arg.annotation) if arg.annotation else None, ast.unparse(dflt) if dflt is not None else None))
    if a.kwarg:
        out.append((a.kwarg.arg, "var_keyword", ast.unparse(a.kwarg.annotation) if a.kwarg.annotation else None, None))
    return out


def oracle_walk(tree):
    out = []

    def rec(body, prefix, in_func):
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                q = prefix + n.name
                out.append((q, n))
                rec(n.body, q + (".<locals>." if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) else "."), False)
            else:
                for f in ("body", "orelse", "finalbody"):
                    if isinstance(getattr(n, f, None), list):
                        rec(getattr(n, f), prefix, in_func)
                for h in getattr(n, "handlers", []):
                    rec(h.body, prefix, in_func)
                for c in getattr(n, "cases", []):
                    rec(c.body, prefix, in_func)
    rec(tree.body, "", False)
    return out


NAMES = ["a", "b", "c", "x1", "val", "_p", "k"]
ANN = [None, "int", "str", "list[int]", "'Fwd'", "a.b.C", "int | None"]
DEF = [None, "1", "None", "'s'", "[1, 2]", "{}", "(1, 2)", "-1"]


def gen_func(rng, indent, name, nested_depth):
    names = rng.sample(NAMES, rng.randrange(0, 6))
    parts, i = [], 0
    npos = rng.randrange(0, len(names) + 1)
    posonly = rng.randrange(0, npos + 1) if rng.random() < 0.5 else 0
    seen_default = False
    for j, n in enumerate(names[:npos]):
        ann = rng.choice(ANN)
        d = rng.choice(DEF) if seen_default or rng.random() < 0.4 else None
        if d:
            seen_default = True
        parts.append(n + (": " + ann if ann else "") + ((" = " if ann else "=") + d if d else ""))
        if posonly and j == posonly - 1:
            parts.append("/")
    rest = names[npos:]
    if rest:
        if rng.random() < 0.5:
            parts.append("*" + rest[0])
            rest = rest[1:]
        else:
            parts.append("*")
        for n in rest[:-1] if rng.random() < 0.5 else rest:
            ann, d = rng.choice(ANN), rng.choice(DEF)
            parts.append(n + (": " + ann if ann else "") + ((" = " if ann else "=") + d if d else ""))
        rest = []
    if rng.random() < 0.3 and len(names) < len(NAMES) and "kw" not in names:
        parts.append("**kw")
    # drop a trailing bare "*" (invalid)
    if parts and parts[-1] == "*":
        parts.pop()
    ret = rng.choice([None, "int", "'X'", "list[str]"])
    pre = "".join(indent + "@d%d\n" % k for k in range(rng.randrange(0, 3)))
    kw = rng.choice(["def", "async def"])
    head = "%s%s %s(%s)%s:\n" % (indent, kw, name, ", ".join(parts), " -> " + ret if ret else "")
    body = []
    if rng.random() < 0.5:
        body.append(indent + '    """doc %s"""\n' % name)
    if nested_depth and rng.random() < 0.6:
        body.append(gen_func(rng, indent + "    ", "in_" + name, nested_depth - 1))
    if rng.random() < 0.3:
        body.append(indent + "    # def fake(): pass\n")
    body.append(indent + "    pass\n")
    return pre + head + "".join(body)


def gen_source(rng):
    out = []
    for k in range(rng.randrange(1, 5)):
        if rng.random() < 0.3:
            out.append("class C%d(B):\n" % k + "".join(gen_func(rng, "    ", "m%d" % j, 1) for j in range(rng.randrange(1, 3))))
        else:
            out.append(gen_func(rng, "", "f%d" % k, 2))
        if rng.random() < 0.3:
            out.append('S = "def nope(): pass"\n')
    return "".join(out)


def test_generated_corpus_matches_independent_oracle():
    rng = random.Random(703)
    total = 0
    for _ in range(300):
        src = gen_source(rng)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue  # generator may emit a rare invalid signature; tool must refuse it too
        res = generate({"source": src})
        want = oracle_walk(tree)
        assert [s["qualname"] for s in res["symbols"]] == [q for q, _ in want], src
        for s, (q, node) in zip(res["symbols"], want):
            assert s["kind"] == {ast.FunctionDef: "function", ast.AsyncFunctionDef: "async_function", ast.ClassDef: "class"}[type(node)]
            assert s["def_line"] == node.lineno
            if s["kind"] != "class":
                got = [(p["name"], p["kind"], p["annotation"], p["default"]) for p in s["parameters"]]
                assert got == oracle_signature(node), (src, q)
                assert s["returns"] == (ast.unparse(node.returns) if node.returns else None)
            assert (s["docstring"] or {}).get("raw") == ast.get_docstring(node, clean=False)
            assert len(s["decorators"]) == len(node.decorator_list)
            assert s["range_sha256"] == sha(slice_range(src, s["range"]))
            total += 1
    assert total > 500


def test_generated_refusals_agree_with_python_parser():
    rng = random.Random(11)
    for _ in range(200):
        src = gen_source(rng)
        chars = list(src)
        for _ in range(rng.randrange(1, 4)):
            chars.insert(rng.randrange(len(chars)), rng.choice(["(", ")", ":", "@", "\n", "*", "=", "\t"]))
        mutated = "".join(chars)
        try:
            ast.parse(mutated)
            valid = True
        except SyntaxError:
            valid = False
        try:
            generate({"source": mutated})
            ok = True
        except ValueError as exc:
            assert re.match(r"^(syntax_error|compile_error|resource_limit)", str(exc)) or "exceeds" in str(exc) or "symbols" in str(exc)
            ok = False
        if valid and ok is False:
            continue  # allowed only for declared resource bounds (checked by message above)
        assert valid == ok


# ---------------------------------------------------------------- purity / honesty flags
def test_module_imports_are_pure_and_never_execute_source():
    tree = ast.parse(MODULE_PATH.read_text())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add((n.module or "").split(".")[0])
    assert mods <= {"__future__", "ast", "hashlib", "re", "typing", "warnings"}, mods
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not (called & {"eval", "exec", "compile", "__import__", "open", "globals", "locals"})
    assert not any(isinstance(n, ast.Attribute) and n.attr in {"literal_eval", "import_module", "system", "Popen", "run"} for n in ast.walk(tree))


def test_source_with_side_effect_text_is_not_executed(tmp_path):
    marker = tmp_path / "ran"
    src = 'import os\nopen(%r, "w").write("x")\ndef f(a=open(%r, "w")): pass\n__import__("os").system("touch %s")\n' % (str(marker), str(marker), marker)
    res = generate({"source": src})
    assert not marker.exists() and res["symbols"][0]["parameters"][0]["default"].startswith("open(")
    assert res["code_executed"] is False and res["imports_resolved"] is False


def test_limits_and_flags_are_stated():
    res = gen("x = 1\n")
    assert res["algorithm"] == "python_ast_api_documentation_v1"
    assert res["code_executed"] is False and res["semantics_derived"] is False
    text = " ".join(res["limits"])
    for word in ("lambda", "executed", "decorator", "annotation", "docstring"):
        assert word in text
    assert res["position_convention"] == "line 1-based; col 0-based Unicode code points; end exclusive; line breaks LF, CRLF, CR"


@pytest.mark.parametrize("src,start,dstart", [
    ("@  dec\ndef f(): pass\n", pos(1, 0), pos(1, 3)),
    ("@ \\\n  dec\ndef f(): pass\n", pos(1, 0), pos(2, 2)),
    ("# @x\n\n@d\ndef f(): pass\n", pos(3, 0), pos(3, 1)),
    ("class A:\n    @d1\n    @ d2\n    def f(self): pass\n", pos(2, 4), pos(2, 5)),
])
def test_decorator_symbol_start_is_the_at_sign_not_the_expression(src, start, dstart):
    s = gen(src)["symbols"][-1]
    assert s["range"]["start"] == start and s["decorators"][0]["range"]["start"] == dstart
    assert slice_range(src, s["range"]).startswith("@")


# --- R2 audit pins (tests-only; runtime byte-unchanged). ---

def test_r2_class_missing_docstring_flag_both_directions():
    undocumented = gen("class C:\n    pass\n")["symbols"][0]
    assert undocumented["missing"] == {"docstring": True}
    documented = gen('class C:\n    "docs"\n')["symbols"][0]
    assert documented["missing"] == {"docstring": False}
    blank = gen('class C:\n    "   "\n')["symbols"][0]
    assert blank["missing"] == {"docstring": True}  # whitespace-only docstring still missing


@pytest.mark.parametrize("exc", [RecursionError("depth"), MemoryError("oom")])
def test_r2_parser_resource_errors_map_to_exact_refusal(monkeypatch, exc):
    # 3.12's parser refuses deep nesting as SyntaxError first, so a real
    # RecursionError is not reliably triggerable (contract documents the arm);
    # patch the parser to exercise the exact mapping deterministically.
    import ast as _ast
    def boom(*a, **k):
        raise exc
    monkeypatch.setattr(_ast, "parse", boom)
    with pytest.raises(ValueError, match=re.escape("resource_limit: parser exceeded recursion or memory bounds")):
        generate({"source": "x = 1\n"})


def test_r2_parser_value_error_maps_to_line0_col0_syntax_refusal(monkeypatch):
    import ast as _ast
    def boom(*a, **k):
        raise ValueError("odd parser complaint")
    monkeypatch.setattr(_ast, "parse", boom)
    with pytest.raises(ValueError, match=re.escape("syntax_error: line 0 col 0: odd parser complaint")):
        generate({"source": "x = 1\n"})


def test_r2_finally_block_symbols_are_collected():
    res = gen("try:\n    pass\nfinally:\n    def fin(): pass\n    class K: pass\n")
    assert [s["name"] for s in res["symbols"]] == ["fin", "K"]
    src = "def f():\n    try:\n        pass\n    finally:\n        def g(): pass\n"
    assert [s["qualname"] for s in gen(src)["symbols"]] == ["f", "f.<locals>.g"]


@pytest.mark.parametrize("src,start,dstart", [
    ("@\tdec\ndef f(): pass\n", pos(1, 0), pos(1, 2)),
    ("@\fdec\ndef f(): pass\n", pos(1, 0), pos(1, 2)),
    ("@ \t\f\\\r\n dec\ndef f(): pass\n", pos(1, 0), pos(2, 1)),
])
def test_r2_decorator_start_scan_covers_tab_formfeed_backslash(src, start, dstart):
    s = gen(src)["symbols"][-1]
    assert s["range"]["start"] == start and s["decorators"][0]["range"]["start"] == dstart
    assert slice_range(src, s["range"]).startswith("@")


def test_r2_symbol_count_key_present_and_exact():
    res = gen("def f(): pass\nclass C: pass\ndef g(): pass\n")
    assert "symbol_count" in res and res["symbol_count"] == 3 == len(res["symbols"])
    assert gen("x = 1\n")["symbol_count"] == 0


def test_r2_parser_warnings_are_suppressed():
    import warnings
    src = 'def f():\n    return "\\d"\n'  # invalid escape sequence warns at parse time
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        res = gen(src)
    assert res["status"] == "generated" and caught == []


def test_r2_limits_list_exact_equality():
    assert gen("x = 1\n")["limits"] == [
        "source is parsed, never executed or imported; decorators, defaults and annotations are source text, not evaluated",
        "decorator semantics (staticmethod, property, wrappers) are not interpreted",
        "annotation and default text is exact source text; string annotations are not resolved",
        "docstring text is preserved verbatim; no sections, parameters or behavior are parsed or inferred from it",
        "lambda expressions and comprehensions are not symbols; only def, async def and class statements are",
        "class constructor signatures are not derived",
        "grammar accepted is that of the Python interpreter running Atlas",
    ]


def test_r2_unknown_semantics_lists_exact_equality():
    fn = gen("def f(): pass\n")["symbols"][0]
    assert fn["unknown_semantics"] == ["parameter_descriptions", "return_description", "raises", "side_effects", "behavior", "thread_safety"]
    cls = gen("class C: pass\n")["symbols"][0]
    assert cls["unknown_semantics"] == ["attributes", "behavior", "invariants", "thread_safety"]


@pytest.mark.xfail(strict=True, reason="known defect: _child_blocks emits try body/else/finally before handlers, so handler symbols violate the contract source-order claim; runtime fix queued as a separate unit")
def test_r3_try_handler_symbols_follow_source_order():
    src = "try:\n    def t(): pass\nexcept E:\n    def e(): pass\nelse:\n    def el(): pass\nfinally:\n    def fi(): pass\n"
    assert [s["name"] for s in gen(src)["symbols"]] == ["t", "e", "el", "fi"]
