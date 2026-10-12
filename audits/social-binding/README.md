# m06 canonical publish delta

Base: execution patch on 4ea55fae. Offline scheduler/adapter fakes, no platform calls.

Released selectors:

    PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest tests/modules/test_m06_publish_guardrail.py tests/modules/test_m06_scheduler.py -q

Every PublishRequest field (platform, text, format, link, media URLs, alt texts, thread
chunks) is now in the digest-bound action. The publish callback constructs its request
from the gate's canonical action. Tests compare the exact published request and ledger
digest and refuse mutation of every content field. A callback contract probe detects
using a detached entry/request instead of the canonical argument; it is not a real gate.
Explicit outbound_declarations={} means undeclared and denied, never default allow.

m06 social defaults declare instagram/twitter/tiktok/linkedin post, 25/day each.
These are caller policy declarations, NOT verified provider terms. They are distinct
from approved-execution/worker defaults (only Gmail send, 50/day). Social actions on the
worker require an explicit social declaration; m06 defaults do not apply to the worker.

Limits: approval status and execution-time digest are checked, but there is no persisted
owner-reviewed digest. Edits before execution binding are not detected. Per-scheduler
in-memory history resets when a scheduler is rebuilt (including worker-created scheduler
instances). No cross-worker budget, crash durability, independent approver authentication,
or live media/platform test. Adapter endpoint semantics remain outside this delta.

Mutation receipts use CAUGHT=pytest FAILED only; errors/timeouts are INVALID and source
restore is checked by SHA-256.

Released-selector result: 27 passed. Final mutation result: CAUGHT=4, SURVIVED=0,
INVALID=0, NOT-APPLICABLE=0; SHA-256 restoration true.
