# LEARN-ANALOGY836-CASE837

Candidate SCOPED, no general semantic analogy/case learning. Minimal legacy
payloads refuse analogy_source_features/case_feature_weights. No scaffold path.

836requires1..64 symbolic source/target feature text maps and0..64 explicit
correspondences. Unknown references/duplicate source mappings refuse. Missing
source/target mappings and many-to-one targets are reported; complete means total
bijective coverage, not discovered semantic correspondence.0..64 sourced target
allowed-value constraints and0..256 sourced candidate inferences are checked.
An inference supports only if mapping is complete, value matches its supplied
source feature, target has constraints, and all those constraints allow it.
Target feature observation equality is not required: constraints, not copied target
values, define permissible inferred candidates. No constraint means unsupported,
never fabricated permission. All sources supplied, not fetched/verified.

837requires1..64 positive finite weighted feature labels, exact target feature
schema and1..256 sourced cases with exact same schema and supplied proposed_action.
Ranking is weighted exact matches divided by total weight, ties by case ID.
Action reuse requires an explicit selected known case plus1..64 unique sourced
boolean target checks. No checks means waiting; any failed check blocks reuse.
A caller may select a non-top-ranked case explicitly. Reused action is exactly the
supplied case action, not invented transformation; checks are caller records, not
independently executed verifications. No retention/revision of the case bank,
persistence or external effects. action_executed=False/source_truth_verified=False.

Text bounded240chars, duplicate IDs/shapes/refs refuse. Existing mounted
401/422/403auth/owner/tenant checks. Synthetic partial/many-to-one maps, constraints,
wrong/missing inference support, rankings/ties, checked/failed reuse and auth are
tested. Residual: supplied symbolic maps/features/checks only, no NL extraction,
semantic correctness, novel adaptation, general learning or verified truth.
