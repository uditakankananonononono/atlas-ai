"""Bounded Monte Carlo tree search over plan orderings (spec 4.2.4 rumination,
row M20-16).

Unlike the earlier random-ordering ruminator, this is a real UCT search: the
tree's levels are the plan's pending steps, an action is "execute step X
next", and the chance of step failure is folded into the rollout. The search
is hard-bounded on three axes - simulations, wall-clock seconds, and tree
depth - and every result carries visit counts, mean values and standard
errors so the executive (and the user) can see how confident the
recommendation is. A fixed seed makes runs reproducible for audits.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from .schemas import PlanNode, Risk, TaskState

RISK_COST = {Risk.READ: 0.05, Risk.REVERSIBLE: 0.15, Risk.EXTERNAL: 0.35, Risk.IRREVERSIBLE: 0.6}


def _success_probability(node: PlanNode) -> float:
    """Prior completion probability: degraded by past failed attempts."""
    return max(0.05, 0.9 - 0.1 * node.attempts)


@dataclass
class ActionStat:
    """Typed per-action evaluation at the search root."""

    node_id: str
    title: str
    visits: int
    mean_value: float
    standard_error: float


@dataclass
class MCTSResult:
    """Typed search result with evaluation/uncertainty reporting."""

    best_action_id: str | None
    best_action_title: str | None
    simulations_run: int
    stopped_by: str  # "simulation_budget" | "time_budget" | "terminal"
    principal_variation: list[str]
    action_stats: list[ActionStat]
    root_value: float
    root_standard_error: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "best_action_id": self.best_action_id,
            "best_action_title": self.best_action_title,
            "simulations_run": self.simulations_run,
            "stopped_by": self.stopped_by,
            "principal_variation": list(self.principal_variation),
            "action_stats": [vars(s) for s in self.action_stats],
            "root_value": self.root_value,
            "root_standard_error": self.root_standard_error,
        }


@dataclass
class _TreeNode:
    """One UCT tree node: the set of plan steps completed so far."""

    completed: frozenset[str]
    parent: "_TreeNode | None" = None
    action_taken: str | None = None  # plan-node id executed to reach here
    visits: int = 0
    total_value: float = 0.0
    total_value_sq: float = 0.0
    children: dict[str, "_TreeNode"] = field(default_factory=dict)
    untried: list[str] = field(default_factory=list)

    @property
    def mean_value(self) -> float:
        return self.total_value / self.visits if self.visits else 0.0

    def standard_error(self) -> float:
        if self.visits < 2:
            return 1.0
        variance = max(0.0, self.total_value_sq / self.visits - self.mean_value ** 2)
        return math.sqrt(variance / self.visits)


class BoundedMCTS:
    """UCT over next-step selection for a partial HTN plan."""

    def __init__(
        self,
        *,
        max_simulations: int = 64,
        max_seconds: float = 1.0,
        max_depth: int = 12,
        exploration: float = math.sqrt(2.0),
        seed: int | None = None,
    ) -> None:
        if max_simulations < 1:
            raise ValueError("max_simulations must be >= 1")
        if max_seconds <= 0:
            raise ValueError("max_seconds must be positive")
        if max_depth < 1:
            raise ValueError("max_depth must be >= 1")
        self.max_simulations = max_simulations
        self.max_seconds = max_seconds
        self.max_depth = max_depth
        self.exploration = exploration
        import random

        self.random = random.Random(seed)

    # -- plan helpers ----------------------------------------------------

    @staticmethod
    def _pending(plan: list[PlanNode], completed: frozenset[str]) -> list[PlanNode]:
        return [
            n for n in plan
            if n.state in (TaskState.PENDING, TaskState.RUNNING) and n.id not in completed
        ]

    @classmethod
    def _ready(cls, plan: list[PlanNode], completed: frozenset[str]) -> list[PlanNode]:
        done = {n.id for n in plan if n.state == TaskState.SUCCEEDED} | set(completed)
        failed = {n.id for n in plan if n.state in (TaskState.FAILED, TaskState.BLOCKED)}
        return [
            n for n in cls._pending(plan, completed)
            if all(d in done for d in n.depends_on)
            and not any(d in failed for d in n.depends_on)
        ]

    # -- search ------------------------------------------------------------

    def search(self, plan: list[PlanNode]) -> MCTSResult:
        start = time.monotonic()
        ready = self._ready(plan, frozenset())
        if not ready:
            return MCTSResult(
                best_action_id=None, best_action_title=None, simulations_run=0,
                stopped_by="terminal", principal_variation=[], action_stats=[],
                root_value=1.0 if not self._pending(plan, frozenset()) else 0.0,
                root_standard_error=0.0,
            )
        root = _TreeNode(completed=frozenset(), untried=[n.id for n in ready])
        by_id = {n.id: n for n in plan}
        stopped_by = "simulation_budget"
        simulations = 0
        for _ in range(self.max_simulations):
            if time.monotonic() - start >= self.max_seconds:
                stopped_by = "time_budget"
                break
            node = root
            completed = set(node.completed)
            depth = 0
            # select + expand
            while depth < self.max_depth:
                if node.untried:
                    action = node.untried.pop(self.random.randrange(len(node.untried)))
                    child = _TreeNode(
                        completed=frozenset(completed | {action}),
                        parent=node, action_taken=action,
                    )
                    child_ready = self._ready(plan, child.completed)
                    child.untried = [n.id for n in child_ready]
                    node.children[action] = child
                    node = child
                    completed.add(action)
                    depth += 1
                    break
                if not node.children:
                    break
                node = self._uct_select(node)
                completed = set(node.completed)
                depth += 1
            # rollout from the frontier
            reward = self._rollout(plan, completed, depth)
            # backpropagate
            while node is not None:
                node.visits += 1
                node.total_value += reward
                node.total_value_sq += reward * reward
                node = node.parent
            simulations += 1

        stats = [
            ActionStat(
                node_id=child.action_taken or "",
                title=by_id[child.action_taken].title if child.action_taken in by_id else "",
                visits=child.visits,
                mean_value=round(child.mean_value, 4),
                standard_error=round(child.standard_error(), 4),
            )
            for child in root.children.values()
        ]
        stats.sort(key=lambda s: (s.visits, s.mean_value), reverse=True)
        best = stats[0] if stats else None
        return MCTSResult(
            best_action_id=best.node_id if best else None,
            best_action_title=best.title if best else None,
            simulations_run=simulations,
            stopped_by=stopped_by if simulations else "terminal",
            principal_variation=self._principal_variation(root, by_id),
            action_stats=stats,
            root_value=round(root.mean_value, 4),
            root_standard_error=round(root.standard_error(), 4),
        )

    def _uct_select(self, node: _TreeNode) -> _TreeNode:
        log_parent = math.log(max(1, node.visits))

        def score(child: _TreeNode) -> float:
            if child.visits == 0:
                return float("inf")
            return child.mean_value + self.exploration * math.sqrt(log_parent / child.visits)

        return max(node.children.values(), key=score)

    def _rollout(self, plan: list[PlanNode], completed: set[str], depth: int) -> float:
        """Simulate one plausible completion; reward blends progress and risk."""
        done = set(completed)
        risk_paid = 0.0
        steps = 0
        while depth + steps < self.max_depth:
            ready = self._ready(plan, frozenset(done))
            if not ready:
                break
            node = self.random.choice(ready)
            risk_paid += RISK_COST.get(node.risk, 0.1)
            if self.random.random() < _success_probability(node):
                done.add(node.id)
            # a failed step blocks its descendants but not its siblings
            steps += 1
        total = len([n for n in plan if n.state != TaskState.CANCELLED]) or 1
        finished = len([n for n in plan if n.state == TaskState.SUCCEEDED]) + len(done - {n.id for n in plan if n.state == TaskState.SUCCEEDED})
        progress = min(1.0, finished / total)
        return max(0.0, min(1.0, progress - 0.1 * risk_paid))

    def _principal_variation(self, root: _TreeNode, by_id: dict[str, PlanNode]) -> list[str]:
        variation: list[str] = []
        node = root
        while node.children:
            node = max(node.children.values(), key=lambda c: c.visits)
            if node.action_taken and node.action_taken in by_id:
                variation.append(by_id[node.action_taken].title)
        return variation
