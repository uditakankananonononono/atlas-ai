"""rev3: verifier-noise sensitivity - sound-but-incomplete checking.

Two degradation axes on the verified condition, held-out tasks:
  p_drop : probability the actor FAILS to state an effect prediction
           for a step (expect stripped).  The drop stream is seeded
           per task+seed only.  Cells are paired by task and seed,
           but NOT strictly nested: once a dropped predicate changes
           a trajectory, the draw streams desynchronize across p
           values (A33 measured 11/360 held-out runs where the
           superset property fails).
  gates  : on  = full TOOLS registry (preconditions + spec effect
                  floors)
           off = registry with pre=None and effect=None (schema
                 checks only)
At p_drop=1.0 with gates off the verified condition is the baseline
loop wearing a harness - except that its error-observation repairs
still use REPAIR_FIX (the actor was built with verified=True), so
the exact convergence target is the EQUAL-PROBABILITY control, not
the 0.60 baseline.  noise_sweep asserts that cell reproduces the
baseline-eq success counts EXACTLY (same seeds, same actor; the
verified=True flag otherwise only attaches predictions, which are
all dropped).  Disclosed as post-hoc in RESULTS.md; not part of the
registered measurement."""
import dataclasses
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                '..', '..', 'backend'))
from instinct_models.stepverify import run_verified_loop  # noqa: F401,E402

import actor as actor_mod  # noqa: E402
import run as run_mod  # noqa: E402
import tasks as tasks_mod  # noqa: E402
import world as world_mod  # noqa: E402

P_DROPS = (0.0, 0.25, 0.5, 0.75, 1.0)


def _noisy_factory(p_drop):
    def factory(task, seed):
        inner = actor_mod.make_actor(task, seed, verified=True)
        rng = random.Random('noise-%s-%d' % (task['id'], seed))

        def act(t, history, violation):
            step = inner(t, history, violation)
            if step is not None and step.expect is not None \
                    and rng.random() < p_drop:
                stripped = dataclasses.replace(step, expect=None)
                # the inner actor tracks its pending step by object
                # identity; re-point it at the stripped step or the
                # plan never advances
                if inner.pending is not None \
                        and inner.pending[1] is step:
                    inner.pending = (inner.pending[0], stripped)
                step = stripped
            return step
        return act
    return factory


def _gates_off():
    return [dataclasses.replace(t, pre=None, effect=None)
            for t in world_mod.TOOLS]


def grid(taskset):
    out = {}
    for gates in (True, False):
        tools = None if gates else _gates_off()
        for p in P_DROPS:
            v = 0
            n = 0
            for task in taskset:
                for seed in run_mod.SEEDS:
                    n += 1
                    v += run_mod._run_verified(
                        task, seed,
                        actor_factory=_noisy_factory(p),
                        tools=tools)['success']
            out[(gates, p)] = v / n
    return out


def main():
    for split, taskset in (('heldout', tasks_mod.HELD_OUT),
                           ('heldout-text', tasks_mod.HELD_OUT_TEXT)):
        g = grid(taskset)
        b = sum(run_mod._run_baseline(t, s)['success']
                for t in taskset for s in run_mod.SEEDS)
        e = sum(run_mod._run_baseline(t, s,
                                      retry_fix=actor_mod.REPAIR_FIX
                                      )['success']
                for t in taskset for s in run_mod.SEEDS)
        n = len(taskset) * len(run_mod.SEEDS)
        # convergence floor: full degradation must equal the
        # equal-probability control (repair probability survives
        # degradation; verification does not)
        floor = 0
        for task in taskset:
            for seed in run_mod.SEEDS:
                floor += run_mod._run_verified(
                    task, seed, actor_factory=_noisy_factory(1.0),
                    tools=_gates_off())['success']
        assert floor == e, (floor, e)
        print('%s: baseline %.3f | baseline-eq %.3f (n=%d)'
              % (split, b / n, e / n, n))
        print('p_drop | gates-on | gates-off')
        for p in P_DROPS:
            print('%.2f   | %.3f    | %.3f'
                  % (p, g[(True, p)], g[(False, p)]))


if __name__ == '__main__':
    main()
