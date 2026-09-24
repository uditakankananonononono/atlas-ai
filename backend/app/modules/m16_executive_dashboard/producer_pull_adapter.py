from __future__ import annotations
import json,urllib.request
from .asymmetric_proof_events import SignedProofEvent
from .producer_event_ingest import ProducerEventIngest
class ProducerPullAdapter:
 """Pulls signed events from a configured producer subscription endpoint and ingests them.

 Fails closed: without an explicit subscription URL or fetcher, no events are read or ingested.
 Every pulled event still passes registry-backed signature verification before persistence."""
 def __init__(self,ingest:ProducerEventIngest,subscription_url:str|None=None,fetcher=None):self.ingest=ingest;self.subscription_url=subscription_url;self.fetcher=fetcher
 def _fetch_raw(self):
  if self.fetcher is not None:return self.fetcher()
  if not self.subscription_url:raise ValueError('producer pull subscription is not configured; refusing to ingest unauthenticated events')
  request=urllib.request.Request(self.subscription_url,headers={'Accept':'application/json'})
  with urllib.request.urlopen(request,timeout=15) as response:return json.loads(response.read().decode())
 def pull_once(self)->dict:
  raw=self._fetch_raw()
  items=raw.get('events') if isinstance(raw,dict) else raw
  if not isinstance(items,list) or not items:raise ValueError('producer subscription returned no events')
  events=[SignedProofEvent.model_validate(item) for item in items]
  result=self.ingest.ingest_batch(events)
  return {**result,'pulled':len(events),'boundary':'Pulls one batch from the configured producer subscription and ingests only registry-authenticated events. Unconfigured subscriptions fail closed. It does not manage subscriptions, inspect proof bytes, or deploy.'}
