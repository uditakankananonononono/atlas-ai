"""rev11: the ALIAS world - structural (plan-level) errors, and the
honest ceiling of step verification.

The actor can follow a heuristic bias pairing instead of the
statement's declared pairing (P_ALIAS draw at plan time).  SA bias
reads never exist (precondition block / error observation);
SB bias reads exist (self-consistent wrong plan - nothing can
catch it; the stated ceiling).

Conditions per sub-family (paired seeds, MAX_STEPS=25, n=90 = 30
tasks x 3 seeds each):
  base         untrained actor, baseline loop
  steptool     7-knob StepTool-trained actor (alias added to the
               rev10 six; trained on the alias dev split only)
  verified     untrained actor + e11 verification
  steptool+ver trained actor + verification (stacking)
  base-shuf    baseline, repair targets the SHUFFLED control pair
  ver-shuf     verified, repair targets the SHUFFLED control pair
The shuffled-label control isolates "repairs toward the STATEMENT"
from "repairs toward anything existing" (parent's addition).

PRE-REGISTERED (parent messages 2026-10-21, before numbers):
P_ALIAS init 0.50; dev 10+10 / held-out 30+30, generator seeds 7/8;
FOR verification = steptool+ver beats steptool on SA (CI positive);
CEILING = SB gaps ~0 across conditions (if not, the rev9 channel
decomposition is wrong and RESULTS must say so).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                '..', '..', 'backend'))
import actor as actor_mod  # noqa: E402
import run as run_mod  # noqa: E402
import steptool_sweep as st  # noqa: E402
import tasks as tasks_mod  # noqa: E402

st._GLOBALS = dict(st._GLOBALS, alias='P_ALIAS')


def _rate(xs):
    return sum(xs) / len(xs) if xs else float('nan')


def alias_fired(task, seed, p_alias):
    # for family-S tasks the alias draw is the actor's FIRST rng
    # call (plan construction, before any step): reconstructable
    import random as _r
    return _r.Random('actor-%s-%d' % (task['id'], seed)).random() \
        < p_alias


def eval_cond(taskset, probs=None, verified=False, shuffle=False):
    saved = {n: getattr(actor_mod, g) for n, g in st._GLOBALS.items()}
    saved_r = actor_mod.ALIAS_REPAIR
    if probs is not None:
        st._set_probs(probs)
    if shuffle:
        actor_mod.ALIAS_REPAIR = 'shuffle'
    try:
        outs = []
        for task in taskset:
            for seed in run_mod.SEEDS:
                fn = (run_mod._run_verified if verified
                      else run_mod._run_baseline)
                outs.append(fn(task, seed)['success'])
        return outs
    finally:
        st._set_probs(saved)
        actor_mod.ALIAS_REPAIR = saved_r


def main():
    dev = tasks_mod.DEV_ALIAS
    print('training 7-knob StepTool policy on alias dev (%d tasks)...'
          % len(dev))
    theta_sg, _ = st.train(dev, step_grained=True)
    p_sg = st.theta_probs(theta_sg)
    print('  trained probs: %s'
          % {n: round(p, 4) for n, p in p_sg.items()})
    for sub in ('SA', 'SB'):
        held = [t for t in tasks_mod.HELD_OUT_ALIAS
                if t['family'] == sub]
        base = eval_cond(held)
        sg = eval_cond(held, probs=p_sg)
        ver = eval_cond(held, verified=True)
        sgv = eval_cond(held, probs=p_sg, verified=True)
        bsh = eval_cond(held, shuffle=True)
        vsh = eval_cond(held, verified=True, shuffle=True)
        print('%s (n=%d per condition)' % (sub, len(base)))
        print('  base %.3f | steptool %.3f | verified %.3f | '
              'steptool+ver %.3f | base-shuf %.3f | ver-shuf %.3f'
              % (_rate(base), _rate(sg), _rate(ver), _rate(sgv),
                 _rate(bsh), _rate(vsh)))
        # conditioned on the alias draw (reconstructed per task+seed
        # and condition): the ceiling statement is about ALIAS-FIRED
        # runs only.  Output order is task-major: (held[i//3],
        # SEEDS[i%3]).
        conds = {'base': (base, 0.50), 'steptool': (sg, p_sg['alias']),
                 'verified': (ver, 0.50),
                 'steptool+ver': (sgv, p_sg['alias'])}
        for name, (vals, p) in conds.items():
            fired = [v for i, v in enumerate(vals)
                     if alias_fired(held[i // 3],
                                    run_mod.SEEDS[i % 3], p)]
            clean = [v for i, v in enumerate(vals)
                     if not alias_fired(held[i // 3],
                                        run_mod.SEEDS[i % 3], p)]
            print('  %s | alias-fired n=%d succ %.3f | not-fired '
                  'n=%d succ %.3f'
                  % (name, len(fired), _rate(fired), len(clean),
                     _rate(clean)))
        lo, hi = run_mod._bootstrap_diff(list(zip(sgv, sg)))
        print('  FOR-VERIFICATION steptool+ver - steptool: %+.3f '
              '[%+.3f, %+.3f]' % (_rate(sgv) - _rate(sg), lo, hi))
        lo, hi = run_mod._bootstrap_diff(list(zip(ver, base)))
        print('  verified - base: %+.3f [%+.3f, %+.3f]'
              % (_rate(ver) - _rate(base), lo, hi))
        lo, hi = run_mod._bootstrap_diff(list(zip(sg, base)))
        print('  steptool - base: %+.3f [%+.3f, %+.3f]'
              % (_rate(sg) - _rate(base), lo, hi))
        lo, hi = run_mod._bootstrap_diff(list(zip(vsh, ver)))
        print('  SHUFFLE CONTROL ver-shuf - ver: %+.3f [%+.3f, '
              '%+.3f]' % (_rate(vsh) - _rate(ver), lo, hi))
        lo, hi = run_mod._bootstrap_diff(list(zip(bsh, base)))
        print('  SHUFFLE CONTROL base-shuf - base: %+.3f [%+.3f, '
              '%+.3f]' % (_rate(bsh) - _rate(base), lo, hi))


if __name__ == '__main__':
    main()
