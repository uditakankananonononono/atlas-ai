"""Epistemic Cartographer.

An explicit, inspectable map over input regions. For each region it keeps
  * reliability: shrunk EXCESS error of the model ensemble (item error minus the
    mean error of the task/budget it came from, so regions are comparable across
    tasks and label budgets);
  * model disagreement (excess), and per-model excess error (who is reliable where);
  * label-contradiction rate (a PROXY for evaluation unreliability, not a validated
    label-error detector): rate of unanimous-member, confident predictions that contradict
    the given label, plus the standard error of the
    region's reliability across tasks (how little the map knows);
  * relations between failures: a region x task excess-error matrix gives a
    co-failure correlation graph; sparse regions borrow strength from regions that
    fail together with them and from adjacent regions;
  * a coverage score (distance to the region centroid relative to that region's
    typical distance) for inputs the map has no way to place.
It is a plain numpy object; `describe()` prints the map in words.
"""
from __future__ import annotations

import numpy as np

ITEM_COLS = ["maxp", "margin", "entropy", "vote_dis", "maxp_std", "nlab", "k", "knn_dist", "length"]
MAP_COLS = ["exc_err", "exc_err_sm", "exc_dis", "exc_mod_mean", "exc_mod_min", "exc_mod_max",
            "suspect", "log_n", "se", "oom", "route_dis"]
TAU = 30.0


def item_features(P, nlab, k, knn_dist, length):
    """P: (M, n, k) member probabilities. Returns (F, agree) with F columns = ITEM_COLS."""
    ens = P.mean(0)
    srt = np.sort(ens, 1)
    maxp = srt[:, -1]
    margin = srt[:, -1] - srt[:, -2]
    ent = -(ens * np.log(ens + 1e-12)).sum(1)
    pred = ens.argmax(1)
    agree = (P.argmax(2) == pred[None]).T.astype(np.float64)  # (n, M)
    vote_dis = 1.0 - agree.mean(1)
    mstd = P.max(2).std(0)
    n = len(pred)
    F = np.c_[maxp, margin, ent, vote_dis, mstd, np.full(n, nlab), np.full(n, k), knn_dist, length]
    return F, agree


class Cartographer:
    def __init__(self, n_regions, centroids=None):
        self.R = n_regions
        self.centroids = centroids

    def fit(self, rec, smoothing=True):
        """rec keys: region, err, agree (n,M), model_err (n,M), suspect, tb (task-budget id), tid, budget."""
        R = self.R
        region, tb = rec["region"], rec["tb"]
        err = rec["err"].astype(float)
        dis = 1.0 - rec["agree"].mean(1)
        merr = rec["model_err"].astype(float)
        M = merr.shape[1]
        # per task-budget means -> excess
        ntb = tb.max() + 1
        cnt = np.bincount(tb, minlength=ntb).astype(float)
        cnt[cnt == 0] = 1
        mean_err = np.bincount(tb, err, ntb) / cnt
        mean_dis = np.bincount(tb, dis, ntb) / cnt
        mean_m = np.stack([np.bincount(tb, merr[:, m], ntb) / cnt for m in range(M)], 1)
        x_err = err - mean_err[tb]
        x_dis = dis - mean_dis[tb]
        x_m = merr - mean_m[tb]
        n = np.bincount(region, minlength=R).astype(float)
        s_err = np.bincount(region, x_err, R)
        s_dis = np.bincount(region, x_dis, R)
        s_m = np.stack([np.bincount(region, x_m[:, m], R) for m in range(M)], 1)
        self.n = n
        self.exc_err = s_err / (n + TAU)
        self.exc_dis = s_dis / (n + TAU)
        self.exc_m = s_m / (n + TAU)[:, None]
        # label-contradiction rate (proxy) (budgets >= 100 only), shrunk to global
        use = rec["budget"] >= 100
        sus = rec["suspect"].astype(float)
        nu = np.bincount(region[use], minlength=R).astype(float)
        su = np.bincount(region[use], sus[use], R)
        g = sus[use].mean() if use.any() else 0.0
        self.suspect = (su + TAU * g) / (nu + TAU)
        self.suspect_global = g
        # region x task excess-error matrix (mean over that task's budgets/docs)
        tid = rec["tid"]
        T = tid.max() + 1
        key = region * T + tid
        c = np.bincount(key, minlength=R * T).astype(float).reshape(R, T)
        s = np.bincount(key, x_err, R * T).reshape(R, T)
        with np.errstate(invalid="ignore", divide="ignore"):
            Rm = np.where(c >= 3, s / c, np.nan)
        ntask = (~np.isnan(Rm)).sum(1)
        with np.errstate(invalid="ignore"):
            sd = np.nanstd(Rm, axis=1)
        sd = np.where(ntask >= 2, sd, np.nanmean(sd[ntask >= 2]) if (ntask >= 2).any() else 0.1)
        self.se = sd / np.sqrt(np.maximum(ntask, 1))
        self.ntask = ntask
        # co-failure graph
        self.nbrs = [[] for _ in range(R)]
        if smoothing:
            corr = np.full((R, R), -np.inf)
            valid = ~np.isnan(Rm)
            Z = np.where(valid, Rm, 0.0)
            for i in range(R):
                for j in range(i + 1, R):
                    m = valid[i] & valid[j]
                    if m.sum() >= 8:
                        a, b = Rm[i, m], Rm[j, m]
                        if a.std() > 1e-9 and b.std() > 1e-9:
                            cc = np.corrcoef(a, b)[0, 1]
                            corr[i, j] = corr[j, i] = cc
            for i in range(R):
                order = np.argsort(-corr[i])[:4]
                nb = [int(j) for j in order if corr[i, j] > 0.2]
                if self.centroids is not None:
                    sim = self.centroids @ self.centroids[i]
                    sim[i] = -np.inf
                    nb += [int(j) for j in np.argsort(-sim)[:3]]
                self.nbrs[i] = sorted(set(nb))
        raw = s_err / np.maximum(n, 1)
        sm = np.zeros(R)
        for i in range(R):
            if self.nbrs[i]:
                sm[i] = (s_err[i] + TAU * raw[self.nbrs[i]].mean()) / (n[i] + TAU)
            else:
                sm[i] = self.exc_err[i]
        self.exc_err_sm = sm
        self.best_model = self.exc_m.argmin(1)
        return self

    def features(self, region, oom, agree, permute=None):
        """Map-derived features for items. `permute` (array R->R) is the shuffled-map control."""
        r = region if permute is None else permute[region]
        route_dis = 1.0 - agree[np.arange(len(r)), self.best_model[r]]
        return np.c_[self.exc_err[r], self.exc_err_sm[r], self.exc_dis[r], self.exc_m[r].mean(1),
                     self.exc_m[r].min(1), self.exc_m[r].max(1), self.suspect[r],
                     np.log1p(self.n[r]), self.se[r], oom, route_dis]

    def describe(self, k=5):
        """Plain-language rendering of the map."""
        order = np.argsort(-self.exc_err_sm)
        lines = ["Epistemic map: %d regions, %.0f supporting item-records" % (self.R, self.n.sum())]
        lines.append("Least reliable regions (smoothed excess error): " + ", ".join(
            "r%d(%+.3f, n=%d)" % (i, self.exc_err_sm[i], self.n[i]) for i in order[:k]))
        lines.append("Most reliable regions: " + ", ".join(
            "r%d(%+.3f, n=%d)" % (i, self.exc_err_sm[i], self.n[i]) for i in order[::-1][:k]))
        o2 = np.argsort(-self.suspect)
        lines.append("Regions with the highest label-contradiction rate (proxy only): " + ", ".join(
            "r%d(%.2f)" % (i, self.suspect[i]) for i in o2[:k]))
        o3 = np.argsort(-self.se)
        lines.append("Regions the map knows least about (largest se): " + ", ".join(
            "r%d(se=%.3f, tasks=%d)" % (i, self.se[i], self.ntask[i]) for i in o3[:k]))
        return "\n".join(lines)
