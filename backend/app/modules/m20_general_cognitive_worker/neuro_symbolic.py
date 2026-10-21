"""Neuro-symbolic reasoning engine (Extra doc row 1973, v2).

A runnable neuro-symbolic mechanism, stdlib-only:

- ``LogisticUnit``: a logistic neuron over named features, trained by real
  batch gradient descent on log-loss. ``fit`` ALWAYS starts from zero
  weights and bias (supplied weights are for scoring, not training). A unit
  constructed with explicit weights, or any unit after ``fit``, counts as
  fitted. All weights, features, bias and rate are validated finite.
- ``NeuroSymbolicEngine``: threshold-gated forward chaining over weighted
  Horn-like rules. Each infer pass evaluates every rule against the
  pass-start snapshot of FINAL (post-revision) scores, so a fact the
  neural layer revised below the threshold no longer gates rules that
  depend on it - its downstream conclusions lose support and are retracted.
  Derived scores are recomputed fresh each pass: noisy-OR over the
  DISTINCT rule ids that fired, then neural revision from provenance
  features {derivations, prior, rule_score} when a fitted unit is supplied. There is no one-shot integration latch: integrated facts are
  rescored on every pass. Rule ids are unique (duplicates rejected).
  Multi-hop chains propagate across passes (one firing sweep per pass).
  Termination is bounded by ``max_iterations``; non-convergence is
  reported via ``result["truncated"]``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def _require_finite(name: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number, got {value!r}")
    try:
        f = float(value)
    except OverflowError:
        raise ValueError(f"{name} is too large to represent as a float: {value!r}") from None
    if not math.isfinite(f):
        raise ValueError(f"{name} must be a finite number, got {value!r}")
    return f


def _require_positive_int(name: str, value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive int, got {value!r}")
    return value


class LogisticUnit:
    """Single logistic neuron over named features."""

    def __init__(self, weights: dict[str, float] | None = None, bias: float = 0.0,
                 rate: float = 0.5) -> None:
        self.weights = {str(k): _require_finite(f"weight[{k}]", v) for k, v in (weights or {}).items()}
        self.bias = _require_finite("bias", bias)
        self.rate = _require_finite("rate", rate)
        if self.rate <= 0.0:
            raise ValueError(f"rate must be > 0, got {self.rate!r}")
        self.fitted = weights is not None

    def _checked_features(self, features: dict[str, float]) -> dict[str, float]:
        return {str(k): _require_finite(f"feature[{k}]", v) for k, v in features.items()}

    def logit(self, features: dict[str, float]) -> float:
        feats = self._checked_features(features)
        total = self.bias
        for k, v in feats.items():
            total += self.weights.get(k, 0.0) * v
            if not math.isfinite(total):
                raise ValueError(
                    f"logit overflow: finite weights/features produced a non-finite total")
        if not math.isfinite(total):
            raise ValueError("logit overflow: non-finite total")
        return total

    def score(self, features: dict[str, float]) -> float:
        return _sigmoid(self.logit(features))

    def fit(self, examples: list[tuple[dict[str, float], int]], epochs: int = 400) -> list[float]:
        """Batch gradient descent on log-loss, ALWAYS zero-initialized."""
        _require_positive_int("epochs", epochs)
        examples = list(examples)
        if not examples:
            raise ValueError("examples must be non-empty")
        checked = []
        for features, label in examples:
            if label not in (0, 1):
                raise ValueError(f"label must be 0 or 1, got {label!r}")
            checked.append((self._checked_features(features), float(label)))
        keys = sorted({k for feats, _ in checked for k in feats})
        self.weights = {k: 0.0 for k in keys}
        self.bias = 0.0
        n = len(checked)
        history: list[float] = []
        for _ in range(epochs):
            loss = 0.0
            grad_w = {k: 0.0 for k in keys}
            grad_b = 0.0
            for feats, y in checked:
                p = _sigmoid(self.logit(feats))
                p = min(max(p, 1e-12), 1.0 - 1e-12)
                loss += -(y * math.log(p) + (1.0 - y) * math.log(1.0 - p))
                err = p - y
                for k in keys:
                    grad_w[k] += err * feats.get(k, 0.0)
                grad_b += err
            for k in keys:
                self.weights[k] -= self.rate * grad_w[k] / n
            self.bias -= self.rate * grad_b / n
            if not all(math.isfinite(w) for w in self.weights.values()) or not math.isfinite(self.bias):
                raise ValueError(
                    "fit diverged: gradient update produced non-finite weights/bias; "
                    "rescale features or lower the rate")
            history.append(loss / n)
        self.fitted = True
        return history


@dataclass(frozen=True)
class Rule:
    id: str
    antecedents: tuple
    consequent: str
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("rule id must be non-empty")
        ants = tuple(str(a) for a in self.antecedents)
        if not ants:
            raise ValueError("rule needs at least one antecedent")
        object.__setattr__(self, "antecedents", ants)
        if not self.consequent:
            raise ValueError("consequent must be non-empty")
        if self.consequent in ants:
            raise ValueError(f"self-loop rule rejected: {self.consequent!r} is its own antecedent")
        w = _require_finite("weight", self.weight)
        if not 0.0 < w <= 1.0:
            raise ValueError(f"rule weight must be in (0, 1], got {w!r}")
        object.__setattr__(self, "weight", w)


MAX_ITERATIONS_LIMIT = 64


class NeuroSymbolicEngine:
    """Threshold-gated forward chaining with neural revision of derived facts.

    Policies (pinned by tests):
    - Supplied facts are authoritative and immutable: a rule may not
      conclude a supplied fact, and a fact may not be supplied under a
      name that is already a rule consequent (both rejected at add time).
      Consequently a supplied fact's score never changes and needs no
      restoration; a DERIVED fact whose support disappears is removed
      outright (no stale value is kept).
    - Self-loop rules (consequent among their own antecedents) are
      rejected at construction.
    - Convergence is SCORES-ONLY: result["converged"] means the score
      map stopped changing between passes. With rule cycles, scores can
      converge while the support structure would keep evolving on later
      passes; no stable-depth or stable-provenance claim is made.
      provenance carries rule ids only and is not depth-bearing, and the
      neural revision features are {derivations, prior, rule_score} - no
      depth - so the unit cannot be steered by unbounded cycle depth.
    - max_iterations defaults to 8 and is bounded above by
      MAX_ITERATIONS_LIMIT (64).
    """

    def __init__(self, threshold: float = 0.5, max_iterations: int = 8) -> None:
        self.threshold = _require_finite("threshold", threshold)
        if not 0.0 < self.threshold < 1.0:
            raise ValueError(f"threshold must be in (0, 1), got {self.threshold!r}")
        self.max_iterations = _require_positive_int("max_iterations", max_iterations)
        if self.max_iterations > MAX_ITERATIONS_LIMIT:
            raise ValueError(
                f"max_iterations must be <= {MAX_ITERATIONS_LIMIT}, got {self.max_iterations}")
        self.rules: list[Rule] = []
        self._rule_ids: set[str] = set()
        self.facts: dict[str, float] = {}

    def add_rule(self, rule: Rule) -> None:
        if rule.id in self._rule_ids:
            raise ValueError(f"duplicate rule id: {rule.id!r}")
        if rule.consequent in self.facts:
            raise ValueError(
                f"rule consequent {rule.consequent!r} collides with a supplied fact; "
                "supplied facts are authoritative and immutable")
        self._rule_ids.add(rule.id)
        self.rules.append(rule)

    def add_fact(self, name: str, score: float) -> None:
        s = _require_finite(f"score[{name}]", score)
        if not 0.0 <= s <= 1.0:
            raise ValueError(f"fact score must be in [0, 1], got {s!r}")
        if str(name) in {r.consequent for r in self.rules}:
            raise ValueError(
                f"fact {name!r} collides with a rule consequent; "
                "supplied facts are authoritative and immutable")
        self.facts[str(name)] = s

    def infer(self, unit: LogisticUnit | None = None) -> dict:
        if unit is not None and not isinstance(unit, LogisticUnit):
            raise ValueError("unit must be a LogisticUnit or None")
        revise = unit is not None and unit.fitted
        scores = dict(self.facts)
        provenance: dict[str, list[str]] = {}
        trace: list[dict] = []
        contributions: dict[str, dict[str, float]] = {}
        iterations = 0
        converged = False
        for it in range(1, self.max_iterations + 1):
            iterations = it
            snapshot = dict(scores)
            pass_contrib: dict[str, dict[str, float]] = {}
            for rule in self.rules:
                if any(a not in snapshot or snapshot[a] < self.threshold
                       for a in rule.antecedents):
                    continue
                base = rule.weight * min(snapshot[a] for a in rule.antecedents)
                slot = pass_contrib.setdefault(rule.consequent, {})
                if rule.id not in slot or base > slot[rule.id]:
                    slot[rule.id] = base
                trace.append({"pass": it, "rule": rule.id,
                              "derived": rule.consequent, "score": base})
            next_scores = dict(snapshot)
            for consequent, slot in pass_contrib.items():
                combined = 1.0
                for base in slot.values():
                    combined *= (1.0 - base)
                rule_score = 1.0 - combined
                final = rule_score
                if revise:
                    final = unit.score({
                        "derivations": float(len(slot)),
                        "prior": snapshot.get(consequent, 0.0),
                        "rule_score": rule_score,
                    })
                next_scores[consequent] = final
                provenance[consequent] = sorted(slot)
            for name in list(next_scores):
                if name not in self.facts and name not in pass_contrib and name in contributions:
                    del next_scores[name]  # retract: support fell away this pass
                    provenance.pop(name, None)
            contributions = pass_contrib
            converged = all(
                abs(next_scores.get(n, -1.0) - snapshot.get(n, -1.0)) <= 1e-9
                for n in set(next_scores) | set(snapshot))
            scores = next_scores
            if converged:
                break
        accepted = {n: s for n, s in scores.items() if s >= self.threshold}
        return {
            "accepted": accepted,
            "scores": scores,
            "iterations": iterations,
            "converged": converged,
            "truncated": not converged,
            "trace": trace,
            "provenance": provenance,
        }
