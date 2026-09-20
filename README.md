# Atlas AI

Atlas AI is a human-controlled modular work platform owned by Udita. This repository contains a FastAPI API, Next.js dashboard, tenant-scoped persistence, worker/queue configuration, source and provider adapters, approval-gated effects, document renderers, billing test-mode wiring, and production container definitions.

## Honest state

This is an active product build, not a finished production service. Modules 0-23 are registered on live API routers and have offline tests, but registration is not proof that every requested feature is complete. The row-by-row evidence audit is in [`docs/IMPLEMENTATION_AUDIT.md`](docs/IMPLEMENTATION_AUDIT.md) and [`audits/ledger-140.json`](audits/ledger-140.json). The audit deliberately labels adjacent-but-incomplete work **thin** and absent exact requirements **missing**.

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

## Current module state

All module routers below are mounted by `backend/app/main.py`. "Implemented core" means substantive code and tests exist. "Thin" means important requested production capability is still absent.

| ID | Module | Current real implementation | Important remaining gap |
|---:|---|---|---|
| 0 | Human Approval Center | durable proposals, decisions, expiry, audit events, blocking callbacks | cross-process dashboard fan-out |
| 1 | Opportunity Discovery | RSS/Atom, GitHub and Devpost scans, normalization, scoring, SQL state, gated digests | scheduled source fleet, spaCy/dateparser/embedding normalization, 200 verified scholarship sources |
| 2 | Competition Manager | rule extraction, checklist/drafting, SQL state, evidence status, browser handoff | Docs grounding, winner corpus, announcement monitors and follow-ups |
| 3 | Grant Writer | provider-backed proposal sections, budgets, funded-example analysis, durable corpus, DOCX/PDF renderer | 1,000+ real funded corpus, vector retrieval and live rate evidence |
| 4 | Research Scientist | literature clustering, provider-backed hypotheses, sandbox proposals, scientific adapters | durable surveillance, embedding clusters, ReAct/gap finder, manuscript/artifact pipeline |
| 5 | Outreach Manager | tenant SQL CRM, change history, professor discovery, drafts and gated sends | more official enrichment sources and a real approved-send executor |
| 6 | Social Media Manager | provider-backed plans, asset prompts, SQL plans/reports, official X metrics, gated scheduling | real asset generation and platform execution after approval |
| 7 | Brand Collaboration | discovery scoring, tenant ledger, PDF/HTML collateral, reports/invoices, gated send | live provider integrations and production artifact storage |
| 8 | Startup Growth | real Next.js archives, Supabase waitlist route, PPTX deck, code-grounded docs, gated publish | deployment executor and broader templates |
| 9 | Knowledge Workspace | tenant graph, review suggestions, versioning and planner export | Google Docs/Sheets ingestion and richer visual editing |
| 10 | Email Assistant | Gmail OAuth/watch/ingestion, seven-class classifier, action extraction, priority/follow-up, gated replies | production OAuth credentials and approved send execution |
| 11 | Calendar Intelligence | Google/CalDAV sync, solver, travel/prep/focus constraints, conflict proposals | production credentials and live apply verification |
| 12 | AI Research Lab | cost/latency/capability router, bounded retries, confidence and YAML DAG execution | production model catalog and distributed node runner |
| 13 | Browser Agent | sessions, URL safety, form matching, screenshot-bound single-use approvals | deployed Playwright/VLM runtime and artifact storage |
| 14 | Project Builder | tenant project plans, tasks, dependencies and approval gates | richer project executors and integrations |
| 15 | Document Generator | versioned documents, diffs and PDF/DOCX/PPTX renderers | Google publishing and higher-fidelity templates |
| 16 | Executive Dashboard | approval queue, command previews, critical paths and graph UI | live SSE/Redis fan-out and fuller operational UI |
| 17 | Narrative Architect | cited-source collection and bounded narrative drafting | more official sources and full editing workflow |
| 18 | Side Hustle Scraper | sourced blueprint generation with login-scrape rejection | larger source registry and market validation adapters |
| 19 | Idea Incubator | budget-capped previews and approval gates | durable long-running incubation orchestration |
| 20 | General Cognitive Worker | plans, dependencies, bounded retries, budgets, memory and supervision | durable distributed execution and broader real tool adapters |
| 21 | Claire | in-Atlas workflows, bounded capabilities, optional paired-client protocol, per-action gates and deception refusal | persistent orchestration and deployed paired-client transport |
| 22 | Tools Hub | allow-listed discovery and approval-gated installation proposals | production catalog, provenance/security scanner and post-approval installer |
| 23 | Billing | plan metadata, Stripe test Checkout proposals, idempotent executions and event dedupe | signed webhooks, invoice/cancel/tax flows, production prices |

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
