"""Count-accounting regressions found via peer review. Normal repo imports.

Converted from the peer RED oracle and boundary/malformed/tamper probes.
A frozen legacy row is pinned independently; unknown old counts never default.
"""
import hashlib
import json
from pathlib import Path

import pytest

from app.runtime.guardrails import outbound_gate as g
from app.runtime.guardrails.enforcer import GuardrailEnforcer
from app.runtime.guardrails.errors import GuardrailRefusal

DECL = {
    "tos": {"example.com": {"allowed_kinds": ["read"], "automation_allowed": True}},
    "rate_limits": {"example.com": {"read": {"max": 10, "window_seconds": 3600}}},
}
NOW = "2026-10-13T17:00:00+00:00"
SHA = "b4e6d2f139378643809b980e02c84b2f8556b15fe1946939292f36a402bb967b"


def action(i, count, at):
    return {"id": f"a{i}", "platform": "example.com", "kind": "read", "at": at,
            "count": count, "automated": True, "purpose": "research",
            "subjects": [], "data_categories": []}


def fixture():
    blob = (Path(__file__).parent / "fixtures/g136_legacy_fixture.json").read_bytes()
    assert hashlib.sha256(blob).hexdigest() == SHA
    return blob.decode()


@pytest.mark.parametrize("enforcer", [False, True])
def test_declared_count_blocks_second_effect_and_roundtrips(enforcer):
    effects = []
    gate = GuardrailEnforcer()
    ledger = []
    if enforcer:
        gate.dispatch_outbound(action(1, 6, 1000), DECL, effect=effects.append, now=NOW)
        with pytest.raises(GuardrailRefusal):
            gate.dispatch_outbound(action(2, 6, 1010), DECL, effect=effects.append, now=NOW)
        ledger = gate.ledger("outbound")
        restored = GuardrailEnforcer.loads(gate.dumps()).ledger("outbound")
    else:
        ledger, _ = g.dispatch(action(1, 6, 1000), DECL, effect=effects.append, now=NOW)
        with pytest.raises(GuardrailRefusal) as held:
            g.dispatch(action(2, 6, 1010), DECL, effect=effects.append, now=NOW, ledger=ledger)
        ledger = held.value.ledger
        restored = g.loads(g.dumps(ledger))
    assert [a["id"] for a in effects] == ["a1"]
    assert [h["count"] for h in g.history(ledger, "example.com")] == [6]
    assert [h["count"] for h in g.history(restored, "example.com")] == [6]


def test_equality_boundary_and_over_boundary_effects():
    ledger, effects = [], []
    for i, count, at in [(4, 4, 2000), (5, 6, 2001)]:
        ledger, _ = g.dispatch(action(i, count, at), DECL, effect=effects.append, now=NOW, ledger=ledger)
    with pytest.raises(GuardrailRefusal):
        g.dispatch(action(6, 1, 2002), DECL, effect=effects.append, now=NOW, ledger=ledger)
    assert [a["id"] for a in effects] == ["a4", "a5"]


@pytest.mark.parametrize("bad", [0, -1, "6", True])
def test_malformed_count_refuses_before_ledger_or_effect(bad):
    ledger, effects = [], []
    with pytest.raises(ValueError, match="^count must be a positive integer$"):
        g.dispatch(action(1, bad, 1000), DECL, effect=effects.append, now=NOW, ledger=ledger)
    assert ledger == [] and effects == []


def test_new_missing_count_uses_p70_default_not_legacy_default():
    a = action(1, 1, 1000)
    del a["count"]
    effects = []
    ledger, _ = g.dispatch(a, DECL, effect=effects.append, now=NOW)
    assert ledger[-1]["record"]["count"] == 1
    assert g.history(ledger, "example.com")[0]["count"] == 1
    assert [a["id"] for a in effects] == ["a1"]


@pytest.mark.parametrize("enforcer", [False, True])
def test_frozen_legacy_unknown_count_refuses_at_load(enforcer):
    blob = fixture()
    if enforcer:
        doc = json.loads(GuardrailEnforcer().dumps())
        doc["outbound"] = json.loads(blob)
        load = lambda: GuardrailEnforcer.loads(json.dumps(doc))
    else:
        load = lambda: g.loads(blob)
    with pytest.raises(ValueError, match="^OUTGATE:.*predates count accounting"):
        load()


@pytest.mark.parametrize("kind", ["hash", "content"])
def test_corrupted_legacy_fixture_refuses_chain(kind):
    blob = fixture()
    doc = json.loads(blob)
    if kind == "hash":
        doc[0]["record_hash"] = "0" * 64
    else:
        doc[0]["record"]["platform"] = "example.org"
    with pytest.raises(ValueError, match="^GRLEDGER:"):
        g.loads(json.dumps(doc))
