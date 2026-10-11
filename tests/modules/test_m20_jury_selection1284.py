from app.modules.m20_general_cognitive_worker import jury_selection1284 as m

def test_row_identity_and_vocabulary():
 out=m.run({'row':1284,'as_of':'2026-10-12','entries':[{'element':x,'status':'supplied','source_ref':'private-ref'} for x in ['case_neutral_topics', 'cause_grounds', 'equal_protection_review']]})
 assert out['row']==1284 and out['coverage']['referenced']==3
 assert [x['element'] for x in out['elements']]==['case_neutral_topics', 'cause_grounds', 'equal_protection_review']
 assert out['legal_conclusion'] is False and out['references_verified'] is False
 assert 'private-ref' not in str(out)
