# M04 row 225 repair - box-uncertainty robust counterpart

## Defect
`optimize` row 225 (robust optimization, box uncertainty) evaluated the worst-case
objective only over `_lp_vertices`. The worst case of a linear objective under box
uncertainty, `worst(x) = sum_j nom_j*x_j + rad_j*|x_j|`, is convex piecewise-linear,
not linear. Vertex-only search is valid only for linear objectives over polytopes.
Counterexample (bounded, independently confirmed): coefficients [0,0], uncertainty
[1,1], box [-1,1]^2 - true minimum is 0 at the interior point [0,0]; the old code
returned 2 at a vertex.

## Fix
New `_robust_candidates`: exact candidate set for a convex separable piecewise-linear
objective over a 2D polygon - all feasible vertices, all feasible edge kinks where an
edge line crosses x1 = 0 or x2 = 0, and the unconstrained per-coordinate minimizer
(clamped to the box) when feasible. Row 225 minimizes `worst` over that set. Public
API unchanged: same input keys, same result keys, same `algorithm` prefix
`box_uncertainty_robust_counterpart` (adds informational `search` field). Still 2D,
consistent with the reference solver's stated limit; still raises on infeasible
constraints and negative radii; adds a coefficient-dimension guard.

## Verification
- Regression: the counterexample is a pinned test (best_point [0,0], value 0).
- Property battery: nominal-only (zero uncertainty collapses to the plain LP),
  mixed per-coordinate, weak-dominance pull to zero, flat direction (nom == rad),
  linear-constraint interaction with interior pull.
- Independence: exact results cross-checked against 200k-sample brute force on 8
  randomized cases (exact <= sampled min in all cases).
- tests/modules/test_m04_quant_methods_185_234.py: 105 passed.

## LIMITS
- 2D only, like the rest of this reference optimizer (raises otherwise).
- Exactness claim covers convex separable piecewise-linear objectives over linear
  polytopes; it is a reference computation for specialist review, not a production
  robust-optimization library.
- Pre-existing unrelated failures on base 394fe963 in tests/modules/
  test_m04_research_scientist.py (2 tests) are out of scope for this repair.
