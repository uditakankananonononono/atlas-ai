# Atlas hard-budget repair frontier: prior-art record
Search date: October 14, 2026. Status: candidate benchmark, NOT a world first.

## Search and switch record
Searched public papers, repositories and benchmarks before implementation.
Queries included:
- agent memory evidence revocation dependency truth maintenance incremental repair benchmark
- LLM agent memory benchmark conflicting updated facts LongMemEval memory consolidation
- incremental computation self adjusting computation dependency graph minimal recomputation github
- agent memory repair exact budget optimal frontier replay equivalence certificate knapsack dependencies benchmark
- belief revision budgeted repair Pareto frontier dependency graph LLM memory
- "memory repair" "optimal" "budget" agent certificate
- "memory" "repair frontier" agent
- precedence constrained knapsack problem exact algorithms NP hard Pareto unsupported scalarization

Candidate A (dependency-aware revocation/repair) rejected as novel because it already exists.
Candidate B (repair-cost frontier) also overlaps direct prior art.
Candidate C built here: a bounded executable diagnostic for unsupported HARD-CAP
Pareto points, comparing cap-optimal predecessor-closed selection with the best
budget-feasible point optimal under any nonnegative scalarization coefficient.
No exact matching benchmark was found in these searches. That is not proof of
novelty: the optimization and unsupported-point phenomenon are classical.
The measured win is expected from optimizing a different objective. It does NOT
show that Atlas beats MemoRepair as a system, nor that this is a new algorithm.

## Sources read
1. MemoRepair: Barrier-First Cascade Repair in Agentic Memory. Primary paper,
https://arxiv.org/html/2605.07242
Section 2.4 explicitly defines predecessor-closed repair selection, exact
scalarized max-weight closure/min-cut, and identifies a hard-cap variant as
precedence-constrained knapsack. Main experiments use fixed lambda. It already
reports repair-cost frontiers. Closest prior art. High confidence in this overlap.

2. From Faulty Memories to Corrected Actions: Dependency-Guided Rollback Repair
for Memory-Augmented Agents. August 11, 2026 primary abstract,
https://arxiv.org/abs/2608.10502
Already uses typed provenance and selective replay. Reported paper results not
reproduced here. High confidence for rejecting candidate A.

3. TEPA: Revoking Stale Memories for Conflict-Robust Language Agents. Primary paper,
https://arxiv.org/html/2608.07429v2
Explicit lifecycle revocation and current evidence retrieval already exist.
High confidence for overlap, not evidence for our benchmark's uniqueness.

4. MemTX: Transactional Belief Commit for Stateful Agent Memory. Primary paper,
https://arxiv.org/html/2607.23929
Belief-commit state, effect gating and typed cascading repair already exist.
High confidence for overlap; none is claimed as our invention.

5. ERRAND: Budgeted Maintenance of Agent Memory. Primary abstract,
https://arxiv.org/abs/2609.29545
Budgeted revalidation with priced maintenance already exists. Our benchmark does
not implement or evaluate ERRAND; it assumes diagnosed affected nodes.

6. LongMemEval. Official benchmark repository,
https://github.com/xiaowu0162/LongMemEval
Tests knowledge updates, temporal reasoning and abstention among other abilities.
Our synthetic DAG task is NOT a run on LongMemEval.

7. MemoryAgentBench. Official benchmark repository,
https://github.com/HUST-AI-HYZ/MemoryAgentBench
Incremental memory/conflict-resolution evaluation exists. Not run here.

8. Jane Street Incremental. Implementation repository,
https://github.com/janestreet/incremental/
Dependency-aware incremental computation predates this work. No incremental
computation novelty is claimed.

9. Calyxos. Implementation repository,
https://github.com/krish-shahh/calyxos
Python dependency tracking and selective recomputation also exist. No such
mechanism is claimed as new here.

10. A pegging approach to the precedence-constrained knapsack problem.
Classical optimization paper landing page,
https://www.sciencedirect.com/science/article/abs/pii/S0377221706010642
Exact PCKP algorithms predate agent memory. Search excerpt describes exact
pegging; full article access may be restricted. No classical-algorithm novelty.

11. Heuristic and Exact Algorithms for the Precedence-Constrained Knapsack Problem.
Classical optimization bibliographic page,
https://dl.acm.org/doi/10.5555/3182683.3183062
Further historical prior art for the exact optimization problem. Full article
access may be restricted; not used to support a performance claim.

## Exclusions and remaining work
No paid model/tool, live agent or user data used. No real task or external
benchmark score measured. No shared-models change for this candidate. No public
release. Novelty remains UNCONFIRMED. A real trace evaluation, incomplete-
provenance stress test, scalable solver and independent audit are next steps,
not completed outcomes. The source papers' own novelty claims were not adopted.
