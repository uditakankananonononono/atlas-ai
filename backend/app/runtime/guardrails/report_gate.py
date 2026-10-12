"""Report emission gate (instinct-doc group 142, lines 55, 211).

Enforced runtime check over every report BEFORE it leaves the system:
emit_report() runs the landed claim_status check (P65|L55) and refuses -
GuardrailRefusal, ledgered with the report digest and the exact findings -
when any claim is unmarked, conflicting or structural-ambiguous, or when the
report carries no claims at all (a vacuous check proves nothing). Only
reports where every claim is explicitly labeled pass, and the passing digest
is ledgered so the emitted bytes are hash-bound.

The claim grammar and label set belong to claim_status and its contract;
this gate adds the emission choke point, the refusal, and the evidence
ledger. It enforces labeling and provenance discipline; it cannot verify
that a VERIFIED label is true - that binding comes from the evidence gates
(research_gate, tool_usage_bar) the claims point at. Pure stdlib, no I/O,
no clock.
"""
from __future__ import annotations

import hashlib

from app.reports import claim_status

from . import ledger as _ledger
from ._fields import ident, instant, iso, make_fail, sha256_hex, text
from .errors import GuardrailRefusal

PREFIX = "REPGATE"
_fail = make_fail(PREFIX)

MAX_REPORT = 1_000_000
MAX_FINDINGS = 64
VERDICTS = ("emitted", "refused:unmarked_claims", "refused:conflicting_claims",
            "refused:structural_ambiguous", "refused:vacuous")
LIMITS = (
    "Enforces explicit claim labeling only; it cannot verify that a VERIFIED label is true.",
    "Claim grammar is the claim_status contract: table rows with exactly one Label/Status column and CLAIM: marker lines; other prose is not checked.",
    "Only the report digest is stored; the gate keeps no content copy.",
    "The ledger is tamper-evident, not tamper-proof; safe storage of the serialized ledger is the caller's job.",
)

_DECISION_KEYS = {"kind", "report_id", "at", "verdict", "report_sha256",
                  "claims_total", "marked", "findings"}


def _validate_content(ledger):
    for entry in ledger:
        seq = entry["seq"]
        record = entry["record"]
        if record.get("kind") != "decision":
            _fail(f"ledger entry {seq} has an unknown record kind")
        if set(record) != _DECISION_KEYS:
            _fail(f"ledger entry {seq} has an unexpected record shape")
        ident(record["report_id"], "report_id", fail=_fail)
        instant(record["at"], "at", fail=_fail)
        if record["verdict"] not in VERDICTS:
            _fail(f"ledger entry {seq} has an unknown verdict")
        sha256_hex(record["report_sha256"], "report_sha256", fail=_fail)
        for counter in ("claims_total", "marked"):
            if type(record[counter]) is not int or record[counter] < 0:
                _fail(f"ledger entry {seq} has invalid content")
        findings = record["findings"]
        if type(findings) is not list or len(findings) > MAX_FINDINGS:
            _fail(f"ledger entry {seq} has invalid content")
        for finding in findings:
            if type(finding) is not dict or set(finding) != {"line", "kind", "reason"}:
                _fail(f"ledger entry {seq} has invalid content")
            if type(finding["line"]) is not int or finding["line"] < 1:
                _fail(f"ledger entry {seq} has invalid content")
            text(finding["kind"], "kind", fail=_fail, max_len=32)
            text(finding["reason"], "reason", fail=_fail, max_len=256)
    return ledger


def check_ledger(ledger):
    _ledger.check_chain(ledger)
    return _validate_content(ledger)


def dumps(ledger):
    check_ledger(ledger)
    return _ledger.dumps(ledger)


def loads(text_):
    return _ledger.loads(text_, validate_content=_validate_content)


def _findings(result):
    out = []
    for item in result["unmarked"]:
        out.append({"line": item["line"], "kind": "unmarked", "reason": str(item["reason"])[:256]})
    for item in result["conflicting"]:
        out.append({"line": item["line"], "kind": "conflicting",
                    "reason": ("labels " + ",".join(item["tokens"]))[:256]})
    for item in result["structural_ambiguous"]:
        out.append({"line": item["line"], "kind": "structural-ambiguous",
                    "reason": str(item["reason"])[:256]})
    out.sort(key=lambda f: f["line"])
    return out[:MAX_FINDINGS]


def emit_report(report_id, body, *, now, ledger=None, labels=claim_status.DEFAULT_LABELS):
    """The enforcement point: admit one report for emission.

    Returns (ledger, decision record) when every claim is labeled. Raises
    GuardrailRefusal - ledgered first, with the findings - when the report is
    unmarked, conflicting, structural-ambiguous or vacuous.
    """
    report_id = ident(report_id, "report_id", fail=_fail)
    if type(body) is not str or not body.strip():
        _fail("empty_field:report")
    if len(body) > MAX_REPORT:
        _fail("text_too_long:report")
    if ledger is None:
        ledger = []
    check_ledger(ledger)
    at = iso(instant(now, "now", fail=_fail))
    result = claim_status.check_text(body, labels=labels)
    digest = hashlib.sha256(body.encode()).hexdigest()
    findings = _findings(result)
    if result["vacuous"]:
        verdict = "refused:vacuous"
    elif result["unmarked"]:
        verdict = "refused:unmarked_claims"
    elif result["conflicting"]:
        verdict = "refused:conflicting_claims"
    elif result["structural_ambiguous"]:
        verdict = "refused:structural_ambiguous"
    else:
        verdict = "emitted"
    record = {"kind": "decision", "report_id": report_id, "at": at, "verdict": verdict,
              "report_sha256": digest, "claims_total": result["claims_total"],
              "marked": result["marked"], "findings": findings}
    ledger = _ledger.append(ledger, record)
    if verdict != "emitted":
        raise GuardrailRefusal(
            f"{PREFIX}:{verdict}",
            f"report {report_id!r} refused: {verdict} "
            f"({result['claims_total']} claims, {result['marked']} marked)",
            details={"report_id": report_id, "verdict": verdict,
                     "claims_total": result["claims_total"], "marked": result["marked"],
                     "findings": findings},
            ledger=ledger)
    return ledger, record


__all__ = ["VERDICTS", "LIMITS", "emit_report", "check_ledger", "dumps", "loads"]
