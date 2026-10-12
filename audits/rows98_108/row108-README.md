# Row 108: owner-recorded agency ledger

Evidence tier: supplied-input deterministic computation.
No external provider execution or semantic outcome acceptance.

Exact released selector, Python 3.12, repository root:

```sh
PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_c36_agency.py -q -rf
```

Five core mutations specified in row108.json. Run:

```sh
python scripts/release/scoped_mutations.py audits/rows98_108/row108.json OUT
```

45-second timeout per run. CAUGHT requires rc1 plus FAILED IDs, no errors or
skips. Source SHA restored and checked each mutation. Fresh receipt binds
checkout HEAD/tree/status and tracked code/test/spec hashes. Initial non-kills:
payment_amount: SURVIVED, total: INVALID-SITE. Initial raw logs are retained in the private archive, not in this patch.
Portable delivered logs and per-log original/delivered SHA256 pairs plus
normalization disclosures are in the separate portable evidence package.
Sensitivities
added before rerun; final five CAUGHT. No runtime source edit.

UNTESTED: Owner-recorded payment arithmetic only. No outreach, charging, real collected revenue, business outcome or authenticated approval. Whole-repository regression, external dependency truth
and hostile-process containment untested. Direct pytest timeout is not an
escaped-descendant guarantee. Declared source hashes are not semantic truth.
Literal row remains PARTIAL; no admission/award/virality/revenue/coverage victory.
