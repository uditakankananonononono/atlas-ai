# Finite login experiments

M18 now has a separate, executable login-run surface, mounted at
`/api/v1/side-hustle-scraper/login-runs`. The legacy artifact runner remains a
preparation-only compatibility API. It is not an executor. Its HTTP receipt
insertion endpoints reject client assertions; manually entered outcomes remain
explicitly unverified and are never used by the login executor.

## Flow

1. The authenticated owner selects one installed platform, exact account, and
   `pc.<paired-device>.<session>` session. Create returns a login handoff.
2. The owner logs in on their own browser. No credential, cookie, password or
   session-token input is requested by this module.
3. `/discover` reads bounded evidence (at most ten excerpts of 2,000 characters)
   from the installed discovery page after checking the selected account.
   Source URLs and excerpt hashes persist in the sourced blueprint. Excerpts are
   data, not instructions. No generated ranking or profit score is used.
4. `/preview` accepts the owner's hypothesis, exact draft and 1-120 minute cap.
   Only one zero-cost publication is supported. It fills the local browser
   draft and per-run correlation field, captures final form/account/audience/
   destination/terms and a screenshot, then requests explicit M0 human review.
5. The selecting owner approves through the existing approval center.
6. `/execute` compares the browser with the approved snapshot, consumes the
   bound one-shot approval, durably claims the submit, and sends one approved
   click through the existing paired-device dispatcher. The native daemon checks
   snapshot digest, live account/terms/form/destination and approved field values
   immediately before the click. It does not use a simulated executor.
7. `/reconcile` reads the same paired browser. Success requires an exact account,
   run correlation id, provider receipt id and published draft readback. A
   server HMAC signs the tenant/run/approval/content-bound observed evidence.
   It confirms publication only, never demand, conversions or profit.

## Configuration

`ATLAS_M18_RECEIPT_KEY`: server-managed persistent signing key, at least 32 bytes.
Never put this in a request or browser recipe. Rotate only with a deliberate
receipt migration: old receipts will fail verification under a changed key.

`ATLAS_M18_LOGIN_DB`: durable SQLite path. Production must mount persistent
storage, not an ephemeral `/tmp` directory. SQLite uses WAL, FULL synchronous
writes and compare-and-swap revisions. Concurrent workers cannot both claim a
submit. Scaling beyond shared local SQLite requires a separately reviewed store.

`ATLAS_M18_BROWSER_RECIPES`: operator-installed JSON array of `BrowserRecipe`
records. Only pinterest, x, youtube and instagram names are eligible in deployed
configuration. Each requires exact origin, discovery/compose URLs, selectors for
account/source/content/submit/no-fee terms/receipt/receipt content/receipt account,
and correlation input/receipt correlation. An explicit `allowed_fields` array
of exact public form field names is mandatory; there is no inferred or default
allowlist. The allowlist is included in the preview and M0 approval payload.
Unknown fields, duplicate names, password inputs, unnamed inputs and external
form-associated controls are refused before value reads, fills or screenshots.
Operators must not allowlist secrets. Changing the allowlist changes the recipe
digest and requires a new run. URLs cannot leave the exact origin.
There are intentionally **no bundled real-platform recipes**: none have been
verified. An uninstalled platform returns a blocker, never pretend execution.
A site's actual no-fee terms and safe correlation readback must be reviewed
before a recipe is installed. Sites without safe supported correlation or with
sensitive form fields are blocked, not worked around. Recipe selectors are
server configuration, never caller-controlled.

The PC device must already be paired through M13, online, and explicitly granted
navigate, extract, read_values, screenshot, fill and click_submit capabilities.
Device revocation is checked for every bridge command. Existing pacing stays in
place (at least two seconds per production command).

## Failure semantics and limits

CAPTCHA/challenge, login walls and throttling pause the run. There is no automatic
retry, identity rotation, challenge solver, or evasion. A submit-time obstacle or
transport error produces unknown, not failed/succeeded speculation. A durable
submitting claim after a crash is never re-clicked. The owner must inspect or
reconcile the browser. If the receipt cannot be matched, the result remains
unknown. A crash between consuming approval and saving the submit claim cannot
create a duplicate effect: retry still requires unchanged final state, and the
claim is checked atomically before network dispatch.

This is a deliberately small execution capability, not a general side-hustle
operator. Purchases, paid experiments, messages to contacts, arbitrary actions,
multiple posts, real-site success and monetary outcome measurement are outside
this adapter. There is no frontend login-run wizard in this change. The API
returns screenshot paths for existing authenticated browser tooling; it does not
publish private screenshots. Owners must review the returned exact preview and
screenshot before approving. Raw evidence and local paths must not be shared to
external audiences by this module.

## Verification

`tests/modules/test_m18_login_browser.py` runs real Chromium with a local HTTP
fake site, the native PC Daemon, DaemonConnection, BridgedSessions, real M0 SQL
approvals, and the same production composition root. Only the site and local
websocket transport are fixtures; no browser, executor, approval, receipt or
store is stubbed. It covers login/account mismatch, sourced discovery, preview,
one actual local publication, authoritative readback, restart, duplicate and
concurrent submit, denial, revocation, changed final state, last-moment device
race, pre/post-submit crash, secret-field refusal, stale receipt, signature
tampering, tenant isolation, CAPTCHA/throttle pause and caller-forged receipts.
No test accesses a real platform, account or signup, pays, posts externally,
contacts another person or pushes a commit.

The minute cap also sets a persisted wall-clock expiry bound into the approval
payload. An expired run cannot submit even with an approved M0 request. `/stop`
lets the selecting owner stop before a durable submit claim; a claimed effect
must instead be inspected/reconciled. Lost/dismissed approvals do not authorize
execution. A stopped run cannot use its old approval.

## Hardening and recovery

Tenant, device and local session names must each be 1-128 ASCII letters, digits,
underscores or hyphens. Session IDs remain `pc.<device>.<name>`. The schema and
runner validate session IDs, and the screenshot path builder independently
validates components and checks resolved containment under `/tmp/atlas-browser`,
including existing symlinks. This is not protection against a hostile process
racing local filesystem symlink changes; the server's local filesystem remains
a trusted boundary.

An `awaiting_approval` run can be previewed again by its selecting owner. A
successful re-preview binds a fresh snapshot, expiry and new pending approval;
the old approval no longer matches that run. This recovers a first run after a
second run changes the shared browser. It does not retry a durable submit or
allow re-preview of submitting, unknown, succeeded, stopped or expired runs.
Browser operations are not serialized across runs: changing the shared page
still requires re-review. No real-site recipes or real-platform validation are
claimed.

## Round 3: form destination, form attributes, click-time rewrites, arming TTL

**Browser-resolved destination (N1).** Python `urljoin(page.url, action)` ignores
`<base href>`; Chromium does not. The preview and the device pre-click now read
the form's destination from the real DOM through the `HTMLFormElement.prototype`
accessors (so `<input name="action">` clobbering cannot spoof them) and bind
`form_facts` (`action`, `base_uri`, `base_count`, `method`, `enctype`, `target`,
`no_validate`, `on_attrs`) into the preview digest. Any `<base>` element, at
preview or on the device before the click, is rejected, and the browser-resolved
action must equal the reviewed action exactly. This needs a new read-only
`form_facts` command (it uses the paired device's existing `read_values`
capability, so no re-pairing is needed).

**Form-level attributes (N2).** Rejected at preview and again on the device:
`enctype` other than the recipe's reviewed value (`BrowserRecipe.form_enctype`,
default urlencoded), any `target`, `novalidate`, and any `on*` attribute on the
form, anything inside it, or any ancestor (including `<body onload>`; this is
deliberately strict). The form must use POST. All of it is part of the digest.

**Click-time rewrites (N3), a mitigation, not a proof.** During the approved
click the device installs (a) a capturing `submit` listener that re-reads the
browser-resolved action/method/enctype/target/base and cancels a mismatch, and
(b) a network route guard that allows exactly one request: a main-frame POST to
the reviewed URL whose urlencoded body equals the approved values (redirect hops
of that request are allowed). Every other navigation and every other non-GET/HEAD
request is aborted and reported. The runner records `guard.blocked`; a blocked
request with no approved POST ends in `approval_burned` (nothing was sent), a
blocked request alongside the approved POST ends in `unknown` with no auto-retry.
The guard is removed after the click.

Residual limits, stated plainly:
- Scripts are not blocked. Any script already running in the paired browser can
  still change the page between the final check and the click, and the in-page
  listener can be pre-empted (the network guard is tested to hold on its own).
- The network guard sees this page's HTTP requests only. It does not cover
  service workers, WebSockets, or browser-level traffic outside the page route.
- Plain GET subresource requests are allowed (so the page renders); a GET with a
  side effect to another URL is not stopped.
- Body binding is only possible for urlencoded forms. `multipart/form-data` and
  `text/plain` recipes would get destination/method binding but no body check.
- A hostile page could behave differently when it is not under review. The owner
  review of the screenshot and preview remains the primary control.

**Arming TTL (N4).** An armed approved submit now expires (`arm_ttl_seconds`,
default 120 s on the server, plus a wall-clock `deadline` the daemon enforces).
After expiry the arming is dropped, `is_armed` is false, unrelated clicks work
again, and a click on the approved control raises instead of falling back to a
navigation click. The approval itself was already consumed, so the owner must
preview and approve again. The in-memory arming is lost on a server restart, which
also frees the session.
