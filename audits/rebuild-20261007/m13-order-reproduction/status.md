# M13 original combined failure: unresolved

Peer-attributed original b944215 run: 159 passed, 1 failed; exact node test_m13_source_reconciliation_browser.py::test_actual_browser_source_reconciliation_uses_same_session_and_no_second_click. Only the summary was retained; original traceback and execution order are unavailable. Standalone peer rerun passed. This signature suggests order/session pollution as one hypothesis, but it does not establish the cause.

## Collection correction

Our recovered original local combined log explicitly collected 160 items, not 161. The earlier 161 claim was a reporting arithmetic error that propagated into reports. Current collection under the isolated peer interpreter also gives 160 exact node IDs. Main interpreter lacks Playwright and yields 150 collected plus two import errors; this is not a comparable complete execution environment. Peer exact current node list is requested for cross-environment parity comparison.

## New retained evidence

Actual peer commit b944215353d8d641cb476cf3ffba8075072840da, unmodified. Python 3.12.14, pytest 9.1.1, asyncio 1.4.0, Playwright available. Real local Chromium fixture; no external navigations beyond hermetic intercepted fixture URLs. Commands disable randomly and cacheprovider and retain verbose order/tracebacks.

- Default combined M11/M13 order: 159 passed, 1 skipped.
- File-order seed 17: 159 passed, 1 skipped.
- File-order seed 83: 159 passed, 1 skipped.
- Exact browser reconciliation standalone: 1 passed.

The skipped test is PostgreSQL session CAS, with pgserver unavailable. These passes do not explain or replace the original peer failure. No leaking predecessor has been identified, no browser/session product fix is justified yet, and no root-cause closure is claimed.
