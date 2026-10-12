# m23 legacy admitted_cases.fetch_case_metadata: Crawl-delay via delegation

Decision: option (a). The legacy unbounded helper had its own fetch path (own httpx client, own robots parse, no
Crawl-delay, 1MB check only after the full body was read). It is now a thin delegate to
`admitted_cases_bounded.fetch_case_metadata_bounded` (lazy import, because the bounded module imports this one).
Call syntax retains the existing case_id/transport arguments, but behavior is not fully backward compatible: `fetch_case_metadata(case_id, transport=None, **kwargs)`; extra kwargs
(`max_crawl_delay`, `sleep`, `page_limit`, ...) pass through. Status/result shape and invalid-argument behavior
change as described below; passing the selected old tests does not establish full backward compatibility.
Why not a guard (b): the only non-route caller is its own test file, and delegation removes the duplicate unsafe path
instead of documenting it. routes.py already imports the bounded function under the same name.

Historical released selector (not a current-count claim): `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 -m pytest tests/modules/test_m23_admitted_cases_legacy_delegation.py tests/modules/test_m23_admitted_cases_crawl_delay.py tests/modules/test_m23_admitted_cases_bounded.py tests/modules/test_m23_admitted_cases.py -q` (41 passed).

Mutation receipts: `python3 audits/m23-legacy-crawl-delay/run_mutations.py` -> mutation_receipts.txt. Historical 8-mutant battery (L1-L8) on
admitted_cases.py. CAUGHT only on pytest rc=1 with FAILED lines. FAILED includes product KeyError/RuntimeError,
not just assertions; mixed FAILED plus SKIP is not rejected. No independent ERROR/collection/internal/fatal
screening is implemented beyond rc and FAILED-ID presence. Timeout, other nonzero rc, or rc1 without FAILED
IDs is INVALID; rc0 is SURVIVED, including rc0 with skips. Historical result: CAUGHT=8,
SURVIVED=0, INVALID=0, recorded SHA-256 restore check passes. L2 drops all kwargs, including the injected sleep.
Its retained old receipt says 35.59s; this is a harness observation, not wall-clock acceptance, a total-call
bound or real-server timing proof. Current focused L2 replay uses the kwargs sentinel with no real sleep.
Historical L8 is a constant-reachable stub with an unused client/parser, not restoration of the old fetch path.
The original operator label and receipt remain unchanged as historical records, not true-restoration evidence.
L9 was removed before release; see the warning in Limits.

## Limits: what stays untested
- No live fetch applies to the FINAL released test selector and run_mutations.py only: all HTTP there is faked with MockTransport. WARNING: an earlier, unreleased run of this harness included a mutant (L9, transport=None) that may have attempted REAL, unrecorded HTTP requests from the build sandbox. That mutant was removed and is not in the receipts.
- Nominal tests inject `sleep`; historical L2 dropped that injection. Neither that old duration nor this
  follow-up establishes real-server timing or a total wall-clock bound.
- Delegation is checked by behavior and by a monkeypatched sentinel; nothing stops a future caller from adding a new
  fetch path elsewhere in the module.
- The legacy function is still importable and callable by non-test code. This patch removes the duplicate unbounded fetch path; the helper inherits the bounded helper's limits and is not forbidden.
- The original delegation version had no cross-call pacing. Current calls inherit HostPacer from the bounded
  helper; see audits/m23-host-pacing/README.md for process-local, injected-pacer and nominal-time limits.
  The old "up to 30s" statement was not a total-call bound.
- Crawl-delay forms the stdlib parser ignores (non-digit, negative, decimal) count as no delay.
- Behavior change: the legacy helper now returns the bounded helper's closed status set and result shape, and raises
  ValueError on invalid cap args. The `too_large` status is kept, but now comes from the bounded read limits, which stop reading early.

## Current pkg8 replay on 41098321

`pkg8-followup/replay.py` restores the actual old fetch function body from source
715337337dc704cf18085128fef3ad24f8e88021 under the current kwargs-compatible
signature. This is body restoration, not byte-identical restoration of the old
module/signature. It preserves the old robots/page requests, ignored Crawl-delay,
full-body read then size check and metadata parsing. The current signature keeps
kwargs calls from failing only at argument binding. No product implementation
change is made or retained.

On Python 3.12.14, the retained current baseline and restored baseline each have
41 passed. The true-body probe has 6 FAILED / 35 passed, including delay/order,
cap/refusal and delegate assertions; the focused kwargs-drop sentinel has 1 FAILED.
Both probes report rc1 plus FAILED IDs and SHA-matching restoration. The full
logs and receipt.json are in pkg8-followup/. These are local recorded outcomes,
not independent reviewer execution or semantic acceptance. Commands normalize
only the interpreter path for delivery; this is disclosed in each receipt.
MockTransport is used by the selectors and a socket-connect denial plugin adds
a second offline check. This does not resolve or erase the permanent L9 warning
above. No full historical eight-mutant rerun is claimed.

### Delivered-log normalization

Delivered logs are intentionally changed from the original raw pytest bytes.
Trailing whitespace is removed; private workspace paths, if present, are replaced
with `<workspace-path>`. Original raw bytes are retained privately. The
`delivered_log_normalization.files` register in pkg8-followup/receipt.json names
every changed line and any original/delivered path pair, plus original and
delivered SHA-256 for each file. `original_log_sha256` binds raw evidence;
`log_sha256` binds delivered logs. No rerun is implied by this formatting repair.

- L2-kwargs-sentinel.log: original `f399d672871f9e305967f0d178649ee6a468593e80609c2a663ab7f2b00886e8`; delivered `ad8b1cceb77a9977b2d12a3cb09bccf9a36b245483657592075444c91ed7b74d`. Normalized lines: 17 (trailing-whitespace).
- L8-true-legacy-body.log: original `569a3588a35aa9d29dcbc616bd40ea59e9a77c6c71bbbc6fea63c8207553d47f`; delivered `5db30b30b45888da64e1bf9ac66339f66746bf83e3d337a2e62f20a23097d9fc`. Normalized lines: 10 (trailing-whitespace), 12 (trailing-whitespace), 23 (trailing-whitespace), 34 (trailing-whitespace), 44 (trailing-whitespace), 61 (trailing-whitespace), 71 (trailing-whitespace), 73 (trailing-whitespace), 78 (trailing-whitespace).
- baseline.log: original `bf16fb909a37fe9c1ed75e530dc4c5a5a6b07041b04f9b9e495ce79e82777940`; delivered `bf16fb909a37fe9c1ed75e530dc4c5a5a6b07041b04f9b9e495ce79e82777940`. Normalized lines: none.
- restored-baseline.log: original `45b37cf9a51b9b4407763b2661e8a098d18e57aa31702e334fd51aff35b9c3c1`; delivered `45b37cf9a51b9b4407763b2661e8a098d18e57aa31702e334fd51aff35b9c3c1`. Normalized lines: none.
