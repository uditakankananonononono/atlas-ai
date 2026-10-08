# M12 adaptation on Atlas main 3eef2c0

Base: 3eef2c0ab2344abfcc2de912e154a1b28f43d087.
The original f64e0c37 packages remain separate evidence, not prerequisites.

The opt-in module cherry-picked clean. executor.py conflicted because main had
the older executor: invented .5 confidence, no unknown/review separation, no
policy validation or result guards. Main's adapter also invented .75 confidence.
The main router, DAG, HTTP layer and provider usage infrastructure are older than
f64e0c37. No claim of parity with the old-base audited branch is made.

This adaptation implements the boundary directly in ResearchExecutor using
BoundedProvider; plain data is detached and bounded before dispatch and after
return. Invalid returned confidence/logprobs are unknown here, not the old-base
unavailable-confidence sanitation path. Missing evidence is review-required.
Subclass results are rejected before reconstruction, unlike the old-base path.
RetryPolicy validates its values. AtlasProvider no longer invents .75 confidence;
it returns None with unavailable provenance. The single-run HTTP route returns
409 unknown/no retry, 422 review/no retry or 422 invalid-input/no retry.

Tests use explicit scripted provider doubles, not real model inference. Executed
all main-base M12 tests on Python 3.12.14: 939 passed, one existing Starlette/httpx
warning. The 1334 count from the old base does not apply to this base. Before
control runs retain their actual outcomes in receipts. No main writes or push.

Limits: no owner-PC acceptance, source authentication, calibrated quality,
provider usage extraction, actual billing, aggregate spending control, provider
resource/transport bounds, router hardening, workflow unknown/review HTTP repair,
durable replay, rollback, prompt-injection resistance or concurrent snapshot
claim. Default limits are local choices. Main's existing DAG and router remain
unchanged. Existing adapter usage stays empty because main exposes text only.
