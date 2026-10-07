# Peer-derived provider/core uncertainty adaptation

Reviewed actual peer prerequisite commits dd3ca6b2db and 78f0be856b against our adapted providers.py/model_catalog.py/shared_model_layer.py. Not literal cherry-pick/API parity: peer exposes generate_result and richer usage objects; our existing generate tuple API and surrounding model policy remain. Unknown exception type is additive.

Contract retained: one generation POST per invoked attempt, no reliability retries after dispatch, typed unknown for transport/status/unusable generation response, no free-first fallback after unknown. Pre-dispatch missing credentials/configuration and open-circuit unavailability can fall through. Private/public route eligibility and paid opt-in remain unchanged. Shared generation guards invoked routes, skips the tool-only Needle route, and preserves SharedModelError compatibility for existing callers. Default general shared router callers remain unchanged.

Known conservative boundary: HTTP status failures including 402 and connection failures are treated as unknown once the generation call is attempted; this may stop fallback even when the remote rejected before generating. It prevents hidden duplicate attempts but does not prove a billable effect occurred. Arbitrary custom adapter exceptions and usage parsing are not fully typed by this narrow adaptation. No production spend/effect verification or automatic cross-request reconciliation claim.

Existing mocked transport and actual local HTTP/shared-router canaries plus catalog/layer policy tests retained in selected.log. This is a scoped semantic assessment, not live-provider availability/usage or production verification. PostgreSQL and migration-history collision gates remain unchanged.
