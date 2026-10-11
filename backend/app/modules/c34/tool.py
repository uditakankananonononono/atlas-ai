"""S3.3 / c34.tool - tool-builder scaffolds.

Source excerpt (verbatim): "monitor companies and able to autonomously build
algorithms and tools for all of their needs".

Given ONE supplied need statement for a company the owner named, emit a small
Python tool as DRAFT file strings (module + tests) from fixed templates keyed by
need type. Substitution for "autonomously build ... all of their needs": one
scaffold per supplied need, never unsolicited delivery. Nothing is written to
disk, fetched or executed by this unit. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import ast
import datetime
import re

from app.modules.c30 import policy

PREFIX = "PROTO"
FIELD_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
TYPES = ("csv_transform", "scorer", "deduper", "report")
MAX_FIELDS = 16
MAX_FIELD_LEN = 64
MAX_TYPE = 32
MAX_DESC = 500
REQUEST_KEYS = {"as_of", "requested_by_owner", "company", "need"}
NEED_KEYS = {"id", "type", "description", "fields"}
# Generated code may import only these stdlib modules (plus its own tool module).
ALLOWED_IMPORTS = {"csv", "io", "unittest"}
BANNED_CALLS = {"open", "exec", "eval", "compile", "__import__", "input", "getattr", "setattr", "globals", "vars"}
_SPEND_RE = re.compile(r"\b(buy|purchase|pay|payment|subscribe|subscription|invoice|checkout|billing)\b", re.I)
_UNSAFE_RE = re.compile(
    r"\b(scrape|crawl|http|https|url|fetch|download|upload|network|socket|subprocess|shell|"
    r"email|e-mail|send|post|tweet|dm|trade|trading|login|log in|password|account|signup|sign up)\b", re.I)

# The company is supplied text: it appears only in the COMPANY = repr(...) line, never inside this docstring.
_HEAD = '"""DRAFT scaffold %(id)s (%(type)s). Review before use; not verified against real data."""\n'

_MODULES = {
    "csv_transform": '''import csv
import io

COMPANY = %(company_r)s
NEED = %(desc_r)s
FIELDS = %(fields_r)s


def transform(rows):
    return [{f: row.get(f, "") for f in FIELDS} for row in rows]


def parse(text):
    return list(csv.DictReader(io.StringIO(text)))


def render(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\\n")
    writer.writeheader()
    writer.writerows(transform(rows))
    return buf.getvalue()
''',
    "scorer": '''COMPANY = %(company_r)s
NEED = %(desc_r)s
FIELDS = %(fields_r)s


def score(row):
    total = 0.0
    for f in FIELDS:
        try:
            total += float(row.get(f, 0) or 0)
        except (TypeError, ValueError):
            pass
    return round(total, 6)


def rank(rows):
    scored = [dict(row, score=score(row)) for row in rows]
    return sorted(scored, key=lambda r: (-r["score"], repr(sorted(r.items()))))
''',
    "deduper": '''COMPANY = %(company_r)s
NEED = %(desc_r)s
FIELDS = %(fields_r)s


def key(row):
    return tuple(str(row.get(f, "")).strip().lower() for f in FIELDS)


def dedupe(rows):
    seen = set()
    out = []
    for row in rows:
        k = key(row)
        if k in seen:
            continue
        seen.add(k)
        out.append(row)
    return out
''',
    "report": '''COMPANY = %(company_r)s
NEED = %(desc_r)s
FIELDS = %(fields_r)s


def summarize(rows):
    filled = {f: sum(1 for r in rows if str(r.get(f, "")).strip()) for f in FIELDS}
    return {"rows": len(rows), "filled": filled}


def render(rows):
    s = summarize(rows)
    lines = ["rows: %%d" %% s["rows"]]
    lines += ["%%s: %%d filled" %% (f, s["filled"][f]) for f in FIELDS]
    return "\\n".join(lines) + "\\n"
''',
}

_TESTS = {
    "csv_transform": '''
    def test_transform_keeps_only_fields_and_roundtrips(self):
        rows = [dict({f: "v" + f for f in tool.FIELDS}, extra="z")]
        out = tool.transform(rows)
        self.assertEqual(set(out[0]), set(tool.FIELDS))
        self.assertEqual(tool.parse(tool.render(rows)), out)
''',
    "scorer": '''
    def test_score_and_rank(self):
        hi = {f: "2" for f in tool.FIELDS}
        lo = {f: "1" for f in tool.FIELDS}
        self.assertEqual(tool.score(hi), round(2.0 * len(tool.FIELDS), 6))
        self.assertEqual([r["score"] for r in tool.rank([lo, hi])], [tool.score(hi), tool.score(lo)])
        self.assertEqual(tool.score({}), 0.0)
''',
    "deduper": '''
    def test_dedupe_is_case_and_space_insensitive_and_keeps_first(self):
        a = {f: "A" for f in tool.FIELDS}
        b = {f: " a " for f in tool.FIELDS}
        c = {f: "other" for f in tool.FIELDS}
        self.assertEqual(tool.dedupe([a, b, c]), [a, c])
''',
    "report": '''
    def test_summary_counts_filled_fields(self):
        rows = [{f: "x" for f in tool.FIELDS}, {}]
        s = tool.summarize(rows)
        self.assertEqual(s["rows"], 2)
        self.assertEqual(s["filled"], {f: 1 for f in tool.FIELDS})
        self.assertTrue(tool.render(rows).startswith("rows: 2\\n"))
''',
}


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _check_description(desc):
    if _SPEND_RE.search(desc):
        policy.check("spend", PREFIX)  # raises PROTO_REFUSED_SPEND
    if _UNSAFE_RE.search(desc):
        _refuse("UNSAFE", "description")


def scan_source(source):
    """Return violations found in generated code: non-stdlib imports, banned
    calls, write-mode or network/subprocess use. Empty list means clean."""
    bad = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS and not a.name.startswith("tool_"):
                    bad.append("import:" + a.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if node.level or (root not in ALLOWED_IMPORTS and not root.startswith("tool_")):
                bad.append("from:" + (node.module or "."))
        elif isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            if name in BANNED_CALLS:
                bad.append("call:" + name)
        elif isinstance(node, ast.Attribute) and node.attr in {"system", "popen", "Popen", "urlopen", "connect"}:
            bad.append("attr:" + node.attr)
    return bad


def run(request):
    """Scaffold one tool from one supplied need; returns the draft files dict."""
    # COUNT first, then strict key-type, then SET-allowlist: hostile keys are
    # never hashed or compared before the exact-type gate (str subclasses that
    # name allowed keys are refused, not accepted).
    if type(request) is not dict:
        _refuse("BAD_TYPE", "request")
    if len(request) != len(REQUEST_KEYS):
        _refuse("BAD_TYPE", "request")
    if any(type(key) is not str for key in request):
        _refuse("BAD_TYPE", "request")
    if set(request) != REQUEST_KEYS:
        _refuse("BAD_TYPE", "request")
    if request["requested_by_owner"] is not True:
        _refuse("UNSOLICITED")
    as_of = policy.clean_text(request["as_of"], PREFIX, "as_of", 10)
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
            raise ValueError
        datetime.date.fromisoformat(as_of)
    except ValueError:
        _refuse("BAD_TYPE", "as_of")
    company = policy.clean_text(request["company"], PREFIX, "company", 128)
    need = request["need"]
    if type(need) is not dict:
        _refuse("BAD_TYPE", "need")
    if len(need) != len(NEED_KEYS):
        _refuse("BAD_TYPE", "need")
    if any(type(key) is not str for key in need):
        _refuse("BAD_TYPE", "need")
    if set(need) != NEED_KEYS:
        _refuse("BAD_TYPE", "need")
    ntype = need["type"]
    if type(ntype) is not str:
        _refuse("BAD_TYPE", "type")
    if len(ntype) > MAX_TYPE:  # cap before membership
        _refuse("BAD_TYPE", "type")
    if ntype not in TYPES:
        _refuse("NOSPEC", "type")
    nid = policy.clean_text(need["id"], PREFIX, "id", 32)
    if not ID_RE.fullmatch(nid):
        _refuse("BAD_TYPE", "id")
    desc = policy.clean_text(need["description"], PREFIX, "description", MAX_DESC)
    _check_description(desc)
    fields = need["fields"]
    if type(fields) is not list:
        _refuse("BAD_TYPE", "fields")
    if not fields:
        _refuse("EMPTY", "fields")
    if len(fields) > MAX_FIELDS:
        _refuse("BAD_TYPE", "fields")
    for f in fields:
        if type(f) is not str or len(f) > MAX_FIELD_LEN or not FIELD_RE.fullmatch(f):  # cap before regex
            _refuse("BAD_TYPE", "fields")
    if len(set(fields)) != len(fields):
        _refuse("BAD_TYPE", "fields")
    subs = {"id": nid, "type": ntype, "company_r": repr(company), "desc_r": repr(desc), "fields_r": repr(list(fields))}
    module_name = "tool_%s" % nid
    module_src = (_HEAD % subs) + _MODULES[ntype] % subs
    test_src = ('"""DRAFT tests for %s."""\nimport unittest\n\nimport %s as tool\n\n\n'
                "class Test%s(unittest.TestCase):%s\n\nif __name__ == \"__main__\":\n    unittest.main()\n"
                % (module_name, module_name, "".join(p.capitalize() for p in nid.split("_")) or "Tool", _TESTS[ntype]))
    files = {"test_%s.py" % module_name: test_src, "%s.py" % module_name: module_src}
    for name, src in files.items():  # the unit refuses to emit code its own scan rejects
        try:
            violations = scan_source(src)
        except SyntaxError:
            _refuse("UNSAFE", name)
        if violations:
            _refuse("UNSAFE", name)
    return {
        "unit": "S3.3", "company": company, "need_id": nid, "need_type": ntype, "as_of": as_of,
        "draft": True, "files": files, "file_count": len(files),
        "scope": policy.scope(["one scaffold per supplied need", "fixed templates for %d need types" % len(TYPES),
                               "ast scan of emitted code"],
                              ["understanding the company's real needs beyond the supplied description",
                               "unsolicited delivery", "writing files", "running generated code",
                               "monitoring companies"],
                              "supplied need statement", as_of),
    }
