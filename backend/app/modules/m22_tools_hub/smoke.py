"""Sandboxed smoke-run of an installed tool's entrypoint.

The smoke-run answers one question with evidence: does the installed code load
in isolation? It copies the installed tool read-only into ``/input/tool``, writes
a small harness as the runner's entrypoint, and runs it with no network, a
cleared environment, a read-only system, tmpfs ``/tmp`` and rlimits. The harness
writes ``/output/smoke.json`` (imports/requires the entrypoint and records what
loaded); stdout/stderr are captured with hashes.

Backend interface
-----------------
``SmokeBackend.run(language=..., input_dir=..., output_dir=..., limits=...)``
deliberately matches ``SandboxBackend`` in the M4 approved sandbox (PB8, branch
pb8). ``select_smoke_backend`` prefers M4's backend for Python once that module
is merged (imported lazily, so nothing here depends on unmerged code) and uses
the bundled ``BwrapSmokeBackend`` otherwise, and always for Node (M4 runs
python and r only). M4 runs ``/input/analysis.py``; the harness is written under
that name and also under ``smoke_main.*`` for the bundled backend.
"""
from __future__ import annotations

import hashlib
import json
import os
import resource
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Protocol


class SmokeError(RuntimeError):
    pass


@dataclass(frozen=True)
class SmokeLimits:
    timeout_seconds: int = 60
    memory_mb: int = 1024
    cpus: float = 1.0
    pids: int = 64
    max_file_mb: int = 64
    max_log_bytes: int = 256 * 1024
    max_output_files: int = 20
    max_output_bytes: int = 4 * 1024 * 1024
    max_dataset_bytes: int = 0


@dataclass
class SmokeRun:
    backend: str
    isolation: dict[str, Any]
    exit_code: int | None
    timed_out: bool
    stdout: bytes
    stderr: bytes
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0


class SmokeBackend(Protocol):
    name: str

    def available(self, language: str = "python") -> bool: ...

    def run(self, *, language: str, input_dir: Path, output_dir: Path, limits: Any) -> Any: ...


HARNESS_NAMES = {"python": ("smoke_main.py", "analysis.py"), "node": ("smoke_main.js",)}

PY_HARNESS = r'''
import importlib, json, sys, traceback, runpy
entry = sys.argv[1] if len(sys.argv) > 1 else %(entry)r
sys.path.insert(0, "/input/tool")
result = {"language": "python", "entrypoint": entry, "python": sys.version.split()[0]}
try:
    if entry.endswith("/__init__.py") or (entry.endswith(".py") and "/" not in entry):
        name = entry[:-len("/__init__.py")] if entry.endswith("/__init__.py") else entry[:-3]
        mod = importlib.import_module(name.replace("/", "."))
        result.update(mode="import", module=name, file=getattr(mod, "__file__", None),
                      version=str(getattr(mod, "__version__", "")) or None,
                      public_names=sorted(n for n in dir(mod) if not n.startswith("_"))[:50])
    elif entry.endswith(".py"):
        runpy.run_path("/input/tool/" + entry, run_name="atlas_smoke")
        result.update(mode="run_path")
    else:
        with open("/input/tool/" + entry, "rb") as fh:
            result.update(mode="read", bytes=len(fh.read()))
    result["ok"] = True
except BaseException as exc:
    result.update(ok=False, error=type(exc).__name__ + ": " + str(exc)[:500],
                  traceback=traceback.format_exc()[-2000:])
with open("/output/smoke.json", "w") as fh:
    json.dump(result, fh)
print("ATLAS_SMOKE", "ok" if result["ok"] else "failed")
'''

NODE_HARNESS = r'''
const fs = require("fs");
const entry = %(entry)s;
const result = {language: "node", entrypoint: entry, node: process.version};
try {
  if (entry.endsWith(".js") || entry.endsWith(".cjs")) {
    const mod = require("/input/tool/" + entry);
    result.mode = "require";
    result.export_type = typeof mod;
    result.public_names = mod && typeof mod === "object" ? Object.keys(mod).slice(0, 50) : [];
  } else {
    result.mode = "read";
    result.bytes = fs.readFileSync("/input/tool/" + entry).length;
  }
  result.ok = true;
} catch (e) {
  result.ok = false;
  result.error = String(e && e.stack || e).slice(0, 2000);
}
fs.writeFileSync("/output/smoke.json", JSON.stringify(result));
console.log("ATLAS_SMOKE", result.ok ? "ok" : "failed");
'''


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BwrapSmokeBackend:
    """Bundled bubblewrap runner: no network, cleared env, read-only system, rlimits."""

    name = "bubblewrap-smoke"
    INTERPRETERS = {"python": ["/usr/bin/python3", "-I", "-B"], "node": ["/usr/bin/node"]}

    def __init__(self, bwrap: str | None = None) -> None:
        self.bwrap = bwrap or shutil.which("bwrap")

    def available(self, language: str = "python") -> bool:
        interp = self.INTERPRETERS.get(language)
        return bool(self.bwrap) and bool(interp) and Path(interp[0]).exists()

    def _system_mounts(self) -> list[str]:
        args = ["--ro-bind", "/usr", "/usr"]
        for top in ("lib", "lib64", "lib32", "bin", "sbin"):
            host = Path("/") / top
            if host.is_symlink():
                args += ["--symlink", os.readlink(host), f"/{top}"]
            elif host.exists():
                args += ["--ro-bind", str(host), f"/{top}"]
        for path in ("/etc/alternatives", "/etc/ld.so.cache", "/etc/localtime", "/etc/ssl/certs"):
            args += ["--ro-bind-try", path, path]
        return args

    def command(self, language: str, input_dir: Path, output_dir: Path) -> list[str]:
        return [self.bwrap or "bwrap", "--unshare-all", "--die-with-parent", "--new-session",
                *self._system_mounts(), "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                "--ro-bind", str(input_dir), "/input", "--bind", str(output_dir), "/output",
                "--chdir", "/tmp", "--clearenv", "--setenv", "PATH", "/usr/bin:/bin",
                "--setenv", "HOME", "/tmp", "--setenv", "LANG", "C.UTF-8",
                *self.INTERPRETERS[language], f"/input/{HARNESS_NAMES[language][0]}"]

    def run(self, *, language: str, input_dir: Path, output_dir: Path, limits: Any) -> SmokeRun:
        if not self.available(language):
            raise SmokeError(f"bubblewrap or the {language} interpreter is not installed")
        mem = limits.memory_mb * 1024 * 1024
        fsize = limits.max_file_mb * 1024 * 1024
        cpu = max(1, int(limits.timeout_seconds * max(limits.cpus, 1)))
        # Node reserves large virtual address space; bound it by CPU/time/files instead of RLIMIT_AS.
        cap_as = language != "node"

        def preexec() -> None:
            if cap_as:
                resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
            resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

        logs = Path(tempfile.mkdtemp(prefix="atlas-smoke-logs-"))
        started, t0 = _now(), time.monotonic()
        try:
            with (logs / "out").open("wb") as out, (logs / "err").open("wb") as err:
                proc = subprocess.Popen(self.command(language, input_dir, output_dir), stdout=out, stderr=err,
                                        stdin=subprocess.DEVNULL, start_new_session=True, preexec_fn=preexec,
                                        close_fds=True)
                try:
                    code, timed_out = proc.wait(timeout=limits.timeout_seconds), False
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    proc.wait(); code, timed_out = None, True
            data = {}
            for key in ("out", "err"):
                raw = (logs / key).read_bytes()
                data[key] = (raw[:limits.max_log_bytes], len(raw) > limits.max_log_bytes)
        finally:
            shutil.rmtree(logs, ignore_errors=True)
        return SmokeRun(
            backend=self.name,
            isolation={"network": "none (network namespace)", "namespaces": "user,pid,ipc,uts,net,cgroup",
                       "filesystem": "read-only system and /input, tmpfs /tmp, writable /output only",
                       "environment": "cleared",
                       "rlimits": {"address_space_mb": limits.memory_mb if cap_as else None,
                                   "cpu_seconds": cpu, "file_size_mb": limits.max_file_mb}},
            exit_code=code, timed_out=timed_out, stdout=data["out"][0], stderr=data["err"][0],
            stdout_truncated=data["out"][1], stderr_truncated=data["err"][1],
            started_at=started, finished_at=_now(), duration_seconds=round(time.monotonic() - t0, 3))


def m4_backend(language: str) -> Any | None:
    """M4's sandbox backend for Python when the M4 approved-sandbox module is present."""
    if language != "python" or os.getenv("ATLAS_SMOKE_BACKEND", "auto") == "bundled":
        return None
    try:
        from app.modules.m04_research_scientist.approved_sandbox import select_backend  # type: ignore
    except ImportError:
        return None
    try:
        backend = select_backend(os.getenv("ATLAS_SANDBOX_BACKEND"))
    except Exception:
        return None
    return backend if backend.available(language) else None


def select_smoke_backend(language: str) -> SmokeBackend:
    backend = m4_backend(language)
    if backend is not None:
        return backend
    bundled = BwrapSmokeBackend()
    if bundled.available(language):
        return bundled
    raise SmokeError(f"no sandbox available for {language}: install bubblewrap (or merge the M4 runner)")


def language_for(manifest_metadata: dict[str, Any], entrypoint: str) -> str:
    if manifest_metadata.get("registry") == "npm" or entrypoint.endswith((".js", ".cjs")):
        return "node"
    return "python"


def smoke_run(installed_path: str | Path, entrypoint: str, *, language: str,
              backend: SmokeBackend | None = None, limits: Any = None) -> dict[str, Any]:
    """Run the harness against an installed tool; returns an evidence record."""
    installed = Path(installed_path).resolve()
    if not installed.is_dir():
        raise SmokeError("installed tool directory is missing")
    rel = PurePosixPath(entrypoint)
    if rel.is_absolute() or ".." in rel.parts or not (installed / entrypoint).is_file():
        raise SmokeError("entrypoint is not a file inside the installed tool")
    backend = backend or select_smoke_backend(language)
    limits = limits or SmokeLimits()
    work = Path(tempfile.mkdtemp(prefix="atlas-smoke-"))
    try:
        input_dir, output_dir = work / "input", work / "output"
        output_dir.mkdir(parents=True)
        shutil.copytree(installed, input_dir / "tool", symlinks=False)
        harness = (PY_HARNESS % {"entry": entrypoint}) if language == "python" else (NODE_HARNESS % {"entry": json.dumps(entrypoint)})
        for name in HARNESS_NAMES[language]:
            (input_dir / name).write_text(harness, encoding="utf-8")
        run = backend.run(language=language, input_dir=input_dir, output_dir=output_dir, limits=limits)
        result_path = output_dir / "smoke.json"
        result = None
        if result_path.is_file() and result_path.stat().st_size <= 1024 * 1024:
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                result = None
    finally:
        shutil.rmtree(work, ignore_errors=True)
    stdout, stderr = bytes(run.stdout or b""), bytes(run.stderr or b"")
    passed = bool(result and result.get("ok")) and run.exit_code == 0 and not run.timed_out
    return {
        "passed": passed, "language": language, "entrypoint": entrypoint, "backend": run.backend,
        "isolation": run.isolation, "exit_code": run.exit_code, "timed_out": run.timed_out,
        "result": result, "stdout": stdout.decode("utf-8", "replace")[:4000],
        "stderr": stderr.decode("utf-8", "replace")[:4000],
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(), "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "started_at": run.started_at, "finished_at": run.finished_at, "duration_seconds": run.duration_seconds,
        "claim": "entrypoint loaded in an isolated no-network sandbox" if passed else "entrypoint did not load cleanly in the sandbox; see result/stderr",
    }
