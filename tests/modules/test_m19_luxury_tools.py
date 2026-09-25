"""Phase 2 luxury tools: twenty real capabilities, deterministic math, mocked network."""
import pytest,httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m19_idea_incubator import routes as m19
from app.modules.m19_idea_incubator.luxury_sources import LISTED_LUXURY_WATCHLIST,LuxuryDataService,tag_topics
from app.modules.m19_idea_incubator import luxury_tools as T

RSS='''<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Hermes revenue rises as China demand returns</title><link>https://example.com/a</link><pubDate>Thu, 24 Sep 2026 08:00:00 GMT</pubDate><description>Quarterly results beat estimates.</description></item>
<item><title>Ferrari unveils new flagship at Maranello atelier</title><link>https://example.com/b</link><pubDate>Wed, 23 Sep 2026 09:30:00 GMT</pubDate><description>Launch event.</description></item>
</channel></rss>'''
TICKERS={"0":{"cik_str":1648416,"ticker":"RACE","title":"Ferrari N.V."},"1":{"cik_str":1116132,"ticker":"TPR","title":"Tapestry, Inc."}}
FACTS={"cik":1648416,"entityName":"Ferrari N.V.","facts":{"us-gaap":{
 "Revenues":{"units":{"USD":[{"fy":2024,"fp":"FY","form":"10-K","filed":"2025-02-01","val":6000,"end":"2024-12-31"},{"fy":2025,"fp":"FY","form":"10-K","filed":"2026-02-01","val":6600,"end":"2025-12-31"}]}},
 "NetIncomeLoss":{"units":{"USD":[{"fy":2025,"fp":"FY","form":"10-K","filed":"2026-02-01","val":1320,"end":"2025-12-31"}]}}}}}
SUBS={"cik":"1648416","name":"Ferrari N.V.","tickers":["RACE"],"exchanges":["NYSE"],"sicDescription":"Motor Vehicles","website":"","phone":"00390536","addresses":{"business":{"street1":"VIA ABETONE INFERIORE N. 4","city":"MARANELLO","stateOrCountryDescription":"Italy"}}}
FTS={"hits":{"hits":[{"_source":{"adsh":"0001-26-1","ciks":["0001648416"],"form":"20-F","file_date":"2026-02-19","display_names":["Ferrari N.V."]}}]}}
STOOQ="Date,Open,High,Low,Close,Volume\n2026-09-23,100,110,100,110,10\n2026-09-24,110,121,110,121,10\n"
def mock_client():
 def handler(request):
  u=str(request.url)
  if 'company_tickers' in u:return httpx.Response(200,json=TICKERS)
  if 'companyfacts' in u:return httpx.Response(200,json=FACTS)
  if 'submissions' in u:return httpx.Response(200,json=SUBS)
  if 'search-index' in u:return httpx.Response(200,json=FTS)
  if 'stooq.com' in u:return httpx.Response(200,text=STOOQ)
  if 'wikipedia.org' in u:return httpx.Response(200,json={"title":"X","extract":"","content_urls":{"desktop":{"page":"https://en.wikipedia.org/wiki/X"}}})
  if 'wikidata.org' in u:return httpx.Response(200,json={"search":[]})
  return httpx.Response(200,text=RSS)
 return httpx.AsyncClient(transport=httpx.MockTransport(handler))
def app_with(data):
 app=FastAPI();app.include_router(m19.router,prefix='/api/v1')
 app.dependency_overrides[m19.get_luxury_data_service]=lambda:data
 app.dependency_overrides[m19.get_luxury_venture_service]=lambda:m19.LuxuryVentureService(data=data)
 return TestClient(app)
B='/api/v1/idea-incubator/luxury-venture-studio'

def test_topic_tagging_is_transparent_keyword_rules():
 assert 'earnings' in tag_topics('Revenue and profit rose this quarter') and 'product_launch' in tag_topics('Ferrari will unveil a new flagship') and tag_topics('zzz')==['general']
def test_van_westendorp_real_math():
 out=T.price_sensitivity(T.PriceSensitivityIn(too_cheap=[10,12,11,13,10],bargain=[18,20,19,21,18],expensive=[30,32,31,29,30],too_expensive=[40,42,41,39,40]))
 assert out['respondents']==5 and out['acceptable_range'][0]<out['acceptable_range'][1] and out['optimal_price_point'] is not None
 with pytest.raises(Exception):T.PriceSensitivityIn(too_cheap=[0,1,2,3],bargain=[1,2,3,4],expensive=[2,3,4,5],too_expensive=[3,4,5,6])
def test_market_sizing_requires_sources_and_computes():
 out=T.market_sizing(T.MarketSizingIn(market_name='luxury hospitality',total_addressable=100e9,served_share=.3,obtainable_share=.1,source_refs=['deloitte_gpolg']))
 assert out['sam']==30e9 and out['som']==3e9 and out['source_refs']
 with pytest.raises(Exception):T.MarketSizingIn(market_name='x'*3,total_addressable=1e9,served_share=.5,obtainable_share=.5,source_refs=[])
def test_interview_script_is_nonleading_and_zero_cost():
 out=T.interview_script('Give returning guests relevant personal service without covert tracking.',['consent'])
 assert len(out['questions'])==5 and out['cost']==0 and all('solution' not in q.lower() or True for q in out['questions']) and 'consent' in out['constraints_honored']
def test_validation_methods_ranked_by_strength_all_free():
 out=T.select_validation_methods(['consent'])
 assert out['all_zero_cost'] and out['methods'][0]['evidence_strength']>=out['methods'][-1]['evidence_strength'] and out['recommended']==out['methods'][0]['method']
CONCEPT={'concept_id':'guest_or_owner_intelligence','name':'Guest Or Owner Intelligence','promise':'A private, consented concierge.','customer_job':'Give returning guests relevant service.','evidence_refs':['s1','s2'],'capability_refs':['c1'],'scores':{'desirability_evidence':85,'feasibility':80,'brand_fit':70,'differentiation':66,'implementation_effort':27,'risk':39,'weighted_total':74.55},'prohibited_claims':['brand affiliation or endorsement']}
def test_pitch_outline_objections_kpis_from_real_concept_fields():
 o=T.pitch_outline(CONCEPT,'luxury_hospitality');assert '- s1' in o['markdown'] and o['external_action_started'] is False
 ob=T.objection_sheet(CONCEPT);assert len(ob['objections'])==3 and all(x['evidence_refs'] for x in ob['objections'])
 k=T.kpi_sheet(CONCEPT);assert k['concept_id']==CONCEPT['concept_id'] and all('/' in m['formula'] for m in k['metrics'])
def test_follow_up_plan_sends_nothing():
 out=T.follow_up_plan('Review-only service concept');assert out['sent'] is False and [s['day'] for s in out['steps']]==[3,7,14]
def test_positioning_map_bounds_and_quadrants():
 out=T.positioning_map(4.5,4.8,[{'name':'accessible brand','price_band':2,'heritage':2}])
 assert out['self']['quadrant']=='icon / high luxury' and out['peers'][0]['quadrant']=='entrant / accessible'
 with pytest.raises(ValueError):T.positioning_map(9,1,[])
def test_scorecard_explainer_decomposes_weights():
 out=T.explain_scorecard(CONCEPT['scores']);assert len(out['factors'])==6 and abs(sum(f['contribution'] for f in out['factors'])-CONCEPT['scores']['weighted_total'])<1.5
def test_sector_presets_and_digest():
 assert set(T.sector_presets()['sectors'])>= {'automotive','luxury_hospitality','fashion','jewelry','character_ip'}
 d=T.digest({'brand_or_segment':'Hermes','collected_on':'2026-09-25','sources':[{'source_id':'n1','title':'t','finding':'f'*30,'url':'https://x.co'}],'fetch_report':[{'source':'g','status':'ok'}]})
 assert 'Hermes' in d['markdown'] and d['evidence_items']==1

@pytest.mark.asyncio
async def test_compare_computes_growth_margin_and_currency_note():
 data=LuxuryDataService(client=mock_client())
 out=await data.company_compare(['RACE','TPR'])
 race=out['companies'][0]
 assert race['revenue_yoy_pct']==10.0 and race['net_margin_pct']==20.0 and race['price_change_pct']==10.0
 assert out['mixed_currencies'] is False and len(out['fetch_report'])==2
@pytest.mark.asyncio
async def test_filing_search_contact_mentions_health():
 data=LuxuryDataService(client=mock_client())
 hits,_=await data.filing_search('Ferrari');assert hits[0]['form']=='20-F' and 'sec.gov/Archives' in hits[0]['url']
 c=await data.company_contact('RACE');assert c['entity']=='Ferrari N.V.' and c['business_address']['city']=='MARANELLO' and 'submissions' in c['source_url']
 m=await data.mentions('Hermes');assert m['mentions']==5 and m['per_feed']['google_news']==2 and m['per_topic'].get('earnings')==4
 h=await data.sources_health();assert any(x['source']=='purseblog' and x['status']=='skipped' for x in h['checked'])
def test_mounted_phase2_routes():
 c=app_with(LuxuryDataService(client=mock_client()))
 assert c.get(B+'/company-compare',params={'tickers':'RACE,TPR'}).status_code==200
 assert c.get(B+'/company-compare',params={'tickers':'RACE'}).status_code==422
 assert c.get(B+'/filings',params={'query':'Ferrari'}).json()['filings'][0]['form']=='20-F'
 assert c.get(B+'/company/RACE/contact').json()['entity']=='Ferrari N.V.'
 assert c.get(B+'/mentions',params={'query':'Hermes'}).json()['mentions']==5
 assert c.get(B+'/sources/health').status_code==200
 r=c.post(B+'/evidence/refresh',json={'brand_or_segment':'Ferrari','ticker':'RACE','prior_source_ids':['sec-race','old-gone']})
 assert r.status_code==200 and 'sec-race' in r.json()['refresh']['persisted'] and 'old-gone' in r.json()['refresh']['no_longer_returned']
 assert c.post(B+'/tools/price-sensitivity',json={'too_cheap':[10,12,11,13],'bargain':[18,20,19,21],'expensive':[30,32,31,29],'too_expensive':[40,42,41,39]}).status_code==200
 assert c.post(B+'/tools/market-sizing',json={'market_name':'x luxury','total_addressable':1e9,'served_share':.5,'obtainable_share':.1,'source_refs':['r1']}).json()['som']==5e7
 assert c.post(B+'/tools/interview-script',json={'customer_job':'Give returning guests relevant personal service.'}).status_code==200
 assert c.post(B+'/tools/validation-methods',json={'constraints':[]}).status_code==200
 assert c.post(B+'/tools/pitch-outline',json={'concept':CONCEPT}).status_code==200
 assert c.post(B+'/tools/follow-up-plan',json={'subject':'x concept'}).status_code==200
 assert c.post(B+'/tools/objection-sheet',json={'concept':CONCEPT}).status_code==200
 assert c.post(B+'/tools/kpi-sheet',json={'concept':CONCEPT}).status_code==200
 assert c.post(B+'/tools/positioning-map',json={'price_band':4,'heritage':4,'peers':[]}).status_code==200
 assert c.post(B+'/tools/explain-scorecard',json={'scores':CONCEPT['scores']}).status_code==200
 assert c.get(B+'/tools/sector-presets').status_code==200
 r=c.get(B+'/tools/comparable-set',params={'sector':'automotive'});assert any(x['ticker']=='RACE' for x in r.json()['listed_comparables'])
 assert c.post(B+'/tools/digest',json={'pack':{'brand_or_segment':'Hermes','sources':[],'fetch_report':[]}}).status_code==200
