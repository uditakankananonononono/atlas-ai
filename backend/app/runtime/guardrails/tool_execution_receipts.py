"""Persistent evidence of real, explicitly registered trusted-local tool runs.

Not a sandbox or a service/API verifier. Registration is an operator action, not
owner approval. Untrusted executables must never be registered. No shell, no
inherited credentials, bounded captured output, process-group timeout cleanup.
Receipts count successful local invocations, not useful work or external truth.
The SQLite store is trusted local state, not a cryptographic authority boundary.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import signal
import sqlite3
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone

from .errors import GuardrailRefusal


def _fail(reason):
    raise ValueError("TOOLEXEC:" + reason)


def _name(value):
    if type(value) is not str or not value.strip() or len(value) > 128:
        _fail("bad_name")
    if value != value.strip() or any(ord(c) < 32 for c in value):
        _fail("bad_name")
    return value


def _hash(path):
    with open(path, "rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return digest


def _pins(paths):
    return {str(Path(path).absolute()): _hash(path) for path in paths}


def _same_pins(pins):
    try:
        return _pins(pins) == pins
    except OSError:
        return False


def _kill(proc):
    # Children remaining in the new session's process group are also killed.
    # A hostile descendant can create another session; this is not containment.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait(timeout=5)


class ExecutionStore:
    """Operator-managed registry and durable local execution receipts.

    Separate connections may append concurrently via SQLite transactions. There
    is no API for accepting caller-authored success receipts or verifier labels.
    Anyone with write access to this database can forge its contents.
    """
    def __init__(self, path):
        if os.name != "posix":
            _fail("posix_required")
        self._db = sqlite3.connect(path, timeout=10)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS registrations (
                project TEXT NOT NULL, name TEXT NOT NULL, spec TEXT NOT NULL,
                PRIMARY KEY(project,name));
            CREATE TABLE IF NOT EXISTS receipts (
                id TEXT PRIMARY KEY, project TEXT NOT NULL, identity TEXT NOT NULL,
                status TEXT NOT NULL, receipt TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS receipt_count ON receipts(project,status,identity);
        """)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self._db.close()

    def register(self, project, name, argv, *, inputs=(), timeout=30, output_limit=1048576):
        """Pin an approved local command and its operator-declared dependencies.

        Files hidden in imports, configs, libraries or network responses are not
        discovered automatically. All execution is trusted-local, never sandboxed.
        """
        project, name = _name(project), _name(name)
        if type(argv) is not list or not argv or len(argv) > 128:
            _fail("bad_argv")
        if any(type(a) is not str or not a or "\x00" in a or len(a) > 4096 for a in argv):
            _fail("bad_argv")
        if not Path(argv[0]).is_absolute():
            _fail("absolute_executable_required")
        exe = str(Path(argv[0]).resolve(strict=True))
        if not Path(exe).is_file() or not os.access(exe, os.X_OK):
            _fail("not_executable")
        if type(inputs) not in (tuple, list) or len(inputs) > 128:
            _fail("bad_inputs")
        if any(type(p) is not str or not Path(p).is_absolute() for p in inputs):
            _fail("absolute_inputs_required")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 300:
            _fail("bad_timeout")
        if type(output_limit) is not int or not 1 <= output_limit <= 16777216:
            _fail("bad_output_limit")
        pins = _pins([exe, *inputs])
        # Identity excludes aliases, project names and argument spelling.
        # Equal executable+declared dependency bytes count once per project.
        identity = hashlib.sha256(json.dumps(sorted(set(pins.values()))).encode()).hexdigest()
        spec = {"argv": [exe, *argv[1:]], "pins": pins, "timeout": timeout,
                "output_limit": output_limit, "identity": identity}
        try:
            with self._db:
                self._db.execute("INSERT INTO registrations VALUES(?,?,?)",
                                 (project, name, json.dumps(spec, sort_keys=True)))
        except sqlite3.IntegrityError:
            _fail("already_registered")
        return identity

    def execute(self, project, name):
        project, name = _name(project), _name(name)
        row = self._db.execute("SELECT spec FROM registrations WHERE project=? AND name=?",
                               (project, name)).fetchone()
        if not row:
            _fail("unregistered")
        spec = json.loads(row[0])
        if not _same_pins(spec["pins"]):
            _fail("pin_changed")
        start = time.monotonic()
        started = datetime.now(timezone.utc).isoformat()
        hashes = {"stdout": hashlib.sha256(), "stderr": hashlib.sha256()}
        sizes = {"stdout": 0, "stderr": 0}
        status, returncode = "failed", None
        # Temporary working directory reduces accidental cross-project reads.
        # Absolute input paths and executable filesystem access remain available.
        with tempfile.TemporaryDirectory(prefix="atlas-tool-") as work:
            try:
                proc = subprocess.Popen(spec["argv"], cwd=work,
                    env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": work,
                         "TMPDIR": work}, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            except OSError:
                status = "spawn_failed"
            else:
                try:
                    with selectors.DefaultSelector() as selector:
                        for label in hashes:
                            pipe = getattr(proc, label)
                            os.set_blocking(pipe.fileno(), False)
                            selector.register(pipe, selectors.EVENT_READ, label)
                        status = "succeeded"
                        while selector.get_map():
                            remaining = spec["timeout"] - (time.monotonic() - start)
                            if remaining <= 0:
                                status = "timeout"
                                break
                            for key, _ in selector.select(min(.05, remaining)):
                                # Read at most one extra byte to detect limit exceedance.
                                space = spec["output_limit"] - sum(sizes.values())
                                chunk = os.read(key.fileobj.fileno(), min(65536, space + 1))
                                if not chunk:
                                    selector.unregister(key.fileobj)
                                    continue
                                if len(chunk) > space:
                                    status = "output_limit"
                                    break
                                hashes[key.data].update(chunk)
                                sizes[key.data] += len(chunk)
                            if status != "succeeded":
                                break
                        if status == "succeeded":
                            remaining = spec["timeout"] - (time.monotonic() - start)
                            try:
                                returncode = proc.wait(timeout=max(.001, remaining))
                            except subprocess.TimeoutExpired:
                                status = "timeout"
                            else:
                                if returncode != 0:
                                    status = "failed"
                finally:
                    _kill(proc)
                    if returncode is None:
                        returncode = proc.returncode
                    proc.stdout.close()
                    proc.stderr.close()
        if status == "succeeded" and not _same_pins(spec["pins"]):
            status = "pin_changed"
        receipt = {"id": uuid.uuid4().hex, "project": project, "tool": name,
                   "identity": spec["identity"], "status": status, "returncode": returncode,
                   "started_at": started, "elapsed_seconds": time.monotonic() - start,
                   "stdout_sha256": hashes["stdout"].hexdigest(),
                   "stderr_sha256": hashes["stderr"].hexdigest(),
                   "stdout_bytes": sizes["stdout"], "stderr_bytes": sizes["stderr"],
                   "pins": spec["pins"], "tier": "trusted-local-execution"}
        with self._db:
            self._db.execute("INSERT INTO receipts VALUES(?,?,?,?,?)", (receipt["id"], project,
                spec["identity"], status, json.dumps(receipt, sort_keys=True)))
        return receipt

    def receipt(self, receipt_id):
        row = self._db.execute("SELECT receipt FROM receipts WHERE id=?", (receipt_id,)).fetchone()
        if not row:
            _fail("unknown_receipt")
        return json.loads(row[0])

    def evaluate(self, project, *, bar=200):
        project = _name(project)
        if type(bar) is not int or not 1 <= bar <= 100000:
            _fail("bad_bar")
        count = self._db.execute("SELECT COUNT(DISTINCT identity) FROM receipts "
            "WHERE project=? AND status='succeeded'", (project,)).fetchone()[0]
        return {"project": project, "bar": bar, "distinct_executed_tools": count,
                "shortfall": max(0, bar-count), "met": count >= bar,
                "tier": "trusted-local-execution"}

    def require_bar(self, project, *, bar=200):
        """Refuse a completion path lacking observed successful local runs.

        This is a tool-count condition only, not owner authorization for an
        outbound effect. Existing approval/egress gates remain independently
        required. No callback/effect API bypass is supplied here.
        """
        result = self.evaluate(project, bar=bar)
        if not result["met"]:
            raise GuardrailRefusal("TOOLEXEC:bar_unmet", "real local tool execution bar unmet",
                                   details=result)
        return result
