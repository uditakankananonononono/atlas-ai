import json, sys
import numpy as np
from engine import classes, run, SETTINGS
rng0 = np.random.default_rng(0)
NOISE = 0.1
rows = []
n_cl = len(classes())
for w in range(n_cl):  # every behavioral class as the hidden world, 3 seeds each
    for seed in range(3):
        costs = 1 + 4 * np.random.default_rng(1000 + w).random(len(SETTINGS))  # per-world costs in [1,5]
        for pol in ("random", "eig", "eig_cost"):
            r = run(w, pol, costs, NOISE, np.random.default_rng(10 * w + seed), )
            rows.append(dict(world=w, seed=seed, policy=pol, **r))
open("rows.jsonl", "w").write("\n".join(json.dumps(r, default=lambda o: o.item()) for r in rows) + "\n")
print("classes", n_cl, "rows", len(rows))
for pol in ("random", "eig", "eig_cost"):
    rs = [r for r in rows if r["policy"] == pol]
    print(pol, "n", len(rs), "correct", round(np.mean([r["correct"] for r in rs]), 3), "converged", round(np.mean([r["converged"] for r in rs]), 3),
          "mean steps", round(np.mean([r["steps"] for r in rs]), 2), "mean cost", round(np.mean([r["cost"] for r in rs]), 2))
a = {(r["world"], r["seed"], r["policy"]): r["cost"] for r in rows}
rng = np.random.default_rng(1)
for p in ("eig", "eig_cost"):
    d = np.array([a[(w, s, p)] - a[(w, s, "random")] for w in range(n_cl) for s in range(3)])
    bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
    print(f"cost {p} minus random: {d.mean():+.2f} CI [{np.percentile(bs,2.5):+.2f},{np.percentile(bs,97.5):+.2f}]")
d = np.array([a[(w, s, "eig_cost")] - a[(w, s, "eig")] for w in range(n_cl) for s in range(3)])
bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
print(f"cost eig_cost minus eig: {d.mean():+.2f} CI [{np.percentile(bs,2.5):+.2f},{np.percentile(bs,97.5):+.2f}]")
