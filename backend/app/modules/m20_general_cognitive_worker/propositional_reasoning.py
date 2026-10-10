"""Bounded propositional CNF entailment with independently checkable receipts."""
class _Budget(Exception):pass

def reason(data):
    if not isinstance(data,dict):raise ValueError('input must be object')
    clauses=data.get('clauses');query=data.get('query');limit=data.get('max_steps',10000)
    if type(limit) is not int or not 1<=limit<=50000:raise ValueError('max_steps requires integer 1..50000')
    if not isinstance(clauses,list) or not 1<=len(clauses)<=128:raise ValueError('clauses require 1..128 CNF clauses')
    if not isinstance(query,list) or not 1<=len(query)<=32:raise ValueError('query requires 1..32 disjoined literals')
    for clause in clauses+[query]:
        if not isinstance(clause,list) or len(clause)>32 or any(type(x) is not int or x==0 or abs(x)>32 for x in clause):raise ValueError('literals require signed exact integers 1..32, max32 per clause')
    original=clauses+[[-q]for q in query]
    normalized=[frozenset(c)for c in original]
    variables=sorted({abs(x)for c in normalized for x in c})
    work=0
    def tick():
        nonlocal work
        work+=1
        if work>limit:raise _Budget()
    def search(current,assignment):
        tick()
        current=[c for c in current if not any(-x in c for x in c)]
        while True:
            if any(not c for c in current):return None
            if not current:return assignment
            unit=next((next(iter(c))for c in current if len(c)==1),None)
            if unit is None:break
            tick();v=abs(unit)
            if v in assignment and assignment[v]!=(unit>0):return None
            assignment={**assignment,v:unit>0}
            current=[frozenset(x for x in c if x!=-unit)for c in current if unit not in c]
        v=min(abs(x)for c in current for x in c)
        for value in (False,True):
            lit=v if value else -v
            reduced=[frozenset(x for x in c if x!=-lit)for c in current if lit not in c]
            result=search(reduced,{**assignment,v:value})
            if result is not None:return result
        return None
    result={'algorithm':'bounded_propositional_DPLL_resolution','status':'inconclusive',
            'counterexample':None,'resolution_proof':[], 'real_world_truth_verified':False,
            'scope':'Finite propositional CNF entailment over supplied axioms, not first-order reasoning or verified real-world truth.'}
    try:
        model=search(normalized,{})
        if model is not None:
            result.update(status='not_entailed',counterexample={str(v):model.get(v,False)for v in variables})
        else:
            proof=[];known=[];seen=set()
            for index,c in enumerate(normalized):
                if c in seen or any(-x in c for x in c):continue
                seen.add(c);known.append(c);proof.append({'clause':sorted(c),'source':index,'parents':None,'pivot':None})
                if not c:break
            empty=next((i for i,c in enumerate(known)if not c),None)
            right=0
            while empty is None and right<len(known):
                for left in range(right):
                    a,b=known[left],known[right]
                    for pivot in sorted(a):
                        tick()
                        if -pivot not in b:continue
                        resolvent=(a-{pivot})|(b-{-pivot})
                        if any(-x in resolvent for x in resolvent)or resolvent in seen:continue
                        seen.add(resolvent);known.append(resolvent)
                        proof.append({'clause':sorted(resolvent),'source':None,'parents':[left,right],'pivot':pivot})
                        if not resolvent:empty=len(known)-1;break
                    if empty is not None:break
                right+=1
            if empty is not None:result.update(status='entailed',resolution_proof=proof[:empty+1])
    except _Budget:pass
    result['steps']=min(work,limit);result['max_steps']=limit
    return result
