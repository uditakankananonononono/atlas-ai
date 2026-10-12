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
Adapter: launch_quiz_c2_routes.py. Main-app mounting is explicitly opt-in.
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
Set `ATLAS_C2_ENABLED=1` and `ATLAS_C2_DB=/absolute/private/quiz.sqlite`
before starting the service. The parent directory must already exist with mode
0700 (or stricter). The database is created with mode 0600; public modes,
symlinks and hard-linked database files refuse. Missing or invalid storage while
enabled fails startup. Without the exact enable value, no C2 routes are mounted.
The existing standalone router remains an explicit in-memory host adapter.

The mounted adapter uses SQLite transactions with BEGIN IMMEDIATE, FULL
synchronous commits and secure_delete. Every operation reloads the state under
the transaction, so separate connections on the same local database serialize and
keep session IDs unique. Answers, documents and edits survive process restart;
delete/revoke removes the owner-bound session from persisted live state. Invalid
operations roll back. State is capped at 100 sessions and 25MB encoded JSON;
Unicode escaping counts toward that cap. No silent memory fallback is used.
Returned mounted profile/plan scope names local persistence; the core alone
continues to report durable storage absent.

Use a trusted private local filesystem and protect the directory from concurrent
replacement. Path validation does not eliminate check-to-open races. SQLite is
not encrypted storage, remote storage or a distributed database. secure_delete
is not proof of erasure from backups, snapshots, storage hardware or historical
copies. Operators must apply retention and deletion to those separately.


## LIMITS

No claim of replicating intelligence, personality, a mind, or clinical traits.
No model training, semantic comprehension, generated prose, browser access,
external tool use, messaging, spending, posting or scraping. Supplied text
is used only for explicit lexical style markers. Only synthetic data appears
in tests and receipts; no owner's real documents were ingested.

The standalone in-memory store supports 100 sessions by default (configurable
1-1000) and loses profiles on restart. Opt-in main-app storage persists up to
100 sessions. IDs are sequential and are not authentication;
core caller must supply a trusted owner, HTTP adapter derives it from auth.
No UI, encrypted storage, retention timer, production deployment, or end-to-end
launch flow is verified. Shared-local-database connection transactions are supported;
multi-process behavior, network-filesystem and multi-host concurrency are not
verified. FULL synchronous is configured but its crash/durability behavior has
no direct test pin. One dependency deprecation warning remains in the reviewed
floor.

## Verification

Current focused floor: Python 3.12.14 with real tests/conftest.py,
91 passed (66 shared/quiz + 25 durable), 0 failed. This covers the existing engine and authenticated
isolated adapter plus shared-policy, alias/reason, offline-draft and literal
True hook-acceptance pins. Synthetic mounting tests cover restart, owner isolation, edit, draft planning,
revocation, rollback, private path checks and concurrent session creation.
Targeted self-run mutation evidence is not an independent audit or an
exhaustive mutation claim. Full regression, external model validation and
live deployment remain open. No release candy gate is closed
by this unit.
