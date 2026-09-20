# Modules 10 + 11 Integration Notes

## Module 10 — Email Assistant (`app/modules/m10_email_assistant`)

Spec coverage (user directive, Module 10):
- **Gmail OAuth 2.0 + Pub/Sub**: `gmail.py` (authorization URL, code exchange,
  token refresh, users.history/watch/profile via injected httpx client);
  `service.Service.handle_push` decodes and verifies Pub/Sub envelopes; the
  webhook is `POST /api/v1/email-assistant/pubsub?token=...`. Watch renewal is
  `Service.renew_watches` and the `atlas.email.renew_watches` Celery task.
- **Categorisation**: the spec's seven labels in `schemas.EmailCategory`.
  `classifier.BertEmailClassifier` loads the fine-tuned BERT checkpoint lazily
  (transformers, already a project dep); `RuleBasedClassifier` is the
  deterministic fallback until a trained checkpoint exists.
- **Action extraction**: `extraction.extract_actions` calls the injected LLM
  with the exact spec output schema `[{action, deadline, related_entity}]`,
  validates it, retries once, then falls back to a deterministic heuristic so
  ingestion never hard-fails on model noise.
- **Drafting replies**: `_draft_reply` builds a context window from recent
  related emails (same thread) plus an optional knowledge-graph hook
  (`graph_context`, the Module 9 seam). Drafts are proposed to Module 0 as
  `send_email_reply` approvals. **This module has no send path**; executing an
  approved reply is the approval dispatcher's job.

Advancement pass beyond spec: idempotent ingestion on (tenant, gmail_id),
history-id checkpointing, List-Unsubscribe detection, sender-frequency
priority inbox (`GET /priority`), deadline follow-up surfacing
(`GET /follow-ups`), append-only audit rows (`m10_email_events`).

## Module 11 — Calendar Intelligence (`app/modules/m11_calendar_intelligence`)

Spec coverage (user directive, Module 11):
- **Sync**: Google watch channels + incremental syncToken with 410 full-resync
  recovery (`google_calendar.py`, `Service.ensure_watch` /
  `handle_google_notification` / `sync_source`); Outlook/Apple via CalDAV
  calendar-query REPORT (`caldav.py`, stdlib ICS parser in `ics.py`).
- **Smart scheduling**: `solver.Solver` protocol is the OptaPy seam;
  `BuiltInSolver` is a real CSP (working hours, no overlap, deadlines, travel
  buffers, prep blocks, protected focus time; energy-fit soft objective).
- **Conflict resolution**: `Service.request_reschedule` builds alternatives
  (split task / extend hours / push lowest priority) and proposes the first
  viable one as an `apply_reschedule` approval. `apply_reschedule` and
  `apply_plan` verify the approval decision before mutating anything.

Advancement pass beyond spec: splittable tasks, channel-token verification on
webhooks, cancelled-event handling, meeting-load analytics
(`GET /analytics/meeting-load`), append-only audit rows
(`m11_calendar_events_log`).

## Shared

- `app/core/token_crypto.py`: Fernet encryption for stored refresh tokens /
  CalDAV credentials; key from `ATLAS_TOKEN_KEY`, derived per tenant.
  `cryptography>=43` added to pyproject dependencies.
- Env: `ATLAS_GOOGLE_CLIENT_ID`, `ATLAS_GOOGLE_CLIENT_SECRET`,
  `ATLAS_PUBSUB_VERIFICATION_TOKEN`, `ATLAS_CALENDAR_WEBHOOK_URL`,
  `ATLAS_TOKEN_KEY`, `ATLAS_PUBSUB_TOPIC`.
- Celery: `atlas.email.renew_watches`, `atlas.calendar.renew_watches` (hourly
  beat entries use `ATLAS_LOCAL_TENANT`; a multi-tenant dispatcher is
  integrator work).
- Known limitations: ICS TZID-local times are surfaced as UTC; RRULE
  expansion, Gmail pagination beyond 500 history records, and pgvector LTM
  sync for email embeddings (rows carry embeddings in JSON meanwhile) are
  integrator work.
