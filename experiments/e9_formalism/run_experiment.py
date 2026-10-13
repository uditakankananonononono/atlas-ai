"""No dependencies. Writes deterministic evidence, excludes wall-clock claims."""
import argparse
import hashlib
import json
import platform
from random import Random
from formalism import P, discover, Operator, berlekamp_massey, fits, bounded_synthesis
from environment import make_environment, sequence, nth, switched_sequence


def run():
    rows, negatives = [], []
    for seed in (17, 29, 43, 71, 101):
        for family in ('dense', 'diagonal', 'jordan'):
            for dimension in (2, 4, 6, 8):
                ident = seed*100+dimension
                m, state, obs = make_environment(ident, family, dimension)
                all_values = sequence(m, state, obs, 64)
                # 16 fitting + 8 validation values. Test 40 additional values
                # plus distant indices against separately implemented oracle.
                prefix = all_values[:24]
                op = discover(prefix, 8, 8)
                bm_c = berlekamp_massey(prefix[:16])
                bm = Operator(bm_c, tuple(prefix[:len(bm_c)])) if bm_c and fits(prefix, bm_c) else None
                enum, tried, stopped = bounded_synthesis(prefix)
                indices = list(range(24, 64))+[100, 1000, 10**6+seed, 10**12+seed]
                truth = [nth(m, state, obs, i) for i in indices]
                def score(model):
                    return sum(model is not None and model.predict(i) == y for i,y in zip(indices, truth))
                rng = Random(ident)
                shuffled = prefix[:]
                rng.shuffle(shuffled)
                shuffled_op = discover(shuffled, 8, 8)
                row = {'seed': seed, 'family': family, 'dimension': dimension,
                       'test_predictions': len(indices), 'discovery_correct': score(op),
                       'bm_correct': score(bm), 'enumerative_correct': score(enum),
                       'enumerative_candidates': tried, 'enumerative_stop': stopped,
                       'shuffle_correct': score(shuffled_op),
                       'operator': op.definition() if op else None,
                       'prefix': prefix, 'indices': indices, 'truth': truth,
                       'indices_under_iteration_cap_10000': sum(i < 10000 for i in indices)}
                # Associativity and jump composition are testable predictions,
                # not separate rewards for operator name or equation length.
                if op:
                    a,b,c = [op.power(rng.randrange(100)) for _ in range(3)]
                    row['associative'] = op.compose(op.compose(a,b),c) == op.compose(a,op.compose(b,c))
                    row['jump_composition'] = op.compose(op.power(37),op.power(91)) == op.power(128)
                rows.append(row)
        r = Random(seed)
        random_seq = [r.randrange(P) for _ in range(24)]
        negatives.append({'seed':seed,'kind':'iid_random','accepted':discover(random_seq) is not None})
        m,s,o = make_environment(seed, 'dense', 4)
        changed = sequence(m,s,o,24)
        changed[20] = (changed[20]+1) % P
        negatives.append({'seed':seed,'kind':'validation_corruption','accepted':discover(changed) is not None})
        # Genuine transition-matrix switch after the observed prefix.
        after, _, _ = make_environment(seed+10000, 'dense', 4)
        changed_values = switched_sequence(m,after,s,o,101,switch_at=24)
        old_prefix = sequence(m,s,o,24)
        assert changed_values[:24] == old_prefix
        op = discover(old_prefix)
        negatives.append({'seed':seed,'kind':'delayed_matrix_switch',
                          'switch_transition_at':24,'accepted':op is not None,
                          'future_index':100,'predicted':op.predict(100) if op else None,
                          'actual_after_switch':changed_values[100],
                          'old_regime_actual':nth(m,s,o,100),
                          'future_correct':op is not None and op.predict(100)==changed_values[100],
                          'suffix_test_points':77,
                          'suffix_correct':sum(op is not None and op.predict(i)==changed_values[i]
                                               for i in range(24,101))})
    totals = {key:sum(row[key] for row in rows) for key in
              ('test_predictions','discovery_correct','bm_correct','enumerative_correct',
               'shuffle_correct','indices_under_iteration_cap_10000')}
    return {'schema':1, 'python':platform.python_version(),
            'data_provenance':'experimenter-authored synthetic prime-field linear dynamical systems',
            'source_commit':'4f68f54a0d0742982192aa643c2fa92d61437c9b',
            'protocol':{'fit_points':16,'validation_points':8,'max_order':8,
                        'seeds':[17,29,43,71,101],'distant_indices':'100,1000,10^6+seed,10^12+seed',
                        'plain_synthesis_grammar':'sum_j c_j*a[t-d+j], c in {-2,-1,0,1,2}',
                        'enumeration_budget':20000,'tuning_on_test':False},
            'totals':totals,'tasks':rows,'negative_controls':negatives}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',default='results.json')
    args = parser.parse_args()
    data = run()
    payload = json.dumps(data,indent=2,sort_keys=True)+'\n'
    open(args.output,'w').write(payload)
    print(json.dumps(data['totals'],sort_keys=True))
    print('sha256',hashlib.sha256(payload.encode()).hexdigest())
