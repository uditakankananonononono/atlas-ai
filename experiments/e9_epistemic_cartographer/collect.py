"""Collect failure records of the real model ensemble on tasks."""
from __future__ import annotations

import numpy as np
from joblib import Parallel, delayed

from zoo import fit_ensemble, predict_probs
from cartographer import item_features

BUDGETS = (30, 60, 100, 150)
SUSPECT_MAXP = 0.5  # first run used 0.9: that fired on 0.003% of items (degenerate), see RESULTS.md


def suspect_flag(F, agree, err):
    """Unanimous members, ensemble maxp (F column 0) above SUSPECT_MAXP, yet wrong against the label."""
    return ((agree.min(1) == 1) & (F[:, 0] > SUSPECT_MAXP) & (err == 1)).astype(np.int8)


def sample_labeled(rng, ylocal, n):
    """Random labelled subset of size n with >=2 per class."""
    k = ylocal.max() + 1
    idx = []
    for c in range(k):
        pos = np.flatnonzero(ylocal == c)
        idx += list(rng.choice(pos, 2, replace=False))
    rest = np.setdiff1d(np.arange(len(ylocal)), idx)
    idx += list(rng.choice(rest, max(n - len(idx), 0), replace=False))
    return np.array(idx)


def task_arrays(C, cats, eval_role):
    cats = np.array(cats)
    ymap = {int(c): i for i, c in enumerate(cats)}
    tr = np.flatnonzero((C["role"] == 0) & np.isin(C["y"], cats))
    ev = np.flatnonzero((C["role"] == eval_role) & np.isin(C["y"], cats))
    ytr = np.array([ymap[int(c)] for c in C["y"][tr]])
    yev = np.array([ymap[int(c)] for c in C["y"][ev]])
    return tr, ev, ytr, yev


def knn_dist(Xs_lab, Xs_q):
    sim = Xs_q @ Xs_lab.T
    top = -np.sort(-sim, 1)[:, :3]
    return 1.0 - top.mean(1)


def run_one(C, cats, eval_role, budget, seed):
    tr, ev, ytr, yev = task_arrays(C, cats, eval_role)
    k = len(cats)
    rng = np.random.default_rng(seed)
    lab = sample_labeled(rng, ytr, budget)
    models = fit_ensemble(C["Xt"][tr[lab]], C["Xs"][tr[lab]], ytr[lab], seed=seed % 10000)
    P = predict_probs(models, C["Xt"][ev], C["Xs"][ev], k)
    kd = knn_dist(C["Xs"][tr[lab]], C["Xs"][ev])
    F, agree = item_features(P, budget, k, kd, C["length"][ev])
    ens = P.mean(0)
    pred = ens.argmax(1)
    err = (pred != yev).astype(np.int8)
    model_err = (P.argmax(2) != yev[None]).T.astype(np.int8)
    suspect = suspect_flag(F, agree, err)
    return dict(doc=ev, region=C["region"][ev], oom=C["oom"][ev], F=F, agree=agree, err=err,
                model_err=model_err, suspect=suspect, budget=np.full(len(ev), budget),
                ylab=yev, k=np.full(len(ev), k))


def _job(C, tid, cats, eval_role, budget, seed):
    r = run_one(C, cats, eval_role, budget, seed)
    r["tid"] = np.full(len(r["doc"]), tid)
    return r


def collect(C, tasks, group, eval_role, tid0, budgets=BUDGETS, n_jobs=2):
    jobs = []
    for i, cats in enumerate(tasks):
        for b in budgets:
            jobs.append((tid0 + i, cats, b, 1000 * (tid0 + i) + b))
    out = Parallel(n_jobs=n_jobs, batch_size=1)(
        delayed(_job)(C, t, c, eval_role, b, s) for (t, c, b, s) in jobs)
    rec = {k: np.concatenate([o[k] for o in out]) for k in out[0]}
    # task-budget id
    keys = rec["tid"] * 1000 + rec["budget"]
    _, tb = np.unique(keys, return_inverse=True)
    rec["tb"] = tb
    rec["group"] = np.full(len(tb), group)
    return rec
