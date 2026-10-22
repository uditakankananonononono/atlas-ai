"""rev14 catch-quality audit (analysis-only, POST-HOC).

Deterministic replay of the COMMITTED rev13 llm-ver rows
(rows15_llm_ver.jsonl - every raw generation logged) through the
production parser, verifier and loop semantics (actor_llm.parse_output,
StepVerifier, run_verified_loop at MAX_STEPS=25, MAX_REPAIRS=2).  No
model, no network, no new measurement: the replay must reproduce the
registered rev13 totals EXACTLY (183 effect_misses, 12 pre-gate
blocks) - the assertion below pins the audit to the shipped rows.

Step semantics (auditor question, resolved): the jsonl 'step' field is
the index into the actor's raw call log (llm_sweep.py logs EVERY call:
accepted, blocked re-asks, parse failures) - NOT the budget counter.
The budget bounds ACCEPTED steps only (stepverify.py:
`while len(history) < max_steps:`; a blocked call `continue`s without
entering history, so blocks are free under the registered
accepted-history accounting).  Example closures: H00 llm-ver 29 logged
calls = 25 accepted + 4 blocked; H00 llm-ver-noexp 26 = 25 + 1.

Everything printed here is POST-HOC (not pre-registered): an audit of
rev13's subordinate counts, changing no registered number.
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
from instinct_models.stepverify import (       # noqa: E402
    StepVerifier, Step, StepRecord)
from actor_llm import LLMActor                 # noqa: E402

MAX_STEPS = 25
MAX_REPAIRS = 2


def replay(task, rows):
    """Feed the logged raw calls back through the production loop.

    Returns (accepted, blocked) where accepted is a list of
    (tool, canonical_args_json, observation, post_violation_detail).
    Mirrors stepverify.run_verified_loop line for line, with hooks."""
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

    verifier = StepVerifier(world_mod.TOOLS)
    state = {'files': dict(task['files'])}

    def execute(st, tool, args):
        try:
            return world_mod.execute(st, tool, args)
        except world_mod.WorldError as e:
            return 'ERROR: %s' % e, st

    history, blocked, repairs, violation, viols = [], 0, 0, None, []
    accepted = []
    while len(history) < MAX_STEPS:
        step = actor(task, None, violation)
        if step is None:
            break
        v = verifier.verify_pre(step, state)
        if v is not None:
            blocked += 1
            viols.append(v)
            repairs += 1
            if repairs > MAX_REPAIRS:
                break
            violation = v
            continue
        before = state
        observation, state = execute(state, step.tool, dict(step.args))
        v = verifier.verify_post(step, before, observation, state)
        history.append(StepRecord(step, observation, repairs,
                                  tuple(viols)))
        repairs, viols, violation = 0, [], None
        accepted.append((step.tool,
                         json.dumps(step.args, sort_keys=True),
                         observation,
                         v.detail if v else None))
        if v is not None:
            violation = v
    return accepted, blocked


def main():
    tasks = {t['id']: t for t in tasks_mod.HELD_OUT[:30]}
    rows_by_task = collections.defaultdict(list)
    with open(os.path.join(HERE, 'rows15_llm_ver.jsonl')) as f:
        for line in f:
            r = json.loads(line)
            rows_by_task[r['task']].append(r)

    total_miss = total_block = 0
    misses = []           # (task, accepted_index, tool, args_json, detail)
    per_task = collections.Counter()
    for tid in sorted(tasks):
        accepted, blocked = replay(tasks[tid], rows_by_task[tid])
        total_block += blocked
        for i, (tool, ajs, _obs, det) in enumerate(accepted):
            if det is not None:
                misses.append((tid, i, tool, ajs, det))
        per_task[tid] = sum(1 for a in accepted if a[3] is not None)
        total_miss += per_task[tid]

    # pin (rev15 rerun data): the replay must reproduce the registered
    # rev15 counts on the rerun rows (rev13 shipped 183/12; see RESULTS
    # rev15 changed-numbers table)
    assert total_miss == 182, total_miss
    assert total_block == 12, total_block

    print('registered totals reproduced: 182 effect_misses, 12 blocks')
    print('per-task catches:', dict(sorted(per_task.items())))
    by_tool = collections.Counter(m[2] for m in misses)
    print('catches by tool:', dict(by_tool))
    floor = sum(1 for m in misses if 'spec effect' in m[4])
    print('spec-floor violations: %d; actor-prediction: %d'
          % (floor, len(misses) - floor))

    uniq = {(m[0], m[2], m[3]) for m in misses}
    print('distinct caught (task, tool, args) calls: %d' % len(uniq))

    # chain analysis: maximal runs of consecutive caught repetitions of
    # one call, and the outcome of the step AFTER the chain ends
    chains = []
    for tid in sorted(tasks):
        accepted, _ = replay(tasks[tid], rows_by_task[tid])
        i = 0
        while i < len(accepted):
            tool, ajs, _obs, det = accepted[i]
            if det is None:
                i += 1
                continue
            j = i
            while (j + 1 < len(accepted)
                   and accepted[j + 1][:2] == (tool, ajs)
                   and accepted[j + 1][3] is not None):
                j += 1
            length = j - i + 1
            if j + 1 >= len(accepted):
                outcome = 'terminal'
            elif accepted[j + 1][:2] == (tool, ajs):
                outcome = 'repeat_success'   # same call, corrected EXPECT
            else:
                outcome = 'adapt'
            chains.append((tid, tool, ajs, length, outcome))
            i = j + 1
    assert sum(c[3] for c in chains) == total_miss
    lengths = collections.Counter(c[3] for c in chains)
    outcomes = collections.Counter(c[4] for c in chains)
    print('catch chains: %d; length distribution: %s'
          % (len(chains), dict(sorted(lengths.items()))))
    print('chain-end outcomes: adapt (different next call) %d; '
          'repeat with corrected contract %d; terminal (budget end) %d'
          % (outcomes['adapt'], outcomes['repeat_success'],
             outcomes['terminal']))
    print('within-chain repeats caught again: %d'
          % sum(c[3] - 1 for c in chains))
    print('length-18 chains: %s -> all terminal'
          % [(c[0], c[1]) for c in chains if c[3] == 18])


if __name__ == '__main__':
    main()
