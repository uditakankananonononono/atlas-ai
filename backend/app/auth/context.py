"""Authenticated tenant context.

Development accepts explicit headers for local work. Production accepts only a
verified OIDC bearer token; client-supplied tenant/actor headers are ignored.
"""
from __future__ import annotations
import asyncio
import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric import padding, rsa, ec
from cryptography.hazmat.primitives import hashes
from fastapi import Header, HTTPException


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    actor_id: str
    roles: frozenset[str] = frozenset()

    def has_role(self, *allowed: str) -> bool:
        return bool(self.roles.intersection(allowed))


def _decode(segment: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    except Exception as exc:
        raise HTTPException(401, "malformed bearer token") from exc


class OIDCVerifier:
    """RS256 OIDC verification with discovery/JWKS caching and key rotation."""
    def __init__(self, issuer: str, audience: str, *, tenant_claim: str = "atlas_tenant", cache_seconds: int = 300):
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self.tenant_claim = tenant_claim
        self.cache_seconds = cache_seconds
        self._keys: dict[str, dict[str, Any]] = {}
        self._expires = 0.0
        self._lock = asyncio.Lock()

    async def _refresh(self) -> None:
        if not self.issuer.startswith("https://") and os.getenv("ATLAS_ALLOW_INSECURE_OIDC") != "1":
            raise HTTPException(503, "OIDC issuer must use HTTPS")
        async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
            discovery = await client.get(f"{self.issuer}/.well-known/openid-configuration")
            discovery.raise_for_status()
            document = discovery.json()
            if document.get("issuer", "").rstrip("/") != self.issuer:
                raise HTTPException(503, "OIDC discovery issuer mismatch")
            jwks_uri = str(document.get("jwks_uri", ""))
            if not jwks_uri.startswith("https://") and os.getenv("ATLAS_ALLOW_INSECURE_OIDC") != "1":
                raise HTTPException(503, "OIDC JWKS URI must use HTTPS")
            jwks = await client.get(jwks_uri)
            jwks.raise_for_status()
            keys = jwks.json().get("keys", [])
        self._keys = {str(k["kid"]): k for k in keys if k.get("kid") and k.get("kty") in {"RSA", "EC"} and k.get("use", "sig") == "sig"}
        if not self._keys:
            raise HTTPException(503, "OIDC provider returned no signing keys")
        self._expires = time.monotonic() + self.cache_seconds

    async def verify(self, token: str) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(401, "malformed bearer token")
        try:
            header = json.loads(_decode(parts[0])); claims = json.loads(_decode(parts[1]))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPException(401, "malformed bearer token") from exc
        if header.get("alg") not in {"RS256", "ES256"} or not header.get("kid"):
            raise HTTPException(401, "unsupported bearer-token signature")
        kid = str(header["kid"])
        if time.monotonic() >= self._expires or kid not in self._keys:
            async with self._lock:
                if time.monotonic() >= self._expires or kid not in self._keys:
                    try:
                        await self._refresh()
                    except HTTPException:
                        raise
                    except (httpx.HTTPError, ValueError) as exc:
                        raise HTTPException(503, "OIDC signing keys unavailable") from exc
        jwk = self._keys.get(kid)
        if not jwk:
            raise HTTPException(401, "unknown bearer-token signing key")
        try:
            signing_input = f"{parts[0]}.{parts[1]}".encode()
            signature = _decode(parts[2])
            if header["alg"] == "RS256" and jwk.get("kty") == "RSA":
                n = int.from_bytes(_decode(str(jwk["n"])), "big"); e = int.from_bytes(_decode(str(jwk["e"])), "big")
                rsa.RSAPublicNumbers(e, n).public_key().verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
            elif header["alg"] == "ES256" and jwk.get("kty") == "EC" and jwk.get("crv") == "P-256":
                if len(signature) != 64:
                    raise ValueError("invalid ES256 signature length")
                from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
                der = encode_dss_signature(int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:], "big"))
                x = int.from_bytes(_decode(str(jwk["x"])), "big"); y = int.from_bytes(_decode(str(jwk["y"])), "big")
                ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key().verify(der, signing_input, ec.ECDSA(hashes.SHA256()))
            else:
                raise ValueError("token algorithm does not match signing key")
        except Exception as exc:
            raise HTTPException(401, "invalid bearer-token signature") from exc
        now = int(time.time()); leeway = int(os.getenv("ATLAS_OIDC_CLOCK_SKEW_SECONDS", "30"))
        aud = claims.get("aud", []); audiences = {aud} if isinstance(aud, str) else set(aud) if isinstance(aud, list) else set()
        if str(claims.get("iss", "")).rstrip("/") != self.issuer or self.audience not in audiences:
            raise HTTPException(401, "bearer-token issuer or audience rejected")
        if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] < now - leeway:
            raise HTTPException(401, "bearer token expired")
        if isinstance(claims.get("nbf"), (int, float)) and claims["nbf"] > now + leeway:
            raise HTTPException(401, "bearer token not yet valid")
        if not isinstance(claims.get("sub"), str) or not claims["sub"].strip():
            raise HTTPException(401, "bearer token has no immutable subject")
        return claims


_verifier: OIDCVerifier | None = None
_verifier_key: tuple[str, str, str] | None = None

def _production_verifier() -> OIDCVerifier:
    global _verifier, _verifier_key
    issuer = os.environ.get("ATLAS_OIDC_ISSUER", "").strip(); audience = os.environ.get("ATLAS_OIDC_AUDIENCE", "").strip()
    claim = os.environ.get("ATLAS_OIDC_TENANT_CLAIM", "atlas_tenant").strip()
    if not issuer or not audience or not claim:
        raise HTTPException(503, "production OIDC configuration is incomplete")
    key = (issuer, audience, claim)
    if _verifier is None or _verifier_key != key:
        _verifier, _verifier_key = OIDCVerifier(issuer, audience, tenant_claim=claim), key
    return _verifier


async def require_tenant(
    authorization: str | None = Header(default=None),
    x_atlas_tenant: str | None = Header(default=None),
    x_atlas_actor: str | None = Header(default=None),
) -> TenantContext:
    if os.getenv("ATLAS_ENV", "development") != "production":
        return TenantContext(x_atlas_tenant or "local", x_atlas_actor or "local-user")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "OIDC bearer token required")
    verifier = _production_verifier(); claims = await verifier.verify(authorization[7:].strip())
    tenant = claims.get(verifier.tenant_claim)
    if not isinstance(tenant, str) or not tenant.strip():
        raise HTTPException(403, "authenticated subject is not mapped to an Atlas tenant")
    raw_roles = claims.get("roles", [])
    roles = frozenset(str(x) for x in raw_roles) if isinstance(raw_roles, list) else frozenset(str(raw_roles).split())
    return TenantContext(tenant.strip(), claims["sub"].strip(), roles)


def require_admin(tenant: TenantContext = __import__("fastapi").Depends(require_tenant)) -> TenantContext:
    if not tenant.has_role("atlas-admin"):
        raise HTTPException(403, "Atlas administrator role required")
    return tenant


def require_worker(tenant: TenantContext = __import__("fastapi").Depends(require_tenant)) -> TenantContext:
    if not tenant.has_role("atlas-worker", "atlas-admin"):
        raise HTTPException(403, "Atlas worker role required")
    return tenant
