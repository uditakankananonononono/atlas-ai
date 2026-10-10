"""Budgeted exact-key lookup in an explicit immutable supplied local corpus."""
from copy import deepcopy
import math
import threading
from .calibration_predictor import number,text

class CuriosityInvestigator:
    kind='curiosity_investigator'
    boundary='Entropy/relevance/cost rubric proxy only, not expected intrinsic learning value. Exact-key supplied local corpus lookup; no external retrieval, side effects or independent truth verification.'
    def __init__(self,repo):
        self.repo=repo;self.tenant_id=repo.tenant_id;self._revision=0;self._lock=threading.RLock();self.state={'sources':{},'questions':{},'results':{},'budget':0,'spent':0,'preauthorized':False}
    @classmethod
    def load(cls,repo):
        obj=cls(repo);obj._revision,payload=repo.read(cls.kind)
        if payload is not None:obj.state=payload
        return obj
    def _publish(self,staged):
        revision=self.repo.write(self.kind,self._revision,staged);self.state=staged;self._revision=revision
    def authorize(self,sources,*,preauthorized,budget):
        if preauthorized is not True:raise ValueError('explicit local corpus authorization required')
        number(budget,'budget')
        if not 0<budget<=1000:raise ValueError('budget(0,1000] required')
        if not isinstance(sources,list)or not 1<=len(sources)<=32:raise ValueError('1..32 local source records required')
        normalized={}
        for r in sources:
            if not isinstance(r,dict):raise ValueError('local source object required')
            key=text(r.get('source_id'),'source_id');provenance=text(r.get('provenance'),'provenance');answers=r.get('answers')
            if not isinstance(answers,dict)or len(answers)>1000:raise ValueError('bounded local answer dictionary required')
            for k,v in answers.items():text(k,'lookup_key');text(v,'answer')
            if key in normalized:raise ValueError('duplicate source identity')
            normalized[key]={'source_id':key,'provenance':provenance,'answers':deepcopy(answers)}
        with self._lock:
            if self.state['preauthorized']:raise ValueError('corpus and budget authorization immutable; new operator state required')
            staged=deepcopy(self.state);staged.update(sources=normalized,budget=budget,preauthorized=True);self._publish(staged)
            return {'status':'local_corpus_authorized','source_ids':sorted(normalized),'budget':budget,'boundary':self.boundary}
    def enqueue(self,records):
        if not isinstance(records,list)or not 1<=len(records)<=1000:raise ValueError('records require1..1000')
        with self._lock:
            if not self.state['preauthorized']:raise ValueError('authorize local corpus first')
            normalized=[]
            for r in records:
                if not isinstance(r,dict):raise ValueError('question object required')
                row={k:text(r.get(k),k)for k in ('question_id','question','lookup_key')}
                p=number(r.get('prior_probability'),'prior_probability');relevance=number(r.get('decision_relevance'),'decision_relevance');cost=number(r.get('cost'),'cost');frequency=r.get('frequency')
                if not 0<=p<=1 or not 0<=relevance<=1 or not 0<cost<=1000:raise ValueError('probability/relevance[0,1] and cost(0,1000] required')
                if type(frequency)is not int or not 1<=frequency<=1000000:raise ValueError('bounded positive integer frequency required')
                ids=r.get('source_ids')
                if not isinstance(ids,list)or not 1<=len(ids)<=32:raise ValueError('allowlisted source IDs required')
                for key in ids:
                    text(key,'source_id')
                    if key not in self.state['sources']:raise ValueError('source outside preauthorized corpus')
                if len(set(ids))!=len(ids):raise ValueError('duplicate source IDs')
                normalized.append({**row,'prior_probability':p,'decision_relevance':relevance,'cost':cost,'frequency':frequency,'source_ids':sorted(ids),'status':'unresolved'})
            staged=deepcopy(self.state);inserted=0
            for row in normalized:
                key=row['question_id']
                if key in staged['questions']:
                    old=staged['questions'][key]
                    if {**old,'status':'unresolved'}!=row:raise ValueError('question identity changed')
                else:staged['questions'][key]=row;inserted+=1
            if len(staged['questions'])>1000:raise ValueError('question limit1000')
            if inserted:self._publish(staged)
            return {'inserted':inserted,'total':len(self.state['questions'])}
    def _queue(self,state):
        result=[]
        for row in state['questions'].values():
            if row['status']!='unresolved':continue
            p=row['prior_probability'];entropy=0. if p in(0,1)else -p*math.log2(p)-(1-p)*math.log2(1-p)
            result.append({**deepcopy(row),'uncertainty_bits':entropy,'priority':entropy*row['decision_relevance']/row['cost'],'expected_learning_value':None,'rubric':'binary entropy times supplied decision relevance divided by supplied lookup cost'})
        return sorted(result,key=lambda r:(-r['priority'],r['question_id']))
    def queue(self):
        with self._lock:return self._queue(self.state)
    def run(self,*,max_cost):
        number(max_cost,'max_cost')
        if not 0<=max_cost<=1000:raise ValueError('max_cost[0,1000] required')
        with self._lock:
            if not self.state['preauthorized']:raise ValueError('authorize local corpus first')
            staged=deepcopy(self.state);remaining=min(max_cost,staged['budget']-staged['spent']);spent=0;results=[]
            for row in self._queue(staged):
                if row['priority']<=0 or row['cost']>remaining:continue
                sources=[]
                for key in row['source_ids']:
                    src=staged['sources'][key];sources.append({'source_id':key,'provenance':src['provenance'],'lookup_key':row['lookup_key'],'answer':src['answers'].get(row['lookup_key'])})
                answers={src['answer']for src in sources if src['answer']is not None}
                status='no_answer'if not answers else 'answered'if len(answers)==1 else 'conflicting_sources'
                answer=next(iter(answers))if status=='answered'else None
                result={'question_id':row['question_id'],'question':row['question'],'status':status,'answer':answer,'gap_narrowed':status=='answered','source_records':sources,'cost':row['cost'],'priority':row['priority'],'source_truth_verified':False,'boundary':self.boundary}
                staged['questions'][row['question_id']]['status']=status;staged['results'][row['question_id']]=deepcopy(result);results.append(result)
                spent+=row['cost'];remaining-=row['cost'];staged['spent']+=row['cost']
            if results:self._publish(staged)
            return {'investigations':results,'spent':spent,'total_spent':staged['spent'],'remaining_budget':staged['budget']-staged['spent'],'boundary':self.boundary}
