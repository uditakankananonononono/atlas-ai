"""Ledger row 694, Legacy Code Modernization ("Updates old systems").

Scope note: the source text for this row is the single line "Updates old
systems". The scope below is builder-proposed from that line and has not been
ruled on by the owner or the reviewer.

What this module does: it takes Python source text and rewrites a fixed list
of idioms that no longer work on Python 3 (or were removed from recent
Python 3 releases), using Python's own ``ast`` module to find the exact source
spans. Every rewrite is a text edit of that span only; the rest of the file is
left byte-for-byte as it was. Cases it cannot decide from syntax alone are
refused and reported, not guessed. The result is compiled, and an optional
caller-supplied characterization check is run on the new source.

What it does not do: it does not parse Python 2 only syntax (print statements,
``except X, e``, backticks): those are reported as a ``syntax_error`` refusal.
It does not infer types. Rules that match on a method name (``has_key``,
``iteritems`` and the unittest aliases) assume the receiver is the obvious
kind of object; each Change carries that assumption in ``assumption``.
It does not execute the input unless the caller passes a check that does.
Nothing here is sandboxed.

Standard library only.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

RULES = frozenset(
    {"has_key", "unittest_aliases", "collections_abc", "string_module", "getcwdu", "xrange", "dict_iter"}
)
MAX_PASSES = 10

UNITTEST_ALIASES = {
    "assertEquals": "assertEqual",
    "assertNotEquals": "assertNotEqual",
    "assert_": "assertTrue",
    "failUnless": "assertTrue",
    "failIf": "assertFalse",
    "failUnlessEqual": "assertEqual",
    "assertAlmostEquals": "assertAlmostEqual",
    "assertNotAlmostEquals": "assertNotAlmostEqual",
    "assertRegexpMatches": "assertRegex",
    "assertNotRegexpMatches": "assertNotRegex",
    "assertRaisesRegexp": "assertRaisesRegex",
}
COLLECTIONS_ABCS = frozenset(
    {
        "Mapping", "MutableMapping", "Sequence", "MutableSequence", "Set", "MutableSet",
        "Iterable", "Iterator", "Callable", "Hashable", "Sized", "Container", "Generator",
        "Awaitable", "Coroutine", "AsyncIterable", "AsyncIterator", "AsyncGenerator",
        "Collection", "Reversible", "ByteString", "KeysView", "ItemsView", "ValuesView",
        "MappingView",
    }
)
DICT_ITER = {"iteritems": "items", "iterkeys": "keys", "itervalues": "values"}
SAFE_CONSUMERS = frozenset(
    {"sorted", "list", "tuple", "set", "frozenset", "sum", "min", "max", "any", "all", "enumerate"}
)
STRING_FUNCS = frozenset({"lower", "upper", "strip", "join"})


@dataclass(frozen=True)
class Change:
    rule: str
    line: int
    col: int  # ast col_offset: UTF-8 byte offset in that line, of the pass text
    before: str
    after: str
    pass_no: int
    assumption: str


@dataclass(frozen=True)
class Refusal:
    rule: str
    line: int
    col: int
    reason: str


@dataclass
class ModernizationResult:
    original: str
    modernized: str
    changes: list = field(default_factory=list)
    refusals: list = field(default_factory=list)
    passes: int = 0
    compiled_ok: bool = False
    check_passed: Optional[bool] = None
    check_error: Optional[str] = None
    verified: bool = False

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "modernized": self.modernized,
            "changes": [c.__dict__.copy() for c in self.changes],
            "refusals": [r.__dict__.copy() for r in self.refusals],
            "passes": self.passes,
            "compiled_ok": self.compiled_ok,
            "check_passed": self.check_passed,
            "check_error": self.check_error,
            "verified": self.verified,
        }


def characterization(cases: Iterable[tuple]) -> Callable[[str], bool]:
    """Build a check from (function_name, args_tuple, expected) cases.

    The returned callable executes the given source in a fresh namespace and
    calls each named function. It runs the source: the caller owns that risk.
    """
    cases = list(cases)

    def check(source: str) -> bool:
        ns: dict = {"__name__": "__characterization__"}
        exec(compile(source, "<characterization>", "exec"), ns)
        for name, args, expected in cases:
            fn = ns.get(name)
            if not callable(fn):
                return False
            if fn(*args) != expected:
                return False
        return True

    return check


_LINE_BREAK = re.compile(rb"\r\n|\r|\n")


def _line_starts(data: bytes) -> list:
    starts = [0]
    for m in _LINE_BREAK.finditer(data):
        starts.append(m.end())
    return starts


class _Ctx:
    def __init__(self, tree: ast.AST, data: bytes, rules: frozenset, pass_no: int):
        self.tree, self.data, self.rules, self.pass_no = tree, data, rules, pass_no
        self.starts = _line_starts(data)
        self.parent: dict = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                self.parent[child] = node
        self.edits: list = []  # (start, end, repl, Change)
        self.refusals: list = []

    def off(self, line: int, col: int) -> int:
        return self.starts[line - 1] + col

    def span(self, node) -> tuple:
        return self.off(node.lineno, node.col_offset), self.off(node.end_lineno, node.end_col_offset)

    def seg(self, node) -> str:
        a, b = self.span(node)
        return self.data[a:b].decode("utf-8")

    def atom(self, node) -> str:
        text = self.seg(node)
        if isinstance(node, (ast.Name, ast.Attribute, ast.Subscript, ast.Call, ast.List, ast.Dict,
                             ast.Set, ast.ListComp, ast.SetComp, ast.DictComp, ast.JoinedStr)):
            return text
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            return text
        return "(" + text + ")"

    def edit(self, rule: str, node, start: int, end: int, repl: str, assumption: str) -> None:
        before = self.data[start:end].decode("utf-8")
        ch = Change(rule, node.lineno, node.col_offset, before, repl, self.pass_no, assumption)
        self.edits.append((start, end, repl, ch))

    def refuse(self, rule: str, node, reason: str) -> None:
        self.refusals.append(Refusal(rule, node.lineno, node.col_offset, reason))

    def attr_span(self, attr_node: ast.Attribute) -> tuple:
        end = self.off(attr_node.end_lineno, attr_node.end_col_offset)
        start = end - len(attr_node.attr.encode("utf-8"))
        return start, end

    def is_bound_elsewhere(self, name: str, plain_import: bool) -> bool:
        """True if `name` is bound in the module by anything other than a plain import."""
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, (ast.Store, ast.Del)):
                return True
            if isinstance(n, ast.arg) and n.arg == name:
                return True
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == name:
                return True
            if isinstance(n, ast.ExceptHandler) and n.name == name:
                return True
            if isinstance(n, ast.Import):
                for a in n.names:
                    bound = a.asname or a.name.split(".")[0]
                    if bound == name and not (plain_import and a.asname is None):
                        return True
            if isinstance(n, ast.ImportFrom):
                for a in n.names:
                    if (a.asname or a.name) == name:
                        return True
        return False

    def plainly_imported(self, name: str) -> bool:
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    if a.asname is None and a.name.split(".")[0] == name:
                        return True
        return False

    def stdlib_name_ok(self, name: str) -> bool:
        return self.plainly_imported(name) and not self.is_bound_elsewhere(name, True)

    def no_paren_needed(self, node) -> bool:
        p = self.parent.get(node)
        if isinstance(p, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Return, ast.Expr, ast.BoolOp,
                          ast.keyword, ast.comprehension, ast.List, ast.Tuple, ast.Set)):
            return True
        if isinstance(p, (ast.If, ast.While, ast.Assert, ast.IfExp)):
            return p.test is node
        if isinstance(p, ast.UnaryOp) and isinstance(p.op, ast.Not):
            return True
        if isinstance(p, ast.Call):
            return node in p.args
        return False


def _plain_args(call: ast.Call, n_min: int, n_max: int) -> bool:
    return (
        not call.keywords
        and n_min <= len(call.args) <= n_max
        and not any(isinstance(a, ast.Starred) for a in call.args)
    )


def _rule_has_key(ctx: _Ctx, call: ast.Call) -> None:
    f = call.func
    if not (isinstance(f, ast.Attribute) and f.attr == "has_key"):
        return
    if not _plain_args(call, 1, 1):
        ctx.refuse("has_key", call, "has_key needs exactly one plain positional argument")
        return
    text = f"{ctx.atom(call.args[0])} in {ctx.atom(f.value)}"
    if not ctx.no_paren_needed(call):
        text = "(" + text + ")"
    a, b = ctx.span(call)
    ctx.edit("has_key", call, a, b, text, "receiver assumed to be a mapping (type not known statically)")


def _rule_unittest(ctx: _Ctx, call: ast.Call) -> None:
    f = call.func
    if not (isinstance(f, ast.Attribute) and f.attr in UNITTEST_ALIASES
            and isinstance(f.value, ast.Name) and f.value.id == "self"):
        return
    a, b = ctx.attr_span(f)
    if ctx.data[a:b].decode("utf-8") != f.attr:
        ctx.refuse("unittest_aliases", call, "could not locate the method name in source")
        return
    ctx.edit("unittest_aliases", call, a, b, UNITTEST_ALIASES[f.attr],
             "`self` assumed to be a unittest.TestCase")


def _rule_string(ctx: _Ctx, call: ast.Call) -> None:
    f = call.func
    if not (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
            and f.value.id == "string" and f.attr in STRING_FUNCS):
        return
    if not ctx.stdlib_name_ok("string"):
        return
    if f.attr == "join":
        if not _plain_args(call, 1, 2):
            ctx.refuse("string_module", call, "string.join needs one or two plain positional arguments")
            return
        seq = ctx.seg(call.args[0])
        sep = ctx.atom(call.args[1]) if len(call.args) == 2 else "' '"
        text = f"{sep}.join({seq})"
    else:
        if not _plain_args(call, 1, 1):
            ctx.refuse("string_module", call,
                       f"string.{f.attr} with extra arguments has no safe one-to-one str method form here")
            return
        text = f"{ctx.atom(call.args[0])}.{f.attr}()"
    a, b = ctx.span(call)
    ctx.edit("string_module", call, a, b, text, "`string` is the stdlib module: plain import, never rebound")


def _rule_getcwdu(ctx: _Ctx, call: ast.Call) -> None:
    f = call.func
    if not (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
            and f.value.id == "os" and f.attr == "getcwdu"):
        return
    if not ctx.stdlib_name_ok("os") or call.args or call.keywords:
        return
    a, b = ctx.attr_span(f)
    ctx.edit("getcwdu", call, a, b, "getcwd", "`os` is the stdlib module: plain import, never rebound")


def _rule_xrange(ctx: _Ctx, call: ast.Call) -> None:
    f = call.func
    if not (isinstance(f, ast.Name) and f.id == "xrange"):
        return
    if ctx.is_bound_elsewhere("xrange", False):
        return
    a, b = ctx.span(f)
    ctx.edit("xrange", call, a, b, "range", "`xrange` is not defined or rebound anywhere in the module")


def _rule_dict_iter(ctx: _Ctx, call: ast.Call) -> None:
    f = call.func
    if not (isinstance(f, ast.Attribute) and f.attr in DICT_ITER):
        return
    if call.args or call.keywords:
        ctx.refuse("dict_iter", call, f"{f.attr} called with arguments")
        return
    p = ctx.parent.get(call)
    ok = (
        (isinstance(p, (ast.For, ast.AsyncFor, ast.comprehension)) and p.iter is call)
        or (isinstance(p, ast.Call) and isinstance(p.func, ast.Name) and p.func.id in SAFE_CONSUMERS
            and p.args and p.args[0] is call)
    )
    if not ok:
        ctx.refuse("dict_iter", call,
                   f"{f.attr}() result is used outside a single-pass iteration context; "
                   f"{DICT_ITER[f.attr]}() returns a view, not an iterator")
        return
    a, b = ctx.attr_span(f)
    ctx.edit("dict_iter", call, a, b, DICT_ITER[f.attr],
             "receiver assumed to be a dict; result is consumed once in an iteration context")


def _rule_collections(ctx: _Ctx, node) -> None:
    if isinstance(node, ast.ImportFrom) and node.module == "collections" and node.level == 0:
        names = [a.name for a in node.names]
        abc = [n for n in names if n in COLLECTIONS_ABCS]
        if not abc:
            return
        if len(abc) != len(names):
            ctx.refuse("collections_abc", node,
                       "import mixes ABC names with other names; splitting the statement is not done")
            return
        a, b = ctx.span(node)
        m = re.match(r"from(\s+)collections(?=[\s(])", ctx.data[a:b].decode("utf-8"))
        if not m:
            ctx.refuse("collections_abc", node, "could not locate the module name in the import statement")
            return
        end = a + len(m.group(0).encode("utf-8"))
        ctx.edit("collections_abc", node, a, end, "from" + m.group(1) + "collections.abc",
                 "none beyond the Python 3.3+ collections.abc location")
    elif (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
          and node.value.id == "collections" and node.attr in COLLECTIONS_ABCS
          and ctx.plainly_imported("collections")):
        ctx.refuse("collections_abc", node,
                   "attribute form needs `import collections.abc`, which is not added; not rewritten")


_CALL_RULES = (
    ("has_key", _rule_has_key),
    ("unittest_aliases", _rule_unittest),
    ("string_module", _rule_string),
    ("getcwdu", _rule_getcwdu),
    ("xrange", _rule_xrange),
    ("dict_iter", _rule_dict_iter),
)


def _collect(tree: ast.AST, data: bytes, rules: frozenset, pass_no: int) -> _Ctx:
    ctx = _Ctx(tree, data, rules, pass_no)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for name, fn in _CALL_RULES:
                if name in rules:
                    fn(ctx, node)
        if "collections_abc" in rules and isinstance(node, (ast.ImportFrom, ast.Attribute)):
            _rule_collections(ctx, node)
    return ctx


def _apply(data: bytes, edits: list) -> tuple:
    """Apply non-overlapping edits, outermost first. Returns (new_bytes, applied_changes)."""
    applied, last_end, out, pos = [], -1, [], 0
    for start, end, repl, ch in sorted(edits, key=lambda e: (e[0], -e[1])):
        if start < last_end:
            continue  # nested inside an accepted edit: picked up on the next pass
        out.append(data[pos:start])
        out.append(repl.encode("utf-8"))
        pos, last_end = end, end
        applied.append(ch)
    out.append(data[pos:])
    return b"".join(out), applied


def modernize(
    source: str,
    *,
    rules: Optional[Iterable[str]] = None,
    check: Optional[Callable[[str], Any]] = None,
) -> ModernizationResult:
    if not isinstance(source, str):
        raise TypeError("source must be str")
    if rules is None:
        active = RULES
    else:
        active = frozenset(rules)
        unknown = active - RULES
        if unknown:
            raise ValueError(f"unknown rules: {sorted(unknown)}")
    res = ModernizationResult(original=source, modernized=source)
    text = source
    final_ctx = None
    for _ in range(MAX_PASSES + 1):
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError) as e:
            line = getattr(e, "lineno", None) or 1
            res.refusals = [Refusal("syntax_error", line, getattr(e, "offset", None) or 0,
                                    f"source does not parse as Python 3: {e.__class__.__name__}: {e}")]
            res.modernized = source if not res.changes else text
            res.compiled_ok = False
            return _finish(res, check)
        ctx = _collect(tree, text.encode("utf-8"), active, res.passes + 1)
        if not ctx.edits:
            final_ctx = ctx
            break
        if res.passes >= MAX_PASSES:
            final_ctx = ctx
            final_ctx.refusals.append(Refusal("max_passes", 1, 0, "rewrites still pending after the pass limit"))
            break
        new, applied = _apply(text.encode("utf-8"), ctx.edits)
        res.changes.extend(applied)
        res.passes += 1
        text = new.decode("utf-8")
    res.modernized = text
    res.refusals = sorted(final_ctx.refusals, key=lambda r: (r.line, r.col, r.rule))
    try:
        compile(text, "<modernized>", "exec")
        res.compiled_ok = True
    except (SyntaxError, ValueError):
        res.compiled_ok = False
    return _finish(res, check)


def _finish(res: ModernizationResult, check) -> ModernizationResult:
    if not res.compiled_ok:
        try:
            compile(res.modernized, "<modernized>", "exec")
            res.compiled_ok = True
        except (SyntaxError, ValueError):
            res.compiled_ok = False
    if check is not None:
        if not res.compiled_ok:
            res.check_passed, res.check_error = False, "not run: modernized source does not compile"
        else:
            try:
                res.check_passed = bool(check(res.modernized))
            except Exception as e:  # the caller's check may fail in any way
                res.check_passed, res.check_error = False, f"{type(e).__name__}: {e}"
    res.verified = res.compiled_ok and res.check_passed is True
    return res
