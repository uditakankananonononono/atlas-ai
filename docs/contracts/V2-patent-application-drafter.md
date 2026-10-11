# V2 patent-application-drafter (module c37.patents) - claim-draft delta

Provenance line: cross-account builder package, provenance held privately.
Status: candidate on base 475f5f3907bb5aed4f6e9fecdb8dcac7a5db4924, not independently accepted or landed.

## HER WORDS
"see new ideas/ventures and develop its own patent applications"

(DESIGN below is spec-author scope text, not her words. The exact quote was verified against the local authenticated carrier privately; source identifier and narrow quote pin are recorded in the accompanying gate floor note, not in this shareable contract.)

## What the code does
`backend/app/modules/c37/patents.py`, entry point `run(request) -> dict`. From a SUPPLIED invention record and SUPPLIED prior-art records it emits claim DRAFTS only. Every claim and the set carry `DRAFT NOT FOR FILING`.
- Claim 1: `1. A <title> comprising: <c1>; <c2>; ...; and <cn>.` Dependent claims 2.. one per novel feature: `<k>. The <title> of claim 1, wherein <feature>.`
- `invention.owner == "self"` is a caller assertion, recorded as `owner_assertion: caller_supplied, unverified`. No ownership or inventorship check.
- `prior_art` records are unverified caller data, returned unchanged in input order as `prior_art_passthrough`.
- `novelty_input` ({source "c32.ideate", value 0..1}) is echoed labelled caller_supplied, unverified; rounded to 6 places; never used to decide anything.
- Uses the real `policy.clean_text` and `policy.scope` from c30. policy not applicable for `policy.check`: no action path, no spend/outreach/fakeacct/autopost/scrape/trade surface.
- Overlap, Jaccard and novelty are NOT computed here (c32/ideate.py does that).
- No HTTP handler, no registration, `c37/__init__.py` untouched.

## LIMITS
Not legal advice, not a prior-art search, no overlap or novelty computation, no filing, no claim that anything can be protected.

## Input schema (any other key is refused UNKNOWN)
top {as_of YYYY-MM-DD, invention, prior_art, novelty_input}; invention {id, owner, title, summary, components, novel_features}; prior_art item {id, title, url https}; novelty_input {source, value}.
Caps: invention id/title/summary and each list item <= 500 chars; components <= 30; novel_features <= 30; prior_art <= 200 entries (id/title <= 500, url <= 2000).

## Refusal table (ValueError text `INTEL_REFUSED_<REASON>[:field]`)
| Reason | When |
|---|---|
| INTEL_REFUSED_FILE:<key> | key in file, submit, uspto_submit, epo_submit, grant (any depth) |
| INTEL_REFUSED_SEND:<key> | send-class key (send, approve, approved, approval, approval_token, smtp, token, email_send, sender, smtp_host, smtp_port, smtp_user) |
| INTEL_REFUSED_SPEND:<key> | pay, purchase, spend, buy, checkout, card_number |
| INTEL_REFUSED_NOCREDS:<key> | login, password, username, credentials, otp, api_key, access_token, refresh_token, bearer, pass, passwd |
| INTEL_REFUSED_UNKNOWN:<parent> | unknown key (parent is request, invention, prior_art or novelty_input) |
| INTEL_REFUSED_BAD_TYPE:<field> | request, key, as_of, invention, components, novel_features, prior_art (bad entry, bad url, duplicate id), novelty_input, id/title/summary text hygiene |
| INTEL_REFUSED_EMPTY:<field> | empty components or novel_features |
| INTEL_REFUSED_PRIORART_MISSING:prior_art | prior_art absent, None or empty |
| INTEL_REFUSED_NOT_OWNER:owner | owner is not exactly the str "self" |
| INTEL_REFUSED_OVERSIZE:<field> | over a cap, checked before text hygiene; field is id, title, summary, components, novel_features, prior_art (list length), or for a prior_art entry leaf: id, title, url |
Key match: casefold, "-" to "_", exact, no substrings. Precedence SEND > SPEND > FILE > NOCREDS, alphabetically-first key within a class. Suffixes are schema field names or table constants, never request-derived text.

## Validation order
(1) dict, (2) forbidden-key scan, (3) non-str key, (4) unknown key, (5) types then empties (components, novel_features, then prior_art missing), (6) caps, (7) per-field validation (id, owner, title, summary, components, novel_features, prior_art, novelty_input), (8) compute.
Builder reading of two spec points: an empty components/novel_features list gives EMPTY, an absent or non-list one gives BAD_TYPE; a prior_art entry failing text hygiene (blank, control chars) gives BAD_TYPE:prior_art.

## Mutation battery (builder's own, hand-written, 72 mutants, one at a time)
Historical source candidate round 1: 68 killed, 4 survived (M02, M24, M45, M56). Round 2 after one added test: 69 killed, 3 survived. Round 2 is not independent of round 1 because the test was added after seeing the survivor.
Survivor dispositions (builder claims, for the auditor to check, not facts):
- M02 (drop the str check on owner): the `!= "self"` test already refuses every non-str, so the extra clause is redundant. Claimed equivalent.
- M24 (drop isfinite): NaN and inf fail the `0 <= v <= 1` range test anyway. Claimed equivalent.
- M45 (re.match instead of fullmatch for as_of): strptime refuses trailing text, so same refusals. Claimed equivalent.
- M56 (an extra id hygiene pass before caps): killed by the added oversize-before-hygiene test for id, title and summary.

## Unicode hygiene extension (DESIGN, not owner quote)

After caps (len before strip), every supplied string used in an echoed output is checked for Unicode Cc/Cf/Zl/Zp and refused as INTEL_REFUSED_BAD_TYPE:<schema container field>. This includes invention id/title/summary, component and feature items, prior-art id/title/url, and any text reaching a generated claim. Zs is permitted inside text, but URLs refuse any whitespace and Cc/Cf/Zl/Zp/Zs. Prior-art leaf hygiene maps to BAD_TYPE:prior_art. Date and novelty source have exact format/literal validation and never echo invalid values. Owner values never echo; only a constant unverified assertion does. Input dict keys do not echo: unknown keys use the constant schema parent suffix and forbidden keys map to constant normalized tables. Output dict keys and all reason suffixes are code constants, not caller paths. Caps win over Unicode errors; the offending text, index, character and category never appear in errors. Real policy.clean_text and policy.scope are still called without fallback; local prechecks add Cf rejection and map hygiene to the required unit codes.

## Current candidate verification

68 focused tests pass with Python 3.12.14 and the actual repository conftest. New pins were run RED before implementation: missing-module test suite first, then Cf-echo failures against the prior candidate before Unicode changes. Fresh AST battery over this candidate: 310 mutants, 303 killed, 7 SURVIVED, zero non-compile. Every outcome and survivor disposition is in the gate packet. Layered Cc/Zl/Zp checks have redundant refusals with real policy.clean_text; Zl/Zp/Zs URL categories also match isspace. Fieldless _refuse suffix fallback has no callsite and is not claimed as killed. Independent gate review remains required.

## Caller-boundary resource delta (program DESIGN ruling)

Shape/key/resource preflight now runs FIRST, before forbidden scan, then unknown/schema validation. This supersedes the old forbidden FILE:grant-before-non-string-key pin: malformed key now returns BAD_TYPE:key. Content scanning of hostile unbounded shapes was itself unsafe (cycle RecursionError reproduced RED), so it is admitted only after bounded shape checking. Forbidden class precedence remains unchanged among admitted inputs.

All caller dictionaries, lists and required strings are exact built-ins; subclasses are refused by the applicable BAD_TYPE container/field or NOT_OWNER:owner gate. Numeric novelty value is exact int/float, range-checked before isfinite; 10**1000 refuses BAD_TYPE:novelty_input rather than OverflowError.

Three resource layers: schema dictionaries are enum-bounded envelopes with no total-key cap, retaining shape-valid FILE/SEND/UNKNOWN code behavior; unbounded data collections are count-first (components/features 30, prior-art list 200, other nested list/dict 200); whole-payload iterative preflight limits depth to 32 and total nodes to 10000 including dict keys. Collection size checked before child entry allocation or content key-set construction. Caps refuse OVERSIZE:<constant schema container field>, cycles refuse BAD_TYPE:request. No arbitrary caller key/path enters a reason. Cycles and subclasses are refused before the recursive forbidden/key scan; admitted depth/count keep those scans bounded. These limits deliberately reject hostile payloads and preserve ordinary schema-valid inputs; they are not a claim that previously accepted unbounded payloads remain accepted.

### Repair evidence

Fresh subclass/cycle/huge-int tests were RED (3 failures) before repair. Final real-conftest run: 81 passed. Repair battery: 381 AST mutants, 354 killed, 27 SURVIVED, zero non-compile; all raw outcomes and dispositions retained. Resource preflight/late checks and layered hygiene create redundant checks, but allocation-timing survivors are not called equivalent. Independent gate review required.

## Round-2 resource repair

Raw dictionary keys are exact str and capped at 200 characters before casefold/replace, including unknown keys; 201 or more yields constant OVERSIZE:key, with no raw text echoed. Within the cap, matched table normalization/precedence is unchanged. The global prospective nodes + len(node) check now precedes BOTH child comprehensions, not only stack insertion. The earlier floor incorrectly claimed this allocation order; that statement is corrected by this child. Tests include 200/201, a 10MB key refusal, distinguishing budget-before-child error, and structural source order to prove the guard exists before children allocations.
