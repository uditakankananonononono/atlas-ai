"""E7 harness: program induction over int sequences across four authored domains.
Directions 1 (abstraction), 4 (verified skills), 7 (cross-domain transfer), 3 (loop comparison) share it.
Everything is synthetic: tasks and domain input generators are authored here."""
import itertools, random
from functools import lru_cache

PRIMS = {  # name -> (fn, returns_int)
    "inc": (lambda l: [x + 1 for x in l], False), "dbl": (lambda l: [2 * x for x in l], False),
    "neg": (lambda l: [-x for x in l], False), "comp3": (lambda l: [3 - x for x in l], False),
    "isGC": (lambda l: [1 if x in (1, 2) else 0 for x in l], False), "pos": (lambda l: [1 if x > 0 else 0 for x in l], False),
    "cumsum": (lambda l: list(itertools.accumulate(l)), False),
    "diff": (lambda l: [b - a for a, b in zip(l, l[1:])], False),
    "reverse": (lambda l: l[::-1], False), "sort": (lambda l: sorted(l), False),
    "sum": (lambda l: sum(l), True), "max": (lambda l: max(l), True), "min": (lambda l: min(l), True), "len": (lambda l: len(l), True),
}
LISTFNS = [k for k, v in PRIMS.items() if not v[1]]
INTFNS = [k for k, v in PRIMS.items() if v[1]]


def apply_prog(prog, x, lib):
    """prog: tuple of primitive or library names; library macros expand to tuples of names."""
    cur = x
    for name in prog:
        if name in lib:
            cur = apply_prog(lib[name], cur, lib)
        else:
            if isinstance(cur, int):
                return None
            cur = PRIMS[name][0](cur)
            if cur is None:
                return None
        if not isinstance(cur, int) and (len(cur) == 0 or len(cur) > 200):
            return None if len(cur) == 0 else cur
    return cur


def safe_apply(prog, x, lib):
    try:
        return apply_prog(prog, list(x), lib)
    except (ValueError, TypeError, IndexError):
        return None


def flat(prog, lib):
    out = []
    for n in prog:
        out += list(flat(lib[n], lib)) if n in lib else [n]
    return tuple(out)


def enumerate_progs(lib, max_depth=4):
    """Pipelines over (primitives + macros); macro costs 1 depth. Breadth-first by length."""
    names = list(PRIMS) + list(lib)
    for d in range(1, max_depth + 1):
        for p in itertools.product(names, repeat=d):
            yield p


COST = [0]


def solve(task, lib, budget, max_depth=4):
    """Returns (program or None, programs_evaluated). Accepts only if all train examples match; caller verifies on held-out."""
    n = 0
    for p in enumerate_progs(lib, max_depth):
        n += 1
        if n > budget:
            COST[0] += n - 1
            return None, n - 1
        if all(safe_apply(p, i, lib) == o for i, o in task["train"]):
            COST[0] += n
            return p, n
    COST[0] += n
    return None, n


def verify(task, prog, lib):
    return all(safe_apply(prog, i, lib) == o for i, o in task["test"])


# ---- authored domains: (name, target pipeline, description) ----
GEN = {
    "math": lambda r: [r.randint(-5, 9) for _ in range(r.randint(6, 12))],
    "bio": lambda r: [r.randint(0, 3) for _ in range(r.randint(7, 12))],
    "code": lambda r: [r.choice([1, -1]) for _ in range(r.randint(7, 12))],
    "physics": lambda r: [r.randint(0, 20) for _ in range(r.randint(7, 12))],
}
TARGETS = {
    "math": [("peak of shifted running totals", ("inc", "cumsum", "max")), ("sorted running totals reversed", ("cumsum", "sort", "reverse")),
             ("sum of sorted doubled differences", ("diff", "dbl", "sort", "sum")), ("largest drop of running totals", ("cumsum", "diff", "min")),
             ("reverse then peak running total", ("reverse", "cumsum", "max")), ("running totals of differences doubled", ("diff", "dbl", "cumsum")),
             ("lowest negated running total", ("neg", "cumsum", "min")), ("positives running count peak", ("pos", "cumsum", "max")),
             ("sorted differences reversed", ("diff", "sort", "reverse")), ("second difference peak", ("diff", "diff", "max"))],
    "bio": [("GC running count peak", ("isGC", "cumsum", "max")), ("reverse complement running sum", ("comp3", "reverse", "cumsum")),
            ("GC running count reversed", ("isGC", "cumsum", "reverse")), ("complement GC total", ("comp3", "isGC", "sum")),
            ("reverse complement sorted", ("comp3", "reverse", "sort")), ("GC running count sorted", ("isGC", "cumsum", "sort")),
            ("complement running total peak", ("comp3", "cumsum", "max")), ("GC flags reversed running", ("isGC", "reverse", "cumsum")),
            ("base step sorted reversed", ("diff", "sort", "reverse")), ("largest complement step", ("comp3", "diff", "max"))],
    "code": [("max nesting depth shifted", ("inc", "cumsum", "max")), ("depth profile sorted reversed", ("cumsum", "sort", "reverse")),
             ("deepest negative depth", ("neg", "cumsum", "min")), ("depth changes sorted", ("cumsum", "diff", "sort")),
             ("reverse scan peak depth", ("reverse", "cumsum", "max")), ("open count running peak", ("pos", "cumsum", "max")),
             ("depth profile reversed negated", ("cumsum", "reverse", "neg")), ("flags running reversed", ("pos", "cumsum", "reverse")),
             ("depth step min", ("cumsum", "diff", "min")), ("doubled depth peak", ("dbl", "cumsum", "max"))],
    "physics": [("peak position of integrated velocity shifted", ("inc", "cumsum", "max")), ("sorted accelerations reversed", ("diff", "diff", "sort", "reverse")),
                ("peak displacement of velocity", ("diff", "cumsum", "max")), ("reverse time acceleration peak", ("reverse", "diff", "diff", "max")),
                ("accumulated doubled velocity peak", ("diff", "dbl", "cumsum", "max")), ("net negative acceleration", ("diff", "diff", "neg", "sum")),
                ("sorted velocities reversed", ("diff", "sort", "reverse")), ("lowest running total of negated steps", ("diff", "neg", "cumsum", "min")),
                ("running energy proxy sorted", ("dbl", "cumsum", "sort")), ("positive step running peak", ("diff", "pos", "cumsum", "max"))],
}


def make_tasks(seed=0):
    r = random.Random(seed)
    tasks = []
    for dom, items in TARGETS.items():
        for desc, prog in items:
            ex = []
            while len(ex) < 16:
                x = GEN[dom](r)
                o = safe_apply(prog, x, {})
                if o is not None and (isinstance(o, int) or len(o) > 0):
                    ex.append((tuple(x), o))
            tasks.append(dict(domain=dom, desc=desc, target=prog, train=ex[:8], test=ex[8:]))
    return tasks
