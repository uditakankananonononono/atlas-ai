"""HTN planning (spec 4.2.4): hierarchical task network decomposition.

Given a high-level goal, the planner first matches its method library; for
novel goals it asks an injected planner model (LLM) for a decomposition de
novo, validates it, and stores it as a learned method for future reuse.
Plans are DAGs of PlanNode with explicit dependencies and risk tiers.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .embeddings import tokenize
from .schemas import HTNMethod, MethodSource, PlanNode, Risk, TaskState


@runtime_checkable
class PlannerModel(Protocol):
    """LLM that decomposes a novel goal. Returns a list of step dicts:
    {title, tool?, arguments?, depends_on?, risk?, max_attempts?}."""

    def decompose(self, goal: str, *, context: str = "") -> list[dict[str, Any]]: ...


VALID_RISKS = {r.value for r in Risk}


class PlanError(Exception):
    pass


class HTNPlanner:
    def __init__(self, model: PlannerModel | None = None) -> None:
        self.model = model
        self.methods: dict[str, HTNMethod] = {}

    def register_method(self, method: HTNMethod) -> HTNMethod:
        self.methods[method.name] = method
        return method

    def _match_method(self, goal: str) -> HTNMethod | None:
        goal_tokens = set(tokenize(goal))
        if not goal_tokens:
            return None
        best: tuple[float, HTNMethod] | None = None
        for method in self.methods.values():
            pattern_tokens = set(tokenize(method.goal_pattern))
            if not pattern_tokens:
                continue
            overlap = len(goal_tokens & pattern_tokens) / len(goal_tokens | pattern_tokens)
            if overlap >= 0.34 and (best is None or overlap > best[0]):
                best = (overlap, method)
        return best[1] if best else None

    def decompose(self, goal: str, *, context: str = "") -> list[PlanNode]:
        method = self._match_method(goal)
        if method is not None:
            method.times_used += 1
            return self._instantiate(method)
        if self.model is None:
            raise PlanError(f"no method matches goal and no planner model bound: {goal!r}")
        raw_steps = self.model.decompose(goal, context=context)
        nodes = self._validate(raw_steps)
        learned = HTNMethod(
            name=f"learned:{goal[:48]}",
            goal_pattern=goal,
            subtasks=[n.model_copy(deep=True) for n in nodes],
            source=MethodSource.LEARNED,
        )
        self.register_method(learned)
        return nodes

    @staticmethod
    def _instantiate(method: HTNMethod) -> list[PlanNode]:
        """Fresh node ids per plan; depends_on entries (template ids or
        titles) are remapped to the new ids."""
        from uuid import uuid4

        copies = [node.model_copy(deep=True) for node in method.subtasks]
        id_map: dict[str, str] = {}
        title_map: dict[str, str] = {}
        for template, copy in zip(method.subtasks, copies):
            fresh = str(uuid4())
            id_map[template.id] = fresh
            title_map[template.title] = fresh
            copy.id = fresh
        for copy in copies:
            copy.depends_on = [
                id_map.get(dep) or title_map.get(dep) or dep
                for dep in copy.depends_on
            ]
        return copies

    def _validate(self, raw_steps: list[dict[str, Any]]) -> list[PlanNode]:
        if not raw_steps:
            raise PlanError("planner model returned an empty decomposition")
        nodes: list[PlanNode] = []
        ids: set[str] = set()
        for raw in raw_steps:
            if not isinstance(raw, dict) or not raw.get("title"):
                raise PlanError(f"invalid step: {raw!r}")
            risk = raw.get("risk", Risk.READ.value)
            if risk not in VALID_RISKS:
                raise PlanError(f"invalid risk tier {risk!r} in step {raw.get('title')!r}")
            node = PlanNode(
                title=str(raw["title"]),
                tool=raw.get("tool"),
                arguments=dict(raw.get("arguments") or {}),
                depends_on=list(raw.get("depends_on") or []),
                risk=Risk(risk),
                max_attempts=int(raw.get("max_attempts", 3)),
            )
            if raw.get("id"):
                node.id = str(raw["id"])
            if node.id in ids:
                raise PlanError(f"duplicate step id {node.id!r}")
            ids.add(node.id)
            nodes.append(node)
        by_id = {n.id: n for n in nodes}
        by_title = {n.title: n.id for n in nodes}
        for node in nodes:
            resolved = []
            for dep in node.depends_on:
                dep_id = dep if dep in by_id else by_title.get(dep)
                if dep_id is None:
                    raise PlanError(f"step {node.title!r} depends on unknown step {dep!r}")
                resolved.append(dep_id)
            node.depends_on = resolved
        self._check_acyclic(nodes)
        return nodes

    @staticmethod
    def _check_acyclic(nodes: list[PlanNode]) -> None:
        deps = {n.id: list(n.depends_on) for n in nodes}
        visiting: set[str] = set()
        done: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in done:
                return
            if node_id in visiting:
                raise PlanError("cyclic dependency in plan")
            visiting.add(node_id)
            for dep in deps.get(node_id, []):
                visit(dep)
            visiting.discard(node_id)
            done.add(node_id)

        for node in nodes:
            visit(node.id)

    @staticmethod
    def ready_nodes(plan: list[PlanNode]) -> list[PlanNode]:
        """Nodes whose dependencies all succeeded and which have attempts left."""
        done = {n.id for n in plan if n.state == TaskState.SUCCEEDED}
        failed = {n.id for n in plan if n.state == TaskState.FAILED}
        blocked = {n.id for n in plan if n.state in (TaskState.BLOCKED, TaskState.WAITING_APPROVAL)}
        ready = []
        for node in plan:
            if node.state != TaskState.PENDING:
                continue
            if any(dep in failed or dep in blocked for dep in node.depends_on):
                continue
            if all(dep in done for dep in node.depends_on) and node.attempts < node.max_attempts:
                ready.append(node)
        return ready

    @staticmethod
    def is_complete(plan: list[PlanNode]) -> bool:
        return all(n.state in (TaskState.SUCCEEDED, TaskState.CANCELLED) for n in plan)

    @staticmethod
    def is_deadlocked(plan: list[PlanNode]) -> bool:
        if HTNPlanner.is_complete(plan):
            return False
        return not HTNPlanner.ready_nodes(plan) and not any(
            n.state in (TaskState.RUNNING, TaskState.WAITING_APPROVAL) for n in plan
        )

    def record_outcome(self, method_name: str, succeeded: bool) -> None:
        method = self.methods.get(method_name)
        if method is None:
            return
        total = method.times_used
        method.success_rate = (
            (method.success_rate * (total - 1) + (1.0 if succeeded else 0.0)) / total
            if total > 0 else (1.0 if succeeded else 0.0)
        )
