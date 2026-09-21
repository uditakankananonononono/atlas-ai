"""Sandbox policy evaluation and ephemeral code execution (rows M20-18,
M20-21, M20-35).

The policy is deny-by-default: no network, no filesystem access outside the
calling project's volume, and third-party APIs only through an explicit
(method, host, path-prefix) allowlist. Path checks canonicalise through
``os.path.realpath`` so ``..`` segments and symlink escapes both fail.
Execution runs in a fresh subprocess with scrubbed environment, isolated
flags, and RLIMIT_CPU / RLIMIT_AS / RLIMIT_NOFILE resource ceilings; a
preamble disables the socket layer unless the policy grants network access
to the requested host.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
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
        safe = "".join(c for c in project_id if c.isalnum() or c in "-_")
        if not safe:
            raise SandboxViolation(["project id has no usable characters"])
        volume = os.path.join(self.workspace_root, safe)
        os.makedirs(volume, exist_ok=True)
        return os.path.realpath(volume)

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
        """Run Python in an ephemeral, resource-bounded subprocess."""
        if not code.strip():
            raise SandboxViolation(["empty program"])
        hosts = sorted(set(allowed_hosts or []))
        for host in hosts:
            reasons = self.check_host(host)
            if reasons:
                raise SandboxViolation(reasons)
        network = self.policy.network_enabled and bool(hosts)
        timeout = min(
            timeout_seconds or self.policy.max_runtime_seconds,
            self.policy.max_runtime_seconds,
        )
        volume = self.project_volume(project_id)
        preamble = _NETWORK_GUARD % {
            "hosts": tuple(hosts),
            "enable": _NETWORK_ENABLE if network else _NETWORK_DISABLE,
        }
        start = time.monotonic()
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", dir=volume, delete=False, encoding="utf-8",
        ) as handle:
            handle.write(preamble + "\n" + code)
            program = handle.name
        try:
            process = subprocess.Popen(
                [sys.executable, "-I", "-S", program],
                cwd=volume,
                env={"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": "0"},
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, preexec_fn=self._limits if os.name == "posix" else None,
            )
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                timed_out = False
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                timed_out = True
            return SandboxRunResult(
                returncode=process.returncode if process.returncode is not None else -1,
                stdout=(stdout or "")[: self.max_output_bytes],
                stderr=(stderr or "")[: self.max_output_bytes],
                timed_out=timed_out,
                duration_seconds=round(time.monotonic() - start, 4),
                network_used=network,
            )
        finally:
            os.unlink(program)

    @staticmethod
    def _limits() -> None:
        """preexec_fn: resource ceilings inside the child."""
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
