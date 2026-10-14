"""Run from repo root: PYTHONPATH=backend python research/atlas_repair_frontier/run_benchmark.py"""
import json,random,time
from functools import lru_cache
from pathlib import Path
from app.modules.atlas_repair_frontier import Candidate,frontier,supported_points,greedy,replay

def run(seed_count=100,node_count=12):
    records=[];start=time.perf_counter()
    for seed in range(seed_count):
        rng=random.Random(seed)
        nodes=[Candidate(str(i),rng.randint(1,9),rng.randint(0,15),tuple(str(j) for j in range(i) if rng.random()<.16),rng.random()>.1) for i in range(node_count)]
        points=frontier(nodes);supported=supported_points(points)
        feasible_all=[n for n in nodes if n.executable]
        # A child of a non-executable node cannot be republished.
        ready=set()
        for n in nodes:
            if n.executable and set(n.parents)<=ready:ready.add(n.key)
        full_cost=sum(n.cost for n in nodes if n.key in ready)
        by_key={n.key:n for n in nodes}
        @lru_cache(None)
        def independent_value(key):
            return 2+sum(independent_value(parent) for parent in by_key[key].parents)
        full={key:independent_value(key) for key in ready}
        for cap in range(1,sum(n.cost for n in nodes)+1):
            exact=max((p for p in points if p['cost']<=cap),key=lambda p:p['value'])
            scalar=max((p for p in supported if p['cost']<=cap),key=lambda p:p['value'])
            g=greedy(nodes,cap)
            output=replay(nodes,exact['keys'],evidence_version=2)['outputs']
            assert output=={k:full[k] for k in exact['keys']}
            assert exact['cost']<=cap
            records.append({'seed':seed,'cap':cap,'optimal':exact['value'],'scalarized':scalar['value'],'greedy':g['value'],
                            'selected_cost':exact['cost'],'full_replay_fits':full_cost<=cap,'replay_match':True})
    total=lambda field:sum(r[field] for r in records)
    return {'protocol':{'seeds':seed_count,'nodes_per_graph':node_count,'edges_probability':.16,'nonexecutable_probability':.1,
                        'cost_range':[1,9],'value_range':[0,15],'caps':'every integer 1..sum declared costs',
                        'baseline':'Best budget-feasible point optimal for SOME lambda>=0; exact rational intervals, not finite sweep',
                        'warning':'Not MemoRepair reproduction; synthetic declared utility/cost, complete supplied provenance, no model calls'},
            'results':{'graph_cap_pairs':len(records),'exact_total_utility':total('optimal'),'scalarized_total_utility':total('scalarized'),
                       'greedy_total_utility':total('greedy'),'exact_strictly_beats_scalarized':sum(r['optimal']>r['scalarized'] for r in records),
                       'exact_strictly_beats_greedy':sum(r['optimal']>r['greedy'] for r in records),
                       'full_replay_over_budget':sum(not r['full_replay_fits'] for r in records),'replay_matches':sum(r['replay_match'] for r in records),
                       'budget_violations':sum(r['selected_cost']>r['cap'] for r in records),'wall_seconds':time.perf_counter()-start},'records':records}
if __name__=='__main__':
    result=run();path=Path('research/atlas_repair_frontier/results.json');path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
