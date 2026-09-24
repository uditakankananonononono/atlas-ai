"""Durable contradiction decision revisions (M09 enhancement).

- ``RevisionStore.append`` writes one revision per transaction and only when its
  ``previous_revision_sha256`` equals the stored head for that claim
  (compare-and-append). A unique (tenant, claim, seq) index turns a concurrent
  append into a conflict instead of a fork.
- The revision's ``actor_id`` must be the authenticated actor. When the actor has
  registered an Ed25519 public key, the revision must carry a signature over its
  revision hash, verified before the row is written. Registered keys are
  append-only; a signature proves key possession, not real-world identity.
- ``verify_sources`` fetches each snapshot's ``source_uri`` (public http(s) only,
  no redirects, size cap) and compares SHA-256 of the bytes to the captured hash.
  A mismatch means the source changed or was captured wrong; it says nothing
  about which claim is true.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine
from .contradiction_revisions import DecisionRevision

MAX_SOURCE_BYTES = 20 * 1024 * 1024


class RevisionConflict(ValueError):
    pass


class RevisionRejected(ValueError):
    pass


class RevisionRow(Base):
    __tablename__ = "m09_contradiction_revisions"
    __table_args__ = (UniqueConstraint("tenant_id", "claim_norm", "seq", name="uq_m09_rev_seq"),
                      UniqueConstraint("tenant_id", "revision_id", name="uq_m09_rev_id"))
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    claim_norm: Mapped[str] = mapped_column(String(500), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    revision_id: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64))
    previous_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    signature_b64: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ActorKeyRow(Base):
    __tablename__ = "m09_actor_keys"
    __table_args__ = (UniqueConstraint("tenant_id", "actor_id", "key_id", name="uq_m09_actor_key"),)
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    actor_id: Mapped[str] = mapped_column(String(120), index=True)
    key_id: Mapped[str] = mapped_column(String(64))
    public_key_b64: Mapped[str] = mapped_column(Text)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def revision_sha256(r: DecisionRevision) -> str:
    """Same canonical digest as ``verify_revision_chain``."""
    return hashlib.sha256(json.dumps(r.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _norm(claim: str) -> str:
    return claim.casefold().strip()


def _load_key(b64: str) -> Ed25519PublicKey:
    try:
        raw = base64.b64decode(b64, validate=True)
        return Ed25519PublicKey.from_public_bytes(raw)
    except Exception as exc:  # noqa: BLE001 - any decode failure is a bad key
        raise RevisionRejected("public key must be base64 of a 32-byte Ed25519 key") from exc


class RevisionStore:
    def __init__(self, tenant_id: str, actor_id: str, session_factory: sessionmaker = SessionLocal,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc), create_schema: bool = True):
        self.tenant_id, self.actor_id, self.sessions, self.clock = tenant_id, actor_id, session_factory, clock
        if create_schema and session_factory is SessionLocal:
            Base.metadata.create_all(engine, tables=[RevisionRow.__table__, ActorKeyRow.__table__])

    # -- actor keys -----------------------------------------------------------
    def register_key(self, public_key_b64: str) -> dict:
        key = _load_key(public_key_b64)
        raw = base64.b64decode(public_key_b64)
        key_id = hashlib.sha256(raw).hexdigest()[:32]
        del key
        with self.sessions.begin() as db:
            exists = db.scalar(select(ActorKeyRow).where(ActorKeyRow.tenant_id == self.tenant_id,
                                                         ActorKeyRow.actor_id == self.actor_id, ActorKeyRow.key_id == key_id))
            if not exists:
                db.add(ActorKeyRow(tenant_id=self.tenant_id, actor_id=self.actor_id, key_id=key_id,
                                   public_key_b64=public_key_b64, registered_at=self.clock()))
        return {"actor_id": self.actor_id, "key_id": key_id}

    def _keys(self, db, actor_id: str) -> list[ActorKeyRow]:
        return list(db.scalars(select(ActorKeyRow).where(ActorKeyRow.tenant_id == self.tenant_id, ActorKeyRow.actor_id == actor_id)))

    # -- revisions ------------------------------------------------------------
    def append(self, revision: DecisionRevision, signature_b64: str | None = None) -> dict:
        if revision.actor_id != self.actor_id:
            raise RevisionRejected("revision actor_id must be the authenticated actor")
        digest, claim = revision_sha256(revision), _norm(revision.claim_key)
        try:
            with self.sessions.begin() as db:
                head = db.scalar(select(RevisionRow).where(RevisionRow.tenant_id == self.tenant_id, RevisionRow.claim_norm == claim)
                                 .order_by(RevisionRow.seq.desc()).limit(1))
                expected = head.sha256 if head else None
                if revision.previous_revision_sha256 != expected:
                    raise RevisionConflict(f"stale head: expected previous_revision_sha256={expected}")
                key_id = None
                keys = self._keys(db, self.actor_id)
                if keys:
                    if not signature_b64:
                        raise RevisionRejected("actor has a registered key; revision must be signed")
                    try:
                        sig = base64.b64decode(signature_b64, validate=True)
                    except Exception as exc:  # noqa: BLE001
                        raise RevisionRejected("signature is not base64") from exc
                    for k in keys:
                        try:
                            _load_key(k.public_key_b64).verify(sig, digest.encode())
                            key_id = k.key_id
                            break
                        except InvalidSignature:
                            continue
                    if key_id is None:
                        raise RevisionRejected("signature does not verify against the actor's registered keys")
                elif signature_b64:
                    raise RevisionRejected("signature supplied but the actor has no registered key")
                row = RevisionRow(tenant_id=self.tenant_id, claim_norm=claim, seq=(head.seq + 1) if head else 1,
                                  revision_id=revision.revision_id, sha256=digest, previous_sha256=expected,
                                  payload=revision.model_dump(mode="json"), signature_b64=signature_b64, key_id=key_id,
                                  stored_at=self.clock())
                db.add(row)
                db.flush()
                seq = row.seq
        except IntegrityError as exc:
            raise RevisionConflict("concurrent append or duplicate revision_id; re-read the head and retry") from exc
        return {"claim_key": revision.claim_key, "seq": seq, "sha256": digest, "signed_key_id": key_id}

    def chain(self, claim_key: str) -> dict:
        with self.sessions() as db:
            rows = list(db.scalars(select(RevisionRow).where(RevisionRow.tenant_id == self.tenant_id,
                                                             RevisionRow.claim_norm == _norm(claim_key)).order_by(RevisionRow.seq)))
            keys = {k.key_id: k.public_key_b64 for k in db.scalars(select(ActorKeyRow).where(ActorKeyRow.tenant_id == self.tenant_id))}
        if not rows:
            raise LookupError("no revisions for this claim")
        problems, prev = [], None
        for r in rows:
            rev = DecisionRevision.model_validate(r.payload)
            if revision_sha256(rev) != r.sha256:
                problems.append(f"seq {r.seq}: stored payload no longer matches its hash")
            if r.previous_sha256 != prev or rev.previous_revision_sha256 != prev:
                problems.append(f"seq {r.seq}: chain break")
            if r.key_id:
                try:
                    _load_key(keys[r.key_id]).verify(base64.b64decode(r.signature_b64), r.sha256.encode())
                except (KeyError, InvalidSignature):
                    problems.append(f"seq {r.seq}: signature no longer verifies")
            prev = r.sha256
        return {"claim_key": rows[-1].payload["claim_key"], "revision_count": len(rows), "head_sha256": prev,
                "valid": not problems, "problems": problems,
                "revisions": [{"seq": r.seq, "revision_id": r.revision_id, "sha256": r.sha256, "actor_id": r.payload["actor_id"],
                               "signed_key_id": r.key_id, "action": r.payload["action"]} for r in rows],
                "latest_decision": rows[-1].payload}


# -- source bytes -----------------------------------------------------------------
def _http_fetch(url: str) -> bytes:
    import httpx
    from app.modules.m13_browser_agent.security import validate_public_url
    validate_public_url(url)
    with httpx.Client(follow_redirects=False, timeout=20) as client, client.stream("GET", url) as resp:
        if resp.status_code != 200:
            raise RevisionRejected(f"HTTP {resp.status_code}")
        out = bytearray()
        for chunk in resp.iter_bytes():
            out += chunk
            if len(out) > MAX_SOURCE_BYTES:
                raise RevisionRejected("source larger than 20 MB")
        return bytes(out)


def verify_sources(revision: DecisionRevision, source_uris: dict[str, str],
                   fetch: Callable[[str], bytes] = _http_fetch) -> dict:
    results = []
    for snap in revision.source_snapshots:
        uri = source_uris.get(snap.evidence_id)
        if not uri:
            results.append({"evidence_id": snap.evidence_id, "status": "no_uri"})
            continue
        try:
            actual = hashlib.sha256(fetch(uri)).hexdigest()
        except Exception as exc:  # noqa: BLE001 - report per source, keep going
            results.append({"evidence_id": snap.evidence_id, "uri": uri, "status": "unreachable", "error": str(exc)[:300]})
            continue
        results.append({"evidence_id": snap.evidence_id, "uri": uri, "captured_sha256": snap.content_sha256, "fetched_sha256": actual,
                        "status": "match" if actual == snap.content_sha256 else "mismatch"})
    return {"revision_id": revision.revision_id, "all_match": all(r["status"] == "match" for r in results), "sources": results,
            "boundary": "A match shows the bytes at that URL now equal the captured snapshot. It does not show the source is authentic or that its claim is true."}
