# Row 107: bounded listing candidate verification

Evidence tier: hermetic local HTTP / parser fixtures.
No external provider execution or semantic outcome acceptance.

Exact released selector, Python 3.12, repository root:

```sh
PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_m01_competition_live.py -q -rf
```

Five core mutations specified in row107.json. Run:

```sh
python scripts/release/scoped_mutations.py audits/rows98_108/row107.json OUT
```

45-second timeout per run. CAUGHT requires rc1 plus FAILED IDs, no errors or
skips. Source SHA restored and checked each mutation. Fresh receipt binds
checkout HEAD/tree/status and tracked code/test/spec hashes. Initial non-kills:
verify: SURVIVED, duplicate: SURVIVED. Initial raw logs are retained in the private archive, not in this patch.
Portable delivered logs and per-log original/delivered SHA256 pairs plus
normalization disclosures are in the separate portable evidence package.
Sensitivities
added before rerun; final five CAUGHT. No runtime source edit.

UNTESTED: Hermetic loopback/fake Fetch only. Reachable-at-run is not authoritative competition eligibility or exhaustive coverage. Whole-repository regression, external dependency truth
and hostile-process containment untested. Direct pytest timeout is not an
escaped-descendant guarantee. Declared source hashes are not semantic truth.
Literal row remains PARTIAL; no admission/award/virality/revenue/coverage victory.

Intermediate r2 baseline was BASELINE-NOT-RELEASED: the added fake Fetch
fixture lacked allow_http (and its expected URL field). No r2 mutations
were credited. The fixture alone was repaired to the loopback configuration;
r3 baseline passed and all five mutants were CAUGHT. Runtime source stayed
unchanged. The failed baseline receipt and normalized delivered log are
retained separately, alongside private originals.
