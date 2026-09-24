# Integration notes - Module 0 (Human Approval Center)

## What this lane delivers

- `backend/app/modules/m00_approval_center/` (`__init__.py`, `service.py`, `routes.py`, `schemas.py`)
- `tests/modules/test_m00_approval_center.py` (11 tests, all passing, fully offline)
- Owns two tables via the shared `Base`: `m00_approval_requests` (spec data model: id, user_id, module, action_type, payload JSON, status pending/approved/denied/expired, created_at, expires_at, approved_by) and `m00_approval_events` (append-only decision log).

## Shared-file needs (integrator action required)

1. **`backend/app/modules/types.py` does not exist yet.** The conventions require every lane to import `ModuleSpec` from it. This lane tested against this exact definition - please create it verbatim:

   ```python
   """Shared module contract owned by the integrator."""
   from dataclasses import dataclass
   from typing import Any
   from fastapi import APIRouter

   @dataclass(frozen=True)
   class ModuleSpec:
       id: int
       slug: str
       name: str
       router: APIRouter
       service_type: type[Any]
   ```

2. **Mount the router in `backend/app/main.py`** (shared file, not touched by this lane):

   ```python
   from app.modules.m00_approval_center import spec as m00
   app.include_router(m00.router, prefix="/api/v1")
   ```

   Resulting endpoints: `POST /api/v1/approval-center/requests`, `GET .../requests` (filters: status, module_id, user_id, limit), `GET .../requests/{id}`, `POST .../requests/{id}/decision`, `GET .../requests/{id}/audit`, `POST .../expire`, `GET .../events` (SSE).

3. **Redis Streams fan-out (spec: "Dedicated FastAPI service + Redis Streams").** This lane ships an in-process `ApprovalBroadcaster` behind the SSE route, correct for the single-process Phase 1 gateway. When Celery workers run in separate processes, add a Redis-backed publisher (compose already defines `ATLAS_REDIS_URL`) so `submit`/`decide`/`expire_overdue` events reach every process; the broadcaster interface (`subscribe`/`unsubscribe`/`publish`) is the seam. New dependency at that point: `redis` client in pyproject (integrator's shared edit).

4. **Distributed callbacks / worker release.** `Service.register_callback` and `wait_for_decision` cover the spec's "blocks the calling worker, callback invoked on decision" inside one process. Cross-process release-to-execution needs a Redis Streams consumer or Celery task dispatch keyed by approval id - integrator work once the worker tier lands.

5. **Expiry sweeper.** Lazy expiry is built in (reads and decisions expire overdue rows on contact), and `POST .../expire` / `Service.expire_overdue()` does a full sweep. Wire it to Celery Beat (e.g. every 60s) when the scheduler exists.

6. **Auth / user_id.** `user_id` is a free-form string defaulting to `"default"` until the auth skeleton lands; `decided_by` is caller-supplied. Both should come from the authenticated identity once available.

7. **Relationship to `app/core/approvals.py`.** The existing core `ApprovalStore` backs the legacy `/api/v1/approvals` endpoints used by the planner, with a narrower model (no user_id/expires_at/approved_by). Module 0 implements the full spec model in its own tables and deliberately does not edit core. Recommend the integrator converge the planner onto this module's `request_approval` SDK so there is one approval path.

## SDK for other module lanes

```python
from app.modules.m00_approval_center import request_approval

view = request_approval(module_id=5, action_type="send_email",
                        payload={...}, ttl_seconds=3600)            # returns pending view
final = request_approval(module_id=5, action_type="send_email",
                         payload={...}, wait=True)                  # blocks worker until human decides
```

## Compliance

No scraping, self-bot, proxy, or evasion features exist in this module, so no substitutes were needed. BYOK note: this module makes no LLM calls; modules that do must use `app.core.providers.generate` per conventions.

## Tests

`pytest tests/modules/test_m00_approval_center.py` -> 11 passed. Full repo suite (`pytest`) -> 16 passed. No network access required; tests inject their own SQLite engine and clock.


## Impact preview and drift check (2026-09-24)

Register a read-only probe for any gated action whose safety depends on external state:

```python
from app.modules.m00_approval_center.impact import PROBES
PROBES.register("send_email", lambda payload: gmail_thread_state(payload["thread_id"]), module_id=10)
```

Capture the reviewed state when the approval card is shown (`POST /approval-center/requests/{id}/review-state`, optional explicit `{"state": {...}}`). Consumption (`/consume`, `atlas.modules.execute_approved`) re-reads the probe and refuses the permit if anything changed. Approvals without a snapshot behave as before. Table: `m00_approval_review_states` (migration `20260924_m00_review_states`).

**Status (2026-09-24, PB2):** first real probe live. M10 registers `send_email_reply` (`m10_email_assistant/drift_probe.py`) on import: it reads the live Gmail thread (metadata only), the reply target's Reply-To/From and trash state, and the stored draft (recipient, subject, body SHA-256, status). A new reply in the thread, the owner replying from Gmail directly, a changed Reply-To, or an edited draft blocks consume with a drift list; an unreadable state (revoked token, account disconnected, Gmail down) fails closed. M10 also captures the reviewed state automatically when it drafts the reply (after linking the draft to the durable M00 approval id), so reply approvals are checked without a UI call; a failed capture is logged on the draft (`review_state_capture_failed`) and the card can re-capture. Other modules still have no probe.
