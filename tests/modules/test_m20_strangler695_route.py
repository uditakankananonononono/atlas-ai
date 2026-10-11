"""Row695 strangler-fig route dispatch: independent oracle, negatives, bounds."""
import ast
import copy
import itertools
import json
import math
import pathlib
import random
import re

import pytest

from app.modules.m20_general_cognitive_worker.strangler_router695 import evaluate

MODULE_PATH = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/strangler_router695.py"
TARGETS = {"legacy": {"handler": "old-app"}, "replacement": {"handler": "new-app"}}


def R(rid, method, kind, path, target):
    return {"id": rid, "method": method, "match": kind, "path": path, "target": target}


def Q(rid, method, path):
    return {"id": rid, "method": method, "path": path}


def out(status=200, body="ok"):
    return {"status": status, "body": body}


def fx(fid, rid, legacy=None, replacement=None, golden=None):
    d = {"id": fid, "request_id": rid, "legacy": legacy or out(), "replacement": replacement or out()}
    if golden is not None:
        d["golden"] = golden
    return d


def base(**over):
    d = {
        "targets": copy.deepcopy(TARGETS),
        "rules": [
            R("r-orders-prefix", "*", "prefix", "/orders", "replacement"),
            R("r-orders-exact", "GET", "exact", "/orders", "legacy"),
        ],
        "requests": [Q("q1", "GET", "/orders"), Q("q2", "POST", "/orders"), Q("q3", "GET", "/orders/7")],
    }
    d.update(over)
    return d


def routes(res):
    return {r["request_id"]: r for r in res["routes"]}


# ---------------------------------------------------------------- oracle
def oracle_route(rules, method, path):
    """Independent implementation: regex matching plus arithmetic score."""
    best = None
    for r in rules:
        if r["method"] not in ("*", method):
            continue
        if r["match"] == "exact":
            ok = path == r["path"]
            score = 10**6
        else:
            p = r["path"]
            ok = p == "/" or path == p or path.startswith(p + "/")
            score = 100 * (0 if p == "/" else len(p.strip("/").split("/")))
        if not ok:
            continue
        score += 1 if r["method"] != "*" else 0
        if best is None or score > best[0]:
            best = (score, r)
    return None if best is None else best[1]


# ---------------------------------------------------------------- known answers
def test_known_answer_precedence_exact_over_prefix_and_method():
    res = evaluate(base())
    rt = routes(res)
    assert res["status"] == "evaluated"
    assert (rt["q1"]["target"], rt["q1"]["rule_id"]) == ("legacy", "r-orders-exact")
    assert (rt["q2"]["target"], rt["q2"]["rule_id"]) == ("replacement", "r-orders-prefix")
    assert (rt["q3"]["target"], rt["q3"]["rule_id"]) == ("replacement", "r-orders-prefix")
    assert rt["q1"]["handler"] == "old-app" and rt["q3"]["handler"] == "new-app"
    assert [r["request_id"] for r in res["routes"]] == ["q1", "q2", "q3"]


def test_longest_prefix_and_segment_boundary():
    rules = [
        R("a", "*", "prefix", "/", "legacy"),
        R("b", "*", "prefix", "/api", "replacement"),
        R("c", "*", "prefix", "/api/v1", "legacy"),
    ]
    reqs = [Q("x1", "GET", "/api/v1/users"), Q("x2", "GET", "/api/v2"), Q("x3", "GET", "/apix"), Q("x4", "GET", "/api"), Q("x5", "GET", "/")]
    rt = routes(evaluate({"targets": TARGETS, "rules": rules, "requests": reqs}))
    assert {k: v["rule_id"] for k, v in rt.items()} == {"x1": "c", "x2": "b", "x3": "a", "x4": "b", "x5": "a"}


def test_method_specific_beats_wildcard_on_same_path_and_trace_order():
    rules = [R("w", "*", "exact", "/p", "legacy"), R("g", "GET", "exact", "/p", "replacement")]
    res = evaluate({"targets": TARGETS, "rules": rules, "requests": [Q("q", "GET", "/p"), Q("z", "PUT", "/p")]})
    rt = routes(res)
    assert rt["q"]["rule_id"] == "g" and rt["z"]["rule_id"] == "w"
    assert [t["rule_id"] for t in rt["q"]["trace"]] == ["g", "w"]
    assert [t["selected"] for t in rt["q"]["trace"]] == [True, False]
    assert [t["rule_id"] for t in rt["z"]["trace"]] == ["w"]


def test_no_route_without_default_and_default_target():
    d = {"targets": TARGETS, "rules": [R("a", "GET", "exact", "/a", "replacement")], "requests": [Q("q", "GET", "/b")]}
    r = routes(evaluate(d))["q"]
    assert r["decision"] == "no_route" and r["target"] is None and r["handler"] is None and r["rule_id"] is None
    d["default_target"] = "legacy"
    r = routes(evaluate(d))["q"]
    assert (r["decision"], r["target"], r["rule_id"]) == ("default", "legacy", None)


def test_exact_vs_prefix_overlap_reported():
    res = evaluate(base())
    assert any(o["kind"] == "exact_vs_prefix" and o["winner"] == "r-orders-exact" and o["shadowed"] == "r-orders-prefix" for o in res["overlaps"])


# ---------------------------------------------------------------- ambiguity / refusals
def test_cross_dimension_precedence_ambiguity_refused():
    # GET-specific on the shorter prefix vs wildcard on the longer prefix: neither dominates.
    rules = [R("m", "GET", "prefix", "/a", "replacement"), R("p", "*", "prefix", "/a/b", "legacy")]
    with pytest.raises(ValueError, match="ambiguous_precedence"):
        evaluate({"targets": TARGETS, "rules": rules, "requests": [Q("q", "GET", "/a/b")]})
    rules[1]["target"] = "replacement"  # same target: harmless
    assert routes(evaluate({"targets": TARGETS, "rules": rules, "requests": [Q("q", "GET", "/a/b")]}))["q"]["target"] == "replacement"


def test_duplicate_selector_with_different_ids_refused():
    rules = [R("a", "GET", "exact", "/x", "legacy"), R("b", "GET", "exact", "/x", "replacement")]
    with pytest.raises(ValueError, match="duplicate_rule_selector"):
        evaluate({"targets": TARGETS, "rules": rules, "requests": [Q("q", "GET", "/x")]})


BAD_PATHS = ["", "orders", "/orders/", "/a//b", "/a/./b", "/a/../b", "/a/..", "/a?x=1", "/a#f", "/a\\b", "/%2e%2e/x", "/a%2Fb", "/a%2fb", "/a%5Cb", "/a%zz", "/a%", "/caf\u00e9", "/a b", "/a\x00b", "/a\nb", "/%41", "/a%e2%82%ac", "//a", "/a/."]


@pytest.mark.parametrize("path", BAD_PATHS)
def test_unnormalized_request_path_refused_per_request_not_guessed(path):
    d = base(requests=[Q("bad", "GET", path), Q("good", "GET", "/orders")])
    res = evaluate(d)
    rt = routes(res)
    assert rt["bad"]["decision"] == "refused" and rt["bad"]["target"] is None and rt["bad"]["reasons"]
    assert rt["good"]["decision"] == "routed"


@pytest.mark.parametrize("method", ["get", "Get", "FETCH", "", "G ET", "*", None, 5])
def test_unnormalized_method_refused(method):
    res = evaluate(base(requests=[Q("bad", method, "/orders")]))
    assert routes(res)["bad"]["decision"] == "refused"


@pytest.mark.parametrize("path", ["orders", "/a/", "/a//b", "/a/../b", "/a?q", "/%41"])
def test_unnormalized_rule_path_refused_whole(path):
    with pytest.raises(ValueError):
        evaluate(base(rules=[R("r", "GET", "prefix", path, "legacy")]))


def test_root_prefix_allowed_root_exact_allowed_and_prefix_trailing_slash_refused():
    evaluate(base(rules=[R("r", "*", "prefix", "/", "legacy")], requests=[Q("q", "GET", "/")]))
    evaluate(base(rules=[R("r", "GET", "exact", "/", "legacy")], requests=[Q("q", "GET", "/")]))
    with pytest.raises(ValueError):
        evaluate(base(rules=[R("r", "*", "prefix", "/x/", "legacy")]))


def test_missing_and_malformed_targets_refused():
    for bad in [{}, {"legacy": {"handler": "x"}}, {"replacement": {"handler": "x"}}, {"legacy": {"handler": "x"}, "replacement": {}},
                {"legacy": {"handler": ""}, "replacement": {"handler": "y"}}, {"legacy": {"handler": "x"}, "replacement": {"handler": 3}},
                {**TARGETS, "canary": {"handler": "z"}}, "x", None]:
        with pytest.raises(ValueError):
            evaluate(base(targets=bad))
    with pytest.raises(ValueError):
        evaluate(base(rules=[R("r", "GET", "exact", "/o", "canary")]))
    with pytest.raises(ValueError):
        evaluate(base(default_target="canary"))
    with pytest.raises(ValueError):
        evaluate({k: v for k, v in base().items() if k != "targets"})


# ---------------------------------------------------------------- determinism
def test_permutation_invariance_and_repeatability():
    d = base(fixtures=[fx("f1", "q2", replacement=out(500)), fx("f2", "q1")], default_target="legacy")
    ref = evaluate(d)
    assert json.dumps(ref, sort_keys=False) == json.dumps(evaluate(copy.deepcopy(d)), sort_keys=False)
    rng = random.Random(9)
    for _ in range(25):
        e = copy.deepcopy(d)
        for k in ("rules", "requests", "fixtures"):
            rng.shuffle(e[k])
        assert json.dumps(evaluate(e)) == json.dumps(ref)


def test_input_not_mutated():
    d = base(fixtures=[fx("f", "q1")])
    snap = copy.deepcopy(d)
    evaluate(d)
    assert d == snap


# ---------------------------------------------------------------- parity
def parity(res):
    return {p["fixture_id"]: p for p in res["parity"]}


def test_parity_known_answers_status_body_both():
    d = base(requests=[Q("q%d" % i, "POST", "/orders") for i in range(4)], fixtures=[
        fx("m", "q0"),
        fx("s", "q1", replacement=out(201)),
        fx("b", "q2", replacement=out(200, "different")),
        fx("sb", "q3", legacy=out(200, {"a": 1}), replacement=out(404, {"a": 2})),
    ])
    p = parity(evaluate(d))
    assert (p["m"]["parity"], p["m"]["mismatched_fields"]) == (True, [])
    assert p["s"]["mismatched_fields"] == ["status"] and not p["s"]["parity"]
    assert p["b"]["mismatched_fields"] == ["body"]
    assert p["sb"]["mismatched_fields"] == ["body", "status"]
    assert p["s"]["effective_target"] == "replacement" and p["s"]["served_output"] == out(201)


@pytest.mark.parametrize("a,b", [(1, True), (1, 1.0), (0, False), ("1", 1), ([1], [1.0]), ({"a": 1}, {"a": True}), (None, 0), ([1, 2], [2, 1]), ({"a": 1}, {"a": 1, "b": 2})])
def test_body_comparison_is_type_strict_and_structural(a, b):
    d = base(requests=[Q("q", "POST", "/orders")], fixtures=[fx("f", "q", legacy=out(200, a), replacement=out(200, b))])
    assert parity(evaluate(d))["f"]["mismatched_fields"] == ["body"]


def test_dict_key_order_irrelevant():
    d = base(requests=[Q("q", "POST", "/orders")], fixtures=[fx("f", "q", legacy=out(200, {"a": 1, "b": [1, {"c": 2}]}), replacement=out(200, {"b": [1, {"c": 2}], "a": 1}))])
    assert parity(evaluate(d))["f"]["parity"] is True


def test_golden_agree_and_disagree():
    d = base(requests=[Q("q1", "POST", "/orders"), Q("q2", "POST", "/orders"), Q("q3", "POST", "/orders")], fixtures=[
        fx("ok1", "q1", golden={"parity": True, "mismatched_fields": []}),
        fx("ok2", "q2", replacement=out(500), golden={"parity": False, "mismatched_fields": ["status"]}),
        fx("bad", "q3", golden={"parity": False, "mismatched_fields": ["body"]}),
    ])
    res = evaluate(d)
    p = parity(res)
    assert p["ok1"]["golden_ok"] is True and p["ok2"]["golden_ok"] is True and p["bad"]["golden_ok"] is False
    assert res["golden_violations"] == ["bad"]
    assert "r-orders-prefix" in res["rollback_candidates"]  # mismatch and golden violation both count


def test_golden_disagreement_alone_makes_candidate():
    d = base(requests=[Q("q", "POST", "/orders")], fixtures=[fx("bad", "q", golden={"parity": False, "mismatched_fields": ["body"]})])
    res = evaluate(d)
    assert res["rollback_candidates"] == ["r-orders-prefix"]


@pytest.mark.parametrize("g", [{"parity": True}, {"parity": 1, "mismatched_fields": []}, {"parity": False, "mismatched_fields": ["x"]},
                               {"parity": True, "mismatched_fields": ["status"]}, {"parity": False, "mismatched_fields": []},
                               {"parity": False, "mismatched_fields": ["status", "status"]}, {"parity": True, "mismatched_fields": [], "extra": 1}, [], None])
def test_malformed_or_inconsistent_golden_refused(g):
    d = base(requests=[Q("q", "POST", "/orders")], fixtures=[fx("f", "q")])
    d["fixtures"][0]["golden"] = g
    with pytest.raises(ValueError):
        evaluate(d)


# ---------------------------------------------------------------- rollback
def test_rollback_changes_effective_routing_only_for_candidate_rule():
    d = base(requests=[Q("q1", "GET", "/orders"), Q("q2", "POST", "/orders"), Q("q3", "GET", "/orders/7"), Q("q4", "GET", "/other")],
             rules=[R("pre", "*", "prefix", "/orders", "replacement"), R("ex", "GET", "exact", "/orders", "replacement"), R("o", "*", "prefix", "/other", "replacement")],
             fixtures=[fx("f2", "q2", replacement=out(500)), fx("f3", "q3"), fx("f4", "q4")])
    res = evaluate(d)
    assert res["rollback_candidates"] == ["pre"]
    eff = {e["request_id"]: e for e in res["rollback_effect"]}
    assert set(eff) == {"q2", "q3"}  # q1 uses the separate exact rule, q4 another rule
    assert eff["q2"]["before"] == "replacement" and eff["q2"]["after"] == "legacy" and eff["q2"]["rule_id"] == "pre"
    assert res["routes"] and routes(res)["q2"]["target"] == "replacement"  # baseline routing unchanged in report
    assert res["after_rollback_routes"] and {r["request_id"]: r["target"] for r in res["after_rollback_routes"]} == {"q1": "replacement", "q2": "legacy", "q3": "legacy", "q4": "replacement"}


def test_no_candidate_when_matching_or_when_already_legacy():
    d = base(fixtures=[fx("f1", "q1", replacement=out(500)), fx("f2", "q2")])  # q1 served by legacy rule
    res = evaluate(d)
    assert res["rollback_candidates"] == [] and res["rollback_effect"] == []
    assert parity(res)["f1"]["parity"] is False and parity(res)["f1"]["effective_target"] == "legacy"


def test_replacement_routed_without_fixture_is_unverified_not_candidate():
    res = evaluate(base(fixtures=[fx("f1", "q1")]))
    assert res["unverified_replacement_rules"] == ["r-orders-prefix"] and res["rollback_candidates"] == []


def test_matching_fixture_covering_all_requests_still_no_safe_removal():
    d = base(rules=[R("r", "*", "prefix", "/", "replacement")], requests=[Q("q", "GET", "/x")], fixtures=[fx("f", "q")])
    res = evaluate(d)
    assert res["rollback_candidates"] == [] and res["unverified_replacement_rules"] == []
    assert res["legacy_removal_safe"] is False and res["legacy_removal_blockers"]
    assert res["handler_executed"] is False and res["network_routing_performed"] is False and res["production_traffic_verified"] is False


def test_fixture_on_refused_or_unrouted_request_is_not_routed_and_never_candidate():
    d = base(requests=[Q("q", "GET", "/bad/"), Q("n", "GET", "/zzz")], rules=[R("a", "GET", "exact", "/orders", "replacement")],
             fixtures=[fx("f", "q", replacement=out(500)), fx("g", "n", replacement=out(500))])
    res = evaluate(d)
    p = parity(res)
    assert p["f"]["effective_target"] is None and p["g"]["effective_target"] is None and p["f"]["served_output"] is None
    assert p["f"]["parity"] is False
    assert res["rollback_candidates"] == []


# ---------------------------------------------------------------- bounds (N / N+1)
def many_rules(n):
    return [R("r%d" % i, "GET", "exact", "/p%d" % i, "legacy") for i in range(n)]


def test_rule_count_bounds():
    evaluate(base(rules=many_rules(64), requests=[Q("q", "GET", "/p0")]))
    with pytest.raises(ValueError):
        evaluate(base(rules=many_rules(65)))
    with pytest.raises(ValueError):
        evaluate(base(rules=[]))


def test_request_count_bounds():
    evaluate(base(requests=[Q("q%d" % i, "GET", "/orders") for i in range(64)]))
    with pytest.raises(ValueError):
        evaluate(base(requests=[Q("q%d" % i, "GET", "/orders") for i in range(65)]))
    with pytest.raises(ValueError):
        evaluate(base(requests=[]))


def test_fixture_count_bounds():
    reqs = [Q("q%d" % i, "POST", "/orders") for i in range(64)]
    evaluate(base(requests=reqs, fixtures=[fx("f%d" % i, "q%d" % i) for i in range(64)]))
    with pytest.raises(ValueError):
        evaluate(base(requests=reqs + [Q("x", "POST", "/orders")], fixtures=[fx("f%d" % i, "q%d" % i) for i in range(64)] + [fx("fx", "x")]))
    evaluate(base(fixtures=[]))


def test_path_length_and_segment_bounds():
    p256 = "/" + "a" * 255
    p257 = "/" + "a" * 256
    evaluate(base(requests=[Q("q", "GET", p256)]))
    assert routes(evaluate(base(requests=[Q("q", "GET", p257)])))["q"]["decision"] == "refused"
    s16 = "/" + "/".join("a" * 1 for _ in range(16))
    s17 = s16 + "/a"
    s16_rules = [R("r16", "*", "prefix", "/a", "replacement")]
    r16 = routes(evaluate(base(rules=s16_rules, requests=[Q("q", "GET", s16)])))["q"]
    assert r16["decision"] == "routed" and r16["rule_id"] == "r16" and r16["target"] == "replacement" and r16["reasons"] == []
    assert routes(evaluate(base(requests=[Q("q", "GET", s17)])))["q"]["decision"] == "refused"
    with pytest.raises(ValueError):
        evaluate(base(rules=[R("r", "GET", "exact", p257, "legacy")]))
    with pytest.raises(ValueError):
        evaluate(base(rules=[R("r", "GET", "prefix", s17, "legacy")]))
    evaluate(base(rules=[R("r", "GET", "prefix", s16, "legacy")]))


def test_id_bounds_and_charset():
    evaluate(base(rules=[R("a" * 64, "GET", "exact", "/o", "legacy")]))
    for bad in ["a" * 65, "", "a b", "a/b", "é", 5, None, True]:
        with pytest.raises(ValueError):
            evaluate(base(rules=[R(bad, "GET", "exact", "/o", "legacy")]))
        with pytest.raises(ValueError):
            evaluate(base(requests=[Q(bad, "GET", "/o")]))


@pytest.mark.parametrize("status,ok", [(99, False), (100, True), (599, True), (600, False), (True, False), (False, False), (200.0, False), ("200", False), (None, False), (float("nan"), False)])
def test_status_bounds_nonboolean(status, ok):
    d = base(requests=[Q("q", "POST", "/orders")], fixtures=[fx("f", "q", legacy=out(status))])
    if ok:
        evaluate(d)
    else:
        with pytest.raises(ValueError):
            evaluate(d)


@pytest.mark.parametrize("body", [float("nan"), float("inf"), -float("inf"), {"a": float("nan")}, [1, [float("inf")]], {1: "x"}, {"a": {1, 2}}, (1, 2), b"x", object()])
def test_nonfinite_and_non_json_bodies_refused(body):
    d = base(requests=[Q("q", "POST", "/orders")], fixtures=[fx("f", "q", replacement=out(200, body))])
    with pytest.raises(ValueError):
        evaluate(d)


def nest(depth):
    v = 1
    for _ in range(depth):
        v = [v]
    return v


def test_body_depth_node_and_size_bounds():
    def run(body):
        evaluate(base(requests=[Q("q", "POST", "/orders")], fixtures=[fx("f", "q", legacy=out(200, body), replacement=out(200, body))]))
    run(nest(7))  # depth 8 including the scalar leaf
    with pytest.raises(ValueError):
        run(nest(8))
    run(list(range(255)))  # 256 nodes including the list itself
    with pytest.raises(ValueError):
        run(list(range(256)))
    run("x" * 4096)
    with pytest.raises(ValueError):
        run("x" * 4097)
    run({"k" * 64: 1})
    with pytest.raises(ValueError):
        run({"k" * 65: 1})


def test_large_integers_and_floats_finite_ok():
    d = base(requests=[Q("q", "POST", "/orders")], fixtures=[fx("f", "q", legacy=out(200, [1e308, -0.0, 2**70]), replacement=out(200, [1e308, -0.0, 2**70]))])
    assert parity(evaluate(d))["f"]["parity"] is True


# ---------------------------------------------------------------- duplicate / unknown references
def test_duplicate_ids_refused():
    with pytest.raises(ValueError, match="duplicate"):
        evaluate(base(rules=[R("a", "GET", "exact", "/a", "legacy"), R("a", "GET", "exact", "/b", "legacy")]))
    with pytest.raises(ValueError, match="duplicate"):
        evaluate(base(requests=[Q("a", "GET", "/orders"), Q("a", "GET", "/orders")]))
    with pytest.raises(ValueError, match="duplicate"):
        evaluate(base(fixtures=[fx("f", "q1"), fx("f", "q2")]))
    with pytest.raises(ValueError, match="duplicate"):
        evaluate(base(fixtures=[fx("f", "q1"), fx("g", "q1")]))  # two recordings for one request


def test_unknown_references_refused():
    with pytest.raises(ValueError, match="unknown"):
        evaluate(base(fixtures=[fx("f", "nope")]))
    with pytest.raises(ValueError, match="unknown"):
        evaluate(base(default_target="canary"))


@pytest.mark.parametrize("path,val", [("top", 1), ("rule", 1), ("req", 1), ("fix", 1), ("out", 1)])
def test_unknown_keys_refused(path, val):
    d = base(fixtures=[fx("f", "q2")])
    {"top": lambda: d.update(extra=val), "rule": lambda: d["rules"][0].update(extra=val), "req": lambda: d["requests"][0].update(extra=val),
     "fix": lambda: d["fixtures"][0].update(extra=val), "out": lambda: d["fixtures"][0]["legacy"].update(headers={})}[path]()
    with pytest.raises(ValueError):
        evaluate(d)


@pytest.mark.parametrize("bad", [None, [], "x", 3, {"targets": TARGETS}, base(rules="x"), base(requests="x"), base(fixtures="x"), base(rules=[1]), base(requests=[None]), base(fixtures=[[]]),
                                 base(rules=[R("a", "GET", "glob", "/x", "legacy")]), base(rules=[R("a", "get", "exact", "/x", "legacy")]), base(rules=[R("a", "FETCH", "exact", "/x", "legacy")])])
def test_malformed_top_level_refused(bad):
    with pytest.raises(ValueError):
        evaluate(bad)


def test_missing_fixture_outputs_refused():
    d = base(requests=[Q("q", "POST", "/orders")], fixtures=[fx("f", "q")])
    del d["fixtures"][0]["replacement"]
    with pytest.raises(ValueError):
        evaluate(d)
    d = base(requests=[Q("q", "POST", "/orders")], fixtures=[fx("f", "q")])
    d["fixtures"][0]["legacy"] = {"status": 200}
    with pytest.raises(ValueError):
        evaluate(d)


# ---------------------------------------------------------------- generated corpus vs oracle
PATH_POOL = ["/", "/a", "/a/b", "/a/b/c", "/ab", "/b", "/b/a", "/a/bc", "/c/d/e"]


def test_generated_corpus_matches_independent_oracle():
    rng = random.Random(695)
    checked = 0
    for _ in range(400):
        sel = set()
        rules = []
        for i in range(rng.randrange(1, 8)):
            kind = rng.choice(["exact", "prefix"])
            method = rng.choice(["*", "GET", "POST"])
            path = rng.choice(PATH_POOL)
            if (kind, method, path) in sel:
                continue
            sel.add((kind, method, path))
            rules.append(R("r%d" % i, method, kind, path, rng.choice(["legacy", "replacement"])))
        reqs = [Q("q%d" % j, m, p) for j, (m, p) in enumerate(itertools.product(["GET", "POST", "DELETE"], PATH_POOL))]
        d = {"targets": TARGETS, "rules": rules, "requests": reqs}
        try:
            res = evaluate(d)
        except ValueError as exc:
            assert "ambiguous_precedence" in str(exc)
            assert has_ambiguity(rules)
            continue
        assert not has_ambiguity(rules)
        for r in res["routes"]:
            q = next(x for x in reqs if x["id"] == r["request_id"])
            want = oracle_route(rules, q["method"], q["path"])
            if want is None:
                assert r["decision"] == "no_route"
            else:
                assert r["rule_id"] == want["id"] and r["target"] == want["target"], (rules, q)
            checked += 1
    assert checked > 3000


def overlap(a, b):
    if a["method"] != "*" and b["method"] != "*" and a["method"] != b["method"]:
        return False
    def covers(p, path):
        return p == "/" or path == p or path.startswith(p + "/")
    if a["match"] == "exact" and b["match"] == "exact":
        return a["path"] == b["path"]
    if a["match"] == "exact":
        return covers(b["path"], a["path"])
    if b["match"] == "exact":
        return covers(a["path"], b["path"])
    return covers(a["path"], b["path"]) or covers(b["path"], a["path"])


def pk(r):
    if r["match"] == "exact":
        return (1, 0)
    return (0, 0 if r["path"] == "/" else len(r["path"].strip("/").split("/")))


def has_ambiguity(rules):
    for a, b in itertools.combinations(rules, 2):
        if overlap(a, b) and a["target"] != b["target"]:
            ma, mb = a["method"] != "*", b["method"] != "*"
            a_dom = pk(a) >= pk(b) and ma >= mb
            b_dom = pk(b) >= pk(a) and mb >= ma
            if not (a_dom or b_dom):
                return True
    return False


def test_generated_parity_corpus_matches_independent_oracle():
    rng = random.Random(7)
    for _ in range(200):
        reqs = [Q("q%d" % i, "POST", "/orders") for i in range(5)]
        fixtures, expect = [], {}
        for i in range(5):
            body = rng.choice([1, "1", True, None, [1], {"a": 1}])
            body2 = rng.choice([1, "1", True, None, [1], {"a": 1}])
            s1, s2 = rng.choice([200, 201]), rng.choice([200, 201])
            fixtures.append(fx("f%d" % i, "q%d" % i, legacy=out(s1, body), replacement=out(s2, body2)))
            exp = (["body"] if json.dumps(body) != json.dumps(body2) else []) + (["status"] if s1 != s2 else [])
            expect["f%d" % i] = sorted(exp)
        res = evaluate(base(requests=reqs, fixtures=fixtures))
        for f, p in parity(res).items():
            assert p["mismatched_fields"] == expect[f] and p["parity"] == (not expect[f])


# ---------------------------------------------------------------- purity
def test_module_imports_are_pure():
    tree = ast.parse(MODULE_PATH.read_text())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add((n.module or "").split(".")[0])
    assert mods <= {"math", "re", "__future__", "typing"}, mods
    banned = {"eval", "exec", "compile", "__import__", "open", "getattr", "setattr", "globals", "locals"}
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not (called & banned), called & banned


def test_result_is_json_serialisable_and_finite():
    d = base(fixtures=[fx("f", "q2", legacy=out(200, [1.5]), replacement=out(200, [1.5]))])
    s = json.dumps(evaluate(d), allow_nan=False)
    assert "handler" in s


# ================================================================ R2 audit pins (tests only; runtime unchanged)
def ev(rules, requests, fixtures=None, default=None):
    d = {"targets": copy.deepcopy(TARGETS), "rules": rules, "requests": requests}
    if fixtures is not None:
        d["fixtures"] = fixtures
    if default is not None:
        d["default_target"] = default
    return evaluate(d)


def test_body_integer_bit_length_boundary_256_ok_257_refused():
    ok = (1 << 256) - 1
    bad = 1 << 256
    rules, reqs = [R("r", "*", "prefix", "/", "legacy")], [Q("q", "GET", "/x")]
    for v in (ok, -ok, 0, 1 << 255):
        ev(rules, reqs, [fx("f", "q", legacy=out(200, v), replacement=out(200, v))])
    for v in (bad, -bad, bad + 1):
        with pytest.raises(ValueError, match="body integer too large"):
            ev(rules, reqs, [fx("f", "q", legacy=out(200, v))])
        with pytest.raises(ValueError, match="body integer too large"):
            ev(rules, reqs, [fx("f", "q", replacement=out(200, [v]))])
    res = ev(rules, reqs, [fx("f", "q", legacy=out(200, ok), replacement=out(200, ok - 1))])
    assert res["parity"][0]["mismatched_fields"] == ["body"]


def reasons_for(path):
    return ev([R("r", "*", "prefix", "/", "legacy")], [Q("q", "GET", path)])["routes"][0]["reasons"]


@pytest.mark.parametrize("path", ["/a%20b", "/a%21", "/a%7B", "/a%80", "/a%FF", "/%C3%A9", "/a%20%20"])
def test_percent_escapes_that_are_allowed(path):
    assert reasons_for(path) == []


@pytest.mark.parametrize("path", ["/a%1F", "/a%00", "/a%0A", "/a%7F", "/a%41", "/a%7A", "/a%7E", "/a%2D", "/a%2E", "/a%30", "/a%5F",
                                  "/a%2F", "/a%5C", "/a%25", "/a%3F", "/a%23"])
def test_percent_escapes_that_are_ambiguous_are_refused(path):
    assert reasons_for(path) == ["ambiguous_percent_encoding"]


@pytest.mark.parametrize("path", ["/a%2", "/a%", "/a%GG", "/a%1f", "/a%7f", "/a%2g", "/a%%20"])
def test_malformed_or_lowercase_percent_escapes_refused(path):
    assert reasons_for(path) == ["bad_percent_encoding"]


def test_percent_hex_is_base_16_not_10():
    assert reasons_for("/a%10") == ["ambiguous_percent_encoding"]  # 0x10 control char; base 10 would read 10 (allowed)
    assert reasons_for("/a%20") == []  # 0x20 space; base 10 would read 20 (control char)
    assert reasons_for("/a%99") == []  # 0x99 allowed
    assert reasons_for("/a%7E") == ["ambiguous_percent_encoding"]


def test_percent_escape_in_rule_path_same_policy():
    evaluate(base(rules=[R("r", "GET", "exact", "/a%20b", "legacy")]))
    for bad in ("/a%1F", "/a%7F", "/a%41"):
        with pytest.raises(ValueError, match="ambiguous_percent_encoding"):
            evaluate(base(rules=[R("r", "GET", "exact", bad, "legacy")]))


def test_same_path_different_methods_do_not_overlap_or_conflict():
    for kind in ("exact", "prefix"):
        res = ev([R("a", "GET", kind, "/x", "legacy"), R("b", "POST", kind, "/x", "replacement")], [Q("q", "GET", "/x"), Q("p", "POST", "/x")])
        assert res["overlaps"] == []
        assert {r["request_id"]: r["rule_id"] for r in res["routes"]} == {"q": "a", "p": "b"}


def test_overlap_kind_labels_winner_and_direction_for_both_id_orders():
    cases = [
        # (rules, kind, winner, shadowed, targets_differ)
        ([("a", "*", "exact", "/x", "legacy"), ("b", "GET", "exact", "/x", "replacement")], "method_specific_vs_wildcard", "b", "a", True),
        ([("a", "GET", "exact", "/x", "legacy"), ("b", "*", "exact", "/x", "replacement")], "method_specific_vs_wildcard", "a", "b", True),
        ([("a", "*", "exact", "/x", "legacy"), ("b", "GET", "exact", "/x", "legacy")], "method_specific_vs_wildcard", "b", "a", False),
        ([("a", "*", "prefix", "/x", "legacy"), ("b", "*", "prefix", "/x/y", "replacement")], "prefix_vs_prefix", "b", "a", True),
        ([("a", "*", "prefix", "/x/y", "replacement"), ("b", "*", "prefix", "/x", "legacy")], "prefix_vs_prefix", "a", "b", True),
        ([("a", "GET", "prefix", "/x", "legacy"), ("b", "*", "prefix", "/x", "replacement")], "prefix_vs_prefix", "a", "b", True),
        ([("a", "*", "prefix", "/x", "legacy"), ("b", "GET", "exact", "/x/y", "replacement")], "exact_vs_prefix", "b", "a", True),
        ([("a", "GET", "exact", "/x/y", "replacement"), ("b", "*", "prefix", "/x", "legacy")], "exact_vs_prefix", "a", "b", True),
        ([("a", "*", "prefix", "/", "legacy"), ("b", "*", "prefix", "/x", "legacy")], "prefix_vs_prefix", "b", "a", False),
        ([("a", "*", "prefix", "/x", "legacy"), ("b", "*", "exact", "/", "legacy")], None, None, None, None),
    ]
    for rules, kind, winner, shadowed, differ in cases:
        rs = [R(*r) for r in rules]
        res = ev(rs, [Q("q", "GET", "/x")])
        if kind is None:
            assert res["overlaps"] == []
        else:
            assert res["overlaps"] == [{"kind": kind, "winner": winner, "shadowed": shadowed, "targets_differ": differ}], rules
        res2 = ev(list(reversed(rs)), [Q("q", "GET", "/x")])
        assert res2["overlaps"] == res["overlaps"]


def test_non_overlapping_prefixes_and_segment_boundary_produce_no_overlap():
    res = ev([R("a", "*", "prefix", "/x", "legacy"), R("b", "*", "prefix", "/xy", "replacement"), R("c", "*", "exact", "/xz", "legacy")], [Q("q", "GET", "/x")])
    assert res["overlaps"] == []


def test_dominance_and_ambiguity_both_orders():
    # more specific path but wildcard method vs less specific path but method-specific, different targets: ambiguous
    pairs = [
        (R("a", "*", "prefix", "/x/y", "legacy"), R("b", "GET", "prefix", "/x", "replacement")),
        (R("a", "*", "exact", "/x/y", "legacy"), R("b", "GET", "prefix", "/x", "replacement")),
        (R("a", "GET", "exact", "/x", "legacy"), R("b", "*", "exact", "/x", "legacy")),
    ]
    for a, b in pairs[:2]:
        for order in ((a, b), (b, a)):
            with pytest.raises(ValueError, match="ambiguous_precedence"):
                ev(list(order), [Q("q", "GET", "/x/y")])
        same = dict(b, target=a["target"])
        res = ev([a, same], [Q("q", "GET", "/x/y")])  # same target: allowed, recorded as not differing
        assert [o["targets_differ"] for o in res["overlaps"]] == [False]
    # dominating on both axes (or tied on one) is fine
    ok = ev([R("a", "GET", "exact", "/x", "legacy"), R("b", "*", "prefix", "/x", "replacement")], [Q("q", "GET", "/x")])
    assert ok["routes"][0]["rule_id"] == "a" and ok["overlaps"][0]["winner"] == "a"
    ok = ev([R("a", "GET", "prefix", "/x/y", "legacy"), R("b", "*", "prefix", "/x", "replacement")], [Q("q", "GET", "/x/y")])
    assert ok["routes"][0]["rule_id"] == "a"
    ok = ev([R("a", "*", "prefix", "/x/y", "legacy"), R("b", "*", "prefix", "/x", "replacement")], [Q("q", "GET", "/x/y")])
    assert ok["routes"][0]["rule_id"] == "a"


def test_equal_specificity_keys_never_overlap_exhaustive():
    """The 'equal key' tie in overlap winner selection is unreachable: prove it over a small universe."""
    paths = ["/", "/a", "/a/b", "/b", "/a/b/c"]
    rules = [(m, k, p) for m in ("*", "GET", "POST") for k in ("exact", "prefix") for p in paths]
    n = 0
    for (m1, k1, p1), (m2, k2, p2) in itertools.combinations(rules, 2):
        a, b = R("a", m1, k1, p1, "legacy"), R("b", m2, k2, p2, "replacement")
        try:
            res = ev([a, b], [Q("q", "GET", "/a")])
        except ValueError:
            continue  # duplicate selector or ambiguity refusals
        for o in res["overlaps"]:
            ka = (k1 == "exact", 0 if k1 == "exact" else 0 if p1 == "/" else p1.count("/"), m1 != "*")
            kb = (k2 == "exact", 0 if k2 == "exact" else 0 if p2 == "/" else p2.count("/"), m2 != "*")
            assert ka != kb
            assert o["winner"] == ("a" if ka > kb else "b")
            n += 1
    assert n > 100


def test_default_target_replacement_rollback_after_mismatch():
    reqs = [Q("q", "GET", "/nothing"), Q("r", "GET", "/o")]
    rules = [R("ro", "*", "exact", "/o", "legacy")]
    fixture_bad = fx("f1", "q", legacy=out(200, "a"), replacement=out(200, "b"))
    res = ev(rules, reqs, [fixture_bad], default="replacement")
    q = routes(res)["q"]
    assert (q["decision"], q["target"], q["rule_id"], q["handler"]) == ("default", "replacement", None, "new-app")
    assert res["rollback_candidates"] == ["@default"]
    assert res["rollback_effect"] == [{"request_id": "q", "rule_id": None, "before": "replacement", "after": "legacy"}]
    aq = {r["request_id"]: r for r in res["after_rollback_routes"]}["q"]
    assert (aq["decision"], aq["target"], aq["rule_id"], aq["handler"]) == ("default", "legacy", None, "old-app")
    ar = {r["request_id"]: r for r in res["after_rollback_routes"]}["r"]
    assert ar["target"] == "legacy" and ar["rule_id"] == "ro"
    # matching fixture: nothing to roll back; still replacement
    ok = ev(rules, reqs, [fx("f1", "q")], default="replacement")
    assert ok["rollback_candidates"] == [] and ok["rollback_effect"] == []
    assert {r["request_id"]: r for r in ok["after_rollback_routes"]}["q"]["target"] == "replacement"
    # no fixture: unverified default, no candidate
    nf = ev(rules, reqs, [], default="replacement")
    assert nf["unverified_replacement_rules"] == ["@default"] and nf["rollback_candidates"] == []
    # default legacy: never a candidate, stays legacy
    dl = ev(rules, reqs, [fixture_bad], default="legacy")
    assert dl["rollback_candidates"] == [] and routes(dl)["q"]["target"] == "legacy"
    assert {r["request_id"]: r for r in dl["after_rollback_routes"]}["q"]["target"] == "legacy"
    assert dl["unverified_replacement_rules"] == []


def test_default_golden_violation_alone_triggers_default_rollback():
    reqs = [Q("q", "GET", "/nothing")]
    rules = [R("ro", "*", "exact", "/o", "legacy")]
    g = {"parity": False, "mismatched_fields": ["body"]}
    res = ev(rules, reqs, [fx("f", "q", golden=g)], default="replacement")  # outputs match, golden claims mismatch
    assert res["golden_violations"] == ["f"] and res["rollback_candidates"] == ["@default"]
    assert res["after_rollback_routes"][0]["target"] == "legacy"


def test_request_echo_fields_valid_and_refused():
    res = ev([R("r", "*", "prefix", "/", "legacy")], [Q("a", "GET", "/ok"), Q("b", "get", "/ok"), Q("c", "GET", "/ok/"), Q("d", "Get", "ok"), Q("e", 7, "/ok")])
    r = routes(res)
    assert (r["a"]["method"], r["a"]["path"], r["a"]["reasons"], r["a"]["decision"]) == ("GET", "/ok", [], "routed")
    assert (r["b"]["method"], r["b"]["path"], r["b"]["reasons"], r["b"]["decision"], r["b"]["rule_id"], r["b"]["trace"]) == (
        None, "/ok", ["method_not_normalized_uppercase_http_method"], "refused", None, [])
    assert (r["c"]["method"], r["c"]["path"], r["c"]["reasons"]) == ("GET", None, ["trailing_slash_ambiguous"])
    assert (r["d"]["method"], r["d"]["path"], r["d"]["reasons"]) == (None, None, ["method_not_normalized_uppercase_http_method", "path_must_start_with_slash"])
    assert (r["e"]["method"], r["e"]["path"], r["e"]["reasons"]) == (None, "/ok", ["method_not_normalized_uppercase_http_method"])
    for k in ("a", "b", "c", "d", "e"):
        assert r[k]["request_id"] == k
    for k in ("b", "c", "d", "e"):
        assert r[k]["handler"] is None and r[k]["target"] is None
    assert r["a"]["handler"] == "old-app" and r["a"]["target"] == "legacy"


def test_golden_ok_is_exact_equality_over_all_field_subsets():
    fields = [[], ["body"], ["status"], ["body", "status"]]
    for actual in fields:
        for claimed in fields:
            legacy = out(200, "x")
            repl = out(200 if "status" not in actual else 201, "x" if "body" not in actual else "y")
            g = {"parity": not claimed, "mismatched_fields": list(reversed(claimed))}
            res = ev([R("r", "*", "prefix", "/", "legacy")], [Q("q", "GET", "/a")], [fx("f", "q", legacy=legacy, replacement=repl, golden=g)])
            p = res["parity"][0]
            assert p["mismatched_fields"] == actual and p["parity"] == (not actual)
            assert p["golden_ok"] is (sorted(claimed) == actual)
            assert res["golden_violations"] == ([] if sorted(claimed) == actual else ["f"])
    none = ev([R("r", "*", "prefix", "/", "legacy")], [Q("q", "GET", "/a")], [fx("f", "q")])
    assert none["parity"][0]["golden_ok"] is None and none["golden_violations"] == []


def test_golden_wrong_fields_with_consistent_parity_and_wrong_parity_rejected():
    rules, reqs = [R("r", "*", "prefix", "/", "legacy")], [Q("q", "GET", "/a")]
    # wrong mismatched_fields, internally consistent parity=False
    res = ev(rules, reqs, [fx("f", "q", legacy=out(200, "a"), replacement=out(200, "b"), golden={"parity": False, "mismatched_fields": ["status"]})])
    assert res["parity"][0]["golden_ok"] is False
    # golden says all good while outputs differ
    res = ev(rules, reqs, [fx("f", "q", legacy=out(200, "a"), replacement=out(200, "b"), golden={"parity": True, "mismatched_fields": []})])
    assert res["parity"][0]["golden_ok"] is False
    # golden claims mismatch while outputs equal
    res = ev(rules, reqs, [fx("f", "q", golden={"parity": False, "mismatched_fields": ["body"]})])
    assert res["parity"][0]["golden_ok"] is False
    # internally inconsistent golden is refused outright
    for g in ({"parity": True, "mismatched_fields": ["body"]}, {"parity": False, "mismatched_fields": []}):
        with pytest.raises(ValueError, match="golden parity contradicts"):
            ev(rules, reqs, [fx("f", "q", golden=g)])


CLEAN = ["fixture_parity_compares_recorded_outputs_only", "no_production_traffic_or_handler_execution_observed"]


def test_legacy_removal_blockers_each_only_under_its_cause():
    leg = R("l", "*", "exact", "/old", "legacy")
    rep = R("n", "*", "exact", "/new", "replacement")
    clean = ev([leg], [Q("q", "GET", "/old")])
    assert clean["legacy_removal_blockers"] == sorted(CLEAN) and clean["legacy_removal_safe"] is False

    refused = ev([leg], [Q("q", "GET", "/old"), Q("bad", "get", "/old")])
    assert refused["legacy_removal_blockers"] == sorted(CLEAN + ["refused_requests_present"])

    unrouted = ev([leg], [Q("q", "GET", "/old"), Q("u", "GET", "/missing")])
    assert unrouted["legacy_removal_blockers"] == sorted(CLEAN + ["unrouted_requests_present"])

    both = ev([leg], [Q("q", "GET", "/old"), Q("u", "GET", "/missing"), Q("bad", "get", "/old")])
    assert both["legacy_removal_blockers"] == sorted(CLEAN + ["refused_requests_present", "unrouted_requests_present"])

    no_fix = ev([leg, rep], [Q("q", "GET", "/old"), Q("n", "GET", "/new")])
    assert no_fix["legacy_removal_blockers"] == sorted(CLEAN + ["replacement_routes_without_fixture"])

    verified = ev([leg, rep], [Q("q", "GET", "/old"), Q("n", "GET", "/new")], [fx("f", "n")])
    assert verified["legacy_removal_blockers"] == sorted(CLEAN) and verified["unverified_replacement_rules"] == []

    # default (no_route avoided) with replacement default and no fixture counts as unverified too
    dflt = ev([leg], [Q("q", "GET", "/old"), Q("u", "GET", "/x")], default="replacement")
    assert dflt["legacy_removal_blockers"] == sorted(CLEAN + ["replacement_routes_without_fixture"])
    dflt_leg = ev([leg], [Q("q", "GET", "/old"), Q("u", "GET", "/x")], default="legacy")
    assert dflt_leg["legacy_removal_blockers"] == sorted(CLEAN)

    mism = ev([leg, rep], [Q("q", "GET", "/old"), Q("n", "GET", "/new")], [fx("f", "n", replacement=out(500, "x"))])
    assert mism["legacy_removal_blockers"] == sorted(CLEAN + ["parity_mismatch_present"])
    mism_legacy_routed = ev([leg], [Q("q", "GET", "/old")], [fx("f", "q", replacement=out(200, "other"))])
    assert mism_legacy_routed["legacy_removal_blockers"] == sorted(CLEAN + ["parity_mismatch_present"])

    golden = ev([leg, rep], [Q("q", "GET", "/old"), Q("n", "GET", "/new")],
                [fx("f", "n", golden={"parity": False, "mismatched_fields": ["body"]})])
    assert golden["legacy_removal_blockers"] == sorted(CLEAN + ["golden_violation_present"])

    # fixture on a refused request: parity is computed against recorded outputs, no routing blocker added except refusal
    on_refused = ev([leg], [Q("bad", "get", "/old")], [fx("f", "bad")])
    assert on_refused["legacy_removal_blockers"] == sorted(CLEAN + ["refused_requests_present"])
    # matching fixtures everywhere and fixture covering a no-route request
    on_unrouted = ev([leg], [Q("u", "GET", "/missing")], [fx("f", "u")])
    assert on_unrouted["legacy_removal_blockers"] == sorted(CLEAN + ["unrouted_requests_present"])


# ================================================================ R3 audit pins (tests only; runtime unchanged)
def test_path_length_256_ok_257_refused_for_rule_and_request():
    p256, p257 = "/" + "a" * 255, "/" + "a" * 256
    assert len(p256) == 256 and len(p257) == 257
    for kind in ("exact", "prefix"):
        evaluate(base(rules=[R("r", "GET", kind, p256, "legacy")]))
        with pytest.raises(ValueError, match="^rule r path refused: path_length$"):
            evaluate(base(rules=[R("r", "GET", kind, p257, "legacy")]))
    ok = routes(ev([R("r", "*", "exact", p256, "legacy")], [Q("q", "GET", p256)]))["q"]
    assert ok["decision"] == "routed" and ok["reasons"] == [] and ok["path"] == p256
    bad = routes(ev([R("r", "*", "prefix", "/", "legacy")], [Q("q", "GET", p257)]))["q"]
    assert bad["decision"] == "refused" and bad["reasons"] == ["path_length"] and bad["path"] is None and bad["method"] == "GET"


def test_empty_path_refused_with_path_length_for_rule_and_request():
    with pytest.raises(ValueError, match="^rule r path refused: path_length$"):
        evaluate(base(rules=[R("r", "GET", "exact", "", "legacy")]))
    with pytest.raises(ValueError, match="^rule r path refused: path_length$"):
        evaluate(base(rules=[R("r", "GET", "prefix", "", "legacy")]))
    bad = routes(ev([R("r", "*", "prefix", "/", "legacy")], [Q("q", "GET", "")]))["q"]
    assert bad["decision"] == "refused" and bad["reasons"] == ["path_length"] and bad["path"] is None
    one = routes(ev([R("r", "*", "prefix", "/", "legacy")], [Q("q", "GET", "/")]))["q"]
    assert one["decision"] == "routed" and one["reasons"] == []


def _dict_nest(levels):
    v = 1
    for _ in range(levels):
        v = {"k": v}
    return v


def test_dict_nesting_depth_boundary_7_ok_8_refused_in_either_output():
    def run(legacy, replacement=None):
        return ev([R("r", "*", "prefix", "/", "legacy")], [Q("q", "POST", "/x")],
                  [fx("f", "q", legacy=out(200, legacy), replacement=out(200, legacy if replacement is None else replacement))])
    run(_dict_nest(7))
    run({"a": [{"b": [{"c": [{"d": 1}]}]}]})  # mixed dict/list, depth 8 with the leaf
    for body in (_dict_nest(8), _dict_nest(9), {"a": [{"b": [{"c": [{"d": [1]}]}]}]}):
        with pytest.raises(ValueError, match="^body exceeds depth 8 or 256 nodes$"):
            run(body)
        with pytest.raises(ValueError, match="^body exceeds depth 8 or 256 nodes$"):
            run(1, body)
    res = run(_dict_nest(7), _dict_nest(6))
    assert res["parity"][0]["mismatched_fields"] == ["body"]
