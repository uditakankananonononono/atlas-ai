"""T1-T4 bounded ingestion and advice preparation. No sending or training runtime."""
from __future__ import annotations
import hashlib
import ipaddress
import json
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET

class Refusal(ValueError):
    pass

def public_url(url):
    if not isinstance(url,str) or len(url)>4096 or any(c.isspace() for c in url):
        raise Refusal('TREND_REFUSED_SCRAPE')
    p=urlsplit(url)
    try: port=p.port
    except ValueError: raise Refusal('TREND_REFUSED_SCRAPE')
    if p.scheme!='https' or not p.hostname or p.username or p.password or port not in (None,443):
        raise Refusal('TREND_REFUSED_SCRAPE')
    host=p.hostname.lower()
    if host.endswith('.') or re.fullmatch(r'[0-9.]+',host) and host.count('.')!=3:
        raise Refusal('TREND_REFUSED_SCRAPE')
    if '.' not in host or host.endswith(('.local','.internal','.localhost')):
        raise Refusal('TREND_REFUSED_SCRAPE')
    try:
        ip=ipaddress.ip_address(host)
        if not ip.is_global: raise Refusal('TREND_REFUSED_SCRAPE')
    except ValueError as exc:
        if isinstance(exc,Refusal):raise
    return url

@dataclass(frozen=True)
class SourcePermit:
    source_id: str
    origin: str
    license: str
    terms_url: str
    checked_at: str
    terms_allowed: bool
    def allows(self,url):
        public_url(url);public_url(self.origin);public_url(self.terms_url)
        if self.terms_allowed is not True or not self.checked_at or self.license not in ('CC0','CC-BY-4.0','CC-BY-SA-4.0','public-domain','permission-granted'):
            raise Refusal('TREND_REFUSED_SCRAPE')
        if urlsplit(url).netloc.lower()!=urlsplit(self.origin).netloc.lower():raise Refusal('TREND_REFUSED_SCRAPE')

@dataclass(frozen=True)
class FetchResponse:
    status: int
    text: str
    headers: dict

class PublicFetcher:
    """Caller supplies a bounded, no-redirect transport. No credentials accepted.

    Network integration deliberately not enabled in HTTP routes. Deployments must
    provide a transport with DNS/IP pinning, content-type and compressed-size limits.
    """
    def __init__(self, permits, transport, clock=time.monotonic, interval=60, limit=100000):
        if interval<60 or not 1<=limit<=100000:raise Refusal('TREND_REFUSED_LIMIT')
        self.permits=permits;self.transport=transport;self.clock=clock;self.interval=interval;self.limit=limit;self.last={}
    def fetch(self,source_id,url):
        public_url(url)
        permit=self.permits.get(source_id)
        if permit is None:raise Refusal('TREND_REFUSED_SCRAPE')
        permit.allows(url)
        host=urlsplit(url).netloc;now=self.clock()
        if now-self.last.get(host,float('-inf'))<self.interval:raise Refusal('TREND_REFUSED_RATELIMIT')
        self.last[host]=now
        robots=self.transport(permit.origin.rstrip('/')+'/robots.txt',self.limit)
        if robots.status!=200 or len(robots.text.encode())>self.limit:raise Refusal('TREND_REFUSED_SCRAPE')
        rp=RobotFileParser();rp.parse(robots.text.splitlines())
        if not rp.can_fetch('AtlasPublicCorpus',url):raise Refusal('TREND_REFUSED_SCRAPE')
        delay=rp.crawl_delay('AtlasPublicCorpus') or rp.crawl_delay('*') or 0
        if delay>self.interval:raise Refusal('TREND_REFUSED_RATELIMIT')
        reply=self.transport(url,self.limit)
        if reply.status!=200:raise Refusal('TREND_REFUSED_FETCH')
        if len(reply.text.encode())>self.limit:raise Refusal('TREND_REFUSED_OVERSIZE')
        return reply.text

class _Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
        if tag in ('p','div','br','li','h1','h2'):self.parts.append('\n')
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)

def plain(text):
    p=_Text();p.feed(text);return ''.join(p.parts).strip()

def registry_report():
    root=Path(__file__).resolve().parents[4]/'config/training_sources'
    cases=json.loads((root/'college_candidates.json').read_text())
    books=json.loads((root/'book_collections.json').read_text())
    return {'college_candidate_sites':len({urlsplit(x['url']).hostname for x in cases}), 'college_verified_sites':sum(x['status']=='verified' for x in cases),
            'book_collections':len(books),'book_independent_domains':len({urlsplit(x['url']).hostname for x in books}), 'ingested_records':0}

def shared_policy(payload,prefix):
    try:
        from app.modules.c30.policy import check
    except ImportError as exc:raise Refusal(prefix+'_REFUSED_UNAVAILABLE') from exc
    # check is canonical deny-only compatibility API; no implied offline allow.
    action=next((name for name in ('spend','outreach','fakeacct','autopost','scrape','trade') if payload.get(name)),payload.get('type','analyze'))
    check(action,prefix)

class TrainingUnits:
    def __init__(self,permits=None,policy=None):
        self.permits=dict(permits or {});self.policy=policy
    def _policy(self,action,prefix):
        if not isinstance(action,dict) or any(not isinstance(k,str) or isinstance(v,(dict,list,tuple,set)) for k,v in action.items()):
            raise Refusal(prefix+'_REFUSED_ACTION_SHAPE')
        try:result=self.policy(action) if self.policy is not None else shared_policy(action,prefix)
        except ValueError as exc:raise Refusal(str(exc)) from exc
        if not (result is None or result is True or isinstance(result,dict) and result.get('allowed') is True):
            raise Refusal(prefix+'_REFUSED_ACTION')
    def _records(self,payload,prefix):
        records=payload.get('records',[])
        if not isinstance(records,list) or len(records)>500:raise Refusal(prefix+'_REFUSED_OVERSIZE')
        out=[];seen=set()
        for r in records:
            if not isinstance(r,dict):raise Refusal(prefix+'_REFUSED_SCHEMA')
            if r.get('paywalled'):raise Refusal(prefix+'_REFUSED_PAYWALL')
            if r.get('piracy'):raise Refusal('TREND_REFUSED_PIRACY')
            if r.get('credentials') or r.get('logged_in'):raise Refusal(prefix+'_REFUSED_SCRAPE')
            permit=self.permits.get(r.get('source_id'))
            if permit is None:raise Refusal(prefix+'_REFUSED_SCRAPE')
            try:permit.allows(r.get('url'))
            except Refusal as exc:raise Refusal(prefix+'_REFUSED_SCRAPE') from exc
            text=r.get('text')
            if not isinstance(text,str) or len(text.encode())>100000:raise Refusal(prefix+'_REFUSED_OVERSIZE')
            if not isinstance(r.get('as_of'),str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',r['as_of']):raise Refusal(prefix+'_REFUSED_DATE')
            digest=hashlib.sha256(text.encode()).hexdigest()
            if (r['source_id'],digest) in seen:continue
            seen.add((r['source_id'],digest))
            out.append({'source_id':r['source_id'],'url':r['url'],'license':permit.license,'terms_url':permit.terms_url,
                        'rights_checked_at':permit.checked_at,'as_of':r['as_of'],'sha256':digest,'text':plain(text)})
        return out
    def run(self,unit,payload):
        if unit not in ('T1','T2','T3','T4') or not isinstance(payload,dict):raise Refusal('TREND_REFUSED_SCHEMA')
        if unit=='T2':return self._search(payload)
        prefix={'T1':'APPLY','T3':'TREND','T4':'FLEET'}[unit]
        records=self._records(payload,prefix)
        log=[]
        if unit=='T4':
            if not records:raise Refusal('FLEET_REFUSED_NOADVICE')
            log.append({'stage':'advice','sources':[r['url'] for r in records],'summaries':[r['text'][:500] for r in records]})
        self._policy(payload.get('action',{}),prefix)
        result={'unit':unit,'scope':{'implemented':'bounded supplied-source normalization and preparation',
                'not_implemented':['model training','live accounts','automatic online actions','complete internet coverage'],
                'data_source':'supplied licensed documents','as_of':max((r['as_of'] for r in records),default=None)},'records':records}
        if unit=='T1':
            for r in records:
                text=r.pop('text');r['stats']=dict(re.findall(r'(?im)^(SAT|ACT|GPA):\s*([^\n]+)',text))
                r['outcomes']=re.findall(r'(?im)^Outcome:\s*([^\n]+)',text)
                r['essay_summary']=(' '.join(text.split())[:500] if text else '')
                r['summary_method']='bounded extractive excerpt, not generative';r['outcome_verified']=False
            result['ingested_sites']=len({urlsplit(r['url']).hostname for r in records})
        elif unit=='T3':
            result['concept_candidates']=[{'technique':line.strip()[:500],'source_url':r['url'],'source_sha256':r['sha256'],'status':'candidate_not_installed'} for r in records for line in r['text'].splitlines() if re.search(r'\b(always|test|verify|compare|practice|avoid|measure)\b',line,re.I)][:500]
            result['model_trained']=False
        else:
            log.extend([{'stage':'policy','status':'passed'},{'stage':'prepared','action':payload.get('action',{})}])
            result.update(status='prepared_only',log=log,task=payload.get('task',''))
        return result
    def _search(self,p):
        kind=p.get('kind');content=p.get('content')
        if kind not in ('blog','podcast','git') or not isinstance(content,str):raise Refusal('TREND_REFUSED_SCHEMA')
        self._records({'records':[{'source_id':p.get('source_id'),'url':p.get('url'),'text':content,'as_of':p.get('as_of'), **{flag:p.get(flag) for flag in ('paywalled','piracy','credentials','logged_in')}}]},'TREND')
        self._policy(p.get('action',{}),'TREND');rows=[]
        query=p.get('query','')
        if not isinstance(query,str) or len(query)>1000:raise Refusal('TREND_REFUSED_SCHEMA')
        try:
            if kind=='git':
                data=json.loads(content)
                for x in data.get('items',[]):rows.append({'title':x.get('name',''),'url':x.get('html_url',''),'summary':x.get('description') or ''})
            else:
                if '<!DOCTYPE' in content.upper() or '<!ENTITY' in content.upper():raise Refusal('TREND_REFUSED_XML')
                root=ET.fromstring(content)
                for item in root.iter():
                    if item.tag.split('}')[-1] not in ('item','entry'):continue
                    row={'title':'','url':'','summary':''}
                    for c in item:
                        tag=c.tag.split('}')[-1]
                        if tag=='title':row['title']=c.text or ''
                        if tag=='link':row['url']=c.get('href') or c.text or ''
                        if tag in ('description','summary'):row['summary']=plain(c.text or '')[:500]
                        if tag=='transcript':row.update(transcript_url=c.get('url'),transcript_ingested=False)
                    rows.append(row)
        except (ET.ParseError,ValueError,TypeError,AttributeError) as exc:
            if isinstance(exc,Refusal):raise
            raise Refusal('TREND_REFUSED_PARSE') from exc
        accepted=[]
        for r in rows:
            for field in ('url','transcript_url'):
                if r.get(field):
                    try:public_url(r[field])
                    except Refusal:r[field]=''
            if not r.get('url') and not r.get('transcript_url'):continue
            if all(term in (str(r['title'])+' '+str(r['summary'])).lower() for term in query.lower().split()):accepted.append(r)
        return {'unit':'T2','kind':kind,'results':accepted[:100],'matched_in_input':len(accepted),
                'scope':{'implemented':'RSS/Atom and GitHub public-search-response adapters over supplied payloads','not_implemented':['live GitHub credentials','automatic transcript retrieval','unbounded crawling'], 'data_source':p['url'],'as_of':p['as_of']}}
