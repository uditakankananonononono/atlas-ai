"""c37.cross_field_loop (doc row 103): across-field leader analysis ->
integration ticket loop.

Closes the audit gap on c37.leaders/c34.industry ("no cross-field autonomous
knowledge/build loop"): a deterministic LOOP that takes leader/method records
(with evidence), takes target problems in OTHER fields, generates
method-transfer proposals scored by evidence support, and emits integration
tickets in the m14 project-builder intake shape - closing the
analyze -> propose -> queue-for-build circuit over supplied records.

Honest bounds: the loop runs over SUPPLIED records only (no live research),
scores are transparent counts of distinct evidence references, and tickets
enter "owner_review" - nothing is built, launched or integrated
automatically. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import hashlib
import json
import re

from app.modules.c30 import policy

PREFIX = "INTEL"
MAX_ENTITIES = 500
MAX_PROBLEMS = 200
MAX_PROPOSALS = 1000
MAX_TICKETS = 50
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

LIMITS = (
    "Loop runs over supplied records only; no live research or fetching.",
    "Scores are distinct-evidence counts, not a judgement of superiority.",
    "Tickets queue for owner review; nothing is built or integrated automatically.",
)


def _err(code, detail=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, code, (":" + detail) if detail else ""))


def _entity(e):
    if not isinstance(e, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:entity" % PREFIX)
    eid = policy.clean_text(e.get("id"), PREFIX, "entity.id", 64)
    name = policy.clean_text(e.get("name"), PREFIX, "entity.name", 256)
    field = policy.clean_text(e.get("field"), PREFIX, "entity.field", 120)
    methods = e.get("methods", [])
    if isinstance(methods, bool) or not isinstance(methods, (list, tuple)):
        raise ValueError("%s_REFUSED_BAD_TYPE:methods" % PREFIX)
    out = []
    for m in methods:
        if not isinstance(m, dict):
            raise ValueError("%s_REFUSED_BAD_TYPE:method" % PREFIX)
        mid = policy.clean_text(m.get("id"), PREFIX, "method.id", 64)
        summary = policy.clean_text(m.get("summary"), PREFIX, "method.summary", 2000, allow_ws=True)
        refs = m.get("evidence_refs", [])
        if isinstance(refs, bool) or not isinstance(refs, (list, tuple)) or not refs:
            _err("NOSOURCE", mid)
        out.append({"id": mid, "summary": summary,
                    "evidence_refs": sorted({policy.clean_text(r, PREFIX, "ref", 256)
                                             for r in refs})})
    return {"id": eid, "name": name, "field": field, "methods": out}


def _problem(p):
    if not isinstance(p, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:problem" % PREFIX)
    pid = policy.clean_text(p.get("id"), PREFIX, "problem.id", 64)
    field = policy.clean_text(p.get("field"), PREFIX, "problem.field", 120)
    statement = policy.clean_text(p.get("statement"), PREFIX, "problem.statement", 2000,
                                  allow_ws=True)
    refs = p.get("evidence_refs", [])
    if isinstance(refs, bool) or not isinstance(refs, (list, tuple)):
        raise ValueError("%s_REFUSED_BAD_TYPE:evidence_refs" % PREFIX)
    return {"id": pid, "field": field, "statement": statement,
            "evidence_refs": sorted({policy.clean_text(r, PREFIX, "ref", 256) for r in refs})}


def run(body):
    """body = {"as_of", "entities": [...], "problems": [...], "max_tickets"?}.
    Returns ranked cross-field transfer proposals plus m14-shaped tickets."""
    if isinstance(body, bool) or not isinstance(body, dict) \
            or not {"as_of", "entities", "problems"} <= set(body):
        raise ValueError("%s_REFUSED_BAD_TYPE:body" % PREFIX)
    as_of = body["as_of"]
    if not isinstance(as_of, str) or not _DATE.fullmatch(as_of):
        raise ValueError("%s_REFUSED_BAD_TYPE:as_of" % PREFIX)
    entities = body["entities"]
    problems = body["problems"]
    if isinstance(entities, bool) or not isinstance(entities, (list, tuple)) \
            or not entities or len(entities) > MAX_ENTITIES:
        raise ValueError("%s_REFUSED_BAD_TYPE:entities" % PREFIX)
    if isinstance(problems, bool) or not isinstance(problems, (list, tuple)) \
            or not problems or len(problems) > MAX_PROBLEMS:
        raise ValueError("%s_REFUSED_BAD_TYPE:problems" % PREFIX)
    max_tickets = body.get("max_tickets", 10)
    if isinstance(max_tickets, bool) or not isinstance(max_tickets, int) \
            or not 1 <= max_tickets <= MAX_TICKETS:
        raise ValueError("%s_REFUSED_BAD_TYPE:max_tickets" % PREFIX)
    ents = [_entity(e) for e in entities]
    probs = [_problem(p) for p in problems]
    fields = sorted({e["field"] for e in ents} | {p["field"] for p in probs})
    proposals = []
    for e in ents:
        for m in e["methods"]:
            for p in probs:
                if p["field"] == e["field"]:
                    continue  # cross-field only
                if len(proposals) >= MAX_PROPOSALS:
                    _err("OVERSIZE", "proposals")
                support = sorted(set(m["evidence_refs"]) | set(p["evidence_refs"]))
                score = len(set(m["evidence_refs"])) + len(set(p["evidence_refs"]))
                proposals.append({
                    "source_entity": e["name"], "source_field": e["field"],
                    "method_id": m["id"], "method_summary": m["summary"],
                    "target_problem": p["id"], "target_field": p["field"],
                    "problem_statement": p["statement"],
                    "evidence_support": support, "score": score,
                })
    proposals.sort(key=lambda x: (-x["score"], x["source_entity"], x["method_id"],
                                  x["target_problem"]))
    tickets = []
    for i, prop in enumerate(proposals[:max_tickets]):
        tid = "xfield-" + hashlib.sha256(json.dumps(
            [prop["method_id"], prop["target_problem"]]).encode()).hexdigest()[:10]
        tickets.append({
            "ticket_id": tid,
            "kind": "integration_proposal",
            "title": "Apply %s (%s) to %s problem %s" % (
                prop["method_id"], prop["source_field"], prop["target_field"],
                prop["target_problem"]),
            "spec": {
                "hypothesis": "Method from %s may transfer to %s." % (
                    prop["source_field"], prop["target_field"]),
                "method_summary": prop["method_summary"],
                "problem_statement": prop["problem_statement"],
                "evidence_support": prop["evidence_support"],
            },
            "status": "owner_review",
            "rank": i + 1,
            "score": prop["score"],
        })
    return {
        "as_of": as_of,
        "fields_covered": fields,
        "cross_field_pairs": sorted({"%s->%s" % (p["source_field"], p["target_field"])
                                     for p in proposals}),
        "proposals_considered": len(proposals),
        "tickets": tickets,
        "loop": {"analyze": "entities+methods+problems supplied with evidence",
                 "propose": "cross-field method transfer ranked by evidence support",
                 "queue": "top-%d tickets emitted in m14 intake shape" % len(tickets)},
        "limits": list(LIMITS),
        "scope": policy.scope(["cross-field-transfer-proposals", "evidence-ranked",
                               "m14-shaped-tickets"],
                              ["live-research", "automatic-build", "superiority-claims"],
                              "supplied-records", as_of),
    }
