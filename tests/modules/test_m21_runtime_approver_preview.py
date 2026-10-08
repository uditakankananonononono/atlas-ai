# ruff: noqa: F811
"""Slice 9: the approver reads a bounded, redacted, deterministic preview of the refused call's stored arguments.

Labels: PROTECTION_* (must stay closed), NEW_*. Limits: the preview is what the model asked for (not proof of intent); redaction
regexes are best-effort; the digest still binds the full payload; SQLite only; no UI; purpose stays withheld.
"""
import json
import time  # noqa: F401

import pytest
from sqlalchemy import update

from app.modules.m21_claire.runtime.goals import GoalRow
from app.modules.m21_claire.runtime.preview import MAX_BYTES, MAX_STRING, render_preview
from tests.modules.test_m21_runtime_effects import _clear, clk, goal, store  # noqa: F401

DIG = "d" * 64


def seed(store, *refusals):
    gid = goal(store)
    with store._sessions.begin() as s:
        s.execute(update(GoalRow).where(GoalRow.id == gid).values(status="awaiting_review", report=json.dumps({"refusals": list(refusals)})))
    return gid


def ref(tool="send_mail", digest=DIG, **args):
    return {"reason": "approval_required", "tool": tool, "gates": ["comms"], "digest": digest, "arguments": args}


def test_NEW_preview_shows_recipient_and_amount_fields():
    p = render_preview({"to": "bob@example.com", "amount": 125.5, "memo": "invoice 7"})
    assert p["value"] == {"amount": 125.5, "memo": "invoice 7", "to": "bob@example.com"}
    assert p["truncated"] is False and p["contains_redactions"] is False and p["untrusted_model_content"] is True
    assert render_preview(None) is None


def test_PROTECTION_preview_is_deterministic_and_order_independent():
    a = render_preview({"b": 1, "a": [3, 2, {"z": 1, "y": 2}]}); b = render_preview({"a": [3, 2, {"y": 2, "z": 1}], "b": 1})
    assert a == b and json.dumps(a, sort_keys=False) == json.dumps(b, sort_keys=False)


def test_PROTECTION_caps_hold_on_hostile_arguments_and_flag_truncation():
    big = render_preview({"s": "x" * 50_000})
    assert len(big["value"]["s"]) < MAX_STRING + 40 and "50000 chars total" in big["value"]["s"] and big["truncated"] is True
    wide = render_preview({f"k{i}": i for i in range(10_000)})
    assert len(wide["value"]) <= 21 and wide["truncated"] is True
    deep = {"a": {"b": {"c": {"d": {"e": {"f": 1}}}}}}
    d = render_preview(deep)
    assert d["truncated"] is True and "omitted" in json.dumps(d["value"])
    many = render_preview({f"k{i}": "y" * 290 for i in range(20)})
    assert len(json.dumps(many["value"]).encode()) <= MAX_BYTES or many["value"].get("omitted") == "preview_over_budget"
    assert many["truncated"] is True
    uni = render_preview({"n": "é" * 400, "emoji": "😀" * 400})
    assert uni["truncated"] is True
    lst = render_preview({"l": list(range(500))})
    assert len(lst["value"]["l"]) == 21 and lst["truncated"] is True


def test_PROTECTION_redaction_markers_pass_through_and_are_flagged():
    from app.modules.m21_claire.runtime.redaction import redact
    stored = redact({"to": "bob", "api_key": "sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123", "note": "password: hunter2hunter2"})
    p = render_preview(stored)
    assert p["contains_redactions"] is True
    text = json.dumps(p)
    assert "sk-ABCDEF" not in text and "hunter2hunter2" not in text and p["value"]["to"] == "bob"


def test_PROTECTION_preview_comes_from_the_same_refusal_as_its_digest(store):
    d1, d2 = "1" * 64, "2" * 64
    gid = seed(store, ref(to="alice", digest=d1), ref(tool="wire", digest=d2, amount=900))
    v = store.approver_view("t1", gid)
    by = {r["digest"]: r for r in v["refusals"]}
    assert by[d1]["preview"]["value"] == {"to": "alice"} and by[d1]["tool"] == "send_mail"
    assert by[d2]["preview"]["value"] == {"amount": 900} and by[d2]["tool"] == "wire"
    assert v["untrusted_model_content"] is True and "purpose" not in v


def test_PROTECTION_view_is_a_pure_read_of_the_stored_row(store):
    gid = seed(store, ref(to="alice"))
    v1 = store.approver_view("t1", gid); v2 = store.approver_view("t1", gid)
    assert v1 == v2
    with store._sessions.begin() as s:
        row = s.get(GoalRow, gid)
        assert json.loads(row.report)["refusals"][0]["arguments"] == {"to": "alice"}   # nothing written back


def test_PROTECTION_route_gating_unchanged_and_purpose_still_hidden(store):
    from fastapi.testclient import TestClient
    from app.auth.context import TenantContext, require_tenant
    from app.main import app
    gid = seed(store, ref(to="alice"))
    who = {"ctx": TenantContext("t1", "ap1", frozenset({"claire-approver"}))}
    app.dependency_overrides[require_tenant] = lambda: who["ctx"]
    try:
        c = TestClient(app); u = f"/api/v1/claire/runtime/goals/{gid}/approver-view"
        j = c.get(u).json()
        assert j["refusals"][0]["preview"]["value"] == {"to": "alice"} and "do work" not in json.dumps(j)
        who["ctx"] = TenantContext("t1", "ap1"); assert c.get(u).status_code == 403
        who["ctx"] = TenantContext("t2", "ap1", frozenset({"claire-approver"})); assert c.get(u).status_code == 404
        who["ctx"] = TenantContext("t1", "a1"); assert c.get(u).status_code == 403          # the goal's own actor has no approver view
    finally:
        app.dependency_overrides.pop(require_tenant, None)


def test_PROTECTION_refusal_without_arguments_snapshot_has_no_preview(store):
    gid = seed(store, {"reason": "approval_required", "tool": "t", "gates": ["comms"], "digest": DIG})
    assert store.approver_view("t1", gid)["refusals"][0]["preview"] is None


@pytest.mark.parametrize("val", [object(), {1, 2}, b"x"])
def test_PROTECTION_unsupported_types_never_crash_the_preview(val):
    p = render_preview({"k": val}); assert p["truncated"] is True


def test_PROTECTION_token_shaped_KEYS_are_scrubbed_and_non_string_keys_survive():
    p = render_preview({"sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123": "v", 7: "seven"})
    t = json.dumps(p)
    assert "sk-ABCDEF" not in t and p["value"]["7"] == "seven"


def test_PROTECTION_distinct_keys_that_collide_when_truncated_never_merge():
    """Reviewer's exact case: 'x'*100+'a' and 'x'*100+'b' both cut to the same 100-char key. Both values must be shown."""
    p = render_preview({"x" * 100 + "a": "first", "x" * 100 + "b": "second"})
    assert sorted(p["value"].values()) == ["first", "second"] and len(p["value"]) == 2
    assert p["truncated"] is True and p["key_altered"] is True


def test_PROTECTION_keys_that_collide_after_scrubbing_never_merge():
    k1 = "sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123"; k2 = "sk-ZYXWVUTSRQPONMLKJIHGFEDCBA9876"
    p = render_preview({k1: "one", k2: "two"})
    assert sorted(p["value"].values()) == ["one", "two"] and p["key_altered"] is True
    assert "sk-ABCDEF" not in json.dumps(p) and "sk-ZYXWVU" not in json.dumps(p)


def test_PROTECTION_str_twin_keys_and_marker_named_keys_never_merge_or_overwrite():
    p = render_preview({1: "int", "1": "str"})
    assert sorted(p["value"].values()) == ["int", "str"]
    many = {f"k{i:02d}": i for i in range(25)}; many["...(more keys)"] = "real"
    q = render_preview(many)
    assert "real" in q["value"].values() and q["truncated"] is True


def test_PROTECTION_unaltered_keys_leave_key_altered_false_and_are_deterministic():
    p = render_preview({"to": "a", "amount": 1})
    assert p["key_altered"] is False
    coll = {"x" * 100 + "a": 1, "x" * 100 + "b": 2}
    assert render_preview(coll) == render_preview(dict(reversed(list(coll.items()))))


def test_PROTECTION_reviewer_case_single_101_char_key_is_flagged():
    p = render_preview({"k" * 101: "v"})
    assert p["truncated"] is True and p["key_altered"] is True and len(next(iter(p["value"]))) == 100


def test_PROTECTION_literal_dots_key_is_not_overwritten_by_the_more_keys_marker():
    many = {f"k{i:02d}": i for i in range(25)}; many["..."] = "user-value"
    p = render_preview(many)
    assert p["value"]["..."] == "user-value" and p["truncated"] is True
    assert any(str(v).endswith("more keys") for v in p["value"].values())


def test_PROTECTION_string_only_redaction_marker_sets_contains_redactions():
    from app.modules.m21_claire.runtime.redaction import redact
    stored = redact({"note": "sk-" + "A" * 30})
    assert "[REDACTED:" in stored["note"]
    p = render_preview(stored)
    assert p["contains_redactions"] is True and "AAAAAAAAAA" not in json.dumps(p)
    assert render_preview({"note": "plain"})["contains_redactions"] is False
