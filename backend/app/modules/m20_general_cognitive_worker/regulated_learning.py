"""Evidence-linked descriptive recommendation with explicit learner choice."""
from copy import deepcopy
from .calibration_predictor import text,number
from .learning_calibration import calibrate_attempts

def cycle(p):
    goal=p.get('learning_goal');catalog=p.get('strategy_catalog')
    if not isinstance(goal,dict):raise ValueError('learning_goal object required')
    goal={key:text(goal.get(key),key)for key in ('goal_id','metric','source')}|{'target':number(goal.get('target'),'goal target')}
    if goal['metric']!='task_success_rate' or not 0<=goal['target']<=1:raise ValueError('task_success_rate metric and target[0,1] required')
    if not isinstance(catalog,list)or not 1<=len(catalog)<=32:raise ValueError('strategy_catalog requires1..32 entries')
    strategies={}
    for row in catalog:
        if not isinstance(row,dict):raise ValueError('strategy object required')
        row={key:text(row.get(key),key)for key in ('strategy','next_action','source')}
        if row['strategy']in strategies:raise ValueError('duplicate strategy')
        strategies[row['strategy']]=row
    output={'status':'abstained','reason':None,'goal':goal,'recommended_strategy':None,'recommended_action':None,'selected_next_action':None,'learner_choice':None,'choice_matches_recommendation':None,'learner_approval_required':True,'action_executed':False,'source_truth_verified':False,'learning_improvement':None,'boundary':'Descriptive Brier-based recommendation on supplied scored attempts and reflection, with explicit learner choice. No causal effectiveness, autonomous choice, execution or inferred mastery.'}
    attempts=p.get('attempts',[])
    if not isinstance(attempts,list)or len(attempts)>1000:raise ValueError('attempts requires0..1000 records')
    if not attempts:return {**output,'reason':'missing_attempt_evidence'}
    calibration=calibrate_attempts(attempts)
    if any(row['strategy']not in strategies for row in calibration['observations']):raise ValueError('unknown attempt strategy')
    reflection=p.get('reflection')
    if reflection is None:return {**output,'reason':'missing_reflection'}
    if not isinstance(reflection,dict):raise ValueError('reflection object required')
    observation=text(reflection.get('observation'),'reflection observation');source=text(reflection.get('source'),'reflection source');ids=reflection.get('evidence_ids')
    if not isinstance(ids,list)or not 1<=len(ids)<=1000:raise ValueError('reflection evidence IDs required')
    for key in ids:text(key,'reflection evidence ID')
    if len(set(ids))!=len(ids)or not set(ids)<={row['evidence_id']for row in calibration['observations']}:raise ValueError('unique known reflection evidence IDs required')
    # Reflect on exactly the scored evidence used, so a winner cannot silently be
    # selected using unacknowledged observations from another reflection scope.
    if set(ids)!={row['evidence_id']for row in calibration['observations']}:raise ValueError('reflection must cover all scored attempt evidence')
    recommended=calibration['recommended_strategy'];success=sum(row['succeeded']for row in calibration['observations'])/len(attempts)
    output.update(calibration=calibration,reflection_evidence_ids=sorted(ids),reflection={'observation':observation,'source':source},observed_goal_metric=success,goal_met_on_observed_attempts=success>=goal['target'],recommended_strategy=recommended,recommended_action=None if recommended is None else strategies[recommended]['next_action'],best_observed_strategies=calibration['best_observed_strategies'])
    choice=p.get('learner_choice')
    if choice is None:return {**output,'status':'awaiting_learner_choice','reason':'no_learner_choice'}
    if not isinstance(choice,dict):raise ValueError('learner_choice object required')
    choice={key:text(choice.get(key),key)for key in ('strategy','reason','source')}
    if choice['strategy']not in strategies:raise ValueError('unknown learner choice strategy')
    return {**output,'status':'recommendation_ready','reason':None,'learner_choice':deepcopy(choice),'selected_next_action':strategies[choice['strategy']]['next_action'],'choice_matches_recommendation':None if recommended is None else choice['strategy']==recommended}
