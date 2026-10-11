from app.modules.m20_general_cognitive_worker import witness_preparation1283 as m

def test_row_identity_and_vocabulary():
 out=m.run({'row':1283,'as_of':'2026-10-12','entries':[{'element':x,'status':'supplied','source_ref':'private-ref'} for x in ['firsthand_recollection', 'documents', 'uncertainty', 'prohibited_coaching']]})
 assert out['row']==1283 and out['coverage']['referenced']==4
 assert [x['element'] for x in out['elements']]==['firsthand_recollection', 'documents', 'uncertainty', 'prohibited_coaching']
 assert out['legal_conclusion'] is False and out['references_verified'] is False
 assert 'private-ref' not in str(out)
