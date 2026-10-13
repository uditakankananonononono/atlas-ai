# Row105 mounted bounded review

Literal source: requirement "Pre-Suasion", description "Primes attention before persuasion attempt". This patch does not demonstrate that psychology outcome. It mounts the already-existing numeric bookkeeping helper at authenticated `POST /m20/pre-suasion105/review`. No sending, posting, deployment, priming advice, measurement of attention or prediction occurs. Caller disclosure is not independently verified. Literal row remains PARTIAL.

## Released scope

`backend/app/main.py` includes the dedicated router. Both production middleware and router dependency require authentication. Tests use real signed fixture tokens through the production verifier, without changing the middleware or replacing the app with a test router. Review is stateless and tenant repeatability is tested. JSON is capped at 8192 streamed bytes, duplicate object keys and non-finite constants are refused, and helper schema types are preserved without Pydantic coercion. Errors never include supplied values. The existing helper is unchanged.

Base: `64f71c1e2c161cfceca6d279b01c8f6058c7a54d`. Exact mounted selector: `tests/modules/test_row105_mounted.py` (21 cases). Test bytes are identical in red and green. Unpatched extracted source seed: exit1,20 assertion failures due to404,1 authentication PASS. Patched seed: exit0,42P including21 unchanged standalone cases. Same patched current-main selector: exit0,42P. No collection or environment failure is credited as red. No full-suite claim: the baseline failing set covers this dedicated selector only; global regressions remain unverified.

Commands (run from each source root with installed dependencies):

```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/modules/test_row105_mounted.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/modules/test_row105_mounted.py tests/modules/test_m20_pre_suasion105.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python audits/row105-mounted/replay.py OUTPUT_DIRECTORY
```

Mutation result:8CAUGHT,0SURVIVED,0INVALID; baseline21P and restored21P. Every mutated file restored to its original SHA256. Raw receipts retain every FAILED node ID, exit code and log hash. This finite battery tests mount removal, duplicate keys, body cap, refusal status, disclosure, boolean weights, tie retention and media guard. It is not exhaustive or proof of literal priming.

Exploratory failures are retained separately: two deep-valid-JSON fixture attempts incorrectly expected a decoder refusal; the decoder accepted nested arrays and the helper properly refused non-mapping input. The released test uses incomplete deep JSON. Those exploratory failures are not red evidence for this release. Earlier17-case logs are historical and do not substantiate the released21-case selector.

Raw logs and full source-seed/manifest are delivered separately for independent audit. Repository evidence logs are normalized only for private absolute paths and trailing whitespace; normalization pairs record original and delivered hashes. Report is READY-FOR-AUDIT, not auditor PASS or landed. Routing changes must be serialized by the integrator. No pushes or ledger edits were made.
