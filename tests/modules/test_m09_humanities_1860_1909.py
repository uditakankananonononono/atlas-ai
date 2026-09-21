import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m09_knowledge_workspace.humanities_support_1860_1909 import FEATURES,humanities_support_1860_1909
SRC={'id':'s','title':'Primary source','source_url':'https://archive.example/s','provenance':'archive scan'}
def payload(fid):
 d={'sources':[SRC],'research_question':'How is the evidence structured?'}
 if fid<1868:d|={'passages':[{'id':'p','source_id':'s','quotation':'text','location':'p. 1','observations':['repetition'],'interpretations':['framing'],'counter_readings':['alternative']}],'lens':{'principles':['situated reading']},'reader_positions':['historical']}
 elif fid<1884:d|={'tokens':['a','b','a'],'annotations':[{'start':0,'end':1,'label':'x'}],'languages_or_varieties':['documented variety']}
 elif fid<1894:d|={'traditions':[{'name':'T','self_designation':'T'}],'claims':[{'claim':'documented practice','tradition_or_community':'T','source_ids':['s'],'insider_views':['account'],'scholarly_views':['analysis']}]}
 elif fid<1909:d|={'works':[{'id':'w','title':'Work','creator_or_community':'Community','source_ids':['s'],'formal_features':['rhythm'],'rights':{'status':'review'}}],'contexts':[{'period':'P'}]}
 else:d|={'schema':[{'name':'id','required':True},{'name':'title'}],'records':[{'id':'1','title':'A'},{'id':'','title':'B'}],'edges':[{'source':'1','target':'2'}],'transform_log':['OCR reviewed']}
 return d
@pytest.mark.parametrize('fid',range(1860,1910))
def test_all_50_rows_are_exact_and_substantive(fid):
 o=humanities_support_1860_1909(fid,payload(fid));assert o['feature_id']==fid and o['concept']==FEATURES[fid] and o['review_required'] and o['boundary'] and o['sources'][0]['provenance']=='archive scan'
def test_criticism_preserves_quote_location_and_counter_reading():
 o=humanities_support_1860_1909(1860,payload(1860));r=o['close_readings'][0];assert r['location']=='p. 1' and r['counter_readings']==['alternative'] and r['source_resolved']
def test_linguistics_computes_reproducible_corpus_metrics_and_span_validation():
 d=payload(1881);d['annotations'].append({'start':2,'end':5,'label':'bad'});o=humanities_support_1860_1909(1881,d);assert o['corpus_summary']['tokens']==3 and o['frequencies']['a']==2 and len(o['invalid_spans'])==1
def test_religion_separates_claim_views_and_support():
 o=humanities_support_1860_1909(1886,payload(1886));assert o['claim_matrix'][0]['evidence_status']=='supported' and o['claim_matrix'][0]['insider_views']==['account']
def test_heritage_catalog_retains_rights_and_attribution_status():
 o=humanities_support_1860_1909(1908,payload(1908));assert o['catalog'][0]['rights']['status']=='review' and o['catalog'][0]['attribution_status']=='unverified'
def test_digital_humanities_reports_missing_data_and_network_summary():
 o=humanities_support_1860_1909(1909,payload(1909));assert o['missing_required']=={'id':[1]} and o['network_summary']['nodes']==2 and o['network_summary']['edges']==1
def test_fails_closed_without_sources_or_required_domain_inputs():
 with pytest.raises(ValueError):humanities_support_1860_1909(1860,{})
 with pytest.raises(ValueError):humanities_support_1860_1909(1909,{'sources':[SRC]})
def test_mounted_route_is_tenant_scoped():
 r=TestClient(app).post('/api/v1/knowledge-workspace/humanities-1860-1909/support',headers={'x-atlas-tenant':'humanities-t'},json={'feature_id':1909,'data':payload(1909)});assert r.status_code==200 and r.json()['tenant_id']=='humanities-t' and r.json()['concept']=='Digital Humanities'
