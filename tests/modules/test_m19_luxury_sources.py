"""M26 Luxury Venture Studio: real-source adapters, evidence collection, mounted routes.

Network is fully mocked through httpx.MockTransport; fixtures mirror the real
payload shapes of SEC EDGAR, Stooq, Wikipedia/Wikidata and RSS feeds.
"""
import pytest,httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m19_idea_incubator import routes as m19
from app.modules.m19_idea_incubator.luxury_sources import (FREE_REPORT_REGISTRY,LUXURY_FEEDS,LISTED_LUXURY_WATCHLIST,SOURCE_REGISTRY,LuxuryDataService,parse_rss,parse_sec_tickers,parse_stooq_csv,summarize_company_facts,summarize_prices,parse_wikipedia_summary)
from app.modules.m19_idea_incubator.luxury_service import GroundedStudioRequest,LuxuryVentureService
from app.modules.m19_idea_incubator.luxury_venture import Signal,Source

RSS='''<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Hermes opens new leather workshop &amp; hires 200 artisans</title><link>https://example.com/a</link><pubDate>Thu, 24 Sep 2026 08:00:00 GMT</pubDate><description>&lt;p&gt;The house expands capacity in France.&lt;/p&gt;</description></item>
<item><title>Luxury watch demand cools in Q3</title><link>https://example.com/b</link><pubDate>Wed, 23 Sep 2026 09:30:00 GMT</pubDate><description>Swiss exports slow.</description></item>
</channel></rss>'''
GOOGLE_RSS='''<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Ferrari unveils new grand tourer - Robb Report</title><link>https://news.google.com/rss/articles/abc</link><pubDate>Thu, 24 Sep 2026 10:00:00 GMT</pubDate><source url="https://robbreport.com">Robb Report</source><description>Maranello adds a V12 flagship.</description></item>
</channel></rss>'''
TICKERS={"0":{"cik_str":1646972,"ticker":"RACE","title":"Ferrari N.V."},"1":{"cik_str":1001,"ticker":"TPR","title":"Tapestry, Inc."}}
FACTS={"cik":1646972,"entityName":"Ferrari N.V.","facts":{"us-gaap":{
 "RevenueFromContractWithCustomerExcludingAssessedTax":{"units":{"USD":[
  {"fy":2023,"fp":"FY","form":"20-F","filed":"2024-02-23","val":5970000000,"end":"2023-12-31"},
  {"fy":2024,"fp":"FY","form":"20-F","filed":"2025-02-21","val":6677000000,"end":"2024-12-31"},
  {"fy":2024,"fp":"Q4","form":"6-K","filed":"2025-02-21","val":1700000000,"end":"2024-12-31"}]}},
 "NetIncomeLoss":{"units":{"USD":[{"fy":2024,"fp":"FY","form":"20-F","filed":"2025-02-21","val":1526000000,"end":"2024-12-31"}]}}}}}
STOOQ="Date,Open,High,Low,Close,Volume\n2026-09-22,430,436,428,435.2,100000\n2026-09-23,435,441,433,440.1,90000\n"
WIKI={"title":"Hermes","description":"French luxury goods company","extract":"Hermes International is a French luxury design house established in 1837.","content_urls":{"desktop":{"page":"https://en.wikipedia.org/wiki/Herm%C3%A8s"}}}
WIKIDATA={"search":[{"id":"Q843268","label":"Hermes International","description":"French luxury goods manufacturer"}]}

def mock_client(fail_feeds=False):
 def handler(request):
  u=str(request.url)
  if 'company_tickers' in u:return httpx.Response(200,json=TICKERS)
  if 'companyfacts' in u:return httpx.Response(200,json=FACTS)
  if 'stooq.com' in u:return httpx.Response(200,text=STOOQ)
  if 'wikipedia.org' in u:return httpx.Response(200,json=WIKI)
  if 'wikidata.org' in u:return httpx.Response(200,json=WIKIDATA)
  if 'news.google.com' in u:return httpx.Response(200,text=GOOGLE_RSS)
  if any(f['url'].split('/')[2] in u for f in LUXURY_FEEDS):
   if fail_feeds:return httpx.Response(503,text='down')
   return httpx.Response(200,text=RSS)
  return httpx.Response(404,text='unknown')
 return httpx.AsyncClient(transport=httpx.MockTransport(handler))

def test_parse_rss_extracts_items_with_provenance():
 items=parse_rss(RSS,'wwd','WWD')
 assert len(items)==2 and items[0]['url']=='https://example.com/a' and items[0]['feed_name']=='WWD'
 assert 'expands capacity' in items[0]['summary'] and '<' not in items[0]['summary']
 assert parse_rss('<broken','wwd','WWD')==[]
def test_google_news_items_capture_publisher():
 items=parse_rss(GOOGLE_RSS,'google_news','Google News')
 assert items[0]['feed_name']=='Robb Report' and items[0]['feed_homepage']=='https://robbreport.com'
def test_sec_ticker_resolution_and_annual_facts_only():
 t=parse_sec_tickers(TICKERS);assert t['RACE']==(1646972,'Ferrari N.V.')
 f=summarize_company_facts(FACTS)
 assert [r['fy'] for r in f['revenue']]==[2023,2024] and f['revenue'][-1]['value']==6677000000
 assert all(r['end'].endswith('12-31') for r in f['revenue']) and f['net_income'][-1]['value']==1526000000
def test_ifrs_foreign_issuer_facts_are_read():
 payload={"cik":1648416,"entityName":"Ferrari N.V.","facts":{"ifrs-full":{
  "Revenue":{"units":{"EUR":[{"fy":2024,"fp":"FY","form":"20-F","filed":"2025-02-21","val":6677000000,"end":"2024-12-31"}]}},
  "ProfitLoss":{"units":{"EUR":[{"fy":2024,"fp":"FY","form":"20-F","filed":"2025-02-21","val":1526000000,"end":"2024-12-31"}]}}}}}
 f=summarize_company_facts(payload)
 assert f['currency']=='EUR' and f['revenue'][-1]['value']==6677000000 and f['net_income'][-1]['value']==1526000000
def test_stooq_price_summary_is_computed_not_stated():
 rows=parse_stooq_csv(STOOQ);s=summarize_prices(rows)
 assert s['points']==2 and s['latest_close']==440.1 and s['window_change_pct']==round(100*(440.1-435.2)/435.2,1) and s['window_high']==440.1
 assert summarize_prices([])['points']==0

@pytest.mark.asyncio
async def test_company_facts_fetches_real_shapes():
 data=LuxuryDataService(client=mock_client())
 company,report=await data.company_facts('race')
 assert company['ticker']=='RACE' and company['watchlist_segment']=='automotive' and company['facts']['entity']=='Ferrari N.V.'
 assert company['prices']['points']==2 and all(r['status']=='ok' for r in report)
 with pytest.raises(ValueError,match='not a US-listed ticker'):await data.company_facts('LVMH')
@pytest.mark.asyncio
async def test_collect_evidence_splices_into_m19_brief_models():
 data=LuxuryDataService(client=mock_client())
 out=await data.collect_evidence('Ferrari','automotive','RACE')
 assert out['all_sources_free'] and out['fetch_summary']['sources_ok']>=4
 sources=[Source.model_validate(s) for s in out['sources']];signals=[Signal.model_validate({k:s[k] for k in ('signal_id','statement','source_ids','importance')}) for s in out['signals']]
 assert len(sources)>=4 and len(signals)>=2
 ids={s.source_id for s in sources}
 assert all(set(x.source_ids)<=ids for x in signals)
 assert any('reported revenue' in s.finding for s in sources) and any(s.source_id.startswith('report-') for s in sources)
 assert all(s.url.startswith('http') for s in sources)
@pytest.mark.asyncio
async def test_failed_sources_are_reported_not_faked():
 data=LuxuryDataService(client=mock_client(fail_feeds=True))
 out=await data.collect_evidence('Ferrari','automotive','RACE')
 fetchable=[f for f in LUXURY_FEEDS if f.get('verified_fetchable',True)]
 errs=[r for r in out['fetch_report'] if r['status']=='error']
 skipped=[r for r in out['fetch_report'] if r['status']=='skipped']
 assert len(errs)==len(fetchable) and out['fetch_summary']['sources_error']==len(fetchable)
 assert len(skipped)==len(LUXURY_FEEDS)-len(fetchable) and all('not spoof' in r['detail'] or 'not fetchable' in r['detail'] for r in skipped)
 assert all('simulat' not in s['finding'].lower() and 'sample' not in s['finding'].lower() for s in out['sources'])
@pytest.mark.asyncio
async def test_grounded_studio_builds_concepts_from_fetched_evidence():
 svc=LuxuryVentureService(data=LuxuryDataService(client=mock_client()))
 req=GroundedStudioRequest(brand_or_segment='Ferrari',sector='automotive',customer_job='Give owners a digital experience as crafted as the car without diluting scarcity.',constraints=['brand tone','no mass-market channel'],capabilities=[{'capability_id':'concierge-app','description':'Owner concierge with provenance records','readiness':.7}],ticker='RACE')
 out=await svc.grounded_studio(req)
 assert len(out['studio']['concepts'])==3 and out['studio']['pitch_brief']['status']=='review_only'
 assert out['studio']['side_effects']==[] and out['evidence']['fetch_summary']['evidence_items']>=4 and 'boundary' in out
@pytest.mark.asyncio
async def test_grounded_studio_refuses_thin_evidence_instead_of_faking():
 class Empty(LuxuryDataService):
  async def collect_evidence(self,*a,**k):return {'collected_on':'2026-09-25','sources':[],'signals':[],'coverage_notes':[],'fetch_report':[],'fetch_summary':{},'review_required':'x'}
 svc=LuxuryVentureService(data=Empty())
 req=GroundedStudioRequest(brand_or_segment='Ferrari',customer_job='Give owners a crafted digital experience.',constraints=['tone'],capabilities=[{'capability_id':'c','description':'demo capability','readiness':.5}])
 with pytest.raises(ValueError,match='insufficient live evidence'):await svc.grounded_studio(req)

def app_with(service):
 app=FastAPI();app.include_router(m19.router,prefix='/api/v1')
 app.dependency_overrides[m19.get_luxury_data_service]=lambda:service.data if isinstance(service,LuxuryVentureService) else service
 app.dependency_overrides[m19.get_luxury_venture_service]=lambda:service if isinstance(service,LuxuryVentureService) else LuxuryVentureService(data=service)
 return TestClient(app)
def test_source_registry_route_lists_only_free_verified_sources():
 c=app_with(LuxuryDataService(client=mock_client()))
 r=c.get('/api/v1/idea-incubator/luxury-venture-studio/sources')
 assert r.status_code==200 and r.json()['all_free'] and r.json()['no_api_keys_required']
 assert {f['feed_id'] for f in r.json()['feeds']}=={'wwd','robb_report','luxuo','purseblog'}
 assert any(not x['verified_fetchable'] for x in r.json()['reports']) and len(r.json()['listed_companies'])==len(LISTED_LUXURY_WATCHLIST)
def test_mounted_company_news_and_evidence_routes():
 c=app_with(LuxuryDataService(client=mock_client()))
 r=c.get('/api/v1/idea-incubator/luxury-venture-studio/company/RACE');assert r.status_code==200 and r.json()['company']['facts']['entity']=='Ferrari N.V.'
 assert c.get('/api/v1/idea-incubator/luxury-venture-studio/company/LVMH').status_code==422
 r=c.get('/api/v1/idea-incubator/luxury-venture-studio/news',params={'query':'luxury'});assert r.status_code==200 and r.json()['items']
 r=c.post('/api/v1/idea-incubator/luxury-venture-studio/evidence',json={'brand_or_segment':'Ferrari','sector':'automotive','ticker':'RACE'})
 assert r.status_code==200 and r.json()['fetch_summary']['evidence_items']>=4
def test_mounted_grounded_studio_route_is_review_only():
 c=app_with(LuxuryVentureService(data=LuxuryDataService(client=mock_client())))
 r=c.post('/api/v1/idea-incubator/luxury-venture-studio/grounded',json={'brand_or_segment':'Ferrari','sector':'automotive','customer_job':'Give owners a digital experience as crafted as the car.','constraints':['tone'],'capabilities':[{'capability_id':'concierge','description':'Owner concierge','readiness':.7}],'ticker':'RACE'})
 assert r.status_code==200 and r.json()['studio']['pitch_brief']['status']=='review_only' and r.json()['studio']['side_effects']==[]
def test_registry_reports_cover_real_free_reports():
 assert all(x['cost']==0 for x in FREE_REPORT_REGISTRY)
 assert any(x['report_id']=='deloitte_gpolg' and x['verified_fetchable'] for x in FREE_REPORT_REGISTRY)
 assert SOURCE_REGISTRY['coverage_notes']
