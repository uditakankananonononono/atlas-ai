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

- **NLP stack - live (PB2, 2026-09-24).** `nlp_stack.py` is wired into the
  production routes (`get_service` passes `default_stack()`):
  spaCy NER (`ATLAS_SPACY_MODEL`, default `en_core_web_sm`) adds entity tags;
  dateparser normalizes deadlines only next to a deadline cue ("apply by",
  "applications close", ...) in `ATLAS_M01_DEADLINE_TIMEZONE` (default UTC),
  so posting/event dates are not taken as deadlines. The fine-tuned DeBERTa
  eligibility classifier is still unbuilt (no verified checkpoint/licence).
- **Embedding match score - live (PB2, 2026-09-24).** Cosine similarity of
  opportunity vs profile embeddings. `ATLAS_M01_EMBEDDING_PROVIDER`:
  `fastembed` (default, free, in-process ONNX `BAAI/bge-small-en-v1.5`,
  weights cached after first download), `ollama` (local server, `bge-m3`),
  `openai` (BYOK, never default), `token` (explicit opt-out).
- **Provenance.** Every stored opportunity carries `match_engine` and
  `deadline_engine`. Token-cosine/regex values appear only when a dependency
  is missing, the operator opted out, or the backend failed for that item, and
  the value names the reason (`token-cosine:fallback(...)`).
  `GET /opportunity-discovery/nlp-status` reports what is loaded and why any
  part is degraded. Migration `20260924_m01_nlp_provenance` adds the columns.
- **Not yet done:** pgvector storage of opportunity embeddings (vectors are
  computed per scan, not persisted).
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

## 7. Free student platforms (2026-09-25)

`student_platforms.py` adds a separate, read-only M01 surface at
`GET /opportunity-discovery/student-platforms` and
`GET /opportunity-discovery/student-platforms/{id}/discover?query=...&limit=25`.
The latter ranks real public links by deterministic token similarity and returns
`source_url`, `scanned_at`, the platform ID and the original HTTPS listing URL.
The platform's source listing is fetched on demand; it is not yet merged into
`Service.run_scan` or persisted to `m01_opportunities`. A blocked or changed
source returns 503, never dummy results. No paid key is required.

| Platform | Status and precise boundary | Public source |
|---|---|---|
| RippleMatch | Launch only: job matching/auto-apply needs a student account; no application firing | https://ripplematch.com/ |
| Simplify | Launch only: Copilot is a user-installed browser extension; Atlas does not claim to run it | https://simplify.jobs/copilot |
| RaiseMe | Launch only: micro-scholarship balance and school matching need the student's account | https://www.raiseme.com/ |
| Bold.org | Launch only: public listing rate-limited during source check; no circumvention | https://bold.org/scholarships/ |
| Fastweb | Public HTML scholarship listing discovery (not personalized matching) | https://www.fastweb.com/college-scholarships |
| Devpost | Launch only: the official hackathon page linked RSS, but RSS returned 403/406 here; older undocumented JSON endpoint is not treated as an API contract | https://devpost.com/hackathons |
| ChallengeRocket | Public challenge-card discovery, no applications | https://challengerocket.com/hackathons-and-challenges.html |
| Major League Hacking | Public event-card discovery, no registration | https://www.mlh.com/seasons/2026/events |
| Internshala | Public internship-card discovery, no applications | https://internshala.com/internships/ |
| Scholarships360 | Editorial RSS discovery only, not the full scholarship catalog | https://scholarships360.org/feed/ |
| Unigo | Launch only: no validated public listing feed | https://www.unigo.com/scholarships |
| Scholarship Roar | Public RSS discovery | https://scholarshiproar.com/feed/ |
| Scholarship Region | Public RSS discovery | https://www.scholarshipregion.com/feed/ |
| Opportunities for Africans | Public RSS discovery | https://www.opportunitiesforafricans.com/feed/ |
| Scholarship Union | Public RSS discovery | https://scholarshipunion.com/feed/ |
| Opportunities for Youth | Public RSS discovery | https://opportunitiesforyouth.org/feed/ |
| Kaggle Competitions | Launch only: public listing JavaScript-rendered; anonymous API not validated | https://www.kaggle.com/competitions |

The first seven rows are the requested platforms; the remaining ten are
additional free public student opportunity platforms (some are regional and
should not be presented as personalized eligibility matches). Discovery means
read-only links, not account integrations. Even when a vendor offers automated
application behavior to *its own* users, Atlas cannot claim that behavior or
submit on the user's behalf without an authenticated, approval-gated browser
workflow and its own end-to-end test. Free to browse does not establish that
every individual listing is free to enter; check its own terms before applying.

The source-specific parser tests and a separately opted-in live smoke suite are
`tests/modules/test_m01_student_platforms.py` (`ATLAS_M01_LIVE_SMOKE=1`).
A live smoke success proves the public page responded and an item parsed at
that moment, not lasting vendor permission, account-action readiness, or
completeness of the catalog. All sources can change layouts or access policy.
