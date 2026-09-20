from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .approvals import ApprovalStore
from .models import InstallReceipt, ReviewDecision, ReviewRecord, ToolManifest
from .security import ArtifactRejected, SecurityScanner


class InstallError(RuntimeError):
    pass


class ToolInstaller:
    """Approval-gated atomic installer with per-install backup and rollback."""

    def __init__(self, root: Path, approvals: ApprovalStore, scanner: SecurityScanner | None = None):
        self.root = root.resolve()
        self.approvals = approvals
        self.scanner = scanner or SecurityScanner()
        self._lock = threading.RLock()
        self.tools_dir = self.root / "tools"
        self.backups_dir = self.root / "backups"
        self.receipts_dir = self.root / "receipts"
        for path in (self.tools_dir, self.backups_dir, self.receipts_dir):
            path.mkdir(parents=True, exist_ok=True)

    def install(
        self, *, artifact: bytes, manifest: ToolManifest, review: ReviewRecord,
        approval_token: str, actor: str,
    ) -> InstallReceipt:
        report = self.scanner.scan(artifact, manifest)
        if not report.passed:
            raise InstallError("security scan did not pass")
        if review.decision is not ReviewDecision.PASS:
            raise InstallError("review decision is not pass")
        if review.artifact_sha256 != report.artifact_sha256 or review.manifest_digest != manifest.digest:
            raise InstallError("review does not bind this artifact and manifest")
        subject = _install_subject(manifest)
        self.approvals.consume(token=approval_token, action="tool.install", subject_digest=subject, actor=actor)
        operation_id = uuid.uuid4().hex
        target = self.tools_dir / manifest.tool_id
        backup_id: str | None = None
        with self._lock:
            staging = Path(tempfile.mkdtemp(prefix=f".{manifest.tool_id}-", dir=self.tools_dir))
            try:
                self._extract_verified(artifact, manifest, staging)
                if target.exists():
                    backup_id = operation_id
                    shutil.move(str(target), str(self.backups_dir / backup_id))
                try:
                    os.replace(staging, target)
                except Exception:
                    if backup_id and (self.backups_dir / backup_id).exists():
                        shutil.move(str(self.backups_dir / backup_id), str(target))
                    raise
                receipt = InstallReceipt(
                    operation_id=operation_id, tool_id=manifest.tool_id, version=manifest.version,
                    artifact_sha256=report.artifact_sha256, manifest_digest=manifest.digest,
                    installed_path=str(target), backup_id=backup_id, installed_at=datetime.now(timezone.utc),
                )
                self._write_receipt(receipt)
                return receipt
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                raise

    def rollback(self, *, operation_id: str, approval_token: str, actor: str) -> InstallReceipt:
        receipt = self.get_receipt(operation_id)
        if not receipt.backup_id:
            raise InstallError("install has no prior version to restore")
        subject = _rollback_subject(receipt)
        self.approvals.consume(token=approval_token, action="tool.rollback", subject_digest=subject, actor=actor)
        target = Path(receipt.installed_path)
        backup = self.backups_dir / receipt.backup_id
        if not backup.exists():
            raise InstallError("rollback backup is missing")
        with self._lock:
            failed = self.backups_dir / f"failed-{uuid.uuid4().hex}"
            if target.exists():
                shutil.move(str(target), str(failed))
            try:
                shutil.move(str(backup), str(target))
            except Exception:
                if failed.exists():
                    shutil.move(str(failed), str(target))
                raise
            shutil.rmtree(failed, ignore_errors=True)
        return receipt

    def get_receipt(self, operation_id: str) -> InstallReceipt:
        path = self.receipts_dir / f"{operation_id}.json"
        if not path.exists():
            raise InstallError("receipt not found")
        value = json.loads(path.read_text(encoding="utf-8"))
        return InstallReceipt(
            operation_id=value["operation_id"], tool_id=value["tool_id"], version=value["version"],
            artifact_sha256=value["artifact_sha256"], manifest_digest=value["manifest_digest"],
            installed_path=value["installed_path"], backup_id=value.get("backup_id"),
            installed_at=datetime.fromisoformat(value["installed_at"]),
        )

    @staticmethod
    def _extract_verified(artifact: bytes, manifest: ToolManifest, staging: Path) -> None:
        archive_path = staging / ".artifact.zip"
        archive_path.write_bytes(artifact)
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                destination = staging / info.filename
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)
                destination.chmod(0o755 if info.filename == manifest.entrypoint else 0o644)
        archive_path.unlink()
        (staging / ".atlas-install.json").write_text(json.dumps({
            "tool_id": manifest.tool_id, "version": manifest.version,
            "manifest_digest": manifest.digest,
        }, sort_keys=True), encoding="utf-8")

    def _write_receipt(self, receipt: InstallReceipt) -> None:
        path = self.receipts_dir / f"{receipt.operation_id}.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps({
            "operation_id": receipt.operation_id, "tool_id": receipt.tool_id,
            "version": receipt.version, "artifact_sha256": receipt.artifact_sha256,
            "manifest_digest": receipt.manifest_digest, "installed_path": receipt.installed_path,
            "backup_id": receipt.backup_id, "installed_at": receipt.installed_at.isoformat(),
        }, sort_keys=True), encoding="utf-8")
        temp.replace(path)


def _install_subject(manifest: ToolManifest) -> str:
    return f"{manifest.tool_id}:{manifest.version}:{manifest.provenance.artifact_sha256}:{manifest.digest}"


def _rollback_subject(receipt: InstallReceipt) -> str:
    return f"{receipt.operation_id}:{receipt.tool_id}:{receipt.artifact_sha256}"
