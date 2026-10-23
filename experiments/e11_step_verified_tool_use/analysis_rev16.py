"""rev16 analysis: recompute the pre-registered endpoints from the
committed rows16_llm_*.jsonl and assert them against the run-recorded
SUMMARY (rows16_llm_runlog.txt).

Pre-registered endpoints (prereg pinned lane-local pre-run; hash 91c32ddd, per this lane's account lost in the 2026-10-22 wipe and not fetchable; parent ack 05:03 IST, transcript record):
success, wasted catches (catches that are immediate repetitions of an
already-caught identical call), blocked, parse failures.

rev16b (A55 first audit): wasted catches are now computed PER TASK
(adjacent equal keys inside one task's miss sequence) and STRICT
(consecutive ACCEPTED steps, both caught, same call); the rev16 ship
concatenated misses across tasks, counting 13 cross-task adjacencies
for C0 and 13 for A2 as repeats.  Early-termination (repair-budget
exhaustion) and accepted-step totals are reported per arm.

Replay: C0 (llm-ver) and A1 (llm-ver-none) through catch_audit-style
replay with expect=True (both arms parse expects; ver-none's lever is
prompt-level discipline, not stripping); A2/A3 (guard arms) through
llm_sweep._run_verified_guard with a replay actor feeding the logged
raw calls back in order.  Run: python3 analysis_rev16.py
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
import llm_sweep                               # noqa: E402
from actor_llm import LLMActor                 # noqa: E402
from instinct_models.stepverify import (       # noqa: E402
    StepVerifier, Step, StepRecord)

TASKS = {t['id']: t for t in tasks_mod.HELD_OUT[30:60]}
ARMS = {'llm-ver': 'ver', 'llm-ver-none': 'vernone',
        'llm-ver-guard': 'verguard', 'llm-ver-none-guard': 'vernoneguard'}
# run-recorded SUMMARY from rows16_llm_runlog.txt
RECORDED = {'llm-ver': dict(success=0, blocked=7, miss=181, pf=1),
            'llm-ver-none': dict(success=0, blocked=13, miss=9, pf=2),
            'llm-ver-guard': dict(success=0, blocked=49, miss=43, pf=1),
            'llm-ver-none-guard': dict(success=0, blocked=16, miss=6, pf=2)}


def load(cond):
    rows = collections.defaultdict(list)
    with open(os.path.join(HERE, 'rows16_llm_%s.jsonl' % ARMS[cond])) as f:
        for line in f:
            r = json.loads(line)
            rows[r['task']].append(r)
    return rows


def replay_actor(rows):
    q = sorted(rows, key=lambda r: r['step'])

    def actor(_task, _history, _violation):
        if not q:
            return None
        r = q.pop(0)
        if 'parse_error' in r:
            return Step('__format_failure__', {})
        try:
            tool, args, expect = LLMActor.parse_output(r['raw'], True)
        except ValueError:
            return Step('__format_failure__', {})
        return Step(tool, args, expect=expect)
    return actor


def replay_plain(task, rows):
    """catch_audit.replay semantics (verified loop, no guard).
    Returns (seq, blocked, steps) where seq is the accepted-call
    sequence [(tool, argsjson, missed)]."""
    actor = replay_actor(rows)
    verifier = StepVerifier(world_mod.TOOLS)
    state = {'files': dict(task['files'])}
    history, blocked, repairs, violation, viols = [], 0, 0, None, []
    seq = []
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
            obs, state = world_mod.execute(state, step.tool,
                                           dict(step.args))
        except Exception as e:
            obs = 'ERROR: %s' % e
        v = verifier.verify_post(step, before, obs, state)
        history.append(StepRecord(step, obs, repairs, tuple(viols)))
        repairs, viols, violation = 0, [], None
        seq.append((step.tool, json.dumps(step.args, sort_keys=True),
                    v is not None))
        if v is not None:
            violation = v
    return seq, blocked, len(history)


def replay_plain_x(task, rows):
    """replay_plain + exhausted flag (repair-budget break)."""
    actor = replay_actor(rows)
    verifier = StepVerifier(world_mod.TOOLS)
    state = {'files': dict(task['files'])}
    history, blocked, repairs, violation, viols = [], 0, 0, None, []
    seq = []
    exhausted = False
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
                exhausted = True
                break
            violation = v
            continue
        before = state
        try:
            obs, state = world_mod.execute(state, step.tool,
                                           dict(step.args))
        except Exception as e:
            obs = 'ERROR: %s' % e
        v = verifier.verify_post(step, before, obs, state)
        history.append(StepRecord(step, obs, repairs, tuple(viols)))
        repairs, viols, violation = 0, [], None
        seq.append((step.tool, json.dumps(step.args, sort_keys=True),
                    v is not None))
        if v is not None:
            violation = v
    return seq, blocked, len(history), exhausted


def replay_guard(task, rows):
    res = llm_sweep._run_verified_guard(task, 0, replay_actor(rows))
    return res


def replay_guard_seq(task, rows):
    """_run_verified_guard replicated with miss-sequence tracking
    (same semantics; returns (seq, blocked, guard_blocks, steps))."""
    from instinct_models.stepverify import Violation
    actor = replay_actor(rows)
    verifier = StepVerifier(world_mod.TOOLS)
    state = {'files': dict(task['files'])}
    history, blocked, guard_blocks, repairs = [], 0, 0, 0
    violation = None
    catch_counts = {}
    seq = []
    exhausted = False
    while len(history) < 25:
        step = actor(task, None, violation)
        if step is None:
            break
        key = (step.tool, json.dumps(step.args, sort_keys=True))
        v = verifier.verify_pre(step, state)
        if v is None and catch_counts.get(key, 0) >= 2:
            v = Violation('repeat_guard', step.tool,
                          'repeated already-caught call: '
                          'do something different')
            guard_blocks += 1
        if v is not None:
            blocked += 1
            repairs += 1
            if repairs > 2:
                exhausted = True
                break
            violation = v
            continue
        before = state
        try:
            obs, state = world_mod.execute(state, step.tool,
                                           dict(step.args))
        except Exception as e:
            obs = 'ERROR: %s' % e
        v = verifier.verify_post(step, before, obs, state)
        history.append(StepRecord(step, obs, repairs, ()))
        repairs = 0
        violation = None
        seq.append((step.tool, json.dumps(step.args, sort_keys=True),
                    v is not None))
        if v is not None:
            catch_counts[key] = catch_counts.get(key, 0) + 1
            violation = v
    return seq, blocked, guard_blocks, len(history), exhausted


def wasted(misses):
    return sum(1 for i in range(1, len(misses)) if misses[i] == misses[i - 1])


def wasted_strict(seq):
    """consecutive ACCEPTED steps, both caught, same call."""
    return sum(1 for j in range(1, len(seq))
               if seq[j][2] and seq[j - 1][2]
               and (seq[j][0], seq[j][1]) == (seq[j - 1][0],
                                              seq[j - 1][1]))


def chains(seq):
    """Maximal runs of consecutive caught identical calls.
    Returns (length_dist, adapted, corrected, terminal)."""
    dist = collections.Counter()
    adapted = corrected = terminal = 0
    i = 0
    while i < len(seq):
        if not seq[i][2]:
            i += 1
            continue
        j = i
        key = (seq[i][0], seq[i][1])
        while j + 1 < len(seq) and seq[j + 1][2] and \
                (seq[j + 1][0], seq[j + 1][1]) == key:
            j += 1
        dist[j - i + 1] += 1
        nxt = seq[j + 1] if j + 1 < len(seq) else None
        if nxt is None:
            terminal += 1
        elif (nxt[0], nxt[1]) == key and not nxt[2]:
            corrected += 1
        else:
            adapted += 1
        i = j + 1
    return dist, adapted, corrected, terminal


def compute():
    """Returns {cond: dict(miss=, blocked=, pf=, wasted=)} with
    asserts against the run-recorded SUMMARY."""
    out = {}
    per_task_misses = {}
    wmaps = {}
    for cond in ARMS:
        rows = load(cond)
        tot_miss = tot_block = tot_pf = 0
        tot_guard = 0
        tot_steps = tot_exh = 0
        w_task = w_strict = 0
        pm = {}
        wm = {}
        for tid in sorted(rows):
            pf = 0
            for r in rows[tid]:
                try:
                    LLMActor.parse_output(r.get('raw', ''), True)
                except (ValueError, KeyError):
                    pf += 1
            tot_pf += pf
            if 'guard' in cond:
                seq, blocked, guard_blocks, steps, exh = \
                    replay_guard_seq(TASKS[tid], rows[tid])
                res = replay_guard(TASKS[tid], rows[tid])
                assert len([c for c in seq if c[2]]) == \
                    res['effect_misses'], (cond, tid)
                assert blocked == res['blocked'], (cond, tid)
                assert guard_blocks == res['guard_blocks'], (cond, tid)
                tot_guard += guard_blocks
                tot_miss += res['effect_misses']
                tot_block += blocked
                pm[tid] = res['effect_misses']
            else:
                seq, blocked, steps, exh = replay_plain_x(
                    TASKS[tid], rows[tid])
                tot_miss += len([c for c in seq if c[2]])
                tot_block += blocked
                pm[tid] = len([c for c in seq if c[2]])
            tot_steps += steps
            tot_exh += exh
            task_misses = [(c[0], c[1]) for c in seq if c[2]]
            tw = wasted(task_misses)
            w_task += tw
            w_strict += wasted_strict(seq)
            wm[tid] = tw
        per_task_misses[cond] = pm
        wmaps[cond] = wm
        rec = RECORDED[cond]
        assert tot_miss == rec['miss'], (cond, tot_miss, rec['miss'])
        assert tot_block == rec['blocked'], (cond, tot_block,
                                             rec['blocked'])
        assert tot_pf == rec['pf'], (cond, tot_pf, rec['pf'])
        print('%s: replay reproduces run-recorded - misses %d, '
              'blocked %d, parse failures %d'
              % (cond, tot_miss, tot_block, tot_pf))
        out[cond] = dict(miss=tot_miss, blocked=tot_block, pf=tot_pf,
                         wasted=w_task, wasted_strict=w_strict,
                         steps=tot_steps, repair_exhausted=tot_exh)
        print('   wasted catches per task: %d of %d misses; strict '
              '(consecutive accepted, same call): %d'
              % (w_task, tot_miss, w_strict))
        print('   accepted steps %d; repair-budget exhaustion (steps '
              'below 25 - NOT the production `exhausted` flag, which '
              'also fires at the 25-step cap and is true for 30/30 '
              'runs in every arm) ended %d/30 runs early'
              % (tot_steps, tot_exh))
        if 'guard' in cond:
            print('   guard_blocks %d (pre-gate blocks %d)'
                  % (tot_guard, tot_block - tot_guard))
        else:
            all_seqs = []
            for tid in sorted(rows):
                seq, _, _, _ = (replay_guard_seq(TASKS[tid], rows[tid])
                                if 'guard' in cond else
                                replay_plain_x(TASKS[tid], rows[tid]))
                all_seqs.extend(seq)
            dist, ad, co, te = chains(all_seqs)
            print('   chains %s | ends adapted %d corrected %d '
                  'terminal %d' % (dict(sorted(dist.items())), ad, co,
                                   te))
    out['per_task_misses'] = per_task_misses
    out['wasted_per_task'] = wmaps
    return out


def main():
    out = compute()
    per_task_misses = out['per_task_misses']
    # paired per-task comparison C0 vs arms
    c0 = per_task_misses['llm-ver']
    print('\nper-task effect_misses (task: C0 / A1 / A2 / A3):')
    for tid in sorted(c0):
        print('  %s: %d / %d / %d / %d'
              % (tid, c0[tid], per_task_misses['llm-ver-none'][tid],
                 per_task_misses['llm-ver-guard'][tid],
                 per_task_misses['llm-ver-none-guard'][tid]))
    for arm in ('llm-ver-none', 'llm-ver-guard', 'llm-ver-none-guard'):
        a = per_task_misses[arm]
        lt = sum(1 for t in c0 if a[t] < c0[t])
        eq = sum(1 for t in c0 if a[t] == c0[t])
        gt = sum(1 for t in c0 if a[t] > c0[t])
        print('paired vs C0, %s: fewer misses on %d/30 tasks, '
              'equal %d, more %d' % (arm, lt, eq, gt))
        # paired wasted per task
    # paired per-task wasted (A59, rev16d)
    wc0 = out['wasted_per_task']['llm-ver']
    for arm in ('llm-ver-none', 'llm-ver-guard', 'llm-ver-none-guard'):
        wa = out['wasted_per_task'][arm]
        lt = sum(1 for t in wc0 if wa[t] < wc0[t])
        eq = sum(1 for t in wc0 if wa[t] == wc0[t])
        gt = [t for t in wc0 if wa[t] > wc0[t]]
        print('paired wasted vs C0, %s: lower %d/30, equal %d, '
              'higher %d %s' % (arm, lt, eq, len(gt), gt))
    # pre-registered verdict check
    assert sum(c0.values()) == 181
    print('\nC0 finished tasks: 0/30 (run-recorded; success '
          'comparison vacuous per prereg)')
    print('wasted-catch totals per task (rev16b): C0 %d, A1 %d, '
          'A2 %d, A3 %d'
          % (out['llm-ver']['wasted'], out['llm-ver-none']['wasted'],
             out['llm-ver-guard']['wasted'],
             out['llm-ver-none-guard']['wasted']))
    print('wasted-catch totals strict: C0 %d, A1 %d, A2 %d, A3 %d'
          % (out['llm-ver']['wasted_strict'],
             out['llm-ver-none']['wasted_strict'],
             out['llm-ver-guard']['wasted_strict'],
             out['llm-ver-none-guard']['wasted_strict']))


if __name__ == '__main__':
    main()
