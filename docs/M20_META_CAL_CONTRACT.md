# META-CAL: declared-class evidence-backed calibration

Targets row13 Epistemic Humility Calibration for bounded SCOPED acceptance only;
PARTIAL until audit. Existing retrospective CalibrationEngine stays unchanged.
New explicit tenant CalibrationPredictor uses META-DUR CAS snapshots
(kind calibration_predictor) with restart, stale-writer/rollback proof, SQLite
acceptance only. Mounted production/OIDC routes `/calibration-predictor/ingest`
and `/predict` under `/api/v1/api/modules/20` require bound authenticated tenant.

Ingested prediction records have stable prediction_id, declared claim_class,
confidence[0,1], exact boolean resolved outcome, prediction/outcome provenance
identifiers and predicted_at<resolved_at. Duplicate exact record idempotent;
changed identity/provenance/outcome refuses. These are caller-bound identifiers,
not independent verification of author, source or real-world truth. Unresolved,
missing provenance, invalid/nonfinite inputs refuse. No access to withheld labels.

Predict uses only same-class records resolved within inclusive [as_of-30,as_of]
and at least20 in fixed confidence bin (five equal-width bins, final includes1).
Confidence outside observed class-wide support, sparse bin/unsupported class or
expired data abstains with corrected_confidence=None. A binomial model with
Beta(1,1) prior gives posterior mean(successes+1)/(samples+2). This is explicitly
conditional on exchangeable outcomes in that class/bin/window and correct supplied
labels, not a probability invented from generic evidence counts. It does not
establish introspective knowledge boundaries or universal calibrated confidence.
Class-wide support is min/max support, not an OOD detector for unobserved semantic
features; semantic shifts within a class cannot be detected here.

Fixed synthetic miscalibrated class:200 train predictions, separately identified
200 heldout scored predictions. Proper Brier/log loss and binned reliability
improve over raw confidence without heldout ingestion. Changed labels change
estimate. Exact posterior arithmetic/minimum sample support, future labels excluded,
time expiry, class/tenant separation and source traces tested. This is validated
on that declared synthetic claim class, not production truth labels/drift proof.
Sample counts/mismatch counts alone are not epistemic certainty. No model fitting
outside this stated binomial estimator, provider, spend, external label retrieval,
hidden chain-of-thought or other row closure.

Bounded: batch1..1000, total2000 records/tenant, nonempty strings<=240, finite
nonboolean times/confidence. One whole snapshot, no eviction. Caller timestamps
use consistent arbitrary units; window30 uses those units, not assumed wall clock.
Query as_of is explicit, not a trusted current timestamp. Public records mutation
bypasses durability; use ingest. Route invalid422/stale409/unboundtenant503.
Residual: declared validated classes/label sources/time windows only; drift,
external label truth, semantic OOD and all-future-claim calibration not established.
