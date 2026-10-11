# Row 1458: declared-parameter knowledge tracing

## Scope and provenance

Incremental replacement proposal for the SCOPED row1458 arithmetic at remote base
7885256e9791f9eab4239ecab1b8fb7fd4c8787c. This is not a from-zero implementation,
a fitted model, verified learner mastery, psychometrics, or whole-education closure.
The original feature source is Google document
1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY. Its live exported HTML on
2026-10-11 had SHA256
b4e486e6e39c3b3d43069f7215cb51713576e8016cbcf5f6d8ff8c299d6e386e and listed
Student Modeling, Knowledge Tracing, Affect Detection consecutively. The source
list supplies the feature name, not this mathematical acceptance contract.
`audits/additional-2000-features.json`, row1458, is the pinned row identification;
that shared ledger remains unchanged. The package request supplies the bounded
conditional-calculation requirements.

## Inputs

`trace(payload, tenant_id=authenticated_tenant, actor_id=authenticated_actor)` is
pure and stateless. Exactly four top-level fields are accepted:

- `source`: title and http(s) URL. References are preserved, never fetched.
- `sources`: 1..128 source-ID to nonempty citation-text declarations.
- `parameters`: 1..64 skill-ID objects with exactly prior, learn, guess, slip,
  source_id. All four probabilities must be finite int/float values in [0,1].
  Booleans, numeric strings, missing/default parameters and unknown refs refuse.
- `attempts`: 0..512 objects with exactly attempt_id, tenant_id, learner_id,
  skill, correct, occurred_at, source_id. Correct is an exact boolean scored by
  the caller. IDs are nonempty unpadded strings <=256 characters; source titles,
  URLs and citation text are <=2048 characters. Control characters refuse.

Timestamps use ISO dates with T, seconds, optional 1..6 fractional digits, and Z
or numeric timezone offsets. Histories are independently keyed by learner and
skill within the authenticated tenant. Every attempt must match that tenant.
Each history must arrive in strictly increasing UTC time: ties, equivalent-offset
ties and reversals refuse, never silently sort. Different histories may interleave.
Attempt IDs must be unique across the whole request, even for identical repeats.
Unknown fields, unscored events and undeclared skills refuse. All evidence validates
before any history is returned. Parameter/source records are copied in output.
Actor identity is supplied by the authenticated caller, not inferred from learner IDs.

## Calculation and abstention

For prior state p, declared guess g, slip s, learning l and score y, observation
likelihood is `p*(1-s)+(1-p)*g` for correct, or `p*s+(1-p)*(1-g)` for incorrect.
The posterior is respectively `p*(1-s)/likelihood` or `p*s/likelihood`.
Only after the observation is learning applied: `q = posterior+(1-posterior)*l`.
Next-attempt success is `q*(1-s)+(1-q)*g`. The next observation uses q as prior.
Every step records original/UTC timestamp, attempt/source IDs, score, prior,
likelihood, posterior, after_learning and predicted_success_next. No rounding is
applied to numerical results. IEEE float arithmetic is used, not arbitrary precision.

No scored attempts returns abstained/no_scored_attempts, no prediction. One scored
attempt permits arithmetic only; it establishes neither fit nor learner validity.
Zero floating-point likelihood stops that history and returns abstained with failed
attempt/source/time, null final posterior/state/prediction, and the valid prefix.
Underflow to zero also abstains; extremely small evidence is not certified exact.
Other histories may continue, yielding partial_abstention. A prior fallback is never
used for impossible evidence. Earlier prefix predictions are not revised by later data.

## Integration and comparison with the existing row

The new core, new tests and this contract are the only repository additions.
The separately delivered education.py patch is UNAPPLIED in the author checkout.
It intercepts row1458 in the existing scoped wrapper and converts package errors to
EducationError, preserving existing authentication/tenant route behavior. The peer
integrator must review/apply it. Row1457 and all other rows stay unchanged.

Existing row1458 already did observation-then-learning using four example/default
parameters. This proposal removes default/partial parameters and legacy event inputs
for row1458, adds exact chronology/duplicate/schema/source/tenant validation, exposes
posterior and next-success histories, and abstains on zero-likelihood evidence instead
of retaining the prior. This is intentionally a row1458 schema break: old assertions
that expect defaults or mastery_probability must migrate. No compatibility claim is
made. The original SCOPED residuals remain: no fitting, independent learner mastery
validation, field efficacy evidence, high-stakes use, forgetting model, mental-state
inference, independently authenticated score provenance, or real-world calibration.

## Validation interpretation

Exact rational latent-path fixtures and zero/one boundaries test the arithmetic.
Synthetic heldout fixed-parameter learners compare prefix-only Brier error with a
frozen prior. This validates conditional arithmetic under a known generating process,
not real learners or fitted prediction quality. Mounted integration tests use the
existing education router and real RS256 test identities with cached test JWKS, not
network auth. They require KTRACE_WIRING_TEST=1 and the separate patch, otherwise skip.
The full production application import and whole repository suite are outside this
package's verified result. Base/wider comparison must report intentional legacy
row1458 failures separately from any other regression. No package evidence changes
the shared ledger's SCOPED status automatically.

Unicode text-helper boundary: no Unicode control, line/paragraph separator or bidi/format characters. The length cap is checked before Unicode scanning; refusals name the field, never its value. Cc, Zl, Zp, DEL, U+200B-200F, U+202A-202E, U+2066-2069 and U+FEFF are refused. Ordinary internal spaces and printable non-ASCII are allowed. Existing blank-text and outer-whitespace rules are unchanged.

Unicode text-helper boundary: no Unicode control, line/paragraph separator or bidi/format characters. After the string-type guard, raw length is checked before strip, Unicode scan or copying. RAW length is the cap; oversize raw strings are refused, including a 10MB probe, without calling strip. This order changes oversize error precedence but does not widen the cap. Cc/Zl/Zp and the named bidi/format ranges are refused. Internal spaces and printable non-ASCII are allowed; existing outer-whitespace rules remain unchanged.
