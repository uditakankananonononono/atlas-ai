"""E3: goal formation, ranking candidate goals against SYNTHETIC owner preferences.

EVERYTHING IN THIS FILE'S OUTPUT IS UNVERIFIED: the owner-accept labels are drawn from a
hidden synthetic preference function written by the experimenter, not from any real owner
decision. No real owner data was read or used. Baseline R0 is the shipped GapDetector order.
Usage (Python 3.12): python run_experiment.py [out_dir]
"""
import json
import math
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.self_improve.detector import GapDetector  # noqa: E402
from app.self_improve.events import GapEvent, GapEventStore  # noqa: E402

N, TOPK, TRAIN_N = 60, 10, 40


def world(rnd):
    goals = []
    for i in range(N):
        v, c, nov = rnd.random(), rnd.random(), rnd.random()
        goals.append(dict(id=i, v=v, c=c, nov=nov, gated=rnd.random() < 0.2, dup=i, sig=f"gap-{i}",
                          # observable urgency only weakly tied to value
                          urg=min(1.0, max(0.0, 0.3 * v + 0.7 * rnd.random()))))
    for i in range(N // 5):  # 20% near-duplicates under a different signature
        src = rnd.choice(goals[:N])
        goals.append(dict(src, id=len(goals), dup=src["dup"], sig=f"gap-dup-{len(goals)}",
                          urg=min(1.0, src["urg"] * rnd.uniform(0.6, 1.0))))
    for g in goals:  # noisy proposer-side estimates (from synthetic "context")
        g["vh"], g["ch"], g["nh"] = (min(1, max(0, g[k] + rnd.gauss(0, 0.3))) for k in ("v", "c", "nov"))
    return goals


def p_accept(g):
    z = 3 * (g["v"] - 0.6 * g["c"] + 0.5 * g["nov"] - 0.5)
    return 1 / (1 + math.exp(-z))


def labels(goals, rnd):
    return {g["id"]: rnd.random() < p_accept(g) for g in goals}


def detector_order(goals):
    with tempfile.TemporaryDirectory() as d:
        store = GapEventStore(Path(d))
        now = time.time()
        for g in goals:
            n_ev = 2 + int(g["urg"] * 18)
            for k in range(n_ev):
                store.append(GapEvent("mod", g["sig"], at=now - (1 - g["urg"]) * 86400 * 5 - k))
        gaps = GapDetector(store, min_occurrences=2).detect("mod")
    by_sig = {g["sig"]: g for g in goals}
    return [by_sig[x.signature] for x in gaps]


def dedupe(order):
    seen, out = set(), []
    for g in order:
        if g["dup"] not in seen:
            seen.add(g["dup"]); out.append(g)
    return out


def feats(g):
    return [1.0, g["vh"], g["ch"], g["nh"]]


def fit_logit(tr, y, l2=1.0, it=300, lr=0.5):
    w = [0.0] * 4
    for _ in range(it):
        grad = [0.0] * 4
        for g, t in zip(tr, y):
            x = feats(g); p = 1 / (1 + math.exp(-sum(a * b for a, b in zip(w, x))))
            for j in range(4): grad[j] += (p - t) * x[j]
        w = [wj - lr * (gj / len(tr) + (l2 * wj / len(tr) if j else 0)) for j, (wj, gj) in enumerate(zip(w, grad))]
    return w


def run_seed(seed):
    rnd = random.Random(seed)
    train = world(random.Random(seed + 1000))[:TRAIN_N]
    y_tr = [labels([g], rnd)[g["id"]] for g in train]
    w = fit_logit(train, [float(v) for v in y_tr])
    goals = world(rnd)
    y = labels(goals, rnd)
    ev = lambda g: g["vh"] - 0.6 * g["ch"] + 0.5 * g["nh"]
    lg = lambda g: sum(a * b for a, b in zip(w, feats(g)))
    rankers = {
        "R0_detector": detector_order(goals),
        "R1_random": rnd.sample(goals, len(goals)),
        "R2_ev_nodedupe": sorted(goals, key=lambda g: -ev(g)),
        "R3_ev_dedupe": dedupe(sorted(goals, key=lambda g: -ev(g))),
        "R4_learned_dedupe": dedupe(sorted(goals, key=lambda g: -lg(g))),
        "R5_oracle_dedupe": dedupe(sorted(goals, key=lambda g: -p_accept(g))),
    }
    out = {}
    for name, order in rankers.items():
        top = order[:TOPK]
        out[name] = dict(
            accept=sum(y[g["id"]] for g in top) / TOPK,
            dups=TOPK - len({g["dup"] for g in top}),
            gated_in_top=sum(g["gated"] for g in top))
    return out


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    seeds = list(range(21, 41))
    res = {s: run_seed(s) for s in seeds}
    agg = {}
    for name in res[seeds[0]]:
        agg[name] = {m: (round(statistics.mean(res[s][name][m] for s in seeds), 3),
                         round(statistics.pstdev(res[s][name][m] for s in seeds), 3)) for m in ("accept", "dups", "gated_in_top")}
    (out / "results.json").write_text(json.dumps(dict(seeds=seeds, topk=TOPK, synthetic_labels=True, aggregate=agg), indent=1))
    for n, a in agg.items(): print(n, a)


if __name__ == "__main__":
    main()
