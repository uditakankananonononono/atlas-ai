# M20-MECHANICAL-DESIGN1510-01: bounded exact design-review matrix over supplied declarations

Ledger source pin: `audits/additional-2000-features.json` id 1510,
requirement "Mechanical Design", description "" (verbatim, empty), status PARTIAL,
boundary "Auditable engineering calculations with units, assumptions, standards and
explicit safety limits. Qualified engineers validate materials, loads, tests, tolerances
and certification; Atlas never controls machinery or certifies a design.",
current_scope "Supplied diagnostics/templates only: supplied_requirement_field_coverage.
Not execution of original engineering capability, CAD/solver or physical test."

The ledger description is empty: the requirement title "Mechanical Design" is the
whole spec. Exact behavior proposed by this unit: given a caller-declared mechanical
design requirements set (requirements with optional verification method, acceptance
criterion and load case references; declared load cases; interfaces; units;
assumptions; source refs), compute the exact verification-coverage matrix and summary
over those declarations, deterministically, with bounded input and explicit refusals.

## Delta vs existing mechanism

Existing: `_mechanical` at
`backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:43`
(supplied diagnostics only). It echoes the caller's requirements, load cases and
interfaces and emits a coverage boolean per requirement (`covered` when both
`verification_method` and `acceptance` are truthy) plus the uncovered id list. It
performs no input validation (malformed input is echoed or raises an unclassified
error), has no bounds, no refusal codes, no unknown-reference detection, no
determinism or provenance guarantee.

This unit keeps the cluster's coverage semantics (both fields required; empty string
counts as not provided) and adds: strict validation with row-tagged refusal codes
(`MECHAN1510:` prefix), exact N/N+1 bounds, unknown load case reference refusal,
duplicate detection, dedup of repeated load case references (first occurrence kept),
id-sorted matrix for input-order independence, input-order trace for provenance,
canonical-input SHA-256, explicit boundary/provenance flags. It does not modify the
cluster file and does not mount any route; wiring is a separate integrator patch.

## Interface

`evaluate_design_review(data) -> dict`. Raises `MechanicalDesignRefusal`
(a `ValueError` with `.code` and `.detail`).

Input: `requirements` (1..64 objects; `id` non-empty unique string <=128 chars;
optional `verification_method`, `acceptance` strings <=1024 chars; optional
`load_cases` list of declared load case ids), `load_cases` (0..64 objects; `id`
non-empty unique string <=128 chars; optional `description` <=1024 chars),
`interfaces` (0..64 non-empty unique strings), `units` (object of string labels),
`assumptions`, `source_refs` (lists of strings, <=64 each). Unknown top-level keys
refuse. Every requirement load case reference must name a declared load case.

Output receipt: `row` 1510, `capability`, `scope`
"supplied_design_review_matrix", `status` "evaluation_complete",
`verification_matrix` (id-sorted rows: requirement_id, verification_method,
acceptance, load_cases, covered), `summary` (counts, sorted
uncovered_requirement_ids, referenced/unreferenced load case ids,
requirements_complete), `interfaces`, `input_trace` (source order with input
indices, provenance only), `units`, `assumptions`, `source_refs`, `provenance`
(input_sha256 over canonical sorted-keys JSON; declarations_not_measurements;
computed_not_physically_verified; solver_or_cad_executed false;
physical_test_performed false), `boundary` (requires_engineer_review,
not_a_certified_design, no_machinery_control, verbatim boundary text),
`human_review_required` true. Identical inputs give byte-identical receipts;
matrix and summary are identical under any permutation of the input requirements.

## Refusals (codes are exact)

`MECHAN1510:invalid_input` - non-object input; unknown top-level key; requirements
not a list or empty; requirement not an object; missing/empty/duplicate/non-string
ids; non-string method/acceptance/description when present; malformed load_cases or
interfaces; duplicate load case or interface ids; malformed units.
`MECHAN1510:unknown_reference` - requirement references an undeclared load case id
(message names the id).
`MECHAN1510:resource_limit` - requirements/load_cases/interfaces count 65+;
id over 128 characters; text field over 1024 characters. Exactly at a limit is
accepted; one over refuses.

## Limits

No structural, thermal, fatigue, tolerance or material computation; no CAD/FEA/
solver execution; no physical test; no standards compliance check; no measurement
or prediction; declarations are never validated against the physical world. A
complete matrix means only that every declared requirement carries both declared
verification fields. No route is mounted by this unit. Row 1511 (CAD Modeling) and
row 1513 (Computational Fluid Dynamics) are separate units, untouched here. The
full Atlas suite is not run by this unit's package (targeted suite only);
FULL-SUITE UNVERIFIED.

## Tests

`tests/modules/test_m20_mechanical_design1510.py` (stdlib unittest, runs under
pytest, loads the core by file path): hand-computed known-answer fixture; exact
refusal codes and messages; exact N/N+1 bounds (64/65 counts, 128/129 id,
1024/1025 text); empty-string cluster parity; dedup order pin; permutation
independence with input-order trace; byte-identical determinism with canonical
hash recomputation; 150-case seeded corpus against an independent oracle;
boundary/provenance flags; full receipt shape. Mounted auth/tenant route tests
belong to the integrator after wiring.

## v3 repair addendum (base 8231ce0c)

Validation order (breaking where it differs from the original delivery): for
every field the type/shape check comes first, then the count cap (a len() call,
no iteration), and only then any per-item iteration, dedup or allocation. For
every string: length cap first, then the Unicode check ("no Unicode control,
line/paragraph separator or bidi/format characters"), then aggregate accounting.
every collection field requires the exact container type (type(x) is dict /
list): the top object, requirements, load_cases, interfaces, units,
assumptions, source_refs, nested requirement/load_case objects and
requirement.load_cases refs. Subclasses and wrong containers (tuples included)
are refused as invalid_input before len() or any iteration. Constants: MAX_UNITS_KEYS=32, MAX_UNITS_KEY_LEN=32,
MAX_UNITS_VALUE_LEN=32, MAX_INTERFACES=64 (cross-cite: CAD Modeling 1511 keeps
its own MAX_PARAMETERS=32 shared by its global parameter dict and per-feature
parameter list; 1510 has no parameters field).

The incoming object is never copied. The receipt and the provenance hash are
built only from validated values in fresh containers, so no receipt structure
aliases a caller-owned object and two calls over the same input return
byte-identical receipts.

Refusal reasons are generic and name schema fields only. They never contain a
caller key, value, id, reference, unit label, or any repr of caller content.
Duplicate ids: "duplicate id in requirements" / "duplicate id in load_cases" /
"duplicate id in interfaces". Unknown references: "unknown load case reference
at requirements[<input index>].load_cases". Unknown keys: "unknown key at
<input|requirements[i]|load_cases[i]>".

Provenance: input_sha256 is computed over the canonical JSON of the validated,
normalized fields (keys present in the input; requirement load_cases deduped in
first-seen order). provenance.hash_scope = "validated_normalized_fields". Two
inputs that normalize identically hash identically; the hash does not cover
ignored or dropped input. This differs from a hash over the raw input exactly
when the input carries duplicate references or empty-string optional fields.
