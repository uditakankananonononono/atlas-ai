"""High-budget BASE search plus hand-authored witnesses, not abstraction evidence."""
import json
from psb2_data import PROBLEMS,ROOT,task
import extended

def main():
    rows=[]
    for name in PROBLEMS:
        t=task(name,extended=True)
        p,n=extended.solve(t,{},600000)
        witness=extended.WITNESSES[name]
        row=dict(target=name,budget=600000,program=p,programs_evaluated=n,
                 verified=bool(p is not None and extended.verify(t,p,{})),
                 authored_witness=witness,witness_verified=extended.verify(t,witness,{}))
        rows.append(row);print(json.dumps(row),flush=True)
    (ROOT/'coverage.json').write_text(json.dumps(rows,indent=1)+'\n')
if __name__=='__main__':main()
