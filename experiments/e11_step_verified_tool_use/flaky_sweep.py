"""rev9: the spec effect floor's measured contribution - flaky
execution world.

World flag EXEC_FAULT_P: a write/append silently stores truncated
text with that probability (seeded per task+seed, conditions paired).
Four conditions on the int held-out tasks:
  baseline    : ReAct loop, no checks
  floor-only  : verified loop, actor predicates ALL stripped
                (p_drop=1.0), full registry incl. spec effect floors
                -> only the FLOOR can catch a fault
  preds-only  : verified loop, actor predicates intact, registry
                effect floors stripped -> only the ACTOR'S STATED
                PREDICTIONS can catch a fault
  verified    : full mechanism
  baseline-eq : baseline with retry_fix raised to REPAIR_FIX (the
                strict comparison: repairs can't be the explanation)

FAULT VISIBILITY (pre-registered fairness rule): the truncation is
SILENT in the observation text ('wrote N chars' truthfully describes
the args) for EVERY condition; the verified-side conditions see the
fault only through post-execution state checks.  The baseline
receives byte-identical observations to what it would see with no
fault channel.  (A REAL ReAct agent could read the file back and
notice; the scripted baseline never semantically inspects non-error
observations - the A39 non-reading caveat applies.)

PRE-REGISTERED FALSIFICATION (stated before the numbers are
reported): the floor's claimed contribution is floor-only minus
baseline-eq on the flaky held-out.  Results counting AGAINST the
floor: (a) that paired difference is not positive (bootstrap 95% CI
includes 0) - the floor adds nothing even in its home channel; or
(b) floor-only matches or beats preds-only - the actor-predicate
channel would add nothing in this world.  Either outcome gets
reported as the headline.

The floor's measured contribution is floor-only minus baseline.  On
the non-flaky corpus that difference is exactly 0 (rev3 p_drop=1.0
cell, A39's floor-removal mutant): the floor checks
obs/args/state self-consistency and every authored error there is an
INTENT error.  Execution faults are the channel the floor owns.
Post-hoc, disclosed in RESULTS.md."""
import dataclasses
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                '..', '..', 'backend'))
import actor as actor_mod  # noqa: E402
import noise_sweep as ns  # noqa: E402
import run as run_mod  # noqa: E402
import tasks as tasks_mod  # noqa: E402
import world as world_mod  # noqa: E402

FAULT_P = 0.12


def _floors_off():
    return [dataclasses.replace(t, effect=None)
            for t in world_mod.TOOLS]


def cell(taskset):
    succ = dict(baseline=[], eq=[], floor=[], preds=[], verified=[])
    misses = dict(floor=0, preds=0)
    n = 0
    for task in taskset:
        for seed in run_mod.SEEDS:
            n += 1
            key = '%s-%d' % (task['id'], seed)
            world_mod.seed_faults(key)
            succ['baseline'].append(
                run_mod._run_baseline(task, seed)['success'])
            world_mod.seed_faults(key)
            succ['eq'].append(run_mod._run_baseline(
                task, seed, retry_fix=actor_mod.REPAIR_FIX)['success'])
            world_mod.seed_faults(key)
            r = run_mod._run_verified(
                task, seed, actor_factory=ns._noisy_factory(1.0))
            succ['floor'].append(r['success'])
            misses['floor'] += r['effect_misses']
            world_mod.seed_faults(key)
            r = run_mod._run_verified(task, seed, tools=_floors_off())
            succ['preds'].append(r['success'])
            misses['preds'] += r['effect_misses']
            world_mod.seed_faults(key)
            succ['verified'].append(
                run_mod._run_verified(task, seed)['success'])
    out = {k: sum(v) / n for k, v in succ.items()}
    out['misses'] = misses
    out['ci_floor_eq'] = run_mod._bootstrap_diff(
        list(zip(succ['floor'], succ['eq'])))
    out['ci_preds_eq'] = run_mod._bootstrap_diff(
        list(zip(succ['preds'], succ['eq'])))
    out['ci_floor_preds'] = run_mod._bootstrap_diff(
        list(zip(succ['floor'], succ['preds'])))
    return out, n


def main():
    world_mod.EXEC_FAULT_P = FAULT_P
    try:
        for split, taskset in (('dev', tasks_mod.DEV),
                               ('heldout', tasks_mod.HELD_OUT)):
            res, n = cell(taskset)
            print('%s flaky (fault_p=%.2f, n=%d):' % (split, FAULT_P, n))
            print('  baseline %.3f | baseline-eq %.3f | floor-only '
                  '%.3f | preds-only %.3f | verified %.3f'
                  % (res['baseline'], res['eq'], res['floor'],
                     res['preds'], res['verified']))
            print('  STRICT floor-only - baseline-eq %+.3f [%.3f, %.3f]'
                  % (res['floor'] - res['eq'], res['ci_floor_eq'][0],
                     res['ci_floor_eq'][1]))
            print('  preds-only - baseline-eq %+.3f [%.3f, %.3f]'
                  % (res['preds'] - res['eq'], res['ci_preds_eq'][0],
                     res['ci_preds_eq'][1]))
            print('  floor-only - preds-only %+.3f [%.3f, %.3f]'
                  % (res['floor'] - res['preds'],
                     res['ci_floor_preds'][0], res['ci_floor_preds'][1]))
            print('  floor effect-miss repairs %d | preds effect-miss'
                  ' repairs %d'
                  % (res['misses']['floor'], res['misses']['preds']))
    finally:
        world_mod.EXEC_FAULT_P = 0.0


if __name__ == '__main__':
    main()
