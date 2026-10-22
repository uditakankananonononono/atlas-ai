"""rev6: budget sensitivity - how does the verified-minus-baseline gap
move with the step budget (MAX_STEPS)?

Verified and baseline conditions share the same budget per cell;
baseline-eq and the rev5 baseline-schema control included per cell so
the equal-probability and schema-control headlines can be quoted at
every budget.  Post-hoc, disclosed in RESULTS.md; not part of the
registered measurement (which fixes MAX_STEPS = 25)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                '..', '..', 'backend'))
import actor as actor_mod  # noqa: E402
import run as run_mod  # noqa: E402
import tasks as tasks_mod  # noqa: E402

BUDGETS = (6, 10, 14, 18, 25)


def cell(taskset, budget):
    saved = run_mod.MAX_STEPS
    run_mod.MAX_STEPS = budget
    try:
        vf = vp = b = e = scf = scp = 0
        n = 0
        for task in taskset:
            for seed in run_mod.SEEDS:
                n += 1
                vf += run_mod._run_verified(task, seed)['success']
                vp += run_mod._run_verified_paid(task, seed)['success']
                b += run_mod._run_baseline(task, seed)['success']
                e += run_mod._run_baseline(
                    task, seed,
                    retry_fix=actor_mod.REPAIR_FIX)['success']
                scf += run_mod._run_baseline_schema(
                    task, seed, free_rejects=True)['success']
                scp += run_mod._run_baseline_schema(task,
                                                    seed)['success']
        return tuple(x / n for x in (vf, vp, b, e, scf, scp))
    finally:
        run_mod.MAX_STEPS = saved


def main():
    for split, taskset in (('heldout', tasks_mod.HELD_OUT),
                           ('heldout-text', tasks_mod.HELD_OUT_TEXT),
                           ('heldout-mut', tasks_mod.HELD_OUT_MUT)):
        print('%s (n=%d per cell)' % (split, len(taskset)
                                      * len(run_mod.SEEDS)))
        print('budget | ver-free | ver-paid | base | base-eq |'
              ' sch-free | sch-paid')
        for budget in BUDGETS:
            vf, vp, b, e, scf, scp = cell(taskset, budget)
            print('%6d | %.3f    | %.3f     | %.3f | %.3f   |'
                  ' %.3f     | %.3f'
                  % (budget, vf, vp, b, e, scf, scp))


if __name__ == '__main__':
    main()
