# Row 138: claim lint and original Unicode offset

Evidence tier: actual local gate code, declared fixture inputs and inert effect
spies. Not live external enforcement or universal runtime adoption.

Exact released selector, Python 3.12, repository root:

```sh
PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/runtime/guardrails/test_claim_lint_gate.py -q -rf
```

Run the five exact-site mutations via:

```sh
python scripts/release/scoped_mutations.py audits/rows134_142/row138.json OUT
```

Per-run timeout: 45 seconds. Current shared runner CAUGHT requires rc1 with
FAILED test IDs and no matched ERROR/collection, Interrupted or skip marker.
Mixed FAILED plus SKIP is INVALID, not CAUGHT. FAILED includes product
KeyError/RuntimeError, not just assertion failures; counts are failure sensitivity.
rc0 with a skipped-count summary is SURVIVED-WITH-SKIPS and does not release
the baseline. Timeouts, process failures without qualifying rc1/FAILED evidence
and invalid sites are not caught. Every
restore is byte-SHA256 verified. External receipts/logs preserve test IDs,
spec/log hashes and actual outcomes. All five final mutations caught in the historical row battery;
this is not a rerun-current claim.
Initial non-kills: original_offset: SURVIVED. Initial receipts
remain retained. Added exact sensitivity or authority tests to the selector
where needed; no runtime guard weakened or changed.

UNTESTED: Closed exact phrases, not implied/paraphrased/image claims; no capability certification. Whole-repository regression, hostile-process containment,
provider truth and global effect interception are untested. Source restore
and direct pytest timeout do not isolate escaped descendants. Literal scope
remains PARTIAL; computed egress labels are declared wiring inventory, never
certification of every path. Development-auth env is local test fixture only.
