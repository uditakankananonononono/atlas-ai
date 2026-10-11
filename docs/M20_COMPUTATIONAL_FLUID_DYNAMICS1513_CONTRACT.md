# M20 Row 1513 — Computational Fluid Dynamics: Contract

## Ledger source pin (verbatim, audits/additional-2000-features.json, id 1513)

- id: 1513
- requirement: "Computational Fluid Dynamics"
- description: "" (empty)

The ledger description for this row is empty, so the requirement title
"Computational Fluid Dynamics" is the whole specification. Because a title
alone does not define behavior, this contract proposes and pins the exact
behavior below, staying inside the ledger's declared current scope of supplied
diagnostics/templates only.

Ledger boundary (verbatim): "Auditable engineering calculations with units,
assumptions, standards and explicit safety limits. Qualified engineers validate
materials, loads, tests, tolerances and certification; Atlas never controls
machinery or certifies a design."

Ledger current_scope (verbatim): "Supplied diagnostics/templates only:
supplied_mass_flow_balance. Not execution of original engineering capability,
CAD/solver or physical test."

## Mechanism delta (base mechanism this row extends)

Cited mechanism: `backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:60`
(`_cfd`, verified exact on base commit dcab66a2ea4303ea2c763074ef272f3e0cbe17e3).

The cited mechanism sums caller-supplied mass_in and mass_out lists and reports
mass_imbalance_percent = abs(in-out)/max(abs(in),1e-12)*100 with
solver_run_claimed False. Row 1513 turns that flat check into a complete, exact
evaluation. Deltas:

1. Exact rational arithmetic. All rates, totals, shares and the imbalance are
   computed as exact fractions over the declared values and rendered exactly
   (terminating decimals as decimal strings, otherwise "num/den"). No binary
   float enters any result. The cluster's denominator floor
   max(abs(total_in), 1e-12) is preserved exactly as Fraction(1, 10**12).
2. Per-port declarations. The flat lists become declared ports with unique ids,
   direction (in/out) and nonnegative rates; the receipt carries per-port rows
   in declaration order with each port's share of its direction total (null
   when that total is zero).
3. Closure against a declared tolerance. balanced_to_tolerance compares the
   exact imbalance to closure_tolerance_percent (default 5, inclusive at the
   boundary, limited to 0..100).
4. Largest contributors. largest_inflow / largest_outflow name the port with
   the greatest exact share per direction (first declared on ties), null when a
   direction has no ports or a zero total.
5. Refusal taxonomy. Malformed input, invalid directions, negative or
   non-finite rates, duplicate ids, and resource-limit breaches refuse with
   row-tagged codes (COMPUT1513:...) before any evaluation.
6. Provenance. sha256 over the canonical JSON input, plus explicit flags that
   no solver ran and the input is declarations, not a simulation.

Totals, imbalance and closure are order-independent; port_rows and input_trace
preserve declaration order. Pinned by tests.

## Interface

`evaluate_flow_balance(data) -> dict`, module
`backend/app/modules/m20_general_cognitive_worker/computational_fluid_dynamics1513.py`
(standard library only, loaded by file path in tests).

Input object keys: `ports` (required list of 1..64), `closure_tolerance_percent`
(optional, 0..100, default 5), `domain`, `turbulence_model` (optional strings,
max 256 chars), `boundary_conditions` (optional list of max 64 strings). Each
port: `id` (non-empty unique string, max 128 chars), `direction` ("in"/"out"),
`mass_flow_kg_per_s` (JSON number or numeric string, finite, nonnegative).

Result keys: row, capability, scope, status, domain, turbulence_model,
boundary_conditions, port_rows, totals, mass_imbalance_percent,
closure_tolerance_percent, balanced_to_tolerance, largest_inflow,
largest_outflow, summary, input_trace, provenance, boundary,
human_review_required. Every numeric result is an exact-rendered string.

## Refusals (row-tagged)

- COMPUT1513:invalid_input — wrong shapes, unknown top-level key, missing or
  duplicate port id, invalid direction, missing/negative/non-finite rate,
  tolerance outside 0..100 or not numeric.
- COMPUT1513:resource_limit — a declared count or length exceeds its limit
  (ports 64, boundary conditions 64, id 128, text 256).

## Limits

- This evaluates caller-supplied declarations only. No CFD solver runs, no mesh
  is generated, no flow field, turbulence quantity or convergence history is
  computed.
- boundary.requires_engineer_review, boundary.not_a_simulation_run and
  boundary.no_machinery_control are always true; human_review_required is
  always true. Qualified engineers validate models, boundary conditions and
  results; Atlas never controls machinery or certifies a design.

## Tests

`tests/modules/test_m20_computational_fluid_dynamics1513.py` — 16 hermetic
stdlib tests: known-answer fixture, oracle corpus (exact Fraction oracle),
permutation independence of totals, zero-inflow denominator-floor parity,
inclusive tolerance edge, exact rendering (terminating and fraction forms),
shape/port/tolerance refusal strings, refusal prefix pin, N/N+1 pins on port
count (64/65), boundary-condition count (64/65), id length (128/129), text
length (256/257), full receipt boundary/provenance/trace, optional-field
defaults.

## v3 repair addendum (base adccbc0a)

Validation order: for every field the type/shape check comes first, then the
count cap (a len() call, no iteration), and only then any per-item iteration or
allocation. Top-level objects and port objects carry key-count caps
(len(_TOP_KEYS) / len(_PORT_KEYS)) before the allowlist scan; the allowlist
still decides objects whose key count is exactly at the cap. boundary_conditions
checks the count cap before the element-type scan. The uniform numeric rule and
all limits from the repair addendum above are unchanged.

The incoming object is never copied. The receipt and the provenance hash are
built only from validated values in fresh containers, so no receipt structure
(the boundary_conditions list included) aliases a caller-owned object and two
calls over the same input return byte-identical receipts. Custom or hostile
objects (including ones with raising __deepcopy__) are refused as row-tagged
invalid_input, never raw.

Refusal reasons are generic and name schema fields only; they never contain a
caller key, value, id, or any repr of caller content. Duplicate port ids:
"duplicate id in ports".

Provenance: input_sha256 is computed over the canonical JSON of the validated
fields (top-level keys present in the input; port entries carry id, direction,
and the supplied mass_flow_kg_per_s). provenance.hash_scope =
"validated_fields".

## v3 follow-up addendum (numeric digit rule, author FINAL; exact types)

Numeric strings: combined significant digits across whole+fraction after the
first nonzero digit <= 64, AND fractional digits <= 64, applied to EACH token
separately (the number itself and, for p/q forms, the denominator). Replaces
the earlier per-part 64 rule. Check order: raw length (80), then grammar
(shape, invalid_input), then digit counts, then the 1e12 range; size-bound
refusals are resource_limit with the field suffix, no value echo.

Exact container types (type(x) is list/dict) on every collection: the top
object, ports, each port object, boundary_conditions. Subclasses, tuples and
wrong containers refuse as invalid_input before len() or any iteration.
