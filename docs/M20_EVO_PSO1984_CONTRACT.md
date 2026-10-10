# EVO-PSO1984: actual continuous particle swarm

Targets row1984 Swarm Intelligence only for bounded SCOPED acceptance, not
unrestricted swarm intelligence. Does not close1985/1987/1988 or other COG rows.
Legacy scalar Gaussian-mutation reference remains unchanged. New production/OIDC
route `/api/v1/api/modules/20/particle-swarm/solve` accepts `data` and uint32 `seed`.

`objective` selects sphere or nonseparable Rosenbrock minimization. Bounds are
supplied per dimension; no caller code or arbitrary objective runs. Seeded local
RNG independently initializes each particle's position uniformly inside bounds,
then velocity uniformly within +/-10% of each dimension's width. Iterations use
synchronous velocity update: inertia*velocity + cognitive*r1*(personalbest-position)
+ social*r2*(globalbest-position), with fresh independent uniform draws per term,
particle and dimension. Positions advance then clamp inside bounds; clipped
components reset velocity to zero. Personal/global bests update only after the
whole generation is evaluated. This is real PSO, not a GA alias or analytical
optimum substituted for search. Every initialized and updated position is scored.

History retains positions, velocities, scores, personal/global best positions
and scores. Independent draw-by-draw tests reconstruct first and later updates,
including nonzero cognitive correction, synchronous social target and boundary
clamp. Sphere and coupled Rosenbrock seeded benchmark fixtures converge near known
optima, but no global convergence guarantee or arbitrary optimizer claim. A
bounded one-step fixture retains nonzero error rather than fabricating success.
Algorithm states are formal receipts, not hidden chain-of-thought.

Bounds: dimensions1..16 (Rosenbrock2+), particles2..128 default24,
iterations1..1000 default90, (iterations+1)*particles*dimensions<=100000.
Finite bounds must have positive finite width. Inertia0..1 default.7,
cognitive/social0..4 default1.5. Exact integer sizes/seed, no bool numeric inputs.
Nonfinite/overflow/malformed inputs refuse422. Inputs can bound out the optimum;
no feasibility/global-optimum claim. No model/provider/spend/external execution,
no stored swarm state, no multi-agent communications or collective intelligence.

Residual: arbitrary objectives, discrete/heterogeneous/multi-agent swarm tasks
and unrestricted swarm intelligence are not implemented. Candidate ledger stays
unchanged until independent acceptance. Historical reference catalog preserved.
