# Row161 Policy Gradient Methods

Exact description: "Optimizes action policies directly".
Source: https://docs.google.com/document/d/1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY/edit

Actual one-step tabular softmax REINFORCE gradient ascent on supplied sampled
actions/advantages: mean advantage times (onehot action minus old policy), updated
logits/new policy and fixed-sample log-probability surrogate before/after. Stable
log-softmax for extreme update scores. Existing planning method unchanged.

Caps2..20actions,1..1000samples,logits+-100,advantages+-1000,learningrate(0,1].
Strict types/schema/index ranges. Independent nonuniform three-action reference,
positive/negative/zero advantage directions, sample-average/repetition and logit
shift invariance, extreme finite objectives, all numeric/cap/type refusals tested.
Units explicitly distinguish logits, reward-unit advantages and inverse-reward
learning rate. No caller mutation.

SCOPED supplied-sample categorical policy update/PARTIAL literal feature. Does
not run environment,verify on-policy sampling or advantages,guarantee return
improvement,fit baseline/value function,train state-conditioned neural policy or
supply auth/persistence/runtime integration. No external effects.
