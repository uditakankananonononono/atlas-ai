"""Route smoke over the REAL booted app (FastAPI TestClient, in-process) core-flow MUTATING smoke (m19 intake/portfolio/burn-down, m22 discover/candidates/export).

Scope/limits (printed in the report): dev-mode tenant headers (ATLAS_ENV unset) = TEST MODE, NOT production auth proof;
temp SQLite DB with ORM-created schema; outbound non-loopback sockets are BLOCKED so no external side effects (calls
that needed the network show up as errors, not as working features); only the listed flows; a 200 is NOT a working feature.
Usage: PYTHONPATH=backend python scripts/core_flow_smoke.py OUT.json
"""
import signal, json, os, re, socket, sys, tempfile, time, collections
tmp = tempfile.mkdtemp(prefix="core_flow_")
os.environ["ATLAS_DATABASE_URL"] = f"sqlite:///{tmp}/smoke.db"
os.environ["ATLAS_AUTO_CREATE_SCHEMA"] = "1"
os.environ.pop("ATLAS_ENV", None)
os.environ["ATLAS_RATE_LIMIT_PER_MINUTE"] = "1000000"  # harness only: one client would otherwise trip the per-minute limiter (429 = harness artifact)
os.environ.setdefault("ATLAS_TOKEN_KEY", "TEST-ONLY-throwaway-key-not-a-secret-0123456789abcdef")  # labeled test key; unset => routes fail closed 503
_real_connect = socket.socket.connect
def _blocked(self, address, *a, **k):
    host = address[0] if isinstance(address, tuple) else str(address)
    if isinstance(address, tuple) and host not in ("127.0.0.1", "::1", "localhost"):
        raise OSError(f"outbound network blocked by smoke harness: {host}")

_real_connect_holder = None
socket.socket.connect = _blocked
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app, raise_server_exceptions=False)
H = {"x-atlas-tenant": "smoke-tenant", "x-atlas-actor": "smoke-user"}
steps = []
def step(name, method, path, **kw):
    t = time.time()
    r = c.request(method, path, headers=H, **kw)
    try:
        body = r.json()
    except ValueError:
        body = r.text[:300]
    steps.append({"step": name, "method": method, "path": path, "status": r.status_code, "ms": round((time.time() - t) * 1000), "body": json.dumps(body)[:500] if not isinstance(body, str) else body})
    return r, body
V = "/api/v1/idea-incubator"
r, b = step("m19 intake", "POST", f"{V}/ideas", json={"one_liner": "A local-first study planner for ESL students", "budget_cap": 0})
r, b = step("m19 portfolio create", "POST", f"{V}/portfolio/ideas", json={"title": "ESL planner", "problem": "students lose track of deadlines", "proposed_solution": "offline planner", "tags": ["smoke"]})
step("m19 portfolio list", "GET", f"{V}/portfolio/ideas")
step("m19 burn-down", "POST", f"{V}/assumption-burn-down", json={"assumptions": [{"assumption_id": "a1", "text": "students want offline", "uncertainty": 0.8}], "tests": [{"id": "t1", "name": "5 interviews", "cost": 0, "reduces": ["a1"]}], "budget": 0})
T = "/api/v1/tools-hub"
step("m22 discover (network blocked: expect 502 with source errors)", "POST", f"{T}/pipeline/discoveries", json={"query": "pdf parser"})
step("m22 candidates", "GET", f"{T}/pipeline/candidates")
for fmt in ("json", "csv", "markdown", "bogus"):
    step(f"m22 export {fmt}", "GET", f"{T}/candidates/export?format={fmt}")
step("m22 proposal bad payload", "POST", f"{T}/pipeline/proposals", json={"artifact_base64": "AAAA", "manifest": {}})
json.dump(steps, open(sys.argv[1], "w"), indent=1)
for s in steps:
    print(s["status"], s["step"], "|", s["body"][:160].replace("\n", " "))
