"""P70 platform conduct preflight: declared-input checks only. Stdlib only."""
import copy

import pytest

from app.modules.instinct_doc.platform_conduct_p70 import preflight

NOW = 1_000_000


def decl():
    return {
        "tos": {"acme": {"allowed_kinds": ["post", "dm"], "automation_allowed": False}},
        "rate_limits": {"acme": {"post": {"max": 3, "window_seconds": 3600}}},
        "recent_actions": [],
        "consent": [],
        "privacy": {"personal_categories": ["email", "name"],
                    "purpose_allowed": {"outreach": ["email", "name"], "analytics": ["name"]}},
        "review_kinds": [],
    }


def act(**kw):
    a = {"platform": "acme", "kind": "post", "at": NOW}
    a.update(kw)
    return a


def failed(r):
    return sorted(c["check"] for c in r["checks"] if not c["passed"])


def test_plain_allowed_action():
    r = preflight(act(), decl())
    assert r["verdict"] == "allow" and failed(r) == []


def test_result_labels_scope_and_no_action():
    r = preflight(act(), decl())
    assert r["scope"] == "declared-input-only" and r["performs_no_action"] is True
    assert r["not_legal_compliance"] is True


def test_undeclared_platform_denied():
    r = preflight(act(platform="zed"), decl())
    assert r["verdict"] == "deny" and "tos_declared" in failed(r)


def test_kind_not_allowed_denied():
    d = decl()
    d["rate_limits"]["acme"]["share"] = {"max": 5, "window_seconds": 60}
    r = preflight(act(kind="share"), d)
    assert r["verdict"] == "deny" and failed(r) == ["tos_kind_allowed"]


def test_automation_denied_unless_declared_allowed():
    assert failed(preflight(act(automated=True), decl())) == ["tos_automation"]
    d = decl()
    d["tos"]["acme"]["automation_allowed"] = True
    assert preflight(act(automated=True), d)["verdict"] == "allow"


def test_no_rate_limit_declared_is_denied():
    d = decl()
    d["rate_limits"] = {}
    assert failed(preflight(act(), d)) == ["rate_limit"]


def test_rate_limit_counts_recent_actions_in_window():
    d = decl()
    d["recent_actions"] = [{"platform": "acme", "kind": "post", "at": NOW - 10, "count": 3}]
    r = preflight(act(), d)
    assert r["verdict"] == "deny" and failed(r) == ["rate_limit"]
    d["recent_actions"][0]["count"] = 2
    assert preflight(act(), d)["verdict"] == "allow"


def test_rate_limit_boundary_exactly_at_max_allowed_one_over_denied():
    d = decl()
    d["recent_actions"] = [{"platform": "acme", "kind": "post", "at": NOW - 1, "count": 1}]
    assert preflight(act(count=2), d)["verdict"] == "allow"
    assert preflight(act(count=3), d)["verdict"] == "deny"


def test_rate_limit_ignores_old_other_platform_and_other_kind_entries():
    d = decl()
    d["recent_actions"] = [
        {"platform": "acme", "kind": "post", "at": NOW - 3600, "count": 3},
        {"platform": "other", "kind": "post", "at": NOW - 5, "count": 3},
        {"platform": "acme", "kind": "dm", "at": NOW - 5, "count": 3},
    ]
    assert preflight(act(), d)["verdict"] == "allow"


def test_rate_limit_ignores_future_entries():
    d = decl()
    d["recent_actions"] = [{"platform": "acme", "kind": "post", "at": NOW + 5, "count": 3}]
    assert preflight(act(), d)["verdict"] == "allow"


def test_wildcard_kind_limit_counts_all_kinds_of_platform():
    d = decl()
    d["rate_limits"] = {"acme": {"*": {"max": 2, "window_seconds": 60}}}
    d["recent_actions"] = [{"platform": "acme", "kind": "dm", "at": NOW - 5, "count": 2}]
    assert failed(preflight(act(), d)) == ["rate_limit"]


def test_specific_kind_limit_wins_over_wildcard():
    d = decl()
    d["rate_limits"] = {"acme": {"post": {"max": 10, "window_seconds": 60}, "*": {"max": 1, "window_seconds": 60}}}
    d["recent_actions"] = [{"platform": "acme", "kind": "post", "at": NOW - 5, "count": 5}]
    assert preflight(act(), d)["verdict"] == "allow"


def consent(**kw):
    c = {"subject": "u1", "purpose": "outreach", "granted_at": NOW - 100, "expires_at": None, "revoked": False}
    c.update(kw)
    return c


def test_subject_without_consent_denied():
    r = preflight(act(subjects=["u1"], purpose="outreach"), decl())
    assert r["verdict"] == "deny" and failed(r) == ["consent"]
    assert "u1" in [c for c in r["checks"] if c["check"] == "consent"][0]["reason"]


def test_valid_consent_allows():
    d = decl()
    d["consent"] = [consent()]
    assert preflight(act(subjects=["u1"], purpose="outreach"), d)["verdict"] == "allow"


@pytest.mark.parametrize("bad", [
    {"revoked": True}, {"expires_at": NOW}, {"expires_at": NOW - 1},
    {"granted_at": NOW + 1}, {"purpose": "analytics"}, {"subject": "u2"},
])
def test_invalid_consent_denied(bad):
    d = decl()
    d["consent"] = [consent(**bad)]
    assert failed(preflight(act(subjects=["u1"], purpose="outreach"), d)) == ["consent"]


def test_consent_granted_exactly_now_is_valid_and_expiry_one_later_valid():
    d = decl()
    d["consent"] = [consent(granted_at=NOW, expires_at=NOW + 1)]
    assert preflight(act(subjects=["u1"], purpose="outreach"), d)["verdict"] == "allow"


def test_every_subject_needs_consent():
    d = decl()
    d["consent"] = [consent()]
    r = preflight(act(subjects=["u1", "u2"], purpose="outreach"), d)
    assert failed(r) == ["consent"] and "u2" in r["checks"][-1]["reason"] + str(r["checks"])


def test_personal_category_without_subject_needs_declared_purpose():
    r = preflight(act(data_categories=["email"], purpose="outreach"), decl())
    assert r["verdict"] == "allow"
    r = preflight(act(data_categories=["email"]), decl())
    assert "privacy_purpose" in failed(r)


def test_category_outside_purpose_denied():
    r = preflight(act(data_categories=["email"], purpose="analytics"), decl())
    assert failed(r) == ["privacy_purpose"]


def test_unknown_purpose_denied():
    r = preflight(act(data_categories=["name"], purpose="marketing"), decl())
    assert failed(r) == ["privacy_purpose"]


def test_non_personal_category_needs_no_purpose():
    assert preflight(act(data_categories=["weather"]), decl())["verdict"] == "allow"


def test_review_kind_needs_review_when_all_checks_pass_but_deny_still_wins():
    d = decl()
    d["review_kinds"] = ["post"]
    assert preflight(act(), d)["verdict"] == "needs_review"
    assert preflight(act(platform="zed"), d)["verdict"] == "deny"


@pytest.mark.parametrize("mut", [
    lambda a, d: a.pop("platform"), lambda a, d: a.update(kind=""), lambda a, d: a.update(at=True),
    lambda a, d: a.update(at="now"), lambda a, d: a.update(count=0), lambda a, d: a.update(count=True),
    lambda a, d: a.update(subjects="u1"), lambda a, d: a.update(data_categories="email"),
    lambda a, d: a.update(automated="yes"),
    lambda a, d: d.pop("tos"), lambda a, d: d.update(recent_actions="x"),
    lambda a, d: d["rate_limits"]["acme"]["post"].update(max=0),
    lambda a, d: d["rate_limits"]["acme"]["post"].update(window_seconds=-1),
    lambda a, d: d.update(recent_actions=[{"platform": "acme", "kind": "post", "at": "x", "count": 1}]),
    lambda a, d: d.update(consent=[{"subject": "u1"}]),
])
def test_malformed_input_raises_value_error(mut):
    a, d = act(), decl()
    mut(a, d)
    with pytest.raises(ValueError):
        preflight(a, d)


def test_inputs_not_mutated_and_deterministic():
    a, d = act(subjects=["u1"], purpose="outreach"), decl()
    d["consent"] = [consent()]
    a0, d0 = copy.deepcopy(a), copy.deepcopy(d)
    r1, r2 = preflight(a, d), preflight(a, d)
    assert r1 == r2 and a == a0 and d == d0


def test_categories_without_privacy_declaration_denied():
    d = decl()
    d.pop("privacy")
    assert failed(preflight(act(data_categories=["weather"], purpose="outreach"), d)) == ["privacy_purpose"]
    assert preflight(act(), d)["verdict"] == "allow"


def test_consent_revoked_must_be_bool():
    d = decl()
    d["consent"] = [consent(revoked="no")]
    with pytest.raises(ValueError):
        preflight(act(subjects=["u1"], purpose="outreach"), d)
