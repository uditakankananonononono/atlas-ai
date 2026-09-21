# Module 1 (Opportunity Discovery Engine) - integration notes for the integrator

This lane owns only `backend/app/modules/m01_opportunity_discovery/` and
`tests/modules/test_m01_opportunity_discovery.py`. Nothing shared was edited.
Everything below is a request or a note for the integrator.

## 1. Shared file needed: `backend/app/modules/types.py` (new)

`docs/MODULE_CONVENTIONS.md` requires every module to import
`ModuleSpec` from `app.modules.types`, but that file does not exist in the
current snapshot (`backend/app/modules/` contains only `__init__.py` and
`catalog.py`). Every lane needs it, so the integrator should add it once:

```python
from dataclasses import dataclass

from fastapi import APIRouter


@dataclass(frozen=True)
class ModuleSpec:
    id: int
    slug: str
    name: str
    router: APIRouter
    service_type: type
```

and mount each module's router under `/api/v1` in `backend/app/api/routes.py`
(or `main.py`). This module's `spec` (id=1, slug="opportunity-discovery",
name="Opportunity Discovery Engine") matches `catalog.py` exactly.

## 2. Folder naming

The conventions say `mNN_<slug>`, but the catalog slug
`opportunity-discovery` contains a hyphen, which is not a valid Python
package name. This lane uses `m01_opportunity_discovery` (underscores) so the
package is importable; the `ModuleSpec` slug keeps the exact catalog value.
Recommend standardizing on "underscores in folder names, catalog slug in
ModuleSpec/routes" across lanes.

## 3. Route surface (mounted under /api/v1)

- `GET  /opportunity-discovery/sources`
- `POST /opportunity-discovery/scans`
- `GET  /opportunity-discovery/opportunities` (query: min_score, opportunity_type, limit)
- `GET  /opportunity-discovery/opportunities/{opportunity_id}`
- `POST /opportunity-discovery/digests` (drafts a digest and creates an
  ApprovalRequest; never sends)

## 4. Spec compliance: source replacements

The spec's source list includes items that violate platform ToS or the repo's
compliance rules. They are NOT implemented; compliant replacements:

| Spec source | Status in this module |
|---|---|
| Kaggle RSS, Opportunity Desk, Opportunities for Youth, Reddit (r/competitions, r/scholarships), GitHub Topics | Implemented as RSS/Atom feeds / official GitHub REST search API in `DEFAULT_SOURCES` |
| Devpost API | Implemented via its JSON hackathons listing; if Devpost does not formally document this endpoint, treat as enabled-only-after-confirmation and consider their official channels |
| Unstop HTML scraping | Not implemented. Unstop offers no public API; add only via a licensed feed/partnership or user-submitted webhook |
| LinkedIn jobs | Not implemented. Use the official LinkedIn API (requires partnership) or RSS job feeds instead |
| Instagram hashtags | Not implemented. Replace with the official Meta Graph API hashtag search under a user-authorized account |
| Twitter/X lists | Not implemented. Replace with the official X API v2 under a paid tier |
| Discord channels via read-only self-bots | Not implemented (self-bots violate Discord ToS). Replace with an official Discord bot invited by each server |
| Custom webhooks | Intentionally deferred: needs an authenticated inbound webhook route at the gateway level (shared surface), not in this lane |

## 5. Deferred spec features (phase-1 stand-ins)

- **NLP stack** (spaCy entity extraction, dateparser, fine-tuned DeBERTa
  eligibility classifier): replaced by deterministic keyword type-tagging and
  multi-format deadline parsing. No new dependencies added. Reintroduce
  behind the same `tag_type`/`parse_deadline` interfaces when model choices
  and licenses are agreed.
- **Embedding match score**: spec wants cosine similarity between opportunity
  and profile embeddings; `providers.generate` is text-only and there is no
  embedding provider or pgvector wiring yet. Phase 1 uses token-vector cosine
  similarity (`cosine_similarity`). Swap the internals of `match_score` when
  embeddings exist.
- **Expected impact logistic regression**: disabled because no verified open
  dataset contains row-level applicants, comparable decision-time features,
  and both awarded and declined outcomes across Atlas opportunity types. The
  public API exposes `impact_heuristic` with `score_kind="heuristic"` and
  `advisory_only=true`; it is never a win probability. `program_priors.py`
  accepts versioned official aggregate counts keyed by sponsor, mechanism,
  cycle and geography and returns a provenance-bearing Wilson interval.
  Training must wait for a consented first-party outcome ledger spanning
  multiple cycles, temporal holdout evaluation, and calibrated lift over the
  program-prior baseline.
- **Hourly Celery Beat crawls**: this module exposes `run_scan`; the
  integrator should schedule it (e.g. Celery Beat) once workers exist.
- **SSE instant alerts (>0.8)**: `Service` accepts a `notifier` callable and
  invokes it for each new opportunity at or above the threshold. Wire it to
  the foundation's SSE bus when that exists; no SSE code lives in this lane.
- **Daily digest send**: `propose_digest` only creates an ApprovalRequest
  (module_id=1, action_type `send_opportunity_digest_email`,
  `execution_enabled: false`). The Email Assistant (module 10) should perform
  the actual send after human approval.

## 6. Dependencies and config

- No new third-party dependencies (feed parsing uses stdlib ElementTree).
- No new `.env` fields. LLM polish in the digest route uses the shared BYOK
  provider (`app.core.providers.generate`); keys are never read, logged, or
  returned by this module.
- Database: the module defines `OpportunityRow` (table `m01_opportunities`)
  on the shared `Base` and creates it with `create_all` on first use, the
  same pattern as the approval store. When Alembic lands, replace with a
  migration for `m01_opportunities` (columns: see `service.py`).

## 7. BYOK usage

Only the digest route can make a model call, and only when the caller passes
`use_llm: true`; it calls `app.core.providers.generate` and falls back to the
deterministic template on `ProviderError` (e.g. missing key), so the
approval-gated flow works with or without BYOK configured.

## 8. Test file placement

The lane test file is `tests/modules/test_m01_opportunity_discovery.py`. This
patch deliberately does not include a `tests/modules/__init__.py` (several
lanes would collide on it); pytest runs the file fine without one under the
repo's `pythonpath = ["backend"]` config. Add one shared `__init__.py` (or
none) at integration time.

## 9. Consented first-party outcome ledger

`outcome_ledger.py` records owner-scoped pending, waitlisted, awarded, declined,
and withdrawn application outcomes. Every row requires explicit
`application_outcome_history` consent evidence, row-level provenance, an expiry,
and a bounded retention period. Revoking consent deletes all rows covered by
that evidence; expiry purges them. Declines and awards use the same validation
and provenance path. The ledger is advisory-only and deliberately has no
training, feature export, or model-fitting API. A later training proposal needs
fresh owner approval plus the multi-cycle and temporal-validation gates above.

## 10. Tenant isolation

The primary discovery service is bound to the authenticated tenant. Stored
opportunity identities include tenant identity, all list/get queries filter by
tenant, and digest approval payloads retain the tenant boundary. The HTTP
routes construct services from `require_tenant`; callers cannot select another
tenant in request data. Alembic revision `20260922_m01_tenant_isolation`
assigns pre-existing development rows to `local` and adds the tenant index.
