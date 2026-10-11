from app.modules.m20_general_cognitive_worker import legal_writing1286 as m

def test_row_identity_and_vocabulary():
 out=m.run({'row':1286,'as_of':'2026-10-12','entries':[{'element':x,'status':'supplied','source_ref':'private-ref'} for x in ['question', 'short_answer_alternatives', 'facts', 'sourced_rules', 'analysis_gaps']]})
 assert out['row']==1286 and out['coverage']['referenced']==5
 assert [x['element'] for x in out['elements']]==['question', 'short_answer_alternatives', 'facts', 'sourced_rules', 'analysis_gaps']
 assert out['legal_conclusion'] is False and out['references_verified'] is False
 assert 'private-ref' not in str(out)
