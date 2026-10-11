# Self-improvement change gate (improvement_gate): contract

Status: unreviewed build, local branch only. Not accepted, not landed, not wired.
Child of the self_eval commit. Adds new files only. Defines NO c30 module, route or landing logic.

## What it is
`backend/app/self_improve/improvement_gate.py` decides whether a proposed self-improvement
change may exist on a `selfimprove/*` branch. It checks evidence a caller attaches and records
the decision. It runs no git, merges nothing and writes only to its own state directory.
`Authorization.merge_allowed` is always False: merging to main needs a separate human decision.

## Frozen interface
- `ChangePlan(module_slug, feature, branch, files: tuple[str,...], target="branch")`; `digest()` = sha256 of canonical JSON with sorted files.
- `GateEvidence(plan_digest, tests: PytestResult, mutation: MutationRun, baseline_passed=None, equivalent_declared=0)`.
- `MutationRun(total, killed, survived, nomatch, timeouts, results)`.
- `ImprovementGate(module_slug, state_dir, *, sandbox_roots, max_changes_per_window=3, window_s=86400, max_files_per_change=10, now=time.time)`:
  `authorize(plan, evidence) -> Authorization(plan, digest, at)`, `ledger() -> list[dict]`, `changelog() -> str`.
- `run_mutations(target_rel, mutants, pytest_paths, *, cwd, python, timeout)`: copies `cwd` to a scratch dir, applies each (old, new) replacement once, and runs pytest there. Outcomes: killed, survived, nomatch (old text absent), timeout. The baseline must pass first, else `PLAN_REFUSED_UNGATED`. Runs with `PYTHONDONTWRITEBYTECODE=1` (same effect as `python -B`) so a same-size, same-second mutant is never hidden by a stale `.pyc`; the environment is restored afterwards.
- `PlanRefused(ValueError)` with `.code`, `.detail`; `GateLedgerError(ValueError)` for a corrupt ledger.

## Refusal codes and order of checks
1. `PLAN_REFUSED_BAD_PLAN`: blank feature/module/branch/file, no files, module mismatch, target not "branch", branch lacking the `selfimprove/` prefix, non-ChangePlan.
2. `PLAN_REFUSED_SELF_MERGE`: target "main", or branch is main/master/origin/main/HEAD and similar names.
3. `PLAN_REFUSED_OUTSIDE_SANDBOX`: a file is absolute, uses `..`, `.`, `~` or a backslash, or is not under a configured root prefix.
4. `PLAN_REFUSED_BUDGET`: too many files in one change; or the window budget is spent (checked after evidence).
5. `PLAN_REFUSED_UNGATED`: evidence or its tests/mutation part missing, digest mismatch, 0 mutants, counts not adding up, any mutant not applied, declared equivalents above survivors, zero counted passing tests.
6. `PLAN_REFUSED_REGRESSION`: tests failing (return code, failed or errors), test count below `baseline_passed`, survivors above declared equivalents.
Timeouts count as detected. Refusals are logged (code, digest) but do not use budget.

## State
`<state_dir>/<slug>.improvement-ledger.jsonl` (events authorized/refused) and `<slug>.changelog.md`
(one human-readable line per authorization).

## LIMITS
1. The gate trusts the evidence object's numbers; it does not itself rerun tests (use `run_pytest` and `run_mutations` to produce them).
2. Mutants are caller-chosen; a weak mutant list gives weak evidence. It does not generate mutants.
3. `declared equivalents` are a caller's claim, recorded but not verified.
4. A scratch copy of `cwd` is made per run; large trees are slow.
5. It authorizes the existence of a branch change only. It performs no branch creation, commit, merge or deploy.
6. It does not implement the c30 route/module; placement there needs a separate decision.
