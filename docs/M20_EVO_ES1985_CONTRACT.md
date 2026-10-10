# EVO-ES1985: bounded differential evolution

Targets row1985 Evolutionary Computation only for SCOPED acceptance. Implements
DE/rand/1/bin, not a generic evolution-strategy family or all evolutionary
computation. The unit name ES1985 is routing shorthand, not an algorithm claim.
Rows1984/1987/1988 are not closed here. Legacy scalar-Gaussian reference untouched.
New production/OIDC route `/api/v1/api/modules/20/differential-evolution/solve`.

Supplied `data` selects sphere or coupled Rosenbrock objective, dimension bounds,
population_size(default24), generations(default80), mutation_factor(default.8),
crossover_rate(default.7). uint32 seed determines uniform random initialization
and the continuing operator RNG. Each target selects three distinct non-target
vectors from the prior generation; donor is a+F*(b-c), clipped to bounds. Binomial
crossover chooses donor coordinates with probability CR, with one random forced
donor coordinate even at CR0. Every trial is scored; replaces its target iff its
score is no worse. Updates are synchronous, not in-place sequential population
mutation. No benchmark optimum shortcut or caller-supplied scalar aliases.

Receipts include initialized/evolved populations, exact objective scores, donor
indices, clipped mutant, forced/crossed indices, trial and score, acceptance,
best vector and actual evaluation count. Independent tests reconstruct every
operator RNG draw on a seeded fixture with accepted/rejected trials and forced
crossovers, then compare all receipts. Sphere and Rosenbrock small seeded fixtures
converge near known optima, not proof of convergence on arbitrary problems.
Algorithm receipts are formal state, not hidden chain-of-thought.

Bounds:1..16 dimensions, Rosenbrock2+, population4..128, generations1..1000;
(generations+1)*population*dimensions<=100000. Finite positive-width bounds,
F finite(0,2], CR finite[0,1], exact integer sizes/seed, no bools; overflow and
malformed requests refuse422. Actual nested score call count independently
measured, exact generation history and1000/1001 boundary tested. No model,
provider, spend, external execution or persistence. Ledger unchanged until audit.

Residual: arbitrary objectives, discrete encodings, other evolution strategies,
open-ended evolution and unrestricted evolutionary computation not implemented.
