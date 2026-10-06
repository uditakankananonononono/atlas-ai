"""GCW execution through an OS isolation backend, never plain subprocess.

Reuses M4 bubblewrap/Docker no-network isolation. Project output is the
only writable host mount. Missing/unusable backends fail closed. Host and
API policy checks are planning checks, not permission for sandbox egress;
networked sandbox execution is deliberately unsupported.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .safety import SandboxPolicy


class SandboxViolation(PermissionError):
    def __init__(self, reasons: list[str]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = reasons


@dataclass(frozen=True)
class ApiAllowRule:
    """One allow-listed third-party API endpoint (row M20-22)."""

    method: str
    host: str
    path_prefix: str = "/"

    def allows(self, method: str, host: str, path: str) -> bool:
        return (
            self.method.upper() == method.upper()
            and host_matches(host, self.host)
            and path.startswith(self.path_prefix)
        )


def host_matches(host: str, rule: str) -> bool:
    """Exact host or one-level wildcard subdomain (``*.example.com``)."""
    host = host.lower().strip().rstrip(".")
    rule = rule.lower().strip().rstrip(".")
    if rule.startswith("*."):
        suffix = rule[1:]  # ".example.com"
        return host.endswith(suffix) and host != rule[2:]
    return host == rule


@dataclass
class SandboxRunResult:
    """Typed execution result for the trace and the dashboard."""

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float
    network_used: bool = False

    def as_dict(self) -> dict:
        return vars(self)


_NETWORK_GUARD = '''
import socket as _socket
_allowed_hosts = frozenset(%(hosts)r)

def _blocked(*args, **kwargs):
    raise PermissionError("sandbox: network access is disabled by policy")

class _GuardedSocket(_socket.socket):
    def connect(self, address):
        host = address[0] if isinstance(address, tuple) and address else ""
        if host not in _allowed_hosts:
            raise PermissionError(f"sandbox: host {host!r} is not on the API allowlist")
        return super().connect(address)

%(enable)s
'''

_NETWORK_DISABLE = """_socket.socket = _GuardedSocket
_socket.create_connection = _blocked
_socket.getaddrinfo = _blocked"""

_NETWORK_ENABLE = """_orig_create_connection = _socket.create_connection
def _guarded_create_connection(address, *args, **kwargs):
    host = address[0] if isinstance(address, tuple) and address else ""
    if host not in _allowed_hosts:
        raise PermissionError(f"sandbox: host {host!r} is not on the API allowlist")
    return _orig_create_connection(address, *args, **kwargs)
_socket.create_connection = _guarded_create_connection
_socket.socket = _GuardedSocket"""


class SandboxRunner:
    """Evaluates policy and runs code inside per-project volumes."""

    def __init__(
        self,
        policy: SandboxPolicy | None = None,
        *,
        workspace_root: str | None = None,
        api_allowlist: list[ApiAllowRule] | None = None,
        max_output_bytes: int = 64_000,
    ) -> None:
        self.policy = policy or SandboxPolicy()
        self.workspace_root = os.path.realpath(
            workspace_root or os.path.join(tempfile.gettempdir(), "atlas-gcw-sandbox")
        )
        self.api_allowlist = list(api_allowlist or [])
        self.max_output_bytes = max_output_bytes

    # -- policy evaluation -------------------------------------------------

    def project_volume(self, project_id: str) -> str:
        """Per-project volume (row M20-35), created on demand."""
        safe = project_id
        if not safe or any(not (c.isascii() and (c.isalnum() or c in "-_")) for c in safe):
            raise SandboxViolation(["project id must contain only ASCII letters, numbers, dash or underscore"])
        volume = os.path.join(self.workspace_root, safe)
        if os.path.lexists(volume) and os.path.islink(volume):
            raise SandboxViolation(["project volume must not be a symlink"])
        os.makedirs(volume, exist_ok=True)
        resolved = os.path.realpath(volume)
        if os.path.commonpath([self.workspace_root, resolved]) != self.workspace_root:
            raise SandboxViolation(["project volume escapes workspace"])
        return resolved

    def resolve_path(self, project_id: str, path: str) -> str:
        """Canonical containment check: rejects ``..`` and symlink escapes."""
        volume = self.project_volume(project_id)
        candidate = os.path.realpath(os.path.join(volume, path))
        if os.path.commonpath([volume, candidate]) != volume:
            raise SandboxViolation([f"path {path!r} escapes the project volume"])
        return candidate

    def check_host(self, host: str) -> list[str]:
        reasons: list[str] = []
        if not self.policy.network_enabled:
            reasons.append("network is disabled by sandbox policy")
        elif not any(host_matches(host, h) for h in self.policy.allowed_hosts) and not any(
            host_matches(host, r.host) for r in self.api_allowlist
        ):
            reasons.append(f"host {host!r} is not allow-listed")
        return reasons

    def check_api(self, method: str, host: str, path: str) -> list[str]:
        if not any(rule.allows(method, host, path) for rule in self.api_allowlist):
            return [f"no allowlist rule matches {method.upper()} {host}{path}"]
        return []

    # -- execution -----------------------------------------------------------

    def run_python(
        self,
        project_id: str,
        code: str,
        *,
        timeout_seconds: int | None = None,
        allowed_hosts: list[str] | None = None,
    ) -> SandboxRunResult:
        """Run Python with OS isolation and no network, or refuse execution."""
        from app.modules.m04_research_scientist.approved_sandbox import (
            select_backend, ExecutionLimits, BackendUnavailableError,
        )
        if not code.strip():
            raise SandboxViolation(["empty program"])
        if allowed_hosts:
            raise SandboxViolation(["networked sandbox execution is unsupported; no egress granted"])
        timeout = min(timeout_seconds or self.policy.max_runtime_seconds, self.policy.max_runtime_seconds)
        if timeout <= 0:
            raise SandboxViolation(["timeout must be positive"])
        volume = Path(self.project_volume(project_id))
        # No Python-only guards count as isolation. The legacy preamble is
        # retained for clear network errors, with the OS namespace enforcing it.
        preamble = _NETWORK_GUARD % {"hosts": (), "enable": _NETWORK_DISABLE}
        try:
            backend = select_backend()
            with tempfile.TemporaryDirectory(prefix="atlas-gcw-input-") as td:
                input_dir = Path(td)
                (input_dir / "analysis.py").write_text(preamble + "\n" + code, encoding="utf-8")
                result = backend.run(language="python", input_dir=input_dir, output_dir=volume,
                    limits=ExecutionLimits(timeout_seconds=timeout, memory_mb=512,
                        max_file_mb=8, max_log_bytes=self.max_output_bytes))
        except (BackendUnavailableError, OSError) as exc:
            raise SandboxViolation(["OS isolation backend unavailable; execution refused"]) from exc
        return SandboxRunResult(returncode=result.exit_code if result.exit_code is not None else -1,
            stdout=result.stdout.decode("utf-8", errors="replace"),
            stderr=result.stderr.decode("utf-8", errors="replace"),
            timed_out=result.timed_out, duration_seconds=result.duration_seconds, network_used=False)
