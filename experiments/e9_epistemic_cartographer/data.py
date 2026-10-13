"""Corpus and task construction for E9 (Epistemic Cartographer).

Real data: 20 Newsgroups (bydate split, headers/footers/quotes removed). The
train/test split is chronological, so test documents are temporally shifted
from the train documents every model sees.

Frozen design (seeds fixed here, before any result was looked at):
  * 20 categories are split by a seeded permutation into 14 FAMILIAR and 6 NOVEL.
  * Test documents are split per document into MAP (used only to build the
    cartographer's statistics from familiar tasks) and EVAL (used only to score
    unfamiliar tasks). No document is ever in both roles.
  * The cartographer's embedding and regions are fit on train documents of
    FAMILIAR categories only. Task models use their own vectorizer fit on all
    train text (unlabelled text, part of the task's own pool).
"""
from __future__ import annotations

import os
import numpy as np
import scipy.sparse as sp

SPLIT_SEED = 20261013
N_REGIONS = 60
SVD_DIM = 100


def _fetch(cache_dir):
    from sklearn.datasets import fetch_20newsgroups
    kw = dict(remove=("headers", "footers", "quotes"), data_home=cache_dir)
    tr = fetch_20newsgroups(subset="train", shuffle=False, **kw)
    te = fetch_20newsgroups(subset="test", shuffle=False, **kw)
    return tr, te


def build_corpus(cache_dir: str = None, n_regions: int = N_REGIONS):
    """Return dict of arrays. Cached in cache_dir/e9_corpus.npz (+ sparse)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import normalize

    cache_dir = cache_dir or os.path.expanduser("~/.cache/e9")
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, "corpus_v1.npz")
    spath = os.path.join(cache_dir, "corpus_v1_tfidf.npz")
    if os.path.exists(path) and os.path.exists(spath):
        z = np.load(path, allow_pickle=True)
        out = {k: z[k] for k in z.files}
        out["Xt"] = sp.load_npz(spath).tocsr()
        return out

    tr, te = _fetch(cache_dir)
    texts = list(tr.data) + list(te.data)
    y = np.concatenate([tr.target, te.target]).astype(int)
    is_train = np.r_[np.ones(len(tr.data), bool), np.zeros(len(te.data), bool)]
    keep = np.array([len(t.split()) >= 5 for t in texts])
    texts = [t for t, k in zip(texts, keep) if k]
    y, is_train = y[keep], is_train[keep]
    length = np.log1p(np.array([len(t.split()) for t in texts]))

    perm = np.random.default_rng(SPLIT_SEED).permutation(20)
    familiar = np.sort(perm[:14])
    novel = np.sort(perm[14:])
    rng = np.random.default_rng(SPLIT_SEED + 1)
    role = np.where(is_train, 0, np.where(rng.random(len(y)) < 0.5, 1, 2))  # 0 train, 1 MAP, 2 EVAL

    vec = TfidfVectorizer(max_features=20000, sublinear_tf=True, stop_words="english", min_df=3)
    vec.fit(texts_train := [t for t, tr_ in zip(texts, is_train) if tr_])  # task-model vectorizer: train text, unlabelled
    Xt = vec.transform(texts).tocsr()
    svd = TruncatedSVD(SVD_DIM, random_state=0)
    svd.fit(Xt[is_train])
    Xs = normalize(svd.transform(Xt))

    # cartographer embedding: familiar-category TRAIN docs only
    fam_train = is_train & np.isin(y, familiar)
    mvec = TfidfVectorizer(max_features=20000, sublinear_tf=True, stop_words="english", min_df=3)
    mvec.fit([t for t, f in zip(texts, fam_train) if f])
    Mt = mvec.transform(texts)
    msvd = TruncatedSVD(SVD_DIM, random_state=1).fit(Mt[fam_train])
    Em = normalize(msvd.transform(Mt))
    km = KMeans(n_regions, n_init=3, random_state=0).fit(Em[fam_train])
    cent = normalize(km.cluster_centers_)
    sim = Em @ cent.T
    region = sim.argmax(1)
    dist = 1.0 - sim.max(1)
    med = np.array([np.median(dist[fam_train & (region == r)]) if (fam_train & (region == r)).sum() else 1.0
                    for r in range(n_regions)])
    oom = dist / np.maximum(med[region], 1e-6)

    out = dict(y=y, role=role, length=length, Xs=Xs.astype(np.float32), region=region, oom=oom,
               Em=Em.astype(np.float32), familiar=familiar, novel=novel, centroids=cent)
    np.savez_compressed(path, **out)
    sp.save_npz(spath, Xt)
    out["Xt"] = Xt
    return out


def make_tasks(familiar, novel, seed=SPLIT_SEED + 2, n_fam=60, n_a=30, n_b=30):
    """Disjoint k-way tasks (k in 3..5). fam/A drawn only from familiar categories
    (A = new combinations never in fam). B contains 1-3 NOVEL categories."""
    rng = np.random.default_rng(seed)
    seen = set()

    def draw(pool_fn):
        while True:
            k = int(rng.integers(3, 6))
            cats = pool_fn(k)
            key = tuple(sorted(int(c) for c in cats))
            if key not in seen:
                seen.add(key)
                return key

    fam = [draw(lambda k: rng.choice(familiar, k, replace=False)) for _ in range(n_fam)]
    A = [draw(lambda k: rng.choice(familiar, k, replace=False)) for _ in range(n_a)]

    def b_pool(k):
        nn = int(rng.integers(1, min(3, k - 1) + 1))
        c = list(rng.choice(novel, nn, replace=False)) + list(rng.choice(familiar, k - nn, replace=False))
        return c
    B = [draw(b_pool) for _ in range(n_b)]
    return dict(fam=fam, A=A, B=B)
