# EVO-GP1987: expression-tree genetic programming

Targets row1987 Genetic Programming only for bounded SCOPED acceptance. No
1984/1985/1988 or other COG row promotion. Legacy supplied-polynomial candidate
selection stays separate. Production/OIDC route
`/api/v1/api/modules/20/genetic-programming/solve` accepts `data` and uint32 `seed`.

Actual random expression trees use single variable x, integer initial constants
-2,-1,0,1,2 and binary add/subtract/multiply. Given aligned supplied x/y training
samples, evaluates tree predictions and mean squared error. No caller-supplied
coefficient candidate bank, target-specific built-in expression, or analytical
optimum. Tournament selection minimizes fitness; crossover picks subtrees in
both selected parents and substitutes the second into the first, refusing an
oversize proposed child. Mutation replaces a random subtree with a newly grown
random tree sized to the remaining depth. One best tree is copied unchanged each
generation. Population, parents, tournament candidates, crossover/mutation paths
and replacement trees are actual receipts, not hidden chain-of-thought.

This is supervised symbolic regression: training fit is not proof of held-out
generalization or discovered truth. Tests reproduce simple quadratic regression
and independently evaluate every tree, objective, tournament and structural
crossover/mutation receipt. No unrestricted code synthesis, loops, recursion,
I/O, side effects, arbitrary grammar, language compilation, or eval/exec.

Bounds:2..64 aligned finite training samples, population2..128 default40,
generations1..1000 default60, max_depth2..6 default5 (leafdepth1), positive
bounded tournament default3, crossover[0,1] default.8, mutation[0,1] default.3.
Defaults require population>=3 unless caller supplies smaller tournament.
Worst-case evaluated-node work<=3000000 and retained tree-node work<=300000.
Finite numeric inputs/no booleans, overflow refuses422. Strict depth is preserved
by crossover refusal and depth-budgeted mutation. Stochastic search has no global
optimum guarantee. Seeds repeat exact initialization and lineage; no model,
provider, spend, persistence, external code execution, or general cognition claim.

Residual: arbitrary grammars, general-purpose programs, multi-variable tasks,
open-ended synthesis and verified out-of-sample generalization not implemented.
Ledger unchanged until independent acceptance. Formal receipts and public
mutability helpers are not a sandbox for arbitrary caller code.
