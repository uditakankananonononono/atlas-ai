# LEARN-PLAN820-825: additive goal/chunk plan validation

Candidate SCOPED unit. Existing chunking/goal-setting methods require plan_goal,
required_elements and plan_chunks; old copied chunk/goal fields do not count as
execution and minimal payloads refuse. The same bounded engine serves both rows.

Caller supplies a sourced measurable goal, metric label, positive integer count
target1..1e6 and ISO timezone-aware deadline. This grammar assumes an additive
count metric; ratios, rates, percentages, arbitrary utilities and mixed units are
not supported. The metric string is a caller label, not inferred semantics.
1..64 unique required element IDs and1..64 sourced chunks define decomposition.
Each chunk has observable subgoal text, same metric, positive integer target,
timezone deadline, <=64 elements/prerequisite IDs and explicit nonempty if/then
intention text. Text is bounded240chars. No semantic action parsing is performed.

Known prerequisite IDs must form an acyclic graph; unknown/cyclic links refuse.
Ordering uses simultaneous topological layers with alphabetical IDs per layer.
Coverage computes missing/unexpected/multiply assigned elements. A conceptless
chunk may have zero elements but cannot make missing coverage disappear. Count
aggregation sums chunk targets and checks exact equality with the supplied goal.
Goal validity also requires all elements exactly once and no deadline conflicts:
a chunk cannot end after goal or before a prerequisite's deadline. Equal deadlines
are accepted; this is consistency checking, not duration estimation or scheduling.

Outputs retain supplied sources, goals, if/then intentions and ordered chunks,
with computed coverage/count/deadline reports and validated/gaps_or_conflicts.
Malformed inputs refuse without caller mutation. Source truth is unverified,
scheduled=False, goal_chosen_autonomously=False. No persistence, external effects,
autonomous goal choice, feasibility prediction or achieved-goal claim.
Mounted auth inherits401/422/403owner/tenant checks. Synthetic tests cover DAG
ordering/cycles/unknown refs, coverage duplicates/gaps, aggregation, timezone and
deadline consistency, typed targets, intentions and minimal payload refusal.
Residual: supplied additive count-goal decomposition only; no general planning,
cognitive chunk discovery, scheduling or proof of learner improvement.
