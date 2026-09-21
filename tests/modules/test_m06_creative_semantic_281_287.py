import pytest
from app.modules.m06_social_media_manager.creative_semantics_281_287 import CreativeSemanticError,validate
CASES={
'color-theory':({'palette':[{'role':'text','hex':'#000000'},{'role':'background','hex':'#ffffff'}],'accessibility_pairs':[{'foreground':'text','background':'background'}]},lambda x:x['contrast_results'][0]['wcag_aa_normal']),
'composition':({'grid':{'columns':12,'gutter':'24px'},'visual_hierarchy':['headline','body']},lambda x:x['grid_columns']==12),
'typography':({'scale':[16,20,25],'typefaces':{'body':'Inter','display':'Atkinson'},'fallbacks':['sans-serif']},lambda x:x['scale_ratio']==1.25),
'logo-design':({'concepts':[{'symbolism':'path','construction':'grid','originality_attested':True},{'symbolism':'star','construction':'circle','originality_attested':True}],'clear_space':'1x'},lambda x:x['concept_count']==2 and x['all_originality_attested']),
'brand-identity':({'elements':[{'id':'mark'}],'application_rules':{'social':{},'print':{},'product':{}},'governance':{'owner':'brand'}},lambda x:x['surface_coverage']==['print','product','social']),
'packaging-design':({'panel_layout':[{'panel':'front'},{'panel':'back'}],'materials':[{'name':'board'}]},lambda x:x['dieline_status']=='described_not_drawn'),
'ui-ux-design':({'screens':[{'id':'home'}],'components':[{'id':'button'}],'states':['default','hover','disabled','loading','error','empty'],'usability_notes':['keyboard']},lambda x:len(x['state_coverage'])==6),
}
@pytest.mark.parametrize('slug',CASES)
def test_rows_281_287_have_distinctive_semantic_invariants(slug):
 payload,check=CASES[slug];assert check(validate(slug,payload))
@pytest.mark.parametrize('slug',CASES)
def test_rows_281_287_fail_closed_on_generic_acceptance_only_output(slug):
 with pytest.raises(CreativeSemanticError):validate(slug,{'sections':'looks good'})
def test_color_rejects_invalid_hex_and_ui_rejects_missing_error_states():
 d=dict(CASES['color-theory'][0]);d['palette']=[{'role':'text','hex':'black'},{'role':'background','hex':'#ffffff'}]
 with pytest.raises(CreativeSemanticError):validate('color-theory',d)
 d=dict(CASES['ui-ux-design'][0]);d['states']=['default']
 with pytest.raises(CreativeSemanticError):validate('ui-ux-design',d)
def test_mounted_http_semantic_validation_and_negative_path():
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.modules.m06_social_media_manager.routes import router
 app=FastAPI();app.include_router(router,prefix='/api/v1');c=TestClient(app)
 ok=c.post('/api/v1/social-media-manager/creative/ui-ux-design/semantic-validate',json=CASES['ui-ux-design'][0]);assert ok.status_code==200 and ok.json()['row']==287
 assert c.post('/api/v1/social-media-manager/creative/ui-ux-design/semantic-validate',json={'screens':[]}).status_code==422
