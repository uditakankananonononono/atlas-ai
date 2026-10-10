# M14 approval-bound offline Python ready wave

Status: code independently audited and F1/F2 rechecked; documentation confirmation and landing authorization pending. NOT landed. Base: 33e6510a19a685d29d7e3aa266f245f0c21491d9.

## Product contract

Six distinct authenticated routes under `/project-builder`: POST `/projects/{project_id}/sandbox-waves`, POST `/sandbox-waves/{wave_id}/submit`, POST `/sandbox-waves/{wave_id}/execute`, GET `/sandbox-waves/{wave_id}`, GET `/sandbox-waves/{wave_id}/artifacts`, GET `/sandbox-waves/{wave_id}/artifacts/{artifact_id}`. Legacy execution-proposals and approvals cannot execute this unit. Result and artifact reads require the exact creating actor and tenant.

A draft captures the current project revision, entire plan and budget, code and base64 flat-file inputs for every task, declared flat output names (default `result.txt`), backend profile, actual interpreter/environment lock, chosen ready task IDs and reservations. At most one initial ready wave executes, max parallel 1..8; the existing plan ceiling is 500. The plan is never mutated by sandbox execution. Concurrent changes before claim reject the draft; changes during work are recorded as drift, never followed.

Submit always creates a pending M00 `execute_project_sandbox_batch`, TTL one hour, without policy evaluation. Claim requires an explicit approved event, approved status, live expiry, exact request hash, unchanged project/draft/environment and unused approval. A conditional operation claim and M00 effect consumption share the same SQL transaction. Same-effect-ID idempotent allow never permits re-entry. A unique permanent attempted-wave key per project prevents fresh drafts from repeating the initial ready tasks. Review/continuation is a future unit, not implemented here.

A committed claim consumes the zero-USD reservation before dispatch. There are no refunds, automatic retries or resumes. Crash/interruption after claim without saved outcome stays claimed/unknown. A stored sandbox task may be failed or unknown; exit 0 does not prove output quality. Completed dispatch has `awaiting_review`, `all_dag_completed=false` and `independent_quality_verified=false`. Task and artifact receipts are SQL durable, artifacts base64 with verified SHA256; operation payload/digest remains available for review. No external model, package install, network, payment or credit use.

## Mandatory runtime prerequisites and exact limits

Explicit opt-in `ATLAS_M14_SANDBOX_BACKEND=bubblewrap`; explicit existing private absolute nonvolatile `ATLAS_M14_SANDBOX_ROOT`. Reject symlinks and resolved `/tmp`, `/var/tmp`, `/dev/shm`, `/run` roots and descendants, including aliases. No startup root creation or fallback. Deploy one process per root; administrator/root/filesystem trusted. Local disk path validation cannot prove physical mount durability or resist hostile administrators/parent-component swaps.

Before draft and every claim a REAL Python environment-lock probe runs inside this same Bubblewrap/seccomp profile. Binary presence is insufficient. Missing namespaces/interpreter/seccomp fails unavailable BEFORE consumption. No Docker, unsandboxed, mocked or worker-thread fallback for user code. Async orchestration uses host threads to await the sandbox subprocess only.

Deliberate user-code exclusions: **one Python process only; threads and subprocesses unsupported**. Seccomp denies clone, clone3, fork, vfork, unshare, setns, mount, umount2 and ptrace. The configured M04 pids field is not used as evidence of a bound. Here process creation is denied instead. Python interpreter and readonly mounted system files remain in the trusted computing base. Sandbox isolation is not host containment and does not claim protection against kernel exploits.

During execution: readonly root, `/tmp`, system/input/output directory and `/dev`; only at most 20 predeclared flat output files writable. Each file hard-capped 50,000 bytes by RLIMIT_FSIZE, output aggregate <=1,000,000 bytes without dynamic file/tree creation. Logs each hard-capped 50,000 bytes, returned prefix <=16,384 bytes each with truncation flags. Memory address space 64..512 MiB, CPU seconds <= configured 1..60s, open descriptors 64, core dumps off; wall timeout kills the sandbox process group. No writable scratch space for user code. Namespaces deny external networking. These are per-task bounds, not a global machine CPU/memory quota.

Admission: code <=50,000 characters each; strict base64 inputs <=100,000 bytes each, <=20 inputs/task; `analysis.py` and backend helper `empty-tmp` are reserved input names refused at draft admission BEFORE claim or consumption, total code+decoded input <=2MB, serialized full draft <=4MB; reservations fit project max calls/runtime. Postexecution validation: regular non-symlink artifacts, fixed output name limits, <=20 files, aggregate <=1MB; digest verification on download. Whole HTTP body parsing, whole-plan JSON construction and database growth across many drafts are NOT globally quota-limited. No retention/aggregate tenant ledger quota is claimed.

Cancellation: cancelling an asyncio await does not stop host-thread work immediately. Sandbox owns process-group timeout; a cancelled caller may leave durable claimed/unknown while a bounded sandbox finishes, never automatically rerun. SQL durable does not claim guaranteed power-loss fsync, backup rollback protection or a nonrewindable external authority. No production migration, deployment, distributed/remote execution, full-DAG completion or 1000-builder acceptance is claimed.

## Reproduction and honest receipts

`PYTHONPATH=$PWD/backend /tmp/atlas-memo3-venv/bin/python -m pytest tests/modules/test_m14*.py -q`

Exact base: 914 PASS in13.64s. Initial candidate: 946 PASS in48.16s with32newcanaries. Historical pre-repair named canaries34PASS23.83s; actual PG claim rollback/CAS and SQLite+PG migration up/down, real production OIDC (dev bypass disabled), restart/replay, bound output/network/read-only/fork/timeouts/process-group gone. Probe-dependent fixtures SKIP explicitly if host namespace capability unavailable; then no execution claim is supported on that host. PG tests require pgserver+psycopg, not an opt-in skip. Current repaired whole receipt appears below.

Initial strict-backend run 2FAIL/22PASS due malformed bindflag ordering; fixed then24PASS, later32PASS and34PASS. Initial HTTP probe1FAIL/26PASS because shared test development bypass was enabled; test explicitly disables bypass, then production OIDC passes. Prior failures remain receipts, not retroactively green.

Named source mutations: each selected original test1PASS; each mutated test1FAIL: skip-live-expiry, skip-project-revision, skip-draft-digest, skip-human-review, skip-environment-lock, permit-outside-transaction, skip-permanent-project-key, skip-owner, skip-namespace-probe. Permit-outside-transaction killed by SQLite transaction/lock failure, not proof of another database's exact failure mode. Permanent-key mutation killed by uniqueness/failure shape. Independent auditor must reproduce and inspect adjacent bypasses; these kills are scoped test evidence, not formal security proof.

Historical pre-repair candidate whole M14: **948 PASS**, one pgserver runtime-dir warning,46.41s. Compared with exactbase914PASS:34newcanaries. Final real timeout test records spawned process PID and verifies its process group no longer exists after timeout; output/read-only-root/dev-shm/fork bounds canary runs real too.


Current verified F1/F2 repaired candidate81662bcac0db9ae2c2df2580f55d63c7586f9562: **36 canaries PASS25.10s / 950 whole M14 PASS49.16s**, one pgserver runtime-dir warning, no FAIL/SKIP. Exactbase914PASS unchanged. Independent auditor reproduced original34/948 and killed9supplied+3additional mutations; then cleared boundedF1/F2 repair. F1 rejects resolved `/run` descendants (private0700 does not make a conventional volatile path durable). F2 reserves `empty-tmp` at input admission, tested with ZERO operation/approval/effect rows on refusal. Physical mount durability remains unproven. Documentation confirmation/parent landing authorization pending: no public/deployed/landed claim.
