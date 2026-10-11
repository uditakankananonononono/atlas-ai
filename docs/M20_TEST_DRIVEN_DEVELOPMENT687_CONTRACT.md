# Source pin

`audits/coverage-register.json`, row687, main `a294723b7a8f7bbe6067804ee4d7d325e1a8bde9`.
Requirement (verbatim): "Test-Driven Development". Description (verbatim): "Writes tests first".
`audits/additional-2000-features.json` reports PARTIAL. Historical verification labels are not current proof or this package's completion claim.

## Delta

Existing `backend/app/modules/m20_general_cognitive_worker/software_practice_685_709.py:21` `_tdd` echoes failing_test/minimal_change/refactor_checks, converts caller red/green flags to booleans, and computes cycle_complete. Existing test `tests/modules/test_m20_software_practice_685_709.py:48` toggles those flags.
This standalone new file does not repeat that boolean template. It checks bounded explicit supplied stage receipts: ordering, test identity/suite preservation, result counts and declared revision change. Shared cluster, dispatcher, tests and ledger unchanged. No route registration, source fetching or receipt execution.

## Selected schema and bookkeeping

`run(request)` accepts exact dict keys as_of, cycles. as_of is a caller label, not a validated date or trusted clock. cycles is nonempty list at most64. Each cycle exact keys id, behavior, receipts. IDs unique.
Receipts exactly three, ordered red/green/refactor. Each exact keys stage, ordinal, revision_ref, suite_ref, evidence_ref, results. Ordinal exact int1..1000000000, bool refused. Results nonempty list at most100; each exact keys id, outcome, unique test IDs within a stage; outcome PASS or FAIL only.
All four schema levels reject65+keys with the fixed fields:<shape> reason before key iteration or any set construction. After count, every key must have exact type str before allowlist membership; str-subclass keys refuse with the same generic fields reason. No caller key/value is echoed.

Every free-text label/reference exact str, nonblank, raw length at most256. Length checked directly after type before Unicode scan or strip. Rejected Unicode categories Cc/Cf/Zl/Zp, including U+00AD and U+2060. All seven _text fields covered: as_of, cycle_id, behavior, revision_ref, suite_ref, evidence_ref, test_id. Zs accepted within otherwise nonblank text; no new Cs refusal. Full Cf category checked under each interpreter's Unicode database. Ordinary spaces and printable non-ASCII allowed. References are opaque labels, not authenticated/file/content hashes.

A cycle is declaration_consistent only if ordinals increase strictly, red has a FAIL, green/refactor have no FAIL, all three suite refs and test-ID sets match, and red/green revision refs differ. Reasons appear in that fixed order. Refactor revision need not differ. No assertion about when tests were written or whether revision refs refer to real code. Result counts computed from actual supplied rows. Request not changed; output uses fresh structures. Integer counting only, no scores or predictions.

These caps/schema/consistency rules are bounded implementation interpretations of the title/description, not an assertion the owner's original request was limited to receipt bookkeeping. Row intent remains broader: writes tests first. This PREP unit never does that on the caller's behalf.

stage/outcome enums have exact str type first, raw length256cap second, expected-stage comparison/allowed-outcome membership last. Same fixed stage:receipts or outcome:result refusal for each invalid enum; no caller value echoed. Enum controls/Cf refuse by finite allowlist, not by the seven-field _text rule. N256 invalid values reach comparison/membership; N+1 and non-string values refuse earlier, proven by line trace pins.

## Refusals

ValueError exact prefix `TESTDR687:` followed by type:<shape-or-field>, fields:request/cycle/receipt/result, empty:<field>, limit:cycles/receipts/results, text_length:<field>, text_control:<field>, duplicate:cycle_id/test_id, count:receipts, stage:receipts, integer:ordinal, outcome:result. Names, never caller values, in refusal text. Unknown/missing keys share fields errors. Inconsistent receipts are reported reasons, not malformed-schema refusals.

## Builder evidence

Tests authored and executed before runtime existed: raw FileNotFoundError RED on both interpreters, not behavioral assertion RED or unrelated dependency failure. Direct file loader avoids shared package initialization. Standard-library unittest, no pytest/application dependencies.19tests PASS on actual CPython3.12.14 and3.10.12.12 ORIGINAL PRE-repair literal mutation/guard-removal operators (NOT retaken) ASSERT-fail,0survivors in that limited own battery; not independent audit/full mutation coverage. Original raw logs retained. Repair tests first on unchanged runtime:17tests,3assertion failures on both interpreters (count-first, exact key, Cf). Then17PASS both;3targeted guard-removal probes3ASSERT0ERROR0SURVIVED, restored17PASS both. Repair output scrubbed of scratch paths only; no caller identifiers/names. Full Atlas suite UNRUN, package initialization/integration UNVERIFIED. PATCH ONLY: no commits/push/rebase/amend/reset. Independent review needed before landing. No closure claim.

Enum follow-up test-first:19tests2assertion failures on unchanged repair runtime, then19PASS both interpreters;2enum-cap removal probes2ASSERT0ERROR0SURVIVED; restored19PASS both. Original first enum RED stopped after the stage failure; later RED uses subtests and shows both stage/outcome failures, both logs preserved.

## Limits

Supplied declaration bookkeeping only. tests_executed, evidence_verified, repository_behavior_verified and release_authority explicitly false. No test runner, code transformation, actual TDD enforcement, truthful receipt authentication, legal advice, release or deployment. Passing own unit tests proves only this bounded mechanism's tested behavior, not real execution of supplied tests or row687 completion.
