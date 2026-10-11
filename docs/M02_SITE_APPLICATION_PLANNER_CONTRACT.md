# Per-site application draft planner

## Design rationale

Preparing an application needs a snapshot of the target form, explicit answers with
sources, and a reviewable draft. This module implements only that offline preparation
step over supplied snapshots and facts. It does not research competitions, visit
sites, fill any live website or submit anything.

## Existing mechanism and delta

Existing mechanisms on the base this change builds on:
m13_browser_agent/application_flow.py extracts descriptors, stages approved
fields, reads them back and separately gates submission. m02 application_pipeline.py
prepares answer review packages. Neither file is changed here.

Delta: per-site snapshot form map, explicit fact-to-field binding, draft values,
source excerpts, missing required fields, snapshot/draft hashes and a disabled
m00-required proposal descriptor. No site-specific adapters, dossier research,
answer-generation model, integration wiring or browser execution is claimed.

## Interface

`plan_application(site_url=..., html=..., facts=..., bindings=..., sources=...,
challenges=[])` is a stdlib-only deterministic preparation function.

site_url and source URLs must be credential-free HTTPS. HTML is at most one
million characters. Source records require unique id, URL and nonempty excerpt.
The code does not verify source truth, authorship, completeness or freshness.
Facts are supplied text values with known source_ids. A bound fact value must be nonempty text with no
Cc, Cf, Zl or Zp characters (including newlines and tabs, so multi-line answers are refused by
design); refusal names no value. String subclasses are accepted for fact values; this is not an exact-string boundary. A binding value must be an exact string naming a fact key; a
list, dict, number or str subclass is refused with an APPPLAN error. facts, bindings, each source
and each fact must be exact builtin dicts; dict subclasses are refused before any method of theirs runs. Bindings explicitly map
observed field IDs/names to fact keys; no semantic matching or invented answers.
Credential-shaped fact keys are refused at binding time. The key is lowercased and every
non-alphanumeric character removed, then refused if it contains password, passcode, token, secret,
apikey, privatekey, creditcard, cardnumber, securitycode, socialsecurity, ssn, routing,
accountnumber or cookie (substring match, so credit_card_number and session_cookie are covered),
or equals cvv, cvv2, cvc, pin, otp, mfa or iban (exact match, so pinecone is accepted). This is a
denylist, not a detector, and substring tokens can over-refuse harmless keys (for example a key
containing "token" or "ssn" inside another word). Ordinary personal facts stay local to
the caller; do not log or publish real application values.

HTMLParser maps input, textarea and select fields. Hidden/buttons/submits are
excluded. Duplicate identifiers or controls without id/name are refused rather
than guessed. Select values must match supplied option values. Disabled fields
cannot be bound. File/checkbox/radio/password/tel controls require separate manual
handling and are not filled by this mechanism. Required unbound fields are
reported. No label-based selectors or live DOM claim is made.

CAPTCHA, phone, ID, payment and credential challenge markers halt draft fill.
Explicit observed challenges always stop. Text/attribute detection is a
conservative heuristic: false positives and missed dynamically loaded challenges
remain possible. The payment marker deliberately matches the words payment, credit card, checkout
and application fee anywhere in the HTML, so a page that says "No payment required" is also
blocked; this false positive is the safe direction and is kept on purpose. This is not a real-site challenge detector. Live integration
must inspect the actual site and stop on those challenges independently.

Output includes source excerpts and form map, exact supplied draft text, required
missing fields, blockers, SHA256 of HTML and sorted draft values, and status.
The handoff says m00/proposal_only/requires_exact_review. It does not create an
approval, accept an approval or execute a send, post, click, spend or submission.
submission_enabled and browser_action_performed remain false. Existing m00 and
m13 flows would need a separate reviewed integration. Callers must not treat
this descriptor as authorization.

## Limits and missing inputs

No bookmarked websites visited or researched, no live form filled, no competition
entered. Real application work needs official current pages/HTML, a reviewed
profile and answers, the applicant's own site accounts, and per-site source/terms checks.
Supplied source excerpts can include misleading content. The mechanism does not
validate claims, synthesize essays, infer eligibility or replace human review.

No CAPTCHA/phone/ID/payment bypass. No impersonation, altered reposts, external
messages, paid models or spending. No AGI, discovery, guaranteed wins or universal
site coverage claims. Static field IDs can become stale; hashes identify a
snapshot but do not establish that the live form still matches it.

## Verification scope

The tests in tests/modules/test_m02_site_application_planner.py run synthetic static HTML
through the real parser and planner. Fixtures are not claimed as live sites. They pin the four
safety flags (submission_enabled, browser_action_performed and source_facts_verified exactly
false; handoff requires_exact_review exactly true), the draft digest, the HTML and URL gates,
the credential denylist, fact-value character refusal and the exact-dict refusals. Not run: the
full suite, mounted routes/auth/tenant, a live browser, visual layout or any end-to-end submit.
Browser/approval integration and independent acceptance remain separate.
