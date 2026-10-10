# M20-GA01: actual binary genetic algorithm

Requirement: live feature document title "Genetic Algorithms" (source1977,
ledger1986). Source titles only, no prose description. This unit implements
an actual binary-genome GA, not the old scalar Gaussian mutation substitute.
The old cognitive route/pins remain unchanged as truthful historical/legacy
reference behavior. The new route is `/api/v1/api/modules/20/genetic-algorithms/solve`
and uses the same production auth dependency through Module20's mounted router.

The objective is separable/linear: each bit can be optimized independently,
so the optimum needs no search. Oracle tests demonstrate convergence on this
problem only; they do not prove useful search ability on coupled objectives.
GA02 must add a non-separable objective with exhaustive-oracle checks and random
initialization before original row1986 closure is considered.

The new algorithm evaluates a supplied weighted-bit-sum objective, chooses
parents by tournament selection with replacement, uses one-point crossover,
independent bit-flip mutation, and copies the highest-scoring elite genomes to
the next generation. Seeded execution is deterministic. Generation0 and each
subsequent generation retain exact population/scores, selected parents,
tournament candidates, crossover cut and mutation indices. These are algorithm
state receipts, not hidden chain-of-thought. Objective scores can be independently
recalculated from the supplied weights and genomes.

Limits: binary genomes2..64, populations2..128, generations1..1000, retained
work product at most100000. Seed uint32. Rates finite[0,1], exact binary integers
(no booleans), positive tournament size and at least one elite but fewer than
population size. Missing/malformed/nonfinite inputs or objective overflow refuse.
The algorithm is stochastic search, not a guaranteed global optimizer. Small
fixtures converge to independent exhaustive oracle answers, which cannot prove
convergence on arbitrary problems. No external effects, model, provider or spend.

Ledger row remains PARTIAL pending independent original-capability acceptance.
The legacy scalar route still says unverified. Candidate provides an actual
algorithm implementation and bounded reproduced examples, not proof that all
M20 cognitive rows are complete, or a new AGI claim. Other swarm/evolutionary/
genetic-programming methods retain their prior truthful boundaries.
