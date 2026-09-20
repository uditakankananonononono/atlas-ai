# Module 2 integration notes

## Required shared wiring

- Register `m02_competition_manager.spec` in the shared module registry/router. The exported identity is exactly catalog ID `2`, slug `competition-manager`, name `Competition Manager`.
- The snapshot supplied to this lane does not contain `backend/app/modules/types.py`, although `docs/MODULE_CONVENTIONS.md` requires `ModuleSpec` from that path. The integrator must provide the shared `ModuleSpec` definition before importing this package.
- Replace the service's default process-local dictionary with a durable, tenant-scoped repository before production use. No shared schema was added in this lane.
- Wire Knowledge Workspace persistence for reviewed drafts and task-system persistence for generated checklist items. This module currently returns and retains those domain objects but does not edit shared services.
- Wire Module 13 to consume the approval payload for `competition.form_fill_and_submission`. The browser worker should stage fields, capture a screenshot, and request a separate final approval before form submission. A proposal from this module is never permission to submit.
- If automated tracking is wanted, feed `StatusEvidence` from official competition APIs, user-connected email parsing, or manual confirmation.

## Compliance replacements

The original spec mentions web scraping for submission status and judging announcements. This lane does not scrape or evade site controls. It accepts evidence from official APIs, connected email, or manual updates. Official rules text must likewise arrive from a user, licensed source, official API, RSS feed, or site-permitted/user-authorized browser session.

No self-bots, unofficial social wrappers, rotating residential proxies, stealth/evasion, or direct form submission are implemented.

## Approval and BYOK boundaries

Rule extraction and field drafting call `app.core.providers.generate`, so provider credentials stay in the shared BYOK layer. Creating a form-fill proposal writes a pending shared approval request. The returned action explicitly says that execution did not occur. The eventual browser stage and the final submit must remain separate approval-controlled effects.
