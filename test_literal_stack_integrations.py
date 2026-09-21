import json
from app.platform.integrations import RedisStreamBus,ChromaMemory,LangChainPipeline,APSchedulerService
from app.auth.session import RefreshSessionStore
class Redis:
 def __init__(self):self.rows=[]
 def xadd(self,s,f,**k):self.rows.append(('1-0',f));return '1-0'
 def xread(self,d,**k):return [('events',self.rows)]
class Collection:
 def upsert(self,**kwargs):self.kw=kwargs
 def query(self,**kwargs):return {'ids':[['x']]}
class Chroma:
 def get_or_create_collection(self,*a,**k):return Collection()
def test_redis_stream_publish_and_read():
 bus=RedisStreamBus(client=Redis());assert bus.publish('events',{'x':1})=='1-0';assert bus.read('events')[0]['event']=={'x':1}
def test_chroma_is_real_client_boundary():
 store=ChromaMemory('tenant',client=Chroma());assert store.upsert([{'id':'x','text':'t','embedding':[1.], 'metadata':{}}])==1;assert store.query([1])['ids']==[['x']]
def test_langchain_pipeline_executes_steps():assert LangChainPipeline([lambda x:{**x,'a':1},lambda x:{**x,'b':x['a']+1}]).invoke({})['b']==2
def test_refresh_tokens_rotate_once_and_replay_fails():
 s=RefreshSessionStore();token=s.issue('u','t');new=s.rotate(token);assert new!=token
 try:s.rotate(token)
 except PermissionError:pass
 else:raise AssertionError('replay accepted')
