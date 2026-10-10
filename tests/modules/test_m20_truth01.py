"""Truth correction pins, not acceptance of original cognitive capabilities."""
import json
from collections import Counter
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.cognitive_1960_2009 import run,ROWS,REFERENCE_SUBSTITUTES,capability_scope
from app.modules.m20_general_cognitive_worker.cognitive_routes_1960_2009 import router
ROOT=Path(__file__).resolve().parents[2]
EXPECTED={
 'graph_of_thought':'supplied_graph_shortest_path','self_consistency':'supplied_answer_plurality',
 'retrieval_augmented_generation':'supplied_vector_context_selection_only','vector_databases':'in_memory_supplied_vector_scan',
 'embeddings':'character_hash_vectors','semantic_search':'supplied_vector_cosine_ranking',
 'sentiment_analysis':'literal_lexicon_token_count','opinion_mining':'literal_lexicon_token_count',
 'neuro_symbolic_ai':'supplied_rule_weight_score_propagation','hybrid_ai':'supplied_rule_weight_score_propagation',
 'swarm_intelligence':'scalar_elite_gaussian_mutation','evolutionary_computation':'scalar_elite_gaussian_mutation','genetic_algorithms':'scalar_elite_gaussian_mutation',
 'genetic_programming':'supplied_polynomial_candidate_selection',
 **{m:'scalar_mean_coupling_toy_dynamics' for m in ('artificial_life','self_organization','emergence','adaptation','evolution','co_evolution','symbiosis','autopoiesis')},
 'digital_twins':'supplied_series_residual_diagnostics','systems_science':'supplied_graph_degree_diagnostics',
 'complexity_science':'supplied_graph_degree_diagnostics','second_order_cybernetics':'hand_written_gain_adjustment_simulation'}
def payload(m):
 if m=='graph_of_thought':return {'nodes':['a','b'],'edges':[['a','b',2]],'start':'a','goal':'b'}
 if m=='self_consistency':return {'answers':['a','a','b']}
 if m=='retrieval_augmented_generation':return {'query_embedding':[1,0],'documents':[{'id':'a','text':'supplied','embedding':[1,0]}]}
 if m=='vector_databases':return {'query':[1,0],'vectors':{'a':[1,0]}}
 if m=='embeddings':return {'tokens':['cat']}
 if m=='semantic_search':return {'query_embedding':[1,0],'items':[{'id':'a','embedding':[1,0]}]}
 if m in ('sentiment_analysis','opinion_mining'):return {'texts':['good bad great']}
 if m in ('neuro_symbolic_ai','hybrid_ai'):return {'probabilities':{'a':.8},'rules':[{'if':['a'],'then':'b'}]}
 if m in ('swarm_intelligence','evolutionary_computation','genetic_algorithms'):return {'population':[0,2],'target':1,'generations':2}
 if m=='genetic_programming':return {'candidate_coefficients':[[0,1]],'x':[1,2],'y':[1,2]}
 if m=='digital_twins':return {'observed':[1,2],'simulated':[1,1]}
 if m in ('systems_science','complexity_science'):return {'nodes':['a','b'],'edges':[['a','b']]}
 if m=='second_order_cybernetics':return {'target':1,'state':0}
 return {'state':[.1,.9],'steps':2}
def client():
 app=FastAPI();app.include_router(router);return TestClient(app)
@pytest.mark.parametrize('method',sorted(EXPECTED))
def test_catalog_analysis_and_ledger_scope_agree_without_certification(method):
 assert REFERENCE_SUBSTITUTES==EXPECTED
 c=client();catalog={x['method']:x for x in c.get('/cognitive-1960-2009/methods').json()}
 scope=capability_scope(method)
 assert scope=={'reference_operator':EXPECTED[method],'named_capability_executed':False,'status':'reference_substitute_only','original_capability_status':'unverified','verification_boundary':'Supplied-data reference operator only; not verification of the original named capability.'}
 for k,v in scope.items():assert catalog[method][k]==v
 response=c.post('/cognitive-1960-2009/analyze',json={'method':method,'data':payload(method)})
 assert response.status_code==200
 out=response.json()['output']
 for k,v in scope.items():assert out[k]==v
 row=next(x for x in json.loads((ROOT/'audits/additional-2000-features.json').read_text())['rows'] if x['id']==ROWS[method])
 assert row['status']=='PARTIAL' and row['reference_scope']['reference_operator']==EXPECTED[method]
 assert row['reference_scope']['original_capability_status']=='unverified' and row['reference_scope']['named_capability_executed'] is False
 assert EXPECTED[method] in row['boundary'] and 'remains unverified' in row['boundary']
 line=next(x for x in (ROOT/'docs/IMPLEMENTATION_AUDIT.md').read_text().splitlines() if x.startswith(f"| {ROWS[method]} |"))
 assert 'verified-practitioner-depth' not in line and 'PARTIAL-reference-substitute' in line and EXPECTED[method] in line
@pytest.mark.parametrize('method',sorted(EXPECTED))
def test_missing_inputs_and_nonfinite_inputs_refused(method):
 c=client()
 for data in ({},{**payload(method),'extra':float('nan')}):
  with pytest.raises((ValueError,TypeError,KeyError)):run(method,data)
 assert c.post('/cognitive-1960-2009/analyze',json={'method':method,'data':{}}).status_code==422
@pytest.mark.parametrize('method,data',[
 ('semantic_search',{'query_embedding':[1],'items':[]}),
 ('semantic_search',{'query_embedding':[1],'items':[{'id':'a','embedding':[True]}]}),
 ('retrieval_augmented_generation',{'query_embedding':[1],'documents':[{'id':'a','embedding':[1]}],'top_k':0}),
 ('embeddings',{'tokens':['cat'],'dimensions':1.5}),
 ('sentiment_analysis',{'texts':[]}),('opinion_mining',{'texts':[None]}),
 ('neuro_symbolic_ai',{'probabilities':{'a':2},'rules':[]}),
 ('hybrid_ai',{'probabilities':{'a':.8},'rules':[{'if':[],'then':'b'}]}),
 ('systems_science',{'nodes':['a'],'edges':[['a','z']]}),
 ('complexity_science',{'nodes':['a','a'],'edges':[]}),
 ('artificial_life',{'state':[.1,.2],'steps':-1}),
 ('swarm_intelligence',{'population':[1,2],'target':1,'mutation_sigma':-1}),
])
def test_invalid_substitute_input_is_422(method,data):
 assert client().post('/cognitive-1960-2009/analyze',json={'method':method,'data':data}).status_code==422

def test_pins_preserve_source_titles_and_historical_evidence():
 ledger=json.loads((ROOT/'audits/additional-2000-features.json').read_text());pins=json.loads((ROOT/'audits/m20-truth01-source-pins.json').read_text())
 assert len(pins['rows'])==26 and len(pins['audit_doc_before'])==26
 assert ledger['counts']==dict(Counter(r['status'] for r in ledger['rows']))
 rows={r['id']:r for r in ledger['rows']}
 for p in pins['rows']:
  old=p['ledger_row'];new=rows[old['id']]
  for k in ('requirement','description','status','evidence'):assert new[k]==old[k]
  assert old['description']=='' and p['description_present'] is False
  assert p['source_number']==old['id']-9
 assert len([m for m in ROWS if m not in EXPECTED])==24
 for m in ROWS.keys()-EXPECTED.keys():assert capability_scope(m)=={}

def test_reference_arithmetic_does_not_promote_original_capability():
 out=run('graph_of_thought',payload('graph_of_thought'))['output']
 assert out['cost']==2 and out['best_path']==['a','b']
 assert out['original_capability_status']=='unverified' and out['named_capability_executed'] is False
 assert run('self_consistency',payload('self_consistency'))['output']['vote_share']==pytest.approx(2/3)

@pytest.mark.parametrize('method,data',[
 ('genetic_programming',{'candidate_coefficients':[[True]],'x':[1],'y':[1]}),
 ('genetic_programming',{'candidate_coefficients':[[]],'x':[1],'y':[1]}),
 ('graph_of_thought',{'nodes':['a','b'],'edges':[['a','b',True]],'start':'a','goal':'b'}),
])
def test_invalid_numeric_candidates_are_not_success(method,data):
 assert client().post('/cognitive-1960-2009/analyze',json={'method':method,'data':data}).status_code==422

REQUIRED={
 'graph_of_thought':('nodes','edges','start','goal'),
 'self_consistency':('answers',),
 'retrieval_augmented_generation':('query_embedding','documents'),
 'vector_databases':('query','vectors'),
 'embeddings':('tokens',),'semantic_search':('query_embedding','items'),
 'sentiment_analysis':('texts',),'opinion_mining':('texts',),
 'neuro_symbolic_ai':('probabilities','rules'),'hybrid_ai':('probabilities','rules'),
 'genetic_programming':('candidate_coefficients','x','y'),
 'digital_twins':('observed','simulated'),
 'systems_science':('nodes','edges'),'complexity_science':('nodes','edges'),
 'second_order_cybernetics':('target','state'),
 **{m:('population','target') for m in ('swarm_intelligence','evolutionary_computation','genetic_algorithms')},
 **{m:('state',) for m in ('artificial_life','self_organization','emergence','adaptation','evolution','co_evolution','symbiosis','autopoiesis')},
}
@pytest.mark.parametrize('method,key',[(m,k) for m,keys in REQUIRED.items() for k in keys])
@pytest.mark.parametrize('missing_value',['absent','null'])
def test_exact_missing_required_guard_per_method(method,key,missing_value):
 data=payload(method)
 if missing_value=='absent':data.pop(key)
 else:data[key]=None
 with pytest.raises(ValueError) as caught:run(method,data)
 assert str(caught.value)==f'{key} required'

@pytest.mark.parametrize('method',['semantic_search','retrieval_augmented_generation'])
def test_duplicate_item_id_exact_guard(method):
 data=payload(method);key='items' if method=='semantic_search' else 'documents'
 data[key].append(dict(data[key][0]))
 with pytest.raises(ValueError) as caught:run(method,data)
 assert str(caught.value)=='duplicate item id'

@pytest.mark.parametrize('method',['neuro_symbolic_ai','hybrid_ai'])
@pytest.mark.parametrize('threshold',[-.01,1.01])
def test_threshold_range_exact_guard(method,threshold):
 data=payload(method);data['threshold']=threshold
 with pytest.raises(ValueError) as caught:run(method,data)
 assert str(caught.value)=='threshold must be in [0,1]'

@pytest.mark.parametrize('method',sorted(EXPECTED))
@pytest.mark.parametrize('data',[None,[],1,'text'])
def test_nondict_direct_run_exact_guard(method,data):
 with pytest.raises(ValueError) as caught:run(method,data)
 assert str(caught.value)=='data must be an object'

@pytest.mark.parametrize('method',['neuro_symbolic_ai','hybrid_ai'])
@pytest.mark.parametrize('conclusion',[None,'',1,False])
def test_rule_conclusion_exact_guard(method,conclusion):
 data=payload(method);data['rules'][0]['then']=conclusion
 with pytest.raises(ValueError) as caught:run(method,data)
 assert str(caught.value)=='rules require known antecedents and a conclusion'

@pytest.mark.parametrize('method,key',[('embeddings','dimensions'),('retrieval_augmented_generation','top_k'),('swarm_intelligence','generations'),('artificial_life','steps')])
@pytest.mark.parametrize('value',[0,10001])
def test_integer_guard_exact_edges(method,key,value):
 data=payload(method);data[key]=value
 with pytest.raises(ValueError) as caught:run(method,data)
 assert str(caught.value)==f'{key} must be an integer in [1,10000]'

@pytest.mark.parametrize('method',sorted(EXPECTED))
def test_general_reference_limit_retained(method):
 assert 'Reference-scale, deterministic decision support on supplied data; no external retrieval, execution, or claim of human cognition.' in run(method,payload(method))['output']['method_limits']
