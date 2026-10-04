"""Route smoke over the REAL booted app (FastAPI TestClient, in-process) for parameterless GET operations.

Scope/limits (printed in the report): dev-mode tenant headers (ATLAS_ENV unset) = TEST MODE, NOT production auth proof;
temp SQLite DB with ORM-created schema; outbound non-loopback sockets are BLOCKED so no external side effects (calls
that needed the network show up as errors, not as working features); GET only; a 200 is NOT a working feature.
Usage: PYTHONPATH=backend python scripts/route_smoke_get.py OUT.json
"""
import signal, json, os, re, socket, sys, tempfile, time, collections
tmp = tempfile.mkdtemp(prefix="route_smoke_")
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
    return _real_connect(self, address, *a, **k)
socket.socket.connect = _blocked
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app, raise_server_exceptions=False)
spec = app.openapi()["paths"]
STUB = re.compile(r"stub|not implemented|placeholder|mock|todo|fixture|simulated|demo", re.I)
rows = []
for path, ops in sorted(spec.items()):
    get = ops.get("get")
    if not get or "{" in path:
        continue
    if any(p.get("required") for p in get.get("parameters", []) if p.get("in") == "query"):
        rows.append({"path": path, "status": None, "class": "skipped_required_query"}); continue
    t = time.time()
    print("GET", path, file=sys.stderr, flush=True)
    signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError("per-request 20s alarm")))
    signal.alarm(20)
    try:
        r = client.get(path)
        ctype = r.headers.get("content-type", "")
        body = r.text[:400]
        cls = ("5xx_server_error" if r.status_code >= 500 else "fail_closed_4xx" if r.status_code in (401, 403, 404, 405, 409, 422, 501, 503) else "ok_2xx" if r.status_code < 300 else f"other_{r.status_code}")
        if r.status_code == 200 and STUB.search(body):
            cls = "ok_2xx_but_body_mentions_stub_or_fixture"
        if r.status_code == 200 and "json" in ctype:
            try:
                j = r.json()
                if j in ({}, [], None):
                    cls = "ok_2xx_empty"
            except ValueError:
                pass
        rows.append({"path": path, "status": r.status_code, "class": cls, "ctype": ctype[:30], "ms": round((time.time() - t) * 1000), "body": body[:200]})
    except BaseException as e:
        rows.append({"path": path, "status": None, "class": "exception", "error": f"{type(e).__name__}: {str(e)[:160]}"})
    finally:
        signal.alarm(0)
json.dump(rows, open(sys.argv[1], "w"), indent=1)
print(collections.Counter(r["class"] for r in rows))
print("total GET parameterless ops:", len(rows), "of openapi paths", len(spec))
