"""Relative one-state softmax-bandit rewards inferred from action counts.

Identifiability convention fixes first action reward to zero. This is not general
sequential inverse RL or evidence of the demonstrator's actual intent.
"""
import math
from fractions import Fraction


def infer(counts,temperature,pseudocount):
    if type(counts) is not list or not 2<=len(counts)<=20:raise ValueError('2..20 action counts before scan')
    for count in counts:
        if type(count) is not int or not 0<=count<=1000000:raise ValueError('strict integer action count 0..1000000')
    if not sum(counts):raise ValueError('at least one demonstrated action')
    if type(temperature) not in (int,float) or not .000001<=temperature<=1000 or not math.isfinite(temperature):
        raise ValueError('strict finite temperature 1e-6..1000')
    if type(pseudocount) not in (int,float) or not .000001<=pseudocount<=1000 or not math.isfinite(pseudocount):
        raise ValueError('strict finite pseudocount 1e-6..1000')
    prior=Fraction(str(pseudocount));masses=[Fraction(c)+prior for c in counts];total=sum(masses)
    probabilities=[v/total for v in masses]
    rewards=[temperature*math.log(float(v/masses[0])) for v in masses]
    peak=max(rewards);exp=[math.exp((v-peak)/temperature) for v in rewards];z=sum(exp)
    return {'relative_rewards':rewards,'smoothed_probabilities_fraction':[str(p) for p in probabilities],
            'reconstructed_action_probabilities':[v/z for v in exp],
            'reference_action':0,'reference_reward':0,'temperature':temperature,'pseudocount':pseudocount,
            'units':'relative rewards in supplied temperature units; natural-log count ratios',
            'true_objective_identified':False,'sequential_dynamics_modeled':False,
            'demonstration_provenance_verified':False,'external_effects':[],
            'assumptions':['one-state immediate-reward bandit','stationary softmax choice at supplied positive temperature',
                           'positive symmetric pseudocount smoothing','reward offset fixed; reward scale depends on temperature']}
