import asyncio
import httpx
import pytest
from app.core import providers,model_catalog
from app.platform.reliability import CircuitBreaker

@pytest.mark.parametrize('outcome',['timeout','disconnect',408,429,500,503,'json'])
def test_generation_post_unknown_does_not_repeat(monkeypatch,outcome):
 calls=[];real=httpx.AsyncClient
 async def handler(request):
  calls.append(request)
  if outcome=='timeout':raise httpx.ReadTimeout('fixture timeout',request=request)
  if outcome=='disconnect':raise httpx.RemoteProtocolError('fixture disconnect',request=request)
  if outcome=='json':return httpx.Response(200,text='not json')
  return httpx.Response(outcome,json={'error':'fixture'})
 monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kwargs:real(transport=httpx.MockTransport(handler),**kwargs))
 monkeypatch.setitem(providers._BREAKERS,'openai_compat',CircuitBreaker())
 with pytest.raises(providers.ProviderOutcomeUnknown):asyncio.run(providers.generate('fixture','openai_compat','fixture'))
 assert len(calls)==1

@pytest.mark.parametrize('response',[{}, {'choices':[]}, {'choices':[{'message':{'content':''}}]}, [], 'text'])
def test_success_unusable_response_still_holds_no_free_first_fallback(monkeypatch,response):
 calls=[];real=httpx.AsyncClient
 async def handler(request):calls.append(request);return httpx.Response(200,json=response)
 monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kwargs:real(transport=httpx.MockTransport(handler),**kwargs))
 monkeypatch.setattr(model_catalog,'default_chain',lambda:[model_catalog.Route('openai_compat','fixture',model_catalog.LOCAL),model_catalog.Route('ollama','backup',model_catalog.LOCAL)])
 monkeypatch.setitem(providers._BREAKERS,'openai_compat',CircuitBreaker())
 with pytest.raises(providers.ProviderOutcomeUnknown):asyncio.run(model_catalog.generate_free_first('fixture'))
 assert len(calls)==1

def test_preflight_missing_configuration_can_still_select_next_route(monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 monkeypatch.setattr(model_catalog,'default_chain',lambda:[model_catalog.Route('openai','fixture',model_catalog.LOCAL),model_catalog.Route('openai_compat','fixture',model_catalog.LOCAL)])
 real=httpx.AsyncClient;calls=[]
 async def handler(request):calls.append(request);return httpx.Response(200,json={'choices':[{'message':{'content':'fixture'}}]})
 monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kwargs:real(transport=httpx.MockTransport(handler),**kwargs));monkeypatch.setitem(providers._BREAKERS,'openai_compat',CircuitBreaker())
 assert asyncio.run(model_catalog.generate_free_first('fixture'))==('openai_compat','fixture','fixture')
 assert len(calls)==1

def test_actual_local_http_transient_response_single_post_no_backup(monkeypatch):
 from http.server import BaseHTTPRequestHandler,HTTPServer
 from threading import Thread
 calls=[]
 class Handler(BaseHTTPRequestHandler):
  def do_POST(self):
   calls.append(self.path);self.rfile.read(int(self.headers.get('Content-Length',0)))
   self.send_response(503);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"error":"fixture"}')
  def log_message(self,*args):pass
 server=HTTPServer(('127.0.0.1',0),Handler);thread=Thread(target=server.serve_forever);thread.start()
 try:
  monkeypatch.setenv('ATLAS_LOCAL_OPENAI_URL',f'http://127.0.0.1:{server.server_port}/v1')
  monkeypatch.setattr(model_catalog,'default_chain',lambda:[model_catalog.Route('openai_compat','fixture',model_catalog.LOCAL),model_catalog.Route('ollama','backup',model_catalog.LOCAL)])
  monkeypatch.setitem(providers._BREAKERS,'openai_compat',CircuitBreaker())
  with pytest.raises(providers.ProviderOutcomeUnknown):asyncio.run(model_catalog.generate_free_first('fixture'))
  assert calls==['/v1/chat/completions']
 finally:server.shutdown();thread.join();server.server_close()
