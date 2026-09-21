"""Concrete optional production adapters for the literal technical stack."""
from __future__ import annotations
import json,os,uuid
from dataclasses import dataclass
from typing import Any,Callable

class IntegrationError(RuntimeError):pass
class RedisStreamBus:
 def __init__(self,url:str|None=None,client=None):
  if client is None:
   from redis import Redis
   client=Redis.from_url(url or os.environ['ATLAS_REDIS_URL'],decode_responses=True)
  self.client=client
 def publish(self,stream:str,event:dict[str,Any])->str:
  if not stream or not isinstance(event,dict):raise ValueError('stream and event required')
  return str(self.client.xadd(stream,{'json':json.dumps(event,separators=(',',':'))},maxlen=100000,approximate=True))
 def read(self,stream:str,last_id:str='0-0',count:int=100,block_ms:int=1000):
  rows=self.client.xread({stream:last_id},count=count,block=block_ms)
  return [{'id':event_id,'event':json.loads(fields['json'])} for _,events in rows for event_id,fields in events]
class RabbitTopicBus:
 def __init__(self,url:str|None=None,connection=None):
  from kombu import Connection,Exchange
  self.connection=connection or Connection(url or os.environ['ATLAS_RABBITMQ_URL']);self.exchange=Exchange('atlas.events',type='topic',durable=True)
 def publish(self,routing_key:str,event:dict[str,Any]):
  if not routing_key or not isinstance(event,dict):raise ValueError('routing key and event required')
  with self.connection.Producer(serializer='json') as producer:producer.publish(event,exchange=self.exchange,routing_key=routing_key,declare=[self.exchange],retry=True)
  return {'routing_key':routing_key,'published':True}
class ChromaMemory:
 def __init__(self,tenant_id:str,path:str|None=None,client=None):
  if not tenant_id:raise ValueError('tenant required')
  if client is None:
   import chromadb
   client=chromadb.PersistentClient(path=path or os.getenv('ATLAS_CHROMA_PATH','./data/chroma'))
  self.collection=client.get_or_create_collection(f'atlas-{tenant_id}',metadata={'hnsw:space':'cosine'})
 def upsert(self,items:list[dict[str,Any]]):
  self.collection.upsert(ids=[str(x['id']) for x in items],documents=[x['text'] for x in items],embeddings=[x['embedding'] for x in items],metadatas=[x.get('metadata',{}) for x in items]);return len(items)
 def query(self,embedding:list[float],limit:int=8,where:dict|None=None):return self.collection.query(query_embeddings=[embedding],n_results=limit,where=where)
class LangChainPipeline:
 def __init__(self,steps:list[Callable[[dict[str,Any]],dict[str,Any]]]):self.steps=steps
 def invoke(self,payload:dict[str,Any]):
  from langchain_core.runnables import RunnableLambda
  chain=None
  for step in self.steps:chain=RunnableLambda(step) if chain is None else chain|RunnableLambda(step)
  return payload if chain is None else chain.invoke(payload)
class APSchedulerService:
 def __init__(self,scheduler=None):
  if scheduler is None:
   from apscheduler.schedulers.background import BackgroundScheduler
   scheduler=BackgroundScheduler(timezone='UTC')
  self.scheduler=scheduler
 def add(self,job_id:str,func:Callable,trigger:str,**kwargs):
  return self.scheduler.add_job(func,trigger,id=job_id,replace_existing=True,**kwargs)
class CloudStorageAssets:
 def __init__(self,bucket:str,client=None):
  if client is None:
   from google.cloud import storage
   client=storage.Client()
  self.bucket=client.bucket(bucket)
 def upload(self,name:str,data:bytes,content_type:str)->dict[str,str]:
  blob=self.bucket.blob(name);blob.upload_from_string(data,content_type=content_type);return {'bucket':self.bucket.name,'name':name,'generation':str(blob.generation)}
