import json, sys, numpy as np
split = sys.argv[1]; SUF = sys.argv[2] if len(sys.argv) > 2 else ""
rows = [json.loads(l) for l in open(f"rows_{split}.jsonl")]
kinds = sorted({r["kind"] for r in rows}); tasks = sorted({r["seed"] for r in rows})
rng = np.random.default_rng(0)
def succ(r, B): return float(r["solved_vis"] and r["evals"] <= B and r["hid_fail"] == 0)
def per_task(kind, B):
    return np.array([np.mean([succ(r, B) for r in rows if r["kind"] == kind and r["seed"] == t]) for t in tasks])
def ci(d):
    bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(5000)]
    return d.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5)
print(f"split {split}: {len(tasks)} tasks x {len(rows)//len(kinds)//len(tasks)} agent seeds; bugs k in {sorted({r['k'] for r in rows})}")
Bs = [100, 333, 1000]
print("hidden-verified success rate by budget (program evaluations)")
print(f"{'agent':10s}" + "".join(f"{B:>8d}" for B in Bs) + "   visible-pass-but-hidden-fail   mean tests/eval-cost")
for k in kinds:
    rs = [r for r in rows if r["kind"] == k]
    ov = np.mean([r["solved_vis"] and r["hid_fail"] > 0 for r in rs])
    print(f"{k:10s}" + "".join(f"{per_task(k, B).mean():8.3f}" for B in Bs) + f"   {ov:.3f}   {np.mean([r['secs'] for r in rs]):.1f}s/run")
def cmp(a, Ba, b, Bb):
    m, lo, hi = ci(per_task(a, Ba) - per_task(b, Bb))
    print(f"  {a}@{Ba} - {b}@{Bb}: {m:+.3f} CI [{lo:+.3f},{hi:+.3f}]")
if "M"+SUF in kinds:
    print("paired bootstrap over tasks (95%)")
    for base in [k + SUF for k in ("S_fl", "S_uniform", "M_noslow") if k + SUF in kinds]:
        for B in (100, 333):
            cmp("M"+SUF, B, base, B)
        for B in (100, 333):
            if base.startswith("S_"): cmp("M"+SUF, B, base, 3 * B)

print("hidden-verified solves (budget 1000) and visible passes by bug count k, per agent: hidden/visible out of runs")
for k in kinds:
    out = []
    for kk in sorted({r["k"] for r in rows}):
        x = [r for r in rows if r["kind"] == k and r["k"] == kk]
        out.append(f"k={kk}: {sum(succ(r, 1000) for r in x):.0f}/{sum(r['solved_vis'] for r in x)} of {len(x)}")
    print(f"  {k:14s}", "  ".join(out))
print("unsolved runs that stopped before the budget:", sum(1 for r in rows if not r["solved_vis"] and r["evals"] < 1000), "of", sum(1 for r in rows if not r["solved_vis"]))
