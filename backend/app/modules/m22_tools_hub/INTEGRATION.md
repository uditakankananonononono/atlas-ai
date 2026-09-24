# Integration
Mounted through `spec.router` (`/api/v1/tools-hub`). Candidate discovery is read-only. Legacy in-memory installation proposals redact secret/token-like config and require Module 0 approval.

Installation runs through the durable pipeline in `pipeline.py` (routes in `pipeline_routes.py`, prefix `/api/v1/tools-hub/pipeline`):

1. `POST /proposals` with `artifact_base64` (ZIP) + `manifest` - scans first, stores bytes content-addressed, submits a Module 0 `integrate_tool` approval binding the install subject.
2. After a human approves in Module 0: `POST /proposals/{id}/install-jobs` queues one job.
3. The Celery beat task `atlas.m22.drain_install_jobs` (or `POST /jobs/{id}/run`) runs it: approval re-check, hash re-check, re-scan, then `ToolInstaller.install` with a single-use grant. The installer writes the receipt.
4. `GET /portfolio` lists active installs (`?include_history=true` for superseded/rolled back).
5. Rollback: `POST /installs/{operation_id}/rollback-proposals` -> approve `rollback_tool` in Module 0 -> `POST /installs/{operation_id}/rollback-jobs`.

Config: `ATLAS_TOOLS_ROOT` (default `/tmp/atlas-tools`) holds artifacts, per-tenant installs, backups, receipts and consumed-grant state. Tables: `m22_install_proposals`, `m22_install_jobs`, `m22_tool_portfolio`.
