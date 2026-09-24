"""Trusted timestamps for M10 reviewer attestations.

Problem: a retired reviewer key must stop verifying new signatures, but a
decision that was genuinely signed *before* retirement should stay valid.
Signatures carry no trustworthy time, so each attestation is time-stamped by
an independent authority when it is accepted, and after retirement it
verifies only if that timestamp proves it existed before the cutoff.

Scheme chosen (research 2026-09-24, see TRUSTED_TIMESTAMPS.md):

``rfc3161`` (default)  RFC 3161 token from a public TSA. Default FreeTSA
                       (https://freetsa.org/tsr): free, instant, and verifiable
                       offline against its pinned CA (``tsa/freetsa_cacert.pem``,
                       SHA-256 2151b611...4438; TSA cert 8bfb0305...3467, both
                       as published on freetsa.org). Trust: the TSA's key and
                       clock, not Atlas. Any RFC 3161 TSA works via
                       ``ATLAS_M10_TSA_URL`` + ``ATLAS_M10_TSA_CA_FILE``.
``atlas-local``        Ed25519 record signed by this deployment
                       (``ATLAS_M10_LOCAL_TSA_SEED``). Trust: the Atlas server
                       itself, so it is NOT accepted for post-retirement
                       verification unless ``ATLAS_M10_TRUST_LOCAL_TIMESTAMPS=1``.

Not chosen: OpenTimestamps. Its public calendars are free, but proofs stay
"pending" for hours until a Bitcoin block confirms them, and verifying needs a
local Bitcoin Core node, which a free deployment does not have.

Verification never trusts the database: stored tokens are re-verified
cryptographically (imprint, nonce-free re-check, CMS signed attributes, TSA
signature, TSA certificate chain to the pinned CA, timeStamping EKU, genTime
inside the certificate validity) every time.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
from asn1crypto import cms, tsp
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.x509.oid import ExtendedKeyUsageOID
from sqlalchemy import DateTime, LargeBinary, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal

TSA_DIR = Path(__file__).with_name("tsa")
DEFAULT_TSA_URL = "https://freetsa.org/tsr"
DEFAULT_TSA_CA = TSA_DIR / "freetsa_cacert.pem"
_HASHES = {"sha256": hashes.SHA256, "sha384": hashes.SHA384, "sha512": hashes.SHA512, "sha1": hashes.SHA1}


class TimestampError(ValueError):
    pass


def attestation_digest(attestation: dict[str, Any]) -> bytes:
    """SHA-256 over the canonical attestation *including* its signature."""
    fields = {k: attestation[k] for k in ("reviewer_id", "decision_sha256", "key_id", "signature_base64")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()).digest()


# ---------------------------------------------------------------------------
# RFC 3161
# ---------------------------------------------------------------------------


class Rfc3161Client:
    def __init__(self, url: str | None = None, client: httpx.Client | None = None) -> None:
        self.url = url or os.getenv("ATLAS_M10_TSA_URL", DEFAULT_TSA_URL)
        self._client = client

    def stamp(self, digest: bytes) -> bytes:
        nonce = secrets.randbits(63)
        request = tsp.TimeStampReq({"version": 1, "message_imprint": {"hash_algorithm": {"algorithm": "sha256"}, "hashed_message": digest},
                                    "nonce": nonce, "cert_req": True})
        client = self._client or httpx.Client(timeout=30)
        try:
            response = client.post(self.url, content=request.dump(), headers={"Content-Type": "application/timestamp-query"})
        except httpx.HTTPError as exc:
            raise TimestampError(f"TSA unreachable ({self.url}): {exc.__class__.__name__}") from exc
        finally:
            if self._client is None:
                client.close()
        if response.is_error:
            raise TimestampError(f"TSA returned HTTP {response.status_code}")
        try:
            parsed = tsp.TimeStampResp.load(response.content)
            status = parsed["status"]["status"].native
            if status not in {"granted", "granted_with_mods"}:
                raise TimestampError(f"TSA refused the request ({status})")
            tst = parsed["time_stamp_token"]["content"]["encap_content_info"]["content"].parsed
            if tst["nonce"].native != nonce:
                raise TimestampError("TSA response nonce does not match the request (possible replay)")
        except TimestampError:
            raise
        except Exception as exc:
            raise TimestampError("TSA response is not a valid RFC 3161 TimeStampResp") from exc
        return parsed["time_stamp_token"].dump()


@dataclass(frozen=True)
class TsaTrust:
    ca_pem: bytes
    name: str = "freetsa"

    @classmethod
    def configured(cls) -> "TsaTrust":
        path = Path(os.getenv("ATLAS_M10_TSA_CA_FILE", str(DEFAULT_TSA_CA)))
        return cls(path.read_bytes(), name=os.getenv("ATLAS_M10_TSA_NAME", "freetsa" if path == DEFAULT_TSA_CA else path.stem))

    def roots(self) -> list[x509.Certificate]:
        return x509.load_pem_x509_certificates(self.ca_pem)


def _verify_sig(public_key: Any, signature: bytes, data: bytes, hash_name: str) -> None:
    algorithm = _HASHES[hash_name]()
    if isinstance(public_key, ec.EllipticCurvePublicKey):
        public_key.verify(signature, data, ec.ECDSA(algorithm))
    elif isinstance(public_key, rsa.RSAPublicKey):
        public_key.verify(signature, data, padding.PKCS1v15(), algorithm)
    else:
        raise TimestampError(f"unsupported TSA key type {type(public_key).__name__}")


def _digest(hash_name: str, data: bytes) -> bytes:
    h = hashes.Hash(_HASHES[hash_name]())
    h.update(data)
    return h.finalize()


def verify_rfc3161(token_der: bytes, digest: bytes, trust: TsaTrust) -> datetime:
    """Fully verify a TimeStampToken over ``digest``; return its genTime (UTC)."""
    try:
        token = cms.ContentInfo.load(token_der)
        signed = token["content"]
        encap = signed["encap_content_info"]
        if encap["content_type"].native != "tst_info":
            raise TimestampError("token does not contain TSTInfo")
        tst_bytes = encap["content"].contents
        tst = encap["content"].parsed
        imprint = tst["message_imprint"]
        hash_name = imprint["hash_algorithm"]["algorithm"].native
        if hash_name != "sha256" or imprint["hashed_message"].native != digest:
            raise TimestampError("timestamp does not cover this attestation")
        gen_time = tst["gen_time"].native.astimezone(timezone.utc)
        signer = signed["signer_infos"][0]
        sid = signer["sid"].chosen
        certs = [c.chosen for c in (signed["certificates"] or []) if c.name == "certificate"]
        leaf_asn1 = next((c for c in certs if c.issuer == sid["issuer"] and c.serial_number == sid["serial_number"].native), None)
        if leaf_asn1 is None:
            raise TimestampError("TSA signing certificate is not included in the token")
        leaf = x509.load_der_x509_certificate(leaf_asn1.dump())
        attrs = signer["signed_attrs"]
        digest_alg = signer["digest_algorithm"]["algorithm"].native
        attr_map = {a["type"].native: a["values"][0] for a in attrs}
        if attr_map.get("content_type") is None or attr_map["content_type"].native != "tst_info":
            raise TimestampError("signed attributes lack the TSTInfo content type")
        if attr_map.get("message_digest") is None or attr_map["message_digest"].native != _digest(digest_alg, tst_bytes):
            raise TimestampError("signed attributes do not match the TSTInfo")
        signed_bytes = attrs.untag().dump(force=True)
        try:
            _verify_sig(leaf.public_key(), signer["signature"].native, signed_bytes, digest_alg)
        except InvalidSignature as exc:
            raise TimestampError("TSA signature does not verify") from exc
        try:
            eku = leaf.extensions.get_extension_for_class(x509.ExtendedKeyUsage)
        except x509.ExtensionNotFound as exc:
            raise TimestampError("TSA certificate lacks the timeStamping extended key usage") from exc
        if ExtendedKeyUsageOID.TIME_STAMPING not in eku.value:
            raise TimestampError("TSA certificate is not authorised for timestamping")
        if not (leaf.not_valid_before_utc <= gen_time <= leaf.not_valid_after_utc):
            raise TimestampError("genTime is outside the TSA certificate validity")
        chained = False
        for root in trust.roots():
            if leaf.fingerprint(hashes.SHA256()) == root.fingerprint(hashes.SHA256()):
                chained = True
                break
            try:
                leaf.verify_directly_issued_by(root)
                chained = True
                break
            except (ValueError, TypeError, InvalidSignature):
                continue
        if not chained:
            raise TimestampError(f"TSA certificate does not chain to the trusted {trust.name} CA")
        return gen_time
    except TimestampError:
        raise
    except Exception as exc:
        raise TimestampError(f"malformed timestamp token: {exc.__class__.__name__}") from exc


# ---------------------------------------------------------------------------
# Atlas-local signed timestamp record (lower trust)
# ---------------------------------------------------------------------------


class LocalTimestamper:
    def __init__(self, seed_b64: str | None = None, clock: Callable[[], datetime] | None = None) -> None:
        seed = seed_b64 or os.getenv("ATLAS_M10_LOCAL_TSA_SEED")
        if not seed:
            raise TimestampError("ATLAS_M10_LOCAL_TSA_SEED is not configured")
        self._key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(seed))
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def public_key(self) -> bytes:
        from cryptography.hazmat.primitives import serialization
        return self._key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    def stamp(self, digest: bytes) -> bytes:
        record = {"scheme": "atlas-local", "digest_sha256": digest.hex(), "gen_time": self._clock().isoformat()}
        body = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        return json.dumps({"record": record, "signature": base64.b64encode(self._key.sign(body)).decode()}).encode()


def verify_local(token: bytes, digest: bytes, public_key: bytes) -> datetime:
    try:
        envelope = json.loads(token)
        record = envelope["record"]
        body = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        Ed25519PublicKey.from_public_bytes(public_key).verify(base64.b64decode(envelope["signature"]), body)
    except (InvalidSignature, KeyError, ValueError, TypeError) as exc:
        raise TimestampError("local timestamp record does not verify") from exc
    if record.get("digest_sha256") != digest.hex():
        raise TimestampError("timestamp does not cover this attestation")
    return datetime.fromisoformat(record["gen_time"]).astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Storage + service
# ---------------------------------------------------------------------------


class AttestationTimestampRow(Base):
    __tablename__ = "m10_attestation_timestamps"
    __table_args__ = (UniqueConstraint("tenant_id", "attestation_sha256", "scheme"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    reviewer_id: Mapped[str] = mapped_column(String(200))
    key_id: Mapped[str] = mapped_column(String(200))
    attestation_sha256: Mapped[str] = mapped_column(String(64), index=True)
    scheme: Mapped[str] = mapped_column(String(30))
    authority: Mapped[str] = mapped_column(String(200))
    token: Mapped[bytes] = mapped_column(LargeBinary)
    gen_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AttestationTimestamps:
    def __init__(self, tenant_id: str, sessions: sessionmaker = SessionLocal, *, rfc3161: Rfc3161Client | None = None,
                 trust: TsaTrust | None = None, local: LocalTimestamper | None = None, trust_local: bool | None = None,
                 scheme: str | None = None) -> None:
        self.tenant_id, self.sessions = tenant_id, sessions
        self.scheme = (scheme or os.getenv("ATLAS_M10_TIMESTAMP_SCHEME", "rfc3161")).lower()
        self.rfc3161 = rfc3161
        self._trust = trust
        self.local = local
        self.trust_local = trust_local if trust_local is not None else os.getenv("ATLAS_M10_TRUST_LOCAL_TIMESTAMPS") == "1"
        bind = getattr(sessions, "kw", {}).get("bind")
        if bind is not None:
            Base.metadata.create_all(bind, tables=[AttestationTimestampRow.__table__])

    @property
    def trust(self) -> TsaTrust:
        if self._trust is None:
            self._trust = TsaTrust.configured()
        return self._trust

    def _local(self) -> LocalTimestamper:
        if self.local is None:
            self.local = LocalTimestamper()
        return self.local

    def stamp(self, attestation: dict[str, Any]) -> dict[str, Any]:
        """Timestamp one attestation (idempotent per scheme) and store the token."""
        if self.scheme in {"off", "none"}:
            return {"timestamped": False, "reason": "timestamping disabled (ATLAS_M10_TIMESTAMP_SCHEME=off)"}
        digest = attestation_digest(attestation)
        hex_digest = digest.hex()
        with self.sessions() as db:
            existing = db.scalar(select(AttestationTimestampRow).where(AttestationTimestampRow.tenant_id == self.tenant_id,
                                AttestationTimestampRow.attestation_sha256 == hex_digest, AttestationTimestampRow.scheme == self.scheme))
            if existing is not None:
                return {"timestamped": True, "scheme": existing.scheme, "authority": existing.authority,
                        "gen_time": _aware(existing.gen_time), "attestation_sha256": hex_digest, "reused": True}
        if self.scheme == "rfc3161":
            client = self.rfc3161 or Rfc3161Client()
            token = client.stamp(digest)
            gen_time = verify_rfc3161(token, digest, self.trust)  # never store an unverifiable token
            authority = f"rfc3161:{self.trust.name}"
        elif self.scheme == "atlas-local":
            local = self._local()
            token = local.stamp(digest)
            gen_time = verify_local(token, digest, local.public_key())
            authority = "atlas-local"
        else:
            raise TimestampError(f"unsupported timestamp scheme {self.scheme!r}")
        with self.sessions.begin() as db:
            db.add(AttestationTimestampRow(tenant_id=self.tenant_id, reviewer_id=attestation["reviewer_id"], key_id=attestation["key_id"],
                                           attestation_sha256=hex_digest, scheme=self.scheme, authority=authority, token=token,
                                           gen_time=gen_time, created_at=datetime.now(timezone.utc)))
        return {"timestamped": True, "scheme": self.scheme, "authority": authority, "gen_time": gen_time,
                "attestation_sha256": hex_digest, "reused": False}

    def proven_time(self, attestation: dict[str, Any]) -> tuple[datetime, str] | None:
        """Earliest cryptographically re-verified, trusted timestamp for this attestation."""
        digest = attestation_digest(attestation)
        with self.sessions() as db:
            rows = list(db.scalars(select(AttestationTimestampRow).where(AttestationTimestampRow.tenant_id == self.tenant_id,
                        AttestationTimestampRow.attestation_sha256 == digest.hex())))
        proven: list[tuple[datetime, str]] = []
        for row in rows:
            try:
                if row.scheme == "rfc3161":
                    proven.append((verify_rfc3161(row.token, digest, self.trust), row.authority))
                elif row.scheme == "atlas-local" and self.trust_local:
                    proven.append((verify_local(row.token, digest, self._local().public_key()), row.authority))
            except TimestampError:
                continue  # a bad stored token proves nothing
        return min(proven) if proven else None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
