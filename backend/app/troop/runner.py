"""Troop runner: planner -> workers -> reviewer, with retries.

The planner turns a task into steps with dependencies. Independent steps run
in parallel threads. Every worker result goes to the reviewer; a rejected or
failed attempt is retried (the worker gets the reviewer's feedback) up to
max_attempts. A step whose dependency failed is blocked and never runs.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
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
        for name, value, upper in (("max_attempts", max_attempts, 20),
                                   ("max_workers", max_workers, 1000),
                                   ("max_steps", max_steps, 10000)):
            if type(value) is not int or not 1 <= value <= upper:
                raise PlanError(f"{name} must be an integer from 1 to {upper}")
        self.planner, self.worker, self.reviewer = planner, worker, reviewer
        self.max_attempts, self.max_workers, self.max_steps = max_attempts, max_workers, max_steps

    @staticmethod
    def _validate(plan, max_steps):
        if not isinstance(plan, Plan):
            raise PlanError("planner must return Plan")
        steps = plan.steps
        if not steps:
            raise PlanError("plan has no steps")
        if len(steps) > max_steps:
            raise PlanError("plan has too many steps")
        from .roles import Step
        if any(not isinstance(s, Step) or type(s.id) is not str or not s.id.strip()
               or type(s.depends_on) not in (tuple, list)
               or any(type(d) is not str for d in s.depends_on) for s in steps):
            raise PlanError("invalid step")
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
            try:
                v = self.reviewer.review(step, out)
                if type(v.ok) is not bool or type(v.reasons) not in (tuple, list) or any(
                        type(reason) is not str for reason in v.reasons):
                    raise ValueError("invalid reviewer verdict")
            except Exception as e:
                feedback = f"reviewer error: {e}"
                events.append({"role": "reviewer", "step": step.id, "attempt": attempt,
                               "ok": False, "error": str(e)})
                continue
            events.append({"role": "reviewer", "step": step.id, "attempt": attempt,
                           "ok": v.ok, "reasons": list(v.reasons)})
            if v.ok:
                return "completed", out, attempt, events
            feedback = "; ".join(v.reasons)
        return "failed", None, self.max_attempts, events

    def run(self, task):
        if type(task) is not dict or type(task.get("id")) is not str or not task["id"].strip():
            raise PlanError("task id is required")
        plan = self.planner.plan(task)
        self._validate(plan, self.max_steps)
        if plan.task_id != task["id"]:
            raise PlanError("planner task id mismatch")
        transcript = [{"role": "planner", "task": task["id"], "steps": [s.id for s in plan.steps]}]
        outputs, status, attempts = {}, {}, {}
        remaining = list(plan.steps)
        active = {}
        events_by_id = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            while remaining or active:
                for step in list(remaining):
                    if not all(d in status for d in step.depends_on):
                        continue
                    if any(status[d] != "completed" for d in step.depends_on):
                        status[step.id] = "blocked"
                        events_by_id[step.id] = [{"role": "runner", "step": step.id, "event": "blocked"}]
                        remaining.remove(step)
                    elif len(active) < self.max_workers:
                        inputs = {d: outputs[d] for d in step.depends_on}
                        active[pool.submit(self._run_step, step, inputs)] = step
                        remaining.remove(step)
                if active:
                    finished, _ = wait(active, return_when=FIRST_COMPLETED)
                    for future in finished:
                        step = active.pop(future)
                        st, out, n, events = future.result()
                        status[step.id], attempts[step.id] = st, n
                        events_by_id[step.id] = events
                        if st == "completed":
                            outputs[step.id] = out
        # Stable audit order, independent of thread completion order.
        for step in plan.steps:
            transcript.extend(events_by_id[step.id])
        done = sum(1 for v in status.values() if v == "completed")
        overall = "completed" if done == len(status) else ("failed" if done == 0 else "partial")
        return RunResult(overall, outputs, status, attempts, transcript, self.max_workers)
