# m23 legacy admitted_cases.fetch_case_metadata: Crawl-delay via delegation

Decision: option (a). The legacy unbounded helper had its own fetch path (own httpx client, own robots parse, no
Crawl-delay, 1MB check only after the full body was read). It is now a thin delegate to
`admitted_cases_bounded.fetch_case_metadata_bounded` (lazy import, because the bounded module imports this one).
Signature is backward compatible: `fetch_case_metadata(case_id, transport=None, **kwargs)`; extra kwargs
(`max_crawl_delay`, `sleep`, `page_limit`, ...) pass through. Its old tests in test_m23_admitted_cases.py pass unchanged.
Why not a guard (b): the only non-route caller is its own test file, and delegation removes the duplicate unsafe path
instead of documenting it. routes.py already imports the bounded function under the same name.

Run (repo root): `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 -m pytest tests/modules/test_m23_admitted_cases_legacy_delegation.py tests/modules/test_m23_admitted_cases_crawl_delay.py tests/modules/test_m23_admitted_cases_bounded.py tests/modules/test_m23_admitted_cases.py -q` (41 passed).

Mutation receipts: `python3 audits/m23-legacy-crawl-delay/run_mutations.py` -> mutation_receipts.txt. 8 mutants (L1-L8) on
admitted_cases.py. CAUGHT only on pytest rc=1 with FAILED lines; rc 2/4/5 or timeout = INVALID. Result: CAUGHT=8,
SURVIVED=0, INVALID=0, SHA-256 restore check passes. L2 drops the injected sleep, so it really sleeps and takes ~35s.
A first run also had a mutant L9 (transport=None) that was dropped because it could issue real HTTP requests; it was
caught but is not in the harness or receipts.

## Limits: what stays untested
- No live fetch; all HTTP is faked with MockTransport.
- Injected `sleep` only; the default `time.sleep` path and real timing are not tested.
- Delegation is checked by behavior and by a monkeypatched sentinel; nothing stops a future caller from adding a new
  fetch path elsewhere in the module.
- The legacy function is still importable and callable by non-test code. This patch makes it safe, it does not forbid it.
- No cross-call per-host pacing; the sync route can still block up to 30s (see audits/m23-crawl-delay/README.md).
- Crawl-delay forms the stdlib parser ignores (non-digit, negative, decimal) count as no delay.
- Behavior change: the legacy helper now returns the bounded helper's closed status set and result shape, and raises
  ValueError on invalid cap args. The `too_large` status is kept, but now comes from the bounded read limits, which stop reading early.
