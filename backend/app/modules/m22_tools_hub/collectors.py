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
from .sources import default_source_collectors
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
 for x in p.get('items',[])[:20]:yield {'name':x['full_name'],'url':x['html_url'],'summary':x.get('description') or '', 'version':None,'license':(x.get('license') or {}).get('spdx_id'),'maintenance':.8 if not x.get('archived') else .1,'security':.6,'fit':.7,'novelty':.5,'evidence':[{'stars':x.get('stargazers_count',0),'updated_at':x.get('updated_at')}], 'permissions':[], 'kind':'repository'}
def _pypi(p):
 for x in p.get('projects',[])[:20]:yield {'name':x['name'],'url':f"https://pypi.org/project/{x['name']}/",'summary':'Python package from official PyPI index','maintenance':.5,'security':.5,'fit':.6,'novelty':.4,'evidence':[{'source':'pypi'}],'permissions':[], 'kind':'package'}
def _npm(p):
 for row in p.get('objects',[])[:20]:
  x=row.get('package',{});yield {'name':x.get('name',''),'url':(x.get('links') or {}).get('npm',f"https://www.npmjs.com/package/{x.get('name','')}"),'summary':x.get('description') or 'npm package','version':x.get('version'),'license':None,'maintenance':float(row.get('score',{}).get('detail',{}).get('maintenance',.5)),'security':float(row.get('score',{}).get('detail',{}).get('quality',.5)),'fit':.6,'novelty':.4,'evidence':[{'source':'npm','score':row.get('score',{}).get('final')}],'permissions':[], 'kind':'package'}
def default_collectors():
 base=[JsonCollector('github','https://api.github.com/search/repositories?q={query}&per_page=20',_github,kind='repository'),JsonCollector('pypi','https://pypi.org/search/?q={query}&format=application/vnd.pypi.simple.v1+json',_pypi),JsonCollector('npm','https://registry.npmjs.org/-/v1/search?text={query}&size=20',_npm)]
 return base+default_source_collectors()
