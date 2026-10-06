"""Feedback-driven finite bandit policies. Never invent rewards or claim training.

Logged actions may differ from recommendations: this is offline update replay,
not proof of on-policy performance. Reward provenance is caller supplied.
"""
from __future__ import annotations
import numpy as np
from .conic_solvers import finite


def feedback(p):
    arms=p.get('arms');rows=p.get('feedback',[])
    if not isinstance(arms,list) or not arms or any(not isinstance(a,str) or not a for a in arms) or len(set(arms))!=len(arms):raise ValueError('unique nonempty arm labels required')
    if not isinstance(rows,list):raise ValueError('feedback must be a list')
    seen=set()
    for row in rows:
        if not isinstance(row,dict) or row.get('arm') not in arms:raise ValueError('feedback must name a known arm')
        ident=row.get('evidence_id');reward=row.get('reward')
        if not isinstance(ident,str) or not ident or ident in seen:raise ValueError('feedback evidence ids must be nonempty and unique')
        if isinstance(reward,bool) or not isinstance(reward,(int,float)) or not np.isfinite(reward) or not 0<=reward<=1:raise ValueError('observed reward must be finite in [0,1]')
        seen.add(ident)
    return arms,rows


def summarize(arms,rows):
    counts=np.zeros(len(arms),dtype=int);sums=np.zeros(len(arms));history=[]
    for row in rows:
        j=arms.index(row['arm']);counts[j]+=1;sums[j]+=row['reward']
        history.append({'evidence_id':row['evidence_id'],'updated_arm':row['arm'],'count':int(counts[j]),'mean':float(sums[j]/counts[j])})
    means=np.divide(sums,counts,out=np.zeros_like(sums),where=counts>0)
    return counts,means,history


def epsilon_greedy(p):
    arms,rows=feedback(p);counts,means,history=summarize(arms,rows)
    epsilon=float(p.get('epsilon',.1))
    if not np.isfinite(epsilon) or not 0<=epsilon<=1:raise ValueError('epsilon must be in [0,1]')
    best=int(means.argmax()) if rows else None
    probabilities=np.full(len(arms),epsilon/len(arms)) if rows else np.full(len(arms),1/len(arms))
    if best is not None:probabilities[best]+=1-epsilon
    return {'arms':arms,'counts':counts.tolist(),'arm_means':means.tolist(),'action_probabilities':probabilities.tolist(),'greedy_arm':arms[best] if best is not None else None,'has_feedback':bool(rows),
            'history':history,'uncertainty':{'solver_executed':True,'scope':'epsilon-greedy reward policy from bounded observed arm feedback; probabilities only, not invented deployment rewards or guarantee'}}


def ucb(p):
    arms,rows=feedback(p);counts,means,history=summarize(arms,rows)
    untried=[a for a,n in zip(arms,counts) if n==0]
    scores=[None if n==0 else float(m+np.sqrt(2*np.log(max(2,len(rows)+1))/n)) for m,n in zip(means,counts)]
    selected=untried[0] if untried else arms[int(np.argmax(scores))]
    return {'arms':arms,'counts':counts.tolist(),'arm_means':means.tolist(),'ucb_scores':scores,'untried_arms':untried,'selected_arm':selected,
            'history':history,'uncertainty':{'solver_executed':True,'scope':'UCB1 finite bounded-reward policy; untried arms have priority, null score instead of non-JSON infinity; regret theorem needs stationary independent rewards'}}


def thompson(p):
    arms,rows=feedback(p)
    prior=np.asarray(p.get('beta_priors',[[1,1]]*len(arms)),dtype=float)
    if prior.shape!=(len(arms),2) or not np.isfinite(prior).all() or np.any(prior<=0):raise ValueError('positive finite beta priors per arm required')
    posterior=prior.copy();history=[]
    for row in rows:
        if row['reward'] not in (0,1):raise ValueError('Beta-Bernoulli Thompson sampling requires binary outcomes')
        j=arms.index(row['arm']);posterior[j,0]+=row['reward'];posterior[j,1]+=1-row['reward']
        history.append({'evidence_id':row['evidence_id'],'updated_arm':row['arm'],'posterior':posterior[j].tolist()})
    seed=p.get('seed')
    if seed is not None and (type(seed) is not int or seed<0):raise ValueError('seed must be nonnegative integer or absent')
    # Sampling is the policy itself, not random model weights or fake outcomes.
    samples=np.random.default_rng(seed).beta(posterior[:,0],posterior[:,1])
    return {'arms':arms,'beta_posterior':posterior.tolist(),'posterior_means':(posterior[:,0]/posterior.sum(axis=1)).tolist(),
            'posterior_samples':samples.tolist(),'selected_arm':arms[int(samples.argmax())],'history':history,
            'uncertainty':{'solver_executed':True,'scope':'actual Beta-Bernoulli posterior sampling policy; draws are uncertainty samples, not simulated rewards or a trained neural model'}}


def contextual_ucb(p):
    arms,rows=feedback(p);context=finite(p['context'],'context',1);n=context.size
    ridge=float(p.get('ridge',1));alpha=float(p.get('exploration',1))
    if not np.isfinite([ridge,alpha]).all() or ridge<=0 or alpha<0:raise ValueError('positive ridge and nonnegative exploration required')
    matrices=[ridge*np.eye(n) for a in arms];vectors=[np.zeros(n) for a in arms];history=[]
    for row in rows:
        x=finite(row['context'],'feedback context',1)
        if x.shape!=context.shape:raise ValueError('context dimensions differ')
        j=arms.index(row['arm']);before=float(np.linalg.solve(matrices[j],vectors[j])@x)
        matrices[j]+=np.outer(x,x);vectors[j]+=row['reward']*x
        history.append({'evidence_id':row['evidence_id'],'updated_arm':row['arm'],'prediction_before_update':before})
    means=[];scores=[];weights=[]
    for A,b in zip(matrices,vectors):
        theta=np.linalg.solve(A,b);prediction=float(theta@context);bonus=alpha*np.sqrt(context@np.linalg.solve(A,context))
        weights.append(theta.tolist());means.append(prediction);scores.append(float(prediction+bonus))
    return {'arms':arms,'learned_weights':weights,'context_score':scores,'predicted_rewards':means,'selected_arm':arms[int(np.argmax(scores))],
            'history':history,'uncertainty':{'solver_executed':True,'scope':'disjoint linear ridge LinUCB from observed contextual feedback; not causal off-policy evaluation or guaranteed reward prediction'}}
