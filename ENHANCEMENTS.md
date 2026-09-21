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
- **Next (science):** contradiction inbox with source freshness, confidence and explicit merge/retain-both decisions.
## M10 - Email Assistant
- **Next:** thread promise tracker that extracts owner commitments and asks before creating follow-ups.
## M11 - Calendar Intelligence
- **Next:** schedule-risk view combining travel buffer, preparation work, dependency conflicts and cancellation terms.
## M12 - AI Research Lab
- **Landed:** shipped provider and DAG wiring now constructs without dependency overrides and supports OpenAI, Anthropic, DeepSeek and local Ollama through the shared provider boundary.
- **Next (science):** durable queued DAG resumes with per-node budget receipts, dataset hashes, seeds and reproducible provider/model manifests.
## M13 - Browser Agent
- **Next:** readback diff before submit, showing changed fields, destination, price and irreversible controls against the approved snapshot.
## M14 - Project Builder
- **Next (science):** acceptance-criterion coverage map linking each criterion to artifact, test, result and unresolved blocker.
## M15 - Document Generator
- **Landed:** version preflight endpoint checks empty content, duplicate citations/figures, missing citation URLs, empty PPTX and likely slide overflow before export approval.
- **Next:** approval consumption that renders and publishes a private downloadable File with a verified hash.
## M16 - Executive Dashboard
- **Next (science):** gap-to-proof dashboard separating code-complete, test-complete and live-acceptance-complete requirements.
## M17 - Narrative Architect
- **Landed:** canonical service now legally wires Reddit by default and optional official YouTube/Pinterest plus allowlisted public pages through shared bounded collectors.
- **Next:** owner-material evidence completeness meter for each essay concept and critique suggestion.
## M18 - Side Hustle & Knowledge Scraper
- **Landed:** default public collectors, optional official Pinterest/X/Instagram/YouTube paths, a five-artifact experiment checklist with separate publish/send/spend approvals, and adapter receipts plus observed-outcome ingestion bound to consumed approvals.
- **Next:** durable tenant-scoped run storage and signed provider receipt verification.
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
- **Landed:** free official discovery sources for GitHub, PyPI and npm replace the shipped empty collector list.
- **Next:** connect approved discovery proposals to the existing scanner/installer with tenant persistence and rollback receipts.
## M23 - Study Abroad
- **Landed:** application evidence matrix links requirements and essay claims to owner records and official program sources, exposes broken references, and returns explicit missing-input items and coverage.
- **Next:** source-content hashes, official-page freshness checks and reviewer sign-off per matrix revision.
## M24 - Billing
- **Landed:** pre-commit commitment preview binds plan, USD currency, quantity, renewal interval, caller-supplied tax, cancellation policy/deadline and exact charge into a content hash; it refuses guessed FX and never executes payment.
- **Next:** bind the approved preview hash to checkout execution and reconcile Stripe’s final amount before commit.
## M25 - Knowledge Copilot & Training
- **Landed:** mounted contradiction review and claim-substantiation endpoints plus a common M00-M25 artifact provenance event validator with canonical event hashing and receipt requirements for executed/verified states.
- **Next:** persist/deduplicate provenance events, verify source bytes and adopt the contract at every producer plus a device capture adapter.
