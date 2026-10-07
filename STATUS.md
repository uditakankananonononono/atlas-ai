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

## Exact-effect safety token binding

- Reproduced approved token authorizing changed recipient/body/action/task and replay in SafetyGate. Fixed by binding each requested token to canonical finite JSON action/risk/task/payload and locked single-use consumption when the gate approves. Unknown/changed/replayed tokens remain blocked. No external effects executed in tests.
- Scope is one live SafetyGate process. Binding/consumption is not durable across restart; unknown restored tokens fail closed and require new review. A crash/handler failure after consumption cannot silently replay the token. Durable owner-bound atomic effect-token lifecycle remains integration work; no exactly-once distributed-effect guarantee.
- Before-fix2 failures retained. Focused46 passed; M20 result retained. Approval center identity/grants and per-tenant wiring remain separate from this payload binding.

## Prompt-revision follow-up hardening

- Self-falsification found that mutating a stored proposal's proposed_content after review could still apply unreviewed text. Retained failing reproduction in audits/rebuild-20261007/token-hardening-before.log. The earlier exact-revision repair was incomplete against mutable proposal records.
- ImprovementLoop now retains a separate immutable revision snapshot, validates proposal identity/name/content/version/token against it, checks current target kind as well as content/version, and applies the snapshotted content. A process-local lock and separate consumption set block parallel application and replay after resetting the public status field.
- New attacks cover changed text, id/name/version/token, changed target kind, 32 parallel applications, reset public status, and SafetyGate's 32 parallel consumers plus restart fail-closed behavior. Focused39 passed; M20 rerun1677 passed with one expected SCS warning. Independent review pending.
- Still in-process registry behavior, not durable/distributed transactions or protection against unrelated direct registry writes. Production owner approval binding and durable effect integration remain open. No external effect or model execution demonstrated here.

## Mounted improvement HTTP path verification

- Reviewer marked 95228ec/409aabe/0f014a4 CONFIRMED-WITH-CAVEATS after proposal/effect mutations and thread-race attacks. Production Module 0 binding and process-local limits remain open, not completed by that review.
- Closed the requested route-coverage gap locally: six end-to-end tests use the actual app mount /api/v1/api/modules/20/meta/improvement/proposals/{id}/apply, signed production OIDC identities, separately bound owner services and a real in-memory gate, with no service dependency override. Pending/foreign tokens, cross-owner proposal lookup, proposal mutation, stale current content/kind, replay and unauthenticated apply fail. Exact approved revision changes the registry once.
- Test-only mutation bypassing ImprovementLoop.apply in the HTTP route produces five failures; original route restored and six tests pass. Logs retained. M20 rerun1683 passed with one expected SCS warning. This verifies route wiring against the configured test gate, not a deployed production approval integration.

## GCW sandbox filesystem boundary repair

- Reproduced an actual outside-project read: legacy SandboxRunner.run_python opened an absolute temporary host canary and printed its contents with exit0. Its cwd, isolated Python flags, socket monkeypatch and resource ceilings did not isolate files. The old source/doc claim of no access outside the project was false. No user files or external network were used for this reproduction.
- Replaced the unsandboxed subprocess path with M4's actual bubblewrap/Docker isolation backend. There is no plain-process fallback. Bubblewrap execution was reproduced here; Docker was not. Code is read-only /input, the project directory is writable /output, and no network namespace is shared. Missing backends refuse execution; networked GCW execution is explicitly unsupported, even when host policy checks allow a hostname.
- SandboxPolicy.allows_path now resolves traversal/symlinks before containment, rejects relative/empty paths. Project ids no longer sanitize different inputs into the same name; symlink project volumes fail. Durable runtime sandbox workspaces are partitioned by a hash of the repository tenant id so two owners' same project id does not share output.
- Six tests include actual mounted HTTP execution with signed owners, outside-host read/write canaries, same-project owner isolation, no-backend fail-closed, traversal/symlink and unsupported network requests. Replacing the runner with its legacy source produces five failures; fixed source restored. Focused42 pass; M20 rerun1689 pass with expected SCS warning. Independent re-attack pending.
- Scope: OS isolation via an existing backend, not a novel sandbox or proof against kernel vulnerabilities, concurrent host-side symlink replacement or all possible resource attacks. Read-only system/runtime files are visible by design. Project files made by the old shared workspace are not automatically migrated. Production backend deployment and reviewed execution authorization remain integration work.

## Dispatcher exact-effect follow-up

- Three failing fake-handler reproductions found more execution boundary defects: external partial failure retried five times under one approval; a safety denial with neither token nor violation still invoked the handler; caller mutation after an async yield changed the payload executed after review. No real external effects were made.
- Dispatcher now blocks every false safety result, snapshots nested caller arguments before preflight, keeps a separate record snapshot, and gives each handler an isolated copy. Approval-required effects run at most once per dispatch regardless of retry setting; failure/timeout is labeled effect outcome unknown and not retried. Non-effect read/reversible retries remain bounded by the registered policy.
- Focused13 passed; M20 rerun1692 passed with expected SCS warning; before-failure log retained. Independent review pending. This prevents this dispatcher's automatic duplicate attempt, not a downstream exactly-once guarantee, durable reconciliation, or proof that all registered tool risk labels are correct. Tool registration and owner approval integration still matter.

## Sandbox independent re-attack and follow-up

- Reviewer marked35bbdd7 CONFIRMED-WITH-CAVEATS after real bubblewrap attacks on absolute/traversal/symlink outside paths, writes, raw-socket egress, environment and mutation-checked tenant separation. It found the existing tests did not pin the OS network boundary, and flagged host-valid output symlinks as a risk to future artifact readers.
- Added a real host loopback listener test: sandbox code bypasses the Python socket class using its raw base class, but the OS namespace still blocks the host listener. Removing --unshare-all from the actual backend makes this test fail (HOST_NETWORK_REACHED); source restored, eight sandbox tests pass. No public network or user data was used.
- SandboxRunner now removes all output symlinks without following them and refuses the run when any were found. A temporary host-valid link reproduction failed before repair and passes afterward. This cleanup is not race-proof against a concurrent malicious host writer; future host artifact readers must use canonical containment plus no-follow/openat-style checks rather than assume the volume is trusted.
- Docker flag isolation is code-read only in this rebuild; auto selection can choose Docker when present. Read-only system mounts and mountinfo expose runtime/system details by design. Automatic tenant separation applies to GCWRuntime construction; direct SandboxRunner callers must supply independently owned roots.

## Dispatcher reviewer follow-up

- Reviewer confirmed e9cde64 with caveats after fail-closed, caller-mutation, exact-effect, retries and replay attacks, with control mutations. It found spent tokens were mislabeled pending and the known-money list omitted pay.
- Consumed tokens now yield approval_consumed violation and a distinct ApprovalConsumed blocked error, not ApprovalPending. The executive's blocked-action path handles it. Known money aliases pay/payment/purchase/transfer/book_paid/subscribe_paid/checkout/order/place_order/send_money/refund/charge gate even under READ, with case/outer whitespace normalization. These aliases also disable automatic retry after an uncertain effect.
- Focused22 pass; M20 rerun1703 pass with expected SCS warning. The known names are defense-in-depth, not semantic detection of arbitrary tool behavior. A side-effecting tool with a misleading READ declaration and an unrecognized name/omitted external flag can still evade classification; registered tool metadata and owner integration remain trusted configuration requiring review.

## Money-name defense-in-depth follow-up

- Reviewer confirmed835dfaa's consumed-token error and normalization controls, but reproduced READ-declared segmented names and Unicode variants bypassing exact aliases. Replaced money classification with NFKC/case normalization, format-character removal, a small explicit Cyrillic-confusable map and non-alphanumeric token matching. Tokens pay/payment/buy/purchase/checkout/order/wire/transfer/charge/refund/payout/withdraw/donate/subscribe/settle/tip/upgrade require review; payload/orderly/wireframe do not match by substring.
- Focused42 pass, including segmented/fullwidth/zero-width/Cyrillic samples and negative substring cases; M20 rerun1726 pass with expected SCS warning. Name matching remains defense-in-depth with an incomplete alias/confusable vocabulary, not a semantic proof of tool effects. Correct trusted registry risk/visibility metadata is still required.

## Meta-cognition claim corrections: rows19/20/29/30/31

- Inspected exact methods against original row descriptions. Bias scan is literal marker matching and template suggestions, not bias diagnosis/correction. Intuition is cached skill/fact retrieval and a substring comparison to supplied text, not validated intuition. Perspectives are five fixed metadata rubrics, not personality modeling. Devil's advocate is assumption templates/count diagnostics, not grounded alternative explanation. Steelman is lexical fact selection and a response skeleton, not a strongest argument.
- Removed fixed bias severity, cache confidence, persona score and residual-confidence numbers. Outputs carry exact narrower status and capability_executed=false; substring validation reports validated=false. Removed fabricated alternative explanations and strongest-argument text. Review prompts/checklists and supplied fact retrieval remain available under explicit labels.
- Corrected these five historical verified-pushed rows to PARTIAL while preserving original evidence. Current ledger labels1907 historical/48 SCOPED/51 PARTIAL/4 removed. Counts are labels, not verified capabilities. Existing legacy number assertions were replaced with honest null/nonexecution contracts and negative tests prevent junk evidence from manufacturing confidence or an argument.
- Focused48 passed; module/ledger verification recorded separately. This is honest retraction of incomplete cognition, not implementation of the original named breadth. Independent review pending.

## Further meta claim corrections: rows14/17/18/27

- Row14's default counterfactual outcome estimator was fixed odds by risk tier, independent of episode/action data. Removed it as the default. Without an injected model, output is outcome_model_unavailable with null probabilities/no selected best history/no inferred lesson. Optional injected estimates remain explicitly unvalidated supplied-estimator output, not causal counterfactual reasoning. The separate structural causal computation rows844/845 remain narrowly SCOPED and are not integrated as a general episode outcome model.
- Row17 uses fixed challenge/skill thresholds and sorts supplied difficulty values. Listing tasks no longer invents0.05 skill growth per task; every item retains the supplied skill assumption. Row18 is marker-selected prewritten reframing advice. Row27 is a hand-written uncertainty/time planning policy. These are labeled rubrics/templates/policy with capability_executed=false, not full cognition/flow induction.
- Four more rows corrected to PARTIAL, original evidence preserved: current labels1903 historical/48 SCOPED/55 PARTIAL/4 removed. M20+ledger1734 pass with expected SCS warning. Independent review pending; this is a retraction, not original-spec completion.
- Local live model probes during this slice: localhost:11434/api/tags had no connection; localhost:8080/v1/models returned404. The default Ollama hostname ollama did not resolve here. No configured GCW endpoint/model environment overrides were present. This environment has no demonstrated running default model; it says nothing about availability on the user's own device or remote deployment. No paid/hosted generation was attempted.

## Calibration/exploration fabricated-number correction

- Reviewer confirmed prior meta retractions and found two more numeric inventions: row13's evidence-count confidence ceiling and50/50 predictive confidence blend, and row34's frequency-derived expected learning value. Removed them: flagged/adjusted confidence and expected_learning_value are null, with observed_calibration_only or frequency_budget_policy_only status and named capability nonexecution. Actual outcome/confidence calibration curves/error remain descriptive measurements of supplied resolved claims, not assessed knowledge boundaries.
- Exploration is now explicitly a frequency budget policy, not estimated learning value or executed investigation. Removed per-item budget rounding that could overshoot the requested total. Default risk-tier HeuristicOutcomeModel dead code was deleted. Row18/27 exact scope labels are pinned.
- Added route assertions for nonexecution/status propagation on bias-scan, intuition, perspectives, devil's advocate and steelman; calibration claim HTTP responses also carry scope. M20+ledger1736 pass with expected SCS warning. Independent review pending. Two more rows PARTIAL; labels1901 historical/48SCOPED/57PARTIAL/4removed, not verified capabilities.

## Role-pattern/world-model/knowledge-age corrections

- Row11 extracts a fixed role sequence from supplied successful episodes and retrieves it when lexical domain tokens do not overlap. It now excludes failed outcomes and deduplicates source episode ids instead of inflating success counts on every route call. Outputs explicitly say role_sequence_retrieval_only and no named meta-learning execution.
- Row21 versioning of supplied assumptions remains real, but signed supplied evidence weights are not likelihood ratios. Removed the sigmoid posterior probability; posterior is null, the raw number is labeled supplied_weight_score. HTTP current_best is null; highest_supplied_weight_model is only a caller-score ranking, not truth.
- Row33 no longer invents kind-specific decay or a30-day freshness law. Returns observed age with obsolescence_model_unavailable, null freshness/refresh_by and no scheduled refresh. Three rows PARTIAL; original historical claims preserved. Latest labels1898 historical/48SCOPED/60PARTIAL/4removed. M20+ledger1737 pass with expected SCS warning; independent review pending.
- Calibration reviewer confirmed1135334's observed metrics and retractions. Removed the dead confidence-ceiling constructor parameter and renamed the stale legacy test. Caller-trust limit: resolve() accepts/revises caller outcomes, and unknown ids raise KeyError at the class level (HTTP checks existence). Supplied correctness is not independent truth or tamper-proof evidence.

## Goal-prerequisite integrity and row22 scope

- Reproduced goal conflict pruning silently dropping a cancelled prerequisite while retaining its dependent publish/share steps. The helper now cancels the transitive dependency closure, preserves dependency references, and refuses malformed duplicate/missing ids. It does not promote dependent effects into independent work. This helper currently acts on supplied plan objects, not the live scheduler.
- Row22 is marker_conflict_pruning_only/capability_executed=false and PARTIAL. Literal conflict markers are not semantic terminal-value reasoning or generated replacement goals. Original claim retained. Latest labels1897 historical/48SCOPED/61PARTIAL/4removed. M20+ledger1738 pass with expected SCS warning; independent review pending.

## Untooled executive steps no longer fake success

- Reproduced that a tool-less plan node always became SUCCEEDED with the literal reasoning step (no tool), without calling an executor/model. Both unavailable-executor and retained-model-output tests failed on the old source. It no longer counts a title as work: tool-less execution calls the configured executive reason operation and requires a nonempty result string; unavailable/invalid/error responses block the node/task. Actual returned text is retained with a correctness-unverified trace.
- No live reasoning model was demonstrated. Test fixtures prove invocation and fail-closed plumbing only; three runtime tests now explicitly bind a fixture executive rather than inherit fake no-tool success. Nonempty model output means output produced, not a verified solution or original goal fulfillment.
- Also closed reviewer row22 notes: terminal succeeded/failed history is preserved and reported in already_executed_dependents; self dependencies rejected. M20+ledger1746 pass with expected SCS warning. Independent review pending. Original full model-backed cognition and result-quality verification remain open; no labels promoted.

## No unfitted semantic freshness and fresh-plan state correction

- SemanticMemory also had a fixed30-day half-life reliability number. Removed it: freshness is unavailable/null and model-driven due_for_refresh returns no schedule. Caller decay/confidence values remain stored metadata, not assessed truth/freshness. Explicit confirmation still records time. Knowledge-decay HTTP responses name prediction params as ignored and unavailable; age remains measured.
- Fresh DeliberativeLoop.start resets incoming node states/attempts/approval ids/output before execution, so preset SUCCEEDED/CANCELLED does not establish work. run() rejects empty/all-cancelled plans as success. Continuation run/resume still relies on internal/durable plan-state integrity, not arbitrary caller authority; do not use it as a fresh untrusted-plan entrypoint.
- Negative tests pin extreme caller decay, fresh-state reset and all-cancelled no-success. M20+ledger1750 pass with expected SCS warning. No row labels promoted. Independent review pending.

## Low-priority money-name cleanup

- Closed reviewer camelCase/plural gaps: split lower-to-upper boundaries before casefold; added orders/refunds/bill/topup/cashout/deposit/funds/money tokens. Focused53 pass. The same incomplete-name-vocabulary/trusted-metadata caveat still applies; this is defense-in-depth, not semantic effect detection.

## Cognitive-learning belief revision and education model assumptions

- Row880's heuristic prior/reliability/direction blend is no longer a revised confidence probability. Reports belief_revision_model_unavailable with null revision/confidence, complete=false and named nonexecution. Prior remains caller supplied. Row880 PARTIAL.
- Education rows1457/1458 retain real sequential Bayesian knowledge-tracing arithmetic, now SCOPED. Expose all prior/learn/slip/guess parameters and whether callers supplied every one; missing parameters use unfitted_example_defaults. No parameter fitting or independently verified learner mastery. Exact two-attempt manual arithmetic and changed caller parameters tested; nonfinite parameters reject. Probability is conditional on these assumptions, not a grade or measured real mastery.
- Row846's Bayes computation explicitly labels caller-supplied probabilities/likelihoods and unverified assumptions/real-world truth. No inferred likelihood quality. Latest label counts1894 historical/50SCOPED/62PARTIAL/4removed. M20+ledger1762 pass before the added BKT exact test; focused post-test log retained. Independent review pending.

## Final money-name defense pass

- Per reviewer, one final bounded pass adds acronym camelCase split, digit-free segments, charges/payments/purchases/billing/invoice/buyer and exact compact topUp/cashOut forms. Focused64 pass. Stopped denylist expansion here: names cannot prove side-effect behavior, and trusted correct registry risk/visibility declarations are the real control. No universal alias/confusable guarantee.

## Cognitive-learning rows860-909 honest scope

- Read all50 operations. They sort/echo supplied data, compute supplied-score arithmetic, return fixed stages or hand-written heuristics; they do not run the named thinking/learning abilities. Complete=true previously meant nonempty input stages. Now complete=false/capability_executed=false with supplied_input_diagnostics_only; separate input_stage_coverage_complete retains honest input coverage. No bounded uncertainty from filled fields.
- Critical-thinking quality-risk product is explicitly heuristic and has no supported verdict. An insight's caller verification boolean is preserved only as caller_verification_claim; verified=false. Existing diagnostics stay available with the same caveats, not promoted to cognition.49 more historical rows PARTIAL (880 already retracted). Labels1845 historical/50SCOPED/111PARTIAL/4removed.
- All50 negative nonexecution contracts and prior exact-transform tests pass; M20+ledger1775 pass with expected SCS warning. Independent review pending. Actual learned cognitive pipelines/model execution remain unfinished, not made complete by honest output labels.

## BKT correctness type repair

- Reviewer found that string false was truthy and counted as a correct attempt. Eight negative tests reproduced string/number/null/container/missing correctness acceptance. Attempt events now require type(correct) is bool; invalid/missing values reject before analytics or tracing. Non-attempt check-ins do not become attempts or observed grades.
- Mixed supplied/default BKT parameters now say partial_caller, not wholly default. Focused111 and M20+ledger1783 pass with expected SCS warning. Before-fail log retained. Conditional unfitted model scope and no verified learner-mastery claim remain. Independent re-attack pending.

## ProductOrchestrator exact-plan boundary repair

- Separate orchestration path accepted changed step.detail after review and allowed a failed plan to rerun the same token. Retained failing fake-executor reproduction; no external effects. Approval payload now includes goal statement, source metadata and step detail; immutable canonical plan binding checks id/tenant/statement/sources/step fields before dispatch.
- Locked execution consumes the process-local approval before any executor, including failure, and executes steps reconstructed from the reviewed snapshot.32 parallel calls produce one execution. A failed attempt cannot request/reuse approval without a fresh plan. Default execution remains simulated, not real effects.
- M20+ledger1791 pass with expected SCS warning; independent review pending. In-process only, not durable/distributed transactions. Executors and evidence ids remain caller-supplied assertions, not independent proof of actual execution or verification; source citation membership is not source-content validation. Production owner gate/expiry enforcement and evidence attestation remain integration work.

## Cognitive diagnostic label follow-up

- Reviewer confirmed05e6e7d and ebce40a. Renamed row885's echoed confidence to supplied_inference_confidence, row894's multiplication to supplied_outcome_similarity_product, and row905's awareness threshold to low_supplied_awareness_threshold_flag. These labels do not claim inferred confidence, vicarious learning value or evidence of implicit learning. Focused112 pass; scopes/counts unchanged.

## Product-plan expiry fail-closed follow-up

- The orchestration class now retains request expiry separately and enforces it before dispatch even if an injected gate still says APPROVED. Missing expiry fails closed. Focused18 pass, including an expired approved token. Process-local snapshot/expiry/consumption remains non-durable; production center behavior is not substituted by these tests.

## Executive ranking and rumination prediction correction

- MetaReasoner's fixed risk/title/memory-count ranking weights are now heuristic_information_weight/heuristic_progress_weight, not information gain or success probability. Decision HTTP artifacts explicitly label hand-written ranking with no predictive model. Default runtime expectation registration no longer converts those knobs into calibration predictions; supplied outcome/confidence claims still support descriptive metrics and explicitly caller-predicted surprise checks.
- Legacy random-order ruminator expected_success is null, with random_ordering_heuristic_only. The separate real UCT tree search retains its internal simulated reward/value standard errors, but reports unfitted risk/attempt assumptions and no predictive model. Monte Carlo error over a fabricated rollout is not correctness uncertainty or real execution confidence.
- Updated surprise test to provide an explicit caller prediction rather than rely on invented defaults. Negative tests pin non-predictive labels. M20+ledger1793 pass with expected SCS warning; independent review pending. No full cognitive or goal-quality verification claimed.

## Product lock/TTL reviewer follow-up

- Review consumption checks and insert remain in one lock-held claim operation, now pinned by a checking-set test. Executors run after that lock is released, so a slow handler does not serialize all goals and a reentrant same-token call blocks instead of deadlocking.32-thread consumption test remains. Goal records are still process-local; concurrent operator mutation/readback is not a transaction guarantee.
- Constructor validates integer TTL1-86400 seconds, rejecting huge/bool/fractional values before datetime overflow. Focused25 pass. No spending, real external executor or distributed guarantee.

## Remaining heuristic number labels

- Renamed UCT root_value/root_standard_error to heuristic_root_value/heuristic_root_standard_error at the typed object and HTTP output, so bare keys do not imply predictive value. Technical-spec row185 explicitly labels supplied-input scoring and its caller-information-gain * caller-progress-probability - caller-cost arithmetic, not fitted prediction.
- Expectation claim ids in node arguments remain caller/model-controlled metadata. They cannot establish confidence provenance; callers could associate an existing claim with a step. This affects descriptive calibration/reflection, not execution approval. Production provenance binding is not completed. Focused73 pass; independent review pending.

## Refreshed whole-repo regression

Current split-process regression run: 9453 passed, 14 skipped, 3 warnings across 495 test files / 19 batches. Batch0 initially exposed stale expectation for critical-thinking uncertainty=high; corrected to unquantified and complete=false to match the deliberate scope retraction, then re-ran that entire batch. Remaining batches passed unchanged. No live model or deployed integration inference.

## Execution-state rollup is not evidence verification

The execution-truth endpoint and ProductOrchestrator ledger accept caller/executor evidence ids and verifier labels but never retrieve or authenticate those artifacts. Renamed highest_observed_state and verified_fraction to highest_claimed_state and claimed_verified_fraction. All items explicitly carry state_is_caller_claim and evidence_verified=false; aggregate status is supplied_claim_rollup_only. A fabricated independent-verifier label can pass structural validation, but no longer produces an observed/verified output label. This is outcome-claim bookkeeping, not independent verification or deployed action proof. A new regression uses invented evidence to pin that boundary. Focused57 pass. The earlier9453 whole-repo run predates this rename. Runtime module prose and decision-artifact basis also corrected to reflect no default success predictions and heuristic ranking.

## Frontend claimed-state readback

Updated GoalWorkspace client types, fixtures and rendering for claimed_verified_fraction/highest_claimed_state. Counts now say claimed; externally-executed/independently-verified badges are grey and explicitly unverified claims when evidence_verified=false. Verifier labels say claimed verifier. Ledger status and evidence-verification flag are visible. A fixture generated from the current backend is pinned by a Python equality test and used in a UI regression, preventing the old fixture drift. Component suite16 pass, typecheck pass, backend fixture tests4 pass. Inspected the actual 1100x900 browser rendering of GoalWorkspace using that real backend ledger with invented evidence/verifier labels: clear grey unverified-claim badge, no undefined fraction, no green verification claim. Local isolated UI rendering, not deployed authenticated service verification.

## Negotiation/influence rows85-109 scope correction

These routes run supplied-input arithmetic, templates and hand-written behavioral rubrics, not fitted behavioral/predictive models or execution of named influence abilities. Removed fixed confidence values and arbitrary +/- uncertainty/credibility bands (null rather than quantified). Retained actual Wilson/difference-proportion intervals with supplied-count assumptions. Renamed deployment/may-communicate/allowed flags caller_rubric_* and external_action_authorized=false, because caller facts and rubric checks do not grant external authority. Priming group differences remain descriptive, causal_estimate_available=false: assignment/confounding are never verified. All25 ledger rows PARTIAL, historical claims/evidence preserved. Latest labels1820 historical verified-pushed,50SCOPED,136PARTIAL,4removed. Focused80 / focused+ledger90 pass. Original negotiation cognition and deployed evidence verification remain absent.

## Nested negotiation correction

Independent reviewer found remaining nested/alternate-key fabricated bands and self-verified evidence flags after the first top-level correction. Corrected recursively: arbitrary score_interval/interval_80pct/estimated_adjustment_band/expected_settlement_zone null; adherence_support_estimate removed in favor of adherence_prediction=null. Social-proof/scarcity verified renamed evidence_supplied; caller legality/proportionality/authority echoes marked caller_*_claim; credible and *_allowed/*_blocked rubric flags marked caller_rubric_ recursively. Genuine Wilson and difference-proportion intervals are kept. Generic regression now walks all nested dict/list results across25 methods, alongside invented-artifact tests. Focused+ledger112 pass. M20+ledger1828 passed before this nested correction. Earlier top-level claim about arbitrary-band removal was incomplete; this entry records the correction without hiding the earlier claim.

## Sample-rule and echo correction

Renamed social-proof statistically_supported to meets_caller_min_sample_rule: n>=30 is only a hand-written sample-size rule, not a supported claim. Renamed nudge estimated_uptake_lift to supplied_uptake_difference and welfare choice to caller_utility_maximizing_option. Recursive claim labeling skips original caller-owned dict/list containers, preserving echoed facts and nested evidence metadata. Authority evidence assessment now separates caller_record from computed heuristic_weighted_support. New tests pin zero-proportion sample-rule behavior and unchanged caller verified/authorized/interval keys without output authority. Focused+ledger114 pass.

## Ground Horn proof correction rows1970/1971

Reproduced a false proof: a rule consequent was accepted without antecedents; a disjunctive clause's member was also accepted as true. Replaced that branch with actual fixed-point positive ground Horn forward chaining over unit facts and rules, derivation trace and closure. Missing antecedents do not prove a query; multi-literal clauses fail instead of pretending to handle propositional disjunction. Strings are uninterpreted atoms, not parsed negation/first-order syntax. Caller axioms remain unverified. Regression checks a two-stage derivation with reverse rule order, missing antecedents and rejected disjunction. Focused9 pass. Rows1970/1971 SCOPED, old claim preserved. Current labels1818historical/52SCOPED/136PARTIAL/4removed. M20+ledger1856 passed before this correction.

## Supplied cognition/affect correction1975-1977/2009

Cognitive-computing/metacognition branches computed Brier from bool(correct), so string "false" became successful and missing outcomes became scored failures. Now require exact booleans, finite unit confidence, nonempty unique task ids and unit review threshold; results explicitly supplied_scored_attempt_calibration_only, cognition_executed=false/outcome_truth_verified=false. Affect/emotion branch is only caller valence/arousal quadrant classification, not emotion recognition; requires bounded finite signals instead of defaults, heuristic_quadrant_label, confidence=null/emotion_recognized=false.19 focused tests pass, including prior Horn proof tests. All4 ledger rows PARTIAL with preserved history. Current labels1814historical/52SCOPED/140PARTIAL/4removed. Original model-backed cognition still absent.

## Finite optimization1992/1993

The prior ratio-greedy branch missed the best of its own two-item fixture (value8 vs10), divided by zero on free items and admitted negative costs. Replaced with finite exact0/1 subset enumeration, capped20 items, nonnegative finite values/costs/budget, including free items. Returns visited feasible-subset count and optimal-within-supplied-float-arithmetic flag. Not general optimization/operations research. Tests include classic greedy counterexample220vs160, free items/zero budget, bad domains and15 seeded random comparisons against an independent integer-budget dynamic program. Focused22 pass. Rows1992/1993 SCOPED, historical claims preserved. Labels1812historical54SCOPED140PARTIAL4removed.

## Cognitive reference substitutes22-row correction

Explicitly named and retracted22 reference substitutes within1960-2009: shortest-path graph vs graph-of-thought, supplied-answer plurality vs self-consistency generation, context selection vs RAG generation, in-memory vector scan vs database, character hashing vs learned embeddings, supplied cosine scores vs semantic retrieval, scalar elite mutations vs swarm/GA, polynomial candidate selection vs genetic programming, eight mean-coupling toy trajectories vs life/emergence/evolution abilities, supplied residuals vs a synchronized twin, graph degrees vs systems/complexity science, hand-written controller vs second-order cybernetics. Each output now reference_operator/reference_substitute_only/named_capability_executed=false; original rows PARTIAL, preserved history.23 focused pass. Labels1790historical54SCOPED162PARTIAL4removed. Numerical reference outputs remain usable only within their actual narrow operator, not capability certification.

## Remaining same-family reviewer retraction

Added sentiment_analysis/opinion_mining (literal lexicon token counts) and neuro_symbolic_ai/hybrid_ai (supplied rule-weight propagation without neural model) to explicit reference substitutes. Four further rows PARTIAL with history preserved; now26 reference substitutes,1786historical/54SCOPED/166PARTIAL/4removed. Remaining arithmetic branches unchanged per review. Focused+ledger29 pass.

## Atomic credential/reference honesty

Separate atomic-concept surface0093-0115 called nonempty URI/issuer/timestamp fields verified_claims and allowed positioning. Renamed claims_with_supplied_reference_fields/caller_reference_fields_complete; credential/rapport/identity branches now supplied_claim_structure_only, evidence_verified=false/external_action_authorized=false. Caller counterpart facts remain declarations even under legacy their_verified_* input keys; output caller_claimed_commonalities/caller_overlap_found no longer implies verification. Capacity arithmetic verified_gain renamed supplied_capacity_difference. Fake reference/timestamp and claimed overlap regressions pin the boundary.30 focused pass. These atomic ids are a separate denominator from the2009-row register; no register count changed. Latest M20+ledger1872 passed before this atomic correction.

## Remaining atomic source-claim scan

Reviewed atomic70-92 and round9_139-160 for nonempty-field verification. No direct verified-from-presence found in70-92; its fitted staleness/review scheduling claim remains an unrelated heuristic retraction candidate. Round9 corpus had caller connected=true becoming connection_claimed and indexed text source_of_truth=true. Now connection_claimed=false/integration_state_verified=false with separate caller flags; source_of_truth=false/external_source_verified=false, explicitly supplied text corpus. Owner-confirmed must be exactTrue, not string truthiness. Emotion confidence now supplied_confidence. Negotiation genuine_commonalities output renamed caller_declared_commonalities, retaining legacy input key unchanged.

## Atomic staleness/validation correction

Atomic70-92 review dates/staleness odds used fixed180-day coefficients and default volatility/confidence, not fitted belief-decay or review timing. Retracted predicted_staleness/review_on/overdue to null, schedule_generated=false; observed formation age only, future formation date rejected. Also caller-weighted ranking no longer validated_choice/intuition_confirmed: caller_weight_ranked_choice/same_as_salience_candidate with choice_independently_validated=false. Focused60 pass. Separate atomic denominator; register counts unchanged.

## Priority corpus IDOR repair

Reviewer reproduced a confidentiality bug: the mounted round9 corpus endpoint trusted body owner_id to filter the shared default corpus, so another authenticated caller could request a victim's text. Route now binds owner_id to authenticated immutable actor_id, rejects body mismatches403, and uses a distinct corpus keyed by (tenant_id,actor_id), never the default corpus. Mutation/retrieval share a lock. Actual app-mounted RS256 tests use production verifier path: same-tenant different-subject spoof403, different tenant same subject empty, rightful subject receives its own text, unauthenticated401.33 focused pass. Corpus remains process-local and owner_confirmed a caller attestation, not a separate authenticated consent workflow. Insecure explicit dev mode remains header-trusting and must not be deployed.

## Corpus independent re-attack and limits

Independent re-attack of91fd918 confirms victim read/write spoof403, cross-tenant same-subject isolation, no-token401 and no mounted access to default corpus. The corpora map is in-memory and currently unbounded: distinct authenticated subjects can grow memory without eviction, and all content is lost on restart. This is not production storage/resource isolation. ATLAS_DEV_NO_AUTH=1 trusts x-atlas-actor/x-atlas-tenant headers; that explicit dev-only path was not part of this signed-token security test and must never be enabled in deployment. Current M20+atomic+ledger1939 pass, one expected SCS warning, after corpus repair and current label changes.

## Software practice685-709 diagnostic retraction

These branches organize submitted practice evidence but do not run tests, transform code, format/lint a repository, protect a branch, review actual behavior, or perform a release.25 rows now PARTIAL with history preserved. Outputs explicitly supplied_input_practice_diagnostics_only/capability_executed=false/evidence_verified=false/repository_behavior_verified=false/release_authorized=false. Pass/complete/executable/safety names now caller_diagnostic_* rather than verified repository facts, preserving arbitrary echoed caller metadata; uncertainty unquantified instead of fixed medium. Semver arithmetic, change grouping and evidence structural checks remain narrow support, not execution of the original named practice. Focused+ledger110 pass. Latest labels1761historical54SCOPED191PARTIAL4removed.

## Software nested review correction

Renamed computed modernization slices[].ready to caller_diagnostic_ready; TDD red_evidence/green_change to caller_declared_red_evidence/caller_declared_green_change; refactoring new_behavior_allowed to caller_diagnostic_new_behavior_allowed. Direct construction labels rather than generic recursive echo rewriting preserve caller text/metadata. New regressions pin all three residuals. Focused+ledger112 pass. No capability promotion.

Correction to nested review evidence: the first committed run actually111passed/1failed because test694 still expected the old ready key. Initial report of112pass was wrong. Corrected stale expectation and reran:112passed. This does not hide an implementation failure; the stale schema assertion and incorrect report are explicitly recorded here.

## Latest regression after review corrections

Current whole-repo run at8cde270: 9561 passed, 14 skipped, 3 warnings over495files/19isolated batches. First7batch fan-out hit120s timeout with incomplete2/4/6 logs; those three re-run to completion, no orphan pytest processes remained. All final batch results pass. Frontend16components/typecheck pass. No full-spec/model/deployment certification.

## Engineering reference/count correction

Failure analysis counted matching supplied evidence ids as verified_support_count/verified_contrary_count without artifact retrieval. Renamed supplied_reference_* with evidence_verified=false, preserving candidate-not-root-cause. Zero-failure reliability bound truncated fractional trial counts (units0.5 could divide by0; failures0.5 became zero failures). Requires integral nonboolean counts now, finite unit confidence; states independent identical Bernoulli/common-duration/complete-count assumptions and no executed/verified test. Formula remains valid within those supplied assumptions.60 focused tests pass. Broad original failure/reliability capability not certified; no ledger count promotion.

## Engineering integer/design limits review

Shear planes now positive exact integers1..10000 rather than truncated fractions/negative/zero; DOE replicates same integer domain, factors1..12 with nonempty scalar level lists, product*replicates<=10000 checked before constructing the matrix. String levels no longer iterate character-by-character. Reports total replicated count/experiment_executed=false. Shared _num rejects boolean/string coercion and nonfinite inputs; finite extreme magnitudes remain permitted, and other branch-local float coercions/overflow guards are not comprehensively hardened.73 focused pass. These limits bound this matrix constructor only, not complete API resource governance.

## Engineering diagnostic/template15-row retraction

Mechanical requirement coverage, CAD reference ordering, submitted FEA mesh differences and CFD flow balances do not design CAD or run numerical field solvers. Likewise hypothesis references, safety markers, ergonomics/design/CTQ templates, GD&T field presence, QA requirement references and four environment profile templates do not execute their named engineering abilities. Explicit reference_operator/supplied_diagnostics_or_template_only/named_capability_executed=false for15branches; ledger PARTIAL preserves historical claims. Evaluation checks_performed renamed diagnostic_output_fields: listing return keys is not evidence of performed verification.74 focused pass. Other physics/statistical formulas remain narrow supplied-assumption support. Labels1746historical54SCOPED206PARTIAL4removed.

## Engineering facade propagation repair

Specialized-domain facade had discarded engineering status/reference_operator/named_capability_executed and ignored its boundary. Now preserves these in result and retains the engineering boundary in limits. Uniform facade evaluation checks renamed diagnostic_fields, with the HTTP response schema and tests changed together; engineering source uses diagnostic_output_fields rather than manufacturing performed checks from key names.82 focused facade/engineering tests pass, including HTTP response validation and row1512 retraction propagation. Does not promote original solver capability.

## Specialized facade principal binding

Specialized facade previously took tenant/actor readback from raw headers even when the outer app authenticated a different principal. Pure calculation route, not stored-corpus disclosure, but false scope attribution. Now derives both from require_tenant; signed production-path test sends spoof headers alongside a valid token and confirms verified tenant/actor binding, no-token401.8 focused pass. Explicit dev header bypass remains development-only. Latest M20+atomic+ledger1987pass before this binding.

## Sibling principal attribution and rate-limit repair

Cognitive-learning, education and finance routes now derive scope from require_tenant; mismatching legacy scope headers/body rejected403 rather than attributing calculations to another owner. Middleware rate-limit keys now verified tenant/actor, never spoofable x-atlas scope headers under production auth; invalid/missing authentication rejected before private routes. Signed RS256 tests cover all three spoof headers/no-token outcomes and repeated rotating x-atlas header requests reaching429 under the same token, with different tenant allowed.177 focused pass. Explicit development bypass still trusts headers; process-local rate-limit counters remain unbounded/not distributed and authentication is verified again at route boundaries. This does not prove production identity-provider deployment.

## Current auth/gateway regression and scheduler fixture race

Current M20+atomic+ledger+gateway/default-auth2009pass after sibling principal repair. Warnings: expected SCS plus APScheduler JobLookupError on its background thread because the fixture shut down after callback append but before APScheduler removed its date job. Fixed fixture waits for both callback and job removal before shutdown; separate gateway suite6pass with no warning. No scheduler production implementation changed; the wider2009 run was not warning-clean.

## Locked-down API documentation boundary

Middleware authentication intentionally covers every path except /health and /ready, including /docs and /openapi.json. Docs/schema are not anonymously public; signed token required. This changed prior unauthenticated access and is pinned by tests (health200, docs/schema401without token,200with token). Gateway7pass. Middleware and route both verify tokens, a current latency cost; no claim of a shared principal cache or production access rollout.

## Root gateway/auth regression

Root-level tests786pass after principal-bound limiter and authenticated-docs changes, no warning in this run. Wider earlier whole-repo9561 result predates these changes; current M20+atomic+gateway/auth2009 result predates the docs test only. Counts remain separate overlapping runs, not summed.

## Legal1260-1309 template/reference retraction

All50 legal branches share a supplied-field review template with different output keys/mechanism descriptions; no substantive named legal reasoning, actual authority retrieval/treatment/currency verification or evidentiary verification. Explicit supplied_legal_review_template_only/named_capability_executed=false/evidence_verified=false. Reference-field completeness no longer provenance_complete, and a matching authority id no longer sourced fact: supplied_reference_linked_unverified. Existing no-conclusion/no-effect/counsel-review limits retained. Ledger PARTIAL with history.66 focused+ledger pass. Labels1696historical54SCOPED256PARTIAL4removed.

## Legal body-principal scope repair

Legal facade previously attributed a valid authenticated caller's request to body tenant/actor, even if unrelated. Now requires body and nested data scope to match verified principal403, executes/readbacks verified identity. Signed actual-app test pins ta/alice vs tb/bob403, rightful200, nested spoof403/no-token401.61 focused tests pass after workspace recovery, one Starlette/AnyIO deprecation warning in newly built environment. Scanned central routes.py for request/body actor/tenant use: this was its remaining direct body-scope path. No production provider deployment claim.

Recovered environment regression: M20+atomic+ledger1990pass with two warnings (Starlette/AnyIO deprecation and expected SCS inaccurate-result test warning). Initial recovery lacked pytest-asyncio and failed17async cases before installing declared dev plugin; no behavioral code changed to address those environment failures. Counts do not include gateway suite and must not be compared as the same denominator to2009.

## Autonomy world/evaluation numeric honesty

PersistentWorldModel normalized caller reliability*weight into confidence without calibration; renamed supplied_support_share/status supplied_weight_rollup_only/evidence_verified=false/predictive_confidence_available=false. Goal expected_value was simply1-share, now heuristic_gap_priority with supplied-share rationale, not expected utility. Reliability/weight nonfinite/bool rejection added. Transfer benchmark scores a supplied callable against caller expected answers/domain labels, not necessarily learned strategies or held-out real domains; explicit no verified learning/holdout/real-world-transfer flags added and doc corrected.12 focused runtime/evaluation/service-route pass. Hash snapshots protect stored content consistency, not evidence truth or source authentication. No register promotion.

## Autonomous goal exact-review binding

AutonomousGoalEngine activated mutable goal objects using only approval id/decision: changing objective/evidence/rationale after review still activated. Now records canonical reviewed binding covering id/objective/rationale/evidence/heuristic priority/risk, includes all in review payload, rejects changes and spends activation token atomically under a lock. Resetting status cannot reuse the token.17 focused runtime/evaluation/routes pass. This is process-local goal-state activation, not deployed external execution or durable distributed approval lifecycle; goal proposals remain heuristic.

## Synthesis execution safety retraction

ToolSynthesisLab executed generated Python in the service process during test/admit. AST proposal checks offered no CPU/memory isolation, and mutating source afterward bypassed those earlier checks and reviewed source hash. Removed in-process execution/registration: test/request_admission/admit fail closed with clear requirement for bounded OS-isolated execution and exact-source review. Static proposal AST inspection remains; no tool execution/admission capability now claimed. Regression covers manually forged tested status and changed source without tool registration.17 focused pass, one deprecation warning. Full replacement isolated synthesis worker remains unfinished, not silently approximated.

## Caller-evaluator candidate versioning safety

SelfImprovementLab candidate dict previously stayed mutable after scoring/review, so apply could store unreviewed content/score. Full report hashes now bind evaluation and exact review; returned reports are detached copies. Locked local apply/rollback consume approval once and bind baseline version (including equal-content ABA changes). Reject nonfinite/boolean/nonnumeric evaluator scores/minimum gains and nonfinite gain. Caller's evaluator remains untrusted evidence of capability: this versions strings, does not train/deploy a model or prove learned/holdout improvement. State/locking/approval consumption are process-local, not durable/distributed.28 focused tests pass with one deprecation warning, including mutated report fields, concurrent equal-content apply, rollback replay and invalid scores.

Post-autonomy regression (b425892 code): 90 test files selected by test_m20*, atomic*, ledger* names, 2174 passed, two warnings (Starlette deprecation and intentionally bounded SCS inaccurate-solution fixture), 37.95 seconds. This verifies named tests only, not entire repository or original feature depth. Evidence: audits/rebuild-20261007/post-autonomy-regression.log.

Local read/test environment model availability probe: no Ollama binary or Ollama/vLLM process found; existing default Ollama model-list GET ConnectError, default localhost OpenAI-compatible model-list GET HTTP404. No generation requested, no tokens/private prompts used. This is not a check of the owner's deployed environment or all possible runtimes. Adapter fixtures mock generation and verify parser/risk/plumbing only. Actual model-backed cognition remains unverified. Evidence: audits/rebuild-20261007/local-model-list-probe.txt.

## Bounded actual local small-model trial

Loaded official Qwen2.5-0.5B-Instruct Q4_K_M GGUF (491400032 bytes, pinned revision9217f5db79a29953eb74d5343926648285ec7e67, SHA25674a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db verified) with llama.cpp commit8345f333951c661d166b00e6f9362e553768f292 built from source, CPU2threads,1024ctx,1slot,128output, synthetic prompts only and no external tools. Two short runs on fresh loopback ports were stopped after evaluation. Initial startup1.27s peak599208KiB total10.51s: planner failed step-object validation, reason generated correct synthetic color summary but wrong purpose field, reflect wrong purpose field. Adapter previously returned schema-invalid executive objects; now reason requires nonempty result string, reflect requires nonempty cause/fix and exact bool retry, otherwise available=false. No coercion of wrong fields into successful reasoning.

Second actual-model run startup0.81s peak600704KiB total12.37s: planner5.58s rejected unparseable JSON, reason2.35s and reflect2.24s correctly reported schema mismatch. Small pretrained weight loading/HTTP generation reproduced, but these three prompts did NOT produce valid end-to-end planner/executive behavior. No success-rate, original model quality, AGI, training or owner deployment claim.43 separate parser/executive/privacy fixture tests pass; those remain parser/plumbing evidence, not actual-model inference. Evidence: audits/rebuild-20261007/local-qwen-trial/. Public model card: https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF. Runner docs: https://github.com/ggml-org/llama.cpp. No paid route/new account/owner data used.

## Expectation verification retraction

Executive previously called semantic.confirm on title-similar low-confidence facts after any successful tool and logged them as contradicted, without comparing results with fact content. Removed false confirmation timestamp refresh/contradiction claim. Similarity lookup now only logs need for evidence review. No contradiction or fact truth evaluator is implemented here. Regression proves title-identical low-confidence fact retains last_confirmed_at after unrelated successful tool; focused executive/memory/runtime tests passed (see exact count in log).

## Task-scoped episode provenance correction

Shared executive previously copied the entire dispatcher's action history into each episode, falsely attributing earlier tasks' actions to later tasks. ActionRecord now carries dispatch task_id; closed episode selects matching task records and deep-copies them. Regression uses two tasks through one loop with distinct arguments, excludes earlier task actions and verifies later dispatcher mutation cannot rewrite stored episode actions. This fixes local task attribution, not authenticated effect receipts, outcome correctness or durable distributed lifecycle.

Post-small-model/schema/episode regression after40a802d:90 M20/atomic/ledger named files2185pass2warnings36.08s. Warnings are Starlette deprecation and deliberately bounded SCS fixture. These named tests do not prove entire repo or original spec depth. Evidence: audits/rebuild-20261007/post-small-model-episode-regression.log.

## Generated HTN reuse context binding

Base HTN planner previously fuzzy-matched generated plans to different goals and ignored planning context, potentially reusing prior tool arguments/recipient. Generated-method cache now binds exact original goal and SHA256 planning context; distinct keys do not overwrite one another. Durable planner forwards context. Legacy generated methods without bindings fail closed for reuse. Library method fuzzy matching remains explicit token heuristic and is not semantic generalization proof. Generated plan validation/cache is not model training or successful policy learning; durable review lifecycle remains separate.55 focused planner/executive/runtime tests pass1warning, including similar alice/bob goals, changed fixture context and legacy unbound cache.

## Skill-signature evidence filter

Skill proposal grouping previously counted failed episodes/actions and repeated copies of a single episode despite claiming successful repetition. It now requires successful outcome and all actions successful, distinct episode IDs and positive exact integer min_occurrences, and detaches proposed action snapshot. Output includes episode_ids and successful_tool_signature_grouping_only/generalizable_skill_verified=false. This groups tool-name sequences from caller records, not training, causal success proof, semantic transferable skills or authorization to execute copied arguments.36 memory/runtime focused pass1warning. Distinct task provenance should be retained by upstream records; independently authenticated receipts remain unfinished.

## Strict HTN model output fields

HTN validation previously coerced float/bool retry counts, numbers as titles/IDs, iterable arguments/dependencies and silently chose last repeated title for dependency references. It now rejects those malformed fields, bounds decomposition to128steps and retries1..100, and requires unique ID references when dependency title is ambiguous. This is safety/parser validation of supplied model output, not real plan correctness.58 focused planner/runtime/adapter fixture tests pass1warning.

## Latest full named regression

Code revision b60c013: all495 test files partitioned into20 isolated pytest batches;9608passed0failed18skipped,26 warning occurrences summed across batches (not26unique warnings),398.87seconds summed final-batch wall time. This is not one-process full-suite compatibility, browser E2E, production deployment or original feature-depth certification. Initial recovered-environment failures lacked declared Alembic/matplotlib/langchain-core/Chroma/PyMuPDF/Selenium/pytesseract/unstructured dependencies; installed locally and retained initial failed/collection logs beside final clean reruns. Skips still include missing optional model/runtime/integration dependencies (standalone M01 check has2fastembed skips), not verification. Warning categories: Starlette/AnyIO deprecation, Alembic config deprecation, WeasyPrint HarfBuzz-subset deprecation, deliberately bounded SCS inaccurate-solution warning. Exact manifest, batches, exit receipts and summary: audits/rebuild-20261007/latest-full-regression/.

## Working-memory task partition correction

Re-putting a chunk ID under another task previously left stale partition membership, exposing replacement content to earlier task. Now cross-partition reuse rejects, stored/input/output chunk copies are detached, and default-partition capacity no longer evicts named tasks. Aggregate focused(partition=None) remains deliberate all-task read; named/empty-string reads are scoped.54 working-memory/runtime/executive tests pass1warning incl same-ID replacement, caller/readback mutation, default-capacity isolation. This is process-local task buffer isolation, not tenant-authorized storage or distributed concurrency guarantee. Attention remains explicit lexical heuristic.

## Durable memory eviction alignment

Durable working memory previously pruned only process-local chunks while leaving SQL rows, and saved newly submitted chunks even if capacity immediately rejected them. Restart could resurrect pruned memory. Eviction hook now deletes scoped SQL row and put persists only surviving chunk with actual requested partition.38 runtime/working-memory tests pass1warning incl immediately rejected weak chunk and later stronger replacement across reload. Memory update/eviction and DB calls are not one crash-atomic transaction or distributed synchronization; that remains unfinished. No production DB tested.

## World state keys and snapshot consistency

Dot-concatenated subject/predicate state keys silently collided ('a.b','c' vs 'a','b.c'). Keys now serialize JSON pair, an intentional state-key format change; old stored snapshots remain hashed as originally stored. State reads share SQLite read transaction; snapshot uses BEGIN IMMEDIATE spanning state read/prior-link/insert to prevent concurrent forks/mixed observations. Reject nonfinite JSON values.30 autonomy runtime/eval/routes tests pass1warning incl colliding pairs and32concurrent snapshots from8workers with intact chain. Hash chain is local mutable-store consistency, not independently anchored tamper-proofness or provenance truth.

World snapshot verify API now explicitly labels stored_snapshot_hash_chain_consistency_only and false independent_anchor/evidence_truth/completeness_verified. Entire-store rewrite/deletion cannot be detected without independent anchors; an empty chain passing is not completeness proof. Malformed stored JSON returns false instead of500. Focused evidence: hash-chain-scope.log. Adjacent M20/atomic/ledger rerun after462a630:2206pass2warnings37.14s,90files. Neither is original model depth certification.

Autonomy API invalid observations now return422 (e.g. whitespace-only subject) and repeated goal review returns403 instead of uncaught500, no stored bad observation or replacement review.29 focused runtime/API tests pass1warning; not capability depth. Evidence: agi-controlled-input-errors.log.

## Cooperative elapsed budget correction

Executive Budget.seconds was compared against tick count, not elapsed time; scheduler ignored quantum_seconds and reported configured maximum as actual ticks. Executive now checks monotonic elapsed time between steps separately from tick cap; scheduler passes requested seconds and reports measured tick count. Step report explicitly says cooperative_between_steps_only, hard_wall_time_enforced=false, tokens_money_enforced=false. Planning/model/dispatch/DB calls are not preempted by this boundary and can overrun; this is NOT a hard wall-clock, token, cost or fair-time-slice guarantee. Existing test comment equating seconds/ticks was corrected;49 focused runtime/executive tests pass1warning incl deterministic elapsed-clock stop after one action and planning failure zero actual ticks. No production scheduler timing tested.
