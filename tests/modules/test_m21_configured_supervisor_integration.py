"""Mounted/worker/HTTP integration with synthetic model server, not model capability."""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from app.main import app
from app.modules.m21_claire.runtime import routes
from app.modules.m21_claire.runtime.configuration import ConfiguredReadOnlyWorker, WorkerConfiguration, supervise_read_only
from app.modules.m21_claire.runtime.goals import GoalStore
from app.modules.m21_claire.runtime.tools import Tool


class Args(BaseModel): key: str
class Lookup(Tool):
    name, arguments_model = "lookup", Args
    def run(self, arguments): return {"found":arguments.key}


@pytest.mark.parametrize("mode,expected", [("success","completed"), ("invalid","blocked"), ("unavailable","blocked")])
def test_authenticated_mount_through_configured_http_supervisor(tmp_path, monkeypatch, oidc_auth_headers, mode, expected):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(body)
            if mode == "unavailable":
                self.send_response(503); self.end_headers(); self.wfile.write(b'private driver diagnostic'); return
            if mode == "invalid": decision = "invalid output https://private.example/token=secret"
            elif len(body["messages"]) == 2:
                decision = json.dumps({"tool_call":{"name":"lookup","arguments":{"key":"actual-http"}}})
            else: decision = json.dumps({"final":"synthetic transport proof only"})
            response = json.dumps({"choices":[{"message":{"content":decision}}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(response)))
            self.end_headers(); self.wfile.write(response)
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever); thread.start()
    db = f"sqlite:///{tmp_path}/mounted.db"
    config = WorkerConfiguration.from_environment({
        "ATLAS_CLAIRE_RUNTIME_DB":db, "ATLAS_CLAIRE_MODEL_PROVIDER":"hermes",
        "ATLAS_CLAIRE_MODEL_URL":f"http://127.0.0.1:{server.server_port}/v1",
        "ATLAS_CLAIRE_MODEL_NAME":"synthetic-integration-model", "ATLAS_CLAIRE_WORKER_ID":"worker",
        "ATLAS_CLAIRE_WORKER_DEV_SCHEMA":"1", "ATLAS_ENV":"development",
    })
    worker = ConfiguredReadOnlyWorker(config, [Lookup()])
    api_store = GoalStore(db)
    monkeypatch.setattr(routes, "_store", api_store)
    monkeypatch.delenv("ATLAS_DEV_NO_AUTH", raising=False)
    url = "/api/v1/claire/runtime/goals"
    try:
        with TestClient(app) as client:
            owner = oidc_auth_headers(tenant="tenant-a", subject="owner")
            assert client.post(url, json={"purpose":"lookup"}).status_code == 401
            response = client.post(url, headers=owner, json={"purpose":"lookup actual-http", "acceptance_criteria":[{"kind":"tool_receipt","tool":"lookup","min_count":1}]})
            assert response.status_code == 201, response.text
            gid = response.json()["id"]
            result = asyncio.run(supervise_read_only(worker, max_jobs=1))
            assert result.status == "job_limit" and result.goals == (gid,) and result.database_failures == 0
            worker.close(); api_store.close()
            fresh = GoalStore(db)
            monkeypatch.setattr(routes, "_store", fresh)
            try:
                got = client.get(f"{url}/{gid}", headers=owner).json()
                assert got["status"] == expected
                assert client.get(f"{url}/{gid}", headers=oidc_auth_headers(tenant="other", subject="owner")).status_code == 404
                assert client.get(f"{url}/{gid}", headers=oidc_auth_headers(tenant="tenant-a", subject="other")).status_code == 404
                if mode == "success":
                    assert got["verdict"]["accepted"] is True
                    assert got["report"]["receipts"][0]["content"] == {"found":"actual-http"}
                else:
                    assert got["report"]["receipts"] == []
                    assert got["blocker"] == ("model_invalid_output" if mode == "invalid" else "model_unavailable")
                    assert "private.example" not in json.dumps(got)
                    assert "private driver" not in json.dumps(got)
                assert requests and all(r["model"] == "synthetic-integration-model" for r in requests)
                assert "lookup" in requests[0]["messages"][1]["content"]
            finally: fresh.close()
    finally:
        worker.close(); api_store.close(); server.shutdown(); thread.join(); server.server_close()
