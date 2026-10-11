from app.modules.m20_general_cognitive_worker import attorney_client_privilege1293 as m

def test_row_identity_and_vocabulary():
 out=m.run({'row':1293,'as_of':'2026-10-12','entries':[{'element':x,'status':'supplied','source_ref':'private-ref'} for x in ['communication', 'participants', 'purpose', 'confidentiality', 'waiver', 'exceptions']]})
 assert out['row']==1293 and out['coverage']['referenced']==6
 assert [x['element'] for x in out['elements']]==['communication', 'participants', 'purpose', 'confidentiality', 'waiver', 'exceptions']
 assert out['legal_conclusion'] is False and out['references_verified'] is False
 assert 'private-ref' not in str(out)
