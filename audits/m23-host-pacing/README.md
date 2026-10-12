# m23 cross-call per-host pacing (HostPacer): serialized per host, in-flight aware

Change (backend/app/modules/m23_study_abroad/admitted_cases_bounded.py): `HostPacer`, an in-memory, thread-safe ledger.
`fetch_case_metadata_bounded` (and the legacy `admitted_cases.fetch_case_metadata`, which delegates to it) now:
1. `acquire(host, max_pace_wait)` before the robots request. Calls to one host are SERIALIZED: while another call to the
   same host is in flight (robots + Crawl-delay sleep + page), later callers block on a condition variable for at most
   `max_pace_wait` real seconds, then get `host_pacing_busy` (no request made). A host with no known delay therefore
   gets SERIAL first-robots access ("single-flight" in the tests): the other callers queue and then each fetch robots.txt
   themselves, one at a time, using the delay the first one learned. It is not one cached or de-duplicated robots request.
2. The admitted call must also wait until the host's last known Crawl-delay has passed since the previous call's NETWORK PHASE
   ended (end of that call's robots, Crawl-delay sleep and page request, not its start). That wait goes through the injected `sleep`. If it is longer than
   `max_pace_wait` the call returns `host_pacing_busy` with `retry_after_seconds` and holds nothing.
3. `release(host, delay)` runs in a `finally` that wraps the network phase only. It runs BEFORE the post-fetch status,
   content-type and HTML parsing, so another caller may start while the previous call is still parsing and returning:
   exclusion and spacing are to network-phase end, not to function return. It records the finish time, the delay learned from robots.txt (None keeps the
   last known one), clears the in-flight mark and wakes waiters.
Params `pacer` (default: process-wide `DEFAULT_PACER`) and `max_pace_wait` (default 60, validated 0..600, no bool) are
defaulted. `HostPacer(clock, max_queue)`: `max_queue` only lowers the real-time queue wait and exists so tests fail
fast; production leaves it None. All earlier closed statuses keep their semantics; `host_pacing_busy` is the one new status.

## What changed from the first version
- First version booked start slots only. A queued booking was never re-based when an earlier call finished late, so call B
  could start before call A ended (A admitted 1010, finished 1025; B booked 1020, started 1020 while A was running) and 5
  concurrent first calls to a fresh host all fetched robots.txt at once. Both are fixed by per-host in-flight exclusion.
- Regression tests: `test_ab_overlap_regression_...` (B parked while A is in flight, then starts >= A_end + delay) and
  `test_concurrent_first_calls_to_a_fresh_host_are_single_flight` (max 1 in-flight request to the host across 5 threads).

## Blocking bound (formula, not a constant)
Nominal wall-clock of one call (not a guaranteed maximum), with M = max_pace_wait, D = max_crawl_delay, T = httpx TIMEOUT_SECONDS (8):
  queue (<= M) + ledger spacing (<= M, else refused) + robots request (<= T) + in-call delay (<= D) + page request (<= T)
  = 2M + D + 2T.  This is a NOMINAL formula, not a total bound: T is a per-phase httpx timeout (connect, read, write and
  pool each), with no total deadline, so a slow server can exceed 2T and a call can run longer than the formula says.
  Nominal figures: defaults 2*60 + 30 + 2*8 = 166s; with custom D up to 120 and M up to 600, 2*600 + 120 + 16 = 1336s.
The sync route runs in the threadpool, so one such call can hold a worker for about that long, or longer.

Run (repo root): `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 -m pytest tests/modules/test_m23_host_pacing.py tests/modules/test_m23_admitted_cases_legacy_delegation.py tests/modules/test_m23_admitted_cases_crawl_delay.py tests/modules/test_m23_admitted_cases_bounded.py tests/modules/test_m23_admitted_cases.py -q`

Mutation receipts: `python3 audits/m23-host-pacing/run_mutations.py` -> mutation_receipts.txt (Q1-Q23). CAUGHT only on pytest rc=1
with FAILED lines. FAILED includes product KeyError/RuntimeError, not just assertions; mixed FAILED plus SKIP
is not rejected. No independent ERROR/collection/internal/fatal screening is implemented beyond rc and
FAILED-ID presence. Timeout, other nonzero rc, or rc1 without FAILED IDs is INVALID; rc0 is SURVIVED,
including rc0 with skips. Mutated files are SHA-256 checked as restored. No mutant passes
`transport=None`; every call uses MockTransport. Commit the source before running the harness: killing the harness mid-run
can leave a mutant on disk (this happened once during development and was restored from git).

## reset() guard
`HostPacer.reset()` is a trusted maintenance/test hook. It now raises `RuntimeError` and changes nothing while any host is in
flight, because clearing a live in-flight mark would admit a second caller to that host. `reset(force=True)` skips the check
and is meant for tests (the m23 conftest fixture uses it). Idle `reset()` clears the ledger. Tests: a refused reset leaves
state and exclusion intact; idle reset and force reset; mutants Q20-Q23.

## Limits: what stays untested or unfixed
- WARNING (carried from audits/m23-legacy-crawl-delay/README.md, permanent and unresolved): an earlier, unreleased run of
  that lane's harness included a mutant (L9, transport=None) that may have attempted REAL, unrecorded HTTP requests from the
  build sandbox. That mutant was removed and is not in the receipts.
- Dependency injection bypasses the shared ledger: a call given its own or a fresh `HostPacer` (or a no-op `sleep`, or a
  non-monotonic `clock`) is not paced against other callers. The helper does not check that `sleep` really waits.
- The ledger dictionaries are unbounded and never evict: each distinct hostname is kept for the life of the process. The
  default catalog is small; a caller-supplied `catalog` could add hosts.
- If a thread dies without running its `finally` while the process survives (hard thread kill), that host stays marked busy;
  there is no lease or expiry, so later callers get `host_pacing_busy` until restart or `reset(force=True)`.
- `retry_after_seconds` on a queue timeout is a hint, `max(1, last known delay)`, not the remaining wait. Spacing refusals
  report the actual remaining spacing.
- A robots response with no (or an unparseable) Crawl-delay stores delay 0 and so erases a previously known delay for that
  host; robots-denied and robots-unverified calls keep the previous delay.
- Process-local and in-memory: no cross-process or cross-machine pacing; a restart clears it; nothing is persisted.
- Monotonic clock only. Tests use a fake clock for spacing and an injected sleep; the default `time.sleep` and real
  spacing timing are not tested. There is no live fetch.
- Real-thread tests (queue timeout, wake-up, overlap, single-flight) use MockTransport, Events and sub-second real timeouts.
  They show the exclusion under that contention, not the absence of every race.
- A host with no robots Crawl-delay is serialized but not spaced. The first-ever call is not delayed by the ledger.
- A robots-denied or robots-unverified call records its finish time but not a delay (read only after the allow check).
- A page skipped as `crawl_delay_too_long` records the long delay, so retries inside that window wait or are refused.
- Hosts are keyed by hostname only. Waiters are not served in FIFO order (condition-variable wake order).
- Crawl-delay forms the stdlib `RobotFileParser` ignores (non-digit, negative, decimal) count as no delay.
- Injected `sleep` errors are NOT uniformly propagated: inside the call, a `ValueError` or `UnicodeError` or `httpx.HTTPError` raised by `sleep` is converted to a `fetch_failed` row (the call's broad except), while other types (tested: `RuntimeError`) propagate. Only RuntimeError is tested; the conversion of ValueError from `sleep` is by code reading, not a test. The host is released either way.
- An exception that escapes the call still releases the host (tested for in-call and spacing sleep), but a killed thread
  or process cannot.
