import argparse
import hashlib
import json
import platform
from critique import Policy, make_graph, metric, external_error, admit, auc


def run():
    policies = ([Policy('bfs_'+str(i),'bfs',i) for i in range(2)] +
                [Policy('heuristic_'+str(i),'heuristic',i) for i in (1,2,4,8,16,32)] +
                [Policy('quantized_'+str(i),'quantized',i) for i in (2,4,8,16)] +
                [Policy('dijkstra','dijkstra')])
    axes = ('relabel','subdivide','scale','irrelevant_component')
    seeds = (11,23,47,83,131)
    runs = []
    for seed in seeds:
        # Disjoint task identities; deployment has more varied labels via
        # transformation but no critic access, no refit, no metric threshold edit.
        def cases(offset, mode, n):
            return [make_graph(seed*100000+offset+i,mode) for i in range(n)]
        nominal = cases(0,'nominal',60)
        discovery = cases(1000,'challenge',60)
        validation = cases(2000,'challenge',120)
        deployment = cases(3000,'challenge',200)
        scores = {kind:[metric(p,discovery,kind) for p in policies] for kind in axes}
        errors = [external_error(p,validation) for p in policies]
        labels = [x>.10 for x in errors]
        gate = admit(scores,labels,seed)
        deployment_errors = [external_error(p,deployment) for p in policies]
        rows = [{'policy':p.name,'nominal_error':external_error(p,nominal),
                 'metrics':{k:scores[k][i] for k in axes},
                 'independent_validation_error':errors[i],
                 'deployment_error':deployment_errors[i]} for i,p in enumerate(policies)]
        # Old rule: first policy of best nominal accuracy. Fixed before run.
        old = min(range(len(policies)),key=lambda i:(rows[i]['nominal_error'],i))
        dimension = gate['proposed']
        new = min(range(len(policies)),key=lambda i:(rows[i]['nominal_error'],scores[dimension][i],i)) if gate['admitted'] else old
        # Strong baseline uses held-out oracle evaluation, no invented metric.
        oracle_choice = min(range(len(policies)),key=lambda i:(errors[i],i))
        runs.append({'seed':seed,'admission':gate,'policies':rows,
                     'selected_old':policies[old].name,'selected_redefined':policies[new].name,
                     'selected_oracle_baseline':policies[oracle_choice].name,
                     'old_deployment_error':deployment_errors[old],
                     'redefined_deployment_error':deployment_errors[new],
                     'oracle_baseline_deployment_error':deployment_errors[oracle_choice],
                     'deployment_auc':auc(scores[dimension],[e>.10 for e in deployment_errors]),
                     'uninformative_metric_control':admit({'constant':[0]*len(policies)},labels,seed)})
    return {'schema':1,'python':platform.python_version(),
            'source_commit':'4f68f54a0d0742982192aa643c2fa92d61437c9b',
            'data_provenance':'experimenter-authored synthetic weighted directed graphs and authored policy catalogue',
            'protocol':{'task_counts_per_seed':{'nominal':60,'discovery':60,'validation':120,'deployment':200},
                        'seeds':list(seeds),'axes':axes,'risk_label':'independent error >0.10',
                        'evaluator':'Bellman-Ford, independent of candidate heap/BFS algorithms',
                        'metric_catalogue_authored':True,'deployment_visible_to_critic':False,
                        'self_reward':False,'policy_family_holdout':False},
            'runs':runs}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',default='results.json')
    args = parser.parse_args()
    data = run()
    payload = json.dumps(data,indent=2,sort_keys=True)+'\n'
    open(args.output,'w').write(payload)
    for row in data['runs']:
        print(row['seed'],row['admission']['proposed'],row['admission']['admitted'],
              row['admission']['corrected_permutation_p'],row['selected_redefined'],
              row['old_deployment_error'],row['redefined_deployment_error'],row['oracle_baseline_deployment_error'])
    print('sha256',hashlib.sha256(payload.encode()).hexdigest())
