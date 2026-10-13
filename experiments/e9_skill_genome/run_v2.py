"""E9 v2. Usage: python run_v2.py n_seeds budget out.json [cond,cond,...]"""
from __future__ import annotations
import json, sys, random, time
from multiprocessing import Pool
from tasks2 import make_all, CATS
from agent import evaluate
from agent2 import Agent2
from genome import make_skill
from ops import NAMES
from run_experiment import theme_aligned

N_ACQ = 120
CHECK = (0, 60)
ALL = {
    "nolib": dict(mode="nolib"),
    "admit_all": dict(mode="admit_all"),
    "gated": dict(mode="gated"),
    "gated_audit": dict(mode="gated", audit=True),
    "gated_no_rewrite": dict(mode="gated", use_rewrite=False),
    "gated_no_combine": dict(mode="gated", use_combine=False),
    "joint_audit": dict(mode="gated", joint=True, audit=True),
}

def random_lib(seed, size, tag):
    rng = random.Random(f"{seed}-rand-{tag}")
    rl = []
    while len(rl) < size:                       # exactly `size` skills (empty when size is 0)
        p = tuple(rng.choice(NAMES) for _ in range(rng.choice([2, 3])))
        if all(s.program != p for s in rl):
            s = make_skill(f"r{len(rl)}", p, "induced", [((1, 2, 3), (1, 2, 3))])
            s.precondition = frozenset(); s.expected = frozenset()
            rl.append(s)
    return rl

def run_seed(args):
    seed, budget, conds = args
    acq, val, test = make_all(seed)
    out = {"seed": seed, "budget": budget, "conds": {}, "test_cat": [t.cat for t in test],
           "n_val": len(val), "n_test": len(test)}
    for name in conds:
        ag = Agent2(budget=budget, val_tasks=val, **ALL[name])
        curve = {}
        for i, t in enumerate(acq):
            if i in CHECK:
                curve[i] = evaluate(test, ag.library, budget)
            ag.step(t)
            if (i + 1) % 20 == 0:
                ag.combine_round()
                ag.joint_round()
            if (i + 1) % 40 == 0:
                ag.audit_round()
        curve[N_ACQ] = evaluate(test, ag.library, budget)
        lib = ag.library
        out["conds"][name] = {
            "curve": curve, "lib_size": len(lib),
            "lib_theme_aligned": sum(theme_aligned(s.program) for s in lib),
            "lib_programs": [list(s.program) for s in lib], "retired": ag.retired,
            "decisions": ag.log,
        }
        if name == "joint_audit" or (name == "gated" and "joint_audit" not in conds):
            out["conds"]["random_lib_same_size"] = {"curve": {N_ACQ: evaluate(test, random_lib(seed, len(lib), name), budget)},
                                                    "lib_size": len(lib), "matched_to": name}
    return out

if __name__ == "__main__":
    n, budget, path = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    conds = sys.argv[4].split(",") if len(sys.argv) > 4 else list(ALL)
    t0 = time.time()
    with Pool(2) as p:
        rows = p.map(run_seed, [(s, budget, conds) for s in range(n)])
    json.dump({"budget": budget, "rows": rows}, open(path, "w"))
    print("done", time.time() - t0)
