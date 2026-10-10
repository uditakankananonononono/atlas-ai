"""Tenant-bound in-memory scalar linear Kalman twin, caller observations only."""
from copy import deepcopy
import math,threading

def finite(value,name):
    if type(value)not in(int,float)or not math.isfinite(value):raise ValueError(f'{name} requires finite number')
    return value

class TwinRegistry:
    def __init__(self,tenant_id):
        if not isinstance(tenant_id,str)or not tenant_id.strip():raise ValueError('tenant required')
        self.tenant_id=tenant_id;self._models={};self._lock=threading.RLock()
    def names(self):
        with self._lock:return sorted(self._models)
    def create(self,name,*,state,variance,timestamp,transition=1.,control_gain=1.,process_noise=.1,measurement_noise=1.):
        with self._lock:
            if not isinstance(name,str)or not name.strip()or len(name)>120:raise ValueError('name requires nonempty <=120 characters')
            if name in self._models:raise ValueError('twin already exists')
            if len(self._models)>=128:raise ValueError('registry model limit128')
            values={k:finite(v,k)for k,v in dict(state=state,variance=variance,timestamp=timestamp,transition=transition,control_gain=control_gain,process_noise=process_noise,measurement_noise=measurement_noise).items()}
            if variance<0 or process_noise<0 or measurement_noise<=0:raise ValueError('variance/process_noise nonnegative, measurement_noise positive')
            model={'name':name,**values,'history':[],'source_truth_verified':False,'scope':'Caller-observed scalar linear twin; no live sensor, deployment, physical fidelity or real-world truth verification.'}
            self._models[name]=model;return deepcopy(model)
    def get(self,name):
        with self._lock:
            if name not in self._models:raise KeyError('twin not found')
            return deepcopy(self._models[name])
    def _prediction(self,model,timestamp,control):
        finite(timestamp,'timestamp');finite(control,'control')
        if timestamp<=model['timestamp']:raise ValueError('timestamp must strictly increase')
        dt=finite(timestamp-model['timestamp'],'elapsed time')
        try:
            state=finite(model['transition']*model['state']+model['control_gain']*control,'predicted state')
            variance=finite(model['transition']**2*model['variance']+model['process_noise']*dt,'predicted variance')
        except OverflowError as exc:raise ValueError('prediction overflow')from exc
        return state,variance
    def forecast(self,name,*,timestamp,control=0.):
        with self._lock:
            model=self.get(name);state,variance=self._prediction(model,timestamp,control)
            return {'name':name,'timestamp':timestamp,'state':state,'variance':variance,'committed':False,'source_truth_verified':False}
    def assimilate(self,name,*,timestamp,observation,control=0.):
        with self._lock:
            model=self.get(name);finite(observation,'observation')
            if len(model['history'])>=1000:raise ValueError('observation history limit1000')
            predicted,variance=self._prediction(model,timestamp,control)
            innovation=finite(observation-predicted,'innovation');denominator=finite(variance+model['measurement_noise'],'innovation variance')
            gain=variance/denominator;updated=finite(predicted+gain*innovation,'updated state')
            # Joseph scalar form avoids subtractive covariance cancellation.
            covariance=finite((1-gain)**2*variance+gain**2*model['measurement_noise'],'updated variance')
            if covariance<0:raise ValueError('negative updated variance')
            model['history'].append({'timestamp':timestamp,'control':control,'observation':observation,'predicted_state':predicted,'predicted_variance':variance,'innovation':innovation,'gain':gain,'state':updated,'variance':covariance})
            model.update(state=updated,variance=covariance,timestamp=timestamp);self._models[name]=model
            return deepcopy(model)
