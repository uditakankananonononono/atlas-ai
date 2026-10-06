from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,capabilities


def test_static_scientific_template_never_claims_executed_thinking():
 p={'source':{'title':'label','url':'https://example.org'},'problem':'x','question':'x','hypothesis':'y','evidence':['unverified']}
 r=execute('scientific_thinking',p)
 assert r['evaluation']['status']=='planning_scaffold_only'
 assert not r['evaluation']['capability_executed'] and 'not executed' in r['boundary']
 assert r['evaluation']['input_completeness']==1


def test_adding_nonempty_junk_fields_does_not_upgrade_scaffold():
 p={'source':{'title':'label','url':'https://example.org'},'objective':'learn'}
 a=execute('self_explanation',p);b=execute('self_explanation',{**p,**{'junk'+str(i):'nonempty' for i in range(100)}})
 assert a['evaluation']['status']==b['evaluation']['status']=='planning_scaffold_only'
 assert not b['evaluation']['capability_executed']


def test_catalog_distinguishes_real_restricted_computation_from_scaffold():
 catalog={c['row_id']:c for c in capabilities()}
 assert catalog[853]['execution_kind']=='restricted_computation'
 assert catalog[859]['execution_kind']=='planning_scaffold'
