"""Atlas spec 4.2.8 "Uncertainty Expression" and 4.2.2 "Fallback & Retry", bounded.

Spec wording implemented: "When the agent is unsure, it explicitly quantifies its
confidence and asks targeted questions to the user - never guessing recklessly on
high-stakes matters." and "If a model returns a low-confidence result ... the task
is retried with a different model or a self-critique loop."

Mechanism: confidence for a strategy is the Wilson lower bound (conservative) of its
observed success rate from OutcomeMetacognition, shrunk further when recent
calibration shows overconfidence. A stakes level sets the acting threshold. Below it
the gate returns, in order: retry with another strategy that clears the bar, else a
targeted question naming the weakest-evidenced strategy/data gap. High stakes never return "act": at best
"eligible_pending_authority" (the caller must obtain real user/financial/representation
authority). Thresholds are configurable policy defaults, not safety guarantees. Limits: confidence is statistics
over supplied outcomes, not model log-probs; questions are templated from measured
gaps, not generated language.
"""
from __future__ import annotations
import math
from typing import Dict, List

from .outcome_metacognition_1975_2009 import OutcomeMetacognition

# Engineering policy DEFAULTS (threshold, min evidence n); configurable, not empirically
# established safety guarantees. A Wilson bound on supplied past outcomes is not the
# probability that the current task's answer is correct.
DEFAULT_STAKES = {"low": (0.5, 0), "medium": (0.7, 5), "high": (0.9, 20)}
STAKES = DEFAULT_STAKES  # backward-compatible alias


def wilson_lower(wins: int, n: int, z: float = 1.96) -> float:
    if n <= 0:
        return 0.0
    p = wins / n
    d = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / d)


class UncertaintyGate:
    def __init__(self, learner: OutcomeMetacognition, stakes: Dict[str, tuple] = None):
        if not isinstance(learner, OutcomeMetacognition):
            raise ValueError("learner must be an OutcomeMetacognition")
        policy = dict(DEFAULT_STAKES if stakes is None else stakes)
        if set(policy) != {"low", "medium", "high"}:
            raise ValueError("stakes policy must define exactly low, medium, high")
        for k, v in policy.items():
            if (not isinstance(v, tuple) or len(v) != 2 or isinstance(v[0], bool)
                    or not isinstance(v[0], (int, float)) or not math.isfinite(v[0]) or not 0 <= v[0] <= 1
                    or type(v[1]) is not int or v[1] < 0):
                raise ValueError(f"invalid stakes policy for {k}: need (threshold in [0,1], min_n int >= 0)")
        self.policy = policy
        self.learner = learner

    def conservative_confidence(self, name: str) -> dict:
        if name not in self.learner.strategies:
            raise ValueError("unknown strategy")
        w, l = self.learner.wins[name], self.learner.losses[name]
        n = w + l
        lb = wilson_lower(w, n)
        shrink = 1.0
        refl = self.learner.calibration_summary(window=20)
        if refl.get("status") == "overconfident":
            shrink = max(0.0, 1.0 - refl["gap"])  # discount by measured overconfidence
        return {"strategy": name, "n": n, "wins": w, "wilson_lower": lb,
                "calibration_shrink": shrink, "confidence": lb * shrink}

    def decide(self, stakes: str) -> dict:
        if stakes not in self.policy:
            raise ValueError("stakes must be low, medium or high")
        threshold, min_n = self.policy[stakes]
        table: List[dict] = [self.conservative_confidence(k) for k in sorted(self.learner.strategies)]
        ok = [t for t in table if t["n"] >= min_n and t["confidence"] >= threshold]
        base = {"stakes": stakes, "threshold": threshold, "min_evidence": min_n, "table": table}
        if ok:
            best = max(ok, key=lambda t: (t["confidence"], t["strategy"]))
            if stakes == "high":
                # Statistics alone never authorize high-stakes action: the caller must obtain
                # the actual user / financial / representation authority before acting.
                return {**base, "action": "eligible_pending_authority", "requires_authority": True,
                        "strategy": best["strategy"], "confidence": best["confidence"]}
            return {**base, "action": "act", "requires_authority": False,
                    "strategy": best["strategy"], "confidence": best["confidence"]}
        weakest = min(table, key=lambda t: (t["n"], t["strategy"]))
        needed = max(0, min_n - weakest["n"])
        best_c = max(table, key=lambda t: t["confidence"])
        q = (f"Confidence {best_c['confidence']:.2f} for '{best_c['strategy']}' is below the "
             f"{stakes}-stakes bar {threshold:.2f}. "
             + (f"'{weakest['strategy']}' has only {weakest['n']} observed outcomes (need {min_n}). " if needed else "")
             + "Should I proceed anyway, gather more outcomes, or do you want to supply the answer?")
        return {**base, "action": "ask", "question": q, "confidence": best_c["confidence"]}

    def run_with_fallback(self, task, verifier, stakes: str, max_attempts: int = 3) -> dict:
        """Try strategies in confidence order; a failed attempt (recorded as an outcome)
        triggers retry with the next strategy; if none verifies, ask rather than guess.

        Documented bypass: for low/medium stakes this executes WITHOUT consulting
        decide()'s confidence threshold or minimum-evidence gate - calling this method
        is itself the caller's decision to execute. Strategy callables and the verifier
        MUST be pure/read-only: any exception from a callback is recorded as an ordinary
        failure and the next strategy is tried, so a side-effecting callback whose
        effect is ambiguous after an exception would be retried and could double-apply.
        High stakes never execute here: they go through decide() and explicit authority.
        """
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("max_attempts must be a positive int")
        if stakes not in self.policy:
            raise ValueError("stakes must be low, medium or high")
        if stakes == "high":
            raise ValueError("high-stakes execution needs explicit user authority; use decide() and obtain it first")
        order = sorted(self.learner.strategies, key=lambda k: -self.conservative_confidence(k)["confidence"])
        attempts = []
        for name in order[:max_attempts]:
            conf = self.learner.confidence(name)
            try:
                result = self.learner.strategies[name](task)
                ok = verifier(task, result)
                if not isinstance(ok, bool):
                    raise TypeError("verifier must return bool")
                err = None
            except Exception as exc:
                result, ok, err = None, False, f"{type(exc).__name__}: {exc}"
                self.learner.errors[name] += 1
            self.learner.record(name, conf, ok)
            attempts.append({"strategy": name, "success": ok, "error": err})
            if ok:
                return {"status": "verified", "strategy": name, "result": result, "attempts": attempts}
        return {"status": "ask_user", "attempts": attempts,
                "question": "No strategy produced a verified result; please clarify the task or supply the answer."}

    def retrospective(self, window: int = 20) -> dict:
        """Self-critique record: what worked, what did not, why (from measured counts)."""
        rep = self.learner.report()
        best = max(rep, key=lambda k: (rep[k]["confidence"], k))
        worst = min(rep, key=lambda k: (rep[k]["confidence"], k))
        return {"best": best, "worst": worst, "report": rep,
                "errors": dict(self.learner.errors), "calibration": self.learner.calibration_summary(window)}


