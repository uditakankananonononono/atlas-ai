from app.modules.m20_general_cognitive_worker import legal_ethics1290 as m

def test_row_identity_and_vocabulary():
 out=m.run({'row':1290,'as_of':'2026-10-12','entries':[{'element':x,'status':'supplied','source_ref':'private-ref'} for x in ['actor', 'role', 'duty', 'rule_source', 'facts', 'ethics_review']]})
 assert out['row']==1290 and out['coverage']['referenced']==6
 assert [x['element'] for x in out['elements']]==['actor', 'role', 'duty', 'rule_source', 'facts', 'ethics_review']
 assert out['legal_conclusion'] is False and out['references_verified'] is False
 assert 'private-ref' not in str(out)
