from app.modules.m20_general_cognitive_worker.horn_inference import forward


def test_horn_query_proof_tree_reaches_supplied_premises():
    result=forward({'facts':['reviewed','budgeted'],'rules':[
        {'id':'r1','if':['reviewed'],'then':'ready'},
        {'id':'r2','if':['ready','budgeted'],'then':'launchable'}],'query_atoms':['launchable','unknown']})
    query=next(q for q in result['queries'] if q['atom']=='launchable')
    tree=query['proof_tree']
    assert tree['rule_id']=='r2'
    byatom={p['fact']:p for p in tree['premise_proofs']}
    assert byatom['budgeted']['source']=='supplied_fact'
    assert byatom['ready']['premise_proofs'][0]['fact']=='reviewed'
    assert byatom['ready']['premise_proofs'][0]['source']=='supplied_fact'
    assert next(q for q in result['queries'] if q['atom']=='unknown')['proof_tree'] is None


def test_horn_proof_tree_long_chain_truncates_without_recursion_error():
    result=forward({'facts':['f0'],'rules':[{'id':f'r{i}','if':[f'f{i}'],'then':f'f{i+1}'} for i in range(100)],'query_atoms':['f100']})
    tree=result['queries'][0]['proof_tree']
    depth=0
    while 'premise_proofs' in tree:
        depth+=1;tree=tree['premise_proofs'][0]
    assert depth==64 and tree['truncated'] is True
    assert tree['source']=='proof_reference'
