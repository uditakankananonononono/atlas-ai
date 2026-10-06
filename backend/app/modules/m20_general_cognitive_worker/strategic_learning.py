"""Sequential full-information learning and actual finite zero-sum iterations.

Game trajectories are computed best-response iterations for an explicit payoff
matrix, not invented external interactions or evidence of real-world success.
"""
from __future__ import annotations
import numpy as np
from .conic_solvers import finite
from .learning_optimization import observed_records


def hedge(p):
    rows=observed_records(p);rate=float(p.get('learning_rate',.5))
    if not np.isfinite(rate) or rate<=0:raise ValueError('positive finite learning rate required')
    totals=None;loss=0.;history=[]
    for row in rows:
        costs=finite(row['expert_losses'],'expert_losses',1)
        if np.any(costs<0) or np.any(costs>1):raise ValueError('expert losses must lie in [0,1]')
        if totals is None:totals=np.zeros(costs.size)
        if costs.shape!=totals.shape:raise ValueError('expert dimensions must remain constant')
        logits=-rate*totals;weights=np.exp(logits-logits.max());weights/=weights.sum()
        round_loss=float(weights@costs);loss+=round_loss;totals+=costs
        history.append({'evidence_id':row['evidence_id'],'weights_before_observation':weights.tolist(),'mixture_loss':round_loss,'cumulative_loss':loss,'best_fixed_expert_loss':float(totals.min())})
    logits=-rate*totals;final=np.exp(logits-logits.max());final/=final.sum()
    return {'normalized_weights':final.tolist(),'cumulative_loss':loss,'best_fixed_expert_loss':float(totals.min()),
            'cumulative_regret':float(loss-totals.min()),'average_regret':float((loss-totals.min())/len(rows)),
            'expert_totals':totals.tolist(),'history':history,
            'uncertainty':{'solver_executed':True,'scope':'sequential Hedge full-information bounded losses; pre-observation weights; mixture expected loss not an invented realized action reward'}}


def regret_matching(p):
    rows=observed_records(p);regrets=None;total=0.;action_totals=None;history=[]
    for row in rows:
        payoffs=finite(row['action_payoffs'],'action_payoffs',1)
        if np.any(payoffs<0) or np.any(payoffs>1):raise ValueError('action payoffs must lie in [0,1]')
        if regrets is None:regrets=np.zeros(payoffs.size);action_totals=np.zeros(payoffs.size)
        if payoffs.shape!=regrets.shape:raise ValueError('action dimensions must remain constant')
        positive=np.maximum(regrets,0);probabilities=positive/positive.sum() if positive.sum()>0 else np.ones(payoffs.size)/payoffs.size
        expected=float(probabilities@payoffs);total+=expected;action_totals+=payoffs
        regrets+=payoffs-expected
        history.append({'evidence_id':row['evidence_id'],'policy_before_observation':probabilities.tolist(),'expected_payoff':expected,'regrets_after_observation':regrets.tolist()})
    positive=np.maximum(regrets,0);final=positive/positive.sum() if positive.sum()>0 else np.ones(regrets.size)/regrets.size
    external=float(action_totals.max()-total)
    return {'action_probabilities':final.tolist(),'cumulative_regret':external,'average_regret':external/len(rows),
            'expected_cumulative_payoff':total,'action_totals':action_totals.tolist(),'history':history,
            'uncertainty':{'solver_executed':True,'scope':'full-information regret matching for finite bounded action payoffs; mixture expectations, no claimed empirical performance'}}


def game_problem(p):
    M=finite(p['payoff_matrix'],'payoff_matrix',2);limit=p.get('max_iterations',10000);tol=float(p.get('tolerance',1e-3))
    if type(limit) is not int or not 1<=limit<=100000 or not np.isfinite(tol) or tol<=0:raise ValueError('invalid finite game controls')
    return M,limit,tol


def game_result(M,row,col,history,algorithm,tol):
    lower=float(np.min(row@M));upper=float(np.max(M@col));gap=max(0.,upper-lower)
    return {'row_strategy':row.tolist(),'column_strategy':col.tolist(),'equilibrium_gap':gap,'exploitability':gap,
            'lower_value':lower,'upper_value':upper,'iterations':len(history),'converged':gap<=tol,
            'status':'converged' if gap<=tol else 'iteration_limit','history':history,
            'uncertainty':{'solver_executed':True,'scope':algorithm+' for finite two-player zero-sum payoff matrix; computed strategy iteration, not real-world experiment or general-sum equilibrium claim'}}


def fictitious_play(p):
    M,limit,tol=game_problem(p)
    row_counts=np.zeros(M.shape[0]);column_counts=np.zeros(M.shape[1]);history=[]
    for iteration in range(1,limit+1):
        row=row_counts/row_counts.sum() if row_counts.sum() else np.ones(M.shape[0])/M.shape[0]
        col=column_counts/column_counts.sum() if column_counts.sum() else np.ones(M.shape[1])/M.shape[1]
        i=int(np.argmax(M@col));j=int(np.argmin(row@M))
        row_counts[i]+=1;column_counts[j]+=1
        row=row_counts/iteration;col=column_counts/iteration
        gap=float(np.max(M@col)-np.min(row@M))
        history.append({'iteration':iteration,'row_best_response':i,'column_best_response':j,'equilibrium_gap':gap})
        if gap<=tol:break
    return game_result(M,row,col,history,'simultaneous fictitious play',tol)


def game_regret_matching(p):
    M,limit,tol=game_problem(p);row_regret=np.zeros(M.shape[0]);col_regret=np.zeros(M.shape[1]);row_sum=row_regret.copy();col_sum=col_regret.copy();history=[]
    def policy(regret):
        positive=np.maximum(regret,0)
        return positive/positive.sum() if positive.sum()>0 else np.ones(regret.size)/regret.size
    for iteration in range(1,limit+1):
        row=policy(row_regret);col=policy(col_regret);value=float(row@M@col)
        row_regret+=M@col-value;col_regret+=value-row@M
        row_sum+=row;col_sum+=col
        avg_row=row_sum/iteration;avg_col=col_sum/iteration
        gap=float(np.max(M@avg_col)-np.min(avg_row@M))
        history.append({'iteration':iteration,'equilibrium_gap':gap})
        if gap<=tol:break
    return game_result(M,avg_row,avg_col,history,'two-sided regret matching average strategies',tol)
