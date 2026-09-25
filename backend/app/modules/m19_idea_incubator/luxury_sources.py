"""Real, free data sources for the luxury venture studio.

Every adapter fetches live public data with no API key: SEC EDGAR XBRL company
facts and full-text filing search (US-listed companies only), Stooq daily price
history, Wikipedia/Wikidata brand records, luxury trade-press RSS feeds, and
Google News RSS search. A curated registry lists $0 market reports with an
honest per-entry fetch status. Nothing is simulated: when an upstream source
fails, the failure is recorded in fetch_report and the source contributes no
evidence. Optional env config (ATLAS_CONTACT_EMAIL) only sets the contact
identity SEC asks automated clients to declare.
"""
from __future__ import annotations
import os,re
from datetime import date
from html import unescape
from xml.etree import ElementTree
import httpx

VERIFIED_ON='2026-09-25'
LUXURY_FEEDS=(
 {'feed_id':'wwd','name':'WWD','url':'https://wwd.com/feed/','focus':'fashion, beauty and retail business','verified_fetchable':True},
 {'feed_id':'robb_report','name':'Robb Report','url':'https://robbreport.com/feed/','focus':'luxury lifestyle, automotive, hospitality','verified_fetchable':True},
 {'feed_id':'luxuo','name':'LUXUO','url':'https://luxuo.com/feed','focus':'global luxury news','verified_fetchable':True},
 {'feed_id':'purseblog','name':'PurseBlog','url':'https://purseblog.com/feed/','focus':'handbags and leather goods','verified_fetchable':False,'note':'Blocks non-browser clients (HTTP 403); Atlas does not spoof a browser, so this feed is listed but not fetched'},
)
FREE_REPORT_REGISTRY=(
 {'report_id':'deloitte_gpolg','publisher':'Deloitte','title':'Global Powers of Luxury Goods','url':'https://www.deloitte.com/global/en/Industries/consumer/analysis/gx-cb-global-powers-of-luxury-goods.html','cost':0,'verified_fetchable':True,'note':'Annual ranking of the 100 largest luxury goods companies by revenue.'},
 {'report_id':'bain_altagamma','publisher':'Bain & Company / Altagamma','title':'Luxury Goods Worldwide Market Study (press releases)','url':'https://www.bain.com/about/media-center/press-releases/','cost':0,'verified_fetchable':True,'note':'Full report is paid; press releases with headline market figures are free.'},
 {'report_id':'mckinsey_sof','publisher':'McKinsey & Company / BoF','title':'The State of Fashion','url':'https://www.mckinsey.com/industries/retail/our-insights/state-of-fashion','cost':0,'verified_fetchable':False,'note':'Free with registration; automated fetch did not complete, open in a browser.'},
 {'report_id':'bcg_altagamma','publisher':'BCG / Altagamma','title':'True-Luxury Global Consumer Insight','url':'https://www.bcg.com/publications/collections/true-luxury-global-consumer-insight','cost':0,'verified_fetchable':False,'note':'Free landing page blocks automated fetches (HTTP 403); open in a browser.'},
)
# ticker -> (name, sector, SEC CIK). CIKs verified 2026-09-25 against data.sec.gov submissions records.
LISTED_LUXURY_WATCHLIST={
 'RACE':('Ferrari N.V.','automotive',1648416),'TPR':('Tapestry, Inc.','fashion',1116132),'CPRI':('Capri Holdings','fashion',1530721),
 'RL':('Ralph Lauren','fashion',1037038),'EL':('The Estee Lauder Companies','fashion',1001250),'MOV':('Movado Group','jewelry',72573),
 'GOOS':('Canada Goose','fashion',1690511),'SIG':('Signet Jewelers','jewelry',832988),'SHOO':('Steven Madden','fashion',913241),
 'RH':('RH','other',1528849),'REAL':('The RealReal','other',1573221),'BRLT':('Brilliant Earth','jewelry',1866757),
 'MAR':('Marriott International','luxury_hospitality',1048286),'HLT':('Hilton','luxury_hospitality',1585689),'H':('Hyatt','luxury_hospitality',1468174),
}
SOURCE_REGISTRY={'all_free':True,'no_api_keys_required':True,'verified_on':VERIFIED_ON,
 'feeds':list(LUXURY_FEEDS),'reports':list(FREE_REPORT_REGISTRY),
 'listed_companies':[{'ticker':t,'name':n,'sector':sec,'cik':cik} for t,(n,sec,cik) in LISTED_LUXURY_WATCHLIST.items()],
 'coverage_notes':['SEC EDGAR and Stooq cover US-listed companies only; European houses (LVMH, Hermes, Kering, Richemont, Moncler, Burberry) and Sanrio have no SEC filings and are covered through news feeds, Wikipedia/Wikidata and the free report registry.',
  'Google News RSS item links are Google redirect URLs; the publisher name and homepage are captured separately.',
  'Every fetched item carries its real URL and fetch status; failed sources are reported, never replaced with invented content.','SEC EDGAR refuses automated clients whose User-Agent lacks an email-shaped contact: set ATLAS_CONTACT_EMAIL to a real address for the operator, otherwise SEC evidence is reported as unavailable rather than fetched under a fabricated identity.']}
GOOGLE_NEWS_RSS='https://news.google.com/rss/search'
SEC_TICKERS='https://www.sec.gov/files/company_tickers.json'
SEC_FACTS='https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
SEC_FULLTEXT='https://efts.sec.gov/LATEST/search-index'
STOOQ_CSV='https://stooq.com/q/d/l/'
WIKIPEDIA_SUMMARY='https://en.wikipedia.org/api/rest_v1/page/summary/{title}'
WIKIDATA_SEARCH='https://www.wikidata.org/w/api.php'

def _clean(text:str,limit:int)->str:
 return re.sub(r'\s+',' ',unescape(re.sub(r'<[^>]+>',' ',text or ''))).strip()[:limit]

def parse_rss(xml_text:str,source_id:str,source_name:str,limit:int=25)->list[dict]:
 try:root=ElementTree.fromstring(xml_text)
 except ElementTree.ParseError:return []
 items=[]
 for item in root.iter():
  if not item.tag.endswith('item'):continue
  fields={}
  for child in item:
   tag=child.tag.split('}')[-1]
   if tag in ('title','link','pubDate','date','description','source') and child.text:fields.setdefault(tag,child.text)
   if tag=='source' and child.text:fields['source_url']=child.attrib.get('url','')
  title=_clean(fields.get('title',''),300)
  if not title:continue
  tagged=tag_topics(title+' '+_clean(fields.get('description',''),500))
  items.append({'topics':tagged,'title':title,'url':(fields.get('link','') or fields.get('source_url','')).strip(),'published':_clean(fields.get('pubDate',fields.get('date','')),40),'summary':_clean(fields.get('description',''),500),'feed_id':source_id,'feed_name':fields.get('source',source_name) if source_id=='google_news' else source_name,'feed_homepage':fields.get('source_url','')})
  if len(items)>=limit:break
 return items

def parse_sec_tickers(payload:dict)->dict:
 return {str(v.get('ticker','')).upper():(int(v['cik_str']),str(v.get('title',''))) for v in payload.values() if isinstance(v,dict) and v.get('ticker') and v.get('cik_str')}

_REVENUE_KEYS=(('us-gaap','RevenueFromContractWithCustomerExcludingAssessedTax'),('us-gaap','Revenues'),('us-gaap','RevenueFromContractWithCustomerIncludingAssessedTax'),('us-gaap','SalesRevenueNet'),('ifrs-full','Revenue'))
_INCOME_KEYS=(('us-gaap','NetIncomeLoss'),('us-gaap','ProfitLoss'),('ifrs-full','ProfitLoss'))
def _annual(facts:dict,keys:tuple)->tuple[str,list[dict]]:
 all_facts=facts.get('facts',{})
 for namespace,key in keys:
  node=all_facts.get(namespace,{}).get(key)
  if not node:continue
  units=node.get('units',{});unit='USD' if 'USD' in units else next(iter(units),None)
  if not unit:continue
  seen={}
  for row in units[unit]:
   if row.get('fp')!='FY' or row.get('form','').split('/')[0] not in ('10-K','20-F','40-F','10-K/A'):continue
   end=row.get('end','')
   if end and (end not in seen or row.get('filed','')>=seen[end].get('filed','')):seen[end]=row
  series=[{'fy':r.get('fy'),'value':r.get('val'),'end':e,'filed':r.get('filed','')} for e,r in sorted(seen.items())]
  if series:return unit,series[-5:]
 return '',[]

def summarize_company_facts(payload:dict)->dict:
 currency,revenue=_annual(payload,_REVENUE_KEYS);_,net_income=_annual(payload,_INCOME_KEYS)
 return {'entity':payload.get('entityName',''),'currency':currency,'revenue':revenue,'net_income':net_income,'cik':payload.get('cik')}

def parse_stooq_csv(text:str)->list[dict]:
 rows=[]
 for line in text.strip().splitlines()[1:]:
  parts=line.split(',')
  if len(parts)>=5:
   try:rows.append({'date':parts[0],'close':float(parts[4])})
   except ValueError:continue
 return rows

def summarize_prices(rows:list[dict])->dict:
 if not rows:return {'points':0}
 first,last=rows[0],rows[-1];change=round(100*(last['close']-first['close'])/first['close'],1) if first['close'] else None
 return {'points':len(rows),'window_start':first['date'],'window_end':last['date'],'latest_close':last['close'],'window_change_pct':change,'window_high':max(r['close'] for r in rows),'window_low':min(r['close'] for r in rows),'currency_note':'Stooq quotes US listings in USD.'}

def parse_wikipedia_summary(payload:dict)->dict:
 return {'title':payload.get('title',''),'description':payload.get('description',''),'extract':_clean(payload.get('extract',''),800),'url':payload.get('content_urls',{}).get('desktop',{}).get('page','')}

class LuxuryDataService:
 def __init__(self,client:httpx.AsyncClient|None=None,contact:str|None=None):
  self._client=client;self.contact=contact or os.environ.get('ATLAS_CONTACT_EMAIL')
 def _headers(self)->dict:
  # Truthful product identification; a real contact email is appended only when the operator configures one. SEC refuses automated clients without an email-shaped contact, so EDGAR fetches fail (and are reported) until ATLAS_CONTACT_EMAIL is set.
  ua='AtlasAI/1.0 (atlas-ai research client)'+(f'; contact: {self.contact}' if self.contact else '')
  return {'User-Agent':ua}
 async def _get(self,url,**kw)->httpx.Response:
  kw.setdefault('headers',self._headers())
  if self._client is not None:
   r=await self._client.get(url,**kw)
  else:
   async with httpx.AsyncClient(timeout=45,follow_redirects=True) as c:r=await c.get(url,**kw)
  r.raise_for_status();return r
 async def news(self,query:str,limit:int=15)->tuple[list[dict],list[dict]]:
  report=[];items=[]
  try:
   r=await self._get(GOOGLE_NEWS_RSS,params={'q':query,'hl':'en-US','gl':'US','ceid':'US:en'})
   found=parse_rss(r.text,'google_news','Google News',limit);items+=found;report.append({'source':'google_news_rss','status':'ok','items':len(found)})
  except Exception as e:report.append({'source':'google_news_rss','status':'error','detail':str(e)[:200]})
  needle=query.lower()
  for feed in LUXURY_FEEDS:
   if not feed.get('verified_fetchable',True):report.append({'source':feed['feed_id'],'status':'skipped','detail':feed.get('note','not fetchable by automation')});continue
   try:
    r=await self._get(feed['url']);found=[x for x in parse_rss(r.text,feed['feed_id'],feed['name']) if needle in (x['title']+' '+x['summary']).lower()]
    items+=found;report.append({'source':feed['feed_id'],'status':'ok','items':len(found)})
   except Exception as e:report.append({'source':feed['feed_id'],'status':'error','detail':str(e)[:200]})
  items.sort(key=lambda x:x['published'],reverse=True)
  return items[:limit],report
 async def company_facts(self,ticker:str)->tuple[dict,list[dict]]:
  ticker=ticker.upper().strip()
  if not re.fullmatch(r'[A-Z]{1,6}',ticker):raise ValueError('ticker must be 1-6 letters')
  report=[]
  watch=LISTED_LUXURY_WATCHLIST.get(ticker)
  if watch:sec_title,cik=watch[0],watch[2]
  else:
   try:tickers=parse_sec_tickers((await self._get(SEC_TICKERS)).json())
   except Exception as e:raise ValueError(f'{ticker} is not in the curated luxury watchlist and SEC ticker resolution needs a declared contact (set ATLAS_CONTACT_EMAIL): {str(e)[:120]}') from e
   if ticker not in tickers:raise ValueError(f'{ticker} is not a US-listed ticker in the SEC company list')
   cik,sec_title=tickers[ticker]
  facts=summarize_company_facts((await self._get(SEC_FACTS.format(cik=str(cik).zfill(10)))).json())
  report.append({'source':'sec_edgar_xbrl','status':'ok','entity':facts['entity']})
  try:
   csv_text=(await self._get(STOOQ_CSV,params={'s':ticker.lower()+'.us','i':'d'})).text
   if not csv_text.startswith('Date,'):raise ValueError('stooq served a browser-verification page instead of CSV data')
   prices=summarize_prices(parse_stooq_csv(csv_text))
   report.append({'source':'stooq_prices','status':'ok','points':prices.get('points',0)})
  except Exception as e:prices={'points':0};report.append({'source':'stooq_prices','status':'error','detail':str(e)[:200]})
  facts.update(_growth_margins(facts))
  return {'ticker':ticker,'sec_title':sec_title,'cik':cik,'watchlist_segment':watch[1] if watch else None,'watchlist_note':None if watch else 'Not in the curated luxury watchlist; facts are still real SEC/Stooq data.','facts':facts,'prices':prices,'source_urls':{'sec_companyfacts':SEC_FACTS.format(cik=str(cik).zfill(10)),'stooq':f'https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d'}},report
 async def brand_profile(self,name:str)->tuple[dict,list[dict]]:
  report=[];profile={'query':name}
  try:
   r=await self._get(WIKIPEDIA_SUMMARY.format(title=name.replace(' ','_')))
   profile['wikipedia']=parse_wikipedia_summary(r.json());report.append({'source':'wikipedia','status':'ok'})
  except Exception as e:report.append({'source':'wikipedia','status':'error','detail':str(e)[:200]})
  try:
   r=await self._get(WIKIDATA_SEARCH,params={'action':'wbsearchentities','search':name,'language':'en','format':'json','limit':'3'})
   hits=[{'id':h['id'],'label':h.get('label',''),'description':h.get('description',''),'url':'https://www.wikidata.org/wiki/'+h['id']} for h in r.json().get('search',[])]
   profile['wikidata']=hits;report.append({'source':'wikidata','status':'ok','items':len(hits)})
  except Exception as e:report.append({'source':'wikidata','status':'error','detail':str(e)[:200]})
  return profile,report
 async def collect_evidence(self,brand_or_segment:str,sector:str='other',ticker:str|None=None,limit:int=12)->dict:
  today=date.today().isoformat();sources=[];signals=[];fetch_report=[];notes=[]
  def add_source(sid,url,title,observed,finding,weight):
   sources.append({'source_id':sid,'url':url,'title':title[:300],'observed_at':(observed or today)[:40],'finding':finding[:2000]})
   statement=finding.split('. ')[0].strip()
   if len(statement)>=10:signals.append({'signal_id':'auto-'+sid,'statement':statement[:300],'source_ids':[sid],'importance':weight,'auto_extracted':True})
  if ticker:
   try:
    company,rep=await self.company_facts(ticker);fetch_report+=rep
    f=company['facts']
    if f['revenue']:
     rev=f['revenue'][-1];finding=f"{f['entity']} ({company['ticker']}) reported revenue of {rev['value']:,.0f} {f['currency']} for the year ended {rev['end']} (annual filing)"
     if len(f['revenue'])>1:prev=f['revenue'][-2];finding+=f", versus {prev['value']:,.0f} {f['currency']} for the year ended {prev['end']}"
     if f['net_income']:ni=f['net_income'][-1];finding+=f"; net income {ni['value']:,.0f} for the year ended {ni['end']}"
     p=company['prices']
     if p.get('points'):finding+=f". Latest close {p['latest_close']:,.2f} ({p['window_change_pct']:+.1f}% across {p['points']} trading days ending {p['window_end']}, Stooq)"
     add_source('sec-'+ticker.lower(),company['source_urls']['sec_companyfacts'],f'SEC XBRL company facts: {f["entity"]}',today,finding+'.',0.9)
    else:notes.append(f'{ticker} has an SEC record but no annual revenue series in the XBRL company-facts API.')
   except ValueError as e:raise
   except Exception as e:fetch_report.append({'source':'sec_edgar_xbrl','status':'error','detail':str(e)[:200]})
  else:notes.append('No ticker supplied: SEC EDGAR and price coverage apply to US-listed companies only; evidence below comes from news, reference records and free reports.')
  profile,rep=await self.brand_profile(brand_or_segment);fetch_report+=rep
  wiki=profile.get('wikipedia') or {}
  if wiki.get('extract') and wiki.get('url'):add_source('wikipedia-brand',wiki['url'],'Wikipedia: '+wiki['title'],today,wiki['extract'],0.6)
  for hit in (profile.get('wikidata') or [])[:1]:
   if hit.get('description'):add_source('wikidata-'+hit['id'].lower(),hit['url'],f"Wikidata {hit['id']}: {hit['label']}",today,f"{hit['label']} - {hit['description']}. Structured entity record on Wikidata.",0.6)
  query=brand_or_segment if 'luxury' in brand_or_segment.lower() else brand_or_segment+' luxury'
  items,rep=await self.news(query,limit);fetch_report+=rep
  for i,item in enumerate(items):
   finding=item['title']+((': '+item['summary']) if item['summary'] else '')
   add_source(f'news-{i+1}',item['url'] or item.get('feed_homepage','') or 'https://news.google.com/',item['title'],item['published'] or today,finding,0.5)
  for report_entry in FREE_REPORT_REGISTRY[:2]:
   status='landing page verified fetchable' if report_entry['verified_fetchable'] else 'free for humans but not verified fetchable by automation'
   add_source('report-'+report_entry['report_id'],report_entry['url'],f"{report_entry['publisher']}: {report_entry['title']}",VERIFIED_ON,f"Free market report: {report_entry['title']} ({report_entry['publisher']}); {status} as of {VERIFIED_ON}. {report_entry['note']}",0.7)
  ok=sum(1 for r in fetch_report if r['status']=='ok');err=sum(1 for r in fetch_report if r['status']=='error')
  return {'brand_or_segment':brand_or_segment,'sector':sector,'collected_on':today,'sources':sources[:30],'signals':signals[:10],'coverage_notes':notes+SOURCE_REGISTRY['coverage_notes'],'fetch_report':fetch_report,'fetch_summary':{'sources_ok':ok,'sources_error':err,'evidence_items':len(sources)},'all_sources_free':True,'review_required':'Auto-extracted signals quote fetched findings; review and adjust importance before generating concepts.'}

SEC_SUBMISSIONS='https://data.sec.gov/submissions/CIK{cik}.json'
_TOPIC_RULES=(('earnings',('revenue','earnings','profit','sales','shares','dividend','results','quarter')),('product_launch',('unveil','launch','debut','new ','collection','flagship')),('retail_expansion',('boutique','store','opening','workshop','manufacture','atelier')),('leadership',('ceo','creative director','appoint','depart','hire')),('collaboration',('collab','partnership','teams up',' x ')),('market_trend',('demand','market','china','growth','slow','luxury industry')))
def tag_topics(text:str)->list[str]:
 t=text.lower();tags=[k for k,words in _TOPIC_RULES if any(w in t for w in words)]
 return tags or ['general']

def _growth_margins(facts:dict)->dict:
 out={}
 rev=facts.get('revenue',[])
 if len(rev)>1 and rev[-2]['value']:out['revenue_yoy_pct']=round(100*(rev[-1]['value']-rev[-2]['value'])/rev[-2]['value'],1)
 ni=facts.get('net_income',[])
 if rev and ni and rev[-1]['value']:out['net_margin_pct']=round(100*ni[-1]['value']/rev[-1]['value'],1)
 return out

async def _compare_entry(self,ticker):
 company,_=await self.company_facts(ticker)
 f=company['facts'];latest=f['revenue'][-1] if f['revenue'] else {}
 return {'ticker':company['ticker'],'entity':f['entity'],'currency':f['currency'],'latest_revenue':latest.get('value'),'period_end':latest.get('end'),**_growth_margins(f),'price_change_pct':company['prices'].get('window_change_pct')}


async def _company_compare(self,tickers:list[str])->dict:
 entries=[];report=[]
 for t in tickers:
  try:entries.append(await _compare_entry(self,t));report.append({'ticker':t,'status':'ok'})
  except Exception as e:report.append({'ticker':t,'status':'error','detail':str(e)[:160]})
 currencies={e['currency'] for e in entries if e.get('currency')}
 return {"companies":entries,"fetch_report":report,"mixed_currencies":len(currencies)>1,"currency_note":("Figures are reported in each company's own filing currency; no FX conversion is applied." if len(currencies)>1 else "All figures share one filing currency.")}
async def _filing_search(self,query:str,limit:int=10)->tuple[list[dict],list[dict]]:
 r=await self._get(SEC_FULLTEXT,params={'q':f'"{query}"','dateRange':'custom','startdt':'2015-01-01','from':0,'size':limit})
 hits=[]
 for h in r.json().get('hits',{}).get('hits',[]):
  s=h.get('_source',{});adsh=s.get('adsh','');cik=(s.get('ciks') or [''])[0]
  hits.append({'form':s.get('form',''),'filed':s.get('file_date',''),'company':', '.join(s.get('display_names',[])[:2]),'url':f'https://www.sec.gov/Archives/edgar/data/{str(cik).lstrip("0")}/{adsh.replace("-","")}/'})
 return hits[:limit],[{'source':'sec_edgar_fulltext','status':'ok','items':len(hits[:limit])}]
async def _company_contact(self,ticker:str)->dict:
 ticker=ticker.upper().strip()
 if not re.fullmatch(r'[A-Z]{1,6}',ticker):raise ValueError('ticker must be 1-6 letters')
 watch=LISTED_LUXURY_WATCHLIST.get(ticker)
 if watch:cik=watch[2]
 else:
  tickers=parse_sec_tickers((await self._get(SEC_TICKERS)).json())
  if ticker not in tickers:raise ValueError(f'{ticker} is not a US-listed ticker in the SEC company list')
  cik=tickers[ticker][0]
 d=(await self._get(SEC_SUBMISSIONS.format(cik=str(cik).zfill(10)))).json()
 addr=d.get('addresses',{}).get('business',{})
 return {'ticker':ticker,'entity':d.get('name',''),'exchange':d.get('exchanges',[]),'industry':d.get('sicDescription',''),'phone':d.get('phone',''),'website':d.get('website',''),'business_address':{k:v for k,v in addr.items() if v},'source_url':SEC_SUBMISSIONS.format(cik=str(d.get('cik','')).zfill(10)),'note':'Public SEC registrant data; investor relations contact details belong on the company website when the SEC website field is empty.'}
async def _mentions(self,query:str,limit:int=25)->dict:
 items,report=await self.news(query,limit)
 per_feed={};topics={}
 for x in items:
  per_feed[x['feed_id']]=per_feed.get(x['feed_id'],0)+1
  for t in x.get('topics',[]):topics[t]=topics.get(t,0)+1
 return {'query':query,'mentions':len(items),'per_feed':per_feed,'per_topic':topics,'fetch_report':report}
async def _sources_health(self)->dict:
 import time
 checks=[]
 for feed in LUXURY_FEEDS:
  if not feed.get('verified_fetchable',True):checks.append({'source':feed['feed_id'],'status':'skipped','detail':feed.get('note','')});continue
  start=time.monotonic()
  try:
   r=await self._get(feed['url']);n=len(parse_rss(r.text,feed['feed_id'],feed['name'],5));checks.append({'source':feed['feed_id'],'status':'ok' if n else 'empty','items_sampled':n,'latency_ms':round(1000*(time.monotonic()-start))})
  except Exception as e:checks.append({'source':feed['feed_id'],'status':'error','detail':str(e)[:160]})
 return {'checked':checks,'verified_on_constant':VERIFIED_ON}
LuxuryDataService.company_compare=_company_compare
LuxuryDataService.filing_search=_filing_search
LuxuryDataService.company_contact=_company_contact
LuxuryDataService.mentions=_mentions
LuxuryDataService.sources_health=_sources_health
