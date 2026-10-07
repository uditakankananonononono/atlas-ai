"""Validated finite positive Horn closure with recoverable derivation proofs."""
from __future__ import annotations
from .defeasible_reasoning import labels,rules,closure


def forward(p):
    facts=labels(p.get('facts',[]),'facts');program=rules(p.get('rules'))
    if len(facts)>1000 or len(program)>1000:raise ValueError('Horn inference supports <=1000 facts/rules')
    if any(rule['unless'] for rule in program):raise ValueError('positive Horn rules only; use default reasoning for unless')
    known,trace=closure(facts,program);by_rule={r['id']:r for r in program};proofs={f:{'fact':f,'source':'supplied_fact'} for f in facts}
    for event in trace:
        rule=by_rule[event['rule']]
        proofs[event['fact']]={'fact':event['fact'],'source':'derived','rule_id':rule['id'],'premises':sorted(rule['if'])}
    def proof_tree(atom):
        budget=[256]
        def expand(name, depth=0):
            proof=proofs.get(name)
            if proof is None:return None
            if depth>=64 or budget[0]<=0:
                return {'fact':name,'source':'proof_reference','truncated':True}
            budget[0]-=1
            result=dict(proof)
            if proof['source']=='derived':
                result['premise_proofs']=[expand(premise,depth+1) for premise in proof['premises']]
            return result
        return expand(atom)
    queries=labels(p.get('query_atoms',[]),'query_atoms')
    return {'proof_tree_limits':{'depth':64,'nodes_per_query':256},'facts':sorted(known),'rule_trace':trace,'proofs':proofs,
            'queries':[{'atom':q,'entailed':q in known,'proof':proofs.get(q),'proof_tree':proof_tree(q),'not_entailed_does_not_mean_false':q not in known} for q in sorted(queries)],
            'boundary':'Actual finite positive Horn least fixed point. Supplied facts/rules are premises, not independently verified real-world truth. Unsupported cycles derive nothing. No negation, natural-language rule extraction or closed-world falsehood claim.'}
