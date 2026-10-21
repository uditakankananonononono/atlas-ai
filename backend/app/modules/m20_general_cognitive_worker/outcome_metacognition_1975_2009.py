"""Rows 1975 Cognitive Computing and 2009 Metacognition: strategy selection and
confidence learned from observed task outcomes (bounded mechanism).

Strategy choice uses Beta-posterior Thompson-free UCB-style scoring computed from
real recorded outcomes. Confidence is the posterior mean, with a Brier-score
calibration check on the agent's own past predictions. Limits: strategies are
caller-supplied callables; no general cognition is claimed. Deterministic given seed.
"""
from __future__ import annotations
import math
import random
from typing import Callable, Dict, List, Optional, Tuple


class OutcomeMetacognition:
    def __init__(self, strategies: Dict[str, Callable], seed: int = 0, explore: float = 1.0):
        if not isinstance(strategies, dict) or not strategies:
            raise ValueError("need at least one strategy")
        for k, f in strategies.items():
            if not isinstance(k, str) or not k or not callable(f):
                raise ValueError("strategies must map non-empty names to callables")
        if isinstance(explore, bool) or not isinstance(explore, (int, float)) or not math.isfinite(explore) or explore < 0:
            raise ValueError("explore must be finite and >= 0")
        self.errors = {k: 0 for k in strategies}
        self.strategies = dict(strategies)
        self.rng = random.Random(seed)
        self.explore = explore
        self.wins = {k: 0 for k in strategies}
        self.losses = {k: 0 for k in strategies}
        self.predictions: List[Tuple[float, int]] = []  # (confidence, outcome)

    def confidence(self, name: str) -> float:
        w, l = self.wins[name], self.losses[name]
        return (w + 1) / (w + l + 2)  # Laplace/Beta(1,1) posterior mean

    def _score(self, name: str, total: int) -> float:
        n = self.wins[name] + self.losses[name]
        bonus = self.explore * math.sqrt(2 * math.log(total + 2) / (n + 1))
        return self.confidence(name) + bonus

    def select(self) -> Tuple[str, float]:
        total = sum(self.wins.values()) + sum(self.losses.values())
        names = sorted(self.strategies)
        best = max(names, key=lambda k: (self._score(k, total), -names.index(k)))
        return best, self.confidence(best)

    def run(self, task, verifier: Callable[[object, object], bool]) -> dict:
        name, conf = self.select()
        error = None
        result = None
        try:
            result = self.strategies[name](task)
            ok = verifier(task, result)
            if not isinstance(ok, bool):
                raise TypeError("verifier must return bool")
        except Exception as exc:  # callback failure counts as a failed outcome, never a success
            ok = False
            error = f"{type(exc).__name__}: {exc}"
            self.errors[name] += 1
        self.record(name, conf, ok)
        return {"strategy": name, "confidence_before": conf, "success": ok, "result": result, "error": error}

    def record(self, name: str, conf: float, ok: bool) -> None:
        if name not in self.strategies:
            raise ValueError("unknown strategy")
        if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not math.isfinite(conf) or not 0 <= conf <= 1:
            raise ValueError("confidence must be finite in [0,1]")
        if not isinstance(ok, bool):
            raise ValueError("outcome must be bool")
        (self.wins if ok else self.losses)[name] += 1
        self.predictions.append((conf, int(ok)))

    def brier(self) -> Optional[float]:
        if not self.predictions:
            return None
        return sum((c - o) ** 2 for c, o in self.predictions) / len(self.predictions)

    def report(self) -> dict:
        return {k: {"wins": self.wins[k], "losses": self.losses[k],
                    "confidence": self.confidence(k)} for k in self.strategies}

    def calibration_summary(self, window: int = 20) -> dict:
        """Pure monitoring over supplied historical predictions, not task truth."""
        if type(window) is not int or window < 1:
            raise ValueError("window must be a positive integer")
        recent = self.predictions[-window:]
        if not recent:
            return {"status": "no_data"}
        mean_conf = sum(c for c, _ in recent) / len(recent)
        rate = sum(o for _, o in recent) / len(recent)
        gap = mean_conf - rate
        status = "overconfident" if gap > 0.1 else "underconfident" if gap < -0.1 else "calibrated"
        return {"status": status, "mean_confidence": mean_conf,
                "success_rate": rate, "gap": gap, "explore": self.explore}

    def reflect(self, window: int = 20) -> dict:
        """Explicit policy mutation: overconfidence raises exploration weight.

        Repeated explicit calls can increase it again; gate reads never call this.
        """
        result = self.calibration_summary(window)
        if result["status"] == "overconfident":
            self.explore = min(self.explore * 1.5, 4.0)
            result["explore"] = self.explore
        return result

    def to_state(self) -> dict:
        """Plain-JSON outcome history (persistable by the integrator's own store)."""
        return {"wins": dict(self.wins), "losses": dict(self.losses),
                "errors": dict(self.errors), "predictions": [list(p) for p in self.predictions],
                "explore": self.explore}

    def load_state(self, state: dict) -> None:
        """Load a to_state() snapshot. Imported history is taken as-is: wins/losses
        counts and the predictions window are not cross-checked for consistency
        (predictions carry no strategy key), so imported calibration is not
        independently verified - load only state produced by a trusted to_state()."""
        if not isinstance(state, dict):
            raise ValueError("state must be a dict")
        for key in ("wins", "losses"):
            d = state.get(key)
            if not isinstance(d, dict) or set(d) != set(self.strategies):
                raise ValueError(f"{key} must cover exactly the registered strategies")
            if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in d.values()):
                raise ValueError(f"{key} must be non-negative ints")
        def finite_number(value):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return False
            try:
                return math.isfinite(value)
            except OverflowError:
                return False
        preds = state.get("predictions", [])
        if not isinstance(preds, list) or any(
            not isinstance(p, (list, tuple)) or len(p) != 2 or isinstance(p[0], bool)
            or not finite_number(p[0]) or not 0 <= p[0] <= 1
            or type(p[1]) is not int or p[1] not in (0, 1) for p in preds):
            raise ValueError("invalid predictions")
        explore = state.get("explore", self.explore)
        if not finite_number(explore) or explore < 0:
            raise ValueError("invalid explore")
        errs = state.get("errors", {k: 0 for k in self.strategies})
        if (not isinstance(errs, dict) or set(errs) != set(self.strategies)
                or any(type(v) is not int or v < 0 for v in errs.values())):
            raise ValueError("errors must cover exactly the strategies with nonnegative integer counts")
        # Validate/convert everything before publication: a refused state cannot
        # partially replace wins/losses and leave the other fields unchanged.
        try:
            converted_explore = float(explore)
        except OverflowError:
            raise ValueError("invalid explore") from None
        converted_predictions = [(float(c), o) for c, o in preds]
        wins, losses, errors = dict(state["wins"]), dict(state["losses"]), dict(errs)
        self.wins, self.losses, self.errors = wins, losses, errors
        self.predictions, self.explore = converted_predictions, converted_explore


def run_from_history(data: dict, seed: int = 0) -> dict:
    """Plain-data entry point (no callables) suitable for a dispatcher: replay
    observed outcomes `history=[[strategy, success_bool], ...]`, then report the
    strategy this learner would choose next, per-strategy confidence and Brier
    calibration of the replayed predictions."""
    hist = data.get("history")
    names = data.get("strategies")
    if not isinstance(names, list) or not names or any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names):
        raise ValueError("strategies must be a non-empty list of unique names")
    if not isinstance(hist, list):
        raise ValueError("history must be a list")
    m = OutcomeMetacognition({n: (lambda t: None) for n in names}, seed=seed)
    for item in hist:
        if not isinstance(item, (list, tuple)) or len(item) != 2 or item[0] not in m.strategies or not isinstance(item[1], bool):
            raise ValueError("each history item must be [known_strategy, bool]")
        m.record(item[0], m.confidence(item[0]), item[1])
    nxt, conf = m.select()
    return {"next_strategy": nxt, "next_confidence": conf, "brier": m.brier(),
            "report": m.report(), "n_outcomes": len(hist),
            "limits": "bounded Beta-posterior/UCB outcome learning on supplied history; not general cognition"}
