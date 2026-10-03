import json, os, subprocess, sys, pathlib
H = str(pathlib.Path(__file__).with_name("meemee_adapter_proc.py"))

def run(d, *args):
    env = dict(os.environ, ATLAS_DATABASE_URL=f"sqlite:///{d}/atlas.db", ATLAS_AUTO_CREATE_SCHEMA="1")
    p = subprocess.Popen([sys.executable, H, str(d), *args], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p

def done(p):
    o, e = p.communicate(timeout=60)
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
