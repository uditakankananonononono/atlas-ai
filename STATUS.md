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

## Independent falsification review and follow-up

- Independent reviewer reported all first twelve repair commits confirmed against randomized CVXPY/SciPy/brute-force oracles and stub mutations within their stated scopes. This is not verification of full original feature breadth.
- Reviewer found an untested iff operator and epsilon-greedy's unsupported first-arm preference without feedback. Added biconditional entailment/countermodel tests (the iff-to-or mutation fails) and a no-feedback uniform policy with null greedy_arm, explicitly no empirical preference.
- Remaining numerical caveats: dual decomposition returns unprojected block argmins, feasible only within reported residual tolerance. Conic imports require installed CVXPY, so missing dependency breaks workbench import. Bilevel follower tie LP uses exact floating equality and can be fragile. Regret-matching's matching-pennies zero gap from uniform initialization is not evidence of learning; nonuniform independent cases matter.
- Follow-up M20 suite:1558 passed, zero failed. Actual iff-to-or mutation run:1 failed,7 passed; original source restored. Mutation failure log retained.

## Shared model package refresh

- Vendored instinct_models refreshed to upstream shared-models5cb4655 including LexicalToolModel. Recursive comparison against that checked-out upstream package matches, except Atlas-only VENDORED.md and generated bytecode. Package untouched locally.
- Atlas shared-layer tests:14 passed. LexicalToolModel is a lexical tool router, not trained neural weights; no missing model weight claim is upgraded by vendoring.

## Fifteenth repair: deployment-default auth and configured GCW state

- Auth now fails closed by default, including unset/development ATLAS_ENV. Insecure header identity requires explicit ATLAS_DEV_NO_AUTH=1 outside production and logs a loud warning. Production ignores that opt-in. Legacy local test fixtures explicitly opt in; deployment-default tests remove it and assert rejection. Public capabilities lists describe method names only.
- Reproduced signed owner-b retrieving signed owner-a's fact when an integrator bound a single GCW service. Not a deployed-production disclosure claim: default application has no GCW service bound. Before-fix failing reproduction retained.
- GCW stateful adapters now select only an explicitly bound authenticated-tenant service via dependency injection; unbound tenant fails503. Reusing one mutable instance across tenant bindings is rejected. Signed canaries cover facts, tasks, resume/retrospective, trace/standup and ingestion/deduplication separation. Foreign task contexts are rejected before sensory ingestion.
- Integration docs now require tenant-scoped service, stores, tools, clients and approval gates. This is in-process HTTP state isolation, not durable multi-process tenant storage or identity authorization for upstream tools. Those integrations remain open.
- Focused82 passed; M20 plus auth1565 passed, zero failed. Full suite not yet run. No broad feature-completion claim.

## Sixteenth repair: single allowlisted development auth policy

- Reviewer re-attack found explicit no-auth opt-in also worked with unknown/deployed environment labels because the first guard denied only production. Fixed with one shared environment policy used by auth, GCW binding fallback and ProductionConfig: default production; normalize surrounding whitespace/case; bypass only explicit development/local plus opt-in.
- New tests reject bypass for unset/empty/prod/staging/live/production/production-with-space/garbage labels, test allowed local labels and default platform config. M20/auth/platform1597 passed, zero failed.
- Inspected legal/support, atomic-concepts-70-92 and execution-truth-ledger adapters and engines: functions transform caller input, do not access tenant stores or global service state. Main application mount already authenticates them. Direct standalone router mounting requires authentication too; no endpoint-local tenant attribution claim is added for these stateless legacy operators.
- Binding requirements now explicitly note that separate service instances can still share a backend store/DB namespace; top-level object identity rejection cannot detect that. Integrator must enforce tenant-keyed storage and tool-client permissions.
- Full-suite attempt initially failed collection on missing declared dependencies, installed free declared packages, then rerun progressed beyond45% without observed failure before being stopped because source changed for this auth follow-up. It is not a full-suite result; rerun remains open.

## Seventeenth repair: durable runtime owner binding

- Reproduced signed owner-b reading owner-a repository facts through durable GCW HTTP with a temporary database. The real mounted route has duplicated module prefixes; initial shorter-route probe hit404 and was not accepted as proof. Observed OpenAPI path used for the failing canary and fix.
- All durable runtime adapters now select an explicitly owner-bound runtime via authenticated dependency. Binding must match repository tenant. Unknown owner fails503; runtime repository mismatch fails closed. Explicit insecure local development retains the legacy local fixture binding only.
- Signed canaries exercise separate repositories on the same SQL engine: facts/tasks remain tenant-scoped, foreign task detail/step/close404, wrong binding rejected, own task accessible. Does not independently verify all sandbox filesystem/client namespaces or fix duplicated URL prefixes.
- Focused31 passed; M20/auth1579 passed. Root/platform after installing missing declared free dependencies:814 passed,2 failed (obsolete all-verified ledger test and Next14 version test). These failures remain open; no full-suite passing claim.

## Eighteenth repair: ledger count reconciliation and stale test contracts

- Ledger top-level counts now match actual row labels:1972 historical verified-pushed,33 SCOPED,1 PARTIAL,4 removed. Preserved the original all2006 verified-pushed count as historical_counts. This is row-label reconciliation, not independent verification of1972 untouched historical claims.
- Named test computes counts from rows, checks total2010 including removed, and checks original claim/evidence retention for every rebuilt row. It no longer demands that honest scoped/partial annotations disappear.
- Frontend version fixture now checks existing declared16.3.6 against package-lock, retaining app-router source checks. Frontend package/version unchanged; test previously pinned obsolete14.2.32. This is not a build/security compatibility proof.
- Root/platform suite817 passed after local declared dependency installation. Full module and remaining integration suites still open.

## Reserved local owner guard

- Signed OIDC tenant named local now receives403 on both service and durable-runtime selectors; it cannot resolve development bindings. Production per-tenant runtimes are not auto-provisioned or claimed live. Unbound tenants fail503 until an integrator binds them. Focused owner HTTP8 passed.

## Legacy test contract repair

- Old depth-sweep tests submitted placeholder objectives/source labels to repaired measured/formal algorithms and expected support envelopes. They now explicitly require rejection for missing real observations/formulas/models on rows812/819/823/844/845/848/849/850/852. Actual named computation and mutation tests remain in their focused files. ADMM envelope test now supplies a real quadratic/L1 problem rather than unrelated generic optimization fields.
- Clean-database migration test compares the upgraded revision with the actual Alembic graph head, retaining its required table/column checks. No migration changed to satisfy a stale historical head string.
- Contract tests159 passed. First module batch had1402 passes,12 skipped and10 stale-contract failures before these changes; second independent module batch590 passed. Full module coverage still incomplete.

## Broad-suite reconciliation

- Updated M22 wiring fixture to preserve required GitHub/PyPI/npm collectors while admitting the existing source-collector set, checking unique names. HTTPS checks remain on the three URL-bearing base collectors; separate source-parser tests exercise the added collectors. No collector implementation changed.
- All nine module-file batches completed passing after named legacy-contract repairs and local installation of declared free dependencies. Results are split-process suite evidence, not a single-process full-suite run. Exact file manifest and each batch log retained under audits/rebuild-20261007/suite-batches.
- Root/platform817 passed; other integration/runtime/migration/commercial/self-improve suites58 passed. Skipped tests remain skipped, not verified. Passing legacy tests do not upgrade historical feature claims.

## Missing conic dependency boundary

- CVXPY is loaded only when conic/geometric solving is requested. A fresh-process test intercepts every CVXPY import, proves workbench ADMM still computes1.8 and SDP reports explicit missing-dependency failure. No fallback fake conic result. Existing conic/geometric numerical tests still exercise actual installed CVXPY.
- Updated stale workbench module description to distinguish real repaired algorithms/free solvers from remaining narrative analysis/templates.

## Observed-review spaced repetition (row810)

- Replaced arbitrary ease-multiplied first intervals and fixed default calendar anchor with source-grounded SM-2 state transitions: first interval1 day, second6 days, later ceil(previous interval*prior ease), grade-based ease update/floor, failure count reset, same-session repeat flag. Exact reference inspected: https://super-memory.com/english/ol/sm2.htm . Grades/times are evidence-linked caller inputs, not fabricated observations.
- Requires timezone-aware review timestamp and actual prior repetition state. No missing dates defaulted to January2026. Computed due timestamps are plans, not scheduled notifications, and heuristically derived SM-2 does not prove user retention or optimal timing.
- Exact interval/state/failure/quality tests reject bad grades, nonfinite ease, naive timestamps and missing evidence. Focused229 passed; M20/ledger1583 passed. Row810SCOPED pending independent review. Current row counts1971 historical verified-pushed,34 SCOPED,1 PARTIAL,4 removed.

## Evidence-driven support progression (rows821/822)

- Replaced literal support-level flags with actual consecutive-success state transitions over an explicit supplied exercise catalog. Every attempt names a real task at the active level and unique scored evidence. Required success streak advances one level; failure restores one level and resets streak. Missing level tasks return empty, not generated filler. No latent mastery or empirically optimized threshold claim.
- Added independent tests of advancement, failure rollback, duplicate/wrong-level evidence rejection and saturation at independent. Rows821/822 SCOPED pending review. Focused240 passed; updated M20/ledger result retained in support-m20.log.
- Reviewer SM-2 mutation gap fixed: four distinct interval/ease cases now pin actual ceiling formula. Real constant17 mutation run fails4 tests with10 passing; source restored. Prior-ease convention remains explicit.
- Frontend manifest boundary documented: CI and Docker use frontend/16.3.6. Root package/lock remains a legacy duplicate Next15/React19 and was not validated by frontend16 tests; no silent manifest merge.

## Actual keyed assessment (rows829/830/831)

- Replaced purpose-only templates with scored evidence: unique supplied items/keys, explicit positive weights, one evidence-linked response per known item, exact normalized answer matching, earned/possible points and per-objective observed scores/coverage.
- Formative assessment returns error-specific answer feedback and next-step review. Summative final score exists only for a complete response set; missing responses are unknown, not zero or mastery. Diagnostic needs derive from measured per-objective score under an explicit threshold, with unassessed objectives separate. Not semantic essay grading, psychometric validity, independent grading provenance or award/pass-fail authority.
- Tests change weighted scores/needs with actual answers, distinguish incomplete from failing, reject duplicate/unknown evidence and nonfinite weights. Focused225 passed; M20/ledger1600 passed. All three rowsSCOPED pending review. Historical labels1966,SCOPED39,PARTIAL1,removed4 remain label counts, not verified capability counts.

## Measured progress (row826)

- Requires actual dated evidence, strict chronology and a declared measurement unit/direction. Computes observed delta and endpoint rate; separates target_reached from on_track. Decreasing goals are handled correctly rather than always latest>=target.
- A future deadline plus multiple observations permits explicitly uncalibrated endpoint linear extrapolation; no deadline/no rate means unknown on_track, not a guessed forecast. Rejects mixed units, nonfinite values/overflow, duplicate evidence and naive/out-of-order times. No predictive model or evidence-verification claim.
- Focused226 passed; M20/ledger1607 passed. Row826SCOPED pending review. Current row labels1965 historical,40SCOPED,1PARTIAL,4removed.

## Actual graph transduction (row853)

- Replaced copied source/target/similarity labels with actual harmonic graph label propagation. Finite supplied symmetric nonnegative graph and evidence-linked pinned class labels yield a constrained Laplacian linear solve, harmonic residual and energy. Explicit connected-label reachability and condition checks reject unsupported targets; ties remain null predicted_label with all candidate labels.
- Similarities/labels are caller assumptions, not independently learned or verified. Class scores are harmonic weights, not calibrated probabilities. Restricted to the supplied instance graph, not population generalization or semantic/causal inference. Source inspected: https://aaai.org/papers/icml03-118-semi-supervised-learning-using-gaussian-fields-and-harmonic-functions/ .
- Weighted-edge changes alter predicted labels; exact chain interpolation and energy checked; missing anchor/negative/asymmetric graph rejected. Focused225 passed; M20/ledger1613 passed. Row853SCOPED pending review; historical1964,SCOPED41,PARTIAL1,removed4 labels remain scope bookkeeping.

## Finite observed boolean induction (row851)

- Replaced caller pattern/strength echo with exhaustive finite conjunction hypothesis search. Explicit complete boolean features and evidence-linked labels determine consistent version space, minimum observed training errors and simplest consistent rules. Unseen target consensus uses all consistent rules, preserving disagreement or inconsistent evidence as null.
- Restricted to at most8 boolean features/6561 conjunctions and1000 observations, not universal induction or a trained neural model. No future accuracy, real-world truth, calibrated confidence or independent label provenance claim. Caller pattern/strength ignored.
- Named tests learn positive/negated rules from changed labels, preserve unseen ambiguity and contradiction, reject duplicate/nonboolean observations. Focused224 passed; M20/ledger1618 passed. Row851SCOPED pending review; labels1963 historical,42SCOPED,1PARTIAL,4removed.

## Actual exercise interleaving (row811)

- Replaced repeated skill-index cycling and constant variety flag with a largest-remaining-count scheduler over actual supplied exercise records. Defers previous skill, uses every exercise exactly once; impossible imbalanced catalogs preserve unavoidable adjacent repeats and report that status rather than claiming success.
- Named tests verify exact catalog conservation, no adjacent repeats, impossible-case visibility and64 small count combinations against the exact multiset feasibility inequality. No generated exercises, curriculum optimum or learning-gain claim. Row811SCOPED pending review.
- Focused223 passed; M20/ledger1622 passed. Labels1962 historical,43SCOPED,1PARTIAL,4removed. Broad original breadth remains unfinished.

## Actual finite spatial constraints (row842)

- Replaced objects/relation/frame echo with bounded2D axis-order linear constraints, genuine LP feasibility and query min/max signed separation. Queries return universal satisfaction within the supplied feasible set, possible layout or actual violating counterexample. Positive-gap cycles are inconsistent, not quietly retained as output labels.
- Caller explicitly supplies frame and coordinate boxes. Restricted to non-strict east/west/north/south minimum-separation constraints, not vision, metric/rotation geometry, maps or physical current location. Numerical tolerance1e-8; witnesses are feasible layouts, not unique object placements. No diagram/visual-output claim.
- Tests prove transitive separation, concrete counterexample/supporting assignments and positive/zero-gap cycle distinctions. Focused224 passed; M20/ledger1627 passed. Row842SCOPED pending review; labels1961 historical,44SCOPED,1PARTIAL,4removed.

## Actual temporal constraint reasoning (row843)

- Replaced event sorting/relation echo with finite simple temporal network difference constraints, all-pairs closure, negative-cycle consistency detection, implied minimum/maximum gaps and validated feasible relative-time witness. Queries distinguish guaranteed from possible separation. Disconnected event bounds stay null/unbounded, not fabricated dates.
- Restricted to declared-unit relative scalar time gaps, not calendar scheduling/timezone conversion or verified real-world events. Tolerance1e-9, witness checked within1e-8. No absolute anchor or notification effect.
- Tests prove transitive ranges, positive/zero cycles, unknown ordering and reverse negative gaps; reject nonfinite/unknown bounds. Focused224; M20/ledger1632 passed. Row843SCOPED pending review. Current labels1960 historical,45SCOPED,1PARTIAL,4removed.

## Actual finite model reasoning (row839)

- Replaced copied entities/predictions with finite-domain constraint model enumeration. Explicit typed scalar domains and comparison predicates yield actual feasible assignment count, possible values and query entailment/supporting/countermodels across all supplied models. Inconsistent premises report unknown entailment, not vacuous real-world certainty.
- Maximum65536 assignments,10 variables. Not continuous simulation, scientific model learning, natural-language reasoning or independent premise validation. Literal-versus-variable right operands explicit; ordered comparisons require numerical operands.
- Tests compute unique transitive model, ambiguous supported/countermodel query, contradiction, literal/name distinction and size rejection. Focused224; M20/ledger1637 passed. Row839SCOPED pending review; labels1959 historical,46SCOPED,1PARTIAL,4removed.

## Actual finite fuzzy inference (row847)

- Replaced membership min/max summaries with zero-order Sugeno rule inference: nested min/max/complement antecedents, explicit weights, per-rule firing/contribution trace and weighted numerical output. No-firing rule set produces null rather than invented fallback.
- Memberships/consequents are supplied assumptions, not learned or independently verified probabilities/truth. Restricted finite scalar rule inference, no live control deployment. Rejects invalid/boolean/nonfinite memberships, unknown atoms and duplicate rules.
- Tests alter memberships, weights and consequents to change measured output and pin nested logic. Focused226; M20/ledger1644 passed. Row847SCOPED pending review; labels1958 historical,47SCOPED,1PARTIAL,4removed.

## GCW private model context boundary

- GCW planner/executive now explicitly request private routing. General named-model chain skips all hosted-free/hosted-paid routes for private tasks, regardless of token/paid flag, and stops if configured local/self-hosted routes fail. Other public callers retain their existing routing semantics.
- Tests intercept provider calls: configured HF token plus paid flag does not receive private goal/context or reflection data; named Inkling uses only its self-hosted route. Local unavailable becomes honest planner error/executive unavailable, not a stub answer. Focused25 passed; combined M20/catalog/shared-layer result retained in private-model-m20.log.
- These tests use transport fixtures and do not prove a live local model is installed or running. LOCAL/SELF_HOSTED are configuration labels; integrators must point endpoints at their owner-controlled infrastructure. No hosted model called in this repair, no keys collected or credits spent.

## Strict model output boundary

- Model adapters now parse a complete JSON payload (or single fenced payload), rejecting trailing bytes, duplicate keys, nonfinite constants and oversized responses. Planner rejects unknown tool names and invalid/empty/oversized step lists rather than letting unknown tools become plausible task plans. Tool-risk floors still enforced.
- Executive malformed/nonobject JSON becomes explicit unavailable, not prose relabelled as successful reasoning. Local-model tests remain transport fixtures, not live weights/execution evidence.
- Focused19 passed; M20 result logged in strict-model-m20.log. Remaining production-model availability and quality remain open.

## Validated Horn rule inference (row838)

- Old rule loop had real closure but silently stringified malformed/missing conclusions and ignored negation. Now validates positive symbolic rule/atom structure, rejects unless rather than silently treating defaults as unconditional, returns rule/premise proof links and query entailment.
- Unsupported cycles derive nothing; not entailed does not mean false in the real world. Supplied facts/rules remain unverified premises. Restricted <=1000 facts/rules, no natural-language rule extraction or negation semantics.
- Named multi-step conjunctive proof, unsupported cycle, fact-change and bad-rule rejection tests. Focused225; M20/ledger1662 passed. Row838SCOPED pending review;1957historical,48SCOPED,1PARTIAL,4removed labels.

## Learning/reasoning scaffold claim retraction

- The remaining24 learning/reasoning branches are now explicitly planning_scaffold_only in API evaluation/catalog. capability_executed=false; named capability not executed, copied fields/static prompts are not reasoning evidence. Arbitrary nonempty inputs cannot turn them into executed capability claims.
- Retracted their ledger historical verified-pushed status to PARTIAL with original claims/evidence preserved. This removes overstated claims, not missing implementation work. Complete input metric remains a nonempty-field ratio only, explicitly not validity or evidence quality.
- Restricted computed rows remain marked as such, not full capability. Focused222; M20/ledger1665 passed. Current labels1933 historical,48SCOPED,25PARTIAL,4removed. Independent review and full original-spec breadth remain open.

## Story capability claim retraction (rows260-280)

- These21 branches compute supplied-text metrics, graph reachability or template formatting, not full named creative generation/development. API/catalog now labels supplied_text_diagnostics, named_generation_capability_executed=false. General algorithm_executed claim restricted to actual optimizer rows. Removed scene-count pseudo-confidence; more scenes do not establish confidence.
- All21 ledger rows PARTIAL with historical evidence retained. Existing limited metric/template outputs remain available, but novelty/originality/quality proxy fields are not validated creative capability and no rendered visual storyboard was made. Named tests check the new boundary for every row.
- Focused56; M20/ledger1667 passed. Current labels1912historical48SCOPED46PARTIAL4removed. Retraction is not completion; real model-backed creative breadth remains open.

## Tool-selection relevance and score boundary

- Selector no longer chooses a sole unrelated registered tool solely from its Beta prior/risk score and lack of a competitor. Zero capability-token match and zero supplied embedding similarity causes abstention even after100 successful outcomes. Existing eligible related-tool selection remains.
- Score/margin explicitly heuristic, not calibrated statistical confidence or probability. Default embedder is hashed bag-of-words and can collide; positive similarity is not independently verified semantic relevance, and this repair does not make tool selection a learned language model. Approval/dispatcher gates remain separate.
- Focused31 passed; M20 result logged. No external tool executed by these tests.

## Independent review catch-up

- Parent relayed reviewer confirmation through88c24dd for temporal constraints (400-network HiGHS oracle, zero mismatches), Horn closure (300-program oracle, zero mismatches), strict model output and both claim-retraction batches. These scoped confirmations do not establish original-spec completion.
- Private-routing boundary confirmed with configuration caveat: declared LOCAL/SELF_HOSTED route kind does not verify actual destination. README now names configurable OpenAI-compatible/Ollama endpoints and owner-controlled infrastructure requirement; URL ownership/locality remains unchecked.
- Fuzzy, finite model, spatial, boolean induction, graph transduction, interleaving, keyed assessment and progress had test-pass confirmation only, not independent oracle/mutation attack. They retain SCOPED/pending review annotations.

## Exact reviewed prompt-improvement boundary

- Old ImprovementLoop.apply treated caller approved=true/arbitrary approval_id as approval while claiming a Module0 token. Proposal now creates an exact revision request through configured approval gate; apply requires that proposal's id and approved gate decision. No bound gate means fail closed.
- Replay and changed-target version/content reject before mutation. Request includes exact current/proposed prompt content. Only prompt registry changes, not deployed code/safety rules/tool specs. Caller expected_gain remains unvalidated prediction; this is not actual autonomous self-improvement efficacy.
- Named pending/foreign/made-up-token, replay and stale-version tests; existing route tests use real test-gate approval. Focused50 passed; M20 result retained in improvement-gate-m20.log. Production exact owner approval gate still must be bound per tenant by integrator.
