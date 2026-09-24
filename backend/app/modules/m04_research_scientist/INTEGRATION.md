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
