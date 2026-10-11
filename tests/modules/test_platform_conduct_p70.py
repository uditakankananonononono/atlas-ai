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


# ---- repair pins (round 2): finite timestamps, nested ToS/privacy field types, guards ----
NAN, INF = float("nan"), float("inf")


@pytest.mark.parametrize("bad", [NAN, INF, -INF])
def test_non_finite_numbers_rejected_everywhere(bad):
    d = decl()
    with pytest.raises(ValueError):
        preflight(act(at=bad), d)
    d = decl()
    d["recent_actions"] = [{"platform": "acme", "kind": "post", "at": bad, "count": 1}]
    with pytest.raises(ValueError):
        preflight(act(), d)
    d = decl()
    d["consent"] = [consent(granted_at=bad)]
    with pytest.raises(ValueError):
        preflight(act(subjects=["u1"], purpose="outreach"), d)
    d = decl()
    d["consent"] = [consent(expires_at=bad)]
    with pytest.raises(ValueError):
        preflight(act(subjects=["u1"], purpose="outreach"), d)


def test_string_allowed_kinds_is_rejected_not_substring_matched():
    d = decl()
    d["tos"]["acme"]["allowed_kinds"] = "post"
    with pytest.raises(ValueError):
        preflight(act(kind="po"), d)
    with pytest.raises(ValueError):
        preflight(act(kind="post"), d)


@pytest.mark.parametrize("bad_entry", [
    "x", ["post"], None, 5,
    {"allowed_kinds": "post"}, {"allowed_kinds": [1]}, {"allowed_kinds": [""]}, {"allowed_kinds": {"post": 1}},
    {"allowed_kinds": ["post"], "automation_allowed": "yes"},
    {"allowed_kinds": ["post"], "automation_allowed": 1},
])
def test_malformed_tos_entry_raises_value_error(bad_entry):
    d = decl()
    d["tos"]["acme"] = bad_entry
    with pytest.raises(ValueError):
        preflight(act(), d)


def test_declared_platform_without_allowed_kinds_denies_not_crashes():
    d = decl()
    d["tos"]["acme"] = {}
    r = preflight(act(), d)
    assert r["verdict"] == "deny" and "tos_kind_allowed" in failed(r)
    assert "tos_declared" not in failed(r)


def test_tos_entries_for_other_platforms_are_also_validated():
    d = decl()
    d["tos"]["other"] = {"allowed_kinds": "post"}
    with pytest.raises(ValueError):
        preflight(act(), d)


@pytest.mark.parametrize("priv", [
    [], "x", 5,
    {"purpose_allowed": []}, {"purpose_allowed": "x"}, {"purpose_allowed": {"outreach": "email"}},
    {"purpose_allowed": {"outreach": [1]}}, {"purpose_allowed": {"": ["email"]}},
    {"personal_categories": "email"}, {"personal_categories": [1]}, {"personal_categories": [""]},
])
def test_malformed_privacy_raises_value_error(priv):
    d = decl()
    d["privacy"] = priv
    with pytest.raises(ValueError):
        preflight(act(), d)


def test_empty_but_well_typed_privacy_is_valid_and_denies_personal_use():
    d = decl()
    d["privacy"] = {}
    assert preflight(act(), d)["verdict"] == "allow"
    assert preflight(act(data_categories=["email"], purpose="outreach"), d)["verdict"] == "allow"
    d["privacy"] = {"personal_categories": ["email"]}
    assert failed(preflight(act(data_categories=["email"], purpose="outreach"), d)) == ["privacy_purpose"]


def test_non_personal_category_with_missing_purpose_is_allowed():
    r = preflight(act(data_categories=["weather"]), decl())
    assert r["verdict"] == "allow"


def test_personal_category_with_missing_purpose_is_denied():
    r = preflight(act(data_categories=["email"]), decl())
    assert failed(r) == ["privacy_purpose"]


def test_consent_defaults_absent_revoked_and_expiry_mean_valid():
    d = decl()
    d["consent"] = [{"subject": "u1", "purpose": "outreach", "granted_at": NOW - 1}]
    assert preflight(act(subjects=["u1"], purpose="outreach"), d)["verdict"] == "allow"
    d["consent"][0]["revoked"] = True
    assert failed(preflight(act(subjects=["u1"], purpose="outreach"), d)) == ["consent"]


def test_one_valid_consent_among_revoked_and_expired_records_is_enough():
    d = decl()
    d["consent"] = [consent(revoked=True), consent(expires_at=NOW - 5), consent()]
    assert preflight(act(subjects=["u1"], purpose="outreach"), d)["verdict"] == "allow"


def test_subject_with_no_purpose_is_denied():
    d = decl()
    d["consent"] = [consent()]
    assert failed(preflight(act(subjects=["u1"]), d)) == ["consent"]


@pytest.mark.parametrize("a,d", [
    (None, None), ("x", None), ([], None),
])
def test_top_level_types(a, d):
    with pytest.raises(ValueError):
        preflight(a if a is not None else None, decl() if d is None else d)


def test_declarations_not_dict_rejected():
    for bad in (None, [], "x"):
        with pytest.raises(ValueError):
            preflight(act(), bad)


@pytest.mark.parametrize("mut", [
    lambda a, d: d.update(tos=[]), lambda a, d: d.update(rate_limits=[]),
    lambda a, d: d.update(rate_limits={"acme": []}),
    lambda a, d: d.update(rate_limits={"acme": {"post": []}}),
    lambda a, d: d["rate_limits"]["acme"]["post"].update(max="3"),
    lambda a, d: d["rate_limits"]["acme"]["post"].update(max=True),
    lambda a, d: d["rate_limits"]["acme"]["post"].update(window_seconds=True),
    lambda a, d: d["rate_limits"]["acme"]["post"].update(window_seconds=1.5),
    lambda a, d: d.update(recent_actions=["x"]),
    lambda a, d: d.update(recent_actions=[{"platform": "", "kind": "post", "at": 1, "count": 1}]),
    lambda a, d: d.update(recent_actions=[{"platform": "acme", "kind": "", "at": 1, "count": 1}]),
    lambda a, d: d.update(recent_actions=[{"platform": "acme", "kind": "post", "at": 1, "count": 0}]),
    lambda a, d: d.update(consent={}),
    lambda a, d: d.update(consent=["x"]),
    lambda a, d: d.update(consent=[{"subject": "", "purpose": "p", "granted_at": 1}]),
    lambda a, d: d.update(consent=[{"subject": "u", "purpose": "", "granted_at": 1}]),
    lambda a, d: d.update(consent=[{"subject": "u", "purpose": "p"}]),
    lambda a, d: d.update(consent=[{"subject": "u", "purpose": "p", "granted_at": 1, "expires_at": "x"}]),
    lambda a, d: d.update(review_kinds="post"),
    lambda a, d: d.update(review_kinds=[1]),
    lambda a, d: a.update(purpose=""), lambda a, d: a.update(purpose=5),
    lambda a, d: a.update(platform=5), lambda a, d: a.update(count="1"), lambda a, d: a.update(count=-1),
    lambda a, d: a.update(subjects=[""]), lambda a, d: a.update(subjects=[1]),
    lambda a, d: a.update(data_categories=[""]), lambda a, d: a.update(data_categories=[1]),
    lambda a, d: a.update(automated=1),
])
def test_more_malformed_inputs_raise_value_error(mut):
    a, d = act(), decl()
    mut(a, d)
    with pytest.raises(ValueError):
        preflight(a, d)


def test_review_kinds_must_be_strings_but_may_be_absent():
    d = decl()
    d.pop("review_kinds")
    assert preflight(act(), d)["verdict"] == "allow"
    d["review_kinds"] = ("post",)
    assert preflight(act(), d)["verdict"] == "needs_review"


def test_integer_and_float_timestamps_both_finite_ok():
    assert preflight(act(at=NOW + 0.5), decl())["verdict"] == "allow"


@pytest.mark.parametrize("kind", ["po", "pos", "ost", "'", "post'", "["])
def test_kind_must_equal_a_declared_kind_exactly(kind):
    d = decl()
    d["rate_limits"]["acme"]["*"] = {"max": 9, "window_seconds": 60}
    r = preflight(act(kind=kind), d)
    assert r["verdict"] == "deny" and "tos_kind_allowed" in failed(r)


# ---- round 3: huge JSON ints must give ValueError (never OverflowError) ----
BIG = 10 ** 400
LIMIT = 2 ** 53


@pytest.mark.parametrize("v", [BIG, -BIG, LIMIT + 1, -(LIMIT + 1), 1e300, -1e300])
def test_out_of_range_numbers_rejected_on_every_time_path(v):
    with pytest.raises(ValueError):
        preflight(act(at=v), decl())
    d = decl()
    d["recent_actions"] = [{"platform": "acme", "kind": "post", "at": v, "count": 1}]
    with pytest.raises(ValueError):
        preflight(act(), d)
    d = decl()
    d["consent"] = [consent(granted_at=v)]
    with pytest.raises(ValueError):
        preflight(act(subjects=["u1"], purpose="outreach"), d)
    d = decl()
    d["consent"] = [consent(expires_at=v)]
    with pytest.raises(ValueError):
        preflight(act(subjects=["u1"], purpose="outreach"), d)


def test_numbers_exactly_at_limit_are_accepted():
    d = decl()
    d["recent_actions"] = [{"platform": "acme", "kind": "post", "at": LIMIT, "count": 1}]
    d["consent"] = [consent(granted_at=-LIMIT, expires_at=LIMIT)]
    assert preflight(act(at=LIMIT - 1, subjects=["u1"], purpose="outreach"), d)["verdict"] == "allow"


@pytest.mark.parametrize("w", [BIG, LIMIT + 1])
def test_huge_rate_window_rejected_with_value_error(w):
    d = decl()
    d["rate_limits"]["acme"]["post"]["window_seconds"] = w
    with pytest.raises(ValueError):
        preflight(act(at=NOW + 0.5), d)
    with pytest.raises(ValueError):
        preflight(act(), d)


def test_window_exactly_at_limit_is_accepted_with_float_time():
    d = decl()
    d["rate_limits"]["acme"]["post"]["window_seconds"] = LIMIT
    assert preflight(act(at=NOW + 0.5), d)["verdict"] == "allow"


def test_huge_counts_and_max_do_not_overflow():
    d = decl()
    d["rate_limits"]["acme"]["post"]["max"] = BIG * 2
    d["recent_actions"] = [{"platform": "acme", "kind": "post", "at": NOW - 1, "count": BIG}]
    assert preflight(act(count=BIG), d)["verdict"] == "allow"
    d["rate_limits"]["acme"]["post"]["max"] = BIG * 2 - 1
    assert preflight(act(count=BIG), d)["verdict"] == "deny"


# ---- round 3: pins for non-equivalent survivors reported by independent review ----
@pytest.mark.parametrize("bad", [(), "", {}, 0, None])
def test_recent_actions_must_be_a_list(bad):
    d = decl()
    d["recent_actions"] = bad
    with pytest.raises(ValueError):
        preflight(act(), d)


def test_wildcard_only_rate_limit_allows_within_limit_and_denies_over():
    d = decl()
    d["rate_limits"] = {"acme": {"*": {"max": 2, "window_seconds": 60}}}
    assert preflight(act(), d)["verdict"] == "allow"
    d["recent_actions"] = [{"platform": "acme", "kind": "dm", "at": NOW - 1, "count": 1}]
    assert preflight(act(), d)["verdict"] == "allow"
    assert failed(preflight(act(count=2), d)) == ["rate_limit"]


def test_exact_reason_strings_for_privacy_branches():
    def reason(r):
        return [c["reason"] for c in r["checks"] if c["check"] == "privacy_purpose"][0]
    assert reason(preflight(act(data_categories=["weather"]), decl())) == "no declared personal categories"
    assert reason(preflight(act(), decl())) == "no data categories declared"
    assert reason(preflight(act(data_categories=["email"], purpose="outreach"), decl())) == "personal categories within declared purpose"
    assert reason(preflight(act(data_categories=["email"], purpose="analytics"), decl())) == \
        "categories not allowed for declared purpose: email"
    d = decl()
    d.pop("privacy")
    assert reason(preflight(act(data_categories=["email"]), d)) == "data categories given but no privacy declaration"
