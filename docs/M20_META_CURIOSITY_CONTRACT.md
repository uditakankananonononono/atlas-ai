# META-CURIOSITY: supplied local corpus investigation

Row34 candidate for independent SCOPED acceptance. This additive opt-in
operator does not convert legacy lexical frequency into learning value.

An authenticated caller explicitly authorizes an immutable supplied local
corpus and total budget. Each source holds an ID, provenance and an exact-key
answer map. Authorization requires literal true, 1..32 sources, at most1000
answers/source and a finite budget in (0,1000]. No network address is fetched,
no external service is called, no model host is used and no external side effect
is performed. This API flag authorizes only this local corpus workflow, never
external effects or arbitrary retrieval. Reauthorizing/resetting consumed
budget is refused; a separate new operator state needs separate authorization.

Explicit question records link question text, lookup key, allowlisted source
IDs, supplied binary prior probability, decision relevance and cost. The
priority rubric is binary Shannon entropy times relevance divided by cost.
Frequency is recorded but does not drive priority. Expected learning value
remains None: this score is a declared uncertainty/relevance/cost proxy, not a
prediction that a source will answer or a measure of intrinsic learning value.
Question semantics and supplied probabilities/relevance are not inferred or
verified. No vector/semantic search or open-ended question answering is claimed.

Run executes ranked exact-key lookups in the authorized corpus, within both
per-run max_cost and remaining total budget. An unaffordable question is skipped
so a cheaper question can run. Zero-priority questions do not run. Each lookup
cost is a caller-defined accounting unit for the entire listed-source lookup,
not a real monetary charge or measured CPU token cost. Answers matching across
sources narrow the recorded gap; distinct answers yield conflicting_sources
with no chosen answer, and no matches yield no_answer. Missing answers in one
source do not veto an answer in another. All attempts retain source IDs,
provenance, lookup key, returned answer or None and cost. Results are persisted;
no-answer/conflict attempts are not automatically retried. Gap narrowing means
only this corpus returned one distinct answer, not real-world truth.

At most1000 questions,1000/batch. Exact duplicate records are idempotent even
after resolution and do not advance CAS; changed identities or disallowed
sources refuse atomically. Ordering is descending priority then question ID.
META-DUR tenant/kind snapshots commit before memory publication; stale writers
and rollback leave state unchanged. SQLite restart/isolation is tested, not
production deployment/PostgreSQL. Mounted authenticated
/api/v1/api/modules/20/curiosity-investigator routes require explicit binding;
unbound503, invalid422, stale409. Private corpus values are never sent elsewhere.

Synthetic acceptance compares known controlled question choices against
frequency-only ranking, verifies actual lookup answer/no-answer/conflict,
provenance, budgets, duplicate suppression, disallowed sources, entropy edges,
restart, rollback and tenant authentication. Residual: rubric/corpus/test-domain
only; no autonomous curiosity, discovered gaps, external investigation,
independent truth verification or guaranteed learning.
