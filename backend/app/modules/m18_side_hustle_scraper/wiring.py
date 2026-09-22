"""Production collector wiring. Secrets come only from process configuration."""
from __future__ import annotations
import os
from .lane_http import UrllibHttpClient
from .lane_models import FetchPolicy
from .lane_robots import RobotsCache
from .lane_sources import (RedditJsonCollector,HackerNewsCollector,DevToCollector,YouTubeDataCollector,RssFeedCollector,PublicWebCollector,PinterestApiCollector,XApiCollector,InstagramGraphCollector)

class ConfiguredPublicWebCollector(PublicWebCollector):
 def __init__(self,*a,urls=(),**kw):super().__init__(*a,**kw);self.urls=tuple(urls)
 def collect(self,query,limit):
  docs=[];errors=[]
  for url in self.urls[:limit]:
   doc,err=self.fetch_page(url)
   if doc and query.lower() in (doc.title+' '+doc.text).lower():docs.append(doc)
   if err:errors.append(err)
  return docs,errors

def build_collectors(env:dict[str,str]|None=None):
 e=os.environ if env is None else env;http=UrllibHttpClient();policy=FetchPolicy();base={"policy":policy}
 collectors={"reddit":RedditJsonCollector(http,**base),"hacker_news":HackerNewsCollector(http,**base),"dev_to":DevToCollector(http,**base)}
 feeds=[x.strip() for x in e.get("ATLAS_M18_RSS_FEEDS","").split(",") if x.strip()]
 urls=[x.strip() for x in e.get("ATLAS_M18_PUBLIC_URLS","").split(",") if x.strip()]
 if feeds:collectors["rss"]=RssFeedCollector(http,feed_urls=feeds,**base)
 if urls:collectors["public_web"]=ConfiguredPublicWebCollector(http,robots=RobotsCache(http,policy),urls=urls,**base)
 if e.get("ATLAS_YOUTUBE_API_KEY","").strip():collectors["youtube"]=YouTubeDataCollector(http,api_key=e["ATLAS_YOUTUBE_API_KEY"],**base)
 if e.get("ATLAS_PINTEREST_ACCESS_TOKEN","").strip():collectors["pinterest"]=PinterestApiCollector(http,access_token=e["ATLAS_PINTEREST_ACCESS_TOKEN"],**base)
 if e.get("ATLAS_X_BEARER_TOKEN","").strip():collectors["x"]=XApiCollector(http,bearer_token=e["ATLAS_X_BEARER_TOKEN"],**base)
 if e.get("ATLAS_INSTAGRAM_GRAPH_TOKEN","").strip():collectors["instagram"]=InstagramGraphCollector(http,access_token=e["ATLAS_INSTAGRAM_GRAPH_TOKEN"],**base)
 return collectors

def build_refetcher(env:dict[str,str]|None=None):
 """Production freshness fetcher for previously accepted legal source URLs."""
 import hashlib
 from .lane_models import SourceKind
 client=UrllibHttpClient();policy=FetchPolicy()
 allowed={x.value for x in SourceKind}
 def refetch(url:str,kind:SourceKind):
  if kind.value not in allowed:return {'error':f'unsupported source kind: {kind.value}'}
  try:
   response=client.fetch(url,policy=policy)
   return {'status':response.status,'not_modified':response.not_modified,'content_hash':None if response.not_modified else hashlib.sha256(response.body).hexdigest(),'etag':response.headers.get('etag'),'last_modified':response.headers.get('last-modified')}
  except Exception as error:
   from .lane_http import HttpError
   if isinstance(error,HttpError):return {'status':error.status,'error':error.reason}
   return {'error':f'{type(error).__name__}: {error}'}
 return refetch
