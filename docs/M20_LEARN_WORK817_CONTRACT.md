# LEARN-WORK817-818: exact rational register tasks

Candidate SCOPED unit; no general reasoning or educational-effectiveness claim.
Minimal existing method payloads now refuse with arithmetic_task object error.
No static worked-example/problem-cycle scaffold fallback remains.

A task is a single rational register with initial/goal, explicit1..8 sourced
operations (add, subtract, multiply, divide by nonzero rational), maximum depth
integer0..8, and positive absolute state bound<=1e6. Numeric inputs are integers
(not bool) or rational strings<=64chars. Rational numerator/denominator components
are bounded by1e12; initial and goal must lie within state bounds. Intermediate
search values outside these bounds are skipped, so no-solution means only within
the declared grammar/bounds. No expression parser/eval, floats, hidden model or
external retrieval is involved.

Worked trace records sourced pre-state, operation ID, post-state and structured
rationale apply:<operationkind>. The verifier computes the exact rational post
from the current accepted state. Every step must have matching pre/post/rationale
and fit bounds; rejected steps do not update state. A trace passes only if all
steps pass and the final accepted state equals the goal. Rationale validation is
operation-label checking, not semantic interpretation of explanatory prose.

A completion task, if supplied, is grammar-validated even after invalid work, but
is emitted only after a valid goal-reaching worked trace and successful bounded
search proving that the completion goal is reachable. No solution is exposed for
that completion problem; unsuccessful search exposes its bounded status. No
completion task is invented from a template.

Problem solving performs breadth-first search, operations ordered by ID and
visited exact-rational state deduplication. It returns a shortest trace within
the declared grammar/depth/state/component bounds, or no_solution_within_bounds.
A10000distinct-state budget yields search_budget_exhausted, not an impossibility
proof. Supplied-source IDs and generated operation rationale labels are retained;
solver-generated steps identify operation_source, never fabricated learner
attempt provenance. Equal initial/goal returns a valid zero-step solution.

Mounted existing authenticated method routes inherit owner tenant binding,
401/422 and403cross-tenant rejection. Outputs source_truth_verified=False,
learner_understanding=None. Synthetic exact arithmetic, shortest traces, wrong
pre/post/rationale/operations, unreachable/depth/state bounds, completion gating
and invalid grammar are tested. No persistent state, general problem solving,
learner assessment, scheduling, effect or independent truth verification.
