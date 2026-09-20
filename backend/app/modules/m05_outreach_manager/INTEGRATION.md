# Module 5 integration notes

## Required shared wiring

- Add `app.modules.types.ModuleSpec` if it is not already introduced by the integration branch. This module exports `spec` with ID 5, slug `outreach-manager`, name `Outreach Manager`, its router, and `Service` type.
- Register `m05_outreach_manager.spec` in the shared module registry/router. The local router already uses `/outreach-manager`; add only the global `/api/v1` prefix.
- Replace the route module's development `InMemoryContactRepository` with a tenant-scoped PostgreSQL implementation of `ContactRepository`. Persist contact versions and append-only `ContactChange` rows in a transaction.
- Construct `Service` in the shared dependency layer and inject the shared `ApprovalStore`, a lifecycle-managed `httpx.AsyncClient`, and `SemanticScholarClient`. Close the HTTP client during application shutdown. Do not use the route module's development objects in production.
- If Semantic Scholar rate limits require it, add server-side configuration for an official API key and pass it as `x-api-key`. Never expose the key to a response or log.
- Connect approved `send_outreach_email` and `send_follow_up` actions to the existing mail dispatcher. Approval must bind the final recipient, subject, body, sending account, and attachments. This module deliberately never sends mail.
- Connect inbox reply detection in the Email Assistant through Gmail/IMAP provider APIs. Only request a follow-up draft after a thread-level reply check; scheduling and actual sending remain outside this module.

## Compliance substitutions

The source spec mentions scraping university/lab pages and direct SMTP/IMAP sending. This implementation instead uses:

- the official Semantic Scholar Graph API for professor discovery and impact signals;
- user-entered contact data or enrichment supplied by official/licensed APIs such as Hunter/Clearbit through an injected repository/provider (no stealth scraping, self-bots, residential proxies, or unofficial wrappers);
- shared, user-authorized mail provider integrations after a Human Approval Center decision, rather than direct send code in this module;
- provider API/thread metadata for reply tracking. No tracking pixels or covert open tracking are implemented.

Draft generation calls the shared BYOK `app.core.providers.generate` function. Keys are never read, stored, returned, or logged by this module.
