"""Tests for M12 model routing."""

import pytest

from app.modules.m12_ai_research_lab.lane_models import (
    CAP_CHAT, CAP_CODE, CAP_JSON_MODE, CAP_VISION, ModelProfile, TaskRequirements,
    usd_to_micro,
)
from app.modules.m12_ai_research_lab.lane_routing import (
    ModelRouter, NoEligibleModelError,
)


def profile(model_id, in_cost=1000, out_cost=2000, caps=(CAP_CHAT,), quality=3,
            latency=2, enabled=True, ctx=8192):
    return ModelProfile(
        model_id=model_id,
        provider="test",
        display_name=model_id,
        cost_per_1k_input_micro=in_cost,
        cost_per_1k_output_micro=out_cost,
        capabilities=frozenset(caps),
        max_context_tokens=ctx,
        quality_tier=quality,
        latency_tier=latency,
        enabled=enabled,
    )


def router_default():
    return ModelRouter([
        profile("cheap", in_cost=100, out_cost=200, quality=2),
        profile("mid", in_cost=1000, out_cost=2000, quality=3),
        profile("strong", in_cost=10000, out_cost=20000, quality=5),
        profile("vision", in_cost=500, out_cost=1000, caps=(CAP_CHAT, CAP_VISION), quality=3),
        profile("coder", in_cost=800, out_cost=1600, caps=(CAP_CHAT, CAP_CODE), quality=4),
        profile("off", enabled=False),
    ])


def test_route_picks_cheapest_eligible_by_default():
    d = router_default().route(TaskRequirements())
    assert d.chosen.model_id == "cheap"


def test_route_respects_required_capabilities():
    d = router_default().route(
        TaskRequirements(required_capabilities=frozenset({CAP_CHAT, CAP_VISION}))
    )
    assert d.chosen.model_id == "vision"
    verdicts = {v.model_id: v for v in d.verdicts}
    assert not verdicts["cheap"].eligible
    assert "missing capabilities: vision" in verdicts["cheap"].reasons


def test_route_respects_min_quality():
    d = router_default().route(TaskRequirements(min_quality_tier=4))
    assert d.chosen.model_id in ("coder", "strong")
    verdicts = {v.model_id: v for v in d.verdicts}
    assert "quality tier 3 below required 4" in verdicts["mid"].reasons


def test_route_respects_cost_ceiling():
    req = TaskRequirements(
        estimated_input_tokens=1000, estimated_output_tokens=1000,
        max_cost_micro=usd_to_micro(0.002),
    )
    d = router_default().route(req)
    assert d.chosen.model_id == "cheap"
    assert d.estimated_cost_micro == 300  # 100 + 200


def test_route_respects_context_window():
    req = TaskRequirements(estimated_input_tokens=9000, estimated_output_tokens=100)
    with pytest.raises(NoEligibleModelError) as exc:
        router_default().route(req)
    assert any("exceed context" in r for v in exc.value.verdicts for r in v.reasons)


def test_route_skips_disabled_models():
    r = ModelRouter([profile("off", enabled=False)])
    with pytest.raises(NoEligibleModelError):
        r.route(TaskRequirements())
    verdict = r.route.__self__  # noqa - keep linter quiet about unused


def test_route_deterministic_across_calls():
    r = router_default()
    req = TaskRequirements(min_quality_tier=2)
    first = r.route(req)
    for _ in range(5):
        assert r.route(req).chosen.model_id == first.chosen.model_id
        assert r.route(req).verdicts == first.verdicts


def test_route_tie_breaks_on_model_id():
    r = ModelRouter([
        profile("b-model", in_cost=100, out_cost=100),
        profile("a-model", in_cost=100, out_cost=100),
    ])
    d = r.route(TaskRequirements())
    assert d.chosen.model_id == "a-model"


def test_route_latency_preference_changes_choice():
    r = ModelRouter([
        profile("slow-strong", in_cost=1000, out_cost=1000, quality=5, latency=3),
        profile("fast-ok", in_cost=1100, out_cost=1100, quality=3, latency=1),
    ])
    req = TaskRequirements(prefer_low_latency=True, prefer_low_cost=False)
    d = r.route(req)
    assert d.chosen.model_id == "fast-ok"


def test_no_eligible_error_lists_all_reasons():
    r = router_default()
    req = TaskRequirements(
        required_capabilities=frozenset({CAP_VISION, CAP_CODE, CAP_JSON_MODE}),
        min_quality_tier=5,
    )
    with pytest.raises(NoEligibleModelError) as exc:
        r.route(req)
    assert len(exc.value.verdicts) == 6
    assert all(not v.eligible for v in exc.value.verdicts)


def test_estimate_cost_math():
    p = profile("x", in_cost=1_500_000, out_cost=3_000_000)  # $1.50/$3.00 per 1k
    assert p.estimate_cost_micro(1000, 1000) == 4_500_000
    assert p.estimate_cost_micro(1, 1) == 4_500
    assert p.estimate_cost_micro(0, 0) == 0


def test_duplicate_registration_rejected():
    r = ModelRouter([profile("x")])
    with pytest.raises(ValueError):
        r.register(profile("x"))


def test_profile_validation():
    with pytest.raises(ValueError):
        profile("bad", quality=6)
    with pytest.raises(ValueError):
        ModelProfile(
            model_id="", provider="t", display_name="t",
            cost_per_1k_input_micro=0, cost_per_1k_output_micro=0,
        )
    with pytest.raises(ValueError):
        profile("neg", in_cost=-1)
