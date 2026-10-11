# C2 launch quiz and thinking-style profile

Excerpt from owner request: "can literally copy my thinking and intelligence layer by
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

The default adapter now injects shared_policy_hook. Offline draft preparation
is allowed explicitly and never calls the shared deny-only check('draft'),
which would refuse it as unknown. Canonical spend/outreach/fakeacct/autopost/
scrape/trade call c30.policy.check(action, 'POLICY') and preserve its refusal
reason. The legacy fake_account alias maps to fakeacct; all other values,
including non-strings, raise POLICY_REFUSED_UNSUPPORTED without echoing input.
The core enforces these denials before any optional caller hook. A hook must
return literal True and cannot widen this boundary. Unexpected shared-guard
allow still fails closed. No spending, sending or other execution is added.

The shared guard c30.policy is present; the adapter injects it.
Main-app mounting and durable storage remain absent.


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

Current focused floor: Python 3.12.14 with real tests/conftest.py,
66 passed, 0 failed. This covers the existing engine and authenticated
isolated adapter plus shared-policy, alias/reason, offline-draft and literal
True hook-acceptance pins. One dependency deprecation warning remains.
Targeted self-run mutation evidence is not an independent audit or an
exhaustive mutation claim. Full regression, external model validation and
production main-app mounting remain open. No release candy gate is closed
by this unit.
