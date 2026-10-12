"""Bio work admission gate (instinct-doc groups 134 + 135, lines 57-58).

Enforced runtime check over every biology-scoped work item BEFORE any effect
runs. Composes the two landed contract helpers into one admission decision:

- P69|L58 prohibited-bio screen over the item's instruction text: a blocked
  verdict (wet-lab protocol, pathogen enhancement, harm instruction) is an
  unconditional refusal - no approval path can override it.
- P68|L57 in-silico-only classification: physical execution of a bio-scoped
  item is refused unless the caller supplies an approval_check hook that
  validates the item's approval_ref. The hook is caller-bound (wire it to the
  review gate / Module 0); when no hook is supplied the gate fails closed.
  The gate never authenticates an approval reference itself.

Every admission decision - admitted or refused - is appended to the gate's
hash-chained ledger, and run_guarded records the effect outcome as a second
entry, so what was let through and what ran is reconstructable without
trusting logs. The lexical screens underneath keep their own documented
limits: a clear screen means only that no listed pattern matched, and the
closed term sets are contract-governed. Pure stdlib, no I/O, no clock.
"""
from __future__ import annotations

from app.modules.instinct_doc import insilico_guardrail_p68 as p68
from app.modules.instinct_doc import prohibited_bio_p69 as p69

from . import ledger as _ledger
from ._fields import ident, instant, iso, make_fail, text
from .errors import GuardrailRefusal

PREFIX = "BIOGATE"
_fail = make_fail(PREFIX)

MAX_TEXT = 4096
MAX_TERMS = 32
VERDICTS = (
    "admitted:not_bio_scoped",
    "admitted:in_silico",
    "admitted:physical_with_validated_approval",
    "refused:prohibited_bio",
    "refused:physical_without_review",
    "refused:physical_approval_unverifiable",
    "refused:physical_approval_rejected",
)
LIMITS = (
    "Lexical enforcement over the item's declared text and domain terms only; it is not a biosafety, ethics or legal review.",
    "A clear P69 screen means only that no listed prohibited pattern matched; the closed pattern list is contract-governed.",
    "approval_check is a caller-bound hook: the gate records its boolean answer and never authenticates, resolves or trusts an approval_ref by itself.",
    "The ledger is tamper-evident, not tamper-proof; safe storage of the serialized ledger is the caller's job.",
)

_DECISION_KEYS = {"kind", "item_id", "at", "verdict", "p68_verdict", "p69_verdict",
                  "p69_category", "approval_checked", "approval_accepted"}
_EFFECT_KEYS = {"kind", "item_id", "at", "outcome", "error_type"}


def _check_item(item):
    if type(item) is not dict:
        _fail("bad_type:item")
    allowed = {"id", "text", "domain_terms", "execution_mode", "approval_ref"}
    if any(k not in allowed for k in item):
        _fail("unknown_fields:item")
    for name in ("id", "text", "domain_terms", "execution_mode"):
        if name not in item:
            _fail(f"empty_field:{name}")
    item_id = ident(item["id"], "id", fail=_fail)
    body = text(item["text"], "text", fail=_fail, max_len=MAX_TEXT)
    terms = item["domain_terms"]
    if type(terms) is not list or len(terms) > MAX_TERMS:
        _fail("bad_type:domain_terms" if type(terms) is not list else "limit_exceeded:domain_terms")
    for term in terms:
        text(term, "domain_terms", fail=_fail, max_len=64, allow_blank=True)
    mode = item["execution_mode"]
    if type(mode) is not str or mode not in p68.MODES:
        _fail(f"bad_mode:{mode!r}")
    ref = item.get("approval_ref")
    if ref is not None:
        text(ref, "approval_ref", fail=_fail, max_len=128)
    return {"id": item_id, "text": body, "domain_terms": list(terms),
            "execution_mode": mode, "approval_ref": ref}


def _validate_content(ledger):
    for entry in ledger:
        record = entry["record"]
        kind = record.get("kind")
        if kind == "decision":
            if set(record) != _DECISION_KEYS:
                _fail(f"ledger entry {entry['seq']} has an unexpected record shape")
            ident(record["item_id"], "item_id", fail=_fail)
            instant(record["at"], "at", fail=_fail)
            if record["verdict"] not in VERDICTS:
                _fail(f"ledger entry {entry['seq']} has an unknown verdict")
            for flag in ("approval_checked", "approval_accepted"):
                if type(record[flag]) is not bool:
                    _fail(f"ledger entry {entry['seq']} has invalid content")
        elif kind == "effect":
            if set(record) != _EFFECT_KEYS:
                _fail(f"ledger entry {entry['seq']} has an unexpected record shape")
            ident(record["item_id"], "item_id", fail=_fail)
            instant(record["at"], "at", fail=_fail)
            if record["outcome"] not in ("completed", "failed"):
                _fail(f"ledger entry {entry['seq']} has an unknown outcome")
            if record["error_type"] is not None and type(record["error_type"]) is not str:
                _fail(f"ledger entry {entry['seq']} has invalid content")
        else:
            _fail(f"ledger entry {entry['seq']} has an unknown record kind")
    return ledger


def check_ledger(ledger):
    """Verify chain, per-kind content and field validity. Returns the ledger."""
    _ledger.check_chain(ledger)
    return _validate_content(ledger)


def dumps(ledger):
    check_ledger(ledger)
    return _ledger.dumps(ledger)


def loads(text_):
    return _ledger.loads(text_, validate_content=_validate_content)


def admit(item, *, now, ledger=None, approval_check=None):
    """Evaluate one work item. Returns (ledger, decision record).

    Never raises for a prohibited or unapproved item: refusal is a verdict on
    the record. Raises ValueError('BIOGATE:<code>') for malformed input.
    approval_check, when supplied, is called exactly once with the item's
    approval_ref and must return a bool.
    """
    checked = _check_item(item)
    if ledger is None:
        ledger = []
    check_ledger(ledger)
    at = iso(instant(now, "now", fail=_fail))

    screened = p69.screen({"id": checked["id"], "kind": "instruction", "text": checked["text"]})
    p69_verdict = screened["verdict"]
    p69_category = screened["category"]

    if p69_verdict != "clear":
        verdict = "refused:prohibited_bio"
        p68_verdict = None
        approval_checked = False
        approval_accepted = False
    else:
        p68_record = p68.classify({"id": checked["id"], "domain_terms": checked["domain_terms"],
                                   "execution_mode": checked["execution_mode"],
                                   "approval_ref": checked["approval_ref"]})
        p68_verdict = p68_record["verdict"]
        approval_checked = False
        approval_accepted = False
        if p68_verdict in ("not_bio_scoped", "allowed_in_silico"):
            verdict = "admitted:" + ("not_bio_scoped" if p68_verdict == "not_bio_scoped" else "in_silico")
        elif p68_verdict == "refused_physical_without_review":
            verdict = "refused:physical_without_review"
        else:  # flagged_physical_with_review_ref
            approval_checked = True
            if approval_check is None:
                verdict = "refused:physical_approval_unverifiable"
            else:
                approval_accepted = bool(approval_check(checked["approval_ref"]))
                verdict = ("admitted:physical_with_validated_approval" if approval_accepted
                           else "refused:physical_approval_rejected")

    record = {"kind": "decision", "item_id": checked["id"], "at": at, "verdict": verdict,
              "p68_verdict": p68_verdict, "p69_verdict": p69_verdict, "p69_category": p69_category,
              "approval_checked": approval_checked, "approval_accepted": approval_accepted}
    return _ledger.append(ledger, record), record


def run_guarded(effect, item, *, now, ledger=None, approval_check=None):
    """The enforcement point: run effect(item) only after admission.

    Raises GuardrailRefusal when the item is refused - the effect is never
    called. On admission the effect runs and its outcome (completed/failed)
    is ledgered. Returns (ledger, effect result).
    """
    if not callable(effect):
        _fail("bad_type:effect")
    ledger, decision = admit(item, now=now, ledger=ledger, approval_check=approval_check)
    verdict = decision["verdict"]
    if not verdict.startswith("admitted:"):
        raise GuardrailRefusal(
            f"{PREFIX}:{verdict}",
            f"work item {decision['item_id']!r} refused by the bio gate ({verdict})",
            details={"item_id": decision["item_id"], "verdict": verdict,
                     "p68_verdict": decision["p68_verdict"],
                     "p69_verdict": decision["p69_verdict"],
                     "p69_category": decision["p69_category"]},
            ledger=ledger)
    at = iso(instant(now, "now", fail=_fail))
    try:
        result = effect(item)
    except Exception as exc:
        ledger = _ledger.append(ledger, {"kind": "effect", "item_id": decision["item_id"],
                                         "at": at, "outcome": "failed",
                                         "error_type": type(exc).__name__})
        raise
    ledger = _ledger.append(ledger, {"kind": "effect", "item_id": decision["item_id"],
                                     "at": at, "outcome": "completed", "error_type": None})
    return ledger, result


__all__ = ["VERDICTS", "LIMITS", "admit", "run_guarded", "check_ledger", "dumps", "loads"]
