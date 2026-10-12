"""Owner-account identity gate (instinct-doc group 139, line 1).

Enforced runtime check over every external-service call: call() admits a
service call only when the (service, account_identity) pair carries a binding
that is registered, verified and not revoked on the gate's hash-chained
ledger. A call under any other identity - including an unregistered account,
an agent-owned account, or a revoked binding - is a GuardrailRefusal and the
effect is never invoked. Every admission and refusal is ledgered.

Verification is caller-attested: the gate records WHO verified the binding,
when, and under what evidence reference, and enforces that only currently
verified owner accounts are usable. It cannot authenticate the account itself
- wire the verifier hook to the integration acceptance surface
(app.integrations.acceptance) for live probes. Pure stdlib, no I/O, no clock.
"""
from __future__ import annotations

from . import ledger as _ledger
from ._fields import (hook_accepted, ident, instant, iso, make_fail,
                      payload_sha256, text)
from .errors import GuardrailRefusal, attach_ledger

PREFIX = "ACCTGATE"
_fail = make_fail(PREFIX)

MAX_SERVICE = 64
MAX_IDENTITY = 256
MAX_REF = 256
VERDICTS = ("admitted", "refused:unregistered", "refused:registered", "refused:revoked")
LIMITS = (
    "Verification is caller-attested: the gate enforces that only bindings marked verified by a recorded verifier are usable; it cannot authenticate the account.",
    "The gate binds (service, account_identity) pairs only; permissions inside the account are out of scope.",
    "The ledger is tamper-evident, not tamper-proof; safe storage of the serialized ledger is the caller's job.",
)

_REGISTER_KEYS = {"kind", "service", "account_identity", "registered_by", "at", "evidence_ref"}
_VERIFY_KEYS = {"kind", "service", "account_identity", "verified_by", "at", "evidence_ref",
                "authority_ref", "authority_validated"}
_REVOKE_KEYS = {"kind", "service", "account_identity", "revoked_by", "at", "rationale"}
_CALL_KEYS = {"kind", "call_id", "service", "account_identity", "at", "verdict", "failure"}


def _pair_fields(record, seq, keys, actor_field):
    if set(record) != keys:
        _fail(f"ledger entry {seq} has an unexpected record shape")
    text(record["service"], "service", fail=_fail, max_len=MAX_SERVICE)
    text(record["account_identity"], "account_identity", fail=_fail, max_len=MAX_IDENTITY)
    text(record[actor_field], actor_field, fail=_fail)
    instant(record["at"], "at", fail=_fail)


def _validate_content(ledger):
    bindings = {}
    for entry in ledger:
        seq = entry["seq"]
        record = entry["record"]
        kind = record.get("kind")
        key = (record.get("service"), record.get("account_identity"))
        if kind == "binding_registered":
            _pair_fields(record, seq, _REGISTER_KEYS, "registered_by")
            text(record["evidence_ref"], "evidence_ref", fail=_fail, max_len=MAX_REF, allow_blank=True)
            if key in bindings and bindings[key] != "revoked":
                _fail(f"ledger entry {seq} re-registers binding {key!r}")
            bindings[key] = "registered"
        elif kind == "binding_verified":
            _pair_fields(record, seq, _VERIFY_KEYS, "verified_by")
            text(record["evidence_ref"], "evidence_ref", fail=_fail, max_len=MAX_REF, allow_blank=True)
            if record["authority_ref"] is not None:
                text(record["authority_ref"], "authority_ref", fail=_fail, max_len=MAX_REF)
            if type(record["authority_validated"]) is not bool:
                _fail(f"ledger entry {seq} has invalid content")
            if record["authority_validated"] and record["authority_ref"] is None:
                _fail(f"ledger entry {seq} claims validation without a reference")
            if bindings.get(key) not in ("registered", "verified"):
                _fail(f"ledger entry {seq} verifies binding {key!r} out of order")
            bindings[key] = "verified"
        elif kind == "binding_revoked":
            _pair_fields(record, seq, _REVOKE_KEYS, "revoked_by")
            text(record["rationale"], "rationale", fail=_fail, max_len=256)
            if bindings.get(key) not in ("registered", "verified"):
                _fail(f"ledger entry {seq} revokes binding {key!r} out of order")
            bindings[key] = "revoked"
        elif kind == "service_call":
            if set(record) != _CALL_KEYS:
                _fail(f"ledger entry {seq} has an unexpected record shape")
            text(record["call_id"], "call_id", fail=_fail, max_len=64)
            text(record["service"], "service", fail=_fail, max_len=MAX_SERVICE)
            text(record["account_identity"], "account_identity", fail=_fail, max_len=MAX_IDENTITY)
            instant(record["at"], "at", fail=_fail)
            if record["verdict"] not in VERDICTS:
                _fail(f"ledger entry {seq} has an unknown verdict")
            if record["failure"] is not None and type(record["failure"]) is not str:
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


def _state(ledger, service, account_identity):
    state = None
    for entry in ledger:
        record = entry["record"]
        if record.get("service") != service or record.get("account_identity") != account_identity:
            continue
        if record["kind"] == "binding_registered":
            state = "registered"
        elif record["kind"] == "binding_verified" and state in ("registered", "verified"):
            state = "verified"
        elif record["kind"] == "binding_revoked" and state in ("registered", "verified"):
            state = "revoked"
    return state


def register_binding(ledger, service, account_identity, *, registered_by, now, evidence_ref=""):
    """Register a (service, account_identity) binding. Returns the extended ledger."""
    check_ledger(ledger)
    service = text(service, "service", fail=_fail, max_len=MAX_SERVICE)
    account_identity = text(account_identity, "account_identity", fail=_fail, max_len=MAX_IDENTITY)
    registered_by = text(registered_by, "registered_by", fail=_fail)
    evidence_ref = text(evidence_ref, "evidence_ref", fail=_fail, max_len=MAX_REF, allow_blank=True)
    at = iso(instant(now, "now", fail=_fail))
    state = _state(ledger, service, account_identity)
    if state in ("registered", "verified"):
        _fail(f"binding ({service!r}, {account_identity!r}) is already {state}")
    record = {"kind": "binding_registered", "service": service, "account_identity": account_identity,
              "registered_by": registered_by, "at": at, "evidence_ref": evidence_ref}
    return _ledger.append(ledger, record)


def verify_binding(ledger, service, account_identity, *, verified_by, now, evidence_ref="",
                   authority_ref=None, authority_check=None):
    """Mark a registered binding verified. Returns the extended ledger.

    verified_by is a caller-supplied DECLARATION, not authentication. To bind
    the verification to the approval store, pass authority_ref (e.g. a Module 0
    approval id or a review-gate permit id): the caller-bound authority_check
    hook must then confirm it, and the gate fails closed when no hook is wired.
    """
    check_ledger(ledger)
    service = text(service, "service", fail=_fail, max_len=MAX_SERVICE)
    account_identity = text(account_identity, "account_identity", fail=_fail, max_len=MAX_IDENTITY)
    verified_by = text(verified_by, "verified_by", fail=_fail)
    evidence_ref = text(evidence_ref, "evidence_ref", fail=_fail, max_len=MAX_REF, allow_blank=True)
    at = iso(instant(now, "now", fail=_fail))
    if _state(ledger, service, account_identity) not in ("registered", "verified"):
        _fail(f"binding ({service!r}, {account_identity!r}) is not registered")
    binding_digest = payload_sha256({"service": service, "account_identity": account_identity})
    validated = False
    if authority_ref is None and authority_check is not None:
        _fail("authority_required:authority_ref")
    if authority_ref is not None:
        authority_ref = text(authority_ref, "authority_ref", fail=_fail, max_len=MAX_REF)
        if authority_check is None:
            _fail("authority_unverifiable:authority_ref")
        # the hook receives (authority_ref, binding digest) so the approval
        # binds to this exact (service, account_identity) pair
        validated = hook_accepted(authority_check(authority_ref, binding_digest))
        if not validated:
            _fail("authority_rejected:authority_ref")
    record = {"kind": "binding_verified", "service": service, "account_identity": account_identity,
              "verified_by": verified_by, "at": at, "evidence_ref": evidence_ref,
              "authority_ref": authority_ref, "authority_validated": validated}
    return _ledger.append(ledger, record)


def revoke_binding(ledger, service, account_identity, *, revoked_by, rationale, now):
    """Revoke a binding. Revocation is final for the current registration."""
    check_ledger(ledger)
    service = text(service, "service", fail=_fail, max_len=MAX_SERVICE)
    account_identity = text(account_identity, "account_identity", fail=_fail, max_len=MAX_IDENTITY)
    revoked_by = text(revoked_by, "revoked_by", fail=_fail)
    rationale = text(rationale, "rationale", fail=_fail, max_len=256)
    at = iso(instant(now, "now", fail=_fail))
    if _state(ledger, service, account_identity) not in ("registered", "verified"):
        _fail(f"binding ({service!r}, {account_identity!r}) is not live")
    record = {"kind": "binding_revoked", "service": service, "account_identity": account_identity,
              "revoked_by": revoked_by, "at": at, "rationale": rationale}
    return _ledger.append(ledger, record)


def call(ledger, call_id, service, account_identity, *, effect, now, on_commit=None):
    """The enforcement point: run effect() only under a verified binding.

    Returns (ledger, effect result). Raises GuardrailRefusal - and ledgers the
    refused call - when the (service, account_identity) pair is unregistered,
    registered-but-unverified, or revoked.
    """
    if not callable(effect):
        _fail("bad_type:effect")
    if on_commit is not None and not callable(on_commit):
        _fail("bad_type:on_commit")
    check_ledger(ledger)
    call_id = text(call_id, "call_id", fail=_fail, max_len=64)
    service = text(service, "service", fail=_fail, max_len=MAX_SERVICE)
    account_identity = text(account_identity, "account_identity", fail=_fail, max_len=MAX_IDENTITY)
    at = iso(instant(now, "now", fail=_fail))
    state = _state(ledger, service, account_identity)
    verdict = "admitted" if state == "verified" else f"refused:{state or 'unregistered'}"
    record = {"kind": "service_call", "call_id": call_id, "service": service,
              "account_identity": account_identity, "at": at, "verdict": verdict, "failure": None}
    ledger = _ledger.append(ledger, record)
    if on_commit is not None:
        on_commit(ledger)  # write-ahead: the call record is committed before any effect
    if verdict != "admitted":
        raise GuardrailRefusal(
            f"{PREFIX}:{verdict}",
            f"call {call_id!r} to {service!r} as {account_identity!r} refused: binding is {state or 'unregistered'}",
            details={"call_id": call_id, "service": service,
                     "account_identity": account_identity, "binding_state": state or "unregistered"},
            ledger=ledger)
    try:
        result = effect()
    except BaseException as exc:
        # Ambiguous outcome: the admitted call AND its failure are committed
        # and the ledger rides the exception so the caller can persist it.
        ledger = _ledger.append(ledger, {"kind": "service_call", "call_id": call_id,
                                         "service": service, "account_identity": account_identity,
                                         "at": at, "verdict": "admitted",
                                         "failure": type(exc).__name__})
        if on_commit is not None:
            on_commit(ledger)
        raise attach_ledger(exc, ledger)
    return ledger, result


def binding_state(ledger, service, account_identity):
    """Current state for one binding: None, registered, verified or revoked."""
    check_ledger(ledger)
    return _state(ledger, service, account_identity)


__all__ = ["VERDICTS", "LIMITS", "register_binding", "verify_binding", "revoke_binding",
           "call", "binding_state", "check_ledger", "dumps", "loads"]
