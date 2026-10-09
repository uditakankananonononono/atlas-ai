"""Synthetic readiness protection tests; no learned endpoint provided."""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import pytest
from app.modules.m21_claire.runtime.model_readiness import check_local_model
from app.modules.m21_claire.runtime.model_adapter import LocalSharedModel
from app.modules.m21_claire.runtime.types import AgentDecision


def test_real_synthetic_http_reply_captured_without_upgrading_provenance():
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            data=json.dumps({'choices':[{'message':{'content':'{"final":"hello from synthetic server"}'}}]}).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever);thread.start()
    try:
        result=asyncio.run(check_local_model('hermes',f'http://127.0.0.1:{server.server_port}/v1','synthetic'))
        assert result.status=='protocol_answered' and result.response=='hello from synthetic server'
        assert len(result.response_sha256)==64 and not result.learned_model_verified and not result.acceptance_a_met
        assert len(requests)==1 and 'tools' not in requests[0]
        assert requests[0]['model']=='synthetic'
    finally:server.shutdown();thread.join();server.server_close()


def test_closed_endpoint_is_unavailable_and_no_url_diagnostics():
    server=ThreadingHTTPServer(('127.0.0.1',0),BaseHTTPRequestHandler);port=server.server_port;server.server_close()
    result=asyncio.run(check_local_model('hermes',f'http://127.0.0.1:{port}/v1','synthetic'))
    assert result.status=='unavailable' and result.response is None
    assert '127.0.0.1' not in repr(result)


def test_wrong_action_is_invalid(monkeypatch):
    class Model:
        async def decide(self,m):return AgentDecision(replan={'reason':'no','steps':['x']})
    monkeypatch.setattr(LocalSharedModel,'select',lambda *a:Model())
    assert asyncio.run(check_local_model('hermes','http://localhost:8000/v1','m')).status=='invalid_output'


def test_timeout_and_cancel(monkeypatch):
    class Model:
        async def decide(self,m):await asyncio.sleep(10)
    monkeypatch.setattr(LocalSharedModel,'select',lambda *a:Model())
    assert asyncio.run(check_local_model('hermes','http://localhost:8000/v1','m',timeout_seconds=.05)).status=='unavailable'
    async def cancel():
        task=asyncio.create_task(check_local_model('hermes','http://localhost:8000/v1','m'))
        await asyncio.sleep(.01);task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    asyncio.run(cancel())
