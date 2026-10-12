# execution classification and canonical dispatch delta

Landed series base: 14d4be2d. Original development/receipt base: 4ea55fae.
Offline classifier/enforcement repair, not provider integration.

Released selectors:

    PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest tests/runtime/test_approved_execution.py tests/modules/test_worker_outbound_gate.py tests/test_worker_execution.py tests/modules/test_m00_impact_preview.py tests/modules/test_m10_binding_dispatch.py -q

Effect classification is a fixed immutable mapping. Constructor overrides are refused,
and unknown action types fail closed, even with a target/executor registered. Only the
three explicit local ACTION_ALLOWLIST types at their fixed target modules/operations
can use the approval-only path. Reusing a local name on an effect module is refused. Existing
local worker fixtures now use prepare_goal_work instead of unknown fixture names.

The dispatcher deep-copies the execution read and authority binding. The digest covers
nested payload, authenticated dispatcher tenant/actor/correlation context, target module,
operation and approval evidence. Its effect reconstructs context/handoff from the gate's
canonical action, not a detached closure. The hook also rechecks approval module identity.
Worker effects likewise consume the canonical action rather than a stale view. Worker
ids longer than 64 characters are rejected, not silently truncated. A new test proves
rate history spans two tasks in the same process with the same service instance.

Limits: execution-time binding detects read-to-hook drift, NOT edits since owner review.
It is not an owner-reviewed digest or independent authentication of the M00 approver.
The worker tenant is still sourced from M00's view, not an independent authenticated
identity. Worker rate caches remain keyed by tenant/service-object identity and reset on
restart; separate processes/services can multiply budgets. Dispatcher ledgers remain
per dispatcher instance without durable/shared storage. No distributed rate or replay
claim. Arbitrary direct adapters outside these choke points remain out of scope. The
fixed local action classification assumes those exact local operations stay local; this
is not a 65-module runtime enforcement guarantee. M10 provider-conditional production
support is still unavailable; tests use an explicit fake conditional adapter.

Mutation receipts: run_mutations.py applies exact replacements and exact test selectors.
CAUGHT requires pytest rc=1 plus FAILED IDs, with collection/internal/fatal errors
screened and timeout uncredited. FAILED includes product KeyError/RuntimeError crashes,
not only assertion failures. Mixed FAILED plus SKIP is not rejected. These are
failure-sensitivity counts, not proof that every kill is a graceful refusal.
SURVIVED and INVALID are separate. Mutated files are restored and SHA-256 checked.

Historical original-development released-selector result: 134 passed (one FastAPI deprecation warning).
Final mutation result: CAUGHT=11, SURVIVED=0, INVALID=0, NOT-APPLICABLE=0;
SHA-256 restoration true. The initial shallow-copy mutant survived an insufficient
negative-only test; the final test checks preserved nested bytes and refusal of a
new digest too. The hook now requires both the bound digest and live-view digest.
