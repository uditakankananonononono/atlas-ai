"""Effect-category review gate (instinct-doc group 137, lines 60-61).

Enforced runtime check: no contact, application, submission or account action
executes without either (a) a single-use execution permit issued from an
approved, hash-exact, validity-windowed human review of that exact action, or
(b) a live standing preauthorization whose scope covers the action's exact
category + payload hash. execute() is the choke point: without a permit or
preauthorization it raises GuardrailRefusal and the effect is never called.

Generalizes the landed m02 reviewed_execution draft gate to the four effect
categories. Same construction: hash-chained append-only ledger, one final
decision per review, permits recomputed from the presented action (a tampered
payload cannot ride on a stale hash), single-use spend recorded on the chain.
Reviewer identity is a caller-supplied label, not authentication; the module
executes nothing by itself and a permit authorizes nothing outside execute().
Pure stdlib, no I/O, no clock.
"""
from __future__ import annotations

from datetime import timedelta

from . import ledger as _ledger
from ._fields import (hook_accepted, ident, instant, iso, make_fail,
                      payload_sha256, sha256_hex, text)
from .errors import GuardrailRefusal, attach_ledger

PREFIX = "REVGATE"
_fail = make_fail(PREFIX)

CATEGORIES = ("contact", "application", "submission", "account")
DECISIONS = ("approved", "rejected")
MAX_SUMMARY = 512
MAX_VALID_HOURS = 720
MAX_PREAUTH_HOURS = 8760  # one year

_OPEN_KEYS = {"kind", "review_id", "action_id", "category", "payload_sha256",
              "opened_by", "opened_at", "valid_hours"}
_DECISION_KEYS = {"kind", "review_id", "decision", "reviewer", "rationale", "decided_at",
                  "authority_ref", "authority_validated"}
_PERMIT_KEYS = {"kind", "review_id", "permit_id", "issued_at", "action_id", "category", "payload_sha256"}
_SPEND_KEYS = {"kind", "permit_id", "spent_at", "action_id"}
_PREAUTH_KEYS = {"kind", "preauth_id", "category", "payload_sha256", "granted_by",
                 "granted_at", "expires_at", "scope_note",
                 "authority_ref", "authority_validated"}
_REVOKE_KEYS = {"kind", "preauth_id", "revoked_by", "revoked_at", "rationale"}
_PREAUTH_USE_KEYS = {"kind", "preauth_id", "used_at", "action_id"}
_REFUSAL_KEYS = {"kind", "action_id", "at", "reason_code", "permit_id"}
REFUSAL_REASONS = ("review_required", "unknown_permit", "permit_invalid")

LIMITS = (
    "Reviewer and grantor identities are caller-supplied DECLARATIONS, not authentication; bind decisions and grants to the approval store with authority_ref + a caller-bound authority_check hook, which fails closed when absent.",
    "Records live in memory until the caller persists them (on_commit write-ahead or dumps); the gate itself holds no durable store.",
    "A permit or preauthorization covers exactly one category + payload hash; it authorizes nothing outside execute() and no external system is notified.",
    "Preauthorization scope is exact-hash only: a changed payload needs a new grant; there are no wildcard scopes.",
    "Refused executions are ledgered as evidence (execution_refused records) before the refusal is raised.",
    "The ledger is tamper-evident, not tamper-proof; safe storage of the serialized ledger is the caller's job.",
)


def _check_action(action):
    if type(action) is not dict:
        _fail("bad_type:action")
    if set(action) != {"action_id", "category", "summary", "payload"}:
        _fail("unknown_fields:action")
    action_id = ident(action["action_id"], "action_id", fail=_fail)
    category = action["category"]
    if category not in CATEGORIES:
        _fail(f"bad_category:{category!r}")
    text(action["summary"], "summary", fail=_fail, max_len=MAX_SUMMARY)
    payload = action["payload"]
    if type(payload) is not dict:
        _fail("bad_type:payload")
    try:
        digest = payload_sha256(payload)
    except (TypeError, ValueError):
        _fail("bad_payload:payload")
    return {"action_id": action_id, "category": category,
            "summary": action["summary"], "payload_sha256": digest}


def _authority(authority_ref, authority_check):
    """Validate an optional approval-store reference through the caller hook.

    Returns (ref, validated). A supplied ref with no hook fails closed; a
    hook rejection fails closed. No ref: the actor label stays a declaration.
    """
    if authority_ref is None:
        return None, False
    text(authority_ref, "authority_ref", fail=_fail, max_len=256)
    if authority_check is None:
        _fail("authority_unverifiable:authority_ref")
    if not hook_accepted(authority_check(authority_ref)):
        _fail("authority_rejected:authority_ref")
    return authority_ref, True


def _hours(value, name, cap):
    if type(value) not in (int, float) or type(value) is bool:
        _fail(f"bad_type:{name}")
    if not 0 < value <= cap:
        _fail(f"bad_range:{name}")
    return value


def _check_authority_fields(record, seq):
    if record["authority_ref"] is not None:
        text(record["authority_ref"], "authority_ref", fail=_fail, max_len=256)
    if type(record["authority_validated"]) is not bool:
        _fail(f"ledger entry {seq} has invalid content")
    if record["authority_validated"] and record["authority_ref"] is None:
        _fail(f"ledger entry {seq} claims validation without a reference")


def _validate_content(ledger):
    reviews = {}
    permits = {}
    preauths = {}
    for entry in ledger:
        seq = entry["seq"]
        record = entry["record"]
        kind = record.get("kind")
        if kind == "review_opened":
            if set(record) != _OPEN_KEYS:
                _fail(f"ledger entry {seq} has an unexpected record shape")
            ident(record["review_id"], "review_id", fail=_fail)
            ident(record["action_id"], "action_id", fail=_fail)
            if record["category"] not in CATEGORIES:
                _fail(f"ledger entry {seq} has an unknown category")
            sha256_hex(record["payload_sha256"], "payload_sha256", fail=_fail)
            text(record["opened_by"], "opened_by", fail=_fail)
            instant(record["opened_at"], "opened_at", fail=_fail)
            _hours(record["valid_hours"], "valid_hours", MAX_VALID_HOURS)
            if record["review_id"] in reviews:
                _fail(f"ledger entry {seq} reopens review {record['review_id']!r}")
            reviews[record["review_id"]] = "open"
        elif kind == "review_decision":
            if set(record) != _DECISION_KEYS:
                _fail(f"ledger entry {seq} has an unexpected record shape")
            ident(record["review_id"], "review_id", fail=_fail)
            if record["decision"] not in DECISIONS:
                _fail(f"ledger entry {seq} has an unknown decision")
            text(record["reviewer"], "reviewer", fail=_fail)
            text(record["rationale"], "rationale", fail=_fail, max_len=MAX_SUMMARY)
            instant(record["decided_at"], "decided_at", fail=_fail)
            _check_authority_fields(record, seq)
            if reviews.get(record["review_id"]) != "open":
                _fail(f"ledger entry {seq} decides review {record['review_id']!r} out of order")
            reviews[record["review_id"]] = record["decision"]
        elif kind == "execution_permit":
            if set(record) != _PERMIT_KEYS:
                _fail(f"ledger entry {seq} has an unexpected record shape")
            ident(record["review_id"], "review_id", fail=_fail)
            ident(record["permit_id"], "permit_id", fail=_fail)
            ident(record["action_id"], "action_id", fail=_fail)
            if record["category"] not in CATEGORIES:
                _fail(f"ledger entry {seq} has an unknown category")
            sha256_hex(record["payload_sha256"], "payload_sha256", fail=_fail)
            instant(record["issued_at"], "issued_at", fail=_fail)
            if reviews.get(record["review_id"]) != "approved":
                _fail(f"ledger entry {seq} permits review {record['review_id']!r} out of order")
            reviews[record["review_id"]] = "permitted"
            if record["permit_id"] in permits:
                _fail(f"ledger entry {seq} reissues permit {record['permit_id']!r}")
            permits[record["permit_id"]] = "issued"
        elif kind == "permit_spent":
            if set(record) != _SPEND_KEYS:
                _fail(f"ledger entry {seq} has an unexpected record shape")
            ident(record["permit_id"], "permit_id", fail=_fail)
            ident(record["action_id"], "action_id", fail=_fail)
            instant(record["spent_at"], "spent_at", fail=_fail)
            if permits.get(record["permit_id"]) != "issued":
                _fail(f"ledger entry {seq} spends permit {record['permit_id']!r} out of order")
            permits[record["permit_id"]] = "spent"
        elif kind == "preauthorization":
            if set(record) != _PREAUTH_KEYS:
                _fail(f"ledger entry {seq} has an unexpected record shape")
            ident(record["preauth_id"], "preauth_id", fail=_fail)
            if record["category"] not in CATEGORIES:
                _fail(f"ledger entry {seq} has an unknown category")
            sha256_hex(record["payload_sha256"], "payload_sha256", fail=_fail)
            text(record["granted_by"], "granted_by", fail=_fail)
            granted = instant(record["granted_at"], "granted_at", fail=_fail)
            expires = instant(record["expires_at"], "expires_at", fail=_fail)
            if not expires > granted:
                _fail(f"ledger entry {seq} expiry is not after the grant")
            if expires - granted > timedelta(hours=MAX_PREAUTH_HOURS):
                _fail(f"ledger entry {seq} exceeds the preauthorization horizon")
            text(record["scope_note"], "scope_note", fail=_fail, max_len=MAX_SUMMARY)
            _check_authority_fields(record, seq)
            if record["preauth_id"] in preauths:
                _fail(f"ledger entry {seq} regrants preauthorization {record['preauth_id']!r}")
            preauths[record["preauth_id"]] = "live"
        elif kind == "preauthorization_revoked":
            if set(record) != _REVOKE_KEYS:
                _fail(f"ledger entry {seq} has an unexpected record shape")
            ident(record["preauth_id"], "preauth_id", fail=_fail)
            text(record["revoked_by"], "revoked_by", fail=_fail)
            instant(record["revoked_at"], "revoked_at", fail=_fail)
            text(record["rationale"], "rationale", fail=_fail, max_len=MAX_SUMMARY)
            if preauths.get(record["preauth_id"]) != "live":
                _fail(f"ledger entry {seq} revokes preauthorization {record['preauth_id']!r} out of order")
            preauths[record["preauth_id"]] = "revoked"
        elif kind == "execution_refused":
            if set(record) != _REFUSAL_KEYS:
                _fail(f"ledger entry {seq} has an unexpected record shape")
            ident(record["action_id"], "action_id", fail=_fail)
            instant(record["at"], "at", fail=_fail)
            if record["reason_code"] not in REFUSAL_REASONS:
                _fail(f"ledger entry {seq} has an unknown reason code")
            if record["permit_id"] is not None:
                ident(record["permit_id"], "permit_id", fail=_fail)
        elif kind == "preauthorization_used":
            if set(record) != _PREAUTH_USE_KEYS:
                _fail(f"ledger entry {seq} has an unexpected record shape")
            ident(record["preauth_id"], "preauth_id", fail=_fail)
            ident(record["action_id"], "action_id", fail=_fail)
            instant(record["used_at"], "used_at", fail=_fail)
            if record["preauth_id"] not in preauths:
                _fail(f"ledger entry {seq} uses unknown preauthorization {record['preauth_id']!r}")
        else:
            _fail(f"ledger entry {seq} has an unknown record kind")
    return ledger


def check_ledger(ledger):
    """Verify chain, per-kind content and record order. Returns the ledger."""
    _ledger.check_chain(ledger)
    return _validate_content(ledger)


def dumps(ledger):
    check_ledger(ledger)
    return _ledger.dumps(ledger)


def loads(text_):
    return _ledger.loads(text_, validate_content=_validate_content)


def _find_review(ledger, review_id):
    opened = decision = permit = None
    for entry in ledger:
        record = entry["record"]
        if record.get("review_id") != review_id:
            continue
        if record["kind"] == "review_opened":
            opened = record
        elif record["kind"] == "review_decision":
            decision = record
        elif record["kind"] == "execution_permit":
            permit = record
    return opened, decision, permit


def _find_permit(ledger, permit_id):
    permit = None
    spent = False
    for entry in ledger:
        record = entry["record"]
        if record["kind"] == "execution_permit" and record["permit_id"] == permit_id:
            permit = record
        elif record["kind"] == "permit_spent" and record["permit_id"] == permit_id:
            spent = True
    return permit, spent


def _live_preauth(ledger, category, digest, at):
    """The live preauthorization covering (category, digest) at instant `at`, or None."""
    grants = {}
    for entry in ledger:
        record = entry["record"]
        if record["kind"] == "preauthorization":
            grants[record["preauth_id"]] = record
        elif record["kind"] == "preauthorization_revoked":
            grants.pop(record["preauth_id"], None)
    for grant in grants.values():
        if grant["category"] != category or grant["payload_sha256"] != digest:
            continue
        granted = instant(grant["granted_at"], "granted_at", fail=_fail)
        expires = instant(grant["expires_at"], "expires_at", fail=_fail)
        if granted <= at < expires:
            return grant
    return None


def open_review(ledger, action, *, review_id, reviewer, now, valid_hours=24):
    """Open a human review for one exact action. Returns the extended ledger."""
    check_ledger(ledger)
    checked = _check_action(action)
    rid = ident(review_id, "review_id", fail=_fail)
    reviewer = text(reviewer, "reviewer", fail=_fail)
    opened_at = instant(now, "now", fail=_fail)
    hours = _hours(valid_hours, "valid_hours", MAX_VALID_HOURS)
    if _find_review(ledger, rid)[0] is not None:
        _fail(f"review {rid!r} is already open")
    record = {"kind": "review_opened", "review_id": rid, "action_id": checked["action_id"],
              "category": checked["category"], "payload_sha256": checked["payload_sha256"],
              "opened_by": reviewer, "opened_at": iso(opened_at), "valid_hours": hours}
    return _ledger.append(ledger, record)


def record_decision(ledger, *, review_id, decision, reviewer, rationale, now,
                    authority_ref=None, authority_check=None):
    """Append the human decision for an open review. One decision per review, final.

    reviewer is a caller-supplied DECLARATION, not authentication. To bind the
    decision to the approval store, pass authority_ref (e.g. a Module 0
    approval id); the caller-bound authority_check hook must confirm it and
    the gate fails closed without one."""
    check_ledger(ledger)
    rid = ident(review_id, "review_id", fail=_fail)
    if decision not in DECISIONS:
        _fail("bad_decision:decision")
    reviewer = text(reviewer, "reviewer", fail=_fail)
    rationale = text(rationale, "rationale", fail=_fail, max_len=MAX_SUMMARY)
    decided_at = instant(now, "now", fail=_fail)
    opened, prior_decision, _permit = _find_review(ledger, rid)
    if opened is None:
        _fail(f"review {rid!r} is not open")
    if prior_decision is not None:
        _fail(f"review {rid!r} already has a decision")
    if decided_at < instant(opened["opened_at"], "opened_at", fail=_fail):
        _fail(f"review {rid!r} decision is before it opened")
    ref, validated = _authority(authority_ref, authority_check)
    record = {"kind": "review_decision", "review_id": rid, "decision": decision,
              "reviewer": reviewer, "rationale": rationale, "decided_at": iso(decided_at),
              "authority_ref": ref, "authority_validated": validated}
    return _ledger.append(ledger, record)


def issue_permit(ledger, action, *, review_id, now):
    """Issue the single-use permit for an approved, unexpired, hash-exact review.

    Returns (ledger, permit dict). The permit is a local record that the gate
    was passed; it authorizes nothing by itself.
    """
    check_ledger(ledger)
    checked = _check_action(action)
    rid = ident(review_id, "review_id", fail=_fail)
    issued_at = instant(now, "now", fail=_fail)
    opened, decision, permit = _find_review(ledger, rid)
    if opened is None:
        _fail(f"review {rid!r} is not open")
    if decision is None:
        _fail(f"review {rid!r} has no decision")
    if decision["decision"] != "approved":
        _fail(f"review {rid!r} was rejected")
    if permit is not None:
        _fail(f"review {rid!r} already has an execution permit")
    if (opened["action_id"] != checked["action_id"] or opened["category"] != checked["category"]
            or opened["payload_sha256"] != checked["payload_sha256"]):
        _fail("action does not match the reviewed action")
    if issued_at < instant(decision["decided_at"], "decided_at", fail=_fail):
        _fail(f"review {rid!r} permit is before the decision")
    deadline = instant(opened["opened_at"], "opened_at", fail=_fail) + timedelta(hours=opened["valid_hours"])
    if issued_at > deadline:
        _fail(f"review {rid!r} validity window has expired")
    record = {"kind": "execution_permit", "review_id": rid, "permit_id": f"PERMIT-{rid}",
              "issued_at": iso(issued_at), "action_id": checked["action_id"],
              "category": checked["category"], "payload_sha256": checked["payload_sha256"]}
    new_ledger = _ledger.append(ledger, record)
    return new_ledger, {"permit_id": record["permit_id"], "review_id": rid,
                        "action_id": checked["action_id"], "category": checked["category"],
                        "payload_sha256": checked["payload_sha256"],
                        "approved_by": decision["reviewer"], "decided_at": decision["decided_at"],
                        "issued_at": record["issued_at"], "executes": False}


def grant_preauthorization(ledger, action, *, preauth_id, granted_by, now, valid_hours, scope_note,
                           authority_ref=None, authority_check=None):
    """Record a standing preauthorization for the action's exact category +
    payload hash (the doc's 'unless specifically preauthorized' branch).
    Exact-hash scope only; there are no wildcards. Returns the extended ledger.

    granted_by is a caller-supplied DECLARATION, not authentication. Bind the
    grant to the approval store with authority_ref + authority_check (fails
    closed without a hook)."""
    check_ledger(ledger)
    checked = _check_action(action)
    pid = ident(preauth_id, "preauth_id", fail=_fail)
    granted_by = text(granted_by, "granted_by", fail=_fail)
    scope_note = text(scope_note, "scope_note", fail=_fail, max_len=MAX_SUMMARY)
    granted_at = instant(now, "now", fail=_fail)
    hours = _hours(valid_hours, "valid_hours", MAX_PREAUTH_HOURS)
    for entry in ledger:
        if entry["record"].get("preauth_id") == pid and entry["record"]["kind"] == "preauthorization":
            _fail(f"preauthorization {pid!r} already exists")
    ref, validated = _authority(authority_ref, authority_check)
    record = {"kind": "preauthorization", "preauth_id": pid, "category": checked["category"],
              "payload_sha256": checked["payload_sha256"], "granted_by": granted_by,
              "granted_at": iso(granted_at), "expires_at": iso(granted_at + timedelta(hours=hours)),
              "scope_note": scope_note, "authority_ref": ref, "authority_validated": validated}
    return _ledger.append(ledger, record)


def revoke_preauthorization(ledger, *, preauth_id, revoked_by, rationale, now):
    """Revoke a live preauthorization. Revocation is final."""
    check_ledger(ledger)
    pid = ident(preauth_id, "preauth_id", fail=_fail)
    revoked_by = text(revoked_by, "revoked_by", fail=_fail)
    rationale = text(rationale, "rationale", fail=_fail, max_len=MAX_SUMMARY)
    revoked_at = instant(now, "now", fail=_fail)
    live = None
    for entry in ledger:
        record = entry["record"]
        if record["kind"] == "preauthorization" and record["preauth_id"] == pid:
            live = record
        elif record["kind"] == "preauthorization_revoked" and record["preauth_id"] == pid:
            _fail(f"preauthorization {pid!r} is already revoked")
    if live is None:
        _fail(f"preauthorization {pid!r} is not live")
    record = {"kind": "preauthorization_revoked", "preauth_id": pid, "revoked_by": revoked_by,
              "revoked_at": iso(revoked_at), "rationale": rationale}
    return _ledger.append(ledger, record)


def execute(ledger, action, *, effect, now, permit_id=None, on_commit=None):
    """The enforcement point: run effect(action) for a contact, application,
    submission or account action only under a valid permit or a live
    preauthorization.

    With permit_id: the permit must exist, be unspent, hash-exact for the
    presented action, issued after approval, and inside the review validity
    window; it is then spent on the chain before the effect runs (single-use).
    Without permit_id: a live preauthorization covering the action's exact
    category + payload hash must exist; its use is ledgered. Otherwise
    GuardrailRefusal - the effect is never called.
    Returns (ledger, effect result).
    """
    if not callable(effect):
        _fail("bad_type:effect")
    if on_commit is not None and not callable(on_commit):
        _fail("bad_type:on_commit")
    check_ledger(ledger)
    checked = _check_action(action)
    at = instant(now, "now", fail=_fail)

    def refuse(reason_code, message, details, permit_ref=None):
        refused = _ledger.append(ledger, {"kind": "execution_refused",
                                          "action_id": checked["action_id"], "at": iso(at),
                                          "reason_code": reason_code, "permit_id": permit_ref})
        if on_commit is not None:
            on_commit(refused)
        raise GuardrailRefusal(f"{PREFIX}:{reason_code}", message, details=details, ledger=refused)

    if permit_id is not None:
        pid = ident(permit_id, "permit_id", fail=_fail)
        permit, spent = _find_permit(ledger, pid)
        if permit is None:
            refuse("unknown_permit", f"no execution permit {pid!r}",
                   {"permit_id": pid}, permit_ref=pid)
        opened, decision, _ = _find_review(ledger, permit["review_id"])
        reasons = []
        if spent:
            reasons.append("permit already spent")
        if (permit["action_id"] != checked["action_id"] or permit["category"] != checked["category"]
                or permit["payload_sha256"] != checked["payload_sha256"]):
            reasons.append("action does not match the permit hashes")
        if opened is not None:
            deadline = (instant(opened["opened_at"], "opened_at", fail=_fail)
                        + timedelta(hours=opened["valid_hours"]))
            if at > deadline:
                reasons.append("review validity window has expired")
        if reasons:
            refuse("permit_invalid",
                   f"permit {pid!r} does not cover this action: " + "; ".join(reasons),
                   {"permit_id": pid, "reasons": reasons}, permit_ref=pid)
        ledger = _ledger.append(ledger, {"kind": "permit_spent", "permit_id": pid,
                                         "spent_at": iso(at), "action_id": checked["action_id"]})
        if on_commit is not None:
            on_commit(ledger)  # write-ahead: the spend is committed BEFORE the effect
        try:
            return ledger, effect(action)
        except BaseException as exc:
            # Ambiguous outcome: the permit STAYS SPENT (single-use holds on
            # the committed record); reconciliation is a human review matter,
            # never an automatic un-spend.
            raise attach_ledger(exc, ledger)

    grant = _live_preauth(ledger, checked["category"], checked["payload_sha256"], at)
    if grant is None:
        refuse("review_required",
               f"{checked['category']} action {checked['action_id']!r} requires explicit review or a "
               "live preauthorization; neither covers it",
               {"action_id": checked["action_id"], "category": checked["category"],
                "payload_sha256": checked["payload_sha256"]})
    ledger = _ledger.append(ledger, {"kind": "preauthorization_used",
                                     "preauth_id": grant["preauth_id"], "used_at": iso(at),
                                     "action_id": checked["action_id"]})
    if on_commit is not None:
        on_commit(ledger)  # write-ahead: the use is committed BEFORE the effect
    try:
        return ledger, effect(action)
    except BaseException as exc:
        # Ambiguous outcome: the use record was already committed and also
        # rides the exception via the attachment.
        raise attach_ledger(exc, ledger)


def audit_state(ledger, review_id):
    """Current gate state for one review: open, approved, rejected, permitted."""
    check_ledger(ledger)
    rid = ident(review_id, "review_id", fail=_fail)
    opened, decision, permit = _find_review(ledger, rid)
    if opened is None:
        _fail(f"review {rid!r} is not open")
    if permit is not None:
        return "permitted"
    if decision is not None:
        return decision["decision"]
    return "open"


__all__ = ["CATEGORIES", "DECISIONS", "REFUSAL_REASONS", "LIMITS", "open_review", "record_decision",
           "issue_permit", "grant_preauthorization", "revoke_preauthorization",
           "execute", "audit_state", "check_ledger", "dumps", "loads"]
