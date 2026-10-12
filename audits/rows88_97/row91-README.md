# Row 91 image metadata and refusal boundaries

Exact selector: tests/modules/test_group91_metadata_boundaries.py, --noconftest
-q -rf, Python 3.12, per-run timeout 40 seconds. Five CAUGHT by FAILED tests:
model drift, flagged safety refusal, PNG AI label, exact output hash and no
realism-validated claim. SHA restores checked. Uses an explicitly mocked
pipeline and generated blank fixture pixels, not a new inference result.
No runtime edit. Fixture image is never substituted for the historical SD1.5
output or described as product inference.

UNTESTED: new actual SD1.5 execution, model safety quality, visual fidelity,
realism and full-repository regressions. Historical inspected output remains
pseudo-text/brand-like and distorted; literal row stays PARTIAL. Metadata and
refusal evidence does not validate image quality.
