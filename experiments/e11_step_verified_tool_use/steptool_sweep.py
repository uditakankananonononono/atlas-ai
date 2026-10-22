"""rev10: StepTool (Yu et al. 2024, arXiv:2410.07745) replication in
the e11 world - the nearest published baseline mechanism, on equal
terms.

Mechanism replicated (paper section 4):
  step-grained reward shaping   r_t = a*SuccCalling(a_t, s_{t+1})
                                + Contribution(a_t, a_T)  for t < T
                                r_T = IsSolved(q, a_T)
  step-grained optimization     policy gradient over per-step
                                advantages built from those rewards.

Faithful substitutions (disclosed; the paper (sec 4.1.2) states
the framework allows flexible assignment of step-grained rewards,
including rule-based systems, and that acquisition can be adapted
to different settings - RULES-ONLY here is our substitution for
their rules+GPT-4 hybrid, whose annotation prompt is their
Figure 3):
  * backbone: the e11 scripted noisy actor.  The policy's stochastic
    decisions are its six fault draws (FAULT_NAMES); the trainable
    parameters are their logits.  REINFORCE with the exact analytic
    score function for Bernoulli draws: d log p(fired) / d theta
    = fired - p.
  * reward acquisition: world-oracle rules instead of rules+GPT-4
    (the paper's GPT-4 saw the whole trajectory; the oracle here is
    the training-time equivalent - labels are never used at test
    time).
  * SuccCalling(a_t, s_{t+1}) in {0,1}: 0 iff the call returned a
    world error observation.
  * Contribution(a_t, a_T) in {0..5}:
      error observation                       -> 0
      read of a required input (first time)   -> 4
      read of the output path (readback)      -> 3
      read of any other path, or duplicate    -> 1
      add / concat / scale, no error          -> 4
      write/append to the output path whose
        text equals the task answer           -> 5
      write/append to the output path, wrong  -> 1
      write/append elsewhere                  -> 1
    (redundant steps score low, as in the paper's description)
  * IsSolved(q, a_T) in {0,1}: the e11 grader.
  * normalization: rewards on a uniform [0,1] scale, so
    r_t = 0.5*SuccCalling + 0.5*(Contribution/5) (alpha = 0.5 under
    the /5 normalization), r_T = IsSolved.
  * advantage: A_t = G_t - mean_batch(total return) with gamma = 1
    (short episodic horizons).  This is the constant-baseline
    simplification of the paper's GAE value term - disclosed.
  * training set: the 20 dev tasks (the seen split); the held-out 60
    stay untouched until measurement.  Hyperparameters (lr 0.05,
    400 epochs x batch 16) fixed on dev only.

Equal-terms conditions measured on held-out (n=180, paired seeds,
MAX_STEPS=25 as registered):
  base            untrained actor, baseline loop     (registered)
  finalonly       actor trained with r_t = 0 for t<T (the paper's
                  PPO (Final Reward) BASELINE; equal in reward
                  structure to its RQ4 "w/o Step-grained Reward"
                  variant)
  steptool        actor trained with step-grained rewards
  verified        untrained actor + e11 verification (registered)
  steptool+ver    trained actor + e11 verification (stacking)

Pre-registered outcomes (messaged to parent before numbers locked):
  AGAINST the verifier: steptool >= verified (CI of the difference
  includes 0).  Replication FAILURE of the paper: steptool <=
  finalonly (step-grained advantage not positive).
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                '..', '..', 'backend'))
import actor as actor_mod  # noqa: E402
import run as run_mod  # noqa: E402
import tasks as tasks_mod  # noqa: E402

LR = 0.05
EPOCHS = 400
BATCH = 16
MASTER_SEED = 20261021
P_LO, P_HI = 0.005, 0.60
_GLOBALS = {'wrong_path': 'P_WRONG_PATH', 'slip': 'P_SLIP',
            'bad_add': 'P_BAD_ADD', 'bad_concat': 'P_BAD_CONCAT',
            'bad_factor': 'P_BAD_FACTOR', 'premature': 'P_PREMATURE'}


def _logit(p):
    return math.log(p / (1.0 - p))


def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def _get_probs():
    return {n: getattr(actor_mod, g) for n, g in _GLOBALS.items()}


def _set_probs(probs):
    for n, g in _GLOBALS.items():
        setattr(actor_mod, g, min(max(probs[n], P_LO), P_HI))


def step_reward(task, rec, seen):
    """(succ, contribution) for one non-final record."""
    step, obs = rec.step, rec.observation
    errored = isinstance(obs, str) and obs.startswith('ERROR:')
    succ = 0 if errored else 1
    if errored:
        return succ, 0
    tool, args = step.tool, step.args
    key = (tool, tuple(sorted(args.items())))
    if tool == 'read':
        if key in seen:
            c = 1
        elif args.get('path') in task['reads']:
            c = 4
        elif args.get('path') == task['out_path']:
            c = 3
        else:
            c = 1
    elif tool in ('add', 'concat', 'scale'):
        c = 4
    elif tool in ('write', 'append'):
        if args.get('path') == task['out_path']:
            c = 5 if args.get('text') == task['out_want'] else 1
        else:
            c = 1
    else:
        c = 1
    seen.add(key)
    return succ, c


def trajectory_rewards(task, history, success):
    """r_t per HISTORY record (aligned with the actor's emit index,
    so fault draws map to their step).  A successful terminal finish
    carries IsSolved; a mid-trajectory finish (premature, retried)
    scores like any other call."""
    rs = []
    seen = set()
    for i, rec in enumerate(history):
        if i == len(history) - 1 and rec.step.tool == 'finish':
            rs.append(1.0 if success else 0.0)
            continue
        succ, c = step_reward(task, rec, seen)
        rs.append(0.5 * succ + 0.5 * (c / 5.0))
    return rs


def _draw_grad(fired, p):
    """d log p(fired) / d theta for a Bernoulli(p=sigmoid(theta))."""
    return (1.0 - p) if fired else -p


def train(taskset, epochs=EPOCHS, batch=BATCH, lr=LR,
          step_grained=True, master_seed=MASTER_SEED):
    """REINFORCE over the six fault logits.  Returns (theta, curve)."""
    theta = {n: _logit(p) for n, p in _get_probs().items()}
    rng = random.Random(master_seed)
    saved = _get_probs()
    curve = []
    try:
        for ep in range(epochs):
            pairs = [(rng.choice(taskset), rng.randrange(1 << 30))
                     for _ in range(batch)]
            rollouts = []
            for task, seed in pairs:
                _set_probs({n: _sigmoid(theta[n]) for n in theta})
                collect = {}
                run_mod._run_baseline(task, seed, collect=collect)
                success = collect['result']['success']
                hist = collect['history']
                rs = trajectory_rewards(task, hist, success)
                if not step_grained:
                    rs = [0.0] * (len(rs) - 1) + [rs[-1]]
                # fault draws per step: history index aligned with the
                # actor's emit counter (non-finish steps only)
                drawmap = {}
                for emit, name, fired in collect['actor'].fault_log:
                    drawmap.setdefault(emit, []).append((name, fired))
                rollouts.append((rs, drawmap))
            totals = [sum(rs) for rs, _ in rollouts]
            mean_total = sum(totals) / len(totals)
            curve.append(mean_total)
            grad = {n: 0.0 for n in theta}
            probs = {n: min(max(_sigmoid(theta[n]), P_LO), P_HI)
                     for n in theta}
            for rs, drawmap in rollouts:
                for t in range(len(rs)):
                    a_t = sum(rs[t:]) - mean_total   # gamma = 1
                    for name, fired in drawmap.get(t, ()):
                        grad[name] += a_t * _draw_grad(
                            fired, probs[name])
            for n in theta:
                theta[n] += lr * grad[n] / len(rollouts)
    finally:
        _set_probs(saved)
    return theta, curve


def theta_probs(theta):
    return {n: min(max(_sigmoid(theta[n]), P_LO), P_HI)
            for n in theta}


def eval_split(taskset, probs=None, verified=False):
    saved = _get_probs()
    if probs is not None:
        _set_probs(probs)
    try:
        outs = []
        for task in taskset:
            for seed in run_mod.SEEDS:
                if verified:
                    outs.append(run_mod._run_verified(task,
                                                      seed)['success'])
                else:
                    outs.append(run_mod._run_baseline(task,
                                                      seed)['success'])
        return outs
    finally:
        _set_probs(saved)


def _rate(xs):
    return sum(xs) / len(xs)


def main():
    # one policy per world, trained on that world's dev split (the
    # paper trains per benchmark); held-out stays untouched
    for split, dev, taskset in (
            ('heldout', tasks_mod.DEV, tasks_mod.HELD_OUT),
            ('heldout-text', tasks_mod.DEV_TEXT,
             tasks_mod.HELD_OUT_TEXT),
            ('heldout-mut', tasks_mod.DEV_MUT,
             tasks_mod.HELD_OUT_MUT)):
        base_dev = _rate(eval_split(dev))
        print('%s: training StepTool (step-grained) on %s dev (%d '
              'tasks, %d epochs x %d)...'
              % (split, split, len(dev), EPOCHS, BATCH))
        theta_sg, curve_sg = train(dev, step_grained=True)
        sg_dev = _rate(eval_split(dev, probs=theta_probs(theta_sg)))
        print('  dev success: untrained %.3f -> trained %.3f'
              % (base_dev, sg_dev))
        print('  trained fault probs: %s' % {
            n: round(p, 4)
            for n, p in theta_probs(theta_sg).items()})
        print('%s: training final-only ablation (PPO Final '
              'Reward)...' % split)
        theta_fo, curve_fo = train(dev, step_grained=False)
        fo_dev = _rate(eval_split(dev, probs=theta_probs(theta_fo)))
        print('  dev success: untrained %.3f -> trained %.3f'
              % (base_dev, fo_dev))
        print('  trained fault probs: %s' % {
            n: round(p, 4)
            for n, p in theta_probs(theta_fo).items()})
        p_sg, p_fo = theta_probs(theta_sg), theta_probs(theta_fo)
        base = eval_split(taskset)
        fo = eval_split(taskset, probs=p_fo)
        sg = eval_split(taskset, probs=p_sg)
        ver = eval_split(taskset, verified=True)
        sgv = eval_split(taskset, probs=p_sg, verified=True)
        print('%s (n=%d per condition)' % (split, len(base)))
        print('  base %.3f | final-only %.3f | steptool %.3f | '
              'verified %.3f | steptool+ver %.3f'
              % (_rate(base), _rate(fo), _rate(sg), _rate(ver),
                 _rate(sgv)))
        lo, hi = run_mod._bootstrap_diff(list(zip(sg, fo)))
        print('  REPLICATION steptool - final-only: %+.3f [%+.3f, '
              '%+.3f]' % (_rate(sg) - _rate(fo), lo, hi))
        lo, hi = run_mod._bootstrap_diff(list(zip(ver, sg)))
        print('  EQUAL TERMS verified - steptool: %+.3f [%+.3f, '
              '%+.3f]' % (_rate(ver) - _rate(sg), lo, hi))
        lo, hi = run_mod._bootstrap_diff(list(zip(sgv, ver)))
        print('  STACKING steptool+ver - verified: %+.3f [%+.3f, '
              '%+.3f]' % (_rate(sgv) - _rate(ver), lo, hi))


if __name__ == '__main__':
    main()
