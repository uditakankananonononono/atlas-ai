"""M15 export through the REAL booted app routes (main.app) and the REAL Module 0 approval routes, temp DB + temp store.
Dev-mode tenant headers = TEST MODE (production auth not proven). Content is a LABELED FIXTURE. Verifies the delivered
ARTIFACT (hash, OOXML content, LibreOffice round-trip to PDF text), not just status codes. No network."""
import hashlib
import io
import shutil
import subprocess
import zipfile

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.context import TenantContext, require_tenant
from app.core.database import Base
from app.main import app
from app.modules.m15_document_generator import routes
from app.modules.m15_document_generator.delivery import ApprovedDeliveryService, DeliveryStore
from app.modules.m15_document_generator.service import Service as Documents
from app.modules.m15_document_generator.sql_repository import SqlVersionRepository

A = {"x-atlas-tenant": "m15-a", "x-atlas-actor": "alice"}
B = {"x-atlas-tenant": "m15-b", "x-atlas-actor": "bob"}
D = "/api/v1/document-generator"
AC = "/api/v1/approval-center/requests"
REPORT = {"title": "LABELED FIXTURE report", "author": "Fixture Author",
          "sections": [{"title": "Method", "body": "Secchi depth ~ 21 m, weekly. Cost $0 and 50% done."},
                       {"title": "Result", "body": "Clarity improved.\n\nSecond paragraph."}]}


@pytest.fixture
def client(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'm15.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    sessions = sessionmaker(bind=eng, expire_on_commit=False)
    store = DeliveryStore(tmp_path / "store", signing_key=b"k" * 32)

    def docs(t: TenantContext = Depends(require_tenant)):
        from app.core.approvals import approvals
        return Documents(approvals, repository=SqlVersionRepository(t.tenant_id, session_factory=sessions))

    def delivery(t: TenantContext = Depends(require_tenant)):
        return ApprovedDeliveryService(t.tenant_id, actor_id=t.actor_id, versions=SqlVersionRepository(t.tenant_id, session_factory=sessions), store=store)
    app.dependency_overrides[routes.get_service] = docs
    app.dependency_overrides[routes.get_delivery_service] = delivery
    yield TestClient(app, raise_server_exceptions=False), tmp_path
    app.dependency_overrides.pop(routes.get_service, None)
    app.dependency_overrides.pop(routes.get_delivery_service, None)
    eng.dispose()


def _flow(c, headers, fmt="docx"):
    v = c.post(f"{D}/documents/m15doc/versions", headers=headers, json={"title": "t", "format": fmt, "template_id": "report", "content": REPORT})
    assert v.status_code == 200, v.text
    version = v.json()
    prop = c.post(f"{D}/versions/{version['id']}/export-proposals", headers=headers)
    assert prop.status_code == 202, prop.text
    return version, prop.json()["approval_id"]


def _approve(c, headers, approval_id):
    return c.post(f"{AC}/{approval_id}/decision", headers=headers, json={"decision": "approved", "decided_by": "ignored"})


def test_docx_export_approve_deliver_download_and_artifact_content(client):
    c, tmp = client
    version, aid = _flow(c, A)
    assert c.post(f"{D}/approvals/{aid}/deliver", headers=A).status_code == 403  # not approved yet
    assert _approve(c, A, aid).status_code == 200
    d = c.post(f"{D}/approvals/{aid}/deliver", headers=A)
    assert d.status_code == 201, d.text
    got = c.get(d.json()["download_url"], headers=A)
    assert got.status_code == 200 and hashlib.sha256(got.content).hexdigest() == d.json()["sha256"]
    with zipfile.ZipFile(io.BytesIO(got.content)) as z:  # real OOXML package with the fixture's content
        assert "word/document.xml" in z.namelist()
        xml = z.read("word/document.xml").decode("utf8")
    for needle in ("LABELED FIXTURE report", "Method", "Secchi depth", "Second paragraph"):
        assert needle in xml, needle
    (tmp / "delivered.docx").write_bytes(got.content)
    if shutil.which("soffice"):  # independent consumer: LibreOffice opens it and produces text
        r = subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(tmp / "delivered.docx")],
                           capture_output=True, text=True, timeout=100, env={"HOME": str(tmp), "PATH": "/usr/bin:/bin"})
        assert (tmp / "delivered.pdf").exists(), r.stderr[:300]
        if shutil.which("pdftotext"):
            text = subprocess.run(["pdftotext", str(tmp / "delivered.pdf"), "-"], capture_output=True, text=True).stdout
            assert "Clarity improved." in text and "LABELED FIXTURE report" in text


def test_other_tenant_cannot_decide_deliver_or_download_and_one_shot_holds(client):
    c, tmp = client
    version, aid = _flow(c, A)
    assert c.post(f"{AC}/{aid}/decision", headers=B, json={"decision": "approved", "decided_by": "x"}).status_code == 404
    assert c.post(f"{D}/approvals/{aid}/deliver", headers=B).status_code in (403, 404)
    assert c.post(f"{D}/versions/{version['id']}/export-proposals", headers=B).status_code == 404
    assert _approve(c, A, aid).status_code == 200
    assert c.post(f"{D}/approvals/{aid}/deliver", headers=B).status_code in (403, 404)  # B still cannot use A's approved approval
    d = c.post(f"{D}/approvals/{aid}/deliver", headers=A)
    assert d.status_code == 201
    assert c.get(d.json()["download_url"], headers=B).status_code in (403, 404)  # token bound to tenant A
    assert c.post(f"{D}/approvals/{aid}/deliver", headers=A).status_code == 409  # one-shot
    assert c.get(f"{D}/deliveries", headers=B).json() == []
