"""Step-verified tool-use reasoning (prediction-contract verification).

A tool-use loop where every proposed step is checked TWICE by a
programmatic verifier before it is allowed to count:

1. Pre-execution: the call is checked against the tool's argument
   schema and its precondition predicate on the current state.  An
   invalid call is blocked and never reaches the world.
2. Post-execution: the actor must attach an *expected-effect
   predicate* to the call BEFORE it runs (a prediction contract).
   After execution the predicate is evaluated against the actual
   observation and the before/after state pair.  A mismatch triggers
   a bounded repair: the actor re-proposes the step, given a
   structured violation report.

The verifier is not a model: no LLM call, no learned scorer, no
training.  Contracts are ordinary Python callables.

Prior art this is NOT (see atlas-ai experiments
e11_step_verified_tool_use/PRIOR_ART.md): ReAct (2210.03629) has no
step verification; ToolVerifier (2402.14158) verifies tool SELECTION
between candidates with a model; StepTool (2410.07745) is a
training-time reward; CRITIC (2305.11738) and Reflexion (2303.11366)
use model-generated post-hoc critique.  Here the check is an
executable predicate emitted before the call runs.

stdlib only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# An observation predicate: (observation, state_before, state_after) -> str|None
# None means satisfied; otherwise a human-readable violation note.
EffectPredicate = Callable[[Any, Any, Any], "str | None"]
# A precondition predicate: (state, args) -> str|None (None = satisfied)
PrePredicate = Callable[[Any, dict], "str | None"]
# The world executor: (state, tool_name, args) -> (observation, new_state)
Executor = Callable[[Any, str, dict], "tuple[Any, Any]"]


@dataclass(frozen=True)
class ToolSpec:
    """One tool's verification contract."""
    name: str
    required: tuple = ()          # required argument names
    arg_types: dict = field(default_factory=dict)   # name -> python type
    pre: "PrePredicate | None" = None
    # builds the expected-effect predicate for a concrete call; the
    # actor may tighten but never loosen what the spec requires
    effect: "Callable[[Any, dict], EffectPredicate] | None" = None


@dataclass(frozen=True)
class Step:
    """One proposed tool call plus its prediction contract."""
    tool: str
    args: dict
    expect: "EffectPredicate | None" = None   # actor-stated prediction
    note: str = ""                            # actor's one-line rationale


@dataclass(frozen=True)
class Violation:
    """A structured verifier finding, handed to the actor on repair."""
    stage: str        # 'unknown_tool' | 'schema' | 'precondition' | 'effect'
    tool: str
    detail: str


@dataclass(frozen=True)
class StepRecord:
    """What actually happened with one accepted step."""
    step: Step
    observation: Any
    repairs: int                # repairs spent before acceptance
    violations: tuple = ()      # Violations seen along the way


@dataclass(frozen=True)
class LoopResult:
    steps: tuple                # accepted StepRecords, in order
    blocked: int                # calls blocked pre-execution
    effect_misses: int          # accepted executions whose effect then failed
    exhausted: bool             # ran out of step or repair budget
    final_state: Any


def _check_schema(spec: ToolSpec, args: dict) -> "str | None":
    for name in spec.required:
        if name not in args:
            return 'missing required argument %r' % (name,)
    for name, typ in spec.arg_types.items():
        if name in args and not isinstance(args[name], typ):
            return 'argument %r must be %s, got %s' % (
                name, typ.__name__, type(args[name]).__name__)
    return None


class StepVerifier:
    """Pre- and post-execution verification against a tool registry."""

    def __init__(self, tools: "list[ToolSpec]"):
        self._tools = {t.name: t for t in tools}

    def verify_pre(self, step: Step, state: Any) -> "Violation | None":
        spec = self._tools.get(step.tool)
        if spec is None:
            return Violation('unknown_tool', step.tool,
                             'no such tool: %r' % (step.tool,))
        problem = _check_schema(spec, step.args)
        if problem is not None:
            return Violation('schema', step.tool, problem)
        if spec.pre is not None:
            problem = spec.pre(state, step.args)
            if problem is not None:
                return Violation('precondition', step.tool, problem)
        return None

    def verify_post(self, step: Step, state_before: Any,
                    observation: Any, state_after: Any) -> "Violation | None":
        """Evaluate the prediction contract after execution.

        The spec's own effect predicate (when the tool defines one) is
        the floor: it must hold.  The actor's stated predicate is
        checked too; if the actor stated nothing, only the floor runs.
        """
        spec = self._tools[step.tool]
        if spec.effect is not None:
            floor = spec.effect(state_before, step.args)
            problem = floor(observation, state_before, state_after)
            if problem is not None:
                return Violation('effect', step.tool,
                                 'spec effect: ' + problem)
        if step.expect is not None:
            problem = step.expect(observation, state_before, state_after)
            if problem is not None:
                return Violation('effect', step.tool,
                                 'actor prediction: ' + problem)
        return None


def run_verified_loop(actor: Callable, task: Any,
                      tools: "list[ToolSpec]", state: Any,
                      execute: Executor,
                      max_steps: int = 30,
                      max_repairs_per_step: int = 2) -> LoopResult:
    """Drive ``actor`` through verify -> execute -> verify-post cycles.

    ``actor(task, history, violation)`` returns the next Step.  On a
    pre-execution violation the call is blocked (never executed) and
    the actor is re-asked with the Violation, up to
    ``max_repairs_per_step`` times per step.  On a post-execution
    effect violation the step is recorded as a miss and the actor is
    re-asked with the Violation; the world KEEPS the executed effect
    (verification cannot un-happen a side effect).
    """
    verifier = StepVerifier(tools)
    history: "list[StepRecord]" = []
    blocked = 0
    effect_misses = 0
    violations: "list[Violation]" = []
    repairs = 0
    violation = None
    while len(history) < max_steps:
        step = actor(task, history, violation)
        if step is None:                      # actor finished
            break
        v = verifier.verify_pre(step, state)
        if v is not None:
            blocked += 1
            violations.append(v)
            repairs += 1
            if repairs > max_repairs_per_step:
                return LoopResult(tuple(history), blocked, effect_misses,
                                  True, state)
            violation = v
            continue
        before = state
        observation, state = execute(state, step.tool, dict(step.args))
        v = verifier.verify_post(step, before, observation, state)
        record = StepRecord(step, observation, repairs, tuple(violations))
        history.append(record)
        repairs = 0
        violations = []
        violation = None
        if v is not None:
            effect_misses += 1
            violation = v
    return LoopResult(tuple(history), blocked, effect_misses,
                      len(history) >= max_steps, state)
