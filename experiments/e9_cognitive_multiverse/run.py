"""E9 driver: conditions x seeds, writes rows.jsonl and analysis.txt.

Usage: python run.py [out_dir] [--seeds N] [--spam-seeds N] [--jobs N] [--quick]
Default out_dir is the script's own directory.
"""
import json
import math
import pathlib
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import multiverse
from multiverse import Cfg, POP_CONDITIONS, run_population, run_e7lib, run_e7lib8

OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('-') \
    else pathlib.Path(__file__).resolve().parent


def _arg(name, default):
    return int(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


SEEDS = _arg('--seeds', 10)
SPAM_SEEDS = _arg('--spam-seeds', 6)
JOBS = _arg('--jobs', 2)
QUICK = '--quick' in sys.argv
if QUICK:
    SEEDS, SPAM_SEEDS = 2, 1


def job(arg):
    kind, cond, seed, cfg = arg
    if kind == 'e7':
        return run_e7lib(seed, cfg)
    if kind == 'e7-8':
        return run_e7lib8(seed, cfg)
    return run_population(cond, seed, cfg)


def main():
    cfg = Cfg()
    spam_cfg_u = Cfg(spammer=True)  # share-multi-v2 forces counterfactual
    spam_cfg_p = Cfg(spammer=True, credit_mode='publication')
    jobs = [('pop', c, s, cfg) for s in range(1, SEEDS + 1) for c in POP_CONDITIONS]
    jobs += [('e7', 'e7-lib', s, cfg) for s in range(1, SEEDS + 1)]
    jobs += [('e7-8', 'e7-lib-8', s, cfg) for s in range(1, SEEDS + 1)]
    jobs += [('pop', 'share-multi-v2', s, spam_cfg_u) for s in range(1, SPAM_SEEDS + 1)]
    jobs += [('pop', 'share-multi-pub', s, spam_cfg_p) for s in range(1, SPAM_SEEDS + 1)]
    if JOBS > 1:
        with ProcessPoolExecutor(max_workers=JOBS) as ex:
            results = list(ex.map(job, jobs))
    else:
        results = [job(j) for j in jobs]

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in results:
        for e in r.get('log', []):
            rows.append(dict(kind='gen', condition=r['condition'], seed=r['seed'],
                             held_out=r['held_out'], **e))
        row = dict(kind='final', condition=r['condition'], seed=r['seed'],
                   held_out=r['held_out'],
                   h1_pop=r['h1']['pop'], h1_ind=r['h1']['ind'],
                   h2_pop=r['h2']['pop'], h2_ind=r['h2']['ind'],
                   h2_transfer_share=r['h2'].get('transfer_share'),
                   h2_tasks=r['h2'].get('n_tasks'),
                   final_n_lineages=r.get('final_n_lineages'),
                   final_evenness=r.get('final_evenness'),
                   final_pool=r.get('final_pool'),
                   final_names=r.get('final_names'),
                   transfer_events=r.get('transfer_events'),
                   necessary_transfers=r.get('necessary_transfers'),
                   cf_resolves=r.get('cf_resolves'),
                   n_macros=r.get('n_macros'),
                   credit_totals=r.get('credit_totals'),
                   ablation=r.get('ablation'),
                   spammer_survived=r.get('spammer_survived'),
                   spammer_selections_survived=r.get('spammer_selections_survived'),
                   spammer_selections_total=r.get('spammer_selections_total'))
        rows.append(row)
    (OUT / 'rows.jsonl').write_text('\n'.join(json.dumps(r, sort_keys=True) for r in rows) + '\n')

    finals = [r for r in rows if r['kind'] == 'final']
    # main-suite rows have spammer totals None; spam-suite rows have ints
    mains = [r for r in finals if r['spammer_selections_total'] is None
             or r['condition'] == 'e7-lib']
    spams = [r for r in finals if isinstance(r['spammer_selections_total'], int)
             and r['spammer_selections_total'] > 0]

    lines = []
    P = lines.append
    P('E9 cognitive multiverse, conditions x seeds (paired eval draws per seed)')
    P('config: %s' % json.dumps(cfg.__dict__, sort_keys=True))
    by_cond = {}
    for r in mains:
        by_cond.setdefault(r['condition'], []).append(r)
    P('')
    P('%-12s %6s %6s %6s %6s %6s %6s %7s %8s' % (
        'condition', 'h2pop', 'h2ind', 'h1pop', 'h1ind', 'lin', 'even', 'pool', 'transfer'))
    for c in POP_CONDITIONS + ('e7-lib', 'e7-lib-8'):
        rs = by_cond.get(c, [])
        if not rs:
            continue
        m = lambda k: float(np.mean([r[k] for r in rs if r[k] is not None]))
        P('%-12s %6.3f %6.3f %6.3f %6.3f %6.2f %6.3f %7.1f %8s' % (
            c, m('h2_pop'), m('h2_ind'), m('h1_pop'), m('h1_ind'),
            m('final_n_lineages') if c != 'e7-lib' else float('nan'),
            m('final_evenness') if c != 'e7-lib' else float('nan'),
            m('final_pool') if c != 'e7-lib' else m('n_macros'),
            m('transfer_events') if c != 'e7-lib' else float('nan')))

    rng = np.random.default_rng(0)

    def boot(a, b):
        d = np.array(a) - np.array(b)
        if len(d) == 0:
            return float('nan'), float('nan'), float('nan')
        bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
        return float(d.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))

    def sign_p(a, b):
        diffs = [x - y for x, y in zip(a, b)]
        w = sum(1 for d in diffs if d > 0)
        l = sum(1 for d in diffs if d < 0)
        n = w + l
        if n == 0:
            return 1.0
        k = max(w, l)
        tail = sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n
        return min(1.0, 2 * tail)

    P('')
    P('paired comparisons by seed (h2_ind / h2_pop / h1_ind), bootstrap 95% CI, sign-test p')
    seeds = sorted({r['seed'] for r in mains})
    get = lambda c, k: [next(r[k] for r in mains if r['condition'] == c and r['seed'] == s)
                        for s in seeds]
    for a, b in (('share-multi-v2', 'share-best'), ('share-multi-v2', 'share-multi'),
                 ('share-multi-v2', 'iso-best'), ('share-multi-v2', 'share-rand'),
                 ('share-multi-v2', 'e7-lib-8'), ('share-best', 'e7-lib-8'),
                 ('share-multi', 'share-best'), ('share-best', 'iso-best'),
                 ('share-multi', 'e7-lib'), ('share-rand', 'iso-best')):
        for k in ('h2_ind', 'h2_pop', 'h1_ind'):
            d, lo, hi = boot(get(a, k), get(b, k))
            P('  %-11s - %-10s %-7s mean %+.3f CI [%+.3f, %+.3f] sign p %.3f'
              % (a, b, k, d, lo, hi, sign_p(get(a, k), get(b, k))))

    P('')
    P('diversity: final n_lineages / evenness per seed')
    for c in POP_CONDITIONS:
        rs = by_cond.get(c, [])
        P('  %-12s lineages %s evenness %s' % (
            c, [r['final_n_lineages'] for r in rs],
            [round(r['final_evenness'], 2) for r in rs]))

    P('')
    P('per held-out domain, h2_ind means:')
    for dom in ('math', 'bio', 'code', 'physics'):
        parts = []
        for c in POP_CONDITIONS + ('e7-lib', 'e7-lib-8'):
            rs = [r for r in mains if r['condition'] == c and r['held_out'] == dom]
            parts.append('%s %.3f (n=%d)' % (
                c, np.mean([r['h2_ind'] for r in rs]) if rs else float('nan'), len(rs)))
        P('  %-8s %s' % (dom, ' | '.join(parts)))

    P('')
    P('ablation audit (both multi arms): remove one lineage\'s macros, re-eval h2')
    for cond in ('share-multi', 'share-multi-v2'):
        rows_a = [(r, a) for r in mains if r['condition'] == cond and r['ablation']
                  for a in r['ablation']]
        pos = [(r, a) for r, a in rows_a if a['attributed_credit'] > 0]
        if pos:
            mt = float(np.mean([a['true_marginal'] for _, a in pos]))
            frac = float(np.mean([a['true_marginal'] > 0 for _, a in pos]))
            P('  %s: %d credited lineages, mean true_marginal %+.3f, fraction with true_marginal>0 %.2f'
              % (cond, len(pos), mt, frac))
        neg = sum(1 for _, a in rows_a if a['true_marginal'] < 0)
        P('  %s: %d ablation rows total, %d with negative true marginal' % (cond, len(rows_a), neg))
    for r in mains:
        if r['condition'] in ('share-multi', 'share-multi-v2') and r['ablation']:
            for a in r['ablation']:
                P('  %s seed %d lineage %s attributed_credit %d true_marginal_h2pop %+.3f'
                  % (r['condition'], r['seed'], a['lineage'], a['attributed_credit'], a['true_marginal']))

    P('')
    P('counterfactual credit cost: mean re-solves per run: %s'
      % {c: round(float(np.mean([r['cf_resolves'] for r in mains if r['condition'] == c and r['cf_resolves'] is not None])), 1)
         for c in POP_CONDITIONS if any(r['condition'] == c and r['cf_resolves'] for r in mains)})
    nec = {c: (sum(r['transfer_events'] or 0 for r in mains if r['condition'] == c),
               sum(r['necessary_transfers'] or 0 for r in mains if r['condition'] == c))
           for c in POP_CONDITIONS}
    P('transfer uses vs counterfactual-necessary transfers (main suite totals): %s' % nec)

    P('')
    P('spammer suite (1 junk-publishing mind): counterfactual credit vs publication credit')
    for c in ('share-multi-v2', 'share-multi-pub'):
        rs = [r for r in spams if r['condition'] == c]
        if not rs:
            continue
        surv = sum(r['spammer_selections_survived'] for r in rs)
        tot = sum(r['spammer_selections_total'] for r in rs)
        P('  %-16s selections survived %d/%d, final pool %.1f, h2_ind %.3f, h2_pop %.3f'
          % (c, surv, tot, float(np.mean([r['final_pool'] for r in rs])),
             float(np.mean([r['h2_ind'] for r in rs])),
             float(np.mean([r['h2_pop'] for r in rs]))))

    text = '\n'.join(lines) + '\n'
    (OUT / 'analysis.txt').write_text(text)
    print(text)


if __name__ == '__main__':
    main()
