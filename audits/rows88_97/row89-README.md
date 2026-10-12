# Row 89 classifier calculation boundaries

Exact selector: tests/modules/test_group89_classifier_boundaries.py,
--noconftest -q -rf, Python 3.12, 40-second timeout per run. Controlled logits
exercise actual sigmoid/scoring/threshold code without loading weights. Five
CAUGHT by FAILED tests: sigmoid calculation, threshold selection, source hash,
real-person refusal and no-personality claim. SHA restored per mutation.

UNTESTED: actual pinned model inference in this selector, calibration, domain
quality, personality/intelligence and human psychology. Historical actual-model
execution remains distinct; this is controlled computation sensitivity only.
Literal row remains PARTIAL. No model download or runtime edit.
