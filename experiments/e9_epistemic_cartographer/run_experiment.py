"""E9 driver.  python run_experiment.py {collect|fail|alloc|all} [--work DIR]

Stages are deterministic given the seeds in data.py / collect.py / below.
"""
from __future__ import annotations

import json
import os
import sys
import time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data
import collect as col
from cartographer import Cartographer, ITEM_COLS, MAP_COLS, item_features
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from scipy.stats import spearmanr

NF = 5  # doc folds for out-of-fold map statistics
GBM = dict(max_iter=200, learning_rate=0.06, max_depth=5, min_samples_leaf=100,
           l2_regularization=1.0, early_stopping=False, random_state=0)
IC = {c: i for i, c in enumerate(ITEM_COLS)}
MC = {c: i for i, c in enumerate(MAP_COLS)}
BASE = ["nlab", "k"]


def cat(*rs):
    return {k: np.concatenate([r[k] for r in rs]) for k in rs[0]}


def get_records(work, C, tasks):
    p = os.path.join(work, "records.npz")
    if os.path.exists(p):
        z = np.load(p)
        parts = {}
        for g in ("fam", "A", "B"):
            parts[g] = {k[len(g) + 1:]: z[k] for k in z.files if k.startswith(g + "_")}
            parts[g]["suspect"] = col.suspect_flag(parts[g]["F"], parts[g]["agree"], parts[g]["err"])
        return parts
    fam = col.collect(C, tasks["fam"], "fam", 1, 0)
    A = col.collect(C, tasks["A"], "A", 2, 1000)
    B = col.collect(C, tasks["B"], "B", 2, 2000)
    np.savez_compressed(p, **{g + "_" + k: v for g, r in (("fam", fam), ("A", A), ("B", B)) for k, v in r.items()})
    return dict(fam=fam, A=A, B=B)


def remap(rec):
    """compact tid / tb ids (they must be dense for bincount-based map fitting)."""
    _, rec["tid"] = np.unique(rec["tid"], return_inverse=True)
    _, rec["tb"] = np.unique(rec["tb"], return_inverse=True)
    return rec


def crossfit_map_features(rec, centroids, R, permute=None, smoothing=True):
    fold = (rec["doc"] * 2654435761 % (2 ** 32)) % NF
    out = np.zeros((len(rec["doc"]), len(MAP_COLS)))
    for f in range(NF):
        tr = fold != f
        sub = {k: v[tr] for k, v in rec.items() if k in ("region", "err", "agree", "model_err", "suspect", "budget", "tid", "tb")}
        m = Cartographer(R, centroids).fit(sub, smoothing=smoothing)
        te = fold == f
        out[te] = m.features(rec["region"][te], rec["oom"][te], rec["agree"][te], permute)
    return out


def cols(F, M, item, mp):
    parts = [F[:, [IC[c] for c in item]]]
    if mp:
        parts.append(M[:, [MC[c] for c in mp]])
    return np.hstack(parts)


ITEM_ALL = ITEM_COLS
MAP_ALL = MAP_COLS
VARIANTS = {
    "item_gbm": (ITEM_ALL, []),
    "map_only": (BASE, MAP_ALL),
    "cartographer": (ITEM_ALL, MAP_ALL),
    "cart_shuffled_map": (ITEM_ALL, MAP_ALL),   # control, uses permuted-region features
    "cart_no_smoothing": (ITEM_ALL, [c for c in MAP_ALL if c != "exc_err_sm"]),
    "cart_no_routing": (ITEM_ALL, [c for c in MAP_ALL if c != "route_dis"]),
    "cart_no_eval_unrel": (ITEM_ALL, [c for c in MAP_ALL if c not in ("suspect", "se")]),
}


def auc(y, s):
    return roc_auc_score(y, s) if 0 < y.sum() < len(y) else np.nan


def ece(y, p, bins=10):
    b = np.minimum((p * bins).astype(int), bins - 1)
    e = 0.0
    for i in range(bins):
        m = b == i
        if m.any():
            e += m.mean() * abs(y[m].mean() - p[m].mean())
    return e


def boot_ci(per_tid_vals, B=2000, seed=0):
    """per_tid_vals: dict tid -> value (nan skipped). Bootstrap over tids."""
    v = np.array([x for x in per_tid_vals if not np.isnan(x)])
    rng = np.random.default_rng(seed)
    bs = [v[rng.integers(0, len(v), len(v))].mean() for _ in range(B)]
    return float(v.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)), len(v)


def paired_ci(a, b, B=2000, seed=0):
    d = np.array(a) - np.array(b)
    ok = ~np.isnan(d)
    return boot_ci(d[ok], B, seed)


def fit_models(fam, C):
    """Train every predictor on familiar-task records with out-of-fold map features."""
    R = len(C["centroids"])
    Mx = crossfit_map_features(fam, C["centroids"], R)
    perm = np.random.default_rng(7).permutation(R)
    Ms = crossfit_map_features(fam, C["centroids"], R, permute=perm)
    Fi = fam["F"]
    y = fam["err"]
    models = {}
    for name, (item, mp) in VARIANTS.items():
        M_ = Ms if name == "cart_shuffled_map" else Mx
        X = cols(Fi, M_, item, mp)
        models[name] = HistGradientBoostingClassifier(**GBM).fit(X, y)
    sc = StandardScaler().fit(Fi)
    models["item_logit"] = (sc, LogisticRegression(C=1.0, max_iter=500).fit(sc.transform(Fi), y))
    iso = IsotonicRegression(out_of_bounds="clip").fit(1 - Fi[:, IC["maxp"]], y)
    iso_v = IsotonicRegression(out_of_bounds="clip").fit(Fi[:, IC["vote_dis"]], y)
    models["maxp_iso"] = iso
    models["vote_iso"] = iso_v
    final_map = Cartographer(R, C["centroids"]).fit({k: fam[k] for k in
                              ("region", "err", "agree", "model_err", "suspect", "budget", "tid", "tb")})
    return models, final_map, perm


def predict_all(models, final_map, perm, rec):
    Fi = rec["F"]
    Mx = final_map.features(rec["region"], rec["oom"], rec["agree"])
    Ms = final_map.features(rec["region"], rec["oom"], rec["agree"], permute=perm)
    sc = {}
    for name, (item, mp) in VARIANTS.items():
        M_ = Ms if name == "cart_shuffled_map" else Mx
        sc[name] = models[name].predict_proba(cols(Fi, M_, item, mp))[:, 1]
    s, lr = models["item_logit"]
    sc["item_logit"] = lr.predict_proba(s.transform(Fi))[:, 1]
    sc["maxp_iso"] = models["maxp_iso"].predict(1 - Fi[:, IC["maxp"]])
    sc["vote_iso"] = models["vote_iso"].predict(Fi[:, IC["vote_dis"]])
    # raw (uncalibrated) rankers
    sc["raw_1minus_maxp"] = 1 - Fi[:, IC["maxp"]]
    sc["raw_knn_dist"] = Fi[:, IC["knn_dist"]]
    sc["raw_map_region_err"] = Mx[:, MC["exc_err_sm"]]
    return sc, Mx


def stage_fail(work, C, parts, out):
    fam = remap(parts["fam"])
    models, fmap, perm = fit_models(fam, C)
    print(fmap.describe())
    res = {"map_description": fmap.describe()}
    per = {}
    for g in ("A", "B"):
        rec = remap(parts[g])
        sc, Mx = predict_all(models, fmap, perm, rec)
        y = rec["err"]
        names = list(sc)
        res[g] = {"n_items": int(len(y)), "error_rate": float(y.mean()), "by_budget": {}}
        tids = np.unique(rec["tid"])
        for b in col.BUDGETS + ("all",):
            sel = np.ones(len(y), bool) if b == "all" else rec["budget"] == b
            tab = {}
            pertask = {n: [] for n in names}
            for t in tids:
                m = sel & (rec["tid"] == t)
                for n in names:
                    pertask[n].append(auc(y[m], sc[n][m]))
            for n in names:
                mean, lo, hi, nt = boot_ci(pertask[n])
                p = np.clip(sc[n][sel], 0, 1)
                row = {"auc_task_macro": mean, "ci": [lo, hi], "n_tasks": nt}
                if not n.startswith("raw_"):
                    row["brier"] = float(np.mean((p - y[sel]) ** 2))
                    row["ece"] = float(ece(y[sel], p))
                tab[n] = row
            diffs = {}
            for a_, b_ in (("cartographer", "item_gbm"), ("cartographer", "cart_shuffled_map"),
                           ("cartographer", "maxp_iso"), ("cartographer", "item_logit"),
                           ("map_only", "maxp_iso"), ("item_gbm", "maxp_iso")):
                m_, lo, hi, nt = paired_ci(pertask[a_], pertask[b_])
                diffs[a_ + "_minus_" + b_] = {"auc_diff": m_, "ci": [lo, hi]}
            res[g]["by_budget"][str(b)] = {"methods": tab, "paired_auc_diff": diffs}
        per[g] = (rec, sc, Mx)
    # task-level difficulty prediction (budget 100)
    rows = []
    for g in ("A", "B"):
        rec, sc, Mx = per[g]
        for t in np.unique(rec["tid"]):
            m = (rec["tid"] == t) & (rec["budget"] == 100)
            rows.append(dict(g=g, true=rec["err"][m].mean(),
                             cart=sc["cartographer"][m].mean(), item=sc["item_gbm"][m].mean(),
                             maxp=sc["raw_1minus_maxp"][m].mean(), vote=sc["vote_iso"][m].mean(),
                             map_only=sc["map_only"][m].mean(), oom=Mx[m, MC["oom"]].mean(),
                             regerr=Mx[m, MC["exc_err_sm"]].mean()))
    import pandas as pd
    df = pd.DataFrame(rows)
    td = {}
    rng = np.random.default_rng(0)
    for n in ("cart", "item", "maxp", "vote", "map_only", "oom", "regerr"):
        rho = spearmanr(df[n], df["true"])[0]
        bs = []
        for _ in range(2000):
            i = rng.integers(0, len(df), len(df))
            bs.append(spearmanr(df[n].values[i], df["true"].values[i])[0])
        td[n] = {"spearman": float(rho), "ci": [float(np.nanpercentile(bs, 2.5)), float(np.nanpercentile(bs, 97.5))]}
    # novel-vs-familiar split of the same
    td["n_tasks"] = int(len(df))
    # within-set (A only) too
    for g in ("A", "B"):
        d = df[df.g == g]
        td["within_" + g] = {n: float(spearmanr(d[n], d["true"])[0]) for n in ("cart", "item", "maxp", "vote", "map_only")}
    res["task_difficulty_budget100"] = td
    # label ambiguity probe
    res["ambiguity_probe"] = ambiguity_probe(C, per)
    json.dump(res, open(os.path.join(out, "results_failure_prediction.json"), "w"), indent=1)
    return res


def ambiguity_probe(C, per):
    """Among failing eval items, can the map's label-contradiction rate tell objectively
    ambiguous items (near-duplicate text carrying a different category label elsewhere
    in the corpus) from other failures?  Weak but externally defined ground truth."""
    from sklearn.preprocessing import normalize
    X = normalize(C["Xt"])
    out = {}
    pos_all, s_map, s_item, s_conf = [], [], [], []
    for g in ("A", "B"):
        rec, sc, Mx = per[g]
        sel = np.flatnonzero((rec["budget"] == 150) & (rec["err"] == 1))
        docs = rec["doc"][sel]
        sim = (X[docs] @ X.T).toarray() if False else X[docs] @ X.T
        sim = sim.tocsr()
        amb = np.zeros(len(docs), bool)
        for i, d in enumerate(docs):
            row = sim.getrow(i)
            j, v = row.indices, row.data
            m = (v > 0.8) & (j != d) & (C["y"][j] != C["y"][d])
            amb[i] = m.any()
        pos_all.append(amb)
        s_map.append(Mx[sel, MC["suspect"]])
        s_item.append(rec["F"][sel, IC["vote_dis"]])
        s_conf.append(rec["F"][sel, IC["maxp"]])
    amb = np.concatenate(pos_all)
    out["n_failures"] = int(len(amb))
    out["n_ambiguous"] = int(amb.sum())
    if amb.sum() >= 15:
        out["auc_map_suspect_rate"] = float(auc(amb, np.concatenate(s_map)))
        out["auc_vote_disagreement"] = float(auc(amb, np.concatenate(s_item)))
        out["auc_confidence"] = float(auc(amb, np.concatenate(s_conf)))
    return out


# ------------------------------------------------------------------ allocation
STRATS = ["random", "uncertainty", "qbc", "meta_item", "cart", "cart_eval_aware", "cart_quota", "cart_shuffled_map"]
ALLOC_SIZES = (30, 60, 90, 120, 150)
POOL = 1200


def quota_select(region, p, nsel):
    R = region.max() + 1
    mass = np.bincount(region, p, R)
    want = mass / mass.sum() * nsel
    q = np.floor(want).astype(int)
    rem = nsel - q.sum()
    q[np.argsort(-(want - q))[:rem]] += 1
    chosen = []
    for r in range(R):
        idx = np.flatnonzero(region == r)
        if q[r] and len(idx):
            chosen += list(idx[np.argsort(-p[idx])[:q[r]]])
    chosen = np.array(chosen, int)
    if len(chosen) < nsel:  # regions too small: fill by global score
        rest = np.setdiff1d(np.arange(len(p)), chosen)
        chosen = np.r_[chosen, rest[np.argsort(-p[rest])[:nsel - len(chosen)]]]
    return chosen[:nsel]


def alloc_run(C, models, fmap, perm, cats, tid, strat):
    from zoo import fit_ensemble, predict_probs
    cats = np.array(cats)
    k = len(cats)
    tr, ev, ytr, yev = col.task_arrays(C, cats, 2)
    rng_pool = np.random.default_rng(555 + tid)
    pool = np.sort(rng_pool.choice(len(tr), min(POOL, len(tr)), replace=False))
    trp, ytrp = tr[pool], ytr[pool]
    rng0 = np.random.default_rng(999 + tid)          # identical start across strategies
    lab = list(col.sample_labeled(rng0, ytrp, ALLOC_SIZES[0]))
    rng_s = np.random.default_rng(31 * tid + 5)
    accs = {}
    for step, size in enumerate(ALLOC_SIZES):
        li = np.array(lab)
        ms = fit_ensemble(C["Xt"][trp[li]], C["Xs"][trp[li]], ytrp[li], seed=tid)
        Pev = predict_probs(ms, C["Xt"][ev], C["Xs"][ev], k)
        accs[size] = float((Pev.mean(0).argmax(1) == yev).mean())
        if size == ALLOC_SIZES[-1]:
            break
        unl = np.setdiff1d(np.arange(len(trp)), li)
        Pu = predict_probs(ms, C["Xt"][trp[unl]], C["Xs"][trp[unl]], k)
        kd = col.knn_dist(C["Xs"][trp[li]], C["Xs"][trp[unl]])
        F, agree = item_features(Pu, size, k, kd, C["length"][trp[unl]])
        reg, oom = C["region"][trp[unl]], C["oom"][trp[unl]]
        nsel = ALLOC_SIZES[step + 1] - size
        if strat == "random":
            pick = rng_s.choice(len(unl), nsel, replace=False)
        elif strat == "uncertainty":
            pick = np.argsort(-(1 - F[:, IC["maxp"]]))[:nsel]
        elif strat == "qbc":
            pick = np.argsort(-(F[:, IC["vote_dis"]] + 1e-3 * (1 - F[:, IC["maxp"]])))[:nsel]
        else:
            Mx = fmap.features(reg, oom, agree, permute=perm if strat == "cart_shuffled_map" else None)
            item, mp = VARIANTS["item_gbm"] if strat == "meta_item" else VARIANTS["cartographer"]
            name = "item_gbm" if strat == "meta_item" else ("cart_shuffled_map" if strat == "cart_shuffled_map" else "cartographer")
            p = models[name].predict_proba(cols(F, Mx, item, mp))[:, 1]
            if strat == "cart_eval_aware":
                p = p / (1 + Mx[:, MC["suspect"]] / max(fmap.suspect_global, 1e-6))
            if strat == "cart_quota":
                pick = quota_select(reg, p, nsel)
            else:
                pick = np.argsort(-p)[:nsel]
        lab += list(unl[pick])
    return accs


def stage_alloc(work, C, parts, tasks, out, n_jobs=2, strategies=STRATS):
    from joblib import Parallel, delayed
    fam = remap(parts["fam"])
    models, fmap, perm = fit_models(fam, C)
    jobs = []
    for g in ("A", "B"):
        for i, cats in enumerate(tasks[g]):
            for s in strategies:
                jobs.append((g, i, cats, 1000 * (1 if g == "A" else 2) + i, s))
    res = Parallel(n_jobs=n_jobs, batch_size=1)(
        delayed(alloc_run)(C, models, fmap, perm, c, tid, s) for (g, i, c, tid, s) in jobs)
    rows = [dict(group=g, task=i, strat=s, **{"acc%d" % k_: v for k_, v in r.items()})
            for (g, i, c, tid, s), r in zip(jobs, res)]
    json.dump(rows, open(os.path.join(out, "allocation_raw.json"), "w"))
    return summarize_alloc(rows, out)


def summarize_alloc(rows, out):
    import pandas as pd
    df = pd.DataFrame(rows)
    df["auc_curve"] = df[["acc%d" % s for s in ALLOC_SIZES]].mean(1)
    res = {}
    for grp in ("A", "B", "A+B"):
        d = df if grp == "A+B" else df[df.group == grp]
        piv = {m: d.pivot_table(index=["group", "task"], columns="strat", values=m) for m in ("acc90", "acc150", "auc_curve")}
        r = {}
        for m, pv in piv.items():
            r[m] = {s: boot_ci(pv[s].values) for s in STRATS if s in pv}
            r[m + "_paired_vs"] = {}
            for a_ in ("cart", "cart_eval_aware", "cart_quota", "meta_item"):
                for b_ in ("random", "uncertainty", "qbc", "meta_item", "cart_shuffled_map"):
                    if a_ != b_ and a_ in pv and b_ in pv:
                        r[m + "_paired_vs"][a_ + "_minus_" + b_] = paired_ci(pv[a_].values, pv[b_].values)
        res[grp] = r
    json.dump(res, open(os.path.join(out, "results_allocation.json"), "w"), indent=1)
    return res


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    work = os.path.expanduser("~/e9_work")
    if "--work" in sys.argv:
        work = sys.argv[sys.argv.index("--work") + 1]
    os.makedirs(work, exist_ok=True)
    out = os.path.dirname(os.path.abspath(__file__))
    C = data.build_corpus(os.path.join(work, "cache"))
    tasks = data.make_tasks(C["familiar"], C["novel"])
    json.dump({k: [list(map(int, t)) for t in v] for k, v in tasks.items()} | {
        "familiar": list(map(int, C["familiar"])), "novel": list(map(int, C["novel"]))},
        open(os.path.join(out, "tasks.json"), "w"))
    parts = get_records(work, C, tasks)
    if stage in ("fail", "all"):
        stage_fail(work, C, {k: dict(v) for k, v in parts.items()}, out)
    if stage in ("alloc", "all"):
        stage_alloc(work, C, {k: dict(v) for k, v in parts.items()}, tasks, out)


if __name__ == "__main__":
    main()
