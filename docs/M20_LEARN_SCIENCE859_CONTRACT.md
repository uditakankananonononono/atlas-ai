# M20 SCIENCE859 scoped contract

This is generic Atlas product functionality, not a science research execution lane.

`scientific_protocol` supplies a sourced ID/hypothesis, explicit predeclared=true,
distinct operational independent/outcome variables with definition/source, outcome
unit, a prediction, controls, procedure, confounds and replication artifact refs.
Prediction declares exact rational minimum_effect greater than falsify_at_or_below
and integer minimum_per_group1..128. The supported analysis is treatment mean minus
control mean. These thresholds and minimum sample counts are supplied design choices,
not inferred power, significance, randomization or causal identification.

Procedure is1..32 unique nonempty bounded strings, preserved in supplied order.
Controls are1..32 unique sourced descriptions. Confounds are0..32 unique sourced
records with exact boolean controlled labels. Empty confounds means no caller-listed
confound, not proof none exists. Artifact records are0..16 sourced unique refs with
kind protocol/data/analysis. Coverage of all three yields a declaration-completeness
checklist only. No file is fetched, artifact accessibility verified or replication
performed. No placeholder default is invented for missing artifacts.

Observations are0..256 unique sourced exact rational values in control/treatment,
bound to the exact protocol ID. Inputs use bounded integer or ASCII integer/fraction
strings with rational components at most10^12; mean/effect components retain that
bound. Outputs preserve sorted observations and source traces. Empty/missing groups
produce no effect. Fewer than the declared minimum in either group yields inconclusive
insufficient data; any declared uncontrolled confound yields inconclusive confounds;
otherwise effect>=minimum confirms these supplied data, effect<=falsification threshold
disconfirms these supplied data, and the open interval is inconclusive. Effects may
still be displayed while inconclusive; no unsupported causal claim follows.

No independent source truth, protocol preregistration verification, hypothesis truth,
statistical significance, experiment execution, model discovery or real replication.
Minimal payloads refuse. Mounted authentication/tenant checks remain. This is a bounded
hypothesis check, not full scientific thinking or research closure.
