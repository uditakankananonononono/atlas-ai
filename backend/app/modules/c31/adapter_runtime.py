"""Row 75 / c31.adapter_runtime - executable tool adapter (replaces the
NotImplementedError stub path of c31.integrate for reviewed tools).

Runs an owner-reviewed, allowlisted local command as an adapter. No shell,
absolute executable path from a supplied allowlist, scrubbed environment,
wall-clock timeout, output cap, paid tools refused. It executes locally
only; it does not discover, download or install tools. Stdlib only.
"""
from __future__ import annotations

import os
import subprocess

from app.modules.c30 import policy

PREFIX = "ADAPTER"
MAX_ARGS = 32
MAX_OUT = 65536
MAX_TIMEOUT = 30.0


def _spec(spec, allowlist):
    if not isinstance(spec, dict):
        raise ValueError("ADAPTER_REFUSED_BAD_TYPE:spec")
    name = policy.clean_text(spec.get("name"), PREFIX, "name", 64)
    if bool(spec.get("paid", False)):
        raise ValueError("ADAPTER_REFUSED_SPEND:" + name)
    if spec.get("reviewed") is not True:
        raise ValueError("ADAPTER_REFUSED_UNREVIEWED:" + name)
    exe = policy.clean_text(spec.get("executable"), PREFIX, "executable", 512)
    if not os.path.isabs(exe) or exe not in allowlist:
        raise ValueError("ADAPTER_REFUSED_NOT_ALLOWLISTED:" + name)
    if not os.path.isfile(exe) or not os.access(exe, os.X_OK):
        raise ValueError("ADAPTER_REFUSED_NOT_EXECUTABLE:" + name)
    args = spec.get("args", [])
    if isinstance(args, bool) or not isinstance(args, (list, tuple)) or len(args) > MAX_ARGS:
        raise ValueError("ADAPTER_REFUSED_BAD_TYPE:args")
    args = [policy.clean_text(a, PREFIX, "arg", 1024, allow_blank=True) for a in args]
    timeout = spec.get("timeout", 10.0)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) \
            or not 0 < timeout <= MAX_TIMEOUT:
        raise ValueError("ADAPTER_REFUSED_BAD_TYPE:timeout")
    return name, exe, args, float(timeout)


def run(spec, allowlist, stdin_text=""):
    """Execute one reviewed adapter. Returns exit code, capped stdout/stderr
    and a timed_out flag. Raises ADAPTER_REFUSED_* on any spec violation."""
    if isinstance(allowlist, bool) or not isinstance(allowlist, (list, tuple, set, frozenset)):
        raise ValueError("ADAPTER_REFUSED_BAD_TYPE:allowlist")
    name, exe, args, timeout = _spec(spec, frozenset(allowlist))
    if not isinstance(stdin_text, str) or len(stdin_text) > MAX_OUT:
        raise ValueError("ADAPTER_REFUSED_BAD_TYPE:stdin")
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
    try:
        p = subprocess.run([exe] + args, input=stdin_text.encode("utf-8"),
                           capture_output=True, timeout=timeout, env=env,
                           shell=False, cwd="/tmp")
        out, err, code, timed_out = p.stdout, p.stderr, p.returncode, False
    except subprocess.TimeoutExpired as e:
        out, err, code, timed_out = e.stdout or b"", e.stderr or b"", None, True
    return {"adapter": name, "exit_code": code, "timed_out": timed_out,
            "stdout": out[:MAX_OUT].decode("utf-8", "replace"),
            "stderr": err[:MAX_OUT].decode("utf-8", "replace"),
            "scope": policy.scope(
                ["local execution of one reviewed allowlisted executable"],
                ["tool discovery", "download or install", "network control",
                 "arbitrary tool rebuild", "spend (refused)"],
                "supplied adapter spec and allowlist")}
