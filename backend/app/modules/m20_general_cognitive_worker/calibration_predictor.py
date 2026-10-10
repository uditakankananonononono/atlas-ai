"""Class-conditional fixed-bin calibration from resolved supplied provenance."""
from copy import deepcopy
import math,threading

def number(value,label):
    if type(value)not in(int,float)or not math.isfinite(value):raise ValueError(f'{label} requires finite number')
    return value
def text(value,label):
    if not isinstance(value,str)or not value.strip()or len(value)>240:raise ValueError(f'{label} requires bounded nonempty string')
    return value

class CalibrationPredictor:
    kind='calibration_predictor'
    def __init__(self,repo):self.repo=repo;self.tenant_id=repo.tenant_id;self.records={};self._revision=0;self._lock=threading.RLock()
    @classmethod
    def load(cls,repo):
        obj=cls(repo);obj._revision,payload=repo.read(cls.kind)
        if payload is not None:obj.records=payload
        return obj
    def ingest(self,records):
        if not isinstance(records,list)or not 1<=len(records)<=1000:raise ValueError('records require1..1000 resolved predictions')
        normalized=[]
        for r in records:
            if not isinstance(r,dict):raise ValueError('prediction object required')
            values={k:text(r.get(k),k)for k in ('prediction_id','claim_class','prediction_source','outcome_source')}
            confidence=number(r.get('confidence'),'confidence');predicted=number(r.get('predicted_at'),'predicted_at');resolved=number(r.get('resolved_at'),'resolved_at')
            if not 0<=confidence<=1 or type(r.get('outcome'))is not bool or resolved<=predicted:raise ValueError('resolved boolean outcome after prediction and confidence[0,1] required')
            normalized.append({**values,'confidence':confidence,'outcome':r['outcome'],'predicted_at':predicted,'resolved_at':resolved})
        with self._lock:
            staged=deepcopy(self.records);inserted=0
            for r in normalized:
                ident=r['prediction_id']
                if ident in staged:
                    if staged[ident]!=r:raise ValueError('prediction identity reused with changed provenance/outcome')
                else:staged[ident]=r;inserted+=1
            if len(staged)>2000:raise ValueError('record limit2000')
            if inserted:
                revision=self.repo.write(self.kind,self._revision,staged);self.records=staged;self._revision=revision
            return {'inserted':inserted,'total':len(self.records),'status':'resolved_provenance_records_stored','boundary':'Caller-bound provenance/labels, not independent truth verification.'}
    def predict(self,claim_class,confidence,*,as_of):
        text(claim_class,'claim_class');number(confidence,'confidence');number(as_of,'as_of')
        if not 0<=confidence<=1:raise ValueError('confidence[0,1] required')
        abstain={'status':'abstained','corrected_confidence':None,'training_prediction_ids':[],
                 'boundary':'Unsupported class/confidence support/time window or sparse bin; no inferred knowledge boundary.'}
        with self._lock:
            rows=[r for _,r in sorted(self.records.items())if r['claim_class']==claim_class and as_of-30<=r['resolved_at']<=as_of and r['predicted_at']<r['resolved_at']]
            if not rows or not min(r['confidence']for r in rows)<=confidence<=max(r['confidence']for r in rows):return abstain
            index=min(4,int(confidence*5));selected=[r for r in rows if min(4,int(r['confidence']*5))==index]
            if len(selected)<20:return abstain
            successes=sum(r['outcome']for r in selected);corrected=(successes+1)/(len(selected)+2)
            return {'status':'calibrated','corrected_confidence':corrected,'raw_confidence':confidence,
                    'claim_class':claim_class,'bin_index':index,'sample_size':len(selected),'successes':successes,
                    'training_prediction_ids':[r['prediction_id']for r in selected],
                    'training_provenance':[{'prediction_source':r['prediction_source'],'outcome_source':r['outcome_source']}for r in selected],
                    'window_start':as_of-30,'window_end':as_of,'estimator':'Beta(1,1) binomial posterior mean within fixed confidence bin',
                    'source_truth_verified':False,'boundary':'Validated synthetic claim-class bin calibration only, conditional on supplied labels/exchangeability/window; not introspective certainty or all future claims.'}
