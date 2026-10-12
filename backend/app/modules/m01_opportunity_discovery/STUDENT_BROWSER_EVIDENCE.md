# Student platform adapter patch evidence

Base: atlas-ai 4163f497f38420a7f755501034549fc9e2e4a4b0.
Scope: instinct-doc groups 47-54. No push, no real applications, no secret handling.

## Changes

Added M01 owner-browser execution path using existing M13 ApplicationFlow,
BrowserService and durable application sessions, mounted directly on M01 router.
All 17 sources have explicit DOM link classification and exact origin boundaries.
SQL checkpoints persist actor identity, observed links, new-opportunity deltas,
read pacing and sticky site blocks. Selected links must still exist in current
DOM; opening creates a new isolated application session. Staging performs actual
M13 form inspection/fill/readback/screenshot and refuses unsupported controls.
Submission remains the existing per-application M02 approval-bound engine.

No registry labels changed to imply public feeds or account success.

## Verified tests

`python3 -m pytest tests/modules/test_m01_student_browser.py tests/modules/test_m01_student_platforms.py tests/modules/test_m02_m13_application_workflow.py -q`

64 passed, 10 skipped. Skips are existing opt-in live-source tests, not hidden failures.
New tests cover 17 link contracts, Devpost subdomains, ChallengeRocket cards,
strict-origin and stale-link rejection, SQL persistence, delta reads, rate limit,
sticky CAPTCHA/rate block, cross-tenant/actor denial, mounted API strict inputs,
actual text staging with no submit clicks, and non-text-control refusal.

Additional existing M02 integrated-application tests: 2 failed / 1 passed due to
SQLite missing m00_approval_events. Reproduced unchanged on detached base in a
separate worktree; not fixed in this lane. Full suite not run. Python runtime is
3.10, while project declares 3.12; repeat the test run on supported environment.

No live account, live form layout, extension, screenshot pixels, alert delivery
or successful vendor submission was tested. Test screenshot bytes are hermetic
fixtures and not visual proof. Unit link HTML is not a recorded vendor DOM.

## Closure verdict

All eight groups remain PARTIAL, despite useful executable code:

47 RippleMatch: owner-page navigation and individual form staging exist; actual
account matches and automatic applications are not verified. Vendor source only
documents recommendations, not unconditional auto-submit.

48 Simplify: site link browser workflow and Atlas text autofill exist; installing
or controlling Copilot and free batch applications are NOT implemented. Current
official help says Autopilot requires Simplify+ and Copilot is owner-reviewed.

49 RaiseMe: portfolio/college navigation and text staging exist. College following,
portfolio achievement entry, conditional aid calculations and automatic deadline
portfolio submission not verified or automated by this patch.

50 Bold: scholarship links and account navigation feed individual review-gated
text staging. Account matching semantics and actual successful application
remain unverified; prior public listing block remains honest.

51 Fastweb: discovery plus observed-link handoff/text staging. External sponsor
forms intentionally need a separate explicit M02 workflow, not widened trust.

52 Devpost: browser listing link discovery and durable new-event deltas exist.
Authenticated newsletter checkbox configuration and delivered email alerts are
not implemented; no alert delivery claim.

53 ChallengeRocket: card-backed challenge selection plus individual text staging.
Actual entry, eligibility/rules review and successful site receipt unverified.

54 +10 platforms: all ten registry entries have browser link contracts alongside
existing public feed/listing discovery. Editorial sources are not application
providers; ten complete authenticated workflows have not been established.

## Operational limits

Pacing is per session, not tenant-wide vendor quota. No automated monitoring was
started. Owner must confirm own account and permitted site use; attestation is
not independent verification of platform terms. Unsupported checkbox/radio/select
and file controls require owner handling. Public discovery behavior unchanged.
Existing M02 submit routes remain available and own final authorization. Browser
adapter only restricts its own read/open/stage routes. No account credentials are
accepted by these APIs; login happens personally in the paired browser.

## Sources read October 12, 2026

Original source doc retrieved in full:
https://docs.google.com/document/d/1VRD84FClUlTk5pX8kcW6ZFxGfbAR6MwH8EoWdkCzlss/edit

Vendor workflow sources:
https://resources.ripplematch.com/what-is-ripplematch-and-how-does-it-work
https://help.simplify.jobs/articles/2415391-using-copilot-to-autofill-applications
https://help.simplify.jobs/articles/1784339-getting-started-with-autopilot
https://help.raise.me/hc/en-us/articles/115002095588-Micro-Scholarships-101
https://bold.org/how-it-works/
https://help.devpost.com/article/111-manage-your-notification-settings
https://challengerocket.com/hackathons-and-challenges.html
https://www.fastweb.com/college-scholarships

These support workflow facts, not permission for platform automation. The patch
does not assert an API or automation terms grant that has not been checked.
