# Row 1546: supplied vibration modal calculation

## Source and scope

Original extra Doc: `1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY`, title "Category 1: Executive Function & Meta-Cognition (100 features)". Live export contains "Vibration Testing" between "Environmental Testing" and "Shock Testing". This verifies the feature name, not a numeric row or a detailed modal specification. Row 1546 is the engineering range mapping and package assignment.

`analyze_modal(data)` performs a calculation on supplied 1 or 2 degree-of-freedom linear undamped matrices. It does not perform a physical vibration test, measure a specimen, verify a supplied source, certify a structure, or authorize release. No model downloads, hardware, network, persistence or external effects.

## Inputs and numerical boundary

Required: request_id (nonblank string, maximum 128 characters), model="linear_undamped", units exactly {mass: "kg", stiffness: "N/m"}, mass_matrix and stiffness_matrix as matching 1x1 or 2x2 lists. Optional: measurements and tolerance_hz. Unknown fields are refused, including damping and nonlinear flags even when false. Numeric values must be int or float, never bool or numeric strings, finite and at most 1e12 in magnitude. Matrix scale must be at least 1e-12; both matrices must be exactly symmetric, positive definite, and have minimum/maximum eigenvalue ratio greater than 1e-12. Outside this numerical domain is refused, not regularized.

Matrices need not be diagonal. Cholesky whitening gives A=L^-1 K L^-T. A symmetric 2x2 eigensolve gives eigenvalues, then phi=L^-T y. Modes are sorted by ascending eigenvalue. Repeated eigenvalues use whitened coordinate basis deterministically. Returned shapes have phi^T M phi=1. Largest absolute component is positive; first index within a relative 1e-12 near-tie wins. Residual is ||K phi-lambda M phi||2. Relative residual divides that norm by ||K phi||2+|lambda| ||M phi||2; a nonfinite residual or value above 1e-8 is refused. omega=sqrt(lambda); frequency=omega/(2 pi).

Measurements are zero to DOF-count records, exactly mode_id, frequency_hz, source_ref. IDs are unique integers in 1..DOF-count. Frequencies are positive Hz; source_ref is nonblank, maximum 256 characters, provenance supplied but not authenticated. Nonempty observations require explicit finite nonnegative tolerance_hz. Inclusive absolute comparison: |measured-calculated| <= tolerance. No automatic nearest-mode pairing. Comparisons sorted by mode_id regardless of observation input order. Unmeasured modes are listed, never invented. Comparison agreement is not model validation or physical certification. No conversion of incompatible units.

## Delivery and integration

Only the new core, tests and this contract are in the review commit. Separate row1546 wiring patch is unapplied in this branch. It replaces the old PSD diagnostic dispatch with supplied modal calculation and adds principal-bound checks on the engineering leaf route. It preserves named_capability_executed=false and distinguishes modal_calculation_executed=true. Legacy PSD callers require explicit migration, not silent reinterpretation. Integrator must decide schema migration and run whole-app regressions. No ledger status changes.

## Verification limits

Standalone analytic/refusal tests avoid the package's eager service import. Mounted checks run the actual engineering leaf router and actual require_tenant in a disposable wired tree with a controlled verifier producing claims; they do not verify OIDC signatures or boot the full app. Base domain floor executes an exact copy of the base engineering test source outside its dependency-heavy conftest, using actual base core/leaf router with namespace import isolation. Full app boot and full repository regression remain unverified. Raw attempts and their outcomes are retained, including an invalid initial missing-dependency RED and a redundant equivalent normalization mutant. Acceptance evidence is self-reported and must be independently reproduced before integration.
