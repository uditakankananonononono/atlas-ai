"""Sanity tests for the e11 measurement harness itself."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                '..', '..', 'backend'))

import actor as actor_mod
import run as run_mod
import tasks as tasks_mod
import world as world_mod
from instinct_models.stepverify import StepVerifier


class TestWorld(unittest.TestCase):
    def test_read_missing_raises(self):
        with self.assertRaises(world_mod.WorldError):
            world_mod.execute({'files': {}}, 'read', {'path': 'x'})

    def test_add_rejects_non_integer(self):
        with self.assertRaises(world_mod.WorldError):
            world_mod.execute({'files': {}}, 'add', {'a': '1x', 'b': '2'})

    def test_write_then_read_roundtrip(self):
        st = {'files': {}}
        _, st = world_mod.execute(st, 'write', {'path': 'o', 'text': '42'})
        obs, st = world_mod.execute(st, 'read', {'path': 'o'})
        self.assertEqual(obs, '42')


class TestVerifierOnWorld(unittest.TestCase):
    def test_missing_read_blocked(self):
        v = StepVerifier(world_mod.TOOLS)
        from instinct_models.stepverify import Step
        viol = v.verify_pre(Step('read', {'path': 'ghost'}),
                            {'files': {}})
        self.assertEqual(viol.stage, 'precondition')

    def test_slipped_write_caught_by_actor_contract(self):
        v = StepVerifier(world_mod.TOOLS)
        from instinct_models.stepverify import Step
        before = {'files': {}}
        after = {'files': {'out.txt': '43'}}
        step = Step('write', {'path': 'out.txt', 'text': '43'},
                    expect=lambda obs, b, a: None
                    if a['files'].get('out.txt') == '42'
                    else 'I stated 42')
        viol = v.verify_post(step, before, 'wrote', after)
        self.assertIsNotNone(viol)
        self.assertEqual(viol.stage, 'effect')


class TestTasks(unittest.TestCase):
    def test_splits_disjoint_and_seeded(self):
        self.assertEqual(len(tasks_mod.DEV), 20)
        self.assertEqual(len(tasks_mod.HELD_OUT), 60)
        d_ids = {t['id'] for t in tasks_mod.DEV}
        h_ids = {t['id'] for t in tasks_mod.HELD_OUT}
        self.assertFalse(d_ids & h_ids)
        again = tasks_mod.make_tasks('heldout', 60, 2)
        self.assertEqual([t['answer'] for t in again],
                         [t['answer'] for t in tasks_mod.HELD_OUT])

    def test_grader_strict(self):
        t = dict(answer='5', out_path='o.txt', out_want='5')
        self.assertTrue(tasks_mod.grade(t, {'files': {'o.txt': '5'}}, '5'))
        self.assertFalse(tasks_mod.grade(t, {'files': {'o.txt': '6'}}, '5'))
        self.assertFalse(tasks_mod.grade(t, {'files': {'o.txt': '5'}}, '6'))
        self.assertFalse(tasks_mod.grade(t, {'files': {}}, '5'))
        self.assertFalse(tasks_mod.grade(t, {'files': {'o.txt': '5'}}, None))


class TestActor(unittest.TestCase):
    def test_clean_actor_solves_family_A(self):
        task = dict(id='T00', family='A', reads=['a.txt', 'b.txt'],
                    files={'a.txt': '3', 'b.txt': '4'},
                    answer='7', out_path='out.txt', out_want='7')
        # force all error draws to miss by zeroing the rates
        saved = (actor_mod.P_WRONG_PATH, actor_mod.P_SLIP,
                 actor_mod.P_BAD_ADD, actor_mod.P_PREMATURE)
        actor_mod.P_WRONG_PATH = actor_mod.P_SLIP = 0.0
        actor_mod.P_BAD_ADD = actor_mod.P_PREMATURE = 0.0
        try:
            res = run_mod._run_verified(task, 1)
        finally:
            (actor_mod.P_WRONG_PATH, actor_mod.P_SLIP,
             actor_mod.P_BAD_ADD, actor_mod.P_PREMATURE) = saved
        self.assertTrue(res['success'], res)

    def test_deterministic_per_seed(self):
        task = tasks_mod.DEV[0]
        r1 = run_mod._run_verified(task, 11)
        r2 = run_mod._run_verified(task, 11)
        self.assertEqual(r1, r2)


class TestTextWorld(unittest.TestCase):
    def test_concat_tool_roundtrip(self):
        st = {'files': {}}
        obs, st = world_mod.execute(
            st, 'concat', {'a': 'apple,kiwi', 'b': 'mango', 'sep': ','})
        self.assertEqual(obs, 'apple,kiwi,mango')

    def test_concat_effect_spec_catches_swap(self):
        from instinct_models.stepverify import Step
        v = StepVerifier(world_mod.TOOLS)
        step = Step('concat', {'a': 'x', 'b': 'y', 'sep': ','})
        viol = v.verify_post(step, {'files': {}}, 'y,x', {'files': {}})
        self.assertIsNotNone(viol)
        self.assertEqual(viol.stage, 'effect')

    def test_text_splits_disjoint_seeded_wellformed(self):
        import re
        self.assertEqual(len(tasks_mod.DEV_TEXT), 20)
        self.assertEqual(len(tasks_mod.HELD_OUT_TEXT), 60)
        d_ids = {t['id'] for t in tasks_mod.DEV_TEXT}
        h_ids = {t['id'] for t in tasks_mod.HELD_OUT_TEXT}
        self.assertFalse(d_ids & h_ids)
        again = tasks_mod.make_text_tasks('heldout', 60, 4)
        self.assertEqual([t['answer'] for t in again],
                         [t['answer'] for t in tasks_mod.HELD_OUT_TEXT])
        for t in tasks_mod.DEV_TEXT + tasks_mod.HELD_OUT_TEXT:
            want = ','.join(t['files'][p] for p in t['reads'])
            self.assertEqual(t['answer'], want, t['id'])
            self.assertTrue(re.fullmatch(r'[a-z]+(,[a-z]+)*',
                                         t['answer']), t['id'])
            if t['family'] == 'T3':
                self.assertGreater(len(t['files']), len(t['reads']))

    def test_clean_actor_solves_family_T1(self):
        task = dict(id='TDX', family='T1', reads=['a.txt', 'b.txt'],
                    files={'a.txt': 'apple,kiwi', 'b.txt': 'mango'},
                    answer='apple,kiwi,mango', out_path='out.txt',
                    out_want='apple,kiwi,mango')
        saved = (actor_mod.P_WRONG_PATH, actor_mod.P_SLIP,
                 actor_mod.P_BAD_CONCAT, actor_mod.P_PREMATURE)
        actor_mod.P_WRONG_PATH = actor_mod.P_SLIP = 0.0
        actor_mod.P_BAD_CONCAT = actor_mod.P_PREMATURE = 0.0
        try:
            rv = run_mod._run_verified(task, 1)
            rb = run_mod._run_baseline(task, 1)
        finally:
            (actor_mod.P_WRONG_PATH, actor_mod.P_SLIP,
             actor_mod.P_BAD_CONCAT, actor_mod.P_PREMATURE) = saved
        self.assertTrue(rv['success'], rv)
        self.assertTrue(rb['success'], rb)

    def test_swapped_concat_caught_only_by_contract(self):
        # a swapped concat executes cleanly in the world (silent for
        # the baseline) but violates the actor's stated prediction
        saved = actor_mod.P_BAD_CONCAT
        actor_mod.P_BAD_CONCAT = 1.0
        actor_mod.RETRY_FIX = 0.0
        try:
            task = dict(id='TDY', family='T1', reads=['a.txt', 'b.txt'],
                        files={'a.txt': 'apple', 'b.txt': 'mango'},
                        answer='apple,mango', out_path='out.txt',
                        out_want='apple,mango')
            rv = run_mod._run_verified(task, 1)
            rb = run_mod._run_baseline(task, 1)
        finally:
            actor_mod.P_BAD_CONCAT = saved
            actor_mod.RETRY_FIX = 0.60
        self.assertGreaterEqual(rv['effect_misses'] + rv['blocked'], 1,
                                rv)
        self.assertEqual(rb['error_obs'], 0, rb)


class TestNoiseSweep(unittest.TestCase):
    def test_p_drop_zero_reproduces_verified_run(self):
        import noise_sweep as ns
        task = tasks_mod.DEV[0]
        a = run_mod._run_verified(task, 11)
        b = run_mod._run_verified(task, 11,
                                  actor_factory=ns._noisy_factory(0.0))
        self.assertEqual(a, b)

    def test_full_degradation_converges_to_baseline_eq(self):
        import noise_sweep as ns
        for task in tasks_mod.DEV[:3]:
            for seed in (11, 22):
                deg = run_mod._run_verified(
                    task, seed, actor_factory=ns._noisy_factory(1.0),
                    tools=ns._gates_off())
                eq = run_mod._run_baseline(
                    task, seed, retry_fix=actor_mod.REPAIR_FIX)
                self.assertEqual(deg['success'], eq['success'],
                                 (task['id'], seed, deg, eq))


class TestMutWorld(unittest.TestCase):
    def test_bad_factor_corrupts_before_error(self):
        st = {'files': {'a.txt': '5'}}
        obs, st = world_mod.execute(st, 'scale',
                                    {'path': 'a.txt', 'factor': '2x'})
        self.assertTrue(obs.startswith('ERROR:'))
        self.assertEqual(st['files']['a.txt'], 'CORRUPT')

    def test_pre_gate_blocks_corruption(self):
        task = dict(id='DMX', family='M', reads=['a.txt'],
                    files={'a.txt': '5'}, factor='3',
                    answer='15', out_path='out.txt', out_want='15')
        saved = actor_mod.P_BAD_FACTOR
        actor_mod.P_BAD_FACTOR = 1.0
        try:
            rv = run_mod._run_verified(task, 1)
            rb = run_mod._run_baseline(task, 1)
        finally:
            actor_mod.P_BAD_FACTOR = saved
        # verified: every bad scale blocked pre-execution, no
        # corruption, task still solved after repair
        self.assertGreaterEqual(rv['blocked'], 1, rv)
        # baseline: the corruption landed and is unrecoverable
        self.assertFalse(rb['success'], rb)

    def test_clean_actor_solves_family_M(self):
        task = dict(id='DMY', family='M', reads=['a.txt', 'b.txt'],
                    files={'a.txt': '3', 'b.txt': '4'}, factor='2',
                    answer='14', out_path='out.txt', out_want='14')
        saved = (actor_mod.P_WRONG_PATH, actor_mod.P_SLIP,
                 actor_mod.P_BAD_ADD, actor_mod.P_BAD_FACTOR,
                 actor_mod.P_PREMATURE)
        actor_mod.P_WRONG_PATH = actor_mod.P_SLIP = 0.0
        actor_mod.P_BAD_ADD = actor_mod.P_BAD_FACTOR = 0.0
        actor_mod.P_PREMATURE = 0.0
        try:
            rv = run_mod._run_verified(task, 1)
            rb = run_mod._run_baseline(task, 1)
        finally:
            (actor_mod.P_WRONG_PATH, actor_mod.P_SLIP,
             actor_mod.P_BAD_ADD, actor_mod.P_BAD_FACTOR,
             actor_mod.P_PREMATURE) = saved
        self.assertTrue(rv['success'], rv)
        self.assertTrue(rb['success'], rb)

    def test_mut_splits_seeded_wellformed(self):
        self.assertEqual(len(tasks_mod.DEV_MUT), 20)
        self.assertEqual(len(tasks_mod.HELD_OUT_MUT), 60)
        again = tasks_mod.make_mut_tasks('heldout', 60, 6)
        self.assertEqual([t['answer'] for t in again],
                         [t['answer'] for t in tasks_mod.HELD_OUT_MUT])
        for t in tasks_mod.DEV_MUT:
            want = str(sum(int(t['files'][p]) * int(t['factor'])
                           for p in t['reads']))
            self.assertEqual(t['answer'], want, t['id'])


class TestSchemaControl(unittest.TestCase):
    def test_schema_blocks_bad_factor_before_corruption(self):
        task = dict(id='DMZ', family='M', reads=['a.txt', 'b.txt'],
                    files={'a.txt': '5', 'b.txt': '4'}, factor='3',
                    answer='27', out_path='out.txt', out_want='27')
        saved = actor_mod.P_BAD_FACTOR
        actor_mod.P_BAD_FACTOR = 1.0
        try:
            # retry_fix=1.0: the repair draw always lands, so the
            # ONLY thing standing between the actor and corruption
            # is the schema gate itself
            rs = run_mod._run_baseline_schema(task, 1, retry_fix=1.0)
        finally:
            actor_mod.P_BAD_FACTOR = saved
        self.assertGreaterEqual(rs['schema_blocked'], 1, rs)
        # no corruption: the malformed scale never executed, and the
        # guaranteed clean retry solves the task
        self.assertTrue(rs['success'], rs)

    def test_schema_does_not_catch_swapped_concat(self):
        # swapped concat args are all well-typed: the schema control
        # is blind to the text world's silent error channel
        saved = actor_mod.P_BAD_CONCAT
        actor_mod.P_BAD_CONCAT = 1.0
        actor_mod.RETRY_FIX = 0.0
        try:
            task = dict(id='TDZ', family='T1', reads=['a.txt', 'b.txt'],
                        files={'a.txt': 'apple', 'b.txt': 'mango'},
                        answer='apple,mango', out_path='out.txt',
                        out_want='apple,mango')
            rs = run_mod._run_baseline_schema(task, 1)
        finally:
            actor_mod.P_BAD_CONCAT = saved
            actor_mod.RETRY_FIX = 0.60
        self.assertEqual(rs['schema_blocked'], 0, rs)
        self.assertFalse(rs['success'], rs)


class TestA33F1PoisonedTotal(unittest.TestCase):
    def test_violated_concat_not_absorbed(self):
        # A33 F1 witness shape: chained concat, swap always fires,
        # repairs always clean.  Pre-fix the VIOLATED observation
        # poisoned the running total and chain repairs could not
        # recover; post-fix the repair rebuilds from clean reads.
        task = dict(id='THX', family='T1',
                    reads=['a.txt', 'b.txt', 'c.txt'],
                    files={'a.txt': 'apple', 'b.txt': 'mango',
                           'c.txt': 'kiwi'},
                    answer='apple,mango,kiwi', out_path='out.txt',
                    out_want='apple,mango,kiwi')
        saved = (actor_mod.P_WRONG_PATH, actor_mod.P_SLIP,
                 actor_mod.P_BAD_CONCAT, actor_mod.P_PREMATURE,
                 actor_mod.REPAIR_FIX)
        actor_mod.P_WRONG_PATH = actor_mod.P_SLIP = 0.0
        actor_mod.P_PREMATURE = 0.0
        actor_mod.P_BAD_CONCAT = 1.0
        actor_mod.REPAIR_FIX = 1.0
        try:
            rv = run_mod._run_verified(task, 11)
            rb = run_mod._run_baseline(task, 11)
        finally:
            (actor_mod.P_WRONG_PATH, actor_mod.P_SLIP,
             actor_mod.P_BAD_CONCAT, actor_mod.P_PREMATURE,
             actor_mod.REPAIR_FIX) = saved
        self.assertGreaterEqual(rv['effect_misses'], 1, rv)
        self.assertTrue(rv['success'], rv)
        self.assertFalse(rb['success'], rb)     # swap stays silent


class TestFlakyWorld(unittest.TestCase):
    def _flaky(self, p, fn):
        saved = world_mod.EXEC_FAULT_P
        world_mod.EXEC_FAULT_P = p
        try:
            return fn()
        finally:
            world_mod.EXEC_FAULT_P = saved

    def test_fault_zero_reproduces_registered(self):
        import flaky_sweep as fs
        import noise_sweep as ns

        def go():
            task = tasks_mod.HELD_OUT[0]
            world_mod.seed_faults('H00-11')
            a = run_mod._run_verified(task, 11)
            world_mod.seed_faults('H00-11')
            b = run_mod._run_verified(
                task, 11, actor_factory=ns._noisy_factory(1.0),
                tools=fs._floors_off())
            world_mod.seed_faults('H00-11')
            c = run_mod._run_verified(
                task, 11, actor_factory=ns._noisy_factory(1.0))
            return a, b, c
        a, b, c = self._flaky(0.0, go)
        self.assertEqual(a, run_mod._run_verified(tasks_mod.HELD_OUT[0],
                                                  11))
        self.assertEqual(b, c)   # floor contributes nothing at p=0
                                 # when no predicates are stated

    def test_fault_caught_by_floor_without_predicates(self):
        import noise_sweep as ns

        def go():
            task = tasks_mod.HELD_OUT[0]
            world_mod.seed_faults('H00-11')
            return run_mod._run_verified(
                task, 11, actor_factory=ns._noisy_factory(1.0))
        r = self._flaky(1.0, go)
        self.assertGreaterEqual(r['effect_misses'], 1, r)

    def test_fault_is_silent_for_baseline(self):
        # the fault channel adds NO error observations: error_obs at
        # p=1.0 equals error_obs at p=0.0 for the same task+seed
        # (any error_obs come from the actor's own intent errors)
        def go(p):
            def inner():
                task = tasks_mod.HELD_OUT[1]
                world_mod.seed_faults('H01-11')
                return run_mod._run_baseline(task, 11)
            return self._flaky(p, inner)
        r0 = go(0.0)
        r1 = go(1.0)
        self.assertEqual(r0['error_obs'], r1['error_obs'], (r0, r1))
        self.assertFalse(r1['success'], r1)


class TestPaidAccounting(unittest.TestCase):
    def test_paid_equals_free_when_budget_never_binds(self):
        saved = (actor_mod.P_WRONG_PATH, actor_mod.P_SLIP,
                 actor_mod.P_BAD_ADD, actor_mod.P_PREMATURE)
        actor_mod.P_WRONG_PATH = actor_mod.P_SLIP = 0.0
        actor_mod.P_BAD_ADD = actor_mod.P_PREMATURE = 0.0
        try:
            for t in tasks_mod.DEV[:5]:
                self.assertEqual(run_mod._run_verified(t, 11),
                                 run_mod._run_verified_paid(t, 11),
                                 t['id'])
        finally:
            (actor_mod.P_WRONG_PATH, actor_mod.P_SLIP,
             actor_mod.P_BAD_ADD, actor_mod.P_PREMATURE) = saved

    def test_paid_consumes_budget_on_blocks(self):
        # exact pin (A33 rev8a): wrong_path=1.0 forces a blocked call;
        # the free loop budgets on accepted history, the paid loop
        # charges the block - STRICT difference, no equality allowed
        saved = (actor_mod.P_WRONG_PATH, run_mod.MAX_STEPS)
        actor_mod.P_WRONG_PATH = 1.0
        run_mod.MAX_STEPS = 6
        try:
            t = tasks_mod.HELD_OUT[0]
            free = run_mod._run_verified(t, 11)
            paid = run_mod._run_verified_paid(t, 11)
            self.assertEqual(free['blocked'], 3, free)
            self.assertEqual(paid['blocked'], 3, paid)
            self.assertEqual(free['steps'], 6, free)
            self.assertEqual(paid['steps'], 3, paid)
            self.assertLess(paid['steps'], free['steps'])
        finally:
            actor_mod.P_WRONG_PATH, run_mod.MAX_STEPS = saved

    def test_violation_changes_paid_result(self):
        # exact pin (A33 rev8a): slip=1.0 forces an effect violation
        # + repair; at budget 8 the free run succeeds, the paid run
        # exhausts and fails - the accounting changes the OUTCOME
        saved = (actor_mod.P_SLIP, run_mod.MAX_STEPS)
        actor_mod.P_SLIP = 1.0
        run_mod.MAX_STEPS = 8
        try:
            t = tasks_mod.HELD_OUT[0]
            free = run_mod._run_verified(t, 11)
            paid = run_mod._run_verified_paid(t, 11)
            self.assertTrue(free['success'], free)
            self.assertTrue(free['finished'], free)
            self.assertEqual(free['steps'], 8, free)
            self.assertFalse(paid['success'], paid)
            self.assertFalse(paid['finished'], paid)
            self.assertTrue(paid['exhausted'], paid)
            self.assertEqual(paid['steps'], 6, paid)
        finally:
            actor_mod.P_SLIP, run_mod.MAX_STEPS = saved

    def test_tight_grid_cells_exact_counts(self):
        # exact pins on the published tight cells (A33 rev8a: the
        # unit suite must catch accounting mutants without running
        # the whole sweep).  Counts are success counts out of 180.
        import budget_sweep as bs

        def raw_counts(taskset, budget):
            saved = run_mod.MAX_STEPS
            run_mod.MAX_STEPS = budget
            try:
                c = dict(vf=0, vp=0, b=0, e=0, scf=0, scp=0)
                for task in taskset:
                    for seed in run_mod.SEEDS:
                        c['vf'] += run_mod._run_verified(
                            task, seed)['success']
                        c['vp'] += run_mod._run_verified_paid(
                            task, seed)['success']
                        c['b'] += run_mod._run_baseline(
                            task, seed)['success']
                        c['e'] += run_mod._run_baseline(
                            task, seed,
                            retry_fix=actor_mod.REPAIR_FIX)['success']
                        c['scf'] += run_mod._run_baseline_schema(
                            task, seed, free_rejects=True)['success']
                        c['scp'] += run_mod._run_baseline_schema(
                            task, seed)['success']
                return c
            finally:
                run_mod.MAX_STEPS = saved

        self.assertEqual(
            raw_counts(tasks_mod.HELD_OUT_MUT, 14),
            dict(vf=172, vp=149, b=97, e=97, scf=152, scp=137))
        self.assertEqual(
            raw_counts(tasks_mod.HELD_OUT, 6),
            dict(vf=74, vp=58, b=53, e=53, scf=56, scp=53))
        self.assertEqual(
            raw_counts(tasks_mod.HELD_OUT_TEXT, 6),
            dict(vf=84, vp=74, b=71, e=71, scf=71, scp=71))

    def test_schema_free_rejects_at_slack_budget(self):
        saved = run_mod.MAX_STEPS
        run_mod.MAX_STEPS = 25
        try:
            t = tasks_mod.HELD_OUT_MUT[0]
            a = run_mod._run_baseline_schema(t, 11, free_rejects=True)
            b = run_mod._run_baseline_schema(t, 11)
            self.assertEqual(a['success'], b['success'], (a, b))
        finally:
            run_mod.MAX_STEPS = saved

class TestStepToolReplication(unittest.TestCase):
    def test_draw_grad_formula(self):
        import steptool_sweep as st
        self.assertAlmostEqual(st._draw_grad(True, 0.3), 0.7)
        self.assertAlmostEqual(st._draw_grad(False, 0.3), -0.3)

    def test_step_reward_pins(self):
        import steptool_sweep as st

        class S:
            def __init__(self, tool, args):
                self.tool, self.args = tool, args

        class R:
            def __init__(self, tool, args, obs):
                self.step, self.observation = S(tool, args), obs

        t = tasks_mod.DEV[0]
        good_read = R('read', {'path': t['reads'][0]}, '12')
        self.assertEqual(st.step_reward(t, good_read, set()), (1, 4))
        dup = R('read', {'path': t['reads'][0]}, '12')
        seen = {('read', (('path', t['reads'][0]),))}
        self.assertEqual(st.step_reward(t, dup, seen), (1, 1))
        decoy = R('read', {'path': 'decoy.txt'}, '5')
        self.assertEqual(st.step_reward(t, decoy, set()), (1, 1))
        err = R('read', {'path': 'nope'}, 'ERROR: no such file')
        self.assertEqual(st.step_reward(t, err, set()), (0, 0))
        ok_write = R('write', {'path': t['out_path'],
                               'text': t['out_want']}, 'wrote')
        self.assertEqual(st.step_reward(t, ok_write, set()), (1, 5))
        bad_write = R('write', {'path': t['out_path'],
                                'text': 'wrong'}, 'wrote')
        self.assertEqual(st.step_reward(t, bad_write, set()), (1, 1))

    def test_training_deterministic(self):
        import steptool_sweep as st
        a, _ = st.train(tasks_mod.DEV, epochs=5, batch=4)
        b, _ = st.train(tasks_mod.DEV, epochs=5, batch=4)
        self.assertEqual(a, b)

    def test_trained_probs_exact_pins(self):
        # pins the full int-world training run (guards the trainer)
        import steptool_sweep as st
        th, _ = st.train(tasks_mod.DEV, step_grained=True)
        got = {n: round(p, 4) for n, p in st.theta_probs(th).items()}
        self.assertEqual(got, {'wrong_path': 0.0392, 'slip': 0.0239,
                               'bad_add': 0.0796, 'bad_concat': 0.08,
                               'bad_factor': 0.1,
                               'premature': 0.0153})

    def test_heldout_condition_exact_counts(self):
        # pins the published rev10 cells (counts out of 180)
        import steptool_sweep as st
        th_sg, _ = st.train(tasks_mod.DEV, step_grained=True)
        th_fo, _ = st.train(tasks_mod.DEV, step_grained=False)
        p_sg, p_fo = (st.theta_probs(th_sg), st.theta_probs(th_fo))
        self.assertEqual(sum(st.eval_split(tasks_mod.HELD_OUT)), 134)
        self.assertEqual(
            sum(st.eval_split(tasks_mod.HELD_OUT, probs=p_fo)), 164)
        self.assertEqual(
            sum(st.eval_split(tasks_mod.HELD_OUT, probs=p_sg)), 174)
        self.assertEqual(
            sum(st.eval_split(tasks_mod.HELD_OUT, verified=True)),
            155)
        self.assertEqual(
            sum(st.eval_split(tasks_mod.HELD_OUT, probs=p_sg,
                              verified=True)), 175)


class TestAliasWorld(unittest.TestCase):
    def test_generator_invariants(self):
        for t in tasks_mod.DEV_ALIAS + tasks_mod.HELD_OUT_ALIAS:
            if t['family'] == 'SB':
                self.assertTrue(all(p in t['files']
                                    for p in t['bias_reads']))
                self.assertNotEqual(set(t['reads']),
                                    set(t['bias_reads']))
            self.assertTrue(all(p in t['files']
                                for p in t['shuffle_reads']), t['id'])
            self.assertNotEqual(set(t['shuffle_reads']),
                                set(t['reads']))
            self.assertNotEqual(set(t['shuffle_reads']),
                                set(t['bias_reads']))
            self.assertEqual(len(t['shuffle_reads']), 2)
            want = sum(int(t['files'][p]) for p in t['reads'])
            self.assertEqual(t['answer'], str(want))

    def test_alias_draw_at_plan_time(self):
        import actor as actor_mod
        import alias_sweep as al
        saved = actor_mod.P_ALIAS
        try:
            actor_mod.P_ALIAS = 1.0
            t = tasks_mod.DEV_ALIAS[0]
            a = actor_mod.make_actor(t, 11, verified=False)
            reads = [d[1] for d in a.plan if d[0] == 'read']
            self.assertEqual(reads, t['bias_reads'])
            self.assertEqual(a.fault_log[0][1:], ('alias', True))
            self.assertTrue(al.alias_fired(t, 11, 1.0))
            actor_mod.P_ALIAS = 0.0
            a = actor_mod.make_actor(t, 11, verified=False)
            reads = [d[1] for d in a.plan if d[0] == 'read']
            self.assertEqual(sorted(reads), sorted(t['reads']))
            self.assertEqual(a.fault_log[0][1:], ('alias', False))
        finally:
            actor_mod.P_ALIAS = saved

    def test_alias_fired_reconstruction_matches_log(self):
        import alias_sweep as al
        t = tasks_mod.DEV_ALIAS[3]
        collect = {}
        run_mod._run_baseline(t, 22, collect=collect)
        logged = [f for (_, n, f) in collect['actor'].fault_log
                  if n == 'alias'][0]
        self.assertEqual(logged, al.alias_fired(t, 22,
                                                actor_mod.P_ALIAS))

    def test_alias_heldout_exact_counts(self):
        # pins the published rev11 cells (success counts out of 90)
        import alias_sweep as al
        import steptool_sweep as st
        theta, _ = st.train(tasks_mod.DEV_ALIAS, step_grained=True)
        p_sg = st.theta_probs(theta)
        self.assertEqual(
            {n: round(p, 4) for n, p in p_sg.items()},
            {'wrong_path': 0.0184, 'slip': 0.0383, 'bad_add': 0.0768,
             'bad_concat': 0.08, 'bad_factor': 0.1,
             'premature': 0.0153, 'alias': 0.0875})
        sa = [t for t in tasks_mod.HELD_OUT_ALIAS
              if t['family'] == 'SA']
        sb = [t for t in tasks_mod.HELD_OUT_ALIAS
              if t['family'] == 'SB']
        self.assertEqual(
            {'base': sum(al.eval_cond(sa)),
             'sg': sum(al.eval_cond(sa, probs=p_sg)),
             'ver': sum(al.eval_cond(sa, verified=True)),
             'sgv': sum(al.eval_cond(sa, probs=p_sg, verified=True)),
             'bsh': sum(al.eval_cond(sa, shuffle=True)),
             'vsh': sum(al.eval_cond(sa, verified=True,
                                     shuffle=True))},
            {'base': 52, 'sg': 80, 'ver': 68, 'sgv': 85,
             'bsh': 34, 'vsh': 38})
        self.assertEqual(
            {'base': sum(al.eval_cond(sb)),
             'sg': sum(al.eval_cond(sb, probs=p_sg)),
             'ver': sum(al.eval_cond(sb, verified=True)),
             'sgv': sum(al.eval_cond(sb, probs=p_sg, verified=True)),
             'bsh': sum(al.eval_cond(sb, shuffle=True)),
             'vsh': sum(al.eval_cond(sb, verified=True,
                                     shuffle=True))},
            {'base': 29, 'sg': 76, 'ver': 38, 'sgv': 77,
             'bsh': 29, 'vsh': 38})

    def test_alias_ceiling_sb_fired(self):
        # the stated ceiling: on SB alias-fired runs nothing catches
        # the wrong plan - success is ~0 in every condition
        import alias_sweep as al
        import steptool_sweep as st
        theta, _ = st.train(tasks_mod.DEV_ALIAS, step_grained=True)
        p_sg = st.theta_probs(theta)
        sb = [t for t in tasks_mod.HELD_OUT_ALIAS
              if t['family'] == 'SB']
        seeds = run_mod.SEEDS
        got = {}
        for name, kw, p in (('base', {}, 0.50),
                            ('sg', dict(probs=p_sg), p_sg['alias']),
                            ('ver', dict(verified=True), 0.50),
                            ('sgv', dict(probs=p_sg, verified=True),
                             p_sg['alias'])):
            vals = al.eval_cond(sb, **kw)
            got[name] = sum(
                v for i, v in enumerate(vals)
                if al.alias_fired(sb[i // 3], seeds[i % 3], p))
        self.assertEqual(got, {'base': 0, 'sg': 0, 'ver': 1,
                               'sgv': 0})


class TestResultsDocIntact(unittest.TestCase):
    def test_all_rev_sections_present(self):
        # regression (rev9 truncation): RESULTS.md must carry every
        # section heading rev2..rev9; a merge-truncation fails here
        import os
        path = os.path.join(os.path.dirname(__file__), 'RESULTS.md')
        with open(path) as f:
            text = f.read()
        for n in range(2, 15):
            self.assertIn('## rev%d:' % n, text)


class TestLLMActorOffline(unittest.TestCase):
    """rev12: offline unit tests for the real-model actor shim.  These
    never touch the llama server; the live probe is llm_sweep.py."""

    def test_catch_audit_reproduces_registered_totals(self):
        # rev14/rev15: the post-hoc catch audit (deterministic replay
        # of the committed llm-ver rows) must reproduce the registered
        # totals exactly: 182 effect_misses, 12 pre-gate blocks (rev15
        # rerun rows; rev13 pinned 183 - see RESULTS rev15 table).
        import collections
        import json
        import os
        import catch_audit
        import tasks as tasks_mod
        tasks = {t['id']: t for t in tasks_mod.HELD_OUT[:30]}
        rows = collections.defaultdict(list)
        path = os.path.join(os.path.dirname(__file__),
                            'rows15_llm_ver.jsonl')
        with open(path) as f:
            for line in f:
                r = json.loads(line)
                rows[r['task']].append(r)
        miss = block = 0
        for tid in sorted(tasks):
            accepted, blocked = catch_audit.replay(tasks[tid], rows[tid])
            miss += sum(1 for a in accepted if a[3] is not None)
            block += blocked
        self.assertEqual(miss, 182)
        self.assertEqual(block, 12)

    def test_compile_expect_observation(self):
        from actor_llm import compile_expect
        e = compile_expect('observation = 12')
        self.assertIsNone(e('12', {}, {}))
        self.assertIsNotNone(e('13', {}, {}))

    def test_compile_expect_after_state(self):
        from actor_llm import compile_expect
        e = compile_expect('out.txt = 15')
        self.assertIsNone(e(None, {}, {'files': {'out.txt': '15'}}))
        self.assertIsNotNone(e(None, {}, {'files': {'out.txt': '16'}}))

    def test_compile_expect_none_and_bad(self):
        from actor_llm import compile_expect
        self.assertIsNone(compile_expect('none'))
        # a bare alpha string IS a valid observation contract in this
        # text world (leniency, disclosed); an empty assignment is not
        self.assertIsNotNone(compile_expect('twelve'))
        with self.assertRaises(ValueError):
            compile_expect('x = ')

    def test_parse_first_tool_line_of_dump(self):
        from actor_llm import LLMActor
        tool, args, expect = LLMActor.parse_output(
            'TOOL: read path=a.txt\nEXPECT: none\n'
            'TOOL: add a=1 b=2\nEXPECT: observation = 3', True)
        self.assertEqual((tool, args), ('read', {'path': 'a.txt'}))
        self.assertIsNone(expect)

    def test_parse_json_args_leniency(self):
        from actor_llm import LLMActor
        tool, args, _ = LLMActor.parse_output(
            'TOOL: read {"path": "a.txt"}\nEXPECT: none', True)
        self.assertEqual((tool, args), ('read', {'path': 'a.txt'}))

    def test_parse_bare_value_expect_leniency(self):
        from actor_llm import LLMActor
        _, _, expect = LLMActor.parse_output(
            'TOOL: add a=1 b=2\nEXPECT: 3', True)
        self.assertIsNone(expect('3', {}, {}))
        self.assertIsNotNone(expect('4', {}, {}))

    def test_parse_missing_expect_is_format_failure(self):
        from actor_llm import LLMActor
        with self.assertRaises(ValueError):
            LLMActor.parse_output('TOOL: read path=a.txt', True)

    def test_format_failure_step_enters_loops(self):
        # a parse failure becomes Step('__format_failure__'): the
        # verified pre-gate blocks it (unknown tool), the baseline
        # executes it into an ERROR observation
        from actor_llm import FORMAT_FAILURE_TOOL
        from instinct_models.stepverify import StepVerifier
        import world as world_mod
        from instinct_models.stepverify import Step
        v = StepVerifier(world_mod.TOOLS)
        viol = v.verify_pre(Step(FORMAT_FAILURE_TOOL, {}),
                            {'files': {}})
        self.assertIsNotNone(viol)
        self.assertEqual(viol.stage, 'unknown_tool')
        try:
            world_mod.execute({'files': {}}, FORMAT_FAILURE_TOOL, {})
            self.fail('should raise')
        except world_mod.WorldError:
            pass


if __name__ == '__main__':
    unittest.main()
