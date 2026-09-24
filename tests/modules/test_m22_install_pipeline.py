"""Durable M22 install pipeline: Module 0 approval -> worker job -> installer receipt."""
from __future__ import annotations

import base64
import hashlib
import io
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service as ApprovalCenter
from app.modules.m22_tools_hub.pipeline import (
    INSTALL_ACTION, ROLLBACK_ACTION, InstallPipeline, PipelineConflict, PipelineError,
    tenants_with_queued_jobs,
)


def zip_of(files: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path, data in files.items():
            z.writestr(path, data)
    return out.getvalue()


def bundle(version="1.0.0", body=b"print('hello from tool')\n", tool_id="safe-tool"):
    files = {"run.py": body, "README.md": b"# tool\n"}
    blob = zip_of(files)
    manifest = {
        "schema_version": 1, "tool_id": tool_id, "version": version, "entrypoint": "run.py",
        "files": {p: hashlib.sha256(d).hexdigest() for p, d in files.items()},
        "permissions": ["network.read"],
        "provenance": {"source_url": "https://example.test/tool.zip", "publisher": "Example",
                       "artifact_sha256": hashlib.sha256(blob).hexdigest()},
    }
    return blob, manifest


@pytest.fixture
def env(tmp_path: Path):
    eng = create_engine(f"sqlite:///{tmp_path/'db.sqlite'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    sessions = sessionmaker(bind=eng, expire_on_commit=False)
    center = ApprovalCenter(session_factory=sessions)

    def make(tenant="tenant-a"):
        return InstallPipeline(tenant, root=tmp_path / "tools", center=center, session_factory=sessions)
    return make, center, sessions, tmp_path


def approve(center, approval_id, who="udita"):
    center.decide(approval_id, ApprovalStatus.APPROVED, decided_by=who)


def test_full_install_writes_own_receipt_and_persists_portfolio(env):
    make, center, sessions, tmp = env
    p = make()
    blob, manifest = bundle()
    prop = p.propose(artifact=blob, manifest=manifest, requested_by="alice",
                     candidate={"name": "safe-tool", "api_token": "leak-me"})
    assert prop["status"] == "awaiting_approval"
    assert "api_token" not in prop["candidate"]
    approval = center.get(prop["approval_id"])
    assert approval["action_type"] == INSTALL_ACTION and approval["module_id"] == 22
    assert approval["payload"]["install_subject"] == prop["install_subject"]
    assert approval["payload"]["artifact_sha256"] == hashlib.sha256(blob).hexdigest()

    with pytest.raises(PermissionError, match="pending"):
        p.enqueue_install(prop["id"])
    approve(center, prop["approval_id"])
    job = p.enqueue_install(prop["id"])
    assert job["state"] == "queued"
    with pytest.raises(PipelineConflict):
        p.enqueue_install(prop["id"])

    done = p.run_job(job["id"])
    assert done["state"] == "succeeded", done["error"]
    receipt = done["receipt"]
    assert receipt["artifact_sha256"] == hashlib.sha256(blob).hexdigest()
    installed = Path(receipt["installed_path"])
    assert (installed / "run.py").read_bytes() == b"print('hello from tool')\n"

    # a fresh pipeline object (new process) sees the same durable state
    again = make()
    assert again.get_proposal(prop["id"])["status"] == "installed"
    port = again.portfolio()
    assert [x["tool_id"] for x in port] == ["safe-tool"]
    assert port[0]["approved_by"] == "udita" and port[0]["operation_id"] == receipt["operation_id"]
    # replay of a finished job does nothing
    assert again.run_job(job["id"])["state"] == "succeeded"
    with pytest.raises(PipelineConflict):
        again.enqueue_install(prop["id"])


def test_denied_or_foreign_approval_never_installs(env):
    make, center, *_ = env
    p = make()
    blob, manifest = bundle()
    prop = p.propose(artifact=blob, manifest=manifest, requested_by="alice")
    center.decide(prop["approval_id"], ApprovalStatus.DENIED, decided_by="udita")
    with pytest.raises(PermissionError, match="denied"):
        p.enqueue_install(prop["id"])
    other = make("tenant-b")
    with pytest.raises(KeyError):
        other.enqueue_install(prop["id"])
    assert p.portfolio() == [] and other.portfolio() == []


def test_scan_failure_blocks_proposal(env):
    make, center, *_ = env
    p = make()
    blob, manifest = bundle()
    manifest["provenance"]["artifact_sha256"] = "0" * 64
    with pytest.raises(PipelineError, match="provenance"):
        p.propose(artifact=blob, manifest=manifest, requested_by="alice")
    assert p.list_proposals() == []
    assert [a for a in center.list(user_id="tenant-a") if a["module_id"] == 22] == []


def test_tampered_stored_artifact_fails_job_and_is_recorded(env):
    make, center, _, tmp = env
    p = make()
    blob, manifest = bundle()
    prop = p.propose(artifact=blob, manifest=manifest, requested_by="alice")
    approve(center, prop["approval_id"])
    job = p.enqueue_install(prop["id"])
    stored = tmp / "tools" / "artifacts" / f"{prop['artifact_sha256']}.zip"
    stored.write_bytes(zip_of({"run.py": b"import os; os.system('rm -rf /')"}))
    result = p.run_job(job["id"])
    assert result["state"] == "failed" and "integrity" in result["error"]
    assert p.get_proposal(prop["id"])["status"] == "failed"
    assert p.portfolio() == []
    # restoring the correct bytes lets the bounded retry succeed
    stored.write_bytes(blob)
    retry = p.enqueue_install(prop["id"])
    assert retry["id"] == job["id"]
    assert p.run_job(job["id"])["state"] == "succeeded"


def test_upgrade_then_approved_rollback_restores_previous_version(env):
    make, center, *_ = env
    p = make()
    for version, body in (("1.0.0", b"print('v1')\n"), ("1.1.0", b"print('v2')\n")):
        blob, manifest = bundle(version, body)
        prop = p.propose(artifact=blob, manifest=manifest, requested_by="alice")
        approve(center, prop["approval_id"])
        job = p.run_job(p.enqueue_install(prop["id"])["id"])
        assert job["state"] == "succeeded", job["error"]
    active = p.portfolio()
    assert len(active) == 1 and active[0]["version"] == "1.1.0" and active[0]["rollback_available"]
    history = p.portfolio(include_history=True)
    assert {x["status"] for x in history} == {"active", "superseded"}

    op = active[0]["operation_id"]
    rb = p.propose_rollback(op, "alice")
    assert center.get(rb["approval_id"])["action_type"] == ROLLBACK_ACTION
    with pytest.raises(PermissionError):
        p.enqueue_rollback(op, rb["approval_id"])
    # an install approval cannot be reused to authorize a rollback
    with pytest.raises(PermissionError, match="different action"):
        p.enqueue_rollback(op, p.list_proposals()[0]["approval_id"])
    approve(center, rb["approval_id"])
    job = p.enqueue_rollback(op, rb["approval_id"])
    assert p.drain()[0]["state"] == "succeeded"
    installed = Path(active[0]["installed_path"])
    assert (installed / "run.py").read_bytes() == b"print('v1')\n"
    now = p.portfolio()
    assert len(now) == 1 and now[0]["version"] == "1.0.0"
    assert p.get_job(job["id"])["receipt"]["rolled_back_at"]


def test_queued_tenant_discovery(env):
    make, center, sessions, _ = env
    p = make("tenant-q")
    blob, manifest = bundle()
    prop = p.propose(artifact=blob, manifest=manifest, requested_by="alice")
    approve(center, prop["approval_id"])
    p.enqueue_install(prop["id"])
    assert "tenant-q" in tenants_with_queued_jobs(sessions)
    p.drain()
    assert "tenant-q" not in tenants_with_queued_jobs(sessions)


def test_http_surface_end_to_end(env, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m22_tools_hub import pipeline_routes

    make, center, *_ = env
    pipelines: dict[str, InstallPipeline] = {}
    app = FastAPI()
    app.include_router(pipeline_routes.router, prefix="/api/v1/tools-hub")
    app.dependency_overrides[pipeline_routes.get_pipeline] = lambda: pipelines.setdefault("t", make("t"))
    client = TestClient(app)
    blob, manifest = bundle()
    r = client.post("/api/v1/tools-hub/pipeline/proposals",
                    json={"artifact_base64": base64.b64encode(blob).decode(), "manifest": manifest},
                    headers={"X-Atlas-Tenant": "t", "X-Atlas-Actor": "alice"})
    assert r.status_code == 201, r.text
    prop = r.json()
    assert client.post(f"/api/v1/tools-hub/pipeline/proposals/{prop['id']}/install-jobs").status_code == 403
    approve(center, prop["approval_id"])
    job = client.post(f"/api/v1/tools-hub/pipeline/proposals/{prop['id']}/install-jobs").json()
    ran = client.post(f"/api/v1/tools-hub/pipeline/jobs/{job['id']}/run").json()
    assert ran["state"] == "succeeded"
    port = client.get("/api/v1/tools-hub/pipeline/portfolio").json()
    assert port[0]["tool_id"] == "safe-tool"
    bad = client.post("/api/v1/tools-hub/pipeline/proposals", json={"artifact_base64": "!!!!", "manifest": manifest})
    assert bad.status_code == 422
    assert client.get("/api/v1/tools-hub/pipeline/jobs/nope").status_code == 404
