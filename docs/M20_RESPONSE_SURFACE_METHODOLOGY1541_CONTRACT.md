# Row 1541: Response Surface Methodology supplied-input bookkeeping

Ledger source: audits/additional-2000-features.json id1541, requirement "Response Surface Methodology", description "", status verified-pushed at live fetched base 0ca1bbeeade1b23d4b2944cb2a28c307c8cab77b. Ledger SHA256 285cc16c474215b241383fb922c8a2f2abfa9f7cda3592b04dc61141317d83ff. The description is empty: the title is the whole ledger spec. Historical status is not independent execution proof or closure.

Delta vs backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:201: _rsm evaluates supplied float polynomial coefficients and labels output predicted_response. This standalone module instead constructs an exact quadratic design matrix from supplied points/responses, computes rational Gaussian-elimination rank and residual degrees of freedom, and response sum/mean. It does not fit coefficients, optimize or predict. Existing cluster, ledger and routes untouched. Three new files only, PREP-only.

## Exact contract

Exact one-to-eight factors; one-to100 points, exactly matching rational-string responses, strict point schema. Terms are intercept, linear, squared and pairwise interaction. Rational components <=1000000 with <=7digits, signed ASCII numerator and positive denominator; no floats. Rank is exact algebraic bookkeeping, not experimental suitability or physical validity. Common names/IDs are nonblank control-free strings1..100 characters. Refusals use exact row prefix and stable codes. Output has release_authorized=false and physical_validity_verified=false, no external effects. No artificial confidence or certification introduced.

## Executed evidence

Six hermetic stdlib tests on Python3.10.12; initial missing-module RED saved, then GREEN. N/N+1 pins for applicable list/text/numeric bounds. Real deterministic output is synthetic supplied-input bookkeeping, not a physical experiment. Builder NEW scratch mutant battery and classifications are supplied; independent mutant adjudication remains REQUIRED before landing and was not performed by this builder. FULL-SUITE UNVERIFIED. No acceptance, landing or closure claim.

## Limits

Exact one-to-eight factors; one-to100 points, exactly matching rational-string responses, strict point schema. Terms are intercept, linear, squared and pairwise interaction. Rational components <=1000000 with <=7digits, signed ASCII numerator and positive denominator; no floats. Rank is exact algebraic bookkeeping, not experimental suitability or physical validity. No physical solver, instrumentation, measurement validation, experiment execution, optimization, predictive engineering, certification or release authority. Exact algebra/arithmetic is not evidence that a real design is safe, robust or reliable. No full ledger-title fulfillment claimed. No auth/tenant integration or existing cluster suite run. Constants/schema are local bounded contracts, not industry standards.

LIMIT (documentation only, no new refusal): factor labels are arbitrary validated text, so term_names may collide with generated labels. A factor named "1" can share the intercept label; a factor named "a*b" can share an interaction label when factors "a" and "b" also exist. Matrix columns remain positional and exact rank uses the matrix rather than label uniqueness. Do not treat term_names as unique dictionary keys. Colliding term_names are accepted as duplicate-named columns; matrix rank is correct. Name validation is unchanged.

Raw-cap allocation hardening: text performs strict str guard, raw length100 check, then strip/control scan. Rational performs strict str guard, raw length16 check, then regex/lstrip/split/component checks/Fraction parse. Raw cap16 covers the prior maximum accepted signed7digit/7digit rational; oversize malformed input now gets the raw-cap refusal earlier. This is hardening, not a vulnerability claim. Cap+1 and10MB refused before scans/regex; no new physical claims.
