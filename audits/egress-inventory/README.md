# static binding inventory delta

Released selectors:

    PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest tests/runtime/guardrails/test_effect_bindings.py tests/runtime/guardrails/test_egress_coverage_ratchet.py -q

The 65 imported-egress modules remain inventoried. m01/http.py is UNGATED because its
generic Request(method=method, data=payload) can POST, including the read-style search
queries in adapters.py. A public-read prefix does not make this generic transport safe.
m18/lane_http.py stays EXEMPT-BY-DESIGN: its urllib Request carries no data/method;
body= hits construct response records or fake responses, not outbound request bodies.

A dead guardrail import no longer earns GATED in the computed binding inventory: a gate
or refusal call must also be present. Package-scoped publish checks require at least one
non-self call site; an empty caller set cannot earn GATED. Snapshot regenerated only
from the computation, no CSV edits. clicky module wording now names the actual bounded,
default-off GET and does not claim it never performs network calls.

Limits: AST import/call-name and named-transport inventory, not call-graph or runtime
verification. Dynamic imports, aliases, helper indirection, out-of-package publish
callers and side-effecting GETs can escape. A gate call's presence does not prove it
executes on all effect paths. Named read exemptions are static judgments, not certified
provider behavior. Hard import ratchet is still a separate, coarser wiring metric.

Report provenance: VERIFIED covers "the validator computed this result", not artifact
goodness. M14's renderer creates provenance labels itself; direct renderer and alternate
README/export wiring are not fixed here. Existing injected-renderer refusal tests do
not prove all exports are gated. Claim-id truncation on those paths remains untested.

Mutation receipts use CAUGHT=pytest FAILED only, exclude collection errors/timeouts,
and check byte-exact source restoration by SHA-256.

Final computed inventory: 65 modules, GATED=10, EXEMPT-BY-DESIGN=26, UNGATED=29.
Full guardrails selector: `python -m pytest tests/runtime/guardrails -q` -> 243 passed.
Released-selector result: 16 passed. Final mutation result: CAUGHT=6, SURVIVED=0,
INVALID=0, NOT-APPLICABLE=0; SHA-256 restoration true.

Clicky rationale follow-up: every REVIEWED_UNGATED key must exist in scan, baseline
and snapshot and remain UNGATED with its note present. The clicky-specific AST check
requires the real live guard with both conditions, its refusal, exact env flag, and the
single urllib Request in _fetch to remain GET with no data. Wording must still state
that it is a default-off guard, not M00 authority. The .submit hit is the executor's
ThreadPoolExecutor.submit, not a network send. Guard removal, GET-to-POST and prose
overclaim mutants all fail without relying on regenerated snapshot contents. This is
a narrow structural contract, not complete control-flow/provider behavior proof.
