# Module 5 integration notes

## Required shared wiring

- Add `app.modules.types.ModuleSpec` if it is not already introduced by the integration branch. This module exports `spec` with ID 5, slug `outreach-manager`, name `Outreach Manager`, its router, and `Service` type.
- Register `m05_outreach_manager.spec` in the shared module registry/router. The local router already uses `/outreach-manager`; add only the global `/api/v1` prefix.
- The router's `Container` dependency already wires the SQL repositories (`SqlContactRepository`, `SqlCampaignRepository`), `SemanticScholarClient`, Hunter/Clearbit enrichment clients, the lab discovery service, the campaign service, and the delivery service per request, and closes the shared `httpx.AsyncClient` deterministically. Production deployments only need the environment variables below.
- SQL tables (`m05_contacts`, `m05_contact_changes`, `m05_campaigns`, `m05_messages`, `m05_message_events`) are created per tenant from shared `Base` metadata by the repositories (`Base.metadata.create_all(engine)`), following the same tenant pattern as Module 0. The integrator should convert this to Alembic migrations when the shared migration tooling lands; until then repository construction auto-provisions.
- Add `email-validator` to shared dependencies because Pydantic's `EmailStr` needs it, or replace `EmailStr` centrally with the repository's chosen validated email type.

## Environment variables

| Variable | Required for | Notes |
| --- | --- | --- |
| `HUNTER_API_KEY` | email verification + email finder enrichment | official Hunter.io key; never logged or returned |
| `CLEARBIT_API_KEY` | person/company profile enrichment | sent as a Bearer token; never logged or returned |
| `ATLAS_SMTP_HOST` | delivery (approved sends) | without this + `ATLAS_SMTP_FROM`, send/delivery-audit/delivery-report endpoints return a clear 503 |
| `ATLAS_SMTP_PORT` | delivery | default 587 (STARTTLS) |
| `ATLAS_SMTP_USERNAME` / `ATLAS_SMTP_PASSWORD` | delivery | optional SMTP auth |
| `ATLAS_SMTP_FROM` | delivery | the approved sending account; approval payloads must bind this exact account |
| Semantic Scholar key | professor discovery | optional `x-api-key` configuration on `SemanticScholarClient` if rate limits require it |

## Delivery and approvals

- `DeliveryService.send_approved` is triple-gated: the message must be in `approved` state, a Module 0 approval for that message must exist and be approved, and the approval payload must bind the exact recipient, subject, body, and message id. Any drift fails closed with no send.
- `ModuleZeroApprovalGate` works over the facade's current `put/list/decide/audit` surface by scanning `list(module_id=5)`. **Request for the Module 0 lane:** add `approvals.get(approval_id)` to the facade so the gate can do a direct lookup instead of scanning. The gate already isolates this in one method.
- Module 0 `decide()` invokes the registered per-message callback (`CampaignService.record_decision(message_id, approved, actor)`). There is no public message-decision route: callers cannot mirror or self-attest an approval.
- `submit_for_approval` registers the approval with payload `{recipient, subject, body, sending_account, message_id}` so the gate's exact-match check has something to bind against.

## Follow-up scheduling

`CampaignService.due_follow_ups()` returns sent messages whose follow-up window has elapsed with no reply and remaining follow-up budget. Wire a periodic worker (Celery beat or the shared scheduler) to:

1. call `due_follow_ups()` per tenant,
2. call `draft_follow_up(message_id, generate)` to create the next draft (idempotent: an existing follow-up draft is returned unchanged),
3. call `submit_for_approval` on each new draft so a human approves every send.

Reply detection stays in the Email Assistant over Gmail/IMAP provider APIs; it should call `POST /messages/{id}/reply`, which cancels pending follow-ups and stops the chain. No tracking pixels or covert open tracking are implemented.

## Compliance substitutions

The source spec mentions scraping university/lab pages and direct SMTP/IMAP sending. This implementation instead uses:

- the official Semantic Scholar Graph API for professor discovery and impact signals;
- Hunter.io and Clearbit official APIs for verified email enrichment (a contact only becomes `verified` on a provider verdict of `valid`; enrichment never silently overwrites existing contact fields — every change is an attributed `ContactChange` row);
- robots.txt-respecting, per-host-rate-limited lab page collection for university/lab discovery, with all extracted emails starting `unverified`;
- SMTP sending only through the triple-gated delivery service after a Human Approval Center decision, never direct send code elsewhere in the module;
- provider API/thread metadata for reply tracking;
- manual handoffs (never automated self-bots) for LinkedIn/Instagram/X/Discord/Slack outreach steps in plans, each still requiring per-send approval.

Draft and proposal generation calls the shared BYOK `app.core.providers.generate` function. Keys are never read, stored, returned, or logged by this module.

## Lab registry growth

`data/lab_registry.json` ships with a small seed of well-known institutes and labs. Operators can extend it with additional entries (`name`, `university`, `country`, `topics`, `page_url`); `LabRegistry.load()` reads this module-relative file and can also accept an explicit path for deployment-specific registries. Discovery remains scoped to this registry plus explicitly supplied URLs — it is not a general web crawler.

## Growth planning surface (feature rows 417-450)

`growth.py` adds 34 typed, evidence-bound planning builders mounted at
`POST /outreach-manager/growth/<slug>` (one route per row, see the
`_GROWTH_ENDPOINTS` table in routes.py). Properties the integrator can rely on:

- Every builder returns a deterministic, reviewable artifact (`BusinessArtifact`,
  or typed results for lead scoring and price elasticity). Nothing executes:
  artifacts only plan.
- Every external effect is listed in the artifact's `gated_effects` and, where a
  real send exists (email marketing row 425), binds to the campaign runtime's
  exact-review approval machinery - the same action types, verified-email scope
  rules, and per-domain caps as outreach campaigns.
- No builder fabricates contacts, journalists, creators, prices, or market data.
  Empty supplied lists produce artifacts with explicit scope checks and manual
  import steps, never invented entries.
- Computed rows do transparent arithmetic on supplied numbers (lead scores,
  midpoint elasticity, funnel conversion, CRO drop-off, health scores, price
  floors, tier spacing, bundle discounts, dynamic-price bound stacking) and
  embed those inputs as evidence items.
- Requests carry caller-supplied evidence (`source` + `fact`); artifacts must
  cite at least one evidence item and every section's evidence keys are
  validated. Missing evidence or invalid inputs return 422.

## Corporate review artifacts (feature rows 476-509)

`corporate.py` adds 34 evidence-bound review-artifact builders mounted at
`POST /outreach-manager/corporate/<slug>`, sharing the artifact model and
invariants of the growth surface (evidence citation enforced, all external
effects approval-gated, deterministic computation on supplied inputs).

Finance- and legal-adjacent rows (compensation, equity, cap table, fundraising,
valuation, term sheets, M&A, IPO) carry an explicit "planning aid only - not
financial, legal, tax, or investment advice" scope check, and fundraising rows
carry "no investor contact, solicitation, or send is performed by this module".
Computed rows: stakeholder quadrants, span-of-control flags, SWOT pairings,
PESTLE attention list, scenario grids, OKR scoring formula (plus a public
`score_okr` for period-end review), KPI leading/lagging balance, pay mix,
equity/cap-table percentages with over-authorization rejection, fundraising
runway math, financial projection arithmetic, single-multiple valuation with
caveats, diligence coverage %, term-sheet give-for-must trade plan, M&A implied
multiple, IPO readiness scorecard.
