"""Hermetic M09 real-HTTP/PG/UI bridge. No OIDC provider or user-auth acceptance.

Generates ephemeral signed fixture tokens, seeds only a local verifier's public
JWKS cache, and keeps production signature/claim validation on. Never enables
header auth or overrides require_tenant. No browser submit/device paths.
"""
from pathlib import Path
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

import httpx
import pgserver
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

ROOT = Path(__file__).resolve().parents[2]
SERVER = '''
import json, os, time
from fastapi import FastAPI
from app.auth import context
from app.modules.m09_knowledge_workspace.routes import router
v = context._production_verifier()
v._keys = {"bridge-fixture": json.loads(os.environ["ATLAS_BRIDGE_PUBLIC_JWK"])}
v._expires = time.monotonic() + 3600
app = FastAPI()
app.include_router(router, prefix="/api/v1")
import uvicorn
uvicorn.run(app, host="127.0.0.1", port=int(os.environ["ATLAS_BRIDGE_PORT"]))
'''


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key().public_numbers()
    jwk = {"kty": "RSA", "kid": "bridge-fixture", "use": "sig", "alg": "RS256",
           "n": b64(pub.n.to_bytes((pub.n.bit_length()+7)//8, "big")),
           "e": b64(pub.e.to_bytes((pub.e.bit_length()+7)//8, "big"))}
    def token(tenant="bridge-a", expires=900):
        header = b64(json.dumps({"alg": "RS256", "kid": "bridge-fixture"}).encode())
        claims = b64(json.dumps({"iss": "https://fixture.invalid", "aud": "bridge", "sub": "fixture-owner", "atlas_tenant": tenant, "exp": time.time()+expires}).encode())
        message = f"{header}.{claims}".encode()
        return f"{header}.{claims}.{b64(key.sign(message, padding.PKCS1v15(), hashes.SHA256()))}"
    with tempfile.TemporaryDirectory(prefix="atlas-m09-bridge-") as scratch:
        server = pgserver.get_server(Path(scratch)/"pg", cleanup_mode="stop")
        api_port, ui_port = free_port(), free_port()
        env = {**os.environ, "PYTHONPATH": "backend", "ATLAS_ENV": "production", "ATLAS_DEV_NO_AUTH": "0",
               "ATLAS_DATABASE_URL": server.get_uri().replace("postgresql://", "postgresql+psycopg://"),
               "ATLAS_OIDC_ISSUER": "https://fixture.invalid", "ATLAS_OIDC_AUDIENCE": "bridge", "ATLAS_OIDC_TENANT_CLAIM": "atlas_tenant",
               "ATLAS_BRIDGE_PUBLIC_JWK": json.dumps(jwk), "ATLAS_BRIDGE_PORT": str(api_port),
               "ATLAS_INTERNAL_API_URL": f"http://127.0.0.1:{api_port}", "ATLAS_BRIDGE_API_URL": f"http://127.0.0.1:{api_port}",
               "ATLAS_BRIDGE_UI_PORT": str(ui_port), "ATLAS_BRIDGE_TOKEN": token(), "ATLAS_BRIDGE_OTHER_TOKEN": token("bridge-b"),
               "ATLAS_BRIDGE_EXPIRED_TOKEN": token(expires=-120),
               "NEXT_PUBLIC_SUPABASE_URL": "https://test.supabase.co", "NEXT_PUBLIC_SUPABASE_ANON_KEY": "test-anon-key"}
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True)
        with open(Path(scratch)/"api.log", "w+") as log:
            api = subprocess.Popen([sys.executable, "-c", SERVER], cwd=ROOT, env=env, stdout=log, stderr=log)
            try:
                for _ in range(100):
                    try:
                        if httpx.get(f"http://127.0.0.1:{api_port}/openapi.json", timeout=1).status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    if api.poll() is not None:
                        raise RuntimeError("bridge API stopped before ready")
                    time.sleep(.1)
                else:
                    raise RuntimeError("bridge API readiness timed out")
                result = subprocess.run(["npx", "playwright", "test", "--config", "playwright.bridge.config.ts"], cwd=ROOT/"frontend", env=env)
                if result.returncode:
                    log.seek(0)
                    print(log.read()[-3000:], file=sys.stderr)
                return result.returncode
            finally:
                api.terminate()
                try:
                    api.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    api.kill(); api.wait()


if __name__ == "__main__":
    raise SystemExit(main())
