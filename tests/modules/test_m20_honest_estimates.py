"""M20 planning/outcome estimates must come from recorded evidence.

Replays the audit's failing probes against the baseline (313309b): the old
HeuristicOutcomeModel returned .9/.75/.55/.4 by risk tier and ignored the
action text; the old ruminator scored random orderings with a hard-coded
0.9-0.1*attempts; BoundedMCTS used the same fixed prior; MetaReasoner used
constants. Here every number must change when the recorded episodes change,
and must be unavailable (None) when there is too little evidence.
"""
import asyncio

import pytest

from app.modules.m20_general_cognitive_worker import metacognition, mcts as mcts_mod
from app.modules.m20_general_cognitive_worker.episodic_memory import EpisodicMemory
from app.modules.m20_general_cognitive_worker.evidence import ToolEvidence, wilson_interval
from app.modules.m20_general_cognitive_worker.executive import MCTSRuminator, MetaReasoner
from app.modules.m20_general_cognitive_worker.mcts import BoundedMCTS
from app.modules.m20_general_cognitive_worker.metacognition import (
    CounterfactualEngine, EvidenceOutcomeModel,
)
from app.modules.m20_general_cognitive_worker.schemas import (
    ActionRecord, Episode, EpisodeOutcome, PlanNode, Risk, TaskState,
)


def episodes_for(**tool_outcomes):
    """tool -> list[bool] of recorded action successes."""
    eps = []
    for tool, outcomes in tool_outcomes.items():
        eps.append(Episode(
            task_id=f"t-{tool}", goal=f"use {tool}",
            actions=[ActionRecord(tool=tool, succeeded=ok) for ok in outcomes],
            outcome=EpisodeOutcome.SUCCEEDED,
        ))
    return eps


# -- the old fixed tables are gone -------------------------------------------------

def test_fixed_prior_symbols_are_removed():
    assert not hasattr(metacognition, "HeuristicOutcomeModel")
    assert not hasattr(mcts_mod, "_success_probability")
    assert not hasattr(mcts_mod, "RISK_COST")


# -- counterfactuals ---------------------------------------------------------------

def test_counterfactual_same_risk_different_actions_get_different_evidence():
    ev = ToolEvidence(episodes_for(send_email=[True] * 9 + [False], post_tweet=[True] * 2 + [False] * 4))
    engine = CounterfactualEngine(EvidenceOutcomeModel(ev))
    ep = episodes_for(deploy=[False])[0]
    out = engine.simulate(ep, [
        {"action": "send_email to ceo", "risk": "external"},
        {"action": "post_tweet about launch", "risk": "external"},
        {"action": "paste a dog photo", "risk": "external"},
        {"action": "do nothing", "risk": "external"},
    ])
    probs = [a["estimated_success_probability"] for a in out["alternatives"]]
    assert probs[0] == 0.9 and probs[1] == pytest.approx(0.333, abs=1e-3)
    assert probs[2] is None and probs[3] is None  # old code returned .55 for all four
    assert out["best_alternative"]["alternative_action"] == "send_email to ceo"
    assert out["unestimated_alternatives"] == 2
    first = out["alternatives"][0]["estimate"]
    assert (first["successes"], first["samples"]) == (9, 10)
    low, high = wilson_interval(9, 10)
    assert first["interval_95"] == [round(low, 4), round(high, 4)]
    assert "no success estimate" in out["alternatives"][2]["lesson"]


def test_counterfactual_estimate_changes_when_history_changes():
    eps = EpisodicMemory()
    for e in episodes_for(send_email=[True, True, True]):
        eps.record(e)
    engine = CounterfactualEngine(EvidenceOutcomeModel(ToolEvidence(eps.episodes)))
    ep = episodes_for(x=[False])[0]
    alt = [{"action": "send_email", "risk": "external"}]
    assert engine.simulate(ep, alt)["alternatives"][0]["estimated_success_probability"] == 1.0
    for e in episodes_for(send_email=[False, False, False, False, False, False, False]):
        eps.record(e)
    assert engine.simulate(ep, alt)["alternatives"][0]["estimated_success_probability"] == 0.3


def test_counterfactual_below_minimum_samples_is_unavailable_with_counts():
    ev = ToolEvidence(episodes_for(send_email=[True, True]), min_samples=3)
    est = ev.for_tool("send_email")
    assert not est.available and (est.successes, est.samples) == (2, 2)
    assert "need at least 3" in est.basis


def test_counterfactual_does_not_guess_when_text_names_several_tools():
    ev = ToolEvidence(episodes_for(a_tool=[True] * 3, b_tool=[False] * 3))
    est = ev.for_action_text("run a_tool then b_tool")
    assert not est.available and "several recorded tools" in est.basis


def test_custom_float_model_is_labelled_unverified():
    class Mine:
        def estimate(self, action, risk, *, tool=None):
            return 0.77

    out = CounterfactualEngine(Mine()).simulate(
        episodes_for(x=[False])[0], [{"action": "a", "risk": "read"}])
    est = out["alternatives"][0]["estimate"]
    assert est["value"] == 0.77 and "cannot verify" in est["basis"]


# -- MetaReasoner ------------------------------------------------------------------

def test_meta_reasoner_ranks_within_tier_by_observed_rate_and_flags_missing_evidence():
    ev = ToolEvidence(episodes_for(good=[True] * 5, bad=[True, False, False, False]))
    meta = MetaReasoner(ev)
    bad = PlanNode(title="bad step", tool="bad", risk=Risk.READ)
    unknown = PlanNode(title="unknown step", tool="never_seen", risk=Risk.READ)
    good = PlanNode(title="good step", tool="good", risk=Risk.READ)
    send = PlanNode(title="send", tool="good", risk=Risk.EXTERNAL)
    ranked = meta.score_candidates([send, bad, unknown, good])
    assert [c.node.title for c in ranked] == ["good step", "bad step", "unknown step", "send"]
    assert ranked[0].score == 1.0 and ranked[1].score == 0.25
    assert ranked[2].score is None and ranked[2].information_gain is None
    assert "observed success rate 5/5" in ranked[0].ranking_basis


def test_meta_reasoner_ignores_attempt_count_constants():
    meta = MetaReasoner(ToolEvidence(episodes_for(t=[True] * 3)))
    a = PlanNode(title="a", tool="t", attempts=0)
    b = PlanNode(title="b", tool="t", attempts=2)
    scores = [c.score for c in meta.score_candidates([a, b])]
    assert scores == [1.0, 1.0]  # evidence only; no 0.5+0.1*ltm_hits-0.1*attempts


# -- search ------------------------------------------------------------------------

def _plan():
    a = PlanNode(title="fetch", tool="fetcher", risk=Risk.READ)
    b = PlanNode(title="parse", tool="parser", risk=Risk.READ)
    return [a, b]


def test_mcts_rollouts_follow_recorded_failure_rates():
    plan = _plan()
    reliable = BoundedMCTS(max_simulations=200, max_seconds=5, seed=3,
                           evidence=ToolEvidence(episodes_for(fetcher=[True] * 20, parser=[True] * 20)))
    flaky = BoundedMCTS(max_simulations=200, max_seconds=5, seed=3,
                        evidence=ToolEvidence(episodes_for(fetcher=[True] * 2 + [False] * 18,
                                                           parser=[True] * 2 + [False] * 18)))
    r, f = reliable.search(plan), flaky.search(plan)
    assert r.root_value == 1.0 and r.assumed_success_steps == []
    assert f.root_value < 0.5  # same plan, same seed: the evidence moved the value
    assert f.mode == "simulated_search"
    assert set(f.evidence) == {n.id for n in plan} and all(e["available"] for e in f.evidence.values())


def test_mcts_without_evidence_reports_assumption_not_probability():
    plan = _plan()
    res = BoundedMCTS(max_simulations=32, seed=1).search(plan)
    d = res.as_dict()
    assert d["value_is_conditional"] is True
    assert set(d["assumed_success_steps"]) == {n.id for n in plan}
    assert "not a success probability" in d["value_semantics"]
    assert all(not e["available"] for e in d["evidence"].values())


def test_mcts_is_simulation_only_and_never_mutates_plan():
    plan = _plan()
    before = [(n.state, n.attempts) for n in plan]
    BoundedMCTS(max_simulations=32, seed=1,
                evidence=ToolEvidence(episodes_for(fetcher=[False] * 5, parser=[True] * 5))).search(plan)
    assert [(n.state, n.attempts) for n in plan] == before


def test_mcts_risk_is_not_a_hidden_penalty():
    # Same evidence, different risk tier: value identical (risk only breaks ties).
    ev = ToolEvidence(episodes_for(t=[True] * 3 + [False] * 3))
    low = [PlanNode(title="x", tool="t", risk=Risk.READ)]
    high = [PlanNode(title="x", tool="t", risk=Risk.IRREVERSIBLE)]
    vl = BoundedMCTS(max_simulations=300, seed=9, evidence=ev).search(low).root_value
    vh = BoundedMCTS(max_simulations=300, seed=9, evidence=ev).search(high).root_value
    assert vl == vh


# -- ruminator ---------------------------------------------------------------------

def test_ruminator_expected_success_is_product_of_observed_rates_only_when_all_known():
    ev = ToolEvidence(episodes_for(fetcher=[True] * 4 + [False] * 1, parser=[True] * 3 + [False] * 1))
    a = PlanNode(title="fetch", tool="fetcher")
    b = PlanNode(title="parse", tool="parser", depends_on=[a.id])
    out = MCTSRuminator(simulations=40, seed=1, evidence=ev).ruminate([a, b])
    assert out["best_ordering"] == ["fetch", "parse"]
    assert out["expected_success"] == pytest.approx(0.8 * 0.75, abs=1e-4)
    assert "independent" in out["expected_success_status"]
    assert out["mode"] == "simulated_search" and out["assumed_success_steps"] == []
    c = PlanNode(title="mystery", tool="unseen")
    out2 = MCTSRuminator(simulations=40, seed=1, evidence=ev).ruminate([a, b, c])
    assert out2["expected_success"] is None
    assert out2["assumed_success_steps"] == ["mystery"]


def test_ruminator_result_does_not_depend_on_seed_for_forced_chain():
    ev = ToolEvidence(episodes_for(t=[True] * 3))
    a = PlanNode(title="a", tool="t")
    b = PlanNode(title="b", tool="t", depends_on=[a.id])
    c = PlanNode(title="c", tool="t")
    r1 = MCTSRuminator(seed=1, evidence=ev).ruminate([a, b, c])
    r2 = MCTSRuminator(seed=2, evidence=ev).ruminate([a, b, c])
    assert r1["expected_success"] == r2["expected_success"] == 1.0  # old: .59 vs .66 random


def test_rumination_executes_nothing_and_loop_uses_episode_evidence():
    from test_m20_executive import build_loop
    loop, _, _ = build_loop()
    from app.modules.m20_general_cognitive_worker.schemas import TaskContext
    ctx = TaskContext(goal="research competitors and email the findings")
    ctx.plan = loop.planner.decompose(ctx.goal)
    records_before = len(loop.dispatcher.records)
    out = loop.ruminate(ctx)
    assert len(loop.dispatcher.records) == records_before  # simulated, not executed
    assert all(n.state == TaskState.PENDING for n in ctx.plan)
    assert out["mode"] == "simulated_search"
    assert loop.ruminator.evidence.counts() == {}  # nothing recorded yet -> honest
