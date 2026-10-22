"""Real-model LLM sweep driver (rev12 validity probe, rev13 1.5B probe).

A local Qwen2.5-Instruct GGUF (via llama.cpp llama-server, pinned)
drives the UNCHANGED baseline and verified loops, 3 conditions:

  llm-base       _run_baseline, model actor, no contracts
  llm-ver        _run_verified, model actor + EXPECT contracts
  llm-ver-noexp  _run_verified, model actor, EXPECT stripped (parent
                 addition 1: isolates the prediction-contract channel
                 from the pre-gate + floor)

This docstring describes the MECHANISM only.  The pinned model, GGUF
sha256, runtime build, generation parameters (temperature, seed,
max_tokens), task slice (rev12: HELD_OUT[:10]; rev13: HELD_OUT[:30]),
row file prefix and harness limits live in the run's meta.json: rev12
-> rows_llm_meta.json; rev13 -> rows15_llm_meta.json.  Both runs were
pre-registered to parent BEFORE any numbers.

Parent addition 2: EVERY raw model output is logged per step in the
rows jsonl (fields: task, condition, step, raw, parsed tool/args or
parse_error); format failures per task per condition are reported
separately from verifier blocks so the probe cannot silently measure
formatting instead of tool use.  Format failures enter the loops as
Step('__format_failure__') (pre-gate block in verified, ERROR
observation in baseline) - disclosed accounting: `blocked` includes
them.  Rows are checkpointed per run; the done-manifest is the resume
file."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                '..', '..', 'backend'))
import actor as actor_mod  # noqa: E402
import actor_llm  # noqa: E402
import run as run_mod  # noqa: E402
import tasks as tasks_mod  # noqa: E402
import world as world_mod  # noqa: E402

# Harness robustness (disclosed): the scripted actor never emitted a call
# whose args a tool implementation indexes blindly, so world.execute can
# raise non-WorldError exceptions (e.g. KeyError on a missing 'a') that
# _run_baseline does not catch.  A real tool API returns a 400-style error
# instead of crashing the client harness, so for the LLM probe ONLY we
# wrap execute to convert any unexpected exception into a WorldError,
# which the baseline already records as an ERROR observation.  The
# verified pre-gate is untouched (its schema check runs first anyway).
_REAL_EXECUTE = world_mod.execute


def _guarded_execute(state, tool, args):
    try:
        return _REAL_EXECUTE(state, tool, args)
    except world_mod.WorldError:
        raise
    except Exception as e:
        raise world_mod.WorldError('malformed call: %s' % e)


world_mod.execute = _guarded_execute

URL = os.environ.get('LLM_URL', 'http://127.0.0.1:8137')
N_TASKS = int(os.environ.get('LLM_TASKS_N', '10'))
TASKS = tasks_mod.HELD_OUT[:N_TASKS]
SEED = int(os.environ.get('LLM_SEED', '0'))
PREFIX = os.environ.get('LLM_ROWS_PREFIX', 'rows_llm')
HERE = os.path.dirname(os.path.abspath(__file__))
DONE_PATH = os.path.join(HERE, PREFIX + '_done.txt')


def _load_done():
    try:
        return set(open(DONE_PATH).read().split())
    except OSError:
        return set()


def _mark_done(key):
    with open(DONE_PATH, 'a') as f:
        f.write(key + '\n')


def _llm_factory(want_expect):
    def factory(task, seed):
        return actor_llm.LLMActor(task, URL, want_expect)
    return factory


_LAST_ACTOR = []


def _patched_make_actor(t, s, verified=False):
    a = actor_llm.LLMActor(t, URL, False)
    _LAST_ACTOR.append(a)
    return a


def run():
    conditions = ['llm-base', 'llm-ver', 'llm-ver-noexp']
    rows = {c: [] for c in conditions}
    summary = {c: [] for c in conditions}
    done = _load_done()
    if done:
        print('resuming: %d runs already done' % len(done), flush=True)
    saved = actor_mod.make_actor
    try:
        for task in TASKS:
            for cond in conditions:
                if cond == 'llm-base':
                    actor_mod.make_actor = _patched_make_actor
                    res = run_mod._run_baseline(task, SEED)
                    actor_mod.make_actor = saved
                    actor = _LAST_ACTOR.pop()
                else:
                    actor = actor_llm.LLMActor(task, URL,
                                               cond == 'llm-ver')
                    res = run_mod._run_verified(
                        task, SEED, actor_factory=lambda t, s: actor)
                key = '%s|%s' % (task['id'], cond)
                if key in done:
                    continue
                step_rows = []
                for i, entry in enumerate(actor.raw_log):
                    row = {'task': task['id'], 'family': task['family'],
                           'condition': cond, 'step': i}
                    row.update(entry)
                    step_rows.append(row)
                path = os.path.join(HERE, '%s_%s.jsonl'
                                    % (PREFIX, cond.replace('llm-', '')
                                       .replace('-', '')))
                with open(path, 'a') as f:      # checkpoint per run
                    for row in step_rows:
                        f.write(json.dumps(row, sort_keys=True) + '\n')
                rows[cond].extend(step_rows)
                summary[cond].append(dict(
                    task=task['id'], family=task['family'], **res,
                    parse_failures=actor.parse_failures))
                _mark_done(key)
                print('%s %-14s %-8s success=%s steps=%d blocked=%d '
                      'misses=%d err_obs=%d parse_fail=%d'
                      % (task['id'], cond, task['family'], res['success'],
                         res['steps'], res['blocked'],
                         res['effect_misses'], res['error_obs'],
                         actor.parse_failures), flush=True)
    finally:
        actor_mod.make_actor = saved
    print('\n=== SUMMARY (per condition, n=%d tasks this session) ==='
          % len(TASKS))
    for cond in conditions:
        runs = summary[cond]
        n = len(runs)
        print('%s: success %d/%d | blocked %d | effect_misses %d | '
              'error_obs %d | silent_fail %d | parse_failures %d'
              % (cond, sum(r['success'] for r in runs), n,
                 sum(r['blocked'] for r in runs),
                 sum(r['effect_misses'] for r in runs),
                 sum(r['error_obs'] for r in runs),
                 sum(r['silent_fail'] for r in runs),
                 sum(r['parse_failures'] for r in runs)))
    return summary


if __name__ == '__main__':
    run()
