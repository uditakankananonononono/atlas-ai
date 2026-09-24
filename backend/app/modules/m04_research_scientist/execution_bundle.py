"""Executed reproducibility bundle: one zip proving code, inputs, environment, logs and outputs.

Extends the unexecuted bundle in ``reproducibility_bundle.py`` (schema 1,
"No execution is claimed") with schema 2, built only from a finished
approved-sandbox receipt. Every file in the zip is listed in
``manifest.json`` with its SHA-256; the manifest is sealed with
``manifest_sha256`` and carries the receipt's own seal, so the bundle can be
checked offline with ``verify_execution_bundle`` and traced back to the
Module 0 approval that authorised the run.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from typing import Any

from .approved_sandbox import ENTRYPOINTS, ExecutionReceiptStore, verify_manifest

FINISHED_STATES = ("succeeded", "exited_nonzero", "timed_out")
DEFAULT_MAX_DATASET_BYTES = 50 * 1024 * 1024


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_execution_bundle(receipt: dict[str, Any], store: ExecutionReceiptStore, tenant_id: str,
                           max_dataset_bytes: int = DEFAULT_MAX_DATASET_BYTES) -> tuple[bytes, dict[str, Any]]:
    if receipt.get("state") not in FINISHED_STATES:
        raise ValueError(f"only finished runs can be bundled (state is {receipt.get('state')})")
    if not verify_manifest(receipt):
        raise ValueError("execution receipt failed its seal check")
    files: dict[str, bytes] = {}
    code = store.read_artifact(tenant_id, receipt["code_sha256"])
    files[ENTRYPOINTS[receipt["language"]]] = code
    lock = receipt["environment_lock"]
    files["environment.lock.json"] = json.dumps(lock, indent=2, sort_keys=True).encode()
    files["logs/stdout.txt"] = store.read_artifact(tenant_id, receipt["stdout"]["sha256"])
    files["logs/stderr.txt"] = store.read_artifact(tenant_id, receipt["stderr"]["sha256"])
    for item in receipt.get("outputs", []):
        files[f"outputs/{item['path']}"] = store.read_artifact(tenant_id, item["sha256"])
    datasets, included = [], 0
    for ds in receipt.get("datasets", []):
        entry = {k: ds[k] for k in ("url", "final_url", "sha256", "bytes", "path") if k in ds}
        name = ds["path"].rsplit("/", 1)[-1]
        if included + int(ds["bytes"]) <= max_dataset_bytes:
            files[f"data/{name}"] = store.read_artifact(tenant_id, ds["sha256"])
            included += int(ds["bytes"])
            entry["bundled_as"] = f"data/{name}"
        else:
            entry["bundled_as"] = None  # too large; fetch from url and check sha256
        datasets.append(entry)
    rerun = ("# Re-run\n\nMount `data/` read-only at `/input/data` and the analysis file at `/input/`, "
             "run with no network, then compare new output hashes with `manifest.json`.\n")
    files["README.md"] = (f"# {receipt['objective']}\n\nExecuted {receipt.get('finished_at')} in the "
                          f"`{receipt['backend']}` sandbox, state `{receipt['state']}`, exit code "
                          f"`{receipt.get('exit_code')}`. Approved by Module 0 approval `{receipt['approval_id']}`.\n\n"
                          f"Environment lock: `{receipt['environment_lock_sha256']}` "
                          f"({len(lock.get('packages', {}))} packages, {lock.get('implementation', lock.get('language'))} "
                          f"{lock.get('version')}).\n\n{rerun}").encode()
    manifest = {
        "schema_version": 2, "executed": True, "objective": receipt["objective"],
        "language": receipt["language"], "approval_id": receipt["approval_id"], "run_id": receipt["run_id"],
        "request_hash": receipt["request_hash"], "code_sha256": receipt["code_sha256"],
        "environment_lock_sha256": receipt["environment_lock_sha256"],
        "execution": {k: receipt.get(k) for k in ("backend", "isolation", "limits", "state", "exit_code",
                                                  "timed_out", "started_at", "finished_at", "duration_seconds")},
        "stdout": receipt["stdout"], "stderr": receipt["stderr"],
        "outputs": receipt.get("outputs", []), "rejected_outputs": receipt.get("rejected_outputs", []),
        "datasets": datasets, "receipt_manifest_sha256": receipt["manifest_sha256"],
        "files": {path: {"sha256": _sha(data), "bytes": len(data)} for path, data in sorted(files.items())},
    }
    manifest["manifest_sha256"] = _sha(_canonical(manifest))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        for path, data in sorted(files.items()):
            zf.writestr(path, data)
    payload = out.getvalue()
    return payload, {**manifest, "bundle_sha256": _sha(payload)}


def verify_execution_bundle(payload: bytes) -> dict[str, Any]:
    """Offline check: seal, every listed file hash, and the output/code/lock cross-links."""
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
        problems = []
        if manifest.get("manifest_sha256") != _sha(_canonical(body)):
            problems.append("manifest seal mismatch")
        names = set(zf.namelist()) - {"manifest.json"}
        listed = set(manifest.get("files", {}))
        if names != listed:
            problems.append(f"unlisted or missing files: {sorted(names ^ listed)}")
        for path in names & listed:
            if _sha(zf.read(path)) != manifest["files"][path]["sha256"]:
                problems.append(f"hash mismatch: {path}")
        for item in manifest.get("outputs", []):
            entry = manifest["files"].get(f"outputs/{item['path']}")
            if not entry or entry["sha256"] != item["sha256"]:
                problems.append(f"output not bundled as recorded: {item['path']}")
        code_entry = manifest["files"].get(ENTRYPOINTS[manifest["language"]], {})
        if code_entry.get("sha256") != manifest.get("code_sha256"):
            problems.append("code hash does not match approved code")
        if "environment.lock.json" in names:
            lock = json.loads(zf.read("environment.lock.json"))
            lock_body = {k: v for k, v in lock.items() if k != "lock_sha256"}
            if lock.get("lock_sha256") != manifest.get("environment_lock_sha256") or \
               lock["lock_sha256"] != _sha(json.dumps(lock_body, sort_keys=True, separators=(",", ":"), default=str).encode()):
                problems.append("environment lock hash mismatch")
    return {"valid": not problems, "problems": problems, "manifest_sha256": manifest.get("manifest_sha256")}
