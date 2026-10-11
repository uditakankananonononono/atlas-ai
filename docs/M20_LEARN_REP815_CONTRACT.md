# LEARN-REP815-816: symbolic representation/example packs

Candidate SCOPED rebuild of rows815/816 for independent acceptance. Existing
methods now require structured concepts, not just verbal/visual labels or
copied examples; minimal payloads refuse with a concepts error. No scaffold
fallback or image understanding/generation is claimed.

A pack has1..64 provenance-bound concepts, each1..32 text-valued invariant
features. This is a caller-declared symbolic classification, not a discovered
concept definition. Dual coding validates0..64 verbal propositions and0..64
visual elements against concept IDs. Verbal text and visual alt text/accessibility
labels are mandatory and bounded; these strings are not semantically interpreted.
At most256 explicit mappings connect known verbal/visual IDs in the same concept.
For each pair the operator computes missing invariant features and disagreements
between representations or the concept's invariant values. Concept coverage and
unmapped representation IDs are computed. A pair must have all invariant values
correct; every representation must be mapped and every concept must have both
modes before the pack is valid. Wrong values/missing coverage produce a gap report,
not fabricated success. Unknown references/duplicate IDs/invalid shapes refuse.

Concrete examples validate1..256 provenance-bound example/counterexample records
against the same concept invariant map. All invariant features must be present;
a positive example must satisfy all, while a counterexample must violate at least
one. Variant features are explicitly declared, present, unique, and cannot be
invariant keys. This checks declarations, not natural-language or pixel content.
Every concept needs at least one valid positive and one valid counterexample for
coverage_complete; any invalid item makes the pack invalid. Boundary means an
explicit supplied counterexample, not a mathematically nearest boundary search.

Outputs retain concepts and definition sources, mapped IDs, accessibility labels,
verbal/source references and example/source results. Source truth verification is
false and learning improvement is None. Ordering is deterministic except example
reports deliberately retain caller order. Existing mounted authenticated routes
inherit owner tenant binding; unauthenticated401, invalid422, cross-tenant403.
No persistent state, external retrieval, generated images, scheduling or effects.
Synthetic tests verify conflict/missing coverage, invariant violations, roles,
variants, invalid references and mounted auth. Residual: supplied symbolic
mappings/invariants only; no semantic correctness, actual visual accessibility
audit, multimodal cognition or evidence of learning improvement.
