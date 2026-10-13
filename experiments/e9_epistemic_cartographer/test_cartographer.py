"""Fast synthetic tests for the cartographer machinery (no corpus download)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data
import ec_run_experiment as rx
from cartographer import Cartographer, item_features, ITEM_COLS, MAP_COLS

R, M = 12, 5


def planted(n_per=400, n_tasks=20, seed=0, p_region=None, offsets=True, suspect_region=None, sparse=None):
    rng = np.random.default_rng(seed)
    p_region = np.linspace(0.05, 0.6, R) if p_region is None else p_region
    rows = []
    for t in range(n_tasks):
        off = rng.uniform(-0.1, 0.1) if offsets else 0.0
        for b in (60, 150):
            for r in range(R):
                n = n_per // 10 if (sparse is not None and r == sparse) else n_per // R * 3
                p = np.clip(p_region[r] + off, 0.01, 0.99)
                err = (rng.random(n) < p).astype(np.int8)
                agree = (rng.random((n, M)) > p[None] * 0.5).astype(float)
                me = (rng.random((n, M)) < p).astype(np.int8)
                sus = np.zeros(n, np.int8)
                if suspect_region is not None and r == suspect_region:
                    sus = (rng.random(n) < 0.5).astype(np.int8)
                rows.append(dict(region=np.full(n, r), err=err, agree=agree, model_err=me, suspect=sus,
                                 budget=np.full(n, b), tid=np.full(n, t), tb=np.full(n, t * 2 + (b == 150))))
    return {k: np.concatenate([x[k] for x in rows]) for k in rows[0]}


def test_item_features_shapes_and_ranges():
    rng = np.random.default_rng(0)
    P = rng.dirichlet(np.ones(4), size=(5, 30))
    F, agree = item_features(P, 60, 4, rng.random(30), rng.random(30))
    assert F.shape == (30, len(ITEM_COLS)) and agree.shape == (30, 5)
    assert (F[:, 0] >= 0.25 - 1e-9).all() and (F[:, 1] >= 0).all() and ((F[:, 3] >= 0) & (F[:, 3] <= 1)).all()


def test_map_recovers_planted_reliability():
    rec = planted()
    m = Cartographer(R).fit(rec)
    truth = np.linspace(0.05, 0.6, R)
    assert np.corrcoef(m.exc_err_sm, truth)[0, 1] > 0.95
    assert m.exc_err_sm.argmax() == R - 1 and m.exc_err_sm.argmin() == 0


def test_excess_error_removes_task_difficulty_offsets():
    # with large per-task offsets the region ordering must still be recovered
    rec = planted(offsets=True, seed=3)
    m = Cartographer(R).fit(rec)
    assert np.corrcoef(m.exc_err, np.linspace(0.05, 0.6, R))[0, 1] > 0.95


def test_suspect_rate_flags_planted_label_noise_region():
    rec = planted(suspect_region=4)
    m = Cartographer(R).fit(rec)
    assert m.suspect.argmax() == 4 and m.suspect[4] > 3 * np.median(m.suspect)


def test_coverage_uncertainty_larger_for_sparse_region():
    rec = planted(sparse=7, seed=1, n_tasks=30)
    m = Cartographer(R).fit(rec)
    assert m.n[7] < 0.5 * np.median(m.n)


def test_smoothing_uses_cofailing_regions_for_sparse_region():
    # region 0 is sparse; regions 0 and 1 share a task-level failure factor.
    rng = np.random.default_rng(5)
    rows = []
    for t in range(60):
        z = rng.normal(0, 0.15)             # shared factor between regions 0 and 1
        for r in range(R):
            n = 6 if r == 0 else 60
            p = np.clip((0.4 + z) if r in (0, 1) else 0.2, 0.01, 0.99)
            err = (rng.random(n) < p).astype(np.int8)
            rows.append(dict(region=np.full(n, r), err=err, agree=np.ones((n, M)), model_err=np.tile(err[:, None], (1, M)),
                             suspect=np.zeros(n, np.int8), budget=np.full(n, 100), tid=np.full(n, t), tb=np.full(n, t)))
    rec = {k: np.concatenate([x[k] for x in rows]) for k in rows[0]}
    cent = np.eye(R)
    cent = cent / np.linalg.norm(cent, axis=1, keepdims=True)
    m = Cartographer(R, cent).fit(rec, smoothing=True)
    assert 1 in m.nbrs[0]
    m0 = Cartographer(R, cent).fit(rec, smoothing=False)
    raw0 = m0.exc_err[0] * (m0.n[0] + 30) / m0.n[0]
    nb = np.mean([m0.exc_err[j] * (m0.n[j] + 30) / m0.n[j] for j in m.nbrs[0]])
    lo, hi = sorted([raw0, nb])
    assert lo - 1e-9 <= m.exc_err_sm[0] <= hi + 1e-9   # smoothed value is a blend of own and neighbour evidence
    assert m0.exc_err_sm[0] == m0.exc_err[0]            # no graph -> falls back to own shrunk estimate


def test_crossfit_features_do_not_leak_on_pure_noise():
    # failures independent of everything: out-of-fold map features must not predict them.
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(2)
    n = 6000
    rec = dict(doc=np.arange(n), region=rng.integers(0, R, n), oom=rng.random(n),
               agree=rng.integers(0, 2, (n, M)).astype(float), err=(rng.random(n) < 0.3).astype(np.int8),
               model_err=(rng.random((n, M)) < 0.3).astype(np.int8), suspect=(rng.random(n) < 0.05).astype(np.int8),
               budget=np.full(n, 150), tid=rng.integers(0, 10, n))
    rec["tb"] = rec["tid"].copy()
    X = rx.crossfit_map_features(rec, None, R)
    a = roc_auc_score(rec["err"], X[:, MAP_COLS.index("exc_err")])
    assert 0.46 < a < 0.54


def test_shuffled_map_control_changes_features():
    rec = planted()
    m = Cartographer(R).fit(rec)
    perm = np.random.default_rng(0).permutation(R)
    reg = np.arange(R)
    a = m.features(reg, np.ones(R), np.ones((R, M)))
    b = m.features(reg, np.ones(R), np.ones((R, M)), permute=perm)
    assert not np.allclose(a, b)
    assert np.allclose(b[:, 0], a[perm, 0])


def test_quota_select_exact_count_unique_and_biased_to_mass():
    rng = np.random.default_rng(0)
    reg = rng.integers(0, 6, 500)
    p = np.where(reg == 2, 0.9, 0.05) * rng.uniform(0.9, 1, 500)
    sel = rx.quota_select(reg, p, 30)
    assert len(sel) == 30 and len(set(sel)) == 30
    assert (reg[sel] == 2).mean() > 0.6


def test_bootstrap_ci_contains_mean_and_is_ordered():
    v = np.random.default_rng(0).normal(1.0, 0.5, 40)
    m, lo, hi, n = rx.boot_ci(v)
    assert lo < m < hi and n == 40
    m2, lo2, hi2, _ = rx.paired_ci(v + 1, v)
    assert abs(m2 - 1) < 1e-9 and lo2 <= hi2


def test_auc_and_ece_helpers():
    y = np.array([0, 0, 1, 1])
    assert rx.auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == 1.0
    assert np.isnan(rx.auc(np.zeros(4), np.arange(4.)))
    assert rx.ece(y, np.array([0, 0, 1, 1.0])) == 0.0


def test_tasks_disjoint_and_constructed_as_specified():
    fam, nov = np.arange(14), np.arange(14, 20)
    T = data.make_tasks(fam, nov)
    allt = T["fam"] + T["A"] + T["B"]
    assert len(set(allt)) == len(allt) == 120
    assert all(set(t) <= set(fam) for t in T["fam"] + T["A"])
    assert all(len(set(t) & set(nov)) >= 1 for t in T["B"])
    assert all(3 <= len(t) <= 5 for t in allt)
    assert T == data.make_tasks(fam, nov)  # deterministic


def test_describe_runs():
    rec = planted()
    assert "Least reliable regions" in Cartographer(R).fit(rec).describe()
