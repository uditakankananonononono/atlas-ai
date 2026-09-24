"""Approved sandbox execution for Module 4 analysis proposals.

``routes.propose_analysis`` files an inert ``execute_sandboxed_analysis``
request with the Human Approval Center. This module is the other half: it
runs that exact reviewed code, and only that code, once a human approved it.

Guards, in order:

1. the approval exists and belongs to the calling tenant (else not found);
2. it is a Module 4 ``execute_sandboxed_analysis`` item with a valid payload;
3. its status is ``approved`` (pending / denied / expired are refused);
4. no earlier run for it is started or finished (only infrastructure
   failures, where the code never ran, may be retried);
5. Module 0 issues a one-shot permit bound to the hash of the exact reviewed
   payload (``Service.consume_effect``), so an edited payload cannot run.

Execution happens in a real isolation backend and never in-process:

* ``DockerBackend`` - ephemeral container, ``--network none``, read-only
  root, all capabilities dropped, no-new-privileges, nobody user, CPU,
  memory, pid and time limits, read-only ``/input`` and writable ``/output``.
* ``BubblewrapBackend`` - Linux namespaces via ``bwrap --unshare-all`` (no
  network, private pid/ipc/uts/user namespaces), read-only system mounts,
  clean environment, plus address-space, CPU-time and file-size rlimits.

Datasets named in the proposal are downloaded *outside* the sandbox before
the run (HTTPS only, public addresses only, size-capped) and hashed, so the
analysis itself never needs network. Every attempt persists a receipt with
the request hash, code hash, dataset hashes, captured stdout/stderr (hashed,
size-capped), exit code, timing, and the SHA-256 of every output file. Logs
and outputs are copied into a tenant-scoped content-addressed store and the
whole receipt is sealed with a manifest hash.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import resource
import shutil
import signal
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol
from urllib.parse import urlparse
from uuid import uuid4

from .schemas import ProposedAnalysis

SANDBOX_ACTION = "execute_sandboxed_analysis"
MODULE_ID = 4
ENTRYPOINTS = {"python": "analysis.py", "r": "analysis.R"}
# States that mean the reviewed code started or finished; these block replay.
BLOCKING_STATES = ("started", "succeeded", "exited_nonzero", "timed_out")


class SandboxExecutionError(RuntimeError):
    """Base error for approved sandbox execution."""


class ExecutionNotFoundError(SandboxExecutionError, KeyError):
    """Approval or receipt does not exist for this tenant."""


class ExecutionForbiddenError(SandboxExecutionError, PermissionError):
    """Approval is not in an executable state."""


class ExecutionConflictError(SandboxExecutionError):
    """The approval already ran, or its permit was already consumed."""


class BackendUnavailableError(SandboxExecutionError):
    """No real isolation backend is available on this host."""


class DatasetStagingError(SandboxExecutionError):
    """A dataset could not be fetched safely."""


@dataclass(frozen=True)
class ExecutionLimits:
    timeout_seconds: int = 600
    memory_mb: int = 2048
    cpus: float = 1.0
    pids: int = 128
    max_file_mb: int = 512
    max_log_bytes: int = 2 * 1024 * 1024
    max_output_files: int = 200
    max_output_bytes: int = 256 * 1024 * 1024
    max_dataset_bytes: int = 512 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "ExecutionLimits":
        base = cls()
        def pick(name: str, default: Any, cast: Callable[[str], Any]) -> Any:
            raw = os.getenv(f"ATLAS_SANDBOX_{name.upper()}")
            return cast(raw) if raw else default
        return cls(**{k: pick(k, v, type(v)) for k, v in asdict(base).items()})


@dataclass
class SandboxRun:
    backend: str
    isolation: dict[str, Any]
    exit_code: int | None
    timed_out: bool
    stdout: bytes
    stderr: bytes
    stdout_truncated: bool
    stderr_truncated: bool
    started_at: str
    finished_at: str
    duration_seconds: float


class SandboxBackend(Protocol):
    name: str

    def available(self) -> bool: ...

    def run(self, *, language: str, input_dir: Path, output_dir: Path,
            limits: ExecutionLimits) -> SandboxRun: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_capped(path: Path, cap: int) -> tuple[bytes, bool]:
    size = path.stat().st_size if path.exists() else 0
    if not size:
        return b"", False
    with path.open("rb") as handle:
        return handle.read(cap), size > cap


def _run_process(args: list[str], *, stdout_path: Path, stderr_path: Path,
                 timeout: int, preexec: Callable[[], None] | None = None,
                 on_timeout: Callable[[subprocess.Popen], None] | None = None) -> tuple[int | None, bool]:
    """Run a process group with a hard wall-clock timeout."""
    with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
        proc = subprocess.Popen(args, stdout=out, stderr=err, stdin=subprocess.DEVNULL,
                                start_new_session=True, preexec_fn=preexec, close_fds=True)
        try:
            return proc.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            if on_timeout:
                on_timeout(proc)
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            return None, True


class BubblewrapBackend:
    """Namespace sandbox using bubblewrap; no network, clean env, rlimits."""

    name = "bubblewrap"
    INTERPRETERS = {"python": ["/usr/bin/python3", "-I", "-B"],
                    "r": ["/usr/bin/Rscript", "--vanilla"]}

    def __init__(self, bwrap: str | None = None) -> None:
        self.bwrap = bwrap or shutil.which("bwrap")

    def available(self, language: str = "python") -> bool:
        return bool(self.bwrap) and Path(self.INTERPRETERS[language][0]).exists()

    def _system_mounts(self) -> list[str]:
        args = ["--ro-bind", "/usr", "/usr"]
        for top in ("lib", "lib64", "lib32", "bin", "sbin"):
            host = Path("/") / top
            if host.is_symlink():
                args += ["--symlink", os.readlink(host), f"/{top}"]
            elif host.exists():
                args += ["--ro-bind", str(host), f"/{top}"]
        for path in ("/etc/alternatives", "/etc/R", "/etc/ld.so.cache", "/etc/localtime"):
            args += ["--ro-bind-try", path, path]
        return args

    def command(self, language: str, input_dir: Path, output_dir: Path) -> list[str]:
        interp = self.INTERPRETERS[language]
        return [self.bwrap or "bwrap", "--unshare-all", "--die-with-parent", "--new-session",
                *self._system_mounts(),
                "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                "--ro-bind", str(input_dir), "/input", "--bind", str(output_dir), "/output",
                "--chdir", "/output", "--clearenv",
                "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "HOME", "/tmp",
                "--setenv", "MPLBACKEND", "Agg", "--setenv", "LANG", "C.UTF-8",
                *interp, f"/input/{ENTRYPOINTS[language]}"]

    def run(self, *, language: str, input_dir: Path, output_dir: Path,
            limits: ExecutionLimits) -> SandboxRun:
        if not self.available(language):
            raise BackendUnavailableError(f"bubblewrap or the {language} interpreter is not installed")
        mem = limits.memory_mb * 1024 * 1024
        fsize = limits.max_file_mb * 1024 * 1024
        cpu = max(1, int(limits.timeout_seconds * max(limits.cpus, 1)))

        def preexec() -> None:
            resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
            resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

        logs = Path(tempfile.mkdtemp(prefix="atlas-sbx-logs-"))
        started, t0 = _now(), time.monotonic()
        try:
            code, timed_out = _run_process(
                self.command(language, input_dir, output_dir),
                stdout_path=logs / "stdout", stderr_path=logs / "stderr",
                timeout=limits.timeout_seconds, preexec=preexec)
            out, out_cut = _read_capped(logs / "stdout", limits.max_log_bytes)
            err, err_cut = _read_capped(logs / "stderr", limits.max_log_bytes)
        finally:
            shutil.rmtree(logs, ignore_errors=True)
        return SandboxRun(
            backend=self.name,
            isolation={"network": "none (network namespace)", "namespaces": "user,pid,ipc,uts,net,cgroup",
                       "filesystem": "read-only system, read-only /input, tmpfs /tmp, writable /output",
                       "environment": "cleared", "rlimits": {"address_space_mb": limits.memory_mb,
                       "cpu_seconds": cpu, "file_size_mb": limits.max_file_mb}},
            exit_code=code, timed_out=timed_out, stdout=out, stderr=err,
            stdout_truncated=out_cut, stderr_truncated=err_cut, started_at=started,
            finished_at=_now(), duration_seconds=round(time.monotonic() - t0, 3))


class DockerBackend:
    """Ephemeral no-network container, matching the module's sandbox policy."""

    name = "docker"

    def __init__(self, docker: str | None = None,
                 images: dict[str, str] | None = None,
                 process_runner: Callable[..., tuple[int | None, bool]] = _run_process) -> None:
        self.docker = docker or shutil.which("docker")
        self.images = images or {
            "python": os.getenv("ATLAS_SANDBOX_PYTHON_IMAGE", "python:3.12-slim"),
            "r": os.getenv("ATLAS_SANDBOX_R_IMAGE", "r-base:4.4.1")}
        self.process_runner = process_runner

    def available(self, language: str = "python") -> bool:
        return bool(self.docker)

    def command(self, name: str, language: str, input_dir: Path, output_dir: Path,
                limits: ExecutionLimits) -> list[str]:
        interp = {"python": ["python", "-I", "-B"], "r": ["Rscript", "--vanilla"]}[language]
        return [self.docker or "docker", "run", "--rm", "--name", name,
                "--network", "none", "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "--user", "65534:65534",
                "--cpus", str(limits.cpus), "--memory", f"{limits.memory_mb}m",
                "--memory-swap", f"{limits.memory_mb}m", "--pids-limit", str(limits.pids),
                "--ulimit", f"fsize={limits.max_file_mb * 1024 * 1024}",
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=256m",
                "-e", "HOME=/tmp", "-e", "MPLBACKEND=Agg",
                "-v", f"{input_dir}:/input:ro", "-v", f"{output_dir}:/output:rw",
                "-w", "/output", self.images[language], *interp,
                f"/input/{ENTRYPOINTS[language]}"]

    def run(self, *, language: str, input_dir: Path, output_dir: Path,
            limits: ExecutionLimits) -> SandboxRun:
        if not self.available(language):
            raise BackendUnavailableError("docker is not installed")
        os.chmod(output_dir, 0o777)  # container runs as nobody
        name = f"atlas-sbx-{uuid4().hex[:12]}"
        logs = Path(tempfile.mkdtemp(prefix="atlas-sbx-logs-"))

        def kill(_proc: Any) -> None:
            subprocess.run([self.docker or "docker", "kill", name], capture_output=True, timeout=30)

        started, t0 = _now(), time.monotonic()
        try:
            code, timed_out = self.process_runner(
                self.command(name, language, input_dir, output_dir, limits),
                stdout_path=logs / "stdout", stderr_path=logs / "stderr",
                timeout=limits.timeout_seconds, on_timeout=kill)
            out, out_cut = _read_capped(logs / "stdout", limits.max_log_bytes)
            err, err_cut = _read_capped(logs / "stderr", limits.max_log_bytes)
        finally:
            shutil.rmtree(logs, ignore_errors=True)
        return SandboxRun(
            backend=self.name,
            isolation={"network": "none", "image": self.images[language], "user": "65534:65534",
                       "root_filesystem": "read-only", "capabilities": "all dropped",
                       "limits": {"cpus": limits.cpus, "memory_mb": limits.memory_mb, "pids": limits.pids}},
            exit_code=code, timed_out=timed_out, stdout=out, stderr=err,
            stdout_truncated=out_cut, stderr_truncated=err_cut, started_at=started,
            finished_at=_now(), duration_seconds=round(time.monotonic() - t0, 3))


def select_backend(preference: str | None = None) -> SandboxBackend:
    """Pick a real isolation backend. There is deliberately no unsandboxed option."""
    choice = (preference or os.getenv("ATLAS_SANDBOX_BACKEND", "auto")).lower()
    options: dict[str, SandboxBackend] = {"docker": DockerBackend(), "bubblewrap": BubblewrapBackend()}
    if choice in options:
        return options[choice]
    if choice != "auto":
        raise BackendUnavailableError(f"unknown sandbox backend {choice!r}")
    for backend in (options["docker"], options["bubblewrap"]):
        if backend.available():
            return backend
    raise BackendUnavailableError("no sandbox backend available: install docker or bubblewrap")


# --------------------------------------------------------------------------- datasets

class DatasetFetcher(Protocol):
    def fetch(self, url: str, destination: Path, max_bytes: int) -> dict[str, Any]: ...


def _public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if not addr.is_global or addr.is_multicast:
            return False
    return bool(infos)


class HttpDatasetFetcher:
    """HTTPS-only, public-address-only, size-capped dataset download."""

    def __init__(self, resolver: Callable[[str], bool] = _public_host, max_redirects: int = 3,
                 transport: Any = None) -> None:
        self.resolver = resolver
        self.max_redirects = max_redirects
        self.transport = transport

    def _check(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise DatasetStagingError(f"dataset URL must be https: {url}")
        if not self.resolver(parsed.hostname):
            raise DatasetStagingError(f"dataset host is not a public address: {parsed.hostname}")

    def fetch(self, url: str, destination: Path, max_bytes: int) -> dict[str, Any]:
        import httpx
        current = url
        with httpx.Client(timeout=60, follow_redirects=False, transport=self.transport) as client:
            for _ in range(self.max_redirects + 1):
                self._check(current)
                with client.stream("GET", current) as response:
                    if response.is_redirect:
                        current = str(response.url.join(response.headers.get("location", "")))
                        continue
                    if response.status_code != 200:
                        raise DatasetStagingError(f"dataset {url} returned HTTP {response.status_code}")
                    digest, total = hashlib.sha256(), 0
                    with destination.open("wb") as handle:
                        for chunk in response.iter_bytes():
                            total += len(chunk)
                            if total > max_bytes:
                                raise DatasetStagingError(f"dataset {url} exceeds {max_bytes} bytes")
                            digest.update(chunk)
                            handle.write(chunk)
                    return {"url": url, "final_url": current, "bytes": total,
                            "sha256": digest.hexdigest(),
                            "content_type": response.headers.get("content-type", "")}
        raise DatasetStagingError(f"dataset {url} redirected too many times")


def _dataset_name(index: int, url: str) -> str:
    base = Path(urlparse(url).path).name or "dataset"
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", base)[:80].lstrip(".") or "dataset"
    return f"{index:02d}_{safe}"


# --------------------------------------------------------------------------- receipts

def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ExecutionReceiptStore:
    """SQLite, tenant-scoped receipts plus a content-addressed artifact store."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "m04-sandbox-receipts.sqlite"
        self._lock = threading.Lock()
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS m04_sandbox_receipts ("
                       "seq INTEGER PRIMARY KEY AUTOINCREMENT, receipt_id TEXT NOT NULL, "
                       "tenant_id TEXT NOT NULL, approval_id TEXT NOT NULL, state TEXT NOT NULL, "
                       "receipt TEXT NOT NULL, created_at TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS m04_sandbox_artifacts ("
                       "tenant_id TEXT NOT NULL, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL, "
                       "PRIMARY KEY (tenant_id, sha256))")
            db.execute("CREATE INDEX IF NOT EXISTS m04_sbx_by_approval "
                       "ON m04_sandbox_receipts (tenant_id, approval_id, seq)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def record(self, tenant_id: str, receipt: dict[str, Any]) -> None:
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO m04_sandbox_receipts (receipt_id, tenant_id, approval_id, state, receipt, created_at) "
                       "VALUES (?,?,?,?,?,?)", (receipt["receipt_id"], tenant_id, receipt["approval_id"],
                                                receipt["state"], _canonical(receipt), _now()))

    def latest(self, tenant_id: str, approval_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT receipt FROM m04_sandbox_receipts WHERE tenant_id=? AND approval_id=? "
                             "ORDER BY seq DESC LIMIT 1", (tenant_id, approval_id)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT receipt FROM m04_sandbox_receipts r WHERE tenant_id=? AND seq = ("
                "SELECT MAX(seq) FROM m04_sandbox_receipts WHERE tenant_id=r.tenant_id AND approval_id=r.approval_id) "
                "ORDER BY seq DESC LIMIT ?", (tenant_id, limit)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def _blob(self, tenant_id: str, sha: str) -> Path:
        tenant_dir = hashlib.sha256(tenant_id.encode()).hexdigest()[:24]
        return self.root / "artifacts" / tenant_dir / sha[:2] / sha

    def put_bytes(self, tenant_id: str, data: bytes) -> str:
        sha = _sha(data)
        path = self._blob(tenant_id, sha)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
        self._register(tenant_id, sha, len(data))
        return sha

    def put_file(self, tenant_id: str, source: Path, sha: str, size: int) -> None:
        path = self._blob(tenant_id, sha)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            shutil.copyfile(source, tmp)
            tmp.replace(path)
        self._register(tenant_id, sha, size)

    def _register(self, tenant_id: str, sha: str, size: int) -> None:
        with self._lock, self._connect() as db:
            db.execute("INSERT OR IGNORE INTO m04_sandbox_artifacts VALUES (?,?,?)", (tenant_id, sha, size))

    def read_artifact(self, tenant_id: str, sha: str) -> bytes:
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ExecutionNotFoundError(sha)
        with self._connect() as db:
            known = db.execute("SELECT 1 FROM m04_sandbox_artifacts WHERE tenant_id=? AND sha256=?",
                               (tenant_id, sha)).fetchone()
        path = self._blob(tenant_id, sha)
        if not known or not path.exists():
            raise ExecutionNotFoundError(sha)
        data = path.read_bytes()
        if _sha(data) != sha:
            raise SandboxExecutionError(f"stored artifact {sha} failed its integrity check")
        return data


def hash_outputs(output_dir: Path, limits: ExecutionLimits) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Hash regular files under output_dir; symlinks and overflow are rejected, never followed."""
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    total = 0
    for path in sorted(output_dir.rglob("*")):
        rel = path.relative_to(output_dir).as_posix()
        if path.is_symlink():
            rejected.append({"path": rel, "reason": "symlink"})
            continue
        if not path.is_file():
            continue
        size = path.stat().st_size
        if len(accepted) >= limits.max_output_files:
            rejected.append({"path": rel, "reason": "output file count limit"})
            continue
        if total + size > limits.max_output_bytes:
            rejected.append({"path": rel, "reason": "output byte limit"})
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        total += size
        accepted.append({"path": rel, "bytes": size, "sha256": digest.hexdigest()})
    return accepted, rejected


# --------------------------------------------------------------------------- executor

class ApprovedSandboxExecutor:
    """Runs approved Module 4 analysis proposals and seals the evidence."""

    def __init__(self, tenant_id: str, *, actor_id: str | None = None, center: Any = None,
                 backend: SandboxBackend | None = None, store: ExecutionReceiptStore | None = None,
                 fetcher: DatasetFetcher | None = None, limits: ExecutionLimits | None = None) -> None:
        if center is None:
            from app.modules.m00_approval_center.service import default_service
            center = default_service()
        if store is None:
            root = Path(os.getenv("ATLAS_RUNTIME_DATA_DIR", "/tmp/atlas-runtime")) / "m04-sandbox"
            store = ExecutionReceiptStore(root)
        self.tenant_id = tenant_id
        self.actor_id = actor_id or tenant_id
        self.center = center
        self._backend = backend
        self.store = store
        self.fetcher = fetcher or HttpDatasetFetcher()
        self.limits = limits or ExecutionLimits.from_env()

    @property
    def backend(self) -> SandboxBackend:
        if self._backend is None:
            self._backend = select_backend()
        return self._backend

    def _load_approval(self, approval_id: str) -> tuple[dict[str, Any], ProposedAnalysis]:
        try:
            view = self.center.get(approval_id)
        except KeyError as exc:
            raise ExecutionNotFoundError(approval_id) from exc
        if view.get("user_id") != self.tenant_id:
            raise ExecutionNotFoundError(approval_id)
        if view.get("module_id") != MODULE_ID or view.get("action_type") != SANDBOX_ACTION:
            raise ExecutionForbiddenError("approval is not a Module 4 sandboxed analysis")
        status = getattr(view.get("status"), "value", view.get("status"))
        if status != "approved":
            raise ExecutionForbiddenError(f"approval is {status}, not approved")
        payload = dict(view.get("payload") or {})
        try:
            proposal = ProposedAnalysis.model_validate(payload)
        except Exception as exc:
            raise ExecutionForbiddenError(f"approved payload is not a valid analysis proposal: {exc}") from exc
        return view, proposal

    def execute(self, approval_id: str) -> dict[str, Any]:
        view, proposal = self._load_approval(approval_id)
        prior = self.store.latest(self.tenant_id, approval_id)
        if prior and prior["state"] in BLOCKING_STATES:
            raise ExecutionConflictError(f"approval already has a {prior['state']} run ({prior['receipt_id']})")
        backend = self.backend
        if not backend.available(proposal.language):
            raise BackendUnavailableError(f"{backend.name} cannot run {proposal.language} on this host")
        payload = dict(view["payload"])
        request_hash = _sha(_canonical({"module_id": MODULE_ID, "action_type": SANDBOX_ACTION,
                                        "payload": payload, "user_id": self.tenant_id}).encode())
        # One-shot permit bound to the exact reviewed payload. A deterministic
        # effect id lets an infrastructure-failed attempt retry the same permit,
        # but only when this store proves the earlier attempt never ran code.
        # Module 0's audit trail is the cross-store truth: a consumed permit
        # with no local infra_failed receipt means the code may already have run.
        consumed = any(e.get("event") == "effect_consumed" for e in self.center.audit(approval_id))
        if consumed and not (prior and prior["state"] == "infra_failed"):
            raise ExecutionConflictError("approval permit was already consumed by an earlier run")
        try:
            permit = self.center.consume_effect(
                approval_id, module_id=MODULE_ID, action_type=SANDBOX_ACTION, payload=payload,
                user_id=self.tenant_id, effect_id=f"m04-sandbox:{approval_id}", actor=self.actor_id)
        except Exception as exc:
            if type(exc).__name__ == "ApprovalConflictError":
                raise ExecutionConflictError(str(exc)) from exc
            raise
        run_id = str(uuid4())
        receipt: dict[str, Any] = {
            "receipt_id": run_id, "run_id": run_id, "approval_id": approval_id, "tenant_id": self.tenant_id,
            "actor_id": self.actor_id, "state": "started", "objective": proposal.objective,
            "language": proposal.language, "request_hash": request_hash,
            "code_sha256": _sha(proposal.code.encode()), "permit_consumed_at": str(permit.get("consumed_at")),
            "backend": backend.name, "limits": asdict(self.limits), "datasets": [], "created_at": _now()}
        self.store.record(self.tenant_id, receipt)
        work = Path(tempfile.mkdtemp(prefix="atlas-m04-run-"))
        try:
            input_dir, output_dir = work / "input", work / "output"
            (input_dir / "data").mkdir(parents=True)
            output_dir.mkdir()
            (input_dir / ENTRYPOINTS[proposal.language]).write_text(proposal.code, encoding="utf-8")
            try:
                receipt["datasets"] = self._stage(proposal.dataset_urls, input_dir / "data")
            except Exception as exc:
                return self._finish(receipt, "infra_failed", error=f"dataset staging failed: {exc}")
            os.chmod(input_dir, 0o755)
            try:
                run = backend.run(language=proposal.language, input_dir=input_dir,
                                  output_dir=output_dir, limits=self.limits)
            except Exception as exc:
                return self._finish(receipt, "infra_failed", error=f"{type(exc).__name__}: {exc}")
            outputs, rejected = hash_outputs(output_dir, self.limits)
            for item in outputs:
                self.store.put_file(self.tenant_id, output_dir / item["path"], item["sha256"], item["bytes"])
            receipt.update({
                "isolation": run.isolation, "exit_code": run.exit_code, "timed_out": run.timed_out,
                "started_at": run.started_at, "finished_at": run.finished_at,
                "duration_seconds": run.duration_seconds,
                "stdout": {"sha256": self.store.put_bytes(self.tenant_id, run.stdout),
                           "bytes": len(run.stdout), "truncated": run.stdout_truncated},
                "stderr": {"sha256": self.store.put_bytes(self.tenant_id, run.stderr),
                           "bytes": len(run.stderr), "truncated": run.stderr_truncated},
                "outputs": outputs, "rejected_outputs": rejected})
            state = "timed_out" if run.timed_out else ("succeeded" if run.exit_code == 0 else "exited_nonzero")
            return self._finish(receipt, state)
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def _stage(self, urls: Iterable[str], data_dir: Path) -> list[dict[str, Any]]:
        staged, budget = [], self.limits.max_dataset_bytes
        for index, url in enumerate(urls):
            name = _dataset_name(index, url)
            meta = self.fetcher.fetch(url, data_dir / name, budget)
            budget -= int(meta["bytes"])
            staged.append({**meta, "path": f"/input/data/{name}"})
        return staged

    def _finish(self, receipt: dict[str, Any], state: str, error: str | None = None) -> dict[str, Any]:
        receipt = {**receipt, "receipt_id": str(uuid4()), "state": state}
        if error:
            receipt["error"] = error
        receipt.pop("manifest_sha256", None)
        receipt["manifest_sha256"] = _sha(_canonical(receipt).encode())
        self.store.record(self.tenant_id, receipt)
        return receipt

    def readback(self, approval_id: str) -> dict[str, Any]:
        receipt = self.store.latest(self.tenant_id, approval_id)
        if receipt is None:
            raise ExecutionNotFoundError(approval_id)
        return receipt

    def list_receipts(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.store.list(self.tenant_id, limit)

    def artifact(self, sha256: str) -> bytes:
        return self.store.read_artifact(self.tenant_id, sha256)


def verify_manifest(receipt: dict[str, Any]) -> bool:
    """Recompute the seal over a finished receipt."""
    body = {k: v for k, v in receipt.items() if k != "manifest_sha256"}
    return receipt.get("manifest_sha256") == _sha(_canonical(body).encode())


__all__ = ["ApprovedSandboxExecutor", "BubblewrapBackend", "DockerBackend", "ExecutionLimits",
           "ExecutionReceiptStore", "HttpDatasetFetcher", "SANDBOX_ACTION", "select_backend",
           "verify_manifest", "hash_outputs"]
