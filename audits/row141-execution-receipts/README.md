# Row 141 real local execution receipts

Source: instinct doc 1VRD84FClUlTk5pX8kcW6ZFxGfbAR6MwH8EoWdkCzlss,
read live on 2026-10-13. Opening passage demands "200+ external tools like
benchling, alphafold etc each". Global deliverables later say "40+ external
tools / services / APIs / platforms used" per project and "200+ external tools
overall across the program where feasible". These different bars are preserved.
Row numbering follows the existing main tool_usage_bar.py group-141 docstring;
no complete 142-row map was available in this checkout.

This delta does not replace the caller-attested tool_usage_bar API or count
its strings as observed execution. ExecutionStore is a separate trusted-local
runtime path: explicitly register commands with executable and declared file
hashes; actually execute them; retain output hashes and counts in SQLite; count
only successful, unchanged local invocations by project; refuse the bar when
unmet. Alias/repeat suppression uses executable+declared input byte identities,
not tool display names. Pin checks before and after catch tested file changes,
including a dependency symlink retarget before execution.

It uses no shell, a temporary working directory, stripped environment, bounded
capture, monotonic deadlines, a new process session and same-group cleanup.
Registration alone never adds an observed execution. Receipts cannot be
imported through the public API. Independent connections observe committed runs.

## Reproduce

Python 3.12, pytest, and pydantic (runtime package import) are needed:

```sh
PYTHONPATH=backend python -m pytest --noconftest -p no:cacheprovider tests/runtime/guardrails/test_tool_execution_receipts.py tests/runtime/guardrails/test_tool_usage_bar.py -q -rf
python scripts/release/scoped_mutations.py audits/row141-execution-receipts/mutations.json OUTPUT
```

Builder run: 38 passed across these two selectors, of which 28 are the new
receipt selector and 10 are the unchanged attestation selector. Authored local
fixture programs run as actual subprocesses. They are not real external-service
usage, a licensed benchmark or real scientific work. Nine final exact-site
mutations were CAUGHT by failed test IDs with verified byte restores. Initial
accept_timeout mutation SURVIVED; the added zero-exit-parent/live-child-pipes
probe now catches it. Initial and final logs are retained in the delivery bundle.
Missing-module RED was a collection error before implementation, not a failing
behavior assertion; an earlier RED setup run lacked pydantic. Both are retained.

## Remaining scope: PARTIAL

- No 200 external tools executed. No service/API adapters, credentials, provider
  receipts, scientific relevance or usefulness validation. No group closure.
- No universal runtime wiring. Completion callers must explicitly choose
  require_bar; existing outbound/owner approval gates are still required.
- Not a sandbox: local tools have ordinary filesystem and network access.
  Register trusted commands only. A hostile descendant can escape its session;
  killpg is not containment. No network isolation or memory/CPU quota.
- Before/after pins do not close a malicious replacement-and-restore race.
  Imports, libraries, interpreter behavior and undeclared dependencies are not
  pinned. Scripts must be declared by the operator. Inputs affect identity;
  content variations could therefore inflate tool breadth, while tools sharing
  pinned bytes are conservatively conflated. Identity is not semantic tool ID.
- A database writer can forge receipts; no independent signing/verification.
  Receipt output hashes attest captured bytes, not their truth. Successful exit
  does not prove meaningful work. Hashes are for captured output only; on limit
  refusal, the final over-limit chunk is not retained or counted.
- Database persistence after a completed run can fail. Such failure raises and
  never produces an invented receipt. Crash recovery of in-flight work is not
  implemented; side-effecting commands should not be registered here.
- No full-repository regression, signed-in ChatGPT review or independent audit
  was performed by this builder. The patch needs the independent gate.
