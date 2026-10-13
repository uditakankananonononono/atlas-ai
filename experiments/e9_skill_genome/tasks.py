"""Authored synthetic task generator (SYNTHETIC; themes, ops, and distributions are the experimenter's)."""
from __future__ import annotations
import random
from dataclasses import dataclass
from ops import OPS, NAMES

THEMES = [
    ("abs", "dedupe", "sort"), ("filter_pos", "cumsum", "reverse"), ("dedupe", "sort_desc", "take3"),
    ("abs", "running_max", "halve"), ("filter_even", "mul2", "sort"), ("drop1", "pair_sum", "mod5"),
    ("sq", "filter_gt5", "dedupe"),
    ("reverse", "rotate1", "cumsum"), ("filter_odd", "add3", "sort_desc"), ("every2", "abs", "dedupe"),  # novel
]
SEEN_THEMES = list(range(7))
NOVEL_THEMES = [7, 8, 9]

def apply_ops(ops, x):
    for n in ops:
        x = OPS[n](x)
    return x

@dataclass
class Task:
    tid: str
    theme: int
    target: tuple
    train_inputs: tuple
    train_outputs: tuple
    hidden_inputs: tuple
    hidden_outputs: tuple
    rich: bool
    def signature(self):
        return (self.target, self.train_inputs)

def _poor(rng):
    n = rng.randint(4, 8)
    return tuple(rng.sample(range(0, 21), n))          # distinct, non-negative

def _rich(rng):
    n = rng.randint(4, 8)
    x = [rng.randint(-9, 20) for _ in range(n)]
    x[rng.randrange(n)] = x[rng.randrange(n)]           # likely a duplicate
    x[rng.randrange(n)] = -rng.randint(1, 9)            # a negative
    return tuple(x)

def _hidden(rng, k=12):
    out = [(), (5,), (7, 7, 7, 7), (-3, -3, 4)]
    while len(out) < k:
        n = rng.randint(0, 9)
        out.append(tuple(rng.randint(-9, 20) for _ in range(n)))
    return tuple(out)

def make_task(rng, tid, themes):
    while True:
        th = rng.choice(themes)
        base = THEMES[th]
        mode = rng.random()
        extra = rng.choice([n for n in NAMES if n not in ("sort", "reverse")])
        if mode < 0.4:
            target = base
        elif mode < 0.7:
            target = base + (extra,)
        else:
            target = base[:2] + (extra,)
        rich = rng.random() < 0.5
        gen = _rich if rich else _poor
        tin = tuple(gen(rng) for _ in range(3))
        tout = tuple(apply_ops(target, x) for x in tin)
        if len(set(tout)) < 2 or all(len(o) == 0 for o in tout):
            continue
        hin = _hidden(rng)
        hout = tuple(apply_ops(target, x) for x in hin)
        return Task(tid, th, target, tin, tout, hin, hout, rich)

def make_set(seed, tag, n, themes, forbid=frozenset()):
    rng = random.Random(f"{seed}-{tag}")
    tasks, sigs = [], set()
    while len(tasks) < n:
        t = make_task(rng, f"{tag}{len(tasks)}", themes)
        s = t.signature()
        if s in sigs or s in forbid:
            continue
        sigs.add(s); tasks.append(t)
    return tasks

def feedback(task, fn_apply):
    """Environment feedback after an answer: pass/fail on hidden inputs plus first counterexample."""
    for x, y in zip(task.hidden_inputs, task.hidden_outputs):
        try:
            got = tuple(fn_apply(x))
        except Exception:
            got = None
        if got != y:
            return False, (x, y, got)
    return True, None
