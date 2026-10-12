"""E2 step 2: can a static-feature predictor forecast 'will the module's own tests kill this change'
better than the base rate? Leave-one-module-out CV; stdlib + numpy."""
import json
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
allrows = [json.loads(l) for l in (Path(sys.argv[1] if len(sys.argv) > 1 else HERE) / "mutants.jsonl").read_text().splitlines()]
rows = [r for r in allrows if not r["invalid"]]
N_INVALID = len(allrows) - len(rows)
OPS = sorted({r["op"] for r in rows})
KINDS = sorted({r["line_kind"] for r in rows})
KINDS = [k for k in KINDS if sum(r["line_kind"] == k for r in rows) >= 10]


def X(rs, sets):
    out = []
    for r in rs:
        v = [1.0]
        if "op" in sets: v += [float(r["op"] == o) for o in OPS]
        if "line" in sets: v += [float(r["line_kind"] == k) for k in KINDS] + [float(r["has_string"])]
        if "fn" in sets: v += [float(r["fn_named_in_tests"]), float(r["fn_private"]), float(r["in_function"])]
        if "mod" in sets: v += [min(r["test_ratio"], 5.0) / 5.0, float(r["n_test_files"] > 0)]
        out.append(v)
    return np.array(out)


def fit(Xt, y, l2=1.0, it=400, lr=0.5):
    w = np.zeros(Xt.shape[1])
    for _ in range(it):
        p = 1 / (1 + np.exp(-Xt @ w))
        w -= lr * (Xt.T @ (p - y) / len(y) + l2 * np.r_[0, w[1:]] / len(y))
    return w


def auc(p, y):
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0: return float("nan")
    return float(np.mean([(a > b) + 0.5 * (a == b) for a in pos for b in neg]))


def ece(p, y, bins=5):
    e = 0.0
    for b in range(bins):
        m = (p >= b / bins) & (p < (b + 1) / bins + (1e-9 if b == bins - 1 else 0))
        if m.any(): e += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(e)


def cv(sets):
    mods = sorted({r["module"] for r in rows})
    P, Y = [], []
    for m in mods:
        tr = [r for r in rows if r["module"] != m]; te = [r for r in rows if r["module"] == m]
        ytr = np.array([float(r["killed"]) for r in tr]); yte = np.array([float(r["killed"]) for r in te])
        if sets == "base":
            p = np.full(len(te), ytr.mean())
        else:
            w = fit(X(tr, sets), ytr); p = 1 / (1 + np.exp(-X(te, sets) @ w))
        P += list(p); Y += list(yte)
    P, Y = np.array(P), np.array(Y)
    cv.last = (P, Y)
    return dict(brier=float(np.mean((P - Y) ** 2)), ece=ece(P, Y), auc=auc(P, Y))


Y = np.array([float(r["killed"]) for r in rows])
res = dict(n=len(rows), n_invalid_excluded=N_INVALID, killed_rate=float(Y.mean()), fallback_all_tests=sum(r["fallback_all_tests"] for r in rows),
           per_module={m: dict(n=sum(r["module"] == m for r in rows),
                               killed=round(float(np.mean([r["killed"] for r in rows if r["module"] == m])), 3))
                       for m in sorted({r["module"] for r in rows})})
res["models"] = {"base_rate": cv("base"), "op": cv(("op",)), "op+line": cv(("op", "line")),
                 "op+line+fn": cv(("op", "line", "fn")), "mod_only": cv(("mod",)), "all": cv(("op", "line", "fn", "mod"))}
# noise: bootstrap (2000x) over mutants, paired Brier difference vs base rate (negative = better than base)
cv("base"); Pb, Yb = cv.last
rng = np.random.default_rng(0)
for name, sets in (("op", ("op",)), ("op+line+fn", ("op", "line", "fn")), ("mod_only", ("mod",)), ("all", ("op", "line", "fn", "mod"))):
    cv(sets); Pm, _ = cv.last
    d = (Pm - Yb) ** 2 - (Pb - Yb) ** 2
    bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
    res["models"][name]["brier_minus_base_ci95"] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
(HERE / "results.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
