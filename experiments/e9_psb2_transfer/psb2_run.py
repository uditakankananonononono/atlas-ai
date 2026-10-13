"""Frozen protocol. Exact and extended results are never pooled.
PSB2 problems are distinct tasks, NOT scientific domains. Resampled instances are
not independent tasks. No bootstrap across 20 seeds is presented as n=120 domains.
"""
import argparse, contextlib, json, sys, time
from pathlib import Path
from functools import lru_cache
from psb2_data import ROOT, PROBLEMS, NATIVE, task, manifest
sys.path.append(str(ROOT.parent/'e7_library_transfer'))
import dsl, library, extended

@contextlib.contextmanager
def backend(module):
    # Reuse unchanged e7 candidate extraction, promotion, fit/validation split,
    # generous discovery budget, macro size and random-library generation.
    keys=('PRIMS','solve','verify')
    old={k:getattr(library,k) for k in keys}
    try:
        for k in keys: setattr(library,k,getattr(module,k))
        yield
    finally:
        for k,v in old.items():setattr(library,k,v)

def result(t,lib,b,module):
    p,n=module.solve(t,lib,b)
    verified=p is not None and module.verify(t,p,lib)
    return dict(solved=bool(verified),program=p,programs_evaluated=n)

def within(t,b,module,seed):
    # One target problem is a tiny domain. Split its training IO into separate
    # pseudo-tasks to allow the unmodified e7 >=2 fit-task rule. This is explicitly
    # within-problem validation, not additional independently specified problems.
    # All held-out target test IO is forbidden to this training path.
    examples=t['train']
    shards=[]
    for j in range(8):
        rows=examples[j::8]
        cut=len(rows)//2
        shards.append(dict(domain=t['domain'],desc=t['desc']+f'/shard{j}',
                           train=rows[:cut],test=rows[cut:]))
    return library.learn(shards,b,seed=seed,min_domains=1)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--seeds',type=int,default=5)
    parser.add_argument('--budgets',type=int,nargs='+',default=[1000,3000,10000])
    parser.add_argument('--track',choices=['exact','extended','all'],default='all')
    args=parser.parse_args()
    rows=[]; artifacts={}; start=time.monotonic()
    for track,module,names in [('exact',dsl,NATIVE),('extended',extended,PROBLEMS)]:
        if args.track not in (track,'all'):continue
        with backend(module):
            for b in args.budgets:
                # Authored source tasks remain unchanged in exact track. In extended
                # track only argument container changes. No target-derived programs.
                source=dsl.make_tasks(0)
                if track=='extended':
                    source=[dict(t,train=[([list(i)],o) for i,o in t['train']],
                                   test=[([list(i)],o) for i,o in t['test']]) for t in source]
                source_lib,source_log=library.learn(source,b,seed=0)
                for seed in range(args.seeds):
                    tasks=[task(name,seed,extended=track=='extended') for name in names]
                    for target in tasks:
                        held=target['domain']
                        other=[t for t in tasks if t['domain']!=held]
                        psb_lib,psb_log=library.learn(other,b,seed=seed)
                        own_lib,own_log=within(target,b,module,seed)
                        # Strict size match, including k=0 (fix e7.run's max(1,k)).
                        random=library.random_lib(len(source_lib),seed=seed+b)
                        controls={'base':{},'transfer':source_lib,'random':random,
                                  'psb_lopo':psb_lib,'within':own_lib}
                        entry=dict(track=track,budget=b,seed=seed,target=held)
                        entry.update({key:result(target,lib,b,module) for key,lib in controls.items()})
                        entry['macro_counts']={key:len(lib) for key,lib in controls.items()}
                        rows.append(entry)
                        artifacts[f'{track}/{b}/{seed}/{held}']={
                            'libs':controls,'source_log':source_log,'psb_log':psb_log,'own_log':own_log}
                        print(track,b,seed,held,{k:v['solved'] for k,v in entry.items() if isinstance(v,dict) and 'solved' in v},flush=True)
    (ROOT/'rows.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    (ROOT/'libraries.json').write_text(json.dumps(artifacts,sort_keys=True,indent=1)+'\n')
    (ROOT/'manifest.json').write_text(json.dumps(manifest(),sort_keys=True,indent=2)+'\n')
    print('seconds',round(time.monotonic()-start,2))
if __name__=='__main__':main()
