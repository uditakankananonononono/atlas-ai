# Row 1512: Finite Element Analysis

Original ledger: `audits/additional-2000-features.json`, row `1512`, requirement
`Finite Element Analysis`, source document ID
`1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY`.
This pins the exact ledger title, not proof of full capability or a fresh read of
that source document. Baseline is PARTIAL and compares supplied mesh results;
it has no axial displacement solver. No ledger or acceptance status is changed.

## Accepted bounded computation

`solve_axial_bar(data)` computes a supplied, finite 1D axial linear-elastic bar.
No 2D/3D, geometric/material nonlinearity, contact, dynamic analysis, thermal
strain, beam bending, inferred loads, constitutive fitting, safety certification,
physical validation or machine control. Engineer review is required. Supplied
references are echoed, not authenticated. There are no network calls or effects.

Input is a dict with exactly these permitted top-level keys:
- `model`: `1d_axial_linear_elastic`
- `units`: exactly `{length: m, force: N, modulus: Pa, area: m^2}`.
  Displacements are m, strains dimensionless, stresses Pa, energy N m.
  No unit inference/conversion. Unknown or incompatible unit labels refuse.
- `nodes`: 2..64 `{id: unique nonempty string, x: finite number}`.
- `elements`: 1..128 `{id: unique string, nodes: [node_id, node_id],
  E: positive finite Pa, A: positive finite m^2}`.
- `loads`: list of unique known `{node, force}`. Empty is allowed, missing is
  not. Unlisted nodes have zero applied load; duplicates are not silently added.
- `displacements`: list of unique known `{node, value}`. Every disconnected
  component, including isolated nodes, needs an anchor or refuses as singular.
- `source_refs`: optional list of at most 128 strings, each at most 2048 chars.

IDs at most 128 chars. Boolean/string numeric values refuse. Input absolute
numeric magnitudes at most 1e100. Elements require distinct nodes at distinct
coordinates. Parallel elements and disconnected independently anchored components
are allowed. Reversed connectivity is canonicalized by position then ID.
Unknown top-level geometry fields refuse instead of being ignored. Residual: nested
unknown fields (inside nodes, elements, loads or displacements) are ignored, not refused;
thermal strain is not modeled and an unmodeled field is not detected.

Assembly adds `EA/L * [[1,-1],[-1,1]]`. Displacement constraints eliminate fixed
DOFs with `f_free - K_free,fixed u_fixed`. Scaled partial-pivot elimination
rejects pivot ratios <=1e-12. No artificial stabilizer or pseudoinverse. That
threshold can refuse strongly ill-conditioned but mathematically valid models.
Overflow, underflowed zero stiffness, nonfinite results or free equilibrium
residual above `1e-8 * max(1, |f|, |K u|)` refuse. Not a certified numerical
error bound; large rigid offsets can suffer cancellation. Known limit: with a prescribed
displacement of 1e15 on a unit test bar, the reported stress is 2.5 where exact
arithmetic gives 2.0, with no refusal. A wrong answer can occur without refusal in
this regime; engineer review is required.

Sorted deterministic output: node displacement/reaction/restraint, element
length/strain/stress/axial force, strain energy, external half-work including
support work, free-DOF equilibrium residual, signed global force balance,
model/units/source refs and explicit safety boundary. Reactions are `K u - f`
on restrained nodes, zero elsewhere. Strain is `(u_right-u_left)/L`, stress is
`E strain`. Energy is sum `0.5 EA/L (delta u)^2`. No input mutation.

## Exact refusals

All public refusals are ValueError with one exact message:
`FEA1512_INPUT`, `FEA1512_MODEL`, `FEA1512_UNITS`, `FEA1512_BOUNDS`,
`FEA1512_NODE`, `FEA1512_ELEMENT`, `FEA1512_MATERIAL`, `FEA1512_LOAD`,
`FEA1512_BC`, `FEA1512_SOURCE`, `FEA1512_SINGULAR`, `FEA1512_NUMERICAL`.
Validation order is input/model/units/bounds/nodes/elements/loads/BCs/component
anchors/source refs/numerics. Multiple invalid inputs get the first error, with one
exception: element stiffness `E*A/L` overflow, underflow to zero or non-finite is
checked at the ELEMENT stage (while elements are read), so it is reported as
`FEA1512_NUMERICAL` before any later load, BC, anchor or source error. The final
numerics stage covers only the pivot test, overflow in assembly or results, and the
equilibrium residual.

## Verification and integration boundary

Stdlib unittest tests independently check uniform, two-element/nonuniform,
compression, prescribed/nonzero BCs, restrained loads, parallel elements,
independently anchored components, global equilibrium and energy identity.
Smooth refinement oracle: EA=1, constant body force 2 represented by supplied
consistent nodal loads, u=2x-x^2; midpoint interpolation error quarters as mesh
size halves. Body-force assembly itself is not an implemented capability.
Serial analytic enumeration: 36 mesh/material/load combinations. Exact bounds
64/65 nodes and 128/129 elements, type/unit/connectivity/singularity refusals.
Independent mutations cover off-diagonal sign, BC elimination sign, reaction
sign and stress material multiplier. Raw receipts are in the review archive.

The existing dispatcher and mounted authenticated tenant routes are UNCHANGED.
A separate unapplied patch offers optional routing for explicitly model-tagged
inputs; legacy supplied diagnostics stay available. Integration owner must
apply/review wiring, run existing engineering tests and mounted route tenant/auth
checks, and decide title acceptance. No mounted/auth verification was run here,
no full repository suite, and no claim this package is a user-visible capability.
