# Module self-evaluation loop (self_eval): contract

Status: unreviewed build, local branch only. Not accepted, not landed, not wired.

## What it is
`backend/app/self_improve/self_eval.py` measures a module's own behaviour with
real executions and feeds failures and regressions into the EXISTING
self-improvement pipeline (`SelfImprovementEngine.record_gap`). It adds no
edits to `detector.py`, `events.py`, `engine.py`, `gate.py` or `mixin.py`.
Activation of anything stays behind the existing approval gate; this file
never activates, approves or generates code.

## Signals (all measured, none simulated)
1. Probe cases: caller-supplied callables are really called. Per case: pass,
   fail (wrong result) or error (raised Exception), plus wall latency from
   `time.perf_counter` (injectable `clock` for tests only).
2. History: each evaluation is appended as one JSON line to
   `<state_dir>/<module_slug>.self-eval.jsonl`. The baseline is the most recent prior line.
3. Optional local pytest run (`run_pytest`): a real subprocess; counts are
   parsed from pytest's own summary line, or None when unparseable.

## Frozen interface
- `Case(args=(), kwargs={}, expect=NO_EXPECT, check=None)`: with `expect`, pass iff `result == expect`; with `check`, pass iff `bool(check(result))` (an exception in check is an error); with neither, pass iff the call does not raise. Giving both `expect` and `check` raises ValueError.
- `Probe(name: str, fn: callable, cases: tuple[Case, ...])`: name non-empty, at least one case, else ValueError.
- `ModuleSelfEvaluator(module_slug, state_dir, *, latency_factor=3.0, latency_min_abs_s=0.001, clock=time.perf_counter, now=time.time)`.
  - `evaluate(probes, *, pytest_result=None) -> EvalReport` (ValueError on duplicate probe names; probes list non-empty). Appends to history after computing the baseline comparison.
  - `history() -> list[dict]` (raises SelfEvalError on a corrupt line, never skips it).
  - `record_gaps(report, engine) -> list` calls `engine.record_gap(signature, kind=, detail=, exemplar=)` once per distinct signature and returns what it returned.
- `run_pytest(paths, *, cwd, python=sys.executable, timeout=120) -> PytestResult(returncode, passed, failed, errors, duration_s, tail)`.
- `EvalReport`: module_slug, at, probes (tuple[ProbeResult]), total_cases, passed, failed, errored, pass_rate (float, or None when 0 cases), regressions (tuple[Regression]), baseline_at (float or None), pytest (PytestResult or None); `to_dict()`.
- `ProbeResult`: name, cases, passed, failed, errored, median_latency_s, max_latency_s, error_types (sorted tuple of exception class names).
- `Regression(probe, reason, detail)` reasons: `probe_regressed` (baseline had 0 failed and 0 errored, now more than 0), `latency_regressed` (median > latency_factor * baseline median AND difference > latency_min_abs_s), `probe_missing` (probe in baseline absent now). No baseline: `regressions` is empty and `baseline_at` is None.
- Errors: `SelfEvalError(ValueError)`.

## Gap events recorded by record_gaps
- Per probe with failed or errored > 0: signature `selfeval:<probe>:failing`, kind `repeated_error`.
- Per regression: signature `selfeval:<probe>:<reason>`, kind `capability_miss` for `latency_regressed`, else `repeated_error`.
- pytest returncode != 0: signature `selfeval:pytest:failing`, kind `repeated_error`.
The detector's own `min_occurrences` decides when a signature becomes a gap.

## LIMITS
1. It measures only the probes a caller supplies; it finds nothing about behaviour no probe covers.
2. Latency is wall time on one machine, per call, with no warmup or noise model; the factor rule can false-alarm on a busy host.
3. The baseline is only the previous run, not a trend or statistic.
4. Passing probes show the module still behaves as the probe expects, not that it improved.
5. Nothing here claims capability growth, learning or any benchmark.
6. Not wired into any module; adoption needs a separate, reviewed patch.
