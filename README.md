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
| 0 | Human Approval Center | durable proposals, decisions, expiry, audit events, blocking callbacks, impact preview with live-state drift check (first real probe: M10 reply sends) | cross-process dashboard fan-out |
| 1 | Opportunity Discovery | RSS/Atom, GitHub and Devpost scans, live spaCy NER + dateparser deadlines + free local embedding match with per-row engine provenance, SQL state, gated digests | scheduled source fleet, DeBERTa eligibility classifier, pgvector persistence of embeddings, 200 verified scholarship sources |
| 2 | Competition Manager | rule extraction, checklist/drafting, SQL state, evidence status, per-claim evidence completeness score against the stored owner corpus, browser handoff | Docs grounding, winner corpus, announcement monitors and follow-ups |
| 3 | Grant Writer | grounded staged proposals, deterministic budgets, funded-example corpus/search, approval-gated export and explicit-rule science-grant compliance preflight, versioned source-anchored agency schema packs (NSF GRFP) | complete official funded corpus, agency schema packs and live rate evidence |
| 4 | Research Scientist | literature clustering, provider-backed hypotheses, surveillance, quantitative/environmental methods, approval-gated sandbox proposals, approved sandbox execution (one-shot Module 0 permit, bubblewrap/Docker no-network isolation, hashed logs and outputs, in-sandbox environment lock, sealed receipts, artifact download, executed reproducibility bundle), and downloadable content-addressed reproducibility bundles | live-source acceptance; Docker backend not yet run on a live host (bubblewrap backend is executed in tests) |
| 5 | Outreach Manager | tenant SQL CRM, change history, professor discovery, drafts and gated sends, cross-campaign contact cadence guard, contact timeline in the outreach approval card | more official enrichment sources and a real approved-send executor |
| 6 | Social Media Manager | provider-backed plans, asset prompts, SQL plans/reports, official X metrics, gated scheduling, cross-platform claim/citation parity preview | real asset generation and platform execution after approval |
| 7 | Brand Collaboration | discovery scoring, tenant ledger, PDF/HTML collateral, reports/invoices, gated send, contract obligation tracker (deadlines, evidence, approvals, invoice/payment status) | live provider integrations and production artifact storage |
| 8 | Startup Growth | real Next.js archives, Supabase waitlist route, PPTX deck, code-grounded docs, gated publish, free-first experiment board (paid ideas are proposals only) with Plausible/CSV analytics import | deployment executor and broader templates |
| 9 | Knowledge Workspace | tenant graph, review suggestions, versioning, planner export, durable signed contradiction-decision chains with governed actor keys (rotate/retire/effective-from, event log) and immutably stored source bytes for hash checks | Google Docs/Sheets ingestion and richer visual editing |
| 10 | Email Assistant | Gmail OAuth/watch/ingestion, seven-class classifier, action extraction, priority/follow-up, gated replies re-checked against the live thread and draft before any send permit, reviewer-key governance with RFC 3161 timestamped attestations (FreeTSA by default) that stay valid after key retirement | production OAuth credentials and approved send execution |
| 11 | Calendar Intelligence | Google/CalDAV sync, solver, travel/prep/focus constraints, conflict proposals, signed risk-evidence ingest (registered provider keys, authenticated fetch, immutable storage) | production credentials and live apply verification |
| 12 | AI Research Lab | cost/latency/capability router, bounded retries, confidence, YAML DAG execution, and shipped Atlas-provider wiring, leased checkpoint worker queue with registry-verified provider receipts | durable distributed node runner and live-provider acceptance |
| 13 | Browser Agent | sessions, URL safety, form matching, screenshot-bound single-use approvals, approvals bound to a persisted pre-submit capture with live re-check and one attempt per capture | deployed Playwright/VLM runtime and artifact storage |
| 14 | Project Builder | scientific acceptance-to-artifact/test matrix,  tenant project plans, tasks, dependencies and approval gates, live receipts verified with registered issuer keys and stored immutably with re-verification | richer project executors and integrations |
| 15 | Document Generator | versioned documents, structural diffs, export proposals, renderers, and preflight checks for citations/figures/slide usability; approved delivery: one-shot Module 0 permit bound to the recomputed content hash, real PDF/LaTeX/DOCX/PPTX renders with figures and references, structural validation, hashed tenant store, signed expiring download links | production object storage behind the delivery store; Dockerfile now installs TeX for PDF, image build not yet verified |
| 16 | Executive Dashboard | approval queue, command previews, critical paths and graph UI | live SSE/Redis fan-out and fuller operational UI |
| 17 | Narrative Architect | bounded narrative drafting/critique with default Reddit and optional official YouTube/Pinterest/allowlisted public-source wiring | live provider acceptance and full editing workflow |
| 18 | Side Hustle Scraper | approval-bound adapter receipts and measured outcome ingestion,  wired public/official source collectors plus artifact-first experiment checklists with separate publish/send/spend approvals | effect adapters, observed outcome ingestion and live-provider acceptance |
| 19 | Idea Incubator | information-gain assumption burn-down and budget-feasible experiment selection,  budget-capped previews and approval gates | durable long-running incubation orchestration |
| 20 | General Cognitive Worker | per-claim execution truth ledger,  plans, dependencies, bounded retries, budgets, memory and supervision | durable distributed execution and broader real tool adapters |
| 21 | Claire | paired-device hash-chain result receipt verification,  in-Atlas workflows, bounded capabilities, expiring fingerprinted device pairing/revocation, per-action gates and deception refusal | installable signed paired-PC daemon and durable orchestration |
| 22 | Tools Hub | durable tenant-persisted install pipeline (`/tools-hub/pipeline`): pre-scan + content-addressed artifact store, Module 0 approval bound to tool/version/artifact/manifest hashes, worker job that re-verifies and re-scans before the installer consumes a single-use grant, installer-written receipts, persisted portfolio with version history and separately approved rollback; free official GitHub/PyPI/npm discovery with tenant-persisted, de-duplicated candidates; proposals straight from a candidate that fetch the PyPI wheel or npm tarball and check it against the registry-published SHA-256/SHA-512 before scanning; separately approved sandboxed smoke-run (no network, cleared env, read-only system, rlimits) of the installed entrypoint with hashed logs recorded on the portfolio | GitHub-only candidates cannot be installed (no registry-published digest); PyPI sdist-only packages are refused (Atlas does not run builds); smoke-run proves the entrypoint loads, not that the tool does useful work; no dependency resolution; Python smoke-runs now go through M4's merged sandbox backend (bubblewrap/Docker); Node smoke-runs still use the bundled bubblewrap runner, which needs bwrap in the worker image |
| 23 | Study Abroad | application requirement/essay-claim evidence matrix,  advising, identity interview, essay tools and lifecycle planning | live program-source and application acceptance |
| 24 | Billing | exact-charge and cancellation commitment preview,  plan metadata, test-mode checkout/cancel/invoice approvals, signed idempotent webhook, entitlements and metering | live Stripe acceptance and production pricing/tax setup |
| 25 | Knowledge Copilot & Training | consent-bound local ingestion/search/export plus mounted contradiction and claim-substantiation checks | universal module artifact routing and device capture adapter |

See [`ENHANCEMENTS.md`](ENHANCEMENTS.md) for module-by-module landed enhancements and clearly separated next candidates, prioritizing computational-science workflows.

## Fallback policy

A fallback is legitimate only when a real primary implementation exists and the fallback handles an optional dependency, missing key, upstream failure or malformed model output. Current legitimate examples are: provider-backed email action extraction to deterministic extraction; provider-backed social strategy to deterministic formatting; WeasyPrint PDF to inspectable HTML; PPTX to Markdown when `python-pptx` is not installed; and routed model retries across eligible providers.

Deterministic logic that replaces a requested primary capability is not called complete. M1 normalization and matching now run on a live stack in the production routes: spaCy NER, cue-anchored dateparser deadlines and free in-process embedding similarity (fastembed `BAAI/bge-small-en-v1.5`; Ollama or BYOK OpenAI by config). Each opportunity records the engine that scored it (`match_engine`, `deadline_engine`), and `GET /api/v1/opportunity-discovery/nlp-status` shows what is loaded. Keyword/token scoring runs only when a dependency is missing or a backend fails, and the row says so. The M1 impact score is still a labelled heuristic, and the DeBERTa eligibility classifier is not built. The M10 rule classifier is useful on its own, but it is also a stand-in until a verified trained checkpoint is supplied. Exact classifications and evidence are in [`docs/FALLBACK_AUDIT.md`](docs/FALLBACK_AUDIT.md).

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

## Shared model layer (instinct_models)

Atlas uses the model layer shared with Meemee and Sugarcode: https://github.com/uditakankananonononono/shared-models, vendored at `backend/instinct_models` (pin in `backend/instinct_models/VENDORED.md`, currently f8840ff; re-sync with `scripts/sync_shared_models.sh <sha>`).

- `app/core/shared_model_layer.py`: `atlas_config()` / `atlas_router()` / `run()`. Product is always `atlas`. Reads `INSTINCT_*` env, falling back to `ATLAS_*` (`ATLAS_HF_MODEL`, `ATLAS_ORNITH_URL`, `ATLAS_ORNITH_MODEL`, `ATLAS_INKLING_LOCAL_URL`, `ATLAS_NEEDLE_WEIGHTS`, `ATLAS_ALLOW_HOSTED`).
- `run()` defaults to `private=True`: contract and mail content never reaches the hosted HF route (free tier, metered past it). Set `ATLAS_ALLOW_HOSTED=0` to drop the hosted route entirely.
- Needle only gets tool-calling tasks. Local routes (Needle, Ornith, Inkling on her own hardware) are free.
- Needle training data: `app/modules/m07_brand_collaboration/needle_dataset.py` builds rows from confirmed M07 obligation drafts only (pending/rejected never read); arguments appear only when their exact text is in the clause. Feed it to `instinct_models.training.build_needle_jsonl`; the manifest marks it train-locally-only.
