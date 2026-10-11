"""Row703 Documentation Generation: API facts from a Python AST, never from execution.

Parses supplied source text with ast.parse (no compile, no exec, no import) and reports
signatures, annotations, defaults, decorators, docstrings and source ranges exactly as
written. Anything the source does not state is reported as missing or unknown, never inferred.
See docs/M20_DOC703_CONTRACT.md.
"""
from __future__ import annotations

import ast
import hashlib
import re
import warnings
from typing import Any

ALGORITHM = "python_ast_api_documentation_v1"
MAX_CHARS = 65536
MAX_LINES = 2000
MAX_NODES = 20000
MAX_SYMBOLS = 500
MAX_DEPTH = 8
POSITION_CONVENTION = "line 1-based; col 0-based Unicode code points; end exclusive; line breaks LF, CRLF, CR"
LIMITS = [
    "source is parsed, never executed or imported; decorators, defaults and annotations are source text, not evaluated",
    "decorator semantics (staticmethod, property, wrappers) are not interpreted",
    "annotation and default text is exact source text; string annotations are not resolved",
    "docstring text is preserved verbatim; no sections, parameters or behavior are parsed or inferred from it",
    "lambda expressions and comprehensions are not symbols; only def, async def and class statements are",
    "class constructor signatures are not derived",
    "grammar accepted is that of the Python interpreter running Atlas",
]
UNKNOWN_FUNCTION = ["parameter_descriptions", "return_description", "raises", "side_effects", "behavior", "thread_safety"]
UNKNOWN_CLASS = ["attributes", "behavior", "invariants", "thread_safety"]
_LINE = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+")
_FILENAME = re.compile(r"[A-Za-z0-9_./-]{1,128}")
_HEX = re.compile(r"[0-9a-f]{64}")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _Source:
    def __init__(self, text: str) -> None:
        self.text = text
        self.lines = _LINE.findall(text)
        self.bytes = [ln.encode("utf-8") for ln in self.lines]
        self.starts, total = [], 0
        for ln in self.lines:
            self.starts.append(total)
            total += len(ln)

    def col(self, line: int, byte_col: int) -> int:
        return len(self.bytes[line - 1][:byte_col].decode("utf-8"))

    def pos(self, line: int, byte_col: int) -> dict:
        return {"line": line, "col": self.col(line, byte_col)}

    def flat(self, p: dict) -> int:
        return self.starts[p["line"] - 1] + p["col"]

    def rng(self, node: ast.AST) -> dict:
        return {"start": self.pos(node.lineno, node.col_offset), "end": self.pos(node.end_lineno, node.end_col_offset)}

    def slice(self, rng: dict) -> str:
        return self.text[self.flat(rng["start"]):self.flat(rng["end"])]

    def seg(self, node: ast.AST) -> str:
        return self.slice(self.rng(node))


def _check_input(data: Any) -> tuple:
    if not isinstance(data, dict):
        raise ValueError("input must be an object")
    required, optional = {"source"}, {"filename", "expected_sha256"}
    keys = set(data)
    if any(type(k) is not str for k in data) or required - keys or keys - required - optional:
        raise ValueError(f"input keys invalid: missing {sorted(required - keys)} unknown {sorted(keys - required - optional, key=str)}")
    source = data["source"]
    if type(source) is not str:
        raise ValueError("source must be a string")
    filename = data.get("filename")
    if "filename" in data and (type(filename) is not str or not _FILENAME.fullmatch(filename)):
        raise ValueError("filename must be 1..128 characters of letters, digits and _./-")
    expected = data.get("expected_sha256")
    if "expected_sha256" in data and (type(expected) is not str or not _HEX.fullmatch(expected)):
        raise ValueError("expected_sha256 must be 64 lowercase hex characters")
    return source, filename, expected


def _params(src: _Source, args: ast.arguments) -> list:
    out = []

    def add(arg: ast.arg, kind: str, default: ast.AST | None) -> None:
        out.append({"name": arg.arg, "kind": kind, "annotation": src.seg(arg.annotation) if arg.annotation else None,
                    "default": src.seg(default) if default is not None else None, "has_default": default is not None,
                    "description": None, "semantics": "unknown"})

    positional = args.posonlyargs + args.args
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    for i, (arg, dflt) in enumerate(zip(positional, defaults)):
        add(arg, "positional_only" if i < len(args.posonlyargs) else "positional_or_keyword", dflt)
    if args.vararg:
        add(args.vararg, "var_positional", None)
    for arg, dflt in zip(args.kwonlyargs, args.kw_defaults):
        add(arg, "keyword_only", dflt)
    if args.kwarg:
        add(args.kwarg, "var_keyword", None)
    return out


def _signature_text(params: list, returns: str | None, n_posonly: int, has_kwonly: bool) -> str:
    parts, seen_var = [], False
    for i, p in enumerate(params):
        if p["kind"] == "keyword_only" and not seen_var:
            parts.append("*")
            seen_var = True
        text = {"var_positional": "*", "var_keyword": "**"}.get(p["kind"], "") + p["name"]
        if p["kind"] == "var_positional":
            seen_var = True
        if p["annotation"] is not None:
            text += ": " + p["annotation"]
        if p["default"] is not None:
            text += (" = " if p["annotation"] is not None else "=") + p["default"]
        parts.append(text)
        if p["kind"] == "positional_only" and (i + 1 == len(params) or params[i + 1]["kind"] != "positional_only"):
            parts.append("/")
    return "(" + ", ".join(parts) + ")" + (" -> " + returns if returns is not None else "")


def _docstring(src: _Source, node: ast.AST) -> dict | None:
    body = node.body
    if not body or not isinstance(body[0], ast.Expr) or not isinstance(body[0].value, ast.Constant) or type(body[0].value.value) is not str:
        return None
    return {"raw": ast.get_docstring(node, clean=False), "cleaned": ast.get_docstring(node, clean=True), "range": src.rng(body[0])}


def _decorators(src: _Source, node: ast.AST) -> tuple:
    decs = [{"source": src.seg(d), "range": src.rng(d)} for d in node.decorator_list]
    start = {"line": node.lineno, "col": src.col(node.lineno, node.col_offset)}
    if decs:
        first = decs[0]["range"]["start"]
        i = src.flat(first) - 1
        while i >= 0 and src.text[i] in " \t\f\\\r\n":
            i -= 1
        at = i  # flat offset of '@'
        line = max(n for n, s in enumerate(src.starts, 1) if s <= at)
        start = {"line": line, "col": at - src.starts[line - 1]}
    return decs, start


def _child_blocks(node: ast.AST) -> list:
    blocks = []
    for field in ("body", "orelse", "finalbody"):
        value = getattr(node, field, None)
        if isinstance(value, list):
            blocks.append(value)
    for h in getattr(node, "handlers", []) or []:
        blocks.append(h.body)
    for c in getattr(node, "cases", []) or []:
        blocks.append(c.body)
    return blocks


def _collect(src: _Source, tree: ast.Module) -> list:
    symbols, counts = [], {}

    def visit(block: list, qprefix: str, parent: dict | None, depth: int, scope: str) -> None:
        for node in block:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if depth + 1 > MAX_DEPTH:
                    raise ValueError(f"scope nesting exceeds {MAX_DEPTH}")
                if len(symbols) >= MAX_SYMBOLS:
                    raise ValueError(f"more than {MAX_SYMBOLS} symbols")
                symbols.append(_symbol(src, node, qprefix, parent, depth, scope, counts))
                me = symbols[-1]
                is_class = isinstance(node, ast.ClassDef)
                visit(node.body, me["qualname"] + ("." if is_class else ".<locals>."), me, depth + 1, "class" if is_class else "function")
            else:
                for b in _child_blocks(node):
                    visit(b, qprefix, parent, depth, scope)

    visit(tree.body, "", None, 0, "module")
    return symbols


def _symbol(src: _Source, node: ast.AST, qprefix: str, parent: dict | None, depth: int, scope: str, counts: dict) -> dict:
    qual = qprefix + node.name
    counts[qual] = counts.get(qual, 0) + 1
    decs, start = _decorators(src, node)
    end = src.pos(node.end_lineno, node.end_col_offset)
    rng = {"start": start, "end": end}
    doc = _docstring(src, node)
    is_class = isinstance(node, ast.ClassDef)
    sym = {"id": f"{qual}#{counts[qual]}", "kind": "class" if is_class else "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
           "name": node.name, "qualname": qual, "parent_id": parent["id"] if parent else None, "depth": depth, "scope": scope,
           "def_line": node.lineno, "range": rng, "range_sha256": _sha(src.slice(rng)), "decorators": decs, "decorator_semantics": "not_interpreted",
           "type_params": [src.seg(t) for t in getattr(node, "type_params", [])], "docstring": doc}
    documented = doc is not None and bool(doc["cleaned"].strip())
    if is_class:
        sym.update(bases=[src.seg(b) for b in node.bases],
                   keywords=[{"name": k.arg, "value": src.seg(k.value)} for k in node.keywords],
                   constructor_signature="not_derived", missing={"docstring": not documented}, unknown_semantics=list(UNKNOWN_CLASS))
    else:
        params = _params(src, node.args)
        returns = src.seg(node.returns) if node.returns else None
        sym.update(parameters=params, returns=returns, return_description=None,
                   signature_text=_signature_text(params, returns, len(node.args.posonlyargs), bool(node.args.kwonlyargs)),
                   missing={"docstring": not documented, "return_annotation": returns is None,
                            "unannotated_parameters": [p["name"] for p in params if p["annotation"] is None]},
                   unknown_semantics=list(UNKNOWN_FUNCTION))
    sym["semantics_derived"] = False
    return sym


def generate(data: Any) -> dict:
    """Return machine-readable API documentation facts. Raises ValueError with an exact reason on refusal."""
    source, filename, expected = _check_input(data)
    if len(source) > MAX_CHARS:
        raise ValueError(f"source exceeds {MAX_CHARS} characters")
    if "\x00" in source:
        raise ValueError("source contains NUL")
    try:
        encoded = source.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("source is not UTF-8 encodable") from None
    digest = hashlib.sha256(encoded).hexdigest()
    if expected is not None and expected != digest:
        raise ValueError("expected_sha256 mismatch")
    src = _Source(source)
    if len(src.lines) > MAX_LINES:
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
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise ValueError(f"ast exceeds {MAX_NODES} nodes")
    symbols = _collect(src, tree)
    return {"algorithm": ALGORITHM, "status": "generated", "filename": filename, "source_sha256": digest,
            "source_chars": len(source), "source_bytes": len(encoded), "line_count": len(src.lines),
            "position_convention": POSITION_CONVENTION,
            "module": {"docstring": _docstring(src, tree)}, "symbols": symbols, "symbol_count": len(symbols),
            "limits": list(LIMITS), "code_executed": False, "imports_resolved": False, "semantics_derived": False}
