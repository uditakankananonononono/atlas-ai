# Claire originality brief: evidence perturbation probes

Exploratory design hypothesis, not a novelty claim against prior literature and not
AGI evidence. No training/model capability result is asserted.

## Candidate: contrastive evidence invariants

For each goal's declared acceptance criterion, generate small counterfactual probes
around the evidence boundary. A successful receipt is changed to failed, moved to
another tool, removed, duplicated, or replaced by persuasive final text. Acceptance
must respond to actual authorized evidence, never narrative confidence.

Use these probes before releasing a new adapter/tool: if removing a successful
receipt leaves acceptance unchanged, flag an evidence-independence bug. If final text
changes acceptance, flag narrative leakage. If a second receipt from another tool
counts, flag identity leakage. Do not invent a score and call it intelligence.

## Why explore it

Behavioral regression usually tests handpicked examples. Systematically pairing an
accepted report with minimally changed rejected reports makes the acceptance
boundary visible. This could become a low-cost release diagnostic for evidence
integrity, alongside real runtime tests, not instead of them.

## Bounded prototype

Generate report variations for the existing tool-receipt criterion and evaluate with
the real acceptance function. This is a test harness only: no user goal modification,
no side effects, no model prompt injection, no automatic alteration of approvals.
Declared scope: receipt-based acceptance; no provenance authentication, external
truth verification, semantic correctness or full task success claim.

## Prototype finding

The current evaluator counts successful matching receipt rows. A replayed duplicate
therefore satisfies min_count=2 together with the original receipt, although this is
not evidence of two distinct effects. The test records current behavior; it does not
repair it. This is a semantic gap only when a criterion intends distinct work/effects.
Read calls may legitimately repeat; blindly deduplicating arguments would be wrong.

Proposed next design: explicit criterion semantics (receipt rows versus unique
committed effect identities), with durable effect keys and provenance carried into
receipts. Preserve legacy receipt-count behavior under its honest name rather than
silently changing goals already in flight. Independent reviewer should judge scope
before any implementation. No live goal or approval is changed by the probe.
