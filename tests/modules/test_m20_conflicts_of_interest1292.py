from app.modules.m20_general_cognitive_worker import conflicts_of_interest1292 as m

def test_row_identity_and_vocabulary():
 out=m.run({'row':1292,'as_of':'2026-10-12','entries':[{'element':x,'status':'supplied','source_ref':'private-ref'} for x in ['clients', 'former_clients', 'adverse_parties', 'matters', 'consent_questions']]})
 assert out['row']==1292 and out['coverage']['referenced']==5
 assert [x['element'] for x in out['elements']]==['clients', 'former_clients', 'adverse_parties', 'matters', 'consent_questions']
 assert out['legal_conclusion'] is False and out['references_verified'] is False
 assert 'private-ref' not in str(out)
