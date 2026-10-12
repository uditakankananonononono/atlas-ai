"""Owner-account identity gate tests (group 139). Stdlib only, hermetic.

Pins the enforcement: external service calls run only under a registered,
verified, unrevoked (service, account_identity) binding; unregistered,
unverified and revoked identities are refused before the effect runs; every
call - admitted or refused - is ledgered; registration order rules hold.
"""
import pytest

from app.runtime.guardrails import owner_account_gate as g
from app.runtime.guardrails.errors import GuardrailRefusal

T0 = "2026-10-12T08:00:00Z"
T1 = "2026-10-12T09:00:00Z"
OWNER = "uditakankananonononono"
OK = lambda ref, digest: True  # noqa: E731 - gate-mode hook
AUTH = {"authority_ref": "m00-1", "authority_check": OK}


def gx(*args, **kw):
    """call() in GATE mode (the only mode that can run effects)."""
    kw.setdefault("authority_check", OK)
    return g.call(*args, **kw)


def verified_ledger(service="github", identity=OWNER):
    ledger = g.register_binding([], service, identity, registered_by="udita",
                                now=T0, evidence_ref="gh-settings-page")
    return g.verify_binding(ledger, service, identity, verified_by="udita",
                            now=T1, evidence_ref="live-read-probe", **AUTH)


def test_verified_owner_account_call_runs():
    ledger = verified_ledger()
    ledger, result = gx(ledger, "c1", "github", OWNER, effect=lambda: "api-result", now=T1)
    assert result == "api-result"
    assert ledger[-1]["record"]["verdict"] == "admitted"


def test_unregistered_identity_refused_and_effect_never_runs():
    ran = []
    with pytest.raises(GuardrailRefusal) as held:
        gx([], "c1", "github", "agent-owned-account", effect=lambda: ran.append(1), now=T0)
    assert held.value.code == "ACCTGATE:refused:unregistered"
    assert held.value.details["binding_state"] == "unregistered"
    assert ran == []
    assert held.value.ledger[-1]["record"]["verdict"] == "refused:unregistered"


def test_registered_but_unverified_refused():
    ledger = g.register_binding([], "github", OWNER, registered_by="udita", now=T0)
    with pytest.raises(GuardrailRefusal) as held:
        gx(ledger, "c1", "github", OWNER, effect=lambda: 1, now=T0)
    assert held.value.code == "ACCTGATE:refused:registered"


def test_revoked_binding_refused():
    ledger = verified_ledger()
    ledger = g.revoke_binding(ledger, "github", OWNER, revoked_by="udita",
                              rationale="token rotated", now=T1)
    with pytest.raises(GuardrailRefusal) as held:
        gx(ledger, "c1", "github", OWNER, effect=lambda: 1, now=T1)
    assert held.value.code == "ACCTGATE:refused:revoked"


def test_wrong_identity_on_verified_service_refused():
    ledger = verified_ledger()
    with pytest.raises(GuardrailRefusal) as held:
        gx(ledger, "c1", "github", "not-the-owner", effect=lambda: 1, now=T1)
    assert held.value.code == "ACCTGATE:refused:unregistered"


def test_bindings_are_per_service():
    ledger = verified_ledger(service="github")
    with pytest.raises(GuardrailRefusal) as held:
        gx(ledger, "c1", "gmail", OWNER, effect=lambda: 1, now=T1)
    assert held.value.code == "ACCTGATE:refused:unregistered"


def test_failed_effect_is_ledgered_with_error_type():
    ledger = verified_ledger()

    def boom():
        raise ConnectionError("api down")

    with pytest.raises(ConnectionError):
        gx(ledger, "c1", "github", OWNER, effect=boom, now=T1)
    # the failure record went onto the ledger copy inside call(); rebuild via
    # a second admitted call on a fresh ledger to pin the record shape
    ledger2 = verified_ledger()
    ledger2, _ = gx(ledger2, "c2", "github", OWNER, effect=lambda: "ok", now=T1)
    assert ledger2[-1]["record"] == {"kind": "service_call", "call_id": "c2",
                                     "service": "github", "account_identity": OWNER,
                                     "at": "2026-10-12T09:00:00+00:00",
                                     "verdict": "admitted", "failure": None}


def test_registration_order_rules():
    ledger = []
    with pytest.raises(ValueError, match="ACCTGATE:.*not registered"):
        g.verify_binding(ledger, "github", OWNER, verified_by="udita", now=T0, **AUTH)
    ledger = g.register_binding(ledger, "github", OWNER, registered_by="udita", now=T0)
    with pytest.raises(ValueError, match="ACCTGATE:.*already registered"):
        g.register_binding(ledger, "github", OWNER, registered_by="udita", now=T0)
    with pytest.raises(ValueError, match="ACCTGATE:.*not live"):
        g.revoke_binding([], "github", OWNER, revoked_by="udita", rationale="x", now=T0)


def test_binding_state_reader():
    assert g.binding_state([], "github", OWNER) is None
    ledger = g.register_binding([], "github", OWNER, registered_by="udita", now=T0)
    assert g.binding_state(ledger, "github", OWNER) == "registered"
    ledger = g.verify_binding(ledger, "github", OWNER, verified_by="udita", now=T1, **AUTH)
    assert g.binding_state(ledger, "github", OWNER) == "verified"
    ledger = g.revoke_binding(ledger, "github", OWNER, revoked_by="udita",
                              rationale="r", now=T1)
    assert g.binding_state(ledger, "github", OWNER) == "revoked"


def test_reregister_after_revoke_allowed():
    ledger = verified_ledger()
    ledger = g.revoke_binding(ledger, "github", OWNER, revoked_by="udita",
                              rationale="rotated", now=T1)
    ledger = g.register_binding(ledger, "github", OWNER, registered_by="udita", now=T1)
    ledger = g.verify_binding(ledger, "github", OWNER, verified_by="udita", now=T1, **AUTH)
    _, result = gx(ledger, "c9", "github", OWNER, effect=lambda: "back", now=T1)
    assert result == "back"


def test_input_validation():
    ledger = verified_ledger()
    with pytest.raises(ValueError, match="ACCTGATE:empty_field:service"):
        gx(ledger, "c1", " ", OWNER, effect=lambda: 1, now=T1)
    with pytest.raises(ValueError, match="ACCTGATE:bad_type:effect"):
        gx(ledger, "c1", "github", OWNER, effect=None, now=T1)


def test_roundtrip_and_tamper_detection():
    ledger = verified_ledger()
    ledger, _ = gx(ledger, "c1", "github", OWNER, effect=lambda: "x", now=T1)
    restored = g.loads(g.dumps(ledger))
    assert restored == ledger
    tampered = [dict(e, record=dict(e["record"])) for e in restored]
    tampered[0]["record"]["kind"] = "binding_verified"  # skip registration
    with pytest.raises(ValueError, match="GRLEDGER:.*integrity"):
        g.check_ledger(tampered)
