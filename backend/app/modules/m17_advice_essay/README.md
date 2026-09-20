# Module 17 - Social Media Advice Compiler & College Essay Architect

## Scope

This module compiles attributable advice from user-submitted material and approved
public APIs/pages, clusters it into traceable tips, and supports college-essay
coaching from user-confirmed experiences. It generates concept lenses, metaphors,
outlines, writer prompts, critique findings, and questions for revision.

It does **not** scrape logged-in sessions, bypass access controls, rotate proxies,
create accounts, generate engagement, evade platform controls, evade AI detection,
or claim machine-generated prose was written by the user. Concepts are scaffolds,
not submission-ready essays. The user must verify facts and write the final words.
Any future external publication or application submission belongs behind Module 0
approval and is intentionally not exposed by these routes.

## Host integration

Mount `build_router(service_provider, owner_provider)`. `owner_provider` must derive a
UUID from authenticated context. Never derive it from request content. Configure a
`GuardedPublicCollector` only with hosts and clients approved for lawful public access.
External API/model/transcription implementations are injected; imports are offline.

## Endpoints

- `POST /v1/modules/17/sources`
- `POST /v1/modules/17/advice/compile`
- `POST /v1/modules/17/identity-materials`
- `POST /v1/modules/17/essay/concepts`
- `POST /v1/modules/17/essay/critique`

## Data boundaries

Every stored row has `owner_id`; every read is owner-scoped. Public advice keeps its
canonical URL, creator when known, permission basis, and source IDs through compiled
tips. Identity material must be explicitly user-confirmed before concept generation.
