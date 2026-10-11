# Row 1532 - GD&T: bounded 1D datum tolerance chain

Source pin: `audits/additional-2000-features.json`, id 1532, original requirement
`GD&T`, base `7885256e9791f9eab4239ecab1b8fb7fd4c8787c`. That title is
not evidence of full GD&T. Baseline has only frame-field presence diagnostics.
This package adds a finite signed 1D dimensional chain, not arbitrary geometry.

## API and model

`datum_stack1532.evaluate_stack(packet)` is a pure stdlib operation. Packet has
exactly geometry (`linear_1d`), unit (`mm`, `cm`, `m`, `inch`), datums, components,
and fit_limits. Every record has a unique id within its collection, explicit
matching unit and a nonblank source_ref. No conversion is performed.

Datums: id, offset, unit, source_ref. Components: id, datum, nominal, lower,
upper, sign (integer +1 or -1), unit, source_ref. Fit limits: id, lower, upper,
unit, source_ref. Intervals are absolute local dimension bounds, closed at both
ends, not +/- tolerances. Nominal must lie within its interval.

Each contribution is `sign * (datum_offset + local_dimension)`. Negative signs
reverse interval endpoints. Total nominal and worst-case bounds are exact sums.
Datum translation cancels only when the signed coefficients of translated
references sum to zero; unbalanced stacks translate. Offsets are exact supplied
constants, not uncertain datum errors. Fits are simultaneous constraints on the
same scalar: intersection, never a union. Empty fit intersection or a disjoint
stack has `no_feasible_fit`; containment is `guaranteed_within_declared_limits`;
partial overlap is `not_guaranteed`. No fits means `no_fit_limits_declared`.
A worst-case interval can overbound realizable correlated dimensions; a nonempty
intersection is not a physical feasibility proof.

Outputs use exact rational strings (`1/10`, never rounded binary floats), sorted
record-ID source and fit traces, feature_id 1532, model, unit, nominal/lower/upper,
fit_intersection and fit_status. Traces preserve supplied source_ref and datum
source_ref. References are not authenticated. Caller input is not mutated.

## Refusals and bounds

Strict exact fields refuse accidental unsupported geometric extensions.
Angular/profile/true-position/statistical RSS constructs are unsupported.
Every refusal is ValueError with an exact `GDT1532:` code, including field or id
where applicable. Empty components/datums refused; fit list may be empty.
Each collection <=64 records; text <=128 characters; numeric spelling <=64
characters; magnitude <=10^12; absolute decimal exponent <=18. Finite built-in
ints/floats and decimal strings only; no booleans, NaN, infinity or fraction
strings. Floats mean their Python shortest decimal spelling, not the exact
binary representation. Errors for competing bad records follow sorted IDs.

## Evidence and limits

10 stdlib unittest nodes cover a 62-sign-configuration endpoint enumeration
oracle, analytical signed stacks, translation, multi-datum stacks, permutation,
zero tolerance, exact decimals, disjoint/touching fits, IDs/source traces,
refusals, mutation-free operation, and exact 64/65, 128/129, 64/65 numeric-text,
10^12/(10^12+1), 18/19 exponent boundaries. Eight separately executed core mutants
alter signs, offset, fit intersection, geometry rejection, ordering, bounds,
source trace or nominal sign. Raw receipts are separate artifacts.

Existing base invalid-frame test body was executed directly, plus diagnostic
honesty and adjacent nominal tolerance floors. No existing pytest suite was run.
New core was tested directly without repository conftest/dependency imports.
No model download, external execution, network test, physical inspection,
certification, drawing release or full GD&T claim. No RSS implementation.

Shared dispatcher patch is unapplied and uncommitted. Integrator must resolve
legacy feature_control_frames payload compatibility, diagnostic metadata, mounted
route authentication and cross-tenant tests before integration/publication. Main
and audit ledger remain unchanged. Passing core tests is not audit acceptance.

## Integration compatibility and mounted boundary

Legacy `feature_control_frames` payloads are not converted to 1D dimensional
chains: frame-field presence cannot supply missing geometry/dimensions. They
refuse with `GDT1532:unknown_fields:packet` (mounted HTTP422). The old frame
presence diagnostic is intentionally replaced, not certified or silently coerced.
The mounted engineering route binds authenticated owner/actor and rejects
cross-owner/actor metadata. GDT strips validated transport metadata only before
the strict pure-core packet check. It does not resolve any resource reference.
Pure-core implementation is unchanged from the reviewed R2. Existing engineering
route responses now carry tenant/actor identity; all methods on that route use
the same owner boundary. Public full-GD&T/physical-inspection/release claims stay
false. Permanent audit provenance caveats: R1 local-main branch was misnamed;
the original rename command had no raw receipt.
