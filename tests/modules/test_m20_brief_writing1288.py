from app.modules.m20_general_cognitive_worker import brief_writing1288 as m

def test_row_identity_and_vocabulary():
 out=m.run({'row':1288,'as_of':'2026-10-12','entries':[{'element':x,'status':'supplied','source_ref':'private-ref'} for x in ['record_proposition', 'authority', 'counterauthority', 'analysis', 'requested_relief']]})
 assert out['row']==1288 and out['coverage']['referenced']==5
 assert [x['element'] for x in out['elements']]==['record_proposition', 'authority', 'counterauthority', 'analysis', 'requested_relief']
 assert out['legal_conclusion'] is False and out['references_verified'] is False
 assert 'private-ref' not in str(out)
