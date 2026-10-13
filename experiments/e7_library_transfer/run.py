import json, sys
import numpy as np
from dsl import make_tasks
from library import learn, n_solved, random_lib
from dsl import solve, verify
tasks = make_tasks(0)
DOMS = ["math", "bio", "code", "physics"]
rows = []; libs = {}
def solved(t, lib, B):
    p, n = solve(t, lib, B); return bool(p is not None and verify(t, p, lib))
for B in (1000, 3000, 10000):
    for held in DOMS:
        train = [t for t in tasks if t["domain"] != held]; test = [t for t in tasks if t["domain"] == held]
        lib, log = learn(train, B, seed=0)
        libs[f"{B}/{held}"] = {k: list(v) for k, v in lib.items()}
        # within-domain control: learn from held-out domain's own tasks 0..4, test on 5..9 only
        own_train, own_test = test[:5], test[5:]
        own_lib, _ = learn(own_train, B, seed=0, min_domains=1)
        rl = random_lib(max(1, len(lib)), seed=B)
        for t in test:
            rows.append(dict(budget=B, held=held, task=t["desc"], base=solved(t, {}, B), transfer=solved(t, lib, B),
                             random_lib=solved(t, rl, B), n_macros=len(lib),
                             own=(solved(t, own_lib, B) if t in own_test else None),
                             own_base=(solved(t, {}, B) if t in own_test else None)))
json.dump(libs, open("libs.json", "w"), indent=1)
open("rows.jsonl", "w").write("\n".join(json.dumps(r) for r in rows) + "\n")
rng = np.random.default_rng(0)
for B in (1000, 3000, 10000):
    rs = [r for r in rows if r["budget"] == B]
    f = lambda k: np.array([r[k] for r in rs], float)
    print(f"B={B}: n={len(rs)} base {f('base').mean():.3f} transfer {f('transfer').mean():.3f} random_lib {f('random_lib').mean():.3f}")
    for a, b in (("transfer", "base"), ("transfer", "random_lib")):
        d = f(a) - f(b); bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
        print(f"   {a} - {b}: {d.mean():+.3f} CI [{np.percentile(bs,2.5):+.3f},{np.percentile(bs,97.5):+.3f}]")
    per = {h: (np.mean([r['base'] for r in rs if r['held']==h]), np.mean([r['transfer'] for r in rs if r['held']==h]), [r['n_macros'] for r in rs if r['held']==h][0]) for h in DOMS}
    print("   per held-out domain (base, transfer, macros):", {h: (round(float(a),2), round(float(b),2), m) for h,(a,b,m) in per.items()})
    own = [r for r in rs if r["own"] is not None]
    print(f"   within-domain control (5 tasks per domain): own_base {np.mean([r['own_base'] for r in own]):.3f} own_lib {np.mean([r['own'] for r in own]):.3f} cross-domain lib on same tasks {np.mean([r['transfer'] for r in own]):.3f}")
print("macros at B=1000:", {k: list(v) for k, v in libs.items() if k.startswith("1000/")})
