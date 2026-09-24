# Atlas AI

Atlas AI is a human-controlled modular work platform owned by Udita. This repository contains a FastAPI API, Next.js dashboard, tenant-scoped persistence, worker/queue configuration, source and provider adapters, approval-gated effects, document renderers, billing test-mode wiring, and production container definitions.

## Honest state

This is an active product build, not a finished production service. Modules 0-25 are registered on API routers and have offline tests, but registration is not proof that every requested feature is complete. The row-by-row evidence audit is in [`docs/IMPLEMENTATION_AUDIT.md`](docs/IMPLEMENTATION_AUDIT.md) and [`audits/ledger-140.json`](audits/ledger-140.json). The audit deliberately labels adjacent-but-incomplete work **thin** and absent exact requirements **missing**.

The previous README was stale. It still described the first foundation commit and called current modules stubs even after their implementations landed. It also claimed auth, tenant state, workers, providers, billing and deployment were all deferred, which is no longer true. This README replaces those claims rather than papering over remaining gaps.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --app-dir backend --reload
pytest -q

cd frontend
npm ci
npm run typecheck
npm run build
```

Development infrastructure is available through `docker compose up --build`. The production topology is in `docker-compose.prod.yml`; it still needs provisioned infrastructure, migrations, TLS, live monitoring and backups before a 24/7 launch claim is valid.

## Models (free-first)

Atlas routes text generation free-first: Ollama or any OpenAI-compatible server on your own PC (llama.cpp, vLLM, LM Studio), then the Hugging Face free tier. Paid providers (OpenAI, Anthropic, Gemini, DeepSeek, Sakana Fugu) are optional config and stay off unless `ATLAS_ALLOW_PAID=true`. If no free route works, Atlas stops and says why. Named models: Inkling and Inkling-Small are open weights and wired. Fugu is a paid hosted API, not open weights. "Ultron" isn't one model, so it isn't wired. Details, sources and setup are in [`docs/OPEN_MODELS.md`](docs/OPEN_MODELS.md).

## Current module state

All module routers below are mounted by `backend/app/main.py`. "Implemented core" means substantive code and tests exist. "Thin" means important requested production capability is still absent.

| ID | Module | Current real implementation | Important remaining gap |
|---:|---|---|---|
| 0 | Human Approval Center | durable proposals, decisions, expiry, audit events, blocking callbacks | cross-process dashboard fan-out |
| 1 | Opportunity Discovery | RSS/Atom, GitHub and Devpost scans, normalization, scoring, SQL state, gated digests | scheduled source fleet, spaCy/dateparser/embedding normalization, 200 verified scholarship sources |
| 2 | Competition Manager | rule extraction, checklist/drafting, SQL state, evidence status, per-claim evidence completeness score against the stored owner corpus, browser handoff | Docs grounding, winner corpus, announcement monitors and follow-ups |
| 3 | Grant Writer | grounded staged proposals, deterministic budgets, funded-example corpus/search, approval-gated export and explicit-rule science-grant compliance preflight, versioned source-anchored agency schema packs (NSF GRFP) | complete official funded corpus, agency schema packs and live rate evidence |
| 4 | Research Scientist | literature clustering, provider-backed hypotheses, surveillance, quantitative/environmental methods, approval-gated sandbox proposals, and downloadable content-addressed reproducibility bundles | approved sandbox execution with captured output hashes/logs and live-source acceptance |
| 5 | Outreach Manager | tenant SQL CRM, change history, professor discovery, drafts and gated sends, cross-campaign contact cadence guard | more official enrichment sources and a real approved-send executor |
| 6 | Social Media Manager | provider-backed plans, asset prompts, SQL plans/reports, official X metrics, gated scheduling, cross-platform claim/citation parity preview | real asset generation and platform execution after approval |
| 7 | Brand Collaboration | discovery scoring, tenant ledger, PDF/HTML collateral, reports/invoices, gated send, contract obligation tracker (deadlines, evidence, approvals, invoice/payment status) | live provider integrations and production artifact storage |
| 8 | Startup Growth | real Next.js archives, Supabase waitlist route, PPTX deck, code-grounded docs, gated publish, free-first experiment board (paid ideas are proposals only) with Plausible/CSV analytics import | deployment executor and broader templates |
| 9 | Knowledge Workspace | tenant graph, review suggestions, versioning and planner export | Google Docs/Sheets ingestion and richer visual editing |
| 10 | Email Assistant | Gmail OAuth/watch/ingestion, seven-class classifier, action extraction, priority/follow-up, gated replies | production OAuth credentials and approved send execution |
| 11 | Calendar Intelligence | Google/CalDAV sync, solver, travel/prep/focus constraints, conflict proposals | production credentials and live apply verification |
| 12 | AI Research Lab | cost/latency/capability router, bounded retries, confidence, YAML DAG execution, and shipped Atlas-provider wiring | durable distributed node runner and live-provider acceptance |
| 13 | Browser Agent | sessions, URL safety, form matching, screenshot-bound single-use approvals | deployed Playwright/VLM runtime and artifact storage |
| 14 | Project Builder | scientific acceptance-to-artifact/test matrix,  tenant project plans, tasks, dependencies and approval gates | richer project executors and integrations |
| 15 | Document Generator | versioned documents, structural diffs, export proposals, renderers, and preflight checks for citations/figures/slide usability | approval consumption that delivers a verified downloadable File |
| 16 | Executive Dashboard | approval queue, command previews, critical paths and graph UI | live SSE/Redis fan-out and fuller operational UI |
| 17 | Narrative Architect | bounded narrative drafting/critique with default Reddit and optional official YouTube/Pinterest/allowlisted public-source wiring | live provider acceptance and full editing workflow |
| 18 | Side Hustle Scraper | approval-bound adapter receipts and measured outcome ingestion,  wired public/official source collectors plus artifact-first experiment checklists with separate publish/send/spend approvals | effect adapters, observed outcome ingestion and live-provider acceptance |
| 19 | Idea Incubator | information-gain assumption burn-down and budget-feasible experiment selection,  budget-capped previews and approval gates | durable long-running incubation orchestration |
| 20 | General Cognitive Worker | per-claim execution truth ledger,  plans, dependencies, bounded retries, budgets, memory and supervision | durable distributed execution and broader real tool adapters |
| 21 | Claire | paired-device hash-chain result receipt verification,  in-Atlas workflows, bounded capabilities, expiring fingerprinted device pairing/revocation, per-action gates and deception refusal | installable signed paired-PC daemon and durable orchestration |
| 22 | Tools Hub | proposal-bound installer receipts and rollback evidence,  free official GitHub/PyPI/npm discovery, ranked candidates, approval proposals and separate scanner/installer primitives | connect proposal to installer with tenant persistence and receipts |
| 23 | Study Abroad | application requirement/essay-claim evidence matrix,  advising, identity interview, essay tools and lifecycle planning | live program-source and application acceptance |
| 24 | Billing | exact-charge and cancellation commitment preview,  plan metadata, test-mode checkout/cancel/invoice approvals, signed idempotent webhook, entitlements and metering | live Stripe acceptance and production pricing/tax setup |
| 25 | Knowledge Copilot & Training | consent-bound local ingestion/search/export plus mounted contradiction and claim-substantiation checks | universal module artifact routing and device capture adapter |

See [`ENHANCEMENTS.md`](ENHANCEMENTS.md) for module-by-module landed enhancements and clearly separated next candidates, prioritizing computational-science workflows.

## Fallback policy

A fallback is legitimate only when a real primary implementation exists and the fallback handles an optional dependency, missing key, upstream failure or malformed model output. Current legitimate examples are: provider-backed email action extraction to deterministic extraction; provider-backed social strategy to deterministic formatting; WeasyPrint PDF to inspectable HTML; PPTX to Markdown when `python-pptx` is not installed; and routed model retries across eligible providers.

Deterministic logic that replaces a requested primary capability is not called complete. The M1 keyword/date/token scoring and impact heuristic currently stand in for live spaCy/dateparser/embedding/model-backed normalization. That is a disguised stub and remains a build item in the audit. The M10 rule classifier is useful on its own, but it is also a stand-in until a verified trained checkpoint is supplied. Exact classifications and evidence are in [`docs/FALLBACK_AUDIT.md`](docs/FALLBACK_AUDIT.md).

## Safety and commercial boundaries

- Every message, follow-up, publication, form submission, deletion and money action is previewed and approval-gated.
- No Discord self-bots, piracy adapters, fabricated application activities, fabricated labels, deception as the user, login-driven mass scraping or personal-session evasion.
- Collection uses public sources, official APIs, invited bots, newsletters, open-access sources and discovery followed by selected tracking.
- Users bring model/provider keys. Metered features expose configuration/cost before use.
- Stripe remains test-mode only. Atlas is not yet a launched billing service.

## Evidence

- Full implementation audit: [`docs/IMPLEMENTATION_AUDIT.md`](docs/IMPLEMENTATION_AUDIT.md)
- Machine-readable 140-row audit: [`audits/ledger-140.json`](audits/ledger-140.json)
- Architecture and deployment: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- Billing boundary: [`docs/BILLING.md`](docs/BILLING.md)

## Commercial launch acceptance boundary

Atlas can be packaged and tested without paid services, but the following are not claimed complete until the named live acceptance evidence exists:

- **Billing:** a reviewed production Stripe account, tax/pricing configuration, and a test purchase/refund/cancellation receipt. Until then Stripe remains test-mode only.
- **Paired computer:** signed installers tested on each supported OS, OS-keystore identity, native permission prompts, kill switch, update/uninstall path, and signed action receipts from real machines.
- **External providers:** owner-provided credentials, quota confirmation, and one reversible acceptance run for every enabled send, publish, submit, or deploy adapter.
- **Operations:** production TLS/domain, backup and restore drill, monitoring alerts, incident owner, retention policy, and load evidence for the chosen capacity.

Missing acceptance evidence is shown as configuration-gated or not live-verified. It must not be described as executed, available, or production-ready.
