"""Troop runner: planner -> workers -> reviewer, with retries.

The planner turns a task into steps with dependencies. Independent steps run
in parallel threads. Every worker result goes to the reviewer; a rejected or
failed attempt is retried (the worker gets the reviewer's feedback) up to
max_attempts. A step whose dependency failed is blocked and never runs.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .roles import PlanError, Plan, WorkerError  # noqa: F401  (PlanError re-exported)


@dataclass
class RunResult:
    status: str
    outputs: dict
    step_status: dict
    attempts: dict
    transcript: list
    max_workers: int = 0  # configured concurrency this run used, reported back


class TroopRunner:
    def __init__(self, planner, worker, reviewer, max_attempts=2, max_workers=4, max_steps=50):
        self.planner, self.worker, self.reviewer = planner, worker, reviewer
        self.max_attempts, self.max_workers, self.max_steps = max_attempts, max_workers, max_steps

    @staticmethod
    def _validate(plan, max_steps):
        steps = plan.steps
        if not steps:
            raise PlanError("plan has no steps")
        if len(steps) > max_steps:
            raise PlanError("plan has too many steps")
        ids = [s.id for s in steps]
        if len(set(ids)) != len(ids):
            raise PlanError("duplicate step id")
        for s in steps:
            for d in s.depends_on:
                if d not in ids:
                    raise PlanError(f"unknown dependency {d!r} for step {s.id!r}")
        done, layers, remaining = set(), [], list(steps)
        while remaining:
            layer = [s for s in remaining if all(d in done for d in s.depends_on)]
            if not layer:
                raise PlanError("plan has a dependency cycle")
            layers.append(layer)
            done.update(s.id for s in layer)
            remaining = [s for s in remaining if s.id not in done]
        return layers

    def _run_step(self, step, inputs):
        events, feedback, out = [], None, None
        for attempt in range(1, self.max_attempts + 1):
            try:
                out = self.worker.execute(step, inputs, attempt, feedback)
            except Exception as e:  # worker failure is data, not a crash
                msg = str(e)
                events.append({"role": "worker", "step": step.id, "attempt": attempt, "error": msg})
                feedback = f"worker error: {msg}"
                continue
            events.append({"role": "worker", "step": step.id, "attempt": attempt})
            v = self.reviewer.review(step, out)
            events.append({"role": "reviewer", "step": step.id, "attempt": attempt,
                           "ok": v.ok, "reasons": list(v.reasons)})
            if v.ok:
                return "completed", out, attempt, events
            feedback = "; ".join(v.reasons)
        return "failed", None, self.max_attempts, events

    def run(self, task):
        if not task.get("id"):
            raise PlanError("task id is required")
        plan = self.planner.plan(task)
        layers = self._validate(plan, self.max_steps)
        transcript = [{"role": "planner", "task": task["id"], "steps": [s.id for s in plan.steps]}]
        outputs, status, attempts = {}, {}, {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            for layer in layers:
                runnable = []
                for s in layer:
                    if all(status.get(d) == "completed" for d in s.depends_on):
                        runnable.append(s)
                    else:
                        status[s.id] = "blocked"
                        transcript.append({"role": "runner", "step": s.id, "event": "blocked"})
                futs = [(s, pool.submit(self._run_step, s, {d: outputs[d] for d in s.depends_on})) for s in runnable]
                for s, f in futs:
                    st, out, n, events = f.result()
                    status[s.id], attempts[s.id] = st, n
                    transcript.extend(events)
                    if st == "completed":
                        outputs[s.id] = out
        done = sum(1 for v in status.values() if v == "completed")
        overall = "completed" if done == len(status) else ("failed" if done == 0 else "partial")
        return RunResult(overall, outputs, status, attempts, transcript, self.max_workers)
