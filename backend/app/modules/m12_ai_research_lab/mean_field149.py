"""Coordinate-ascent mean-field approximation to a supplied binary log joint.

Finite declared distributions only; nonconvex optimization has no global guarantee.
"""
import itertools
import math


def approximate(log_weights,initial,max_sweeps=100,tolerance=1e-9):
    if type(initial) is not list or not 1<=len(initial)<=8:
        raise ValueError('1..8 initial binary probabilities before scan')
    for p in initial:
        if type(p) not in (int,float) or not 0<p<1 or not math.isfinite(p):
            raise ValueError('strict finite initial probabilities inside zero and one')
    n=len(initial)
    if type(log_weights) is not list or len(log_weights)!=2**n:
        raise ValueError('exact binary log weight table size')
    for value in log_weights:
        if type(value) not in (int,float) or not -100<=value<=100 or not math.isfinite(value):
            raise ValueError('strict finite log weights within -100..100')
    if type(max_sweeps) is not int or not 1<=max_sweeps<=1000:
        raise ValueError('strict 1..1000 sweep cap')
    if type(tolerance) not in (int,float) or not 1e-12<=tolerance<=1 or not math.isfinite(tolerance):
        raise ValueError('strict finite tolerance within 1e-12..1')
    states=list(itertools.product((0,1),repeat=n));q=list(initial)
    peak=max(log_weights);log_z=peak+math.log(sum(math.exp(v-peak) for v in log_weights))
    def objective():
        expected=sum(weight*math.prod(q[j] if bit else 1-q[j] for j,bit in enumerate(state)) for state,weight in zip(states,log_weights))
        entropy=-sum(p*math.log(p)+(1-p)*math.log1p(-p) for p in q)
        return expected+entropy
    history=[objective()];converged=False
    for sweep in range(1,max_sweeps+1):
        before=list(q)
        for coordinate in range(n):
            delta=0.0
            for state,weight in zip(states,log_weights):
                others=math.prod(q[j] if bit else 1-q[j] for j,bit in enumerate(state) if j!=coordinate)
                delta+=(1 if state[coordinate] else -1)*weight*others
            # Stable sigmoid with a numerical interior clamp for entropy evaluation.
            p=1/(1+math.exp(-delta)) if delta>=0 else math.exp(delta)/(1+math.exp(delta))
            q[coordinate]=min(1-1e-15,max(1e-15,p))
        history.append(objective())
        if max(abs(a-b) for a,b in zip(q,before))<=tolerance:
            converged=True;break
    return {'binary_probabilities':q,'elbo':history[-1],'elbo_history':history,
            'log_normalizer':log_z,'reverse_kl':max(0.0,log_z-history[-1]),
            'sweeps':sweep,'converged_by_probability_change':converged,
            'state_order':'lexicographic binary tuples, last coordinate changes fastest',
            'units':'natural-log probability units (nats)',
            'global_optimum_verified':False,'supplied_joint_truth_verified':False,
            'posterior_model_execution_performed':False,'external_effects':[],
            'assumptions':['supplied log weights are unnormalized log joint at fixed evidence',
                           'independent Bernoulli factors approximate correlated posterior',
                           'probabilities clamped to [1e-15,1-1e-15] for float entropy stability']}
