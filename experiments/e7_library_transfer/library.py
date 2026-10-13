import itertools, random
from collections import defaultdict
from dsl import PRIMS, make_tasks, solve, verify, flat

GENEROUS = 20000


def solved_programs(tasks, lib=None):
    out = []
    for t in tasks:
        p, n = solve(t, lib or {}, GENEROUS)
        if p is not None and verify(t, p, lib or {}):
            out.append((t, flat(p, lib or {})))
    return out


def candidates(sols, min_tasks=2, min_domains=2):
    cnt = defaultdict(set)
    for t, p in sols:
        for L in (2, 3):
            for i in range(len(p) - L + 1):
                cnt[p[i:i + L]].add((t["desc"], t["domain"]))
    return [c for c, s in cnt.items() if len(s) >= min_tasks and len({d for _, d in s}) >= min_domains]


def n_solved(tasks, lib, budget):
    c = 0
    for t in tasks:
        p, _ = solve(t, lib, budget)
        c += p is not None and verify(t, p, lib)
    return c


def learn(train_tasks, budget, seed=0, min_domains=2):
    """Promote a macro only if it raises the number of solved VALIDATION tasks (other half of training tasks) at `budget`."""
    r = random.Random(seed)
    idx = list(range(len(train_tasks))); r.shuffle(idx)
    half = len(idx) // 2
    fit = [train_tasks[i] for i in idx[:half]]; val = [train_tasks[i] for i in idx[half:]]
    cands = candidates(solved_programs(fit), min_domains=min_domains)
    lib = {}
    base = n_solved(val, lib, budget)
    log = []
    for c in sorted(cands):
        name = "m_" + "_".join(c)
        trial = dict(lib); trial[name] = c
        s = n_solved(val, trial, budget)
        log.append((name, base, s))
        if s > base:
            lib, base = trial, s
    return lib, log


def random_lib(k, seed):
    r = random.Random(seed); names = list(PRIMS)
    return {f"r{i}": tuple(r.choice(names) for _ in range(r.choice([2, 3]))) for i in range(k)}
