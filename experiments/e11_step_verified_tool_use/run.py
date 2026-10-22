"""E11 harness: baseline ReAct-style loop vs prediction-contract
step-verified loop, same actor, same tasks, paired seeds.

Baseline: the actor's steps execute directly.  WorldErrors come back
as error observations (the ReAct failure signal); the actor may
retry.  Silent corruptions (mis-transcribed writes) produce no error
signal and flow into the final answer.

Verified: instinct_models.stepverify.run_verified_loop.  Pre-execution
schema/precondition violations block the call (never executed);
post-execution effect-predicate violations hand the actor a
structured Violation.  WorldErrors that slip past the pre-gate are
converted to observations and caught by the spec effect floor.

Usage: python3 run.py [dev|heldout|dev-text|heldout-text|dev-mut|heldout-mut]
Writes rows_<split>.jsonl and prints the summary table.
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                '..', '..', 'backend'))
from instinct_models.stepverify import (StepRecord, run_verified_loop)

import actor as actor_mod
import tasks as tasks_mod
import world as world_mod

MAX_STEPS = 25
MAX_REPAIRS = 2
SEEDS = (11, 22, 33)


class _ErrSignal:
    stage = 'world_error'
    tool = ''
    detail = 'execution error observation'


def _run_baseline(task, seed, retry_fix=None, collect=None):
    """ReAct-style: propose -> execute -> observe, error text included.
    retry_fix overrides the actor's repair probability for this run
    (the equal-probability control passes REPAIR_FIX).  collect, when
    a dict, receives 'history' and 'actor' for training-time reward
    scoring (rev10 StepTool replication); no behavior change."""
    saved = actor_mod.RETRY_FIX
    if retry_fix is not None:
        actor_mod.RETRY_FIX = retry_fix
    try:
        state = {'files': dict(task['files'])}
        act = actor_mod.make_actor(task, seed, verified=False)
        history = []
        violations = 0
        steps = 0
        finished_answer = None
        while steps < MAX_STEPS:
            # the actor detects error observations from its own history;
            # there is no verifier signal in the baseline condition
            step = act(task, tuple(history), None)
            if step is None:
                break
            try:
                obs, state = world_mod.execute(state, step.tool,
                                               dict(step.args))
            except world_mod.WorldError as e:
                obs = 'ERROR: %s' % e
                violations += 1
            history.append(StepRecord(step, obs, 0, ()))
            steps += 1
            if step.tool == 'finish' and not str(obs).startswith('ERROR:'):
                finished_answer = step.args.get('answer')
                break
        result = dict(
            success=tasks_mod.grade(task, state, finished_answer),
            steps=steps, error_obs=violations, blocked=0,
            effect_misses=0,
            silent_fail=(finished_answer is not None
                         and finished_answer != task['answer']),
            finished=finished_answer is not None)
        if collect is not None:
            collect['history'] = list(history)
            collect['actor'] = act
            collect['result'] = result
        return result
    finally:
        actor_mod.RETRY_FIX = saved


# rev5: the schema-control baseline validates tool ARGUMENTS only
# (presence, types, integer-text shape) before executing - no
# preconditions on state (path existence is NOT schema), no effect
# predicates.  This is the "any careful framework does input
# validation" control; it isolates what the prediction contract adds
# beyond schema checking.
_SCHEMA_CHECKS = {
    'list': {},
    'read': {'path': str},
    'write': {'path': str, 'text': str},
    'append': {'path': str, 'text': str},
    'add': {'a': 'int-text', 'b': 'int-text'},
    'concat': {'a': str, 'b': str, 'sep': str},
    'scale': {'path': str, 'factor': 'int-text'},
    'finish': {'answer': str},
}


def _schema_error(tool, args):
    checks = _SCHEMA_CHECKS.get(tool)
    if checks is None:
        return 'no such tool: %s' % tool
    for name, kind in checks.items():
        if name not in args:
            return 'missing arg: %s' % name
        v = args[name]
        if kind is str:
            if not isinstance(v, str):
                return 'arg %s must be str, got %s' % (name,
                                                       type(v).__name__)
        else:
            try:
                int(v)
            except (TypeError, ValueError):
                return 'arg %s must be integer text, got %r' % (name, v)
    return None


def _run_baseline_schema(task, seed, retry_fix=None, free_rejects=False):
    """ReAct-style loop + argument-schema validation before execution.
    A schema rejection is recorded as an error observation (the call
    is not executed), so the actor retries it with the same repair
    probability as any other failure.  free_rejects=True gives the
    schema control the verified loop's free-block convention
    (rejections do not consume the step budget) - used ONLY by the
    accounting sweep, never in the registered numbers."""
    saved = actor_mod.RETRY_FIX
    if retry_fix is not None:
        actor_mod.RETRY_FIX = retry_fix
    try:
        state = {'files': dict(task['files'])}
        act = actor_mod.make_actor(task, seed, verified=False)
        history = []
        violations = 0
        schema_blocks = 0
        steps = 0
        finished_answer = None
        while steps < MAX_STEPS:
            step = act(task, tuple(history), None)
            if step is None:
                break
            err = _schema_error(step.tool, step.args)
            if err is not None:
                obs = 'ERROR: schema: %s' % err
                schema_blocks += 1
            else:
                try:
                    obs, state = world_mod.execute(state, step.tool,
                                                   dict(step.args))
                except world_mod.WorldError as e:
                    obs = 'ERROR: %s' % e
                    violations += 1
            history.append(StepRecord(step, obs, 0, ()))
            if not (free_rejects and err is not None):
                steps += 1
            if step.tool == 'finish' and not str(obs).startswith('ERROR:'):
                finished_answer = step.args.get('answer')
                break
        return dict(success=tasks_mod.grade(task, state, finished_answer),
                    steps=steps, error_obs=violations,
                    schema_blocked=schema_blocks, blocked=0,
                    effect_misses=0,
                    silent_fail=(finished_answer is not None
                                 and finished_answer != task['answer']),
                    finished=finished_answer is not None)
    finally:
        actor_mod.RETRY_FIX = saved


def _run_verified(task, seed, actor_factory=None, tools=None):
    """actor_factory(task, seed) and tools default to the standard
    verified condition; noise_sweep overrides both."""
    state = {'files': dict(task['files'])}
    act = (actor_factory(task, seed) if actor_factory
           else actor_mod.make_actor(task, seed, verified=True))

    def execute(st, tool, args):
        try:
            return world_mod.execute(st, tool, args)
        except world_mod.WorldError as e:
            return 'ERROR: %s' % e, st

    result = run_verified_loop(act, task,
                               tools if tools is not None
                               else world_mod.TOOLS, state,
                               execute, max_steps=MAX_STEPS,
                               max_repairs_per_step=MAX_REPAIRS)
    state = result.final_state
    finished_answer = None
    for rec in result.steps:
        if rec.step.tool == 'finish':
            finished_answer = rec.step.args.get('answer')
    return dict(success=tasks_mod.grade(task, state, finished_answer),
                steps=len(result.steps), error_obs=0,
                blocked=result.blocked,
                effect_misses=result.effect_misses,
                silent_fail=(finished_answer is not None
                             and finished_answer != task['answer']),
                finished=finished_answer is not None,
                exhausted=result.exhausted)


def _run_verified_paid(task, seed):
    """Verified loop with ATTEMPT-based budgeting: pre-gate blocks and
    effect violations consume budget too (equalized accounting
    against the baseline and schema loops).  Mirrors
    stepverify.run_verified_loop semantics exactly, including the
    repair cap; pinned equal to _run_verified whenever the budget
    never binds.  Accounting-sweep only; the registered numbers use
    run_verified_loop's accepted-history budgeting."""
    from instinct_models.stepverify import StepVerifier, StepRecord
    state = {'files': dict(task['files'])}
    act = actor_mod.make_actor(task, seed, verified=True)
    verifier = StepVerifier(world_mod.TOOLS)

    def execute(st, tool, args):
        try:
            return world_mod.execute(st, tool, args)
        except world_mod.WorldError as e:
            return 'ERROR: %s' % e, st

    history = []
    violation = None
    blocked = 0
    effect_misses = 0
    repairs = 0
    attempts = 0
    exhausted = False
    while attempts < MAX_STEPS:
        step = act(task, tuple(history), violation)
        if step is None:
            break
        attempts += 1
        v = verifier.verify_pre(step, state)
        if v is not None:
            blocked += 1
            repairs += 1
            if repairs > MAX_REPAIRS:
                exhausted = True
                break
            violation = v
            continue
        before = state
        obs, state = execute(state, step.tool, dict(step.args))
        v = verifier.verify_post(step, before, obs, state)
        history.append(StepRecord(step, obs, repairs, ()))
        repairs = 0
        if v is not None:
            effect_misses += 1
        violation = v
    else:
        exhausted = True
    finished_answer = None
    for rec in history:
        if rec.step.tool == 'finish':
            finished_answer = rec.step.args.get('answer')
    return dict(success=tasks_mod.grade(task, state, finished_answer),
                steps=len(history), error_obs=0, blocked=blocked,
                effect_misses=effect_misses,
                silent_fail=(finished_answer is not None
                             and finished_answer != task['answer']),
                finished=finished_answer is not None,
                exhausted=exhausted)


def _bootstrap_diff(pairs, reps=2000, seed=7):
    """Paired bootstrap on the success-rate difference."""
    rng = random.Random(seed)
    n = len(pairs)
    # paired resample
    diffs = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        v = sum(pairs[i][0] for i in idx) / n
        b = sum(pairs[i][1] for i in idx) / n
        diffs.append(v - b)
    diffs.sort()
    lo = diffs[int(0.025 * reps)]
    hi = diffs[int(0.975 * reps)]
    return lo, hi


def main(split):
    taskset = {'dev': tasks_mod.DEV,
               'heldout': tasks_mod.HELD_OUT,
               'dev-text': tasks_mod.DEV_TEXT,
               'heldout-text': tasks_mod.HELD_OUT_TEXT,
               'dev-mut': tasks_mod.DEV_MUT,
               'heldout-mut': tasks_mod.HELD_OUT_MUT}[split]
    rows = []
    for task in taskset:
        for seed in SEEDS:
            vb = _run_baseline(task, seed)
            ve = _run_baseline(task, seed, retry_fix=actor_mod.REPAIR_FIX)
            vs = _run_baseline_schema(task, seed)
            vv = _run_verified(task, seed)
            rows.append(dict(id=task['id'], family=task['family'],
                             seed=seed, baseline=vb, baseline_eq=ve,
                             baseline_schema=vs, verified=vv))
    with open('rows_%s.jsonl' % split, 'w') as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + '\n')
    n = len(rows)
    b_succ = sum(r['baseline']['success'] for r in rows)
    e_succ = sum(r['baseline_eq']['success'] for r in rows)
    s_succ = sum(r['baseline_schema']['success'] for r in rows)
    v_succ = sum(r['verified']['success'] for r in rows)
    b_silent = sum(r['baseline']['silent_fail'] for r in rows)
    v_silent = sum(r['verified']['silent_fail'] for r in rows)
    v_blocked = sum(r['verified']['blocked'] for r in rows)
    v_misses = sum(r['verified']['effect_misses'] for r in rows)
    b_err = sum(r['baseline']['error_obs'] for r in rows)
    pairs = [(r['verified']['success'], r['baseline']['success'])
             for r in rows]
    lo, hi = _bootstrap_diff(pairs)
    pairs_eq = [(r['verified']['success'], r['baseline_eq']['success'])
                for r in rows]
    lo_e, hi_e = _bootstrap_diff(pairs_eq)
    pairs_sc = [(r['verified']['success'],
                 r['baseline_schema']['success']) for r in rows]
    lo_s, hi_s = _bootstrap_diff(pairs_sc)
    print('split=%s runs=%d (tasks=%d x seeds=%d)' % (split, n, len(taskset),
                                                      len(SEEDS)))
    print('success: verified %d/%d = %.3f | baseline %d/%d = %.3f | '
          'baseline-eq %d/%d = %.3f | baseline-schema %d/%d = %.3f'
          % (v_succ, n, v_succ / n, b_succ, n, b_succ / n,
             e_succ, n, e_succ / n, s_succ, n, s_succ / n))
    print('paired diff vs baseline %.3f  bootstrap95 [%.3f, %.3f]'
          % ((v_succ - b_succ) / n, lo, hi))
    print('HEADLINE paired diff vs baseline-eq %.3f  bootstrap95 '
          '[%.3f, %.3f]' % ((v_succ - e_succ) / n, lo_e, hi_e))
    print('SCHEMA CONTROL paired diff vs baseline-schema %.3f  '
          'bootstrap95 [%.3f, %.3f]'
          % ((v_succ - s_succ) / n, lo_s, hi_s))
    print('schema control blocked %d calls'
          % sum(r['baseline_schema']['schema_blocked'] for r in rows))
    print('silent wrong answers: verified %d | baseline %d'
          % (v_silent, b_silent))
    print('verified blocked calls %d, effect misses %d | '
          'baseline error observations %d' % (v_blocked, v_misses, b_err))
    for fam in sorted({r['family'] for r in rows}):
        sub = [r for r in rows if r['family'] == fam]
        m = len(sub)
        print('  family %s: verified %.3f baseline %.3f baseline-eq %.3f'
              % (fam,
                 sum(r['verified']['success'] for r in sub) / m,
                 sum(r['baseline']['success'] for r in sub) / m,
                 sum(r['baseline_eq']['success'] for r in sub) / m))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'dev')
