"""Exact symbolic Horn explanation practice, not natural-language evaluation."""
from .defeasible_reasoning import closure
from .calibration_predictor import text

def atoms(value,label):
    if not isinstance(value,list)or len(value)>64:raise ValueError(label+' requires at most64 symbolic atoms')
    for atom in value:text(atom,label)
    if len(set(value))!=len(value):raise ValueError(label+' contains duplicate atoms')
    return set(value)

def practice(mode,p):
    target=text(p.get('explanation_target'),'explanation_target');fact_rows=p.get('explanation_facts');rule_rows=p.get('explanation_rules');attempts=p.get('explanation_attempts',[])
    if not isinstance(fact_rows,list)or len(fact_rows)>64:raise ValueError('explanation_facts requires0..64 provenance records')
    if not isinstance(rule_rows,list)or not 1<=len(rule_rows)<=64:raise ValueError('explanation_rules requires1..64 provenance records')
    if not isinstance(attempts,list)or len(attempts)>100:raise ValueError('explanation_attempts requires0..100 records')
    facts={};program=[];by_id={}
    for row in fact_rows:
        if not isinstance(row,dict):raise ValueError('fact object required')
        atom=text(row.get('atom'),'fact atom');source=text(row.get('source'),'fact source')
        if atom in facts:raise ValueError('duplicate fact atom')
        facts[atom]=source
    for row in rule_rows:
        if not isinstance(row,dict):raise ValueError('rule object required')
        key=text(row.get('id'),'rule id');conclusion=text(row.get('then'),'rule conclusion');premises=atoms(row.get('if'),'rule premises');source=text(row.get('source'),'rule source')
        if key in by_id or row.get('unless'):raise ValueError('unique positive Horn rules required')
        rule={'id':key,'if':premises,'then':conclusion,'unless':set(),'source':source};program.append(rule);by_id[key]=rule
    known,trace=closure(set(facts),program)
    # Retain only one canonical derivation's target-relevant ancestors, preserving
    # closure order. Alternative valid proofs remain accepted in attempts.
    first={event['fact']:by_id[event['rule']]for event in trace};needed=set()
    def visit(atom):
        if atom in facts or atom in needed:return
        needed.add(atom)
        if atom in first:
            for premise in first[atom]['if']:visit(premise)
    if target in known:visit(target)
    derivation=[{'rule_id':event['rule'],'conclusion':event['fact'],'premises':sorted(by_id[event['rule']]['if']),'source':by_id[event['rule']]['source']}for event in trace if event['fact']in needed]
    conditions=[{'removed_fact':atom,'target_still_entailed':target in closure(set(facts)-{atom},program)[0]}for atom in sorted(facts)]
    seen=set();results=[];previous=None
    for attempt in attempts:
        if not isinstance(attempt,dict):raise ValueError('attempt object required')
        evidence=text(attempt.get('evidence_id'),'evidence_id');source=text(attempt.get('source'),'attempt source');steps=attempt.get('steps')
        if evidence in seen:raise ValueError('duplicate attempt evidence')
        seen.add(evidence)
        if not isinstance(steps,list)or len(steps)>64:raise ValueError('attempt steps requires0..64 records')
        available=set(facts);feedback=[]
        for i,step in enumerate(steps):
            if not isinstance(step,dict):raise ValueError('step object required')
            key=text(step.get('rule_id'),'step rule_id');conclusion=text(step.get('conclusion'),'step conclusion');premises=atoms(step.get('premises'),'step premises');rule=by_id.get(key)
            missing=sorted(premises-available);rule_matches=rule is not None and rule['then']==conclusion and rule['if']==premises
            accepted=rule_matches and not missing
            if accepted:available.add(conclusion)
            feedback.append({'step_index':i,'rule_id':key,'accepted':accepted,'missing_premises':missing,'rule_matches':rule_matches,'expected_conclusion':None if rule is None else rule['then'],'expected_premises':None if rule is None else sorted(rule['if']),'rule_source':None if rule is None else rule['source']})
        reached=target in available;correct=target in known and reached and all(row['accepted']for row in feedback)
        results.append({'evidence_id':evidence,'source':source,'correct':correct,'target_reached':reached,'step_feedback':feedback,'retry_recommended':not correct,'improved_from_previous':previous is False and correct})
        previous=correct
    return {'status':'practice_ready'if target in known else 'target_not_entailed','target_entailed':target in known,'derived_atoms':sorted(known),'derivation':derivation,'condition_checks':conditions,'task':{'mode':mode,'target':target,'question':f'Which supplied rules and prerequisite facts justify {target}?','condition_question':f'Which supplied fact removals prevent deriving {target}?'},'fact_provenance':[{'atom':atom,'source':facts[atom]}for atom in sorted(facts)],'attempt_results':results,'source_truth_verified':False,'learner_understanding':None,'boundary':'Finite positive Horn structured explanation and counterfactual fact-deletion checks only; exact rule/premise/ordered-step validation, not free-text semantics or learner understanding. Source records are supplied premises, not verified truth.'}
