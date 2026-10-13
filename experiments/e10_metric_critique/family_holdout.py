"""Metric chosen/admitted on one policy family, predictions on another.

No new family is used in gate tuning or selection. A deliberately incorrect
invariant constant policy shows why metric success alone is not correctness.
"""
import json
from critique import Policy, make_graph, metric, external_error, admit, auc


class ConstantPolicy:
    name = 'adversarial_always_zero'
    def solve(self, graph, source, target):
        return 0


def run():
    axes = ('relabel','subdivide','scale','irrelevant_component')
    rows = []
    for seed in (11,23,47,83,131):
        proposal_policies = [Policy('heuristic_'+str(i),'heuristic',i) for i in (1,2,4,8,16,32)]
        # Six low-error controls balance the proposal population, but are not
        # independent policy families. Cluster-independence remains a caveat.
        proposal_policies += [Policy('quantized_'+str(i),'quantized',i) for i in (1,2,3,4,5,6)]
        transfer_policies = [Policy('bfs_forward','bfs',0),Policy('bfs_reverse','bfs',1),
                             Policy('exact_dijkstra','dijkstra')]
        def cases(offset,n):
            return [make_graph(seed*100000+offset+i,'challenge') for i in range(n)]
        proposal,validation,transfer = cases(4000,80),cases(5000,120),cases(6000,200)
        scores = {kind:[metric(p,proposal,kind) for p in proposal_policies] for kind in axes}
        labels = [external_error(p,validation)>.10 for p in proposal_policies]
        gate = admit(scores,labels,seed)
        kind = gate['proposed']
        transfer_scores = [metric(p,proposal,kind) for p in transfer_policies]
        transfer_errors = [external_error(p,transfer) for p in transfer_policies]
        adversary = ConstantPolicy()
        rows.append({'seed':seed,'admission':gate,'heldout_families':['bfs','dijkstra'],
                     'transfer_auc':auc(transfer_scores,[x>.10 for x in transfer_errors]),
                     'transfer':[{'policy':p.name,'metric_failure':score,'external_error':err}
                                 for p,score,err in zip(transfer_policies,transfer_scores,transfer_errors)],
                     'invariant_wrong_control':{'metric_failure':metric(adversary,proposal,kind),
                                                 'external_error':external_error(adversary,transfer)}})
    return {'authored_synthetic':True,'policy_family_holdout':True,'runs':rows}


if __name__ == '__main__':
    data = run()
    open('experiments/e10_metric_critique/family_holdout_results.json','w').write(json.dumps(data,indent=2,sort_keys=True)+'\n')
    for r in data['runs']:
        print(r['seed'],r['admission']['proposed'],r['admission']['admitted'],r['transfer_auc'],r['invariant_wrong_control'])
