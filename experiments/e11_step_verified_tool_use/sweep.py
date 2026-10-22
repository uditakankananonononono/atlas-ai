"""Post-hoc sensitivity sweep: how does the verified-minus-baseline
gap move with the two authored repair probabilities?
Disclosed as post-hoc in RESULTS.md; not part of the registered
measurement."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                '..', '..', 'backend'))
import actor as actor_mod
import run as run_mod
import tasks as tasks_mod


def cell(repair_fix, retry_fix, taskset):
    actor_mod.REPAIR_FIX = repair_fix
    actor_mod.RETRY_FIX = retry_fix
    v = b = 0
    n = 0
    for task in taskset:
        for seed in run_mod.SEEDS:
            n += 1
            v += run_mod._run_verified(task, seed)['success']
            b += run_mod._run_baseline(task, seed)['success']
    return v / n, b / n


def main():
    taskset = tasks_mod.HELD_OUT
    print('held-out (60 tasks x 3 seeds per cell)')
    print('REPAIR_FIX \\ RETRY_FIX | ' +
          ' | '.join('%.1f' % r for r in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)))
    for repair in (0.6, 0.8, 0.92, 1.0):
        cells = []
        for retry in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
            v, b = cell(repair, retry, taskset)
            cells.append('%+.3f' % (v - b))
        print('%.2f                   | %s' % (repair, ' | '.join(cells)))
    actor_mod.REPAIR_FIX = 0.92
    actor_mod.RETRY_FIX = 0.60


if __name__ == '__main__':
    main()
