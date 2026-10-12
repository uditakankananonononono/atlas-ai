# Rows 47-64 delta (post-landing deepening)

Scope literal: nothing here promotes any row beyond PARTIAL. Every result below is a recorded local run unless a
receipt file is named; the receipt files are in this directory and the runners are committed so anyone can re-run.

## Row 57 (Clicky)
`execute_stats_request` in c31/clicky.py is a stdlib GET transport for the documented stats endpoint.
- Off by default for the real host: without `base_url` it needs `live_approved=True` AND env
  `ATLAS_CLICKY_LIVE_OWNER_APPROVED=1`, else `APPLY_REFUSED_NOT_APPROVED`. A default-off guard, not an authorization
  system; the owner's sitekey and approval are still needed. No call to api.clicky.com was made.
- A plan is accepted only if `plan_stats_request` would produce exactly it (else `APPLY_REFUSED_BAD_TYPE:plan`).
- Proxy env vars are ignored (empty ProxyHandler); redirects are refused; `timeout` bounds the call AS SEEN BY THE CALLER
  (outer future timeout), plus a read1 deadline loop inside the worker for the body phase. A header-drip server test (each
  read within the per-operation timeout) proves the outer bound. Connect and DNS stalls are bounded by the same outer
  timeout (they run in the worker) but have no dedicated test. RESIDUE: urllib cannot cancel the worker, so after a refusal
  the worker thread may outlive the call (body: until its next read1; connect/headers: until the per-operation timeout or
  the server finishes). It holds no result and nothing waits on it; a test asserts it ends once the server finishes. Refusals carry no chained exception, so the sitekey in the request URL is not
  reachable from `__cause__`/`__context__`/tracebacks. The sitekey is in the query string because the documented API
  takes it there. The result `request.url` is the URL actually hit (no query).
- Tests: `tests/modules/test_c31_clicky_transport.py` runs it against a loopback ThreadingHTTPServer behind an autouse
  socket guard that fails the test on any non-loopback connect.

## Row 56 (20 publisher links)
- `run_row56_liveness.py` is the runner; `row56_receipts.json` is its raw output (per link: robots status, FULL robots text
  and the SHA-256 of the original response bytes, robots Crawl-delay, request timestamps, spacing applied, page status,
  content-type, Location header, byte count and SHA-256). `verify_row56_receipts.py` re-checks it offline.
- This run HONORS per-host robots Crawl-delay (spacing = max(1s, Crawl-delay); above 30s the link is not fetched). Hamilton
  declares 5s, Dartmouth and CollegeTransitions 10s; recorded gaps respect them (0 violations across 20 hosts).
  An EARLIER d1/d3 run, and the existing helper `fetch_case_metadata_bounded`, used 1s spacing and ignored Crawl-delay;
  `row56_link_liveness_2026-10-12.json` is from that earlier helper run and should be read as such (recorded local run,
  Crawl-delay not honored). The helper in production code still ignores Crawl-delay (not changed here).
- Result of this run: 16 page_reachable; jhu 403, collegeessayguy 403, cornell 308 redirect (Location recorded),
  admitraven robots.txt 307 redirect (robots_unverified, page not requested). Nothing was bypassed.
- page_reachable now requires a 200 text/html page whose bytes were actually read; an over-size page is recorded as
  page_too_large_not_read. Body bounds are decoded-retained bounds, not transport peak allocation. Reachable does not
  prove the page is the expected content (a login or soft-challenge page returning 200 would count), nor anything about
  admissions outcomes or licensing. The index is still not a dataset or licensed corpus.

## Row 64 (pipeline)
`tests/modules/test_m25_row64_scale_workflow.py`: real LocalKnowledgePipeline over 210 SYNTHETIC local sources.
All 210 retrievable by their own token (top-1); one positive citation plus wrong-source and ungrounded negatives;
consent and tenant denial; dedup/versioning; deletion; attested restart restore; a contradiction case at scale.
Citation checks bind stored bytes, not semantic truth. Attestation is a caller assertion.
FOUND BY THIS TEST (a residual, pinned not fixed): `contradictions()` pairs any two retrieved chunks whose negation
words differ, and `search()` returns up to 100 chunks with any positive score, so one negated chunk pairs with many
unrelated chunks (noisy, fail-closed). Not a 200-real-source corpus; no learning into Atlas.

## Row 63 (advice pipeline)
`tests/t_units/test_row63_advice_pipeline_workflow.py` (19 tests): real PublicFetcher (permit, robots, rate limit incl.
59.9/60 s boundary and an independent second host, crawl-delay, oversize page, robots non-200, robots over limit, 302 not
followed) over a loopback server via a test-authored transport, then T3 and T4. Each candidate hash is bound to its own page
URL; the candidate list is compared exactly; T3 flags (paywalled, piracy, credentials, logged_in), dedup, the 500-candidate
cap, bad date and oversize text are refused or applied as coded; policy-denial asserts the exact `FLEET_REFUSED_OUTREACH`
and a separate test the `FLEET_REFUSED_UNAVAILABLE` path. UNTESTED: non-UTF-8 response decoding (it belongs to the caller-
supplied transport), TLS/DNS pinning, real advice sources, T1 and T2 beyond the existing t_units tests. Advice becoming
training or a created artifact is not shown; row 63 stays PARTIAL.

## Mutation receipts
`run_mutations.py [out.txt]` applies each single-replacement mutant (exact old/new text in the script) and runs the named
test file. CAUGHT means pytest exited 1 with at least one FAILED test ID. FAILED includes product
KeyError/RuntimeError, not just assertions; mixed FAILED plus SKIP is not rejected. No independent
ERROR/collection/internal/fatal screening is implemented beyond rc and FAILED-ID presence. Timeout,
other nonzero rc, or rc1 without FAILED IDs is INVALID; rc0 is SURVIVED, including rc0 with skips. Restore is verified by SHA-256 of every mutated file against its pre-run content.
The last run's counts and any SURVIVED or INVALID entries are in `mutation_receipts.txt` and are stated in the delivery
message. Prior versions of this harness counted any non-zero exit as a catch; that is why the counts below were re-run.
