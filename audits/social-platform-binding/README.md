# Social adapter and canonical platform binding

Development base: fc71886b; patch rebased and receipts rerun on 81145546. Moves adapter-factory selection from the pre-admission
entry view into the admitted callback. Factory Platform and PublishRequest.platform
are both read from the same canonical action. No factory call occurs on platform-drift
refusal. This closes the earlier untested stale-entry/canonical-platform divergence.

Released selector:

    PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest tests/modules/test_m06_publish_guardrail.py tests/modules/test_m06_scheduler.py -q

Result: 29 passed. The real default gate test changes platform after execution binding
and requires authority_rejected with zero factory and publish calls. A separate custom-
gate contract probe changes Twitter to LinkedIn and compares factory selection to the
actual published request platform. The probe is not a real authority admission: the
default hook would refuse that digest change. It specifically proves callback wiring.

Four exact replacement mutants: stale entry factory platform, fixed Twitter factory,
detached request platform, and premature factory call. CAUGHT=4, SURVIVED=0, INVALID=0,
NOT-APPLICABLE=0; byte-exact SHA-256 source restoration true. Full FAILED node ids are
retained in mutation_receipts.txt. CAUGHT requires rc=1 and FAILED ids, with collection/
internal/fatal errors screened and timeout uncredited. FAILED may include product
KeyError/RuntimeError exceptions; mixed FAILED plus SKIP is not rejected. These are
selected-test failure-sensitivity counts, not comprehensive coverage.

Limits: trusts the factory to return the adapter for its requested Platform; does not
certify the adapter endpoint/account or provider terms. Custom enforcers remain caller-
trusted and can bypass real authority/policy admission. Post-admission factory failure
may consume rate budget and is not atomic rollback. Media compliance is checked on the
entry before the gate; this callback patch does not give custom gates permission to
change platform/content or certify their media checks. Execution-time digest is not an
owner-reviewed digest. Per-scheduler ledgers remain in memory, no cross-process durable
rate proof. No live platform/API call, approval-time binding or deployment proof.
Historical S2/S3 missing-key helper failures remain missing-key regression detection,
not graceful refusal evidence; this new platform test does not reclassify those receipts.
