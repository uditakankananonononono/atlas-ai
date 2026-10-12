# m23 cross-call per-host pacing (HostPacer): serialized per host, in-flight aware

Change (backend/app/modules/m23_study_abroad/admitted_cases_bounded.py): `HostPacer`, an in-memory, thread-safe ledger.
`fetch_case_metadata_bounded` (and the legacy `admitted_cases.fetch_case_metadata`, which delegates to it) now:
1. `acquire(host, max_pace_wait)` before the robots request. Calls to one host are SERIALIZED: while another call to the
   same host is in flight (robots + Crawl-delay sleep + page), later callers block on a condition variable for at most
   `max_pace_wait` real seconds, then get `host_pacing_busy` (no request made). A host with no known delay therefore
   gets a single-flight first robots fetch: the others queue, then use the delay it learned.
2. The admitted call must also wait until the host's last known Crawl-delay has passed since the previous call FINISHED
   (end of that call, not its start). That wait goes through the injected `sleep`. If it is longer than
   `max_pace_wait` the call returns `host_pacing_busy` with `retry_after_seconds` and holds nothing.
3. `release(host, delay)` runs in a `finally`: records the finish time, the delay learned from robots.txt (None keeps the
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

Mutation receipts: `python3 audits/m23-host-pacing/run_mutations.py` -> mutation_receipts.txt (Q1-Q19). CAUGHT only on pytest rc=1
with FAILED lines; rc 2/4/5 or timeout = INVALID. Mutated files are SHA-256 checked as restored. No mutant passes
`transport=None`; every call uses MockTransport. Commit the source before running the harness: killing the harness mid-run
can leave a mutant on disk (this happened once during development and was restored from git).

## Limits: what stays untested or unfixed
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
- An exception that escapes the call still releases the host (tested for in-call and spacing sleep), but a killed thread
  or process cannot.
