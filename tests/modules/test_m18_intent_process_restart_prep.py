"""ATLAS-4: AUTHORED NOT RUN. Actual child interpreters, no external fetch.

Phase faults model persisted restart boundaries, not power loss. Only the
opt-in IntentBoundHostRateLimiter is covered; no global collector binding claim.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import pytest
from app.modules.m18_side_hustle_scraper.dispatch_intent import (
    DispatchIntentWAL, IntentBoundHostRateLimiter,
)
from app.modules.m18_side_hustle_scraper.durable_rate_limiter import DurableHostRateLimiter
from app.modules.m18_side_hustle_scraper.lane_rate_limit_state import StateRejected

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)
TENANT = "restart-canary-tenant"
HOST = "pending.example.test"
OTHER = "other.example.test"

# Executed only when the peer runs tests, never during PREP authoring.
CHILD = r'''
from datetime import datetime
import json, os, sys
from pathlib import Path
from app.modules.m18_side_hustle_scraper.dispatch_intent import DispatchIntentWAL, IntentBoundHostRateLimiter
from app.modules.m18_side_hustle_scraper.durable_rate_limiter import DurableHostRateLimiter
from app.modules.m18_side_hustle_scraper.lane_rate_limit_state import StateRejected

config = json.load(sys.stdin)
root = Path(config["root"])
now = datetime.fromisoformat(config["now"])
tenant, host, other = config["tenant"], config["host"], config["other"]
wal = DispatchIntentWAL(root, tenant)
initial = wal.path.read_bytes()
expected = config["pending"]
assert wal.read()["pending"] == expected
limiter = IntentBoundHostRateLimiter(root, tenant, clock=lambda: now)
pacing_initial = limiter._path.read_bytes()
assert wal.path.read_bytes() == initial, "startup changed pending WAL"
assert limiter._path.read_bytes() == pacing_initial

if config["mutation"]:
    # Deliberately wrong startup/dispatch interpretation, real subprocess only.
    # No product-source rewrite. Removes the pending gate from this child's class.
    IntentBoundHostRateLimiter._guard = DurableHostRateLimiter._guard

if config["mode"] == "probe":
    denied = []
    for target in (other, host):
        operations = [
            ("check", lambda: limiter.check(target)),
            ("begin", lambda: limiter.begin_request(target)),
            ("record", lambda: limiter.record_request(target)),
            ("failure", lambda: limiter.record_failure(target, ("http error", 429))),
            ("retry", lambda: limiter.honor_retry_after(target, 120)),
            ("success", lambda: limiter.record_success(target)),
        ]
        for name, operation in operations:
            try:
                operation()
            except StateRejected:
                denied.append([target, name])
            else:
                raise AssertionError("pending ignored: " + target + "/" + name)
            assert wal.read()["pending"] == expected
            assert wal.path.read_bytes() == initial, "denial modified WAL"
            assert limiter._path.read_bytes() == pacing_initial, "denial modified pacing"
    print(json.dumps({"mode": "probe", "pid": os.getpid(), "denied": denied,
                      "pending": wal.read()["pending"]}, sort_keys=True))
else:
    assert config["mode"] == "ack"
    wrong = dict(expected)
    wrong["id"] = ("0" if expected["id"][0] != "0" else "1") + expected["id"][1:]
    attempts = [
        ("wrong-intent", wrong, {"operator_inspected": True}),
        ("omitted-grant", expected, {}),
        ("false-grant", expected, {"operator_inspected": False}),
        ("integer-grant", expected, {"operator_inspected": 1}),
    ]
    refused = []
    for name, intent, grant in attempts:
        try:
            wal.acknowledge_inspected(intent, **grant)
        except StateRejected:
            refused.append(name)
        else:
            raise AssertionError("invalid ack accepted: " + name)
        assert wal.path.read_bytes() == initial
        assert limiter._path.read_bytes() == pacing_initial
    wal.acknowledge_inspected(expected, operator_inspected=True)
    assert wal.read()["pending"] is None
    assert wal.read()["revision"] == config["revision"] + 1
    assert limiter._path.read_bytes() == pacing_initial, "ack rewrote saved pacing"
    wait = limiter.check(host)
    assert wait == config["expected_wait"]
    if config["expected_wait"] > 0:
        assert limiter.begin_request(host) == config["expected_wait"]
        assert limiter._path.read_bytes() == pacing_initial
        assert wal.read()["pending"] is None
    # A NEW request on another host is permitted, not a replay of the old intent.
    assert limiter.begin_request(other) == 0.0
    assert wal.read()["pending"] is None
    assert wal.read()["revision"] == config["revision"] + 3
    assert limiter.check(host) == config["expected_wait"]
    print(json.dumps({"mode": "ack", "pid": os.getpid(), "refused": refused,
                      "wait": wait, "pending": wal.read()["pending"]}, sort_keys=True))
'''


def _prepare(root, phase, monkeypatch):
    wal = DispatchIntentWAL(root, TENANT)
    wal.provision()
    DurableHostRateLimiter(root, TENANT, bootstrap=True, clock=lambda: NOW)
    limiter = IntentBoundHostRateLimiter(root, TENANT, clock=lambda: NOW)
    pacing_path = limiter._path
    if phase == "before_snapshot":
        pending = wal.begin(HOST, NOW)
        expected_wait = 0.0
    else:
        assert phase == "after_snapshot"
        def refuse_completion(intent):
            raise StateRejected("phase boundary after snapshot")
        # Snapshot really writes; only completion is refused in the parent.
        with monkeypatch.context() as context:
            context.setattr(limiter.intent_wal, "_complete", refuse_completion)
            with pytest.raises(StateRejected, match="phase boundary"):
                limiter.begin_request(HOST)
        pending = wal.read()["pending"]
        expected_wait = limiter.policy.min_request_interval_seconds
        payload = json.loads(pacing_path.read_bytes())["payload"]
        assert payload["states"][HOST]["last_request_at"] == NOW.isoformat()
        assert payload["states"][HOST]["total_requests"] == 1
    saved = wal.read()
    assert saved["pending"] == pending
    # Children receive only serialized facts and paths, no limiter/WAL object.
    config = {"root": str(root.resolve()), "tenant": TENANT, "now": NOW.isoformat(),
              "host": HOST, "other": OTHER, "pending": pending,
              "revision": saved["revision"], "expected_wait": expected_wait}
    return wal.path, pacing_path, config


def _child(config, mode, *, mutation=False):
    # Do not copy parent environment or any credentials. Absolute executable.
    return subprocess.run(
        [sys.executable, "-c", CHILD], input=json.dumps({**config, "mode": mode, "mutation": mutation}),
        cwd=REPO, env={"PYTHONPATH": str(REPO / "backend"), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=30, check=False,
    )


@pytest.mark.parametrize("phase", ["before_snapshot", "after_snapshot"])
def test_second_interpreter_pending_denial_and_exact_ack(tmp_path, monkeypatch, phase):
    wal_path, pacing_path, config = _prepare(tmp_path, phase, monkeypatch)
    pending_raw, pacing_raw = wal_path.read_bytes(), pacing_path.read_bytes()
    probe = _child(config, "probe")
    assert probe.returncode == 0, (probe.returncode, probe.stdout, probe.stderr)
    assert probe.stderr == ""
    report = json.loads(probe.stdout)
    assert report["mode"] == "probe"
    assert report["pending"] == config["pending"]
    assert report["denied"] == [[target, action] for target in (OTHER, HOST)
                                for action in ("check", "begin", "record", "failure", "retry", "success")]
    import os
    assert report["pid"] != os.getpid()
    assert wal_path.read_bytes() == pending_raw
    assert pacing_path.read_bytes() == pacing_raw
    ack = _child(config, "ack")
    assert ack.returncode == 0, (ack.returncode, ack.stdout, ack.stderr)
    assert ack.stderr == ""
    accepted = json.loads(ack.stdout)
    assert accepted["mode"] == "ack" and accepted["pid"] != os.getpid()
    assert accepted["refused"] == ["wrong-intent", "omitted-grant", "false-grant", "integer-grant"]
    assert accepted["wait"] == config["expected_wait"] and accepted["pending"] is None
    final = json.loads(wal_path.read_bytes())["state"]
    assert final["pending"] is None and final["revision"] == config["revision"] + 3
    snapshot = json.loads(pacing_path.read_bytes())["payload"]
    assert snapshot["tenant_id"] == TENANT
    assert snapshot["states"][OTHER]["last_request_at"] == NOW.isoformat()
    if phase == "after_snapshot":
        assert snapshot["states"][HOST] == json.loads(pacing_raw)["payload"]["states"][HOST]


@pytest.mark.parametrize("phase", ["before_snapshot", "after_snapshot"])
def test_actual_child_mutation_ignores_pending_is_rejected(tmp_path, monkeypatch, phase):
    wal_path, pacing_path, config = _prepare(tmp_path, phase, monkeypatch)
    pending_raw, pacing_raw = wal_path.read_bytes(), pacing_path.read_bytes()
    mutant = _child(config, "probe", mutation=True)
    assert mutant.returncode != 0, "canary wrongly accepted ignored pending WAL"
    assert "AssertionError: pending ignored: " + OTHER + "/check" in mutant.stderr
    assert mutant.stdout == ""
    assert wal_path.read_bytes() == pending_raw
    assert pacing_path.read_bytes() == pacing_raw
