# Premortem comparison

Against the actual peer b944215 bundle object, PremortemEngine.analyze is AST-identical. It uses placeholder likelihood/impact scores and labels them as review assumptions, not measured probabilities. Our assess_register is additive, absent from the peer implementation; preserve it rather than treating it as peer parity.

The supplied ordinal register validates bounded inputs/ratings, ranks RPN products, exposes missing controls, and marks evidence references unverified. Completeness means ready for owner review only, not approval or verified evidence. Two added canaries plus selected foresight/route tests: 7 passed, 170 deselected. No product code changes required. This closes the bounded analyze/export/register-label comparison, not independent assessment of supplied risk truth or production clearance.
