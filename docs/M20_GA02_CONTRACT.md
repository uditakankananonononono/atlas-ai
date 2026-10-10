# M20-GA02: coupled-objective binary genetic search

Targets row1986 "Genetic Algorithms" only. Does not close1984/1985/1987/1988,
which require COG-1960 original capability work. Does not close other M20 rows.
GA01's weighted-bit route and result shape remain unchanged. The new production
OIDC-authenticated route is `/api/v1/api/modules/20/genetic-algorithms/solve-quadratic`.

Input `data` supplies `weights` and `interactions`: `[i,j,coefficient]` triples
of distinct bit indices. Objective is sum(weights[i]*bit[i]) plus
sum(coefficient*bit[i]*bit[j]). Nonempty, nonzero interactions make this a coupled
objective, not the separable GA01 problem. Duplicate pairs, including reversed
pairs, refuse. The user supplies the objective; this is not objective discovery.

`population_size` (default32) starts independent uniformly random bits from the
supplied uint32 seed. No caller-supplied population is accepted on this route.
Initialization and the GA use one advancing local RNG. Same seed/input repeats
exactly; changing seed changes initialization and search lineage. The same GA01
core performs actual tournament selection, one-point crossover, independent
bit-flip mutation and top-k elitism. Every score uses the coupled objective,
including tournaments and elite ranking. No exhaustive oracle or optimum hint
runs in the solver. Small test fixtures independently enumerate their oracle.

The deceptive six-bit fixture has all-negative one-bit improvements from zeros
and a positive global all-ones optimum. Ten seeded runs match that exhaustive
oracle; several start without the optimum and discover it later. A second fixture
has mixed positive and negative pair interactions. These are reproduced bounded
search examples, not a guarantee of convergence on arbitrary coupled problems.
`global_optimum_guaranteed` remains false. Generation receipts retain exact
population, scores, tournaments, selected parents, crossover cut and mutation
positions. These are algorithm state, not hidden chain-of-thought.

Bounds: bits2..64, population2..128, generations1..1000; retained product
(generations*population*bits)<=100000; evaluated quadratic work product
((generations+1)*population*(bits+terms))<=1000000. Rates and weights must be finite,
booleans are not exact numeric inputs, and overflow refuses. At least one elite
but fewer than population, positive bounded tournament size, same GA01 defaults.
Missing or malformed inputs return422 on the route. No model, API, spend,
external execution or durable search storage. General optimizers, genetic
programming and other evolutionary/swarm methods are outside this unit.

This candidate fills GA02's specified residual gap for row1986 only, pending
independent original-capability audit. Ledger stays PARTIAL until accepted;
tests alone do not promote a row. GA01 legacy/reference catalog remains intact.
