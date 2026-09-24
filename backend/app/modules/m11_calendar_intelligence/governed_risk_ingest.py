"""Governed risk-evidence ingest (M11 enhancement).

One call runs the whole chain that used to be separate endpoints:

1. resolve the snapshot's (provider, key_id) in the tenant's provider-key
   registry; unknown, inactive or retired keys fail closed;
2. verify the Ed25519 signature over the canonical snapshot metadata (same
   canonical form as ``asymmetric_risk_evidence``);
3. fetch the source bytes through a configured provider adapter and check they
   hash to the signed ``content_sha256``;
4. persist the bytes immutably in ``RiskSnapshotStore``.

``HttpsProviderRetriever`` is the real adapter: it is configured from
``ATLAS_M11_RISK_PROVIDERS`` (JSON ``{"provider": {"hosts": [...],
"token_env": "ENV_NAME"}}``), only fetches https URLs on that provider's
listed hosts after the public-address guard, sends the bearer token read from
the named env var (never stored or echoed), does not follow redirects, and caps
size. Unconfigured providers fail closed. Read-only: nothing changes events,
cancels, or spends.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Protocol
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import select

from .asymmetric_risk_evidence import SignedRiskSnapshot
from .provider_key_registry import RiskProviderKeyRegistry, RiskProviderKeyRow
from .risk_snapshot_store import RiskSnapshotStore

MAX_BYTES = 10 * 1024 * 1024


class IngestRejected(ValueError):
    pass


class ProviderRetriever(Protocol):
    def fetch(self, provider: str, source_uri: str) -> bytes: ...


def provider_config() -> dict:
    raw = os.environ.get("ATLAS_M11_RISK_PROVIDERS", "").strip()
    if not raw:
        return {}
    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise IngestRejected("ATLAS_M11_RISK_PROVIDERS is not valid JSON") from exc
    return cfg if isinstance(cfg, dict) else {}


class HttpsProviderRetriever:
    def __init__(self, config: dict | None = None, transport=None):
        self.config = provider_config() if config is None else config
        self.transport = transport

    def fetch(self, provider: str, source_uri: str) -> bytes:
        import httpx
        from app.modules.m13_browser_agent.security import validate_public_url
        cfg = self.config.get(provider)
        if not cfg:
            raise IngestRejected(f"no retrieval adapter configured for provider '{provider}'")
        parts = urlsplit(source_uri)
        if parts.scheme != "https":
            raise IngestRejected("provider sources must be https")
        hosts = {h.lower() for h in cfg.get("hosts", [])}
        if (parts.hostname or "").lower() not in hosts:
            raise IngestRejected(f"host '{parts.hostname}' is not listed for provider '{provider}'")
        headers = {}
        token_env = cfg.get("token_env")
        if token_env:
            token = os.environ.get(token_env)
            if not token:
                raise IngestRejected(f"provider '{provider}' needs env {token_env}, which is not set")
            headers["Authorization"] = f"Bearer {token}"
        if self.transport is None:
            validate_public_url(source_uri, allowed_hosts=hosts)
        with httpx.Client(follow_redirects=False, timeout=20, transport=self.transport) as client, \
                client.stream("GET", source_uri, headers=headers) as resp:
            if resp.status_code != 200:
                raise IngestRejected(f"provider returned HTTP {resp.status_code}")
            out = bytearray()
            for chunk in resp.iter_bytes():
                out += chunk
                if len(out) > MAX_BYTES:
                    raise IngestRejected("source larger than 10 MB")
        return bytes(out)


def _governed_key(registry: RiskProviderKeyRegistry, provider: str, key_id: str) -> RiskProviderKeyRow:
    with registry.sessions() as db:
        row = db.scalar(select(RiskProviderKeyRow).where(RiskProviderKeyRow.tenant_id == registry.tenant_id,
                                                         RiskProviderKeyRow.provider == provider,
                                                         RiskProviderKeyRow.key_id == key_id))
    if row is None:
        raise IngestRejected(f"key {provider}/{key_id} is not registered for this tenant")
    if not row.active or row.retired_at is not None:
        raise IngestRejected(f"key {provider}/{key_id} is retired")
    return row


def ingest_signed_snapshot(snap: SignedRiskSnapshot, *, registry: RiskProviderKeyRegistry,
                           retriever: ProviderRetriever, store: RiskSnapshotStore) -> dict:
    key_row = _governed_key(registry, snap.provider, snap.key_id)
    canonical = json.dumps(snap.model_dump(mode="json", exclude={"signature_base64"}), sort_keys=True,
                           separators=(",", ":")).encode()
    try:
        sig = base64.b64decode(snap.signature_base64, validate=True)
        Ed25519PublicKey.from_public_bytes(key_row.public_key).verify(sig, canonical)
    except InvalidSignature as exc:
        raise IngestRejected(f"signature does not verify for {snap.evidence_id}") from exc
    except ValueError as exc:
        raise IngestRejected("signature is not valid base64") from exc
    data = retriever.fetch(snap.provider, snap.source_uri)
    if not data:
        raise IngestRejected("provider returned empty bytes")
    actual = hashlib.sha256(data).hexdigest()
    if actual != snap.content_sha256:
        raise IngestRejected("fetched bytes do not match the signed content hash")
    try:
        row = store.persist(snap.source_uri, actual, data)
    except ValueError as exc:
        raise IngestRejected(str(exc)) from exc
    return {"ingested": True, "evidence_id": snap.evidence_id, "kind": snap.kind, "provider": snap.provider,
            "key_id": snap.key_id, "key_fingerprint_sha256": key_row.fingerprint_sha256, "content_sha256": actual,
            "byte_count": len(data), "persisted_at": row.persisted_at.isoformat(),
            "receipt_sha256": hashlib.sha256(canonical + sig).hexdigest(),
            "boundary": "Signed by a registered, unretired provider key and byte-identical to what was signed. It does not prove the route or policy is true, change events, cancel, or spend."}
