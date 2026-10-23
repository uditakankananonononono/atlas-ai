"""Additive pins for row 23 registry-guard comparisons (mutation ids 80/151).

A policy-shaped object whose equality dunders lie about None must not flip the
refresh/escalation decisions in DecisionFatigueGuard.decide: the guard decides
by identity (`is` / `is not None`), not equality. Production bytes unchanged.
"""
from datetime import timedelta

from app.modules.m20_general_cognitive_worker.metacognition import (
    DecisionFatigueGuard, _now)


class EqLiarPolicy:
    """Policy-shaped object claiming equality with None (a lie)."""

    def __init__(self, decision_type, default_choice, max_auto_per_day=10,
                 used_today=0, last_reset=None):
        self.decision_type = decision_type
        self.default_choice = default_choice
        self.max_auto_per_day = max_auto_per_day
        self.used_today = used_today
        self.last_reset = last_reset if last_reset is not None else _now()

    def __eq__(self, other):
        return other is None

    def __ne__(self, other):
        return other is not None


def test_stale_policy_is_refreshed_despite_equality_liar():
    # Mutant id 80 (L936 `policy is not None` -> `policy != None`) skips
    # _refresh for the liar: a stale, capped policy must still be reset and
    # then automate.
    g = DecisionFatigueGuard()
    liar = EqLiarPolicy("c", "x", max_auto_per_day=1, used_today=1,
                        last_reset=_now() - timedelta(days=2))
    g.policies["c"] = liar
    out = g.decide("c", options=["x", "y"])
    assert out["automated"] is True and out["chosen"] == "x"
    assert liar.used_today == 1


def test_registered_policy_is_not_treated_as_none_despite_equality_liar():
    # Mutant id 151 (L938 `policy is None` -> `policy == None`) takes the
    # escalation branch for the liar: a fresh registered policy must automate.
    g = DecisionFatigueGuard()
    g.policies["c"] = EqLiarPolicy("c", "x")
    out = g.decide("c", options=["x", "y"])
    assert out["automated"] is True and out["chosen"] == "x"
