# Student platform adapter patch evidence

Base: atlas-ai 4163f497f38420a7f755501034549fc9e2e4a4b0.
Scope: instinct-doc groups 47-54. No push, no real applications, no secret handling.

## Changes

Added M01 owner-browser execution path using existing M13 ApplicationFlow,
BrowserService and durable application sessions, mounted directly on M01 router.
The original 17 sources have explicit DOM link classification and exact origin boundaries.
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
private source locator withheld

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

## Origin-race correction (patch 0003)

The initial patch failed audit: platform origin checking before awaited inspect
was insufficient. A mid-stage origin flip could fill an unrelated page.

Correction: ApplicationFlow start accepts explicit per-session allowed hosts.
Platform parent/child sessions install this scope before page creation; unsupported
transports fail closed. Playwright intercepts all requests and redirects against
that session's exact host set, disables service workers, aborts forbidden requests,
and permanently aborts subsequent operations after a forbidden request. This is
strict, including cross-origin assets and SSO; owner-visible site failure is safer
than silently widening scope. Devpost child scope adds only the selected observed
event hostname, not a wildcard. Other generic M02 sessions remain unchanged.

A scoped page/locator wrapper rechecks current origin synchronously at actual
fill/click/readback boundaries with no intervening await before dispatch, and again
after each await. M13/M02 operations obtain the scoped page from the session adapter,
so final-submit-adjacent readbacks/screenshots and exact approval clicks inherit
this boundary too. Request interception prevents cross-origin network navigation,
rather than relying only on rejection after the page loads.

Adversarial hermetic tests cover origin flips between snapshot and inspect,
after inspect, during stage extraction, and at locator creation; all stop before
private field writes. Same-origin redirect is allowed; external redirect is
aborted and stays aborted, including future same-origin requests. Unsupported
transport refuses session creation. Final targeted result: 71 passed, 10 skipped.
No live Chromium/vendor navigation was run; actual browser acceptance remains an
explicit gate, not implied by interceptor unit tests.


Row 54 (2026-10-12) adds 10 RSS-only editorial feeds to the registry. They get adapters only so the registry and adapter tables stay in lockstep; staging is refused for them in StudentBrowser.stage (enforced, tested). start/read/open remain available, as they were for the 6 earlier editorial sources; nothing here is evidence of any application flow.

## v5 notes (2026-10-12)

- Editorial ban is now global: ApplicationFlow.stage (m13 stage_policy.py) raises PermissionError for rss-mode student_platform sessions, not only StudentBrowser.stage. The route schema carries the refusal.
- Prefill plan binding: POST .../browser-sessions/{id}/prefill-plan returns a plan plus plan_token, a digest over page URL, field descriptors, planned fields and submit selector. stage(plan_token=...) recomputes it from a fresh inspect and refuses on any drift.
- Digit guard (m13 value_guard.py): ALL non-digit characters, separators and letters, are stripped (letter-interleaved '123a45a6789' counts as 9 digits; free text such as '123 Main St Apt 4B 94110' is therefore refused under non-phone keys) after NFKC and other-script digit normalization. Non-phone keys refuse runs of exactly 9 or 12+ digits. Phone keys (key matches phone/mobile/tel/telephone/cell) use the shape rule exactly: only digits, spaces, dots, hyphens, parentheses and an optional leading '+'; 7-15 total digits, never exactly 9; 12-15 digits only with a leading '+'. So 7-8 digit values are ACCEPTED under a phone key, as are 10-11 digit values under non-phone keys; a dashed NNN-NN-NNNN pattern is refused under every key. Known false positives: any 9-digit or 12+ digit non-ID number under a non-phone key (e.g. a 9-digit grant amount) is refused; fail closed. Residuals are listed in the module docstring; digits spelled as words are not detected.
- Field context (section headings, aria-labelledby/describedby, role=heading, captions) is captured and used for exclusion and unlabeled-control eligibility. It is not used for value matching. M13's generic fuzzy matcher ignores context entirely; no new enforcement there. Context over-withholds by design (fail closed). Hidden text is excluded; parts cap 120 chars, total 600.
- Service.fill refuses select matches and ID-shaped values.

### Scope residuals of the global editorial refusal (v7 docs)

1. The refusal sits in ApplicationFlow.stage. Low-level fill/submit routes carry no editorial classification of their own. If a caller can reach them without going through stage, the editorial ban does not apply there. Whether the m13 /fill route is mounted was not verified. Service.fill does refuse select matches and ID-shaped values, but it does not check editorial status.
2. Detection is metadata-based (rss-mode student_platform session tags). A direct-kind session on an editorial URL with no rss metadata is not caught by this helper.
3. Sessions staged before this change are not revoked. One with a valid exact approval could still submit. No live sessions exist in the tests, so this is accepted for a code change, but it is stated here.

### v8 notes

- plan_token is an unkeyed SHA-256 digest over page URL, field descriptors, planned fields and submit selector. It is optional on stage, has no expiry and no session binding of its own (the stage call is already scoped to the tenant/actor/session). A token from one session can be replayed on another session only if that page is byte-identical in those respects. Accepted: it detects drift, it is not an authorization. M02 final-submit approval remains the authorization gate.
- Service.fill now checks the live DOM control type (tag and input type through locator.evaluate) rather than trusting the caller's descriptor type. Anything other than textarea or a text-like input (text, email, tel, url, search, number, or empty type) is refused, as is a locator that cannot report its type (fail closed). Residual: contenteditable elements and custom widgets that render as div are not text-like inputs by this check and are refused.
- The editorial ban test is parametrized over all 16 editorial_discovery adapters, on both the ApplicationFlow.stage and StudentBrowser.stage paths. Row-54 provenance is unchanged (10 feeds, PROVENANCE.json).
