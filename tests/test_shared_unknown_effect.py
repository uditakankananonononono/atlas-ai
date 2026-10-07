import asyncio
import pytest
from instinct_models.providers import InklingLocal,ProviderError
from instinct_models.router import Router,Task
from app.core import shared_model_layer,providers,model_catalog

def chain(calls):
 def unknown(*args):calls.append('first');raise ProviderError('dispatched fixture failure')
 def backup(*args):calls.append('backup');return {'choices':[{'message':{'content':'backup'}}]}
 return Router([InklingLocal('http://fixture.invalid/v1','first',transport=unknown),InklingLocal('http://fixture.invalid/v1','backup',transport=backup)])

def test_atlas_shared_generation_stops_after_error(monkeypatch):
 calls=[];monkeypatch.setattr(shared_model_layer,'atlas_router',lambda:chain(calls))
 with pytest.raises(providers.ProviderOutcomeUnknown):asyncio.run(providers.generate('fixture','shared'))
 assert calls==['first']

def test_atlas_freefirst_cannot_restart_after_shared_error(monkeypatch):
 calls=[];monkeypatch.setattr(shared_model_layer,'atlas_router',lambda:chain(calls))
 monkeypatch.setattr(model_catalog,'default_chain',lambda:[model_catalog.Route('shared','fixture',model_catalog.LOCAL),model_catalog.Route('ollama','backup',model_catalog.LOCAL)])
 with pytest.raises(providers.ProviderOutcomeUnknown):asyncio.run(model_catalog.generate_free_first('fixture'))
 assert calls==['first']

def test_opt_in_does_not_change_default_router_callers():
 calls=[];result=chain(calls).run(Task(messages=[{'role':'user','content':'fixture'}]))
 assert result.ok and calls==['first','backup']

def test_unconfigured_shared_skip_can_reach_configured_route():
 calls=[]
 def backup(*args):calls.append('backup');return {'choices':[{'message':{'content':'fixture'}}]}
 router=Router([InklingLocal(None,None),InklingLocal('http://fixture.invalid/v1','backup',transport=backup)])
 assert asyncio.run(shared_model_layer.generate('fixture',router=router))==('inkling-local','backup','fixture')
 assert calls==['backup']

@pytest.mark.parametrize('outcome',['503','malformed'])
def test_actual_local_shared_http_error_never_invokes_backup(monkeypatch,outcome):
 from http.server import BaseHTTPRequestHandler,HTTPServer
 from threading import Thread
 calls=[]
 class Handler(BaseHTTPRequestHandler):
  def do_POST(self):
   calls.append('http');self.rfile.read(int(self.headers.get('Content-Length',0)))
   self.send_response(503 if outcome=='503' else 200);self.end_headers();self.wfile.write(b'not-json')
  def log_message(self,*args):pass
 server=HTTPServer(('127.0.0.1',0),Handler);thread=Thread(target=server.serve_forever);thread.start()
 def backup(*args):calls.append('backup');return {'choices':[{'message':{'content':'backup'}}]}
 try:
  router=Router([InklingLocal(f'http://127.0.0.1:{server.server_port}/v1','first'),InklingLocal('http://fixture.invalid/v1','backup',transport=backup)])
  monkeypatch.setattr(shared_model_layer,'atlas_router',lambda:router)
  with pytest.raises(providers.ProviderOutcomeUnknown):asyncio.run(providers.generate('fixture','shared'))
  assert calls==['http']
 finally:server.shutdown();thread.join();server.server_close()

@pytest.mark.parametrize('failure',['urlerror','oserror'])
def test_dispatched_os_transport_failure_is_classified_unknown(monkeypatch,failure):
 from urllib.error import URLError
 calls=[]
 def transport(*args):calls.append('first');raise URLError('fixture') if failure=='urlerror' else OSError('fixture')
 def backup(*args):calls.append('backup');return {'choices':[{'message':{'content':'backup'}}]}
 router=Router([InklingLocal('http://fixture.invalid/v1','first',transport=transport),InklingLocal('http://fixture.invalid/v1','backup',transport=backup)])
 monkeypatch.setattr(shared_model_layer,'atlas_router',lambda:router)
 with pytest.raises(providers.ProviderOutcomeUnknown) as error:asyncio.run(providers.generate('fixture','shared'))
 assert error.value.outcome=='unknown' and calls==['first']
