"""Structured symbolic representation and example validation only."""
from copy import deepcopy
import pytest
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,LearningReasoningError
SRC={'title':'Synthetic concepts','url':'https://example.org/concepts'}
def pack():return {'source':SRC,'objective':'Represent shape concepts','concepts':[{'concept_id':'triangle','invariants':{'sides':'three','closed':'yes'},'source':'fixture:definition'}],'verbal_propositions':[{'id':'v','concept_id':'triangle','features':{'sides':'three','closed':'yes'},'text':'A closed three-sided shape','source':'fixture:verbal'}],'visual_elements':[{'id':'img','concept_id':'triangle','features':{'sides':'three','closed':'yes'},'alt_text':'A closed triangle','source':'fixture:visual'}],'representation_mappings':[{'verbal_id':'v','visual_id':'img','concept_id':'triangle'}],'example_items':[{'example_id':'positive','concept_id':'triangle','features':{'sides':'three','closed':'yes','color':'red'},'variant_features':['color'],'role':'example','source':'fixture:positive'},{'example_id':'boundary','concept_id':'triangle','features':{'sides':'four','closed':'yes','color':'red'},'variant_features':['color'],'role':'counterexample','source':'fixture:boundary'}]}
def run(method='dual_coding',**changes):return execute(method,{**pack(),**changes})

def test_dual_mapping_exact_coverage_accessibility_and_honesty():
 r=run()['result']['representation_pack']
 assert r['status']=='validated' and r['valid'] is True
 assert r['concept_reports']==[{'concept_id':'triangle','verbal_ids':['v'],'visual_ids':['img'],'mapped_pairs':[['v','img']],'missing_verbal':False,'missing_visual':False,'missing_mapping':False}]
 assert r['mapping_reports']==[{'verbal_id':'v','visual_id':'img','concept_id':'triangle','conflicting_features':[],'missing_verbal_invariants':[],'missing_visual_invariants':[],'valid':True}]
 assert r['visual_accessibility']==[{'visual_id':'img','alt_text':'A closed triangle','source':'fixture:visual'}]
 assert r['source_truth_verified'] is False and r['image_understanding_executed'] is False and r['learning_improvement'] is None
 assert run()['evaluation']['capability_executed'] is True

def test_missing_and_conflicting_mapping_report_not_fabricated_success():
 p=pack();p['visual_elements'][0]['features']['sides']='four'
 r=execute('dual_coding',p)['result']['representation_pack']
 assert r['valid'] is False and r['mapping_reports'][0]['conflicting_features']==['sides']
 p=pack();p['visual_elements'][0]['features'].pop('closed');r=execute('dual_coding',p)['result']['representation_pack']
 assert r['mapping_reports'][0]['missing_visual_invariants']==['closed'] and r['valid'] is False
 r=run(representation_mappings=[])['result']['representation_pack'];assert r['valid'] is False and r['concept_reports'][0]['missing_mapping'] is True
 r=run(visual_elements=[],representation_mappings=[])['result']['representation_pack'];assert r['valid'] is False and r['concept_reports'][0]['missing_visual'] is True
 r=run(verbal_propositions=[],representation_mappings=[])['result']['representation_pack'];assert r['concept_reports'][0]['missing_verbal'] is True

def test_concrete_invariant_variant_counterexample_computation():
 r=run('concrete_examples')['result']['example_pack']
 assert r['valid'] is True and r['concept_reports']==[{'concept_id':'triangle','valid_example_ids':['positive'],'valid_counterexample_ids':['boundary'],'coverage_complete':True}]
 assert r['example_reports']==[{'example_id':'positive','concept_id':'triangle','role':'example','violated_invariants':[],'missing_invariants':[],'variant_features':['color'],'valid':True,'source':'fixture:positive'},{'example_id':'boundary','concept_id':'triangle','role':'counterexample','violated_invariants':['sides'],'missing_invariants':[],'variant_features':['color'],'valid':True,'source':'fixture:boundary'}]
 assert r['source_truth_verified'] is False and r['learning_improvement'] is None
 assert run('concrete_examples')['evaluation']['capability_executed'] is True

def test_wrong_example_role_missing_feature_and_invariant_variants():
 p=pack();p['example_items'][1]['features']['sides']='three'
 r=execute('concrete_examples',p)['result']['example_pack'];assert r['valid'] is False and r['example_reports'][1]['valid'] is False
 p=pack();p['example_items'][0]['features'].pop('closed');r=execute('concrete_examples',p)['result']['example_pack'];assert r['example_reports'][0]['missing_invariants']==['closed'] and r['valid'] is False
 p=pack();p['example_items'][0]['variant_features']=['sides']
 with pytest.raises(LearningReasoningError):execute('concrete_examples',p)
 r=run('concrete_examples',example_items=pack()['example_items'][:1])['result']['example_pack'];assert r['valid'] is False and r['concept_reports'][0]['coverage_complete'] is False

@pytest.mark.parametrize('change',[{'concepts':[]},{'concepts':[{'concept_id':'c','invariants':{},'source':'fixture'}]},{'visual_elements':[{'id':'img','concept_id':'triangle','features':{},'alt_text':'','source':'fixture'}]},{'representation_mappings':[{'verbal_id':'unknown','visual_id':'img','concept_id':'triangle'}]},{'verbal_propositions':[[]]}])
def test_malformed_rep_records_and_nonmutation(change):
 p={**pack(),**change};before=deepcopy(p)
 with pytest.raises(LearningReasoningError):execute('dual_coding',p)
 assert p==before

def test_unknown_example_duplicate_ids_and_source_guards():
 for field in ['concepts','verbal_propositions','visual_elements','example_items']:
  p=pack();p[field][0]['source']=''
  with pytest.raises(LearningReasoningError):execute('concrete_examples'if field=='example_items'else 'dual_coding',p)
  p=pack();p[field].append(deepcopy(p[field][0]))
  with pytest.raises(LearningReasoningError):execute('concrete_examples'if field=='example_items'else 'dual_coding',p)
 p=pack();p['example_items'][0]['concept_id']='unknown'
 with pytest.raises(LearningReasoningError):execute('concrete_examples',p)

def test_mounted_auth_tenant_and_minimal_payload_refusal(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner')
 for method in ['dual_coding','concrete_examples']:
  path='/api/v1/api/modules/20/learning-reasoning-810-859/'+method
  assert c.post(path,json={'payload':pack()}).status_code==401
  r=c.post(path,headers=h,json={'payload':pack()});assert r.status_code==200 and r.json()['tenant_id']=='a' and r.json()['evaluation']['capability_executed'] is True
  assert c.post(path,headers=h,json={'payload':{'source':SRC,'objective':'x'}}).status_code==422
  assert c.post(path,headers=h,json={'payload':{**pack(),'resource_refs':[{'tenant_id':'b'}]}}).status_code==403

def test_unmapped_decorative_visual_and_invalid_matching_values():
 p=pack();p['visual_elements'].append({**p['visual_elements'][0],'id':'decorative'})
 r=execute('dual_coding',p)['result']['representation_pack'];assert r['unmapped_visual_ids']==['decorative'] and r['valid'] is False
 p=pack()
 for field in ['verbal_propositions','visual_elements']:p[field][0]['features']['sides']='four'
 r=execute('dual_coding',p)['result']['representation_pack'];assert r['mapping_reports'][0]['conflicting_features']==['sides'] and r['valid'] is False

def test_shapes_caps_and_mapping_identity_guards():
 for field in ['concepts','verbal_propositions','visual_elements']:
  p=pack();rows=[]
  for i in range(64):
   row=deepcopy(p[field][0]);row['concept_id'if field=='concepts'else 'id']=str(i);rows.append(row)
  p[field]=rows
  if field=='concepts':
   # Keep original references valid by renaming first definition.
   p[field][0]['concept_id']='triangle'
  else:p['representation_mappings']=[]
  execute('dual_coding',p)
  extra=deepcopy(rows[-1]);extra['concept_id'if field=='concepts'else 'id']='extra';p[field]=rows+[extra]
  with pytest.raises(LearningReasoningError):execute('dual_coding',p)
 p=pack();p['representation_mappings']*=2
 with pytest.raises(LearningReasoningError):execute('dual_coding',p)
 p=pack();p['concepts'][0]['invariants']={str(i):'value'for i in range(32)};execute('dual_coding',p)
 p['concepts'][0]['invariants']['extra']='value'
 with pytest.raises(LearningReasoningError):execute('dual_coding',p)

@pytest.mark.parametrize('change',[{'role':'boundary'},{'variant_features':'color'},{'variant_features':['color','color']},{'variant_features':['missing']},{'features':[]}])
def test_example_shape_role_and_variant_guards(change):
 p=pack();p['example_items'][0].update(change)
 with pytest.raises(LearningReasoningError):execute('concrete_examples',p)

def test_positive_example_invariant_violation_is_invalid():
 p=pack();p['example_items'][0]['features']['sides']='four'
 r=execute('concrete_examples',p)['result']['example_pack']
 assert r['valid'] is False and r['example_reports'][0]['valid'] is False and r['example_reports'][0]['violated_invariants']==['sides']

@pytest.mark.parametrize('target,key,value',[
 ('invariants','', 'three'),('invariants','sides',''),('features','', 'three'),('features','sides','')])
def test_all_feature_key_value_text_guards(target,key,value):
 p=pack()
 if target=='invariants':p['concepts'][0][target]={key:value}
 else:p['verbal_propositions'][0][target]={key:value}
 with pytest.raises(LearningReasoningError):execute('dual_coding',p)

@pytest.mark.parametrize('field,key',[('concepts','concept_id'),('verbal_propositions','id'),('visual_elements','id'),('representation_mappings','verbal_id'),('representation_mappings','visual_id'),('example_items','example_id')])
def test_all_identifier_text_guards(field,key):
 p=pack();p[field][0][key]=''
 with pytest.raises(LearningReasoningError):execute('concrete_examples'if field=='example_items'else 'dual_coding',p)

@pytest.mark.parametrize('variants',['x',[''],[1]])
def test_variant_type_and_text_guards_unmasked(variants):
 p=pack();p['example_items'][0]['features']['x']='value';p['example_items'][0]['variant_features']=variants
 with pytest.raises(LearningReasoningError):execute('concrete_examples',p)

def test_record_minima_mapping_and_example_caps():
 for field in ['concepts','example_items']:
  p=pack();p[field]=[]
  with pytest.raises(LearningReasoningError):execute('concrete_examples',p)
 # Dual representation lists/mappings accept zero and report gaps, not refusal.
 r=run(verbal_propositions=[],visual_elements=[],representation_mappings=[])['result']['representation_pack']
 assert r['status']=='gaps_or_conflicts' and r['valid'] is False
 assert r['concept_reports']==[{'concept_id':'triangle','verbal_ids':[],'visual_ids':[],'mapped_pairs':[],'missing_verbal':True,'missing_visual':True,'missing_mapping':True}]
 p=pack();p['verbal_propositions']=[{**p['verbal_propositions'][0],'id':str(i)}for i in range(17)];p['visual_elements']=[{**p['visual_elements'][0],'id':str(i)}for i in range(16)]
 pairs=[{'verbal_id':str(i),'visual_id':str(j),'concept_id':'triangle'}for i in range(17)for j in range(16)]
 p['representation_mappings']=pairs[:256];assert len(execute('dual_coding',p)['result']['representation_pack']['mapping_reports'])==256
 p['representation_mappings']=pairs[:257]
 with pytest.raises(LearningReasoningError):execute('dual_coding',p)
 p=pack();p['example_items']=[{**p['example_items'][i%2],'example_id':str(i)}for i in range(256)];assert len(execute('concrete_examples',p)['result']['example_pack']['example_reports'])==256
 p['example_items'].append({**p['example_items'][0],'example_id':'257'})
 with pytest.raises(LearningReasoningError):execute('concrete_examples',p)

def test_variant_cap_with_present_noninvariant_features():
 # Features cap32 shadows valid variants33; exact32 noninvariant variants are
 # validly shaped but missing invariants is reported, not refused.
 p=pack();p['example_items'][0]['features']={str(i):'value'for i in range(32)};p['example_items'][0]['variant_features']=[str(i)for i in range(32)]
 assert execute('concrete_examples',p)['result']['example_pack']['example_reports'][0]['missing_invariants']==['closed','sides']
 p['example_items'][0]['variant_features'].append('extra')
 with pytest.raises(LearningReasoningError,match='variant_features'):execute('concrete_examples',p)

def test_unknown_and_mismatched_references():
 for field in ['verbal_propositions','visual_elements','representation_mappings','example_items']:
  p=pack();p[field][0]['concept_id']='unknown'
  with pytest.raises(LearningReasoningError):execute('concrete_examples'if field=='example_items'else 'dual_coding',p)
 p=pack();p['representation_mappings'][0]['visual_id']='unknown'
 with pytest.raises(LearningReasoningError):execute('dual_coding',p)
 for field in ['verbal_propositions','visual_elements']:
  p=pack();p['concepts'].append({'concept_id':'other','invariants':{'sides':'three'},'source':'fixture:other'});p[field][0]['concept_id']='other'
  with pytest.raises(LearningReasoningError):execute('dual_coding',p)
 p=pack();p['concepts'][0]['invariants']={}
 with pytest.raises(LearningReasoningError):execute('dual_coding',p)

def test_full_invalid_mapping_and_example_reports():
 p=pack();p['verbal_propositions'][0]['features']={'sides':'four'};p['visual_elements'][0]['features']={'sides':'three'}
 r=execute('dual_coding',p)['result']['representation_pack']
 assert r['status']=='gaps_or_conflicts' and r['valid'] is False
 assert r['mapping_reports']==[{'verbal_id':'v','visual_id':'img','concept_id':'triangle','conflicting_features':['sides'],'missing_verbal_invariants':['closed'],'missing_visual_invariants':['closed'],'valid':False}]
 assert r['unmapped_verbal_ids']==r['unmapped_visual_ids']==[]
 assert r['concepts']==p['concepts']
 assert r['verbal_provenance']==[{'verbal_id':'v','text':'A closed three-sided shape','source':'fixture:verbal'}]
 assert r['visual_accessibility']==[{'visual_id':'img','alt_text':'A closed triangle','source':'fixture:visual'}]
 assert r['boundary']=='Supplied symbolic concept/feature mappings only, with accessibility text and computed coverage/conflict checks. No image interpretation/generation or learning-effectiveness claim.'
 p=pack();p['example_items'][0]['features']={'sides':'four','color':'red'}
 r=execute('concrete_examples',p)['result']['example_pack']
 assert r['status']=='gaps_or_conflicts' and r['valid'] is False
 assert r['example_reports'][0]=={'example_id':'positive','concept_id':'triangle','role':'example','violated_invariants':['sides'],'missing_invariants':['closed'],'variant_features':['color'],'valid':False,'source':'fixture:positive'}
 assert r['concept_reports']==[{'concept_id':'triangle','valid_example_ids':[],'valid_counterexample_ids':['boundary'],'coverage_complete':False}]
 assert r['concepts']==p['concepts'] and r['source_truth_verified'] is False and r['learning_improvement'] is None
 assert r['boundary']=='Supplied symbolic invariant/example/counterexample checks only. Variants are declared non-invariant properties; no semantic classification or learning-effectiveness claim.'

def test_report_ordering_reverse_multi_inputs_and_fixed_seed():
 import os,subprocess,sys
 p=pack();v=p['verbal_propositions'][0];w=p['visual_elements'][0]
 p['verbal_propositions']=[{**v,'id':key}for key in ['zebra','middle','alpha']];p['visual_elements']=[{**w,'id':key}for key in ['zebra','middle','alpha']]
 p['representation_mappings']=[{'verbal_id':key,'visual_id':key,'concept_id':'triangle'}for key in ['zebra','middle','alpha']]
 r=execute('dual_coding',p)['result']['representation_pack']
 assert r['concept_reports'][0]['mapped_pairs']==[['alpha','alpha'],['middle','middle'],['zebra','zebra']]
 assert [m['verbal_id']for m in r['mapping_reports']]==['alpha','middle','zebra']
 assert r['verbal_provenance']==[{'verbal_id':key,'text':v['text'],'source':v['source']}for key in ['alpha','middle','zebra']]
 p['representation_mappings']=[];r=execute('dual_coding',p)['result']['representation_pack']
 assert r['unmapped_verbal_ids']==r['unmapped_visual_ids']==['alpha','middle','zebra']
 code="from app.modules.m20_general_cognitive_worker.representation_practice import dual_pack; p="+repr(p)+"; r=dual_pack(p); assert r['unmapped_visual_ids']==['alpha','middle','zebra']; assert r['unmapped_verbal_ids']==['alpha','middle','zebra']"
 result=subprocess.run([sys.executable,'-c',code],env={**os.environ,'PYTHONHASHSEED':'6'},capture_output=True,text=True)
 assert result.returncode==0,result.stdout+result.stderr
 p=pack();p['example_items'][0]['features'].update(zebra='value',alpha='value');p['example_items'][0]['variant_features']=['zebra','color','alpha']
 assert execute('concrete_examples',p)['result']['example_pack']['example_reports'][0]['variant_features']==['alpha','color','zebra']

def test_visual_feature_and_representation_concept_text_guards():
 for field in ['verbal_propositions','visual_elements']:
  p=pack();p[field][0]['concept_id']=''
  with pytest.raises(LearningReasoningError):execute('dual_coding',p)
 for props in [{'':'value'},{'sides':''}]:
  p=pack();p['visual_elements'][0]['features']=props
  with pytest.raises(LearningReasoningError):execute('dual_coding',p)
 p=pack();p['representation_mappings'][0]['concept_id']=''
 with pytest.raises(LearningReasoningError):execute('dual_coding',p)

def test_one_invalid_among_multiple_valid_reports_not_all_guard():
 p=pack();p['visual_elements'].append({**p['visual_elements'][0],'id':'bad','features':{'sides':'four','closed':'yes'}});p['representation_mappings'].append({'verbal_id':'v','visual_id':'bad','concept_id':'triangle'})
 r=execute('dual_coding',p)['result']['representation_pack'];assert r['valid'] is False and [m['valid']for m in r['mapping_reports']]==[False,True]
 p=pack();p['example_items'].append({**p['example_items'][0],'example_id':'bad','features':{'sides':'four','closed':'yes','color':'red'}})
 r=execute('concrete_examples',p)['result']['example_pack'];assert r['valid'] is False and r['concept_reports'][0]['coverage_complete'] is True and r['example_reports'][2]['valid'] is False

def test_empty_dual_concepts_refuses_not_vacuous_validation():
 from app.modules.m20_general_cognitive_worker.representation_practice import dual_pack
 p=pack();p.update(concepts=[],verbal_propositions=[],visual_elements=[],representation_mappings=[])
 with pytest.raises(ValueError,match='concepts requires1..64 records'):dual_pack(p)

@pytest.mark.parametrize('field,key,value,message',[('concepts','concept_id',[], 'concept_id requires bounded nonempty string'),('verbal_propositions','id',[], 'representation id requires bounded nonempty string'),('visual_elements','id',1, 'representation id requires bounded nonempty string'),('representation_mappings','verbal_id',[], 'verbal_id requires bounded nonempty string'),('representation_mappings','visual_id',[], 'visual_id requires bounded nonempty string')])
def test_unhashable_nontext_ids_refuse_valueerror(field,key,value,message):
 from app.modules.m20_general_cognitive_worker.representation_practice import dual_pack
 p=pack();p[field][0][key]=value
 with pytest.raises(ValueError,match=message):dual_pack(p)

def test_reference_errors_are_valueerror_not_keyerror():
 from app.modules.m20_general_cognitive_worker.representation_practice import dual_pack,example_pack
 for field in ['verbal_propositions','visual_elements']:
  p=pack();p[field][0]['concept_id']='unknown'
  with pytest.raises(ValueError,match='unique representation IDs and known concepts required'):dual_pack(p)
 p=pack();p['representation_mappings'][0]['concept_id']='unknown'
 with pytest.raises(ValueError,match='known representation/concept references required'):dual_pack(p)
 p=pack();p['example_items'][0]['concept_id']='unknown'
 with pytest.raises(ValueError,match='unique example IDs and known concepts required'):example_pack(p)
 p=pack();p['example_items'][0]['variant_features']=[[]]
 with pytest.raises(ValueError,match='variant feature requires bounded nonempty string'):example_pack(p)

def test_noninvariant_disagreement_and_each_invariant_direction():
 p=pack();p['verbal_propositions'][0]['features']['color']='red';p['visual_elements'][0]['features']['color']='blue'
 r=execute('dual_coding',p)['result']['representation_pack'];assert r['mapping_reports'][0]['conflicting_features']==['color'] and r['mapping_reports'][0]['valid'] is False and r['valid'] is False
 # Set both representation values equal but contrary to the definition. Removing
 # either invariant-v check is exercised separately by omitting that key in the
 # other representation, so shared-pair disagreements cannot mask the validator.
 for bad,other in [('verbal_propositions','visual_elements'),('visual_elements','verbal_propositions')]:
  p=pack();p[bad][0]['features']['sides']='four';p[other][0]['features'].pop('sides')
  r=execute('dual_coding',p)['result']['representation_pack']
  assert r['mapping_reports'][0]['conflicting_features']==['sides'] and r['mapping_reports'][0]['valid'] is False
 p=pack();p['visual_elements'][0]['features'].pop('closed')
 r=execute('dual_coding',p)['result']['representation_pack'];assert r['mapping_reports'][0]['missing_visual_invariants']==['closed'] and r['mapping_reports'][0]['valid'] is False

def test_unmapped_visual_top_status_and_invalid_counterexample_coverage():
 p=pack();p['visual_elements'].append({**p['visual_elements'][0],'id':'unmapped'})
 r=execute('dual_coding',p)['result']['representation_pack'];assert r['unmapped_visual_ids']==['unmapped'] and r['valid'] is False and r['status']=='gaps_or_conflicts'
 p=pack();p['example_items'][1]['features']['sides']='three'
 r=execute('concrete_examples',p)['result']['example_pack'];assert r['example_reports'][1]['valid'] is False and r['concept_reports'][0]['valid_counterexample_ids']==[] and r['concept_reports'][0]['coverage_complete'] is False
