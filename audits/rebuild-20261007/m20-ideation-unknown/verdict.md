# Model-ideation uncertainty propagation

ModelIdeationEngine is an additive local surface, absent from the peer b944215 reflection implementation. It previously flattened the combined FreeFirstExecutiveModel's typed unknown outcome into ordinary unavailable RuntimeError and mounted HTTP 503. Retained original canary: 1 failed.

Correction preserves ProviderOutcomeUnknown when a returned response declares outcome unknown; mounted route returns HTTP 409 with outcome unknown and retry_allowed false. Ordinary unavailable remains 503, malformed model output remains 422, and no template fallback or automatic retry is added. Two dedicated canaries plus existing reflection/routes suite: 26 passed. Fresh full regression receipts are retained alongside this verdict.

This closes the response-type flattening path only. The service ideation API is not a durable runtime task, has no runtime restart/reentry hold or reconciliation workflow, and does not gain one from this correction. Repeated caller requests remain a caller-level boundary; no cross-request no-retry guarantee is claimed. Proposed model ideas, constraint checks and risks remain unverified; this is not evidence of usefulness or production clearance.
