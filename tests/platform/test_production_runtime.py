import asyncio,json,logging
import pytest
from app.platform.config import ConfigError,ProductionConfig
from app.platform.health import readiness
from app.platform.observability import CloudJsonFormatter,bind_trace,inject_trace
from app.platform.reliability import CircuitBreaker,CircuitOpen,IdempotencyConflict,IdempotencyStore,RateLimitExceeded,TenantRateLimiter
from app.platform.secrets import GoogleSecretManagerProvider,SecretError,VaultLiteralProvider

def production_env(**changes):
 env={"ATLAS_ENV":"production","ATLAS_DATABASE_URL":"postgresql+psycopg://host/atlas","ATLAS_REDIS_URL":"rediss://host/0","ATLAS_SECRET_PROVIDER":"gcp-secret-manager","ATLAS_OIDC_ISSUER":"https://issuer","ATLAS_OIDC_AUDIENCE":"atlas"}; env.update(changes); return env

def test_cloud_run_config_accepts_managed_service_references():
 cfg=ProductionConfig.from_env(production_env()); assert cfg.environment=="production" and cfg.secret_provider=="gcp-secret-manager"
@pytest.mark.parametrize("changes",[{"ATLAS_DATABASE_URL":"sqlite:///bad"},{"ATLAS_OIDC_AUDIENCE":""},{"ATLAS_SECRET_PROVIDER":"environment"},{"ATLAS_RATE_LIMIT_PER_MINUTE":"0"}])
def test_production_config_rejects_unsafe_or_invalid_values(changes):
 with pytest.raises(ConfigError): ProductionConfig.from_env(production_env(**changes))

def test_secret_manager_builds_latest_version_path_without_exposing_value():
 seen=[]; p=GoogleSecretManagerProvider("project-1",lambda path:(seen.append(path) or b"secret")); assert p.get("database-url")=="secret"; assert seen==["projects/project-1/secrets/database-url/versions/latest"]
def test_vault_literal_rejects_path_traversal_and_reads_named_key():
 provider=VaultLiteralProvider("atlas",lambda mount,key:{"value":f"{mount}:{key}"}); assert provider.get("token")=="atlas:token"
 with pytest.raises(SecretError): provider.get("../token")

def test_rate_limit_isolated_by_tenant_and_actor():
 r=TenantRateLimiter(2,10); r.check("a","u",0); r.check("a","u",1)
 with pytest.raises(RateLimitExceeded): r.check("a","u",2)
 r.check("b","u",2); r.check("a","v",2)
def test_idempotency_is_tenant_safe_and_detects_payload_conflict():
 s=IdempotencyStore(); calls=[]
 assert s.execute("a","k","one",lambda:(calls.append(1) or 7))==(7,False)
 assert s.execute("a","k","one",lambda:99)==(7,True)
 assert s.execute("b","k","one",lambda:8)==(8,False)
 with pytest.raises(IdempotencyConflict): s.execute("a","k","two",lambda:9)
 assert calls==[1]
@pytest.mark.asyncio
async def test_circuit_breaker_retries_timeout_and_opens():
 now=[0.0]; breaker=CircuitBreaker(2,5,lambda:now[0]); calls=0
 async def fail():
  nonlocal calls; calls+=1; raise OSError("down")
 with pytest.raises(OSError): await breaker.call(fail,.1,retries=1)
 assert calls==2
 with pytest.raises(CircuitOpen): await breaker.call(fail,.1)
 now[0]=6
 async def ok(): return "ok"
 assert await breaker.call(ok,.1)=="ok"
@pytest.mark.asyncio
async def test_circuit_breaker_enforces_timeout():
 async def slow(): await asyncio.sleep(.05)
 with pytest.raises(asyncio.TimeoutError): await CircuitBreaker(1).call(slow,.001)
def test_readiness_requires_database_cache_and_current_migration():
 ready,checks=readiness(lambda:True,lambda:True,lambda:False); assert not ready and checks["migrations"] is False
def test_cloud_logging_json_and_trace_propagation():
 trace=bind_trace("trace-123"); rec=logging.LogRecord("atlas",logging.INFO,"",0,"ready",(),None); data=json.loads(CloudJsonFormatter().format(rec)); assert data["trace_id"]==trace and inject_trace({})["traceparent"]==trace

from base64 import urlsafe_b64encode
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from app.auth import context as auth
from fastapi import HTTPException

def _b64(value: bytes) -> str: return urlsafe_b64encode(value).rstrip(b"=").decode()
def _token(key, kid, claims):
 header=_b64(json.dumps({"alg":"RS256","kid":kid}).encode()); payload=_b64(json.dumps(claims).encode())
 signature=key.sign(f"{header}.{payload}".encode(),padding.PKCS1v15(),hashes.SHA256())
 return f"{header}.{payload}.{_b64(signature)}"

@pytest.mark.asyncio
async def test_production_auth_verifies_oidc_and_ignores_spoofed_headers(monkeypatch):
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048); pub=key.public_key().public_numbers(); now=__import__('time').time()
 verifier=auth.OIDCVerifier("https://issuer","atlas"); verifier._keys={"k1":{"kid":"k1","kty":"RSA","n":_b64(pub.n.to_bytes((pub.n.bit_length()+7)//8,'big')),"e":_b64(pub.e.to_bytes((pub.e.bit_length()+7)//8,'big'))}}; verifier._expires=__import__('time').monotonic()+60
 token=_token(key,"k1",{"iss":"https://issuer","aud":"atlas","exp":now+60,"sub":"immutable-user","atlas_tenant":"real-tenant","roles":["atlas-admin"]})
 monkeypatch.setenv("ATLAS_ENV","production"); monkeypatch.setattr(auth,"_production_verifier",lambda:verifier)
 ctx=await auth.require_tenant(f"Bearer {token}","victim","administrator")
 assert ctx.tenant_id=="real-tenant" and ctx.actor_id=="immutable-user" and ctx.has_role("atlas-admin")

@pytest.mark.asyncio
async def test_production_auth_rejects_headers_without_bearer(monkeypatch):
 monkeypatch.setenv("ATLAS_ENV","production")
 with pytest.raises(HTTPException) as error: await auth.require_tenant(None,"victim","administrator")
 assert error.value.status_code==401

@pytest.mark.asyncio
async def test_oidc_rejects_wrong_audience_and_expiration():
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048); pub=key.public_key().public_numbers(); now=__import__('time').time(); verifier=auth.OIDCVerifier("https://issuer","atlas"); verifier._keys={"k":{"kid":"k","kty":"RSA","n":_b64(pub.n.to_bytes((pub.n.bit_length()+7)//8,'big')),"e":_b64(pub.e.to_bytes((pub.e.bit_length()+7)//8,'big'))}}; verifier._expires=__import__('time').monotonic()+60
 for claims in ({"iss":"https://issuer","aud":"wrong","exp":now+60,"sub":"u","atlas_tenant":"t"},{"iss":"https://issuer","aud":"atlas","exp":now-100,"sub":"u","atlas_tenant":"t"}):
  with pytest.raises(HTTPException): await verifier.verify(_token(key,"k",claims))

@pytest.mark.asyncio
async def test_supabase_compatible_es256_oidc_identity(monkeypatch):
 from cryptography.hazmat.primitives.asymmetric import ec
 from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
 key=ec.generate_private_key(ec.SECP256R1());pub=key.public_key().public_numbers();now=__import__('time').time()
 header=_b64(json.dumps({'alg':'ES256','kid':'ec'}).encode());payload=_b64(json.dumps({'iss':'https://project.supabase.co/auth/v1','aud':'authenticated','sub':'owner','atlas_tenant':'tenant-a','exp':now+60}).encode())
 der=key.sign(f'{header}.{payload}'.encode(),ec.ECDSA(hashes.SHA256()));r,s=decode_dss_signature(der);token=f'{header}.{payload}.{_b64(r.to_bytes(32,"big")+s.to_bytes(32,"big"))}'
 verifier=auth.OIDCVerifier('https://project.supabase.co/auth/v1','authenticated');verifier._keys={'ec':{'kid':'ec','kty':'EC','crv':'P-256','x':_b64(pub.x.to_bytes(32,'big')),'y':_b64(pub.y.to_bytes(32,'big'))}};verifier._expires=__import__('time').monotonic()+60
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(auth,'_production_verifier',lambda:verifier)
 ctx=await auth.require_tenant(f'Bearer {token}',None,None)
 assert ctx.tenant_id=='tenant-a' and ctx.actor_id=='owner'
