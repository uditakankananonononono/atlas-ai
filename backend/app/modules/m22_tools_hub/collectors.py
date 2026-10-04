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
from .sources import _recency_score, default_source_collectors
class JsonCollector:
 def __init__(self,name,url,parse,kind="package"):self.name=name;self.url=url;self.parse=parse;self.kind=kind
 async def collect(self,query):
  import asyncio
  def fetch():
   request=Request(self.url.format(query=quote_plus(query)),headers={'User-Agent':'AtlasAI-ToolsHub/1.0','Accept':'application/json'})
   with urlopen(request,timeout=10) as r:return json.load(r)
  payload=await asyncio.to_thread(fetch)
  for item in self.parse(payload):yield item
def _github(p):
 for x in p.get('items',[])[:20]:yield {'name':x['full_name'],'url':x['html_url'],'summary':x.get('description') or '', 'version':None,'license':(x.get('license') or {}).get('spdx_id'),'maintenance':.1 if x.get('archived') else _recency_score(x.get('pushed_at') or x.get('updated_at')),'security':.6,'fit':.7,'novelty':.5,'evidence':[{'stars':x.get('stargazers_count',0),'updated_at':x.get('updated_at'),'pushed_at':x.get('pushed_at')}], 'permissions':[], 'kind':'repository'}
PYPI_SIMPLE_URL='https://pypi.org/simple/'
class PypiNameCollector:
 """PyPI has NO search API (the /search/ page is HTML only). The supported official interface is the Simple index
 (PEP 691 JSON, all project names, ~10MB). This collector therefore does NAME-ONLY matching against that index
 (exact > prefix > substring > shorter first). It does not search descriptions or keywords; summaries say so."""
 kind='package'
 def __init__(self,fetch=None,ttl=3600):
  self.name='pypi';self.url=PYPI_SIMPLE_URL;self._fetch=fetch;self._ttl=ttl;self._cache=(0.0,'')
 MAX_BYTES=100*1024*1024  # decompressed cap; index was ~44MB raw / ~10MB gzip on 2026-10-04
 def _gunzip(self,r):
  import zlib
  d=zlib.decompressobj(31);out=bytearray()
  while True:
   chunk=r.read(1<<20)
   if not chunk:break
   out+=d.decompress(chunk,self.MAX_BYTES+1-len(out))
   if len(out)>self.MAX_BYTES:break
  return bytes(out)
 def _read(self):
  if self._fetch:
   payload=self._fetch(self.url);return json.dumps(payload).encode()
  request=Request(self.url,headers={'User-Agent':'AtlasAI-ToolsHub/1.0','Accept':'application/vnd.pypi.simple.v1+json','Accept-Encoding':'gzip'})
  with urlopen(request,timeout=30) as r:
   raw=r.read(self.MAX_BYTES+1) if r.headers.get('Content-Encoding')!='gzip' else self._gunzip(r)
  if len(raw)>self.MAX_BYTES:raise ValueError('PyPI simple index exceeds the size cap; refusing to parse')
  return raw
 def _load(self):
  """Returns (names_text, stale). Parses with a regex over the raw bytes (no 900k-dict json tree), keeps ONE
  newline-joined string. On fetch failure a previously cached index is served and flagged stale; with no cache the error is raised."""
  import re,time
  at,text=self._cache
  if text and time.time()-at<self._ttl:return text,False
  try:
   raw=self._read().decode('utf-8','replace')
   names=re.findall(r'"name"\s*:\s*"([^"\\]+)"',raw)
   if not names:raise ValueError('PyPI simple index had no project names')
   text='\n'.join(names);self._cache=(time.time(),text);return text,False
  except Exception:
   if text:return text,True
   raise
 async def collect(self,query):
  import asyncio
  text,stale=await asyncio.to_thread(self._load)
  q=(query or '').strip().lower().replace('_','-')
  if not q:return
  hits=[n for n in text.split('\n') if q in n.lower()]
  hits.sort(key=lambda n:(n.lower()!=q,not n.lower().startswith(q),len(n),n.lower()))
  for n in hits[:20]:
   yield {'name':n,'url':f"https://pypi.org/project/{n}/",'summary':'PyPI project NAME match from the official Simple index (name-only; descriptions are not searched)','maintenance':.5,'security':.5,'fit':.6,'novelty':.4,'evidence':[{'source':'pypi','match':'name-only','stale_cache':stale}],'permissions':[],'kind':'package'}
def _npm(p):
 for row in p.get('objects',[])[:20]:
  x=row.get('package',{});yield {'name':x.get('name',''),'url':(x.get('links') or {}).get('npm',f"https://www.npmjs.com/package/{x.get('name','')}"),'summary':x.get('description') or 'npm package','version':x.get('version'),'license':None,'maintenance':float(row.get('score',{}).get('detail',{}).get('maintenance',.5)),'security':float(row.get('score',{}).get('detail',{}).get('quality',.5)),'fit':.6,'novelty':.4,'evidence':[{'source':'npm','score':row.get('score',{}).get('final')}],'permissions':[], 'kind':'package'}
def default_collectors():
 base=[JsonCollector('github','https://api.github.com/search/repositories?q={query}&per_page=20',_github,kind='repository'),PypiNameCollector(),JsonCollector('npm','https://registry.npmjs.org/-/v1/search?text={query}&size=20',_npm)]
 return base+default_source_collectors()
