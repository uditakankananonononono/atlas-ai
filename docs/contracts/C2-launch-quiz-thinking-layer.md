# C2 launch quiz and thinking-style profile

Source pin: Udita's authenticated WhatsApp message, October 11, 2026,
15:03:34 IST: "can literally copy my thinking and intelligence layer by
quizzing me during the launch process make it advanced"; "the thinking
process should be like me when i feed it some docs (which it asks for) and
is highly step by step and advanced".

## Implemented bounded behavior

The stdlib engine captures four explicit preference axes: values, decision
rules, dilemmas, and writing style. Each has a followup whose wording uses
the previous choice and requests an example/counterexample. Answers retain
explanations, sources, and review status. This is a fixed eight-question
adaptive template, not an unlimited generative interviewer.

Profiles can be inspected, corrected, or deleted. Consent must be literal
True before collection. Revocation deletes the session, including answers,
preferences and document text. Returned profiles are detached copies.
The optional document request asks for the owner's decision notes and writing
samples. Ten explicitly consented text documents, 20,000 characters each,
are accepted atomically; duplicate IDs fail. Lexical compare, verify,
experiment and reflect cues add source-linked planning checkpoints. Document
instructions do not run, change policy, or override explicit preferences.

A draft plan restates requirements, applies each chosen preference to an
explicit planning step, adds document-cue checkpoints, and asks for review.
This visible planning explanation is not private chain-of-thought or a copied
mind. Uncertain preferences remain named. No task is actually solved or
executed by these scaffold steps.

Each profile and plan carries implemented/not_implemented/data_source/as_of
scope. Counts derive from supplied session records. Caller supplies as_of;
it is a label, not an independently verified capture timestamp.

## Integration

Core: m20_general_cognitive_worker/launch_quiz_c2.py.
Additive adapter: launch_quiz_c2_routes.py, **not mounted in the main app**.
It exposes POST /api/v1/c31/launch-quiz/run (start, answer, documents, edit,
plan, delete, revoke) and GET /api/v1/c31/launch-quiz/report. Identity comes
from require_tenant's authenticated tenant and actor, not request payload.
Isolated mounted-adapter tests use production RS256 verification fixtures.
The adapter serializes operations with an RLock in one process only.

Default local enforce_policy rejects spend/outreach/fake_account/autopost/
scrape/trade and every action except draft. A policy_hook(action) can further
restrict: it must return literal True; it cannot override the local refusal.
Shared c30.policy does not exist at base a1b859ce. The integrator must map
that hook to the eventual shared policy before calling this integrated.

## LIMITS

No claim of replicating intelligence, personality, a mind, or clinical traits.
No model training, semantic comprehension, generated prose, browser access,
external tool use, messaging, spending, posting or scraping. Supplied text
is used only for explicit lexical style markers. Only synthetic data appears
in tests and receipts; no owner's real documents were ingested.

In-memory store only, up to 100 sessions by default (configurable 1-1000).
Process restart loses profiles. IDs are sequential and are not authentication;
core caller must supply a trusted owner, HTTP adapter derives it from auth.
No UI, main-app mounting, database, encrypted storage, retention timer,
cross-worker concurrency, production deployment, or end-to-end launch flow.
A deployed persistence layer must implement owner-bound deletion separately.

## Verification

Initial test-first import RED was before engine creation. Later boundary
canaries were RED (2 failed / 17 passed) before malformed-key and fail-closed
shared-hook fixes. Python 3.12.14 with real tests/conftest.py: 21 passed,
0 failed. The FastAPI adapter has one dependency deprecation warning.
Hand-selected mutation battery is self-run, not an independent audit; its
exact modes and counts are in audits/c2-launch-quiz/mutation-results.json.
Full regression, independent audit, external model validation, shared-policy
mapping and production main-app mounting remain open. No release candy gate
is closed by this unit.
