"""E11 scripted noisy actor.

The actor is a hand-written planner that knows each task family's
correct plan skeleton.  It is NOT a language model; its error mix is
authored and its rates are disclosed in RESULTS.md.  Per task it is
seeded; both loop conditions share the seed, so error rates match
across conditions (exact draws diverge once one condition repairs a
step the other does not - the pairing is by task and seed, not by
identical mistakes).  It reads its own accepted-step
history to collect observations (that is what makes it ReAct-shaped).

Plan pointer discipline: the actor keeps a PENDING step.  It advances
its plan pointer only when the pending step shows up in the accepted
history.  A violation re-emits the pending step (clean with high
probability).  Nothing else moves the pointer, so repairs cannot
double-advance the plan.

Error modes (independent draws at the named plan positions):
  P_WRONG_PATH : a read targets another existing file (a decoy in
                 family C; a nonexistent path elsewhere)
  P_SLIP       : a value being written is mis-transcribed (one digit
                 mutated) - SILENT: execution succeeds, content wrong
  P_BAD_ADD    : add gets a non-integer first argument
  P_PREMATURE  : the write position is replaced by an early finish
                 answering the running total (0 before any sum)
Repairs: on a violation (verified condition) the pending step is
re-emitted clean with probability REPAIR_FIX, else the same error is
re-drawn once; on a bare error observation (baseline) the same with
RETRY_FIX.
"""
import random
import re

from instinct_models.stepverify import Step

P_WRONG_PATH = 0.12
P_SLIP = 0.12
P_BAD_ADD = 0.08
P_BAD_CONCAT = 0.08    # text world: concat operands swapped (SILENT:
                       # the string is well-formed, the order wrong)
P_BAD_FACTOR = 0.10    # mut world: malformed scale factor (DESTRUCTIVE
                       # in the baseline: corrupts the target file)
P_PREMATURE = 0.05
P_ALIAS = 0.50         # rev11: structural plan error - follow the
                       # heuristic bias pairing, not the statement
REPAIR_FIX = 0.92
RETRY_FIX = 0.60
ALIAS_REPAIR = 'stated'  # rev11 shuffled-label control: 'shuffle'
                         # repairs toward the shuffled pairing instead

# rev10 (StepTool replication): the fault draws are the policy's
# stochastic decisions.  They are routed through ScriptedActor._draw,
# which logs (emit_index, name, fired) so a policy-gradient trainer
# can score trajectories.  _draw reads the module constant at call
# time (noise_sweep and the trainer set them per run) and consumes
# exactly one rng.random() per at-risk check, in the original order -
# the random stream is unchanged, so all registered numbers are
# byte-identical.
FAULT_NAMES = ('wrong_path', 'slip', 'bad_add', 'bad_concat',
               'bad_factor', 'premature', 'alias')
_FAULT_GLOBAL = {'wrong_path': 'P_WRONG_PATH', 'slip': 'P_SLIP',
                 'bad_add': 'P_BAD_ADD', 'bad_concat': 'P_BAD_CONCAT',
                 'bad_factor': 'P_BAD_FACTOR',
                 'premature': 'P_PREMATURE', 'alias': 'P_ALIAS'}


def _mutate_int_text(rng, text):
    digits = [i for i, c in enumerate(text) if c.isdigit()]
    if not digits:
        return '7'
    i = rng.choice(digits)
    d = (int(text[i]) + rng.choice((1, 2))) % 10
    return text[:i] + str(d) + text[i + 1:]


def _mutate_word(rng, text):
    letters = [i for i, c in enumerate(text) if c.isalpha()]
    if not letters:
        return 'q'
    i = rng.choice(letters)
    c = chr((ord(text[i]) - 97 + rng.choice((1, 2))) % 26 + 97)
    return text[:i] + c + text[i + 1:]


class ScriptedActor:
    def __init__(self, task, seed, verified):
        self.task = task
        self.rng = random.Random('actor-%s-%d' % (task['id'], seed))
        self.verified = verified
        self.values = {}        # path -> integer text observed
        self.total = None       # running sum as text
        self.emitted = 0        # steps returned so far (fault-log index)
        self.fault_log = []     # (emit_index, fault_name, fired)
        self.plan = self._make_plan()
        self.pos = 0
        self.pending = None     # (descriptor, Step) awaiting acceptance
        self.finished = False
        self._poisoned = set()  # ids of effect-violated StepRecords

    def _draw(self, name):
        p = globals()[_FAULT_GLOBAL[name]]
        fired = self.rng.random() < p
        self.fault_log.append((self.emitted, name, fired))
        return fired

    def _make_plan(self):
        t = self.task
        if t['family'] in ('SA', 'SB'):
            # rev11: structural alias error.  ONE draw at plan time:
            # follow the heuristic bias pairing instead of the
            # statement's declared pairing.  The wrong plan is then
            # executed faithfully (rate draws still apply on top).
            reads = (list(t['bias_reads']) if self._draw('alias')
                     else list(t['reads']))
            return ([('read', p) for p in reads]
                    + [('sum2',), ('write',), ('readback',),
                       ('finish',)])
        reads = t['reads']
        plan = [('read', p) for p in reads]
        if t['family'].startswith('T'):
            if t['family'] == 'T2':
                plan += [('concat2',), ('write',), ('readback',),
                         ('finish',)]
            else:
                n = max(0, len(reads) - 1)
                plan += [('concatall',)] * n + [('write',), ('finish',)]
            return plan
        if t['family'] == 'M':
            plan = ([('scale', p) for p in reads]
                    + [('read', p) for p in reads]
                    + [('sumall',)] * max(0, len(reads) - 1)
                    + [('write',), ('finish',)])
            return plan
        if t['family'] == 'B':
            plan += [('sum2',), ('write',), ('readback',), ('finish',)]
        else:
            n_adds = max(0, len(reads) - 1)
            plan += [('sumall',)] * n_adds + [('write',), ('finish',)]
        return plan

    # -- intake ----------------------------------------------------------
    def _absorb(self, history, violation):
        # A33 F1: never absorb the observation of a record whose effect
        # check FAILED - the violated value is poison and must not
        # seed repair operands.  Excluded durably: a violated record
        # stays in history after the repair, so exclusion is tracked
        # by record identity, not position.
        if violation is not None and history \
                and getattr(violation, 'stage', None) == 'effect':
            self._poisoned.add(id(history[-1]))
        self.values = {}
        self.total = None
        for rec in history:
            if id(rec) in self._poisoned:
                continue
            step, obs = rec.step, rec.observation
            is_text = self.task['family'].startswith('T')
            if step.tool == 'read':
                if is_text:
                    if isinstance(obs, str) \
                            and not obs.startswith('ERROR:'):
                        self.values[step.args['path']] = obs
                    continue
                try:
                    int(obs)
                except (TypeError, ValueError):
                    continue
                self.values[step.args['path']] = obs
            elif step.tool in ('add', 'concat'):
                if is_text:
                    if isinstance(obs, str) \
                            and not obs.startswith('ERROR:'):
                        self.total = obs
                    continue
                try:
                    int(obs)
                except (TypeError, ValueError):
                    continue
                self.total = obs

    # -- the actor callable ------------------------------------------------
    def __call__(self, task, history, violation):
        failed_pending = False
        if self.pending is not None and history \
                and history[-1].step is self.pending[1]:
            # the pending step was executed (it passed any gate)
            if self.pending[1].tool == 'finish':
                self.finished = True
            obs = history[-1].observation
            errored = (isinstance(obs, str)
                       and obs.startswith('ERROR:'))
            if violation is not None or errored:
                # executed but failed (post-check or world error):
                # the plan does NOT advance; the descriptor is retried
                failed_pending = True
            else:
                self.pos += 1
                self.pending = None
        self._absorb(history, violation)
        if self.finished:
            return None
        if failed_pending or (violation is not None
                              and self.pending is not None):
            # retry the pending descriptor: blocked pre-execution
            # (violation, not in history) or failed after execution
            desc = self.pending[0]
            fix_p = REPAIR_FIX if self.verified else RETRY_FIX
            clean = self.rng.random() < fix_p
            if clean and self.task['family'] in ('SA', 'SB') \
                    and desc[0] == 'read' \
                    and desc[1] not in self.task['reads']:
                # the failure signal points at the off-statement
                # path: re-target the declared (or, in the
                # shuffled-label control, the shuffled) path at the
                # same read position
                idx = sum(1 for d in self.plan[:self.pos]
                          if d[0] == 'read')
                target = (self.task['shuffle_reads'] if
                          ALIAS_REPAIR == 'shuffle'
                          else self.task['reads'])
                if idx < len(target):
                    desc = ('read', target[idx])
                    self.plan[self.pos] = desc
            step = self._build(desc, clean)
            self.pending = (desc, step)
            self.emitted += 1
            return step
        if self.pos >= len(self.plan):
            return None
        desc = self.plan[self.pos]
        step = self._build(desc, clean=False)
        self.pending = (desc, step)
        self.emitted += 1
        return step

    # -- step builders -----------------------------------------------------
    def _build(self, desc, clean):
        kind = desc[0]
        if kind == 'read':
            return self._b_read(desc[1], clean)
        if kind == 'sum2':
            vals = [self.values.get(p) for p in self.task['reads']]
            vals = [v for v in vals if v is not None]
            a, b = (vals + ['0', '0'])[:2]
            return self._b_add(a, b, clean)
        if kind == 'sumall':
            reads = self.task['reads']
            if self.total is None:
                got = [self.values.get(p) for p in reads]
                got = [v for v in got if v is not None]
                a, b = (got + ['0', '0'])[:2]
            else:
                used = self.plan[:self.pos].count(('sumall',)) + 1
                nxt = reads[used] if used < len(reads) else None
                b = self.values.get(nxt, '0')
                a = self.total
            return self._b_add(a, b, clean)
        if kind == 'scale':
            return self._b_scale(desc[1], clean)
        if kind == 'concat2':
            vals = [self.values.get(p) for p in self.task['reads']]
            vals = [v for v in vals if v is not None]
            a, b = (vals + ['', ''])[:2]
            return self._b_concat(a, b, clean)
        if kind == 'concatall':
            reads = self.task['reads']
            if self.total is None:
                got = [self.values.get(p) for p in reads]
                got = [v for v in got if v is not None]
                a, b = (got + ['', ''])[:2]
            else:
                used = self.plan[:self.pos].count(('concatall',)) + 1
                nxt = reads[used] if used < len(reads) else None
                b = self.values.get(nxt, '')
                a = self.total
            return self._b_concat(a, b, clean)
        if kind == 'write':
            is_text = self.task['family'].startswith('T')
            stated = (self.total if self.total is not None
                      else ('' if is_text else 0))
            stated = str(stated)
            text = stated
            if not clean and self._draw('slip'):
                text = (_mutate_word(self.rng, stated) if is_text
                        else _mutate_int_text(self.rng, stated))
            if not clean and self._draw('premature'):
                return self._b_finish(early=True)
            expect = None
            if self.verified:
                path = self.task['out_path']

                def expect(obs, b_, a_, p=path, w=stated):
                    got = a_['files'].get(p)
                    return None if got == w else (
                        'after my write, %s holds %r; I stated %r'
                        % (p, got, w))
            return Step('write',
                        {'path': self.task['out_path'], 'text': text},
                        expect=expect)
        if kind == 'readback':
            return Step('read', {'path': self.task['out_path']},
                        expect=None)
        if kind == 'finish':
            return self._b_finish(early=False)
        raise AssertionError(kind)

    def _b_scale(self, path, clean):
        # the prediction contracts the INTENDED factor, computed from
        # the pre-state at check time (contents are unobserved before
        # the reads); the error draw below must not move it
        expect = None
        if self.verified:
            f = self.task['factor']

            def expect(obs, b_, a_, p=path, f=f):
                try:
                    want = str(int(b_['files'][p]) * int(f))
                except (KeyError, ValueError):
                    return None
                got = a_['files'].get(p)
                return None if got == want else (
                    'after my scale, %s holds %r; I stated %r'
                    % (p, got, want))
        factor = self.task['factor']
        if not clean and self._draw('bad_factor'):
            factor = factor + 'x'
        return Step('scale', {'path': path, 'factor': factor},
                    expect=expect)

    def _b_concat(self, a, b, clean):
        # the prediction contracts the INTENDED operands; the error
        # draw below must not move it (a swapped concat is otherwise
        # self-consistent and invisible to the world spec floor)
        expect = None
        if self.verified:
            want = a + ',' + b

            def expect(obs, b_, a_, w=want):
                return None if obs == w else (
                    'concat returned %r, I predicted %r' % (obs, w))
        if not clean and self._draw('bad_concat'):
            a, b = b, a
        return Step('concat', {'a': a, 'b': b, 'sep': ','},
                    expect=expect)

    def _b_read(self, path, clean):
        if not clean and self._draw('wrong_path'):
            decoys = sorted(p for p in self.task['files']
                            if p != path
                            and p not in self.task['reads'])
            if decoys:
                # family C: an existing decoy - the world is
                # consistent, so verification cannot catch this
                path = self.rng.choice(decoys)
            else:
                # families A/B: a nonexistent mistyped path - a
                # visible error for the baseline, a blocked call for
                # the verified loop
                path = path[:-1] + ('0' if not path[-1].isdigit()
                                    else 'x')
        expect = None
        if self.verified:
            if self.task['family'].startswith('T'):
                def expect(obs, b, a):
                    if not isinstance(obs, str) or not re.fullmatch(
                            r'[a-z]+(,[a-z]+)*', obs or ''):
                        return ('read observation is not a comma-joined'
                                ' word list')
                    return None
            else:
                def expect(obs, b, a):
                    if not isinstance(obs, str):
                        return 'read observation is not text'
                    try:
                        int(obs)
                    except ValueError:
                        return 'read observation is not integer text'
                    return None
        return Step('read', {'path': path}, expect=expect)

    def _b_add(self, a, b, clean):
        if not clean and self._draw('bad_add'):
            a = str(a) + 'x'
        expect = None
        if self.verified:
            try:
                want = str(int(a) + int(b))
            except (ValueError, TypeError):
                want = None
            if want is not None:
                def expect(obs, b_, a_, w=want):
                    return None if obs == w else (
                        'add returned %r, I predicted %r' % (obs, w))
        return Step('add', {'a': str(a), 'b': str(b)}, expect=expect)

    def _b_finish(self, early):
        fam = self.task['family']
        if fam in ('B', 'T2') and not early:
            fallback = '' if fam.startswith('T') else '0'
            answer = self.values.get(self.task['out_path'],
                                     str(self.total or fallback))
        else:
            fallback = '' if fam.startswith('T') else 0
            answer = str(self.total if self.total is not None
                         else fallback)
        return Step('finish', {'answer': answer})


def make_actor(task, seed, verified):
    return ScriptedActor(task, seed, verified)
