"""Free, official-registry and public-site discovery collectors.

Package registries (GitHub/PyPI/npm) live here; the wider source set
(blog sites, podcast sites, git hosts, RSS/Atom feeds, optional keyed
Podcast Index) lives in ``sources.py``. ``default_collectors`` returns
both groups; every collector also carries a ``kind`` attribute so callers
can filter repositories vs blogs vs podcasts.
"""
from __future__ import annotations
import json
from urllib.parse import quote_plus
from urllib.request import Request,urlopen
from .sources import _recency_score, default_source_collectors, honest_signals
class JsonCollector:
 def __init__(self,name,url,parse,kind="package"):self.name=name;self.url=url;self.parse=parse;self.kind=kind
 async def collect(self,query):
  import asyncio
  def fetch():
   request=Request(self.url.format(query=quote_plus(query)),headers={'User-Agent':'AtlasAI-ToolsHub/1.0','Accept':'application/json'})
   with urlopen(request,timeout=10) as r:return json.load(r)
  payload=await asyncio.to_thread(fetch)
  for item in self.parse(payload):yield honest_signals(item)
def _github(p):
 for x in p.get('items',[])[:20]:yield {'name':x['full_name'],'url':x['html_url'],'summary':x.get('description') or '', 'version':None,'license':(x.get('license') or {}).get('spdx_id'),'maintenance':.1 if x.get('archived') else _recency_score(x.get('pushed_at') or x.get('updated_at')),'security':.6,'fit':.7,'novelty':.5,'evidence':[{'stars':x.get('stargazers_count',0),'updated_at':x.get('updated_at'),'pushed_at':x.get('pushed_at')}], 'permissions':[], 'kind':'repository'}
PYPI_SIMPLE_URL='https://pypi.org/simple/'
import re as _re
_PYPI_NAME=_re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$')
class _HttpsPypiRedirects:
 """urllib redirect handler: only https redirects to pypi.org / files.pythonhosted.org are followed."""
 @staticmethod
 def build():
  from urllib.request import HTTPRedirectHandler,build_opener
  from urllib.parse import urlparse
  class H(HTTPRedirectHandler):
   def redirect_request(self,req,fp,code,msg,headers,newurl):
    u=urlparse(newurl)
    if u.scheme!='https' or u.hostname not in ('pypi.org','files.pythonhosted.org'):
     raise ValueError(f'refusing redirect to {newurl[:80]}')
    return super().redirect_request(req,fp,code,msg,headers,newurl)
  return build_opener(H)
MAX_PYPI_NAME=256  # engineering bound, NOT a PyPI rule: longest name observed in the 2026-10-04 index was 188 chars
class PypiNameCollector:
 """PyPI has NO search API (the /search/ page is HTML only). The supported official interface is the Simple index
 (PEP 691 JSON, all project names, ~44MB raw / ~10MB gzip on 2026-10-04). This collector therefore does NAME-ONLY
 matching against that index (exact > prefix > substring > shorter first). It does not search descriptions or keywords,
 and the maintenance/security/fit/novelty signals are NOT measured (reported as 0 = no signal, flagged unmeasured)."""
 kind='package'
 MAX_BYTES=100*1024*1024  # decompressed cap
 FAIL_COOLDOWN=60.0
 def __init__(self,fetch=None,ttl=3600):
  import threading
  self.name='pypi';self.url=PYPI_SIMPLE_URL;self._fetch=fetch;self._ttl=ttl;self._cache=(0.0,'');self._lock=threading.Lock();self._fail=(0.0,None);self.rejected_names=0
 def _gunzip(self,r):
  import zlib
  d=zlib.decompressobj(31);out=bytearray()
  while not d.eof:
   chunk=r.read(1<<20)
   if not chunk:raise ValueError('truncated gzip response from PyPI simple index')
   out+=d.decompress(chunk,self.MAX_BYTES+1-len(out))
   if len(out)>self.MAX_BYTES:break
  return bytes(out)
 def _read(self):
  if self._fetch:
   return json.dumps(self._fetch(self.url)).encode()
  request=Request(self.url,headers={'User-Agent':'AtlasAI-ToolsHub/1.0','Accept':'application/vnd.pypi.simple.v1+json','Accept-Encoding':'gzip'})
  with _HttpsPypiRedirects.build().open(request,timeout=30) as r:
   raw=self._gunzip(r) if r.headers.get('Content-Encoding')=='gzip' else r.read(self.MAX_BYTES+1)
  if len(raw)>self.MAX_BYTES:raise ValueError('PyPI simple index exceeds the size cap; refusing to parse')
  return raw
 def _parse(self,raw):
  """Structural, incremental parse: meta object is parsed with json, then each element of the top-level
  "projects" array is decoded one at a time with raw_decode (no full 900k-dict tree). Unsupported shape is refused."""
  text=raw.decode('utf-8','strict')
  k=text.find('"projects"')
  if not text.lstrip().startswith('{') or k<0:raise ValueError('PyPI simple index shape not recognised (JSON object with projects)')
  try:meta=json.loads(text[:k].rstrip().rstrip(',')+'}')
  except ValueError:raise ValueError('PyPI simple index shape not recognised (projects is not a top-level key)') from None
  version=str(((meta or {}).get('meta') or {}).get('api-version',''))
  if not version.startswith('1.'):raise ValueError('PyPI simple index shape not recognised (need meta.api-version 1.x)')
  pos=text.find('[',k)
  if pos<0:raise ValueError('PyPI simple index projects is not an array')
  pos+=1;dec=json.JSONDecoder();names=[];rejected=0;n=len(text)
  while True:
   while pos<n and text[pos] in ' \t\r\n,':pos+=1
   if pos>=n:raise ValueError('PyPI simple index projects array is unterminated')
   if text[pos]==']':break
   try:item,pos=dec.raw_decode(text,pos)
   except RecursionError:raise ValueError('PyPI simple index entry is nested too deeply; refusing') from None
   name=item.get('name') if isinstance(item,dict) else None
   if isinstance(name,str) and len(name)<=MAX_PYPI_NAME and _PYPI_NAME.match(name):names.append(name)
   else:rejected+=1
  rest=text[pos+1:].strip()  # outer object must be complete: only '}' or ',"key":value...}' may follow the array
  if rest!='}':
   try:json.loads('{"_":0'+rest)
   except (ValueError,RecursionError):raise ValueError('PyPI simple index has malformed or truncated data after the projects array') from None
  if not names:raise ValueError('PyPI simple index had no valid project names')
  self.rejected_names=rejected
  return '\n'.join(names)
 def index_stats(self):
  """Last accepted index: names kept, entries rejected (invalid/over-long/non-object), fetched_at epoch."""
  return {'names':self._cache[1].count('\n')+1 if self._cache[1] else 0,'rejected_entries':self.rejected_names,'fetched_at':self._cache[0]}
 def _load(self):
  """Returns (names_text, stale, fetched_at). Single-flight (lock). On failure a cached index is served flagged stale;
  with no cache the error is raised and re-raised for FAIL_COOLDOWN seconds without refetching."""
  import time
  with self._lock:
   at,text=self._cache
   now=time.time()
   if text and now-at<self._ttl:return text,False,at
   if self._fail[1] is not None and now<self._fail[0] and not text:raise self._fail[1]
   try:
    text2=self._parse(self._read());self._cache=(time.time(),text2);self._fail=(0.0,None);return text2,False,self._cache[0]
   except Exception as error:
    if text:return text,True,at
    self._fail=(time.time()+self.FAIL_COOLDOWN,error);raise
 async def collect(self,query):
  import asyncio,time
  text,stale,at=await asyncio.to_thread(self._load)
  q=(query or '').strip().lower().replace('_','-')
  if not q:return
  hits=[n for n in text.split('\n') if q in n.lower()]
  hits.sort(key=lambda n:(n.lower()!=q,not n.lower().startswith(q),len(n),n.lower()))
  age=int(time.time()-at)
  for n in hits[:20]:
   yield {'name':n,'url':f"https://pypi.org/project/{n}/",'summary':'PyPI project NAME match from the official Simple index (name-only; descriptions are not searched)'+(f' [STALE cache, age {age}s]' if stale else ''),'maintenance':0.,'security':0.,'fit':0.,'novelty':0.,'unmeasured':['maintenance','security','fit','novelty'],'evidence':[{'source':'pypi','match':'name-only','stale_cache':stale,'cache_age_s':age,'quality_signals':'unmeasured','rejected_index_entries':self.rejected_names}],'permissions':[],'kind':'package'}
def _npm_detail(row,key):
 v=((row.get('score') or {}).get('detail') or {}).get(key)
 return float(v) if isinstance(v,(int,float)) and not isinstance(v,bool) and 0<=v<=1 else None
def _npm(p):
 for row in p.get('objects',[])[:20]:
  x=row.get('package',{});yield {'name':x.get('name',''),'url':(x.get('links') or {}).get('npm',f"https://www.npmjs.com/package/{x.get('name','')}"),'summary':x.get('description') or 'npm package','version':x.get('version'),'license':None,'maintenance':_npm_detail(row,'maintenance') or 0.,'security':0.,'fit':.6,'novelty':.4,'measured_signals':['maintenance'] if _npm_detail(row,'maintenance') is not None else [],'evidence':[{'source':'npm','registry_score_final':row.get('score',{}).get('final'),'registry_maintenance':_npm_detail(row,'maintenance'),'registry_quality':_npm_detail(row,'quality'),'computed_by':'npm registry (vendor-computed, NOT an Atlas measurement)','note':'registry-computed scores; quality is not security'}],'permissions':[], 'kind':'package'}
def default_collectors():
 base=[JsonCollector('github','https://api.github.com/search/repositories?q={query}&per_page=20',_github,kind='repository'),PypiNameCollector(),JsonCollector('npm','https://registry.npmjs.org/-/v1/search?text={query}&size=20',_npm)]
 return base+default_source_collectors()
