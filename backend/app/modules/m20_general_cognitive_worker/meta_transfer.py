"""Bounded structural strategy abstraction from verified supplied executions."""
from copy import deepcopy
import threading

def problem(value):
    if not isinstance(value,dict)or value.get('objective') not in ('precedence_safe_completion','dependency_safe_setup_continuity'):raise ValueError('unsupported problem objective')
    tasks,edges=value.get('tasks'),value.get('dependencies')
    if not isinstance(tasks,list)or not 1<=len(tasks)<=64 or any(not isinstance(t,str)or not t.strip()or len(t)>120 for t in tasks)or len(set(tasks))!=len(tasks):raise ValueError('unique bounded tasks required')
    if not isinstance(edges,list)or not 1<=len(edges)<=256:raise ValueError('bounded nonempty dependencies required')
    seen=set()
    for e in edges:
        if not isinstance(e,list)or len(e)!=2 or any(t not in tasks for t in e)or e[0]==e[1]or tuple(e)in seen:raise ValueError('declared unique nonself dependencies required')
        seen.add(tuple(e))
    plan=[];remaining=set(tasks)
    while remaining:
        ready=sorted(t for t in remaining if all(a in plan for a,b in edges if b==t))
        if not ready:raise ValueError('cyclic dependencies')
        plan.append(ready[0]);remaining.remove(ready[0])
    if value['objective']=='dependency_safe_setup_continuity':
        groups=value.get('groups')
        if not isinstance(groups,dict)or set(groups)!=set(tasks)or any(not isinstance(v,str)or not v.strip()or len(v)>120 for v in groups.values()):raise ValueError('declared task groups required')
    return tasks,edges,plan

def policy_plan(tasks,edges,groups,policy):
    plan=[];remaining=set(tasks)
    while remaining:
        ready=sorted(t for t in remaining if all(a in plan for a,b in edges if b==t))
        if policy=='prefer_previous_group_then_lexical'and plan:
            matching=[t for t in ready if groups[t]==groups[plan[-1]]]
            if matching:ready=matching
        plan.append(ready[0]);remaining.remove(ready[0])
    return plan

def text(value,label):
    if not isinstance(value,str)or not value.strip()or len(value)>240:raise ValueError(f'{label} required bounded string')
    return value

class TransferLearner:
    kind='meta_transfer'
    def __init__(self,repo):self.repo=repo;self.tenant_id=repo.tenant_id;self.patterns={};self._revision=0;self._lock=threading.RLock()
    @classmethod
    def load(cls,repo):
        obj=cls(repo);obj._revision,payload=repo.read(cls.kind)
        if payload is not None:obj.patterns=payload
        return obj
    def learn(self,episode):
        if not isinstance(episode,dict):raise ValueError('episode object required')
        ident=text(episode.get('episode_id'),'episode_id');domain=text(episode.get('domain'),'domain');provenance=text(episode.get('provenance'),'provenance')
        outcome=episode.get('outcome')
        if outcome not in ('succeeded','failed'):raise ValueError('explicit succeeded/failed outcome required')
        if outcome=='failed':return {'status':'excluded','reason':'failed outcome cannot support transfer'}
        tasks,edges,_=problem(episode.get('problem'));order=episode.get('executed_order')
        if not isinstance(order,list)or len(order)!=len(tasks)or set(order)!=set(tasks)or any(order.index(a)>=order.index(b)for a,b in edges):raise ValueError('successful execution must demonstrate every precedence invariant')
        policy=None;mismatches={}
        if episode['problem']['objective']=='dependency_safe_setup_continuity':
            groups=episode['problem']['groups']
            for candidate in ('lexical_ready_first','prefer_previous_group_then_lexical'):
                expected=policy_plan(tasks,edges,groups,candidate)
                mismatches[candidate]=sum(a!=b for a,b in zip(expected,order))
            supported=[p for p,count in mismatches.items()if count==0]
            if len(supported)!=1:return {'status':'abstained','reason':'demonstration does not uniquely support a declared policy'}
            policy=supported[0]
        record={'learned_policy':policy,'policy_mismatch_counts':mismatches,'status':'abstracted','episode_id':ident,'domain':domain,'provenance':provenance,'source':deepcopy(episode),
                'abstraction':episode['problem']['objective'],'source_roles':['prerequisite','dependent'],
                'preconditions':['finite acyclic dependencies over declared tasks'],
                'invariants':['every task appears once','each prerequisite precedes dependent'],
                'outcome_signal':'caller-supplied successful order satisfies checked dependency invariants',
                'boundary':'Induces a fixed dependency-order strategy from supplied successful execution; not general task learning or independent outcome verification.'}
        with self._lock:
            if ident in self.patterns:
                if self.patterns[ident]!=record:raise ValueError('episode identity reused with changed evidence')
                return deepcopy(self.patterns[ident])
            if len(self.patterns)>=128:raise ValueError('pattern limit128')
            staged={**self.patterns,ident:record};revision=self.repo.write(self.kind,self._revision,staged)
            self.patterns=staged;self._revision=revision;return deepcopy(record)
    def transfer(self,target):
        abstain={'status':'abstained','plan':None,'execution_authorized':False,'boundary':'Unsupported mapping or no disjoint-domain demonstrated strategy'}
        if not isinstance(target,dict):return abstain
        try:domain=text(target.get('domain'),'domain');tasks,edges,plan=problem(target.get('problem'))
        except ValueError:return abstain
        with self._lock:
            sources=[v for _,v in sorted(self.patterns.items())if v['domain']!=domain and v['abstraction']==target['problem']['objective']]
            if not sources:return abstain
            source=sources[0]
            if source['learned_policy'] is not None:
                plan=policy_plan(tasks,edges,target['problem']['groups'],source['learned_policy'])
            return {'status':'plan_candidate','plan':plan,'execution_authorized':False,'source_episode_ids':[source['episode_id']],
                    'source_provenance':[source['provenance']],'preconditions':deepcopy(source['preconditions']),
                    'invariants':deepcopy(source['invariants']),
                    'mapping':{'learned_policy':source['learned_policy'],'source_roles':deepcopy(source['source_roles']),'source_dependencies':deepcopy(source['source']['problem']['dependencies']),'target_dependencies':deepcopy(edges),'target_tasks':deepcopy(tasks)},
                    'boundary':'Fixed precedence-order abstraction adapted to explicit held-out-domain dependency graph; no success guarantee, execution or open-world learning.'}
