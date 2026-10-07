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

## Sensory dedupe provenance correction

Dedupe used global external IDs and hashes of audio/image/PDF model-generated text, silently dropping independent sources/modalities and distinct files with identical generated description. Keys now scope source+modality; binary modalities hash original bytes. Same raw input in same source/modality still dedupes. Source label is caller-reported, not verified sender identity. Model-generated text remains unverified; raw hash proves input equality, not semantic truth.41 sensory/runtime tests pass1warning including three modalities with different raw bytes/same generated text. Dedupe remains process-local/unbounded; durable bounded replay tracking and real multimodal model acceptance unfinished.

Sensory source allowlist/replay checks now run BEFORE binary injected transcriber/vision/parser and CSV parsing. Previously discard happened after model/parser, risking processing disclosure for rejected source.42 sensory/runtime tests pass1warning prove zero injected calls for disallowed source and duplicate raw bytes/ID. Source values remain caller labels, not authentication; no network model endpoint ownership verified. Process-local replay check is not concurrent atomic or durable.

Post-sensory/cooperative-budget adjacent regression after11c3192:90 M20/atomic/ledger named files2213pass2warnings36.75s. Evidence: post-sensory-budget-regression.log. Not whole repository or original-depth certification; last full495-file run predates subsequent memory/world/budget/sensory fixes.

## Episode store detached snapshots

record/get/for_task/recall/successful_patterns previously exposed same mutable history objects, allowing callers to rewrite outcomes/actions without updating vector/SQL. Store and reads now detach deeply; successful patterns reject episodes containing failed actions.57 executive/memory/runtime tests pass1warning incl mutations of input/record-return/all read paths. This is stored snapshot consistency, not independently verified execution truth. Explicit record of same ID remains caller-controlled update, no immutable authenticated receipt guarantee.

## Semantic memory detached snapshots

Caller/readback fact or graph metadata mutation previously rewrote in-process records without updating embeddings/SQL. Store/get/query/confirm/link/neighbors now detach deeply. Explicit store and confirm remain mutation paths; supplied provenance/confidence are not verified truth.58 memory/runtime/executive tests pass1warning incl fact/source and metadata mutation. No durable immutable receipt or causal fact verification claimed.

Post-memory detachment adjacent rerun afterfd0310d:90 M20/atomic/ledger2215pass2warnings36.99s. Existing M20 SandboxRunner feasibility check executed print("synthetic isolation probe") in bubblewrap: return0, expectedstdout,0.04s,no network. No generated code executed in service process, no science backend modification. Synthesis test/admission remain unavailable pending M20 exact-source/case isolation implementation and review lifecycle; working isolation probe is not completed synthesis capability.

## Isolated supplied pure-code tests, admission still disabled

Replaced synthesis test-only failclosed with M20-only supplied pure-code tests through existing SandboxRunner bubblewrap/Docker isolation, never in-process exec. Frozen detached source/AST/cases, source16Kchars/candidate64KB/cases1..20, JSON object inputs/expected JSON outputs,2secondwall512MiBaddressspace64KBoutput. Exact source/case changes reject; outputs compare canonical JSON.33 autonomy/runtime/API tests pass1warning including actual local bubblewrap sum function, incorrect cases, source/case mutation, unavailable backend failclosed, time-bound long loop and memory-allocation failure. Source generation/model synthesis and tool admission remain unavailable; request_admission/admit still failclosed. Existing backend requires usable isolation on deployment and is not a universal sandbox security proof. No science module edits, no hosted execution, no registration or external effects. Prior2215pass adjacent evidence is in post-memory-detachment-regression.log, predates this test-only path.

Post-isolated-pure-code adjacent regression: initial1failed2218pass due runaway fixture requiring timed_out while CPU rlimit killed first(return137,1.015s,timed_outfalse). Test now requires nonzero bounded stop(duration<5s), not misattributing137 to confirmed walltimeout. No backend runtime changed. Rerun2219pass2warnings37.41s90files; prior failure and rerun retained. This verifies bounded fixture termination, not universal resource isolation or production availability. Evidence: post-isolated-pure-code-before-timeout-fixture.log and post-isolated-pure-code-regression.log.

## AGI ledger historical-claim correction

Original audits/agi-capability-ledger.json still said AGI-01 reliability-weighted confidence, AGI-03 executable admission/typed tool dispatch, AGI-04 implemented-bounded recursive improvement, AGI-05 held-out transfer. Those are stale overclaims, not source-grounded current capability. Schema2 preserves original entries verbatim under historical_capabilities; current AGI-01..06 are PARTIAL with exact supplied-rollup/heuristic/pure-code-test/caller-evaluator/cache scopes and missing model/admission/production/durable guarantees. No aggregate original2000-feature verdict counts changed by this separate8-row ledger.

World supplied-weight rollup now scales before summing to prevent NaN shares from individually finite1e308weights. Relative supplied shares stay finite; overflowing raw support returnsnull with sum_exceeds_float_range instead of invalid Infinity.34 autonomy/API tests pass1warning incl2:1shares and snapshot JSON. These remain caller weight shares, not predictive confidence or truth.

ToolSelector Beta-smoothed history is manual supplied counters, not connected to real runtime dispatch history. API now explicitly reports history_status=manual_supplied_counts_with_beta_1_1_prior/runtime_dispatch_history_connected=false and raw supplied counts per candidate; validates exact bool outcomes/registered names.34 tool/runtime tests pass1warning. Default0.5 is prior, not measured reliability; ranking remains heuristic not learned tool policy.

Registered tools now snapshot ToolSpec deeply and expose detached spec readbacks/nonassignable spec+handler properties. Caller registration/readback mutation previously weakened risk/preconditions used at dispatch.46 safety/runtime/model-adapter fixtures pass1warning prove mutation cannot remove external risk/precondition. This is public-interface local integrity, not protection from hostile in-process Python accessing private internals, versioned tool review or OS isolation of registered trusted handlers.

Durable generated-method review gate corrected: repeated decompose of same goal/context reused name and saved replacement active, because demotion considered only new names. With require_review, every generated method registration now writes proposed directly, never temporary active; no new-name-only demotion.54 runtime/planner tests pass1warning incl3same-key replans remain proposed in memory/SQL. Method activation API still lacks separate exact-revision durable reviewer token lifecycle; no broader review/security completion claimed. Adjacent2222pass2warnings36.86s afterbee71dc predates this fix.

Method listing now returns review_hash; explicit activation requires expected_hash and rejects changed current revision409 without activation.55 runtime/planner tests pass1warning including same-name replaced candidate. Intentional API change: missing review hash fails422. This binds public activation request to displayed content, not a durable issuer/Module0 approval decision lifecycle or cross-process atomic review. Caller owner review and authenticated route controls remain necessary; no autonomous approval claimed.

## Method-review HTTP/durable revision correction

Prior hash tests covered direct planner only. New HTTP test reproduced a409 when submitting hash from current listing: same-name replacement appended SQL rows by new ID, while in-memory name map held only latest. Replacement now retains existing method ID, updating one row. HTTP missing/stale/current hashes reproduce422/409/200; restart test verifies latest subtask and proposed status survive, old hash rejects and explicit current hash activates persistently.35 runtime-depth tests pass1warning; adjacent90 M20/atomic/ledger files2226pass2warnings38.39s. Original failing HTTP1failed2224pass preserved. Additional restart fixture initially used nonexistent HTNMethod.steps, corrected to subtasks; that fixture failure is retained. No production DB migration or legacy duplicate cleanup performed, no concurrent multi-process compare-and-swap or durable reviewer decision lifecycle verified. Earlier direct-test hash claim was insufficient for HTTP/SQL behavior.

## Supplied tool argument-schema enforcement

ToolSpec.parameters previously only exported function schemas; dispatcher ignored required/types/additionalProperties and sent invalid arguments to handlers. Eight initial failing fixtures retained. Registration now checks the declared JSON Schema dialect (default2020-12), rejects invalid/unknown schema and non-document-local references. Validation uses an empty retrieval registry before approval consumption or handler invocation. Ten new tests cover wrong/missing/extra/boolean-as-integer arguments, actual valid fixture arithmetic, local references, unresolved references, remote/file refs, and preservation of an existing approval token after invalid arguments.128 focused safety/dispatcher/executive/runtime/schema tests pass1warning;91 adjacent M20/atomic/ledger files2236pass2warnings39.02s. Declared direct jsonschema dependency>=4.23,<5, previously installed transitively. This enforces caller-supplied schemas only, not independently verified schemas, model-generated typed calls, handler result schemas, synthesis generation/admission, production approval provenance, sandbox isolation of trusted handlers or durable exactly-once effects. JSON Schema format annotations are not separately asserted.

## Runtime trace flush cursor correction

Restart cursor was set to total SQL trace count while new loop.traces was empty, dropping the first N new traces. Surprise handling also advanced cursor for newly appended reflection before earlier pending trace was saved, dropping that earlier trace. Two failing reproductions retained. Cursor now starts0 for current process list and all surprise traces flush in ordered shared path. Another failing fixture found partial flush retried already-committed traces after a pre-commit error; cursor advances after each successful save.38 runtime-depth tests pass1warning;91 adjacent M20/atomic/ledger files2239pass2warnings40.62s. Tests verify restart, pending+reflection order and simulated pre-commit failure retry. No claim of crash-atomic trace/task transaction, uncertain-commit reconciliation, concurrent shared-runtime thread safety, immutable audit provenance or production durable effect outcomes. Historical traces skipped by old bug are not recovered.

## Retrospective restart history correction

close previously read only new in-process loop.traces, so a restarted runtime ignored stored failure/approval trace evidence when writing its template retrospective. Reproduced with actual local async handler raising a synthetic error, durable traces, fresh runtime then close; initial assertion failed and log retained. close now flushes pending traces and reads task-scoped SQL history.39 runtime-depth tests pass1warning;91 adjacent files2240pass2warnings41.74s. Retrospective remains deterministic text templates using trace string matching and stored plan status, not model-derived causal analysis, independently validated lessons or verified output-quality assessment. Idempotent repeated close remains tested. Historical traces already lost by earlier persistence defects are not reconstructed.

## Scheduler quantum continuation correction

A normal scheduler tick/time slice called run's terminal budget-exhaustion path, marking unfinished context FAILED and removing it from active scheduling. Failed reproduction retained. Scheduler-only yield_on_boundary now keeps unfinished work RUNNING without failure episode; direct run/start defaults keep their separate budget failure behavior. Last-step completion at scheduler boundary closes success without an extra slice.59 runtime/executive tests pass1warning, including actual fixture squares4/9/16 across three1tick quanta with restart after first, durable final state and deterministic between-step wall-boundary yield.91 adjacent files2242pass2warnings. Still cooperative, no hard wall/token/money enforcement or production fairness guarantee. Dispatcher records are process-local: final episode after restart lacks actions from earlier process, although plan summaries persist; durable per-action history remains unfinished.

## Clean-restart local action journal

Prior dispatcher.records was process-local; successful episode after restart contained only later actions, dropping earlier completed slice payloads. Extended existing square fixture initially failed expected2/3/4 action history, retained. ActionRecord now has stable ID; additive tenant-scoped m20_action_records stores reported payloads at normal context persistence, idempotent identical save and conflicting same-ID rewrite reject. Runtime hydrates records so later episode includes pre-restart actions.118 runtime/executive/dispatcher tests pass1warning;91 adjacent files2244pass2warnings38.46s. Local SQLite upgrade/downgrade of additive migration tested; production migration NOT applied, existing databases require it before new runtime. Clean-slice restart2/3/4 history reproduced, but no atomic handler/task/journal transaction, crash gap elimination, independent effect receipts, authenticated provenance or exactly-once guarantee. Action journal is unbounded and all tenant records hydrate; scalability/retention remains unfinished. Existing historical missing actions are not recovered.

## Optional reflection failure isolation

Terminal handler failure triggered optional model reflection inside dispatch try. Reflection exception was mislabeled tool error then invoked reflection twice and escaped before normal failure close/persistence. Six failing fixtures retained. Reflection exceptions now trace reflection model error once, retain original handler failure and allow terminal failed episode. Invalid/unavailable reflection dicts fail schema check; valid cause/fix/noncoerced bool retry is labeled unverified hypothesis and does not retry tool or prove causal explanation.75 executive/runtime/model-adapter fixtures pass1warning;91 adjacent files2251pass2warnings. These are failure-isolation/schema fixtures, not successful actual-model reflection; earlier actual tiny Qwen trial still failed intended schema. No causal learning, repair execution or production recovery claim.

## Task owner/scheduler metadata restart correction

SQL task storage omitted last_run_at/ticks_served/wm_partition; load_task also returned tenant_id=default for every tenant. Reproduced after fixing an initial fixture missing TaskContext import; both fixture error and real before-failure retained. Additive runtime_metadata_json stores scheduler service history/partition, while owner comes from scoped SQL row.44 runtime-depth tests pass1warning;91 adjacent2253pass2warnings40.18s. Local SQLite migration with an existing legacy row preserves row, defaults metadata{} and downgrades; production migration NOT applied. Legacy missing scheduler history defaults0/None and cannot be reconstructed. This preserves reported scheduling fields across clean restart, not production fairness, cross-process task locking or authenticated execution truth. Existing DBs need both Oct7 action-record and task-metadata migrations before this runtime.

## Unit-demand VCG allocation correction and integration claims

MechanismDesigner.vcg assigned only firstN sorted agents when agents exceeded items; later high-value agents could never win. Above8items main allocation was greedy but externality search factorial, so both optimality and truthfulness/scaling claims were false. Seven before-failures retained. Replaced with SciPy optimal assignment over real items plus zero-valued unallocated slots, leave-one-out optimal welfare payments, bounded64agents/items and finite nonnegative valuations<=1e100. Scarce-item later-agent and9item nongreedy counterexamples reproduce;96 independent small exhaustive fixtures match allocation welfare and payments.59 strategy/HTTP tests pass1warning;91 adjacent2262pass2warnings37.64s. Float assignment/extreme dynamic-range/ties remain numerical limits; unit-demand/quasi-linear theoretical conditions are not general combinatorial mechanism design or empirical incentive proof. Integration text retracted exact-all-row capability claims and production create_schema guidance, separates service/runtime bindings, records Oct7 unapplied migrations and actual Qwen schema failures. Docs are corrected scope, not new completion evidence.

## Supplied IID multiplier-growth boundary correction

ErgodicityAnalyzer treated a zero-probability zero multiplier as ruin, returning-Infinity log growth that HTTP JSON cannot serialize. It also accepted negative/nonfinite/bool inputs and broad ruin/ergodicity language overstated supplied average arithmetic. Eight failing fixtures retained. Only positive-probability support contributes; positive-mass zero multiplier yields growth0/lognull with explicit negative-infinity mathematical status. Finite nonnegative inputs, minimum1e-300 total mass and normalization scope are explicit. Legacy ergodic field only compares these two averages, not general process ergodicity or financial prediction.68 strategy/HTTP tests pass1warning incl extinction200JSON-safe, zero-probability outcome ignored and negative multiplier422;91 adjacent2271pass2warnings. Stale HTTP test expected original ruin phrasing and failed, retained before updating to narrowed verdict. This is supplied IID multiplier arithmetic, not measured dynamics or future ruin guarantee.

## Named HTTP task-step quantum correction

/runtime/tasks/{id}/step ignored accepted quantum_seconds and used terminal direct-run semantics; prior scheduler yield covered only/runtime/step. Before-failure retained. Named step now passes cooperative seconds budget and explicit yield-on-boundary, preserving direct run_task default.71 runtime/executive tests pass1warning;91 adjacent2272pass2warnings. HTTP fixture squares4then9 executes across wall-limited slice then1tick completion; clock is synthetic but handler arithmetic actually runs. Initial post-fix fixture undo restored auth env too and caused second request401; corrected to restore clock only, failure retained. Quantum still checks only between steps, no hard timeout/token/money enforcement or actual model cognition claim.

## Closed-task restart/execution lifecycle correction

close removed active task only from in-memory scheduler, leaving persistent active state. Restart rehydrated closed work; rerunning completed closed task created duplicate success episode. Two failing fixtures retained. New close explicitly cancels active context/unfinished nodes, clears pending approvals and persists; runtime hydration excludes any task with stored retrospective, including legacy closed-active rows. run_task/resume return stored context without execution for closed tasks.48 runtime-depth tests pass1warning;91 adjacent2275pass2warnings. Clean restart cancellation/no dispatch, duplicate episode prevention and legacy waiting-approval exclusion pinned. No atomic close/retrospective/task transaction, concurrent close-versus-running-handler cancellation, database corruption immunity or production lifecycle guarantee. Legacy closed-active rows retain their historical state on read but cannot be scheduled/run/resumed through these runtime entrypoints.

## Full-chain migration correction

Refreshed496-file full regression batch0 failed1test with1271pass2skip: clean Alembic upgrade hit action table already exists. Earlier isolated additive migration tests were insufficient. Actual cause is older20260922_m20_runtime_schema importing live GCWBase.metadata, prematurely creating future action table/task column. Initial suspicion of inherited auto-create flag was wrong. Historical M20 migration now uses frozen pre-Oct7 table metadata copied from0b1d027 source declarations, not live models.50 migration/runtime tests pass2warning, including clean-head and historical-revision absence then upgrade-to-head presence of new schema. Full batch0 rerun1273pass2skip2warnings; batch1=162pass10skip1warning. Remaining full batches still in progress. No production migration execution; changing historical metadata avoids future creation on clean upgrades but does not reconcile unknown existing divergent production schemas.

## Refreshed full repository regression after lifecycle/migration fixes

496test files,20 isolated file batches at082d8ae plus migration correction975cb80:9705passed,0failed,14skipped,26summed warning occurrences,398.26s summed final batch wall time. Manifest, each final log/receipt and summary in audits/rebuild-20261007/full-regression-after-lifecycle/. Initial batch0 clean migration failure1failed1271pass2skip preserved separately; all final batches exit0. Warnings are summed occurrences, not unique categories. Skips remain skips. This is local repository-test compatibility, not original2000feature depth, actual cognition/model quality, production rollout, external effects or live schema migration certification. Earlier9608pass18skip495files atb60c013 retained, not retroactively merged. Counts differ with added tests and isolated batch collection/import state; no certification inferred from larger number.

## Retrospective snapshot identity correction

Durable load rebuilt records with write, creating new IDs/timestamps rather than preserving stored identity. write/lessons_for also exposed mutable internal objects, letting caller changes diverge from SQL/vector. Failed fixture retained. Internal snapshot loader now preserves stored IDs/times, write and retrieval detach deeply.55 runtime/reflection tests pass1warning;91 adjacent2276pass2warnings40.54s. This is stored-record identity/local snapshot consistency, not immutable authenticated provenance, causal lesson truth or production deployment. Refreshed full9705pass evidence predates this latest fix; not silently promoted.

## Procedural-memory snapshot/retirement correction

SkillLibrary register/find/match/list/activate/proposal outputs exposed internal mutable objects; callers could change steps/status/evidence without SQL/vector-consistent writes. DurableSkillLibrary inherited retire without persisting it, restoring retired skills as active after restart. Two failing fixtures retained. Registration snapshots and public reads/proposal returns now detach deeply; durable retire writes changed registry.51 runtime-depth tests pass1warning;91 adjacent2278pass2warnings40.63s. Explicit trusted register/activate remain available and are not exact-revision durable approval lifecycle; tool-signature proposals remain heuristic grouping, not generalized learned skills. This is local snapshot/durable status consistency, not authenticated provenance or production deployment. Latest full9705pass predates this and retrospective identity fix.

## HTN method public snapshot integrity

register_method return/input/public methods dict shared mutable active template. Caller changes could replace reviewed subtasks without SQL update or review transition. Failed fixture retained. Internal method store is private; public methods property is detached read-only mapping; registration snapshots input/return. Internal usage counter updates still work.74 runtime/planner tests pass1warning;91 adjacent2279pass2warnings38.58s. Explicit trusted registration still changes library, and private Python internals are not security isolation. No durable distributed review token, concurrent compare-and-swap, authenticated method provenance or model planning success claimed. Latest full9705pass predates subsequent snapshot fixes.

## Registered library plan validation/fresh execution correction

Registered HTN libraries bypassed generated-step DAG checks; instantiation retained supplied succeeded/cancelled/attempts/approval/result fields, allowing fresh runtime success without handler execution. Five failing planner fixtures retained. Registration validates bounded/nonempty step list, unique IDs, resolvable/unambiguous dependencies and acyclicity before durable save; instantiation resets execution state while retaining descriptive fields.80 planner/runtime tests pass1warning;91 adjacent2285pass2warnings39.45s. Actual fixture computes9 even when template preset succeeded/fake output; invalid DAG leaves no SQL method. Validation doesn't establish goal relevance, safe model reasoning, reviewer authority or original model quality. Legacy persisted invalid templates fail loading rather than run unvalidated; no migration of corrupt library entries or production rollout performed.

## Supplied transfer benchmark snapshot consistency

Frozen TransferCase shells still held mutable problem/expected objects. Strategy/scorer/caller changes could alter benchmark data and recomputed hash after execution. Three initial failures retained. Benchmark now detaches at construction, readback and every strategy/scorer invocation; hash binds construction snapshot. Bool/string scorer values reject rather than coerce to perfect1. Eleven evaluation tests pass;91 adjacent2292pass2warnings38.73s. This is caller-label/callable evaluation with stable local data, not learned strategy, verified held-out domain, empirical real-world transfer or independent scorer truth. No actual-model benchmark success claimed; provenance event remains locally recorded metadata, not authenticated causal proof.

## Approved synthetic native-schema small-model follow-up

Same pinned0.5B Qwen GGUF/checksum and llama.cpp8345f333,2threads1024ctx128output, synthetic-only/no tools/fresh loopback/stopped. Trial-only purpose prompts/native response_format transport injected into actual adapter parsing; production routing untouched. Initial top-level schema request wasn't applied as intended by pinned server (expects nested json_schema.schema), preserved. Corrected native schema3/3valid, exact purposes2/3pass: plannerFAIL cyclic dependencies rejected by HTN validation, arithmetic17+25PASS42, reflectionPASS prompt-dictated labels/false. Reflection success is instruction/schema adherence, not discovered cause/repair.0.811s startup675012KiBpeak9.064stotal. Raw prompts/schemas/responses/errors in local-qwen-constrained-trial/. Small-model plumbing verification only, no general cognition/production/real-world transfer claim. Original unconstrained adapter all3fail evidence remains unchanged.

## Plan-risk escalation dispatch correction

Planner/plan could raise step risk, but executive dispatch ignored node tier and gated only registered ToolSpec tier. EXTERNAL plan on READ registered tool therefore executed without intended approval; initial failure retained. Optional dispatch risk floor now uses max registered/plan tier for exact effect binding and retry decision, executive passes node.risk.139 executive/dispatcher/runtime tests pass1warning;91 adjacent2295pass2warnings. Escalated READ pauses then approves once; lower caller floor cannot downgrade registered external, changed effective tier cannot reuse token, escalated uncertain handler stops after one attempt. This enforces explicit supplied/registered risk tiers, not inference of every real-world effect or owner authority. No denylist changes, no external effects or production approval integration claimed.

## Four-form curve-fit common-scale selection correction

NonLinearModeler compared y-space linear/log R-squared with log(y)-space exponential/power R-squared, incompatible metrics. Constantx/nonfinite/bool input also accepted; large finite covariance arithmetic yieldedNaN. Six initial failures retained. Fits normalized transformed axes, selects all candidates by original-y residual R-squared, exposes transformed scores separately and excludes nonfinite numeric candidates.75 strategy/HTTP tests pass1warning;91 adjacent2302pass2warnings. Independent NumPy polyfit original-residual check matches four reported scores;1e150 exact line remains finite/JSON-safe. This is four-candidate supplied-sample least squares, not general function discovery, original concept depth or validated future extrapolation. Floating-point dynamic-range/tie/underflow limitations remain. No trained predictive model or deployment claim.

## Supplied DAG critical-path correction

CriticalPathAnalyzer marked only one selected longest path critical, incorrectly excluding parallel zero-slack branches. Raw helper collapsed duplicateIDs, missing depsKeyError and long chains recursion failure. Six initial failures retained. Bounded1..10000task DAG validates IDs/dependencies/finite nonnegative durations, iterative topological longest/forward calculations avoid recursion; exposes one selected path and all zero-slack critical flags.97 strategy/HTTP/reasoning tests pass1warning;91 adjacent2308pass2warnings. Parallel equal branches and1200task chain reproduced. Supplied point-duration CPM only, no resource-constrained/uncertain scheduling or actual completion forecast. Float tolerance1e-12 times total stated; near-critical numeric ties are not exact mathematical certification.

## Supplied Monte Carlo summary correction

Population std recomputed mean(samples) inside each sample loop, quadratic summary cost. Nonfinite/bool/string samples accepted; extreme finite squaring overflowed. Six initial failures retained. Bounded integer10..100000trials, finite numeric sample validation and one scaled mean/population variance calculation; median averaging avoids same-sign sum overflow.103 reasoning/strategy/HTTP tests pass1warning;91 adjacent2314pass2warnings39.48s. Synthetic alternating+-1e300 summary mean0/std1e300JSON-safe; counted-mean fixture prevents per-sample mean recomputation. Explicit supplied-sampler simulation/quantile convention, not measured empirical distribution, calibrated predictive interval or deadline guarantee. Scaling can lose tiny relative magnitudes; arbitrary sampler CPU/runtime remains caller-controlled, trial bound is not process isolation.

## Supplied decision-tree rollback validation

Raw rollback treated unknown/empty branch as leaf; wrapper validated probability sum only, allowing negative probabilities summing1, nonfinite/bool leaves and cyclic recursion. Seven initial failures retained. Both raw/wrapper validate finite numeric leaf, known kind, nonempty branch, nonnegative chance probabilities sum1, cyclic/depth128/node10000 bounds; response labels bounded supplied-tree rollback.110 reasoning/strategy/HTTP tests pass1warning;91 adjacent2321pass2warnings35.19s. This is arithmetic on supplied probabilities/utilities, not learned policy, calibrated uncertainty, causal choice quality or empirical decision validity. Chance sum tolerance1e-6 is numerical, probabilities aren't inferred/verified. Trusted Python node/spec mutation and arbitrary evaluator effects remain separate concerns; no production decision authority claim.

## Bounded supplied sensitivity arithmetic interpreter

AST syntax allowlist still used in-process eval, accepting string work/exponent towers and uncontrolled divide-by-zero/empty/nonfinite inputs. Five initial failures retained (two invalid cases already rejected). Numeric-only AST interpreter replaces compile/eval with explicit arithmetic;4096chars256nodes32depth128params/exponent magnitude1000 bounds, finite numeric input/result checks and controlledValueError.94 strategy/HTTP tests pass1warning;91 adjacent2328pass2warnings35.07s. This computes bounded supplied model arithmetic and one-at-a-time swings, not learned sensitivity/interaction or empirically validated business model. No OS sandbox proof, numerical conditioning guarantee, broader denylist or generated code admission change.

## Supplied stationary ErlangC numeric correction

M/M/c direct powers/factorials overflowed at500servers; nonfinite rates/bool/unbounded counts accepted. Five initial failures retained. Log-domain ErlangC avoids powers/factorials overflow, finite rates and1..10000integer servers validated, numeric wait overflow rejects.99 strategy/HTTP tests pass1warning;91 adjacent2333pass2warnings37.42s.500servers450offered load finite/JSON-safe; c1 matches M/M/1 wait/Pwait. This is supplied stationary Poisson/exponential/identical-server formula, not measured queue fit, future waiting guarantee, staffing recommendation or real system capacity certification. Floating-point rounding and near-instability numeric limits remain; no production integration claim.

## Approval-request handoff snapshot correction

SafetyGate hashed exact effect, then passed nested mutable payload to injected approval gate. Gate mutation changed executed args after immediate approval while token hash still bound original. Dev gate stored caller request object too. Two failing fixtures retained. Approval request handoff and InMemoryApprovalGate storage now deep-copy; dispatcher keeps its execution snapshot.122 dispatcher/safety/runtime tests pass1warning;91 adjacent2335pass2warnings36.07s. Mutating test gate cannot rewrite executed reviewed argument; dev caller mutation doesn't rewrite stored request. This is local interface integrity, not authenticated reviewer decision, immutable gate storage, expiry enforcement, durable token provenance or production permission proof. No denylist changes or external sends.

## Supplied hypothesis ranking boundary/validation correction

A single active candidate normalized to probability1 and next update divided by zero; invalid later ID/ratio mutated earlier record before failing. Binary odds update acceptedNaN/Infinity/bool. Initial5failed25pass and expanded7failed54pass logs retained; attempted edit first failed because system python was absent, then applied with repository interpreter. Whole batch validates/computes before local mutation; log-odds binary update handles0/1/extreme finite ratios and rejects nonfinite/bool.61foresight/HTTP tests pass1warning; explicitly recorded87adjacent files2189pass2warnings34.32s (different selection from earlier91-file runs, not comparable coverage). Hypothesis engine remains an independent-binary-odds-then-normalize ranking heuristic with fixed retirement threshold, NOT categorical Bayesian inference, learned/discovered hypotheses, evidence truth or full row38. Scope now returned by HTTP and named in source. Binary update is exact supplied two-event Bayesian arithmetic within float rounding, not inferred likelihoods. No durability/concurrent transaction/immutable public records or production cognition claim.

## Supplied2x2 Nash input/numeric/scope correction

Only row shape validated; invalid/nonfinite/bool column matrix slipped through, and1e308matching-pennies differences overflowed and lost interior candidate. One pure result was called "unique stable outcome" without stability analysis. Five initial failures retained. Raw helper/wrapper validate both finite numeric2x2 matrices; independent player scaling before indifference differences keeps large matching-pennies0.5/0.5.131reasoning/strategy/HTTP tests pass1warning; same recorded87adjacent files2198pass2warnings35.40s. Asymmetric fixture independently checks both players' expected-payoff indifference. Scope is supplied2x2 pure enumeration plus nondegenerate interior candidate, not enumeration of degenerate mixed families, stability analysis, general game solving or real opponent behavior. Numeric cancellation/underflow can still omit ill-conditioned candidates; all full-depth claims remain open. No external gameplay, production or investment recommendation.

## Retraction: caller flags are not causal/correlation verification

Row40 CausalAssessor previously returned "causal_supported" from randomizedTrue alone or three checklist flags; no dataset/study/effect was inspected. Empty flags returned "correlational_only" without computing correlation. Both claims retracted: every input now returns verdictunverified/causality_verifiedfalse with separate caller-checklist coverage. All32flag combinations tested. Flags strictly bool/known keys; missing data/design/effect inspection remains required even with complete declarations. Four initial failures retained.66foresight/HTTPpass1warning; recorded87adjacentfiles2203pass2warnings35.53s (before final additive reminder text; focused rerun after text). This is an honest incomplete-feature result and checklist only, NOT implemented causal assessment. Prior checklist tests were changed to assert unverified rather than certifying flags. No new causal discovery/identification, actual study verification or production integration; row40 remains at original-depth gap. Existing explicit supplied structural-model computations elsewhere are separate and do not rescue this checklist claim.

## Supplied expected-value probability semantics correction

Raw expected_value divided by total probability, turning0.2chance100 into100 rather than20. Sensitivity added mass then renormalized, not actual10pp; duplicate best tuples all shifted. Seven failing reproductions retained. Bounded finite numeric outcome validation, sum(p*v) with explicit missing-mass-zero convention, scaled arithmetic; single first-best index shifts up to10pp capped0..1 with other mass proportional, degenerate remainder zero-valued.100reasoning/foresight/HTTPpass1warning; recorded87adjacentfiles2211pass2warnings38.08s.0.5chance100 sensitivity now60/40; duplicate tie checks selected0.4probability and independent sum;+-1e308balanced expectation finite0. This is supplied arithmetic plus a declared sensitivity convention, not independently known missing outcome value, calibrated forecast, optimal actual decision or full cognition. Zero missing-mass convention is explicit, not evidence; probability tolerance1e-12, float dynamic-range limits remain. No financial action/recommendation or production deployment.

## Supplied Kelly endpoint arithmetic correction

Full fraction/cap1 with certainwin1 reached0*log0 and raised domain error; nonfinite/bool odds accepted. Four initial failures retained. Raw/helper validate finite numeric win probability/positive odds and wrapper finite fraction/cap; log1p positive-mass terms omit zero-mass log0.108reasoning/foresight/HTTPpass1warning; recorded87adjacent2219pass2warnings37.15s. Certainwin2odds full1 growthlog3 reproduced; independent SciPy scalar maximum matches0.7win2odds full fraction/growth. Scope explicitly supplied IID binary-return arithmetic, not verified edge, empirical distribution, safe bankroll prediction, financial advice or action. Fraction/cap are caller policy and estimate errors remain. Source change is local while Git access waits; not deployment proof.

## Prompt registry detached-template consistency correction

register input/return/get/active exposed internal mutable prompt templates, allowing changes without version/audit writes. Registering same object twice also deactivated replacement. Two initial failing reproductions retained. Registry stores/returns deep snapshots, same input re-register creates activeversion2 without caller mutation.120metacognition/routes/runtime/exact-gate/mounted-owner tests pass1warning; recorded87adjacent2221pass2warnings41.21s. Initial broad3failed2218pass log retained: three stale-target fixtures relied on mutating get output; now they perform explicit registry replacement and still verify exact-review rejection at changedversion2. Snapshot mutation tests separately prove no state change. This is local registry integrity, not immutable audit/proposal store, authenticated reviewer, durable distributed revision/expiry, learned improvement benefit or production self-improvement. Trusted explicit registration remains an API; no denylist/permission surface widened.

## Semantic/episodic embedding-failure publication correction

Replacement stored new content before injected embedder; exception left old vector/new content or unindexed new item. Two initial failures retained. Compute vector before publishing content/vector.64memory/runtimepass1warning; recorded87adjacent2223pass2warnings40.82s. Fixtures preserve exact old record after replacement failure and absent new record after first-insert failure for both stores. This covers injected embedding exceptions only, not malformed vector validation, concurrent readers/writers, SQL write failure/crash transaction, trained embeddings or semantic relevance. Default hashing retrieval remains heuristic, not model-backed cognition; no production rollout or full original memory capability claim.

## Retrospective embedding-failure publication correction

Same content-before-embed ordering existed in retrospective snapshot loader/write, outside prior semantic/episodic fix. One failing replacement fixture retained. Compute embedding before publishing retrospective/vector.60reflection/runtimepass1warning; recorded87adjacent2224pass2warnings41.52s. Failed replacement preserves original and failed first write creates no extra record. Injected embedding exception consistency only, not malformed-vector checks, concurrent/store transaction, full close atomicity or lesson truth. No learned reflective cognition/production guarantee.

## Scheduler per-operation clock snapshot correction

Base next_context recomputed implicit wall time during sort/top/equality-tier; deadline priorities differed and empty tier caused modulozero. One initial failure retained via injected advancing clock. next_context/order/cognitive_load now use one timestamp per operation.81planner/scheduler/runtimepass1warning; recorded87adjacent2225pass2warnings39.68s. One deadline selection calls clockonce and returns actual context. This is local scheduling consistency, not starvation/deadline guarantee, measured parallel throughput or production clock reliability; active-context mutations/concurrency remain separate. Fair scheduler already passed explicit snapshot for selection.

## Heuristic UCT rollout failed-step bookkeeping correction

Rollout comment promised failed step blocks descendants but actual failed pending node remained eligible, repeatedly resampled/charged and starving siblings within rollout. One failed fixture retained. Local failed set now excludes failed nodes/direct dependents; unmet dependency already prevents deeper descendants.82runtime/planner/schedulerpass1warning; recorded87adjacent2226pass2warnings41.70s. Forced failure samples parent then sibling once, never child/repeatedparent. This repairs declared heuristic rollout bookkeeping, NOT empirical completion probabilities, full stochastic tree semantics, predicted correctness, actual execution quality or cognition. Expansion still assumes completion, reward risk/probabilities remain unfitted hand-written; no general search optimality/production claim.

## Refreshed full repository regression after source repairs

At sourcee2fe166,496test files in20isolated batches:9813passed0failed14skipped26summedwarningoccurrences419.27ssummed batch wall time. All20exit0. Manifest, logs, receipts, summary and bounded runner in audits/rebuild-20261007/full-regression-after-source-fixes/. Warning receipt parsing includes singular/plural; occurrences, not unique categories. Earlier9705pass snapshot remains separate. Includes later memory/review/numeric/checklist retractions; no certification of original breadth, actual cognition, real-world data quality, production schema or deployment. Skips are not completed features; broader full-depth gaps unchanged.

## Finite vector cosine scaling correction

Direct squared norm/dot overflow made identical1e308vectorsNaN;1e-300vectors underflowed to0. Nonfinite/bool accepted. Four initial failures retained. Independent per-vector scaling/finite numeric checks/fsum cosine clamped[-1,1]; empty/dimension mismatch retains legacy0.81memory/sensory/runtimepass1warning; recorded87adjacent2231pass2warnings35.37s. Extreme identical/antiparallel and independently normalized NumPy nonuniform fixture reproduced. Numeric vector arithmetic only, not semantic meaning, trained embedding quality, vector publication validation or model-backed cognition. Mixed-scale tiny components can underflow; mismatched dimensions still yield0 not certification. Latestfull9813pass predates this correction and isn't silently current.

## Supplied binary-test posterior zero-event correction

Binary sensitivity/specificity helper returned0 for impossible conditioning event, falsely asserting posterior; tiny positive product underflow likewise returned0 when true supplied posterior1. Bool rates accepted. Three initial failures retained,NaN/Infinity cases already rejected. Finite exactnumeric rates/bool selector validated; log likelihood normalization returns endpoints or controlled undefined-posteriorValueError for zero-probability event.114reasoning/foresight/HTTPpass1warning; recorded87adjacent2237pass2warnings33.72s. Independent80digit Decimal posterior fixture and1e-200times1e-200nonzero likelihood reproduced. Supplied arithmetic only, not verified test characteristics/calibrated diagnostics/real-world evidence. Complement rounding near1 and float representability remain. Latestfull9813pass predates cosine/this fix; no updated full-suite claim.

## Supplied beta-binomial count/numeric correction

Fractional/boolcounts and nonfinite shapes accepted;1e308equalshapes denominatorInfinity yieldedmean0. Five failures retained. Finite positive numeric shapes/integercounts0..10**15 validated; scaled posterior mean handles extreme shapes, nonfinite result rejects.79foresight/HTTPpass1warning; recorded87adjacent2242pass2warnings35.78s. Existing1/1+7success3failure analytic8/12 and largeequal0.5 reproduced. Caller prior/count arithmetic only, not independent count evidence, verified IID Bernoulli observation, trained rate model or original cognition. Floating precision can lose small updates relative to huge shapes. Latestfull9813pass atsourcee2fe166 predates latest3fixes.

## Heuristic UCT no-ready state correction

No pending node was treated as rootvalue1, even allFAILED/BLOCKED/WAITING_APPROVAL, falsely matching completed plan. Three initial failures retained. No-ready reports supplied succeeded/noncancelled fraction and no_ready_action unless all included succeeded; zero-visit clock stop retains time_budget instead of terminal.86runtime/plannerpass1warning; recorded87adjacent2246pass2warnings36.11s. Failed/blocked/waiting0, completed-plus-failed0.5 reproduced. Empty/allcancelled convention remains1 with no action, not verified success. Heuristic supplied-state report only, not output correctness, full stochastic tree model, actual predictive cognition or deployment. Latestfull9813pass predates subsequentcosine/Bayes/beta/thisfix.

## Model JSON exponent overflow correction

parse_constant rejected literalNaN/Infinity but JSON1e999/-1e999 silently becameInfinity through float parser. Two failing parses retained; first test-file creation lacked imports and collection error also retained before moving canary to existing strict-output file. Finite parse_float now rejects exponent overflow.88strict-output/freefirst/private-route/runtimepass1warning; recorded87adjacent2248pass2warnings35.45s. Parser/fixture-only evidence, no new model run/provider routing change or model correctness claim. Large integer/depth bounds and broader model trust remain separate; latestfull9813pass predates five subsequentfixes.

## Model JSON structural bounds

Text100kbound didn't bound parsed nesting;100/1500deep JSON accepted, two failures retained. Initial assertion that1500would raise decoderRecursionError was wrong in this environment and corrected to parent. Iterative parsed-depth64/node20000 limits plus decoderRecursionError normalization added.92strict/freefirst/private/runtimepass1warning after final injected decoder-error canary;87adjacent2251pass2warnings38.75s before that extra test. Recursion branch tested by injected decoder failure, not observed production exception. Structural parser guard only, not model correctness/prompt injection/provenance/OS resource isolation. No actual model run/provider route changes. Latestfull9813pass predates latest sixfixes.

## Legacy random-order heuristic candidate/count correction

best_score-1 discarded valid sufficiently costly/long ordering; blocked search reported configured16not actual1attempt. Two failing fixtures retained. bestscore-infinity, actualattemptcount and nullscore/noorder when blocked; simulationsinteger1..10000 validated.65planner/executive/service/HTTPpass1warning; recorded87adjacent2254pass2warnings37.18s.5IRREVERSIBLEsteps retained. Interim claim ordinary3step lost was wrong (READ/REVERSIBLE/EXTERNALexistingcanary passed) and corrected to parent. Reward is unfitted and order-invariant for same node set, so sampling doesn't optimize those orderings. No measured success, general tree search, predictive planning or cognition claim. Latestfull9813pass predates sevenlaterfixes.

## Legacy rumination lifecycle preservation

Legacy analyze-only rumination resetSUCCEEDED/BLOCKED/WAITING_APPROVALtoRUNNING, and raised callback leftRUMINATING. Four actual failing fixtures retained; earlier wronghelperNameErrorlog also retained before corrected fixture. prior state now restored in finally; trace says heuristicordering notmcts.97executive/service/HTTP/runtimepass1warning; recorded87adjacent2258pass2warnings35.94s. No handler/plan changes or reactivation; heuristic analysis remains nonpredictive/order-invariant and does not prove cognition. No concurrent state-change protection/production lifecycle guarantee. Latestfull9813pass predates eightlaterfixes.

## Retraction: legal authority metadata is not verification

Rows1210-1259template said authorityverifiedTruefromURL/title/jurisdiction/as-of, issueconfidence"supported"fromIDpresence, deadline"verified"fromcallerboolean, controls"evidenced"fromlabels. No legal retrieval/study/source/deadline computation. Retracted: authorityverifiedfalse, verifiedcount0, issueunverified, callerdeadlineclaimseparate, controllabelsunverified, named_capability_executedfalse/supplied_legal_review_template_only. One failingcanary retained;14legal/HTTPpass1warning; recorded87adjacent2259pass2warnings37.22s. Existingtests changed to expect metadata-onlynotcertification; attorneyreview remains blocked on independentverification. This is honest incompletefeature result, NOT legalresearch/drafting/practitionerimplementation. Profiles, suppliedcontent/checklists remain, no sources retrieved or real law analyzed. Latestfull9813pass predates ninelaterfixes.

## Heuristic UCT budget input correction

Constructor acceptedNaN/Infinityclock, boolsimulations/fractionaldepth and invalid exploration;NaNtimecomparison never fires. Six initial failures retained. Exactinteger simulations1..100000/depth1..128, finite seconds(0,60]/exploration[0,100] validate.94runtime/plannerpass1warning; recorded87adjacent2265pass2warnings39.02s. This rejects bad configured limits; clock remains cooperative between simulations, NOT hard preemption inside traversal/rollout, now source wording corrected. Heuristic reward/unfittedprobabilities unchanged, no cognition or deployment claim. Full9813pass predates tenlaterfixes.

## Observed calibration raw-input correction

Raw resolve acceptedstring"false"as truthycorrect, assess acceptedboolconfidence/fractionalorboolcount, zero bins silently empty. Five initial failures retained. Exactbooloutcome/finite numericconfidence0..1/integercount0..10**15/integerbins1..1000 validate.119metacognition/HTTP/runtimepass1warning; recorded87adjacent2270pass2warnings40.30s. Invalid correctness rejected before mutation. Observed supplied-label metrics only, not truth of outcome labels, predictive recalibration/epistemic boundary, mutable-public-claim immunity or production certification. HTTPpydanticcoercion separate; no claim that raw guard establishes strict transport inputs. Full9813pass predates elevenlaterfixes.

## Observed calibration public snapshots

assess/resolve returnedinternalclaim and publicmapping exposed it, permitting uncheckedconfidence/outcomechange withoutSQLwrite. One failingcanary retained. Privateclaimstore/detachedread-onlymapping/deepreturn snapshots; durableloader usesprivatehydration.120metacognition/HTTP/runtimepass1warning; recorded87adjacent2271pass2warnings36.90s. Mutatingreturnedpredictiondoesn'tresolvemetric, mutatingresolved/publicsnapshot leaveserror0.8. Localintegrityonly, not empirical label truth, privatePythonisolation,SQLcrashatomicity, immutableprovenance or predictivecalibration. HTTPcoercion unchanged; full9813pass predatestwelvelaterfixes.

## Calibration HTTP strict-input boundary

Priorrawguards were bypassed by requestcoercion: bool/stringconfidence,stringcount/stringoutcomeaccepted; countabove10**15raisedunhandledValueError. Five initialfailuresretained. Claimrequest strictfiniteboundednumber/count and StrictBooloutcome return422beforeengine.125metacognition/HTTP/runtimepass1warning; recorded87adjacent2276pass2warnings41.47s. This binds transport to rawtypedmetrics, not labeltruth/authenticatedobservation/predictivecalibration. Full9813pass predatesthirteenlaterfixes; no productionclaim.

## Scheduler surprise report propagation

_run_and_persistresolved/consumedcallerexpectationsthenstepre-evaluated, reportedsurprisesemptydespitepersistedreflection. Oneactualfailedreport retained; initialmissingToolSpecdescriptionfixtureandbroadfailurealsoretained. Runhelper nowreturnsfirstsurprises; stepreportsitandrun_taskdoesn'tdoubleevaluate.65runtimepass1warning; recorded87adjacent2277pass2warnings39.05s. Syntheticreadsuccessvs0.1suppliedpredictionreportsfixturestepandresolvesclaim. Suppliedprediction/outcomelabelconsistencyonly, not calibrated surprise/cause/replanning or provenance; full9813pass predatesfourteenlaterfixes.

## Approval resume exact waiting-node lifecycle correction

resume acceptedanynode, resetsucceededREADtoPENDING/reexecuted it; unknownnode rejection blockedwholecontext. Two initialfailuresretained. Exactbool/existingWAITING_APPROVALnodewithapprovalID required before mutation; unknownKeyError/nonwaitingValueError, legacyHTTP404/409 andstrictboolrequest.106executive/service/routes/runtimepass1warning; recorded87adjacent2279pass2warnings39.95s before HTTPerrorcatch edit, focusedafter. Completedreadstayssucceeded/callsonce, unknowndenialdoesn'tblockwholecontext. Localresumesemanticsnot authenticatedreview/ownergrant; gate stillchecksboundtoken. No effectexecutedbeyondsyntheticfixture. Full9813pass predatesfifteenlaterfixes.

## Skill revision bookkeeping

register used active-only lookup: retiring all revisions reset next version to1; activating older revision left two active same-name entries. Two reproduced failures retained. Version now increments from maximum stored same-name revision; activation retires other same-name entries and durable adapter persists all changed entries.84memory/runtimepass1warning; recorded87adjacent2282pass2warnings38.78s. Restart fixture verifies retirement/version/activation continuity. Local registry bookkeeping only, not authenticated exact-revision approval, skill generality or multirow SQL crash atomicity. Full9813pass predatessixteenlaterfixes.

## Full local regression after skill revision corrections

Source 724c275: 496 files in 20 isolated batches, 9869passed/0failed/14skipped/26 summed warning occurrences, 417.2s summed process time; every exit0. Manifest, receipts, logs, runner and summary retained under full-regression-after-skill-revisions. This refresh includes the sixteen source corrections since e2fe166. Green local fixtures do not verify original cognition breadth, authenticated review authority, distributed effects or production provisioning. Historical full-regression evidence retained unchanged.

## Working-memory supplied attention publication

Eight reproduced failures: invalid supplied scores accepted and callback failures leave overcapacity store or partial refresh scores. Finite numeric0..1/notbool validation; isolated callback inputs and staged score/capacity selection before shared publication.83working-memory/runtimepass1warning; recorded87adjacent2291pass2warnings39.90s. Callback content mutation canary also passes. Local callback-failure consistency only, not semantic attention, cognition, reentrant/concurrent isolation or durable multirow SQL crash atomicity. Latest full9869pass source724c275 predates this correction.

## Embedding buffer publication

Seven reproduced failures: semantic/episodic/retrospective stores alias provider reusable buffer, giving unrelated stored entries queryscore1; malformed fact vectors publish. Initial retrospective fixture used nonexistent recall method, retained separately and corrected before reproduced similarity failure. Shared finite exact-dimension vector validation and detached list snapshots used for stores and queries.91memory/runtimepass1warning; recorded87adjacent2298pass2warnings38.06s. Synthetic orthogonal supplied vectors now return1and0; invalid fact publication rejects. Local vector integrity only, not semantic retrieval quality, cognition or SQL crash atomicity. Latest full9869pass source724c275 predates two later source corrections.

## Supplied ideation flag ranking

Three actual initial failures retained: malformed/NaN weights accepted, truthy string false earns weight, finite weight addition overflows. Finite numeric/notbool weights, exactTrue criterion flags, fsum with overflow rejection and batch validation before score mutation.76reflection/runtimepass1warning; recorded87adjacent2301pass2warnings40.28s. Explicit weighted ranking of supplied flags only, not independent feasibility/constraint evaluation, creative cognition or original divergent/convergent capability. Latest full9869pass source724c275 predates three later source corrections.

## Supplied uncertainty threshold validation

Three reproduced failures retained: NaN becomesconfidence1, invalid/reversed thresholds accepted, stringfalsehighstakes accepted. Exactfinite0..1confidence/thresholds, highstakes thresholdnotlowerthanordinary, exactboolflag.79reflection/runtimepass1warning; recorded87adjacent2304pass2warnings39.10s. Question generation from supplied confidence/flag only, not empirically measured epistemic uncertainty or high-stakes safety certification. Latestfull9869passsource724c275 predatesfourlaterfixes.

## Supplied scheduler aging rates

Six actual failures retained: malformed/nonfinite/negative/bool aging rates accepted; finite aging multiplication overflow selects infinite priority. Finite nonnegative numeric/notbool rate and finite computed priority validate before selection mutates counters.72runtimepass1warning; recorded87adjacent2310pass2warnings38.01s. Same-clock base/aging calculation. Heuristic aging and local service counts, not unrestricted starvation/fairness guarantee with unbounded arrivals or zero rate. Latestfull9869passsource724c275 predatesfivelaterfixes.

## Supplied simulation fidelity metric integrity

Two reproduced failures retained: malformed/nonfinite/bool numeric predictions publish, returned/public records rewrite computed score. Strictfinite numeric prediction/actual/confidence, boundedconfidence, private records with detachedread-onlymapping/deepreturns. Scaled operands avoid unneeded difference overflow.81foresight/HTTPpass1warning; recorded87adjacent2312pass2warnings41.69s. Relativeerror arithmetic on supplied prediction/actual only; futureconfidence multiplier is legacy heuristic, not fitted calibration or independent outcome verification. Raw validation does not establish HTTP strict input types. Latestfull9869passsource724c275 predatessixlaterfixes. Original cognition/production incomplete.

## Simulation HTTP numeric boundary

Six reproduced failures retained: bool/string prediction/confidence/actual coerce into accepted raw numbers. Strictfinite numeric fields now422beforetracker mutation; integer JSON numbers remain accepted.87foresight/HTTPpass1warning; recorded87adjacent2318pass2warnings40.95s. Transport input consistency only, not supplied outcome truth/independent verification/fitted calibration. Latestfull9869passsource724c275 predatessevenlaterfixes.

## Hypothesis public snapshots

One actual failure retained: returned/public/ranking views rewrite internal probability/status despite update validation. Privatehypothesisstore with detachedread-onlypublicmapping/deepreturns/rankingviews.88foresight/HTTPpass1warning; recorded87adjacent2319pass2warnings39.82s. Synthetic0.6prior/LR2vs0.4 yieldsnormalized0.75/1.15 despite external view mutations. Heuristic independent binary odds plus survivor renormalization, not categorical Bayesian inference/evidence truth or cognition. Latestfull9869passsource724c275 predateseightlaterfixes.

## Binary Bayesian sequence odds preservation

Two reproduced failures retained: displayedposterior rounds1afterLR1e300 then LR1e-300 cannotrecover0.5; invalidprior skippedonemptysequence. Accumulate supplied loglikelihood ratios independently of displayed posterior, fsum prefix terms; validateinitialprior evenemptysequence.90foresightHTTPpass1warning; recorded87adjacent2321pass2warnings38.27s. Synthetic reciprocalLRsequence now0.5final. Finiteprecision binary suppliedlikelihood arithmetic, not independent likelihood verification/categoricalinference or cognition. Latestfull9869passsource724c275 predatesninelaterfixes.

## Supplied base-rate heuristic blend

Twelve actual initial failures retained: malformedstrength/count/probabilityinput and finite denominator overflow collapses0.5samplefactor to0.1floor. Positivefinite numericstrength/notbool; finite0..1suppliedprobabilities/notbool; exactintegercount0..10**308; scaled ratio avoids denominator overflow.102foresightHTTPpass1warning; recorded87adjacent2333pass2warnings41.03s. Syntheticstrength1e308/count10**308 nowweight0.5andadjusted0.5. Explicitheuristicblend, minimumsamplefactor0.1evenzero samples, not inferred base rate/empirical calibration. Raw guards do not prove strictHTTPinputs. Latestfull9869passsource724c275 predatestenlaterfixes.

## Supplied planning ratio arithmetic

Ten actual failures retained: malformedshrinkage/nonfinite/boolnumericinput/overflowratio publication and avoidablemultiplieroverflow. Finite nonnegative shrinkage, validfiniteestimated/actual, ratiofinitebeforeappend; shrinkageweightcomputedbeforemultiply, corrected-resultoverflowrejects.112foresightHTTPpass1warning; recorded87adjacent2343pass2warnings38.71s. Three1e308ratios withzeroshrinkage nowfinite1e308multiplier; estimate10correctedresultrejects. Supplied ratio shrinkage heuristic only, not verified durations/validated forecasting; publichistory mutation remains separate. Latestfull9869passsource724c275 predateselevenlaterfixes.

## Planning ratio history views

One actual failure retained: publichistorylist permitsNaN/ratioedit bypassing validation. Privatehistory/detachedread-onlymappinglistviews.113foresightHTTPpass1warning; recorded87adjacent2344pass2warnings38.74s. Publicsnapshotmutationleavesmultiplier2/samplecount1. Localinputintegrityonly, not verified durations/validated forecasts or privatePythonsecurity. Latestfull9869passsource724c275 predatestwelvelaterfixes.

## Supplied reference-case outcome arithmetic

Five actual failures retained: invalidnumericoutcomespublish; evenfinite median overflows1.6e308/1.7e308. Finite numeric/notbool case outcomes; dividedoperandsforevenmedian.118foresightHTTPpass1warning; recorded87adjacent2349pass2warnings39.22s. Syntheticmean/median1.65e308 nowfinite. Lexicalcase matching/fallbackheuristic only, not verified relevance/predictive validity. Publiccases/configvalidation/transportcoercion remain separate. Latestfull9869passsource724c275 predatesthirteenlaterfixes.

## Reference selection snapshots and midpoint correction

Eight actual failures retained: invalid selectionconfig accepted, publiccase mutation bypasses guards, prior dividedoperandmedianfix loses equal smallestsubnormal. Positiveinteger minsimilar; finite0..1notbool overlap; privatecases/deepdetachedviews; signaware midpoint preserves equalminimumsubnormal and largefinitepair.126foresightHTTPpass1warning; recorded87adjacent2357pass2warnings39.40s. Corrects incompleteness of previousmedianfix. Lexicalreference selection only, not evidence relevance/forecast validity. Latestfull9869passsource724c275 predatesfourteenlaterfixes.

## Full local regression after foresight corrections

Source c5b11ab: 496 files/20 isolated batches/9944passed/0failed/14skipped/26summedwarningoccurrences/420.24s summedprocess time, everyexit0. Manifest/receipts/logs/runner/summary retained under full-regression-after-foresight-fixes. Includesfourteen source corrections since724c275. Historical9869and9813runs retainedunchanged. Localfixtures do not verify original cognition breadth, authenticated review authority, distributed effects or production provisioning.

## Supplied optimism metric inputs and snapshots

Eight reproduced failures retained: invalidsampleminimum/confidence/outcometypes/publicrecordeditsrewrite signederror. Positiveintegerminsamples; strictfinite0..1numericconfidence/notbool/exactbooloutcome; private records/detachedread-onlymapping.134foresightHTTPpass1warning; recorded87adjacent2365pass2warnings39.47s. Snapshotedit leaves signederror0.8/count1. Supplied-labelmeanerror/heuristicsubtraction only, not verifiedoutcomes or fittedpredictivecalibration. Transportcoercion separate. Latestfull9944passsourcec5b11ab predatesonelaterfix.

## Optimism HTTP strict numeric and outcome types

Six actual failures retained: bool/stringconfidence/stringintegeroutcome coerce past rawguards. Strictfinite0..1numericfields/StrictBooloutcome422beforemutation.140foresightHTTPpass1warning; recorded87adjacent2371pass2warnings39.29s. Transport consistency only, not truth of suppliedoutcomes or empiricalpredictivecalibration. Latestfull9944passsourcec5b11ab predatestwolaterfixes.

## Supplied scenario weight normalization

Six reproduced failures retained: negative/nonfinite/bool/unknownweights and sumoverflow yieldsallzeroshares. Knownfixedscenario names/finite nonnegativenotboolweights/positive mass/scaled normalization.146foresightHTTPpass1warning; recorded87adjacent2377pass2warnings38.48s. Four1e308weights yield0.25each. Fixed driver narrative templates and supplied/defaultweightnormalization, not forecast validity/creative scenario discovery. Transportcoercion separate. Latestfull9944passsourcec5b11ab predatesthreelaterfixes.

## Base-rate HTTP input types

Five actual failures retained: bool/stringprobability/count coerce past rawguards. Strictfinite0..1numericprobabilities/exactintegercount0..10**308 now422beforearithmetic.151foresightHTTPpass1warning; recorded87adjacent2382pass2warnings41.25s. Transport type consistency only, not calibratedprobability or base-rateprovenance. Latestfull9944passsourcec5b11ab predatesfourlaterfixes.

## Planning HTTP numeric and overflow boundary

Five reproduced failures retained: bool/stringdurationcoercion and unhandledratio/correctedestimateoverflow. Strictfinite requestnumbers; arithmeticValueError translates422with ratio rejectionbeforepublication.156foresightHTTPpass1warning; recorded87adjacent2387pass2warnings41.11s. Supplieddurationarithmetic/transportconsistency only, not forecast validity or verifieddurations. Latestfull9944passsourcec5b11ab predatesfivelaterfixes.

## Supplied outside-view blend inputs

Five actual failures retained: nonfinite/bool insideestimate/weight and suppliedNaNreference median accepted. Strictfinite numeric/notboolinsideestimate/weight/median, weight0..1.161foresightHTTPpass1warning; recorded87adjacent2392pass2warnings38.83s. Convex arithmetic/framingtemplates only, not outside-view inference/reference relevanceverification. Transportcoercion separate. Latestfull9944passsourcec5b11ab predatessixlaterfixes.

## Reference and outside-view HTTP numeric boundary

Six actual failures retained: bool/stringoutcome/estimate/weight coerce past rawguards. Strictfinite numericfields now422beforecasepublication/blendarithmetic.167foresightHTTPpass1warning; recorded87adjacent2398pass2warnings45.06s. Transport consistency only, not reference relevance/predictive validity. Latestfull9944passsourcec5b11ab predatessevenlaterfixes.

## Scenario HTTP supplied weight boundary

Four actual failures retained: bool/stringweightcoercion and unhandlednegative/unknownweight errors. Strictfinite nonnegative mappingvalues; planvalidationValueError becomes422.171foresightHTTPpass1warning; recorded87adjacent2402pass2warnings45.30s. Fixed-template narrative/suppliedweightnormalization only, not forecasting or inferred scenario likelihood. Latestfull9944passsourcec5b11ab predateseightlaterfixes.

## Supplied sampler subnormal median

One actual failure retained: evenequalminimumsubnormalmedian lostto0 via divided operands. Signaware midpoint preserves equalminimumpositivevalue and avoidsoverflow forlargefinitepairs. 153foresight/reasoningpass; recorded87adjacent2403pass2warnings43.39s. Suppliedsampler descriptivestatistics only, not model/forecast validity. Latestfull9944passsourcec5b11ab predatesninelaterfixes.

## Supplied hyperbolic discount numeric arithmetic

Five reproduced failures retained: malformed/nonfinite/boolinputs and overflowingfinite denominator returns0instead ofrepresentable0.5. InitialunqualifiedfixtureNameError retainedseparately/correctedbefore actualreproduction. Finite numeric/notboolinputs; overflowpathdividesbeforemultiplication.158reasoning/foresightpass; recorded87adjacent2408pass2warnings44.06s. Supplied hyperbolicformula only, not inferreduserdiscountpreferences or temporaldecisionoptimization. Latestfull9944passsourcec5b11ab predatestenlaterfixes.

## Supplied sensitivity callback validation

Eight actual failures retained: invalidswing evaluatescallbackbeforevalidation, callbackrewritescallerparams, malformedoutputsaccepted. Finite numeric/notbool nonnegativeswing/params/perturbations validatedbeforeevaluation; detachedcallbackdicts andfiniteoutput/impactguards.166reasoningforesightpass; recorded87adjacent2416pass2warnings45.03s. One-at-a-time supplied-evaluator sensitivity only, not global sensitivity/causalproof. Arbitrarycallbackexternal effects cannotrollback. Latestfull9944passsourcec5b11ab predateselevenlaterfixes.

## Supplied Little law finite algebra

Six actual failures retained: bool/negative/nonfiniteinput/undefinedzerodenominator/overflowresult. Exactlytwosuppliedfinite nonnegative numeric/notboolvalues, positive divisiondenominator, finiteresult.172reasoningforesightpass; recorded87adjacent2422pass2warnings43.83s. Steady-statealgebra only, not verifiedqueue stability/validthroughputmeasurement/production performance. Latestfull9944passsourcec5b11ab predatestwelvelaterfixes.

## Brier supplied label score types

Five actual failures retained: string/integeroutcomes/bool/outofrange/NaNprobabilities accepted. Malformedpair alreadyValueError, not countednewfailure. Finite numeric0..1notboolprobability/exactbooloutcome/validpairs/fsum meansquareerror.178reasoningforesightpass; recorded87adjacent2428pass2warnings42.47s. Proper score on supplied labels only; lowermeansquareerror not independent calibration or labeltruth. Latestfull9944passsourcec5b11ab predatesthirteenlaterfixes.

## Standalone supplied planning median ratio

Seven actual failures retained: malformedestimate/ratios accepted/discarded and largefinite evenmedianoverflow. Positivefinite numeric/notboolestimate/ratios; stablepositive midpoint; finitecorrectedresult.185reasoningforesightpass; recorded87adjacent2435pass2warnings41.99s. Explicit0.05ratiofloor/emptyhistoryfactor1heuristic, not verifieddurations/reference relevance or validatedforecasting. Latestfull9944passsourcec5b11ab predatesfourteenlaterfixes.

## Full local regression after reasoning corrections

Source 69d6262: 496files/20isolatedbatches/10022passed/0failed/14skipped/26summedwarningoccurrences/433.55s summedprocess time, everyexit0. Manifest/receipts/logs/runner/summary under full-regression-after-reasoning-fixes. Includesfourteen sourcecorrections sincec5b11ab. Historical9944/9869/9813runs retainedunchanged. Localfixtures do not establish original cognition breadth, authenticated review authority, distributed effects or production provisioning.

## Supplied minimax regret table

Five actual failures retained: empty/mismatched/malformed tables and extremefinite differencescollapse distinctregrets toinfinitytie. Nonempty matching scenario tables/finite numericnotboolpayoffs; commonscale regret comparison avoids differenceoverflow.190reasoningforesightpass; recorded87adjacent2440pass2warnings42.12s. Supplied table decisioncriterion only, not scenario validity/real-worldoptimal choice; common-scale finiteprecision can lose tiny relative distinctions. Latestfull10022passsource69d6262 predatesonelaterfix.

## Bare-minimum ideation capability downgrade

Observed count12produces6unique defaultframe strings; forcedanalogyjust formats suppliedpairs; convergerankssuppliedflags. No modelgeneration/independentconstraintevaluation/noveltyassessment/learnedanalogy. One initialboundarycanaryfailure retained. Outputs nowfixed_prompt_frame_only or supplied_concept_pair_formatting_only, creative_generation_executed=false; source descriptions and READMEexplicitlythin/unfinished.86reflectionruntimepass1warning; recorded87adjacent2441pass2warnings41.64s. This is an honest downgrade, not a creative implementation upgrade or original capability completion. Latestfull10022passsource69d6262 predatestwolaterfixes.

## Ideation model-backed workflow build-out, live acceptance open

User1:24:29scope sharpened towardreal-worldfunctionalbuildout. Two actual initial missingworkflow failures retained. Separate ModelIdeationEngine.generate andPOST/meta/ideation/generate nowcall injectedexecutive model withobjective/constraints/count; dedicatedprivatefree-firstprompt, structuredproposal/firsttest/risks/exactconstraintcoverage, duplicateandmalformedoutputrejection, boundedinputs, unavailable503 andnotemplatefallback. Legacyfixedframes namedthin/downgradedexplicitly, notsilentlyupgraded.95reflection/routes/runtimepass1warning; recorded87adjacent2447pass2warnings44.11s. Synthetic task-specificmodel fixture and mockedprivateadapter provewiringonly; noactualmodelgeneration/usefulnessacceptancerun. Modelwrittenrisk/constraintclaims unverified; noexternalactions. This is functionalproposalplumbing, NOT originalcreativecognitioncompletion. Productionmodelconfig/realusefulnessremainopen; owner-controlledendpointnotprovedbyprivatelabel. Latestfull10022passsource69d6262 predatesthreelaterfixes.

## Actual local ideation acceptance failed

Parent authorized pinnedlocaltrial afteruserbuildmandate. SameverifiedGGUF/runner, freshloopback18961/2threads/1024ctx/256outputtokens/syntheticonly. Actualproductionprovider/adapter transport withrecordingwrapper thatforwardsrealcalls, no mock/native-schema/promptsubstitution.0/2accepted: both truncatedinvalidJSON, librarysamplewrongcount/checktypes; homeworkcomplexsurveillanceproposal/stringrisks/unrelatedchecks. Vaguefirsttests. Rawoutputsverbatim/logs/scriptretained underlocal-qwen-ideation-acceptance.23.30stotal/599896KiBpeak/serverstopped. Explicitstatus: plumbingworksfixtures, pinnedmodeltooweakforconfiguredworkflow, real-worldideationnotfunctional.256tokenlimitcontributes;2samplesnotproofalldifferentconfigurationsfail. Legacyfixedframedowngrade staysnamed. Noexternalaction/spend/newweights. Latestfull10022source69d6262 predatesthreecodefixes.

## Ideation output failure diagnostics

Actuallocaltrial exposed malformedoutput misreported as providerunavailable. One reproducedcanary retained. Executiveadapterfailurekind distinguishesinvalid_output/provider_unavailable; ideationinvalidoutput nowValueError/HTTP422, unavailableRuntimeError/503.96reflection/routes/runtimepass1warning; recorded87adjacent2448pass2warnings45.13s. Diagnosticcorrection only; failedliveideation0/2unchanged, no rerun or qualityupgradeclaim. Latestfull10022passsource69d6262 predatesfourlatercodefixes.

## Structured premortem risk-control register build-out

Legacypremortem sameplaceholder0.5x0.7suppliedrisks/keywordgenericprevention is thin, explicitlynamedinREADME; notrealcausalfailureanalysis. Twoinitialmissingworkflowfailuresretained. Newassess_register/HTTP supports1..100riskobjects, exactordinal1..10severity/occurrence/detection, productpriority/tieordering, owner/mitigation/test/evidencegaps, completeness-onlyreviewstate. No inferredprobability/evidenceverification/actionapproval.175foresightHTTPpass1warning; recorded87adjacent2451pass2warnings (exacttimeinlog). Payrollriskfixture180 outranks30; HTTPincompletepacketgaps clearafter suppliedfields but evidence remainsunverified. Request-scopedfunctionalreviewregister, notdurableriskownership/liveevidence/scheduledfollowup. Those operationalparts remainunfinished, not a fullyreal-worldriskworkflow. Latestfull10022source69d6262 predatesfivelatercodefixes.

## Durable tenant risk review revisions

Oneactualmissingworkflowfailure retained. SQLtenant/register currentrevision plus append-onlythroughinterface historicalreportrows; transaction CASupdate/historyinsert, stale409, unknown/cross-tenant404, strictrevision/validatedrisks, runtimecreate/get/history/revise routes. Restartfixture preservesoriginalowner/controlgaps; revision2doesnotoverwritehistory1.76runtime/migrationpass2warnings; recorded87adjacent2453pass2warnings (exacttimeinlog). Additivemigration localSQLitecleanhead tested; initialdirectpytestcombinedimportpathfailure retained, python-mpytest passes. No productionmigration. Suppliedowner/evidenceunverified, noassigneeidentity/notifications/followup, noPostgreSQLconcurrentacceptance, noadmin-tamperproofing. Usefuldurablecontrolreview not completeoperationalriskmanagement. Latestfull10022source69d6262 predatessixcodefixes.

## Durable risk register discovery and failure rollback

Oneactualmissinglistfailure retained: registeredriskIDmustbecarriedafterrestart. Addedtenant-boundGET/runtime/risk-registers boundedrecent1..100summarylist, opencontrolgapcount/highestsuppliedpriority/reviewcompleteness. IndependentfileSQLiteengineclose/reopenfixture listsoriginalregister; othertenantempty. Injectedrevisionhistoryinsertfailure rollsbackcurrentCASrevisionandhistorytogether.76runtimepass1warning; recorded87adjacent2455pass2warnings47.44s. LocalSQLitetransaction/restart evidence, notPostgresparallelwriters/deployedavailability. No liveevidence/assigneeverification/notifications. Latestfull10022source69d6262 predatessevencodefixes.

## Additional risk revision parallel-writer evidence

FileSQLite twoindependentengines/threads/barrier submitexpectedrevision1together: onecommit/oneconflict/history1,2/winnerownerretained.77runtimepass1warning. Testpassedfirstattempt, evidenceaddition notnewreproduceddefect orsourcefix. PostgreSQL/deployedparallelacceptanceremainsopen. Logrisk-parallel-writer retained.

## Risk review revision comparison

Oneactualmissingcomparefailure retained: owner/control/ratingchangesrequiredmanualJSONcomparison. Tenant-scoped revisioncompare computesadded/removedrisks andchangedfields/beforeafterpriorities, HTTP404unknownrevision/422badinputs.78runtimepass1warning; recorded87adjacent2457pass2warnings (exacttimeinlog). Reviewdiffnotapproval/evidenceverification. No visualUIorproductionacceptanceclaimed. Latestfull10022source69d6262 predateseightcodefixes.

## Runtime tool selector dispatch-history integration

The missing integration canary failed first: a persisted local tool failure did not change the prior score of 0.5. Runtime selection now rebuilds Beta(1,1) counts from distinct action IDs in the tenant repository. Repeated selection and runtime restart retain the failure mean of 1/3 without double counting. Evidence: 79 runtime tests passed with one warning; 2,458 adjacent tests passed with two warnings in 48.83 seconds.

Additional acceptance runs real local fixture handlers (two successful returns and one exception), persists their dispatcher records, closes the file-backed SQLite engine, and reopens it. Selection retains counts 2/1 and posterior mean 0.6 without running any handler again. This test passed on its first run; it is additional evidence, not another reproduced defect. 80 runtime tests passed with one warning.

These are reported local handler outcomes, not independently verified external outcomes or calibrated predictions. History is keyed by unversioned tool names; tool-version changes and drift are not handled. Counts in the score schema keep their existing supplied_successes/supplied_failures names for compatibility, with the history source identified separately. The full 10,022-test run remains historical at source 69d6262 and predates nine code changes.

## Evidence-backed runtime retrospectives

Two canaries failed first: closing a task had no structured action outcome report, and an unexecuted task claimed "goal accepted" under went_well. Close now includes a persisted report with final task state, step-state counts, per-tool local success/failure counts, action IDs, and last recorded failure text. Failed action diagnostics supplement trace-derived prose; an empty cancelled task no longer claims success. Old retrospect payloads load with an empty report for compatibility; existing retrospectives are not retroactively rebuilt.

Evidence: 82 runtime tests passed with one warning; 2,461 adjacent tests passed with two warnings in 51.95 seconds. The acceptance invokes real local fixture handlers, retains successful data containing the word "error" as success, records an actual exception, and checks idempotent close and runtime restart. This is a reported local execution summary, not independent external outcome verification, causal diagnosis, automatic repair, or verified reusable learning. Trace-based lessons remain heuristics. Latest full 10,022-test source 69d6262 predates ten code changes.

## Full regression after workflow build-outs

Current source 857b51f was checked across all 496 test files in 20 isolated batches: 10,048 passed, zero failed, 14 skipped, 26 summed warning occurrences, 436.13 seconds summed batch-process time. Every batch exited zero. Manifest and outputs are retained in audits/rebuild-20261007/full-regression-after-workflow-buildouts. This replaces the older 10,022 count as current local test evidence, not evidence of general cognition, production readiness, independently verified external effects, or model ideation quality. The actual pinned local ideation trial remains zero accepted out of two.

## Individual risk control revision workflow

A failing HTTP canary exposed the missing single-risk update workflow. A tenant-scoped PATCH can now update selected control/rating fields on one risk without resubmitting other risks. The risk ID cannot change, validation remains the same as full revision, and the expected revision uses the existing atomic compare-and-swap commit. Stale review returns 409; unknown risk/register returns 404; unsupported or empty changes return 422. Every accepted patch creates the same retained history revision as a full edit.

Evidence: 83 runtime tests passed with one warning; 2,462 adjacent tests passed with two warnings. No owner identity verification, notifications, scheduling, evidence inspection, or approval is added. The full 10,048 run at source 857b51f predates this one code change. This is a backend editing workflow, not a deployed visual UI.

## Review lessons connected to later planning

A failing captured-planner canary showed persisted retrospective lessons never entered later planning. Runtime planning now retrieves up to three similar retrospectives and up to three bounded lesson excerpts from each. Each excerpt is a hypothesis with confidence zero, labeled an unverified review suggestion and linked to its retrospective ID. Repeated retrieval avoids duplicate excerpts; the working-memory task partition is retained. Both immediate and prepared-plan paths use this context.

Evidence: 85 runtime tests passed with one warning; 2,464 adjacent tests passed with two warnings. This is fixture-tested retrieval and planner-context integration, not demonstrated model improvement, autonomous skill learning, verified advice, or authority for any effect. Similarity is the existing lexical/deterministic embedding ranking, not relevance probability. Existing planner review and tool approval boundaries are unchanged. Full 10,048 at source 857b51f predates two code changes.

## Supplied text context for durable runtime tasks

A missing-route canary failed first. Runtime tasks now accept bounded text with a caller-supplied source label and reference. A deterministic tenant/task/source/reference chunk ID makes replay idempotent while the chunk is retained; a changed body under the same retained reference returns 409. Text is persisted in the task working-memory partition, labeled unverified supplied context, and given hypothesis type and confidence zero. A captured planner receives it after restart. Closed tasks reject new context; unknown or other-tenant tasks are not accessible.

Evidence: 87 runtime tests passed with one warning; adjacent regression before the final additional restart/tenant test had 2,465 passed with two warnings in 45.87 seconds. This is bounded text/planning integration, not source authentication, multimodal ingestion, verified facts, semantic evidence matching, or model usefulness acceptance. Deduplication lasts only while the working-memory chunk is retained; pruning permits re-ingestion. Cross-process concurrent submissions are not an atomic conflict protocol. No production deployment is claimed. Full 10,048 at source 857b51f predates three code changes.

## Ongoing task importance/deadline editing

A failing HTTP canary exposed the missing schedule edit for existing runtime work. PATCH now updates importance (exact integer 1..5) and/or deadline, persists before changing the in-process scheduler, and supports explicit deadline clearing. Update deadlines require an explicit timezone and are normalized to UTC. Unknown tasks return 404 and closed tasks 409. This changes local runtime service order, not any real calendar or notification.

Evidence: 89 runtime tests passed with one warning. The adjacent regression before an added failed-save rollback test had 2,467 passed with two warnings in 49.70 seconds. Restart preserves importance/deadline and scheduling order. A failed repository save leaves the in-process task importance unchanged. Cross-process task edits still lack revision CAS, and no distributed scheduler or deadline guarantee is claimed. Full 10,048 at source 857b51f predates four code changes.

## Retained task execution evidence readback

A missing HTTP endpoint canary failed first. Durable runtime tasks now expose the newest retained action and trace records, each independently bounded to 1..100 rows at the database query, with total counts and truncation flags. Restart reads the same persisted evidence; unknown and other-tenant tasks return not found. Returned records retain timestamps, action IDs, local results, trace detail and policy labels.

Evidence: 91 runtime tests passed with one warning; 2,470 adjacent tests passed with two warnings in 48.05 seconds. These are reported local records, not authenticated external effects or independent verification. Counts and record reads are separate queries, so concurrent writers can change totals during readback. There is no pagination, export UI, or deployed acceptance. Full 10,048 at source 857b51f predates five code changes.

## Supplied DAG preparation without a planner model

A failing endpoint canary exposed the lack of an explicit-plan path for novel tasks with no model. Empty unexecuted tasks now accept a supplied DAG through the existing 1..128-step validation, with cycles and invalid dependencies rejected. Imported execution state, approval IDs and attempts are reset. Submission prepares and persists only; a later step call goes through normal tool dispatch and safety gating. Existing plans are not replaced and closed/executed tasks reject preparation.

Evidence: 93 runtime tests passed with one warning. Adjacent regression before the additional external-approval/restart test had 2,471 passed with two warnings in 45.27 seconds. Real local fixture handler runs only on a later step; an external-risk fixture stays waiting for fresh approval without calling its handler. This enables caller-authored plans, not autonomous planning or verified plan feasibility. Cross-process plan preparation lacks atomic revision CAS and production acceptance is absent. Full 10,048 at source 857b51f predates six code changes.

## Persisted structured results and dependent-step dataflow

A failing real local two-handler canary showed the runtime lost structured output and could not feed it to a dependent step. Dispatcher records and plan nodes now retain detached JSON object results up to 64,000 bytes, rejecting non-object, nonfinite or oversized output as failure. Explicit argument references use {"$step": "dependency-id", "path": ["field", 0]} to read a successful direct dependency's persisted output. Missing paths, missing output and non-dependency references block before handler execution. Resolved actual arguments still pass tool schema validation and safety review. Method instantiation remaps reference IDs and clears imported output.

Evidence: 99 runtime tests passed with one warning; 2,478 adjacent tests passed with two warnings (time in retained log). Real local fetch and sum handlers produce 42 across a between-step restart. An external-risk fixture receives an approval request for the resolved address without running; invalid paths block. These are local reported JSON results, not verified external artifacts or causal truth. There is no large-file result storage, streamed result support, model quality acceptance or deployed dataflow. Existing records load with result/output null; old truncated summaries are not parsed into evidence. Full 10,048 at source 857b51f predates seven code changes.

### Dataflow evidence correction

Commit 9585203 incorrectly stated green final counts after the shell continued past a failed supplemental test. Actual outputs at that commit were 98 passed / 1 failed and 2,477 passed / 1 failed. The test used nonexistent approval-request attributes instead of the actual payload field; no production code changed in this correction. Those failing outputs are retained as plan-dataflow-fixture-api-error*.log. After correcting the fixture assertion and rerunning with fail-fast: 99 runtime tests passed with one warning; 2,478 adjacent tests passed with two warnings in 49.38 seconds. The original dataflow implementation canary had already passed; this correction completes the supplemental safety evidence, not a new implementation fix.

## Plan capability and static-input preflight diagnostics

A failing endpoint canary showed no all-step preparation report. Runtime preflight now reports unknown tools, absent reasoning model, invalid static schema arguments, missing caller-supplied precondition flags, and effective risk for each plan step without dispatching or requesting approval. Output bindings are explicitly deferred until dependency output exists. Static checks passing never grants dispatch readiness or approval; normal execution must recheck actual resolved arguments and safety.

Evidence: 101 runtime tests passed with one warning. Adjacent regression before an added clean-static/no-grant test had 2,479 passed with two warnings in 46.75 seconds. No handler calls or approval requests occur during preflight. This is preparation diagnostics, not plan feasibility, authenticated preconditions, effect authority, or runtime availability guarantees. Supplied context flags are not stored or forwarded into dispatch. Full 10,048 at source 857b51f predates eight code changes.

## Real default offline CSV computation tool

A failing end-to-end canary showed the durable runtime registered no useful local handlers. It now registers csv_summary: supplied CSV parsing and grouped count/sum/mean/min/max over one numeric column. The tool rejects duplicate/empty headers, missing columns, malformed row width, nonnumeric/nonfinite values, overflow, more than 1,000 rows, more than 100 groups, or more than 64,000 input bytes. No network, account access or file mutation occurs.

Evidence: 109 runtime tests passed with one warning. Adjacent regression before added malformed-data/bounds tests had 2,481 passed with two warnings in 47.85 seconds. A caller-authored expense-style DAG with the default handler computes ops total 30 / mean 15 and sales total 5, retaining results in SQL with no model or fixture handler. This is useful bounded CSV arithmetic, not financial advice, unit/currency conversion, source verification or autonomous business analysis. Full 10,048 at source 857b51f predates nine code changes.

## Real default CSV export reconciliation

A failing default-handler canary showed no export reconciliation operation. csv_reconcile now parses two caller-supplied exports with unique nonempty keys and reports left-only/right-only keys, unchanged keys, and selected raw-string field changes. Each export is capped at 32,000 bytes and 500 records; at most 20 unique comparison columns are accepted. Malformed widths, duplicate headers/keys, blank keys and missing columns are rejected rather than silently merged.

Evidence: 115 runtime tests passed with one warning; 2,494 adjacent tests passed with two warnings in 51.90 seconds. An invoice-style plan runs the default handler and persists the exact differences. Numeric strings 1 and 1.0 remain different by design. This is exact supplied-data reconciliation, not authenticated invoice/payment truth, fuzzy entity matching, financial advice, numeric/currency normalization or any external mutation. Full 10,048 at source 857b51f predates ten code changes.

## Full regression after structured dataflow and default local tools

All 496 test files at source 539fda3 were checked in 20 isolated batches: 10,081 passed, zero failed, 14 skipped, 26 summed warning occurrences. Every batch exited zero; summed process time is recorded in the retained summary. Evidence is in audits/rebuild-20261007/full-regression-after-dataflow-tools. This includes the ten post-857b51f code changes and supersedes the historical 10,048 count as current local test evidence. It does not establish production deployment, general cognition, verified external effects, or successful model ideation; the pinned model trial remains zero accepted out of two.

## Real CSV filter-to-summary pipeline

A failing default-handler canary exposed the missing row selection step. csv_filter now supports exact raw-string AND predicates and column projection over supplied CSV, capped at 32,000 input bytes and 1,000 rows. Headers and selected/filter columns are validated; output uses CSV quoting. Empty matches retain the header and an explicit zero count.

Evidence: 117 runtime tests passed with one warning; 2,496 adjacent tests passed with two warnings in 49.97 seconds. The actual default filter handler selects open rows, its structured CSV output persists, and after runtime restart the actual default summary handler consumes that output through a dependency binding to compute total 15. No injected handlers or model were needed. This is a bounded exact data pipeline, not authenticated invoice truth, inferred business rules, fuzzy filtering or external execution. Full 10,081 at source 539fda3 predates one code change.

## Durable runtime supervision review

A failing endpoint canary showed no durable operational work-state view. Runtime supervision now reads persisted task states, failed/blocked/waiting tasks and their unfinished steps, and local action/failure totals. It reports healthy as null rather than inferring system health from code availability. Restart returns the same task-state counts. This is a local work review API, not live production health, worker heartbeat, external outcome verification or an alert service.

Evidence: 118 runtime tests passed with one warning; 2,497 adjacent tests passed with two warnings in 51.25 seconds. Unknown-handler work appears failed rather than healthy or complete. Reads are not one atomic cross-table snapshot and currently load all tenant tasks/action payloads; large-history scaling remains unfinished. The legacy service's unconditional health flag remains separate and must not be read as production verification. Full 10,081 at source 539fda3 predates two code changes.

## Dispatch outcome counting without journal payload reload

Two failing canaries exposed the missing aggregate path: runtime selection loaded every retained action payload, and no tenant-scoped count query existed. Tool selection now rebuilds counts from a grouped SQL query over reported outcome fields; supervision totals use the same aggregate. Large result payloads are not materialized into Python during either count operation. Local SQLite tests cover exact success/failure counts and tenant separation.

Evidence: 120 runtime tests passed with one warning; 2,499 adjacent tests passed with two warnings in 49.07 seconds. This changes data access, not score calibration or independent evidence status. Database work still scans tenant action rows and startup still hydrates the full journal; no indexed count cache or PostgreSQL live acceptance is claimed. Full 10,081 at source 539fda3 predates three code changes.

## Task-scoped action history instead of startup journal hydration

A failing restart canary showed runtime initialization loaded all tenant action payloads. Startup now begins with an empty process-local dispatcher record buffer. Episode completion reads that task's retained actions and merges current-run records by ID, preserving pre-restart work without duplicate action entries.

Evidence: 121 runtime tests passed with one warning; 2,500 adjacent tests passed with two warnings in 48.88 seconds. The actual default filter-to-summary pipeline resumes with no global action read and its final episode includes both handlers. This removes one unbounded startup payload load, not all scaling limits: task/memory hydration, current-process action buffers and long single-task episode history still grow. SQL action history remains retained; no archival policy or distributed exactly-once guarantee is claimed. Full 10,081 at source 539fda3 predates four code changes.

## Persisted action buffer draining

Two failing canaries showed successfully saved action payloads accumulated in the process buffer. Runtime flush now drains only the committed prefix, including when a later save fails. Unsaved records remain for retry; SQL history is not deleted. Ten actual default-summary tasks retain their result and one-action episodes without a growing dispatcher buffer. Partial write failure and retry retains exactly three SQL records with no duplicate inserts.

Evidence: 123 runtime tests passed with one warning; 2,502 adjacent tests passed with two warnings. This bounds the post-flush action buffer, not all memory or crash behavior. During one long run before flush, records still accumulate; trace/task/memory stores still grow. No concurrent runtime dispatch locking or exactly-once effect guarantee is added. Full 10,081 at source 539fda3 predates five code changes.

## Runtime tool discovery and executable local walkthrough

A failing endpoint canary exposed no registered-tool discovery route. GET runtime/tools now returns the actual handler descriptions, risk, preconditions and input schemas without granting approval or claiming external availability. A supplemental fixture assertion was corrected because the mounted test runtime also registers a web_search fixture; its failed output is retained, and the catalog intentionally includes every registered handler.

Evidence: 124 runtime tests passed with one warning; 2,503 adjacent tests passed with two warnings. A separate executable walkthrough with retained actual JSON output uses temporary file SQLite, real default filter and summary, engine reopen, structured dependency bindings, evidence readback and retrospective. Computed total is 15. No model or injected handler is used. The walkthrough documents its narrow scope and no external effects. Full 10,081 at source 539fda3 predates six code changes.

## Concrete temporal contradiction witnesses

Two failing canaries showed temporal difference-constraint inconsistency returned no conflicting input bounds. The solver now recovers and validates an actual negative cycle, reporting input constraint indices, edge directions, lower/upper-bound origin and negative summed upper bound. Unrelated constraints are not included in the tested three-bound contradiction. The witness is explicitly not claimed to be a minimal conflict set. Consistent networks return a null conflict witness.

Evidence: eight focused temporal tests passed; 2,505 adjacent tests passed with two warnings in 48.97 seconds before an added disconnected self-conflict test. This is finite relative-time constraint reasoning over supplied bounds, not calendar scheduling, actual temporal evidence verification or a causal explanation. Numerical overflow or a witness unavailable at the stated tolerance rejects instead of inventing a conflict. Full 10,081 at source 539fda3 predates seven code changes and the new test file.

## Default temporal constraint checker in execution plans

A failing no-model plan canary exposed no registered temporal reasoning handler. temporal_check now exposes the actual finite difference-constraint solver as a default read-only tool with bounded input schema and persisted structured output. Supplied timing contradictions retain their concrete negative-cycle witness in the action journal and plan output. Successful checker execution does not mean the supplied schedule is feasible; the output status separately says inconsistent.

Evidence: 133 focused runtime/temporal tests passed with one warning; 2,507 adjacent tests passed with two warnings. The acceptance uses the actual default solver, no model or injected handler. This is relative scalar time in a caller-declared unit, not absolute dates, calendar booking, observed timing verification or production scheduling. Full 10,081 at source 539fda3 predates eight code changes and the new temporal conflict test file.

## Explicit dependency output conditions

A failing actual temporal-check pipeline showed execution success alone cannot decide whether a checker result permits later work. The default require_value tool now compares resolved actual and expected JSON exactly, with a 16,000-byte cap, rejecting mismatches. A failed prerequisite leaves its dependents unexecuted. The caller must place the condition in the DAG; there is no implicit interpretation of every tool result. Plan max_attempts still controls retries; use one for a non-retryable prerequisite check.

Evidence: 127 runtime tests passed with one warning; 2,509 adjacent tests passed with two warnings in 54.85 seconds. The actual temporal solver returns inconsistent, its check node succeeds, the explicit condition fails, and later CSV work is never dispatched. Exact JSON comparison distinguishes true from 1 and numeric serialization 1 from 1.0; it is not truthiness, semantic equivalence, source verification or action approval. Full 10,081 at source 539fda3 predates nine code changes and the new temporal conflict test file.

## Full regression after reasoning workflows, with retained flaky failure

All 497 test files at source c5815ed were checked in 20 isolated batches. The initial result was 10,095 passed, one failed, 14 skipped, 26 summed warning occurrences, 490.56 seconds summed batch time. The one failure was M22 test_real_sandbox_timeout_is_enforced: the job failed but timed_out was false. The exact test passed immediately on recheck, and the full affected batch passed on recheck. No M22/M4 source was changed and the first failure remains retained.

Using the successful batch-15 recheck alongside the other original batches gives 10,096 passed, zero failed, 14 skipped, 26 summed warning occurrences, 490.95 seconds summed batch time. This is not a clean first-attempt full green run. The timeout assertion's timing sensitivity remains unresolved; a CPU-limit-versus-wall-time explanation is only a hypothesis. Manifest, both batch outputs, exact-test recheck and summary are in audits/rebuild-20261007/full-regression-after-reasoning-workflows. This is local test evidence, not production/cognition/model quality acceptance.
