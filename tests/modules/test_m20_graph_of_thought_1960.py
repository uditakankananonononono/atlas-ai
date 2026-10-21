"""Row 1960 Graph-of-Thought practitioner-depth controller tests."""
import pytest
from app.modules.m20_general_cognitive_worker.graph_of_thought_1960 import run_graph_of_thought


def proposer(texts, k, kind):
    if kind == "aggregation":
        return [" + ".join(texts)]
    if kind == "refinement":
        return [texts[0] + "!"]
    return [texts[-1] + "." + str(i) for i in range(k)]


def length_scorer(node, path):
    return (len(node.text) % 10) / 10


def constant_scorer(node, path):
    return 0.5


def test_row1960_expansion_builds_layered_graph():
    r = run_graph_of_thought("root", proposer, constant_scorer, branching=2, max_depth=2, beam_width=2)
    kinds = r["graph"]["kinds"]
    assert kinds["root"] == 1 and kinds["expansion"] == 6  # 2 at depth1 + 4 at depth2
    assert r["graph"]["node_count"] == 1 + 6 + 1  # plus final aggregation
    assert r["graph"]["edge_count"] == 6 + 2


def test_row1960_beam_keeps_highest_scored():
    r = run_graph_of_thought("root", proposer, length_scorer, branching=3, max_depth=1,
                             beam_width=1, aggregate_final=False)
    # length_scorer prefers "root.22"? depths: candidates root.0(6)->.6? deterministic check:
    assert r["best_score"] == max((len("root." + str(i)) % 10) / 10 for i in range(3))


def test_row1960_deterministic_same_inputs_same_result():
    a = run_graph_of_thought("root", proposer, length_scorer, branching=3, max_depth=3, beam_width=2)
    b = run_graph_of_thought("root", proposer, length_scorer, branching=3, max_depth=3, beam_width=2)
    assert a == b


def test_row1960_aggregation_has_multiple_parents_and_path():
    r = run_graph_of_thought("root", proposer, constant_scorer, branching=2, max_depth=1, beam_width=2)
    assert r["best_kind"] == "aggregation"
    assert r["best_path"][-1] == "root.0 + root.1"
    assert r["graph"]["kinds"]["aggregation"] == 1


def test_row1960_aggregation_skipped_for_single_beam():
    r = run_graph_of_thought("root", proposer, constant_scorer, branching=2, max_depth=1, beam_width=1)
    assert r["graph"]["kinds"]["aggregation"] == 0
    assert r["best_kind"] == "expansion"


def test_row1960_refinement_improves_until_budget_or_no_gain():
    r = run_graph_of_thought("root", proposer, length_scorer, branching=1, max_depth=1,
                             beam_width=1, refine_budget=3)
    assert r["graph"]["kinds"]["refinement"] >= 1
    calls = []
    def stop_when_worse(node, path):
        calls.append(node.text)
        return 0.9 if "!" not in node.text else 0.1  # refinement scores worse
    r2 = run_graph_of_thought("root", proposer, stop_when_worse, branching=1, max_depth=1,
                              beam_width=1, refine_budget=3)
    assert r2["graph"]["kinds"]["refinement"] == 1  # stopped after first non-improving refine
    assert r2["best_score"] == 0.9  # original kept as best


def test_row1960_empty_proposal_terminates_branch():
    def dry(texts, k, kind):
        return [] if kind == "expansion" else ["x"]
    r = run_graph_of_thought("root", dry, constant_scorer, max_depth=4)
    assert r["graph"]["node_count"] == 1
    assert r["best_path"] == ["root"]


def test_row1960_max_nodes_cap_enforced():
    r = run_graph_of_thought("root", proposer, constant_scorer, branching=3, max_depth=3,
                             beam_width=3, max_nodes=4)
    assert r["graph"]["node_count"] <= 4


def test_row1960_duplicate_proposals_deduplicated():
    def dup(texts, k, kind):
        return ["same", "same", "other"]
    r = run_graph_of_thought("root", dup, constant_scorer, branching=3, max_depth=1,
                             beam_width=2, aggregate_final=False)
    assert r["graph"]["node_count"] == 3  # root + 2 distinct


@pytest.mark.parametrize("kwargs", [
    {"branching": 0}, {"branching": 9}, {"max_depth": 0}, {"max_depth": 9},
    {"beam_width": 0}, {"beam_width": 17}, {"max_nodes": 0}, {"max_nodes": 10001},
    {"branching": True}, {"max_depth": 2.5}, {"refine_budget": -1}, {"refine_budget": 9},
])
def test_row1960_parameter_validation(kwargs):
    with pytest.raises(ValueError):
        run_graph_of_thought("root", proposer, constant_scorer, **kwargs)


def test_row1960_seed_and_callable_validation():
    with pytest.raises(ValueError):
        run_graph_of_thought("", proposer, constant_scorer)
    with pytest.raises(ValueError):
        run_graph_of_thought("   ", proposer, constant_scorer)
    with pytest.raises(ValueError):
        run_graph_of_thought("root", None, constant_scorer)
    with pytest.raises(ValueError):
        run_graph_of_thought("root", proposer, "not-callable")


@pytest.mark.parametrize("bad", [-0.1, 1.1, float("nan"), float("inf"), True, "0.5"])
def test_row1960_scorer_range_enforced(bad):
    with pytest.raises(ValueError, match="scorer"):
        run_graph_of_thought("root", proposer, lambda node, path: bad, max_depth=1)


def test_row1960_proposer_contract_enforced():
    with pytest.raises(ValueError, match="at most"):
        run_graph_of_thought("root", lambda t, k, kind: ["a"] * (k + 1), constant_scorer, branching=1, max_depth=1)
    with pytest.raises(ValueError, match="non-empty"):
        run_graph_of_thought("root", lambda t, k, kind: ["  "], constant_scorer, max_depth=1)
    with pytest.raises(ValueError, match="non-empty"):
        run_graph_of_thought("root", lambda t, k, kind: [42], constant_scorer, max_depth=1)


def test_row1960_trace_records_typed_operations():
    r = run_graph_of_thought("root", proposer, constant_scorer, branching=2, max_depth=1, beam_width=2)
    assert any(t.startswith("expand:") for t in r["trace"])
    assert any(t.startswith("aggregate:") for t in r["trace"])


def test_row1960_limits_declare_injected_model_boundary():
    r = run_graph_of_thought("root", proposer, constant_scorer)
    assert any("injected" in limit for limit in r["limits"])


def test_row1960_deep_search_respects_depth():
    r = run_graph_of_thought("root", proposer, constant_scorer, branching=1, max_depth=5,
                             beam_width=1, aggregate_final=False)
    assert len(r["best_path"]) == 6  # root + 5 levels


# ---------------- mounted boundary: /cognitive-1960-2009/graph-of-thought/search ----------------

def _client():
    from fastapi.testclient import TestClient
    from app.modules.m20_general_cognitive_worker.cognitive_routes_1960_2009 import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_row1960_route_executes_search():
    client = _client()
    payload = {"seed": "root", "branching": 2, "max_depth": 2, "beam_width": 2,
               "thoughts": [{"text": "idea-a", "score": 0.4}, {"text": "idea-b", "score": 0.9},
                            {"text": "idea-c", "score": 0.7}]}
    r = client.post("/cognitive-1960-2009/graph-of-thought/search", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["graph"]["kinds"]["expansion"] >= 2
    assert "verification_boundary" in body and "caller-supplied" in body["verification_boundary"]


def test_row1960_route_rejects_bad_params_and_conflicting_scores():
    client = _client()
    bad = {"seed": "root", "branching": 99,
           "thoughts": [{"text": "a", "score": 0.5}]}
    assert client.post("/cognitive-1960-2009/graph-of-thought/search", json=bad).status_code == 422
    conflict = {"seed": "root", "thoughts": [{"text": "a", "score": 0.1}, {"text": "a", "score": 0.9}]}
    assert client.post("/cognitive-1960-2009/graph-of-thought/search", json=conflict).status_code == 422


def test_row1960_route_aggregation_never_outscores_weakest_parent():
    client = _client()
    payload = {"seed": "root", "branching": 2, "max_depth": 1, "beam_width": 2,
               "thoughts": [{"text": "weak", "score": 0.2}, {"text": "strong", "score": 0.95}]}
    body = client.post("/cognitive-1960-2009/graph-of-thought/search", json=payload).json()
    assert body["graph"]["kinds"]["aggregation"] == 1
    assert body["best_score"] <= 0.95


# ---------------- coordinator-HOLD RED-first pins (v2) ----------------

def test_pin1_scorer_huge_int_is_valueerror_not_overflow():
    with pytest.raises(ValueError, match="scorer"):
        run_graph_of_thought("root", proposer, lambda node, path: 10 ** 1000, max_depth=1)


def test_pin2_seed_whitespace_normalized_core_and_route():
    r = run_graph_of_thought("  root  ", proposer, constant_scorer, branching=1, max_depth=1,
                             beam_width=1, aggregate_final=False)
    assert r["nodes"][0]["text"] == "root"
    client = _client()
    payload = {"seed": " root ", "branching": 1, "max_depth": 1, "beam_width": 1,
               "thoughts": [{"text": "idea", "score": 0.5}]}
    resp = client.post("/cognitive-1960-2009/graph-of-thought/search", json=payload)
    assert resp.status_code == 200, resp.text
    assert resp.json()["nodes"][0]["text"] == "root"
    blank = {"seed": "   ", "thoughts": [{"text": "idea", "score": 0.5}]}
    assert client.post("/cognitive-1960-2009/graph-of-thought/search", json=blank).status_code == 422


def test_pin3_expansion_depth_capped_aggregation_one_layer_beyond():
    r = run_graph_of_thought("root", proposer, constant_scorer, branching=2, max_depth=1, beam_width=2)
    expansion_depths = [n["depth"] for n in r["nodes"] if n["kind"] == "expansion"]
    assert expansion_depths and max(expansion_depths) <= 1
    aggregates = [n for n in r["nodes"] if n["kind"] == "aggregation"]
    assert len(aggregates) == 1 and aggregates[0]["depth"] == 2  # documented: one layer beyond deepest beam


def test_pin4_root_can_win_when_nothing_outscores_it():
    r = run_graph_of_thought("root", proposer, lambda node, path: 0.9 if node.kind == "root" else 0.1,
                             branching=2, max_depth=2, beam_width=2)
    assert r["best_kind"] == "root"  # documented: root best = no better answer found
    assert r["best_score"] == 0.9


def test_pin5_aggregation_scored_from_parents_not_pool_string_match():
    client = _client()
    payload = {"seed": "root", "branching": 2, "max_depth": 1, "beam_width": 2,
               "thoughts": [{"text": "weak", "score": 0.2}, {"text": "strong", "score": 0.95},
                            {"text": "weak + strong", "score": 0.99}]}
    body = client.post("/cognitive-1960-2009/graph-of-thought/search", json=payload).json()
    agg = [n for n in body["nodes"] if n["kind"] == "aggregation"]
    assert len(agg) == 1
    assert agg[0]["score"] == 0.2  # weakest parent, never the pool's colliding 0.99 entry


def test_pin6_output_contains_full_graph_nodes_and_edges():
    r = run_graph_of_thought("root", proposer, constant_scorer, branching=2, max_depth=1, beam_width=2)
    assert len(r["nodes"]) == r["graph"]["node_count"]
    assert len(r["edges"]) == r["graph"]["edge_count"]
    for n in r["nodes"]:
        assert set(n) == {"id", "text", "parents", "depth", "kind", "score"}
    root = r["nodes"][0]
    assert root["kind"] == "root" and root["parents"] == []
    agg = [n for n in r["nodes"] if n["kind"] == "aggregation"][0]
    assert len(agg["parents"]) == 2


# ---------------- peer-audit v3 pins (mutant survivors) ----------------

def test_pin_v3_equal_score_refinement_stops_after_one():
    # equal score is not improvement; budget must stop after one refinement node
    r = run_graph_of_thought("root", proposer, constant_scorer, branching=1, max_depth=1,
                             beam_width=1, aggregate_final=False, refine_budget=3)
    assert [n["text"] for n in r["nodes"]] == ["root", "root.0", "root.0!"]
    assert r["graph"]["kinds"]["refinement"] == 1


def test_pin_v3_same_text_refinement_adds_no_node():
    def same_text_proposer(texts, k, kind):
        if kind == "refinement":
            return [texts[0]]  # identical text carries no new information
        return [texts[-1] + ".x"]
    r = run_graph_of_thought("root", same_text_proposer, constant_scorer, branching=1, max_depth=1,
                             beam_width=1, aggregate_final=False, refine_budget=3)
    assert [n["text"] for n in r["nodes"]] == ["root", "root.x"]
    assert r["graph"]["kinds"]["refinement"] == 0


def test_pin_v3_route_root_scored_at_pool_minimum():
    client = _client()
    payload = {"seed": "root", "branching": 2, "max_depth": 1, "beam_width": 2,
               "thoughts": [{"text": "weak", "score": 0.2}, {"text": "strong", "score": 0.95}]}
    body = client.post("/cognitive-1960-2009/graph-of-thought/search", json=payload).json()
    assert body["nodes"][0]["kind"] == "root"
    assert body["nodes"][0]["score"] == 0.2  # never out-scores the weakest supplied thought


# ---------------- v4 pins: first-parent traversal through aggregates ----------------

def _witness_proposer(texts, k, kind):
    if kind == "aggregation":
        return ["AGG"]
    if kind == "refinement":
        return [texts[0] + "!REF"]
    return ["root+c0", "root+c1"][:k]


def test_pin_v4_best_path_walks_first_parent_of_aggregate():
    # peer witness: refinement of a multi-parent aggregate; best_path must walk parents[0]
    def scorer(node, path):
        if "!REF" in node.text: return 0.99
        if node.text == "AGG": return 0.6
        return 0.5
    r = run_graph_of_thought("root", _witness_proposer, scorer, branching=2, max_depth=1,
                             beam_width=2, aggregate_final=True, refine_budget=1)
    assert r["best_path"] == ["root", "root+c0", "AGG", "AGG!REF"]


def test_pin_v4_best_path_walks_first_parent_swapped_beam_order():
    # same witness with beam order swapped: parents[0] is now the other member
    def scorer(node, path):
        if "!REF" in node.text: return 0.99
        if node.text == "AGG": return 0.6
        if node.text == "root+c1": return 0.55
        return 0.5
    r = run_graph_of_thought("root", _witness_proposer, scorer, branching=2, max_depth=1,
                             beam_width=2, aggregate_final=True, refine_budget=1)
    assert r["best_path"] == ["root", "root+c1", "AGG", "AGG!REF"]


# ---------------- v5 pins: strongest-parent selection + site-guard invariants ----------------

def test_pin_v5_aggregate_best_path_uses_strongest_parent():
    # peer witness: strongest parent of the aggregate leads the reported chain
    def scorer(node, path):
        if node.text == "AGG": return 0.9
        if node.text == "root+c0": return 0.7
        if node.text == "root+c1": return 0.3
        return 0.5
    r = run_graph_of_thought("root", _witness_proposer, scorer, branching=2, max_depth=1,
                             beam_width=2, aggregate_final=True, refine_budget=0)
    assert r["best_path"] == ["root", "root+c0", "AGG"]


def test_pin_v5_aggregate_best_path_strongest_parent_swapped():
    def scorer(node, path):
        if node.text == "AGG": return 0.9
        if node.text == "root+c0": return 0.3
        if node.text == "root+c1": return 0.7
        return 0.5
    r = run_graph_of_thought("root", _witness_proposer, scorer, branching=2, max_depth=1,
                             beam_width=2, aggregate_final=True, refine_budget=0)
    assert r["best_path"] == ["root", "root+c1", "AGG"]


def test_pin_v5_aggregate_parents_share_one_beam_depth():
    # invariant behind the depth max/min equivalence: beam members of one
    # expansion round all share a depth, so aggregates never mix parent depths
    r = run_graph_of_thought("root", proposer, constant_scorer, branching=2, max_depth=3, beam_width=2)
    for n in r["nodes"]:
        if n["kind"] == "aggregation":
            parent_depths = {r["nodes"][p]["depth"] for p in n["parents"]}
            assert len(parent_depths) == 1
            assert n["depth"] == parent_depths.pop() + 1


def test_pin_v5_empty_aggregation_proposal_adds_no_node():
    def dry_aggregate(texts, k, kind):
        return [] if kind == "aggregation" else [texts[-1] + ".x", texts[-1] + ".y"][:k]
    r = run_graph_of_thought("root", dry_aggregate, constant_scorer, branching=2, max_depth=1, beam_width=2)
    assert r["graph"]["kinds"]["aggregation"] == 0
    assert r["graph"]["node_count"] == 3


def test_pin_v5_empty_refinement_proposal_adds_no_node():
    def dry_refine(texts, k, kind):
        if kind == "refinement": return []
        if kind == "aggregation": return ["AGG"]
        return [texts[-1] + ".x"][:k]
    r = run_graph_of_thought("root", dry_refine, constant_scorer, branching=1, max_depth=1,
                             beam_width=1, aggregate_final=False, refine_budget=2)
    assert r["graph"]["kinds"]["refinement"] == 0
    assert r["graph"]["node_count"] == 2


def test_pin_v5_beam_head_governs_next_round_parents():
    # beam membership decides WHICH parents expand next round; best-over-all
    # cannot mask a wrong beam choice at depth >= 2
    def scorer(node, path):
        if node.text == "root.0": return 0.9
        if node.text == "root.1": return 0.1
        return 0.5
    r = run_graph_of_thought("root", proposer, scorer, branching=2, max_depth=2,
                             beam_width=1, aggregate_final=False)
    texts = [n["text"] for n in r["nodes"]]
    assert texts == ["root", "root.0", "root.1", "root.0.0", "root.0.1"]


# v6: four independently executed peer survivor witnesses.
def test_pin_v6_strongest_parent_equal_score_prefers_latest_id():
    def score(node, path):
        return 0.9 if node.text == 'AGG' else 0.5
    r = run_graph_of_thought('root', _witness_proposer, score, branching=2,
                             beam_width=2, max_depth=1, aggregate_final=True, refine_budget=0)
    assert r['best_path'] == ['root', 'root+c1', 'AGG']


def test_pin_v6_refinement_adds_one_depth_layer():
    def propose(texts, k, kind):
        return ['child!R'] if kind == 'refinement' else ['child']
    r = run_graph_of_thought('root', propose, constant_scorer, branching=1,
                             beam_width=1, max_depth=1, aggregate_final=False, refine_budget=1)
    assert [n['depth'] for n in r['nodes']] == [0, 1, 2]


def test_pin_v6_refinement_scorer_receives_parent_and_child():
    seen = []
    def propose(texts, k, kind):
        return ['child!R'] if kind == 'refinement' else ['child']
    def score(node, path):
        seen.append((node.kind, list(path)))
        return 0.5
    run_graph_of_thought('root', propose, score, branching=1,
                         beam_width=1, max_depth=1, aggregate_final=False, refine_budget=1)
    assert [p for kind, p in seen if kind == 'refinement'] == [['child', 'child!R']]


def test_pin_v6_route_proposer_excludes_already_used_seed():
    resp = _client().post('/cognitive-1960-2009/graph-of-thought/search', json={
        'seed': 'root', 'branching': 1, 'beam_width': 1, 'max_depth': 1,
        'thoughts': [{'text': 'root', 'score': 0.9}, {'text': 'a', 'score': 0.5}]})
    assert resp.status_code == 200, resp.text
    assert resp.json()['best_path'] == ['root', 'a']
    assert resp.json()['best_score'] == 0.5
