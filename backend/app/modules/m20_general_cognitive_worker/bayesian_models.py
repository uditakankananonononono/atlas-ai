"""Finite declared hypotheses with supplied conditional likelihoods, not truth."""
from copy import deepcopy
import math
import threading
from .calibration_predictor import number,text

class BayesianModelRegistry:
    kind='bayesian_models'
    boundary='Finite caller-declared exhaustive mutually exclusive hypotheses only; supplied priors, provenance and conditionally independent likelihoods, not verified truth or discovered worlds.'
    def __init__(self,repo):
        self.repo=repo;self.tenant_id=repo.tenant_id;self.state=None;self._revision=0;self._lock=threading.RLock()
    @classmethod
    def load(cls,repo):
        obj=cls(repo);obj._revision,obj.state=repo.read(cls.kind);return obj
    def _publish(self,staged):
        revision=self.repo.write(self.kind,self._revision,staged)
        self.state=staged;self._revision=revision
    def configure(self,hypotheses,*,partition_source,conditional_independence):
        text(partition_source,'partition_source')
        if conditional_independence is not True:raise ValueError('explicit conditional independence assumption required')
        if not isinstance(hypotheses,dict)or not 2<=len(hypotheses)<=32:raise ValueError('2..32 explicit hypotheses required')
        normalized={}
        for name,h in hypotheses.items():
            text(name,'hypothesis name')
            if not isinstance(h,dict):raise ValueError('hypothesis object required')
            prior=number(h.get('prior'),'prior');assumptions=h.get('assumptions')
            if not 0<=prior<=1:raise ValueError('prior[0,1] required')
            if not isinstance(assumptions,dict)or len(assumptions)>32:raise ValueError('bounded assumptions dictionary required')
            for key,value in assumptions.items():text(key,'assumption');text(value,'assumption value')
            normalized[name]={'prior':prior,'assumptions':deepcopy(assumptions)}
        if not math.isclose(math.fsum(h['prior']for h in normalized.values()),1,rel_tol=0,abs_tol=1e-12):raise ValueError('priors must sum to one')
        with self._lock:
            history=[] if self.state is None else deepcopy(self.state['history'])+[deepcopy({**self.state,'history':[]})]
            if len(history)>20:raise ValueError('version history limit20')
            staged={'version':1 if self.state is None else self.state['version']+1,'hypotheses':normalized,'partition_source':partition_source,'conditional_independence':True,'evidence':{},'history':history}
            self._publish(staged)
            return {'version':staged['version'],'status':'configured','boundary':self.boundary}
    def ingest(self,records):
        if not isinstance(records,list)or not 1<=len(records)<=1000:raise ValueError('records require1..1000')
        with self._lock:
            if self.state is None:raise ValueError('configure hypotheses first')
            normalized=[]
            for r in records:
                if not isinstance(r,dict):raise ValueError('evidence object required')
                item={key:text(r.get(key),key)for key in ('evidence_id','source','observation')};likelihoods=r.get('likelihoods')
                if likelihoods is not None:
                    if not isinstance(likelihoods,dict)or not set(likelihoods)<=set(self.state['hypotheses']):raise ValueError('registered likelihood keys required')
                    for val in likelihoods.values():
                        number(val,'likelihood')
                        if not 0<=val<=1:raise ValueError('likelihood[0,1] required')
                normalized.append({**item,'likelihoods':deepcopy(likelihoods)})
            staged=deepcopy(self.state);inserted=0
            for item in normalized:
                key=item['evidence_id']
                if key in staged['evidence']:
                    if staged['evidence'][key]!=item:raise ValueError('evidence identity changed')
                else:staged['evidence'][key]=item;inserted+=1
            if len(staged['evidence'])>1000:raise ValueError('evidence limit1000')
            if inserted:self._publish(staged)
            return {'inserted':inserted,'total':len(self.state['evidence']),'version':self.state['version']}
    def compare(self):
        with self._lock:
            s=deepcopy(self.state)
        output={'status':'abstained','posteriors':None,'current_best':None,'entropy_bits':None,'version':None if s is None else s['version'],'source_truth_verified':False,'boundary':self.boundary}
        if s is None:return {**output,'reason':'unconfigured'}
        rows=[s['evidence'][key]for key in sorted(s['evidence'])]
        output.update({'evidence_ids':[r['evidence_id']for r in rows],'evidence_provenance':[{'source':r['source'],'observation':r['observation']}for r in rows],'partition_source':s['partition_source'],'conditional_independence':s['conditional_independence'],'hypotheses':s['hypotheses']})
        if not rows:return {**output,'reason':'no_evidence'}
        if any(r['likelihoods']is None or set(r['likelihoods'])!=set(s['hypotheses'])for r in rows):return {**output,'reason':'missing_likelihoods'}
        logs={}
        for name,h in sorted(s['hypotheses'].items()):
            values=[h['prior']]+[r['likelihoods'][name]for r in rows]
            logs[name]=-math.inf if 0 in values else math.fsum(math.log(v)for v in values)
        peak=max(logs.values())
        if peak==-math.inf:return {**output,'reason':'zero_joint_evidence_probability'}
        weights={key:math.exp(value-peak)for key,value in logs.items()};total=math.fsum(weights.values());posterior={key:value/total for key,value in weights.items()}
        best=max(posterior,key=posterior.get);tied=sum(math.isclose(v,posterior[best],rel_tol=0,abs_tol=1e-12)for v in posterior.values())>1
        return {**output,'status':'compared','reason':None,'posteriors':posterior,'current_best':None if tied else best,'entropy_bits':-math.fsum(v*math.log2(v)for v in posterior.values()if v>0),'estimator':'Normalized prior times product of supplied conditionally independent likelihoods (log space)'}
