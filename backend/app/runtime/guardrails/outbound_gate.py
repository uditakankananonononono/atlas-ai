"""Outbound action dispatch gate (instinct-doc group 136, line 59).

Enforced runtime check over every outbound platform action BEFORE it is
performed: platform terms, automation consent, rate limits, subject consent
and purpose-limited data categories. Composes the landed P70 preflight with
two enforcement additions:

1. The effect runs only through dispatch(): a denied preflight verdict is a
   GuardrailRefusal and the effect is never called; a needs_review verdict
   requires a caller-bound review_check hook (wire it to the review gate /
   Module 0) and fails closed without one.
2. Rate-limit history comes from the gate's own ledger: dispatch() rebuilds
   recent_actions from its prior "dispatched" records for the same platform
   and merges them under the caller's declarations, so an action stream that
   already passed the gate cannot redeclare its own history to slip under a
   declared limit. Caller-supplied recent_actions still apply on top.

The P70 layer keeps its documented scope: it checks caller-declared rules
only, reads no real terms of service and is not legal compliance; missing
declarations deny (fail closed). Every dispatch decision is ledgered with the
full check list. Pure stdlib, no I/O, no network, no clock.
"""
from __future__ import annotations

from app.modules.instinct_doc import platform_conduct_p70 as p70

from . import ledger as _ledger
from ._fields import ident, instant, iso, make_fail, text
from .errors import GuardrailRefusal

PREFIX = "OUTGATE"
_fail = make_fail(PREFIX)

VERDICTS = ("dispatched", "dispatched:after_review", "refused:denied", "refused:review_required")
LIMITS = (
    "Checks caller-declared platform rules only; the gate reads no real terms of service and is not proof of legal compliance.",
    "review_check is a caller-bound hook: the gate records its boolean answer and never authenticates a review by itself.",
    "Ledger-derived rate history covers actions that went through this gate only; actions performed outside the gate are invisible to it.",
    "The ledger is tamper-evident, not tamper-proof; safe storage of the serialized ledger is the caller's job.",
)

_DECISION_KEYS = {"kind", "action_id", "platform", "action_kind", "at", "action_at", "verdict",
                  "preflight_verdict", "failed_checks", "review_checked", "review_accepted"}


def _validate_content(ledger):
    for entry in ledger:
        record = entry["record"]
        if record.get("kind") != "decision":
            _fail(f"ledger entry {entry['seq']} has an unknown record kind")
        if set(record) != _DECISION_KEYS:
            _fail(f"ledger entry {entry['seq']} has an unexpected record shape")
        ident(record["action_id"], "action_id", fail=_fail)
        text(record["platform"], "platform", fail=_fail, max_len=64)
        text(record["action_kind"], "action_kind", fail=_fail, max_len=64)
        instant(record["at"], "at", fail=_fail)
        if record["verdict"] not in VERDICTS or record["preflight_verdict"] not in ("allow", "deny", "needs_review"):
            _fail(f"ledger entry {entry['seq']} has an unknown verdict")
        if type(record["failed_checks"]) is not list or any(type(c) is not str for c in record["failed_checks"]):
            _fail(f"ledger entry {entry['seq']} has invalid content")
        for flag in ("review_checked", "review_accepted"):
            if type(record[flag]) is not bool:
                _fail(f"ledger entry {entry['seq']} has invalid content")
    return ledger


def check_ledger(ledger):
    _ledger.check_chain(ledger)
    return _validate_content(ledger)


def dumps(ledger):
    check_ledger(ledger)
    return _ledger.dumps(ledger)


def loads(text_):
    return _ledger.loads(text_, validate_content=_validate_content)


def history(ledger, platform):
    """Reconstruct P70 recent_actions for one platform from dispatched records.

    Each dispatched decision contributes its action's (kind, action_at, count=1)
    using the action's own declared timestamp, so history and future actions
    share one time domain. Refused actions contribute nothing - they never
    happened.
    """
    check_ledger(ledger)
    text(platform, "platform", fail=_fail, max_len=64)
    out = []
    for entry in ledger:
        record = entry["record"]
        if record["platform"] == platform and record["verdict"] in ("dispatched", "dispatched:after_review"):
            out.append({"platform": record["platform"], "kind": record["action_kind"],
                        "at": record["action_at"], "count": 1})
    return out


def _check_action(action):
    if type(action) is not dict:
        _fail("bad_type:action")
    ident(action.get("id"), "id", fail=_fail)
    # P70 owns the deep validation of the remaining fields.
    return action


def dispatch(action, declarations, *, effect, now, ledger=None, review_check=None):
    """The enforcement point: run effect(action) only after the gate admits it.

    action: a P70 action dict plus a non-empty "id" field used for ledgering.
    declarations: the P70 declarations dict; the gate merges its own
    ledger-derived rate history under declarations["recent_actions"].
    Returns (ledger, effect result). Raises GuardrailRefusal when the action
    is denied or needs a review the hook does not confirm.
    """
    if not callable(effect):
        _fail("bad_type:effect")
    _check_action(action)
    if type(declarations) is not dict:
        _fail("bad_type:declarations")
    if ledger is None:
        ledger = []
    check_ledger(ledger)
    at = iso(instant(now, "now", fail=_fail))

    merged = dict(declarations)
    merged["recent_actions"] = list(declarations.get("recent_actions", [])) + history(ledger, action["platform"])
    preflight = p70.preflight({k: v for k, v in action.items() if k != "id"}, merged)
    failed = [c["check"] for c in preflight["checks"] if not c["passed"]]

    review_checked = False
    review_accepted = False
    if preflight["verdict"] == "deny":
        verdict = "refused:denied"
    elif preflight["verdict"] == "needs_review":
        review_checked = True
        if review_check is None:
            verdict = "refused:review_required"
        else:
            review_accepted = bool(review_check(action))
            verdict = "dispatched:after_review" if review_accepted else "refused:review_required"
    else:
        verdict = "dispatched"

    record = {"kind": "decision", "action_id": action["id"], "platform": action["platform"],
              "action_kind": action["kind"], "at": at, "action_at": action["at"], "verdict": verdict,
              "preflight_verdict": preflight["verdict"], "failed_checks": failed,
              "review_checked": review_checked, "review_accepted": review_accepted}
    ledger = _ledger.append(ledger, record)
    if verdict.startswith("refused:"):
        raise GuardrailRefusal(
            f"{PREFIX}:{verdict}",
            f"outbound action {action['id']!r} refused ({verdict}; failed checks: {failed or ['review']})",
            details={"action_id": action["id"], "verdict": verdict,
                     "preflight_verdict": preflight["verdict"], "failed_checks": failed},
            ledger=ledger)
    return ledger, effect(action)


__all__ = ["VERDICTS", "LIMITS", "dispatch", "history", "check_ledger", "dumps", "loads"]
