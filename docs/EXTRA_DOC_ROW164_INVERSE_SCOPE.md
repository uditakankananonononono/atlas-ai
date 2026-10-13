# Row164 Inverse RL

Exact description: "Infers objectives from behavior".
Source: https://docs.google.com/document/d/1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY/edit

Actual relative one-state bandit rewards inferred from supplied action counts
under declared softmax temperature and symmetric positive pseudocount. Reward
reference action0 fixed to zero; reward differences temperature*log(smoothed
count ratio). Exact rational smoothed probabilities, float rewards and reconstructed
softmax probabilities returned. Existing planning method unchanged.

Caps2..20actions,integer counts0..1million with nonzero total,temperature and
pseudocount1e-6..1000. Nonuniform independent count-ratio references,zero counts,
fractional smoothing,temperature scale ambiguity,permutation/reference ambiguity,
reconstruction,all bounds/types/shapes and no mutation tested.

SCOPED inverse-softmax bandit preference inference/PARTIAL literal feature.
No actual intent/objective identification,sequential dynamics,expert trajectory
modeling, general inverseRL training,provenance verification,auth/persistence/runtime
integration. Infinitely many reward offsets and alternative choice mechanisms can
explain behavior. No external effects.
