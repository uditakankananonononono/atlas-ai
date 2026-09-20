# Module 16 integration

Provides a durable tenant-scoped executive snapshot, event cursor API plus resumable SSE live feed, consolidated approval review, and preview-first natural-language command bar. Read-only commands may execute once; mutations only create approval requests. Command previews expire and cannot be replayed. `critical_path` detects cycles and calculates the duration-weighted dependency path for the Gantt UI.

The host event bus should call `append_event` and update the materialized snapshot transactionally. SSE works now and is proxy-safe; a Redis-backed broadcaster can add WebSockets across replicas without changing the cursor/event contract. Register `spec` and mark catalog item 16 implemented.
