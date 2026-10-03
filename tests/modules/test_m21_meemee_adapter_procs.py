import json, os, subprocess, sys, pathlib
H = str(pathlib.Path(__file__).with_name("meemee_adapter_proc.py"))

def run(d, *args, **extra):
    env = dict(os.environ, ATLAS_DATABASE_URL=f"sqlite:///{d}/atlas.db", ATLAS_AUTO_CREATE_SCHEMA="1", **extra)
    p = subprocess.Popen([sys.executable, H, str(d), *args], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p

def done(p):
    o, e = p.communicate(timeout=60)
    if p.returncode == 137:
        return {"crashed": True}
    assert p.returncode == 0, e
    return json.loads(o.strip().splitlines()[-1]) if o.strip().startswith("{") or "{" in o else o.strip()

def effects(d):
    f = d / "effects.log"
    return f.read_text().split() if f.exists() else []

def test_restart_replay_and_changed_action(tmp_path):
    assert done(run(tmp_path, "setup"))
    r1 = done(run(tmp_path, "exec", "k1", "ls")); assert r1["ok"] and not r1["replayed"]
    r2 = done(run(tmp_path, "exec", "k1", "ls")); assert r2["ok"] and r2["replayed"] and r2["status"] == "completed"  # new process
    r3 = done(run(tmp_path, "exec", "k1", "rm x")); assert not r3["ok"]  # same key, changed action
    r4 = done(run(tmp_path, "exec", "k2", "ls")); assert not r4["ok"] and "already used" in r4["err"]  # approval replay, new key
    assert effects(tmp_path) == ["ls"]

def test_concurrent_processes_one_effect(tmp_path):
    done(run(tmp_path, "setup"))
    ps = [run(tmp_path, "exec", "k1", "ls") for _ in range(6)]
    rs = [done(p) for p in ps]
    assert effects(tmp_path) == ["ls"]
    assert sum(1 for r in rs if r["ok"] and not r["replayed"]) == 1
    assert all(r["ok"] for r in rs)

def test_concurrent_different_keys_same_approval_only_one_wins(tmp_path):
    done(run(tmp_path, "setup"))
    ps = [run(tmp_path, "exec", f"k{i}", "ls") for i in range(1, 5)]
    rs = [done(p) for p in ps]
    assert effects(tmp_path) == ["ls"]
    assert sum(1 for r in rs if r["ok"] and not r["replayed"]) == 1


def chain_ok(d):
    import sqlite3
    rows = sqlite3.connect(d / "m.db").execute("SELECT sequence,previous_hash,event_hash FROM claire_adapter_audit ORDER BY sequence").fetchall()
    prev = "0" * 64
    for i, (seq, ph, eh) in enumerate(rows, 1):
        assert seq == i and ph == prev
        prev = eh
    return len(rows)

import pytest

@pytest.mark.parametrize("point,effects_n,status", [
    ("after_claim", 0, "indeterminate"),
    ("after_issue", 0, "indeterminate"),
    ("after_update", 0, "issued"),
    ("after_transport", 1, "issued"),
    ("mid_audit", 0, None),
])
def test_real_crash_points_fail_closed(tmp_path, point, effects_n, status):
    done(run(tmp_path, "setup"))
    r = done(run(tmp_path, "exec", "k1", "ls", ADAPTER_CRASH_AT=point))
    assert r == {"crashed": True}
    r2 = done(run(tmp_path, "exec", "k1", "ls"))  # fresh process, same key + same approval
    assert r2["ok"] and r2["replayed"]
    if status:
        assert r2["status"] == status
    assert len(effects(tmp_path)) == effects_n  # the retry never produced a second effect
    chain_ok(tmp_path)
    r3 = done(run(tmp_path, "exec", "k9", "ls"))
    assert not r3["ok"] and "already used" in r3["err"]  # consumed approval cannot be replayed

def test_replay_without_authorizing_approval_cannot_read_result(tmp_path):
    done(run(tmp_path, "setup"))
    assert done(run(tmp_path, "exec", "k1", "ls"))["ok"]
    r = done(run(tmp_path, "exec", "k1", "ls", NO_TOKEN="1"))
    assert not r["ok"] and "requires the approval" in r["err"]
