"""E11 fixed task set: three authored families over the file world.

Every task is a dict:
  id, family, statement, files (initial world), answer (grader
  string), out_path (file the grader also checks), out_want.
Families:
  A 'aggregate': sum the integers in N named files, write the sum to
    an output file, finish with the sum.
  B 'chain': read x, read y, add, write, read back, finish with the
    read-back value.
  C 'distractor': like A but the directory contains similar-named
    decoy files that must NOT be read.
The split: 20 dev tasks (ids D*, used while designing) and 60
held-out tasks (ids H*, reported).  Everything is seeded and
enumerated here; nothing is learned from the held-out set.
"""
import random
from itertools import combinations


def _decoys(rng, real_paths, n):
    decoys = {}
    for path in real_paths:
        base, ext = path.rsplit('.', 1)
        for k in range(n):
            decoys['%s_%d.%s' % (base, k + 1, ext)] = str(
                rng.randint(-500, 500))
    return decoys


def make_tasks(split, count, seed):
    rng = random.Random('e11-%s-%d-%d' % (split, count, seed))
    tasks = []
    fams = ['A', 'B', 'C']
    for i in range(count):
        fam = fams[i % 3]
        tid = '%s%02d' % ('D' if split == 'dev' else 'H', i)
        if fam == 'A':
            n = rng.randint(3, 5)
            names = ['data%d.txt' % j for j in range(n)]
            vals = [rng.randint(-200, 200) for _ in range(n)]
            files = {nm: str(v) for nm, v in zip(names, vals)}
            total = sum(vals)
            tasks.append(dict(
                id=tid, family='A',
                statement=('sum the integers in %s, write the sum to '
                           'out.txt, then finish with it'
                           % ', '.join(names)),
                files=files, reads=names, answer=str(total),
                out_path='out.txt', out_want=str(total)))
        elif fam == 'B':
            x, y = rng.randint(-99, 99), rng.randint(-99, 99)
            files = {'x.txt': str(x), 'y.txt': str(y)}
            total = x + y
            tasks.append(dict(
                id=tid, family='B',
                statement=('read x.txt and y.txt, add them, write the '
                           'sum to sum.txt, read sum.txt back, finish '
                           'with what you read'),
                files=files, reads=['x.txt', 'y.txt'], answer=str(total),
                out_path='sum.txt', out_want=str(total)))
        else:
            n = rng.randint(2, 3)
            names = ['data%d.txt' % j for j in range(n)]
            vals = [rng.randint(-200, 200) for _ in range(n)]
            files = {nm: str(v) for nm, v in zip(names, vals)}
            files.update(_decoys(rng, names, 2))
            total = sum(vals)
            tasks.append(dict(
                id=tid, family='C',
                statement=('sum ONLY the integers in %s (other files '
                           'are decoys), write the sum to out.txt, '
                           'then finish with it' % ', '.join(names)),
                files=files, reads=names, answer=str(total),
                out_path='out.txt', out_want=str(total)))
    return tasks


DEV = make_tasks('dev', 20, 1)
HELD_OUT = make_tasks('heldout', 60, 2)


# ---------------------------------------------------------------------
# rev11: ALIAS world - structural (plan-level) errors, not rate noise.
# The statement declares an explicit file pairing; the actor carries a
# fixed heuristic bias (P_ALIAS draw at plan time):
#   SA 'habit': bias = ('x.txt', 'y.txt'), never present -> the biased
#     read violates the read precondition (blocked) / errors.
#   SB 'lexicographic': bias = the two lexicographically-smallest
#     existing files; the declared pair is always a different
#     existing pair -> the wrong plan executes cleanly (ceiling:
#     nothing can catch it).
# task['bias_reads'] is the actor's default; task['shuffle_reads'] is
# a deterministic different existing pair used by the shuffled-label
# repair control.  Dev seed 7 / held-out seed 8 (convention: odd dev,
# even held-out).  PRE-REGISTERED before measurement (parent message,
# 2026-10-21): P_ALIAS init 0.50, 10+10 dev / 30+30 held-out.
def make_alias_tasks(split, count, seed):
    rng = random.Random('e11-alias-%s-%d-%d' % (split, count, seed))
    tasks = []
    half = count // 2
    for i in range(count):
        sub = 'SA' if i < half else 'SB'
        tid = '%sA%02d' % ('D' if split == 'dev' else 'H', i)
        names = ['east.txt', 'north.txt', 'south.txt']
        if rng.random() < 0.5:
            names.append('west.txt')
        vals = {nm: str(rng.randint(-200, 200)) for nm in names}
        lex = sorted(names)
        pairs = [list(c) for c in combinations(lex, 2)]
        if sub == 'SA':
            bias = ['x.txt', 'y.txt']
        else:
            bias = lex[:2]
        # declared pair: an existing pair different from the bias
        declared = list(rng.choice(
            [c for c in pairs if set(c) != set(bias)]))
        # shuffled-label control pair: existing, different from both
        rest = [c for c in pairs
                if set(c) != set(declared) and set(c) != set(bias)]
        shuffled = list(rest[0]) if rest else list(declared)
        total = sum(int(vals[nm]) for nm in declared)
        tasks.append(dict(
            id=tid, family=sub,
            statement=('read %s and %s, add them, write the sum to '
                       'out.txt, read out.txt back, finish with what '
                       'you read' % (declared[0], declared[1])),
            files=vals, reads=declared, bias_reads=bias,
            shuffle_reads=shuffled, answer=str(total),
            out_path='out.txt', out_want=str(total)))
    return tasks


DEV_ALIAS = make_alias_tasks('dev', 20, 7)
HELD_OUT_ALIAS = make_alias_tasks('heldout', 60, 8)


# ---------------------------------------------------------------------
# rev2: second world family over NON-INTEGER data.  Files hold
# comma-joined word lists; the arithmetic tool is replaced by a
# string concat tool.  Families mirror A/B/C so the comparison is the
# mechanism's transfer, not a new task design:
#   T1 'concat-aggregate': comma-join the lists in N named files
#   T2 'concat-chain': read x, read y, concat, write, read back, finish
#   T3 'concat-distractor': like T1 with same-named decoy files
# Separate splits (TD*/TH* ids) keep the rev1 int-world numbers
# byte-reproducible; nothing here feeds back into DEV/HELD_OUT.
WORDS = ('apple banana cherry delta ember frost grape hazel iris '
         'juniper kiwi lemon mango nova olive pepper quartz river '
         'stone tulip').split()


def _word_list(rng):
    return ','.join(rng.choice(WORDS)
                    for _ in range(rng.randint(2, 4)))


def _text_decoys(rng, real_paths, n):
    decoys = {}
    for path in real_paths:
        base, ext = path.rsplit('.', 1)
        for k in range(n):
            decoys['%s_%d.%s' % (base, k + 1, ext)] = _word_list(rng)
    return decoys


def make_text_tasks(split, count, seed):
    rng = random.Random('e11-text-%s-%d-%d' % (split, count, seed))
    tasks = []
    fams = ['T1', 'T2', 'T3']
    for i in range(count):
        fam = fams[i % 3]
        tid = '%s%02d' % ('TD' if split == 'dev' else 'TH', i)
        if fam == 'T1':
            n = rng.randint(3, 5)
            names = ['list%d.txt' % j for j in range(n)]
            contents = [_word_list(rng) for _ in range(n)]
            files = dict(zip(names, contents))
            answer = ','.join(contents)
            tasks.append(dict(
                id=tid, family='T1',
                statement=('concatenate the word lists in %s (in that '
                           'order, comma-joined), write the result to '
                           'out.txt, then finish with it'
                           % ', '.join(names)),
                files=files, reads=names, answer=answer,
                out_path='out.txt', out_want=answer))
        elif fam == 'T2':
            cx, cy = _word_list(rng), _word_list(rng)
            files = {'x.txt': cx, 'y.txt': cy}
            answer = cx + ',' + cy
            tasks.append(dict(
                id=tid, family='T2',
                statement=('read x.txt and y.txt, concatenate them '
                           'comma-joined, write the result to cat.txt, '
                           'read cat.txt back, finish with what you '
                           'read'),
                files=files, reads=['x.txt', 'y.txt'], answer=answer,
                out_path='cat.txt', out_want=answer))
        else:
            n = rng.randint(2, 3)
            names = ['list%d.txt' % j for j in range(n)]
            contents = [_word_list(rng) for _ in range(n)]
            files = dict(zip(names, contents))
            files.update(_text_decoys(rng, names, 2))
            answer = ','.join(contents)
            tasks.append(dict(
                id=tid, family='T3',
                statement=('concatenate ONLY the word lists in %s '
                           '(other files are decoys), comma-joined and '
                           'in that order, write the result to '
                           'out.txt, then finish with it'
                           % ', '.join(names)),
                files=files, reads=names, answer=answer,
                out_path='out.txt', out_want=answer))
    return tasks


DEV_TEXT = make_text_tasks('dev', 20, 3)
HELD_OUT_TEXT = make_text_tasks('heldout', 60, 4)


# ---------------------------------------------------------------------
# rev4: mutating-error world.  rev3 showed precondition gates add no
# OUTCOME value when every gated call is side-effect-free.  Family M
# makes the gated call destructive: a scale with a malformed factor
# CORRUPTS the target file before the error is observable.  Plan:
# scale each named file in place by the task factor, then read, sum,
# write, finish.
def make_mut_tasks(split, count, seed):
    rng = random.Random('e11-mut-%s-%d-%d' % (split, count, seed))
    tasks = []
    for i in range(count):
        tid = '%s%02d' % ('DM' if split == 'dev' else 'HM', i)
        n = rng.randint(3, 4)
        names = ['cell%d.txt' % j for j in range(n)]
        vals = [rng.randint(-50, 50) for _ in range(n)]
        factor = rng.randint(2, 5)
        files = {nm: str(v) for nm, v in zip(names, vals)}
        total = sum(v * factor for v in vals)
        tasks.append(dict(
            id=tid, family='M',
            statement=('scale each of %s in place by %d, then sum the '
                       'scaled values, write the sum to out.txt, then '
                       'finish with it' % (', '.join(names), factor)),
            files=files, reads=names, factor=str(factor),
            answer=str(total), out_path='out.txt',
            out_want=str(total)))
    return tasks


DEV_MUT = make_mut_tasks('dev', 20, 5)
HELD_OUT_MUT = make_mut_tasks('heldout', 60, 6)


def grade(task, final_state, finished_answer):
    """Strict grader: exact final answer AND exact output file."""
    if finished_answer is None:
        return False
    if finished_answer != task['answer']:
        return False
    return final_state['files'].get(task['out_path']) == task['out_want']
