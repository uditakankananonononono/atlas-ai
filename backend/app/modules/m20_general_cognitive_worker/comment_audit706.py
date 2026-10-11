"""Row706 Code Comments: tokenizer-based comment extraction and mechanical audit of Python source.

Comments come from the Python tokenizer, so '#' inside strings never counts. Everything reported is a
lexical or structural fact (position, grouping, category, literal-echo and commented-out-code candidates,
rationale keywords, symbol coverage). Whether a comment explains the code well is not judged.
Source is parsed and tokenized only, never executed. See docs/M20_COMMENTS706_CONTRACT.md.
"""
from __future__ import annotations

import ast
import hashlib
import io
import re
import tokenize
import warnings
from typing import Any

ALGORITHM = "python_comment_audit_v1"
POSITION_CONVENTION = "line 1-based; col 0-based Unicode code points; end exclusive; line breaks LF, CRLF"
MAX_CHARS = 65536
MAX_LINES = 2000
MAX_TOKENS = 40000
MAX_SYMBOLS = 500
DEFAULT_MAX_LINE = 100
DEFAULT_MIN_SPAN = 15
LIMITS = [
    "source is parsed and tokenized only; it is not executed, imported or evaluated",
    "comments are found by the Python tokenizer, so '#' inside string literals is never a comment",
    "commented_out_code_candidate and restates_code_candidate are lexical candidates, not findings: prose that parses as code or repeats the code's words can be flagged",
    "restates_code_candidate fires only when every comment word literally appears in the code line's words",
    "has_rationale_keyword is a lexical keyword match (because, since, so that, to avoid, workaround, work around, due to, in order to, otherwise, required by, why, in case); it does not mean the comment explains why",
    "whether a comment explains, helps, is accurate or is up to date is not judged",
    "marker owner/reference detection is lexical: a parenthesized word, a TICKET-123 style id or #123 within the first 80 characters",
    "symbol coverage uses line ranges only: a comment block on the line before a def or class counts as leading regardless of indentation",
    "a bare annotation such as 'why: speed' parses as code but is treated as a label, not commented-out code",
    "grammar accepted is that of the Python interpreter running Atlas; bare CR line breaks are refused",
]
_MARKER = re.compile(r"(TODO|FIXME|HACK|XXX|NOTE)\b")
_MARKER_REF = re.compile(r"\([^)\s][^)]*\)|\b[A-Z][A-Z0-9]+-[0-9]+\b|#[0-9]+")
_DIRECTIVE = re.compile(r"(type:|noqa\b|pragma\b|pylint:|fmt:|isort:|mypy:|pyright:|nosec\b|flake8\b|ruff:)")
_CODING = re.compile(r"[ \t\f]*#.*?coding[:=][ \t]*[-\w.]+")
_RATIONALE = re.compile(r"\b(because|since|so that|to avoid|workaround|work around|due to|in order to|otherwise|required by|why|in case)\b", re.I)
_WORD = re.compile(r"[A-Za-z0-9]+")
_CAMEL = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])")
_SKIP_TOKENS = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER}
CATEGORIES = ("directive", "empty", "marker", "prose")


def _int_option(data: dict, name: str, default: int, lo: int, hi: int) -> int:
    if name not in data:
        return default
    v = data[name]
    if type(v) is not int or not lo <= v <= hi:
        raise ValueError(f"{name} must be an integer {lo}..{hi}")
    return v


def _words(text: str) -> set:
    return {w.lower() for w in _WORD.findall(text)}


def _code_words(tokens_on_line: list) -> set:
    out = set()
    for s in tokens_on_line:
        out.add(s.lower())
        out.update(w.lower() for w in _WORD.findall(s))
        out.update(w.lower() for w in _CAMEL.findall(s))
    return out


def _looks_like_code(text: str) -> bool:
    body = text.strip()
    if not body:
        return False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(body)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return False
    if any(not isinstance(stmt, ast.Expr) and not (isinstance(stmt, ast.AnnAssign) and stmt.value is None) for stmt in tree.body):
        return True
    return any(isinstance(n, (ast.Call, ast.Await, ast.Lambda)) for n in ast.walk(tree))


def _category(token_string: str, text: str, line: int, kind: str) -> str:
    if kind == "standalone" and ((line == 1 and token_string.startswith("#!")) or (line <= 2 and _CODING.match(token_string))):
        return "directive"
    stripped = text.lstrip()
    if _DIRECTIVE.match(stripped):
        return "directive"
    if not stripped:
        return "empty"
    if _MARKER.match(stripped):
        return "marker"
    return "prose"


def audit(data: Any) -> dict:
    """Audit comments in supplied Python source. Raises ValueError with an exact reason on refusal."""
    if not isinstance(data, dict):
        raise ValueError("input must be an object")
    required, optional = {"source"}, {"max_line_length", "min_lines_for_comment"}
    keys = set(data)
    if any(type(k) is not str for k in data) or required - keys or keys - required - optional:
        raise ValueError(f"input keys invalid: missing {sorted(required - keys)} unknown {sorted(keys - required - optional, key=str)}")
    source = data["source"]
    if type(source) is not str:
        raise ValueError("source must be a string")
    max_line = _int_option(data, "max_line_length", DEFAULT_MAX_LINE, 40, 200)
    min_span = _int_option(data, "min_lines_for_comment", DEFAULT_MIN_SPAN, 1, 500)
    if len(source) > MAX_CHARS:
        raise ValueError(f"source exceeds {MAX_CHARS} characters")
    if "\x00" in source:
        raise ValueError("source contains NUL")
    try:
        encoded = source.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("source is not UTF-8 encodable") from None
    if re.search(r"\r(?!\n)", source):
        raise ValueError("source must use LF or CRLF line breaks")
    line_count = source.count("\n") + (1 if source and not source.endswith("\n") else 0)
    if line_count > MAX_LINES:
        raise ValueError(f"source exceeds {MAX_LINES} lines")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"syntax_error: line {exc.lineno or 0} col {exc.offset or 0}: {exc.msg}") from None
    except (RecursionError, MemoryError):
        raise ValueError("resource_limit: parser exceeded recursion or memory bounds") from None
    except ValueError as exc:
        raise ValueError(f"syntax_error: line 0 col 0: {exc}") from None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, SyntaxError) as exc:
        raise ValueError(f"syntax_error: line 0 col 0: tokenize failed: {exc}") from None
    if len(tokens) > MAX_TOKENS:
        raise ValueError(f"source exceeds {MAX_TOKENS} tokens")
    nodes = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    if len(nodes) > MAX_SYMBOLS:
        raise ValueError(f"more than {MAX_SYMBOLS} symbols")

    code_lines: set = set()
    words_on_line: dict = {}
    for t in tokens:
        if t.type in _SKIP_TOKENS:
            continue
        code_lines.update(range(t.start[0], t.end[0] + 1))
        if t.type in (tokenize.NAME, tokenize.NUMBER):
            words_on_line.setdefault(t.start[0], []).append(t.string)

    comments = []
    for t in tokens:
        if t.type != tokenize.COMMENT:
            continue
        line, col = t.start
        kind = "standalone" if t.line[:col].strip() == "" else "inline"
        text = t.string[1:]
        comments.append({"id": "C%04d" % (len(comments) + 1), "line": line, "col": col, "end_col": t.end[1], "kind": kind, "text": text,
                         "category": _category(t.string, text, line, kind), "flags": [], "has_rationale_keyword": bool(_RATIONALE.search(text)),
                         "block_id": None, "associated_line": line if kind == "inline" else None})

    blocks, cur = [], []
    for c in comments:
        if c["kind"] != "standalone":
            continue
        if cur and cur[-1]["line"] + 1 == c["line"] and cur[-1]["col"] == c["col"]:
            cur.append(c)
        else:
            if cur:
                blocks.append(cur)
            cur = [c]
    if cur:
        blocks.append(cur)
    block_out = []
    for i, members in enumerate(blocks, 1):
        bid = "B%04d" % i
        nxt = members[-1]["line"] + 1
        assoc = nxt if nxt in code_lines else None
        for m in members:
            m["block_id"], m["associated_line"] = bid, assoc
        block_out.append({"id": bid, "first_line": members[0]["line"], "last_line": members[-1]["line"], "col": members[0]["col"],
                          "comment_ids": [m["id"] for m in members], "associated_line": assoc})
    in_block = {m["id"]: len(members) > 1 for members in blocks for m in members}

    for c in comments:
        flags = []
        if c["category"] == "prose":
            if _looks_like_code(c["text"]):
                flags.append("commented_out_code_candidate")
            cw = _words(c["text"])
            if cw and c["associated_line"] in words_on_line and cw <= _code_words(words_on_line[c["associated_line"]]):
                flags.append("restates_code_candidate")
        elif c["category"] == "marker":
            if not _MARKER_REF.search(c["text"].lstrip()[:80]):
                flags.append("marker_without_owner_or_ref")
        elif c["category"] == "empty" and not in_block.get(c["id"], False):
            flags.append("empty_comment")
        if c["end_col"] > max_line:
            flags.append("long_comment_line")
        c["flags"] = sorted(flags)

    symbols = []
    for n in sorted(nodes, key=lambda n: (min([n.lineno] + [d.lineno for d in n.decorator_list]), n.col_offset)):
        start = min([n.lineno] + [d.lineno for d in n.decorator_list])
        lead = next((b["id"] for b in block_out if b["last_line"] == start - 1), None)
        inner = sum(1 for c in comments if n.lineno < c["line"] <= n.end_lineno)
        span = n.end_lineno - start + 1
        body = n.body
        doc = bool(body) and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and type(body[0].value.value) is str
        symbols.append({"name": n.name, "kind": "class" if isinstance(n, ast.ClassDef) else "async_function" if isinstance(n, ast.AsyncFunctionDef) else "function",
                        "start_line": start, "end_line": n.end_lineno, "line_span": span, "has_docstring": doc, "leading_block_id": lead,
                        "inner_comment_count": inner, "flags": ["long_symbol_without_comments"] if span >= min_span and inner == 0 and lead is None else []})

    by_flag: dict = {}
    for c in comments:
        for f in c["flags"]:
            by_flag[f] = by_flag.get(f, 0) + 1
    return {"algorithm": ALGORITHM, "status": "audited", "source_sha256": hashlib.sha256(encoded).hexdigest(), "source_chars": len(source),
            "source_bytes": len(encoded), "line_count": line_count, "code_line_count": len(code_lines), "comment_count": len(comments),
            "options": {"max_line_length": max_line, "min_lines_for_comment": min_span}, "position_convention": POSITION_CONVENTION,
            "comments": comments, "blocks": block_out, "symbols": symbols,
            "counts": {"by_category": {k: sum(1 for c in comments if c["category"] == k) for k in CATEGORIES},
                       "by_kind": {"inline": sum(1 for c in comments if c["kind"] == "inline"), "standalone": sum(1 for c in comments if c["kind"] == "standalone")},
                       "by_flag": dict(sorted(by_flag.items()))},
            "limits": list(LIMITS), "code_executed": False, "semantics_judged": False}
