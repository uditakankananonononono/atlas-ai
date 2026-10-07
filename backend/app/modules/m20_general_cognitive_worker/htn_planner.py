"""HTN planning (spec 4.2.4): hierarchical task network decomposition.

Given a high-level goal, the planner first matches its method library; for
novel goals it asks an injected planner model (LLM) for a decomposition de
novo, validates it, and stores it as a learned method for future reuse.
Plans are DAGs of PlanNode with explicit dependencies and risk tiers.
"""
from __future__ import annotations

import hashlib
from types import MappingProxyType
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
        self._methods: dict[str, HTNMethod] = {}

    @property
    def methods(self):
        return MappingProxyType({name: method.model_copy(deep=True) for name, method in self._methods.items()})

    def register_method(self, method: HTNMethod) -> HTNMethod:
        method = self._validated_method(method)
        self._methods[method.name] = method
        return method.model_copy(deep=True)

    def _validated_method(self, method: HTNMethod) -> HTNMethod:
        method = method.model_copy(deep=True)
        validated = self._validate([node.model_dump(mode="json") for node in method.subtasks])
        for node, checked in zip(method.subtasks, validated):
            node.depends_on = checked.depends_on
        return method

    def _match_method(self, goal: str, *, context: str = "") -> HTNMethod | None:
        goal_tokens = set(tokenize(goal))
        if not goal_tokens:
            return None
        best: tuple[float, HTNMethod] | None = None
        for method in self._methods.values():
            if method.source == MethodSource.LEARNED:
                if method.generated_goal != goal or method.generated_context_sha256 != hashlib.sha256(context.encode()).hexdigest():
                    continue
            pattern_tokens = set(tokenize(method.goal_pattern))
            if not pattern_tokens:
                continue
            overlap = len(goal_tokens & pattern_tokens) / len(goal_tokens | pattern_tokens)
            if overlap >= 0.34 and (best is None or overlap > best[0]):
                best = (overlap, method)
        return best[1] if best else None

    def decompose(self, goal: str, *, context: str = "") -> list[PlanNode]:
        method = self._match_method(goal, context=context)
        if method is not None:
            method.times_used += 1
            return self._instantiate(method)
        if self.model is None:
            raise PlanError(f"no method matches goal and no planner model bound: {goal!r}")
        raw_steps = self.model.decompose(goal, context=context)
        nodes = self._validate(raw_steps)
        learned = HTNMethod(
            name=f"learned:{goal[:48]}:{hashlib.sha256((goal + chr(0) + context).encode()).hexdigest()[:16]}",
            goal_pattern=goal,
            subtasks=[n.model_copy(deep=True) for n in nodes],
            source=MethodSource.LEARNED,
            generated_goal=goal, generated_context_sha256=hashlib.sha256(context.encode()).hexdigest(),
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
            copy.state = TaskState.PENDING
            copy.attempts = 0
            copy.approval_id = None
            copy.result_summary = ""
            copy.output = None
        def remap(value):
            if isinstance(value, dict):
                result = {key: remap(item) for key, item in value.items()}
                if isinstance(result.get('$step'), str):
                    result['$step'] = id_map.get(result['$step']) or title_map.get(result['$step']) or result['$step']
                return result
            if isinstance(value, list): return [remap(item) for item in value]
            return value
        for copy in copies:
            copy.arguments = remap(copy.arguments)
            copy.depends_on = [
                id_map.get(dep) or title_map.get(dep) or dep
                for dep in copy.depends_on
            ]
        return copies

    def _validate(self, raw_steps: list[dict[str, Any]]) -> list[PlanNode]:
        if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= 128:
            raise PlanError("planner decomposition must be a list of 1..128 steps")
        nodes: list[PlanNode] = []
        ids: set[str] = set()
        for raw in raw_steps:
            if not isinstance(raw, dict) or not raw.get("title"):
                raise PlanError(f"invalid step: {raw!r}")
            if not isinstance(raw["title"], str) or not raw["title"].strip():
                raise PlanError("step title must be nonempty text")
            if raw.get("tool") is not None and (not isinstance(raw["tool"], str) or not raw["tool"].strip()):
                raise PlanError("step tool must be null or nonempty text")
            if "arguments" in raw and not isinstance(raw["arguments"], dict):
                raise PlanError("step arguments must be an object")
            deps = raw.get("depends_on", [])
            if not isinstance(deps, list) or any(not isinstance(dep,str) or not dep for dep in deps):
                raise PlanError("dependencies must be a list of nonempty step identifiers")
            attempts = raw.get("max_attempts", 3)
            if type(attempts) is not int or not 1 <= attempts <= 100:
                raise PlanError("max_attempts must be an integer in 1..100")
            if "id" in raw and (not isinstance(raw["id"], str) or not raw["id"].strip()):
                raise PlanError("step id must be nonempty text")
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
        duplicate_titles = {n.title for n in nodes if sum(x.title == n.title for x in nodes) > 1}
        for node in nodes:
            resolved = []
            for dep in node.depends_on:
                if dep not in by_id and dep in duplicate_titles:
                    raise PlanError("ambiguous dependency title; use unique step id")
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
        method = self._methods.get(method_name)
        if method is None:
            return
        total = method.times_used
        method.success_rate = (
            (method.success_rate * (total - 1) + (1.0 if succeeded else 0.0)) / total
            if total > 0 else (1.0 if succeeded else 0.0)
        )
