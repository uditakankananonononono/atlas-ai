from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m22_tools_hub import (
    ApprovalError, ApprovalStore, ArtifactRejected, InstallError, ManifestError,
    ReviewDecision, ReviewRecord, SecurityScanner, ToolInstaller, ToolManifest,
    _install_subject, _rollback_subject,
)


def artifact(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, data in files.items():
            archive.writestr(path, data)
    return output.getvalue()


def manifest_for(blob: bytes, files: dict[str, bytes], *, version="1.0.0") -> ToolManifest:
    return ToolManifest.from_dict({
        "schema_version": 1, "tool_id": "safe-tool", "version": version,
        "entrypoint": "run.py",
        "files": {path: hashlib.sha256(data).hexdigest() for path, data in files.items()},
        "permissions": ["network.read"],
        "provenance": {"source_url": "https://example.test/tool.zip", "publisher": "Example",
                       "artifact_sha256": hashlib.sha256(blob).hexdigest()},
    })


def review_for(manifest: ToolManifest) -> ReviewRecord:
    return ReviewRecord("security-reviewer", ReviewDecision.PASS,
                        manifest.provenance.artifact_sha256, manifest.digest)


def test_manifest_rejects_traversal_and_unknown_fields():
    files = {"../run.py": b"print('x')"}
    blob = artifact(files)
    with pytest.raises(ManifestError, match="unsafe path"):
        manifest_for(blob, files)
    good_files = {"run.py": b"print('x')"}
    good_blob = artifact(good_files)
    raw = {
        "schema_version": 1, "tool_id": "x", "version": "1.0.0", "entrypoint": "run.py",
        "files": {"run.py": hashlib.sha256(good_files["run.py"]).hexdigest()},
        "permissions": [], "provenance": {"source_url": "https://x.test/x.zip", "publisher": "x",
        "artifact_sha256": hashlib.sha256(good_blob).hexdigest()}, "surprise": True,
    }
    with pytest.raises(ManifestError, match="unknown manifest fields"):
        ToolManifest.from_dict(raw)


def test_scanner_binds_artifact_and_detects_dangerous_code():
    files = {"run.py": b"import os\nos.system('whoami')\n"}
    blob = artifact(files)
    manifest = manifest_for(blob, files)
    report = SecurityScanner().scan(blob, manifest)
    assert not report.passed
    assert {item.code for item in report.findings} == {"shell-process"}
    with pytest.raises(ArtifactRejected, match="digest"):
        SecurityScanner().scan(blob + b"tampered", manifest)


def test_approval_is_separated_bound_single_use_and_expiring(tmp_path):
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    clock = lambda: now
    store = ApprovalStore(tmp_path / "approvals.json", clock=clock)
    with pytest.raises(ApprovalError, match="separation"):
        store.issue(action="tool.install", subject_digest="x", approved_by="alice", requested_by="alice")
    grant = store.issue(action="tool.install", subject_digest="subject", approved_by="bob",
                        requested_by="alice", ttl=timedelta(minutes=5))
    with pytest.raises(ApprovalError, match="subject mismatch"):
        store.consume(token=grant.token, action="tool.install", subject_digest="other", actor="alice")
    store.consume(token=grant.token, action="tool.install", subject_digest="subject", actor="alice")
    with pytest.raises(ApprovalError, match="consumed"):
        store.consume(token=grant.token, action="tool.install", subject_digest="subject", actor="alice")
    expired = store.issue(action="tool.install", subject_digest="later", approved_by="bob",
                          requested_by="alice", ttl=timedelta(microseconds=1))
    now = now + timedelta(seconds=1)
    with pytest.raises(ApprovalError, match="expired"):
        store.consume(token=expired.token, action="tool.install", subject_digest="later", actor="alice")


def test_install_requires_review_and_approval_then_rolls_back(tmp_path):
    approvals = ApprovalStore(tmp_path / "approval-state.json")
    installer = ToolInstaller(tmp_path / "hub", approvals)
    files_v1 = {"run.py": b"print('v1')\n", "data.txt": b"one"}
    blob_v1 = artifact(files_v1)
    manifest_v1 = manifest_for(blob_v1, files_v1)
    with pytest.raises(ApprovalError):
        installer.install(artifact=blob_v1, manifest=manifest_v1, review=review_for(manifest_v1),
                          approval_token="none", actor="builder")
    approval_v1 = approvals.issue(action="tool.install", subject_digest=_install_subject(manifest_v1),
                                  approved_by="reviewer", requested_by="builder")
    first = installer.install(artifact=blob_v1, manifest=manifest_v1, review=review_for(manifest_v1),
                              approval_token=approval_v1.token, actor="builder")
    assert (tmp_path / "hub/tools/safe-tool/run.py").read_bytes() == files_v1["run.py"]
    files_v2 = {"run.py": b"print('v2')\n", "data.txt": b"two"}
    blob_v2 = artifact(files_v2)
    manifest_v2 = manifest_for(blob_v2, files_v2, version="2.0.0")
    approval_v2 = approvals.issue(action="tool.install", subject_digest=_install_subject(manifest_v2),
                                  approved_by="reviewer", requested_by="builder")
    second = installer.install(artifact=blob_v2, manifest=manifest_v2, review=review_for(manifest_v2),
                               approval_token=approval_v2.token, actor="builder")
    assert second.backup_id
    assert (tmp_path / "hub/tools/safe-tool/run.py").read_bytes() == files_v2["run.py"]
    rollback_approval = approvals.issue(action="tool.rollback", subject_digest=_rollback_subject(second),
                                        approved_by="reviewer", requested_by="builder")
    installer.rollback(operation_id=second.operation_id, approval_token=rollback_approval.token, actor="builder")
    assert (tmp_path / "hub/tools/safe-tool/run.py").read_bytes() == files_v1["run.py"]
    assert first.backup_id is None


def test_install_rejects_review_for_different_manifest(tmp_path):
    approvals = ApprovalStore()
    installer = ToolInstaller(tmp_path, approvals)
    files = {"run.py": b"print('safe')\n"}
    blob = artifact(files)
    manifest = manifest_for(blob, files)
    bad_review = ReviewRecord("reviewer", ReviewDecision.PASS, manifest.provenance.artifact_sha256, "0" * 64)
    grant = approvals.issue(action="tool.install", subject_digest=_install_subject(manifest),
                            approved_by="reviewer", requested_by="builder")
    with pytest.raises(InstallError, match="does not bind"):
        installer.install(artifact=blob, manifest=manifest, review=bad_review,
                          approval_token=grant.token, actor="builder")


def test_persisted_approval_state_never_contains_bearer_token(tmp_path):
    path = tmp_path / "approvals.json"
    store = ApprovalStore(path)
    grant = store.issue(action="tool.install", subject_digest="subject", approved_by="reviewer",
                        requested_by="builder")
    assert grant.token not in path.read_text(encoding="utf-8")
    reloaded = ApprovalStore(path)
    reloaded.consume(token=grant.token, action="tool.install", subject_digest="subject", actor="builder")
