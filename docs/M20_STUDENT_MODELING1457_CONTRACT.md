# Row1457 Student Modeling

Ledger source pin: audits/additional-2000-features.json, id1457, requirement "Student Modeling", description "". The description is empty: the title is the whole requirement text. This contract proposes the exact bounded behavior below, rather than attributing it to a longer requirement. Base dcab66a2ea4303ea2c763074ef272f3e0cbe17e3, verified from GitHub origin main. PREP-only local candidate; independent review pending, no closure/landing claim.

## Existing mechanism and additive delta

backend/app/modules/m20_general_cognitive_worker/education.py:203-218 already computes sequential Bayesian knowledge tracing with prior_mastery, learn_rate, slip and guess; it labels caller/partial/default parameter source, fitted_to_data:false, learner_mastery_verified:false. Line215 keeps prior on zero likelihood; line281 aggregates mean modeled mastery. This is real conditional arithmetic, not merely a template. The cited row-card line281 is the aggregate, not the full update mechanism.

New file student_modeling1457.py adds a strict supplied-parameter per-step trace audit, explicit evidence/event IDs, per-group ordering, zero-likelihood refusals and bounded schema validation. It does not change education.py, its tests, routes, registry, ledger or policy. No claim of inventing BKT or fitting parameters. Hermetic standard-library implementation.

## Proposed exact behavior

run(request) takes exactly parameters and events. Parameters exactly prior_mastery, learn_rate, slip, guess, all builtin int/float excluding bool, finite within[0,1]. No defaults. Events list max1024; each exactly event_id,learner_id,skill,correct. Identifiers nonblank strings<=120 characters, no control characters; learner_id is caller-declared pseudonymous ID, never verified identity. Event IDs globally unique. Correct must be explicit bool. Distinct learner/skill pairs max128. Input sequence is authoritative within each pair; no timestamp inference, sorting or deduplication of observations. Empty events valid: no states, not fabricated learners.

For each event, p is group's prior modeled probability (initial caller prior on first event). Correct likelihood=p*(1-slip)+(1-p)*guess; incorrect likelihood=p*slip+(1-p)*(1-guess). Posterior=p*(1-slip)/likelihood if correct, else p*slip/likelihood. Post-learning probability=posterior+(1-posterior)*learn_rate. Exact zero likelihood refuses whole request as impossible under supplied parameters, never invents evidence. Internal arithmetic stays unrounded; reported numeric fields round six places. No forgetting parameter or event weighting.

Output: sorted dict with row_id1457, parameters, parameter_source caller, traces in supplied event order, states sorted learner_id/skill, status conditional_unfitted_model_calculation, fitted_to_data false, learner_mastery_verified false, educator_review_required true, and scope. Trace includes event_id,learner_id,skill,correct,step (within pair starting1),prior,likelihood,posterior,post_learning. State includes learner_id,skill,event_ids in sequence,attempts,modeled_probability. No grades, labels of ability, traits, ranks or intervention/advice actions. Same input gives deterministic JSON; no wall-clock, no input mutation, no side effects.

## Exact row-tagged refusals

ValueError strings start STUDEN1457:, no success-like error result:

- BAD_TYPE:<path>: wrong container/numeric/bool/text type, blank/control identifiers or out-of-range probabilities.
- UNKNOWN:<path>: extra key.
- MISSING:<path>: required key absent.
- DUPLICATE:event_id: repeated event ID.
- OVERSIZE:events / OVERSIZE:pairs / OVERSIZE:<identifier field>: exceeds1024 /128 /120 inclusive caps.
- IMPOSSIBLE:<event_id>: likelihood exactly zero.

No source content establishes learner consent or verified correctness; inputs are declarations. No persistence or disclosure: callers must establish consent, access rights, minimization and educator/learner review for their use. Input identifiers need not name real students. New unit has only run as public callable and no spend/send/post/account/trade/scrape paths. No host wiring or mutation of live student records.

## Verification plan

Contract-first, missing-target RED before implementation, independent sequential arithmetic oracle, order sensitivity, group independence, probabilities at boundaries, impossible observations, correct bool typing, schema/refusal text, N/N+1 input/identifier/pair pins, no input mutation and deterministic outputs. Hand-authored one-change mutation sample records ASSERT/ERROR/TIMEOUT/NONCOMPILE/SURVIVED separately, every survivor disposition retained. FULL-SUITE UNVERIFIED: full repository suite not run. Local unit results are builder evidence, not independent acceptance.

## Builder evidence

Builder evidence addendum: contract-first build start actual clock18:12:42 IST (earlier rounded18:12:46 note corrected). Adds to existing education.py arithmetic and does not replace it. Missing-target RED18:13:31, first GREEN18:13:44:10 tests, Python3.10.12. One-change sample26 variants:21 ASSERT,3 ERROR,1 NONCOMPILE,1 SURVIVED,0 TIMEOUT. m08 removed zero-likelihood guard produces division ERROR; m09/m11 off-by-one caps produce boundary-test ERROR, not assertion kills. m26 deliberate incomplete expression is NONCOMPILE, not semantic kill. m21 removed finite check SURVIVED: equivalent over builtin numeric accepted domain because[0,1] comparison rejects NaN/infinity/huge integers before float conversion; retained original finite check and survivor classification. Raw output preserved, no zero-survivor claim. FULL-SUITE UNVERIFIED: only the new unit suite was run. No independent audit/landing claim.

## Limits

Conditional unfitted arithmetic, not actual mastery, learning efficacy, diagnosis, hidden-trait inference, prediction validation, manipulation or educational advice. Parameters and outcomes caller supplied, not validated/fitted to learners. No high-stakes education decision, grading, credentialing, recommendation, educator replacement or irreversible action. No forgetting, skill transfer, missing-data correction, calibration or efficacy claim. Qualified educator and affected learner must review assumptions, consent, accessibility, fairness and any downstream interpretation. PREP only; no push, effects or closure claim.
