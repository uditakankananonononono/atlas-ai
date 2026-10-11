"""Row706 Code Comments: tokenizer-based comment extraction and mechanical audit."""
import ast
import copy
import io
import json
import pathlib
import random
import re
import tokenize

import pytest

from app.modules.m20_general_cognitive_worker.comment_audit706 import audit

MODULE_PATH = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/comment_audit706.py"


def run(source, **kw):
    return audit({"source": source, **kw})


def err(data):
    with pytest.raises(ValueError) as e:
        audit(data)
    return str(e.value)


S1 = ('#!/usr/bin/env python\n# -*- coding: utf-8 -*-\n# Compute total.\nx = 1  # x = 1\n# TODO fix this\n'
      'def f(a):  # noqa: E501\n    # because the API requires it\n    return a\n')


def by_line(res):
    return {c["line"]: c for c in res["comments"]}


# ---------------------------------------------------------------- exact fixture
def test_exact_fixture_comments_categories_flags_blocks():
    res = run(S1)
    cs = res["comments"]
    assert [c["id"] for c in cs] == ["C%04d" % i for i in range(1, 8)]
    assert [(c["line"], c["col"], c["end_col"], c["kind"]) for c in cs] == [
        (1, 0, 21, "standalone"), (2, 0, 23, "standalone"), (3, 0, 16, "standalone"), (4, 7, 14, "inline"),
        (5, 0, 15, "standalone"), (6, 11, 23, "inline"), (7, 4, 33, "standalone")]
    assert [c["text"] for c in cs] == ["!/usr/bin/env python", " -*- coding: utf-8 -*-", " Compute total.", " x = 1", " TODO fix this", " noqa: E501",
                                      " because the API requires it"]
    assert [c["category"] for c in cs] == ["directive", "directive", "prose", "prose", "marker", "directive", "prose"]
    assert [c["flags"] for c in cs] == [[], [], [], ["commented_out_code_candidate", "restates_code_candidate"], ["marker_without_owner_or_ref"], [], []]
    assert [c["has_rationale_keyword"] for c in cs] == [False, False, False, False, False, False, True]
    assert [(c["block_id"], c["associated_line"]) for c in cs] == [("B0001", 4), ("B0001", 4), ("B0001", 4), (None, 4), ("B0002", 6), (None, 6), ("B0003", 8)]
    assert res["blocks"] == [
        {"id": "B0001", "first_line": 1, "last_line": 3, "col": 0, "comment_ids": ["C0001", "C0002", "C0003"], "associated_line": 4},
        {"id": "B0002", "first_line": 5, "last_line": 5, "col": 0, "comment_ids": ["C0005"], "associated_line": 6},
        {"id": "B0003", "first_line": 7, "last_line": 7, "col": 4, "comment_ids": ["C0007"], "associated_line": 8}]
    assert res["comment_count"] == 7 and res["code_line_count"] == 3 and res["line_count"] == 8
    assert res["counts"]["by_category"] == {"directive": 3, "empty": 0, "marker": 1, "prose": 3}
    assert res["counts"]["by_kind"] == {"inline": 2, "standalone": 5}
    assert res["counts"]["by_flag"] == {"commented_out_code_candidate": 1, "marker_without_owner_or_ref": 1, "restates_code_candidate": 1}
    assert res["semantics_judged"] is False and res["code_executed"] is False


def test_symbol_coverage_exact_fixture():
    res = run(S1, min_lines_for_comment=3)
    assert res["symbols"] == [{"name": "f", "kind": "function", "start_line": 6, "end_line": 8, "line_span": 3, "has_docstring": False,
                               "leading_block_id": "B0002", "inner_comment_count": 1, "flags": []}]
    src = "def g(a):\n    x = 1\n    y = 2\n    return x + y\n"
    s = run(src, min_lines_for_comment=4)["symbols"][0]
    assert s["flags"] == ["long_symbol_without_comments"] and s["inner_comment_count"] == 0 and s["leading_block_id"] is None
    assert run(src, min_lines_for_comment=5)["symbols"][0]["flags"] == []
    assert run(src, min_lines_for_comment=3)["symbols"][0]["flags"] == ["long_symbol_without_comments"]


def test_decorated_async_class_symbol_ranges_and_leading_block_gap():
    src = ("# about C\n\nclass C:\n    pass\n\n# about g\n@dec\nasync def g():\n    \"\"\"Doc.\"\"\"\n    # inside\n    pass\n"
           "# about h\n\n# real lead\ndef h(): pass\n")
    syms = {s["name"]: s for s in run(src)["symbols"]}
    assert [(s["name"], s["kind"], s["start_line"], s["end_line"]) for s in run(src)["symbols"]] == [("C", "class", 3, 4), ("g", "async_function", 7, 11), ("h", "function", 15, 15)]
    assert syms["C"]["leading_block_id"] is None  # blank line between comment and class
    assert syms["g"]["leading_block_id"] == "B0002" and syms["g"]["has_docstring"] is True and syms["g"]["inner_comment_count"] == 1
    assert syms["h"]["leading_block_id"] == "B0005"


# ---------------------------------------------------------------- tokenizer, not text search
TRAP = ('s = "# fake1"\nt = \'\'\'\n# fake2\n# fake3\n\'\'\'\nu = f"{s}# fake4"\nr = b"#fake5"  # real1\nv = "a#b"\n'
        '"""\n# fake6\n"""\nw = r"#\\d"  # real2\n# real3\n')


def test_hash_inside_strings_is_never_a_comment():
    res = run(TRAP)
    assert [(c["line"], c["text"]) for c in res["comments"]] == [(7, " real1"), (12, " real2"), (13, " real3")]
    assert res["comments"][0]["col"] == 15 and res["comments"][0]["kind"] == "inline"
    assert res["comments"][2]["associated_line"] is None  # no code line after it


def test_unicode_columns_are_code_points():
    src = 's = "\U0001F600"  # c\n# \u00e9\u0301\U0001F600\n'
    cs = run(src)["comments"]
    assert (cs[0]["col"], cs[0]["end_col"]) == (9, 12)
    assert (cs[1]["col"], cs[1]["end_col"], cs[1]["text"]) == (0, 5, " \u00e9\u0301\U0001F600")


@pytest.mark.parametrize("nl", ["\n", "\r\n"])
def test_line_breaks_lf_and_crlf_give_identical_results(nl):
    src = nl.join(["# a", "x = 1  # b", "# c", "y = 2", ""])
    res = run(src)
    assert [(c["line"], c["col"], c["end_col"], c["text"]) for c in res["comments"]] == [(1, 0, 3, " a"), (2, 7, 10, " b"), (3, 0, 3, " c")]
    assert res["line_count"] == 4 and res["code_line_count"] == 2
    assert [c["associated_line"] for c in res["comments"]] == [2, 2, 4]


def test_no_trailing_newline_and_comment_only_file():
    res = run("# only")
    assert res["comment_count"] == 1 and res["code_line_count"] == 0 and res["comments"][0]["associated_line"] is None and res["line_count"] == 1
    assert run("")["comment_count"] == 0 and run("")["line_count"] == 0


# ---------------------------------------------------------------- classification
def cat(text, code="v = 1"):
    src = "#" + text + "\n" + code + "\n"
    c = run(src)["comments"][0]
    return c["category"], c["flags"]


@pytest.mark.parametrize("text,expect", [
    (" TODO fix", ("marker", ["marker_without_owner_or_ref"])),
    (" TODO(ana) fix", ("marker", [])),
    (" FIXME[ABC-12] later", ("marker", [])),
    (" HACK: see ABC-7", ("marker", [])),
    (" XXX see #42", ("marker", [])),
    (" NOTE: remember", ("marker", ["marker_without_owner_or_ref"])),
    (" todo lower", ("prose", [])),
    (" TODOS are bad", ("prose", [])),
    (" type: ignore", ("directive", [])),
    (" noqa", ("directive", [])),
    (" pylint: disable=x", ("directive", [])),
    (" fmt: off", ("directive", [])),
    (" mypy: ignore-errors", ("directive", [])),
    (" pragma: no cover", ("directive", [])),
    (" nosec", ("directive", [])),
    (" isort: skip", ("directive", [])),
    (" pyright: basic", ("directive", [])),
    ("", ("empty", ["empty_comment"])),
    ("   ", ("empty", ["empty_comment"])),
    (" Compute the total.", ("prose", [])),
    (" see below", ("prose", [])),
    (" re-run", ("prose", [])),
    (" yes", ("prose", [])),
    (" a, b", ("prose", [])),
    (" foo(bar)", ("prose", ["commented_out_code_candidate"])),
    (" return y", ("prose", ["commented_out_code_candidate"])),
    (" import os", ("prose", ["commented_out_code_candidate"])),
    (" x = 1", ("prose", ["commented_out_code_candidate"])),
    (" await go()", ("prose", ["commented_out_code_candidate"])),
    (" else:", ("prose", [])),
    (" 12:30 meeting", ("prose", [])),
])
def test_classification_table(text, expect):
    assert cat(text) == expect


def test_shebang_and_coding_only_where_pep_allows():
    assert run("#!/bin/python\nx = 1\n")["comments"][0]["category"] == "directive"
    assert run("x = 1\n#!/bin/python\n")["comments"][0]["category"] == "prose"
    assert run("# coding: latin-1\nx = 1\n")["comments"][0]["category"] == "directive"
    assert run("x = 1\ny = 2\n# coding: latin-1\n")["comments"][0]["category"] == "prose"
    assert run("# vim: set fileencoding=utf-8 :\nx = 1\n")["comments"][0]["category"] == "directive"
    assert run("x = 1\n# coding: latin-1\n")["comments"][0]["category"] == "directive"  # line 2 is allowed


def test_restates_code_only_for_literal_word_echo():
    assert run("count += 1  # count += 1\n")["comments"][0]["flags"] == ["commented_out_code_candidate", "restates_code_candidate"]
    assert run("total_count = 0  # total count\n")["comments"][0]["flags"] == ["restates_code_candidate"]
    assert run("totalCount = 0  # Total Count 0\n")["comments"][0]["flags"] == ["restates_code_candidate"]
    assert run("count = 0  # reset the counter\n")["comments"][0]["flags"] == []
    assert run("count = 0  # count of retries\n")["comments"][0]["flags"] == []
    assert run("# count\ncount = 0\n")["comments"][0]["flags"] == ["restates_code_candidate"]
    assert run("# count\n\ncount = 0\n")["comments"][0]["flags"] == []  # detached: no associated code line
    assert run("x = 1  #\n")["comments"][0]["flags"] == ["empty_comment"]  # no words, so never "restates"


def test_rationale_keywords_are_lexical_only():
    for text, want in [(" because x", True), (" Because x", True), (" so that it works", True), (" to avoid races", True), (" workaround for bug", True),
                       (" work around bug", True), (" due to X", True), (" in order to go", True), (" otherwise fails", True), (" required by spec", True),
                       (" why: speed", True), (" in case of fire", True), (" unbecause", False), (" sincerely", False), (" increments i", False), ("", False)]:
        assert run("#" + text + "\nv = 1\n")["comments"][0]["has_rationale_keyword"] is want, text


@pytest.mark.parametrize("width,flag", [(99, False), (100, False), (101, True)])
def test_long_comment_line_bound_n_and_n_plus_1(width, flag):
    src = "#" + "x" * (width - 1) + "\n"
    assert ("long_comment_line" in run(src)["comments"][0]["flags"]) is flag
    inline = "v = 1  #" + "y" * (width - 8)
    assert ("long_comment_line" in run(inline)["comments"][0]["flags"]) is flag


def test_max_line_length_option_bounds_and_effect():
    assert "long_comment_line" in run("# " + "x" * 40, max_line_length=40)["comments"][0]["flags"]
    assert "long_comment_line" not in run("# " + "x" * 38, max_line_length=40)["comments"][0]["flags"]
    run("# a", max_line_length=40)
    run("# a", max_line_length=200)
    for bad in (39, 201, True, 100.0, "100", None):
        assert err({"source": "# a", "max_line_length": bad}) == "max_line_length must be an integer 40..200"
    for bad in (0, 501, True, 3.0, "3", None):
        assert err({"source": "# a", "min_lines_for_comment": bad}) == "min_lines_for_comment must be an integer 1..500"
    run("# a", min_lines_for_comment=1)
    run("# a", min_lines_for_comment=500)


def test_empty_comments_inside_a_block_are_paragraph_separators():
    res = run("# one\n#\n# two\nv = 1\n")
    assert [c["flags"] for c in res["comments"]] == [[], [], []] and res["comments"][1]["category"] == "empty"
    assert run("#\nv = 1\n")["comments"][0]["flags"] == ["empty_comment"]


def test_block_grouping_rules():
    src = "# a\n# b\n\n# c\n# d\nx = 1\nif x:\n    # e\n    # f\n    y = 2\n"
    res = run(src)
    assert [(b["first_line"], b["last_line"], b["col"], b["associated_line"]) for b in res["blocks"]] == [(1, 2, 0, None), (4, 5, 0, 6), (8, 9, 4, 10)]
    res = run("# a\n    \n# b\nx = 1\n")
    assert [(b["first_line"], b["last_line"]) for b in res["blocks"]] == [(1, 1), (3, 3)]  # whitespace-only line separates blocks


def test_inline_comment_never_joins_a_block_and_standalone_col_change_splits():
    src = "# a\n  # b\nx = 1\n"
    res = run(src)
    assert [b["col"] for b in res["blocks"]] == [0, 2] and [b["associated_line"] for b in res["blocks"]] == [None, 3]
    res = run("x = 1  # a\ny = 2  # b\n")
    assert res["blocks"] == [] and [c["block_id"] for c in res["comments"]] == [None, None]


def test_symbol_flags_leading_block_counts_marker_blocks_and_nested():
    src = "# TODO x\ndef f():\n    def g():\n        # inner\n        pass\n    return g\n"
    syms = {s["name"]: s for s in run(src, min_lines_for_comment=2)["symbols"]}
    assert syms["f"]["leading_block_id"] == "B0001" and syms["f"]["inner_comment_count"] == 1 and syms["f"]["flags"] == []
    assert syms["g"]["inner_comment_count"] == 1 and syms["g"]["leading_block_id"] is None


def test_comment_after_dedent_counts_to_enclosing_range_only_by_line():
    src = "def f():\n    pass\n    # trailing inside\ndef g():\n    pass\n"
    syms = {s["name"]: s for s in run(src)["symbols"]}
    assert syms["f"]["end_line"] == 2 and syms["f"]["inner_comment_count"] == 0  # comment after the last statement is outside the node range
    assert syms["g"]["leading_block_id"] == "B0001"  # line-based: the comment on line 3 directly precedes line 4, indentation is not considered
    res = run(src)
    assert res["blocks"][0]["associated_line"] == 4


# ---------------------------------------------------------------- refusals and bounds
def test_exact_errors():
    assert err(None) == "input must be an object"
    assert err({}) == "input keys invalid: missing ['source'] unknown []"
    assert err({"source": "x", "extra": 1}) == "input keys invalid: missing [] unknown ['extra']"
    assert err({"source": 5}) == "source must be a string"
    assert err({"source": "x" * 65537}) == "source exceeds 65536 characters"
    assert err({"source": "x\x00"}) == "source contains NUL"
    assert err({"source": "\ud800"}) == "source is not UTF-8 encodable"
    assert err({"source": "# a\rx = 1\n"}) == "source must use LF or CRLF line breaks"
    assert err({"source": "x = 1\r"}) == "source must use LF or CRLF line breaks"
    assert err({"source": "#\n" * 2001}) == "source exceeds 2000 lines"
    assert re.match(r"^syntax_error: line 1 col \d+: .+", err({"source": "def f(:\n"}))
    assert re.match(r"^syntax_error: line \d+ col \d+: .+", err({"source": "if x:\n  a\n b\n"}))


def test_char_and_line_bounds_n_and_n_plus_1():
    assert run("#" + "a" * 65535)["comment_count"] == 1
    assert err({"source": "#" + "a" * 65536}) == "source exceeds 65536 characters"
    assert run("#\n" * 2000)["line_count"] == 2000 and run("#\r\n" * 2000)["line_count"] == 2000
    assert run("\n".join(["#"] * 2000))["line_count"] == 2000
    assert err({"source": "\n".join(["#"] * 2001)}) == "source exceeds 2000 lines"
    assert err({"source": "#\r\n" * 2001}) == "source exceeds 2000 lines"


def token_count(src):
    return len(list(tokenize.generate_tokens(io.StringIO(src).readline)))


def test_token_bound_n_and_n_plus_1():
    n40000 = "0;" * 19999
    n40001 = "0;" * 19999 + "0"
    assert token_count(n40000) == 40000 and token_count(n40001) == 40001
    assert run(n40000)["comment_count"] == 0
    assert err({"source": n40001}) == "source exceeds 40000 tokens"


def test_symbol_bound_n_and_n_plus_1():
    assert len(run("\n".join("def f%d(): pass" % i for i in range(500)))["symbols"]) == 500
    assert err({"source": "\n".join("def f%d(): pass" % i for i in range(501))}) == "more than 500 symbols"


@pytest.mark.parametrize("src", ["x = $\n", "class\n", "print 'x'\n", "x = (\n", "'''unterminated\n", "\ufeffx = 1\n"])
def test_syntax_errors_are_refused_not_tokenized(src):
    assert err({"source": src}).startswith("syntax_error: line ")


def test_deeply_nested_input_is_refusal_or_success_not_crash():
    for src in ["(" * 500 + ")" * 500, "x = " + "[" * 150 + "]" * 150]:
        try:
            run(src)
        except ValueError as exc:
            assert re.match(r"^(syntax_error|resource_limit)", str(exc))


# ---------------------------------------------------------------- generated corpus vs construction oracle
PROSE = [" Compute the total.", " because the API requires it", " see the design note", " handle the edge case", " why: speed"]
MARKERS = [(" TODO fix", ["marker_without_owner_or_ref"]), (" TODO(ana) fix", []), (" FIXME[ABC-12] later", [])]
DIRECT = [" type: ignore", " noqa: E501", " pylint: disable=x", " fmt: off"]
CODEISH = [" x = 1", " foo(bar)", " return y", " import os"]
RATIONALE = re.compile(r"\b(because|since|so that|to avoid|workaround|work around|due to|in order to|otherwise|required by|why|in case)\b", re.I)


def pick_comment(rng):
    k = rng.randrange(5)
    if k == 0:
        t = rng.choice(PROSE)
        return t, "prose", []
    if k == 1:
        t, f = rng.choice(MARKERS)
        return t, "marker", f
    if k == 2:
        return rng.choice(DIRECT), "directive", []
    if k == 3:
        return rng.choice(CODEISH), "prose", ["commented_out_code_candidate"]
    return "", "empty", ["empty_comment"]


def gen_source(rng):
    lines, exp, n = [], [], 0
    body = []  # (kind, indent)
    for _ in range(rng.randrange(3, 14)):
        body.append(rng.choice(["code", "inline", "stand", "blank", "trap", "tripletrap"]))
    out_lines = []
    in_func = rng.random() < 0.5
    ind = "    " if in_func else ""
    if in_func:
        out_lines.append(("def fn():", None))
    for kind in body:
        n += 1
        if kind == "code":
            out_lines.append((ind + "v%d = %d" % (n, n), None))
        elif kind == "inline":
            t, c, f = pick_comment(rng)
            if c == "empty":
                code = ind + "v%d = %d  #" % (n, n)
            else:
                code = ind + "v%d = %d  #%s" % (n, n, t)
            out_lines.append((code, ("inline", len(ind + "v%d = %d  " % (n, n)), t, c, f)))
        elif kind == "stand":
            t, c, f = pick_comment(rng)
            if c == "empty":
                f = []  # decided by block context below
            out_lines.append((ind + "#" + t, ("stand", len(ind), t, c, f)))
        elif kind == "blank":
            out_lines.append(("", None))
        elif kind == "trap":
            out_lines.append((ind + "s%d = \"#fake %d\"" % (n, n), None))
        else:
            out_lines.append((ind + "t%d = '''" % n, None))
            out_lines.append(("# fake in string", None))
            out_lines.append(("'''", None))
    out_lines.append((ind + "pass", None))
    return out_lines


def oracle(out_lines):
    comments = []
    for i, (text, meta) in enumerate(out_lines, 1):
        if meta:
            kind, col, t, c, f = meta
            comments.append({"line": i, "col": col, "kind": kind, "text": t, "category": c, "flags": list(f), "end_col": col + 1 + len(t)})
    # blocks: consecutive standalone comments, same col
    blocks, cur = [], []
    for cm in comments:
        if cm["kind"] == "stand" and cur and cur[-1]["line"] + 1 == cm["line"] and cur[-1]["col"] == cm["col"]:
            cur.append(cm)
            continue
        if cur:
            blocks.append(cur)
        cur = [cm] if cm["kind"] == "stand" else []
    if cur:
        blocks.append(cur)
    code_lines = {i for i, (t, _) in enumerate(out_lines, 1) if t.strip() and not t.strip().startswith("#")}
    # string-interior and comment lines are not "code"; recompute precisely
    return comments, blocks


def test_generated_sources_match_construction_oracle():
    rng = random.Random(706)
    checked = blocks_seen = 0
    for _ in range(300):
        out_lines = gen_source(rng)
        src = "\n".join(t for t, _ in out_lines) + "\n"
        try:
            ast.parse(src)
        except SyntaxError:
            continue
        res = run(src)
        want, wblocks = oracle(out_lines)
        assert [(c["line"], c["col"], c["end_col"], c["kind"], c["text"]) for c in res["comments"]] == [(w["line"], w["col"], w["end_col"], "inline" if w["kind"] == "inline" else "standalone", w["text"]) for w in want], src
        for c, w in zip(res["comments"], want):
            assert c["category"] == w["category"], (src, c)
            multi = any(len(b) > 1 and w in b for b in wblocks)
            wf = ([] if multi else ["empty_comment"]) if w["category"] == "empty" else w["flags"]
            assert c["flags"] == sorted(wf), (src, c)
            assert c["has_rationale_keyword"] == bool(RATIONALE.search(w["text"]))
        got_blocks = [[c["line"] for c in res["comments"] if c["block_id"] == b["id"]] for b in res["blocks"]]
        assert got_blocks == [[w["line"] for w in b] for b in wblocks]
        for b, wb in zip(res["blocks"], wblocks):
            nxt = wb[-1]["line"] + 1
            ok = nxt <= len(out_lines) and out_lines[nxt - 1][0].strip() != "" and not out_lines[nxt - 1][0].strip().startswith("#")
            assert b["associated_line"] == (nxt if ok else None)
        blocks_seen += len(wblocks)
        checked += len(want)
    assert checked > 400 and blocks_seen > 100


# ---------------------------------------------------------------- determinism, purity, honesty
def test_deterministic_no_mutation_and_json_safe():
    d = {"source": S1 + TRAP.replace("s = ", "s2 = "), "max_line_length": 60}
    snap = copy.deepcopy(d)
    a, b = audit(d), audit(d)
    assert d == snap and json.dumps(a) == json.dumps(b)
    assert json.loads(json.dumps(a, allow_nan=False)) == a


def test_source_hash_binding_and_counts():
    import hashlib
    res = run(S1)
    assert res["source_sha256"] == hashlib.sha256(S1.encode()).hexdigest() and res["source_chars"] == len(S1) and res["source_bytes"] == len(S1.encode())
    assert run(S1 + "\n")["source_sha256"] != res["source_sha256"]


def test_module_is_pure_and_never_executes_source(tmp_path):
    tree = ast.parse(MODULE_PATH.read_text())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add((n.module or "").split(".")[0])
    assert mods <= {"__future__", "ast", "hashlib", "io", "re", "tokenize", "typing", "warnings"}, mods
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not (called & {"eval", "exec", "compile", "__import__", "open", "globals", "locals"})
    marker = tmp_path / "ran"
    src = "open(%r, 'w').write('x')  # side effect\n" % str(marker)
    run(src)
    assert not marker.exists()


def test_limits_stated():
    res = run("# a\n")
    text = " ".join(res["limits"])
    for w in ("candidate", "lexical", "explains", "tokenizer", "not executed"):
        assert w in text
    assert res["algorithm"] == "python_comment_audit_v1"
    assert res["position_convention"] == "line 1-based; col 0-based Unicode code points; end exclusive; line breaks LF, CRLF"


# ---------------------------------------------------------------- mutation-audit additions (survivors of the first audit)
def _body(n, comment_at=None, extra=""):
    lines = ["def f():"] + ["    x = %d" % i for i in range(n - 1)]
    if comment_at is not None:
        lines[comment_at] += "  # c"
    return "\n".join(lines) + "\n" + extra


def test_default_min_lines_is_15_exactly():
    assert run(_body(15))["symbols"][0]["flags"] == ["long_symbol_without_comments"]
    assert run(_body(14))["symbols"][0]["flags"] == []
    assert run(_body(15))["options"] == {"max_line_length": 100, "min_lines_for_comment": 15}


def test_one_inner_comment_exempts_symbol_and_leading_block_exempts():
    assert run(_body(5, comment_at=2), min_lines_for_comment=3)["symbols"][0]["flags"] == []
    assert run(_body(5, comment_at=2), min_lines_for_comment=3)["symbols"][0]["inner_comment_count"] == 1
    s = run("# why\n" + _body(5), min_lines_for_comment=3)["symbols"][0]
    assert s["leading_block_id"] == "B0001" and s["flags"] == []


def test_inner_range_includes_last_line_and_excludes_def_line():
    s = run("def f():\n    return 1  # last\n")["symbols"][0]
    assert s["inner_comment_count"] == 1
    s = run("def f():  # on def line\n    return 1\n")["symbols"][0]
    assert s["inner_comment_count"] == 0


def test_decorated_symbol_starts_at_first_decorator():
    res = run("# lead\n@a\n@b\ndef f():\n    return 1\n")
    s = res["symbols"][0]
    assert (s["start_line"], s["end_line"], s["line_span"], s["leading_block_id"]) == (2, 5, 4, "B0001")


def test_wordless_prose_never_restates():
    res = run("x = 1  # ???\n# ...\ny = 2\n")
    assert [c["flags"] for c in res["comments"]] == [[], []]


def test_marker_and_directive_only_at_start_of_text():
    cs = run("x = 1  # see TODO later\ny = 2  # use noqa here\nz = 3  # a type: b\n")["comments"]
    assert [c["category"] for c in cs] == ["prose", "prose", "prose"]


def test_marker_reference_must_be_near_start():
    far = " TODO " + "." * 80 + " (ana)"
    assert run("# %s\nx = 1\n" % far.strip())["comments"][0]["flags"] == ["marker_without_owner_or_ref"]
    assert run("#  TODO(ana)\nx = 1\n")["comments"][0]["flags"] == []


def test_commented_code_needs_call_await_or_lambda_for_expressions():
    assert run("# lambda: 1\nx = 1\n")["comments"][0]["flags"] == ["commented_out_code_candidate"]
    assert run("# foo()\nx = 1\n")["comments"][0]["flags"] == ["commented_out_code_candidate"]
    assert run("# a + b\nx = 1\n")["comments"][0]["flags"] == []


def test_flags_are_sorted_when_long_and_code():
    res = run("x = 1  # " + "a = 1" + " " * 40 + "\n", max_line_length=40)
    assert res["comments"][0]["flags"] == ["commented_out_code_candidate", "long_comment_line"]
    res = run("# TODO " + "x" * 60 + "\nx = 1\n", max_line_length=40)
    assert res["comments"][0]["flags"] == ["long_comment_line", "marker_without_owner_or_ref"]


def test_multiline_string_lines_count_as_code_lines():
    assert run('x = """a\nb\nc"""\n')["code_line_count"] == 3
    assert run('x = 1\n\n# c\n')["code_line_count"] == 1
    assert run('s = (1,\n     2)  # c\n')["code_line_count"] == 2


def test_docstring_must_be_string_constant_first_statement():
    d = {s["name"]: s["has_docstring"] for s in run('def a():\n    "d"\n\ndef b():\n    42\n\ndef c():\n    f()\n\ndef d():\n    x = 1\n    "late"\n\ndef e():\n    b"x"\n')["symbols"]}
    assert d == {"a": True, "b": False, "c": False, "d": False, "e": False}
