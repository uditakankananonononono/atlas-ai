"""Independent exhaustive combinations oracle; does not import optimizer code.
Run after run_benchmark.py from repository root.
"""
import json,random
from itertools import combinations
from pathlib import Path

def validate():
    result=json.loads(Path('research/atlas_repair_frontier/results.json').read_text())
    assert result['protocol']['seeds']==100 and result['protocol']['nodes_per_graph']==12
    checked=0
    for seed in range(100):
        rng=random.Random(seed);nodes=[]
        for i in range(12):
            cost=rng.randint(1,9);value=rng.randint(0,15)
            parents={j for j in range(i) if rng.random()<.16};executable=rng.random()>.1
            nodes.append((cost,value,parents,executable))
        by_cost={0:0}
        for count in range(1,13):
            for selected in combinations(range(12),count):
                keys=set(selected)
                if all(nodes[i][3] and nodes[i][2]<=keys for i in selected):
                    cost=sum(nodes[i][0] for i in selected);value=sum(nodes[i][1] for i in selected)
                    by_cost[cost]=max(value,by_cost.get(cost,0))
        for row in result['records']:
            if row['seed']!=seed:continue
            expected=max(value for cost,value in by_cost.items() if cost<=row['cap'])
            assert row['optimal']==expected,(seed,row,expected)
            checked+=1
    print(f'INDEPENDENT_ORACLE_MATCH {checked} of {len(result["records"])} graph/cap cases')
if __name__=='__main__':validate()
