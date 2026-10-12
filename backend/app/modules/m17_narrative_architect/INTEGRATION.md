# Module 17 narrative integration

## Implemented

The mounted service collects supplied public collector results, preserves source
URLs/hashes, extracts deterministic tips with optional model labels, and keeps a
bounded deduplicated in-process cache partitioned by owner identifier. Critique
returns local suggestions; concepts are scaffolds, never final essay prose.
Revision acceptance/key registry storage are separate SQL components.

## Not implemented in this collection service

Official PRAW collection, Whisper transcription, a tenant-Postgres advice corpus
and vector retrieval are integration requirements, not shipped collector paths.
Current Reddit wiring uses the existing public JSON collector. The advice corpus
is not durable and eviction can remove old evidence. Configure public/licensed
collectors only. Media transcription must preserve source and reuse permission.
Do not claim these unavailable backends as deployed capabilities.

Acceptance still requires cross-tenant isolation, source retention, repeated
collection deduplication, bounded-cache behavior, injection fixtures, and no
mutation of the user's draft.
