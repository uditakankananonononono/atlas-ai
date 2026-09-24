"""Module 4 approved sandbox execution: real bubblewrap runs, guards, receipts, routes."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import ApprovalBroadcaster, Service
from app.modules.m04_research_scientist import routes
from app.modules.m04_research_scientist.approved_sandbox import (
    ApprovedSandboxExecutor, BubblewrapBackend, DockerBackend, ExecutionConflictError,
    ExecutionForbiddenError, ExecutionLimits, ExecutionNotFoundError, ExecutionReceiptStore,
    HttpDatasetFetcher, select_backend, verify_manifest,
)
from app.modules.m04_research_scientist.schemas import ProposedAnalysis

def _bwrap_works() -> bool:
    """bwrap must exist AND be allowed to create namespaces on this host."""
    import subprocess
    backend = BubblewrapBackend()
    if not backend.available():
        return False
    probe = subprocess.run([backend.bwrap, "--unshare-all", "--ro-bind", "/usr", "/usr",
                            "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
                            "/usr/bin/true"], capture_output=True)
    return probe.returncode == 0


needs_bwrap = pytest.mark.skipif(not _bwrap_works(), reason="bubblewrap unavailable or user namespaces blocked")


@pytest.fixture
def center(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/m00.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return Service(session_factory=sessionmaker(bind=engine, expire_on_commit=False),
                   broadcaster=ApprovalBroadcaster())


def submit(center, code, tenant="tenant-a", urls=(), approve=True):
    proposal = ProposedAnalysis(objective="Compute summary statistics", language="python",
                                code=code, dataset_urls=list(urls))
    view = center.submit(module_id=4, action_type=proposal.action_type,
                         payload=proposal.model_dump(mode="json"), user_id=tenant)
    if approve:
        center.decide(view["id"], ApprovalStatus.APPROVED, decided_by="udita")
    return view["id"]


def executor(center, tmp_path, tenant="tenant-a", **kw):
    kw.setdefault("limits", ExecutionLimits(timeout_seconds=20, memory_mb=1024))
    kw.setdefault("backend", BubblewrapBackend())
    return ApprovedSandboxExecutor(tenant, center=center, store=ExecutionReceiptStore(tmp_path / "store"), **kw)


STATS = """
import json, statistics
values = [3, 1, 4, 1, 5, 9, 2, 6]
result = {"mean": statistics.mean(values), "median": statistics.median(values)}
open("/output/result.json", "w").write(json.dumps(result, sort_keys=True))
print("mean", result["mean"])
"""


@needs_bwrap
def test_approved_analysis_runs_and_every_output_is_hashed(center, tmp_path):
    ex = executor(center, tmp_path)
    receipt = ex.execute(submit(center, STATS))
    assert receipt["state"] == "succeeded" and receipt["exit_code"] == 0
    assert receipt["backend"] == "bubblewrap" and "network" in receipt["isolation"]
    expected = b'{"mean": 3.875, "median": 3.5}'
    [out] = receipt["outputs"]
    assert out == {"path": "result.json", "bytes": len(expected), "sha256": hashlib.sha256(expected).hexdigest()}
    assert ex.artifact(out["sha256"]) == expected
    assert ex.artifact(receipt["stdout"]["sha256"]) == b"mean 3.875\n"
    assert receipt["code_sha256"] == hashlib.sha256(STATS.encode()).hexdigest()
    assert verify_manifest(receipt)
    assert verify_manifest({**receipt, "exit_code": 1}) is False
    assert ex.readback(receipt["approval_id"]) == receipt


@needs_bwrap
def test_sandbox_has_no_network_and_cannot_write_input(center, tmp_path):
    code = """
import socket, sys
try:
    socket.create_connection(("1.1.1.1", 443), timeout=3); print("NETWORK_OPEN")
except OSError as exc:
    print("network blocked", exc.errno)
try:
    open("/input/analysis.py", "a").write("x"); print("INPUT_WRITABLE")
except OSError:
    print("input read-only")
import os; print("HOME", os.environ.get("HOME"), "KEYS", sorted(k for k in os.environ if "KEY" in k or "TOKEN" in k))
"""
    ex = executor(center, tmp_path)
    receipt = ex.execute(submit(center, code))
    out = ex.artifact(receipt["stdout"]["sha256"]).decode()
    assert "network blocked" in out and "NETWORK_OPEN" not in out
    assert "input read-only" in out and "INPUT_WRITABLE" not in out
    assert "KEYS []" in out


def test_unapproved_foreign_and_wrong_action_items_are_refused(center, tmp_path):
    ex = executor(center, tmp_path)
    pending = submit(center, "print(1)", approve=False)
    with pytest.raises(ExecutionForbiddenError, match="pending"):
        ex.execute(pending)
    denied = submit(center, "print(1)", approve=False)
    center.decide(denied, ApprovalStatus.DENIED, decided_by="udita")
    with pytest.raises(ExecutionForbiddenError, match="denied"):
        ex.execute(denied)
    foreign = submit(center, "print(1)", tenant="tenant-b")
    with pytest.raises(ExecutionNotFoundError):
        ex.execute(foreign)
    other = center.submit(module_id=4, action_type="research_request", payload={"q": "x"}, user_id="tenant-a")
    center.decide(other["id"], ApprovalStatus.APPROVED, decided_by="udita")
    with pytest.raises(ExecutionForbiddenError, match="not a Module 4"):
        ex.execute(other["id"])
    with pytest.raises(ExecutionNotFoundError):
        ex.execute("missing")
    assert ex.list_receipts() == []


@needs_bwrap
def test_one_shot_permit_blocks_replay_including_failed_code(center, tmp_path):
    ex = executor(center, tmp_path)
    ok = submit(center, "print('once')")
    ex.execute(ok)
    with pytest.raises(ExecutionConflictError):
        ex.execute(ok)
    bad = submit(center, "raise SystemExit(3)")
    receipt = ex.execute(bad)
    assert receipt["state"] == "exited_nonzero" and receipt["exit_code"] == 3
    with pytest.raises(ExecutionConflictError):
        ex.execute(bad)
    # a second executor with a fresh receipt store still cannot re-run: Module 0 permit is consumed
    fresh = ApprovedSandboxExecutor("tenant-a", center=center, backend=BubblewrapBackend(),
                                    store=ExecutionReceiptStore(tmp_path / "other"))
    audit = [e["event"] for e in center.audit(ok)]
    assert "effect_consumed" in audit
    with pytest.raises(ExecutionConflictError, match="already consumed"):
        fresh.execute(ok)
    assert {r["approval_id"] for r in ex.list_receipts()} == {ok, bad}


@needs_bwrap
def test_timeout_is_enforced_and_recorded(center, tmp_path):
    ex = executor(center, tmp_path, limits=ExecutionLimits(timeout_seconds=2))
    receipt = ex.execute(submit(center, "import time\nprint('start', flush=True)\ntime.sleep(30)"))
    assert receipt["state"] == "timed_out" and receipt["exit_code"] is None
    assert receipt["duration_seconds"] < 10


@needs_bwrap
def test_symlink_outputs_are_rejected_not_followed(center, tmp_path):
    code = "import os\nos.symlink('/etc/passwd', '/output/leak')\nopen('/output/ok.txt','w').write('ok')"
    receipt = executor(center, tmp_path).execute(submit(center, code))
    assert [o["path"] for o in receipt["outputs"]] == ["ok.txt"]
    assert receipt["rejected_outputs"] == [{"path": "leak", "reason": "symlink"}]


@needs_bwrap
def test_datasets_are_staged_outside_the_sandbox_and_hashed(center, tmp_path):
    body = b"x,y\n1,2\n3,4\n"
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body, headers={"content-type": "text/csv"}))
    fetcher = HttpDatasetFetcher(resolver=lambda host: True, transport=transport)
    code = "rows = open('/input/data/00_table.csv').read().splitlines()\nprint(len(rows))"
    ex = executor(center, tmp_path, fetcher=fetcher)
    receipt = ex.execute(submit(center, code, urls=["https://data.example.org/files/table.csv"]))
    assert receipt["state"] == "succeeded", receipt
    [ds] = receipt["datasets"]
    assert ds["sha256"] == hashlib.sha256(body).hexdigest() and ds["bytes"] == len(body)
    assert ds["path"] == "/input/data/00_table.csv"
    assert ex.artifact(receipt["stdout"]["sha256"]) == b"3\n"


def test_dataset_guards_reject_private_hosts_http_and_oversize(tmp_path):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"a" * 100))
    private = HttpDatasetFetcher(resolver=lambda host: False, transport=transport)
    with pytest.raises(Exception, match="public"):
        private.fetch("https://internal.example/x", tmp_path / "x", 1000)
    public = HttpDatasetFetcher(resolver=lambda host: True, transport=transport)
    with pytest.raises(Exception, match="https"):
        public.fetch("http://example.org/x", tmp_path / "x", 1000)
    with pytest.raises(Exception, match="exceeds"):
        public.fetch("https://example.org/x", tmp_path / "x", 10)
    redirect = httpx.MockTransport(lambda r: httpx.Response(302, headers={"location": "http://169.254.169.254/"}))
    with pytest.raises(Exception, match="https"):
        HttpDatasetFetcher(resolver=lambda h: True, transport=redirect).fetch("https://example.org/x", tmp_path / "x", 10)


@needs_bwrap
def test_infrastructure_failure_is_retryable_with_same_permit(center, tmp_path):
    class Flaky:
        calls = 0
        def fetch(self, url, destination, max_bytes):
            Flaky.calls += 1
            if Flaky.calls == 1:
                raise ConnectionError("upstream down")
            destination.write_bytes(b"1")
            return {"url": url, "final_url": url, "bytes": 1, "sha256": hashlib.sha256(b"1").hexdigest(), "content_type": ""}
    ex = executor(center, tmp_path, fetcher=Flaky())
    approval = submit(center, "print(open('/input/data/00_d.txt').read())", urls=["https://example.org/d.txt"])
    first = ex.execute(approval)
    assert first["state"] == "infra_failed" and "upstream down" in first["error"]
    second = ex.execute(approval)
    assert second["state"] == "succeeded" and second["run_id"] != first["run_id"]


def test_docker_backend_command_enforces_isolation(tmp_path):
    calls = {}
    def runner(args, **kw):
        calls["args"] = args
        kw["stdout_path"].write_bytes(b"ok\n"); kw["stderr_path"].write_bytes(b"")
        return 0, False
    (tmp_path / "in").mkdir(); (tmp_path / "out").mkdir()
    backend = DockerBackend(docker="/usr/bin/docker", images={"python": "python:3.12-slim", "r": "r-base:4.4.1"}, process_runner=runner)
    run = backend.run(language="python", input_dir=tmp_path / "in", output_dir=tmp_path / "out", limits=ExecutionLimits())
    args = " ".join(calls["args"])
    for flag in ("--network none", "--read-only", "--cap-drop ALL", "--security-opt no-new-privileges",
                 "--user 65534:65534", "--memory 2048m", "--pids-limit 128", ":/input:ro"):
        assert flag in args
    assert calls["args"][-1] == "/input/analysis.py" and run.exit_code == 0 and run.stdout == b"ok\n"


def test_backend_selection_never_falls_back_to_unsandboxed(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(Exception, match="no sandbox backend"):
        select_backend("auto")
    with pytest.raises(Exception, match="unknown"):
        select_backend("subprocess")


@needs_bwrap
def test_http_routes_propose_approve_execute_download(center, tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "default_service", lambda: center)
    app = FastAPI(); app.include_router(routes.router)
    ex = executor(center, tmp_path)
    app.dependency_overrides[routes.get_sandbox_executor] = lambda: ex
    client = TestClient(app)
    headers = {"X-Atlas-Tenant": "tenant-a"}
    proposal = client.post("/research-scientist/analyses/proposals", headers=headers,
                           json={"objective": "Compute summary statistics", "code": STATS}).json()
    approval_id = proposal["approval_id"]
    assert client.post(f"/research-scientist/analyses/{approval_id}/execute", headers=headers).status_code == 403
    center.decide(approval_id, ApprovalStatus.APPROVED, decided_by="udita")
    created = client.post(f"/research-scientist/analyses/{approval_id}/execute", headers=headers)
    assert created.status_code == 201 and created.json()["state"] == "succeeded"
    assert client.post(f"/research-scientist/analyses/{approval_id}/execute", headers=headers).status_code == 409
    assert client.get(f"/research-scientist/analyses/{approval_id}/execution", headers=headers).json() == created.json()
    sha = created.json()["outputs"][0]["sha256"]
    download = client.get(f"/research-scientist/analyses/artifacts/{sha}", headers=headers)
    assert download.status_code == 200 and hashlib.sha256(download.content).hexdigest() == sha
    assert client.get("/research-scientist/analyses/artifacts/" + "0" * 64, headers=headers).status_code == 404
    assert [r["approval_id"] for r in client.get("/research-scientist/analyses/executions", headers=headers).json()] == [approval_id]


# ---------------------------------------------------------------- environment lock + executed bundle
import io
import json
import zipfile

from app.modules.m04_research_scientist.execution_bundle import build_execution_bundle, verify_execution_bundle


@needs_bwrap
def test_environment_lock_is_captured_inside_the_sandbox(center, tmp_path):
    import platform
    receipt = executor(center, tmp_path).execute(submit(center, "print('x')"))
    lock = receipt["environment_lock"]
    assert lock["language"] == "python" and lock["backend"] == "bubblewrap"
    # the sandbox runs the host's /usr/bin/python3, not this test's venv interpreter
    import subprocess
    host = subprocess.run(["/usr/bin/python3", "-c", "import platform;print(platform.python_version())"],
                          capture_output=True, text=True).stdout.strip()
    assert lock["version"] == host
    assert isinstance(lock["packages"], dict) and lock["platform"]
    assert receipt["environment_lock_sha256"] == lock["lock_sha256"] and len(lock["lock_sha256"]) == 64


def test_broken_sandbox_fails_before_the_permit_is_consumed(center, tmp_path):
    from app.modules.m04_research_scientist.approved_sandbox import BackendUnavailableError, SandboxRun

    class Broken:
        name = "broken"
        def available(self, language="python"):
            return True
        def run(self, **kw):
            return SandboxRun("broken", {}, 1, False, b"", b"no interpreter", False, False, "", "", 0.0)

    approval = submit(center, "print(1)")
    with pytest.raises(BackendUnavailableError, match="environment probe failed"):
        executor(center, tmp_path, backend=Broken()).execute(approval)
    assert "effect_consumed" not in [e["event"] for e in center.audit(approval)]


@needs_bwrap
def test_executed_bundle_contains_and_verifies_code_data_lock_logs_outputs(center, tmp_path):
    body = b"a,b\n1,2\n"
    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=body))
    fetcher = HttpDatasetFetcher(resolver=lambda h: True, transport=transport)
    code = STATS + "\nprint(open('/input/data/00_t.csv').read().count('\\n'))\n"
    ex = executor(center, tmp_path, fetcher=fetcher)
    receipt = ex.execute(submit(center, code, urls=["https://data.example.org/t.csv"]))
    payload, manifest = build_execution_bundle(receipt, ex.store, "tenant-a")
    assert manifest["schema_version"] == 2 and manifest["executed"] is True
    names = set(zipfile.ZipFile(io.BytesIO(payload)).namelist())
    assert {"manifest.json", "analysis.py", "environment.lock.json", "logs/stdout.txt", "logs/stderr.txt",
            "outputs/result.json", "data/00_t.csv", "README.md"} <= names
    assert manifest["datasets"][0]["bundled_as"] == "data/00_t.csv"
    assert manifest["environment_lock_sha256"] == receipt["environment_lock_sha256"]
    assert verify_execution_bundle(payload) == {"valid": True, "problems": [], "manifest_sha256": manifest["manifest_sha256"]}

    # tamper with one output file -> verification names it
    src = zipfile.ZipFile(io.BytesIO(payload)); out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as dst:
        for n in src.namelist():
            dst.writestr(n, b'{"mean": 99}' if n == "outputs/result.json" else src.read(n))
    report = verify_execution_bundle(out.getvalue())
    assert not report["valid"] and "hash mismatch: outputs/result.json" in report["problems"]

    # oversize datasets are referenced by hash, not bundled
    _, small = build_execution_bundle(receipt, ex.store, "tenant-a", max_dataset_bytes=1)
    assert small["datasets"][0]["bundled_as"] is None and small["datasets"][0]["sha256"] == hashlib.sha256(body).hexdigest()


@needs_bwrap
def test_bundle_route_and_unfinished_runs(center, tmp_path, monkeypatch):
    app = FastAPI(); app.include_router(routes.router)
    ex = executor(center, tmp_path)
    app.dependency_overrides[routes.get_sandbox_executor] = lambda: ex
    client = TestClient(app); h = {"X-Atlas-Tenant": "tenant-a"}
    approval = submit(center, STATS)
    assert client.get(f"/research-scientist/analyses/{approval}/bundle", headers=h).status_code == 404
    ex.execute(approval)
    res = client.get(f"/research-scientist/analyses/{approval}/bundle", headers=h)
    assert res.status_code == 200 and res.headers["x-atlas-bundle-sha256"] == hashlib.sha256(res.content).hexdigest()
    assert verify_execution_bundle(res.content)["valid"]


# ---------------------------------------------------------------- approval-gated re-run + hash diff
from app.modules.m04_research_scientist.rerun import RerunService, diff_environment, diff_outputs


def approve_rerun(center, svc, original_approval, reason="quarterly check"):
    proposal = svc.propose(original_approval, reason)
    assert proposal["status"] == "pending" and proposal["action_type"] == "rerun_sandboxed_analysis"
    center.decide(proposal["approval_id"], ApprovalStatus.APPROVED, decided_by="udita")
    return proposal["approval_id"]


@needs_bwrap
def test_deterministic_analysis_reproduces_with_stored_datasets(center, tmp_path):
    calls = {"n": 0}
    body = b"v\n1\n2\n3\n"

    class OnceFetcher:
        def fetch(self, url, destination, max_bytes):
            calls["n"] += 1
            destination.write_bytes(body)
            return {"url": url, "final_url": url, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "content_type": ""}

    ex = executor(center, tmp_path, fetcher=OnceFetcher())
    code = "rows=open('/input/data/00_v.csv').read().split()[1:]\nopen('/output/sum.txt','w').write(str(sum(map(int,rows))))\nprint('ok')"
    original = submit(center, code, urls=["https://example.org/v.csv"])
    ex.execute(original)
    svc = RerunService(ex)
    rerun = svc.execute(approve_rerun(center, svc, original))
    cmp = rerun["comparison"]
    assert rerun["kind"] == "rerun" and rerun["state"] == "succeeded"
    assert cmp["verdict"] == "reproduced" and cmp["summary"] == {"identical": 1, "changed": 0, "missing": 0, "new": 0}
    assert cmp["stdout_identical"] and cmp["environment"]["identical"]
    assert calls["n"] == 1  # datasets came from the hash-checked store, not a re-download
    assert verify_manifest(rerun)


@needs_bwrap
def test_nondeterministic_analysis_is_reported_as_diverged(center, tmp_path):
    ex = executor(center, tmp_path)
    code = "import os\nopen('/output/stable.txt','w').write('same')\nopen('/output/noise.bin','wb').write(os.urandom(16))"
    original = submit(center, code)
    first = ex.execute(original)
    svc = RerunService(ex)
    cmp = svc.execute(approve_rerun(center, svc, original))["comparison"]
    assert cmp["verdict"] == "diverged"
    by_path = {r["path"]: r["status"] for r in cmp["outputs"]}
    assert by_path["stable.txt"] == "identical" and by_path["noise.bin"] == "changed"
    assert set(by_path) == {o["path"] for o in first["outputs"]}
    assert cmp["summary"] == {"identical": 1, "changed": 1, "missing": 0, "new": 0}


@needs_bwrap
def test_rerun_guards(center, tmp_path):
    ex = executor(center, tmp_path)
    svc = RerunService(ex)
    with pytest.raises(ExecutionNotFoundError):
        svc.propose("never-ran")
    original = submit(center, "open('/output/a','w').write('1')")
    ex.execute(original)
    pending = svc.propose(original)["approval_id"]
    with pytest.raises(ExecutionForbiddenError, match="pending"):
        svc.execute(pending)
    with pytest.raises(ExecutionForbiddenError, match="not a Module 4 sandboxed"):
        ex.execute(pending)  # a re-run approval cannot be used as a fresh analysis approval
    approved = approve_rerun(center, svc, original)
    svc.execute(approved)
    with pytest.raises(ExecutionConflictError):
        svc.execute(approved)
    foreign = RerunService(executor(center, tmp_path / "b", tenant="tenant-b"))
    with pytest.raises(ExecutionNotFoundError):
        foreign.execute(approved)


def test_diff_helpers():
    rows = diff_outputs([{"path": "a", "sha256": "1", "bytes": 1}, {"path": "b", "sha256": "2", "bytes": 1}],
                        [{"path": "a", "sha256": "1", "bytes": 1}, {"path": "c", "sha256": "3", "bytes": 2}])
    assert [(r["path"], r["status"]) for r in rows] == [("a", "identical"), ("b", "missing"), ("c", "new")]
    env = diff_environment({"version": "3.10.1", "packages": {"numpy": "1.26", "old": "1"}, "lock_sha256": "x"},
                           {"version": "3.10.2", "packages": {"numpy": "2.0", "new": "3"}, "lock_sha256": "y"})
    assert env["identical"] is False and env["fields"]["version"] == {"original": "3.10.1", "rerun": "3.10.2"}
    assert env["packages_changed"] == {"numpy": {"original": "1.26", "rerun": "2.0"}}
    assert env["packages_added"] == {"new": "3"} and env["packages_removed"] == {"old": "1"}


@needs_bwrap
def test_rerun_http_routes(center, tmp_path):
    app = FastAPI(); app.include_router(routes.router)
    ex = executor(center, tmp_path)
    app.dependency_overrides[routes.get_sandbox_executor] = lambda: ex
    client = TestClient(app); h = {"X-Atlas-Tenant": "tenant-a"}
    original = submit(center, STATS)
    assert client.post(f"/research-scientist/analyses/{original}/reruns", headers=h, json={}).status_code == 404
    ex.execute(original)
    proposal = client.post(f"/research-scientist/analyses/{original}/reruns", headers=h, json={"reason": "check"})
    assert proposal.status_code == 202
    rid = proposal.json()["approval_id"]
    assert client.post(f"/research-scientist/analyses/reruns/{rid}/execute", headers=h).status_code == 403
    center.decide(rid, ApprovalStatus.APPROVED, decided_by="udita")
    done = client.post(f"/research-scientist/analyses/reruns/{rid}/execute", headers=h)
    assert done.status_code == 201 and done.json()["comparison"]["verdict"] == "reproduced"
    assert client.post(f"/research-scientist/analyses/reruns/{rid}/execute", headers=h).status_code == 409
    assert client.get(f"/research-scientist/analyses/{rid}/bundle", headers=h).status_code == 200
