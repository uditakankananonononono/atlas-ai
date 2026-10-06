# Atlas rebuild status - October 7, 2026

Not complete. No full-spec completion claim is supported.

## Independent audit snapshots at main 313309b

These counts use different tests and must not be merged or rounded up:

- 2,006-row audit: VERIFIED 0, SCOPED 1,556, PARTIAL 230, OVERSTATED 220. No row behavior was reproduced individually. Many labels came from AST scanning or file-level inference.
- 2,009-row register audit: VERIFIED 771, SCOPED 1,027, PARTIAL 178, OVERSTATED 33. VERIFIED here means mechanically located row computation with passing tests, plus approximately 15 close reads. It is not a manual source read of every row.
- Missing is not a verdict in these audits. A complete missing-feature count is unknown.

The old `verified-pushed` ledger is historical builder attribution, not current verification. Existing paths, row numbers in source, canned invariants and passing constant-assert tests do not prove features work. Its original claims remain available for comparison.

## First repair, M20 and certification surfaces

- Three legacy semantic reports now return unverified, never pass based on file/path/text checks. Their 862 inventory rows are not certified. Artifact checks remain separate.
- Row 823's static metacognitive-loop strings were replaced with measured strategy calibration. Actual scored attempts produce per-attempt and per-strategy Brier loss, signed overconfidence and an evidence-linked observed strategy comparison. Empty/unscored/nonfinite/duplicate inputs fail. Ties do not invent a winner.
- Scope: descriptive calibration of caller-supplied observations. Not causal strategy evaluation, autonomous self-awareness or full metacognition. The full original row 823 remains PARTIAL.
- No models loaded, no paid API or keys used, no deployment attempted in this repair.
- Focused run: 379 passed. M20 suite: 1,448 passed, 1 failed. The failure is `test_full_loop_pauses_for_external_approval`: a dependent send remains PENDING after a completed read instead of becoming WAITING_APPROVAL. Reproduced in isolation. This path was not changed by the calibration repair. Full suite and independent audit of the new code are still outstanding.

## Remaining work

M20 is still open. Next: inspect all its overstated row branches against the source requirement, build real computations and execution paths, then request independent review. Later units follow the tier-ordered worklist. Other major gaps include absent model-backed cognition, research-method constants, unmounted research-method routes and production infrastructure.

## Second repair

- Row 236: replaced the clipped-gradient imitation with iterative ADMM for convex quadratic plus L1 regularization. Exact quadratic solve, soft-threshold subproblem, scaled dual update, primal/dual stopping tests, KKT residual, full iteration history and explicit iteration-limit result. Tested against an analytic soft-threshold optimum and an independent SciPy optimizer on a coupled problem. Nonconvex, nonsymmetric and nonfinite problems fail. This solver is SCOPED to the stated problem class, not all possible ADMM applications.
- Legacy cognitive scheduler no longer swallows approval infrastructure exceptions. It blocks and surfaces the error without calling an external adapter. The approval test now uses a real initialized SQLite approval store, verifies the pending request and execution only after approval.
- M20 rerun: 1,457 passed, 0 failed. This is module-suite evidence, not full-spec verification. The earlier failure remains in the first committed log; it was traced to a missing approval table and a swallowed scheduler exception, not a dependency ordering bug.
- Rows 236 and 823 now carry explicit current SCOPED/PARTIAL labels in the builder ledger; their original claims are preserved alongside them. All other old verified-pushed claims remain historical, not current certification. Independent review pending.

## Third repair

- Rows 235, 237, 238, 239: removed the diagnostic branches using solver names without solving. New iterative dual decomposition (separable quadratic with sum equality), coordinate descent and proximal gradient (quadratic plus L1), and Frank-Wolfe (quadratic on simplex) return numerical solutions, objective, convergence status, iteration trace and applicable optimality certificates. Scope is restricted to these explicitly stated convex problem classes. The ledger labels remain SCOPED; independent review pending.
- Tests: analytic solutions, KKT/gap certificates, independent SciPy optimizer comparisons, coordinate-by-coordinate updates, monotonic nonsmooth objective, invalid-problem failures and nonconvergence at an iteration cap. Frank-Wolfe can converge slowly on boundary optima: a three-coordinate case meets 1e-4 gap, not 1e-6, inside the 10,000 iteration budget; the API reports iteration_limit when it cannot meet the requested tolerance. Tests do not hide that behavior.
- Focused solvers/workbench: 65 passed. M20 rerun: 1,473 passed, 0 failed. No full-suite or full-spec completion claim.

## Fourth repair

- Row 240 runs Kelley cutting planes for a convex quadratic on a bounded box. Each new gradient generates a supporting-plane cut; an actual LP master supplies a lower bound, evaluated candidates supply upper bounds, and their gap controls convergence. Tested against analytic and independent SciPy optimization, monotonic lower-bound refinement and an iteration cap.
- Row 241 runs binary linear branch-and-bound: LP relaxation, fractional-coordinate branching, incumbent updates and both bound/infeasibility pruning. Exhaustive enumeration independently checks a binary optimum. A node cap does not claim optimality; infeasibility returns no solution.
- Row 242 runs restricted-master column generation for a finite explicit catalog of nonnegative equality-form LP columns. Actual LP duals price excluded columns and expand the master. Full-catalog LP independently checks the result. Requires a feasible initial master. This is not an implicit combinatorial pricing oracle or claim of handling unlimited columns.
- These three rows stay SCOPED to the named problem classes; independent review pending. SciPy dependency declared. 58 focused tests pass; M20 rerun 1,482 passed, 0 failed. Full suite not run. Later solver branches remain diagnostics, not complete solvers.
