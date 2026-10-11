"""Module self-evaluation loop: real measured signals into the gap pipeline.

See docs/SELF_EVAL_LOOP.md. Stdlib only. Never activates or generates code.
"""
from __future__ import annotations

import json
import os
import re
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable


class SelfEvalError(ValueError):
    pass


class _NoExpect:
    def __repr__(self) -> str:
        return "NO_EXPECT"


NO_EXPECT = _NoExpect()


@dataclass(frozen=True)
class Case:
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    expect: Any = NO_EXPECT
    check: Callable | None = None

    def __post_init__(self) -> None:
        if self.expect is not NO_EXPECT and self.check is not None:
            raise ValueError("give expect or check, not both")


@dataclass(frozen=True)
class Probe:
    name: str
    fn: Callable
    cases: tuple

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("probe name must be non-empty")
        if len(self.cases) == 0:
            raise ValueError("probe needs at least one case")


@dataclass(frozen=True)
class ProbeResult:
    name: str
    cases: int
    passed: int
    failed: int
    errored: int
    median_latency_s: float
    max_latency_s: float
    error_types: tuple


@dataclass(frozen=True)
class Regression:
    probe: str
    reason: str
    detail: str


@dataclass(frozen=True)
class PytestResult:
    returncode: int
    passed: int | None
    failed: int | None
    errors: int | None
    duration_s: float
    tail: str


@dataclass(frozen=True)
class EvalReport:
    module_slug: str
    at: float
    probes: tuple
    total_cases: int
    passed: int
    failed: int
    errored: int
    pass_rate: float | None
    regressions: tuple
    baseline_at: float | None
    pytest: PytestResult | None

    def to_dict(self) -> dict:
        return {
            "module_slug": self.module_slug, "at": self.at,
            "probes": [{**asdict(p), "error_types": list(p.error_types)} for p in self.probes],
            "total_cases": self.total_cases, "passed": self.passed, "failed": self.failed,
            "errored": self.errored, "pass_rate": self.pass_rate,
            "regressions": [asdict(r) for r in self.regressions],
            "baseline_at": self.baseline_at,
            "pytest": None if self.pytest is None else asdict(self.pytest),
        }


def _run_case(fn, case, clock):
    t0 = clock()
    try:
        result = fn(*case.args, **case.kwargs)
        t1 = clock()
        if case.check is not None:
            status = "pass" if case.check(result) else "fail"
        elif case.expect is not NO_EXPECT:
            status = "pass" if result == case.expect else "fail"
        else:
            status = "pass"
        return status, t1 - t0, None
    except Exception as exc:  # noqa: BLE001 - the error itself is the measurement
        return "error", clock() - t0, type(exc).__name__


class ModuleSelfEvaluator:
    def __init__(self, module_slug: str, state_dir, *, latency_factor: float = 3.0,
                 latency_min_abs_s: float = 0.001, clock=time.perf_counter, now=time.time) -> None:
        safe = "".join(c for c in str(module_slug) if c.isalnum() or c in "-_")
        if not module_slug or safe != module_slug:
            raise ValueError(f"unsafe module slug {module_slug!r}")
        self.module_slug = module_slug
        self._dir = Path(state_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"{module_slug}.self-eval.jsonl"
        self._factor = latency_factor
        self._min_abs = latency_min_abs_s
        self._clock = clock
        self._now = now

    def history(self) -> list:
        if not self._path.exists():
            return []
        out = []
        for n, line in enumerate(self._path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SelfEvalError(f"corrupt history line {n}: {exc}") from exc
        return out

    def evaluate(self, probes, *, pytest_result: PytestResult | None = None) -> EvalReport:
        probes = list(probes)
        if not probes:
            raise ValueError("at least one probe is required")
        names = [p.name for p in probes]
        if len(set(names)) != len(names):
            raise ValueError("duplicate probe names")
        hist = self.history()
        baseline = hist[-1] if hist else None
        results = []
        for p in probes:
            counts = {"pass": 0, "fail": 0, "error": 0}
            lats, types = [], set()
            for case in p.cases:
                status, lat, etype = _run_case(p.fn, case, self._clock)
                counts[status] += 1
                lats.append(lat)
                if etype:
                    types.add(etype)
            results.append(ProbeResult(p.name, len(p.cases), counts["pass"], counts["fail"],
                                       counts["error"], statistics.median(lats), max(lats),
                                       tuple(sorted(types))))
        regressions = []
        if baseline is not None:
            base = {b["name"]: b for b in baseline["probes"]}
            for r in results:
                b = base.get(r.name)
                if b is None:
                    continue
                if b["failed"] == 0 and b["errored"] == 0 and (r.failed + r.errored) > 0:
                    regressions.append(Regression(r.name, "probe_regressed",
                                                  f"baseline clean, now failed={r.failed} errored={r.errored}"))
                bl = b["median_latency_s"]
                if r.median_latency_s > self._factor * bl and r.median_latency_s - bl > self._min_abs:
                    regressions.append(Regression(r.name, "latency_regressed",
                                                  f"median {r.median_latency_s} vs baseline {bl}"))
            for b in baseline["probes"]:
                if b["name"] not in names:
                    regressions.append(Regression(b["name"], "probe_missing", "probe absent from this run"))
        total = sum(r.cases for r in results)
        passed = sum(r.passed for r in results)
        report = EvalReport(
            self.module_slug, self._now(), tuple(results), total, passed,
            sum(r.failed for r in results), sum(r.errored for r in results),
            passed / total if total else None, tuple(regressions),
            None if baseline is None else baseline["at"], pytest_result)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(report.to_dict(), sort_keys=True) + "\n")
        return report

    def record_gaps(self, report: EvalReport, engine) -> list:
        planned = {}
        for p in report.probes:
            if p.failed or p.errored:
                planned.setdefault(f"selfeval:{p.name}:failing", (
                    "repeated_error", f"probe {p.name}: passed={p.passed} failed={p.failed} errored={p.errored}",
                    {"probe": p.name, "passed": p.passed, "failed": p.failed, "errored": p.errored,
                     "error_types": list(p.error_types)}))
        for g in report.regressions:
            kind = "capability_miss" if g.reason == "latency_regressed" else "repeated_error"
            planned.setdefault(f"selfeval:{g.probe}:{g.reason}", (kind, g.detail,
                                                                  {"probe": g.probe, "reason": g.reason}))
        if report.pytest is not None and report.pytest.returncode != 0:
            t = report.pytest
            planned.setdefault("selfeval:pytest:failing", (
                "repeated_error", f"pytest returncode={t.returncode} passed={t.passed} failed={t.failed} errors={t.errors}",
                {"returncode": t.returncode, "passed": t.passed, "failed": t.failed, "errors": t.errors}))
        return [engine.record_gap(sig, kind=k, detail=d, exemplar=x) for sig, (k, d, x) in planned.items()]


_COUNT = re.compile(r"(\d+) (passed|failed|errors?)")


def run_pytest(paths, *, cwd, python: str = sys.executable, timeout: float = 120) -> PytestResult:
    paths = list(paths)
    if not paths or any((not isinstance(p, str)) or not p or p.startswith("-") for p in paths):
        raise ValueError("paths must be non-empty strings that do not start with '-'")
    env = {k: v for k, v in os.environ.items() if not k.startswith("AWS_")}
    t0 = time.perf_counter()
    try:
        proc = subprocess.run([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *paths],
                              cwd=str(cwd), env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise SelfEvalError(f"pytest timed out after {timeout}s") from exc
    dur = time.perf_counter() - t0
    out = proc.stdout + proc.stderr
    lines = [l for l in proc.stdout.splitlines() if l.strip()]
    found = _COUNT.findall(lines[-1]) if lines else []
    if found:
        c = {"passed": 0, "failed": 0, "error": 0}
        for n, k in found:
            c["error" if k.startswith("error") else k] += int(n)
        counts = (c["passed"], c["failed"], c["error"])
    else:
        counts = (None, None, None)
    return PytestResult(proc.returncode, *counts, dur, out[-2000:])
