"""Per-project verified tool-use bar (instinct-doc groups 141 + 3 + 4, line 1
vs lines 67-68).

The source doc contradicts itself: the opening passage demands 200+ external
tools for EACH project; a later section says 40+ per project and 200+ across
the program. This gate implements evidence for the STRICTEST reading so
either ruling lands without rework: the bar is a parameter, defaulting to 200
per project, and evaluate() reports the count against any bar the caller
asks about. Nothing is silently reduced.

A tool use counts only when the record carries BOTH an evidence_ref and a
verified_by attestation (fail closed): a bare declaration is not use. The
count is distinct verified tools per project - recording the same tool twice
never inflates it. require_bar() is the enforcement point: below the bar it
raises GuardrailRefusal naming the exact shortfall, so no completion path
can claim the bar while the evidence says otherwise. Every evaluation is
ledgered. Pure stdlib, no I/O, no clock.
"""
from __future__ import annotations

from . import ledger as _ledger
from ._fields import ident, instant, iso, make_fail, text
from .errors import GuardrailRefusal

PREFIX = "TOOLBAR"
_fail = make_fail(PREFIX)

DEFAULT_BAR = 200            # strictest reading: 200+ tools EACH project
ALTERNATIVE_BAR = 40         # later passage: 40+ per project, 200+ program-wide
MAX_BAR = 100000
MAX_TOOL = 128
MAX_REF = 256
VERDICTS = ("met", "unmet")
LIMITS = (
    "Verification is caller-attested: a use record counts only with a recorded verifier and evidence reference; the gate cannot execute the tools.",
    "Counts are distinct verified tools per project; they say nothing about how well any tool was used.",
    "The default bar is the doc's strictest passage (200+ each); evaluate() takes any bar so an owner ruling for 40+ needs no code change.",
    "The ledger is tamper-evident, not tamper-proof; safe storage of the serialized ledger is the caller's job.",
)

_USE_KEYS = {"kind", "project_id", "tool", "used_at", "evidence_ref", "verified_by"}
_EVAL_KEYS = {"kind", "project_id", "bar", "at", "verdict", "distinct_verified_tools", "shortfall"}


def _validate_content(ledger):
    for entry in ledger:
        seq = entry["seq"]
        record = entry["record"]
        kind = record.get("kind")
        if kind == "tool_use_recorded":
            if set(record) != _USE_KEYS:
                _fail(f"ledger entry {seq} has an unexpected record shape")
            ident(record["project_id"], "project_id", fail=_fail)
            text(record["tool"], "tool", fail=_fail, max_len=MAX_TOOL)
            instant(record["used_at"], "used_at", fail=_fail)
            text(record["evidence_ref"], "evidence_ref", fail=_fail, max_len=MAX_REF)
            text(record["verified_by"], "verified_by", fail=_fail)
        elif kind == "bar_evaluated":
            if set(record) != _EVAL_KEYS:
                _fail(f"ledger entry {seq} has an unexpected record shape")
            ident(record["project_id"], "project_id", fail=_fail)
            if type(record["bar"]) is not int or type(record["bar"]) is bool or not 1 <= record["bar"] <= MAX_BAR:
                _fail(f"ledger entry {seq} has an invalid bar")
            instant(record["at"], "at", fail=_fail)
            if record["verdict"] not in VERDICTS:
                _fail(f"ledger entry {seq} has an unknown verdict")
            if type(record["distinct_verified_tools"]) is not int or record["distinct_verified_tools"] < 0:
                _fail(f"ledger entry {seq} has invalid content")
            if type(record["shortfall"]) is not int or record["shortfall"] < 0:
                _fail(f"ledger entry {seq} has invalid content")
        else:
            _fail(f"ledger entry {seq} has an unknown record kind")
    return ledger


def check_ledger(ledger):
    _ledger.check_chain(ledger)
    return _validate_content(ledger)


def dumps(ledger):
    check_ledger(ledger)
    return _ledger.dumps(ledger)


def loads(text_):
    return _ledger.loads(text_, validate_content=_validate_content)


def record_use(ledger, project_id, tool, *, used_at, evidence_ref, verified_by):
    """Record one verified tool use. evidence_ref and verified_by are both
    REQUIRED (fail closed): a use without an attestation never counts."""
    check_ledger(ledger)
    project_id = ident(project_id, "project_id", fail=_fail)
    tool = text(tool, "tool", fail=_fail, max_len=MAX_TOOL)
    used = iso(instant(used_at, "used_at", fail=_fail))
    evidence_ref = text(evidence_ref, "evidence_ref", fail=_fail, max_len=MAX_REF)
    verified_by = text(verified_by, "verified_by", fail=_fail)
    return _ledger.append(ledger, {"kind": "tool_use_recorded", "project_id": project_id,
                                   "tool": tool, "used_at": used,
                                   "evidence_ref": evidence_ref, "verified_by": verified_by})


def verified_tools(ledger, project_id):
    """Distinct verified tool names for one project, sorted."""
    check_ledger(ledger)
    project_id = ident(project_id, "project_id", fail=_fail)
    tools = set()
    for entry in ledger:
        record = entry["record"]
        if record["kind"] == "tool_use_recorded" and record["project_id"] == project_id:
            tools.add(record["tool"])
    return sorted(tools)


def evaluate(ledger, project_id, *, bar=DEFAULT_BAR, now):
    """Evaluate one project against a bar. Returns (ledger, verdict record).

    The verdict is ledgered either way: an UNMET evaluation is the truthful
    evidence state, not an error. Raises GuardrailRefusal never; use
    require_bar for enforcement.
    """
    check_ledger(ledger)
    project_id = ident(project_id, "project_id", fail=_fail)
    if type(bar) is not int or type(bar) is bool or not 1 <= bar <= MAX_BAR:
        _fail("bad_range:bar")
    at = iso(instant(now, "now", fail=_fail))
    count = len(verified_tools(ledger, project_id))
    verdict = "met" if count >= bar else "unmet"
    record = {"kind": "bar_evaluated", "project_id": project_id, "bar": bar, "at": at,
              "verdict": verdict, "distinct_verified_tools": count,
              "shortfall": max(0, bar - count)}
    return _ledger.append(ledger, record), record


def require_bar(ledger, project_id, *, bar=DEFAULT_BAR, now):
    """The enforcement point: refuse when the project is below the bar.

    Returns (ledger, verdict record) when met. Raises GuardrailRefusal with
    the exact shortfall when unmet; the unmet evaluation is ledgered first.
    """
    ledger, record = evaluate(ledger, project_id, bar=bar, now=now)
    if record["verdict"] != "met":
        raise GuardrailRefusal(
            f"{PREFIX}:bar_unmet",
            f"project {project_id!r} has {record['distinct_verified_tools']} distinct verified "
            f"tools against a bar of {bar} (shortfall {record['shortfall']})",
            details={"project_id": project_id, "bar": bar,
                     "distinct_verified_tools": record["distinct_verified_tools"],
                     "shortfall": record["shortfall"]},
            ledger=ledger)
    return ledger, record


__all__ = ["DEFAULT_BAR", "ALTERNATIVE_BAR", "VERDICTS", "LIMITS", "record_use",
           "verified_tools", "evaluate", "require_bar", "check_ledger", "dumps", "loads"]
