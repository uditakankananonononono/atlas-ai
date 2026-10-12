# m23 admitted-cases: robots Crawl-delay in the production helper

Change: `fetch_case_metadata_bounded` (backend/app/modules/m23_study_abroad/admitted_cases_bounded.py) now reads
`Crawl-delay` for our user agent after the robots `can_fetch` check and before the page request.
- delay > `max_crawl_delay` (default 30, validated 0..120, no bool) -> returns status `crawl_delay_too_long` with
  `crawl_delay_seconds`; the page is not requested.
- 0 < delay <= cap -> `sleep(delay)` (injected, default `time.sleep`), then the page request.
- No delay, or robots denied: unchanged behavior (a denied page is never requested).
- New params `max_crawl_delay` and `sleep` have defaults, so existing callers are unchanged.

Run (repo root): `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 -m pytest tests/modules/test_m23_admitted_cases_crawl_delay.py tests/modules/test_m23_admitted_cases_bounded.py tests/modules/test_m23_admitted_cases.py -q`
(32 passed).

Mutation receipts: `python3 audits/m23-crawl-delay/run_mutations.py` -> mutation_receipts.txt. 12 mutants (M1-M12),
CAUGHT only on pytest rc=1 with FAILED lines. FAILED includes product KeyError/RuntimeError,
not just assertions; mixed FAILED plus SKIP is not rejected. No independent ERROR/collection/internal/fatal
screening is implemented beyond rc and FAILED-ID presence. Timeout, other nonzero rc, or rc1 without FAILED
IDs is INVALID; rc0 is SURVIVED, including rc0 with skips. Result: CAUGHT=12, SURVIVED=0, INVALID=0.
Mutated files are SHA-256 checked as restored. M12 takes ~50s because the mutant really sleeps.

## Limits: what stays untested
- No live fetch. All HTTP is faked.
- `sleep` is injected, so real wall-clock timing is not tested (only the requested seconds and call order).
- HISTORICAL SCOPE (this package alone): one robots plus one page request per call, no cross-call pacing inside this package. Cross-call per-host pacing was added later by the separate HostPacer change (see audits/m23-host-pacing/README.md); read this line as the scope of this package, not the current combined behavior.
- The legacy unbounded `admitted_cases.fetch_case_metadata` (used by tests/modules/test_m23_admitted_cases.py, shadowed in
  routes.py by the bounded import) still ignored Crawl-delay at the time of this package only; the later legacy-delegation change (audits/m23-legacy-crawl-delay/) routes it through the bounded helper. Current behavior is described there, not here.
- 30s is only the DEFAULT cap on the requested Crawl-delay sleep. It is not a wall-clock bound for the route. A call also
  spends time on the robots request, the page request and parsing (httpx timeouts are per phase, with no total deadline),
  and `max_crawl_delay` can be set up to 120s. Nominal per-call time is about 2*T + D (T = httpx timeout per phase, 8s;
  D = Crawl-delay actually slept, at most max_crawl_delay). No timing acceptance test exists. The sync route runs in the
  threadpool, so a slow call holds a worker.
- The per-call delay is not cross-call or concurrent pacing: it only spaces that call's robots request from its page
  request. Pacing across calls to the same host is a separate mechanism (HostPacer, audits/m23-host-pacing/).
- Only whole-number delays are honored. Fractional policies (for example `Crawl-delay: 0.5` or `2.5`), negative and
  malformed values are not read by the stdlib `RobotFileParser` and are treated as no delay; a test pins that stdlib
  limitation, it is not a compliant fractional-delay implementation. Do not read this as "all robots policies handled".
- `sleep` is a trusted callable and is not validated; a non-callable or a raising callable propagates its error.
- Tests do not cover: the upper cap boundary of 120, a non-finite `max_crawl_delay` (rejected by the range check, not
  separately tested), or an exception inside the injected sleep.
- `test_result_contains_no_robots_text_or_error_detail` is named more strongly than it asserts: it checks that the string
  'User-agent' is absent and that the result is a superset of the row keys. It does not prove that no arbitrary error
  detail can appear.
- Harness: a mutant is CAUGHT on rc=1 plus FAILED lines. It does not distinguish an assertion failure from a setup or
  teardown error beyond that summary, and only the first failing test ids are kept, not the full trace.
- Crawl-delay values the stdlib `RobotFileParser` does not parse (non-digit, negative, decimal) are treated as no delay.
