# Atlas module enhancements

Status legend: **Landed** is working code with a named test. **Next** is a proposed enhancement, not an implementation claim.

## M00 - Human Approval Center
- **Next:** approval impact preview that compares the exact effect payload with the current external state immediately before consumption.
## M01 - Opportunity Discovery
- **Next:** deadline-change monitor with source snapshots and owner-visible eligibility deltas.
## M02 - Competition Manager
- **Next:** evidence completeness score that links each answer claim to a profile-corpus source or `[NEEDS INPUT]`.
## M03 - Grant Writer
- **Landed:** deterministic science-grant preflight parses explicit word limits, budget caps, required attachments, evaluation criteria and unresolved `[NEEDS INPUT]` placeholders without inventing rules.
- **Next (science):** agency-specific schema packs sourced from versioned official calls, with deadline and amendment tracking.
## M04 - Research Scientist
- **Landed:** downloadable computational reproducibility bundle with analysis code, input/parameter snapshots, SHA-256 input and manifest identity, dependencies, seed, source URLs and an explicit `execution_performed: false` boundary.
- **Next:** approved sandbox execution that adds output hashes, logs and environment lock to the same manifest.
## M05 - Outreach Manager
- **Next:** relationship-aware contact cadence that prevents duplicate or socially excessive outreach across campaigns.
## M06 - Social Media Manager
- **Next:** cross-platform content adaptation preview with claim/citation parity and platform-limit checks.
## M07 - Brand Collaboration
- **Next:** deliverable obligation tracker linking contract promises, approvals, deadlines, evidence and invoice status.
## M08 - Startup Growth
- **Next:** free-first experiment board that records hypothesis, cap, observed conversion and stop decision without auto-spend.
## M09 - Knowledge Workspace
- **Landed (science):** tenant-scoped contradiction inbox groups conflicting claim values, exposes source freshness and confidence, ranks review order, records explicit prefer/retain-both decisions, and hashes the deterministic review artifact without claiming source authentication or truth.
- **Landed:** contradiction decision-revision verifier binds each append-only revision to the prior revision hash and content hashes for every referenced source snapshot.
- **Next:** persist revisions transactionally and fetch source bytes to verify captured hashes and actor signatures.
## M10 - Email Assistant
- **Landed:** evidence-bound thread promise tracker extracts only owner-authored commitments, links each promise to its source message/excerpt, computes due state, and proposes follow-up review without creating tasks, drafts, reminders, or sends.
- **Landed:** persistent promise-state reconciliation verifies prior snapshot and promise hashes, records reviewer-bound state receipts, completes only a named promise backed by an exact owner-authored completion excerpt, and fails closed on ambiguous updates.
- **Landed:** tenant/thread-scoped transactional snapshot persistence uses compare-and-swap against the stored reconciliation head so stale writers fail closed without overwrite.
- **Next:** authenticate reviewer identities and source-message bytes before persistence.
## M11 - Calendar Intelligence
- **Landed:** read-only schedule-risk view combines travel and preparation buffer shortfalls, incomplete/unknown dependencies, and sourced cancellation exposure into a deterministic risk artifact without changing events, cancelling bookings, or spending.
- **Landed:** live risk-evidence verifier binds mapping travel estimates and vendor cancellation terms to fresh retrieval timestamps, provider/source metadata, normalized-record hashes, and captured snapshot hashes, failing closed on stale, future, or mismatched evidence.
- **Next:** add provider-authenticated retrieval adapters and signed immutable snapshot storage.
## M12 - AI Research Lab
- **Landed:** shipped provider and DAG wiring now constructs without dependency overrides and supports OpenAI, Anthropic, DeepSeek and local Ollama through the shared provider boundary.
- **Landed (science):** canonical reproducible-run checkpoints pin workflow/code identity, dataset hashes, per-node provider/model/seed, budget and spend receipts, output hashes and explicit resume state without claiming execution or byte verification.
- **Landed:** resume preflight verifies supplied dataset bytes against pinned hashes and validates provider receipts with caller-configured trusted HMAC keys before declaring the supplied evidence resumable.
- **Landed:** provider-issued Ed25519 receipt verification validates canonical node receipts against configured public keys without exposing shared signing secrets.
- **Next:** persist checkpoints transactionally in the worker queue and govern public-key provisioning and rotation.
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
## M15 - Document Generator
- **Landed:** version preflight endpoint checks empty content, duplicate citations/figures, missing citation URLs, empty PPTX and likely slide overflow before export approval.
- **Landed:** private-publication receipt verification requires consumed approval, private access, HTTPS download URL and exact approved-vs-published SHA-256 match.
- **Landed:** provider-publication receipt verification binds a consumed approval and approved render hash to a private HTTPS object receipt authenticated with a configured provider HMAC key.
- **Landed:** Ed25519 provider-publication receipts replace shared signing secrets while retaining consumed-approval, private-access, and approved-render hash checks.
- **Next:** execute the renderer and private upload in the approved worker and govern provider-key provisioning and rotation.
## M16 - Executive Dashboard
- **Landed (science):** gap-to-proof dashboard reports exact requirement and per-module gaps while keeping code artifacts, test evidence and live acceptance separate.
- **Landed:** proof-event verification authenticates producer events with configured HMAC keys and requires deployment receipts to carry version and environment bindings.
- **Landed:** Ed25519 proof-event verification authenticates canonical producer events with configured public keys and preserves deployment receipt bindings.
- **Next:** subscribe to producer event streams, persist events immutably, and govern producer-key provisioning and rotation.
## M17 - Narrative Architect
- **Landed:** canonical service now legally wires Reddit by default and optional official YouTube/Pinterest plus allowlisted public pages through shared bounded collectors.
- **Landed:** owner-material evidence completeness meter links every concept and critique suggestion to hashed owner records, exposes missing references and exact coverage, and never claims truth or disclosure permission.
- **Landed:** revision-acceptance verification binds accepted suggestions and owner-record hashes to distinct essay versions, requires owner review, and keeps disclosure approval separate for the named audience boundary.
- **Next:** persist the revision chain and enforce the disclosure gate in publication adapters.
## M18 - Side Hustle & Knowledge Scraper
- **Landed:** default public/official collectors, approval-gated experiments, adapter receipts and outcomes now extend to tenant-scoped durable SQLite WAL run snapshots that survive runner restarts and preserve exact approval/receipt links.
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
