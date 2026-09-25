"""Subprocess sandbox: run a candidate feature's tests in isolation.

The candidate and its tests are written to a fresh temp dir and executed
with a scrubbed environment and a hard timeout. pytest is the runner.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from .plans import Candidate


@dataclass(frozen=True)
class SandboxResult:
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    workdir: str = ""


class SandboxRunner:
    def __init__(self, *, timeout_seconds: float = 120.0, keep_workdirs: bool = False) -> None:
        self.timeout_seconds = timeout_seconds
        self.keep_workdirs = keep_workdirs

    @staticmethod
    def _scrubbed_env() -> dict[str, str]:
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": "0",
               "HOME": tempfile.gettempdir(), "PYTHONDONTWRITEBYTECODE": "1"}
        for var in ("SYSTEMROOT", "WINDIR", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL"):
            if var in os.environ:
                env[var] = os.environ[var]
        return env

    def run(self, candidate: Candidate) -> SandboxResult:
        workdir = Path(tempfile.mkdtemp(prefix="atlas-si-sandbox-"))
        (workdir / "feature.py").write_text(candidate.code, encoding="utf-8")
        (workdir / "test_feature.py").write_text(candidate.test_code, encoding="utf-8")
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider", str(workdir)],
                capture_output=True, text=True, timeout=self.timeout_seconds,
                env=self._scrubbed_env(), cwd=str(workdir),
            )
            duration = time.monotonic() - start
            return SandboxResult(
                passed=proc.returncode == 0, exit_code=proc.returncode,
                stdout=proc.stdout[-4000:], stderr=proc.stderr[-4000:],
                duration_seconds=round(duration, 3),
                workdir=str(workdir) if self.keep_workdirs else "",
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start
            return SandboxResult(
                passed=False, exit_code=-1, stdout=(exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
                stderr=f"timed out after {self.timeout_seconds}s",
                duration_seconds=round(duration, 3), timed_out=True,
                workdir=str(workdir) if self.keep_workdirs else "",
            )
        finally:
            if not self.keep_workdirs:
                import shutil
                shutil.rmtree(workdir, ignore_errors=True)
