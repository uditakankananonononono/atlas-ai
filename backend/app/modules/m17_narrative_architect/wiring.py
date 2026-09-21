"""Legal default source wiring for narrative evidence."""
from __future__ import annotations
import asyncio,os
from app.modules.m18_side_hustle_scraper.wiring import build_collectors
class AsyncEvidenceCollector:
 def __init__(self,collector):self.collector=collector
 async def collect(self,query,limit):
  docs,errors=await asyncio.to_thread(self.collector.collect,query,limit)
  return [{'url':d.url,'text':d.text,'creator':d.author,'published_at':d.published_at.isoformat() if d.published_at else None,'engagement':sum(d.engagement.values()),'rights':d.rights.value,'collection_errors':[e.reason for e in errors]} for d in docs]
def build_narrative_collectors(env=None):
 raw=build_collectors(os.environ if env is None else env)
 return {k:AsyncEvidenceCollector(v) for k,v in raw.items() if k in {'reddit','youtube','pinterest','public_web'}}
