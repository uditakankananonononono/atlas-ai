# A16 real Chromium product consumer

Actual M13 Service and PlaywrightSessions launch headless Chromium 1243, use
separate tenant contexts with the same session label, navigate controlled HTML,
fill/read back a DOM field, extract content, create a real PNG through the pinned
artifact root, record SQL audit events and close contexts/HAR/browser resources.
Cookie and field-state isolation, capacity and persistence-mode refusal are pinned.
The inspected 1280x720 screenshot shows the fixture heading, filled email field
and explicit no-submission label, readable without clipping.

Production validate_public_url and _guard_route are unchanged. Test-only DNS
maps the fixture hostname to a global canary IP. A transport wrapper calls the
unchanged guard then fulfills the accepted fixture URL, rather than making a
public-site request. Real Chromium loopback subresource requests are aborted;
separate guard controls cover loopback, localhost and metadata. No submit or
external action is exercised, no user profile/cookies or real account is used.
This is transport-interception fixture evidence, not live public-site or Browserless
acceptance, universal SSRF/rebinding safety, production isolation or full A16/M13.
HAR driver-write containment and same-UID rename residuals remain as documented.

First real attempt: three guard controls passed; screenshot failed with Chromium
Page.captureScreenshot protocol error. Unchanged rerun: four passed. Focused
same-tree browser/security/artifact/store suite: 51 passed, zero failures. The
initial failure is retained, not rewritten as a pass or explained as a proven
product defect/environment cause. No runtime change was made to force acceptance.
