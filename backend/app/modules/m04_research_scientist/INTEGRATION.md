# Module 4 integration notes

## Shared wiring needed

1. The supplied snapshot does not contain `backend/app/modules/types.py`, although `docs/MODULE_CONVENTIONS.md` requires every module to import `ModuleSpec` from it. The integrator must add the shared `ModuleSpec` definition before importing this package.
2. Import `backend.app.modules.m04_research_scientist.spec`, include its router under the global `/api/v1` prefix, and register its `service_type` in the shared module registry. No shared file was changed in this lane.
3. Literature ingestion should be wired to official or licensed sources only: NCBI E-utilities/PubMed, arXiv API, bioRxiv API/RSS, Crossref, publisher RSS, and user-configured journal RSS. Respect source rate limits, licenses, and robots policies. The lane accepts normalized `PaperInput` objects and performs no scraping itself.
4. Wire an approved sandbox runner later for `ProposedAnalysis`. It must require a granted Human Approval Center request, run in an ephemeral container, default to no network, enforce CPU/memory/time/file limits, use a read-only input mount, and retain logs/artifacts for review. This module intentionally never executes submitted/generated code.
5. Dataset discovery should use official Hugging Face Hub, Kaggle, NCBI, or Zenodo APIs and validate each dataset's license, consent, and intended-use restrictions. Do not add self-bots, unofficial social wrappers, rotating residential proxies, stealth/evasion, or ToS-violating scraping.
6. Manuscript generation and target-journal lookup belong behind Modules 15 and compliant official journal-finder APIs. Publishing/submission must remain separately approval-gated.

## Behavior delivered

- Deterministic offline clustering of normalized papers using transparent Jaccard similarity and connected components.
- BYOK-backed hypothesis drafting through `app.core.providers.generate`, with evidence IDs and explicit scientific/data-use caveats.
- Typed, inert Python/R analysis proposals that reject network-enabled execution and always require approval.

## Approved sandbox execution (builder pb8, 2026-09-24)

Item 4 above is now wired in `approved_sandbox.py` and exposed by `routes.py`:

- `POST /research-scientist/analyses/{approval_id}/execute` runs an approved `execute_sandboxed_analysis` item once. Pending/denied/expired -> 403, other tenant or unknown -> 404, already run or permit consumed -> 409, no isolation backend -> 503.
- `GET /research-scientist/analyses/{approval_id}/execution` and `GET /research-scientist/analyses/executions` read back sealed receipts.
- `GET /research-scientist/analyses/artifacts/{sha256}` downloads a captured log or output file; the hash is re-checked on every read and scoped to the tenant.

Guards: tenant match, Module 4 action type, valid `ProposedAnalysis` payload, approved status, local receipt replay check, Module 0 audit check, then `Service.consume_effect` (one-shot permit bound to the reviewed request hash). Only an `infra_failed` attempt (code never ran) may retry.

Backends (`ATLAS_SANDBOX_BACKEND=auto|docker|bubblewrap`; there is no unsandboxed option):
- Docker: `--network none`, read-only root, `--cap-drop ALL`, no-new-privileges, user 65534, CPU/memory/pids/file-size limits, read-only `/input`. Images via `ATLAS_SANDBOX_PYTHON_IMAGE` / `ATLAS_SANDBOX_R_IMAGE`. Command construction is tested; a live Docker run has not been evidenced yet.
- Bubblewrap: `bwrap --unshare-all` (no network, private user/pid/ipc/uts namespaces), read-only system mounts, cleared environment, address-space/CPU/file-size rlimits, wall-clock kill. Executed for real in `tests/modules/test_m04_approved_sandbox.py` (network-blocked, read-only input, timeout, symlink rejection).

Datasets are downloaded before the run, outside the sandbox: HTTPS only, public addresses only (checked on every redirect), size-capped, SHA-256 recorded, mounted read-only at `/input/data/NN_name`.

Receipts record request hash, code hash, datasets, backend and isolation, limits, exit code, timing, stdout/stderr hashes (capped, truncation flagged), every output file hash, rejected outputs, and a `manifest_sha256` seal (`verify_manifest`). Limits are set with `ATLAS_SANDBOX_<FIELD>` env vars (see `ExecutionLimits`). Storage root: `ATLAS_RUNTIME_DATA_DIR/m04-sandbox` (SQLite + content-addressed files).

Not done: running as a Celery job for long analyses (the route runs synchronously in the API worker thread pool), R execution tested only when Rscript is installed, CI runs the bubblewrap tests only where user namespaces are permitted (they skip otherwise).

### Environment lock and executed bundle (pb8)

Before the permit is consumed, `capture_environment_lock` runs a probe in the same backend, limits and image the analysis will use and records interpreter version, implementation, platform, libc, every installed package with its version and (Docker) the local image id. It is hashed (`environment_lock_sha256`) into the receipt. If the probe fails, the run returns 503 and the approval is not consumed. The approved code and staged dataset bytes are kept in the tenant content store.

`GET /research-scientist/analyses/{approval_id}/bundle` returns a schema-2 zip built from a finished receipt: `analysis.py|R`, `environment.lock.json`, `logs/stdout.txt`, `logs/stderr.txt`, `outputs/...`, `data/...` (datasets up to 50 MB total; larger ones are listed by URL + SHA-256), `README.md`, and `manifest.json` listing every file hash, sealed with `manifest_sha256` and carrying the receipt seal and approval id. `execution_bundle.verify_execution_bundle(bytes)` checks it offline. The R lock probe is written but was not executed here (no Rscript on the builder host).

### Re-run and output-hash diff (pb8)

`rerun.py`: `POST /research-scientist/analyses/{approval_id}/reruns` files a Module 0 `rerun_sandboxed_analysis` approval bound to the original run id, receipt seal, code hash and dataset hashes (nothing runs). After approval, `POST /research-scientist/analyses/reruns/{rerun_approval_id}/execute` checks the original is unchanged, captures a fresh environment lock before consuming the one-shot permit, re-executes the stored approved code on the stored dataset bytes (integrity-checked, no re-download), and returns a sealed receipt with `comparison`: verdict `reproduced` (same exit code, every output hash identical) or `diverged`, per-file status, stdout/stderr identity and an environment diff (interpreter/platform fields, packages added/removed/changed). Re-run receipts can be bundled with the same `/bundle` route. A re-run approval cannot be used as an analysis approval and vice versa.

### Scheduled re-run proposals (pb8)

`rerun_schedule.py` + routes: `POST /research-scientist/analyses/rerun-schedules` (scope `analysis` with the original approval id, or `project` with a tag set via `POST /research-scientist/analyses/{approval_id}/projects`; `interval_hours`, `overdue_after_hours`, optional `first_due_at`), `GET` list, `POST .../{id}/pause|resume`, `POST .../tick` (calling tenant only) and `GET .../stats`. Beat task `atlas.m04.propose_due_reruns` (every 900 s, `celery_app.py`) ticks every tenant with active schedules. A tick only files approvals via `RerunService.propose`: it skips an analysis whose last proposal is still pending or approved-but-unexecuted, is idempotent per (schedule, analysis, due slot) and advances past `now` in whole intervals. Stats read live Module 0 status for every filed proposal and flag overdue ones. Storage: `m04-rerun-schedules.sqlite` beside the sandbox receipts. The M16 dashboard does not yet pull this card (shared file, left for the dashboard owner).
