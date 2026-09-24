# Atlas module enhancements

Status legend: **Landed** is working code with a named test. **Next** is a proposed enhancement, not an implementation claim.

## M00 - Human Approval Center
- **Landed:** approval impact preview. Modules register read-only state probes, and `POST /approval-center/requests/{id}/review-state` snapshots what the reviewer saw. `GET .../impact-preview` shows the exact effect payload against reviewed and live state with a dotted-path drift list. `/consume` and the Celery executor now run `consume_effect_checked`, so drift since review blocks the permit (409 plus the drift list, audited as `effect_blocked_drift`), and a snapshot with no probe fails closed. Test: `tests/modules/test_m00_impact_preview.py`.
## M01 - Opportunity Discovery
- **Next:** deadline-change monitor with source snapshots and owner-visible eligibility deltas.
## M02 - Competition Manager
- **Landed:** evidence completeness score (`evidence.py`, `POST /competition-manager/evidence-completeness`, and `evidence_completeness` on integrated applications): each drafted claim must cite `[n]` to an owner-profile source whose text shares its specific terms, or carry `[NEEDS INPUT]`; unsupported and uncited claims are listed, and the package is only `complete` when none remain.
- **Landed:** evidence scoring reads the tenant's stored profile corpus: `source_ids` (the ids the drafter saw, now returned as `evidence_source_ids` on integrated applications) load in marker order so citations cannot drift; `question` re-runs the drafter's retrieval and is flagged `marker_drift_possible`; missing, cross-tenant or empty-corpus sources block `complete` (`tests/modules/test_m02_evidence_corpus.py`).
- **Next:** semantic entailment check (free local NLI model) on top of the term-overlap support test, so a paraphrase citing the right source with wrong facts is caught.
## M03 - Grant Writer
- **Landed:** deterministic science-grant preflight parses explicit word limits, budget caps, required attachments, evaluation criteria and unresolved `[NEEDS INPUT]` placeholders without inventing rules.
- **Landed (science):** versioned agency schema packs (`schema_packs.py`, `data/schema_packs/<agency>/<program>/<version>.json`, `/grant-writer/schema-packs*`). Every rule carries the verbatim sentence it came from plus source URL and retrieval time; packs without anchors are rejected. `check` reports missing documents, page overruns, missing separate headings, URLs/DOIs where forbidden, too few reference writers and the deadlines for the applicant's field (timezone-exact); `diff` tracks amendments between versions; `verify-source` re-reads the public call and flags any anchor that no longer appears. First pack: NSF GRFP, NSF 26-526 (FY 2027), captured 2026-09-24 and verified against the live page (`tests/modules/test_m03_schema_packs.py`).
- **Next (science):** more packs (NIH F31, NSF CAREER, DOE CSGF) and a scheduled verify-source run that opens a review item when anchors disappear.
## M04 - Research Scientist
- **Landed:** downloadable computational reproducibility bundle with analysis code, input/parameter snapshots, SHA-256 input and manifest identity, dependencies, seed, source URLs and an explicit `execution_performed: false` boundary.
- **Next:** approved sandbox execution that adds output hashes, logs and environment lock to the same manifest.
## M05 - Outreach Manager
- **Landed:** relationship-aware contact cadence (`cadence.py`, `GET /outreach-manager/messages/{id}/cadence`): before review, every campaign's messages to the same person (matched by normalised email across contact records) are checked; opt-out and bounces are hard stops, a recent reply in another campaign blocks new cold outreach, in-review duplicates across campaigns are refused, and a min gap plus 30-day cap apply by `metadata.relationship` (cold 7d/2, warm 3d/4, close 1d/8; unknown = cold). In-campaign follow-ups use the campaign's own window as their gap. The decision rides in the approval payload and due follow-ups skip people contacted elsewhere (`tests/modules/test_m05_cadence.py`).
- **Landed:** owner-editable cadence policy per tenant (`CadencePolicyStore`, `GET/PUT /outreach-manager/cadence-policy`): versioned, append-only rules for cold/warm/close plus live-thread window, bounded and reason-required; every cadence decision reports the `policy_version` it used. Reviewer-visible cross-campaign timeline `GET /outreach-manager/contacts/{id}/timeline` lists every message to the same person (all contact records sharing the email) with campaign, status and send time.
- **Next:** show the timeline and cadence decision inside the M00 approval card for outreach sends.
## M06 - Social Media Manager
- **Landed:** cross-platform adaptation preview (`adaptation.py`, `POST /social-media-manager/plans/{id}/adaptation-preview`, `POST /social-media-manager/adaptation-preview`): source claims (sentences with figures, URLs or `[n]` references) are matched against each platform draft into a claim x platform parity matrix (`kept_cited` / `kept_uncited` / `kept` / `dropped`); a kept claim that loses its source and any figure absent from the source are blocking errors; existing platform limits, hashtag caps, disclosure and real X thread chunks are included. Read-only (`tests/modules/test_m06_adaptation.py`).
- **Landed:** scheduling gate: `request_schedule` runs the adaptation preview (source = request `source` or the plan brief, optional `references`) and refuses with 422 when any draft has `citation_dropped` or `unsupported_figure`; no approval is filed and the plan stays `draft`. Approved requests carry the per-platform `adaptation_parity`.
- **Next:** paraphrase-aware claim matching for figure-free claims (free local model), replacing the 50% content-word overlap rule.
## M07 - Brand Collaboration
- **Landed:** deliverable obligation tracker (`obligations.py`, `/brand-collaboration/obligations*`, `GET /brand-collaboration/brands/{id}/obligations`): each contract promise quotes its clause and locator and links deadlines, delivery evidence (URL or hash), Module 0 approvals, the invoice artifact and owner-recorded payments through append-only, tenant-scoped events. Status (`open`/`due_soon`/`overdue`/`delivered`/`waived`) and billing (`not_invoiced`/`invoiced`/`payment_overdue`/`paid`) are derived, never typed; flags catch delivered-not-invoiced, invoiced-before-delivery, late payment, denied approvals and active exclusivity. Nothing sends or charges (`tests/modules/test_m07_obligations.py`). Also fixed brand discovery persisting `created_at` as a string (failed on SQLite).
- **Landed:** contract -> draft obligations (`contract_extraction.py`, `POST /brand-collaboration/contracts/extract`, `/obligation-drafts/{id}/confirm|reject`, `GET /brands/{id}/obligation-drafts`): extraction uses the model layer restricted to local/self-hosted routes (contract text never goes to hosted models; no private route = 503, not a fallback). Every draft quotes the contract verbatim; rows whose quote is not in the contract are dropped and reported; quantity/amount/dates not found in the quote are flagged. Nothing becomes an obligation until the owner confirms that row; the quote becomes the clause text and cannot be edited. `GET /brand-collaboration/obligations-attention` is the cross-brand due-soon/overdue/money-leak digest (`tests/modules/test_m07_contract_extraction.py`).
- **Next:** wire `obligations-attention` into the owner's daily brief once a brief module exists (none on main today), and accept PDF/DOCX contracts via local text extraction.
## M08 - Startup Growth
- **Landed:** free-first experiment board (`experiments.py`, `/startup-growth/experiments*`): cards record hypothesis, metric + success rate, and a time/effort cap over free tools only (cards naming a cost or paid channel - ads, boosted, sponsored, promoted - are refused). Observations are append-only; the board derives rate, Wilson 95% interval, cap usage and a suggested call; every stop/continue/scale_free/pivot decision needs a reason, and `continue` is refused at cap until the owner extends it with a reason. Paid ideas can only be filed as `paid_experiment_proposal` Module 0 requests that execute nothing; `spend_executed_minor` is always 0 (`tests/modules/test_m08_experiments.py`).
- **Landed (analytics import):** `analytics_import.py` + `/startup-growth/experiments/{id}/import/plausible|csv` turn files she exported herself into observations: Plausible's export schema (`imported_visitors`: visitors per day as exposures; `imported_custom_events`: visitors on the named goal as conversions) with an optional date window, or any CSV (Umami, sheets, form tools) with owner-named exposure/conversion/date/filter columns. Unknown goals, missing columns and conversions > exposures are refused with the reason; each import is fingerprinted so re-uploading the same export never double counts. Plausible daily uniques summed over days are visitor-days and are labelled so (`tests/modules/test_m08_analytics_import.py`).
- **Next:** read the Plausible ZIP directly (pick the two CSVs by filename) and add a per-variant import for A/B cards.
## M09 - Knowledge Workspace
- **Landed (science):** tenant-scoped contradiction inbox groups conflicting claim values, exposes source freshness and confidence, ranks review order, records explicit prefer/retain-both decisions, and hashes the deterministic review artifact without claiming source authentication or truth.
- **Landed:** contradiction decision-revision verifier binds each append-only revision to the prior revision hash and content hashes for every referenced source snapshot.
- **Landed (durable revisions):** `revision_store.py` + `/knowledge-workspace/contradiction-revisions` (POST append, GET chain, POST keys, POST verify-sources). Each revision is written in its own transaction only when `previous_revision_sha256` equals the stored head for the claim (compare-and-append; a unique (tenant, claim, seq) index turns a concurrent append into 409 instead of a fork). The revision's `actor_id` must be the authenticated actor; once an actor registers an Ed25519 public key, every revision must carry a signature over its revision hash, checked before writing. Reading the chain re-hashes stored payloads and re-checks signatures, so later edits in the database show up as problems. `verify-sources` fetches each snapshot URL (public http(s) only, no redirects, 20 MB cap) and reports match/mismatch/unreachable per source; a match proves the bytes are unchanged, not that the source is authentic or true (`tests/modules/test_m09_revision_store.py`).
- **Next:** key revocation with an effective-from time, and storing fetched source bytes (content-addressed) so later checks don't depend on the URL still being up.
## M10 - Email Assistant
- **Landed:** evidence-bound thread promise tracker extracts only owner-authored commitments, links each promise to its source message/excerpt, computes due state, and proposes follow-up review without creating tasks, drafts, reminders, or sends.
- **Landed:** persistent promise-state reconciliation verifies prior snapshot and promise hashes, records reviewer-bound state receipts, completes only a named promise backed by an exact owner-authored completion excerpt, and fails closed on ambiguous updates.
- **Landed:** tenant/thread-scoped transactional snapshot persistence uses compare-and-swap against the stored reconciliation head so stale writers fail closed without overwrite.
- **Next:** authenticate reviewer identities and source-message bytes before persistence.
- **Landed:** reconciliation evidence verification hashes supplied source-message bytes and validates reviewer decision attestations with configured Ed25519 public keys.
- **Next:** persist reconciliation snapshots transactionally and govern reviewer-key identity, provisioning, and rotation.
- **Landed:** tenant-scoped reviewer public-key registry pins Ed25519 key IDs to fingerprints, rejects rebinding, and records explicit retirement.
- **Next:** persist reconciliation snapshots transactionally and verify source-message bytes using governed reviewer identities.
- **Landed:** verified source-message bytes persist tenant-scoped and immutable by message ID, with exact-repeat idempotency and fail-closed replacement conflicts.
- **Next:** persist reconciliation snapshots transactionally and authenticate reviewer identities against governed keys.
## M11 - Calendar Intelligence
- **Landed:** read-only schedule-risk view combines travel and preparation buffer shortfalls, incomplete/unknown dependencies, and sourced cancellation exposure into a deterministic risk artifact without changing events, cancelling bookings, or spending.
- **Landed:** live risk-evidence verifier binds mapping travel estimates and vendor cancellation terms to fresh retrieval timestamps, provider/source metadata, normalized-record hashes, and captured snapshot hashes, failing closed on stale, future, or mismatched evidence.
- **Landed:** Ed25519 risk-evidence verification authenticates canonical travel and cancellation snapshot metadata plus content hashes with configured provider public keys.
- **Next:** add provider-authenticated retrieval adapters and immutable source-byte storage.
- **Landed:** tenant-scoped source snapshot bytes persist immutably by verified content hash, with idempotent exact repeats and fail-closed metadata conflicts.
- **Next:** add provider-authenticated retrieval adapters and asymmetric provider signatures.
- **Landed:** provider retrieval adapter fails closed unless configured, fetches HTTPS source bytes through the injected authenticated boundary, and verifies the expected content hash.
- **Next:** persist retrieved bytes immutably and add asymmetric provider signatures.
- **Landed:** tenant-scoped risk-provider public-key registry pins Ed25519 key IDs to fingerprints, rejects rebinding, and records retirement.
- **Next:** add provider-authenticated retrieval adapters and immutable snapshot storage using governed keys.
## M12 - AI Research Lab
- **Landed:** shipped provider and DAG wiring now constructs without dependency overrides and supports OpenAI, Anthropic, DeepSeek and local Ollama through the shared provider boundary.
- **Landed (science):** canonical reproducible-run checkpoints pin workflow/code identity, dataset hashes, per-node provider/model/seed, budget and spend receipts, output hashes and explicit resume state without claiming execution or byte verification.
- **Landed:** resume preflight verifies supplied dataset bytes against pinned hashes and validates provider receipts with caller-configured trusted HMAC keys before declaring the supplied evidence resumable.
- **Landed:** provider-issued Ed25519 receipt verification validates canonical node receipts against configured public keys without exposing shared signing secrets.
- **Next:** persist checkpoints transactionally in the worker queue and govern public-key provisioning and rotation.
- **Landed:** validated checkpoints enqueue transactionally under tenant and run; idempotent repeats reuse the queued head and conflicting heads fail closed.
- **Next:** replace shared-key receipt validation with provider-issued asymmetric signatures and add worker dequeue/lease semantics.
- **Landed:** tenant-scoped provider public-key registry pins Ed25519 key IDs to fingerprints, rejects rebinding, and records explicit retirement.
- **Next:** persist checkpoints transactionally in the worker queue and use registered asymmetric keys for provider receipts.
## M13 - Browser Agent
- **Landed:** pre-submit readback diff compares fields, destination, exact price/currency and irreversible controls against the approved snapshot, requiring new approval for any change and never submitting itself.
- **Landed:** immediate pre-submit capture reads destination and fields directly from the browser adapter and binds them to DOM and screenshot byte hashes before any separate submit decision.
- **Landed:** verified DOM and screenshot bytes persist immutably under tenant and capture hash; duplicate hashes cannot replace stored evidence.
- **Next:** bind a single-use approval and submit attempt to the persisted capture hash.
## M14 - Project Builder
- **Landed (science):** acceptance matrix links criteria to hashed artifacts and named test results; proof-status keeps code-complete, test-complete and live-acceptance-complete separate with exact blockers and never promotes weaker evidence.
- **Landed:** live-receipt verification authenticates supplied receipts with configured HMAC keys and binds each to the exact deployed version, environment, and acceptance-run input hash.
- **Landed:** Ed25519 live-receipt verification authenticates canonical receipts with configured issuer public keys while preserving exact deployment, environment, and acceptance-input bindings.
- **Next:** persist receipts immutably and govern issuer-key provisioning and rotation.
- **Landed:** verified live receipts persist tenant-scoped and append-only; duplicate receipt IDs cannot replace stored proof.
- **Next:** use asymmetric issuer signatures and govern issuer-key provisioning and rotation.
- **Landed:** tenant-scoped issuer public-key registry pins Ed25519 key IDs to fingerprints, rejects rebinding, and records explicit retirement.
- **Next:** use registered asymmetric issuer signatures for receipt verification and persist receipts immutably.
## M15 - Document Generator
- **Landed:** version preflight endpoint checks empty content, duplicate citations/figures, missing citation URLs, empty PPTX and likely slide overflow before export approval.
- **Landed:** private-publication receipt verification requires consumed approval, private access, HTTPS download URL and exact approved-vs-published SHA-256 match.
- **Landed:** provider-publication receipt verification binds a consumed approval and approved render hash to a private HTTPS object receipt authenticated with a configured provider HMAC key.
- **Landed:** Ed25519 provider-publication receipts replace shared signing secrets while retaining consumed-approval, private-access, and approved-render hash checks.
- **Next:** execute the renderer and private upload in the approved worker and govern provider-key provisioning and rotation.
- **Landed:** approved publication-worker adapter binds tenant, version, format and content hash to the approved payload before rendering and private upload, then checks the upload receipt against exact rendered bytes.
- **Next:** consume approvals atomically for replay protection and replace shared-key receipts with provider-issued asymmetric signatures.
- **Landed:** authenticated private-publication receipts persist tenant-scoped and append-only; approval IDs and provider object keys cannot replace prior evidence.
- **Next:** execute the renderer and private upload in the approved worker and replace shared-key receipts with provider-issued asymmetric signatures.
- **Landed:** tenant-scoped publication-provider public-key registry pins Ed25519 key IDs to fingerprints, rejects rebinding, and records retirement.
- **Next:** execute the renderer/private upload in the approved worker and use registered asymmetric keys for receipts.
## M16 - Executive Dashboard
- **Landed (science):** gap-to-proof dashboard reports exact requirement and per-module gaps while keeping code artifacts, test evidence and live acceptance separate.
- **Landed:** proof-event verification authenticates producer events with configured HMAC keys and requires deployment receipts to carry version and environment bindings.
- **Landed:** Ed25519 proof-event verification authenticates canonical producer events with configured public keys and preserves deployment receipt bindings.
- **Next:** subscribe to producer event streams, persist events immutably, and govern producer-key provisioning and rotation.
- **Landed:** authenticated producer events persist tenant-scoped and append-only; duplicate event IDs cannot replace stored proof.
- **Next:** subscribe to producer event streams and adopt asymmetric producer signatures with governed key rotation.
- **Landed:** producer subscription-delivery verifier authenticates pushed transport envelopes and preserves delivery identity before nested proof processing.
- **Next:** provision remote subscriptions, persist events immutably, and adopt asymmetric producer signatures.
- **Landed:** tenant-scoped producer public-key registry pins Ed25519 key IDs to fingerprints, rejects rebinding, and records explicit retirement.
- **Next:** subscribe to producer streams, persist events immutably, and verify signatures through the governed registry.
## M17 - Narrative Architect
- **Landed:** canonical service now legally wires Reddit by default and optional official YouTube/Pinterest plus allowlisted public pages through shared bounded collectors.
- **Landed:** owner-material evidence completeness meter links every concept and critique suggestion to hashed owner records, exposes missing references and exact coverage, and never claims truth or disclosure permission.
- **Landed:** revision-acceptance verification binds accepted suggestions and owner-record hashes to distinct essay versions, requires owner review, and keeps disclosure approval separate for the named audience boundary.
- **Landed:** tenant-scoped append-only revision persistence requires each accepted revision to extend the stored essay-version head and rejects chain breaks.
- **Next:** enforce the disclosure gate in publication adapters.
- **Landed:** publication-gate adapter requires owner review and explicit disclosure approval for the exact audience and revision, then checks the external receipt binding.
- **Next:** persist the revision chain and authenticate publication receipts.
- **Landed:** Ed25519 publication-receipt verification authenticates the provider receipt and exact essay, revision and audience binding.
- **Next:** persist the revision chain and enforce the disclosure gate in publication adapters.
- **Landed:** tenant-scoped publication-provider public-key registry pins Ed25519 key IDs to fingerprints, rejects rebinding, and records retirement.
- **Next:** persist the revision chain and enforce the disclosure gate using governed publication keys.
## M18 - Side Hustle & Knowledge Scraper
- **Landed:** public/official collectors, approval-gated durable experiments, receipts/outcomes, and the freshness API now performs bounded production refetches, hashes observed bytes, records cache headers, changes and dead-source failures instead of returning 501.
- **Next:** signed provider receipt verification and shared Postgres storage for horizontally scaled workers.
## M19 - Idea Incubator
- **Landed:** assumption burn-down ranks tests by expected entropy reduction per cost/time burden and selects a budget-feasible learning portfolio while preserving caller-supplied uncertainty.
- **Next:** update priors from observed experiment evidence with auditable Bayesian revisions.
## M20 - General Cognitive Worker
- **Landed:** execution truth ledger preserves planned, simulated, externally executed and independently verified states per claim, requiring evidence for effects and evidence plus verifier for independent verification.
- **Next (science):** persist append-only state transitions and cryptographically bind receipts from all modules.
## M21 - Claire
- **Landed:** mounted expiring device pairing plus paired-device result-receipt verification over a tamper-evident hash chain, with revocation enforcement and explicit limits on attesting OS behavior.
- **Next:** installable paired-PC daemon with OS-keystore identity, native approval prompts and certificate signatures over receipt heads.
## M22 - Tools Hub
- **Landed:** free official GitHub/PyPI/npm discovery plus an integration-receipt endpoint that binds installer operation, artifact/manifest hashes, approval, candidate and rollback backup to the exact proposal.
- **Next:** tenant-persist proposals/portfolio and invoke the scanner/installer through a durable worker rather than accepting a supplied receipt.
## M23 - Study Abroad
- **Landed:** application evidence matrix links requirements and essay claims to owner records and official program sources, exposes broken references, and returns explicit missing-input items and coverage.
- **Next:** source-content hashes, official-page freshness checks and reviewer sign-off per matrix revision.
## M24 - Billing
- **Landed:** pre-commit commitment preview binds plan, USD currency, quantity, renewal interval, caller-supplied tax, cancellation policy/deadline and exact charge into a content hash; checkout proposals now bind that exact preview hash and expected cents, revalidate them before Stripe session creation, reject tampering, and fail closed on unsupported annual, multi-seat or Atlas-tax shapes.
- **Next:** reconcile Stripe's returned line items/tax and webhook invoice total against the approved cents before treating checkout as committed.
## M25 - Knowledge Copilot & Training
- **Landed:** common M00-M25 provenance events now have durable tenant-scoped SQLite WAL storage, idempotent replay, conflicting-replay rejection, canonical event hashing, and optional artifact-byte SHA-256 verification.
- **Next:** verify remote source bytes/freshness, adopt the contract at every producer, and add the device capture adapter.
- **Landed (M01, honest scoring):** opportunity output now names the deterministic value `impact_heuristic`, tags it `score_kind=heuristic` and `advisory_only=true`, while a provenance-bearing ProgramPrior adapter ingests official sponsor/mechanism/cycle/geography application and award counts with Wilson uncertainty. It does not claim an applicant win probability or train on award-only open data.
- **Landed (M01, consented outcomes):** owner-scoped first-party application outcome ledger records pending, waitlisted, awarded, declined and withdrawn states with equal provenance requirements, explicit consent evidence, bounded retention, expiry purge and immediate deletion on consent revocation. It is advisory-only and exposes no model-training or feature-export path.
- **Landed (M01, tenant isolation):** authenticated M01 routes now bind discovery storage and reads to the tenant; the same canonical opportunity URL has a different deterministic identity per tenant, cross-tenant get/list returns nothing, and digest approval payloads retain the tenant boundary. An explicit Alembic migration adds the indexed tenant column without dropping existing rows.
- **Landed (M03, tenant boundary):** proposal, budget, success-analysis and export routes now require authenticated tenant context; export approvals carry the server-derived tenant ID and the service fails closed on an empty tenant, preventing approval work from detaching from its owner.
- **Landed (M02, review tenant boundary):** humanized application-answer review packages now require authenticated tenant context and carry the server-derived tenant ID in the exact-answer approval payload; the pipeline fails closed on an empty tenant before browser staging or final-submit approval.
- **Landed (M07/M08, approval tenant handoff):** brand collateral sends and startup publish/deploy/share proposals now require tenant-scoped repositories and bind the repository tenant ID into every approval payload, preserving ownership at the handoff to external execution.
- **Landed (M05, send tenant handoff):** initial outreach and durable campaign-message approvals now bind the authenticated container tenant into every send/follow-up payload; both services fail closed on an empty tenant so external delivery cannot detach from its owner.
- **Landed (M06, approval tenant handoff):** schedule and A/B publish approvals now pass through one tenant-bound approval boundary that injects the authenticated repository tenant into every payload and fails closed when tenant identity is empty.
- **Landed (M00, policy tenant isolation):** approval policies now use tenant+policy composite identity; admin upsert/list and effect evaluation are tenant-scoped, so one tenant's allow/deny/review rule cannot change another tenant's external-action gate. Unknown tenants still fail closed to human review.
- **Landed (M04, provider authentication):** the BYOK-backed hypothesis endpoint now requires authenticated tenant context before any model call, preventing unauthenticated production callers from consuming configured provider capacity or cost; local literature clustering remains a read-only computation.
- **Landed (M00, legacy approval tenant isolation):** the mounted compatibility planner and `/api/v1/approvals` list, audit, and decision routes now bind every request to authenticated tenant identity; cross-tenant records are omitted or returned as not found, and the authenticated actor is recorded for decisions.
- **Landed (M01, approval provenance):** digest proposals now store their M00 approval under the authenticated opportunity tenant, while core-spec approval-required capabilities can no longer treat caller-supplied booleans as owner approval or claim an external effect executed.

## Commercial readiness lane
- **Landed:** clean owner-PC install with secret-default rejection, a one-shot Alembic migration gate, isolated PostgreSQL/Redis volumes, and API readiness that checks live database, Redis and exact migration heads.
- **Landed:** authenticated first-run checklist stores only local completion state and explicitly performs no sends, publishing, submissions or spending.
- **Landed:** reproducible M00-M25 repository-evidence generator keeps offline-test discovery separate from live and production acceptance.
- **Landed:** operator runbook covers startup, backup/restore drills, upgrades, rollback boundaries, incident stops and credential rotation without claiming unobserved scale or uptime.
- **Landed (M02, approval provenance):** form-fill and integrated-answer review proposals now persist M00 approvals under the authenticated competition tenant, and core-spec external-action rows cannot turn caller-supplied booleans into owner approval or execution claims.
- **Landed (M03, export approval ownership):** grant export proposals now persist their M00 approval row under the authenticated grant-writer tenant, matching the tenant already bound into the exact export payload.
- **Landed (M05, approval authority):** outreach and follow-up proposals persist M00 rows under the authenticated tenant, and the public message-decision endpoint is removed so callers cannot self-attest approval; only the bound M00 decision callback may mirror approval into delivery state.
- **Landed (M06, approval ownership):** schedule and A/B proposals persist M00 rows under the authenticated social tenant, and scheduler decision rechecks are tenant-scoped so a foreign approval identifier cannot authorize a local platform write.
- **Landed (M07/M08, approval ownership):** brand collateral/report/invoice sends and startup push/deploy/share/publish proposals now persist their M00 approval rows under the authenticated repository tenant, matching each exact payload's tenant boundary.
- **Landed (M04, core-spec approval authority):** Google-account research and Google Docs compilation capability plans can no longer convert a caller-supplied boolean into owner approval or claim an account/document effect executed; both remain approval-required and explicitly non-executing.
- **Landed (M10, reply approval ownership):** generated email-reply drafts now bind authenticated repository tenant identity into both the exact reply payload and the M00 approval row, preventing cross-tenant approval lookup or dispatch drift.
- **Landed (M11, calendar approval ownership):** plan and reschedule proposals bind tenant into exact payloads and M00 rows; status/payload rechecks reject foreign-tenant approval identifiers before any calendar plan or reschedule is applied.
- **Landed (M12, authenticated research context):** emerging-biomed analysis now derives tenant and actor only from the shared authenticated context; caller-controlled legacy identity headers can no longer spoof execution provenance.
- **Landed (M14, execution approval ownership):** project-plan execution proposals now persist their M00 approval row under the project's authenticated tenant, matching the tenant already bound into the exact plan and budget payload.
- **Landed (M15, render approval ownership):** document render proposals now persist their M00 approval row under the document version's authenticated tenant, matching the exact version, format, template and content hash payload.
- **Landed (M17, publication approval authority):** revision publication now requires an exact tenant-scoped persisted acceptance whose revision hash, acceptance hash, target version, audience, owner review and disclosure approval all match; caller booleans alone cannot trigger publication.
