"""End-to-end, through the REAL booted app routes and the REAL shared Module 0 approval service, in a temp DB and a temp
tools root (ATLAS_TOOLS_ROOT). Dev-mode tenant headers = TEST MODE (production auth not proven). No network, no real install
outside tmp. The artifact is a LABELED FIXTURE zip built in the test."""
import base64
import hashlib
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app

A = {"x-atlas-tenant": "xt-a", "x-atlas-actor": "alice"}
B = {"x-atlas-tenant": "xt-b", "x-atlas-actor": "bob"}
P = "/api/v1/tools-hub/pipeline"
AC = "/api/v1/approval-center/requests"


def _bundle(body=b"print('fixture tool')\n", version="1.0.0"):
    files = {"run.py": body, "README.md": b"# fixture\n"}
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in files.items():
            z.writestr(k, v)
    blob = out.getvalue()
    manifest = {"schema_version": 1, "tool_id": "fixture-tool", "version": version, "entrypoint": "run.py",
                "files": {k: hashlib.sha256(v).hexdigest() for k, v in files.items()},
                "permissions": ["network.read"],
                "provenance": {"source_url": "https://example.test/tool.zip", "publisher": "LABELED FIXTURE",
                               "artifact_sha256": hashlib.sha256(blob).hexdigest()}}
    return blob, manifest


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Proposals/jobs/portfolio use their OWN temp SQLite (the pipeline's default SessionLocal would otherwise write the
    ambient ./atlas.db); approvals use the conftest-isolated Module 0 default service (shared by all tenants, as in prod)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    from app.auth.context import TenantContext, require_tenant
    from fastapi import Depends
    from app.modules.m22_tools_hub import pipeline_routes
    from app.modules.m22_tools_hub.pipeline import InstallPipeline
    eng = create_engine(f"sqlite:///{tmp_path / 'pipeline.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    sessions = sessionmaker(bind=eng, expire_on_commit=False)
    root = tmp_path / "tools"
    cache = {}

    def get_pipeline(tenant: TenantContext = Depends(require_tenant)):
        if tenant.tenant_id not in cache:
            cache[tenant.tenant_id] = InstallPipeline(tenant.tenant_id, root=root, session_factory=sessions)
        return cache[tenant.tenant_id]
    app.dependency_overrides[pipeline_routes.get_pipeline] = get_pipeline
    yield TestClient(app, raise_server_exceptions=False), root
    app.dependency_overrides.pop(pipeline_routes.get_pipeline, None)
    eng.dispose()


def _propose(c, headers, blob, manifest):
    r = c.post(f"{P}/proposals", json={"artifact_base64": base64.b64encode(blob).decode(), "manifest": manifest}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_other_tenant_cannot_see_decide_audit_or_install_with_a_foreign_approval(client):
    c, root = client
    blob, manifest = _bundle()
    prop = _propose(c, A, blob, manifest)
    aid, pid = prop["approval_id"], prop["id"]
    # tenant B: approval invisible/undecidable/unauditable, proposal invisible, cannot enqueue
    assert c.get(f"{AC}/{aid}", headers=B).status_code in (403, 404)
    assert c.post(f"{AC}/{aid}/decision", json={"decision": "approved", "decided_by": "ignored-by-server"}, headers=B).status_code in (403, 404)
    assert c.get(f"{AC}/{aid}/audit", headers=B).status_code in (403, 404)
    assert aid not in [x["id"] for x in c.get(AC, headers=B).json()]
    assert c.get(f"{P}/proposals/{pid}", headers=B).status_code == 404
    assert c.post(f"{P}/proposals/{pid}/install-jobs", headers=B).status_code in (403, 404)
    assert c.get(f"{P}/proposals", headers=B).json() == []
    # and the approval is still undecided after B's attempts
    assert c.get(f"{AC}/{aid}", headers=A).json()["status"] == "pending"
    assert c.post(f"{P}/proposals/{pid}/install-jobs", headers=A).status_code == 403  # A unapproved: refused too


def test_owner_approved_install_verifies_artifact_on_disk_and_stays_invisible_to_other_tenant(client):
    c, root = client
    blob, manifest = _bundle()
    prop = _propose(c, A, blob, manifest)
    assert c.post(f"{AC}/{prop['approval_id']}/decision", json={"decision": "approved", "decided_by": "ignored-by-server"}, headers=A).status_code == 200
    job = c.post(f"{P}/proposals/{prop['id']}/install-jobs", headers=A)
    assert job.status_code == 202, job.text
    jid = job.json()["id"]
    assert c.post(f"{P}/jobs/{jid}/run", headers=B).status_code in (403, 404)  # B cannot run A's job
    ran = c.post(f"{P}/jobs/{jid}/run", headers=A).json()
    assert ran["state"] == "succeeded", ran
    # actual artifact verification on disk, not just a 200: installed files match the manifest hashes
    found = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("run.py") if "tenants" in p.parts}
    assert found and set(found.values()) == {manifest["files"]["run.py"]}
    assert c.get(f"{P}/portfolio", headers=A).json()[0]["tool_id"] == "fixture-tool"
    assert c.get(f"{P}/portfolio", headers=B).json() == []
    assert c.get(f"{P}/jobs/{jid}", headers=B).status_code == 404


def test_tampered_artifact_is_rejected_at_proposal_and_nothing_is_installed(client):
    c, root = client
    blob, manifest = _bundle()
    manifest["files"]["run.py"] = hashlib.sha256(b"something else").hexdigest()  # manifest no longer matches the bytes
    r = c.post(f"{P}/proposals", json={"artifact_base64": base64.b64encode(blob).decode(), "manifest": manifest}, headers=A)
    assert r.status_code >= 400 and r.status_code < 500, r.text
    assert not [p for p in root.rglob("run.py")] if root.exists() else True


def _install(c, headers, blob, manifest):
    prop = _propose(c, headers, blob, manifest)
    assert c.post(f"{AC}/{prop['approval_id']}/decision", json={"decision": "approved", "decided_by": "x"}, headers=headers).status_code == 200
    jid = c.post(f"{P}/proposals/{prop['id']}/install-jobs", headers=headers).json()["id"]
    assert c.post(f"{P}/jobs/{jid}/run", headers=headers).json()["state"] == "succeeded"
    return [e for e in c.get(f"{P}/portfolio", headers=headers).json() if e["version"] == manifest["version"]][0]["operation_id"]


def test_foreign_approved_rollback_approval_cannot_drive_another_tenants_rollback(client):
    c, root = client
    blob, manifest = _bundle()
    blob2, manifest2 = _bundle(body=b"print('v2')\n", version="2.0.0")
    _install(c, A, blob, manifest)
    op_a = _install(c, A, blob2, manifest2)  # a rollback needs a previous version to restore
    _install(c, B, blob, manifest)
    op_b = _install(c, B, blob2, manifest2)
    rb_a = c.post(f"{P}/installs/{op_a}/rollback-proposals", headers=A).json()
    assert c.post(f"{AC}/{rb_a['approval_id']}/decision", json={"decision": "approved", "decided_by": "x"}, headers=A).status_code == 200
    # B tries to use A's APPROVED rollback approval id for B's own operation, and for A's operation
    r1 = c.post(f"{P}/installs/{op_b}/rollback-jobs", json={"approval_id": rb_a["approval_id"]}, headers=B)
    r2 = c.post(f"{P}/installs/{op_a}/rollback-jobs", json={"approval_id": rb_a["approval_id"]}, headers=B)
    assert r1.status_code in (403, 404) and r2.status_code == 404, (r1.text, r2.text)  # foreign op id: 404, never a 500
    assert c.post(f"{P}/installs/{op_a}/rollback-proposals", headers=B).status_code == 404
    assert c.post(f"{P}/installs/nonexistent/rollback-proposals", headers=A).status_code == 404
    assert c.get(f"{P}/jobs", headers=B).json() == [j for j in c.get(f"{P}/jobs", headers=B).json() if j["kind"] != "rollback"]
    # owner can still use it
    assert c.post(f"{P}/installs/{op_a}/rollback-jobs", json={"approval_id": rb_a["approval_id"]}, headers=A).status_code == 202


def test_approved_check_itself_refuses_a_foreign_tenants_approval_even_when_payload_matches(client):
    """Pins the user_id guard in InstallPipeline._approved directly (HTTP tests are also blocked by other layers:
    per-tenant receipts, operation-id binding). A's approved approval with a payload that MATCHES, presented by B."""
    c, root = client
    from app.modules.m22_tools_hub import pipeline_routes
    from app.modules.m22_tools_hub.pipeline import ROLLBACK_ACTION, InstallPipeline
    blob, manifest = _bundle()
    blob2, manifest2 = _bundle(body=b"print('v2')\n", version="2.0.0")
    _install(c, A, blob, manifest)
    op_a = _install(c, A, blob2, manifest2)
    rb = c.post(f"{P}/installs/{op_a}/rollback-proposals", headers=A).json()
    assert c.post(f"{AC}/{rb['approval_id']}/decision", json={"decision": "approved", "decided_by": "x"}, headers=A).status_code == 200
    gen = app.dependency_overrides[pipeline_routes.get_pipeline]
    from app.auth.context import TenantContext
    pa, pb = gen(TenantContext("xt-a", "alice")), gen(TenantContext("xt-b", "bob"))
    from app.modules.m00_approval_center.service import default_service
    payload = default_service().get(rb["approval_id"])["payload"]
    expected = {k: payload[k] for k in ("operation_id", "rollback_subject")}
    assert pa._approved(rb["approval_id"], ROLLBACK_ACTION, expected)["user_id"] == "xt-a"  # owner passes
    with pytest.raises(KeyError):
        pb._approved(rb["approval_id"], ROLLBACK_ACTION, expected)  # same approval + same payload, other tenant
