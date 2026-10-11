"""Row 849 Non-Monotonic Reasoning: strict front door over the shared stable-model engine.

`revise(payload)` validates every input (exact builtin types, caps, revision-set rules) and only then calls the
unchanged engine `defeasible_reasoning.default_inference`, which recomputes exact stable models before and after
explicit fact additions and removals. The engine's internals are inherited as-is: this module guarantees only what it
validates. Negation is absence from a stable model, never real-world falsehood. No default priority is applied, all
alternative stable models are kept, and nothing is verified against the world. Stdlib only, deterministic.
"""
from __future__ import annotations

import unicodedata

from .defeasible_reasoning import default_inference

PREFIX = "NONMON849"
MAX_FACTS, MAX_RULES, MAX_PREMISES, MAX_ATOM = 32, 16, 8, 64
MAX_ADDED, MAX_REMOVED, MAX_QUERIES, MAX_KEYS, MAX_OPTIONAL_ATOMS = 16, 16, 16, 16, 12
MAX_RULE_ID = 256
_REFUSED_CATEGORIES = ('Cc', 'Cf', 'Zl', 'Zp')  # Zs accepted
_CONCLUSION_KEYS = ("decide", "conclusion", "determination", "truth", "advice")
BOUNDARY = ("Exact finite normal logic-program stable models over caller-supplied symbolic rules. Revision recomputes "
            "models after the stated additions and removals; all alternative stable models are kept, no default "
            "priority and no real-world truth claim is made, and absence from a model is not falsity.")
_TOP = ("facts", "rules", "added_facts", "removed_facts", "query_atoms")
_RULE = ("id", "if", "unless", "then")


def _err(reason):
    return ValueError(PREFIX + ":" + reason)


def _shape(d, allowed, kind):
    if type(d) is not dict:
        raise _err("BAD_TYPE:" + kind)
    if len(d) > MAX_KEYS:  # count before any iteration or lookup
        raise _err("TOO_MANY:keys")
    for k in d:
        if type(k) is not str:
            raise _err("BAD_TYPE:key")
    for k in _CONCLUSION_KEYS:
        if d.get(k):
            raise _err("CONCLUSION_REFUSED")
    for k in d:
        if k not in allowed:
            raise _err("UNKNOWN_KEY")
    for k in allowed:
        if k not in d:
            raise _err("MISSING:" + k)


def _text(v, name, cap):
    if type(v) is not str:
        raise _err("BAD_TYPE:" + name)
    if len(v) > cap:  # raw length before strip or any Unicode scan
        raise _err("TEXT_TOO_LONG:" + name)
    if not v.strip():
        raise _err("EMPTY:" + name)
    if any(unicodedata.category(c) in _REFUSED_CATEGORIES for c in v):
        raise _err("CONTROL_CHARS:" + name)
    return v


def _list(v, name, cap):
    if type(v) is not list:
        raise _err("BAD_TYPE:" + name)
    if len(v) > cap:  # size before any element is read
        raise _err("TOO_MANY:" + name)
    return v


def _atoms(v, name, cap):
    out = []
    for a in _list(v, name, cap):
        _text(a, "atom", MAX_ATOM)
        out.append(a)
    if len(set(out)) != len(out):
        raise _err("DUPLICATE:" + name)
    return out


def _rules(v):
    _list(v, "rules", MAX_RULES)
    if not v:
        raise _err("EMPTY:rules")
    out, ids = [], set()
    for r in v:
        _shape(r, _RULE, "rule")
        rid = _text(r["id"], "rule_id", MAX_RULE_ID)
        if rid in ids:
            raise _err("DUPLICATE:rule_id")
        ids.add(rid)
        body = _atoms(r["if"], "if", MAX_PREMISES)
        unless = _atoms(r["unless"], "unless", MAX_PREMISES)
        head = _text(r["then"], "atom", MAX_ATOM)
        out.append({"id": rid, "if": body, "unless": unless, "then": head})
    return out


def revise(payload):
    """Recompute stable models after explicit fact additions/removals; decide nothing else."""
    _shape(payload, _TOP, "payload")
    facts = _atoms(payload["facts"], "facts", MAX_FACTS)
    rules = _rules(payload["rules"])
    added = _atoms(payload["added_facts"], "added_facts", MAX_ADDED)
    removed = _atoms(payload["removed_facts"], "removed_facts", MAX_REMOVED)
    queries = _atoms(payload["query_atoms"], "query_atoms", MAX_QUERIES)
    if set(added) & set(facts):
        raise _err("ADDED_ALREADY_PRESENT")
    if not set(removed) <= set(facts):
        raise _err("REMOVED_NOT_PRESENT")
    revised = (set(facts) - set(removed)) | set(added)
    rule_atoms = set()
    for r in rules:
        rule_atoms |= {r["then"]} | set(r["if"]) | set(r["unless"])
    for state in (set(facts), revised):  # the engine's optional-atom search bound, checked on both states
        if len(rule_atoms - state) > MAX_OPTIONAL_ATOMS:
            raise _err("TOO_MANY:optional_atoms")
    e = default_inference({"facts": facts, "defaults": rules, "added_facts": added, "removed_facts": removed,
                           "query_atoms": queries})
    before = e["before"]
    comparable = bool(before["consistent"] and e["consistent"])
    return {
        "row": 849, "status": "recomputed_exact_stable_models_only",
        "revision": {"added_facts": sorted(added), "removed_facts": sorted(removed)},
        "before": {"stable_models": before["stable_models"], "model_count": before["model_count"],
                   "cautious_conclusions": before["cautious_conclusions"], "consistent": before["consistent"]},
        "stable_models": e["stable_models"], "model_count": e["model_count"],
        "cautious_conclusions": e["cautious_conclusions"], "possible_conclusions": e["possible_conclusions"],
        "ambiguous_conclusions": e["ambiguous_conclusions"], "consistent": e["consistent"],
        "revision_comparable": comparable,
        "retracted_conclusions": e["retracted_conclusions"] if comparable else None,
        "new_conclusions": e["new_conclusions"] if comparable else None,
        "queries": e["queries"],
        "no_real_world_truth_claim": True, "default_priority_applied": False, "boundary": BOUNDARY,
    }
