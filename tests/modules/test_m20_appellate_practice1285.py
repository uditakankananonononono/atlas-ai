from app.modules.m20_general_cognitive_worker import appellate_practice1285 as m

def test_row_identity_and_vocabulary():
 out=m.run({'row':1285,'as_of':'2026-10-12','entries':[{'element':x,'status':'supplied','source_ref':'private-ref'} for x in ['appealability', 'preservation', 'record_cites', 'review_standard', 'requested_relief']]})
 assert out['row']==1285 and out['coverage']['referenced']==5
 assert [x['element'] for x in out['elements']]==['appealability', 'preservation', 'record_cites', 'review_standard', 'requested_relief']
 assert out['legal_conclusion'] is False and out['references_verified'] is False
 assert 'private-ref' not in str(out)
