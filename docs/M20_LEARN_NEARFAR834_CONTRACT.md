# LEARN-NEARFAR834-835: declared feature similarity rubric

Candidate SCOPED; both method names now run the same declared rubric rather than
forcing their names as the answer. Minimal legacy source/target feature-list
payloads refuse transfer_schema. Existing source_case/target_case fields unused.

A schema has1..64 unique sourced feature IDs with finite weight(0,1000]. Source
and target dictionaries cover exactly those feature IDs, with bounded240char text
values. Similarity is sum of weights for exact matching values divided by total
weight. Finite threshold[0,1] makes near when similarity>=threshold, far otherwise.
Feature agreement/difference reports retain values, weights and sources. The
requested method name is retained separately. No natural-language similarity,
latent distance, semantic normalization or empirically learned thresholds.

A supplied sourced target task has1..64 unique accepted exact text answers.
Without a response, similarity/classification remain available but performance
abstains awaiting_independent_target_response and no transfer evidence is recorded.
An explicit independent=True response with ID/source/text is checked by exact
answer membership. Near classification never implies correct performance; far
can score correctly. Independence is a caller declaration, not verified behavior.
Both successes/failures return scored evidence, not a persisted learning log.

All sources/keys are supplied references, truth unverified, general_transfer=None.
No effects, retrieval, models, persistence or scheduling. Existing mounted
401/422/403auth/owner/tenant checks apply. Synthetic weights/threshold equality,
far-success/near-failure, missing response, typed grammar and auth are tested.
Residual: caller-defined finite feature rubric and exact-key task only, not
semantic/general transfer, learned distance or demonstrated educational effect.
