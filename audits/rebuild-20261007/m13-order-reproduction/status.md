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

## Follow-up collection/connection lead

The supplied peer collection list and our current exact list are identical: 160 node IDs, same order. Collection discrepancy is closed as the earlier reporting arithmetic error.

Peer reports Python 3.12.14, pytest 8.4.2, Playwright 1.63.0 and no pytest-playwright. Our isolated interpreter is Python 3.12.14, pytest 9.1.1, Playwright 1.63.0, pytest-asyncio 1.4.0, anyio 4.15.1, langsmith 0.14.4 and no pytest-playwright. Plugin/version parity beyond Python/Playwright is not established.

Peer reports a separate ancestor c5918ca5 standalone failure around 14:33 IST with a surviving Playwright connection-error fragment at _connection.py:632. That is not the missing original b944215 combined-run traceback. Direct session source uses a fresh tmp_path, instance async lock and per-instance Playwright/browser/context, with finally close. No module-level shared browser is present. Driver startup/launch and teardown can raise connection errors, but there is no evidence identifying which operation failed in the original run. No automatic launch retry is present; adding one without an observed failure would mask evidence rather than explain it.

Ten new separate-process exact-browser repeats all pass, each with verbose full traceback capture enabled. These repeated passes do not rule out a transient connection/resource failure and do not close the original failure gate. No order/session leakage or launch-race root cause is established.
