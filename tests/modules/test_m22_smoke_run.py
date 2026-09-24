"""M22 sandboxed smoke-run of installed entrypoints (real bubblewrap when available)."""
from __future__ import annotations

import hashlib
import io
import shutil
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service as ApprovalCenter
from app.modules.m22_tools_hub.pipeline import SMOKE_ACTION, InstallPipeline, PipelineError
from app.modules.m22_tools_hub.smoke import BwrapSmokeBackend, SmokeLimits, SmokeRun, select_smoke_backend

HAS_BWRAP = BwrapSmokeBackend().available("python")
needs_bwrap = pytest.mark.skipif(not HAS_BWRAP, reason="bubblewrap not installed")


def tool_bundle(init: bytes, tool_id="demo-tool", version="1.0.0"):
    files = {"demo/__init__.py": init, "demo/extra.txt": b"data\n"}
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for p, d in files.items():
            z.writestr(p, d)
    blob = out.getvalue()
    return blob, {
        "schema_version": 1, "tool_id": tool_id, "version": version, "entrypoint": "demo/__init__.py",
        "files": {p: hashlib.sha256(d).hexdigest() for p, d in files.items()}, "permissions": [],
        "provenance": {"source_url": "https://example.test/demo.zip", "publisher": "Example",
                       "artifact_sha256": hashlib.sha256(blob).hexdigest()}}


class RecordingBackend:
    """Stands in for M4's SandboxBackend to prove the interface is swappable."""
    name = "m4-compatible-fake"

    def __init__(self):
        self.calls = []

    def available(self, language="python"):
        return True

    def run(self, *, language, input_dir, output_dir, limits):
        self.calls.append((language, sorted(p.name for p in input_dir.iterdir())))
        (output_dir / "smoke.json").write_text('{"ok": true, "mode": "import"}')
        return SmokeRun(backend=self.name, isolation={"network": "none"}, exit_code=0, timed_out=False,
                        stdout=b"ATLAS_SMOKE ok\n", stderr=b"")


@pytest.fixture
def env(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'db.sqlite'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    sessions = sessionmaker(bind=eng, expire_on_commit=False)
    center = ApprovalCenter(session_factory=sessions)

    def make(**kw):
        return InstallPipeline("tenant-a", root=tmp_path / "tools", center=center, session_factory=sessions, **kw)
    return make, center


def install(p, center, init: bytes, version="1.0.0"):
    blob, manifest = tool_bundle(init, version=version)
    prop = p.propose(artifact=blob, manifest=manifest, requested_by="alice")
    center.decide(prop["approval_id"], ApprovalStatus.APPROVED, decided_by="udita")
    job = p.run_job(p.enqueue_install(prop["id"])["id"])
    assert job["state"] == "succeeded", job["error"]
    return p.portfolio()[0]


def smoke(p, center, op):
    req = p.propose_smoke(op, "alice")
    assert center.get(req["approval_id"])["action_type"] == SMOKE_ACTION
    with pytest.raises(PermissionError):
        p.enqueue_smoke(op, req["approval_id"])
    center.decide(req["approval_id"], ApprovalStatus.APPROVED, decided_by="udita")
    return p.run_job(p.enqueue_smoke(op, req["approval_id"])["id"])


def test_swappable_backend_receives_harness_and_tool(env):
    make, center = env
    backend = RecordingBackend()
    p = make(smoke_backend=backend)
    entry = install(p, center, b"VALUE = 1\n")
    assert "not yet shown to load" in entry["execution_claim"]
    job = smoke(p, center, entry["operation_id"])
    assert job["state"] == "succeeded"
    language, names = backend.calls[0]
    assert language == "python" and {"analysis.py", "smoke_main.py", "tool"} <= set(names)
    after = p.portfolio()[0]
    assert after["smoke"]["passed"] and after["smoke"]["backend"] == "m4-compatible-fake"
    assert "loaded in an isolated no-network smoke-run" in after["execution_claim"]


@needs_bwrap
def test_real_sandbox_imports_tool(env):
    make, center = env
    p = make()
    entry = install(p, center, b"__version__ = '1.0.0'\ndef hello():\n    return 'hi'\n")
    job = smoke(p, center, entry["operation_id"])
    assert job["state"] == "succeeded", job["receipt"]
    result = job["receipt"]["result"]
    assert result["module"] == "demo" and result["version"] == "1.0.0" and "hello" in result["public_names"]
    assert job["receipt"]["isolation"]["network"].startswith("none")


@needs_bwrap
def test_real_sandbox_has_no_network_and_no_host_writes(env, tmp_path):
    make, center = env
    p = make()
    probe = tmp_path / "escaped.txt"
    init = (b"import socket\n"
            b"try:\n    open(%r, 'w').write('x')\nexcept OSError:\n    pass\n"
            b"socket.create_connection(('1.1.1.1', 53), timeout=3)\n" % str(probe).encode())
    entry = install(p, center, init)
    job = smoke(p, center, entry["operation_id"])
    assert job["state"] == "failed"
    assert "OSError" in job["receipt"]["result"]["error"] or "gaierror" in job["receipt"]["result"]["error"]
    assert not probe.exists()
    assert p.portfolio()[0]["smoke"]["passed"] is False


@needs_bwrap
def test_real_sandbox_timeout_is_enforced(env):
    make, center = env
    p = make(smoke_limits=SmokeLimits(timeout_seconds=2))
    entry = install(p, center, b"while True:\n    pass\n")
    job = smoke(p, center, entry["operation_id"])
    assert job["state"] == "failed" and job["receipt"]["timed_out"] is True


def test_smoke_requires_active_install_and_matching_approval(env):
    make, center = env
    p = make(smoke_backend=RecordingBackend())
    first = install(p, center, b"A = 1\n")
    install(p, center, b"A = 2\n", version="1.1.0")
    with pytest.raises(PipelineError, match="superseded"):
        p.propose_smoke(first["operation_id"], "alice")
    with pytest.raises(KeyError):
        p.propose_smoke("nope", "alice")
    active = p.portfolio()[0]
    # an install approval cannot authorize a smoke-run
    install_approval = p.list_proposals()[0]["approval_id"]
    with pytest.raises(PermissionError, match="different action"):
        p.enqueue_smoke(active["operation_id"], install_approval)


def test_backend_selection_falls_back_to_bundled(monkeypatch):
    monkeypatch.setenv("ATLAS_SMOKE_BACKEND", "bundled")
    if HAS_BWRAP:
        assert select_smoke_backend("python").name == "bubblewrap-smoke"
    if shutil.which("node") and HAS_BWRAP:
        assert select_smoke_backend("node").name == "bubblewrap-smoke"
