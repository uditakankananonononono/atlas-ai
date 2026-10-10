# COG-LOGIC1970-A: propositional reasoning and proof

Candidate targets rows1970 Automated Reasoning and1971 Theorem Proving only.
Broadens the old positive-ground-Horn routine to actual finite propositional
CNF reasoning with disjunction and negation. Does NOT implement unrestricted
first-order logic, quantifiers, arithmetic theories or verify supplied axioms.
Independent acceptance must decide bounded SCOPED closure. Row1973 Neuro-Symbolic
AI and1974 Hybrid AI remain open: this unit has no neural predictor.

Production-authenticated route `/api/v1/api/modules/20/propositional-reasoning/entail`
accepts `clauses` (CNF conjunction of disjoined signed integer literals), `query`
(one disjoined clause), optional `max_steps`. Positive integers mean propositions,
negative integers their negations. To prove query, solver checks clauses together
with each negated query literal. Actual DPLL uses unit propagation and branching.
A satisfying assignment is a total counterexample satisfying axioms and falsifying
query. If unsatisfiable, independent resolution saturation builds a checkable
empty-clause certificate with original clause source indices or prior parent
indices and pivot. Input axioms remain uninterpreted, not real-world truth.
Inconsistent axioms entail any query under classical logic; certificate exposes
that contradiction rather than treating it as independent factual support.

`status` is entailed only with an empty-clause certificate, not_entailed only with
a model, otherwise inconclusive when work ends. Separate resolution construction
can exhaust budget after DPLL finds unsatisfiability; this still returns
inconclusive rather than claiming an uncertified theorem. No fabricated proof.
No hidden model reasoning or chain-of-thought, only formal algorithm certificates.

Bounds: variables1..32, input CNF1..128 clauses, each0..32 literals (empty clause
is contradiction), query1..32 literals, exact nonzero signed integers, no bools.
Work budget1..50000 default10000 shared by DPLL search/propagation and resolution
pivot attempts. Exact malformed requests refuse422. Worst-case exponential search
is bounded by work, not a general convergence or production-throughput guarantee.
Repeated literals and tautologies have ordinary set/clause semantics. No model,
paid API, external execution, persistent state, or other COG row closure.

Tests independently enumerate small truth tables, check every certificate source
and resolvent, and validate every counterexample. Generated seeded four-variable
corpus120 instances includes satisfiable/unsatisfiable/entailed/not-entailed cases.
Mounted production/OIDC test verifies exact returned proof. Historical cognitive
routes and catalog retained; ledger untouched pending independent acceptance.
