"""Row 1520 Failure Analysis (ledger: requirement title only - "Failure Analysis", no description).

Bounded plan over caller-supplied failure-analysis declarations. Delta against
the existing mechanism _failure(d) in engineering_1510_1559.py (read on
live main 36e4793f77619645cb221f397cdcd5d2116997a4, line 98): existing is
hypothesis bookkeeping that silently intersects supplied evidence references
(dangling references dropped without notice), carries unvalidated hypothesis
fields through {**h}, and has no schema, no bounds and untagged failure modes;
this unit validates a bounded declaration with FAIL1520-tagged refusals,
refuses dangling and duplicated evidence references, derives counts from
validated references only, and returns a labeled plan. No root-cause
determination, no physical examination, no evidence authentication; the plan
is a plan, never a result.
"""

import unicodedata

ROW = 1520
_P = "FAIL1520: "
_KEYS = ("problem_statement", "evidence", "hypotheses", "timeline", "preservation_actions")
_EVIDENCE_KEYS = ("id", "kind", "description")
_HYPOTHESIS_KEYS = ("id", "statement", "supporting_evidence_ids", "contrary_evidence_ids")
_EVENT_KEYS = ("at", "event")
_BAD_CATS = ("Cc", "Cf", "Zl", "Zp")  # Zs accepted; Cs surrogates stay a disclosed residual
_LIMITS = [
    "Plan over supplied declarations only; evidence kinds, caps and reference rules are bookkeeping conventions, not analysis standards.",
    "No physical examination, laboratory work or evidence authentication is performed here and no root cause is determined or implied.",
    "Supplied timeline labels and preservation actions are bookkeeping only; they are never parsed, ordered or evaluated.",
]


def _unicode_clean(text, name):
    for ch in text:
        if unicodedata.category(ch) in _BAD_CATS:
            _fail(name + " carries a refused Unicode character")
    return text


class FailError(ValueError):
    pass


def _fail(msg):
    raise FailError(_P + msg)


def _text(value, name, cap):
    if type(value) is not str:
        _fail(name + " must be text")
    if len(value) > cap:  # cap before strip, before Unicode
        _fail(name + " must be at most %d characters" % cap)
    if not value.strip():
        _fail(name + " must be non-empty text")
    return _unicode_clean(value, name)


def _mapping(value, name, keys):
    if type(value) is not dict:
        _fail(name + " must be a mapping")
    if len(value) > len(keys):
        _fail("unknown " + name + " key")
    if any(type(k) is not str for k in value):
        _fail(name + " keys must be text")
    for k in keys:
        if k not in value:
            _fail(k + " required")
    if len(value) != len(keys):
        _fail("unknown " + name + " key")
    return value


def _refs(value, name, known):
    if type(value) is not list or len(value) > 50:
        _fail(name + " must be a list of at most 50 references")
    seen = set()
    for entry in value:
        ref = _text(entry, name + " entries", 64)
        if ref in seen:
            _fail("duplicate evidence reference")
        seen.add(ref)
        if ref not in known:
            _fail("unknown evidence reference")
    return list(value)


def plan(data):
    if type(data) is not dict:
        _fail("input must be a mapping")
    if len(data) > len(_KEYS):
        _fail("unknown key")
    if any(type(k) is not str for k in data):
        _fail("keys must be text")
    for k in _KEYS:
        if k not in data:
            _fail(k + " required")
    if len(data) != len(_KEYS):
        _fail("unknown key")
    problem = _text(data["problem_statement"], "problem_statement", 512)
    evidence = data["evidence"]
    if type(evidence) is not list or not 1 <= len(evidence) <= 50:
        _fail("evidence must be a list of 1 to 50 items")
    known = set()
    for item in evidence:
        _mapping(item, "evidence", _EVIDENCE_KEYS)
        eid = _text(item["id"], "evidence id", 64)
        if eid in known:
            _fail("evidence ids must be unique")
        known.add(eid)
        _text(item["kind"], "evidence kind", 32)
        _text(item["description"], "evidence description", 256)
    hypotheses = data["hypotheses"]
    if type(hypotheses) is not list or not 1 <= len(hypotheses) <= 20:
        _fail("hypotheses must be a list of 1 to 20 items")
    out = []
    hids = set()
    unsupported = []
    referenced = set()
    for i, item in enumerate(hypotheses):
        _mapping(item, "hypothesis", _HYPOTHESIS_KEYS)
        hid = _text(item["id"], "hypothesis id", 64)
        if hid in hids:
            _fail("hypothesis ids must be unique")
        hids.add(hid)
        statement = _text(item["statement"], "hypothesis statement", 256)
        sup = _refs(item["supporting_evidence_ids"], "supporting_evidence_ids", known)
        con = _refs(item["contrary_evidence_ids"], "contrary_evidence_ids", known)
        if set(sup) & set(con):
            _fail("an evidence item cannot be both supporting and contrary")
        referenced.update(sup)
        referenced.update(con)
        if not sup:
            unsupported.append(hid)
        out.append({"index": i, "id": hid, "statement": statement,
                    "supporting_evidence_count": len(sup), "contrary_evidence_count": len(con),
                    "net_support": len(sup) - len(con), "status": "candidate_not_root_cause"})
    timeline = data["timeline"]
    if type(timeline) is not list or len(timeline) > 50:
        _fail("timeline must be a list of 0 to 50 events")
    for event in timeline:
        _mapping(event, "timeline", _EVENT_KEYS)
        _text(event["at"], "timeline at", 64)
        _text(event["event"], "timeline event", 256)
    actions = data["preservation_actions"]
    if type(actions) is not list or len(actions) > 20:
        _fail("preservation_actions must be a list of 0 to 20 entries")
    for action in actions:
        _text(action, "preservation_actions entries", 256)
    return {"row": ROW, "analysis_type": "failure",
            "problem_statement": problem,
            "evidence_registered": len(evidence),
            "hypotheses": out,
            "hypotheses_supplied": len(out),
            "unsupported_hypothesis_ids": unsupported,
            "unreferenced_evidence_ids": sorted(known - referenced),
            "timeline_events_declared": len(timeline),
            "preservation_actions_declared": len(actions),
            "root_cause_claimed": False, "evidence_verified": False,
            "plan_only": True, "test_executed": False,
            "limits": list(_LIMITS)}
