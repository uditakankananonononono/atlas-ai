"""Reproducible run manifests: canonical JSON, SHA-256 digests, atomic writes.

A manifest pins the run's identity (run_id, workflow, code version, python
version, platform, seed), its config and input hashes, and per-step records.
Writing is atomic (tmp file + os.replace) so a crash never leaves a torn
manifest. Verification recomputes every hash and reports each mismatch.
"""

from __future__ import annotations

import json
import os
import platform as _platform
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .lane_models import RunManifest, StepRecord, canonical_json, sha256_hex

MANIFEST_VERSION = 1


def capture_environment() -> Tuple[str, str]:
    """(python_version, platform) strings for manifests."""
    return (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        _platform.platform(),
    )


def build_manifest(
    run_id: str,
    workflow_name: str,
    config: Dict[str, Any],
    run_input: Any,
    code_version: str = "unknown",
    seed: Optional[int] = None,
    steps: Tuple[StepRecord, ...] = (),
    status: str = "running",
    total_cost_micro: int = 0,
    created_at_utc: Optional[str] = None,
) -> RunManifest:
    py, plat = capture_environment()
    return RunManifest(
        run_id=run_id,
        workflow_name=workflow_name,
        created_at_utc=created_at_utc or datetime.now(timezone.utc).isoformat(),
        code_version=code_version,
        python_version=py,
        platform=plat,
        seed=seed,
        config=dict(config),
        config_hash=sha256_hex(canonical_json(config)),
        input_hash=sha256_hex(canonical_json(run_input)),
        steps=steps,
        status=status,
        total_cost_micro=total_cost_micro,
    )


def manifest_file_payload(manifest: RunManifest) -> Dict[str, Any]:
    return {
        "manifest_version": MANIFEST_VERSION,
        "manifest": manifest.to_dict(),
        "digest": manifest.digest(),
    }


def write_manifest_atomic(path: str | Path, manifest: RunManifest) -> Path:
    """Write manifest JSON atomically. Returns the final path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = manifest_file_payload(manifest)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path


@dataclass(frozen=True)
class ManifestVerification:
    ok: bool
    problems: Tuple[str, ...]
    manifest: Optional[RunManifest]


def read_manifest(path: str | Path) -> RunManifest:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    m = payload["manifest"]
    return RunManifest(
        run_id=m["run_id"],
        workflow_name=m["workflow_name"],
        created_at_utc=m["created_at_utc"],
        code_version=m["code_version"],
        python_version=m["python_version"],
        platform=m["platform"],
        seed=m.get("seed"),
        config=m["config"],
        config_hash=m["config_hash"],
        input_hash=m["input_hash"],
        steps=tuple(StepRecord(**s) for s in m.get("steps", [])),
        status=m.get("status", "running"),
        total_cost_micro=m.get("total_cost_micro", 0),
    )


def verify_manifest(path: str | Path) -> ManifestVerification:
    """Recompute every hash in the manifest file and report mismatches."""
    problems: List[str] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return ManifestVerification(False, (f"unreadable manifest: {exc}",), None)

    if payload.get("manifest_version") != MANIFEST_VERSION:
        problems.append(
            f"unsupported manifest_version: {payload.get('manifest_version')}"
        )
    m = payload.get("manifest")
    if not isinstance(m, dict):
        return ManifestVerification(False, ("missing manifest body",) + tuple(problems), None)

    stored_digest = payload.get("digest")
    try:
        manifest = read_manifest(path)
    except (KeyError, TypeError, ValueError) as exc:
        return ManifestVerification(
            False, tuple(problems) + (f"malformed manifest body: {exc}",), None
        )

    recomputed = manifest.digest()
    if stored_digest != recomputed:
        problems.append(
            f"digest mismatch: stored {stored_digest} != recomputed {recomputed}"
        )
    expected_config_hash = sha256_hex(canonical_json(manifest.config))
    if manifest.config_hash != expected_config_hash:
        problems.append("config_hash does not match embedded config")
    return ManifestVerification(not problems, tuple(problems), manifest)
