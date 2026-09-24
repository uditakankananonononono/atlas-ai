"""Approval-gated re-run of a finished sandbox analysis, with an output-hash diff.

A re-run executes code again, so it is its own Module 0 action
(``rerun_sandboxed_analysis``) bound to the original run: original approval
id, code hash, dataset hashes and the original receipt seal. Once approved it
re-executes the *stored* approved code against the *stored* dataset bytes
(hash-checked, no re-download, so drift in upstream data cannot masquerade
as non-reproducibility), captures a fresh environment lock in the same kind
of sandbox, and diffs everything against the original receipt:

* each output file: identical / changed / missing / new;
* stdout and stderr hashes, exit code, timeout;
* environment: interpreter and platform changes, packages added / removed /
  changed version, image id.

Verdict: ``reproduced`` when the exit code and every output hash match,
``diverged`` otherwise; environment drift is reported alongside either way.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from .approved_sandbox import (
    BLOCKING_STATES, ENTRYPOINTS, MODULE_ID, ApprovedSandboxExecutor, BackendUnavailableError,
    ExecutionConflictError, ExecutionForbiddenError, ExecutionNotFoundError, SandboxExecutionError,
    _canonical, _now, _sha, capture_environment_lock, hash_outputs, verify_manifest,
)

RERUN_ACTION = "rerun_sandboxed_analysis"
FINISHED = ("succeeded", "exited_nonzero", "timed_out")


def diff_outputs(original: list[dict[str, Any]], rerun: list[dict[str, Any]]) -> list[dict[str, Any]]:
    before = {o["path"]: o for o in original}
    after = {o["path"]: o for o in rerun}
    rows = []
    for path in sorted(before.keys() | after.keys()):
        a, b = before.get(path), after.get(path)
        status = "missing" if b is None else "new" if a is None else \
                 "identical" if a["sha256"] == b["sha256"] else "changed"
        rows.append({"path": path, "status": status,
                     "original_sha256": a and a["sha256"], "rerun_sha256": b and b["sha256"],
                     "original_bytes": a and a["bytes"], "rerun_bytes": b and b["bytes"]})
    return rows


def diff_environment(original: dict[str, Any], rerun: dict[str, Any]) -> dict[str, Any]:
    fields = {}
    for key in ("language", "implementation", "version", "platform", "machine", "libc", "backend", "image_digest"):
        if original.get(key) != rerun.get(key):
            fields[key] = {"original": original.get(key), "rerun": rerun.get(key)}
    a, b = original.get("packages", {}), rerun.get("packages", {})
    changed = {n: {"original": a[n], "rerun": b[n]} for n in sorted(a.keys() & b.keys()) if a[n] != b[n]}
    return {"identical": original.get("lock_sha256") == rerun.get("lock_sha256"),
            "fields": fields, "packages_added": {n: b[n] for n in sorted(b.keys() - a.keys())},
            "packages_removed": {n: a[n] for n in sorted(a.keys() - b.keys())}, "packages_changed": changed}


class RerunService:
    def __init__(self, executor: ApprovedSandboxExecutor) -> None:
        self.ex = executor

    def _original(self, approval_id: str) -> dict[str, Any]:
        receipt = self.ex.store.latest(self.ex.tenant_id, approval_id)
        if receipt is None:
            raise ExecutionNotFoundError(approval_id)
        if receipt["state"] not in FINISHED:
            raise ExecutionConflictError(f"original run is {receipt['state']}; only finished runs can be re-run")
        if not verify_manifest(receipt) or "environment_lock" not in receipt:
            raise ExecutionConflictError("original receipt is unsealed or has no environment lock")
        return receipt

    def propose(self, original_approval_id: str, reason: str = "") -> dict[str, Any]:
        original = self._original(original_approval_id)
        payload = {"original_approval_id": original_approval_id, "original_run_id": original["run_id"],
                   "original_receipt_manifest_sha256": original["manifest_sha256"],
                   "code_sha256": original["code_sha256"], "language": original["language"],
                   "objective": original["objective"],
                   "dataset_sha256": [d["sha256"] for d in original.get("datasets", [])],
                   "sandbox_policy": "ephemeral-no-network", "reason": reason[:1000]}
        view = self.ex.center.submit(module_id=MODULE_ID, action_type=RERUN_ACTION, payload=payload,
                                     user_id=self.ex.tenant_id)
        return {"approval_id": view["id"], "status": getattr(view["status"], "value", view["status"]),
                "action_type": RERUN_ACTION, "payload": payload}

    def execute(self, rerun_approval_id: str) -> dict[str, Any]:
        ex = self.ex
        try:
            view = ex.center.get(rerun_approval_id)
        except KeyError as exc:
            raise ExecutionNotFoundError(rerun_approval_id) from exc
        if view.get("user_id") != ex.tenant_id:
            raise ExecutionNotFoundError(rerun_approval_id)
        if view.get("module_id") != MODULE_ID or view.get("action_type") != RERUN_ACTION:
            raise ExecutionForbiddenError("approval is not a Module 4 re-run")
        status = getattr(view.get("status"), "value", view.get("status"))
        if status != "approved":
            raise ExecutionForbiddenError(f"approval is {status}, not approved")
        payload = dict(view["payload"])
        original = self._original(payload["original_approval_id"])
        if original["manifest_sha256"] != payload["original_receipt_manifest_sha256"] or \
           original["code_sha256"] != payload["code_sha256"]:
            raise ExecutionForbiddenError("original run changed since the re-run was approved")
        prior = ex.store.latest(ex.tenant_id, rerun_approval_id)
        if prior and prior["state"] in BLOCKING_STATES:
            raise ExecutionConflictError(f"re-run already has a {prior['state']} run")
        consumed = any(e.get("event") == "effect_consumed" for e in ex.center.audit(rerun_approval_id))
        if consumed and not (prior and prior["state"] == "infra_failed"):
            raise ExecutionConflictError("re-run permit was already consumed")
        backend = ex.backend
        language = original["language"]
        if not backend.available(language):
            raise BackendUnavailableError(f"{backend.name} cannot run {language} on this host")
        code = ex.store.read_artifact(ex.tenant_id, original["code_sha256"])  # integrity-checked
        datasets = [(d, ex.store.read_artifact(ex.tenant_id, d["sha256"])) for d in original.get("datasets", [])]
        try:
            lock = capture_environment_lock(backend, language, ex.limits)
        except SandboxExecutionError as exc:
            raise BackendUnavailableError(str(exc)) from exc
        try:
            ex.center.consume_effect(rerun_approval_id, module_id=MODULE_ID, action_type=RERUN_ACTION,
                                     payload=payload, user_id=ex.tenant_id,
                                     effect_id=f"m04-rerun:{rerun_approval_id}", actor=ex.actor_id)
        except Exception as exc:
            if type(exc).__name__ == "ApprovalConflictError":
                raise ExecutionConflictError(str(exc)) from exc
            raise
        run_id = str(uuid4())
        receipt: dict[str, Any] = {
            "receipt_id": run_id, "run_id": run_id, "kind": "rerun", "approval_id": rerun_approval_id,
            "original_approval_id": original["approval_id"], "original_run_id": original["run_id"],
            "tenant_id": ex.tenant_id, "actor_id": ex.actor_id, "state": "started",
            "objective": original["objective"], "language": language,
            "request_hash": _sha(_canonical({"module_id": MODULE_ID, "action_type": RERUN_ACTION,
                                             "payload": payload, "user_id": ex.tenant_id}).encode()),
            "code_sha256": original["code_sha256"], "backend": backend.name, "limits": asdict(ex.limits),
            "datasets": original.get("datasets", []), "environment_lock": lock,
            "environment_lock_sha256": lock["lock_sha256"], "created_at": _now()}
        ex.store.record(ex.tenant_id, receipt)
        work = Path(tempfile.mkdtemp(prefix="atlas-m04-rerun-"))
        try:
            input_dir, output_dir = work / "input", work / "output"
            (input_dir / "data").mkdir(parents=True); output_dir.mkdir()
            (input_dir / ENTRYPOINTS[language]).write_bytes(code)
            for meta, data in datasets:
                (input_dir / "data" / meta["path"].rsplit("/", 1)[-1]).write_bytes(data)
            os.chmod(input_dir, 0o755)
            try:
                run = backend.run(language=language, input_dir=input_dir, output_dir=output_dir, limits=ex.limits)
            except Exception as exc:
                return ex._finish(receipt, "infra_failed", error=f"{type(exc).__name__}: {exc}")
            outputs, rejected = hash_outputs(output_dir, ex.limits)
            for item in outputs:
                ex.store.put_file(ex.tenant_id, output_dir / item["path"], item["sha256"], item["bytes"])
            stdout_sha = ex.store.put_bytes(ex.tenant_id, run.stdout)
            stderr_sha = ex.store.put_bytes(ex.tenant_id, run.stderr)
            files = diff_outputs(original.get("outputs", []), outputs)
            reproduced = (not run.timed_out and run.exit_code == original.get("exit_code")
                          and all(r["status"] == "identical" for r in files))
            receipt.update({
                "isolation": run.isolation, "exit_code": run.exit_code, "timed_out": run.timed_out,
                "started_at": run.started_at, "finished_at": run.finished_at,
                "duration_seconds": run.duration_seconds,
                "stdout": {"sha256": stdout_sha, "bytes": len(run.stdout), "truncated": run.stdout_truncated},
                "stderr": {"sha256": stderr_sha, "bytes": len(run.stderr), "truncated": run.stderr_truncated},
                "outputs": outputs, "rejected_outputs": rejected,
                "comparison": {
                    "verdict": "reproduced" if reproduced else "diverged",
                    "exit_code": {"original": original.get("exit_code"), "rerun": run.exit_code},
                    "timed_out": {"original": original.get("timed_out"), "rerun": run.timed_out},
                    "stdout_identical": stdout_sha == original["stdout"]["sha256"],
                    "stderr_identical": stderr_sha == original["stderr"]["sha256"],
                    "outputs": files,
                    "summary": {s: sum(1 for r in files if r["status"] == s)
                                for s in ("identical", "changed", "missing", "new")},
                    "environment": diff_environment(original["environment_lock"], lock)}})
            state = "timed_out" if run.timed_out else ("succeeded" if run.exit_code == 0 else "exited_nonzero")
            return ex._finish(receipt, state)
        finally:
            shutil.rmtree(work, ignore_errors=True)
