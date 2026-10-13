"""Finite conjunctive concept induction with negative and boundary-case checks.

Conjunction hypotheses use observed positive attributes. This is an explicit
symbolic learner, not natural-language concept discovery or truth verification.
"""
import itertools


def induce(inputs):
    positives=inputs.get('examples');negatives=inputs.get('non_examples');queries=inputs.get('boundary_cases',[])
    if not isinstance(positives,list) or not 1<=len(positives)<=100 or not isinstance(negatives,list) or len(negatives)>100:
        raise ValueError('bounded positive and negative example lists required')
    if not isinstance(queries,list) or len(queries)>100:raise ValueError('bounded boundary cases required')
    seen=set()
    def parse(row):
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id'] or row['id']in seen:
            raise ValueError('unique nonempty example IDs required')
        seen.add(row['id']);values=row.get('attributes')
        if not isinstance(values,list) or len(values)>32 or any(not isinstance(v,str) or not v or len(v)>200 for v in values):
            raise ValueError('bounded explicit attribute labels required')
        if len(set(values))!=len(values):raise ValueError('duplicate attributes rejected')
        return set(values)
    positive_sets=[parse(row)for row in positives];negative_sets=[parse(row)for row in negatives];query_sets=[parse(row)for row in queries]
    common=set.intersection(*positive_sets)
    if len(common)>16:raise ValueError('hypothesis attribute count exceeds16')
    attributes=sorted(common);hypotheses=[];tested=0
    # Shortest consistent conjunctions are minimal in this finite hypothesis
    # language. Stop after first consistent cardinality, retain all tied rules.
    for size in range(len(attributes)+1):
        for candidate in itertools.combinations(attributes,size):
            tested+=1;rule=set(candidate)
            if all(not rule<=negative for negative in negative_sets):hypotheses.append(list(candidate))
        if hypotheses:break
    predictions=[]
    for row,values in zip(queries,query_sets):
        votes=[set(rule)<=values for rule in hypotheses]
        verdict=None if not votes or any(v!=votes[0]for v in votes) else votes[0]
        predictions.append({'id':row['id'],'classification':verdict,'hypothesis_votes':votes,
                            'reason':'no_consistent_hypothesis'if not votes else 'disagreement'if verdict is None else 'all_minimal_hypotheses_agree'})
    return {'kind':'minimal_consistent_symbolic_conjunctions','status':'consistent_hypotheses'if hypotheses else 'no_consistent_conjunction',
            'hypotheses':hypotheses,'hypotheses_tested':tested,'common_positive_attributes':attributes,
            'boundary_cases':predictions,'positive_count':len(positives),'negative_count':len(negatives),
            'real_world_category_verified':False,'general_concept_learning':False,
            'limits':'Finite conjunctions of supplied attributes only. Contradictory labels remain unresolved. Unanimity over minimal hypotheses is not calibrated certainty.'}
