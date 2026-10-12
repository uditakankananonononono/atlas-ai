"""Row 75 / c31.adapter_runtime - standalone executable tool adapter.

This module is NOT wired into c31.integrate: integrate.select still emits its
NotImplementedError adapter stub, and nothing calls this runtime yet.

Runs an allowlisted local command. No shell, absolute executable path from a
supplied allowlist, scrubbed environment, paid tools refused. Timeout limits
the wait for the direct child; on expiry the child's process group is killed
(best effort: a descendant that left the group is not killed). Stdout and
stderr are read in chunks and at most MAX_OUT bytes of each are retained per
run; the rest is read and discarded. Reader threads are joined for at most
2s each, so output draining may be left unfinished if a descendant holds the
pipes; those daemon threads are not force-closed. "truncated" reports
discarded bytes. Peak process memory is not measured. The "caller_marked_reviewed" flag is a caller
assertion that the spec was looked at; it is NOT owner permission and grants
no authority. The caller must hold real owner approval before calling run().
It executes locally only; it does not discover, download or install tools.
Stdlib only.
"""
from __future__ import annotations

import os
import subprocess
import threading

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
    if spec.get("caller_marked_reviewed") is not True:
        raise ValueError("ADAPTER_REFUSED_NOT_MARKED_REVIEWED:" + name)
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
    """Execute one allowlisted adapter the caller marked reviewed. Returns exit code, capped stdout/stderr
    and a timed_out flag. Raises ADAPTER_REFUSED_* on any spec violation."""
    if isinstance(allowlist, bool) or not isinstance(allowlist, (list, tuple, set, frozenset)):
        raise ValueError("ADAPTER_REFUSED_BAD_TYPE:allowlist")
    name, exe, args, timeout = _spec(spec, frozenset(allowlist))
    if not isinstance(stdin_text, str) or len(stdin_text) > MAX_OUT:
        raise ValueError("ADAPTER_REFUSED_BAD_TYPE:stdin")
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
    proc = subprocess.Popen([exe] + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env, shell=False, cwd="/tmp",
                            start_new_session=True)
    bufs = {"out": bytearray(), "err": bytearray()}
    over = {"out": False, "err": False}

    def pump(stream, key):
        while True:
            chunk = stream.read(8192)
            if not chunk:
                return
            room = MAX_OUT - len(bufs[key])
            if room > 0:
                bufs[key] += chunk[:room]
            if len(chunk) > room:
                over[key] = True  # drained and discarded, never stored

    def feed():
        try:
            proc.stdin.write(stdin_text.encode("utf-8"))
        except OSError:
            pass
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass

    threads = [threading.Thread(target=pump, args=(proc.stdout, "out"), daemon=True),
               threading.Thread(target=pump, args=(proc.stderr, "err"), daemon=True),
               threading.Thread(target=feed, daemon=True)]
    for t in threads:
        t.start()
    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, 9)
        except OSError:
            proc.kill()
        proc.wait()
    for t in threads:
        t.join(2.0)
    code = None if timed_out else proc.returncode
    out, err = bytes(bufs["out"]), bytes(bufs["err"])
    return {"adapter": name, "exit_code": code, "timed_out": timed_out,
            "stdout": out.decode("utf-8", "replace"),
            "stderr": err.decode("utf-8", "replace"),
            "truncated": over["out"] or over["err"],
            "drain_may_be_incomplete": any(t.is_alive() for t in threads),
            "scope": policy.scope(
                ["local execution of one allowlisted executable the caller marked reviewed (not owner permission)"],
                ["tool discovery", "download or install", "network control",
                 "arbitrary tool rebuild", "spend (refused)"],
                "supplied adapter spec and allowlist")}
