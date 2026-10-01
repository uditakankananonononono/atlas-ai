"""Reproduction of the defect with the real native package: SIGKILL after the
effect and before state is saved replays the effect (fake counter 1 -> 2)."""
import json, os, subprocess, sys
from pathlib import Path

WORKER = str(Path(__file__).with_name("effect_worker.py"))


def worker(tmp, cmd, *extra, crash="", tenant="t1"):
    env = dict(os.environ, EFFECT_CRASH=crash)
    p = subprocess.run([sys.executable, WORKER, str(tmp / "atlas.sqlite"), str(tmp / "counter"),
                        tenant, cmd, *extra], env=env, capture_output=True, text=True, timeout=60)
    return p


def counter(tmp):
    f = tmp / "counter"
    return int(f.read_text() or 0) if f.exists() else 0


def test_sigkill_after_effect_must_not_replay_counter(tmp_path):
    task = json.loads(worker(tmp_path, "submit").stdout)["task_id"]
    crashed = worker(tmp_path, "run", task, crash="after_effect")
    assert crashed.returncode == -9
    assert counter(tmp_path) == 1
    worker(tmp_path, "run", task)          # restart / second worker
    assert counter(tmp_path) == 1, "effect replayed after restart (1 -> 2)"
