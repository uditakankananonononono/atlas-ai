# Builder 5, instinct-doc group 53

Base: atlas-ai main 332f60303d295129cbc11ea2543487a8b21748f8.
Source: live owner Google Doc retrieved October 13, 2026, ID
1VRD84FClUlTk5pX8kcW6ZFxGfbAR6MwH8EoWdkCzlss, paragraph 58:
"ChallengeRocket (100% Free for students): Free to browse and apply to business/tech competitions. + 10 more."
Group numbering corroborated from prior group 47-54 evidence, not reconstructed
from a new count. Science and row 120 were left untouched.

## Runtime delivered

ChallengeRocket application sessions can now capture complete static DOM text
(excluding controls, scripts and explicitly hidden text) for owner review.
The returned packet binds the text and page URL to a SHA-256 digest. Rules,
eligibility, deadline and cost excerpts are keyword heuristics in the same
response, not eligibility or fee verification. Missing categories are explicit.
Capture is bounded to 2 MB HTML and 100,000 text characters, with 60-second
capture pacing.

Owner review requires four strict boolean attestations, stores the captured
text, URL, digest and time in the SQL-backed application session, clears old
final-submit approval, and audits only review facts and digest. Owner/tenant
binding follows existing authenticated application ownership. Reviews expire
at 24 hours, and are per session. Review does not authorize submission.

M13 ApplicationFlow.stage itself enforces review so bypassing the M01 wrapper
cannot stage unreviewed ChallengeRocket session values. Current terms are
checked when requesting final approval and again before consuming an existing
approval or clicking submit. A changed fee or other static text stops the flow,
even if the fixture screenshot bytes are unchanged. Existing exact M02
final-submit authorization remains required. No external submission occurred.

## Reproduction

Python 3.12.14, pytest 8.4.2, SQLAlchemy 2.0.46, FastAPI 0.143.0,
Starlette 0.52.1, Playwright 1.63.0, cryptography 46.0.7.
A fresh virtual environment was installed with focused dependencies within
project version ranges. It is not a full declared dependency installation.

Command:
python -m pytest tests/modules/test_challengerocket_terms_review.py tests/modules/test_m01_student_browser.py tests/modules/test_m02_m13_application_workflow.py tests/modules/test_m01_student_platforms.py tests/modules/test_m01_student_platforms_deepening.py -q

129 passed, 20 skipped, one upstream AnyIO/Starlette deprecation warning.
20 skips are pre-existing opt-in live source tests. New test file: 19 passed.
Tests execute actual SQL persistence, M01/M13 staging, authenticated mounted
routes, strict review input, origin/actor/tenant rejection, missing terms,
expiry, changed-page rejection and approved-execution refusal. Browser DOM
and screenshot transport are fixtures, not a live vendor or visual proof.

Two builder-run error-sensitivity probes: removing the M13 stage review call
fails the unreviewed-stage test; removing final terms checks fails the
changed-terms approved-execution test. The submit mutation reaches missing
fixture effect-store mechanics rather than a real effect, so this is control-
flow error sensitivity, not proof of an external submission prevented.
Mutations were restored before the final test run. Independent audit pending.

## Honest verdict

Group 53 remains PARTIAL. BUILT: runtime terms capture and owner review,
SQL persistence and M13 stage/approval/submit-time text gates with tests.
VERIFIED: not yet independently reproduced. LANDED: no, local patch only.

Not implemented/verified: live ChallengeRocket account acceptance, successful
entry/provider receipt, site permissions/rules interpretation, independent
eligibility/deadline/fee verification, arbitrary controls/uploads, linked or
external rule-document capture, a deployed continuous application workflow.
The review route is an owner attestation, not money authority or blanket site
consent. Costly entries fail the no-cost attestation workflow; a paid workflow
must be separately designed and approved.

Residual limits: static HTML hidden checks do not compute CSS visibility;
owner attestation may be wrong; keyword excerpts are not complete rules;
linked terms are not fetched; generic direct-kind sessions and low-level M13
Service methods do not carry the ChallengeRocket session metadata and do not
inherit this review gate. A DOM change between the last extraction and fill or
submit remains a time-of-check/time-of-use window. This patch does not claim
atomic DOM locking or universal terms enforcement. No UI was built or rendered,
no full repo suite, live vendor test, ChatGPT facade review, or deployment run.
