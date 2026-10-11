# LEARN-ACTIVATE832-TRANSFER833

Candidate SCOPED unit. Minimal old832/833payloads now refuse with
activation_concepts/transfer_rule; no copied activation/bridge prompt fallback.

832requires1..64 sourced concept records, each1..64 accepted symbolic values.
Up to1000 prior responses and1000 new evidence records reference known concepts
with unique IDs and bounded source/value text. Exact prior key match returns
matches_supplied_key; mismatch is a misconception candidate, never grade or
verified learner belief. New evidence remains separate, cannot overwrite prior
responses, and does not retrospectively grade them. Unactivated concepts mean no
prior responses, regardless of new evidence. Sources/keys are supplied, not fetched
or semantically assessed. Grades/understanding remain None, truth unverified.

833takes one sourced positive Horn rule with<=64 premises (effective max63
when the conclusion is distinct from all premises), target task with<=64
facts/query, and1..64 bijective correspondences covering exactly source rule atoms.
Truthy unless values refuse; absent or falsey unless values ([], empty string,
0, False) are ignored and represent no exception. Target query must equal mapped conclusion; no partial/extra/many-to-one mappings.
Entailment means the target conclusion is already a supplied fact or all mapped
premises are present. No source-case semantic abstraction or discovered mapping
is claimed. Supplied legacy source_case/target_case fields are not used by this
new engine. This is exact declared-rule adaptation, not general transfer.

Without a target_response it returns awaiting_independent_target_response with
correct=None/transfer_evidence_recorded=False. An explicitly declared independent
response with ID/source and boolean entailment is scored against the computed
expected answer. Independence is a caller declaration, not observed closed-book
behavior. Both correct and incorrect responses count as transfer evidence in the
returned result, not a persisted learning log; wrong responses are never wins.
No persistence, retrieval, effects or autonomous application. Existing mounted
auth401/422/403owner/tenant checks apply. Truth=False/general_transfer=None.
Synthetic known/missing premises, mapped queries, wrong/absent responses,
activation separation/mismatch, invalid maps and auth are tested. Residual:
supplied symbolic rule/keys only, not semantic activation, causal learning effects,
open-world skill transfer or proof of independent target performance.
