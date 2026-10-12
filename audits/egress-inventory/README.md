# Static binding inventory delta

Released selectors:

    PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest tests/runtime/guardrails/test_effect_bindings.py tests/runtime/guardrails/test_egress_coverage_ratchet.py -q

## Computed results and declared rules

| Item | Evidence type | Meaning |
|---|---|---|
| Module census total and GATED/EXEMPT-BY-DESIGN/UNGATED counts | Computed | AST/file scan results under the declared rules, not a certified complete census |
| Per-module status and snapshot | Computed | Classification output, not an independently verified runtime safety finding |
| EGRESS, WRITE_CALLS, GATE_CALLS and SOCKET_LOOKUP_ONLY | Declared | Library/call-name recognition rules defining the scan |
| GATED_CALLERS and GATED_WRITE_METHODS | Declared | Named caller/method and refusal-test bindings used by the computation |
| EXEMPT_REASONS, WRITE_CAPABLE_TRANSPORTS and REVIEWED_UNGATED | Declared | Named exemptions, transport overrides and reviewed-gap rationale, not computed behavioral proof |

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
Retained limits: call-name/package/library/import-form/scope, no domination/completeness.
Specifically, matching call names anywhere in a file does not establish receiver identity,
reachability or that a gate dominates every effect. Package-scoped publish searches omit
out-of-package callers; declared EGRESS omits unlisted libraries; import forms and aliases
can evade recognition. Scope is only backend/app Python files, excludes runtime/guardrails,
and drops SyntaxError files. Generic variable-method/bare-function writes beyond the
named transport override can be missed. No complete call graph or runtime census is proved.

Report provenance: VERIFIED covers "the validator computed this result", not artifact
goodness. M14's renderer creates provenance labels itself; direct renderer and alternate
README/export wiring are not fixed here. Existing injected-renderer refusal tests do
not prove all exports are gated. Claim-id truncation on those paths remains untested.

Mutation receipts use CAUGHT=pytest FAILED only, exclude collection errors/timeouts,
and check byte-exact source restoration by SHA-256.

Final computed inventory: 65 modules, GATED=10, EXEMPT-BY-DESIGN=26, UNGATED=29.
The earlier 64-module view predates the clicky addition: 4ea55fae includes
modules/c31/clicky.py as the extra UNGATED entry; the m01 transport reclassification
then moves one EXEMPT-BY-DESIGN entry to UNGATED (not unexplained count drift).
Historical original-development full guardrails selector: `python -m pytest tests/runtime/guardrails -q` -> 243 passed.
Historical original-development released-selector result: 16 passed. Final mutation result: CAUGHT=6, SURVIVED=0,
INVALID=0, NOT-APPLICABLE=0; SHA-256 restoration true.

Clicky rationale follow-up: every REVIEWED_UNGATED key must exist in scan, baseline
and snapshot and remain UNGATED with its note present. The clicky-specific AST check
requires the real live guard with both conditions, its refusal, exact env flag, and the
single urllib Request in _fetch to remain GET with no data. Wording must still state
that it is a default-off guard, not M00 authority. The .submit hit is the executor's
ThreadPoolExecutor.submit, not a network send. Guard removal, GET-to-POST and prose
overclaim mutants all fail without relying on regenerated snapshot contents. This is
a narrow structural contract, not complete control-flow/provider behavior proof.

## Wording follow-up on 62d0481d

Documentation/output-label change only: removed the "never declared" overclaim and
identified computed results versus the declared rules producing them. No classifier
branches, policy tables, snapshot data or enforcement behavior changed. Historical
selector/mutation receipts above are retained as historical, not rerun claims.

## Selector scope and base reconciliation

The original-development receipts (4ea55fae plus the three deltas) are 134 for the
full execution selector, 27 for m06 scheduler/publish, 16 for inventory/ratchet,
243 for the guardrails directory, and 309 for guardrails plus
`tests/modules/test_c31_clicky_transport.py tests/modules/test_c31_clicky_a3.py`.
They are different selectors, not competing counts of the same suite. The series
was subsequently rebased, with label/path normalization only, onto 14d4be2d.
Other runs report 245 guardrails tests and 67 bounded execution/social tests; they use separate selectors or revisions, and no retained development receipt matches an exact 67-node selector, so that figure is not recorded here as a selector result.

Fresh follow-up checks on 62d0481d: the inventory/ratchet selector above is 16 passed;
`tests/runtime/guardrails` is 245 passed; the bounded selector
`tests/runtime/test_approved_execution.py tests/modules/test_worker_outbound_gate.py
tests/modules/test_m06_publish_guardrail.py tests/modules/test_m06_scheduler.py`
is 66 passed (one FastAPI warning). These fresh checks do not overwrite historical
receipts or imply those larger original selectors were rerun on this base.

## Inventory pytest node-id rename

Two names changed without assertion, policy or output changes:
`test_snapshot_matches_computation_and_prints_declared_counts` ->
`test_snapshot_matches_computation_and_prints_computed_counts`, and
`test_gated_status_is_computed_not_declared` ->
`test_gated_status_depends_on_declared_caller_evidence`.
File-level selectors are unchanged. External selectors/receipts naming the old node IDs
were not verified; consumers of those IDs must use the new names. This is wording
alignment, not an assertion or classifier repair.
