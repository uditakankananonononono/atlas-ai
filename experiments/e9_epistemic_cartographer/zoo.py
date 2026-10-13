"""A small, genuinely diverse ensemble of real models trained on a task's labelled docs."""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import ComplementNB
from sklearn.svm import LinearSVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import ExtraTreesClassifier

MODEL_NAMES = ["lr_tfidf", "cnb_tfidf", "svm_tfidf", "knn_svd", "et_svd"]
M = len(MODEL_NAMES)


def _softmax(z):
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


def fit_ensemble(Xt, Xs, y, seed=0):
    """Xt: sparse tfidf (n,d); Xs: dense svd (n,100); y local labels 0..k-1 (all present)."""
    ms = []
    ms.append(("t", LogisticRegression(C=20, max_iter=300).fit(Xt, y)))
    ms.append(("t", ComplementNB(alpha=0.3).fit(Xt, y)))
    ms.append(("t", LinearSVC(C=1.0, random_state=seed).fit(Xt, y)))
    ms.append(("s", KNeighborsClassifier(n_neighbors=5, weights="distance", metric="cosine").fit(Xs, y)))
    ms.append(("s", ExtraTreesClassifier(n_estimators=60, random_state=seed, n_jobs=1).fit(Xs, y)))
    return ms


def predict_probs(models, Xt, Xs, k):
    """Return P of shape (M, n, k)."""
    out = []
    for i, (kind, m) in enumerate(models):
        X = Xt if kind == "t" else Xs
        if i == 2:
            p = _softmax(3.0 * m.decision_function(X)) if k > 2 else None
            if k == 2:
                d = m.decision_function(X)
                p = _softmax(3.0 * np.c_[-d, d])
        elif i == 1:
            p = m.predict_proba(X)
        else:
            p = m.predict_proba(X)
        out.append(np.asarray(p, dtype=np.float64))
    return np.stack(out)
