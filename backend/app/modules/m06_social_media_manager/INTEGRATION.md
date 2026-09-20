# Module 6 (Social Media Manager) - integration notes

## Shared files this module needs (integrator-owned edits)

1. **`backend/app/modules/types.py` (missing from snapshot).** The conventions
   require `from app.modules.types import ModuleSpec`, but no such file exists
   in the current repo. Please add it with the exact shape the conventions
   show:
   ```python
   @dataclass(frozen=True)
   class ModuleSpec:
       id: int
       slug: str
       name: str
       router: APIRouter
       service_type: type
   ```
   The module cannot import without it; a local shim was used to run the tests
   and is deliberately excluded from this patch.
2. **`backend/app/main.py`:** mount `m06_social_media_manager.spec.router`
   under the global `/api/v1` prefix.
3. **`backend/app/modules/catalog.py`:** flip module 6 status from `"stub"`.

## Configuration / credentials

- New env fields (Phase 1 stopgap): `ATLAS_META_ACCESS_TOKEN`,
  `ATLAS_X_BEARER_TOKEN`, `ATLAS_LINKEDIN_ACCESS_TOKEN`,
  `ATLAS_LINKEDIN_ORG_ID`. These are per-user platform credentials and should
  move into the shared BYOK credential store (per-user encryption, tenant
  isolation, rotation, revocation) once it lands, same as LLM keys.
- No new pyproject dependencies: only fastapi/pydantic/httpx are used.

## Approval-gated effects (executor wiring)

The module files approval requests and never executes external effects. The
approval executor should handle these `action_type` values for `module_id=6`:

- `schedule_post` - payload `{plan_id, platform, format, copy, publish_at, api}`.
  Call only the official API named in `api`: Meta Graph API
  (`/{ig-user-id}/media` + `/media_publish`), X API v2 (`POST /2/tweets`),
  LinkedIn (`/v2/ugcPosts`), TikTok Content Posting API.
- `ab_test` - payload `{plan_id, platform, variant_a, variant_b, api}`.
  Post both variants per platform rules after approval.

## Compliance notes (spec substitutions)

- The spec's asset renderers (ComfyUI/Stable Diffusion XL for images,
  Bark/Tortoise-TTS for audio) are self-hosted and compliant. This module
  emits render prompts only; wiring the render jobs is an integration task
  (recommend gating them behind approval for compute-cost control).
- Analytics uses official read APIs only (Meta Graph insights, X API v2 user
  metrics, LinkedIn organization share statistics). No scraping, self-bots,
  unofficial wrappers, or proxies are used anywhere in this module. TikTok
  metrics raise a clear "not wired" error until an official API path is added.
- The LinkedIn/scraping items in the spec belong to module 7, not this lane.

## Persistence

Plans and analysis reports are held in memory. If durability is needed, add
shared tables (e.g. `m06_content_plans`, `m06_analysis_reports`) and a small
repository behind the existing service constructor; no module code changes
are required beyond injecting it.
