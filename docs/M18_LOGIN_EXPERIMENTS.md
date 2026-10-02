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


## Round 4 audit fixes (m18-login-hardening)

1. **Every CLICK_SUBMIT needs a reviewed destination preview.** The daemon has no
   preview-less click path any more. The M13 capture-bound submit and `Service.submit`
   build one before the approval is consumed (`submit_binding.build_binding_preview`:
   browser-resolved form facts, submit control, full field set, selector to field name
   map). Its digest is carried as `preview_sha256` and covered by the HMAC token.
   `authorize_submit` refuses to arm without a preview. M13 forms must therefore be
   fully described by the approved values: extra named fields, password fields,
   duplicate names, `[form]` controls and `<base>` are refused.
2. **Redirects.** Chromium follows redirects inside the network stack and never calls a
   route handler for the hops, so the old "allow redirect hops" branch never ran and a
   307/308 carried the approved body anywhere. The guard now sends the approved POST with
   `route.fetch(max_redirects=0)` and judges each hop: same-origin hops are followed by the
   guard itself (max 5; 307/308 replay the body only to the same origin), a 303 is left to
   the browser (it becomes a GET), any other cross-origin hop is aborted and reported as
   `redirect ...`. Residuals: the browser receives the final response for the original
   request, so `page.url` stays on the form action after a same-origin redirect chain; the
   guard's own fetch uses the browser context's cookie jar and headers, not byte-identical to
   a native navigation; a 301/302 same-origin hop is handed back to the browser as a GET.
3. **Replay.** The daemon keeps a consumed cache keyed by token and approval id and refuses
   a second CLICK_SUBMIT before doing anything. The cache is in memory: a daemon restart
   forgets it. To bound that, a numeric `deadline` is now mandatory on every CLICK_SUBMIT
   (arming TTL, 120 s), so a replay across a restart still has to land inside the TTL.
   A token the daemon accepted but whose click then failed is also spent.
4. **multipart/form-data and text/plain are refused**, not body-bound: `ALLOWED_ENCTYPES`
   is urlencoded only (recipe construction raises), `validate_facts` and `authorize_submit`
   refuse other encodings, and `NetworkGuard` never approves a non-urlencoded POST.
5. **`window.__atlasGuard` remains page-writable.** Not fixed. It is advisory; the
   authoritative report is the daemon-side `NetworkGuard`. A hostile page can hide what the
   page guard blocked but cannot hide a network-guard block.

## Round 5 audit fixes (m18-login-hardening)

- **F1 redirect chains.** `NetworkGuard._send_approved` now resolves the whole redirect chain itself (redirects disabled on every fetch) and hands the browser only the final non-redirect response, so Chromium never follows an unjudged hop. 301/302/307/308 hops must stay on the previous hop's origin; the single allowed cross-origin hop is a 303 straight out of the approved POST (it becomes a bodyless GET); every hop after a GET must stay on its origin; loops, missing Location and more than 5 hops are blocked and reported. Residual: the browser URL stays the form action after a redirect, and relative links in the final page resolve against it.
- **F2 token and replay.** The deadline is signed into the HMAC token (`deadline=<epoch to 3 decimals>`). The daemon persists consumed tokens/approvals to `consumed_path` (default `~/.atlas-pc/consumed_submit.json`, 0600, fsync + atomic rename) before any browser effect. An unreadable record stops the daemon from starting; an unwritable one refuses the submit. Residual: deleting that file by hand re-opens replay for tokens whose deadline has not passed.
- **F3 submit via click.** `CLICK_NAV` (daemon) and the generic server-side `click` refuse submit-type controls (submit buttons, bare `<button>` in a form, `input[type=submit|image]`, `form=` association, a `<label>` for one, a child of one). A consumed arming now refuses the next click of the same control in `BridgedSessions` instead of falling through to `CLICK_NAV`. `application_flow` binds a preview, checks the reviewed form action and arms the submit before clicking. Residual: a script can still click a non-form control that navigates by JS; that is not detectable here.
- **M13 gaps.** Approval payloads now carry `form_action`, `form_method`, `form_enctype` and `form_page_url`; execute re-binds and refuses a different destination. `dom_sha256` is compared with the live DOM at execute. Server-side (non-paired) sessions have no route guard or arming, so approved submits there are refused unless the service sets `allow_unguarded_server_submit` (tests with fake pages do).
- **F4 headers.** The re-issued request copies Accept/Accept-Language/Accept-Encoding/User-Agent/Referer/Origin/Content-Type/Sec-CH-* from the routed request. Playwright hides Sec-Fetch-*, so those are synthesized for a user-activated main-frame form navigation (`navigate`/`document`/`?1`, Site recomputed per hop). Still different: header order and casing, TLS/connection fingerprint, and HTTP version negotiation.

## Round 6 (fixes for round-5 audit V1, V2, minor)

Pessimistic notes. Nothing here is a proof.

- V1: every daemon-driven click now runs under `NetworkGuard` in baseline mode (nothing approved):
  every non-GET/HEAD request is aborted and reported, plus a page-level capturing submit blocker.
  A blocked request makes CLICK_NAV fail with the blocked list. Residuals: bodyless GET navigations
  are allowed (a GET form submit carries its data in the query string and is only caught by the
  advisory page guard); a click that causes an async POST later than ~0.25 s after the click may
  land after the guard is removed; the page guard is in the page's own JS world and can be defeated;
  only the daemon-process route guard is authoritative.
- V2: the consumed store is `{v,epoch,created_at,seq,consumed,strict,mac}` (HMAC with the command
  secret), read and written under flock on `<path>.lock`, re-read before every consume. Missing
  file under a running daemon, other epoch, lower seq, bad shape or bad MAC all refuse submits
  with a clear error; start-up never raises. A store re-created while the lock file still exists
  is `strict` and refuses tokens armed before it existed (arming time estimated as
  deadline - ARM_TTL_SECONDS, so clock skew or a longer configured TTL weakens that check).
  Residuals: someone who deletes the record AND the lock file AND restarts looks like a first
  run and is not detected; anyone holding the command secret can forge a valid record; a
  different state directory is a different store; the MAC does not stop rollback of the whole
  state directory together with a restart.
- Minor: Set-Cookie of each guard-resolved hop is added to the browser context. Honest note: the
  new test passes on the round-5 code too, because `route.fetch` already shares the context's
  cookie jar, so the explicit step is belt and braces, not a demonstrated fix.

## Round 7 (fixes for round-6 audit)

Pessimistic notes. Nothing here is a proof.

- Click guard (every daemon-driven click, CLICK_NAV and CLICK_SUBMIT): routed at BROWSER CONTEXT level,
  so popups and new tabs are guarded; installed before the click and kept until the page and any popup
  are network-idle plus a quiet period (2.5 s nav, 1.5 s armed submit). Non-GET/HEAD is aborted; any GET
  whose URL contains a current non-trivial (>=4 chars) form value is aborted; a cross-origin GET with a
  query is aborted unless it is exactly the clicked link. Popups opened during the window are closed and
  reported. Script wrappers (fetch, XHR, sendBeacon, form.submit/requestSubmit) cover keepalive requests
  at pagehide, which the network route cannot see; their reports go through a navigation-surviving
  binding plus a same-origin sessionStorage fallback.
  Residuals: the guard is time-boxed, so anything fired after the quiet period is unguarded; the owner's
  own browsing is deliberately not blocked outside a click window (the context is shared with them);
  the taint check is substring matching, so encoded, split or transformed data (base64, hashes, chunks,
  values under 4 chars) passes, and it can false-positive on a link that happens to contain a form value;
  cross-origin GET without a query, and any GET without form data, passes (path-only exfil of
  non-form data is not detected); script wrappers only cover the current document and only code that calls
  the globals afterwards (cached originals or an iframe's clean fetch bypass them); documents loaded after
  a navigation inside the window are covered by the network route only; keepalive requests issued during
  unload are visible to the script wrapper but not to the route, so a page that cached `fetch` earlier
  can still send one (the pagehide test passes because the wrapper blocks it, not because the route does);
  clicks that open `target=_blank` link navigations are treated as popups and closed.
- Consumed store: bound to the device id; signed; plus an ANCHOR (signed device/epoch/seq) in a separate
  directory (ATLAS_PC_ANCHOR_DIR, default ~/.atlas-pc/anchors) shared by every record path of the
  device. A record whose seq is below the anchor (older snapshot, even across a restart), whose epoch is
  not the anchor's, or that is missing while an anchor or lock file exists (strict re-creation) is
  refused or strict. A store error is sticky until restart. Out of scope and honestly open: an attacker
  who can write both the state dir and the anchor dir and holds the command secret; deleting record,
  lock file and anchor together; the anchor is a file, not an OS keychain or hardware counter; arming
  time for the strict check is estimated as deadline - ARM_TTL_SECONDS, so clock skew or a longer
  configured TTL weakens it; a token armed before a record loss with an arming time inside the
  estimate error can pass; two different device ids are two stores by design.
- Set-Cookie: own parser. Max-Age beats Expires; a past Expires or Max-Age <= 0 deletes via
  clear_cookies; quoted values kept verbatim; no comma splitting; Partitioned maps to a partition key
  (needs Secure; the key is the hop's own site, not necessarily the top-level site); Domain must
  match the host; Secure needs a secure context; __Secure-/__Host- and SameSite=None rules enforced.
  Not implemented: public-suffix checks on Domain, cookie size/count limits, Priority, SameParty.

## Round 8 (fixes for round-7 audit)

Threat-model statement first. The page under the daemon is untrusted and runs its own scripts. The guard
stops what a daemon-driven click, and the document that click produced, can send. It cannot stop a page
from sending data the page itself already holds, before any click, and it cannot give a proof. Anything
below marked "open" is open.

- Guard lifetime (finding 1): the guard is no longer removed after a quiet period. It RESTS on the session
  page for the life of that document and is lifted only when the daemon replaces the document (NAVIGATE),
  closes the session, or starts the next guarded click. Timers at 6 s and 12 s, EventSource reconnects and
  service-worker messages therefore meet the guard. After an approved submit a baseline guard is left on the
  resulting document the same way.
- Network policy (finding 2), baseline mode: non-GET/HEAD aborted; websocket/eventsource/ping/beacon resource
  types aborted; requests from service workers aborted; every cross-origin request aborted unless it is exactly
  the clicked link as the page's top-level navigation; same-origin GETs allowed only for URLs already present
  in the page before the click (resource timing entries, src/href/action attributes) and, after the click's own
  top-level navigation, plain assets (no query) of the new document; the substring taint check is kept as a
  second layer only. Popups: the opener is asked, a page created during the click window counts as a popup,
  and a navigation whose frame does not exist yet (a popup's first request) is aborted in the window. Popups
  are closed and reported. Foreign tabs of the shared browser are passed through untouched.
  Injected in the live document: a CSP meta (default-src 'self', connect-src 'none', form-action 'none',
  frame-src 'none') plus wrappers for fetch/XHR/sendBeacon/WebSocket/EventSource/window.open/form.submit.
  The document a click navigates to is delivered with the same CSP plus `sandbox allow-scripts
  allow-same-origin` (no popups, no form submission), redirects handed back unfollowed so each hop is judged.
  Open: after the click's navigation, same-origin plain-asset GETs of the new document are allowed, so that
  document's own scripts can still send path-encoded data to its own origin by requesting an asset path;
  cross-origin assets (CDN scripts, fonts, images) of a guarded page do not load, so real pages render
  degraded after a guarded click; a popup first request after the click window and before the page has a
  frame cannot be told from a tab the owner opened and is passed through; CSP meta and wrappers can be
  undone or bypassed by hostile script (cached originals, an iframe, removing the meta) and are layers, not
  controls; prefetch requests are not seen by Playwright's route at all, the CSP is what stops them; a page
  loaded by NAVIGATE is unguarded until the first guarded click.
- Store (finding 3): the record pins two anchor directories (ATLAS_PC_ANCHOR_DIR or ~/.atlas-pc/anchors, and
  ATLAS_PC_ANCHOR_DIR2 or /var/tmp/atlas-pc-anchors-<uid>); both anchors are signed, keyed by device id and
  pin the same directories; any change of those directories, any anchor with another epoch, a record below the
  highest anchor seq, or no anchor at all for an existing record is refused. An unset consumed_path now means
  a per-device default file, never memory-only. Open and not detectable: restoring the record AND both anchors
  together (a full home plus /var/tmp snapshot restore); deleting record, lock file and all anchors; anyone
  holding the command secret; a re-created (strict) record cannot tell a token armed after loss from a token
  the auditor crafts with a future deadline, because the server's signature, not the device, fixes arming time.
- Cookies (finding 4): empty-name cookies ("=v", or "v" with no "=") and names with spaces are now stored as
  Chromium stores them; Max-Age and Expires are clamped to 400 days so a huge value no longer makes
  add_cookies throw. Still not implemented: public-suffix checks, size/count limits, Priority.

## Round 9 (audit of round 8 failed)

The round-8 audit found: another same-origin tab can be handed the secret over BroadcastChannel and POST
it unguarded (A); WebRTC/ICE reaches UDP and DNS (B); a same-origin top-level navigation or asset path
can carry data (C, C2); a cached `window.open` after the click window opens a cross-origin popup (D);
an old store record plus the old primary anchor with the secondary deleted was accepted; Max-Age with
underscores or non-ASCII digits gave an expiring cookie where Chromium gives a session cookie.

What changed:

- A: session pages run in their own browser context (`BrowserHandle._session_context`), seeded once with a
  copy of the owner's storage state. No other tab of the site shares its storage, BroadcastChannel or
  workers. `BroadcastChannel`, `SharedWorker`, `RTCPeerConnection` are also blocked in the page script.
  Limits: this needs a Browser object. A persistent-profile launch has none, so there the session shares the
  owner's context and the isolation is NOT in force (`BrowserHandle.isolated` is False). Logins the owner
  makes after the first session page are not copied. Page script wrappers are a backup layer only.
- B: launch flags `--disable-quic` and `--force-webrtc-ip-handling-policy=disable_non_proxied_udp` for a
  browser the daemon launches. They are NOT applied when attaching over CDP. `--host-resolver-rules` is not
  applied: the site host is unknown at launch, so DNS exfiltration from a CDP-attached browser stays open.
- C: after a guarded click, exactly one top-level navigation is allowed, and only to the clicked link or a
  URL already in the previous document's markup. Anything else (`/idea/<b64>`, `/idea?d=...`, timers) is aborted.
- C2: subresources of the new document are allowed only if the URL appears in the old or new document's
  markup. Side effect: assets referenced only from scripts will not load on the page after a click.
- D: in an isolated context any unframed navigation (a popup's first request) is aborted at all times.
  In a shared context the old behaviour (abort during the click window only) remains.
- Store: for a record in use BOTH anchors must exist; one missing means refuse.
- Cookie: Max-Age is honoured only when it matches `[+-]?[0-9]+` in ASCII. Chromium is the oracle
  (tests/modules/cookie_diff_chromium.py, run as a test).

Limits that remain, plainly:

- A full snapshot restore of the record and both anchors is not detectable. Neither is deleting
  everything (record, both anchors, lock file): the store then looks like a first run.
- A process running as the same OS user can write all device state.
- The Playwright route cannot see keepalive requests during unload, prefetch, or a popup's first request in a
  shared context. CSP and script wrappers are layers, not controls.
- Network containment (host-resolver rules, proxy refusal) is not enforced for a CDP-attached browser.

All auditor vectors stay as permanent tests: test_zz_auditor_r8.py, test_zz_auditor_store.py,
cookie_diff_chromium.py, and test_m18_login_round9.py.

## Round 10 (audit of round 9 failed)

Findings: (F1, both modes) "pre-listed markup": page script adds an anchor whose href encodes the draft
on the input event; the click-time DOM read then listed it as known, and same-origin Image().src or
location.href to it reached the server. (F2, CDP) RTCPeerConnection through an iframe's contentWindow, a
srcdoc iframe, or a cached constructor reached UDP; an attached browser gets no launch flags.

Corrections to round-9 claims: the round-9 docs implied the launch flags stop WebRTC. They do not
reliably: the round-9 tests ran plain `chromium.launch` and never exercised `launch_args()`, and a live
probe shows `--force-webrtc-ip-handling-policy=disable_non_proxied_udp` alone still lets STUN to a
loopback socket out. What stopped the vectors was the page-script layer, which only covers script-created
frames.

What changed:

- F1: the set of known URLs is now a SNAPSHOT of the URLs in the server's HTML response for the top
  document, taken in the response handler at load, before anything was filled. The click-time DOM is not
  read for it. The clicked link's href is kept only if the server shipped it. No snapshot (document not
  seen as a response, e.g. after history.pushState to a new URL) means nothing is pre-approved.
  Consequence: a link or asset a script adds after load is never allowed after a guarded click.
- Taint matching now covers raw, percent-encoded twice, reversed, separator-chunked, base64 (standard and
  urlsafe, any offset of the token) and hex forms of every filled value. This is defence in depth; a keyed
  or compressed encoding passes it, which is why the snapshot, not the matcher, is the control.
- F2: `FRAME_DENY_JS` is installed with `add_init_script` on every session page, so it runs in every frame
  (iframes, srcdoc) before page script, and defines RTCPeerConnection, webkitRTCPeerConnection,
  RTCDataChannel, WebTransport, BroadcastChannel and SharedWorker as non-configurable constructors that
  throw. This replaces WebRTC for session pages (no video calls in a guarded session). It is a script
  layer; a browser bug or a frame that runs before init scripts would bypass it.
- CDP fails closed: a guarded CLICK_NAV or CLICK_SUBMIT on a CDP-attached browser is refused with a clear
  error unless the owner set `cdp_containment_attested` AND a live probe passes. The probe opens a page
  exactly like a session page and tries ICE directly, via iframe.contentWindow and via srcdoc against a
  local UDP socket; any packet refuses. It probes the script layer only. DNS, proxy and QUIC settings of
  an attached browser are attested, never verified (`Browser.getBrowserCommandLine` needs --enable-automation).
  A negative control (deny script emptied) shows the probe does refuse.
- Launch (browser the daemon starts): `--disable-quic`, `--no-proxy-server`, the WebRTC policy flags, and
  with `site_hosts` set `--host-resolver-rules="MAP * ~NOTFOUND, EXCLUDE <hosts>"`, so a secret cannot
  leave as a DNS name. A configured `--proxy-server` or `--proxy-pac-url` raises. With no `site_hosts`
  no resolver rule is added and DNS exfiltration is not contained. Tests now start the browser through
  `BrowserHandle.start()` and check that only the site resolves.

Limits that remain: as round 9 (snapshot restore, delete-everything, same-OS-user writes, a persistent-
profile launch shares the owner's context so cross-tab isolation is not in force there); plus: the
snapshot is only as good as the server HTML (an XSS-free page is assumed); the page-script layer is not a
network control; in CDP mode DNS and proxy containment are owner-attested.

Auditor vectors kept as permanent tests: test_zz_my_r9.py (+ mymode_fixture.inc) driven by
test_m18_login_round10.py in MODE=persistent, MODE=cdp, and MODE=cdp ATTEST=1.
