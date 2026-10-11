from app.modules.m20_general_cognitive_worker import oral_argument1289 as m

def test_row_identity_and_vocabulary():
 out=m.run({'row':1289,'as_of':'2026-10-12','entries':[{'element':x,'status':'supplied','source_ref':'private-ref'} for x in ['likely_questions', 'record_cites', 'authorities', 'concessions', 'unknowns']]})
 assert out['row']==1289 and out['coverage']['referenced']==5
 assert [x['element'] for x in out['elements']]==['likely_questions', 'record_cites', 'authorities', 'concessions', 'unknowns']
 assert out['legal_conclusion'] is False and out['references_verified'] is False
 assert 'private-ref' not in str(out)
