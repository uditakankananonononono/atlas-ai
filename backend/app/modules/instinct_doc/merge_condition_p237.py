"""Merge-condition audit for doc line [P237|L186] (offline, stdlib only).

Doc line, verbatim: "- Merge Meemee to Claire if she has extra capabilities."

The "if" is the whole unit. Given caller-declared capability inventories for
Meemee and Claire, this unit RECOMPUTES the condition: the extra
capabilities Meemee holds that Claire lacks (set difference, sorted) and the
shared ones. MERGE_CONDITION_MET only when the recomputed extra set is
non-empty. The merge itself is never performed here - it is an
approval-bound action outside this unit, recorded asserted=False.
"""
from __future__ import annotations

import hashlib
import json

FEATURE = "merge_condition_p237"
SOURCE_LINES = ["P237|L186"]
DOC_LINE = "- Merge Meemee to Claire if she has extra capabilities."

MAX_CAPABILITIES = 1_000
CAPABILITY_LIMIT = 128
FIELDS = frozenset({"meemee", "claire"})
SIDE_FIELDS = frozenset({"capabilities"})

MEASURE = "merge-condition audit: extra-capability set recomputed from caller-declared inventories"
DOC_CLAIMS = [{"claim": "Meemee merged into Claire", "asserted": False,
               "note": "merge never performed by this unit; the condition is recomputed only"}]
METHOD_LIMITS = (
    "This unit never merges anything; it recomputes the doc's 'if' condition from caller-declared inventories. ",
    "Inventories are caller-declared labels; duplicates refuse, but the truth of any capability is not judged. ",
    "MERGE_CONDITION_MET names a non-empty recomputed set difference, not a recommendation or an action. ",
)


def _fail(code):
    raise ValueError("P237:" + code)


def _capabilities(side, payload, name):
    if side not in payload:
        _fail("missing_field:%s" % side)
    block = payload[side]
    if type(block) is not dict:
        _fail("bad_type:%s" % side)
    for key in block:
        if key not in SIDE_FIELDS:
            _fail("unknown_field:%s.%s" % (side, key))
    if "capabilities" not in block:
        _fail("missing_field:%s.capabilities" % side)
    caps = block["capabilities"]
    if type(caps) is not list:
        _fail("bad_type:%s.capabilities" % side)
    if len(caps) > MAX_CAPABILITIES:
        _fail("too_many:capabilities")
    seen = set()
    out = []
    for i, c in enumerate(caps):
        field = "%s.capabilities[%d]" % (side, i)
        if type(c) is not str:
            _fail("bad_type:%s" % field)
        if not c.strip():
            _fail("empty_field:%s" % field)
        if len(c) > CAPABILITY_LIMIT:
            _fail("text_too_long:%s" % field)
        clean = c.strip()
        if clean in seen:
            _fail("duplicate_capability:%s" % clean)
        seen.add(clean)
        out.append(clean)
    return out


def evaluate(payload):
    """Recompute the merge condition. No I/O, never merges."""
    if type(payload) is not dict:
        _fail("bad_type:payload")
    for key in payload:
        if key not in FIELDS:
            _fail("unknown_field:%s" % key)
    meemee = _capabilities("meemee", payload, "meemee")
    claire = _capabilities("claire", payload, "claire")
    claire_set = set(claire)
    extra = sorted(c for c in meemee if c not in claire_set)
    shared = sorted(c for c in meemee if c in claire_set)
    blob = json.dumps({"meemee": meemee, "claire": claire},
                      sort_keys=True, separators=(",", ":"))
    return {"feature": FEATURE,
            "source_lines": list(SOURCE_LINES),
            "doc_line": DOC_LINE,
            "measure": MEASURE,
            "payload_sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
            "extra_capabilities": extra,
            "shared_capabilities": shared,
            "meemee_count": len(meemee),
            "claire_count": len(claire),
            "verdict": "MERGE_CONDITION_MET" if extra else "MERGE_CONDITION_NOT_MET",
            "doc_claims": [dict(c) for c in DOC_CLAIMS],
            "limits": list(METHOD_LIMITS)}


_KEYS = {"feature", "source_lines", "doc_line", "measure", "payload_sha256",
         "extra_capabilities", "shared_capabilities", "meemee_count",
         "claire_count", "verdict", "doc_claims", "limits"}


def verify(payload, result):
    """Recompute from the same payload and compare EVERY field in _KEYS;
    failed names the exact fields that differ. Deterministic, internal
    consistency only."""
    checks = ["structure", "exact_keys", "field_equality"]
    if type(result) is not dict:
        return {"verified": False, "failed": ["structure"], "checks": checks}
    if set(result) != _KEYS:
        return {"verified": False, "failed": ["exact_keys"], "checks": checks}
    expected = evaluate(payload)
    failed = [key for key in sorted(_KEYS) if result[key] != expected[key]]
    return {"verified": not failed, "failed": failed, "checks": checks}


def run(payload):
    result = evaluate(payload)
    receipt = verify(payload, result)
    return {"status": "evaluated" if receipt["verified"] else "verification_failed",
            "result": result, "verification": receipt}
