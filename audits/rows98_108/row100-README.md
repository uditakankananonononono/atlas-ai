# Row 100: practice-only scoring and study order

Evidence tier: supplied-input deterministic computation.
No external provider execution or semantic outcome acceptance.

Exact released selector, Python 3.12, repository root:

```sh
PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_c35_practice_engine.py -q -rf
```

Five core mutations specified in row100.json. Run:

```sh
python scripts/release/scoped_mutations.py audits/rows98_108/row100.json OUT
```

45-second timeout per run. CAUGHT requires rc1 plus FAILED IDs, no errors or
skips. Source SHA restored and checked each mutation. Fresh receipt binds
checkout HEAD/tree/status and tracked code/test/spec hashes. Initial non-kills:
weak_first: SURVIVED. Initial logs retained, sensitivities
added before rerun; final five CAUGHT. No runtime source edit.

UNTESTED: Practice only, no live exam assistance or actual awards. Supplied-answer scoring is not real olympiad performance. Whole-repository regression, external dependency truth
and hostile-process containment untested. Direct pytest timeout is not an
escaped-descendant guarantee. Declared source hashes are not semantic truth.
Literal row remains PARTIAL; no admission/award/virality/revenue/coverage victory.
