"""Direction 3 (SCOPED toy): stream of the 40 authored tasks. Compare total solved vs total programs evaluated.
single: base DSL, per-task budget B. single_x: same, per-task budget 3B (the 'more context/compute' control).
multi: fast loop (library macros as cached skills) + deliberative search (budget B) + learning loop (every 8 tasks
re-learn macros from verified solutions, cost counted) + strategic loop (a failed task is retried once at 3B only
if total programs evaluated so far < 0.7*3*B*(k+1)*0.5 after k+1 tasks, about 1.05*B per task)."""
import json, random, sys
import numpy as np
import dsl
from dsl import make_tasks, solve, verify, flat
from library import learn
B = int(sys.argv[1]) if len(sys.argv) > 1 else 1000


def run_stream(order, mode):
    dsl.COST[0] = 0
    lib = {}; solved = []; verified = []
    for k, t in enumerate(order):
        if mode == "single": p, _ = solve(t, {}, B)
        elif mode == "single_x": p, _ = solve(t, {}, 3 * B)
        else:
            p, _ = solve(t, lib, B)
            if (p is None or not verify(t, p, lib)) and dsl.COST[0] < 0.7 * 3 * B * (k + 1) * 0.5:
                p, _ = solve(t, lib, 3 * B)
        ok = p is not None and verify(t, p, lib if mode == "multi" else {})
        solved.append(ok)
        if ok: verified.append(t)
        if mode == "multi" and (k + 1) % 8 == 0 and len(verified) >= 4:
            lib, _ = learn(verified, B, seed=k)
    return sum(solved), dsl.COST[0]


tasks = make_tasks(0)
rows = []
for seed in range(10):
    order = tasks[:]; random.Random(seed).shuffle(order)
    for mode in ("single", "single_x", "multi"):
        s, c = run_stream(order, mode); rows.append(dict(seed=seed, mode=mode, solved=s, cost=c))
open(f"loops_rows_B{B}.jsonl", "w").write("\n".join(json.dumps(r) for r in rows) + "\n")
print("B", B)
for m in ("single", "single_x", "multi"):
    rs = [r for r in rows if r["mode"] == m]
    print(f"{m:9s} solved {np.mean([r['solved'] for r in rs]):.1f}/40 (sd {np.std([r['solved'] for r in rs]):.1f})  mean programs evaluated {np.mean([r['cost'] for r in rs]):.0f}")
a = {(r["seed"], r["mode"]): r for r in rows}
for x in ("single", "single_x"):
    d = np.array([a[(s, "multi")]["solved"] - a[(s, x)]["solved"] for s in range(10)]); print(f"multi - {x} solved: {d.mean():+.2f} (seeds with multi>=: {int((d>=0).sum())}/10)")
