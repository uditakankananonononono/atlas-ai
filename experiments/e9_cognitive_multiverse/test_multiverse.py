"""E9 tests. Run: python -m pytest test_multiverse.py (or python test_multiverse.py).
e7 harness modules are imported through multiverse.py's sys.path insertion."""
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import multiverse
from multiverse import Cfg, Mind, invented_windows, signature, IDENTITY_SIG
import dsl as e7dsl
from dsl import PRIMS, safe_apply, verify, flat


def flat_prims():
    return list(PRIMS)


def test_bfs_short_matches_e7_solve():
    """Comparability anchor (auditor-extended): a bfs+short mind with all
    prims and empty lib reproduces e7 solve() exactly - same program, same
    evaluation count - on all 40 tasks x 4 budgets = 160 cases."""
    tasks = e7dsl.make_tasks(0)
    n = 0
    for task in tasks:
        for budget in (300, 1000, 3000, 10000):
            mind = Mind(0, 0, 'bfs', budget, False, 'short', flat_prims(),
                        random.Random(0))
            got, nodes = mind.solve(task, 16, 20, {})
            want, want_nodes = e7dsl.solve(task, {}, budget)
            assert (got is None) == (want is None)
            assert nodes == want_nodes
            if got is not None:
                assert tuple(got) == tuple(want)
                assert verify(task, got, {})
            n += 1
    assert n == 160


def test_cross_process_determinism():
    """Same run under two PYTHONHASHSEEDs in subprocesses must be identical."""
    import json
    import subprocess
    code = (
        "import sys, json; sys.path.insert(0, %r);"
        "import multiverse;"
        "cfg = multiverse.Cfg(pop_size=4, generations=3, tasks_per_gen=3,"
        " keep=3, h1_pipes=3);"
        "r = multiverse.run_population('share-multi-v2', 2, cfg);"
        "r.pop('log');"
        "print(json.dumps(r, sort_keys=True, default=str))"
        % str(pathlib.Path(__file__).resolve().parent))
    outs = []
    for hs in ('0', '1'):
        env = dict(__import__('os').environ, PYTHONHASHSEED=hs)
        p = subprocess.run([sys.executable, '-c', code],
                           capture_output=True, text=True, env=env, timeout=300)
        assert p.returncode == 0, p.stderr[-500:]
        outs.append(p.stdout)
    assert outs[0] == outs[1]


def test_budget_respected_all_strategies():
    task = e7dsl.make_tasks(0)[3]
    for strat in ('bfs', 'beam', 'rand'):
        m = Mind(0, 0, strat, 50, False, 'short', flat_prims(), random.Random(1))
        _p, nodes = m.solve(task, 8, 5, {})
        assert nodes <= 50, (strat, nodes)


def test_macro_costs_one_depth():
    lib = {'m1': ('inc', 'cumsum'), 'm2': ('sort', 'reverse')}
    prog = ('m1', 'm2', 'inc')
    assert flat(prog, lib) == ('inc', 'cumsum', 'sort', 'reverse', 'inc')
    x = [3, 1, 2]
    assert safe_apply(prog, x, lib) == safe_apply(flat(prog, lib), x, {})


def test_invented_windows_new_only():
    known = {signature((p,)) for p in PRIMS}
    wins = invented_windows(('inc', 'cumsum', 'max'), {}, known)
    assert wins
    for w, sig in wins:
        assert len(w) in (2, 3)
        assert sig not in known and sig != IDENTITY_SIG
    known |= {sig for _, sig in wins}
    assert invented_windows(('inc', 'cumsum', 'max'), {}, known) == []


def test_credit_only_with_sharing():
    cfg = Cfg(pop_size=4, generations=4, tasks_per_gen=3, keep=3, h1_pipes=3)
    r_iso = multiverse.run_population('iso-best', 2, cfg)
    assert r_iso['transfer_events'] == 0 and r_iso['final_pool'] == 0
    r = multiverse.run_population('share-multi', 2, cfg)
    for lin, c in r['credit_totals'].items():
        assert c >= 0 and isinstance(lin, int)


def test_selection_rules_disagree_on_credit():
    minds = []
    for i in range(4):
        m = Mind(i, i, 'bfs', 100, False, 'short', flat_prims(), random.Random(0))
        m.window_solves = (3, 3, 2, 0)[i]
        minds.append(m)
    credit = {3: 4}
    best = sorted(minds, key=lambda m: (-m.window_solves, m.id))
    multi = sorted(minds, key=lambda m: (-(m.window_solves + credit.get(m.lineage, 0)), m.id))
    assert minds[3] not in best[:3]
    assert minds[3] in multi[:3]


def test_determinism():
    cfg = Cfg(pop_size=4, generations=2, tasks_per_gen=2, keep=3, h1_pipes=2)
    a = multiverse.run_population('share-multi', 3, cfg)
    b = multiverse.run_population('share-multi', 3, cfg)
    assert a == b


def test_paired_eval_draws_across_conditions():
    cfg = Cfg(pop_size=4, generations=2, tasks_per_gen=2, keep=3, h1_pipes=2)
    a = multiverse.run_population('share-best', 4, cfg)
    b = multiverse.run_population('share-multi', 4, cfg)
    assert a['held_out'] == b['held_out']
    assert a['h2']['n_tasks'] == b['h2']['n_tasks']


def test_spammer_accounting():
    cfg = Cfg(pop_size=4, generations=4, tasks_per_gen=3, keep=3, h1_pipes=3,
              spammer=True)
    r = multiverse.run_population('share-multi', 5, cfg)
    assert r['spammer_selections_total'] > 0
    assert isinstance(r['spammer_selections_survived'], int)


def test_counterfactual_credit_bounded_by_usage():
    """v2: necessary transfers can never exceed transfer uses; counterfactual
    re-solve counter matches credited macros checked."""
    cfg = Cfg(pop_size=4, generations=4, tasks_per_gen=3, keep=3, h1_pipes=3)
    r = multiverse.run_population('share-multi-v2', 2, cfg)
    assert 0 <= r['necessary_transfers'] <= r['transfer_events']
    assert r['cf_resolves'] >= r['necessary_transfers']
    assert sum(r['credit_totals'].values()) == r['necessary_transfers']
    r1 = multiverse.run_population('share-multi-v2', 2, cfg)
    assert r == r1  # v2 is deterministic too


def test_e7lib8_equal_attempts_arm():
    cfg = Cfg(pop_size=4, generations=2, tasks_per_gen=2, keep=3, h1_pipes=2)
    e = multiverse.run_e7lib8(6, cfg)
    assert 0.0 <= e['h2']['pop'] <= 1.0
    assert e['h2']['pop'] >= e['h2']['ind'] - 1e-9


def test_smoke_full_run():
    cfg = Cfg(pop_size=4, generations=2, tasks_per_gen=2, keep=3, h1_pipes=2)
    r = multiverse.run_population('share-multi', 6, cfg)
    for k in ('h1', 'h2', 'ablation', 'log', 'final_pool'):
        assert k in r
    assert 0.0 <= r['h2']['pop'] <= 1.0
    e = multiverse.run_e7lib(6, cfg)
    assert 0.0 <= e['h2']['pop'] <= 1.0


if __name__ == '__main__':
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in fns:
        fn()
        print('ok', fn.__name__)
