# Row 1279 mounted discovery integration review

Original requirement title: Discovery. It does not define this nested request shape.
The additive `data.discovery` selector and `discovery_bookkeeping` result key are
design choices, not literal owner requirements. Existing generic legal
review output, disclaimer and identity isolation envelope remain unchanged.

The dedicated engine is supplied-input classification bookkeeping, not actual legal
analysis, verified authority, a filing or external action. Row remains PARTIAL.

Independent full app.main HTTP replay on base64f71c1e: two behavioral failures and
seven passing compatibility/identity tests. Patched tree: 130 passed including 121
existing standalone cases and nine dedicated mounted cases. Disabling the new
row dispatch again produces two behavioral failures and seven passes. Source
SHA256 restored exactly. Raw logs are kept with the review package, Development identity headers only, not production OIDC proof.

An initial no-header test incorrectly expected 401. Development mode supplies a
default identity and the route refuses the conflicting body with 403. The final
name and expectation state this exact scoped behavior. The failed initial run is
not counted as product red evidence. No tests were loosened to admit wrong product
behavior; the earlier expectation did not describe this development auth mode.

Unchanged dedicated engine inputs are not fetched or independently verified.
The nested payload carries legal domain data, not another authenticated identity.
Existing wrapper identity mismatch tests reject outer and data tenant/actor claims.
Whole repository, production deployment and independent legal validity untested.
