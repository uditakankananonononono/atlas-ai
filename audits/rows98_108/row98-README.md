# Row 98: supplied essay rubric

Evidence tier: supplied-input deterministic computation.
No external provider execution or semantic outcome acceptance.

Exact released selector, Python 3.12, repository root:

```sh
PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_m23_essay_excellence.py -q -rf
```

Five core mutations specified in row98.json. Run:

```sh
python scripts/release/scoped_mutations.py audits/rows98_108/row98.json OUT
```

45-second timeout per run. CAUGHT requires rc1 plus FAILED IDs, no errors or
skips. Source SHA restored and checked each mutation. Fresh receipt binds
checkout HEAD/tree/status and tracked code/test/spec hashes. Initial non-kills:
none. Initial logs retained, sensitivities
added before rerun; final five CAUGHT. No runtime source edit.

UNTESTED: No prose generation, admission or scholarship prediction, or independent judging of essay excellence. Whole-repository regression, external dependency truth
and hostile-process containment untested. Direct pytest timeout is not an
escaped-descendant guarantee. Declared source hashes are not semantic truth.
Literal row remains PARTIAL; no admission/award/virality/revenue/coverage victory.
