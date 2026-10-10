"""Class exponential survival from supplied completed/censored intervals."""
from copy import deepcopy
import math
import threading
from .calibration_predictor import number,text

class DecaySurvival:
    kind='decay_survival'
    boundary='Class exponential hazard, Gamma(1,1) prior and noninformative right-censoring assumption; supplied source histories, not verified truth/freshness. Internal recommendations only.'
    def __init__(self,repo):
        self.repo=repo;self.tenant_id=repo.tenant_id;self.state={'histories':{},'facts':{},'due':{}};self._revision=0;self._lock=threading.RLock()
    @classmethod
    def load(cls,repo):
        obj=cls(repo);obj._revision,payload=repo.read(cls.kind)
        if payload is not None:obj.state=payload
        return obj
    def _publish(self,state):
        revision=self.repo.write(self.kind,self._revision,state);self.state=state;self._revision=revision
    def ingest(self,records):
        if not isinstance(records,list)or not 1<=len(records)<=1000:raise ValueError('records require1..1000')
        normalized=[]
        for r in records:
            if not isinstance(r,dict):raise ValueError('history object required')
            item={key:text(r.get(key),key)for key in ('history_id','fact_class','source')}
            start=number(r.get('started_at'),'started_at');end=number(r.get('ended_at'),'ended_at')
            if end<=start or type(r.get('changed'))is not bool:raise ValueError('positive exposure interval and boolean change required')
            exposure=end-start;number(exposure,'exposure')
            normalized.append({**item,'started_at':start,'ended_at':end,'changed':r['changed']})
        with self._lock:
            staged=deepcopy(self.state);inserted=0
            for row in normalized:
                key=row['history_id']
                if key in staged['histories']:
                    if staged['histories'][key]!=row:raise ValueError('history identity changed')
                else:staged['histories'][key]=row;inserted+=1
            if len(staged['histories'])>2000:raise ValueError('history limit2000')
            if inserted:self._publish(staged)
            return {'inserted':inserted,'total':len(self.state['histories'])}
    def _forecast(self,state,fact_class,horizon,as_of):
        rows=[r for key,r in sorted(state['histories'].items())if r['fact_class']==fact_class and r['ended_at']<=as_of]
        events=sum(r['changed']for r in rows)
        result={'status':'abstained','stale_probability':None,'current_freshness':None,'source_truth_verified':False,'fact_class':fact_class,'horizon':horizon,'as_of':as_of,'boundary':self.boundary}
        if len(rows)<40 or events<5:return {**result,'reason':'sparse_class'}
        exposure=math.fsum(r['ended_at']-r['started_at']for r in rows)
        number(exposure,'class exposure');shape=events+1;rate=exposure+1
        probability=-math.expm1(-shape*math.log1p(horizon/rate))
        return {**result,'status':'forecast','reason':None,'stale_probability':probability,'sample_size':len(rows),'events':events,'censored':len(rows)-events,'exposure':exposure,'gamma_shape':shape,'gamma_rate':rate,'rate_mean':shape/rate,'rate_stddev':math.sqrt(shape)/rate,'history_ids':[r['history_id']for r in rows],'history_sources':[r['source']for r in rows],'estimator':'Gamma(1,1) exponential hazard posterior predictive 1-(rate/(rate+horizon))**shape'}
    def forecast(self,fact_class,*,horizon,as_of):
        text(fact_class,'fact_class');number(horizon,'horizon');number(as_of,'as_of')
        if not 0<=horizon<=100:raise ValueError('supported horizon[0,100] required')
        with self._lock:return self._forecast(self.state,fact_class,horizon,as_of)
    def track(self,fact_id,fact_class,*,source,confirmed_at):
        text(fact_id,'fact_id');text(fact_class,'fact_class');text(source,'source');number(confirmed_at,'confirmed_at')
        row={'fact_id':fact_id,'fact_class':fact_class,'source':source,'confirmed_at':confirmed_at,'evaluated_at':confirmed_at}
        with self._lock:
            if fact_id in self.state['facts']:raise ValueError('fact already tracked; use refresh')
            if len(self.state['facts'])>=1000:raise ValueError('tracked fact limit1000')
            staged=deepcopy(self.state);staged['facts'][fact_id]=row;self._publish(staged)
            return deepcopy(row)
    def refresh(self,fact_id,*,confirmed_at,source):
        text(fact_id,'fact_id');text(source,'source');number(confirmed_at,'confirmed_at')
        with self._lock:
            row=self.state['facts'].get(fact_id)
            if row is None:raise ValueError('unknown fact')
            if confirmed_at<row['evaluated_at']:raise ValueError('refresh cannot precede previous evaluation/confirmation')
            staged=deepcopy(self.state);staged['facts'][fact_id].update(source=source,confirmed_at=confirmed_at,evaluated_at=confirmed_at);staged['due'].pop(fact_id,None);self._publish(staged)
            return {'status':'caller_reconfirmed','source_truth_verified':False,'fact_id':fact_id}
    def evaluate(self,*,as_of):
        number(as_of,'as_of')
        with self._lock:
            staged=deepcopy(self.state);unsupported=[]
            for key,row in sorted(staged['facts'].items()):
                if as_of<row['evaluated_at']:raise ValueError('evaluation cannot precede previous evaluation/confirmation')
                age=as_of-row['confirmed_at'];number(age,'age')
                horizon=min(100,age);forecast=self._forecast(staged,row['fact_class'],horizon,as_of)
                row['evaluated_at']=as_of
                if forecast['status']=='forecast'and forecast['stale_probability']>=.5:
                    staged['due'][key]={'fact_id':key,'fact_class':row['fact_class'],'source':row['source'],'confirmed_at':row['confirmed_at'],'evaluated_at':as_of,'forecast_horizon':horizon,'age':age,'stale_probability':forecast['stale_probability'],'history_ids':forecast['history_ids'],'reason':'predicted_stale_probability_at_least_half','recommendation_only':True}
                else:
                    staged['due'].pop(key,None)
                    if forecast['status']!='forecast':unsupported.append(key)
            if staged!=self.state:self._publish(staged)
            return {'due':[deepcopy(staged['due'][k])for k in sorted(staged['due'])],'unsupported_fact_ids':unsupported,'source_truth_verified':False,'boundary':self.boundary}
