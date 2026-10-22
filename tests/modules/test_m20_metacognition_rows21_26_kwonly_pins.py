"""Kill the two keyword-only-signature mutants (metacognition.py `*` -> `/` in apply_evidence and decide) that survive v5 + all existing metacognition suites. Tests only."""
import pytest
from app.modules.m20_general_cognitive_worker.metacognition import DecisionFatigueGuard, WorldModelRegistry


def test_apply_evidence_name_positional_supported_keyword_only():
    r = WorldModelRegistry(); r.register("m", {"a": "b"})
    r.apply_evidence(name="m", supported=True)
    with pytest.raises(TypeError):
        r.apply_evidence("m", True)


def test_decide_options_keyword_only_and_type_keyword_ok():
    g = DecisionFatigueGuard()
    assert g.decide(decision_type="x", options=["a"])["automated"] is False
    with pytest.raises(TypeError):
        g.decide("x", ["a"])
