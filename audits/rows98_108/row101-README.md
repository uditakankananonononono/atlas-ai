# Row 101: portfolio ZIP preview constraints

Evidence tier: local filesystem mechanics.
No external provider execution or semantic outcome acceptance.

Exact released selector, Python 3.12, repository root:

```sh
PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_m23_common_app_preview.py -q -rf
```

Five core mutations specified in row101.json. Run:

```sh
python scripts/release/scoped_mutations.py audits/rows98_108/row101.json OUT
```

45-second timeout per run. CAUGHT requires rc1 plus FAILED IDs, no errors or
skips. Source SHA restored and checked each mutation. Fresh receipt binds
checkout HEAD/tree/status and tracked code/test/spec hashes. Initial non-kills:
honors: SURVIVED. Initial raw logs are retained in the private archive, not in this patch.
Portable delivered logs and per-log original/delivered SHA256 pairs plus
normalization disclosures are in the separate portable evidence package.
Sensitivities
added before rerun; final five CAUGHT. No runtime source edit.

UNTESTED: No original personal portfolio inspected, submission or identity attestation. Constraint constants are local assumptions, not current policy verification. Whole-repository regression, external dependency truth
and hostile-process containment untested. Direct pytest timeout is not an
escaped-descendant guarantee. Declared source hashes are not semantic truth.
Literal row remains PARTIAL; no admission/award/virality/revenue/coverage victory.
