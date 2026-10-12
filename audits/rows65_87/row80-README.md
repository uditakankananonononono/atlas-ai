# Row 80: scoped mutation sensitivity

Evidence tier: exact supplied rational polynomial computation only.
Literal requirement remains PARTIAL. No provider/real-world outcome acceptance.

Exact selector (Python3.12):

```sh
PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTEST_PLUGINS=pytest_asyncio.plugin python -m pytest --noconftest tests/mission_build/test_math_strategy.py -q -rf
```

Five core operators in row80.json,60seconds direct pytest timeout each.
CAUGHT means rc1 plus FAILED test IDs without matched ERROR/collection/skip
markers. Runtime exceptions may qualify; not assertion-only proof. Every
source restore is SHA checked. Fresh receipts record checkout and tracked
source/test/spec hashes; not dependency/authenticity attestation.

Initial nonkills: none.

Initial raw logs/receipts remain private. Portable gate package provides
delivered logs, per-log original/delivered SHA256 pairs and every changed
line/path-root mapping. Originals are not part of the public patch.
Later corrections/reruns do not erase initial survivors or failed baselines.

UNTESTED: whole-repository regression, live provider effects, external
dependency truth, semantic quality and literal universal claims. Direct
pytest timeout is not escaped-descendant containment. Fixture owner/review
labels are synthetic, not real user authority. No runtime module changed.
