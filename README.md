# Atlas AI

Original Phase 1 foundation for Atlas AI, owned by Udita. Atlas is being built as a commercial, human-controlled, modular work platform. This repository is new code and does not copy or depend on any private assistant implementation.

## What runs today

A FastAPI service provides:

- `GET /health`
- `GET /api/v1/modules` - the complete module registry
- `POST /api/v1/goals/plan` - a small end-to-end workflow: accept a goal, route it to relevant modules, return a typed plan, and generate a pending approval request before outreach

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --app-dir backend --reload
# another shell
curl -X POST http://localhost:8000/api/v1/goals/plan \
  -H 'content-type: application/json' \
  -d '{"goal":"Research professors and draft outreach email"}'
pytest
```

Or run infrastructure with `docker compose up --build`. PostgreSQL/pgvector and Redis are included now so later phases do not require a platform rewrite.

## Spec map

All module identities live in `backend/app/modules/catalog.py`; code grows behind these stable boundaries.

| ID | Spec module | Phase 1 location | State |
|---:|---|---|---|
|0|Human Approval Center|`core/models.py`, `core/planner.py`|Foundation: pending request model and gate|
|1|Opportunity Discovery|`modules/catalog.py`|Stub|
|2|Competition Manager|`modules/catalog.py`|Stub|
|3|Grant & Fellowship Writer|`modules/catalog.py`|Routing skeleton|
|4|Research Scientist|`modules/catalog.py`|Routing skeleton|
|5|Outreach Manager|`core/planner.py`|Routing + approval gate|
|6|Social Media Manager|`modules/catalog.py`|Stub|
|7|Brand Collaboration Manager|`modules/catalog.py`|Stub|
|8|Startup Growth|`modules/catalog.py`|Stub|
|9|Knowledge Workspace|`modules/catalog.py`|Stub|
|10|Email Assistant|`modules/catalog.py`|Stub|
|11|Calendar Intelligence|`modules/catalog.py`|Stub|
|12|AI Research Lab|`modules/catalog.py`|Stub|
|13|Browser Agent|`modules/catalog.py`|Stub|
|14|Project Builder|`modules/catalog.py`|Routing skeleton|
|15|Document Generator|`modules/catalog.py`|Routing skeleton|
|16|Executive Dashboard|`frontend/app/page.tsx`|Static shell|
|17|Social Advice Compiler & College Essay Architect|`modules/catalog.py`|Stub|
|18|Side Hustle & Knowledge Scraper|`modules/catalog.py`|Stub|
|19|Autonomous Idea Incubator|`modules/catalog.py`|Routing skeleton|
|20|General Cognitive Worker|`modules/catalog.py`|Fallback route, intentionally bounded|
|21|Claire PA / Idea Realisation Engine|`modules/catalog.py`|Stub, bounded by permission and retry budgets|

## Deliberately deferred

Auth/OIDC, tenant data models, encrypted BYOK storage and key rotation, durable approval callbacks, Celery workers, SSE, provider adapters, vector memory, billing/tier enforcement, deployment, and production observability. These are not cosmetic TODOs: they need explicit contracts, acceptance tests, threat modelling, and account choices.

The first customer workflow and cloud target are still open product decisions. Zero-cost services can support an early demo, but no README should promise that a multi-user commercial system will stay at zero operating cost.

## Compliant substitutions

The spec mentions Discord self-bots, unofficial social APIs, residential proxies, stealth scraping, and scraping behind authenticated services. Atlas will instead use official APIs/RSS/licensed sources, user-authorized browser sessions, robots/terms-aware collection, and manual import where no compliant integration exists. See `docs/ARCHITECTURE.md`.

## Commercial boundaries

Module IDs and entitlements will stay separate so `$50 / $150 / $300` product tiers can be added without forking the codebase. Users bring their own model/provider keys; Atlas will not bundle the founder's keys.
