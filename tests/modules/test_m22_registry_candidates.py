"""M22 persisted discovery candidates -> registry fetch (digest-checked) -> pipeline proposal."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service as ApprovalCenter
from app.modules.m22_tools_hub.pipeline import InstallPipeline, PipelineError
from app.modules.m22_tools_hub.registry import (
    RegistryError, build_manifest, fetch_npm, fetch_pypi, http_fetch, manifest_version, registry_for_candidate,
)
from app.modules.m22_tools_hub.service import Service as DiscoveryService


def wheel() -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("tinytool/__init__.py", "def hello():\n    return 'hi'\n")
        z.writestr("tinytool-2.1.dist-info/METADATA", "Name: tinytool\nVersion: 2.1\n")
    return out.getvalue()


def tarball(files: dict[str, bytes], link: bool = False) -> bytes:
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(f"package/{name}"); info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        if link:
            info = tarfile.TarInfo("package/evil"); info.type = tarfile.SYMTYPE; info.linkname = "/etc/passwd"
            tar.addfile(info)
    return out.getvalue()


class FakeRegistry:
    """Serves responses shaped like pypi.org JSON API and registry.npmjs.org."""

    def __init__(self):
        self.whl = wheel()
        self.tgz = tarball({"package.json": b'{"name":"left-pad","main":"index.js"}', "index.js": b"module.exports=function(s){return s}\n"})
        self.calls: list[str] = []
        self.corrupt = False

    def __call__(self, url: str, limit: int) -> bytes:
        self.calls.append(url)
        if url == "https://pypi.org/pypi/tinytool/json":
            return json.dumps({"info": {"version": "2.1", "license": "MIT", "summary": "tiny"}, "urls": [
                {"packagetype": "sdist", "url": "https://files.pythonhosted.org/x/tinytool-2.1.tar.gz", "digests": {"sha256": "0" * 64}},
                {"packagetype": "bdist_wheel", "filename": "tinytool-2.1-py3-none-any.whl",
                 "url": "https://files.pythonhosted.org/x/tinytool-2.1-py3-none-any.whl",
                 "digests": {"sha256": hashlib.sha256(self.whl).hexdigest()}, "size": len(self.whl)}]}).encode()
        if url.endswith("tinytool-2.1-py3-none-any.whl"):
            return self.whl + (b"x" if self.corrupt else b"")
        if url == "https://registry.npmjs.org/left-pad/latest":
            return json.dumps({"version": "1.3.0", "main": "index.js", "license": "WTFPL", "dist": {
                "tarball": "https://registry.npmjs.org/left-pad/-/left-pad-1.3.0.tgz",
                "integrity": "sha512-" + base64.b64encode(hashlib.sha512(self.tgz).digest()).decode()}}).encode()
        if url.endswith("left-pad-1.3.0.tgz"):
            return self.tgz
        raise AssertionError(f"unexpected URL {url}")


class StaticCollector:
    def __init__(self, name, items):
        self.name = name; self.items = items

    async def collect(self, query):
        for item in self.items:
            yield dict(item)


@pytest.fixture
def env(tmp_path: Path):
    eng = create_engine(f"sqlite:///{tmp_path/'db.sqlite'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    sessions = sessionmaker(bind=eng, expire_on_commit=False)
    center = ApprovalCenter(session_factory=sessions)
    return (lambda t="tenant-a": InstallPipeline(t, root=tmp_path / "tools", center=center, session_factory=sessions)), center


def test_pypi_fetch_checks_published_sha256_and_builds_manifest():
    reg = FakeRegistry()
    fetched = fetch_pypi("tinytool", fetch=reg)
    assert fetched.registry_digest == "sha256:" + hashlib.sha256(reg.whl).hexdigest()
    assert fetched.manifest_version == "2.1.0+pypi.2.1"
    m = build_manifest(fetched)
    assert m["entrypoint"] == "tinytool/__init__.py" and m["tool_id"] == "pypi-tinytool"
    assert m["metadata"]["registry_version"] == "2.1"
    reg.corrupt = True
    with pytest.raises(RegistryError, match="SHA-256"):
        fetch_pypi("tinytool", fetch=reg)


def test_npm_fetch_checks_integrity_and_repacks_safely():
    reg = FakeRegistry()
    fetched = fetch_npm("left-pad", fetch=reg)
    assert set(fetched.files) == {"package.json", "index.js"}
    assert build_manifest(fetched)["entrypoint"] == "index.js"
    reg.tgz = tarball({"index.js": b"x"}, link=True)
    with pytest.raises(RegistryError, match="link"):
        fetch_npm("left-pad", fetch=reg)


def test_url_allowlist_and_unsupported_sources():
    for bad in ("http://pypi.org/pypi/x/json", "https://evil.example/x", "https://user:pw@pypi.org/x"):
        with pytest.raises(RegistryError):
            http_fetch(bad, 10)
    with pytest.raises(RegistryError, match="no registry-published digest"):
        registry_for_candidate("github", "https://github.com/a/b")
    assert manifest_version("1.2.3", "npm") == "1.2.3"
    assert manifest_version("2024.1", "pypi") == "2024.1.0+pypi.2024.1"


@pytest.mark.asyncio
async def test_discovery_candidates_persist_dedupe_and_track_queries(env):
    make, _ = env
    svc = DiscoveryService(approval_store=None, collectors=[StaticCollector("pypi", [
        {"name": "tinytool", "url": "https://pypi.org/project/tinytool/", "summary": "tiny", "security": .8, "fit": .9}])])
    p = make()
    first = await p.discover("tiny", svc)
    again = await make().discover("small helpers", svc)
    assert len(first) == 1 and again[0]["id"] == first[0]["id"]
    stored = make().list_candidates()
    assert len(stored) == 1 and stored[0]["queries"] == ["tiny", "small helpers"]
    assert make("tenant-b").list_candidates() == []


@pytest.mark.asyncio
async def test_candidate_to_installed_tool_end_to_end(env):
    make, center = env
    svc = DiscoveryService(approval_store=None, collectors=[StaticCollector("npm", [
        {"name": "left-pad", "url": "https://www.npmjs.com/package/left-pad", "summary": "pad", "security": .7}])])
    p = make()
    cand = (await p.discover("pad", svc))[0]
    reg = FakeRegistry()
    prop = p.propose_from_candidate(cand["id"], requested_by="alice", fetch=reg)
    assert prop["candidate_id"] == cand["id"] and prop["candidate"]["registry"] == "npm"
    assert prop["candidate"]["registry_digest"].startswith("sha512-")
    approval = center.get(prop["approval_id"])
    assert approval["payload"]["source_url"].endswith("left-pad-1.3.0.tgz")
    center.decide(prop["approval_id"], ApprovalStatus.APPROVED, decided_by="udita")
    job = p.run_job(p.enqueue_install(prop["id"])["id"])
    assert job["state"] == "succeeded", job["error"]
    port = p.portfolio()
    assert port[0]["tool_id"] == "npm-left-pad" and port[0]["version"] == "1.3.0"
    assert (Path(port[0]["installed_path"]) / "index.js").exists()


def test_candidate_without_registry_digest_is_refused(env):
    make, _ = env
    p = make()
    from app.modules.m22_tools_hub.service import Candidate
    cand = p.record_candidates([Candidate("a/b", "https://github.com/a/b", "repo", "github")], "q")[0]
    with pytest.raises(PipelineError, match="registry-published digest"):
        p.propose_from_candidate(cand["id"], requested_by="alice", fetch=FakeRegistry())
    with pytest.raises(KeyError):
        make("tenant-b").propose_from_candidate(cand["id"], requested_by="alice", fetch=FakeRegistry())


@pytest.mark.skipif(__import__("os").getenv("ATLAS_LIVE_REGISTRY") != "1", reason="set ATLAS_LIVE_REGISTRY=1 to hit real PyPI/npm")
def test_live_registries_fetch_and_scan():
    from app.modules.m22_tools_hub.models import ToolManifest
    from app.modules.m22_tools_hub.security import SecurityScanner
    for fetched in (fetch_pypi("idna"), fetch_npm("left-pad")):
        manifest = ToolManifest.from_dict(build_manifest(fetched))
        assert SecurityScanner().scan(fetched.artifact, manifest).passed
