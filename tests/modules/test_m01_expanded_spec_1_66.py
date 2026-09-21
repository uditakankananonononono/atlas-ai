import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m01_opportunity_discovery.expanded_spec_1_66 import *
from app.modules.m01_opportunity_discovery.expanded_spec_routes_1_66 import router
EXPECTED={1:'Kaggle RSS',2:'Devpost API',3:'Unstop',4:'Opportunity Desk',5:'Opportunities for Youth',6:'Snowday',7:'Hack Club',8:'GitHub Topics',9:'LinkedIn jobs',10:'Instagram hashtags',11:'Twitter/X lists',12:'Reddit r/competitions',13:'Reddit r/scholarships',14:'Discord channels',15:'Custom webhooks',16:'Girls on Campus',17:'Institute of Competition Sciences',18:'Bold.org',19:'Unigo',20:'Fastweb',21:'JoinSucceed.com',22:'Top-college and company hackathon channels',23:'Tata Imagination Challenge',24:'Samsung Solve for Tomorrow',25:'Google opportunities',26:'Scholarships360',27:'Scholarships.com',28:'Exactly 200 scholarship sites',**{29+i:n for i,n in enumerate(SOCIAL)}}
def transport_for(i):
 m=MODE[i]
 return {'official_api_or_user_export':'official_api','official_api_or_public_page':'official_api','official_api_or_public_list':'official_api','user_authorized_export_or_webhook':'user_export','official_api_export_or_public_page':'public_page'}.get(m,m)
def test_registry_exact_66():
 c=capabilities();assert len(c)==66 and [x['row_id'] for x in c]==list(range(1,67))
@pytest.mark.parametrize('row_id',range(1,67))
def test_each_row_exact_and_substantively_normalizes(row_id):
 assert get_source(row_id)['name']==EXPECTED[row_id]
 transport=transport_for(row_id);authorized=transport in {'user_export','webhook'}
 o=normalize(row_id,{'title':'Opportunity','url':f'https://source{row_id}.example/item','summary':'Open now','eligibility':['students'],'tags':['grant'],'raw_reference':'provider-id'},transport=transport,authorized=authorized)
 assert o['source_row_id']==row_id and o['source_name']==EXPECTED[row_id] and o['provenance']['retrieved_via']==transport and o['policy']['no_evasion'] and len(o['id'])==24
@pytest.mark.parametrize('row_id',range(29,67))
def test_social_rows_are_exact_named_sources_with_public_or_official_boundary(row_id):
 s=get_source(row_id);assert s['kind']=='tracked_social_source' and s['access_mode']=='official_api_export_or_public_page'
def test_batch_deduplicates_and_reports_bad_records_without_losing_good():
 rows=[{'title':'x','url':'https://x.test/a'},{'title':'x','url':'https://x.test/a'},{'title':'','url':'bad'}]
 o=normalize_batch(1,rows,transport='rss');assert o['accepted']==1 and o['deduplicated']==1 and len(o['errors'])==1
def test_user_export_and_webhook_require_authorization_and_disallowed_transport_fails():
 with pytest.raises(SourceRegistryError,match='authorization'):normalize(14,{'title':'x','url':'https://x.test'},transport='user_export')
 with pytest.raises(SourceRegistryError,match='not permitted'):normalize(1,{'title':'x','url':'https://x.test'},transport='login_scrape')
def test_exact_200_registry_rejects_placeholders_duplicates_and_accepts_200_unique():
 incomplete=validate_scholarship_registry([{'url':'https://a.test'},{'url':'https://a.test'},{'url':'bad'}]);assert not incomplete['complete'] and len(incomplete['problems'])==2
 complete=validate_scholarship_registry([{'url':f'https://site{i}.example'} for i in range(200)]);assert complete['complete'] and complete['valid_unique_count']==200
def test_validation_unknown_invalid_url_and_route():
 with pytest.raises(SourceRegistryError):get_source(67)
 with pytest.raises(SourceRegistryError):normalize(1,{'title':'x','url':'javascript:x'},transport='rss')
 app=FastAPI();app.include_router(router,prefix='/api/v1');c=TestClient(app);assert len(c.get('/api/v1/opportunity-discovery/expanded-spec-1-66/sources').json())==66
 assert c.post('/api/v1/opportunity-discovery/expanded-spec-1-66/sources/1/normalize',json={'transport':'login_scrape','records':[]}).status_code==422
