# Row 95 educational digits split

Exact selector: tests/modules/test_group95_digits_execution.py, --noconftest
-q -rf, Python 3.12, 60-second timeout per run. Actual bundled dataset/model
execution. Five mutations: seed, train-only scaler, heldout fraction, comparator
accuracy and scaling claim. Initial train+test scaler mutation SURVIVED because
metrics alone matched; added an observed scaler.fit row-count test. All five
rerun CAUGHT by FAILED tests. Both receipts retained; SHA restore verified.

UNTESTED: external benchmark datasets, split robustness, novel breakthrough,
sector-wide superiority and repository-wide suite. Centroid loses logistic on
this fixed educational split. Literal row remains PARTIAL; no runtime edits.
