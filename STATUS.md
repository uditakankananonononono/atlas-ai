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

## Fifth repair

- Row 243: actual Benders decomposition for a continuous box-bounded first stage with complete simple recourse. Master LP and recourse LP are separate; recourse duals create optimality cuts; upper/lower gap controls completion. Compared to an independently assembled full two-stage LP. No general integer Benders or feasibility-cut claim.
- Row 244: exact scalar Lagrangian dual for a single binary capacity constraint. Independent binary subproblems are solved at all dual breakpoints. The integrality gap is kept explicitly; a dual optimum is not a primal optimum. Exhaustive primal enumeration checks that the bound remains below the true optimum.
- Rows 245/246: real free CVXPY/SCS semidefinite and second-order-cone optimization. SDP uses PSD matrix plus affine trace equalities; SOCP uses affine cones and box bounds. Analytic eigenvalue/Cauchy-Schwarz optima, solver residuals and independent feasibility checks support the tests. Infeasible and inaccurate statuses are not reported converged. This uses an existing open-source solver, not a newly invented optimizer, and the exact supported mathematical programs are stated.
- All four rows remain SCOPED pending independent review. 62 focused tests passed. Later branches remain diagnostic and are not made complete by these repairs.

## Sixth repair

- Row 247: real geometric optimization of positive posynomials, with posynomial inequality constraints and strictly positive box. CVXPY applies a log-log convex transformation and runs SCS. It is an existing open-source solver, not a claim of inventing a novel method. Analytic x+1/x minimum, a constraint that moves the optimum, actual feasibility and invalid coefficients are tested.
- Row 248: real Dinkelbach iterations for affine fractional maximization over a bounded linear domain. A separate LP verifies denominator positivity over the entire feasible set, then each iteration solves the parametric LP and checks the residual. Tested against exact one-dimensional and enumerated two-dimensional vertex optima and honest iteration caps.
- Both rows remain SCOPED to the stated mathematical programs and pending independent review. 56 focused tests pass. No universal optimizer/full-spec claim. Rows249 onward remain open.

## Seventh repair

- Row 249: finite leader choice optimization with actual bounded follower LPs, then a separate optimistic-tie LP constrained to the follower optimum. Every leader value is evaluated against a genuine follower best response. Explicit infeasible choices and tie rule; not general continuous bilevel.
- Row 250: Robbins-Monro root estimation from evidence-linked observed vectors using 1/t updates, with per-observation trace and observed sample variance. No synthetic noise or data is generated. This is mean-root estimation, not arbitrary stochastic optimization.
- Row 251: prequential online linear squared-loss learning. Each prediction is made before the target update, then weights change with the stream. Tests check exact updates, order sensitivity, lack of target leakage, observed mean/variance and evidence rejection. These fixtures do not establish performance on real user data or independent truth of submitted evidence identifiers.
- All three rows remain SCOPED pending independent review. 56 focused tests passed. Rows252 onward and broad cognition remain open.

## Eighth repair

- Rows252-255: observed-feedback bandit policies now actually update arm statistics and select/explore. Epsilon-greedy returns an exploration/exploitation probability distribution; disjoint ridge LinUCB learns weights from contextual feedback; Beta-Bernoulli Thompson sampling updates posterior counts and samples the posterior; UCB1 uses observed counts/means and optimistic bonuses with explicit untried-arm priority.
- Thompson RNG is the actual Bayesian action policy, not random neural weights or generated reward data. Logged feedback may come from another policy; replay is not evidence of on-policy performance. Rewards and provenance are caller supplied, never invented. No deployed-action or causal reward claim. All rows remain SCOPED pending independent review.
- Tests prove exploration can choose the lower observed mean, context changes selection after learned updates, different posterior seeds generate actual distinct draws, exact repeatability with same seed, update arithmetic, duplicate evidence/invalid reward rejection and binary-outcome restriction. 59 focused tests passed. Rows256 onward remain open.

## Ninth repair

- Rows256/257: real sequential Hedge expert weighting and regret-matching policies. Pre-observation weights determine expected mixture loss/payoff; observed losses/payoffs then update the policy. Numerically stable normalization, exact comparator totals and evidence-linked per-round traces. No invented realized rewards or generic optimal-strategy promise.
- Rows258/259: actual repeated two-sided regret matching and simultaneous fictitious play for explicit finite zero-sum matrix games, with average strategies and max/min best-response exploitability certificate. These are computed numerical iterations, not fabricated external gameplay. Restricted to two-player zero-sum, not general-sum equilibrium solving.
- Slow convergence remains visible: matching pennies fictitious play at 10,000 iterations has gap0.014 and does not meet0.001. A named test checks that it reports iteration_limit, not converged; a looser0.03 test checks numerical approximation. Independent matrix-game LP checks value bounds on a nonuniform game.
- Focused59 tests pass; M20 rerun1,529 passed,0 failed. Rows235-259 now route to actual restricted algorithm implementations rather than old diagnostics. This does not verify full original breadth or any of the remaining story/cognition templates. All rebuilt rows remain SCOPED pending independent review.

## Tenth repair

- Row852 no longer copies a caller validity boolean. It enumerates propositional models, proves entailment or returns a countermodel, reports inconsistent premises/vacuous entailment, and leaves real-world soundness unverified. Restricted to12 propositional atoms with bounded formula complexity, not natural-language theorem proving.
- Rows844/845 no longer echo causal roles or a caller result. Explicit acyclic additive linear structural equations support actual do-intervention propagation and unit-level abduction-intervention-prediction, holding inferred exogenous noise constant. Tests distinguish mediated effects and held-fixed confounders, cut edges on intervention, compute exact unit counterfactuals, reject cycles and incomplete factual data. This does not discover causality or verify model assumptions from observations.
- All three rows remain SCOPED pending independent review. Focused73 tests pass; broad M20 logs recorded. Full breadth of causal/deductive reasoning remains unverified. Remaining static learning/reasoning branches stay open.

## Eleventh repair

- Rows848/849 now run exact finite stable-model reasoning, not static revisability flags. Symbolic Horn rules with unless atoms preserve alternative stable models and no-model inconsistency. Fact additions/removals actually retract or restore conclusions. At most12 optional atoms, no prioritized-default/real-world-truth claim.
- Row850 now searches explicit hypothesis subsets, computes positive Horn closure, rejects forbidden consequences, returns inclusion-minimal explanations with proof traces and supplied-cost ranking. Up to16 hypotheses; costs are not learned probabilities and explanations are not truth. Failure to explain yields an empty result, not plausible prose.
- Negative tests preserve ambiguous competing defaults, odd negation cycles, unsupported/duplicate hypotheses and absent explanation. Focused73 tests pass. All rebuilt rows SCOPED pending independent review; remaining formal/learning template breadth open.

## Twelfth repair

- Row812 now actually checks recall: supplied item answer keys, declared closed-book evidence, normalized exact response scoring, calibration, observed skill accuracy and delayed retry plan timestamps. Unattempted prompts do not expose answers or infer mastery. Closed-book declaration and answer-key correctness are not independently verified; no semantic grading claim.
- Row819 now targets the weakest measured subskills using evidence-linked scored accuracy and selects only real supplied exercise catalog entries; ties and missing exercises remain explicit. No latent skill model, difficulty adjustment, guaranteed improvement or generated filler exercises.
- Tests change scores/retry due time and target practice by changing actual outcomes; reject open-book attempts, duplicate evidence and missing source data. Focused71 tests pass. Both rows SCOPED pending review. Retry timestamps are plan data, not notifications scheduled by this repair.

## Thirteenth repair

- Mounted optimization and learning computation routes now bind signed authenticated tenant/actor identity, reject conflicting payload identity and cross-owner/cross-actor reference labels before computation, and return the authenticated identity. Reference labels remain metadata, not permission grants; these stateless functions retrieve no stored resources.
- Signed production OIDC HTTP canaries exercise actual mounted numerical/deduction behavior, unsigned rejection, forged identity headers, conflicting identities/references, and separate owner arithmetic. Malformed supported input shapes produce client errors. A finite-number/size/depth boundary rejects nonfinite payload data, not a universal compute-budget guarantee.
- Focused121 tests passed; M20 1554 passed, zero failed. This proves only these rebuilt stateless computation routes; broader shared GCW task/memory service isolation remains unverified. No cross-owner data disclosure was found in this slice.
