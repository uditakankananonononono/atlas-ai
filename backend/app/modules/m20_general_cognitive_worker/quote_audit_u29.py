"""U29: local audit harness that checks a unit's built code against the owner's exact quote.

What it does: for each "essence" (an exact fragment of the quote) it checks that the evidence the
caller declared exists in the sources the caller supplied (a file, a defined name, a test function,
a text fragment) and that the caller-supplied result for each test is "passed". It lists quote words
no essence covers. It never runs a test, reads meaning, or calls a network service.

External validation (chatgpt, deepseek, claude, perplexity) is only a hook: ``build_external_packet``
assembles what WOULD be sent and a pending proposal for the approval center; ``release_packet``
returns the payload only against a matching owner approval. This module has no send function.
Every refusal starts with ``U29:``.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from typing import Any

PROVIDERS = ("chatgpt", "deepseek", "claude", "perplexity")
NOTE = ("U29: structural evidence check against the quote; it did not run any test, read any meaning, "
        "or judge whether the code does what the quote means.")
QUESTION = ("Does the supplied code, as evidenced here, cover this fragment of the quote? "
            "Answer per fragment and say what is not covered.")
_UNIT_KEYS = {"unit_id", "quote", "quote_sha256", "essences"}
_REQUIRED = ("unit_id", "quote", "quote_sha256", "essences")
_CHECKS = {"file": ("path",), "symbol": ("path", "name"), "test": ("path", "name"), "text": ("path", "contains")}
_SECRET = re.compile(
    r"AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{36}"
    r"|(?i:api[_-]?key|secret|passw(?:or)?d|token)\s*[:=]\s*\S{6,}|Bearer [A-Za-z0-9._-]{16,}")


class QuoteAuditError(ValueError):
    """Refused input. The message always starts with ``U29:``."""


def _fail(text: str) -> None:
    raise QuoteAuditError(f"U29: {text}")


def quote_sha256(quote: str) -> str:
    return hashlib.sha256(quote.encode("utf-8")).hexdigest()


def _defined(tree: ast.AST, name: str) -> bool:
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == name
               for n in ast.walk(tree))


def _parse(sources: dict[str, str], path: str, cache: dict[str, Any]):
    if path not in cache:
        try:
            cache[path] = ast.parse(sources[path])
        except SyntaxError:
            cache[path] = None
    return cache[path]


def _validate_unit(unit: Any) -> None:
    if not isinstance(unit, dict):
        _fail("unit must be an object")
    extra = set(unit) - _UNIT_KEYS
    if extra:
        _fail(f"unknown unit key(s) {sorted(extra)}")
    for key in _REQUIRED:
        if key not in unit:
            _fail(f"unit key '{key}' is required")
    if not isinstance(unit["quote"], str) or not unit["quote"]:
        _fail("quote must be a non-empty string")
    if quote_sha256(unit["quote"]) != unit["quote_sha256"]:
        _fail("quote does not match its recorded sha256 (the quote must be word for word)")
    essences = unit["essences"]
    if not isinstance(essences, list) or not essences:
        _fail("essences must be a non-empty list")
    seen: set[str] = set()
    for e in essences:
        if not isinstance(e, dict):
            _fail("each essence must be an object")
        eid = e.get("id")
        if not isinstance(eid, str) or not eid:
            _fail("each essence needs a non-empty string id")
        if eid in seen:
            _fail(f"duplicate essence id '{eid}'")
        seen.add(eid)
        frag = e.get("fragment")
        if not isinstance(frag, str) or not frag or frag not in unit["quote"]:
            _fail(f"essence '{eid}' fragment is not an exact substring of the quote")
        reqs = e.get("requires")
        if not isinstance(reqs, list):
            _fail(f"essence '{eid}' requires must be a list")
        for r in reqs:
            kind = r.get("kind") if isinstance(r, dict) else None
            if kind not in _CHECKS:
                _fail(f"essence '{eid}' has unknown check kind '{kind}'")
            for field in _CHECKS[kind]:
                if not isinstance(r.get(field), str) or not r.get(field):
                    _fail(f"essence '{eid}' check '{kind}' requires '{field}'")


def audit_unit(unit: dict[str, Any], sources: dict[str, str], test_results: dict[str, str] | None = None,
               as_of: str | None = None) -> dict[str, Any]:
    if not isinstance(unit, dict):
        _fail("unit must be an object")
    if not isinstance(sources, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in sources.items()):
        _fail("sources must be an object of path to text")
    if test_results is None:
        test_results = {}
    if not isinstance(test_results, dict):
        _fail("test_results must be an object")
    if as_of is not None and not isinstance(as_of, str):
        _fail("as_of must be a string or None")
    _validate_unit(unit)
    quote = unit["quote"]
    cache: dict[str, Any] = {}
    out = []
    counts = {"evidenced": 0, "missing": 0, "test_failed": 0, "tests_not_run": 0}
    for e in unit["essences"]:
        missing: list[str] = []
        failed: list[str] = []
        not_run: list[str] = []
        problems: list[str] = []
        if not e["requires"]:
            missing.append("no evidence checks declared")
        for r in e["requires"]:
            kind, path = r["kind"], r["path"]
            if path not in sources:
                missing.append(f"file '{path}' not supplied")
                continue
            if kind == "file":
                continue
            if kind == "text":
                if r["contains"] not in sources[path]:
                    missing.append(f"text '{r['contains']}' not found in '{path}'")
                continue
            tree = _parse(sources, path, cache)
            if tree is None:
                missing.append(f"file '{path}' does not parse")
                continue
            if kind == "symbol":
                if not _defined(tree, r["name"]):
                    missing.append(f"symbol '{r['name']}' not defined in '{path}'")
                continue
            if not _defined(tree, r["name"]):
                missing.append(f"test '{r['name']}' not found in '{path}'")
                continue
            tid = f"{path}::{r['name']}"
            if tid not in test_results:
                not_run.append(f"no result supplied for '{tid}'")
            elif test_results[tid] != "passed":
                failed.append(f"test '{tid}' result is '{test_results[tid]}'")
        problems = missing + failed + not_run
        status = "missing" if missing else "test_failed" if failed else "tests_not_run" if not_run else "evidenced"
        counts[status] += 1
        out.append({"id": e["id"], "fragment": e["fragment"], "status": status, "problems": problems})
    covered = [False] * len(quote)
    for e in unit["essences"]:
        frag, i = e["fragment"], quote.find(e["fragment"])
        while i != -1:
            for k in range(i, i + len(frag)):
                covered[k] = True
            i = quote.find(frag, i + 1)
    unmapped = []
    pos = 0
    for word in quote.split():
        start = quote.index(word, pos)
        pos = start + len(word)
        if not all(covered[start:pos]):
            unmapped.append(word)
    return {"unit_id": unit["unit_id"], "quote_sha256": unit["quote_sha256"], "essences": out,
            "counts": counts, "unmapped_quote_words": unmapped, "note": NOTE,
            "scope": {"implemented": [x["id"] for x in out if x["status"] == "evidenced"],
                      "not_implemented": [x["id"] for x in out if x["status"] != "evidenced"],
                      "data_source": "caller-supplied sources and test results", "as_of": as_of}}


def _packet_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def build_external_packet(unit: dict[str, Any], report: dict[str, Any], excerpts: dict[str, str],
                          providers: list[str], sources: dict[str, str], code_summary: str = "",
                          tests: list[str] | None = None, limits: list[str] | None = None) -> dict[str, Any]:
    _validate_unit(unit)
    if not isinstance(providers, list) or not providers:
        _fail("providers must be a non-empty list")
    seen: set[str] = set()
    for p in providers:
        if p not in PROVIDERS:
            _fail(f"provider '{p}' is not one of {PROVIDERS}")
        if p in seen:
            _fail(f"provider '{p}' listed more than once")
        seen.add(p)
    if not isinstance(excerpts, dict) or not isinstance(sources, dict):
        _fail("excerpts and sources must be objects")
    for path, text in excerpts.items():
        if path not in sources:
            _fail(f"excerpt path '{path}' is not in the supplied sources")
        if not isinstance(text, str) or text not in sources[path]:
            _fail(f"excerpt for '{path}' is not part of the supplied source text")
        if _SECRET.search(text):
            _fail(f"excerpt for '{path}' looks like it contains a credential; not packaged")
    tests = [] if tests is None else tests
    limits = [] if limits is None else limits
    if not isinstance(code_summary, str):
        _fail("code_summary must be a string")
    for name, vals in (("tests", tests), ("limits", limits)):
        if not isinstance(vals, list) or not all(isinstance(v, str) for v in vals):
            _fail(f"{name} must be a list of strings")
    for text in [code_summary, *tests, *limits]:
        if _SECRET.search(text):
            _fail("code_summary, tests or limits look like they contain a credential; not packaged")
    payload = {"unit_id": unit["unit_id"], "quote": unit["quote"], "report": report,
               "excerpts": dict(excerpts), "code_summary": code_summary, "tests": list(tests),
               "limits": list(limits), "question": QUESTION}
    digest = _packet_hash(payload)
    return {"payload": payload, "packet_sha256": digest,
            "proposal": {"action": "external_validation_send", "status": "pending_owner_approval",
                         "executed": False, "providers": list(providers), "packet_sha256": digest,
                         "unit_id": unit["unit_id"], "approval_path": "m00_approval_center",
                         "sends_nothing_itself": True}}


def release_packet(packet: dict[str, Any], approval: Any) -> dict[str, Any]:
    if not isinstance(approval, dict):
        _fail("an approval record is required")
    if _packet_hash(packet["payload"]) != packet["packet_sha256"]:
        _fail("packet payload does not match its sha256")
    if approval.get("decision") != "approved":
        _fail("approval decision is not 'approved'")
    if approval.get("approved_by") != "owner":
        _fail("approval must be recorded as approved_by 'owner'")
    if approval.get("packet_sha256") != packet["packet_sha256"]:
        _fail("approval does not match this packet (sha256 differs)")
    covered = approval.get("providers")
    covered = covered if isinstance(covered, list) else []
    for p in packet["proposal"]["providers"]:
        if p not in covered:
            _fail(f"approval does not cover provider '{p}'")
    return {"payload": packet["payload"], "providers": list(packet["proposal"]["providers"]),
            "released": True, "sent": False,
            "dispatch": "only through the approval center; this module has no send function"}


def _check_packet(packet: Any) -> None:
    if not isinstance(packet, dict) or "payload" not in packet or "packet_sha256" not in packet:
        _fail("a packet from build_external_packet is required")
    if _packet_hash(packet["payload"]) != packet["packet_sha256"]:
        _fail("packet payload does not match its sha256")


def record_response(packet: dict[str, Any], provider: str, response_text: str, as_of: str) -> dict[str, Any]:
    """Store a validator's response verbatim. It is evidence, never approval; nothing is parsed or judged."""
    _check_packet(packet)
    if provider not in packet["proposal"]["providers"]:
        _fail(f"provider '{provider}' is not one the packet was prepared for")
    if not isinstance(response_text, str) or not response_text:
        _fail("response_text must be a non-empty string")
    if not isinstance(as_of, str) or not as_of:
        _fail("as_of must be a non-empty string")
    return {"unit_id": packet["payload"]["unit_id"], "provider": provider,
            "packet_sha256": packet["packet_sha256"], "response_text": response_text,
            "response_sha256": hashlib.sha256(response_text.encode("utf-8")).hexdigest(), "as_of": as_of,
            "status": "evidence_not_approval", "approval": False}


def tickets_from_gaps(response: dict[str, Any], gaps: list[str]) -> list[dict[str, Any]]:
    """One open ticket per gap the caller lists. The harness does not read gaps out of the response."""
    if not isinstance(response, dict) or response.get("status") != "evidence_not_approval" \
            or not isinstance(response.get("response_sha256"), str):
        _fail("a response from record_response is required")
    if not isinstance(gaps, list) or not all(isinstance(g, str) and g for g in gaps) or len(set(gaps)) != len(gaps):
        _fail("gaps must be a list of distinct non-empty strings")
    return [{"ticket_id": hashlib.sha256(f"{response['response_sha256']}|{g}".encode("utf-8")).hexdigest()[:16],
             "unit_id": response["unit_id"], "provider": response["provider"], "gap": g, "status": "open",
             "source_response_sha256": response["response_sha256"]} for g in gaps]
