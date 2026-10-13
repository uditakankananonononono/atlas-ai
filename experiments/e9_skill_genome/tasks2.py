"""v2 task generator (SYNTHETIC). Stratified test/validation, extra-op pools split so test has extra-op sampling not used
in acquisition (primitives themselves still occur in acquisition themes), per-task random hidden inputs (no shared fixed probes), stricter disjointness."""
from __future__ import annotations
import random
from ops import NAMES
from tasks import THEMES, SEEN_THEMES, NOVEL_THEMES, Task, apply_ops, _poor, _rich

_EXTRA_ALL = [n for n in NAMES if n not in ("sort", "reverse")]
EXTRA_A = _EXTRA_ALL[:13]          # the only extra ops used by acquisition tasks
EXTRA_B = _EXTRA_ALL[13:]          # never sampled as the extra op in acquisition (6 of these ops, e.g. drop1/halve/mod5/mul2/sq/take3, still occur inside themes)
assert not set(EXTRA_A) & set(EXTRA_B)

_EDGES = [lambda r: (), lambda r: (r.randint(-9, 20),), lambda r: (r.randint(-9, 20),) * r.randint(2, 6),
          lambda r: tuple(sorted(r.randint(-9, 20) for _ in range(r.randint(2, 8)))),
          lambda r: tuple(sorted((r.randint(-9, 20) for _ in range(r.randint(2, 8))), reverse=True))]

def _hidden(rng, k=12):
    out = [e(rng) for e in rng.sample(_EDGES, 2)]
    while len(out) < k:
        out.append(tuple(rng.randint(-9, 20) for _ in range(rng.randint(0, 9))))
    return tuple(out)

def make_task2(rng, tid, themes, kind, pool, cat=""):
    """kind: 'full' (target = theme) or 'extra' (theme + extra, or first two ops + extra)."""
    while True:
        th = rng.choice(themes)
        base = THEMES[th]
        if kind == "full":
            target = base
        else:
            extra = rng.choice(pool)
            target = base + (extra,) if rng.random() < 0.5 else base[:2] + (extra,)
        rich = rng.random() < 0.5
        gen = _rich if rich else _poor
        tin = tuple(gen(rng) for _ in range(3))
        tout = tuple(apply_ops(target, x) for x in tin)
        if len(set(tout)) < 2 or all(len(o) == 0 for o in tout):
            continue
        hin = _hidden(rng)
        t = Task(tid, th, target, tin, tout, hin, tuple(apply_ops(target, x) for x in hin), rich)
        t.cat = cat
        return t

def sig(t):
    return (t.target, t.train_inputs, t.hidden_inputs)

def _train_inputs(tasks):
    return {x for t in tasks for x in t.train_inputs}

def make_acq(seed, n=120):
    rng = random.Random(f"{seed}-acq2")
    out, seen = [], set()
    while len(out) < n:
        kind = "full" if rng.random() < 0.3 else "extra"
        t = make_task2(rng, f"a{len(out)}", SEEN_THEMES, kind, EXTRA_A, "acq")
        if sig(t) not in seen:
            seen.add(sig(t)); out.append(t)
    return out

CATS = [("seen_full", SEEN_THEMES, "full", None), ("seen_extraA", SEEN_THEMES, "extra", EXTRA_A),
        ("seen_extraB_heldout_sampling", SEEN_THEMES, "extra", EXTRA_B), ("novel_theme", NOVEL_THEMES, "extra", _EXTRA_ALL)]

def make_stratified(seed, tag, per_cat, forbid_sigs, forbid_train):
    """Exactly per_cat tasks per category; train example inputs and full signatures disjoint from `forbid_*`."""
    rng = random.Random(f"{seed}-{tag}2")
    out, seen_sigs, seen_train = [], set(), set()
    for cat, themes, kind, pool in CATS:
        n = 0
        while n < per_cat:
            t = make_task2(rng, f"{tag}{len(out)}", themes, kind, pool, cat)
            if sig(t) in forbid_sigs or sig(t) in seen_sigs:
                continue
            if set(t.train_inputs) & (forbid_train | seen_train):
                continue
            seen_sigs.add(sig(t)); seen_train |= set(t.train_inputs); out.append(t); n += 1
    return out

def make_all(seed):
    acq = make_acq(seed)
    fs, ft = {sig(t) for t in acq}, _train_inputs(acq)
    val = make_stratified(seed, "v", 10, fs, ft)
    fs |= {sig(t) for t in val}; ft |= _train_inputs(val)
    test = make_stratified(seed, "t", 20, fs, ft)
    return acq, val, test
