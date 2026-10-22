"""rev15b (A59): recompute the registered rev12 0.5B probe numbers from
the committed rows_llm_*.jsonl (raw call logs).

Checks, against the rev12 RESULTS section:
- llm-base: per-task ERROR observations (12,16,7,10,17,5,8,13,7,11),
  total 106 - replayed through world.execute (the baseline loop's
  semantics: a call executes, an error is just an observation).
- llm-ver: 0 effect misses, 3 pre-gate blocks, 3 parse failures
  (all on H09) - via catch_audit.replay (production parser + verified
  loop semantics); parse failures are logged rows whose raw output the
  production parser rejects.
- llm-ver-noexp: 0 effect misses, 32 pre-gate blocks.
- 548 logged generations total.

Run: python3 recompute_rev12.py  (exit 0 = all registered numbers
reproduce;AssertionError names the first mismatch).
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', 'backend'))

import world as world_mod                      # noqa: E402
import tasks as tasks_mod                      # noqa: E402
from actor_llm import LLMActor                 # noqa: E402
from instinct_models.stepverify import (       # noqa: E402
    StepVerifier, Step, StepRecord)

TASKS = {t['id']: t for t in tasks_mod.HELD_OUT[:10]}


def load(cond):
    rows = collections.defaultdict(list)
    with open(os.path.join(HERE, 'rows_llm_%s.jsonl' % cond)) as f:
        for line in f:
            r = json.loads(line)
            rows[r['task']].append(r)
    return rows


def main():
    # llm-base: execute every logged call in order, count ERROR obs
    base = load('base')
    per_task = {}
    total_rows = 0
    for tid in sorted(base):
        state = {'files': dict(TASKS[tid]['files'])}
        errs = 0
        for r in sorted(base[tid], key=lambda x: x['step']):
            total_rows += 1
            try:
                obs, state = world_mod.execute(state, r['tool'],
                                               dict(r['args']))
            except Exception as e:
                obs = 'ERROR: %s' % e
            if str(obs).startswith('ERROR'):
                errs += 1
        per_task[tid] = errs
    got = [per_task['H%02d' % i] for i in range(10)]
    want = [12, 16, 7, 10, 17, 5, 8, 13, 7, 11]
    assert got == want, (got, want)
    assert sum(got) == 106
    print('llm-base: per-task ERROR observations %s reproduce; total 106'
          % got)

    # verified arms: replay through the production parser + loop.
    # catch_audit.replay hardcodes expect=True; rev12's live vernoexp
    # runs parsed with expect=False (contracts 'none' strips expect
    # tags), so the replay below is catch_audit.replay with an expect
    # flag, mirroring the live semantics per arm. (With expect=True
    # the vernoexp rows additionally carry 3 prediction-mismatch
    # warnings on H01/H07 - the 0.5B emitted EXPECT lines anyway and
    # its arithmetic predictions were wrong; the calls themselves
    # executed fine. The live arm never parsed them.)
    def replay(task, rows, want_expect):
        q = sorted(rows, key=lambda r: r['step'])

        def actor(_task, _history, _violation):
            if not q:
                return None
            r = q.pop(0)
            if 'parse_error' in r:
                return Step('__format_failure__', {})
            try:
                tool, args, expect = LLMActor.parse_output(r['raw'],
                                                           want_expect)
            except ValueError:
                return Step('__format_failure__', {})
            return Step(tool, args, expect=expect)

        verifier = StepVerifier(world_mod.TOOLS)
        state = {'files': dict(task['files'])}
        history, blocked, repairs, violation, viols = [], 0, 0, None, []
        accepted = []
        while len(history) < 25:
            step = actor(task, None, violation)
            if step is None:
                break
            v = verifier.verify_pre(step, state)
            if v is not None:
                blocked += 1
                viols.append(v)
                repairs += 1
                if repairs > 2:
                    break
                violation = v
                continue
            before = state
            try:
                observation, state = world_mod.execute(
                    state, step.tool, dict(step.args))
            except Exception as e:
                observation = 'ERROR: %s' % e
            v = verifier.verify_post(step, before, observation, state)
            history.append(StepRecord(step, observation, repairs,
                                      tuple(viols)))
            repairs, viols, violation = 0, [], None
            accepted.append((step.tool, observation,
                             v.detail if v else None))
            if v is not None:
                violation = v
        return accepted, blocked

    for cond, want_block, want_pf in [('ver', 3, 3), ('vernoexp', 32, 0)]:
        rows = load(cond)
        total_rows += sum(len(v) for v in rows.values())
        miss = block = pf = 0
        pf_tasks = collections.Counter()
        for tid in sorted(rows):
            for r in rows[tid]:
                raw = r.get('raw', '')
                try:
                    LLMActor.parse_output(raw, 'noexp' not in cond)
                except ValueError:
                    pf += 1
                    pf_tasks[tid] += 1
            accepted, blocked = replay(TASKS[tid], rows[tid],
                                       'noexp' not in cond)
            miss += sum(1 for a in accepted if a[2] is not None)
            block += blocked
        # llm_sweep accounting: a parse failure in a verified loop is
        # blocked by the pre-gate (unknown_tool) and counted in BOTH
        # `blocked` and `parse_failures`; rev12's ver blocks ARE the 3
        # format failures (see the rev12 section).
        assert miss == 0, (cond, miss)
        assert block == want_block, (cond, block, want_block)
        assert pf == want_pf, (cond, pf)
        print('llm-%s: 0 effect misses, %d pre-gate blocks, %d parse '
              'failures reproduce%s'
              % (cond, want_block, pf,
                 ' (all on %s)' % ', '.join(sorted(pf_tasks))
                 if pf_tasks else ''))

    assert total_rows == 548, total_rows
    print('total logged generations: 548 reproduce')
    print('recompute_rev12: all registered rev12 numbers reproduce')


if __name__ == '__main__':
    main()
