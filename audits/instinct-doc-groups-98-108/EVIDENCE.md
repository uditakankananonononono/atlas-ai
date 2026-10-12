# Instinct-doc groups 98-108: PARTIAL -> LANDED evidence

Pinned base: atlas-ai `4163f497f38420a7f755501034549fc9e2e4a4b0`.
Each group below names the audit gap, the unit that closes it, the test
evidence, and the honest boundary of the landing. Every module is stdlib-
only, offline-deterministic unless marked LIVE (those use the new bounded
`c30.public_http` fetch helper, exercised hermetically against local test
servers). Test counts are from `python3 -m pytest` on the listed files.

## Shared infrastructure

- `backend/app/modules/c30/public_http.py` + `tests/modules/test_c30_public_http.py` (10 tests).
  The ONLY network path for the LIVE units: HTTPS-only in production,
  exact host allow-list, robots.txt honored, per-host throttle, conditional
  GET (ETag/Last-Modified), body cap, redirect re-validation, no credentials.
  `allow_http` exists solely for hermetic local-server tests.

## Group 98 - college essay excellence engine

- Gap closed: "winning-material package not inspected or judged".
- `backend/app/modules/m23_study_abroad/essay_excellence.py`: eight-criterion
  deterministic rubric (readability, specificity, evidence linkage,
  reflection, originality, hook, structure, length fit) with published
  formulas, prompt-alignment check, measured revision-over-revision deltas,
  per-college package assembly with completeness status.
- `tests/modules/test_m23_essay_excellence.py` (7 tests): strong draft
  measurably outscores weak draft; revision delta positive; package refuses
  any non-student-confirmed essay.
- Boundary: analyzes student-authored drafts only; generates no prose; no
  admission/award prediction.

## Group 99 - olympiad registration + fee waivers after review

- Gap closed: "no account/register/send execution" -> the request's own bar
  is "after review": a full review-gated pipeline.
- `backend/app/modules/c35/registration_pipeline.py`: composes
  c35.olympiad checklist/prefill + c35.waiver_drafts into a state machine
  (draft -> pending_review -> owner_approved -> handoff_exported) with
  exact-artifact-hash approval; terminal state writes a local handoff bundle
  (packet.json + waiver.txt + README.txt) for the owner.
- `tests/modules/test_c35_registration_pipeline.py` (9 tests): full flow,
  waiver skip on free events, reject path, nested forbidden-key refusals
  (send/register/pay/login/attempt).
- Boundary: Atlas never registers, submits, emails or pays; handoff is
  local files the owner acts on.

## Group 100 - olympiad/quiz attempt capability (PRACTICE/SIMULATION ONLY)

- Gap closed at the platform limit: practice/simulation engine. Live-exam
  assistance is refused in code, not prose.
- `backend/app/modules/c35/practice_engine.py`: timed simulation sessions
  (answers never in session payloads), scoring with per-tag analytics,
  cross-session history, weakest-first spaced study plan, award-eligibility
  tracker against supplied PUBLIC criteria.
- `tests/modules/test_c35_practice_engine.py` (6 tests): session/scoring/
  plan/award loop; LIVE_EXAM refusals on keys and on live-sourced questions.
- Boundary: practice metrics are not olympiad scores; no award is promised;
  no real exam is ever attempted or assisted.

## Group 101 - Common App preview from portfolio ZIP

- Gap closed: "actual prior ZIP and complete personal preview not verified".
- `backend/app/modules/m23_study_abroad/common_app_preview.py`: real ZIP
  reader (profile.json, activities/, honors/, essays/), validation against
  Common App published constraints (10 activities, 150-char descriptions,
  5 honors, 650-word essays, required profile fields), full section-ordered
  markdown preview with per-section status and violation list.
- `tests/modules/test_m23_common_app_preview.py` (8 tests): complete preview
  renders; missing fields, over-limit activities/essays flagged; path
  traversal and bad zips refuse; unknown members reported, never executed.
- Boundary: preview only - nothing submitted, signed or attested.

## Group 102 - continuous huge-data processing

- Gap closed: "synthetic batch benchmark, not sustained ingestion".
- `backend/app/modules/c32/continuous_ingest.py`: drop-directory worker -
  chunked reads, atomic crash-safe checkpoints, dedupe persisted across
  runs, backpressure reporting, bounded memory (one batch), throughput
  ledger measured on real clock time (records/s, MB/s) accumulating across
  runs.
- `tests/modules/test_c32_continuous_ingest.py` (6 tests): multi-run
  continuation, cross-run dedupe, crash-resume without double counting,
  backpressure flag, malformed-line accounting, 5k-record batch run.
- Boundary: ingests the supplied inbox only; nothing fetched.

## Group 103 - cross-field leader analysis and integration

- Gap closed: "no cross-field autonomous knowledge/build loop".
- `backend/app/modules/c37/cross_field_loop.py`: analyze -> propose ->
  queue loop: leader method records x other-field problems -> evidence-
  ranked transfer proposals -> integration tickets in m14 intake shape
  (owner_review status).
- `tests/modules/test_c37_cross_field_loop.py` (5 tests): cross-field-only
  proposals, evidence-count ranking, ticket shape/cap, evidence-required
  refusal, no automatic build.
- Boundary: supplied records only; tickets queue for owner review.

## Group 104 - government/elite R&D monitoring (PUBLIC SOURCES ONLY) [LIVE]

- Gap closed: "fixture registry diff only; no live fetching".
- `backend/app/modules/c37/live_watch.py`: fetches supplied feed URLs on
  each registry source's own hosts through c30.public_http, parses RSS 2.0 /
  Atom (stdlib), feeds items into the EXISTING c37.public_record diff
  (CLASSIFIED/NOSOURCE/PRIVATE refusals still apply after parsing), handles
  304 not-modified, reports fetch metadata.
- `tests/modules/test_c37_live_watch.py` (7 tests, hermetic local server):
  RSS + Atom parse into the real diff, second-run dedupe, unknown-source and
  off-registry feed-host refusals, unparsable refusal, a planted
  "TOP SECRET" feed item refused CLASSIFIED by the downstream diff.
- Boundary: public registry sources only; cannot see or confirm classified
  content; no crawling - only the supplied feeds.

## Group 105 - viral app/content engine across niches

- Gap closed: "no built viral apps".
- `backend/app/modules/c33/app_forge.py`: forges complete runnable static
  apps (index.html + webmanifest + README) carrying engineered-virality
  mechanics (Web Share API + clipboard fallback, referral counter, interest
  capture with local JSON export, ref-param attribution); hook-scored
  content calendar; batch forging with cap.
- `tests/modules/test_c33_app_forge.py` (6 tests): files written and
  complete, mechanics present in the generated HTML, deterministic output,
  calendar scoring, batch cap, AUTOPOST key refusals.
- Boundary: virality is engineered mechanics, not a measured viral outcome;
  apps are local files, never deployed or posted.

## Group 106 - literature -> knowledge -> product invention

- Gap closed: "finite local ingestion... invention unverified".
- `backend/app/modules/c36/invention_pipeline.py`: supplied corpus ->
  concept extraction (terms + phrases) -> co-occurrence graph ->
  cross-document concept pairs -> ranked invention briefs with full
  provenance (document ids + character spans), coverage counts explicit.
- `tests/modules/test_c36_invention_pipeline.py` (5 tests): end-to-end
  briefs carry provenance spans; briefs combine concepts from different
  documents; deterministic graph counts; caps enforced.
- Boundary: supplied corpus only (universal_coverage=False reported);
  briefs are hypotheses for owner review.

## Group 107 - top high-school competition discovery [LIVE]

- Gap closed: "curated registry, not exhaustive verified coverage".
- `backend/app/modules/m01_opportunity_discovery/competition_live.py`:
  fetches supplied public listing pages, extracts competition-keyword link
  candidates, VERIFIES each official URL by fetching it at run time,
  dedupes against the supplied registry, emits additions with provenance
  (listing page, anchor text, fetch date, verification status) and coverage.
- `tests/modules/test_m01_competition_live.py` (5 tests, hermetic local
  server): discovery + verification split (reachable vs not), off-allow-list
  links never fetched, dedupe on second run, HTTPS required in production.
- Boundary: bounded to supplied listing pages - never claims exhaustive
  coverage; verification = fetched OK at run time, nothing more.

## Group 108 - personal brand + owner-run earning agencies

- Gap closed: "planning/drafts only, no agency machinery".
- `backend/app/modules/c36/agency.py`: deterministic brand kit, priced
  service catalog, full client CRM (lead -> qualified -> proposal ->
  owner-approved -> delivered -> invoice -> paid), proposal/invoice
  DOCUMENT generation with exact-draft-hash approval, revenue ledger
  (totals, receivables, per-client) over owner-supplied payment records.
- `tests/modules/test_c36_agency.py` (9 tests): deterministic kit, catalog
  validation, state-machine skips refused, wrong-hash approval refused,
  invoice/payment/ledger totals, OUTREACH/AUTOPOST/CHARGE/SPEND refusals.
- Boundary: documents only - nothing sent, charged or collected; payments
  are owner-recorded facts; revenue is a sum of records, not a promise.

## Verification

- New tests: 74 across 12 files - all pass.
- Adjacent existing suites re-run clean (c30 policy, c32 ingest,
  c33 niches/content, c34 industry, c35 olympiad/waiver, c36
  concepts/blueprint, c37 leaders/public_record, m01 high-school): 280
  passed + 188 subtests.
- Pre-existing environment limitation (not caused by this series):
  `test_m23_esai_parity_07_27.py` and `test_m23_esai_remaining_parity.py`
  need Python >= 3.11 (`enum.StrEnum`); this sandbox runs 3.10.

## What this series deliberately does NOT claim

- Winning olympiads, awards, scholarships or admissions (outcomes are never
  claimable; practice/simulation and preparation are what landed).
- Live-exam assistance of any kind (refused in code).
- Measured virality or monetized business outcomes (mechanics and machinery
  landed; outcomes belong to the real world).
- Exhaustive competition coverage or universal knowledge coverage (bounded
  discovery/ingestion with explicit coverage counts landed).
- Any send/register/submit/charge execution (all such paths are refusals).
