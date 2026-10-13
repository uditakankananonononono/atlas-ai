"""One tabular softmax REINFORCE step on supplied action/advantage samples."""
import math


def update(logits,samples,learning_rate):
    if type(logits) is not list or not 2<=len(logits)<=20:raise ValueError('2..20 action logits before scan')
    for value in logits:
        if type(value) not in (int,float) or not -100<=value<=100 or not math.isfinite(value):raise ValueError('strict finite logits within -100..100')
    if type(learning_rate) not in (int,float) or not 0<learning_rate<=1 or not math.isfinite(learning_rate):
        raise ValueError('strict finite learning rate inside zero through one')
    if type(samples) is not list or not 1<=len(samples)<=1000:raise ValueError('1..1000 action samples before scan')
    for sample in samples:
        if type(sample) is not dict or len(sample)!=2 or set(sample)!={'action','advantage'}:raise ValueError('exact action/advantage fields')
        if type(sample['action']) is not int or not 0<=sample['action']<len(logits):raise ValueError('strict action index in policy')
        value=sample['advantage']
        if type(value) not in (int,float) or not -1000<=value<=1000 or not math.isfinite(value):raise ValueError('strict finite advantage within -1000..1000')
    def probabilities(values):
        peak=max(values);masses=[math.exp(x-peak) for x in values];total=sum(masses)
        return [x/total for x in masses]
    p=probabilities(logits)
    gradient=[sum(s['advantage']*((1 if s['action']==j else 0)-p[j]) for s in samples)/len(samples) for j in range(len(logits))]
    new=[x+learning_rate*g for x,g in zip(logits,gradient)]
    # Log softmax directly, avoiding log(underflowed probability).
    def objective(values):
        peak=max(values);log_z=peak+math.log(sum(math.exp(x-peak) for x in values))
        return sum(s['advantage']*(values[s['action']]-log_z) for s in samples)/len(samples)
    return {'old_probabilities':p,'gradient':gradient,'updated_logits':new,'new_probabilities':probabilities(new),
            'sample_surrogate_before':objective(logits),'sample_surrogate_after':objective(new),
            'units':'advantages in caller reward units; logits dimensionless; learning rate inverse reward units',
            'environment_return_improvement_verified':False,'on_policy_sampling_verified':False,
            'environment_execution_performed':False,'external_effects':[],
            'assumptions':['samples drawn from old policy; not verified','advantages supplied and held fixed for one gradient step',
                           'one state-independent categorical policy; no clipping, baseline fit or entropy bonus']}
