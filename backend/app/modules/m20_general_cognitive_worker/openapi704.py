"""Row704 scoped API documentation: bounded typed operations -> OpenAPI 3.1 subset.

Pure stdlib. Validates supplied operation/schema descriptions and emits a
machine-readable OpenAPI 3.1.0 document plus source trace. It never inspects,
imports or executes the described implementation, so the output documents only
what the caller supplied (see LIMITS).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

MAX_OPERATIONS = 64
MAX_SCHEMAS = 64
MAX_PROPERTIES = 64
MAX_DEPTH = 8            # nested array/object containers inside one schema
MAX_PARAMETERS = 16
MAX_RESPONSES = 8
MAX_ENUM = 32
MAX_TEXT = 500
MAX_PATH = 200
MAX_EXAMPLE_NODES = 1000
MAX_EXAMPLE_STRING = 2000
MAX_INPUT_BYTES = 262144
MAX_INPUT_NODES = 50000
MAX_RAW_DEPTH = 48
MAX_OUTPUT_BYTES = 1_000_000
MAX_LENGTH_KEYWORD = 10000
MAX_KEY = 500            # IC: raw cap on any input dict key (equal to MAX_TEXT)
MAX_REQUIRED = MAX_PROPERTIES  # IC: raw cap on a required list, checked before its items

LIMITS = [
    "Documents only the supplied operation and schema descriptions; it does not verify them against any live implementation, route table or deployment.",
    "Subset only: object/array/string/integer/number/boolean schemas, nullable, enum, length and numeric bounds, $ref to named schemas. Recursive, composed (oneOf/anyOf/allOf/not), pattern, format and additionalProperties-schema forms are refused.",
    "Examples are checked by this module's bounded validator against the supplied schemas only; request/response examples are caller-supplied, not observed traffic.",
    "No security schemes, servers, callbacks, links, non-JSON media types or generator packages.",
]

_METHODS = ("get", "put", "post", "delete", "patch")
_NO_BODY = ("get", "delete")
_NAME = re.compile(r"^[A-Za-z0-9._-]{1,64}\Z")
_OPID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
_SEG = re.compile(r"^[A-Za-z0-9._~-]+\Z")
_PH = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]{0,63})\}\Z")
_STATUS = re.compile(r"^[1-5][0-9][0-9]\Z")
_REF = re.compile(r"^#/components/schemas/([A-Za-z0-9._-]{1,64})\Z")
_TYPES = ("string", "integer", "number", "boolean", "array", "object")
_SCALARS = ("string", "integer", "number", "boolean")
_RESERVED_HEADERS = ("accept", "content-type", "authorization")
_PARAM_ORDER = {"path": 0, "query": 1, "header": 2}
_COMMON = {"type", "nullable", "description"}
_KEYS_BY_TYPE = {
    "string": _COMMON | {"enum", "minLength", "maxLength"},
    "integer": _COMMON | {"enum", "minimum", "maximum"},
    "number": _COMMON | {"enum", "minimum", "maximum"},
    "boolean": _COMMON | {"enum"},
    "array": _COMMON | {"items"},
    "object": _COMMON | {"properties", "required", "additionalProperties"},
}


def _fail(msg: str):
    raise ValueError(msg)


def _isint(v):
    return type(v) is int


def _isnum(v):
    return type(v) in (int, float) and (type(v) is int or math.isfinite(v))


def _text(v, label, required=True):
    if type(v) is not str:
        _fail(f"{label} must be a non-blank string")
    if len(v) > MAX_TEXT:
        _fail(f"{label} exceeds {MAX_TEXT} characters (length bound)")
    if required and not v.strip():
        _fail(f"{label} must be a non-blank string")
    return v


def _keys(d, allowed, label):
    for k in d:
        if k not in allowed:
            _fail(f"unknown key in {label}")


def _prescan(data):
    """Preflight fence: one iterative walk before any validation or recursion.

    Only exact builtin types are admitted (None, bool, int, float, str, list, dict); a
    subclass or any other type is refused by `type()` alone, before len, iteration, equality,
    hashing or any other method of the value is used. Container counts are checked before a
    container is iterated. Messages are constants and never carry caller values."""
    stack = [(data, 0)]
    nodes = 0
    while stack:
        node, depth = stack.pop()
        nodes += 1
        if nodes > MAX_INPUT_NODES:
            _fail("input node bound exceeded")
        if depth > MAX_RAW_DEPTH:
            _fail("input depth bound exceeded")
        t = type(node)
        if node is None or t is bool or t is str:
            continue
        if t is int:
            if node.bit_length() > 64:
                _fail("integer exceeds 64-bit bound")
        elif t is float:
            if not math.isfinite(node):
                _fail("non-finite number refused (finite numbers only)")
        elif t is list:
            if nodes + len(node) + len(stack) > MAX_INPUT_NODES:
                _fail("input node bound exceeded")
            stack.extend((x, depth + 1) for x in node)
        elif t is dict:
            if nodes + len(node) + len(stack) > MAX_INPUT_NODES:
                _fail("input node bound exceeded")
            for k, v in node.items():
                if type(k) is not str:
                    _fail("non-string key refused")
                if len(k) > MAX_KEY:
                    _fail("input key exceeds bound")
                stack.append((v, depth + 1))
        else:
            _fail("unsupported input value type")
    try:
        size = len(json.dumps(data, allow_nan=False))
    except (TypeError, ValueError):
        _fail("input not JSON-serializable")
    if size > MAX_INPUT_BYTES:
        _fail(f"input size bound exceeded ({MAX_INPUT_BYTES} bytes)")


class _Ctx:
    def __init__(self):
        self.refs_from = None  # set of names referenced by current named schema
        self.all_refs = []     # (ref name, where)


def _norm_schema(s, cdepth, ctx, label, allow_ref=True):
    if type(s) is not dict:
        _fail(f"{label}: schema must be an object")
    if "$ref" in s:
        if not allow_ref:
            _fail(f"{label}: $ref not allowed here")
        if len(s) != 1:
            _fail(f"{label}: $ref must stand alone")
        m = _REF.fullmatch(s["$ref"]) if type(s["$ref"]) is str else None
        if not m:
            _fail(f"{label}: unsupported $ref (only #/components/schemas/<name>)")
        ctx.all_refs.append(m.group(1))
        if ctx.refs_from is not None:
            ctx.refs_from.add(m.group(1))
        return {"$ref": s["$ref"]}
    t = s.get("type")
    if type(t) is not str or t not in _TYPES:
        _fail(f"{label}: unsupported schema type")
    for k in s:
        if k not in _KEYS_BY_TYPE[t]:
            _fail(f"{label}: unsupported or unknown schema keyword for type {t}")
    nullable = s.get("nullable", False)
    if type(nullable) is not bool:
        _fail(f"{label}: nullable must be boolean")
    out: dict[str, Any] = {"type": [t, "null"] if nullable else t}
    if "description" in s:
        out["description"] = _text(s["description"], f"{label}.description")
    if "enum" in s:
        e = s["enum"]
        if type(e) is not list or not e:
            _fail(f"{label}: enum must be a non-empty list")
        if len(e) > MAX_ENUM:
            _fail(f"{label}: enum exceeds {MAX_ENUM} values")
        seen = set()
        for v in e:
            if not _matches_scalar(v, t):
                _fail(f"{label}: enum value type does not match {t}")
            key = (type(v).__name__ if t != "number" else "n", float(v) if t == "number" else v)
            if key in seen:
                _fail(f"{label}: enum duplicate value")
            seen.add(key)
        out["enum"] = list(e) + ([None] if nullable else [])
    if t == "string":
        lo, hi = _bound(s, "minLength", label), _bound(s, "maxLength", label)
        if lo is not None and hi is not None and lo > hi:
            _fail(f"{label}: minLength exceeds maxLength (length bounds inverted)")
        for k, v in (("minLength", lo), ("maxLength", hi)):
            if v is not None:
                out[k] = v
    if t in ("integer", "number"):
        vals = {}
        for k in ("minimum", "maximum"):
            if k in s:
                v = s[k]
                if not (_isint(v) if t == "integer" else _isnum(v)):
                    _fail(f"{label}: {k} must be a finite numeric value of the schema type")
                vals[k] = v
                out[k] = v
        if len(vals) == 2 and vals["minimum"] > vals["maximum"]:
            _fail(f"{label}: minimum exceeds maximum")
    if t == "array":
        if cdepth + 1 > MAX_DEPTH:
            _fail(f"{label}: schema depth bound {MAX_DEPTH} exceeded")
        if "items" not in s:
            _fail(f"{label}: array requires items")
        out["items"] = _norm_schema(s["items"], cdepth + 1, ctx, f"{label}.items")
    if t == "object":
        if cdepth + 1 > MAX_DEPTH:
            _fail(f"{label}: schema depth bound {MAX_DEPTH} exceeded")
        props = s.get("properties", {})
        if type(props) is not dict:
            _fail(f"{label}: properties must be an object")
        if len(props) > MAX_PROPERTIES:
            _fail(f"{label}: properties exceed {MAX_PROPERTIES}")
        np = {}
        for name, ps in props.items():
            if not _NAME.fullmatch(name):
                _fail(f"{label}: invalid property name")
            np[name] = _norm_schema(ps, cdepth + 1, ctx, f"{label}.{name}")
        req = s.get("required", [])
        if type(req) is not list:
            _fail(f"{label}: required must be a list of property names")
        if len(req) > MAX_REQUIRED:
            _fail(f"{label}: required exceeds {MAX_REQUIRED}")
        if any(type(r) is not str for r in req):
            _fail(f"{label}: required must be a list of property names")
        if len(set(req)) != len(req):
            _fail(f"{label}: required has duplicate entries")
        for r in req:
            if r not in np:
                _fail(f"{label}: required property not in properties")
        ap = s.get("additionalProperties", False)
        if type(ap) is not bool:
            _fail(f"{label}: unsupported additionalProperties schema (boolean only)")
        out["properties"] = np
        out["required"] = sorted(req)
        out["additionalProperties"] = ap
    return out


def _bound(s, key, label):
    if key not in s:
        return None
    v = s[key]
    if not _isint(v) or not 0 <= v <= MAX_LENGTH_KEYWORD:
        _fail(f"{label}: {key} length must be an integer in 0..{MAX_LENGTH_KEYWORD}")
    return v


def _matches_scalar(v, t):
    if t == "string":
        return type(v) is str
    if t == "boolean":
        return type(v) is bool
    if t == "integer":
        return _isint(v)
    if t == "number":
        return _isnum(v)
    return False


def _count_nodes(v):
    n, stack = 0, [v]
    while stack:
        x = stack.pop()
        n += 1
        if n > MAX_EXAMPLE_NODES:
            _fail(f"example exceeds {MAX_EXAMPLE_NODES} nodes (bound)")
        t = type(x)
        if t is str and len(x) > MAX_EXAMPLE_STRING:
            _fail("example string exceeds bound")
        if t is list:
            stack.extend(x)
        elif t is dict:
            stack.extend(x.values())
    return n


def _check(v, s, comps, path):
    """Validate example v against normalized schema s. Raises ValueError('example ...')."""
    if "$ref" in s:
        name = _REF.fullmatch(s["$ref"]).group(1)
        if name not in comps:
            _fail(f"dangling $ref to '{name}'")
        return _check(v, comps[name], comps, path)
    t = s["type"]
    nullable = type(t) is list
    base = t[0] if nullable else t
    if v is None:
        if nullable:
            return
        _fail(f"example {path}: null not allowed (not nullable)")
    if "enum" in s and not any(type(v) is type(e) and v == e or (base == "number" and _isnum(v) and _isnum(e) and type(e) is not bool and v == e) for e in s["enum"] if e is not None):
        _fail(f"example {path}: value not in enum")
    if base in _SCALARS:
        if not _matches_scalar(v, base):
            _fail(f"example {path}: expected {base}")
        if base == "string":
            if "minLength" in s and len(v) < s["minLength"] or "maxLength" in s and len(v) > s["maxLength"]:
                _fail(f"example {path}: string length out of bounds")
        if base in ("integer", "number"):
            if "minimum" in s and v < s["minimum"] or "maximum" in s and v > s["maximum"]:
                _fail(f"example {path}: number out of bounds")
        return
    if base == "array":
        if type(v) is not list:
            _fail(f"example {path}: expected array")
        for i, x in enumerate(v):
            _check(x, s["items"], comps, f"{path}[{i}]")
        return
    if type(v) is not dict:
        _fail(f"example {path}: expected object")
    for r in s["required"]:
        if r not in v:
            _fail(f"example {path}: missing required '{r}'")
    for k, x in v.items():
        if k in s["properties"]:
            _check(x, s["properties"][k], comps, f"{path}.{k}")
        elif not s["additionalProperties"]:
            _fail(f"example {path}: unexpected property")


def _resolve_root(s, comps):
    seen = 0
    while "$ref" in s:
        s = comps[_REF.fullmatch(s["$ref"]).group(1)]
        seen += 1
        if seen > MAX_SCHEMAS:
            _fail("recursive $ref cycle")
    return s


def _norm_path(path):
    if type(path) is not str or len(path) > MAX_PATH or not path.startswith("/"):
        _fail(f"path must start with '/' and be at most {MAX_PATH} characters")
    holders, canon = [], []
    if path != "/":
        for seg in path[1:].split("/"):
            m = _PH.fullmatch(seg)
            if m:
                holders.append(m.group(1))
                canon.append("{}")
            elif _SEG.fullmatch(seg):
                canon.append(seg)
            else:
                _fail("path has an invalid segment")
    if len(set(holders)) != len(holders):
        _fail("path has duplicate placeholder names")
    return holders, "/" + "/".join(canon)


def _detect_cycles(graph):
    state = {}
    for start in sorted(graph):
        if state.get(start):
            continue
        stack = [(start, iter(sorted(graph[start])))]
        state[start] = 1
        while stack:
            node, it = stack[-1]
            for nxt in it:
                if state.get(nxt) == 1:
                    _fail(f"recursive $ref cycle involving '{nxt}'")
                if not state.get(nxt):
                    state[nxt] = 1
                    stack.append((nxt, iter(sorted(graph[nxt]))))
                    break
            else:
                state[node] = 2
                stack.pop()


def generate_openapi(data: Any) -> dict[str, Any]:
    _prescan(data)
    if type(data) is not dict:
        _fail("request must be an object")
    _keys(data, {"info", "schemas", "operations"}, "request")
    info = data.get("info")
    if type(info) is not dict:
        _fail("info must be an object")
    _keys(info, {"title", "version", "description"}, "info")
    out_info = {"title": _text(info.get("title"), "info.title"), "version": _text(info.get("version"), "info.version")}
    if "description" in info:
        out_info["description"] = _text(info["description"], "info.description")

    schemas = data.get("schemas", {})
    if type(schemas) is not dict:
        _fail("schemas must be an object")
    if len(schemas) > MAX_SCHEMAS:
        _fail(f"schemas exceed {MAX_SCHEMAS}")
    ops = data.get("operations")
    if type(ops) is not list or not ops:
        _fail("operations must be a non-empty list")
    if len(ops) > MAX_OPERATIONS:
        _fail(f"operations exceed {MAX_OPERATIONS}")

    ctx = _Ctx()
    comps: dict[str, Any] = {}
    graph: dict[str, set] = {}
    trace = []
    for name, entry in schemas.items():
        if not _NAME.fullmatch(name):
            _fail("invalid schema name")
        if type(entry) is not dict:
            _fail(f"schema '{name}' must be an object")
        _keys(entry, {"source_ref", "schema"}, f"schema '{name}'")
        ref = _text(entry.get("source_ref"), f"schema '{name}' source_ref")
        ctx.refs_from = set()
        norm = _norm_schema(entry.get("schema"), 0, ctx, f"schema '{name}'")
        graph[name] = ctx.refs_from
        ctx.refs_from = None
        comps[name] = norm
        trace.append({"kind": "schema", "name": name, "source_ref": ref})
    for name, tgt in graph.items():
        for t in tgt:
            if t not in comps:
                _fail(f"dangling $ref to '{t}' in schema '{name}'")
    _detect_cycles(graph)

    paths: dict[str, dict] = {}
    seen_ids, seen_mp, canon_paths = set(), set(), {}
    examples = []
    for i, op in enumerate(ops):
        if type(op) is not dict:
            _fail(f"operation {i} must be an object")
        label = f"operation {i}"
        _keys(op, {"operation_id", "method", "path", "summary", "source_ref", "parameters", "request_body", "responses"}, label)
        method = op.get("method")
        if method not in _METHODS:
            _fail(f"{label}: method must be one of {', '.join(_METHODS)}")
        oid = op.get("operation_id")
        if type(oid) is not str or not _OPID.fullmatch(oid):
            _fail(f"{label}: invalid operation_id")
        if oid in seen_ids:
            _fail(f"duplicate operation_id '{oid}'")
        seen_ids.add(oid)
        label = f"operation '{oid}'"
        holders, canon = _norm_path(op.get("path"))
        path = op["path"]
        if canon in canon_paths and canon_paths[canon] != path:
            _fail(f"duplicate equivalent path templates '{canon_paths[canon]}' and '{path}'")
        canon_paths[canon] = path
        if (method, canon) in seen_mp:
            _fail(f"duplicate method/path {method.upper()} {path}")
        seen_mp.add((method, canon))
        summary = _text(op.get("summary"), f"{label} summary")
        sref = _text(op.get("source_ref"), f"{label} source_ref")
        trace.append({"kind": "operation", "name": oid, "source_ref": sref})

        plist = op.get("parameters", [])
        if type(plist) is not list:
            _fail(f"{label}: parameters must be a list")
        if len(plist) > MAX_PARAMETERS:
            _fail(f"{label}: parameters exceed {MAX_PARAMETERS}")
        params, pseen, path_declared = [], set(), set()
        for j, p in enumerate(plist):
            pl = f"{label} parameter {j}"
            if type(p) is not dict:
                _fail(f"{pl} must be an object")
            _keys(p, {"name", "in", "required", "schema", "example", "description"}, pl)
            pname, loc = p.get("name"), p.get("in")
            if type(pname) is not str or not _NAME.fullmatch(pname):
                _fail(f"{pl}: invalid name")
            if loc not in _PARAM_ORDER:
                _fail(f"{pl}: 'in' must be path, query or header")
            if loc == "header" and pname.lower() in _RESERVED_HEADERS:
                _fail(f"{pl}: reserved header name")
            key = (loc, pname.lower() if loc == "header" else pname)
            if key in pseen:
                _fail(f"{label}: duplicate parameter {loc}:{pname}")
            pseen.add(key)
            req = p.get("required", False)
            if type(req) is not bool:
                _fail(f"{pl}: required must be boolean")
            if loc == "path":
                if req is not True:
                    _fail(f"{pl}: path parameter must declare required true")
                path_declared.add(pname)
            ps = _norm_schema(p.get("schema"), 0, ctx, pl + " schema", allow_ref=False)
            pt = ps["type"][0] if type(ps["type"]) is list else ps["type"]
            if pt == "object" or (pt == "array" and (loc == "path" or "items" not in ps or ps["items"].get("type") not in _SCALARS)):
                _fail(f"{pl}: parameter schema must be scalar{'' if loc == 'path' else ' or array of scalars'}")
            if loc == "path" and type(ps["type"]) is list:
                _fail(f"{pl}: path parameter cannot be nullable")
            np_ = {"name": pname, "in": loc, "required": req, "schema": ps}
            if "description" in p:
                np_["description"] = _text(p["description"], f"{pl}.description")
            if "example" in p:
                _count_nodes(p["example"])
                _check(p["example"], ps, comps, f"{label} parameter {pname}")
                np_["example"] = p["example"]
                examples.append({"operation_id": oid, "kind": "parameter", "name": pname, "valid": True, "example": p["example"]})
            params.append(np_)
        if path_declared != set(holders):
            _fail(f"{label}: path template placeholders {sorted(holders)} must match declared path parameters {sorted(path_declared)}")
        params.sort(key=lambda x: (_PARAM_ORDER[x["in"]], x["name"]))
        item = {"operationId": oid, "summary": summary, "x-source-ref": sref}
        if params:
            item["parameters"] = params

        if "request_body" in op:
            if method in _NO_BODY:
                _fail(f"{label}: {method} operations cannot have a request body")
            rb = op["request_body"]
            if type(rb) is not dict:
                _fail(f"{label}: request_body must be an object")
            _keys(rb, {"required", "schema", "example"}, f"{label} request_body")
            rreq = rb.get("required", False)
            if type(rreq) is not bool:
                _fail(f"{label}: request_body required must be boolean")
            rs = _norm_schema(rb.get("schema"), 0, ctx, f"{label} request body")
            _body_must_be_object(rs, comps, label)
            media = {"schema": rs}
            if "example" in rb:
                _count_nodes(rb["example"])
                _check(rb["example"], rs, comps, f"{label} request body")
                media["example"] = rb["example"]
                examples.append({"operation_id": oid, "kind": "request", "valid": True, "example": rb["example"]})
            item["requestBody"] = {"required": rreq, "content": {"application/json": media}}

        resp = op.get("responses")
        if type(resp) is not dict or not resp:
            _fail(f"{label}: responses must be a non-empty object")
        if len(resp) > MAX_RESPONSES:
            _fail(f"{label}: responses exceed {MAX_RESPONSES}")
        oresp = {}
        for code, r in resp.items():
            if code != "default" and not _STATUS.fullmatch(code):
                _fail(f"{label}: invalid response status")
            if type(r) is not dict:
                _fail(f"{label} response {code} must be an object")
            _keys(r, {"description", "schema", "example"}, f"{label} response {code}")
            entry = {"description": _text(r.get("description"), f"{label} response {code} description")}
            if "schema" in r:
                rs = _norm_schema(r["schema"], 0, ctx, f"{label} response {code}")
                media = {"schema": rs}
                if "example" in r:
                    _count_nodes(r["example"])
                    _check(r["example"], rs, comps, f"{label} response {code}")
                    media["example"] = r["example"]
                    examples.append({"operation_id": oid, "kind": "response", "status": code, "valid": True, "example": r["example"]})
                entry["content"] = {"application/json": media}
            elif "example" in r:
                _fail(f"{label} response {code}: example requires schema")
            oresp[code] = entry
        item["responses"] = oresp
        paths.setdefault(path, {})[method] = item

    for t in ctx.all_refs:
        if t not in comps:
            _fail(f"dangling $ref to '{t}'")

    components = {}
    refsrc = {t["name"]: t["source_ref"] for t in trace if t["kind"] == "schema"}
    for name, s in comps.items():
        components[name] = {**s, "x-source-ref": refsrc[name]}
    doc = {"openapi": "3.1.0", "info": out_info, "paths": paths}
    if components:
        doc["components"] = {"schemas": components}
    try:
        canonical = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError):
        _fail("document not serializable")
    if len(canonical) > MAX_OUTPUT_BYTES:
        _fail(f"output size bound exceeded ({MAX_OUTPUT_BYTES} bytes)")
    parsed = json.loads(canonical)
    kind_rank = {"parameter": 0, "request": 1, "response": 2}
    examples.sort(key=lambda e: (e["operation_id"], kind_rank[e["kind"]], e.get("name") or e.get("status") or ""))
    trace.sort(key=lambda t: (t["source_ref"], t["kind"], t["name"]))
    return {
        "openapi": parsed,
        "canonical_json": canonical,
        "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "source_trace": trace,
        "client_examples": json.loads(json.dumps(examples, sort_keys=True)),
        "implementation_verified": False,
        "limits": list(LIMITS),
    }


def _body_must_be_object(rs, comps, label):
    try:
        root = _resolve_root(rs, comps)
    except KeyError:
        return  # dangling is reported later with the ref name
    if root["type"] != "object":
        _fail(f"{label}: request body schema must be an object")
