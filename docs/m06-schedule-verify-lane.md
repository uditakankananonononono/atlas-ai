# M06 schedule verification lane (README)

Files: `tests/modules/test_m06_schedule_verify_lane.py`, `tests/modules/test_m06_naive_publish_at_lane.py`,
and the naive-`publish_at` guard in `scheduler.py` (`NaivePublishTimeError`, `require_aware`), `service.py`
(`request_schedule`), `schemas.py` (`ScheduleIn`, `RescheduleIn`), `routes.py` (422).

## What is checked
- Nothing publishes before approval; denied and future-dated entries never publish.
- A blocked adaptation files zero approvals and creates zero schedule entries.
- A `publish_at` with no UTC offset is rejected (service, scheduler create/reschedule, request schemas, HTTP 422).
  `None` still means "now"; aware values keep their instant.
- Legacy rows already stored naive are still read as UTC when due (`_aware`); this is unchanged and pinned.

## The secret-free pin is a structural check, not a proof
`secret_findings` walks dict keys, string values and nested list/tuple/set members and flags
(a) key names containing token/secret/password/credential/api_key/authorization and
(b) string values matching a short list of known secret shapes (Bearer tokens, `sk-`, GitHub, AWS, Slack tokens,
JWTs, private-key headers, `password=...`). A negative-control test plants each shape to prove the scan fires.
It does NOT prove a payload is secret-free: unknown formats, encoded values, or secrets that fit none of the
patterns pass. No real platform adapter or credential was exercised.
