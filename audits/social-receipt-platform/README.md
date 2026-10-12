# Social receipt platform binding

Base: 27511b4a. The successful callback returns the platform of the actual constructed
PublishRequest alongside its outcome; PublishRecord uses that captured request platform,
not entry.platform or adapter-result.platform. Canonical factory/request selection is
preserved. The custom-gate Twitter-to-LinkedIn probe now checks both returned and stored
publish-record platform. A separate adapter-result mislabel test proves provider labels
are not used as receipt authority. This repairs a scoped reporting inconsistency, not
an owner-approval or custom-gate authorization guarantee.

Released selector:

    PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest tests/modules/test_m06_publish_guardrail.py tests/modules/test_m06_scheduler.py -q

Result: 30 passed. Receipt battery: 3 CAUGHT, 0 SURVIVED/INVALID/NOT-APPLICABLE,
SHA-256 restoration true. Mutants restore stale-entry receipt, fixed Twitter receipt,
and provider-result receipt. Existing platform battery exact adapter-expression needles
were retargeted to the equivalent refactored request.platform site; fresh composition
replay: 4 CAUGHT, no survivors/invalids/not-applicable, SHA-256 restoration true.
Historical platform receipts are retained unchanged, not presented as fresh runs.

CAUGHT requires rc=1 plus FAILED ids, collection/internal/fatal errors screened and
timeout uncredited. Product KeyError/RuntimeError failures may count; mixed FAILED+SKIP
is not rejected. These are selected-test failure-sensitivity counts, not universal
restoration or comprehensive coverage. Successful-run byte restoration is checked;
interruption during initial mutation write is not claimed safe. Delivered receipts have
no private paths or raw exception dumps; no path/whitespace normalization was needed.
No private-original or missing historical log is recovered by this patch.

The execute_due docstring now names only caught GuardrailRefusal/AdapterError. Other
factory/adapter, malformed canonical-data and repository exceptions may propagate.
ScheduleEntry.platform remains the originally scheduled platform; PublishRecord.platform
is the executed request platform. Endpoint/account and external-id/url correctness remain
adapter-trusted. Media checks remain pre-gate against entry; custom-gate changes are not
media-certified. Execution binding is not owner-reviewed binding; in-memory rates are not
distributed durability; post-admission failures may consume budget. No live provider or
deployment proof. Historical S2/S3 helper KeyErrors retain their missing-key-only meaning.
