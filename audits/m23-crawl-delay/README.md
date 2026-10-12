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
CAUGHT only on pytest rc=1 with FAILED lines; rc 2/4/5 or timeout = INVALID. Result: CAUGHT=12, SURVIVED=0, INVALID=0.
Mutated files are SHA-256 checked as restored. M12 takes ~50s because the mutant really sleeps.

## Limits: what stays untested
- No live fetch. All HTTP is faked.
- `sleep` is injected, so real wall-clock timing is not tested (only the requested seconds and call order).
- One robots plus one page request per call: there is no cross-call, per-host pacing.
- The legacy unbounded `admitted_cases.fetch_case_metadata` (used by tests/modules/test_m23_admitted_cases.py, shadowed in
  routes.py by the bounded import) still ignores Crawl-delay.
- The sync route can block up to 30s per request (it runs in the threadpool).
- Crawl-delay values the stdlib `RobotFileParser` does not parse (non-digit, negative, decimal) are treated as no delay.
