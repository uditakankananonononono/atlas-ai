# Row 685: finite declared-rule example mapping

This package evaluates examples against a small declared rule language. It does not run caller code, test a repository, approve delivery or authorize release. The current ledger remains PARTIAL; no shared ledger is changed.

## Pinned requirement

Base main: `7885256e9791f9eab4239ecab1b8fb7fd4c8787c`.

`audits/additional-2000-features.json` row 685 is Example Mapping, description "Clarifies requirements", status PARTIAL. Its current scope is supplied-input software practice diagnostics, templates and arithmetic only. Its source document is `1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY`. Live reading on October 11, 2026 found "Example Mapping - Clarifies requirements". Ledger file SHA256: `8f697bd86a12d07f13ca1116c3e0ae9616a83b82b2a54e10bfbf2575a8a85312`.

Original feature source: https://docs.google.com/document/d/1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY/edit?usp=drivesdk&authuser=uditakankana%40gmail.com

The baseline `_example` function compares referenced rule IDs and reports a caller diagnostic ready flag. It does not evaluate any rule. The new executor validates and computes finite predicates and reports expected-vs-actual mismatches. This is an incremental repair, not a claim to perform all software practice tasks.

## Input

Call `evaluate_example_mapping(packet)`. All objects reject missing and extra keys. All collection IDs are unique within their own collection and bounded nonblank strings. Source IDs are caller-supplied provenance labels, not proof that those sources were authenticated.

```json
{
  "story": "Adult eligibility",
  "fields": [{"id": "age", "type": "integer"}],
  "rules": [{
    "id": "adult",
    "predicate": {"op": "ge", "field": "age", "value": 18},
    "source_ids": ["requirements:adult"]
  }],
  "examples": [{
    "id": "threshold",
    "inputs": {"age": 18},
    "expected": {"adult": true},
    "source_ids": ["examples:threshold"]
  }],
  "questions": []
}
```

Types: integer, number, string, boolean. No coercion; bool is not a number, float is not an integer. Numeric values must be finite and have absolute value at most 2^53. Empty scalar strings are allowed; IDs/story/questions/sources must be nonblank. No null, containers, functions or field-to-field comparisons.

Comparator predicates use exactly `op`, `field`, `value`. Supported operators are eq, ne, lt, le, gt, ge. Ordering requires a numeric field; equality also supports strings and booleans. Boolean predicates use `{"op":"not","arg":predicate}` or `{"op":"and|or","args":[predicate,...]}`. Every branch is validated, including branches that could short-circuit. No code evaluation, regex, rule references, external lookup or user-defined operators.

Every example supplies exactly all declared fields. Expected outcomes are a nonempty map from known rule IDs to strict boolean values. Partial expected maps are allowed; rules without any declared expected outcome are uncovered even if computed. Every rule is computed for every example, independently of expected outcomes. Invalid schema, unknown refs, duplicate IDs or exceeded bounds raise ValueError before returning any evaluation.

Questions contain exactly id, text, source_ids; all supplied questions are unresolved. This package has no question-resolution workflow.

## Fixed limits

| Item | Maximum |
|---|---:|
| Fields (nonempty) | 32 |
| Rules (nonempty) | 64 |
| Examples (may be empty) | 128 |
| Questions | 64 |
| Predicate depth, root counted as 1 | 8 |
| Predicate nodes per rule | 64 |
| Story, question text, scalar string characters | 2,000 |
| ID/source ID characters | 128 |
| Source IDs per rule/example/question | 16 (nonempty, unique) |

These limits bound evaluation after parsing, not HTTP request byte size or upstream JSON parser depth. They do not create a transport-level DoS guarantee.

## Output

Outputs retain story, fields, validated rules, input values, declared expected outcomes and source IDs. Examples also contain actual outcomes for every rule. Mismatches have example_id, rule_id, expected, actual and the sorted union of example/rule source IDs. Uncovered rule IDs and unresolved questions are explicit.

Collection records are sorted by ID; field/rule maps and source sets are sorted. Reordering top-level records or source lists does not change the output. Boolean operand order is preserved as the declared rule syntax. Inputs are not mutated and output objects do not alias mutable input objects.

`mapping_satisfied` means there is at least one example, every rule has an expected outcome in some example, no mismatch and no unresolved question. It is false otherwise. It does not imply requirements completeness, all input cases covered or production correctness. Mismatch returns `needs_resolution`, rather than raising an input-validation exception or certifying delivery.

`repository_behavior_verified` and `release_authorized` are always false. No ready_for_delivery field is returned.

## Integration ownership

The bundle adds only the executor, its test file and this contract. The separate full-index `integrator-wiring.patch` is not in the commit. It replaces only the row685 dispatch path and updates row685 fixtures/assertions plus an existing-suite mounted auth/tenant test. Rows686..709 retain their implementation paths and behavior. Integrator applies it after review; no route/shared ledger edits are bundled.

Mounted gate uses the actual M20 router at the production prefix and the real local RS256 OIDC verifier through `require_tenant`. It checks no-token/spoofed-header refusal, two signed tenants, stateless separation, invalid schema and mismatch refusal. This is not a full app.main test: that import failed at M01's missing bs4 dependency in the frozen environment.

## Evidence and residuals

Raw receipts include initial tests-first missing-module RED, 104-test first green, expanded 155-test green, 262-test integrated green and eight isolated deliberate mutants killed by the tests. The mutant runner uses real one-at-a-time source changes in a disposable tree and restores the original; it is not independent reviewer acceptance.

Same wider selection: base 136 pass/11 fail, integration 137 pass/11 fail, with identical missing pytest-asyncio/langchain_core failures. Explicit narrower floor: base 112 pass, integration 113 pass. A fully green wider gate is not established. No full Atlas suite, live provider, repository execution, deployment, delivery certification or external effect was run. No evidence authenticity/completeness, arbitrary predicates, generated requirement discovery, field-to-field comparison, transport bounds or question-resolution claims are made. The ledger's repository/release residuals remain.
