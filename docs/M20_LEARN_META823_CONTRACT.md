# LEARN-META823-824: descriptive calibration and learner-controlled cycle

Candidate SCOPED acceptance, not broad metacognition/self-regulation. Row823
keeps existing descriptive arithmetic: per-attempt Brier squared error and signed
prediction error, per-strategy/global means and observed success rates, all exact
best-observed ties, winner only when unique. No prediction correction, causal
strategy comparison or inferred understanding. Evidence and attempt IDs must both
be unique; distinct attempts cannot double count the same supplied evidence.
Standalone823 accepts caller strategy labels without a catalog; those labels are
not independently identified learning strategies.

Row824 now requires a sourced structured learning_goal with metric
 task_success_rate and target[0,1], plus1..32 sourced strategy/action entries.
A source/objective or fixed three-label cycle no longer establishes execution;
minimal payloads refuse clearly. Up to1000 scored attempts feed the same
calibration arithmetic. Strategies must belong to the explicit catalog. Empty
attempt evidence abstains; absent reflection abstains. Reflection includes sourced
observation text and unique evidence IDs covering exactly all scored attempts;
unknown/partial references refuse. No text reflection is semantically evaluated.

A unique lowest observed Brier loss supplies a descriptive recommended strategy
and its supplied next action. Ties retain all best strategies with no winner.
Overall supplied outcome frequency is compared to the declared goal target; this
is observed success rate, not mastery or educational effectiveness. Missing learner
choice gives awaiting_learner_choice, not an autonomous selection. Explicit choice
may differ from recommendation, provided it names a catalog strategy and a sourced
reason. Selected next action follows that choice. All actions remain unexecuted
and require learner approval; no persistent preference or authorization is inferred.

Mounted existing methods inherit owner tenant/auth checks (401/422/403). Sources
are caller references, not retrieved truth; no external effects, persistence,
models or scheduling. Outputs truth verification=False, learning improvement=None.
Synthetic hand-computed scores, outcome flips, ties, duplicate/invalid evidence,
unknown strategies, missing evidence/reflection/choice, explicit dissenting choice
and mounted auth are tested. Residual: supplied descriptive observations only,
no causal strategy effectiveness, semantic reflection analysis, autonomous
self-regulation or proof that any learning took place.
