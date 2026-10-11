"""Row 707 Naming Conventions: bounded AST identifier inspection against explicit rules.

Scope: parses Python source text with ast.parse (never executes, imports or compiles
it) and compares the identifiers the author wrote against naming rules the caller
declares. Nothing is inferred from the source's own style or from an organisation's
habits. Standard library only; needs Python 3.10+ (alias node positions).
"""
import ast
import bisect
import hashlib
import re
import unicodedata
import warnings

MAX_SOURCE_BYTES = 262144
MAX_NODES = 20000
MAX_RULES = 32
MAX_ACRONYMS = 64
MAX_ID_LEN = 64

KINDS = ("function", "method", "class", "parameter", "local", "module_variable",
         "class_attribute", "import_alias")
STYLES = ("snake_case", "UPPER_SNAKE", "PascalCase", "camelCase")
SCOPES = ("module", "class", "function")
RESERVED_RULE_IDS = ("SHADOW",)
POSITION_UNIT = "1-based line; 1-based column in Unicode code points; end_col exclusive"
NOT_INSPECTED = ("attribute_targets", "del_targets", "match_patterns",
                 "names_in_strings_and_comments", "subscript_targets", "unrenamed_imports")

_TOP_KEYS = ("rules", "acronyms", "forbid_shadowing")
_RULE_KEYS = ("id", "kinds", "style", "scope", "allow_leading_underscore",
              "allow_trailing_underscore", "dunder", "acronyms")
_WS = r"(?:\s|\\\r?\n)+"
_DEF_RE = re.compile(r"(?:async" + _WS + r")?(?:def|class)" + _WS + r"(\w+)")
_ALIAS_RE = re.compile(r"[\w.]+" + _WS + r"as" + _WS + r"(\w+)")
_EXCEPT_RE = re.compile(r"(?:\s|\\\r?\n|\))*as" + _WS + r"(\w+)")


class NamingRefusal(ValueError):
    """The request was refused; .code is machine readable, str() is the exact reason."""

    def __init__(self, code, message, detail=None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


def _refuse_rules(message):
    raise NamingRefusal("invalid_rules", message)


def _valid_acronym(a):
    return isinstance(a, str) and len(a) >= 2 and all(c.isupper() for c in a)


def _acronym_list(items, owner):
    if not isinstance(items, list):
        _refuse_rules("%s acronyms must be a list" % owner if owner != "rules" else "rules acronyms must be a list")
    if len(items) > MAX_ACRONYMS:
        _refuse_rules("%s has %d acronyms, limit is %d" % (owner, len(items), MAX_ACRONYMS))
    seen = set()
    for a in items:
        if not _valid_acronym(a):
            _refuse_rules("%s has invalid acronym %s" % (owner, _q(a)))
        if a in seen:
            _refuse_rules("%s has duplicate acronym %s" % (owner, _q(a)))
        seen.add(a)
    return frozenset(seen)


def _q(value):
    return "'%s'" % (value,)


def _validate_rules(spec):
    if not isinstance(spec, dict):
        _refuse_rules("rules must be a dict")
    for key in sorted(spec, key=str):
        if key not in _TOP_KEYS:
            _refuse_rules("rules has unknown key %s" % _q(key))
    raw = spec.get("rules")
    if not isinstance(raw, list) or not raw:
        _refuse_rules("rules must be a non-empty list")
    if len(raw) > MAX_RULES:
        _refuse_rules("rules has %d entries, limit is %d" % (len(raw), MAX_RULES))
    top_acr = _acronym_list(spec.get("acronyms", []), "rules")
    shadow = spec.get("forbid_shadowing", False)
    if not isinstance(shadow, bool):
        _refuse_rules("forbid_shadowing must be bool")
    out, ids = [], set()
    for i, r in enumerate(raw, 1):
        if not isinstance(r, dict):
            _refuse_rules("rule #%d must be a dict" % i)
        if "id" not in r:
            _refuse_rules("rule #%d is missing 'id'" % i)
        rid = r["id"]
        if not isinstance(rid, str) or not rid:
            _refuse_rules("rule #%d id must be a non-empty str" % i)
        if len(rid) > MAX_ID_LEN:
            _refuse_rules("rule #%d id is %d characters, limit is %d" % (i, len(rid), MAX_ID_LEN))
        if rid in RESERVED_RULE_IDS:
            _refuse_rules("rule id %s is reserved" % _q(rid))
        if rid in ids:
            _refuse_rules("duplicate rule id %s" % _q(rid))
        ids.add(rid)
        me = "rule %s" % _q(rid)
        for key in sorted(r, key=str):
            if key not in _RULE_KEYS:
                _refuse_rules("%s has unknown key %s" % (me, _q(key)))
        for need in ("kinds", "style"):
            if need not in r:
                _refuse_rules("%s is missing %s" % (me, _q(need)))
        kinds = r["kinds"]
        if not isinstance(kinds, list) or not kinds:
            _refuse_rules("%s kinds must be a non-empty list" % me)
        seen = set()
        for k in kinds:
            if k not in KINDS:
                _refuse_rules("%s has unknown kind %s" % (me, _q(k)))
            if k in seen:
                _refuse_rules("%s has duplicate kind %s" % (me, _q(k)))
            seen.add(k)
        if r["style"] not in STYLES:
            _refuse_rules("%s has unknown style %s" % (me, _q(r["style"])))
        scope = r.get("scope")
        if "scope" in r and scope not in SCOPES:
            _refuse_rules("%s has unknown scope %s" % (me, _q(scope)))
        flags = {}
        for flag in ("allow_leading_underscore", "allow_trailing_underscore"):
            v = r.get(flag, False)
            if not isinstance(v, bool):
                _refuse_rules("%s %s must be bool" % (me, flag))
            flags[flag] = v
        dunder = r.get("dunder", "flag")
        if dunder not in ("flag", "exempt"):
            _refuse_rules("%s dunder must be 'flag' or 'exempt'" % me)
        acr = top_acr | _acronym_list(r.get("acronyms", []), me)
        out.append({"id": rid, "kinds": frozenset(kinds), "style": r["style"], "scope": scope,
                    "lead": flags["allow_leading_underscore"], "trail": flags["allow_trailing_underscore"],
                    "dunder": dunder, "acronyms": acr})
    out.sort(key=lambda x: x["id"])
    return out, shadow


# ---------------------------------------------------------------- name rules

def _acronym_problem(core, acronyms):
    n, i = len(core), 0
    while i < n:
        if not core[i].isupper():
            i += 1
            continue
        j = i
        while j < n and core[j].isupper():
            j += 1
        run = core[i:j]
        if j < n and core[j].islower():
            run = run[:-1]
        if len(run) >= 2 and run not in acronyms:
            return run
        i = j
    return None


def _style_ok(core, style):
    if style == "snake_case":
        return "__" not in core and not any(c.isupper() for c in core)
    if style == "UPPER_SNAKE":
        return "__" not in core and not any(c.islower() for c in core)
    if "_" in core:
        return False
    return core[0].isupper() if style == "PascalCase" else core[0].islower()


def _judge(name, rule):
    """Return (reason, detail) for the first problem, or None. '_' is handled by the caller."""
    if len(name) > 4 and name.startswith("__") and name.endswith("__"):
        return ("dunder", None) if rule["dunder"] == "flag" else None
    core = name.lstrip("_")
    lead = len(name) - len(core)
    if not core:
        return "no_letters", None
    if lead and (not rule["lead"] or lead > 2):
        return "leading_underscore", None
    if core.endswith("_"):
        if not rule["trail"]:
            return "trailing_underscore", None
        core = core[:-1]
        if core.endswith("_"):
            return "trailing_underscore", None
    if not _style_ok(core, rule["style"]):
        return "style_mismatch", None
    if rule["style"] in ("PascalCase", "camelCase"):
        bad = _acronym_problem(core, rule["acronyms"])
        if bad is not None:
            return "undeclared_acronym", bad
    return None


# ------------------------------------------------------------- source mapping

class _Source:
    def __init__(self, text):
        self.text = text
        starts, pos = [0], 0
        for m in re.finditer(r"\r\n|\r|\n", text):
            starts.append(m.end())
        self.starts = starts
        self.lines = re.split(r"\r\n|\r|\n", text)
        self.unverified = 0

    def abs_from_byte(self, lineno, byte_col):
        line = self.lines[lineno - 1]
        chars = len(line.encode("utf-8")[:byte_col].decode("utf-8", "ignore"))
        return self.starts[lineno - 1] + chars

    def line_col(self, offset):
        i = bisect.bisect_right(self.starts, offset) - 1
        return i + 1, offset - self.starts[i] + 1

    def locate(self, regex, node_lineno, node_col, expected, fallback_len=None, from_end=False):
        """Find the identifier written in source. Returns (text, line, col, end_line, end_col)."""
        start = self.abs_from_byte(node_lineno, node_col)
        m = regex.match(self.text, start)
        if m and unicodedata.normalize("NFKC", m.group(1)) == expected:
            a, b = m.span(1)
            text = m.group(1)
        else:
            self.unverified += 1
            a, b = start, start + len(expected)
            text = expected
        l1, c1 = self.line_col(a)
        l2, c2 = self.line_col(b)
        return text, l1, c1, l2, c2


_NAME_RE = re.compile(r"(\w+)")


# ------------------------------------------------------------------- scopes

class _Scope:
    def __init__(self, kind, parent):
        self.kind = kind
        self.parent = parent
        self.cands = {}
        self.outer = set()

    @property
    def category(self):
        return "function" if self.kind == "comprehension" else self.kind


class _Collector:
    def __init__(self, src):
        self.src = src
        self.scopes = []

    def new_scope(self, kind, parent):
        s = _Scope(kind, parent)
        self.scopes.append(s)
        return s

    def bind(self, scope, key, kind, text, pos):
        if key in scope.outer:
            return
        line, col, end_line, end_col = pos
        scope.cands.setdefault(key, []).append({
            "key": key, "name": text, "kind": kind, "line": line, "col": col,
            "end_line": end_line, "end_col": end_col, "scope": scope})

    def store_kind(self, scope):
        return {"module": "module_variable", "class": "class_attribute"}.get(scope.kind, "local")

    def visit(self, node, scope):
        method = getattr(self, "v_" + type(node).__name__, None)
        if method is None:
            for child in ast.iter_child_nodes(node):
                self.visit(child, scope)
        else:
            method(node, scope)

    def visit_all(self, nodes, scope):
        for n in nodes:
            if n is not None:
                self.visit(n, scope)

    def v_Name(self, node, scope):
        if isinstance(node.ctx, ast.Store):
            a = self.src.abs_from_byte(node.lineno, node.col_offset)
            text, l1, c1, l2, c2 = self.src.locate(_NAME_RE, node.lineno, node.col_offset, node.id)
            self.bind(scope, node.id, self.store_kind(scope), text, (l1, c1, l2, c2))

    def v_NamedExpr(self, node, scope):
        self.visit(node.value, scope)
        target = scope
        while target.kind == "comprehension" and target.parent is not None:
            target = target.parent
        text, l1, c1, l2, c2 = self.src.locate(_NAME_RE, node.target.lineno, node.target.col_offset, node.target.id)
        self.bind(target, node.target.id, self.store_kind(target), text, (l1, c1, l2, c2))

    def v_Global(self, node, scope):
        scope.outer.update(node.names)

    v_Nonlocal = v_Global

    def _comp(self, node, scope):
        inner = self.new_scope("comprehension", scope)
        for gen in node.generators:
            self.visit(gen.target, inner)
            self.visit(gen.iter, inner)
            self.visit_all(gen.ifs, inner)
        for field in ("elt", "key", "value"):
            if hasattr(node, field):
                self.visit(getattr(node, field), inner)

    v_ListComp = v_SetComp = v_GeneratorExp = v_DictComp = _comp

    def _params(self, args, scope):
        for a in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs) + \
                [x for x in (args.vararg, args.kwarg) if x is not None]:
            text, l1, c1, l2, c2 = self.src.locate(_NAME_RE, a.lineno, a.col_offset, a.arg)
            self.bind(scope, a.arg, "parameter", text, (l1, c1, l2, c2))

    def _outer_parts(self, args):
        for a in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs) + \
                [x for x in (args.vararg, args.kwarg) if x is not None]:
            yield a.annotation

    def v_Lambda(self, node, scope):
        self.visit_all(node.args.defaults, scope)
        self.visit_all(node.args.kw_defaults, scope)
        inner = self.new_scope("function", scope)
        self._params(node.args, inner)
        self.visit(node.body, inner)

    def v_FunctionDef(self, node, scope):
        self.visit_all(node.decorator_list, scope)
        self.visit_all(node.args.defaults, scope)
        self.visit_all(node.args.kw_defaults, scope)
        self.visit_all(self._outer_parts(node.args), scope)
        if node.returns is not None:
            self.visit(node.returns, scope)
        text, l1, c1, l2, c2 = self.src.locate(_DEF_RE, node.lineno, node.col_offset, node.name)
        self.bind(scope, node.name, "method" if scope.kind == "class" else "function", text, (l1, c1, l2, c2))
        inner = self.new_scope("function", scope)
        self._params(node.args, inner)
        self.visit_all(node.body, inner)

    v_AsyncFunctionDef = v_FunctionDef

    def v_ClassDef(self, node, scope):
        self.visit_all(node.decorator_list, scope)
        self.visit_all(node.bases, scope)
        self.visit_all([k.value for k in node.keywords], scope)
        text, l1, c1, l2, c2 = self.src.locate(_DEF_RE, node.lineno, node.col_offset, node.name)
        self.bind(scope, node.name, "class", text, (l1, c1, l2, c2))
        inner = self.new_scope("class", scope)
        self.visit_all(node.body, inner)

    def _import(self, node, scope):
        for alias in node.names:
            if alias.name == "*":
                continue
            if alias.asname:
                text, l1, c1, l2, c2 = self.src.locate(_ALIAS_RE, alias.lineno, alias.col_offset, alias.asname)
                self.bind(scope, alias.asname, "import_alias", text, (l1, c1, l2, c2))
            else:
                key = alias.name.split(".")[0]
                line, col = self.src.line_col(self.src.abs_from_byte(alias.lineno, alias.col_offset))
                self.bind(scope, key, None, key, (line, col, line, col + len(key)))

    v_Import = v_ImportFrom = _import

    def v_ExceptHandler(self, node, scope):
        if node.type is not None:
            self.visit(node.type, scope)
        if node.name:
            if node.type is not None:
                text, l1, c1, l2, c2 = self.src.locate(
                    _EXCEPT_RE, node.type.end_lineno, node.type.end_col_offset, node.name)
            else:
                line, col = self.src.line_col(self.src.abs_from_byte(node.lineno, node.col_offset))
                text, l1, c1, l2, c2 = node.name, line, col, line, col + len(node.name)
                self.src.unverified += 1
            self.bind(scope, node.name, self.store_kind(scope), text, (l1, c1, l2, c2))
        self.visit_all(node.body, scope)


# ---------------------------------------------------------------------- main

def _refuse_source(source):
    if not isinstance(source, str):
        raise NamingRefusal("invalid_source", "source must be str")
    if "\x00" in source:
        raise NamingRefusal("invalid_source", "source contains a null byte")
    try:
        size = len(source.encode("utf-8"))
    except UnicodeEncodeError:
        raise NamingRefusal("invalid_source", "source is not valid Unicode text") from None
    if size > MAX_SOURCE_BYTES:
        raise NamingRefusal("resource_limit", "source is %d bytes, limit is %d" % (size, MAX_SOURCE_BYTES))


def _parse(source):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        line = exc.lineno or 0
        raise NamingRefusal("syntax_error", "source is not valid Python syntax at line %d" % line,
                            {"line": line, "col": exc.offset or 0}) from None
    except (RecursionError, MemoryError):
        raise NamingRefusal("resource_limit", "source nesting exceeds parser limits") from None
    total = sum(1 for _ in ast.walk(tree))
    if total > MAX_NODES:
        raise NamingRefusal("resource_limit", "source has %d syntax nodes, limit is %d" % (total, MAX_NODES))
    return tree


def check_naming(source, rules):
    """Check identifiers in `source` against the explicit `rules`; return a report dict.

    Raises NamingRefusal for malformed rules, unusable source, or exceeded limits.
    """
    compiled, forbid_shadowing = _validate_rules(rules)
    _refuse_source(source)
    tree = _parse(source)
    src = _Source(source)
    collector = _Collector(src)
    root = collector.new_scope("module", None)
    try:
        for stmt in tree.body:
            collector.visit(stmt, root)
    except RecursionError:
        raise NamingRefusal("resource_limit", "source nesting exceeds analysis limits") from None

    firsts = []
    for scope in collector.scopes:
        for cands in scope.cands.values():
            firsts.append(min(cands, key=lambda b: (b["line"], b["col"], b["end_line"], b["end_col"])))
    firsts.sort(key=lambda b: (b["line"], b["col"], b["name"]))

    checked, findings, exempt = [], [], 0
    for b in firsts:
        if b["kind"] is None:
            continue
        applicable = [r for r in compiled if b["kind"] in r["kinds"]
                      and (r["scope"] is None or r["scope"] == b["scope"].category)]
        pos = {"line": b["line"], "col": b["col"], "end_line": b["end_line"], "end_col": b["end_col"]}
        if applicable and b["name"] == "_":
            exempt += 1
        elif applicable:
            checked.append({"name": b["name"], "kind": b["kind"], **pos, "rule_ids": [r["id"] for r in applicable]})
            for r in applicable:
                verdict = _judge(b["name"], r)
                if verdict:
                    findings.append({"rule_id": r["id"], "kind": b["kind"], "name": b["name"], **pos,
                                     "reason": verdict[0], "expected": r["style"], "detail": verdict[1]})
        if forbid_shadowing and b["name"] != "_" and b["scope"].category == "function":
            p = b["scope"].parent
            while p is not None:
                if p.kind != "class" and b["key"] in p.cands:
                    prior = min(p.cands[b["key"]], key=lambda x: (x["line"], x["col"]))
                    findings.append({"rule_id": "SHADOW", "kind": b["kind"], "name": b["name"], **pos,
                                     "reason": "shadows_enclosing", "expected": None,
                                     "detail": "line %d" % prior["line"]})
                    break
                p = p.parent
    findings.sort(key=lambda f: (f["line"], f["col"], f["rule_id"], f["reason"]))
    applied = [r["id"] for r in compiled] + (["SHADOW"] if forbid_shadowing else [])
    return {
        "schema": "naming707/1",
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "position_unit": POSITION_UNIT,
        "rules_applied": sorted(applied),
        "style_inferred": False,
        "checked_count": len(checked),
        "exempt_count": exempt,
        "position_unverified_count": src.unverified,
        "checked": checked,
        "findings": findings,
        "compliant": not findings,
        "not_inspected": list(NOT_INSPECTED),
        "limits": {"max_source_bytes": MAX_SOURCE_BYTES, "max_nodes": MAX_NODES,
                   "max_rules": MAX_RULES, "max_acronyms": MAX_ACRONYMS},
    }
