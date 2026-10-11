# M20 Row 1511 — CAD Modeling: Contract

## Ledger source pin (verbatim, audits/additional-2000-features.json, id 1511)

- id: 1511
- requirement: "CAD Modeling"
- description: "" (empty)

The ledger description for this row is empty, so the requirement title "CAD
Modeling" is the whole specification. Because a title alone does not define
behavior, this contract proposes and pins the exact behavior below. The
behavior was chosen to be an exact, auditable extension of the mechanism the
ledger itself cites (see Delta), staying inside the ledger's declared current
scope of supplied diagnostics/templates only.

Ledger boundary (verbatim): "Auditable engineering calculations with units,
assumptions, standards and explicit safety limits. Qualified engineers validate
materials, loads, tests, tolerances and certification; Atlas never controls
machinery or certifies a design."

Ledger current_scope (verbatim): "Supplied diagnostics/templates only:
supplied_feature_reference_order_check. Not execution of original engineering
capability, CAD/solver or physical test."

## Mechanism delta (base mechanism this row extends)

Cited mechanism: `backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:47`
(`_cad`, verified exact on base commit dcab66a2ea4303ea2c763074ef272f3e0cbe17e3).

The cited mechanism performs an order-based reference check over a supplied CAD
feature list and reports `regeneration_ready`. Row 1511 turns that check into a
complete, exact evaluation. Deltas:

1. Exact deterministic regeneration order. When a feature tree has no
   reference findings, the module returns the exact topological regeneration
   order (Kahn's algorithm, lexicographic tie-break), not only a ready flag.
   When findings exist, the order is null and ready is false.
2. Reference findings, enumerated. Self-references and forward references are
   reported individually with feature, kind, and reference, in declaration
   order, instead of collapsing into a boolean.
3. Declared-parameter usage. Declared parameters are echoed, each feature's
   parameter names are validated against them, and the summary lists used and
   unreferenced parameters.
4. Refusal taxonomy. Malformed input, unknown references, unknown parameter
   names, and resource-limit breaches refuse with row-tagged codes
   (CADMOD1511:...) before any evaluation. Duplicate feature ids refuse.
5. Provenance. sha256 over the canonical JSON input, plus explicit flags that
   no geometry kernel ran and no regeneration was performed.
6. Tree order is semantic. Evaluation is order-sensitive by design; the
   declaration order defines what a legal backward reference is. Pinned by
   test.

## Interface

`evaluate_feature_tree(data) -> dict`, module
`backend/app/modules/m20_general_cognitive_worker/cad_modeling1511.py`
(standard library only, loaded by file path in tests).

Input object keys: `features` (required list) and `parameters` (optional
object of string values). Each feature: `id` (non-empty string, unique, max
128 chars), `references` (optional list of feature ids, max 64 entries),
`parameters` (optional list of parameter names declared in the top-level
parameters object). Limits: 64 features, 64 declared references per feature
(counted before dedup), 32 parameters (one shared MAX_PARAMETERS = 32: the
global parameters object holds at most 32 keys and each feature's parameters
list holds at most 32 entries; parameter keys raw cap 32 checked first,
values cap 32).

Result keys: row, capability, scope, status, feature_rows (input order),
reference_errors, regeneration_order (list or null), regeneration_ready,
summary (counts, parameters_declared/used/unreferenced), input_trace,
parameters (echo), provenance, boundary, human_review_required.

## Refusals (row-tagged)

- CADMOD1511:invalid_input — wrong shapes, unknown top-level key, empty or
  duplicate feature id, malformed references/parameters lists.
- CADMOD1511:unknown_reference — a reference names no feature in the tree.
- CADMOD1511:unknown_parameter — a feature names an undeclared parameter.
- CADMOD1511:resource_limit — a declared count or length exceeds its limit.

## Limits

- This evaluates caller-supplied declarations only. No geometry kernel runs,
  no CAD file is parsed, no model is regenerated, no drawing is released.
- The regeneration order is an evaluation artifact over declared references,
  not a rebuilt model.
- boundary.requires_engineer_review, boundary.not_a_released_model and
  boundary.no_machinery_control are always true; human_review_required is
  always true. Qualified engineers validate geometry, tolerances and
  certification; Atlas never controls machinery or certifies a design.

## Tests

`tests/modules/test_m20_cad_modeling1511.py` — 16 hermetic stdlib tests:
end-to-end fixture vs oracle corpus, reference findings in declaration order,
self/forward reference kinds, unknown reference and unknown parameter
refusals, duplicate-id refusal, N/N+1 pins on feature count (64/65),
reference count (64/65), parameter count (32/33), id length (128/129),
dedup-before-count boundary, topological order exactness on a clean tree,
null order on findings, parameter usage summary, provenance hash and flags,
boundary flags, order-sensitivity pin.

## v3 addendum (validation order, caps, hash scope; FINAL author parameter table)

Every collection requires the exact container type (type(x) is list/dict)
BEFORE len(); the count cap runs BEFORE any iteration, dedup or allocation.
The incoming object is never copied: the receipt and the provenance hash are
built only from validated values in fresh containers. Refusal reasons are
generic and name schema fields only - never a caller key, value, id,
reference or parameter name.

FINAL author parameter table: MAX_PARAMETERS = 32 is ONE shared number with
two checks - the global parameters object holds at most 32 keys and each
feature's parameters list holds at most 32 entries. Global parameter keys are
strings with a raw cap of 32 checked FIRST (before Unicode and aggregate);
values keep the existing 32-char cap. Cross-cite: row 1510 keeps
MAX_UNITS_KEYS=32 / MAX_UNITS_KEY_LEN=32 / MAX_UNITS_VALUE_LEN=32 and
MAX_INTERFACES=64; 1510 has no parameters field.

Canonical hash scope: validated fields only - present keys (absent optional
fields are dropped), duplicate references/parameters deduped; aggregate
string-leaf budget 200000 over all validated strings.
