"""E9: skill genome. Usage: python run_experiment.py [n_seeds] [budget]"""
from __future__ import annotations
import json, sys, random, time
from multiprocessing import Pool
from tasks import make_set, SEEN_THEMES, THEMES, NOVEL_THEMES
from agent import Agent, evaluate
from genome import make_skill

N_ACQ, N_VAL, N_TEST = 120, 40, 60
CHECK = (0, 60, 120)

def theme_aligned(prog):
    return any(any(t[i:i + len(prog)] == prog for i in range(len(t) - len(prog) + 1)) for t in THEMES[:7]) and len(prog) >= 2

def run_seed(args):
    seed, budget = args
    acq = make_set(seed, "a", N_ACQ, SEEN_THEMES)
    val = make_set(seed, "v", N_VAL, list(range(10)), forbid={t.signature() for t in acq})
    sigs = {t.signature() for t in acq} | {t.signature() for t in val}
    test = make_set(seed, "t", N_TEST, list(range(10)), forbid=frozenset(sigs))   # disjoint tasks
    assert not ({t.signature() for t in test} & sigs)
    conds = {
        "nolib": dict(mode="nolib"),
        "admit_all": dict(mode="admit_all"),
        "gated": dict(mode="gated"),
        "gated_margin1_posthoc": dict(mode="gated", margin=1),
        "gated_induced_only": dict(mode="gated", use_rewrite=False, use_combine=False),
    }
    out = {"seed": seed, "conds": {}}
    for name, kw in conds.items():
        ag = Agent(budget=budget, val_tasks=val, **kw)
        curve = {}
        for i, t in enumerate(acq):
            if i in CHECK:
                curve[i] = evaluate(test, ag.library, budget)
            ag.step(t)
            if (i + 1) % 20 == 0:
                ag.combine_round()
        curve[N_ACQ] = evaluate(test, ag.library, budget)
        lib = ag.library
        out["conds"][name] = {
            "curve": {k: v for k, v in curve.items()},
            "lib_size": len(lib),
            "lib_theme_aligned": sum(theme_aligned(s.program) for s in lib),
            "lib_origins": {o: sum(s.origin == o for s in lib) for o in ("induced", "rewritten", "combined")},
            "lib_programs": [list(s.program) for s in lib],
            "decisions": ag.log,
            "n_failure_cases_recorded": sum(len(s.failure_cases) for s in lib),
        }
        if name == "gated":   # random-library control of the same size (e7 convention): random contiguous 2-3 op programs
            rng = random.Random(f"{seed}-rand")
            from ops import NAMES
            rl = []
            while len(rl) < max(len(lib), 1):
                p = tuple(rng.choice(NAMES) for _ in range(rng.choice([2, 3])))
                if all(s.program != p for s in rl):
                    rl.append(make_skill(f"r{len(rl)}", p, "induced", [((1, 2, 3), (1, 2, 3))]))
            # random skills get precondition-free, contract-free genomes (no tests to infer from): strongest honest control
            for s in rl:
                from genome import Skill
                s.precondition = frozenset(); s.expected = frozenset()
            out["conds"]["random_lib_same_size"] = {"curve": {N_ACQ: evaluate(test, rl, budget)}, "lib_size": len(rl)}
    out["test_meta"] = [(t.theme, t.rich) for t in test]
    return out

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 2500
    t0 = time.time()
    with Pool(2) as p:
        rows = p.map(run_seed, [(s, budget) for s in range(n)])
    json.dump({"budget": budget, "rows": rows}, open("results.json", "w"))
    print("done", time.time() - t0)
