# Row 849 - Non-Monotonic Reasoning (contract)

## Source pin
- Ledger: audits/additional-2000-features.json, row 849, category "Learning & Knowledge", requirement "Non-Monotonic Reasoning", description "Revises conclusions". Status at the base commit: SCOPED; current_scope "Recompute exact stable models after explicit fact additions/removals, returning cautious conclusion retractions and new conclusions. No arbitrary prioritized default or real-world truth claim."; current_evidence tests/modules/test_m20_defeasible_reasoning.py; independent_review "pending".
- Read at main 070f7ffb838db4b012bd443c4e1054f426220ebe.

## Gap this closes
The behavior in current_scope already exists in `defeasible_reasoning.default_inference` (before/after stable models, retracted and new cautious conclusions) and is tested. What was missing is a bounded, strictly validated entry point: the engine accepts str subclasses and sequence-like inputs, raises AttributeError or KeyError on non-dict or incomplete input, ignores unknown keys, has no caps on facts, rules, premises or queries, and enforces its 12-optional-atom limit only after an unbounded atom union. The engine is shared (horn_inference, explanation_practice, learning_reasoning_810_859), so it is NOT edited.

## What this is
`revise(payload)` in backend/app/modules/m20_general_cognitive_worker/nonmonotonic849.py. It validates, then calls the unchanged engine. The engine's internals are inherited as-is: the front door guarantees only what it validates. Refusals: `NONMON849:<REASON>[:<field>]`, plain ValueError.

## Inputs
Exactly the keys facts, rules, added_facts, removed_facts, query_atoms (all required; at most 16 keys in any dict, counted before iteration). Atoms: exact str, 1-64 chars (raw cap before strip), no Cc/Cf/Zl/Zp characters, Zs accepted. facts up to 32, added_facts 16, removed_facts 16, query_atoms 16, rules 1-16, each rule exactly id (1-256 chars), if (up to 8 atoms), unless (up to 8), then. Lists must be exact builtin list, no duplicates inside any list, rule ids unique. A truthy decide/conclusion/determination/truth/advice key is refused CONCLUSION_REFUSED.
Revision rules: an added fact already in facts is ADDED_ALREADY_PRESENT; a removed fact not in facts is REMOVED_NOT_PRESENT (checked in that order). Choice, disclosed: the engine silently accepts re-adding a present fact; the front door refuses it so every revision is a real change.
Search bound: atoms that appear in rules and are not facts must number at most 12, checked for BOTH the original and the revised fact set before any search (TOO_MANY:optional_atoms). This mirrors the engine's own limit but fires before work.
Other codes: BAD_TYPE, EMPTY, CONTROL_CHARS, TEXT_TOO_LONG, MISSING, UNKNOWN_KEY, TOO_MANY, DUPLICATE. Order: container type, size cap, then elements; oversize beats content errors; subclass inputs are refused untouched.

## Output
row, status "recomputed_exact_stable_models_only", revision (sorted added and removed), before (stable_models, model_count, cautious_conclusions, consistent), stable_models, model_count, cautious/possible/ambiguous conclusions, consistent, queries (engine statuses: cautiously_entailed, ambiguous, not_entailed, inconsistent_program, each with supporting model and countermodel and not_entailed_does_not_mean_false), retracted_conclusions, new_conclusions, revision_comparable, no_real_world_truth_claim=True, default_priority_applied=False, boundary.
Choice, disclosed: when either the original or the revised program has no stable model the cautious sets are not comparable, so revision_comparable is False and retracted_conclusions / new_conclusions are None. The engine would report an empty cautious set for an inconsistent program and so produce spurious retractions or conclusions.

## Limits and residual disclosures
- Finite normal logic programs only, symbolic atoms. Absence from a model is not falsity. No default priority, no ranking of alternative models, no real-world truth or belief claim.
- The engine's own behavior (model enumeration, witnesses, query logic) is inherited unchanged and was not re-audited here beyond the equivalence pins in the tests.
- Lone surrogates (Cs) are not newly refused. Not wired to any route or mount in this change.
- Tests are hermetic stdlib. FULL SUITE NOT RUN. No closure claim. Independent gate: separate record. No ledger or audit file is edited by this change.
